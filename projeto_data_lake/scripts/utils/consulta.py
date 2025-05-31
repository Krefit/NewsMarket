import os
import requests
from dotenv import load_dotenv

# Carrega a chave da API do .env
load_dotenv()
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

def buscar_ticker(query: str):
    print(f"🔍 Buscando correspondência para: {query}")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "SYMBOL_SEARCH",
        "keywords": query,
        "apikey": API_KEY
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        matches = data.get("bestMatches", [])
        if not matches:
            print("❌ Nenhum resultado encontrado.")
            return

        print(f"\n🔎 {len(matches)} resultado(s) encontrado(s):\n")
        for match in matches:
            print(f"✔ Símbolo: {match.get('1. symbol')}")
            print(f"  Nome: {match.get('2. name')}")
            print(f"  Região: {match.get('4. region')}")
            print(f"  Moeda: {match.get('8. currency')}")
            print(f"  Tipo: {match.get('3. type')}")
            print("-" * 40)
    except Exception as e:
        print(f"Erro ao buscar o ticker: {e}")

if __name__ == "__main__":
    while True:
        entrada = input("\nDigite parte do nome ou ticker (ou 'sair' para encerrar): ").strip()
        if entrada.lower() == "sair":
            break
        buscar_ticker(entrada)
