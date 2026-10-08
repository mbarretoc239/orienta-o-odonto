"""Numeros do painel gerencial (gestor e admin). So leitura."""
from core import tarefas
from core.regras import acao_para, rotulo_orientacao

_BASE = "FROM ori_orientacoes o JOIN ori_desvios d ON d.id=o.desvio_id JOIN ori_prestadores p ON p.documento=o.documento " \
        "WHERE o.excluido_em IS NULL"


def _periodo(data_ini, data_fim):
    sql, args = "", []
    if data_ini:
        sql += " AND o.data_orientacao >= ?"
        args.append(str(data_ini))
    if data_fim:
        sql += " AND o.data_orientacao <= ?"
        args.append(str(data_fim))
    return sql, args


def resumo(db, data_ini=None, data_fim=None):
    filtro, args = _periodo(data_ini, data_fim)
    r = db.query(
        "SELECT COUNT(*) AS orientacoes, COUNT(DISTINCT o.documento) AS prestadores, "
        "COALESCE(SUM(o.acao='FORMS'), 0) AS forms, COALESCE(SUM(o.acao='CONTATO DIRETO'), 0) AS contato_direto "
        f"{_BASE}{filtro}", tuple(args))[0]
    r["pendencias_abertas"] = tarefas.contagem(db)
    return r


def por_mes(db, data_ini=None, data_fim=None):
    filtro, args = _periodo(data_ini, data_fim)
    return db.query(f"SELECT substr(o.data_orientacao, 1, 7) AS mes, COUNT(*) AS orientacoes {_BASE}{filtro} "
                    "GROUP BY 1 ORDER BY 1", tuple(args))


def por_desvio(db, data_ini=None, data_fim=None):
    filtro, args = _periodo(data_ini, data_fim)
    return db.query(f"SELECT d.nome AS desvio, COUNT(*) AS orientacoes {_BASE}{filtro} "
                    "GROUP BY d.id ORDER BY orientacoes DESC", tuple(args))


def desvio_por_mes(db, data_ini=None, data_fim=None):
    """Grade desvio x mes (mapa de calor): mostra quais problemas crescem ou diminuem ao longo do tempo."""
    filtro, args = _periodo(data_ini, data_fim)
    return db.query(
        f"SELECT d.nome AS desvio, substr(o.data_orientacao, 1, 7) AS mes, COUNT(*) AS orientacoes {_BASE}{filtro} "
        "GROUP BY d.id, 2 ORDER BY 2, d.id", tuple(args))


def por_usuario(db, data_ini=None, data_fim=None, incluir_importadas=False):
    """Quem registrou as orientacoes do periodo. As importadas da planilha (autor 'migracao') nao sao de
    uma pessoa e esmagariam as demais, entao ficam de fora, a menos que se peca."""
    filtro, args = _periodo(data_ini, data_fim)
    if not incluir_importadas:
        filtro += " AND o.criado_por <> 'migracao'"
    return db.query(
        f"SELECT o.criado_por AS usuario, COUNT(*) AS orientacoes, MAX(o.criado_em) AS ultimo_registro "
        f"{_BASE}{filtro} GROUP BY o.criado_por ORDER BY orientacoes DESC", tuple(args))


def importadas(db, data_ini=None, data_fim=None) -> int:
    """Quantas orientacoes do periodo vieram da planilha (historico importado)."""
    filtro, args = _periodo(data_ini, data_fim)
    return db.query(f"SELECT COUNT(*) AS n {_BASE}{filtro} AND o.criado_por = 'migracao'", tuple(args))[0]["n"]


def reincidentes(db, minimo=3, limite=200):
    """Prestador + desvio com pelo menos `minimo` orientacoes, com a acao que a proxima acionara."""
    linhas = db.query(
        "SELECT o.documento, p.nome AS prestador, d.nome AS desvio, COUNT(*) AS orientacoes, "
        f"MAX(o.data_orientacao) AS ultima {_BASE} GROUP BY o.documento, o.desvio_id "
        "HAVING COUNT(*) >= ? ORDER BY orientacoes DESC, ultima DESC LIMIT ?", (int(minimo), int(limite)))
    for x in linhas:
        x["proxima"] = rotulo_orientacao(x["orientacoes"] + 1)
        x["acao_da_proxima"] = acao_para(x["orientacoes"] + 1) or "—"
    return linhas


def tempo_medio_de_conclusao(db):
    """Dias, em media, entre registrar a orientacao e concluir cada tipo de pendencia."""
    return db.query(
        "SELECT t.tipo, COUNT(*) AS concluidas, "
        "ROUND(AVG(julianday(t.feita_em) - julianday(o.criado_em)), 1) AS dias_em_media "
        "FROM ori_tarefas t JOIN ori_orientacoes o ON o.id=t.orientacao_id "
        "WHERE o.excluido_em IS NULL AND t.feita_em IS NOT NULL GROUP BY t.tipo")
