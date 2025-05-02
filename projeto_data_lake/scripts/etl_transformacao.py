import duckdb
import pandas as pd

# Caminho para o banco local
BANCO_PATH = "../banco_dados/acoes_duckdb.db"
con = duckdb.connect(BANCO_PATH)

# --- Exemplo 1: calcular médias móveis nos preços diários ---
def calcular_medias_moveis(simbolo: str):
    query = f"""
    SELECT * FROM precos_diarios
    WHERE simbolo = '{simbolo}'
    ORDER BY data
    """
    df = con.execute(query).fetchdf()

    if df.empty:
        print(f"Nenhum dado encontrado para {simbolo}")
        return

    df["mm_5"] = df["close"].rolling(window=5).mean()
    df["mm_20"] = df["close"].rolling(window=20).mean()

    print(df.tail(10))  # Apenas para visualização, pode salvar em nova tabela ou arquivo

# --- Exemplo 2: gerar uma visão com agregações por semana ---
def gerar_resumo_semanal(simbolo: str):
    query = f"""
    SELECT * FROM precos_diarios
    WHERE simbolo = '{simbolo}'
    ORDER BY data
    """
    df = con.execute(query).fetchdf()
    if df.empty:
        return

    df["semana"] = df["data"].dt.to_period("W").apply(lambda r: r.start_time)
    resumo = df.groupby("semana").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).reset_index()

    print(resumo.tail(5))  # Exibição simples por enquanto

# --- Execução exemplo para PETR4 ---
if __name__ == "__main__":
    calcular_medias_moveis("PETR4.SA")
    gerar_resumo_semanal("PETR4.SA")
