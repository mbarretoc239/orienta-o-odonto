"""Orientacoes: previa, registro, edicao, exclusao e consulta."""
import uuid
from datetime import date

from core import auditoria, prestadores, tarefas
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


def registradas_no_mes(db, documento, referencia):
    """Orientacoes ja SALVAS do prestador no mes da data de referencia (aviso informativo na tela de registro)."""
    ano_mes = referencia.isoformat()[:7] if isinstance(referencia, date) else str(referencia)[:7]
    return db.query(
        "SELECT d.nome AS desvio, o.numero_orientacao AS numero, o.data_orientacao "
        "FROM ori_orientacoes o JOIN ori_desvios d ON d.id=o.desvio_id "
        "WHERE o.documento=? AND o.excluido_em IS NULL AND substr(o.data_orientacao, 1, 7)=? "
        "ORDER BY o.data_orientacao, o.id",
        (normalizar_documento(documento), ano_mes),
    )


def _comandos_registro(usuario, doc, desvio_id, data_iso, sinalizado, observacao, lote_id, feitas=()):
    """Numero e acao saem do proprio INSERT, entao registros simultaneos nao duplicam o numero.
    `feitas`: tipos de pendencia (forms, contato_direto) que ja nascem concluidos."""
    n = "(SELECT COUNT(*) + 1 FROM ori_orientacoes WHERE documento=? AND desvio_id=? AND excluido_em IS NULL)"
    return [
        (
            "INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, acao, "
            "credenciamento_sinalizado, observacao, criado_por, lote_id) "
            f"SELECT ?, ?, ?, {n}, CASE WHEN ({n}) >= {int(LIMITE_CONTATO_DIRETO)} THEN 'CONTATO DIRETO' "
            f"WHEN ({n}) % {int(ACAO_A_CADA)} = 0 THEN 'FORMS' END, ?, ?, ?, ?",
            (doc, desvio_id, data_iso, doc, desvio_id, doc, desvio_id, doc, desvio_id, sinalizado,
             observacao or None, usuario["usuario"], lote_id),
        ),
        (
            "INSERT INTO ori_auditoria (quem, tabela, registro, acao, depois) "
            "SELECT ?, 'ori_orientacoes', id, 'INSERT', json_object('documento', documento, "
            "'desvio_id', desvio_id, 'numero', numero_orientacao) FROM ori_orientacoes WHERE id = last_insert_rowid()",
            (usuario["usuario"],),
        ),
        *tarefas.comandos_criar(lote_id, desvio_id, usuario["usuario"], feitas),  # depois da auditoria
    ]


def registrar_varios(db, usuario, documento, desvio_ids, data_orientacao, sinalizado, observacao,
                     forms_feito=False, contato_direto_feito=()):
    """Registra uma linha por desvio, todas juntas (ou nenhuma) e ligadas pelo mesmo lote_id.
    Cada desvio tem a propria numeracao e a propria acao. `forms_feito`: o FORMS (que cobre o registro todo) ja foi
    enviado; `contato_direto_feito`: ids dos desvios cujo contato direto ja foi feito. Essas pendencias ja nascem
    concluidas. Retorna (lista de orientacoes|None, mensagem)."""
    doc = normalizar_documento(documento)
    desvio_ids = list(desvio_ids)
    if not desvio_ids:
        return None, "Escolha ao menos um desvio."
    if len(set(desvio_ids)) != len(desvio_ids):
        return None, "O mesmo desvio foi escolhido mais de uma vez."
    if not prestadores.buscar(db, doc):
        return None, "Prestador nao encontrado."
    data_iso = data_orientacao.isoformat() if isinstance(data_orientacao, date) else str(data_orientacao)
    if any(_duplicada(db, doc, did, data_iso, usuario["usuario"]) for did in desvio_ids):
        return None, "Esta orientacao acabou de ser registrada (clique duplo?). Confira na consulta."
    lote_id = uuid.uuid4().hex
    comandos = []
    contato_feito = set(contato_direto_feito)
    for did in desvio_ids:
        feitas = ({"forms"} if forms_feito else set()) | ({"contato_direto"} if did in contato_feito else set())
        comandos += _comandos_registro(usuario, doc, did, data_iso, sinalizado, observacao, lote_id, feitas)
    db.batch(comandos)
    return db.query(
        "SELECT * FROM ori_orientacoes WHERE lote_id=? ORDER BY desvio_id", (lote_id,)
    ), ""


