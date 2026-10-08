"""Usuarios: autocadastro (fica pendente), aprovacao pelo admin, hash scrypt, codigo de recuperacao.

O login e o mesmo usuario do SIGO (texto livre, sem e-mail). Senha e codigo de recuperacao
sao guardados apenas como hash.
"""
import hashlib
import hmac
import os
import re
import secrets

PERFIS = ("contas", "gestor", "admin")
_USUARIO = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
_ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I para nao confundir
MIN_SENHA = 8
MAX_TENTATIVAS = 5
BLOQUEIO_MIN = 15


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
    except (ValueError, AttributeError):
        return False


# ---------- codigo de recuperacao ----------

def gerar_codigo() -> str:
    """Ex.: K7QM-4XD2-9PBT (12 caracteres, ~60 bits)."""
    c = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(12))
    return f"{c[:4]}-{c[4:8]}-{c[8:]}"


def _normalizar_codigo(codigo) -> str:
    return re.sub(r"[^A-Z0-9]", "", (codigo or "").upper())


def _hash_codigo(codigo: str) -> str:
    return hash_senha(_normalizar_codigo(codigo))


def _confere_codigo(codigo, armazenado) -> bool:
    return bool(armazenado) and confere_senha(_normalizar_codigo(codigo), armazenado)


# ---------- bloqueio por tentativas (compartilhado entre login e redefinicao) ----------

def _carregar(db, usuario):
    r = db.query(
        "SELECT *, MAX(0, CAST((julianday(bloqueado_ate) - julianday('now')) * 1440 AS INTEGER) + 1) AS min_restantes, "
        "(bloqueado_ate IS NOT NULL AND bloqueado_ate > datetime('now')) AS bloqueado "
        "FROM ori_usuarios WHERE usuario=?",
        (usuario,),
    )
    return r[0] if r else None


def _falha(db, u, usuario, o_que):
    """Conta um erro; apos MAX_TENTATIVAS bloqueia a conta. Retorna a mensagem."""
    erros = (u["tentativas"] or 0) + 1
    if erros >= MAX_TENTATIVAS:
        db.execute(
            "UPDATE ori_usuarios SET tentativas=0, bloqueado_ate=datetime('now', ?) WHERE usuario=?",
            (f"+{BLOQUEIO_MIN} minutes", usuario),
        )
        return f"Muitas tentativas incorretas. Conta bloqueada por {BLOQUEIO_MIN} minutos."
    db.execute("UPDATE ori_usuarios SET tentativas=? WHERE usuario=?", (erros, usuario))
    return f"{o_que} Restam {MAX_TENTATIVAS - erros} tentativa(s)."


def _msg_bloqueio(u):
    return f"Muitas tentativas incorretas. Tente novamente em {u['min_restantes']} minuto(s)."


# ---------- cadastro e login ----------

def registrar_usuario(db, usuario, nome, senha):
    """Retorna (ok, mensagem, codigo_de_recuperacao|None). A conta nasce pendente, com perfil contas."""
    usuario = normalizar_usuario(usuario)
    nome = (nome or "").strip()
    if not _USUARIO.match(usuario):
        return False, "Usuario invalido: use 3 a 40 caracteres (letras, numeros, ponto, hifen ou sublinhado).", None
    if not nome:
        return False, "Informe o nome.", None
    if len(senha or "") < MIN_SENHA:
        return False, f"A senha precisa ter ao menos {MIN_SENHA} caracteres.", None
    if db.query("SELECT 1 FROM ori_usuarios WHERE usuario=?", (usuario,)):
        return False, "Ja existe cadastro com este usuario.", None
    codigo = gerar_codigo()
    db.execute(
        "INSERT INTO ori_usuarios (usuario, nome, senha_hash, codigo_hash) VALUES (?,?,?,?)",
        (usuario, nome, hash_senha(senha), _hash_codigo(codigo)),
    )
    return True, "Cadastro enviado. Aguarde a aprovacao do administrador.", codigo


def _dados(u):
    return {"usuario": u["usuario"], "nome": u["nome"], "perfil": u["perfil"], "trocar_senha": bool(u["trocar_senha"])}


def autenticar(db, usuario, senha):
    """Retorna (usuario|None, mensagem)."""
    usuario = normalizar_usuario(usuario)
    u = _carregar(db, usuario)
    if not u:
        return None, "Usuario ou senha incorretos."
    if u["bloqueado"]:
        return None, _msg_bloqueio(u)
    if not confere_senha(senha or "", u["senha_hash"]):
        return None, _falha(db, u, usuario, "Usuario ou senha incorretos.")
    if u["status"] == "pendente":
        return None, "Cadastro aguardando aprovacao do administrador."
    if u["status"] != "ativo":
        return None, "Usuario inativo."
    if u["tentativas"] or u["bloqueado_ate"]:
        db.execute("UPDATE ori_usuarios SET tentativas=0, bloqueado_ate=NULL WHERE usuario=?", (usuario,))
    return _dados(u), ""


