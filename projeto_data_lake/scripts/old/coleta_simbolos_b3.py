import pandas as pd
import duckdb
import requests
from io import BytesIO
from zipfile import ZipFile
import os

# Garante que a pasta exista
os.makedirs("../banco_dados", exist_ok=True)

# --- Configuração do caminho do banco ---
BANCO_PATH = os.path.abspath(os.path.join("..", "banco_dados", "acoes_duckdb.db"))
TABELA = "ativos_b3"

# --- Conectar ao banco e criar tabela se necessário ---
con = duckdb.connect(BANCO_PATH)
con.execute(f"""
CREATE TABLE IF NOT EXISTS {TABELA} (
    codigo TEXT PRIMARY KEY,
    nome TEXT,
    cnpj TEXT,
    tipo_mercado TEXT,
    data_referencia DATE
)
""")

# --- URL oficial do site da B3 com os ativos listados ---
url = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesPage/search?language=pt-br"

response = requests.get(url)
if response.status_code != 200:
    print("Erro ao baixar o arquivo da B3")
    exit()

# --- O arquivo vem zipado com um único .csv ---
with ZipFile(BytesIO(response.content)) as zip_file:
    nomes = zip_file.namelist()
    nome_csv = nomes[0]
    with zip_file.open(nome_csv) as file:
        df = pd.read_csv(file, sep=";", encoding="latin1")

# --- Filtrar apenas ações listadas ---
df = df[df["Tipo de Mercado"].str.contains("VISTA", na=False)]

# --- Padronizar colunas e adicionar data de referência ---
df = df[["Código CVM", "Nome Comercial", "CNPJ", "Tipo de Mercado"]]
df.columns = ["codigo", "nome", "cnpj", "tipo_mercado"]
df["data_referencia"] = pd.Timestamp.today().normalize()

# --- Salvar no banco, substituindo dados antigos se necessário ---
con.execute(f"DELETE FROM {TABELA}")
con.execute(f"INSERT INTO {TABELA} SELECT * FROM df")

print("Coleta de símbolos da B3 concluída.")
