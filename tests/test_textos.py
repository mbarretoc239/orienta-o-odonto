from core.textos import FRASE_CIENCIA, relato_forms
from tests.conftest import CNPJ_OK, CPF_OK

CIENCIA = ("As devidas orientações foram feitas na capa do processo e feito este forms para ciência do "
           "credenciamento.")


def test_frase_de_ciencia_e_a_aprovada():
    assert FRASE_CIENCIA == CIENCIA


def test_relato_de_um_desvio_em_texto_corrido():
    t = relato_forms("CLINICA TESTE", CNPJ_OK, [{"desvio": "FALTA DATA DO ATENDIMENTO", "numero": 3, "data": "2026-10-08"}])
    assert t == (
        'Prestador CLINICA TESTE (CNPJ 11.222.333/0001-81) recebeu a 3ª orientação pelo desvio '
        f'"FALTA DATA DO ATENDIMENTO" em 08/10/2026. {CIENCIA}')


def test_relato_de_varios_desvios_na_mesma_data_cita_a_data_uma_vez():
    itens = [
        {"desvio": "DESVIO A", "numero": 3, "data": "2026-10-08"},
        {"desvio": "DESVIO B", "numero": 6, "data": "2026-10-08"},
    ]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert t == ('Prestador MARIA (CPF 529.982.247-25) recebeu, em 08/10/2026, a 3ª orientação pelo desvio '
                 f'"DESVIO A" e a 6ª orientação pelo desvio "DESVIO B". {CIENCIA}')


def test_relato_com_datas_diferentes_e_tres_desvios():
    itens = [
        {"desvio": "A", "numero": 3, "data": "2026-10-08"},
        {"desvio": "B", "numero": 6, "data": "2026-10-09"},
        {"desvio": "C", "numero": 9, "data": "2026-10-10"},
    ]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert ('recebeu a 3ª orientação pelo desvio "A" em 08/10/2026, a 6ª orientação pelo desvio "B" em '
            f'09/10/2026 e a 9ª orientação pelo desvio "C" em 10/10/2026. {CIENCIA}') in t


def test_relato_e_um_paragrafo_so_e_termina_na_frase_de_ciencia():
    itens = [{"desvio": f"D{n}", "numero": 3, "data": "2026-10-08"} for n in range(4)]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert "\n" not in t and "•" not in t
    assert t.endswith(CIENCIA) and "Relato" not in t and "encaminhamento" not in t
