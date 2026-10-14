"""Gera um backup em planilha dos dados (orientacoes, prestadores, desvios, auditoria).

Uso: python scripts/backup.py [--pasta CAMINHO] [--manter N]
Padrao: pasta backups/ do projeto (fora do git) e os 30 backups mais recentes.
Pode ser agendado no Agendador de Tarefas do Windows.
"""
import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import backup  # noqa: E402
from core.db import get_db  # noqa: E402


def main():
    if sys.stdout is None:  # pythonw (Agendador, sem janela): nao ha console, entao o log e gravado direto
        args_pasta = RAIZ / "backups"
        args_pasta.mkdir(exist_ok=True)
        sys.stdout = sys.stderr = open(args_pasta / "backup.log", "a", encoding="utf-8", buffering=1)
        print(f"--- {datetime.now():%d/%m/%Y %H:%M:%S}")
    else:  # saida redirecionada para arquivo: mantem os acentos corretos
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
    try:
        main()
    except Exception:  # noqa: BLE001 - sem console, o erro precisa ficar no log; o codigo de saida avisa o Agendador
        traceback.print_exc()
        sys.exit(1)
