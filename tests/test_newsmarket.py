import numpy as np
import pandas as pd
import pytest

from newsmarket.analise import impacto, sentimento
from newsmarket.coleta import noticias, precos
from newsmarket.config import Ativo, ticker_yahoo
from newsmarket.db import inserir_novos, upsert
from newsmarket.modelo import features, treino

from .conftest import entrada_rss, precos_sinteticos


# ---------------------------------------------------------------- config / coleta

def test_ticker_yahoo():
    assert ticker_yahoo("MXRF11") == "MXRF11.SA"
    assert ticker_yahoo("^BVSP") == "^BVSP"
    assert ticker_yahoo("XPTO.SA") == "XPTO.SA"


def test_normalizar_yfinance_com_fuso():
    idx = pd.DatetimeIndex(["2024-03-01", "2024-03-04"]).tz_localize("America/Sao_Paulo")
    bruto = pd.DataFrame({"Open": [10, 11], "High": [10, 11], "Low": [10, 11], "Close": [10, 11],
                          "Adj Close": [9.5, 10.6], "Volume": [100, 200],
                          "Dividends": [0, 0.1], "Stock Splits": [0, 0]}, index=idx)
    df = precos.normalizar(bruto, "MXRF11")
    assert list(df.columns) == precos.COLUNAS
    assert str(df["data"].iloc[0]) == "2024-03-01"
    assert df["dividendos"].iloc[1] == 0.1


def test_upsert_idempotente(con):
    df = precos_sinteticos(n=50)
    upsert(con, "precos", df)
    upsert(con, "precos", df)
    assert con.execute("SELECT count(*) FROM precos").fetchall()[0][0] == 50


def test_rss_titulo_fuso_e_associacao(con):
    ativos = [Ativo("MXRF11", termos=("MXRF11", "Maxi Renda")), Ativo("HGLG11", termos=("HGLG11",))]
    entradas = [
        entrada_rss("Maxi Renda anuncia dividendos - InfoMoney", "http://a", "InfoMoney"),
        entrada_rss("HGLG11 e MXRF11 sobem", "http://b"),
        entrada_rss("Ibovespa fecha em alta", "http://c"),
        entrada_rss("MXRF110 não é o mesmo ticker", "http://d"),
    ]
    df = noticias.entradas_para_df(entradas, "Google News")
    assert df.loc[0, "titulo"] == "Maxi Renda anuncia dividendos"
    assert df.loc[0, "fonte"] == "InfoMoney"
    assert str(df.loc[0, "publicada_em"]) == "2024-03-04 12:00:00"  # 15h UTC = 12h Brasília
    pares = noticias.associar(df, ativos)
    por_id = pares.groupby("noticia_id")["ticker"].apply(set).to_dict()
    assert por_id[df.loc[0, "id"]] == {"MXRF11"}
    assert por_id[df.loc[1, "id"]] == {"MXRF11", "HGLG11"}
    assert df.loc[2, "id"] not in por_id
    assert df.loc[3, "id"] not in por_id

    assert noticias._gravar(con, df, ativos) == 2
    assert noticias._gravar(con, df, ativos) == 0   # nada duplicado


def test_url_busca_com_janela():
    from datetime import date
    u = noticias.url_busca("MXRF11", date(2024, 1, 1), date(2024, 2, 1))
    assert "after%3A2024-01-01" in u and "before%3A2024-02-01" in u and "hl=pt-BR" in u


# ---------------------------------------------------------------- sentimento

@pytest.mark.parametrize("texto,esperado", [
    ("MXRF11 anuncia aumento de dividendos", 1),
    ("Queda da vacância anima cotistas do HGLG11", 1),
    ("KNRI11 sofre com inadimplência de inquilino", -1),
    ("Fundo corta dividendos após saída do inquilino", -1),
    ("Fundo não registra prejuízo", 1),
    ("Assembleia de cotistas marcada para sexta", 0),
])
def test_sentimento_lexico(texto, esperado):
    s = sentimento.score_lexico(texto)
    assert -1 <= s <= 1
    assert np.sign(s) == esperado


