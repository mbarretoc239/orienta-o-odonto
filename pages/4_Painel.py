from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

from core import graficos, marca, painel, tarefas
from core.exportacao import blindar_formulas
from core.ui import db, erro_banco, exigir_login

st.set_page_config(page_title="Painel gerencial", layout="wide", page_icon=marca.ICONE)
marca.aplicar()
usuario = exigir_login(perfis=("gestor", "admin"))
st.title("Painel gerencial")

PERIODOS = ["Últimos 90 dias", "Mês atual", "Ano atual", "Tudo", "Personalizado"]


def intervalo(escolha: str, hoje: date):
    if escolha == "Últimos 90 dias":
        return hoje - timedelta(days=90), hoje
    if escolha == "Mês atual":
        return hoje.replace(day=1), hoje
    if escolha == "Ano atual":
        return hoje.replace(month=1, day=1), hoje
    if escolha == "Tudo":
        return None, None
    c1, c2 = st.columns(2)
    ini = c1.date_input("De", value=hoje - timedelta(days=30), format="DD/MM/YYYY")
    fim = c2.date_input("Até", value=hoje, format="DD/MM/YYYY")
    return ini, fim


@st.cache_data(ttl=120, show_spinner="Calculando...")
def carregar(ini, fim):
    banco = db()
    return {
        "resumo": painel.resumo(banco, ini, fim),
        "mes": painel.por_mes(banco, ini, fim),
        "etapas": painel.por_mes_e_etapa(banco, ini, fim),
        "funil": painel.funil_de_reincidencia(banco),
        "desvio": painel.por_desvio(banco, ini, fim),
        "desvio_mes": painel.desvio_por_mes(banco, ini, fim),
        "usuario": painel.por_usuario(banco, ini, fim),
        "importadas": painel.importadas(banco, ini, fim),
        "pendencias": tarefas.resumo_por_usuario(banco),
        "conclusao": painel.tempo_medio_de_conclusao(banco),
    }


def com_tabela(titulo: str, df: pd.DataFrame, desenhar, nomes: dict | None = None):
    """Grafico + a mesma informacao em tabela (quem nao enxerga cores, ou prefere numeros, usa a tabela)."""
    st.subheader(titulo)
    if df.empty:
        st.caption("Sem dados no período.")
        return
    desenhar(df)
    with st.expander("Ver como tabela"):
        st.dataframe(df.rename(columns=nomes or {}), hide_index=True, width="stretch")


