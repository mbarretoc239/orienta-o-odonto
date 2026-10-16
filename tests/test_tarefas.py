from core import orientacoes, tarefas
from tests.conftest import CNPJ_OK, GESTOR, USR

OUTRO = {"usuario": "outro.u", "nome": "Outro", "perfil": "contas"}


def registrar(db, data="2026-01-01", usuario=USR, desvio=1, **kw):
    return orientacoes.registrar(db, usuario, CNPJ_OK, desvio, data, None, None, **kw)[0]


def tipos(db, orientacao_id):
    return sorted(r["tipo"] for r in db.query("SELECT tipo FROM ori_tarefas WHERE orientacao_id=?", (orientacao_id,)))


def popular_desvio(db, desvio_id, quantas, autor="x"):
    for n in range(1, quantas + 1):
        db.execute("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, criado_por) "
                   "VALUES (?,?,?,?,?)", (CNPJ_OK, desvio_id, f"2025-01-{n:02d}", n, autor))


def test_so_ha_pendencia_de_acao_e_nenhuma_para_a_1a_e_2a(db):
    regs = [registrar(db, f"2026-01-{n:02d}") for n in range(1, 4)]
    assert tipos(db, regs[0]["id"]) == [] and tipos(db, regs[1]["id"]) == []  # sem pendencia de capa
    assert tipos(db, regs[2]["id"]) == ["forms"]  # a 3a: FORMS
    assert tarefas.contagem(db) == 1 and "capa" not in tarefas.TIPOS


def test_a_partir_da_12a_a_pendencia_e_contato_direto_e_nao_forms(db):
    popular_desvio(db, 1, 11)
    d12 = registrar(db, "2026-02-01")
    assert d12["acao"] == "CONTATO DIRETO" and tipos(db, d12["id"]) == ["contato_direto"]


def test_registro_em_grupo_cria_uma_pendencia_de_forms_por_desvio_na_3a(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('B', 'b')")
    popular_desvio(db, 1, 2)
    popular_desvio(db, 2, 2)
    regs, _ = orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2], "2026-01-01", None, None)
    assert all(tipos(db, r["id"]) == ["forms"] for r in regs)


def test_cada_usuario_ve_so_as_suas_e_o_gestor_ve_por_usuario(db):
    popular_desvio(db, 1, 2)
    registrar(db, "2026-01-01", USR)  # 3a de a.b
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('B', 'b')")
    popular_desvio(db, 2, 2)
    orientacoes.registrar(db, OUTRO, CNPJ_OK, 2, "2026-01-02", None, None)  # 3a de outro.u
    assert len(tarefas.pendencias(db, USR["usuario"])) == 1
    assert len(tarefas.pendencias(db)) == 2
    resumo = {r["usuario"]: (r["forms"], r["contato_direto"], r["total"]) for r in tarefas.resumo_por_usuario(db)}
    assert resumo == {"a.b": (1, 0, 1), "outro.u": (1, 0, 1)}
    assert tarefas.contagem(db, USR["usuario"]) == 1 and tarefas.contagem(db) == 2


def test_marcar_so_as_proprias_exceto_gestor(db):
    popular_desvio(db, 1, 2)
    registrar(db, "2026-01-01", USR)
    t = tarefas.pendencias(db)[0]["tarefa_id"]
    ok, msg = tarefas.marcar(db, OUTRO, t)
    assert not ok and "suas proprias" in msg
    assert tarefas.marcar(db, USR, t)[0]
    assert tarefas.pendencias(db) == [] and tarefas.contagem(db) == 0
    assert db.query("SELECT feita_por FROM ori_tarefas WHERE id=?", (t,))[0]["feita_por"] == "a.b"
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='CONCLUIR' AND quem='a.b'")
    assert tarefas.marcar(db, GESTOR, t, feita=False)[0]  # gestor pode reabrir qualquer uma
    assert tarefas.contagem(db) == 1


def test_marcar_o_forms_de_um_registro_em_grupo_marca_todos_do_lote(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('B', 'b')")
    popular_desvio(db, 1, 2)
    popular_desvio(db, 2, 2)
    orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2], "2026-01-01", None, None)  # as duas na 3a: FORMS
    forms = tarefas.pendencias(db)
    assert len(forms) == 2
    tarefas.marcar(db, USR, forms[0]["tarefa_id"])
    assert tarefas.pendencias(db) == []  # as duas foram marcadas


def test_ja_nasce_concluida_quando_a_pessoa_marca_na_hora_de_registrar(db):
    popular_desvio(db, 1, 2)
    r = registrar(db, "2026-01-01", forms_feito=True)  # a 3a, com o FORMS ja enviado
    assert tipos(db, r["id"]) == ["forms"] and tarefas.contagem(db) == 0
    feita = db.query("SELECT feita_por, feita_em FROM ori_tarefas WHERE orientacao_id=?", (r["id"],))[0]
    assert feita["feita_por"] == "a.b" and feita["feita_em"]
    assert len([p for p in tarefas.pendencias(db, incluir_concluidas_dias=30) if p["feita_em"]]) == 1