def registrar(db, usuario, documento, desvio_id, data_orientacao, sinalizado, observacao, forms_feito=False,
              contato_direto_feito=False):
    """Registro de um unico desvio. Retorna (orientacao|None, mensagem)."""
    regs, msg = registrar_varios(db, usuario, documento, [desvio_id], data_orientacao, sinalizado, observacao,
                                 forms_feito, [desvio_id] if contato_direto_feito else ())
    return (regs[0] if regs else None), msg


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
    comandos = [
        (
            "UPDATE ori_orientacoes SET excluido_em=datetime('now'), excluido_por=? WHERE id=?",
            (usuario["usuario"], orientacao_id),
        ),
        auditoria.registrar(usuario["usuario"], "ori_orientacoes", orientacao_id, "DELETE", antes, None),
    ]
    comandos += _renumerar_apos_exclusao(db, usuario, antes)
    db.batch(comandos)
    return True, "Orientacao excluida."


def _renumerar_apos_exclusao(db, usuario, excluida):
    """As orientacoes seguintes (mesmo prestador e desvio, pela ordem de registro) descem um numero e a
    acao delas e recalculada. Comandos para entrar no mesmo batch da exclusao."""
    restantes = db.query(
        "SELECT id, numero_orientacao, acao FROM ori_orientacoes "
        "WHERE documento=? AND desvio_id=? AND excluido_em IS NULL AND id<>? ORDER BY id",
        (excluida["documento"], excluida["desvio_id"], excluida["id"]),
    )
    comandos = []
    for novo_numero, o in enumerate(restantes, start=1):
        nova_acao = acao_para(novo_numero)
        if o["numero_orientacao"] == novo_numero and o["acao"] == nova_acao:
            continue
        comandos.append((
            "UPDATE ori_orientacoes SET numero_orientacao=?, acao=? WHERE id=?",
            (novo_numero, nova_acao, o["id"]),
        ))
        comandos.append(auditoria.registrar(
            usuario["usuario"], "ori_orientacoes", o["id"], "RENUMERAR",
            {"numero": o["numero_orientacao"], "acao": o["acao"]}, {"numero": novo_numero, "acao": nova_acao},
        ))
        comandos.extend(tarefas.comandos_sincronizar(o["id"]))  # a acao mudou: ajusta as pendencias dela
    return comandos


def autores(db):
    """Quem ja registrou orientacoes (para o filtro 'registrada por' do gestor)."""
    return [r["criado_por"] for r in db.query(
        "SELECT DISTINCT criado_por FROM ori_orientacoes WHERE excluido_em IS NULL ORDER BY criado_por")]


def historico(db, documento):
    """Todas as orientacoes ativas do prestador, da mais recente para a mais antiga."""
    return db.query(
        "SELECT d.nome AS desvio, o.numero_orientacao AS numero, o.data_orientacao AS data, o.acao, "
        "o.criado_por AS registrado_por FROM ori_orientacoes o JOIN ori_desvios d ON d.id=o.desvio_id "
        "WHERE o.documento=? AND o.excluido_em IS NULL ORDER BY o.data_orientacao DESC, o.id DESC",
        (normalizar_documento(documento),),
    )


def situacao_por_desvio(db, documento):
    """Por desvio: quantas orientacoes o prestador ja tem, qual sera a proxima e a acao que ela aciona."""
    linhas = db.query(
        "SELECT d.nome AS desvio, COUNT(*) AS ja_tem FROM ori_orientacoes o JOIN ori_desvios d ON d.id=o.desvio_id "
        "WHERE o.documento=? AND o.excluido_em IS NULL GROUP BY d.id ORDER BY d.id",
        (normalizar_documento(documento),),
    )
    return [{"desvio": x["desvio"], "ja_tem": x["ja_tem"], "proxima": rotulo_orientacao(x["ja_tem"] + 1),
             "acao_da_proxima": acao_para(x["ja_tem"] + 1) or "—"} for x in linhas]


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
