from io import BytesIO

import pandas as pd
import streamlit as st

from core import servico
from core.ui import db, desvios_ativos, erro_banco, exigir_login

st.set_page_config(page_title="Consultar orientações", layout="wide")
usuario = exigir_login()
st.title("Consultar orientações")

try:
    desvios = desvios_ativos()
    c1, c2, c3, c4 = st.columns(4)
    doc = c1.text_input("CNPJ/CPF")
    desvio = c2.selectbox("Desvio", desvios, format_func=lambda d: d["nome"], index=None, placeholder="Todos")
    ini = c3.date_input("De", value=None, format="DD/MM/YYYY")
    fim = c4.date_input("Até", value=None, format="DD/MM/YYYY")
    if st.button("Buscar", type="primary") or "consulta" not in st.session_state:
        st.session_state["consulta"] = servico.listar_orientacoes(
            db(), doc or None, desvio["id"] if desvio else None, ini, fim
        )
    df = pd.DataFrame(st.session_state["consulta"])
    st.caption(f"{len(df)} orientações")
    st.dataframe(df, width="stretch", hide_index=True)

    if not df.empty:
        buf = BytesIO()
        df.to_excel(buf, index=False)
        st.download_button("Exportar para Excel", buf.getvalue(), "orientacoes.xlsx")

    if usuario["perfil"] in servico.PODE_EDITAR and not df.empty:
        with st.expander("Excluir orientação (gestor/admin)"):
            oid = st.number_input("ID da orientação", min_value=1, step=1)
            if st.button("Excluir"):
                ok, msg = servico.excluir_orientacao(db(), usuario, int(oid))
                (st.success if ok else st.error)(msg)
                if ok:
                    st.session_state.pop("consulta", None)
except Exception as e:  # noqa: BLE001
    erro_banco(e)
