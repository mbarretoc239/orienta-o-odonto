import json

import pandas as pd
import pytest

from core import graficos


@pytest.fixture
def capturado(monkeypatch):
    """Intercepta o que seria desenhado, para validar a especificacao do grafico sem abrir o Streamlit."""
    pegos = []
    monkeypatch.setattr(graficos, "_exibir", pegos.append)
    return pegos


def spec(grafico) -> str:
    return json.dumps(grafico.to_dict())  # to_dict valida o grafico contra o esquema do Vega-Lite


MESES = pd.DataFrame({"mes": ["2026-06", "2026-07", "2026-08"], "orientacoes": [3, 8, 5]})
DESVIOS = pd.DataFrame({"desvio": ["FALTA DATA", "RASURA", "MALOTE"], "orientacoes": [9, 4, 2]})
CALOR = pd.DataFrame({"desvio": ["A", "A", "B"], "mes": ["2026-06", "2026-07", "2026-07"], "orientacoes": [2, 5, 1]})
PEND = pd.DataFrame({"usuario": ["ana", "bia"], "forms": [1, 0], "contato_direto": [0, 2]})


def test_rotulo_de_mes():
    assert graficos.rotulo_mes("2026-06") == "jun/26" and graficos.rotulo_mes("2025-12") == "dez/25"


@pytest.mark.parametrize("escuro", [False, True])
def test_todos_os_graficos_sao_validos_e_usam_a_paleta_do_tema(capturado, monkeypatch, escuro):
    t = graficos.ESCURO if escuro else graficos.CLARO
    monkeypatch.setattr(graficos, "tema", lambda: t)
    graficos.colunas_por_mes(MESES)
    graficos.barras_horizontais(DESVIOS, "desvio", "orientacoes", "Desvio")
    graficos.mapa_de_calor(CALOR)
    graficos.pendencias_empilhadas(PEND)
    assert len(capturado) == 4
    textos = [spec(g) for g in capturado]
    assert t["series"][0] in textos[0] and t["series"][0] in textos[1]  # uma serie: cor 1
    assert all(c in textos[3] for c in t["series"][:2])  # as 2 series empilhadas (FORMS e contato direto)
    assert all(c in textos[2] for c in (t["sequencial"][0], t["sequencial"][-1]))  # rampa de uma cor so
    assert all(t["superficie"] in textos[i] for i in (2, 3))  # 2px da cor da superficie entre as marcas


def test_barras_horizontais_ordenadas_do_maior_para_o_menor_e_sem_rampa_de_cor(capturado):
    graficos.barras_horizontais(DESVIOS.sample(frac=1, random_state=1), "desvio", "orientacoes", "Desvio")
    d = capturado[0].to_dict()
    ordem = d["layer"][0]["encoding"]["y"]["sort"]
    assert ordem == ["FALTA DATA", "RASURA", "MALOTE"]
    assert "color" not in d["layer"][0]["encoding"]  # categorias sem ordem natural: nada de cor por valor


def test_paletas_tem_as_mesmas_chaves_e_series_distintas():
    assert set(graficos.CLARO) == set(graficos.ESCURO)
    assert len(set(graficos.CLARO["series"])) == 3 and len(set(graficos.ESCURO["series"])) == 3
    assert graficos.CLARO["series"] != graficos.ESCURO["series"]  # claro e escuro sao escolhidos, nao invertidos
