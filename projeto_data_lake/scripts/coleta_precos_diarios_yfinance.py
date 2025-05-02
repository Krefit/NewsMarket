import yfinance as yf
import pandas as pd
import duckdb
from datetime import datetime, timedelta

# --- Configurações ---
BANCO_PATH = "../banco_dados/acoes_duckdb.db"
TABELA = "precos_diarios"
SIMBOLOS = ["PETR4.SA"]  # Exemplo de símbolo para Petrobras

# --- Conectar e criar tabela se não existir ---
con = duckdb.connect(BANCO_PATH)
con.execute(f"""
CREATE TABLE IF NOT EXISTS {TABELA} (
    simbolo TEXT,
    data DATE,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    PRIMARY KEY (simbolo, data)
)
""")

# --- Para cada símbolo ---
for simbolo in SIMBOLOS:
    # Obter a última data registrada
    resultado = con.execute(f"""
        SELECT MAX(data) FROM {TABELA} WHERE simbolo = ?
    """, [simbolo]).fetchone()

    ultima_data = resultado[0] or (datetime.utcnow() - timedelta(days=365))
    data_inicio = (ultima_data + timedelta(days=1)).strftime("%Y-%m-%d")
    data_fim = datetime.utcnow().strftime("%Y-%m-%d")

    if data_inicio >= data_fim:
        print(f"Nenhum novo dado para {simbolo}")
        continue

    print(f"Baixando dados de {simbolo} de {data_inicio} até {data_fim}")

    dados = yf.download(simbolo, start=data_inicio, end=data_fim)
    if dados.empty:
        print(f"Sem dados para {simbolo}")
        continue

    dados.reset_index(inplace=True)
    dados = dados[["Date", "Open", "High", "Low", "Close", "Volume"]]
    dados.columns = ["data", "open", "high", "low", "close", "volume"]
    dados["simbolo"] = simbolo
    dados = dados[["simbolo", "data", "open", "high", "low", "close", "volume"]]

    con.execute(f"INSERT OR IGNORE INTO {TABELA} SELECT * FROM df", {"df": dados})

print("Coleta diária concluída.")
