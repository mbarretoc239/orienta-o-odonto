"""Cria o primeiro admin. Uso: python scripts/criar_admin.py (pede e-mail, nome e senha no terminal)."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import auth  # noqa: E402
from core.db import criar_schema, get_db  # noqa: E402

db = get_db()
criar_schema(db)
email = input("E-mail do admin: ")
nome = input("Nome: ")
senha = getpass.getpass("Senha (min. 8 caracteres): ")
if len(senha) < auth.MIN_SENHA:
    sys.exit("Senha muito curta.")
auth.criar_admin(db, email, nome, senha)
print(f"Admin ativo em {db.nome}: {email.strip().lower()}")
