"""Coleta de notícias via RSS (Google News + feeds de portais financeiros). Não precisa de chave.

O Google News devolve no máximo ~100 itens por busca, então o histórico é montado de
duas formas:
  * coleta diária (o "bot" rodando todo dia acumula as notícias novas);
  * backfill por janelas mensais usando os operadores after:/before: da busca.
"""

from __future__ import annotations

import calendar
import hashlib
import html
import logging
import re
import time
import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import pandas as pd

from ..config import Ativo
from ..db import inserir_novos

log = logging.getLogger(__name__)
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# Feeds gerais: as notícias são filtradas pelos termos de cada ativo.
FEEDS_GERAIS = [
    "https://www.infomoney.com.br/feed/",
    "https://www.moneytimes.com.br/feed/",
    "https://braziljournal.com/feed/",
]

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


# ----------------------------------------------------------------- utilidades

def _sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))


def normalizar_texto(txt: str | None) -> str:
    return _sem_acento(txt or "").lower()


def limpar_html(txt: str | None) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", txt or "")
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


def id_noticia(url: str, titulo: str) -> str:
    return hashlib.sha1((url or titulo).encode("utf-8")).hexdigest()[:20]


def _para_brasilia(struct) -> datetime | None:
    if not struct:
        return None
    utc = datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    return utc.astimezone(FUSO_BR).replace(tzinfo=None)


def cita_ativo(texto_normalizado: str, ativo: Ativo) -> bool:
    """True se algum termo do ativo aparece como palavra inteira no texto."""
    for termo in ativo.termos:
        t = re.escape(normalizar_texto(termo))
        if re.search(rf"(?<![a-z0-9]){t}(?![a-z0-9])", texto_normalizado):
            return True
    return False


# ----------------------------------------------------------------- parsing

def entradas_para_df(entradas, fonte_padrao: str = "") -> pd.DataFrame:
    """Converte entradas do feedparser em DataFrame no esquema da tabela `noticias`."""
    linhas = []
    for e in entradas:
        titulo = limpar_html(e.get("title"))
        if not titulo:
            continue
        fonte = (e.get("source") or {}).get("title") or fonte_padrao
        # Google News anexa " - Fonte" ao título
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -len(fonte) - 3].strip()
        url = e.get("link", "")
        linhas.append({
            "id": id_noticia(url, titulo),
            "titulo": titulo,
            "resumo": limpar_html(e.get("summary"))[:2000],
            "url": url,
            "fonte": fonte,
            "publicada_em": _para_brasilia(e.get("published_parsed") or e.get("updated_parsed")),
        })
    df = pd.DataFrame(linhas, columns=["id", "titulo", "resumo", "url", "fonte", "publicada_em"])
    return df.drop_duplicates("id")


def associar(df: pd.DataFrame, ativos: list[Ativo]) -> pd.DataFrame:
    """Gera os pares (noticia_id, ticker) para cada notícia que cita um ativo."""
    pares = []
    for _, n in df.iterrows():
        texto = normalizar_texto(f"{n['titulo']} {n['resumo']}")
        for a in ativos:
            if cita_ativo(texto, a):
                pares.append({"noticia_id": n["id"], "ticker": a.ticker})
    return pd.DataFrame(pares, columns=["noticia_id", "ticker"]).drop_duplicates()


# ----------------------------------------------------------------- rede

def _ler_feed(url: str):
    import feedparser

    feed = feedparser.parse(url, agent="Mozilla/5.0 (NewsMarket; +https://github.com/Krefit/NewsMarket)")
    if feed.get("bozo") and not feed.entries:
        raise RuntimeError(f"Feed inválido ou inacessível: {url} ({feed.get('bozo_exception')})")
    return feed.entries


def url_busca(termo: str, inicio: date | None = None, fim: date | None = None) -> str:
    q = f'"{termo}"'
    if inicio:
        q += f" after:{inicio.isoformat()}"
    if fim:
        q += f" before:{fim.isoformat()}"
    return GOOGLE_NEWS.format(q=quote_plus(q))


def _gravar(con, df: pd.DataFrame, ativos: list[Ativo]) -> int:
    if df.empty:
        return 0
    pares = associar(df, ativos)
    df = df[df["id"].isin(pares["noticia_id"])]   # guarda só o que cita algum ativo
    novas = inserir_novos(con, "noticias", df)
    inserir_novos(con, "noticia_ativo", pares)
    return novas


def coletar(con, ativos: list[Ativo], feeds_gerais: list[str] | None = None,
            pausa: float = 1.0) -> int:
    """Coleta diária: busca recente no Google News por termo + feeds gerais."""
    feeds_gerais = FEEDS_GERAIS if feeds_gerais is None else feeds_gerais
    total = 0
    urls = [(url_busca(t), "Google News") for a in ativos for t in a.termos]
    urls += [(f, f.split("/")[2]) for f in feeds_gerais]
    for url, fonte in urls:
        try:
            df = entradas_para_df(_ler_feed(url), fonte_padrao=fonte)
        except Exception as e:
            log.error("Falha ao ler %s: %s", url, e)
            continue
        n = _gravar(con, df, ativos)
        total += n
        log.info("%s: %d itens, %d novos", url[:80], len(df), n)
        time.sleep(pausa)
    return total


def backfill(con, ativos: list[Ativo], inicio: date, fim: date | None = None,
             pausa: float = 2.0) -> int:
    """Busca notícias antigas mês a mês (Google News limita ~100 itens por consulta)."""
    fim = fim or date.today()
    meses = pd.date_range(pd.Timestamp(inicio).replace(day=1), fim, freq="MS")
    total = 0
    for a in ativos:
        for m in meses:
            ini_m = m.date()
            fim_m = (m + pd.offsets.MonthBegin(1)).date()
            for termo in a.termos:
                try:
                    df = entradas_para_df(_ler_feed(url_busca(termo, ini_m, fim_m)), "Google News")
                except Exception as e:
                    log.error("Backfill %s %s: %s", termo, ini_m, e)
                    continue
                n = _gravar(con, df, ativos)
                total += n
                log.info("backfill %s %s: %d novos", termo, ini_m.strftime("%Y-%m"), n)
                time.sleep(pausa)
    return total
