"""Carga inicial: desvios, prestadores (dPrestadores) e historico de orientacoes (planilha).

Uso: python scripts/migrar.py [--dry-run]
Gera data/conflitos_migracao.csv para revisao humana. Roda apenas em banco sem orientacoes.
"""
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.db import criar_schema, get_db  # noqa: E402
from migracao import carga, leitura, montagem  # noqa: E402

DADOS = RAIZ / "data"
ARQ_PRESTADORES = DADOS / "dPrestadores.xlsx"
ARQ_PLANILHA = DADOS / "orientacao_adm_interna.xlsx"


def main(dry_run=False, recarregar=False):
    db = None
    if not dry_run:
        db = get_db()
        criar_schema(db)
        if not recarregar and db.query("SELECT 1 FROM ori_orientacoes LIMIT 1"):
            sys.exit("Banco ja tem orientacoes: migracao cancelada para nao duplicar "
                     "(use --recarregar para refazer so as orientacoes de autor 'migracao').")

    conflitos = []
    desvios = montagem.montar_desvios(leitura.ler_desvios(ARQ_PLANILHA))
    prest = montagem.montar_prestadores(
        leitura.ler_base_oficial(ARQ_PRESTADORES), leitura.ler_ficha_prestadores(ARQ_PRESTADORES), conflitos)
    orient = montagem.montar_orientacoes(leitura.ler_acompanhamento(ARQ_PLANILHA), desvios, prest, conflitos)

    DADOS.mkdir(exist_ok=True)
    pd.DataFrame(conflitos).to_csv(DADOS / "conflitos_migracao.csv", index=False, encoding="utf-8-sig", sep=";")
    print(f"desvios={len(desvios)} prestadores={len(prest)} orientacoes={len(orient)}")
    print("conflitos:", dict(Counter(c["tipo"] for c in conflitos)))
    if dry_run:
        print("dry-run: nada gravado.")
        return
    if recarregar:
        try:
            apagadas, backup = carga.preparar_recarga(db, orient, DADOS)
        except RuntimeError as e:
            sys.exit(str(e))
        print(f"recarga: {apagadas} orientacoes da migracao apagadas (backup em {backup})")
    print(carga.gravar_desvios(db, desvios))
    print(carga.gravar_prestadores(db, prest))
    print(carga.gravar_orientacoes(db, orient))


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv, recarregar="--recarregar" in sys.argv)
