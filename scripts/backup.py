"""Gera um backup em planilha dos dados (orientacoes, prestadores, desvios, auditoria).

Uso: python scripts/backup.py [--pasta CAMINHO] [--manter N]
Padrao: pasta backups/ do projeto (fora do git) e os 30 backups mais recentes.
Pode ser agendado no Agendador de Tarefas do Windows.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import backup  # noqa: E402
from core.db import get_db  # noqa: E402


def main():
    # quando a saida e redirecionada para um arquivo (Agendador de Tarefas), mantem os acentos corretos
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pasta", type=Path, default=RAIZ / "backups")
    ap.add_argument("--manter", type=int, default=30)
    args = ap.parse_args()

    db = get_db()
    caminho, contagens, apagados = backup.salvar(db, args.pasta, args.manter)
    print(f"Backup gerado em {caminho} (banco: {db.nome})")
    for aba, n in contagens.items():
        print(f"  {aba}: {n} linhas")
    if apagados:
        print(f"Backups antigos removidos pela retencao ({args.manter}): {', '.join(apagados)}")


if __name__ == "__main__":
    main()
