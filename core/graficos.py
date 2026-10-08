"""Graficos do painel (Altair), seguindo o metodo de dataviz: uma cor por trabalho, marcas finas, grade discreta,
claro e escuro escolhidos (nao invertidos) e cada grafico com a sua tabela ao lado.

Paleta validada com o validador da skill de dataviz (3 series, claro e escuro: todas as verificacoes passam; o
verde-agua no claro fica abaixo de 3:1 de contraste, por isso toda serie tem legenda visivel e tabela).
"""
import altair as alt
import pandas as pd
import streamlit as st

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CLARO = {
    "texto": "#0b0b0b", "texto2": "#52514e", "mudo": "#898781", "grade": "#e1e0d9", "base": "#c3c2b7",
    "superficie": "#ffffff", "series": ["#2a78d6", "#eb6834", "#1baf7a"],
    # sequencial azul: o valor mais baixo (quase zero) recua para a superficie
    "sequencial": ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
}
ESCURO = {
    "texto": "#ffffff", "texto2": "#c3c2b7", "mudo": "#898781", "grade": "#2c2c2a", "base": "#383835",
    "superficie": "#0e1117", "series": ["#3987e5", "#d95926", "#199e70"],
    "sequencial": ["#0d366b", "#184f95", "#256abf", "#6da7ec", "#b7d3f6"],
}


def tema() -> dict:
    try:
        return ESCURO if st.context.theme.type == "dark" else CLARO
    except Exception:  # noqa: BLE001 - fora do Streamlit, ou versao sem st.context.theme
        return CLARO


def rotulo_mes(ano_mes: str) -> str:
    """'2026-06' -> 'jun/26'."""
    return f"{_MESES[int(ano_mes[5:7]) - 1]}/{ano_mes[2:4]}"


def _estilo(grafico, t: dict, altura: int):
    return (
        grafico.properties(height=altura, width="container", background="transparent")
        .configure_view(stroke=None)
        .configure_axis(
            grid=True, gridColor=t["grade"], gridWidth=1, domainColor=t["base"], tickColor=t["base"],
            labelColor=t["mudo"], titleColor=t["texto2"], labelFontSize=12, titleFontSize=12,
            labelFont="system-ui, Segoe UI, sans-serif", titleFont="system-ui, Segoe UI, sans-serif",
        )
        .configure_legend(labelColor=t["texto2"], titleColor=t["texto2"], labelFontSize=12, symbolType="square",
                          orient="top", title=None)
    )


def _exibir(grafico):
    st.altair_chart(grafico, theme=None, width="stretch")


def colunas_por_mes(df: pd.DataFrame):
    """Tendencia no tempo, uma serie: colunas finas na cor 1; o rotulo so no ultimo mes."""
    t = tema()
    d = df.assign(mes_rotulo=df["mes"].map(rotulo_mes))
    ordem = list(d["mes_rotulo"])
    base = alt.Chart(d).encode(x=alt.X("mes_rotulo:N", sort=ordem, title=None, axis=alt.Axis(labelAngle=0, grid=False)))
    barras = base.mark_bar(size=22, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=t["series"][0]).encode(
        y=alt.Y("orientacoes:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        tooltip=[alt.Tooltip("mes_rotulo:N", title="Mês"), alt.Tooltip("orientacoes:Q", title="Orientações")])
    rotulo = base.mark_text(dy=-8, color=t["texto"], fontSize=12, fontWeight="bold").encode(
        y="orientacoes:Q", text="orientacoes:Q").transform_filter(alt.datum.mes_rotulo == ordem[-1])
    _exibir(_estilo(barras + rotulo, t, 260))


def barras_horizontais(df: pd.DataFrame, categoria: str, valor: str, titulo_categoria: str):
    """Comparar magnitude entre categorias sem ordem natural: uma cor so (nada de rampa por valor).
    Ordenado do maior para o menor; o valor so no maior, o resto no tooltip e na tabela."""
    t = tema()
    d = df.sort_values(valor, ascending=False)
    ordem = list(d[categoria])
    base = alt.Chart(d).encode(y=alt.Y(f"{categoria}:N", sort=ordem, title=None, axis=alt.Axis(grid=False, labelLimit=320)))
    barras = base.mark_bar(size=16, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=t["series"][0]).encode(
        x=alt.X(f"{valor}:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        tooltip=[alt.Tooltip(f"{categoria}:N", title=titulo_categoria), alt.Tooltip(f"{valor}:Q", title="Orientações")])
    rotulo = base.mark_text(align="left", dx=6, color=t["texto"], fontSize=12, fontWeight="bold").encode(
        x=f"{valor}:Q", text=f"{valor}:Q").transform_filter(alt.datum[categoria] == ordem[0])
    _exibir(_estilo(barras + rotulo, t, max(120, 30 * len(d) + 30)))


def mapa_de_calor(df: pd.DataFrame):
    """Desvio x mes: grade de magnitude, uma cor (azul), do claro (pouco) ao escuro (muito)."""
    t = tema()
    d = df.assign(mes_rotulo=df["mes"].map(rotulo_mes))
    ordem_meses = list(dict.fromkeys(d.sort_values("mes")["mes_rotulo"]))
    celulas = alt.Chart(d).mark_rect(stroke=t["superficie"], strokeWidth=2, cornerRadius=3).encode(
        x=alt.X("mes_rotulo:N", sort=ordem_meses, title=None, axis=alt.Axis(labelAngle=0, grid=False, orient="top")),
        y=alt.Y("desvio:N", title=None, axis=alt.Axis(grid=False, labelLimit=320)),
        color=alt.Color("orientacoes:Q", title="Orientações", scale=alt.Scale(range=t["sequencial"], zero=True),
                        legend=alt.Legend(orient="right", gradientLength=120)),
        tooltip=[alt.Tooltip("desvio:N", title="Desvio"), alt.Tooltip("mes_rotulo:N", title="Mês"),
                 alt.Tooltip("orientacoes:Q", title="Orientações")])
    _exibir(_estilo(celulas, t, max(160, 34 * d["desvio"].nunique() + 40)))


def pendencias_empilhadas(df: pd.DataFrame):
    """Partes de um todo por usuario: barras horizontais empilhadas, 2 series (slots 1 e 2, em ordem fixa),
    2px da cor da superficie entre os segmentos."""
    t = tema()
    nomes = {"forms": "FORMS", "contato_direto": "Contato direto"}
    longo = df.melt(id_vars="usuario", value_vars=list(nomes), var_name="tipo", value_name="pendencias")
    longo["tipo"] = longo["tipo"].map(nomes)
    longo = longo[longo["pendencias"] > 0]
    ordem_usuarios = list(df.assign(total=df[list(nomes)].sum(axis=1)).sort_values("total", ascending=False)["usuario"])
    barras = alt.Chart(longo).mark_bar(size=16, stroke=t["superficie"], strokeWidth=2).encode(
        y=alt.Y("usuario:N", sort=ordem_usuarios, title=None, axis=alt.Axis(grid=False)),
        x=alt.X("sum(pendencias):Q", title=None, axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("tipo:N", scale=alt.Scale(domain=list(nomes.values()), range=t["series"])),
        order=alt.Order("tipo:N"),
        tooltip=[alt.Tooltip("usuario:N", title="Usuário"), alt.Tooltip("tipo:N", title="Pendência"),
                 alt.Tooltip("sum(pendencias):Q", title="Em aberto")])
    _exibir(_estilo(barras, t, max(120, 34 * len(ordem_usuarios) + 60)))
