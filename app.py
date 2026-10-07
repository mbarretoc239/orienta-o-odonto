import streamlit as st

from core import auth
from core.ui import db

st.set_page_config(page_title="Orientações a Prestadores", layout="centered")
st.title("Orientações a Prestadores")

u = st.session_state.get("usuario")
if u:
    st.success(f"Olá, {u['nome']}. Use o menu à esquerda para registrar ou consultar orientações.")
    if st.button("Sair"):
        st.session_state.pop("usuario", None)
        st.rerun()
    st.stop()

entrar, cadastrar = st.tabs(["Entrar", "Primeiro acesso"])

with entrar:
    with st.form("login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            usuario, msg = auth.autenticar(db(), email, senha)
            if usuario:
                st.session_state["usuario"] = usuario
                st.rerun()
            st.error(msg)

with cadastrar:
    st.caption("Seu cadastro precisa ser aprovado por um administrador antes do primeiro acesso.")
    with st.form("cadastro"):
        nome = st.text_input("Nome completo")
        email_c = st.text_input("E-mail", key="email_cadastro")
        senha_c = st.text_input("Senha (mínimo 8 caracteres)", type="password", key="senha_cadastro")
        if st.form_submit_button("Solicitar acesso"):
            ok, msg = auth.registrar_usuario(db(), email_c, nome, senha_c)
            (st.success if ok else st.error)(msg)
