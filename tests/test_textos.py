from core.textos import relato_forms
from tests.conftest import CNPJ_OK, CPF_OK


def item(desvio, numero=3, data="2026-10-08", orientacao=None):
    return {"desvio": desvio, "numero": numero, "data": data, "orientacao": orientacao}


def test_relato_de_um_desvio_em_texto_corrido():
    t = relato_forms("CLINICA TESTE", CNPJ_OK, [item("FALTA DATA DO ATENDIMENTO", orientacao="preencher a data")])
    assert t == ('Prestador CLINICA TESTE (CNPJ 11.222.333/0001-81) recebeu a 3ª orientação pelo desvio '
                 '"FALTA DATA DO ATENDIMENTO" em 08/10/2026. Orientar o prestador a preencher a data.')


def test_varios_desvios_na_mesma_data_citam_a_data_uma_vez_e_numeram_as_orientacoes():
    itens = [item("DESVIO A", 3, orientacao="colher as assinaturas"), item("DESVIO B", 6, orientacao="carimbar a guia")]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert t == ('Prestador MARIA (CPF 529.982.247-25) recebeu, em 08/10/2026, a 3ª orientação pelo desvio '
                 '"DESVIO A" e a 6ª orientação pelo desvio "DESVIO B". '
                 'Orientar o prestador a: (1) colher as assinaturas; (2) carimbar a guia.')


def test_datas_diferentes_e_tres_desvios():
    itens = [item("A", 3, "2026-10-08"), item("B", 6, "2026-10-09"), item("C", 9, "2026-10-10")]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert ('recebeu a 3ª orientação pelo desvio "A" em 08/10/2026, a 6ª orientação pelo desvio "B" em '
            '09/10/2026 e a 9ª orientação pelo desvio "C" em 10/10/2026.') in t


def test_orientacoes_repetidas_aparecem_uma_vez_e_ponto_final_duplicado_e_evitado():
    itens = [item("A", orientacao="usar o sistema."), item("B", orientacao="usar o sistema"),
             item("C", orientacao="  ")]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert t.endswith("Orientar o prestador a usar o sistema.") and "(1)" not in t and ".." not in t


def test_sem_orientacao_cadastrada_o_texto_so_identifica():
    t = relato_forms("MARIA", CPF_OK, [item("A")])
    assert t.endswith('"A" em 08/10/2026.') and "Orientar" not in t


def test_texto_e_um_paragrafo_so_e_sem_a_frase_de_ciencia():
    itens = [item(f"D{n}", orientacao=f"fazer {n}") for n in range(4)]
    t = relato_forms("MARIA", CPF_OK, itens)
    assert "\n" not in t and "•" not in t and "ciência" not in t and "capa do processo" not in t
    assert "(4) fazer 3." in t
