import time

import numpy as np
import pandas as pd
import pytest

from newsmarket.db import conectar


@pytest.fixture
def con():
    c = conectar(":memory:")
    yield c
    c.close()


def precos_sinteticos(ticker="TEST11", n=600, seed=0, choques=None, inicio="2022-01-03"):
    """Passeio aleatório; `choques` = {data: retorno extra no dia}."""
    rng = np.random.default_rng(seed)
    datas = pd.bdate_range(inicio, periods=n)
    ret = rng.normal(0, 0.01, n)
    for d, extra in (choques or {}).items():
        ret[datas.get_loc(pd.Timestamp(d))] += extra
    px = 100 * np.exp(np.cumsum(ret))
    return pd.DataFrame({
        "ticker": ticker, "data": datas.date, "abertura": px, "maxima": px * 1.01,
        "minima": px * 0.99, "fechamento": px, "fechamento_ajustado": px,
        "volume": rng.integers(1_000, 10_000, n), "dividendos": 0.0,
    })


@pytest.fixture
def mercado_com_efeito():
    """Ativo em que notícia positiva (às 10h) gera +2% no mesmo dia e negativa gera -2%."""
    rng = np.random.default_rng(1)
    datas = pd.bdate_range("2022-01-03", periods=600)
    dias_news = rng.choice(np.arange(30, 600), size=150, replace=False)
    sinais = rng.choice([1, -1], size=150)
    choques = {datas[i]: 0.02 * s for i, s in zip(dias_news, sinais)}
    precos = precos_sinteticos(choques=choques)
    noticias = pd.DataFrame({
        "noticia_id": [f"n{i}" for i in range(150)],
        "publicada_em": [datas[i] + pd.Timedelta(hours=10) for i in dias_news],
        "titulo": ["x"] * 150,
        "score": sinais.astype(float),
    })
    referencia = precos_sinteticos("REF", seed=99)
    return precos, noticias, referencia


def entrada_rss(titulo, link, fonte=None, quando="2024-03-04 15:00:00", resumo=""):
    """Imita uma entrada do feedparser. `quando` em UTC."""
    e = {"title": titulo, "link": link, "summary": resumo,
         "published_parsed": time.strptime(quando, "%Y-%m-%d %H:%M:%S")}
    if fonte:
        e["source"] = {"title": fonte}
    return e