def test_contato_direto_ja_feito_vale_so_para_o_desvio_marcado(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('B', 'b')")
    popular_desvio(db, 1, 11)
    popular_desvio(db, 2, 11)
    regs, _ = orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2], "2026-02-01", None, None,
                                           contato_direto_feito=[1])
    em_aberto = tarefas.pendencias(db)
    assert [(p["desvio"], p["tipo"]) for p in em_aberto] == [("B", "contato_direto")]  # so o desvio 2 ficou pendente
    assert em_aberto[0]["orientacao_id"] == [r for r in regs if r["desvio_id"] == 2][0]["id"]


def test_forms_nao_marcado_no_registro_fica_pendente(db):
    popular_desvio(db, 1, 2)
    registrar(db, "2026-01-01")
    assert tarefas.contagem(db) == 1


def test_orientacao_excluida_some_das_pendencias_e_a_renumeracao_ajusta_o_forms(db):
    regs = [registrar(db, f"2026-01-0{n}") for n in range(1, 5)]  # 1a, 2a, 3a (FORMS), 4a
    assert [t["orientacao_id"] for t in tarefas.pendencias(db)] == [regs[2]["id"]]
    orientacoes.excluir(db, GESTOR, regs[1]["id"])  # exclui a 2a: a antiga 3a vira 2a e a 4a vira 3a (FORMS)
    assert [t["orientacao_id"] for t in tarefas.pendencias(db)] == [regs[3]["id"]]  # o FORMS passou para a antiga 4a
    assert tipos(db, regs[2]["id"]) == []
    orientacoes.excluir(db, GESTOR, regs[3]["id"])
    assert tarefas.pendencias(db) == []


def test_forms_ja_feito_nao_e_apagado_quando_a_acao_muda(db):
    regs = [registrar(db, f"2026-01-0{n}") for n in range(1, 4)]  # a 3a tem FORMS
    tarefas.marcar(db, USR, tarefas.pendencias(db)[0]["tarefa_id"])
    orientacoes.excluir(db, GESTOR, regs[0]["id"])  # a 3a vira 2a: deixa de ser FORMS
    assert tipos(db, regs[2]["id"]) == ["forms"]  # mantida porque ja estava feita


def test_historico_importado_nao_ganha_pendencia_na_renumeracao(db):
    for n in range(1, 5):
        db.execute("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, acao, "
                   "criado_por) VALUES (?,1,?,?,?,'migracao')",
                   (CNPJ_OK, f"2025-01-0{n}", n, "FORMS" if n == 3 else None))
    primeira = db.query("SELECT id FROM ori_orientacoes ORDER BY id")[0]["id"]
    orientacoes.excluir(db, GESTOR, primeira)
    assert db.query("SELECT COUNT(*) AS n FROM ori_tarefas")[0]["n"] == 0


def test_pendencias_antigas_da_capa_sao_removidas_e_nunca_aparecem(db):
    popular_desvio(db, 1, 2)
    r = registrar(db, "2026-01-01")
    db.execute("INSERT INTO ori_tarefas (orientacao_id, tipo) VALUES (?, 'capa')", (r["id"],))
    assert tarefas.contagem(db) == 1 and all(p["tipo"] != "capa" for p in tarefas.pendencias(db))  # ja ignorada
    tarefas.remover_pendencias_da_capa(db)
    assert db.query("SELECT COUNT(*) AS n FROM ori_tarefas WHERE tipo='capa'")[0]["n"] == 0
    assert tipos(db, r["id"]) == ["forms"]  # a de FORMS continua


def test_historico_e_situacao_por_desvio(db):
    registrar(db, "2026-01-01")
    registrar(db, "2026-01-02")
    h = orientacoes.historico(db, CNPJ_OK)
    assert [x["numero"] for x in h] == [2, 1] and h[0]["registrado_por"] == "a.b"
    assert orientacoes.situacao_por_desvio(db, CNPJ_OK) == [
        {"desvio": "DESVIO A", "ja_tem": 2, "proxima": "3ª orientação", "acao_da_proxima": "FORMS"}]


def test_da_13a_a_pendencia_e_relatar_para_gestao_e_so_o_gestor_marca(db):
    popular_desvio(db, 1, 12)
    r13 = registrar(db, "2026-02-01")
    assert r13["acao"] == "RELATAR PARA GESTÃO" and tipos(db, r13["id"]) == ["relatar_gestao"]
    tarefa = tarefas.pendencias(db)[0]
    ok, msg = tarefas.marcar(db, USR, tarefa["tarefa_id"])  # quem registrou nao marca
    assert not ok and "gestor" in msg and tarefas.contagem(db) == 1
    assert tarefas.marcar(db, GESTOR, tarefa["tarefa_id"])[0]
    assert tarefas.contagem(db) == 0 and tarefas.contagem(db, USR["usuario"]) == 0  # sai da lista de quem registrou


