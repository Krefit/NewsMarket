"""Linha de comando do NewsMarket.

    python -m newsmarket coletar                 # preços + notícias + sentimento (incremental)
    python -m newsmarket coletar --backfill-desde 2024-01-01
    python -m newsmarket status
    python -m newsmarket impacto [--ticker MXRF11] [--janela 3]
    python -m newsmarket prever [--horizonte 1]
    python -m newsmarket rodar                   # coletar + prever (o "bot" diário)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import pandas as pd

from . import config as cfgmod
from .analise import impacto, sentimento
from .coleta import noticias, precos
from .db import conectar, upsert
from .modelo import treino

AVISO = ("Aviso: sinais gerados por modelo estatístico para estudo. Não é recomendação de "
         "investimento; o histórico de acerto está no relatório de validação acima.")


def cmd_coletar(con, cfg, args):
    tickers = [a.ticker for a in cfg.ativos] + list(cfg.referencias.values())
    print("Preços...")
    r = precos.atualizar(con, tickers, completo=args.completo)
    falhas = [t for t, n in r.items() if n < 0]
    print(f"  {sum(n for n in r.values() if n > 0)} linhas gravadas"
          + (f"; falharam: {', '.join(falhas)}" if falhas else ""))
    print("Notícias...")
    n = noticias.coletar(con, list(cfg.ativos))
    if args.backfill_desde:
        n += noticias.backfill(con, list(cfg.ativos), date.fromisoformat(args.backfill_desde))
    print(f"  {n} notícias novas")
    print("Sentimento...")
    print(f"  {sentimento.calcular(con, metodo=args.sentimento)} notícias pontuadas ({args.sentimento})")


def cmd_status(con, cfg, args):
    df = con.execute("""
        WITH p AS (SELECT ticker, count(*) pregoes, min(data) desde, max(data) ate
                   FROM precos GROUP BY ticker),
             n AS (SELECT na.ticker, count(*) noticias, max(n.publicada_em) ultima_noticia
                   FROM noticia_ativo na JOIN noticias n ON n.id = na.noticia_id
                   GROUP BY na.ticker)
        SELECT coalesce(p.ticker, n.ticker) ticker, pregoes, desde, ate,
               coalesce(noticias, 0) noticias, ultima_noticia
        FROM p FULL JOIN n ON p.ticker = n.ticker ORDER BY 1
    """).df()
    print(df.to_string(index=False) if not df.empty else "Banco vazio. Rode: python -m newsmarket coletar")


def cmd_impacto(con, cfg, args):
    alvos = [cfg.ativo(args.ticker)] if args.ticker else list(cfg.ativos)
    todos = []
    for a in alvos:
        ref_tk = cfg.referencias.get("ifix" if a.tipo == "fii" else "ibov")
        ref = precos.carregar(con, ref_tk) if ref_tk else None
        ev = impacto.eventos(impacto.carregar_noticias(con, a.ticker),
                             precos.carregar(con, a.ticker), ref, janela=args.janela)
        if ev.empty:
            print(f"{a.ticker}: sem notícias com preço correspondente.")
            continue
        ev["ticker"] = a.ticker
        todos.append(ev)
        print(f"\n== {a.ticker} ({len(ev)} notícias) — retorno anormal vs "
              f"{ref_tk or 'nenhuma referência'}, acumulado = dia 0 a +{args.janela}")
        print(impacto.resumo(ev).round(3).to_string(index=False))
    if len(todos) > 1:
        print(f"\n== TODOS OS ATIVOS")
        print(impacto.resumo(pd.concat(todos)).round(3).to_string(index=False))


def cmd_prever(con, cfg, args):
    base = treino.base_completa(con, cfg, args.horizonte)
    if base.empty:
        print("Sem dados. Rode primeiro: python -m newsmarket coletar")
        return 1
    print(f"Validação walk-forward (horizonte = {args.horizonte} pregão(ões))...")
    try:
        val = treino.validar(base, args.horizonte)
    except ValueError as e:
        print(f"  {e}")
        return 1
    print(f"  {val.n_linhas} linhas, {val.periodo[0]} a {val.periodo[1]}")
    print(val.tabela.round(4).to_string(index=False))
    print(f"  Ganho de acurácia com notícias: {val.ganho_noticias() * 100:+.2f} p.p.")
    t = val.tabela.set_index("modelo")
    acc = float(t.loc["preco+noticias", "acuracia"])
    acc_trivial = float(t.loc["sempre_classe_majoritaria", "acuracia"])

    pred = treino.treinar_e_prever(base, args.horizonte, acc,
                                   salvar_em=cfgmod.RAIZ / "modelos" / f"modelo_h{args.horizonte}.joblib")
    if acc < acc_trivial + treino.MARGEM_MINIMA:
        print(f"\n  O modelo não superou o palpite trivial em {treino.MARGEM_MINIMA * 100:.0f} p.p. "
              "na validação: todos os sinais ficam NEUTRO.")
        pred["sinal"] = "NEUTRO"
    upsert(con, "predicoes", pred)
    print("\nPróximo movimento previsto:")
    print(pred[["ticker", "data_ref", "prob_alta", "sinal"]].round(3).to_string(index=False))
    print("\n" + AVISO)
    return 0


def cmd_rodar(con, cfg, args):
    cmd_coletar(con, cfg, args)
    return cmd_prever(con, cfg, args)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="newsmarket", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ativos", help="arquivo de ativos (padrão: ativos.toml)")
    ap.add_argument("--db", help="caminho do banco DuckDB")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def opc_coleta(p):
        p.add_argument("--completo", action="store_true", help="rebaixa todo o histórico de preços")
        p.add_argument("--backfill-desde", metavar="AAAA-MM-DD", help="busca notícias antigas desde a data")
        p.add_argument("--sentimento", choices=["lexico", "finbert"], default="lexico")

    opc_coleta(sub.add_parser("coletar", help="atualiza preços, notícias e sentimento"))
    sub.add_parser("status", help="resumo do que há no banco")
    p = sub.add_parser("impacto", help="estudo de evento: efeito das notícias no preço")
    p.add_argument("--ticker")
    p.add_argument("--janela", type=int, default=3)
    p = sub.add_parser("prever", help="valida o modelo e prevê o próximo movimento")
    p.add_argument("--horizonte", type=int, default=1)
    p = sub.add_parser("rodar", help="coletar + prever (rotina diária)")
    opc_coleta(p)
    p.add_argument("--horizonte", type=int, default=1)

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    cfg = cfgmod.carregar(args.ativos, args.db)
    con = conectar(cfg.db_path)
    try:
        fn = {"coletar": cmd_coletar, "status": cmd_status, "impacto": cmd_impacto,
              "prever": cmd_prever, "rodar": cmd_rodar}[args.cmd]
        return fn(con, cfg, args) or 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