def dados_usuario(db, usuario):
    """Usuario ativo (para restaurar sessao); None se nao existir ou nao estiver ativo."""
    r = db.query("SELECT * FROM ori_usuarios WHERE usuario=?", (usuario,))
    if not r or r[0]["status"] != "ativo":
        return None
    return _dados(r[0])


def criar_admin(db, usuario, nome, senha):
    """Cria (ou promove) um admin ativo. Retorna o codigo de recuperacao. Uso: scripts/criar_admin.py."""
    codigo = gerar_codigo()
    db.execute(
        "INSERT INTO ori_usuarios (usuario, nome, senha_hash, perfil, status, codigo_hash) "
        "VALUES (?,?,?,'admin','ativo',?) "
        "ON CONFLICT(usuario) DO UPDATE SET perfil='admin', status='ativo', senha_hash=excluded.senha_hash, "
        "codigo_hash=excluded.codigo_hash, tentativas=0, bloqueado_ate=NULL, trocar_senha=0",
        (normalizar_usuario(usuario), nome.strip(), hash_senha(senha), _hash_codigo(codigo)),
    )
    return codigo


# ---------- recuperacao e troca de senha ----------

def _sem_sessoes(usuario):
    return ("DELETE FROM ori_sessoes WHERE usuario=?", (usuario,))


def redefinir_com_codigo(db, usuario, codigo, nova_senha):
    """'Esqueci minha senha': confere o codigo de recuperacao. Retorna (ok, mensagem, novo_codigo|None).
    Erros contam nas mesmas 5 tentativas do login."""
    usuario = normalizar_usuario(usuario)
    invalido = "Usuario ou codigo de recuperacao invalidos."
    u = _carregar(db, usuario)
    if not u:
        return False, invalido, None
    if u["bloqueado"]:
        return False, _msg_bloqueio(u), None
    if len(nova_senha or "") < MIN_SENHA:
        return False, f"A nova senha precisa ter ao menos {MIN_SENHA} caracteres.", None
    if not _confere_codigo(codigo, u["codigo_hash"]):
        return False, _falha(db, u, usuario, invalido), None
    novo = gerar_codigo()
    db.batch([
        (
            "UPDATE ori_usuarios SET senha_hash=?, codigo_hash=?, tentativas=0, bloqueado_ate=NULL, trocar_senha=0 "
            "WHERE usuario=?",
            (hash_senha(nova_senha), _hash_codigo(novo), usuario),
        ),
        _sem_sessoes(usuario),
    ])
    return True, "Senha redefinida. Guarde o novo codigo de recuperacao.", novo


def trocar_senha(db, usuario, senha_atual, nova_senha):
    """Troca de senha por quem ja esta logado (obrigatoria apos redefinicao pelo admin).
    Retorna (ok, mensagem, codigo|None); gera codigo de recuperacao se a pessoa ainda nao tinha um."""
    usuario = normalizar_usuario(usuario)
    u = _carregar(db, usuario)
    if not u or not confere_senha(senha_atual or "", u["senha_hash"]):
        return False, "Senha atual incorreta.", None
    if len(nova_senha or "") < MIN_SENHA:
        return False, f"A nova senha precisa ter ao menos {MIN_SENHA} caracteres.", None
    if confere_senha(nova_senha, u["senha_hash"]):
        return False, "A nova senha deve ser diferente da atual.", None
    codigo = None if u["codigo_hash"] else gerar_codigo()
    db.execute(
        "UPDATE ori_usuarios SET senha_hash=?, trocar_senha=0, codigo_hash=COALESCE(?, codigo_hash) WHERE usuario=?",
        (hash_senha(nova_senha), _hash_codigo(codigo) if codigo else None, usuario),
    )
    return True, "Senha alterada.", codigo


def senha_temporaria(db, usuario):
    """Admin: gera senha temporaria e obriga a troca no proximo acesso. Retorna a senha (mostrar uma vez)."""
    temporaria = secrets.token_urlsafe(9)
    db.batch([
        (
            "UPDATE ori_usuarios SET senha_hash=?, trocar_senha=1, tentativas=0, bloqueado_ate=NULL WHERE usuario=?",
            (hash_senha(temporaria), usuario),
        ),
        _sem_sessoes(usuario),
    ])
    return temporaria


def novo_codigo(db, usuario):
    """Admin: gera outro codigo de recuperacao (para quem perdeu ou nunca teve). Retorna o codigo."""
    codigo = gerar_codigo()
    db.execute("UPDATE ori_usuarios SET codigo_hash=? WHERE usuario=?", (_hash_codigo(codigo), usuario))
    return codigo
