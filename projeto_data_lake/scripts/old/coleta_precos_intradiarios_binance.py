# scripts/coleta_precos_intradiarios_binance.py
import os
import datetime
import duckdb
from binance.client import Client
from binance.enums import HistoricalKlinesType
from dotenv import load_dotenv

# Garante que a pasta exista
os.makedirs("../banco_dados", exist_ok=True)

load_dotenv()

# --- CONFIGURAÇÃO ---
ATIVO = 'PETR4BRL'  # Par de trading na Binance (verifique nome correto)
INTERVALO = Client.KLINE_INTERVAL_1HOUR
BANCO_DUCKDB = 'banco_dados/acoes_duckdb.db'
TABELA = 'precos_intradiarios'

# --- CONEXÃO COM A BINANCE ---
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

# --- BANCO ---
con = duckdb.connect(BANCO_DUCKDB)

# Criação da tabela, se não existir
con.execute(f"""
CREATE TABLE IF NOT EXISTS {TABELA} (
    simbolo TEXT,
    data TIMESTAMP,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume FLOAT,
    PRIMARY KEY (simbolo, data)
)
""")

# --- CONSULTA A ÚLTIMA DATA DISPONÍVEL ---
ultima_data = con.execute(f"""
    SELECT MAX(data) FROM {TABELA} WHERE simbolo = '{ATIVO}'
""").fetchone()[0]

if ultima_data is None:
    inicio = datetime.datetime.now() - datetime.timedelta(days=30)
else:
    inicio = ultima_data + datetime.timedelta(hours=1)

fim = datetime.datetime.now()

print(f"Coletando dados de {ATIVO} de {inicio} até {fim}...")

# --- COLETA ---
klines = client.get_historical_klines(
    ATIVO,
    INTERVALO,
    start_str=inicio.strftime('%d %b %Y %H:%M:%S'),
    end_str=fim.strftime('%d %b %Y %H:%M:%S'),
    klines_type=HistoricalKlinesType.SPOT
)

# --- INSERÇÃO NO BANCO ---
for k in klines:
    timestamp = datetime.datetime.fromtimestamp(k[0] / 1000.0)
    open_, high, low, close, volume = map(float, k[1:6])

    con.execute(f"""
        INSERT OR IGNORE INTO {TABELA} 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ATIVO, timestamp, open_, high, low, close, volume))

print(f"{len(klines)} registros adicionados.")

# --- FUTURO: MULTI ATIVOS ---
# ativos = ['PETR4BRL', 'VALE3BRL', ...]
# for ativo in ativos:
#     repetir lógica de coleta para cada ativo
