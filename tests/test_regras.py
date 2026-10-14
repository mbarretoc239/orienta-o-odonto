from core.regras import (
    acao_para,
    exige_contato_direto,
    exige_relato_gestao,
    normalizar_documento,
    valida_cnpj,
    valida_cpf,
)
from tests.conftest import CNPJ_OK, CPF_OK


def test_normaliza_documento_restaura_zeros():
    assert normalizar_documento("1.234.567-89") == "00123456789"
    assert normalizar_documento(114312000398) == "00114312000398"
    assert normalizar_documento("") == ""


def test_validadores():
    assert valida_cpf(CPF_OK) and not valida_cpf("11111111111") and not valida_cpf("52998224724")
    assert valida_cnpj(CNPJ_OK) and not valida_cnpj("11222333000180")


def test_acao_a_cada_tres():
    assert [acao_para(n) for n in range(1, 7)] == [None, None, "FORMS", None, None, "FORMS"]


def test_acao_por_numero_da_orientacao():
    assert [acao_para(n) for n in (1, 2, 3, 6, 9, 10, 11)] == [None, None, "FORMS", "FORMS", "FORMS", None, None]
    assert acao_para(12) == "CONTATO DIRETO"
    assert [acao_para(n) for n in (13, 14, 15, 30)] == ["RELATAR PARA GESTÃO"] * 4  # da 13a em diante, mesmo multiplo de 3


def test_contato_direto_so_na_12_e_gestao_da_13_em_diante():
    assert not exige_contato_direto(11) and exige_contato_direto(12) and not exige_contato_direto(13)
    assert not exige_relato_gestao(12) and exige_relato_gestao(13) and exige_relato_gestao(15)
