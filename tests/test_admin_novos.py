from core import auditoria, auth, logs, orientacoes, sessao, usuarios
from tests.conftest import CNPJ_OK, GESTOR, USR

ADMIN = {"usuario": "adm", "nome": "Adm", "perfil": "admin"}
SENHA = "senha-segura-1"


# ---------- logs ----------

def test_log_grava_filtra_e_guarda_o_traceback(db):
    try:
        1 / 0
    except ZeroDivisionError as e:
        logs.registrar_excecao(db, e, usuario="a.b", pagina="Registrar")
    logs.registrar(db, "aviso", "acesso_negado", "perfil contas", "outro.u", "Admin")
    todos = logs.listar(db)
    assert len(todos) == 2 and todos[0]["evento"] == "acesso_negado"  # o mais recente primeiro
    erro = logs.listar(db, nivel="erro")[0]
    assert erro["evento"].startswith("ZeroDivisionError") and "Traceback" in erro["detalhe"] and erro["pagina"] == "Registrar"
    assert len(logs.listar(db, usuario="outro.u")) == 1
    assert len(logs.listar(db, texto="ZeroDivision")) == 1
    assert logs.listar(db, nivel="info") == []


def test_log_nunca_levanta_erro_mesmo_com_banco_quebrado():
    class Quebrado:
        def execute(self, *a, **k):
            raise RuntimeError("banco fora")

    logs.registrar(Quebrado(), "erro", "x")  # nao pode propagar
    logs.limpar_antigos(Quebrado())


def test_limpeza_remove_so_o_que_passou_da_retencao(db):
    logs.registrar(db, "info", "novo")
    logs.registrar(db, "info", "velho")
    db.execute("UPDATE ori_logs SET quando = datetime('now', '-120 days') WHERE evento='velho'")
    logs.limpar_antigos(db, dias=90)
    assert [r["evento"] for r in logs.listar(db)] == ["novo"]


def test_bloqueio_de_login_vira_log(db):
    auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    db.execute("UPDATE ori_usuarios SET status='ativo'")
    for _ in range(auth.MAX_TENTATIVAS):
        auth.autenticar(db, "novo.x", "errada")
    bloqueio = logs.listar(db, nivel="aviso")[0]
    assert bloqueio["evento"] == "conta_bloqueada" and bloqueio["usuario"] == "novo.x"


# ---------- auditoria com filtros ----------

def test_auditoria_filtra_por_quem_tabela_acao_periodo_e_registro(db):
    o = orientacoes.registrar(db, USR, CNPJ_OK, 1, "2026-01-01", None, None)[0]
    orientacoes.excluir(db, GESTOR, o["id"])
    op = auditoria.opcoes(db)
    assert op["quem"] == ["a.b"] and set(op["acao"]) >= {"INSERT", "DELETE"} and "ori_orientacoes" in op["tabela"]
    assert [r["acao"] for r in auditoria.listar(db, acao="DELETE")] == ["DELETE"]
    assert auditoria.listar(db, quem="ninguem") == []
    assert auditoria.listar(db, registro=o["id"], acao="INSERT")[0]["registro"] == str(o["id"])
    assert auditoria.listar(db, data_ini="2999-01-01") == []
    assert len(auditoria.listar(db, limite=1)) == 1


# ---------- aprovacao de cadastros ----------

def test_aprovar_libera_o_login_com_o_perfil_escolhido(db):
    auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    assert usuarios.contar_pendentes(db) == 1 and [p["usuario"] for p in usuarios.pendentes(db)] == ["novo.x"]
    assert auth.autenticar(db, "novo.x", SENHA)[0] is None  # ainda pendente
    ok, _ = usuarios.aprovar(db, ADMIN, "novo.x", "gestor")
    assert ok and usuarios.contar_pendentes(db) == 0
    assert auth.autenticar(db, "novo.x", SENHA)[0]["perfil"] == "gestor"
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='APROVAR' AND quem='adm'")
    assert not usuarios.aprovar(db, ADMIN, "novo.x", "gestor")[0]  # ja nao esta pendente
    assert not usuarios.aprovar(db, ADMIN, "inexistente")[0]
    auth.registrar_usuario(db, "outro.u", "Outro", SENHA)
    assert not usuarios.aprovar(db, ADMIN, "outro.u", "superuser")[0]  # perfil invalido


def test_recusar_deixa_inativo(db):
    auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    assert usuarios.recusar(db, ADMIN, "novo.x")[0]
    assert auth.autenticar(db, "novo.x", SENHA)[1] == "Usuario inativo."
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='RECUSAR'")


# ---------- minha conta ----------

def test_novo_codigo_com_a_senha_invalida_o_anterior(db):
    _, _, antigo = auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    db.execute("UPDATE ori_usuarios SET status='ativo'")
    ok, msg, novo = auth.novo_codigo_com_senha(db, "novo.x", "senha-errada")
    assert not ok and novo is None and msg == "Senha incorreta."
    ok, _, novo = auth.novo_codigo_com_senha(db, "novo.x", SENHA)
    assert ok and novo != antigo
    assert not auth.redefinir_com_codigo(db, "novo.x", antigo, "outra-senha-9")[0]
    assert auth.redefinir_com_codigo(db, "novo.x", novo, "outra-senha-9")[0]


def test_senha_errada_ao_gerar_codigo_conta_para_o_bloqueio(db):
    auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    db.execute("UPDATE ori_usuarios SET status='ativo'")
    for _ in range(auth.MAX_TENTATIVAS):
        auth.novo_codigo_com_senha(db, "novo.x", "errada")
    assert "minuto" in auth.novo_codigo_com_senha(db, "novo.x", SENHA)[1]


def test_trocar_senha_pode_derrubar_as_outras_sessoes_e_manter_a_atual(db):
    atual, outra = sessao.criar(db, "novo.x"), sessao.criar(db, "novo.x")
    sessao.encerrar_outras(db, "novo.x", atual)
    assert sessao.usuario_da_sessao(db, atual) == "novo.x" and sessao.usuario_da_sessao(db, outra) is None