def test_relato_a_gestao_conta_para_o_gestor_e_nao_para_outros_gestores_de_contas(db):
    popular_desvio(db, 1, 12)
    registrar(db, "2026-02-01")  # a.b registra a 13a
    assert tarefas.contagem(db, "a.b", "contas") == 1
    assert tarefas.contagem(db, "g.estor", "gestor") == 1  # o gestor ve o relato de qualquer pessoa
    assert tarefas.contagem(db, "outro.u", "contas") == 0
    por_usuario = {r["usuario"]: r for r in tarefas.resumo_por_usuario(db)}
    assert por_usuario["a.b"]["relatar_gestao"] == 1 and por_usuario["a.b"]["total"] == 1


def test_renumeracao_move_a_pendencia_entre_contato_direto_e_relato_a_gestao(db):
    popular_desvio(db, 1, 12)
    r13 = registrar(db, "2026-02-01")
    assert tipos(db, r13["id"]) == ["relatar_gestao"]
    primeira = db.query("SELECT id FROM ori_orientacoes WHERE desvio_id=1 AND numero_orientacao=1")[0]["id"]
    assert orientacoes.excluir(db, GESTOR, primeira)[0]  # a 13a vira 12a
    assert tipos(db, r13["id"]) == ["contato_direto"]


def test_banco_antigo_com_check_de_tipos_e_recriado_sem_perder_pendencias(db):
    from core.db import _liberar_tipo_relatar_gestao

    registrar(db, "2026-01-01"), registrar(db, "2026-01-02"), registrar(db, "2026-01-03")  # a 3a gera FORMS
    antes = db.query("SELECT * FROM ori_tarefas ORDER BY id")
    db.batch([("ALTER TABLE ori_tarefas RENAME TO ori_tarefas_velha", ()),
              ("CREATE TABLE ori_tarefas (id INTEGER PRIMARY KEY AUTOINCREMENT, orientacao_id INTEGER NOT NULL, "
               "tipo TEXT NOT NULL CHECK (tipo IN ('capa','forms','contato_direto')), feita_em TEXT, feita_por TEXT, "
               "criado_em TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE (orientacao_id, tipo))", ()),
              ("INSERT INTO ori_tarefas SELECT * FROM ori_tarefas_velha", ()), ("DROP TABLE ori_tarefas_velha", ())])
    _liberar_tipo_relatar_gestao(db)
    assert db.query("SELECT * FROM ori_tarefas ORDER BY id") == antes
    db.execute("INSERT INTO ori_tarefas (orientacao_id, tipo) VALUES (1, 'relatar_gestao')")  # agora o tipo e aceito
    _liberar_tipo_relatar_gestao(db)  # idempotente


def test_agrupar_junta_o_forms_do_mesmo_registro_e_deixa_os_outros_separados(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao, orientacao_forms) VALUES ('B', 'b', 'colher a assinatura')")
    popular_desvio(db, 1, 2)
    popular_desvio(db, 2, 2)
    regs, _ = orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2], "2026-01-01", None, None)  # 3a nos dois: 1 FORMS
    itens = tarefas.agrupar(tarefas.pendencias(db))
    assert len(itens) == 1 and itens[0]["tipo"] == "forms" and len(itens[0]["tarefa_ids"]) == 2
    assert tarefas.contagem(db) == 1  # o contador do menu segue a mesma regra: um FORMS por registro
    assert tarefas.resumo_por_usuario(db)[0]["forms"] == 1 and tarefas.resumo_por_usuario(db)[0]["total"] == 1
    assert [d["desvio"] for d in itens[0]["desvios"]] == ["DESVIO A", "B"]
    assert {d["orientacao"] for d in itens[0]["desvios"]} == {None, "colher a assinatura"}
    assert regs  # o relato usa os mesmos dados que o item agrupado traz
    from core import textos
    texto = textos.relato_forms("PRESTADOR", CNPJ_OK, itens[0]["desvios"])
    assert "DESVIO A" in texto and '"B"' in texto and "colher a assinatura" in texto


def test_agrupar_nao_junta_registros_diferentes_nem_tipos_diferentes(db):
    popular_desvio(db, 1, 2)
    registrar(db, "2026-01-01")  # 3a: FORMS (lote 1)
    popular_desvio(db, 1, 8)  # leva o desvio ate a 11a
    registrar(db, "2026-02-01")  # 12a: contato direto
    itens = tarefas.agrupar(tarefas.pendencias(db))
    assert sorted(i["tipo"] for i in itens) == ["contato_direto", "forms"]
