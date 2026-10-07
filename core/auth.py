"""Usuarios: autocadastro (fica pendente), aprovacao pelo admin, hash scrypt.

O login e o mesmo usuario do SIGO (texto livre, sem e-mail).
"""
import hashlib
import hmac
import os
import re

PERFIS = ("contas", "gestor", "admin")
_USUARIO = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
MIN_SENHA = 8


def normalizar_usuario(usuario) -> str:
    return (usuario or "").strip().lower()


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


def registrar_usuario(db, usuario, nome, senha):
    """Retorna (ok, mensagem). A conta nasce pendente, com perfil contas."""
    usuario = normalizar_usuario(usuario)
    nome = (nome or "").strip()
    if not _USUARIO.match(usuario):
        return False, "Usuario invalido: use 3 a 40 caracteres (letras, numeros, ponto, hifen ou sublinhado)."
    if not nome:
        return False, "Informe o nome."
    if len(senha or "") < MIN_SENHA:
        return False, f"A senha precisa ter ao menos {MIN_SENHA} caracteres."
    if db.query("SELECT 1 FROM ori_usuarios WHERE usuario=?", (usuario,)):
        return False, "Ja existe cadastro com este usuario."
    db.execute(
        "INSERT INTO ori_usuarios (usuario, nome, senha_hash) VALUES (?,?,?)",
        (usuario, nome, hash_senha(senha)),
    )
    return True, "Cadastro enviado. Aguarde a aprovacao do administrador."


def autenticar(db, usuario, senha):
    """Retorna (usuario|None, mensagem)."""
    usuario = normalizar_usuario(usuario)
    linhas = db.query("SELECT * FROM ori_usuarios WHERE usuario=?", (usuario,))
    if not linhas or not confere_senha(senha or "", linhas[0]["senha_hash"]):
        return None, "Usuario ou senha incorretos."
    u = linhas[0]
    if u["status"] == "pendente":
        return None, "Cadastro aguardando aprovacao do administrador."
    if u["status"] != "ativo":
        return None, "Usuario inativo."
    return {"usuario": u["usuario"], "nome": u["nome"], "perfil": u["perfil"]}, ""


def criar_admin(db, usuario, nome, senha):
    """Cria (ou promove) um admin ativo. Uso: scripts/criar_admin.py."""
    db.execute(
        "INSERT INTO ori_usuarios (usuario, nome, senha_hash, perfil, status) VALUES (?,?,?,'admin','ativo') "
        "ON CONFLICT(usuario) DO UPDATE SET perfil='admin', status='ativo', senha_hash=excluded.senha_hash",
        (normalizar_usuario(usuario), nome.strip(), hash_senha(senha)),
    )
