"""Leitura das planilhas de origem."""
import warnings

import pandas as pd

warnings.filterwarnings("ignore")


def ler_desvios(caminho):
    b = pd.read_excel(caminho, sheet_name="Base", header=None, dtype=str).iloc[1:, 1:3]
    b.columns = ["nome", "texto"]
    return b.dropna(subset=["nome"])


def ler_acompanhamento(caminho):
    a = pd.read_excel(caminho, sheet_name="Acompanhamento", dtype=str)
    a.columns = ["doc", "nome", "desvio", "data", "qtd", "acao", "sinal", "obs"]
    return a


def ler_base_oficial(caminho):
    """Aba 'PRESTADOR - CNPJ.CPF': fonte oficial do nome."""
    o = pd.read_excel(caminho, sheet_name="PRESTADOR - CNPJ.CPF", dtype=str)
    o.columns = ["nome", "doc", "cod"]
    return o


def ler_ficha_prestadores(caminho):
    """Aba 'prestadores': codigo, tipo, cidade, UF."""
    return pd.read_excel(caminho, sheet_name="prestadores", dtype=str)