def test_sentimento_calcula_so_pendentes(con):
    con.execute("INSERT INTO noticias (id, titulo) VALUES ('a', 'lucro recorde'), ('b', 'prejuízo')")
    assert sentimento.calcular(con) == 2
    assert sentimento.calcular(con) == 0


# ---------------------------------------------------------------- impacto

def test_pregao_de_impacto_respeita_fechamento_e_fim_de_semana():
    pregoes = pd.bdate_range("2024-03-01", periods=5)   # sex 01, seg 04, ter 05...
    pub = pd.Series(pd.to_datetime(["2024-03-01 10:00", "2024-03-01 19:00",
                                    "2024-03-02 11:00", "2024-03-08 20:00"]))
    r = impacto.pregao_de_impacto(pub, pregoes)
    assert [str(d.date()) if pd.notna(d) else None for d in r] == \
        ["2024-03-01", "2024-03-04", "2024-03-04", None]


def test_estudo_de_evento_detecta_efeito(mercado_com_efeito):
    p, n, ref = mercado_com_efeito
    res = impacto.resumo(impacto.eventos(n, p, ref, janela=2)).set_index(["classe", "medida"])
    assert res.loc[("positiva", "dia 0"), "retorno_anormal_medio_pct"] > 1.0
    assert res.loc[("negativa", "dia 0"), "retorno_anormal_medio_pct"] < -1.0
    assert res.loc[("positiva", "dia 0"), "t_stat"] > 3


# ---------------------------------------------------------------- features / modelo

def test_features_sem_vazamento(mercado_com_efeito):
    p, n, ref = mercado_com_efeito
    base = features.montar(p, n, ref, horizonte=1)
    # mudar o futuro não pode mudar as features do passado
    p2 = p.copy()
    p2.loc[p2.index[-50:], "fechamento_ajustado"] *= 3
    base2 = features.montar(p2, n, ref, horizonte=1)
    corte = pd.Timestamp(p["data"].iloc[-52])
    cols = features.FEATURES_PRECO + features.FEATURES_NOTICIA
    a = base[base["data"] < corte][cols].reset_index(drop=True)
    b = base2[base2["data"] < corte][cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)
    assert base["alvo"].iloc[-1:].isna().all()     # último pregão não tem alvo


def test_modelo_com_noticias_supera_so_preco():
    """Planta um efeito no pregão seguinte ao da notícia (o que o horizonte 1 tenta prever)
    e confere que as features de notícia melhoram a acurácia fora da amostra."""
    rng = np.random.default_rng(3)
    datas = pd.bdate_range("2021-01-04", periods=900)
    dias = rng.choice(np.arange(40, 898), size=300, replace=False)
    sinais = rng.choice([1, -1], size=300)
    choques = {datas[i + 1]: 0.03 * s for i, s in zip(dias, sinais)}
    p = precos_sinteticos(n=900, seed=5, choques=choques, inicio="2021-01-04")
    n = pd.DataFrame({"noticia_id": [f"n{i}" for i in range(300)],
                      "publicada_em": [datas[i] + pd.Timedelta(hours=10) for i in dias],
                      "titulo": "x", "score": sinais.astype(float)})
    base = features.montar(p, n, None, horizonte=1)
    base["ticker"] = "TEST11"
    val = treino.validar(base, horizonte=1)
    assert val.ganho_noticias() > 0.05
    pred = treino.treinar_e_prever(base, 1, None)
    assert len(pred) == 1 and 0 <= pred.loc[0, "prob_alta"] <= 1
    assert pred.loc[0, "sinal"] in {"ALTA", "BAIXA", "NEUTRO"}


def test_validar_recusa_pouco_dado():
    base = features.montar(precos_sinteticos(n=100), pd.DataFrame(), None)
    base["ticker"] = "X"
    with pytest.raises(ValueError):
        treino.validar(base)
