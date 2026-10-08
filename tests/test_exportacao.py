import pandas as pd

from core.exportacao import blindar_formulas


def test_texto_que_vira_formula_recebe_aspa_e_o_resto_fica_igual():
    df = pd.DataFrame({
        "observacao": ["=HYPERLINK(\"http://x\")", "+1+1", "-2", "@SOMA(A1)", "normal", None],
        "numero": [1, 2, 3, 4, 5, 6],
    })
    seguro = blindar_formulas(df)
    assert list(seguro["observacao"][:4]) == ["'=HYPERLINK(\"http://x\")", "'+1+1", "'-2", "'@SOMA(A1)"]
    assert seguro["observacao"][4] == "normal" and pd.isna(seguro["observacao"][5])
    assert list(seguro["numero"]) == [1, 2, 3, 4, 5, 6]
    assert df["observacao"][0].startswith("=")  # nao altera o original


def test_planilha_gravada_nao_tem_formula(tmp_path):
    caminho = tmp_path / "x.xlsx"
    blindar_formulas(pd.DataFrame({"obs": ["=1+1"]})).to_excel(caminho, index=False)
    import openpyxl

    celula = openpyxl.load_workbook(caminho).active["A2"]
    assert celula.data_type != "f" and celula.value == "'=1+1"
