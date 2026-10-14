from core import planilha

ITEM = {"documento": "42076531000108", "prestador": "TISSATO ODONTOL LTDA", "desvio": "ENVIO DE RAIO X FÍSICO",
        "data": "2026-07-11", "numero": 5, "acao": None}


def test_linha_na_ordem_das_colunas_da_planilha():
    assert planilha.linha_da_planilha(ITEM, "SIM").split("\t") == [
        "42076531000108", "TISSATO ODONTOL LTDA", "ENVIO DE RAIO X FÍSICO", "11/07/2026", "5ª orientação", "", "SIM"]


def test_acao_e_sinalizacao_ficam_vazias_quando_nao_ha():
    assert planilha.linha_da_planilha(ITEM).endswith("5ª orientação\t\t")  # as 2 ultimas colunas em branco
    assert planilha.linha_da_planilha({**ITEM, "numero": 3, "acao": "FORMS"}, "NAO").endswith("3ª orientação\tFORMS\tNAO")


def test_varios_desvios_viram_varias_linhas_e_nada_quebra_a_colagem():
    itens = [{**ITEM, "desvio": "A\tB"}, {**ITEM, "prestador": "X\nY"}]
    linhas = planilha.linhas_da_planilha(itens).split("\n")
    assert len(linhas) == 2 and all(len(l.split("\t")) == 7 for l in linhas)
    assert "A B" in linhas[0] and "X Y" in linhas[1]


def test_linha_a_partir_da_consulta_do_historico():
    linha = {"id": 9, "documento": "42076531000108", "prestador": "TISSATO ODONTOL LTDA", "desvio": "MALOTE",
             "data_orientacao": "2026-07-11", "numero_orientacao": 6, "acao": "FORMS", "credenciamento_sinalizado": "SIM"}
    texto = planilha.linha_da_planilha(planilha.item_da_consulta(linha), linha["credenciamento_sinalizado"])
    assert texto == "42076531000108\tTISSATO ODONTOL LTDA\tMALOTE\t11/07/2026\t6ª orientação\tFORMS\tSIM"
