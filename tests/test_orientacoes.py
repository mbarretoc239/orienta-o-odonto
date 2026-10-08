import pytest

from core import orientacoes, prestadores
from tests.conftest import CNPJ_OK, CPF_OK, GESTOR, USR


def registrar(db, data="2026-01-01", usuario=USR, sinal=None, obs=None):
    return orientacoes.registrar(db, usuario, CNPJ_OK, 1, data, sinal, obs)


def test_numeracao_e_acao_sequenciais(db):
    res = [registrar(db, data=f"2026-01-0{i}", sinal="SIM")[0] for i in range(1, 5)]
    assert [r["numero_orientacao"] for r in res] == [1, 2, 3, 4]
    assert [r["acao"] for r in res] == [None, None, "FORMS", None]
    assert len(db.query("SELECT * FROM ori_auditoria WHERE acao='INSERT'")) == 4


def test_previa_alerta_na_12(db):
    for i in range(11):
        db.execute(
            "INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, criado_por) "
            "VALUES (?,1,?,?,'x')", (CNPJ_OK, f"2026-01-{i + 1:02d}", i + 1))
    p = orientacoes.previa(db, CNPJ_OK, 1)
    assert p["numero"] == 12 and p["contato_direto"] and p["acao"] == "CONTATO DIRETO"
    reg = registrar(db, data="2026-03-01")[0]
    assert reg["numero_orientacao"] == 12 and reg["acao"] == "CONTATO DIRETO"


def _popular(db, desvio_id, quantas):
    for i in range(quantas):
        db.execute(
            "INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, criado_por) "
            "VALUES (?,?,?,?,'x')", (CNPJ_OK, desvio_id, f"2025-01-{i + 1:02d}", i + 1))


def test_varios_desvios_cada_um_com_sua_acao(db):
    """Exemplo do negocio: X na 12a (contato direto), Y na 1a (nada), Z na 3a (FORMS)."""
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('DESVIO B', 'b')")
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('DESVIO C', 'c')")
    _popular(db, 1, 11)  # X ja tem 11
    _popular(db, 3, 2)   # Z ja tem 2
    regs, msg = orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2, 3], "2026-01-01", None, None)
    por_desvio = {r["desvio_id"]: r for r in regs}
    assert (por_desvio[1]["numero_orientacao"], por_desvio[1]["acao"]) == (12, "CONTATO DIRETO")
    assert (por_desvio[2]["numero_orientacao"], por_desvio[2]["acao"]) == (1, None)
    assert (por_desvio[3]["numero_orientacao"], por_desvio[3]["acao"]) == (3, "FORMS")
    assert len({r["lote_id"] for r in regs}) == 1 and regs[0]["lote_id"]
    assert len(db.query("SELECT * FROM ori_auditoria WHERE acao='INSERT'")) == 3


def test_dois_desvios_na_3a_ficam_ambos_forms(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('DESVIO B', 'b')")
    _popular(db, 1, 2)
    _popular(db, 2, 2)
    regs, _ = orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 2], "2026-01-01", None, None)
    assert [r["acao"] for r in regs] == ["FORMS", "FORMS"]


def test_registro_em_grupo_e_tudo_ou_nada(db):
    assert orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, 1], "2026-01-01", None, None)[0] is None
    assert orientacoes.registrar_varios(db, USR, CNPJ_OK, [], "2026-01-01", None, None)[0] is None
    with pytest.raises(Exception):  # o 2o INSERT falha (desvio_id NULL): o 1o nao pode ficar gravado
        orientacoes.registrar_varios(db, USR, CNPJ_OK, [1, None], "2026-01-01", None, None)
    assert db.query("SELECT COUNT(*) AS n FROM ori_orientacoes")[0]["n"] == 0
    assert db.query("SELECT COUNT(*) AS n FROM ori_auditoria")[0]["n"] == 0


def test_aviso_so_com_registro_salvo_no_mes(db):
    assert orientacoes.registradas_no_mes(db, CNPJ_OK, "2026-10-08") == []
    registrar(db, data="2026-10-02")
    o_setembro = registrar(db, data="2026-09-30")[0]
    r = orientacoes.registradas_no_mes(db, CNPJ_OK, "2026-10-15")
    assert [(x["desvio"], x["numero"], x["data_orientacao"]) for x in r] == [("DESVIO A", 1, "2026-10-02")]
    orientacoes.excluir(db, GESTOR, o_setembro["id"])
    orientacoes.excluir(db, GESTOR, orientacoes.listar(db, CNPJ_OK)[0]["id"])
    assert orientacoes.registradas_no_mes(db, CNPJ_OK, "2026-10-15") == []  # excluida nao conta


