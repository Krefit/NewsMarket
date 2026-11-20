# 📰📈 NewsMarket

Bot que guarda o histórico de ativos da B3 (começando por **FIIs**), mede o **impacto das
notícias** no preço de cada ativo e faz uma **predição de alta ou baixa** para o próximo pregão.

> ⚠️ Projeto de estudo. As previsões não são recomendação de investimento. O próprio bot
> mostra o histórico de acerto do modelo e neutraliza os sinais quando ele não supera um
> palpite trivial.

---

## Como funciona

```
 Yahoo Finance ──► precos ─────────────┐
                                       ├─► features ─► modelo ─► predicoes
 Google News RSS ─► noticias ─► sentimento ─┘        (alta/baixa + prob.)
 Portais (RSS)        │                 │
                      └─ noticia_ativo  └─► estudo de evento (impacto)
```

1. **Coleta de preços** (`yfinance`, sem chave): histórico diário com preço ajustado por
   proventos, para que a queda na data-com dos FIIs não seja lida como "impacto de notícia".
2. **Coleta de notícias** (RSS, sem chave): busca no Google News pelos termos de cada ativo
   e lê os feeds do InfoMoney, Money Times e Brazil Journal. Cada notícia é associada aos ativos
   que cita. O Google News só devolve cerca de 100 itens por busca, por isso existem a coleta
   diária e o *backfill* mês a mês.
3. **Sentimento**: score de −1 a +1 por manchete. O padrão é um léxico financeiro em português
   voltado para FIIs (vacância, inadimplência, dividendos, emissão...). Opcionalmente dá para usar
   o modelo **FinBERT-PT-BR**.
4. **Impacto** (estudo de evento): retorno anormal (ativo − IFIX, ou − Ibovespa para ações)
   no dia da notícia e acumulado nos dias seguintes, separado por notícias positivas, negativas
   e neutras, com estatística t.
5. **Predição**: classificador (*gradient boosting*) que prevê se o preço sobe ou cai nos
   próximos *N* pregões. A validação é **walk-forward**, ou seja, sempre treina no passado e
   testa no futuro, e compara três versões:
   - palpite trivial (sempre a classe mais comum);
   - modelo só com preços;
   - modelo com preços + notícias, que é o que responde à pergunta do projeto.

Tudo fica em um único banco **DuckDB** (`dados/newsmarket.duckdb`), com as tabelas
`precos`, `noticias`, `noticia_ativo`, `sentimento` e `predicoes`.

---

## Instalação (Windows)

```bat
git clone https://github.com/Krefit/NewsMarket.git
cd NewsMarket
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Requer Python 3.11+. Nenhuma chave de API é necessária. O `.env` é opcional (veja `.env.example`).

## Uso

```bat
:: 1ª vez: histórico de preços + notícias desde 2023 (o backfill leva alguns minutos)
python -m newsmarket coletar --backfill-desde 2023-01-01

python -m newsmarket status                  :: o que há no banco
python -m newsmarket impacto                 :: efeito das notícias, por ativo
python -m newsmarket impacto --ticker MXRF11 --janela 5
python -m newsmarket prever                  :: valida o modelo e prevê o próximo pregão
python -m newsmarket prever --horizonte 5    :: direção em 5 pregões

python -m newsmarket rodar                   :: rotina diária = coletar + prever
```

Para virar um bot, agende o `rodar_diario.bat` no Agendador de Tarefas do Windows
(diariamente, depois das 18h). O log vai para `logs\rodar_diario.log`.

### Escolher os ativos

Edite o `ativos.toml`. Para cada ativo, informe o ticker, o tipo (`fii` ou `acao`) e os
termos usados para encontrar notícias (ticker, nome do fundo, gestor):

```toml
[[ativo]]
ticker = "MXRF11"
tipo = "fii"
termos = ["MXRF11", "Maxi Renda"]
```

### Sentimento com FinBERT (opcional)

```bat
pip install transformers torch
python -m newsmarket coletar --sentimento finbert
```

---

## Estrutura

```
newsmarket/
├── config.py            # caminhos e leitura do ativos.toml
├── db.py                # esquema DuckDB e gravação idempotente
├── coleta/
│   ├── precos.py        # yfinance
│   └── noticias.py      # RSS: Google News + portais, associação notícia↔ativo
├── analise/
│   ├── sentimento.py    # léxico PT-BR / FinBERT-PT-BR
│   └── impacto.py       # estudo de evento
├── modelo/
│   ├── features.py      # features de preço e de notícia, sem vazamento do futuro
│   └── treino.py        # validação walk-forward, treino e predição
└── __main__.py          # linha de comando
tests/                   # pytest com dados sintéticos (rode: python -m pytest)
legado/                  # scripts da versão 1 (Alpha Vantage, Finnhub, crawler Clube FII)
```

## Limitações conhecidas

- **Prever a direção de preços é difícil.** Acurácias de 52–55% fora da amostra já são
  consideradas boas. Comece olhando o `impacto`, que diz se existe sinal antes de confiar
  no `prever`.
- FIIs pequenos têm poucas notícias. O backfill e a coleta diária ao longo de meses
  melhoram isso.
- O horário das notícias vem do RSS. Notícias publicadas depois das 17h contam para o
  pregão seguinte.
- O Yahoo Finance pode ter falhas pontuais em tickers da B3. O bot registra o erro e segue
  com os demais ativos.

---

Gustavo Krawczyk Santos · Licença MIT
