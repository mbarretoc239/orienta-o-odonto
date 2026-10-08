"""Preparo de dados para exportar ao Excel."""
import pandas as pd

_INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def blindar_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """Texto que comeca com = + - @ viraria formula ao abrir no Excel (ex.: uma observacao digitada como
    =HYPERLINK(...)). Prefixa uma aspa simples nesses textos, como o proprio Excel faz para forcar texto."""
    def seguro(valor):
        return "'" + valor if isinstance(valor, str) and valor.startswith(_INICIOS_DE_FORMULA) else valor

    copia = df.copy()
    for coluna in copia.columns:
        if copia[coluna].dtype == object or str(copia[coluna].dtype).startswith("str"):
            copia[coluna] = copia[coluna].map(seguro)
    return copia
