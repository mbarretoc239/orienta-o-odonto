from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from core import orientacoes
from core.ui import db, desvios_ativos, erro_banco, exigir_login

st.set_page_config(page_title="Consultar orientações", layout="wide")
usuario = exigir_login()
pode_editar = usuario["perfil"] in orientacoes.PODE_EDITAR
st.title("Consultar orientações")


@st.cache_data(ttl=60, show_spinner="Buscando...")
def buscar(doc, desvio_id, ini, fim):
    return orientacoes.listar(db(), doc, desvio_id, ini, fim)


@st.dialog("Editar orientação")
def editar(linha):
    st.caption(f"{linha['prestador']} · {linha['desvio']} · {linha['numero_orientacao']}ª orientação")
    data = st.date_input("Data da orientação", value=date.fromisoformat(linha["data_orientacao"]), format="DD/MM/YYYY")
    opcoes = ["—", "SIM", "NAO"]
    atual = linha["credenciamento_sinalizado"] or "—"
    sinal = st.radio("Credenciamento sinalizado?", opcoes, index=opcoes.index(atual), horizontal=True)
    obs = st.text_area("Observação", value=linha["observacao"] or "")
    if st.button("Salvar alterações", type="primary"):
        ok, msg = orientacoes.editar(db(), usuario, int(linha["id"]), data, None if sinal == "—" else sinal, obs)
        if ok:
            buscar.clear()
            st.rerun()
        st.error(msg)


@st.dialog("Excluir orientação")
def excluir(linha):
    st.warning(f"Excluir a {linha['numero_orientacao']}ª orientação de {linha['prestador']} "
               f"({linha['desvio']}, {linha['data_orientacao']})? As orientações seguintes deste prestador "
               "e desvio serão renumeradas.")
    if st.button("Excluir definitivamente", type="primary"):
        ok, msg = orientacoes.excluir(db(), usuario, int(linha["id"]))
        if ok:
            buscar.clear()
            st.rerun()
        st.error(msg)


try:
    c1, c2, c3, c4 = st.columns(4)
    doc = c1.text_input("CNPJ/CPF")
    desvio = c2.selectbox("Desvio", desvios_ativos(), format_func=lambda d: d["nome"], index=None, placeholder="Todos")
    ini = c3.date_input("De", value=None, format="DD/MM/YYYY")
    fim = c4.date_input("Até", value=None, format="DD/MM/YYYY")

    dados = buscar(doc or None, desvio["id"] if desvio else None, ini, fim)
    df = pd.DataFrame(dados)
    st.caption(f"{len(df)} orientações" + (f" (mostrando as {orientacoes.LIMITE_CONSULTA} mais recentes)"
                                           if len(df) >= orientacoes.LIMITE_CONSULTA else ""))
    if df.empty:
        st.stop()

    exibicao = df.drop(columns=["id"])
    evento = st.dataframe(exibicao, width="stretch", hide_index=True,
                          on_select="rerun" if pode_editar else "ignore", selection_mode="single-row")

    buf = BytesIO()
    exibicao.to_excel(buf, index=False)
    st.download_button("Exportar para Excel", buf.getvalue(), "orientacoes.xlsx")

    if pode_editar:
        sel = evento.selection.rows if evento else []
        st.caption("Selecione uma linha na tabela para editar ou excluir.")
        b1, b2, _ = st.columns([1, 1, 6])
        if b1.button("Editar", disabled=not sel):
            editar(df.iloc[sel[0]].to_dict())
        if b2.button("Excluir", disabled=not sel):
            excluir(df.iloc[sel[0]].to_dict())
except Exception as e:  # noqa: BLE001
    erro_banco(e)
