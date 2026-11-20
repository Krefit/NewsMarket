"""Sentimento de manchetes financeiras em português.

Dois métodos:
  * "lexico"  (padrão): dicionário de termos do mercado, com foco em FIIs. Rápido, sem
    dependências, explicável. Bom ponto de partida.
  * "finbert": modelo FinBERT-PT-BR (lucas-leme/FinBERT-PT-BR), treinado em notícias
    financeiras brasileiras. Mais preciso, mas exige `pip install transformers torch`.

Score sempre no intervalo [-1, +1].
"""

from __future__ import annotations

import re

import pandas as pd

from ..coleta.noticias import normalizar_texto

# Pesos de 1 a 3. Expressões com várias palavras são buscadas antes das palavras soltas.
POSITIVOS = {
    # resultado e proventos
    "lucro": 2, "lucro recorde": 3, "recorde": 2, "alta": 1, "sobe": 1, "subiu": 1, "dispara": 2,
    "disparam": 2, "valoriza": 2, "valorizacao": 2, "avanca": 1, "avancam": 1, "ganho": 1,
    "ganhos": 1, "supera": 2, "superou": 2, "acima do esperado": 2, "cresce": 1, "crescimento": 1,
    "aumenta dividendos": 3, "aumento de dividendos": 3, "aumenta rendimento": 3,
    "aumento do rendimento": 3, "dividendo extraordinario": 3, "rendimento extraordinario": 3,
    "dividendos maiores": 2, "eleva": 1, "elevacao": 1, "melhora": 1, "recupera": 1,
    "recuperacao": 1, "otimismo": 2, "positivo": 1, "forte": 1,
    # FIIs / imobiliário
    "aquisicao": 1, "adquire": 1, "compra de imovel": 2, "nova locacao": 2, "novo inquilino": 2,
    "locacao": 1, "reduz vacancia": 3, "queda da vacancia": 3, "vacancia zero": 3,
    "ocupacao": 1, "renovacao do contrato": 2, "reajuste": 1, "venda com lucro": 3,
    "ganho de capital": 2, "desconto": 1, "barato": 1,
    # analistas / juros
    "recomendacao de compra": 3, "elevado": 1, "upgrade": 2, "eleva preco-alvo": 3,
    "corte de juros": 2, "corte da selic": 2, "queda da selic": 2, "juros menores": 2,
}

NEGATIVOS = {
    "prejuizo": 3, "queda": 1, "cai": 1, "caiu": 1, "despenca": 3, "despencam": 3,
    "desaba": 3, "recua": 1, "recuam": 1, "baixa": 1, "perda": 2, "perdas": 2,
    "abaixo do esperado": 2, "piora": 2, "pessimismo": 2, "negativo": 1, "fraco": 1, "crise": 2,
    "risco": 1, "incerteza": 1, "pressao": 1, "desvaloriza": 2, "desvalorizacao": 2,
    # proventos
    "corta dividendos": 3, "corte de dividendos": 3, "reduz dividendos": 3,
    "reducao do rendimento": 3, "reduz rendimento": 3, "dividendos menores": 2,
    "suspende dividendos": 3, "sem dividendos": 3,
    # FIIs / imobiliário
    "vacancia": 2, "aumento da vacancia": 3, "inadimplencia": 3, "inadimplente": 3,
    "calote": 3, "devolucao do imovel": 3, "rescisao": 2, "saida do inquilino": 3,
    "desocupacao": 3, "recuperacao judicial": 3, "falencia": 3, "renegociacao": 1,
    "emissao": 1, "nova emissao": 1, "diluicao": 2, "rebaixamento": 2, "rebaixa": 2,
    "default": 3, "multa": 1, "processo": 1, "investigacao": 2, "fraude": 3,
    # analistas / juros
    "recomendacao de venda": 3, "downgrade": 2, "corta preco-alvo": 3,
    "alta de juros": 2, "alta da selic": 2, "aumento da selic": 2, "juros maiores": 2,
}

NEGACOES = {"nao", "sem", "nunca", "nem", "evita", "descarta"}

_TOKEN = re.compile(r"[a-z0-9\-]+")


def _compilar(lexico: dict[str, int]):
    termos = sorted(lexico, key=lambda t: -len(t.split()))
    return [(t, lexico[t], re.compile(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])")) for t in termos]


_POS = _compilar(POSITIVOS)
_NEG = _compilar(NEGATIVOS)


def _pontuar(texto: str, regras, sinal: int, usados: list[tuple[int, int]]) -> float:
    total = 0.0
    for _termo, peso, rx in regras:
        for m in rx.finditer(texto):
            ini, fim = m.span()
            if any(ini < u_fim and fim > u_ini for u_ini, u_fim in usados):
                continue  # já contado dentro de uma expressão maior
            usados.append((ini, fim))
            anteriores = _TOKEN.findall(texto[max(0, ini - 25):ini])[-3:]
            fator = -1 if NEGACOES.intersection(anteriores) else 1
            total += sinal * peso * fator
    return total


def score_lexico(texto: str) -> float:
    t = normalizar_texto(texto)
    usados: list[tuple[int, int]] = []
    # positivos e negativos disputam as mesmas posições; expressões longas primeiro
    regras = sorted([(r, 1) for r in _POS] + [(r, -1) for r in _NEG],
                    key=lambda x: -len(x[0][0].split()))
    bruto = 0.0
    magnitude = 0.0
    for regra, sinal in regras:
        v = _pontuar(t, [regra], sinal, usados)
        bruto += v
        magnitude += abs(v)
    if magnitude == 0:
        return 0.0
    # normaliza para [-1, 1] e amortece textos com um único termo fraco
    return max(-1.0, min(1.0, bruto / max(magnitude, 3.0)))


class _FinBert:
    _pipe = None

    @classmethod
    def score(cls, textos: list[str]) -> list[float]:
        if cls._pipe is None:
            from transformers import pipeline  # import tardio: dependência opcional
            cls._pipe = pipeline("text-classification", model="lucas-leme/FinBERT-PT-BR",
                                 truncation=True, top_k=None)
        saida = []
        for probs in cls._pipe(textos, batch_size=16):
            p = {d["label"].upper(): d["score"] for d in probs}
            saida.append(p.get("POSITIVE", 0.0) - p.get("NEGATIVE", 0.0))
        return saida


def calcular(con, metodo: str = "lexico", recalcular: bool = False) -> int:
    """Calcula o sentimento das notícias que ainda não têm score."""
    filtro = "" if recalcular else "WHERE s.noticia_id IS NULL OR s.metodo <> ?"
    params = [] if recalcular else [metodo]
    df = con.execute(f"""
        SELECT n.id, n.titulo, coalesce(n.resumo, '') AS resumo
        FROM noticias n LEFT JOIN sentimento s ON s.noticia_id = n.id
        {filtro}
    """, params).df()
    if df.empty:
        return 0
    # O título carrega quase todo o sinal; o resumo do Google News costuma repetir o título.
    textos = df["titulo"].tolist()
    if metodo == "finbert":
        scores = _FinBert.score(textos)
    elif metodo == "lexico":
        scores = [score_lexico(t) for t in textos]
    else:
        raise ValueError(f"Método de sentimento desconhecido: {metodo}")
    out = pd.DataFrame({"noticia_id": df["id"], "score": scores, "metodo": metodo})
    from ..db import upsert
    return upsert(con, "sentimento", out)
