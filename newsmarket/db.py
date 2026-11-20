"""Banco DuckDB único do projeto: esquema e gravação idempotente."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ESQUEMA = """
CREATE TABLE IF NOT EXISTS precos (
    ticker              VARCHAR NOT NULL,
    data                DATE    NOT NULL,
    abertura            DOUBLE,
    maxima              DOUBLE,
    minima              DOUBLE,
    fechamento          DOUBLE,
    fechamento_ajustado DOUBLE,   -- ajustado por proventos: use este para retornos
    volume              BIGINT,
    dividendos          DOUBLE,   -- provento pago na data-com (FIIs pagam todo mês)
    PRIMARY KEY (ticker, data)
);

CREATE TABLE IF NOT EXISTS noticias (
    id            VARCHAR PRIMARY KEY,   -- hash da URL
    titulo        VARCHAR NOT NULL,
    resumo        VARCHAR,
    url           VARCHAR,
    fonte         VARCHAR,
    publicada_em  TIMESTAMP,            -- horário de Brasília, sem fuso
    coletada_em   TIMESTAMP DEFAULT current_timestamp
);

-- Uma notícia pode citar vários ativos.
CREATE TABLE IF NOT EXISTS noticia_ativo (
    noticia_id VARCHAR NOT NULL,
    ticker     VARCHAR NOT NULL,
    PRIMARY KEY (noticia_id, ticker)
);

CREATE TABLE IF NOT EXISTS sentimento (
    noticia_id VARCHAR PRIMARY KEY,
    score      DOUBLE,     -- de -1 (muito negativa) a +1 (muito positiva)
    metodo     VARCHAR
);

CREATE TABLE IF NOT EXISTS predicoes (
    ticker      VARCHAR   NOT NULL,
    data_ref    DATE      NOT NULL,   -- último pregão usado
    horizonte   INTEGER   NOT NULL,   -- pregões à frente
    prob_alta   DOUBLE,
    sinal       VARCHAR,              -- ALTA / BAIXA / NEUTRO
    modelo      VARCHAR,
    acuracia_validacao DOUBLE,
    gerada_em   TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (ticker, data_ref, horizonte)
);
"""


def conectar(caminho: str | Path) -> duckdb.DuckDBPyConnection:
    """Abre (e cria, se preciso) o banco e garante o esquema."""
    caminho = Path(caminho)
    if str(caminho) != ":memory:":
        caminho.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(caminho))
    con.execute(ESQUEMA)
    return con


def upsert(con: duckdb.DuckDBPyConnection, tabela: str, df: pd.DataFrame) -> int:
    """Insere ou substitui linhas pela chave primária. Retorna o nº de linhas enviadas."""
    if df is None or df.empty:
        return 0
    cols = ", ".join(df.columns)
    con.register("_staging", df)
    try:
        con.execute(f"INSERT OR REPLACE INTO {tabela} ({cols}) SELECT {cols} FROM _staging").fetchall()
    finally:
        con.unregister("_staging")
    return len(df)


def inserir_novos(con: duckdb.DuckDBPyConnection, tabela: str, df: pd.DataFrame) -> int:
    """Insere ignorando linhas cuja chave já existe. Retorna quantas eram novas."""
    if df is None or df.empty:
        return 0
    antes = con.execute(f"SELECT count(*) FROM {tabela}").fetchall()[0][0]
    cols = ", ".join(df.columns)
    con.register("_staging", df)
    try:
        con.execute(f"INSERT OR IGNORE INTO {tabela} ({cols}) SELECT {cols} FROM _staging").fetchall()
    finally:
        con.unregister("_staging")
    return con.execute(f"SELECT count(*) FROM {tabela}").fetchall()[0][0] - antes
