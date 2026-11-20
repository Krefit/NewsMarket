"""Configuração: caminhos e lista de ativos (ativos.toml)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv é opcional
    load_dotenv = None

RAIZ = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(RAIZ / ".env")


def _caminho(var: str, padrao: str) -> Path:
    p = Path(os.getenv(var, padrao))
    return p if p.is_absolute() else RAIZ / p


@dataclass(frozen=True)
class Ativo:
    ticker: str          # código B3, ex.: MXRF11
    tipo: str = "fii"    # "fii" ou "acao"
    termos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ticker_yahoo(self) -> str:
        return ticker_yahoo(self.ticker)


def ticker_yahoo(ticker: str) -> str:
    """MXRF11 -> MXRF11.SA. Índices (^BVSP) e tickers com sufixo ficam como estão."""
    if ticker.startswith("^") or "." in ticker:
        return ticker
    return f"{ticker}.SA"


@dataclass(frozen=True)
class Config:
    db_path: Path
    ativos: tuple[Ativo, ...]
    referencias: dict[str, str]

    def ativo(self, ticker: str) -> Ativo:
        for a in self.ativos:
            if a.ticker == ticker.upper():
                return a
        raise KeyError(f"Ativo {ticker} não está em ativos.toml")


def carregar(arquivo_ativos: str | Path | None = None, db_path: str | Path | None = None) -> Config:
    arq = Path(arquivo_ativos) if arquivo_ativos else _caminho("NEWSMARKET_ATIVOS", "ativos.toml")
    with open(arq, "rb") as f:
        dados = tomllib.load(f)

    ativos = tuple(
        Ativo(
            ticker=a["ticker"].upper(),
            tipo=a.get("tipo", "fii"),
            termos=tuple(a.get("termos", [a["ticker"]])),
        )
        for a in dados.get("ativo", [])
    )
    if not ativos:
        raise ValueError(f"Nenhum [[ativo]] definido em {arq}")

    db = Path(db_path) if db_path else _caminho("NEWSMARKET_DB", "dados/newsmarket.duckdb")
    return Config(db_path=db, ativos=ativos, referencias=dict(dados.get("referencias", {})))
