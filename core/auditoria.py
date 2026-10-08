import json


def registrar(quem, tabela, registro, acao, antes=None, depois=None):
    """Comando (sql, args) para entrar no mesmo batch da alteracao auditada."""

    def j(v):
        return json.dumps(v, ensure_ascii=False, default=str) if v is not None else None

    return (
        "INSERT INTO ori_auditoria (quem, tabela, registro, acao, antes, depois) VALUES (?,?,?,?,?,?)",
        (quem, tabela, str(registro), acao, j(antes), j(depois)),
    )


def opcoes(db) -> dict[str, list[str]]:
    """Valores existentes para os filtros da tela de auditoria."""
    return {col: [r[col] for r in db.query(f"SELECT DISTINCT {col} FROM ori_auditoria ORDER BY {col}")]
            for col in ("quem", "tabela", "acao")}  # nomes de coluna fixos: nao vem do usuario


def listar(db, quem=None, tabela=None, acao=None, data_ini=None, data_fim=None, registro=None, limite=500):
    sql = "SELECT id, quando, quem, tabela, registro, acao, antes, depois FROM ori_auditoria WHERE 1=1"
    args = []
    for coluna, valor in (("quem", quem), ("tabela", tabela), ("acao", acao)):
        if valor:
            sql += f" AND {coluna}=?"
            args.append(valor)
    if registro:
        sql += " AND registro=?"
        args.append(str(registro).strip())
    if data_ini:
        sql += " AND substr(quando,1,10) >= ?"
        args.append(str(data_ini))
    if data_fim:
        sql += " AND substr(quando,1,10) <= ?"
        args.append(str(data_fim))
    return db.query(sql + " ORDER BY id DESC LIMIT ?", (*args, int(limite)))
