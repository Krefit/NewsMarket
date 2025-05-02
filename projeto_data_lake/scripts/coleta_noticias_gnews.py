import requests
import pandas as pd
import duckdb
from datetime import datetime, timedelta
import os

# --- Configurações ---
API_KEY = os.getenv("GNEWS_API_KEY")  # Definida no .env ou manualmente
PALAVRAS_CHAVE = ["Petrobras", "Vale", "FII", "dividendos", "Ibovespa"]
BANCO_PATH = "../banco_dados/acoes_duckdb.db"

# --- Conectar ao banco e criar tabela, se necessário ---
con = duckdb.connect(BANCO_PATH)
con.execute("""
CREATE TABLE IF NOT EXISTS noticias_diarias (
    palavra_chave TEXT,
    titulo TEXT,
    descricao TEXT,
    url TEXT,
    fonte TEXT,
    data_publicacao TIMESTAMP,
    PRIMARY KEY (palavra_chave, url)
)
""")

# --- Busca a última data registrada para cada palavra ---
ultimas_datas = {}
for palavra in PALAVRAS_CHAVE:
    resultado = con.execute(f"""
        SELECT MAX(data_publicacao)
        FROM noticias_diarias
        WHERE palavra_chave = ?
    """, [palavra]).fetchone()
    ultimas_datas[palavra] = resultado[0] or (datetime.utcnow() - timedelta(days=1))

# --- Loop para buscar notícias por palavra-chave ---
for palavra in PALAVRAS_CHAVE:
    data_inicio = ultimas_datas[palavra].strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Buscando notícias para '{palavra}' a partir de {data_inicio}")

    url = "https://gnews.io/api/v4/search"
    params = {
        "q": palavra,
        "token": API_KEY,
        "lang": "pt",
        "from": data_inicio,
        "sortby": "publishedAt",
        "max": 100
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Erro ao buscar notícias para {palavra}: {response.status_code}")
        continue

    noticias = response.json().get("articles", [])
    if not noticias:
        print(f"Nenhuma notícia nova para '{palavra}'")
        continue

    dados = []
    for noticia in noticias:
        dados.append({
            "palavra_chave": palavra,
            "titulo": noticia.get("title"),
            "descricao": noticia.get("description"),
            "url": noticia.get("url"),
            "fonte": noticia.get("source", {}).get("name"),
            "data_publicacao": noticia.get("publishedAt")
        })

    df = pd.DataFrame(dados)
    df["data_publicacao"] = pd.to_datetime(df["data_publicacao"])

    con.execute("INSERT OR IGNORE INTO noticias_diarias SELECT * FROM df")

print("Coleta de notícias concluída.")
