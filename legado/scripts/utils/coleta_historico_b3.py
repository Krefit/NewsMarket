import os
import requests
import pandas as pd
import duckdb
from dotenv import load_dotenv

# 1) Carrega a chave do .env
load_dotenv()
API_KEY = os.getenv('ALPHAVANTAGE_API_KEY')
if not API_KEY:
    raise RuntimeError("Defina ALPHAVANTAGE_API_KEY no seu .env")

BASE_URL = 'https://www.alphavantage.co/query'
OUTPUT_SIZE = 'full'  # full para todo o histórico

def fetch_daily(symbol: str) -> pd.DataFrame:
    params = {
        'function':   'TIME_SERIES_DAILY',
        'symbol':     symbol,
        'outputsize': OUTPUT_SIZE,
        'apikey':     API_KEY,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json().get('Time Series (Daily)')
    if data is None:
        raise ValueError(f"Erro ao obter {symbol}: {resp.json()}")
    df = pd.DataFrame.from_dict(data, orient='index', dtype=float)
    df.index = pd.to_datetime(df.index)
    df = df.rename(columns={
        '1. open':   'open',
        '2. high':   'high',
        '3. low':    'low',
        '4. close':  'close',
        '5. volume': 'volume'
    })
    df['symbol'] = symbol
    return df.reset_index().rename(columns={'index': 'date'})

def save_to_duckdb_incremental(df: pd.DataFrame, db_path: str, table: str):
    # Conecta (cria o arquivo se não existir)
    con = duckdb.connect(database=db_path, read_only=False)

    # Cria a tabela se não existir (mantém o schema)
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            date DATE,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            symbol VARCHAR
        )
    """)

    # Registra o DataFrame como tabela temporária interna
    con.register('to_insert', df)

    # Insere apenas linhas que ainda não existem em {table}
    con.execute(f"""
        INSERT INTO {table}
        SELECT t.*
        FROM to_insert AS t
        WHERE NOT EXISTS (
            SELECT 1
            FROM {table} AS e
            WHERE e.date   = t.date
              AND e.symbol = t.symbol
        )
    """)

    # Fecha e confirma
    con.close()
    print(f"→ Inseridas apenas linhas novas em {os.path.abspath(db_path)} (tabela {table})")

if __name__ == '__main__':
    tickers = ['PETR4.SAO','HGPO11.SAO','HTMX11.SAO','MXRF11.SAO', 'MALL11.SAO']

    # 2) Faz download e concatena
    dfs = [fetch_daily(sym) for sym in tickers]
    full = pd.concat(dfs, ignore_index=True)

    # 3) Salva de forma incremental no DuckDB
    save_to_duckdb_incremental(full, db_path='daily_history.db', table='daily_prices')
