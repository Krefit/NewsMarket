"""Coleta de preços diários da B3 via Yahoo Finance (yfinance). Não precisa de chave."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from ..config import ticker_yahoo
from ..db import upsert

log = logging.getLogger(__name__)

COLUNAS = ["ticker", "data", "abertura", "maxima", "minima", "fechamento",
           "fechamento_ajustado", "volume", "dividendos"]

_RENOMEAR = {
    "Open": "abertura", "High": "maxima", "Low": "minima", "Close": "fechamento",
    "Adj Close": "fechamento_ajustado", "Volume": "volume", "Dividends": "dividendos",
}


def normalizar(bruto: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Converte o DataFrame do yfinance (índice = data) para o esquema da tabela `precos`."""
    if bruto is None or bruto.empty:
        return pd.DataFrame(columns=COLUNAS)
    df = bruto.rename(columns=_RENOMEAR).copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df["data"] = idx.normalize().date
    df["ticker"] = ticker
    if "fechamento_ajustado" not in df:
        df["fechamento_ajustado"] = df["fechamento"]
    if "dividendos" not in df:
        df["dividendos"] = 0.0
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    df = df.dropna(subset=["fechamento"])
    return df[COLUNAS].drop_duplicates(subset=["ticker", "data"], keep="last").reset_index(drop=True)


def baixar(ticker: str, inicio: date | None = None) -> pd.DataFrame:
    """Baixa o histórico de um ticker B3 (MXRF11) a partir de `inicio` (ou todo o histórico)."""
    import yfinance as yf

    t = yf.Ticker(ticker_yahoo(ticker))
    if inicio is None:
        bruto = t.history(period="max", auto_adjust=False, actions=True)
    else:
        bruto = t.history(start=inicio.isoformat(), auto_adjust=False, actions=True)
    return normalizar(bruto, ticker)


def ultima_data(con, ticker: str) -> date | None:
    r = con.execute("SELECT max(data) FROM precos WHERE ticker = ?", [ticker]).fetchall()[0][0]
    return r


def atualizar(con, tickers: list[str], completo: bool = False) -> dict[str, int]:
    """Atualiza a tabela `precos`. Incremental por padrão (rebaixa os últimos 10 dias)."""
    resultado = {}
    for tk in tickers:
        inicio = None if completo else ultima_data(con, tk)
        if inicio is not None:
            inicio = inicio - timedelta(days=10)  # cobre ajustes retroativos de proventos
        try:
            df = baixar(tk, inicio)
        except Exception as e:  # rede, ticker inexistente, mudança no Yahoo...
            log.error("Falha ao baixar %s: %s", tk, e)
            resultado[tk] = -1
            continue
        if df.empty:
            log.warning("Yahoo não retornou dados para %s", tk)
        resultado[tk] = upsert(con, "precos", df)
        log.info("%s: %d pregões gravados", tk, resultado[tk])
    return resultado


def carregar(con, ticker: str) -> pd.DataFrame:
    return con.execute(
        "SELECT * FROM precos WHERE ticker = ? ORDER BY data", [ticker]
    ).df()
