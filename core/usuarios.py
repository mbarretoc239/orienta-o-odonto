"""Gestao de usuarios pelo admin."""
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


def desbloquear(db, usuario):
    db.execute("UPDATE ori_usuarios SET tentativas=0, bloqueado_ate=NULL WHERE usuario=?", (usuario,))
