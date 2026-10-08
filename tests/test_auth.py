from core import auth, sessao, usuarios
from tests.conftest import GESTOR

SENHA = "senha-segura-1"


def ativar(db, login):
    db.execute("UPDATE ori_usuarios SET status='ativo' WHERE usuario=?", (login,))


def test_cadastro_valida_entradas(db):
    assert auth.registrar_usuario(db, "novo.x", "Novo", SENHA)[0]
    assert not auth.registrar_usuario(db, "NOVO.X", "Novo", SENHA)[0]
    assert not auth.registrar_usuario(db, "a b", "N", SENHA)[0]
    assert not auth.registrar_usuario(db, "bb", "N", SENHA)[0]
    assert not auth.registrar_usuario(db, "outro.u", "N", "curta")[0]


def test_fluxo_pendente_ativo(db):
    auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    u, msg = auth.autenticar(db, "novo.x", SENHA)
    assert u is None and "aprova" in msg
    ativar(db, "novo.x")
    u, _ = auth.autenticar(db, " NOVO.X ", SENHA)
    assert u["perfil"] == "contas" and u["usuario"] == "novo.x"


def test_bloqueio_apos_5_tentativas(db):
    auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    ativar(db, "novo.x")
    for _ in range(4):
        _, msg = auth.autenticar(db, "novo.x", "errada")
        assert msg == "Usuario ou senha incorretos."  # igual a de um usuario que nao existe
    assert auth.autenticar(db, "nao.existe", "errada")[1] == msg
    _, msg = auth.autenticar(db, "novo.x", "errada")
    assert "bloqueada" in msg
    u, msg = auth.autenticar(db, "novo.x", SENHA)  # senha certa, mas conta bloqueada
    assert u is None and "minuto" in msg
    usuarios.desbloquear(db, "novo.x")
    assert auth.autenticar(db, "novo.x", SENHA)[0]["usuario"] == "novo.x"


def test_acerto_zera_tentativas(db):
    auth.registrar_usuario(db, "novo.x", "Novo", SENHA)
    ativar(db, "novo.x")
    auth.autenticar(db, "novo.x", "errada")
    auth.autenticar(db, "novo.x", SENHA)
    assert db.query("SELECT tentativas FROM ori_usuarios")[0]["tentativas"] == 0


def test_sessao_valida_expirada_e_encerrada(db):
    token = sessao.criar(db, "novo.x")
    assert sessao.usuario_da_sessao(db, token) == "novo.x"
    assert sessao.usuario_da_sessao(db, "token-falso") is None
    assert token not in str(db.query("SELECT * FROM ori_sessoes"))  # so o hash e guardado
    db.execute("UPDATE ori_sessoes SET expira_em = datetime('now', '-1 minute')")
    assert sessao.usuario_da_sessao(db, token) is None
    token2 = sessao.criar(db, "novo.x")
    sessao.encerrar(db, token2)
    assert sessao.usuario_da_sessao(db, token2) is None


def novo_usuario(db, login="novo.x"):
    ok, _, codigo = auth.registrar_usuario(db, login, "Novo", SENHA)
    assert ok and len(codigo) == 14 and codigo.count("-") == 2
    ativar(db, login)
    return codigo


def test_codigo_nao_fica_em_texto_no_banco(db):
    codigo = novo_usuario(db)
    assert codigo not in str(db.query("SELECT * FROM ori_usuarios"))
    assert codigo.replace("-", "") not in str(db.query("SELECT * FROM ori_usuarios"))


def test_esqueci_senha_com_codigo(db):
    codigo = novo_usuario(db)
    token = sessao.criar(db, "novo.x")
    ok, _, novo = auth.redefinir_com_codigo(db, "NOVO.X", codigo.lower().replace("-", " "), "outra-senha-9")
    assert ok and novo != codigo
    assert auth.autenticar(db, "novo.x", SENHA)[0] is None  # senha antiga nao vale mais
    assert auth.autenticar(db, "novo.x", "outra-senha-9")[0]["usuario"] == "novo.x"
    assert sessao.usuario_da_sessao(db, token) is None  # sessoes abertas encerradas
    assert not auth.redefinir_com_codigo(db, "novo.x", codigo, "terceira-senha-9")[0]  # codigo usado nao vale
    assert auth.redefinir_com_codigo(db, "novo.x", novo, "terceira-senha-9")[0]


