import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core import auth, servico
from core.db import LocalDb, criar_schema
from core.regras import (
    acao_para,
    normalizar_documento,
    valida_cnpj,
    valida_cpf,
)

CPF_OK = "52998224725"
CNPJ_OK = "11222333000181"


def test_normaliza_documento_restaura_zeros():
    assert normalizar_documento("1.234.567-89") == "00123456789"
    assert normalizar_documento(114312000398) == "00114312000398"
    assert normalizar_documento("") == ""


def test_validadores():
    assert valida_cpf(CPF_OK) and not valida_cpf("11111111111") and not valida_cpf("52998224724")
    assert valida_cnpj(CNPJ_OK) and not valida_cnpj("11222333000180")


def test_contato_direto_a_partir_da_12():
    from core.regras import exige_contato_direto

    assert not exige_contato_direto(11) and exige_contato_direto(12) and exige_contato_direto(15)


def test_acao_a_cada_tres():
    assert [acao_para(n) for n in range(1, 7)] == [None, None, "FORMS", None, None, "FORMS"]


@pytest.fixture
def db():
    d = LocalDb(":memory:")
    criar_schema(d)
    d.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('DESVIO A', 'texto')")
    d.execute("INSERT INTO ori_prestadores (documento, nome) VALUES (?, 'CLINICA TESTE')", (CNPJ_OK,))
    return d


USR = {"usuario": "a.b", "nome": "A", "perfil": "contas"}


def test_numeracao_e_acao_sequenciais(db):
    resultados = [
        servico.registrar_orientacao(db, USR, CNPJ_OK, 1, "2026-01-01", "SIM", None)[0] for _ in range(4)
    ]
    assert [r["numero_orientacao"] for r in resultados] == [1, 2, 3, 4]
    assert [r["acao"] for r in resultados] == [None, None, "FORMS", None]
    assert len(db.query("SELECT * FROM ori_auditoria WHERE acao='INSERT'")) == 4


def test_exclusao_so_gestor_e_renumera(db):
    o = servico.registrar_orientacao(db, USR, CNPJ_OK, 1, "2026-01-01", None, None)[0]
    assert not servico.excluir_orientacao(db, USR, o["id"])[0]
    gestor = {**USR, "perfil": "gestor"}
    assert servico.excluir_orientacao(db, gestor, o["id"])[0]
    assert servico.proximo_numero(db, CNPJ_OK, 1) == 1
    assert db.query("SELECT acao FROM ori_auditoria WHERE acao='DELETE'")


def test_cadastro_prestador_novo(db):
    assert not servico.cadastrar_prestador(db, USR, "123", "X")[0]
    assert servico.cadastrar_prestador(db, USR, CPF_OK, "  maria  da silva ")[0]
    assert servico.buscar_prestador(db, CPF_OK)["nome"] == "MARIA DA SILVA"
    assert not servico.cadastrar_prestador(db, USR, CPF_OK, "outro")[0]


def test_login_fluxo_pendente_ativo(db):
    assert auth.registrar_usuario(db, "novo.x", "Novo", "senha-segura-1")[0]
    assert not auth.registrar_usuario(db, "NOVO.X", "Novo", "senha-segura-1")[0]
    assert not auth.registrar_usuario(db, "a b", "N", "senha-segura-1")[0]
    assert not auth.registrar_usuario(db, "bb", "N", "senha-segura-1")[0]
    assert not auth.registrar_usuario(db, "outro.u", "N", "curta")[0]
    u, msg = auth.autenticar(db, "novo.x", "senha-segura-1")
    assert u is None and "aprova" in msg
    db.execute("UPDATE ori_usuarios SET status='ativo' WHERE usuario='novo.x'")
    u, _ = auth.autenticar(db, " NOVO.X ", "senha-segura-1")
    assert u["perfil"] == "contas" and u["usuario"] == "novo.x"
    assert auth.autenticar(db, "novo.x", "errada")[0] is None
