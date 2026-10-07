"""Gravacao no banco. Retomavel: etapas ja gravadas por uma execucao interrompida sao puladas."""
from core.regras import acao_para

LOTE = 500


def _em_lotes(db, comandos):
    for i in range(0, len(comandos), LOTE):
        db.batch(comandos[i:i + LOTE])


def gravar_desvios(db, desvios):
    if db.query("SELECT 1 FROM ori_desvios LIMIT 1"):
        return "desvios ja carregados: pulando"
    db.batch([("INSERT INTO ori_desvios (nome, texto_padrao) VALUES (?,?)", d) for d in desvios])
    return f"{len(desvios)} desvios gravados"


def gravar_prestadores(db, prest):
    if db.query("SELECT 1 FROM ori_prestadores LIMIT 1"):
        return "prestadores ja carregados: pulando"
    _em_lotes(db, [
        ("INSERT INTO ori_prestadores (documento, nome, codigo, tipo, cidade, uf, origem) VALUES (?,?,?,?,?,?,?)",
         (d, p["nome"], p["codigo"], p["tipo"], p["cidade"], p["uf"], p["origem"]))
        for d, p in prest.items()
    ])
    return f"{len(prest)} prestadores gravados"


def gravar_orientacoes(db, orient):
    _em_lotes(db, [
        ("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, acao, "
         "credenciamento_sinalizado, observacao, criado_por) VALUES (?,?,?,?,?,?,?,'migracao')",
         (r.documento, int(r.desvio_id), r.data, int(r.numero),
          acao_para(int(r.numero)), r.sinal, r.obs))
        for r in orient.itertuples()
    ])
    n = db.query("SELECT COUNT(*) AS n FROM ori_orientacoes")[0]["n"]
    return f"orientacoes no banco: {n} (esperado {len(orient)})"
