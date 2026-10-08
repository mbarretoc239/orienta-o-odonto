from core import orientacoes, tarefas
from tests.conftest import CNPJ_OK, GESTOR, USR

OUTRO = {"usuario": "outro.u", "nome": "Outro", "perfil": "contas"}


def registrar(db, data="2026-01-01", usuario=USR, desvio=1):
    return orientacoes.registrar(db, usuario, CNPJ_OK, desvio, data, None, None)[0]


def tipos(db, orientacao_id):
    return sorted(r["tipo"] for r in db.query("SELECT tipo FROM ori_tarefas WHERE orientacao_id=?", (orientacao_id,)))


def test_toda_orientacao_gera_a_pendencia_da_capa_e_so_as_de_3_6_9_geram_forms(db):
    regs = [registrar(db, f"2026-01-{n:02d}") for n in range(1, 4)]
    assert tipos(db, regs[0]["id"]) == ["capa"] and tipos(db, regs[1]["id"]) == ["capa"]
    assert tipos(db, regs[2]["id"]) == ["capa", "forms"]  # 3a: FORMS


def test_a_partir_da_12a_a_pendencia_e_contato_direto_e_nao_forms(db):
    for n in range(1, 12):
        db.execute("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, criado_por) "
                   "VALUES (?,1,?,?,'x')", (CNPJ_OK, f"2025-01-{n:02d}", n))
    d12 = registrar(db, "2026-02-01")
    assert d12["acao"] == "CONTATO DIRETO" and tipos(db, d12["id"]) == ["capa", "contato_direto"]


def test_registro_em_grupo_cria_pendencias_para_cada_desvio(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('B', 'b')")
    regs, _ = orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2], "2026-01-01", None, None)
    assert all("capa" in tipos(db, r["id"]) for r in regs)
    assert db.query("SELECT COUNT(*) AS n FROM ori_tarefas")[0]["n"] == 2


def test_cada_usuario_ve_so_as_suas_e_o_gestor_ve_por_usuario(db):
    registrar(db, "2026-01-01", USR)
    registrar(db, "2026-01-02", OUTRO)
    assert len(tarefas.pendencias(db, USR["usuario"])) == 1
    assert len(tarefas.pendencias(db)) == 2
    resumo = {r["usuario"]: r["total"] for r in tarefas.resumo_por_usuario(db)}
    assert resumo == {"a.b": 1, "outro.u": 1}
    assert tarefas.contagem(db, USR["usuario"]) == 1 and tarefas.contagem(db) == 2


def test_marcar_so_as_proprias_exceto_gestor(db):
    r = registrar(db, "2026-01-01", USR)
    t = tarefas.pendencias(db)[0]["tarefa_id"]
    ok, msg = tarefas.marcar(db, OUTRO, t)
    assert not ok and "suas proprias" in msg
    assert tarefas.marcar(db, USR, t)[0]
    assert tarefas.pendencias(db) == [] and tarefas.contagem(db) == 0
    feita = db.query("SELECT feita_por FROM ori_tarefas WHERE id=?", (t,))[0]
    assert feita["feita_por"] == "a.b"
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='CONCLUIR' AND quem='a.b'")
    assert tarefas.marcar(db, GESTOR, t, feita=False)[0]  # gestor pode reabrir qualquer uma
    assert tarefas.contagem(db) == 1 and r


def test_marcar_o_forms_de_um_registro_em_grupo_marca_todos_do_lote(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('B', 'b')")
    for d in (1, 2):
        for n in (1, 2):
            db.execute("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, "
                       "criado_por) VALUES (?,?,?,?,'x')", (CNPJ_OK, d, f"2025-01-0{n}", n))
    orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2], "2026-01-01", None, None)  # as duas na 3a: FORMS
    forms = [t for t in tarefas.pendencias(db) if t["tipo"] == "forms"]
    assert len(forms) == 2
    tarefas.marcar(db, USR, forms[0]["tarefa_id"])
    assert [t for t in tarefas.pendencias(db) if t["tipo"] == "forms"] == []  # as duas foram marcadas
    assert len([t for t in tarefas.pendencias(db) if t["tipo"] == "capa"]) == 2  # a capa e por orientacao


def test_orientacao_excluida_some_das_pendencias_e_a_renumeracao_ajusta_o_forms(db):
    regs = [registrar(db, f"2026-01-0{n}") for n in range(1, 5)]  # 1a, 2a, 3a (FORMS), 4a
    assert [t["tipo"] for t in tarefas.pendencias(db) if t["tipo"] == "forms"] == ["forms"]
    orientacoes.excluir(db, GESTOR, regs[1]["id"])  # exclui a 2a: a antiga 3a vira 2a e a 4a vira 3a (FORMS)
    forms = [t for t in tarefas.pendencias(db) if t["tipo"] == "forms"]
    assert len(forms) == 1 and forms[0]["orientacao_id"] == regs[3]["id"]  # o FORMS passou para a antiga 4a
    assert tipos(db, regs[2]["id"]) == ["capa"]
    assert tarefas.contagem(db) == 3 + 1  # capa das 3 orientacoes que sobraram + 1 forms
    orientacoes.excluir(db, GESTOR, regs[3]["id"])
    assert not [t for t in tarefas.pendencias(db) if t["orientacao_id"] == regs[3]["id"]]


def test_forms_ja_feito_nao_e_apagado_quando_a_acao_muda(db):
    regs = [registrar(db, f"2026-01-0{n}") for n in range(1, 4)]  # a 3a tem FORMS
    forms = [t for t in tarefas.pendencias(db) if t["tipo"] == "forms"][0]
    tarefas.marcar(db, USR, forms["tarefa_id"])
    orientacoes.excluir(db, GESTOR, regs[0]["id"])  # a 3a vira 2a: deixa de ser FORMS
    assert tipos(db, regs[2]["id"]) == ["capa", "forms"]  # mantida porque ja estava feita


def test_historico_migrado_sem_pendencias_nao_ganha_pendencia_na_renumeracao(db):
    for n in range(1, 5):
        db.execute("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, acao, "
                   "criado_por) VALUES (?,1,?,?,?,'migracao')",
                   (CNPJ_OK, f"2025-01-0{n}", n, "FORMS" if n == 3 else None))
    primeira = db.query("SELECT id FROM ori_orientacoes ORDER BY id")[0]["id"]
    orientacoes.excluir(db, GESTOR, primeira)
    assert db.query("SELECT COUNT(*) AS n FROM ori_tarefas")[0]["n"] == 0


def test_historico_e_situacao_por_desvio(db):
    registrar(db, "2026-01-01")
    registrar(db, "2026-01-02")
    h = orientacoes.historico(db, CNPJ_OK)
    assert [x["numero"] for x in h] == [2, 1] and h[0]["registrado_por"] == "a.b"
    assert orientacoes.situacao_por_desvio(db, CNPJ_OK) == [
        {"desvio": "DESVIO A", "ja_tem": 2, "proxima": "3ª orientação", "acao_da_proxima": "FORMS"}]
