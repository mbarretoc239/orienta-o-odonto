"""Gestao de usuarios pelo admin."""
from core import auditoria, auth
from core.auth import PERFIS

STATUS = ("pendente", "ativo", "inativo")


def listar(db):
    return db.query(
        "SELECT usuario, nome, perfil, status, tentativas, bloqueado_ate, criado_em "
        "FROM ori_usuarios ORDER BY status, nome"
    )


def atualizar(db, admin, usuario, perfil, status):
    """Retorna (ok, mensagem). O admin nao pode tirar o proprio acesso."""
    if perfil not in PERFIS or status not in STATUS:
        return False, "Perfil ou status invalido."
    if usuario == admin["usuario"] and (perfil != "admin" or status != "ativo"):
        return False, "Voce nao pode remover seu proprio acesso de admin."
    db.execute("UPDATE ori_usuarios SET perfil=?, status=? WHERE usuario=?", (perfil, status, usuario))
    return True, "Usuario atualizado."


def contar_pendentes(db) -> int:
    return db.query("SELECT COUNT(*) AS n FROM ori_usuarios WHERE status='pendente'")[0]["n"]


def pendentes(db):
    return db.query("SELECT usuario, nome, criado_em FROM ori_usuarios WHERE status='pendente' ORDER BY criado_em")


def aprovar(db, admin, usuario, perfil="contas"):
    """Libera um cadastro pendente com o perfil escolhido. Retorna (ok, mensagem)."""
    if perfil not in PERFIS:
        return False, "Perfil invalido."
    if not db.query("SELECT 1 FROM ori_usuarios WHERE usuario=? AND status='pendente'", (usuario,)):
        return False, "Cadastro nao esta pendente."
    db.batch([
        ("UPDATE ori_usuarios SET status='ativo', perfil=? WHERE usuario=? AND status='pendente'", (perfil, usuario)),
        auditoria.registrar(admin["usuario"], "ori_usuarios", usuario, "APROVAR", None, {"perfil": perfil}),
    ])
    return True, "Cadastro aprovado."


def recusar(db, admin, usuario):
    """Recusa um cadastro pendente (fica inativo; o admin ainda pode reativar). Retorna (ok, mensagem)."""
    if not db.query("SELECT 1 FROM ori_usuarios WHERE usuario=? AND status='pendente'", (usuario,)):
        return False, "Cadastro nao esta pendente."
    db.batch([
        ("UPDATE ori_usuarios SET status='inativo' WHERE usuario=? AND status='pendente'", (usuario,)),
        auditoria.registrar(admin["usuario"], "ori_usuarios", usuario, "RECUSAR"),
    ])
    return True, "Cadastro recusado."


def redefinir_senha(db, admin, usuario):
    """Gera senha temporaria (a pessoa precisa troca-la no proximo acesso). Retorna a senha."""
    senha = auth.senha_temporaria(db, usuario)
    db.batch([auditoria.registrar(admin["usuario"], "ori_usuarios", usuario, "RESET_SENHA")])
    return senha


def gerar_codigo_recuperacao(db, admin, usuario):
    codigo = auth.novo_codigo(db, usuario)
    db.batch([auditoria.registrar(admin["usuario"], "ori_usuarios", usuario, "NOVO_CODIGO")])
    return codigo


def desbloquear(db, usuario):
    db.execute("UPDATE ori_usuarios SET tentativas=0, bloqueado_ate=NULL WHERE usuario=?", (usuario,))