try:
    barra = st.container()
    with barra:
        c1, c2 = st.columns([2, 1])
        escolha = c1.selectbox("Período (pela data da orientação)", PERIODOS)
        c2.write("")
        if c2.button("Atualizar dados"):
            carregar.clear()
        ini, fim = intervalo(escolha, date.today())

    d = carregar(ini, fim)
    r = d["resumo"]
    if not r["orientacoes"]:
        st.info("Não há orientações no período escolhido.")
        st.stop()

    k = st.columns(6)
    k[0].metric("Orientações", r["orientacoes"])
    k[1].metric("Prestadores", r["prestadores"])
    k[2].metric("1ªs orientações", int(r["primeiras"]), help="Primeira orientação de um prestador em cada desvio.")
    k[3].metric("FORMS gerados", int(r["forms"]))
    k[4].metric("Contato direto", int(r["contato_direto"]))
    k[5].metric("Pendências abertas", r["pendencias_abertas"], help="Todas as pendências ainda não marcadas, "
                                                                     "independente do período.")

    df_mes = pd.DataFrame(d["mes"])
    df_etapas = pd.DataFrame(d["etapas"])
    df_funil = pd.DataFrame(d["funil"])
    df_desvio = pd.DataFrame(d["desvio"])
    df_usuario = pd.DataFrame(d["usuario"])
    df_calor = pd.DataFrame(d["desvio_mes"])
    df_pend = pd.DataFrame(d["pendencias"])

    esq, dir_ = st.columns(2)
    with esq:
        com_tabela("Orientações por mês", df_mes, graficos.colunas_por_mes,
                   {"mes": "Mês", "orientacoes": "Orientações"})
    with dir_:
        com_tabela("Orientações por desvio", df_desvio,
                   lambda df: graficos.barras_horizontais(df, "desvio", "orientacoes", "Desvio"),
                   {"desvio": "Desvio", "orientacoes": "Orientações"})

    esq, dir_ = st.columns(2)
    with esq:
        com_tabela("Orientações por mês, por etapa", df_etapas, graficos.etapas_por_mes,
                   {"mes": "Mês", "etapa": "Etapa", "orientacoes": "Orientações"})
    with dir_:
        com_tabela("Quantos casos chegaram a cada etapa", df_funil,
                   lambda df: graficos.barras_horizontais(df, "etapa", "casos", "Etapa", "Casos"),
                   {"etapa": "Chegaram a", "casos": "Casos"})
        st.caption("Caso = prestador + desvio (a contagem é por desvio). Considera todo o histórico, não só o período.")

    com_tabela("Desvios ao longo dos meses (quais crescem ou diminuem)", df_calor, graficos.mapa_de_calor,
               {"desvio": "Desvio", "mes": "Mês", "orientacoes": "Orientações"})

    esq, dir_ = st.columns(2)
    with esq:
        com_tabela("Quem registrou", df_usuario,
                   lambda df: graficos.barras_horizontais(df, "usuario", "orientacoes", "Usuário"),
                   {"usuario": "Usuário", "orientacoes": "Orientações", "ultimo_registro": "Último registro"})
        if d["importadas"]:
            st.caption(f"Não inclui {d['importadas']} orientação(ões) do histórico importado da planilha.")
    with dir_:
        com_tabela("Pendências em aberto, por usuário", df_pend, graficos.pendencias_empilhadas,
                   {"usuario": "Usuário", "forms": "FORMS", "contato_direto": "Contato direto",
                    "total": "Total", "mais_antiga": "Mais antiga desde"})

    st.subheader("Prestadores reincidentes")
    minimo = st.slider("Mostrar prestadores com pelo menos esta quantidade de orientações no mesmo desvio",
                       3, 12, 3)
    reinc = pd.DataFrame(painel.reincidentes(db(), minimo))
    if reinc.empty:
        st.caption("Nenhum prestador com tantas orientações no mesmo desvio.")
    else:
        st.dataframe(reinc.rename(columns={
            "documento": "CNPJ/CPF", "prestador": "Prestador", "desvio": "Desvio", "orientacoes": "Orientações",
            "ultima": "Última em", "proxima": "Próxima será", "acao_da_proxima": "Ação da próxima"}),
            hide_index=True, width="stretch")

    st.subheader("Tempo para concluir as pendências")
    if d["conclusao"]:
        df_conc = pd.DataFrame(d["conclusao"])
        df_conc["tipo"] = df_conc["tipo"].map(tarefas.TIPOS)
        st.dataframe(df_conc.rename(columns={"tipo": "Pendência", "concluidas": "Concluídas",
                                             "dias_em_media": "Dias, em média"}), hide_index=True, width="stretch")
    else:
        st.caption("Ainda não há pendências concluídas.")

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nome, tabela in (("Por mês", df_mes), ("Por mês e etapa", df_etapas), ("Chegaram a cada etapa", df_funil), ("Por desvio", df_desvio), ("Desvio x mês", df_calor),
                             ("Por usuário", df_usuario), ("Pendências", df_pend), ("Reincidentes", reinc)):
            if not tabela.empty:
                blindar_formulas(tabela).to_excel(w, sheet_name=nome, index=False)
    st.download_button("Baixar os números do painel (Excel)", buf.getvalue(), "painel_orientacoes.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
except Exception as e:  # noqa: BLE001
    erro_banco(e, "Painel")
