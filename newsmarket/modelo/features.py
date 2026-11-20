"""Montagem da base de treino: uma linha por (ticker, pregão).

Tudo que entra numa linha usa só informação disponível até o fechamento daquele
pregão, para não vazar o futuro. O alvo é a direção do preço `horizonte` pregões depois.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..analise.impacto import pregao_de_impacto, retornos

FEATURES_PRECO = ["ret_1", "ret_5", "ret_20", "vol_20", "dist_mm20", "volume_z",
                  "ref_ret_1", "ref_ret_5"]
FEATURES_NOTICIA = ["n_noticias", "sent_medio", "sent_min", "sent_max",
                    "n_noticias_5d", "sent_soma_5d", "dias_sem_noticia"]


def _features_preco(precos: pd.DataFrame, referencia: pd.DataFrame | None) -> pd.DataFrame:
    p = precos.sort_values("data").copy()
    p["data"] = pd.to_datetime(p["data"])
    p = p.set_index("data")
    px = p["fechamento_ajustado"]
    lr = np.log(px).diff()
    f = pd.DataFrame(index=p.index)
    f["ret_1"] = lr
    f["ret_5"] = lr.rolling(5).sum()
    f["ret_20"] = lr.rolling(20).sum()
    f["vol_20"] = lr.rolling(20).std()
    f["dist_mm20"] = px / px.rolling(20).mean() - 1
    vol = np.log1p(p["volume"].astype(float))
    f["volume_z"] = (vol - vol.rolling(20).mean()) / vol.rolling(20).std()
    if referencia is not None and not referencia.empty:
        rb = retornos(referencia).set_index("data")["ret"].reindex(f.index).fillna(0.0)
    else:
        rb = pd.Series(0.0, index=f.index)
    f["ref_ret_1"] = rb
    f["ref_ret_5"] = rb.rolling(5).sum()
    f["_px"] = px
    return f


def _features_noticia(noticias: pd.DataFrame, pregoes: pd.DatetimeIndex) -> pd.DataFrame:
    f = pd.DataFrame(index=pregoes)
    if noticias.empty:
        for c in FEATURES_NOTICIA:
            f[c] = 0.0
        f["dias_sem_noticia"] = 99.0
        return f
    n = noticias.copy()
    n["dia0"] = pregao_de_impacto(n["publicada_em"], pregoes)
    # notícia publicada após o fechamento do dia t só entra no dia t+1 (dia0 já trata isso)
    g = n.dropna(subset=["dia0"]).groupby("dia0")["score"]
    f["n_noticias"] = g.size().reindex(pregoes).fillna(0)
    f["sent_medio"] = g.mean().reindex(pregoes).fillna(0)
    f["sent_min"] = g.min().reindex(pregoes).fillna(0)
    f["sent_max"] = g.max().reindex(pregoes).fillna(0)
    f["n_noticias_5d"] = f["n_noticias"].rolling(5, min_periods=1).sum()
    soma = g.sum().reindex(pregoes).fillna(0)
    f["sent_soma_5d"] = soma.rolling(5, min_periods=1).sum()
    teve = f["n_noticias"] > 0
    grupos = teve.cumsum()
    contador = teve.groupby(grupos).cumcount().astype(float)
    contador[grupos == 0] = 99.0
    f["dias_sem_noticia"] = contador.clip(upper=99)
    return f


def montar(precos: pd.DataFrame, noticias: pd.DataFrame, referencia: pd.DataFrame | None,
           horizonte: int = 1) -> pd.DataFrame:
    """Base de um ticker. Linhas sem alvo (últimos pregões) ficam com alvo NaN — servem
    para a predição do próximo movimento."""
    fp = _features_preco(precos, referencia)
    fn = _features_noticia(noticias, pd.DatetimeIndex(fp.index))
    df = fp.join(fn)
    futuro = np.log(df["_px"].shift(-horizonte) / df["_px"])
    df["ret_futuro"] = futuro
    df["alvo"] = np.where(futuro.isna(), np.nan, (futuro > 0).astype(float))
    df = df.drop(columns="_px")
    df = df.dropna(subset=FEATURES_PRECO)
    return df.reset_index().rename(columns={"index": "data"})
