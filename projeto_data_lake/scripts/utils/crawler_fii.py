import os
import time
import argparse
import requests
import duckdb
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- Configurações e paths ---

def get_db_path() -> str:
    current_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    return os.path.join(project_root, 'daily_history.db')

DB_PATH = get_db_path()

# Cabeçalhos completos para simular navegador real e evitar bloqueios
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.clubefii.com.br/"
}

# Sessão global para manter cookies e cabeçalhos
session = requests.Session()
session.headers.update(HEADERS)

# --- Funções de DB ---

def init_db(path: str = DB_PATH):
    con = duckdb.connect(path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS fii_history (
            url          VARCHAR,
            nome         VARCHAR,
            ticker       VARCHAR,
            preco        DOUBLE,
            coleta_ts    TIMESTAMP
        )
        """
    )
    return con

# --- Parsing de página de FII ---

def parse_fii_page(url: str) -> dict:
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    nome_tag = soup.select_one("h1.titulo, header h1")
    ticker_tag = soup.select_one("span.fii-ticker, .ticker")
    preco_tag = soup.select_one("div.info-fii span.valor, .price")
    if not (nome_tag and ticker_tag and preco_tag):
        raise ValueError(f"Não reconheceu campos de FII nesta página: {url}")

    nome = nome_tag.get_text(strip=True)
    ticker = ticker_tag.get_text(strip=True)
    preco_str = preco_tag.get_text(strip=True)
    preco = float(
        preco_str.replace("R$", "").replace(".", "").replace(",", ".")
    )

    return {
        "url": url,
        "nome": nome,
        "ticker": ticker,
        "preco": preco,
        "coleta_ts": time.strftime("%Y-%m-%d %H:%M:%S")
    }

# --- Crawl da listagem de FIIs ---

def crawl_listing(listing_url: str) -> set[str]:
    # Garante barra final
    if not listing_url.endswith('/'):
        listing_url += '/'
    # Acessa homepage para cookies
    session.get('https://www.clubefii.com.br/')

    resp = session.get(listing_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Aguarda a tabela principal de FIIs
    table = soup.find('table')
    if not table:
        raise RuntimeError(f"Tabela não encontrada em: {listing_url}")

    links = set()
    for a in table.select('a[href]'):
        href = a['href']
        if href.startswith('#') or href.lower().startswith('javascript:'):
            continue
        full = urljoin(listing_url, href)
        links.add(full)
    return links

# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Crawler de FIIs NewsMarket")
    parser.add_argument(
        '--listing-url',
        default="https://www.clubefii.com.br/fundo_imobiliario_lista/",
        help='URL da página de listagem (tabela) de FIIs (com barra no final)'
    )
    args = parser.parse_args()

    print("Iniciando coleta de FIIs...")
    con = init_db()

    try:
        print(f"Crawling listagem em: {args.listing_url}")
        fii_pages = crawl_listing(args.listing_url)
        print(f"Total de URLs de FII encontradas: {len(fii_pages)}")
    except Exception as e:
        print(f"Erro ao coletar listagem: {e}")
        return

    for url in sorted(fii_pages):
        try:
            data = parse_fii_page(url)
            con.execute(
                "INSERT INTO fii_history VALUES (?, ?, ?, ?, ?)",
                [data['url'], data['nome'], data['ticker'], data['preco'], data['coleta_ts']]
            )
            print(f"[OK] {data['ticker']}")
        except Exception as e:
            print(f"[ERRO] {url}: {e}")
        time.sleep(1)

    con.close()
    print("Coletas concluídas.")

if __name__ == '__main__':
    main()
