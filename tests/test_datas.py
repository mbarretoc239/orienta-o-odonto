from datetime import date

from migracao import datas
from migracao.datas import ALTA, BAIXA, Linha

HOJE = date(2026, 10, 8)


def linhas_junho(trocada, extra=()):
    """Linhas 1-4 e 6-9 em junho/2026 (claras); a linha 5 e a ambigua."""
    base = [Linha(n, date(2026, 6, 14 + (n % 3)), False) for n in (1, 2, 3, 4, 6, 7, 8, 9)]
    return base + [Linha(5, trocada, True), *extra]


def test_e_ambigua_so_para_data_real_com_dia_ate_12():
    assert datas.e_ambigua(date(2026, 6, 12), veio_de_texto=False)
    assert not datas.e_ambigua(date(2026, 6, 15), veio_de_texto=False)  # dia > 12 nunca troca
    assert not datas.e_ambigua(date(2026, 6, 12), veio_de_texto=True)  # digitada como texto: dia e mes certos
    assert not datas.e_ambigua(date(2026, 6, 6), veio_de_texto=False)  # dia == mes: trocar nao muda nada


def test_data_no_futuro_e_trocada_com_confianca_alta():
    s = datas.resolver(linhas_junho(date(2026, 12, 6)), HOJE)[5]
    assert s.sugerida == date(2026, 6, 12) and s.confianca == ALTA


def test_vizinhas_decidem_quando_as_duas_leituras_sao_possiveis():
    s = datas.resolver(linhas_junho(date(2026, 3, 6)), HOJE)[5]  # 06/03 lido; vizinhas em junho -> 03/06
    assert s.sugerida == date(2026, 6, 3) and s.confianca == ALTA
    s = datas.resolver(linhas_junho(date(2026, 6, 3)), HOJE)[5]  # ja combina com as vizinhas: nao muda
    assert s.sugerida == date(2026, 6, 3)


def test_erro_de_ano_vai_para_revisao_sem_trocar():
    s = datas.resolver(linhas_junho(date(2025, 5, 12)), HOJE)[5]  # nenhuma leitura combina com junho/2026
    assert s.confianca == BAIXA and s.sugerida == date(2025, 5, 12)


def test_data_futura_que_destoa_das_vizinhas_vai_para_revisao():
    s = datas.resolver(linhas_junho(date(2026, 11, 2)), HOJE)[5]  # troca = 11/02, mas vizinhas estao em junho
    assert s.confianca == BAIXA


def test_linha_sem_data_usa_as_vizinhas():
    linhas = [Linha(n, date(2026, 6, 15), False) for n in (1, 2, 4, 5)] + [Linha(3, None, False)]
    s = datas.sugerir_sem_data(linhas, 3)
    assert s.sugerida == date(2026, 6, 15) and s.confianca == ALTA
