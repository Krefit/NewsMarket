"""Estudo de evento: quanto o preço se move depois de notícias positivas/negativas.

Para cada notícia associada a um ativo:
  1. define o pregão em que ela pode afetar o preço (dia 0): se saiu antes do
     fechamento, é o próprio pregão; se saiu depois (ou em fim de semana/feriado),
     é o pregão seguinte;
  2. calcula o retorno anormal = retorno do ativo - retorno do índice de referência
     (IFIX para FIIs, Ibovespa para ações), no dia 0 e acumulado até o dia +N;
  3. agrega por faixa de sentimento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HORA_FECHAMENTO = 17  # pregão regular da B3 fecha entre 17h e 18h; usamos 17h por segurança
LIMIAR_SENTIMENTO = 0.2


def retornos(precos: pd.DataFrame) -> pd.DataFrame:
    """precos: colunas data, fechamento_ajustado (um ticker). Retorna data, ret (log)."""
    p = precos.sort_values("data")[["data", "fechamento_ajustado"]].dropna().copy()
    p["data"] = pd.to_datetime(p["data"])
    p["ret"] = np.log(p["fechamento_ajustado"]).diff()
    return p[["data", "ret"]].dropna().reset_index(drop=True)


def pregao_de_impacto(publicada_em: pd.Series, pregoes: pd.DatetimeIndex) -> pd.Series:
    """Mapeia o horário de publicação para o primeiro pregão que pode refletir a notícia."""
    pub = pd.to_datetime(publicada_em)
    dia = pub.dt.normalize()
    depois_do_fechamento = pub.dt.hour >= HORA_FECHAMENTO
    alvo = dia + pd.to_timedelta(depois_do_fechamento.astype(int), unit="D")
    pos = pregoes.searchsorted(alvo.values, side="left")
    valido = pos < len(pregoes)
    out = pd.Series(pd.NaT, index=publicada_em.index, dtype="datetime64[ns]")
    out[valido] = pregoes[pos[valido]]
    return out


def classificar(score: float, limiar: float = LIMIAR_SENTIMENTO) -> str:
    if score >= limiar:
        return "positiva"
    if score <= -limiar:
        return "negativa"
    return "neutra"


def eventos(noticias: pd.DataFrame, precos: pd.DataFrame, referencia: pd.DataFrame | None,
            janela: int = 3) -> pd.DataFrame:
    """noticias: colunas noticia_id, publicada_em, score, titulo (um ticker).

    Retorna uma linha por notícia com o retorno anormal do dia 0 até o dia +janela.
    """
    r = retornos(precos).set_index("data")["ret"]
    if referencia is not None and not referencia.empty:
        rb = retornos(referencia).set_index("data")["ret"].reindex(r.index).fillna(0.0)
        anormal = r - rb
    else:
        anormal = r
    pregoes = pd.DatetimeIndex(anormal.index)
    if noticias.empty or len(pregoes) == 0:
        return pd.DataFrame()

    ev = noticias.copy()
    ev["dia0"] = pregao_de_impacto(ev["publicada_em"], pregoes)
    ev = ev.dropna(subset=["dia0"])
    pos0 = pregoes.get_indexer(ev["dia0"])
    vals = anormal.to_numpy()
    for k in range(janela + 1):
        idx = pos0 + k
        ok = idx < len(vals)
        col = np.full(len(ev), np.nan)
        col[ok] = vals[idx[ok]]
        ev[f"ar_{k}"] = col
    ar_cols = [f"ar_{k}" for k in range(janela + 1)]
    ev["car"] = ev[ar_cols].sum(axis=1, min_count=len(ar_cols))
    ev["classe"] = ev["score"].apply(classificar)
    return ev


def resumo(ev: pd.DataFrame) -> pd.DataFrame:
    """Retorno anormal médio por classe de sentimento, com estatística t e taxa de acerto."""
    if ev.empty:
        return pd.DataFrame()
    linhas = []
    for classe, g in ev.groupby("classe"):
        for col in ["ar_0", "car"]:
            x = g[col].dropna()
            n = len(x)
            media = x.mean() if n else np.nan
            t = media / (x.std(ddof=1) / np.sqrt(n)) if n > 2 and x.std(ddof=1) > 0 else np.nan
            sinal_esperado = {"positiva": 1, "negativa": -1}.get(classe)
            acerto = (np.sign(x) == sinal_esperado).mean() if sinal_esperado and n else np.nan
            linhas.append({"classe": classe, "medida": "dia 0" if col == "ar_0" else "acumulado",
                           "n": n, "retorno_anormal_medio_pct": media * 100,
                           "t_stat": t, "taxa_direcao_esperada": acerto})
    return pd.DataFrame(linhas)


def carregar_noticias(con, ticker: str) -> pd.DataFrame:
    return con.execute("""
        SELECT n.id AS noticia_id, n.publicada_em, n.titulo, n.fonte, s.score
        FROM noticias n
        JOIN noticia_ativo na ON na.noticia_id = n.id
        JOIN sentimento s     ON s.noticia_id  = n.id
        WHERE na.ticker = ? AND n.publicada_em IS NOT NULL
        ORDER BY n.publicada_em
    """, [ticker]).df()
