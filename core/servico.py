"""Operacoes de negocio sobre prestadores e orientacoes."""
from datetime import date

from core import auditoria
from core.regras import ACAO_A_CADA, normalizar_documento, valida_documento

PODE_EDITAR = ("gestor", "admin")


def buscar_prestador(db, documento):
    linhas = db.query("SELECT * FROM ori_prestadores WHERE documento=?", (normalizar_documento(documento),))
    return linhas[0] if linhas else None


def cadastrar_prestador(db, usuario, documento, nome):
    """Cadastro de prestador novo (fora da base). Retorna (ok, mensagem)."""
    doc = normalizar_documento(documento)
    nome = " ".join((nome or "").upper().split())
    if not valida_documento(doc):
        return False, "CPF/CNPJ invalido (confira os digitos)."
    if not nome:
        return False, "Informe o nome do prestador."
    if buscar_prestador(db, doc):
        return False, "Prestador ja cadastrado."
    db.batch([
        (
            "INSERT INTO ori_prestadores (documento, nome, origem, criado_por) VALUES (?,?,'cadastro',?)",
            (doc, nome, usuario["usuario"]),
        ),
        auditoria.registrar(usuario["usuario"], "ori_prestadores", doc, "INSERT", None, {"nome": nome}),
    ])
    return True, "Prestador cadastrado."


def proximo_numero(db, documento, desvio_id):
    r = db.query(
        "SELECT COUNT(*) AS n FROM ori_orientacoes WHERE documento=? AND desvio_id=? AND excluido_em IS NULL",
        (documento, desvio_id),
    )
    return r[0]["n"] + 1


def registrar_orientacao(db, usuario, documento, desvio_id, data_orientacao, sinalizado, observacao):
    """Numero e acao sao calculados no proprio INSERT, entao dois registros simultaneos nao duplicam."""
    doc = normalizar_documento(documento)
    if not buscar_prestador(db, doc):
        return None, "Prestador nao encontrado."
    data_iso = data_orientacao.isoformat() if isinstance(data_orientacao, date) else str(data_orientacao)
    n = "(SELECT COUNT(*) + 1 FROM ori_orientacoes WHERE documento=? AND desvio_id=? AND excluido_em IS NULL)"
    db.batch([
        (
            "INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, acao, "
            "credenciamento_sinalizado, observacao, criado_por) "
            f"SELECT ?, ?, ?, {n}, CASE WHEN ({n}) % {int(ACAO_A_CADA)} = 0 THEN 'FORMS' END, ?, ?, ?",
            (doc, desvio_id, data_iso, doc, desvio_id, doc, desvio_id, sinalizado, observacao or None, usuario["usuario"]),
        ),
        (
            "INSERT INTO ori_auditoria (quem, tabela, registro, acao, depois) "
            "SELECT ?, 'ori_orientacoes', id, 'INSERT', json_object('documento', documento, "
            "'desvio_id', desvio_id, 'numero', numero_orientacao) FROM ori_orientacoes WHERE id = last_insert_rowid()",
            (usuario["usuario"],),
        ),
    ])
    return db.query(
        "SELECT * FROM ori_orientacoes WHERE documento=? AND desvio_id=? AND excluido_em IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (doc, desvio_id),
    )[0], ""


def excluir_orientacao(db, usuario, orientacao_id):
    if usuario["perfil"] not in PODE_EDITAR:
        return False, "Apenas gestor ou admin pode excluir."
    antes = db.query("SELECT * FROM ori_orientacoes WHERE id=? AND excluido_em IS NULL", (orientacao_id,))
    if not antes:
        return False, "Orientacao nao encontrada."
    db.batch([
        (
            "UPDATE ori_orientacoes SET excluido_em=datetime('now'), excluido_por=? WHERE id=?",
            (usuario["usuario"], orientacao_id),
        ),
        auditoria.registrar(usuario["usuario"], "ori_orientacoes", orientacao_id, "DELETE", antes[0], None),
    ])
    return True, "Orientacao excluida."


def listar_orientacoes(db, documento=None, desvio_id=None, data_ini=None, data_fim=None, usuario=None):
    sql = (
        "SELECT o.id, o.documento, p.nome AS prestador, d.nome AS desvio, o.data_orientacao, "
        "o.numero_orientacao, o.acao, o.credenciamento_sinalizado, o.observacao, o.criado_por, o.criado_em "
        "FROM ori_orientacoes o JOIN ori_prestadores p ON p.documento=o.documento "
        "JOIN ori_desvios d ON d.id=o.desvio_id WHERE o.excluido_em IS NULL"
    )
    args = []
    if documento:
        sql += " AND o.documento=?"
        args.append(normalizar_documento(documento))
    if desvio_id:
        sql += " AND o.desvio_id=?"
        args.append(desvio_id)
    if data_ini:
        sql += " AND o.data_orientacao>=?"
        args.append(str(data_ini))
    if data_fim:
        sql += " AND o.data_orientacao<=?"
        args.append(str(data_fim))
    if usuario:
        sql += " AND o.criado_por=?"
        args.append(usuario)
    return db.query(sql + " ORDER BY o.data_orientacao DESC, o.id DESC", tuple(args))
