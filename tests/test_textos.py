from core.textos import relato_forms
from tests.conftest import CNPJ_OK, CPF_OK


def test_relato_de_um_desvio():
    t = relato_forms("CLINICA TESTE", CNPJ_OK, [{"desvio": "FALTA DATA DO ATENDIMENTO", "numero": 3, "data": "2026-10-08"}])
    assert t == (
        'Prestador CLINICA TESTE (CNPJ 11.222.333/0001-81) recebeu a 3ª orientação pelo desvio '
        '"FALTA DATA DO ATENDIMENTO" em 08/10/2026, com encaminhamento para o FORMS.\n\nRelato:\n')


def test_relato_de_varios_desvios_lista_cada_um():
    itens = [
        {"desvio": "DESVIO A", "numero": 3, "data": "2026-10-08"},
        {"desvio": "DESVIO B", "numero": 6, "data": "2026-10-08"},
    ]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert "(CPF 529.982.247-25)" in t
    assert '• 3ª orientação pelo desvio "DESVIO A" em 08/10/2026' in t
    assert '• 6ª orientação pelo desvio "DESVIO B" em 08/10/2026' in t
    assert t.endswith("\n\nRelato:\n")
