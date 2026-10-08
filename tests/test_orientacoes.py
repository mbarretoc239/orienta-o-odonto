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
