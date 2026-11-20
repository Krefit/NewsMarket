# 🚧 Roadmap — NewsMarket

## ✅ Versão 0.2 (reestruturação)

- [x] Remover segredos (`.env`), `.venv` e `.zip` do repositório
- [x] Banco DuckDB único, com esquema fixo e gravação idempotente
- [x] Preços via yfinance (sem chave), ajustados por proventos
- [x] Notícias via RSS (Google News + portais), com backfill mensal
- [x] Associação notícia ↔ ativo por termos configuráveis (`ativos.toml`)
- [x] Sentimento PT-BR: léxico de FIIs + FinBERT-PT-BR opcional
- [x] Estudo de evento (retorno anormal vs IFIX/Ibovespa)
- [x] Modelo de direção com validação walk-forward (preço vs preço + notícias)
- [x] CLI única + `rodar_diario.bat` para agendamento
- [x] Testes automatizados (pytest) com dados sintéticos

## 🔜 Próximos passos

- [ ] Rodar com dados reais e calibrar o léxico com as manchetes coletadas
- [ ] Comparar léxico vs FinBERT-PT-BR no estudo de evento
- [ ] Features específicas de FII: P/VP, dividend yield, proximidade da data-com
      (fonte: Fundamentus / relatórios gerenciais / CVM)
- [ ] Fatos relevantes e comunicados oficiais (B3/CVM) como fonte de notícias
- [ ] Notificação diária das previsões (Telegram ou e-mail)
- [ ] Dashboard (Streamlit): histórico, notícias no gráfico, previsões e acerto realizado
- [ ] Acompanhar o acerto real das previsões já feitas (tabela `predicoes` vs preço realizado)
- [ ] Backtest de estratégia simples (comprar no sinal ALTA) com custos
