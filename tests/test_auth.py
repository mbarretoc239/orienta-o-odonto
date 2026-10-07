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
    for restantes in (4, 3, 2, 1):
        _, msg = auth.autenticar(db, "novo.x", "errada")
        assert f"Restam {restantes}" in msg
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


def test_admin_nao_remove_proprio_acesso(db):
    admin = {**GESTOR, "usuario": "adm", "perfil": "admin"}
    auth.criar_admin(db, "adm", "Adm", SENHA)
    assert not usuarios.atualizar(db, admin, "adm", "contas", "ativo")[0]
    assert not usuarios.atualizar(db, admin, "adm", "admin", "inativo")[0]
    assert usuarios.atualizar(db, admin, "adm", "admin", "ativo")[0]
