"""Usuarios: autocadastro (fica pendente), aprovacao pelo admin, hash scrypt."""
import hashlib
import hmac
import os
import re

PERFIS = ("contas", "gestor", "admin")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_SENHA = 8


def hash_senha(senha: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=2**14, r=8, p=1)
    return f"scrypt${sal.hex()}${h.hex()}"


def confere_senha(senha: str, armazenado: str) -> bool:
    try:
        _, sal, h = armazenado.split("$")
        novo = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=2**14, r=8, p=1)
        return hmac.compare_digest(novo.hex(), h)
    except ValueError:
        return False


def registrar_usuario(db, email, nome, senha):
    """Retorna (ok, mensagem). A conta nasce pendente, com perfil contas."""
    email = (email or "").strip().lower()
    nome = (nome or "").strip()
    if not _EMAIL.match(email):
        return False, "E-mail invalido."
    if not nome:
        return False, "Informe o nome."
    if len(senha or "") < MIN_SENHA:
        return False, f"A senha precisa ter ao menos {MIN_SENHA} caracteres."
    if db.query("SELECT 1 FROM ori_usuarios WHERE email=?", (email,)):
        return False, "Ja existe cadastro com este e-mail."
    db.execute(
        "INSERT INTO ori_usuarios (email, nome, senha_hash) VALUES (?,?,?)",
        (email, nome, hash_senha(senha)),
    )
    return True, "Cadastro enviado. Aguarde a aprovacao do administrador."


def autenticar(db, email, senha):
    """Retorna (usuario|None, mensagem)."""
    email = (email or "").strip().lower()
    linhas = db.query("SELECT * FROM ori_usuarios WHERE email=?", (email,))
    if not linhas or not confere_senha(senha or "", linhas[0]["senha_hash"]):
        return None, "E-mail ou senha incorretos."
    u = linhas[0]
    if u["status"] == "pendente":
        return None, "Cadastro aguardando aprovacao do administrador."
    if u["status"] != "ativo":
        return None, "Usuario inativo."
    return {"email": u["email"], "nome": u["nome"], "perfil": u["perfil"]}, ""


def criar_admin(db, email, nome, senha):
    """Cria (ou promove) um admin ativo. Uso: scripts/criar_admin.py."""
    db.execute(
        "INSERT INTO ori_usuarios (email, nome, senha_hash, perfil, status) VALUES (?,?,?,'admin','ativo') "
        "ON CONFLICT(email) DO UPDATE SET perfil='admin', status='ativo', senha_hash=excluded.senha_hash",
        (email.strip().lower(), nome.strip(), hash_senha(senha)),
    )
