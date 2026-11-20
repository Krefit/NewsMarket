"""Treino, validação walk-forward e predição de direção (alta/baixa).

A pergunta central do projeto é respondida aqui: o modelo com features de notícias
acerta mais que o mesmo modelo só com preços? A validação é sempre no tempo
(treina no passado, testa no futuro), nunca embaralhada.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

from ..analise.impacto import carregar_noticias
from ..coleta.precos import carregar as carregar_precos
from ..config import Config
from .features import FEATURES_NOTICIA, FEATURES_PRECO, montar

log = logging.getLogger(__name__)

LIMIAR_SINAL = 0.05   # prob_alta acima de 0.55 => ALTA; abaixo de 0.45 => BAIXA
MIN_LINHAS = 250
MARGEM_MINIMA = 0.02  # sinais só valem se o modelo bater o palpite trivial por 2 p.p.


def novo_modelo() -> HistGradientBoostingClassifier:
    # raso e regularizado: série financeira tem muito ruído e pouco sinal
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                          l2_regularization=1.0, min_samples_leaf=40,
                                          random_state=42)


def base_completa(con, cfg: Config, horizonte: int = 1) -> pd.DataFrame:
    partes = []
    refs = {k: carregar_precos(con, v) for k, v in cfg.referencias.items()}
    for a in cfg.ativos:
        p = carregar_precos(con, a.ticker)
        if len(p) < 30:
            log.warning("%s: só %d pregões no banco, ignorado", a.ticker, len(p))
            continue
        ref = refs.get("ifix") if a.tipo == "fii" else refs.get("ibov")
        df = montar(p, carregar_noticias(con, a.ticker), ref, horizonte)
        df["ticker"] = a.ticker
        partes.append(df)
    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True).sort_values(["data", "ticker"])


@dataclass
class ResultadoValidacao:
    tabela: pd.DataFrame          # métricas por conjunto de features
    n_linhas: int
    periodo: tuple[date, date]

    def ganho_noticias(self) -> float:
        t = self.tabela.set_index("modelo")
        return t.loc["preco+noticias", "acuracia"] - t.loc["preco", "acuracia"]


def validar(base: pd.DataFrame, horizonte: int = 1, n_folds: int = 5) -> ResultadoValidacao:
    """Walk-forward: divide as datas em blocos; treina em tudo antes de cada bloco."""
    rot = base.dropna(subset=["alvo"]).reset_index(drop=True)
    if len(rot) < MIN_LINHAS:
        raise ValueError(f"Poucos dados para validar ({len(rot)} linhas; mínimo {MIN_LINHAS}).")
    datas = np.sort(rot["data"].unique())
    blocos = np.array_split(datas[len(datas) // 3:], n_folds)   # 1º terço só treina

    conjuntos = {"preco": FEATURES_PRECO, "preco+noticias": FEATURES_PRECO + FEATURES_NOTICIA}
    preds = {k: [] for k in conjuntos}
    verdade, base_maj = [], []
    for bloco in blocos:
        corte = bloco[0]
        # gap = horizonte: o alvo das últimas linhas de treino olharia para dentro do teste
        datas_treino = datas[datas < corte][:-horizonte] if horizonte else datas[datas < corte]
        tr = rot[rot["data"].isin(datas_treino)]
        te = rot[rot["data"].isin(bloco)]
        if tr["alvo"].nunique() < 2 or te.empty:
            continue
        verdade.append(te["alvo"].to_numpy())
        maj = float(tr["alvo"].mean() >= 0.5)
        base_maj.append(np.full(len(te), maj))
        for nome, cols in conjuntos.items():
            m = novo_modelo().fit(tr[cols], tr["alvo"])
            preds[nome].append(m.predict_proba(te[cols])[:, 1])

    y = np.concatenate(verdade)
    linhas = [{"modelo": "sempre_classe_majoritaria",
               "acuracia": accuracy_score(y, np.concatenate(base_maj)), "auc": 0.5}]
    for nome in conjuntos:
        p = np.concatenate(preds[nome])
        linhas.append({"modelo": nome, "acuracia": accuracy_score(y, p >= 0.5),
                       "auc": roc_auc_score(y, p) if len(np.unique(y)) > 1 else np.nan})
    tabela = pd.DataFrame(linhas)
    tabela["n_teste"] = len(y)
    return ResultadoValidacao(tabela, len(rot), (pd.Timestamp(datas[0]).date(),
                                                 pd.Timestamp(datas[-1]).date()))


def sinal(prob_alta: float) -> str:
    if prob_alta >= 0.5 + LIMIAR_SINAL:
        return "ALTA"
    if prob_alta <= 0.5 - LIMIAR_SINAL:
        return "BAIXA"
    return "NEUTRO"


def treinar_e_prever(base: pd.DataFrame, horizonte: int = 1,
                     acuracia_validacao: float | None = None,
                     salvar_em: Path | None = None) -> pd.DataFrame:
    """Treina com todo o histórico rotulado e prevê o próximo movimento de cada ticker."""
    cols = FEATURES_PRECO + FEATURES_NOTICIA
    rot = base.dropna(subset=["alvo"])
    modelo = novo_modelo().fit(rot[cols], rot["alvo"])
    if salvar_em is not None:
        import joblib
        salvar_em.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"modelo": modelo, "features": cols, "horizonte": horizonte}, salvar_em)

    ultimos = base.sort_values("data").groupby("ticker").tail(1)
    prob = modelo.predict_proba(ultimos[cols])[:, 1]
    out = pd.DataFrame({
        "ticker": ultimos["ticker"].to_numpy(),
        "data_ref": pd.to_datetime(ultimos["data"]).dt.date.to_numpy(),
        "horizonte": horizonte,
        "prob_alta": prob,
        "sinal": [sinal(p) for p in prob],
        "modelo": "hgb_preco+noticias",
        "acuracia_validacao": acuracia_validacao,
    })
    return out.sort_values("prob_alta", ascending=False).reset_index(drop=True)
