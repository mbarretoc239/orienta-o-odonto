"""Desvios e seus textos padrao."""
from core import textos

COLUNAS = "id, nome, texto_padrao, ativo, resumo, titulo, corpo, fechamento_tipo"
TIPOS_FECHAMENTO = ("padrao", "imagens", None)


def listar(db, so_ativos=True):
    sql = f"SELECT {COLUNAS} FROM ori_desvios"
    if so_ativos:
        sql += " WHERE ativo=1"
    return db.query(sql + " ORDER BY id")


def atualizar(db, desvio_id, texto_padrao, ativo, resumo=None, titulo=None, corpo=None, fechamento_tipo=None):
    """Texto padrao: usado quando so este desvio e registrado. Resumo, titulo, corpo e fechamento: usados na
    mensagem com mais de um desvio."""
    if fechamento_tipo not in TIPOS_FECHAMENTO:
        raise ValueError("Tipo de fechamento invalido.")
    db.execute(
        "UPDATE ori_desvios SET texto_padrao=?, ativo=?, resumo=?, titulo=?, corpo=?, fechamento_tipo=? WHERE id=?",
        (texto_padrao, int(ativo), resumo, titulo, corpo, fechamento_tipo, desvio_id),
    )


def adicionar(db, nome, texto_padrao):
    nome = " ".join((nome or "").upper().split())
    if not nome:
        return False, "Informe o nome do desvio."
    if db.query("SELECT 1 FROM ori_desvios WHERE nome=?", (nome,)):
        return False, "Desvio ja existe."
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES (?,?)", (nome, texto_padrao or ""))
    textos.preencher_estrutura(db)
    return True, "Desvio adicionado."
