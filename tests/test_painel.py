from core import orientacoes, painel, tarefas
from tests.conftest import CNPJ_OK, GESTOR, USR

OUTRO = {"usuario": "outro.u", "nome": "Outro", "perfil": "contas"}


def popular(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('DESVIO B', 'b')")
    for dia in (1, 2, 3):  # 3 do desvio A em janeiro (a 3a e FORMS)
        orientacoes.registrar(db, USR, CNPJ_OK, 1, f"2026-01-0{dia}", None, None)
    orientacoes.registrar(db, OUTRO, CNPJ_OK, 2, "2026-02-10", None, None)  # 1 do desvio B em fevereiro


def test_resumo_e_filtro_de_periodo(db):
    popular(db)
    r = painel.resumo(db)
    assert (r["orientacoes"], r["prestadores"], r["forms"], r["contato_direto"]) == (4, 1, 1, 0)
    assert r["pendencias_abertas"] == 1  # so a pendencia de FORMS da 3a (nao ha mais pendencia de capa)
    jan = painel.resumo(db, "2026-01-01", "2026-01-31")
    assert jan["orientacoes"] == 3 and jan["forms"] == 1


def test_por_mes_desvio_e_usuario(db):
    popular(db)
    assert painel.por_mes(db) == [{"mes": "2026-01", "orientacoes": 3}, {"mes": "2026-02", "orientacoes": 1}]
    assert painel.por_desvio(db)[0] == {"desvio": "DESVIO A", "orientacoes": 3}
    por_usuario = {x["usuario"]: x["orientacoes"] for x in painel.por_usuario(db)}
    assert por_usuario == {"a.b": 3, "outro.u": 1}
    assert painel.por_mes(db, "2026-02-01") == [{"mes": "2026-02", "orientacoes": 1}]


def test_quem_registrou_ignora_o_historico_importado_ate_que_se_peca(db):
    popular(db)
    db.execute("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, criado_por) "
               "VALUES (?,1,'2025-01-01',1,'migracao')", (CNPJ_OK,))
    assert {x["usuario"] for x in painel.por_usuario(db)} == {"a.b", "outro.u"}
    assert "migracao" in {x["usuario"] for x in painel.por_usuario(db, incluir_importadas=True)}
    assert painel.importadas(db) == 1 and painel.importadas(db, "2026-01-01") == 0


def test_desvio_por_mes_para_o_mapa_de_calor(db):
    popular(db)
    assert painel.desvio_por_mes(db) == [
        {"desvio": "DESVIO A", "mes": "2026-01", "orientacoes": 3},
        {"desvio": "DESVIO B", "mes": "2026-02", "orientacoes": 1}]
    assert painel.desvio_por_mes(db, "2026-02-01") == [{"desvio": "DESVIO B", "mes": "2026-02", "orientacoes": 1}]


def test_reincidentes_mostram_a_proxima_acao(db):
    popular(db)
    r = painel.reincidentes(db, minimo=3)
    assert len(r) == 1 and r[0]["orientacoes"] == 3 and r[0]["proxima"] == "4ª orientação"
    assert r[0]["acao_da_proxima"] == "—" and r[0]["prestador"] == "CLINICA TESTE"
    assert painel.reincidentes(db, minimo=4) == []


def test_excluidas_nao_entram_nos_numeros(db):
    popular(db)
    primeira = orientacoes.historico(db, CNPJ_OK)
    assert primeira
    alvo = db.query("SELECT id FROM ori_orientacoes WHERE criado_por='outro.u'")[0]["id"]
    orientacoes.excluir(db, GESTOR, alvo)
    assert painel.resumo(db)["orientacoes"] == 3 and len(painel.por_mes(db)) == 1


def test_tempo_medio_de_conclusao(db):
    popular(db)
    t = tarefas.pendencias(db)[0]["tarefa_id"]
    tarefas.marcar(db, GESTOR, t)
    r = painel.tempo_medio_de_conclusao(db)
    assert len(r) == 1 and r[0]["concluidas"] == 1 and r[0]["dias_em_media"] is not None
