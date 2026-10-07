"""Desvios e seus textos padrao."""


def listar(db, so_ativos=True):
    sql = "SELECT id, nome, texto_padrao, ativo FROM ori_desvios"
    if so_ativos:
        sql += " WHERE ativo=1"
    return db.query(sql + " ORDER BY id")


def atualizar(db, desvio_id, texto_padrao, ativo):
    db.execute("UPDATE ori_desvios SET texto_padrao=?, ativo=? WHERE id=?", (texto_padrao, int(ativo), desvio_id))


def adicionar(db, nome, texto_padrao):
    nome = " ".join((nome or "").upper().split())
    if not nome:
        return False, "Informe o nome do desvio."
    if db.query("SELECT 1 FROM ori_desvios WHERE nome=?", (nome,)):
        return False, "Desvio ja existe."
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES (?,?)", (nome, texto_padrao or ""))
    return True, "Desvio adicionado."
