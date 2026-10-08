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


def preparar_recarga(db, orient, pasta):
    """Antes de recarregar as orientacoes da migracao: aborta se alguem registrou orientacao nos mesmos
    prestadores (a numeracao seria afetada), guarda um CSV de backup e apaga so as linhas de autor 'migracao'.
    Retorna (quantidade apagada, caminho do backup)."""
    from datetime import datetime

    import pandas as pd

    docs = set(orient["documento"])
    de_pessoas = [r for r in db.query(
        "SELECT documento, criado_por FROM ori_orientacoes WHERE criado_por <> 'migracao'") if r["documento"] in docs]
    if de_pessoas:
        raise RuntimeError(f"Ha {len(de_pessoas)} orientacao(oes) registradas por pessoas em prestadores da "
                           "migracao: recarga abortada para nao alterar a numeracao delas.")
    antigas = db.query("SELECT * FROM ori_orientacoes WHERE criado_por='migracao' ORDER BY id")
    caminho = pasta / f"backup_orientacoes_migracao_{datetime.now():%Y%m%d_%H%M%S}.csv"
    pd.DataFrame(antigas).to_csv(caminho, index=False, encoding="utf-8-sig", sep=";")
    db.execute("DELETE FROM ori_orientacoes WHERE criado_por='migracao'")
    return len(antigas), caminho


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
