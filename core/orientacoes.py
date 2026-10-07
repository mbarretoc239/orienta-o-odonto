"""Orientacoes: previa, registro, edicao, exclusao e consulta."""
from datetime import date

from core import auditoria, prestadores
from core.regras import (
    ACAO_A_CADA,
    LIMITE_CONTATO_DIRETO,
    acao_para,
    exige_contato_direto,
    normalizar_documento,
    rotulo_orientacao,
)

PODE_EDITAR = ("gestor", "admin")
JANELA_DUPLICIDADE_S = 60
LIMITE_CONSULTA = 2000


def proximo_numero(db, documento, desvio_id):
    r = db.query(
        "SELECT COUNT(*) AS n FROM ori_orientacoes WHERE documento=? AND desvio_id=? AND excluido_em IS NULL",
        (documento, desvio_id),
    )
    return r[0]["n"] + 1


def previa(db, documento, desvio_id):
    """O que sera registrado: numero, rotulo, acao e se exige contato direto."""
    numero = proximo_numero(db, normalizar_documento(documento), desvio_id)
    return {
        "numero": numero,
        "rotulo": rotulo_orientacao(numero),
        "acao": acao_para(numero),
        "contato_direto": exige_contato_direto(numero),
    }


def _duplicada(db, doc, desvio_id, data_iso, usuario):
    return bool(db.query(
        "SELECT 1 FROM ori_orientacoes WHERE documento=? AND desvio_id=? AND data_orientacao=? AND criado_por=? "
        "AND excluido_em IS NULL AND criado_em >= datetime('now', ?) LIMIT 1",
        (doc, desvio_id, data_iso, usuario, f"-{JANELA_DUPLICIDADE_S} seconds"),
    ))


def registrar(db, usuario, documento, desvio_id, data_orientacao, sinalizado, observacao):
    """Numero e acao saem do proprio INSERT: dois registros simultaneos nao duplicam o numero.
    Retorna (orientacao|None, mensagem)."""
    doc = normalizar_documento(documento)
    if not prestadores.buscar(db, doc):
        return None, "Prestador nao encontrado."
    data_iso = data_orientacao.isoformat() if isinstance(data_orientacao, date) else str(data_orientacao)
    if _duplicada(db, doc, desvio_id, data_iso, usuario["usuario"]):
        return None, "Esta orientacao acabou de ser registrada (clique duplo?). Confira na consulta."
    n = "(SELECT COUNT(*) + 1 FROM ori_orientacoes WHERE documento=? AND desvio_id=? AND excluido_em IS NULL)"
    db.batch([
        (
            "INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, acao, "
            "credenciamento_sinalizado, observacao, criado_por) "
            f"SELECT ?, ?, ?, {n}, CASE WHEN ({n}) >= {int(LIMITE_CONTATO_DIRETO)} THEN 'CONTATO DIRETO' "
            f"WHEN ({n}) % {int(ACAO_A_CADA)} = 0 THEN 'FORMS' END, ?, ?, ?",
            (doc, desvio_id, data_iso, doc, desvio_id, doc, desvio_id, doc, desvio_id, sinalizado,
             observacao or None, usuario["usuario"]),
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


def _ativa(db, orientacao_id):
    r = db.query("SELECT * FROM ori_orientacoes WHERE id=? AND excluido_em IS NULL", (orientacao_id,))
    return r[0] if r else None


def editar(db, usuario, orientacao_id, data_orientacao, sinalizado, observacao):
    """Edita data, credenciamento e observacao (documento e desvio nao mudam: alterariam a numeracao)."""
    if usuario["perfil"] not in PODE_EDITAR:
        return False, "Apenas gestor ou admin pode editar."
    antes = _ativa(db, orientacao_id)
    if not antes:
        return False, "Orientacao nao encontrada."
    data_iso = data_orientacao.isoformat() if isinstance(data_orientacao, date) else str(data_orientacao)
    depois = {"data_orientacao": data_iso, "credenciamento_sinalizado": sinalizado, "observacao": observacao or None}
    db.batch([
        (
            "UPDATE ori_orientacoes SET data_orientacao=?, credenciamento_sinalizado=?, observacao=? WHERE id=?",
            (data_iso, sinalizado, observacao or None, orientacao_id),
        ),
        auditoria.registrar(usuario["usuario"], "ori_orientacoes", orientacao_id, "UPDATE",
                            {k: antes[k] for k in depois}, depois),
    ])
    return True, "Orientacao atualizada."


def excluir(db, usuario, orientacao_id):
    if usuario["perfil"] not in PODE_EDITAR:
        return False, "Apenas gestor ou admin pode excluir."
    antes = _ativa(db, orientacao_id)
    if not antes:
        return False, "Orientacao nao encontrada."
    db.batch([
        (
            "UPDATE ori_orientacoes SET excluido_em=datetime('now'), excluido_por=? WHERE id=?",
            (usuario["usuario"], orientacao_id),
        ),
        auditoria.registrar(usuario["usuario"], "ori_orientacoes", orientacao_id, "DELETE", antes, None),
    ])
    return True, "Orientacao excluida."


def listar(db, documento=None, desvio_id=None, data_ini=None, data_fim=None, usuario=None):
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
    sql += f" ORDER BY o.data_orientacao DESC, o.id DESC LIMIT {LIMITE_CONSULTA}"
    return db.query(sql, tuple(args))
