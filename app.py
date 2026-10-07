import streamlit as st

from core import auth
from core.ui import db, encerrar_sessao, iniciar_sessao, restaurar_sessao

st.set_page_config(page_title="Orientações a Prestadores", layout="centered")
st.title("Orientações a Prestadores")

restaurar_sessao()
u = st.session_state.get("usuario")
if u:
    st.success(f"Olá, {u['nome']}. Use o menu à esquerda para registrar ou consultar orientações.")
    if st.button("Sair"):
        encerrar_sessao()
    st.stop()

entrar, cadastrar = st.tabs(["Entrar", "Primeiro acesso"])

with entrar:
    with st.form("login"):
        login = st.text_input("Usuário", help="Mesmo usuário do SIGO")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            usuario, msg = auth.autenticar(db(), login, senha)
            if usuario:
                iniciar_sessao(usuario)
            st.error(msg)

with cadastrar:
    st.caption("Seu cadastro precisa ser aprovado por um administrador antes do primeiro acesso.")
    with st.form("cadastro"):
        nome = st.text_input("Nome completo")
        login_c = st.text_input("Usuário", key="usuario_cadastro", help="Mesmo usuário do SIGO")
        st.caption("Mesmo usuário do SIGO")
        senha_c = st.text_input("Senha (mínimo 8 caracteres)", type="password", key="senha_cadastro")
        if st.form_submit_button("Solicitar acesso"):
            ok, msg = auth.registrar_usuario(db(), login_c, nome, senha_c)
            (st.success if ok else st.error)(msg)
