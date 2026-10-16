"""Pendencias de acao de cada orientacao: FORMS (3a, 6a, 9a...), contato direto (12a) e relatar para a gestao
(13a em diante). FORMS e contato direto sao marcados como feitos por quem registrou (ou por gestor/admin) e podem ja
nascer feitos, se a pessoa marcar isso na hora de registrar. O relato a gestao so o gestor (ou admin) marca."""
from core import auditoria
from core.regras import ACAO_RELATAR_GESTAO

TIPOS = {
    "forms": "FORMS preenchido",
    "contato_direto": "Contato direto feito",
    "relatar_gestao": "Relatado para a gestão",
}
# tipo -> acao da orientacao que gera a pendencia
ACAO_DO_TIPO = {"forms": "FORMS", "contato_direto": "CONTATO DIRETO", "relatar_gestao": ACAO_RELATAR_GESTAO}
SO_GESTAO_MARCA = ("relatar_gestao",)
PODE_VER_TODAS = ("gestor", "admin")
_TIPOS_SQL = ", ".join(f"'{t}'" for t in TIPOS)
# um FORMS cobre todos os desvios registrados juntos (mesmo lote): conta como UMA pendencia
_UNIDADE = "CASE WHEN t.tipo='forms' AND o.lote_id IS NOT NULL THEN 'f' || o.lote_id ELSE 't' || t.id END"

_SELECT = (
    "SELECT t.id AS tarefa_id, t.tipo, t.feita_em, t.feita_por, o.id AS orientacao_id, o.lote_id, o.documento, "
    "p.nome AS prestador, d.nome AS desvio, d.orientacao_forms, o.data_orientacao, o.numero_orientacao AS numero, o.acao, "
    "o.criado_por, o.criado_em, CAST(julianday('now') - julianday(o.criado_em) AS INTEGER) AS dias "
    "FROM ori_tarefas t JOIN ori_orientacoes o ON o.id = t.orientacao_id "
    "JOIN ori_prestadores p ON p.documento = o.documento JOIN ori_desvios d ON d.id = o.desvio_id "
    f"WHERE o.excluido_em IS NULL AND t.tipo IN ({_TIPOS_SQL})"
)


def agrupar(dados: list[dict]) -> list[dict]:
    """Um item por pendencia para a tela. Um FORMS vale para todos os desvios registrados juntos (mesmo lote), entao
    as pendencias de FORMS do mesmo lote viram UM item, com a lista de desvios. Os demais tipos ficam um por um."""
    itens, por_lote = [], {}
    for t in dados:
        desvio = {"desvio": t["desvio"], "numero": t["numero"], "data": t["data_orientacao"],
                  "orientacao": t.get("orientacao_forms")}
        if t["tipo"] == "forms" and t["lote_id"]:
            chave = (t["lote_id"], bool(t["feita_em"]))
            if chave in por_lote:
                por_lote[chave]["desvios"].append(desvio)
                por_lote[chave]["tarefa_ids"].append(t["tarefa_id"])
                continue
        item = {"tipo": t["tipo"], "tarefa_id": t["tarefa_id"], "tarefa_ids": [t["tarefa_id"]], "documento": t["documento"],
                "prestador": t["prestador"], "desvios": [desvio], "feita_em": t["feita_em"], "feita_por": t["feita_por"],
                "criado_por": t["criado_por"], "dias": t["dias"], "data": t["data_orientacao"]}
        if t["tipo"] == "forms" and t["lote_id"]:
            por_lote[(t["lote_id"], bool(t["feita_em"]))] = item
        itens.append(item)
    return itens


def comandos_criar(lote_id, desvio_id, usuario, feitas=()):
    """Comandos para entrar no batch do registro: FORMS ou contato direto, conforme a acao da orientacao.
    Os tipos em `feitas` ja nascem concluidos (a pessoa marcou 'ja fiz' ao registrar)."""
    cmds = []
    for tipo, acao in ACAO_DO_TIPO.items():
        feita = tipo in feitas
        quando = "datetime('now')" if feita else "NULL"
        cmds.append((
            f"INSERT OR IGNORE INTO ori_tarefas (orientacao_id, tipo, feita_em, feita_por) "
            f"SELECT id, ?, {quando}, ? FROM ori_orientacoes WHERE lote_id=? AND desvio_id=? AND acao=?",
            (tipo, usuario if feita else None, lote_id, desvio_id, acao),
        ))
    return cmds


def comandos_sincronizar(orientacao_id):
    """Depois de a acao de uma orientacao mudar (renumeracao): tira a pendencia que deixou de valer e cria a
    nova. As orientacoes importadas da planilha (autor 'migracao') nao tem pendencias."""
    cmds = []
    for tipo, acao in ACAO_DO_TIPO.items():
        cmds.append((
            "DELETE FROM ori_tarefas WHERE orientacao_id=? AND tipo=? AND feita_em IS NULL AND NOT EXISTS "
            "(SELECT 1 FROM ori_orientacoes WHERE id=? AND acao=?)",
            (orientacao_id, tipo, orientacao_id, acao),
        ))
        cmds.append((
            "INSERT OR IGNORE INTO ori_tarefas (orientacao_id, tipo) SELECT id, ? FROM ori_orientacoes "
            "WHERE id=? AND acao=? AND criado_por <> 'migracao'",
            (tipo, orientacao_id, acao),
        ))
    return cmds