def test_clique_duplo_nao_duplica(db):
    assert registrar(db)[0]
    reg, msg = registrar(db)
    assert reg is None and "acabou de ser registrada" in msg
    assert orientacoes.proximo_numero(db, CNPJ_OK, 1) == 2


def test_exclusao_so_gestor_e_renumera(db):
    o = registrar(db)[0]
    assert not orientacoes.excluir(db, USR, o["id"])[0]
    assert orientacoes.excluir(db, GESTOR, o["id"])[0]
    assert orientacoes.proximo_numero(db, CNPJ_OK, 1) == 1
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='DELETE'")


def test_excluir_do_meio_renumera_e_recalcula_acao(db):
    regs = [registrar(db, data=f"2026-01-0{i}")[0] for i in range(1, 5)]  # 1a, 2a, 3a (FORMS), 4a
    assert [r["acao"] for r in regs] == [None, None, "FORMS", None]
    assert orientacoes.excluir(db, GESTOR, regs[1]["id"])[0]  # exclui a 2a
    ativas = db.query("SELECT id, numero_orientacao AS n, acao FROM ori_orientacoes "
                      "WHERE excluido_em IS NULL ORDER BY id")
    assert [(a["n"], a["acao"]) for a in ativas] == [(1, None), (2, None), (3, "FORMS")]
    assert [a["id"] for a in ativas] == [regs[0]["id"], regs[2]["id"], regs[3]["id"]]
    assert orientacoes.proximo_numero(db, CNPJ_OK, 1) == 4  # sem numero repetido
    renum = db.query("SELECT registro, antes, depois FROM ori_auditoria WHERE acao='RENUMERAR'")
    assert len(renum) == 2 and any('"numero": 3' in r["depois"] for r in renum)


def test_excluir_a_ultima_nao_renumera_nada(db):
    regs = [registrar(db, data=f"2026-01-0{i}")[0] for i in range(1, 4)]
    assert orientacoes.excluir(db, GESTOR, regs[2]["id"])[0]
    assert db.query("SELECT COUNT(*) AS n FROM ori_auditoria WHERE acao='RENUMERAR'")[0]["n"] == 0
    assert orientacoes.proximo_numero(db, CNPJ_OK, 1) == 3


def test_exclusao_renumera_so_o_mesmo_desvio(db):
    db.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('DESVIO B', 'b')")
    a1 = registrar(db, data="2026-01-01")[0]
    orientacoes.registrar(db, USR, CNPJ_OK, 2, "2026-01-02", None, None)
    registrar(db, data="2026-01-03")
    orientacoes.excluir(db, GESTOR, a1["id"])
    por_desvio = {r["desvio_id"]: r["numero_orientacao"] for r in
                  db.query("SELECT desvio_id, numero_orientacao FROM ori_orientacoes WHERE excluido_em IS NULL")}
    assert por_desvio == {1: 1, 2: 1}  # o desvio B continua na 1a


def test_edicao_so_gestor_e_audita(db):
    o = registrar(db)[0]
    assert not orientacoes.editar(db, USR, o["id"], "2026-02-02", "SIM", "x")[0]
    assert orientacoes.editar(db, GESTOR, o["id"], "2026-02-02", "SIM", "obs nova")[0]
    novo = db.query("SELECT * FROM ori_orientacoes WHERE id=?", (o["id"],))[0]
    assert novo["data_orientacao"] == "2026-02-02" and novo["observacao"] == "obs nova"
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='UPDATE' AND antes LIKE '%2026-01-01%'")


def test_so_gestor_e_admin_cadastram_prestador(db):
    ok, msg = prestadores.cadastrar(db, USR, CPF_OK, "MARIA")
    assert not ok and msg == "Prestador não cadastrado, contate o gestor para verificar."
    assert prestadores.buscar(db, CPF_OK) is None
    assert prestadores.cadastrar(db, {**USR, "perfil": "admin"}, CPF_OK, "MARIA")[0]


def test_cadastro_e_renomear_prestador(db):
    assert not prestadores.cadastrar(db, GESTOR, "123", "X")[0]
    assert prestadores.cadastrar(db, GESTOR, CPF_OK, "  maria  da silva ")[0]
    assert prestadores.buscar(db, CPF_OK)["nome"] == "MARIA DA SILVA"
    assert not prestadores.cadastrar(db, GESTOR, CPF_OK, "outro")[0]
    assert prestadores.renomear(db, GESTOR, CPF_OK, "maria da silva souza")[0]
    assert prestadores.buscar(db, CPF_OK)["nome"] == "MARIA DA SILVA SOUZA"
    assert prestadores.buscar_por_nome(db, "silva souza")[0]["documento"] == CPF_OK
