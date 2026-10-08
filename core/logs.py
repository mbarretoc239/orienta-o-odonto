"""Log de eventos e erros guardado no banco (o log do servidor do Streamlit Cloud some a cada reinicio).

Gravar log nunca pode derrubar a tela: qualquer falha aqui e engolida.
"""
import logging
import traceback

LOG = logging.getLogger("orientacoes")
NIVEIS = ("erro", "aviso", "info")
RETENCAO_DIAS = 90
LIMITE_DETALHE = 4000


def registrar(db, nivel, evento, detalhe=None, usuario=None, pagina=None):
    try:
        db.execute(
            "INSERT INTO ori_logs (nivel, usuario, pagina, evento, detalhe) VALUES (?,?,?,?,?)",
            (nivel, usuario, pagina, str(evento)[:200], (detalhe or None) and str(detalhe)[-LIMITE_DETALHE:]),
        )
    except Exception:  # noqa: BLE001 - log nao pode causar outro erro
        LOG.exception("Nao foi possivel gravar o log no banco: %s", evento)


def registrar_excecao(db, excecao: BaseException, usuario=None, pagina=None):
    """Erro inesperado: guarda o tipo, a mensagem e o traceback."""
    detalhe = "".join(traceback.format_exception(type(excecao), excecao, excecao.__traceback__))
    registrar(db, "erro", f"{type(excecao).__name__}: {excecao}", detalhe, usuario, pagina)


def listar(db, nivel=None, usuario=None, pagina=None, data_ini=None, data_fim=None, texto=None, limite=500):
    sql = "SELECT id, quando, nivel, usuario, pagina, evento, detalhe FROM ori_logs WHERE 1=1"
    args = []
    for coluna, valor in (("nivel", nivel), ("usuario", usuario), ("pagina", pagina)):
        if valor:
            sql += f" AND {coluna}=?"
            args.append(valor)
    if data_ini:
        sql += " AND substr(quando,1,10) >= ?"
        args.append(str(data_ini))
    if data_fim:
        sql += " AND substr(quando,1,10) <= ?"
        args.append(str(data_fim))
    if texto:
        sql += " AND (evento LIKE ? OR detalhe LIKE ?)"
        args += [f"%{texto}%", f"%{texto}%"]
    return db.query(sql + " ORDER BY id DESC LIMIT ?", (*args, int(limite)))


def limpar_antigos(db, dias: int = RETENCAO_DIAS) -> None:
    """Descarta log operacional com mais de `dias` dias (a auditoria dos dados nao e tocada)."""
    try:
        db.execute("DELETE FROM ori_logs WHERE quando < datetime('now', ?)", (f"-{int(dias)} days",))
    except Exception:  # noqa: BLE001
        LOG.exception("Nao foi possivel limpar logs antigos")
