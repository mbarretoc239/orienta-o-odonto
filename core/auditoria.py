import json


def registrar(quem, tabela, registro, acao, antes=None, depois=None):
    """Comando (sql, args) para entrar no mesmo batch da alteracao auditada."""

    def j(v):
        return json.dumps(v, ensure_ascii=False, default=str) if v is not None else None

    return (
        "INSERT INTO ori_auditoria (quem, tabela, registro, acao, antes, depois) VALUES (?,?,?,?,?,?)",
        (quem, tabela, str(registro), acao, j(antes), j(depois)),
    )