def remover_pendencias_da_capa(db) -> None:
    """A pendencia 'orientacao na capa' deixou de existir (so ha pendencias de acao). Limpa as que sobraram."""
    db.execute("DELETE FROM ori_tarefas WHERE tipo='capa'")


def pendencias(db, usuario=None, incluir_concluidas_dias=0):
    """Pendencias em aberto (e, opcionalmente, as concluidas nos ultimos N dias). `usuario`: so as dele."""
    sql = _SELECT
    args = []
    if incluir_concluidas_dias:
        sql += " AND (t.feita_em IS NULL OR t.feita_em >= datetime('now', ?))"
        args.append(f"-{int(incluir_concluidas_dias)} days")
    else:
        sql += " AND t.feita_em IS NULL"
    if usuario:
        sql += " AND o.criado_por = ?"
        args.append(usuario)
    return db.query(sql + " ORDER BY (t.feita_em IS NOT NULL), o.criado_em, t.id", tuple(args))


def contagem(db, usuario=None, perfil=None):
    """Quantas pendencias em aberto (todas, ou de um usuario; `perfil` decide se entram os relatos a gestao)."""
    sql = (f"SELECT COUNT(DISTINCT {_UNIDADE}) AS n FROM ori_tarefas t JOIN ori_orientacoes o ON o.id = t.orientacao_id "
           f"WHERE o.excluido_em IS NULL AND t.feita_em IS NULL AND t.tipo IN ({_TIPOS_SQL})")
    args = ()
    if usuario:
        # gestor/admin tambem contam os relatos a gestao de todo mundo: sao deles para marcar
        sql += (" AND (o.criado_por = ? OR t.tipo = 'relatar_gestao')" if perfil in PODE_VER_TODAS
                else " AND o.criado_por = ?")
        args = (usuario,)
    return db.query(sql, args)[0]["n"]


def resumo_por_usuario(db):
    """Visao do gestor: pendencias em aberto por quem registrou."""
    return db.query(
        "SELECT o.criado_por AS usuario, "
        f"COUNT(DISTINCT CASE WHEN t.tipo='forms' THEN {_UNIDADE} END) AS forms, "
        "SUM(t.tipo='contato_direto') AS contato_direto, SUM(t.tipo='relatar_gestao') AS relatar_gestao, "
        f"COUNT(DISTINCT {_UNIDADE}) AS total, MIN(o.criado_em) AS mais_antiga "
        "FROM ori_tarefas t JOIN ori_orientacoes o ON o.id = t.orientacao_id "
        f"WHERE o.excluido_em IS NULL AND t.feita_em IS NULL AND t.tipo IN ({_TIPOS_SQL}) "
        "GROUP BY o.criado_por ORDER BY total DESC"
    )


def marcar(db, usuario, tarefa_id, feita=True):
    """Marca (ou reabre) uma pendencia. Quem registrou a orientacao e gestor/admin podem. Retorna (ok, mensagem).
    Um FORMS cobre todos os desvios registrados juntos: marcar um marca os do mesmo registro."""
    linhas = db.query(_SELECT + " AND t.id = ?", (tarefa_id,))
    if not linhas:
        return False, "Pendencia nao encontrada."
    t = linhas[0]
    if t["tipo"] in SO_GESTAO_MARCA and usuario["perfil"] not in PODE_VER_TODAS:
        return False, "O relato para a gestao so pode ser marcado como feito pelo gestor."
    if usuario["perfil"] not in PODE_VER_TODAS and t["criado_por"] != usuario["usuario"]:
        return False, "Voce so pode marcar as suas proprias pendencias."
    alvos = [tarefa_id]
    if t["tipo"] == "forms" and t["lote_id"]:
        alvos = [r["id"] for r in db.query(
            "SELECT t.id FROM ori_tarefas t JOIN ori_orientacoes o ON o.id = t.orientacao_id "
            "WHERE t.tipo='forms' AND o.lote_id=? AND o.excluido_em IS NULL", (t["lote_id"],))]
    cmds = []
    for alvo in alvos:
        if feita:
            cmds.append(("UPDATE ori_tarefas SET feita_em=datetime('now'), feita_por=? WHERE id=?",
                         (usuario["usuario"], alvo)))
        else:
            cmds.append(("UPDATE ori_tarefas SET feita_em=NULL, feita_por=NULL WHERE id=?", (alvo,)))
        cmds.append(auditoria.registrar(usuario["usuario"], "ori_tarefas", alvo, "CONCLUIR" if feita else "REABRIR",
                                        None, {"tipo": t["tipo"], "orientacao": t["orientacao_id"]}))
    db.batch(cmds)
    return True, "Pendencia concluida." if feita else "Pendencia reaberta."