def test_codigo_errado_conta_tentativas_e_bloqueia(db):
    novo_usuario(db)
    for _ in range(4):
        ok, msg, _ = auth.redefinir_com_codigo(db, "novo.x", "AAAA-BBBB-CCCC", "outra-senha-9")
        assert not ok and msg == "Usuario ou codigo de recuperacao invalidos."
    assert "bloqueada" in auth.redefinir_com_codigo(db, "novo.x", "AAAA-BBBB-CCCC", "outra-senha-9")[1]
    assert "minuto" in auth.autenticar(db, "novo.x", SENHA)[1]  # o bloqueio vale tambem para o login


def test_redefinir_valida_entradas(db):
    codigo = novo_usuario(db)
    assert not auth.redefinir_com_codigo(db, "inexistente", codigo, "outra-senha-9")[0]
    assert "ao menos" in auth.redefinir_com_codigo(db, "novo.x", codigo, "curta")[1]
    assert auth.autenticar(db, "novo.x", SENHA)[0]  # nada mudou


def test_usuario_sem_codigo_nao_recupera(db):
    novo_usuario(db)
    db.execute("UPDATE ori_usuarios SET codigo_hash=NULL")
    assert not auth.redefinir_com_codigo(db, "novo.x", "AAAA-BBBB-CCCC", "outra-senha-9")[0]


def test_admin_redefine_e_obriga_troca(db):
    novo_usuario(db)
    admin = {**GESTOR, "usuario": "adm", "perfil": "admin"}
    token = sessao.criar(db, "novo.x")
    temporaria = usuarios.redefinir_senha(db, admin, "novo.x")
    assert sessao.usuario_da_sessao(db, token) is None
    assert auth.autenticar(db, "novo.x", SENHA)[0] is None
    u, _ = auth.autenticar(db, "novo.x", temporaria)
    assert u["trocar_senha"] is True
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='RESET_SENHA' AND quem='adm'")
    assert not auth.trocar_senha(db, "novo.x", "errada", "nova-senha-9")[0]
    assert not auth.trocar_senha(db, "novo.x", temporaria, temporaria)[0]  # tem que ser diferente
    ok, _, codigo = auth.trocar_senha(db, "novo.x", temporaria, "nova-senha-9")
    assert ok and codigo is None  # ja tinha codigo: nao gera outro
    assert auth.autenticar(db, "novo.x", "nova-senha-9")[0]["trocar_senha"] is False


def test_trocar_senha_gera_codigo_para_quem_nao_tinha(db):
    novo_usuario(db)
    db.execute("UPDATE ori_usuarios SET codigo_hash=NULL")
    ok, _, codigo = auth.trocar_senha(db, "novo.x", SENHA, "nova-senha-9")
    assert ok and codigo
    assert auth.redefinir_com_codigo(db, "novo.x", codigo, "ultima-senha-9")[0]


def test_admin_gera_novo_codigo(db):
    antigo = novo_usuario(db)
    admin = {**GESTOR, "usuario": "adm", "perfil": "admin"}
    novo = usuarios.gerar_codigo_recuperacao(db, admin, "novo.x")
    assert not auth.redefinir_com_codigo(db, "novo.x", antigo, "outra-senha-9")[0]
    assert auth.redefinir_com_codigo(db, "novo.x", novo, "outra-senha-9")[0]
    assert db.query("SELECT 1 FROM ori_auditoria WHERE acao='NOVO_CODIGO'")


def test_criar_admin_devolve_codigo(db):
    codigo = auth.criar_admin(db, "adm", "Adm", SENHA)
    assert auth.redefinir_com_codigo(db, "adm", codigo, "outra-senha-9")[0]


def test_admin_nao_remove_proprio_acesso(db):
    admin = {**GESTOR, "usuario": "adm", "perfil": "admin"}
    auth.criar_admin(db, "adm", "Adm", SENHA)
    assert not usuarios.atualizar(db, admin, "adm", "contas", "ativo")[0]
    assert not usuarios.atualizar(db, admin, "adm", "admin", "inativo")[0]
    assert usuarios.atualizar(db, admin, "adm", "admin", "ativo")[0]
