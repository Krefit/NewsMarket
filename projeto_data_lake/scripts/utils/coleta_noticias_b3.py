# pip install requests python-dotenv duckdb pandas

import os
from datetime import datetime, timedelta

import requests
import pandas as pd
from dotenv import load_dotenv
import duckdb

# 1. Carrega variáveis de ambiente
load_dotenv()
API_KEY = os.getenv("FINNHUB_API_KEY")
if not API_KEY:
    raise ValueError("Defina FINNHUB_API_KEY em seu .env")

# 2. Colunas esperadas
EXPECTED_COLS = ["symbol", "headline", "summary", "url", "publishedAt", "source"]

def fetch_news_for_ticker(symbol: str, date_from: datetime, date_to: datetime) -> pd.DataFrame:
    """
    Busca notícias históricas da Finnhub via HTTP GET para o intervalo [date_from, date_to].
    Retorna sempre um DataFrame com as colunas EXPECTED_COLS, mesmo vazio.
    """
    from_str = date_from.strftime('%Y-%m-%d')
    to_str   = date_to.strftime('%Y-%m-%d')
    url = (
        "https://finnhub.io/api/v1/company-news"
        f"?symbol={symbol}"
        f"&from={from_str}"
        f"&to={to_str}"
        f"&token={API_KEY}"
    )
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        return pd.DataFrame(columns=EXPECTED_COLS)

    df = pd.DataFrame(data)
    if df.empty or not set(['headline','summary','url','datetime','source']).issubset(df.columns):
        return pd.DataFrame(columns=EXPECTED_COLS)

    df = df[['headline', 'summary', 'url', 'datetime', 'source']].copy()
    df['symbol']      = symbol
    df['publishedAt'] = pd.to_datetime(df['datetime'], unit='s')
    return df.rename(columns={}).loc[:, EXPECTED_COLS]

def main():
    # 3. Defina seus tickers B3 (prefixo BVMF:)
    tickers = ["BVMF:PETR4", "BVMF:VALE3", "BVMF:ITUB4"]
    # 4. Período: últimos 12 meses até hoje
    date_to   = datetime.now()
    date_from = date_to - timedelta(days=365)

    # 5. Coleta todas as notícias no período
    dfs = [fetch_news_for_ticker(tk, date_from, date_to) for tk in tickers]
    df_all = pd.concat(dfs, ignore_index=True, sort=False).loc[:, EXPECTED_COLS]

    if df_all.empty:
        print("Nenhuma notícia histórica encontrada para o período solicitado.")
        return

    # 6. Conecta ao DuckDB 'daily_history.db'
    con = duckdb.connect('daily_history.db')

    # 7. Cria tabela de notícias se não existir
    con.execute("""
        CREATE TABLE IF NOT EXISTS b3_news (
            symbol TEXT,
            headline TEXT,
            summary TEXT,
            url TEXT UNIQUE,
            publishedAt TIMESTAMP,
            source TEXT
        )
    """)

    # 8. Insere incrementalmente (só URLs novas)
    con.register('staged', df_all)
    con.execute("""
        INSERT INTO b3_news
        SELECT s.symbol, s.headline, s.summary, s.url, s.publishedAt, s.source
        FROM staged AS s
        LEFT JOIN b3_news AS b USING(url)
        WHERE b.url IS NULL
    """)
    con.close()

    print(f"{len(df_all)} manchetes (até {date_to.date()}) processadas; novas adicionadas à tabela b3_news.")

if __name__ == "__main__":
    main()
