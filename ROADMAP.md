## 🚧 Roadmap do Projeto Data Lake - NewsMarket

Este roadmap resume as etapas planejadas, em andamento e concluídas no projeto de coleta e análise de dados de ações e notícias para o projeto "NewsMarket".

### 📌 Visão Geral

O projeto tem como objetivo criar um **data lake** com dados de preços de ações (diários e intradiários) e notícias que influenciam o mercado, armazenando tudo em formato estruturado com `DuckDB` e fontes como Yahoo Finance, Binance e GNews.

---

### ✅ Concluído

| Etapa                           | Descrição                                                 |
| ------------------------------- | --------------------------------------------------------- |
| Estrutura de diretórios         | Separação em `scripts/`, `banco_dados/`, `.venv/` etc.    |
| Coleta de preços via Binance    | Implementado para ativos disponíveis na Binance (via API) |
| Ambiente virtual Python (.venv) | Criado e configurado para o projeto                       |
| Script de inicialização `.bat`  | Automatiza as coletas em sequência usando scripts Python  |

---

### 🔄 Em Andamento

| Etapa                        | Descrição                                                        |
| ---------------------------- | ---------------------------------------------------------------- |
| Coleta de símbolos da B3     | Antiga fonte falhou, precisa nova via MT5, Cotações Web ou outra |
| Armazenamento no DuckDB      | Inserção de DataFrames pandas em DuckDB apresenta erros          |
| Geração automática do `.db`  | Definir script único para criar `acoes_duckdb.db` se não existir |
| Coleta de notícias via GNews | Retornando erro 400, revisar parâmetros e requisições            |

---

### 🕒 Planejado

| Etapa                             | Descrição                                          |
| --------------------------------- | -------------------------------------------------- |
| Dashboard para visualização       | Criação de painel com Plotly, Dash ou Streamlit    |
| Integração com API de dados da B3 | Alternativa estável para MetaTrader5               |
| Criação de testes automatizados   | Garantir integridade das coletas com `pytest`      |
| Documentação completa do projeto  | Expandir o `README.md`, comentários e dependências |

---

### 📅 Milestones Futuras

* MVP funcionando com coleta + armazenamento
* Dashboard simples para validação
* Deploy em ambiente de produção com agendamento

---

Para sugestões ou progresso detalhado, verifique também a aba **Projects** ou as **Issues** abertas no repositório.
