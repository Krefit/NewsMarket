# 📊 Projeto Data Lake - Mercado Financeiro

Este projeto tem como objetivo a criação de um *data lake* com dados de ações, preços e notícias, centralizados em um banco de dados DuckDB. Ele automatiza a coleta e persistência de informações de diferentes fontes para análises e modelagens futuras.

---

## 📁 Estrutura do Projeto

```
projeto_data_lake/
├── banco_dados/                      # Arquivos DuckDB gerados
├── scripts/                          # Scripts de coleta
│   ├── coleta_simbolos_b3.py
│   ├── coleta_precos_diarios_yfinance.py
│   ├── coleta_precos_intradiarios_binance.py
│   └── coleta_noticias_gnews.py
├── .venv/                            # Ambiente virtual Python
├── requirements.txt                  # Dependências do projeto
└── run_all.bat                       # Script para executar todas as coletas
```

---

## ⚙️ Requisitos

- Python 3.10+
- DuckDB
- Ambiente virtual (recomendado)
- Conta de API no [GNews](https://gnews.io/) (gratuita)
- Conta na [Binance](https://binance.com) com API habilitada (opcional)

---

## 📦 Instalação

1. Clone este repositório:
```bash
git clone https://github.com/seu-usuario/projeto_data_lake.git
cd projeto_data_lake
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

---

## 🧠 Funcionalidades

| Script                                | Descrição |
|---------------------------------------|-----------|
| `coleta_simbolos_b3.py`               | Baixa a lista de ativos da B3 (em breve substituível por MetaTrader5). |
| `coleta_precos_diarios_yfinance.py`   | Coleta preços diários dos ativos via Yahoo Finance. |
| `coleta_precos_intradiarios_binance.py` | Coleta dados intradiários de criptoativos da Binance. |
| `coleta_noticias_gnews.py`            | Busca notícias relacionadas a temas financeiros via GNews API. |

---

## ▶️ Execução

Execute o arquivo `run_all.bat` para rodar todos os scripts em sequência:

```bash
run_all.bat
```

Ou execute individualmente:

```bash
python scripts/coleta_precos_diarios_yfinance.py
```

---

## 🐛 Possíveis Erros Comuns

- `ModuleNotFoundError`: Certifique-se de que o ambiente virtual está ativado e as dependências instaladas.
- `duckdb.IOException`: A pasta `banco_dados/` precisa existir antes da execução.
- `Erro 400 na GNews`: Verifique se a API Key está correta e dentro dos limites de requisição.

---

## 📘 Futuras Melhorias

- Suporte a MetaTrader5 para dados da B3.
- Normalização e limpeza dos dados.
- Integração com ferramentas de visualização (e.g. Dash, Power BI).
- Criação de pipelines automatizados (Airflow, Prefect).

---

## 👨‍💻 Autor

Gustavo Krawczyk Santos  
Projeto pessoal para estudos em Ciência de Dados no mercado financeiro.

---

## 📜 Licença

MIT License. Consulte o arquivo `LICENSE` para mais informações.
