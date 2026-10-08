import streamlit as st

from core import auth, marca
from core.ui import (
    aplicar_cookie_pendente,
    barra_lateral,
    db,
    diagnostico_sessao,
    encerrar_sessao,
    iniciar_sessao,
    mostrar_segredo,
    restaurar_sessao,
)

st.set_page_config(page_title="Orientações a Prestadores", layout="centered", page_icon=marca.ICONE)
marca.aplicar()
st.title("Orientações a Prestadores")

AVISO_CODIGO = ("Guarde este código em local seguro. Ele é a única forma de redefinir sua senha sem o "
                "administrador e não será mostrado novamente.")


def tela_logada():
    u = st.session_state["usuario"]
    corpo = st.empty()
    with corpo.container():
        if u.get("trocar_senha"):
            st.warning("Sua senha foi redefinida pelo administrador. Defina uma nova senha para continuar.")
            with st.form("trocar_senha"):
                atual = st.text_input("Senha temporária", type="password")
                nova = st.text_input("Nova senha (mínimo 8 caracteres)", type="password")
                if st.form_submit_button("Salvar nova senha", type="primary"):
                    ok, msg, codigo = auth.trocar_senha(db(), u["usuario"], atual, nova)
                    if ok:
                        st.session_state["usuario"] = {**u, "trocar_senha": False}
                        if codigo:
                            st.session_state["codigo_novo"] = codigo
                        st.rerun()
                    st.error(msg)
        else:
            mostrar_segredo("codigo_novo", "Seu código de recuperação", AVISO_CODIGO)
            st.success(f"Olá, {u['nome']}. Use o menu à esquerda para registrar ou consultar orientações.")
    if u.get("trocar_senha"):  # sem menu enquanto a senha temporaria nao for trocada
        if st.button("Sair"):
            corpo.empty()
            encerrar_sessao()
    else:
        barra_lateral(u)


def tela_login():
    mostrar_segredo("codigo_novo", "Seu código de recuperação", AVISO_CODIGO)
    entrar, cadastrar, esqueci = st.tabs(["Entrar", "Primeiro acesso", "Esqueci minha senha"])

    with entrar:
        with st.form("login"):
            login = st.text_input("Usuário", help="Mesmo usuário do SIGO")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                usuario, msg = auth.autenticar(db(), login, senha)
                if usuario:
                    iniciar_sessao(usuario)
                    return
                st.error(msg)

    with cadastrar:
        st.caption("Seu cadastro precisa ser aprovado por um administrador antes do primeiro acesso.")
        with st.form("cadastro"):
            nome = st.text_input("Nome completo")
            login_c = st.text_input("Usuário", key="usuario_cadastro", help="Mesmo usuário do SIGO")
            st.caption("Mesmo usuário do SIGO")
            senha_c = st.text_input("Senha (mínimo 8 caracteres)", type="password", key="senha_cadastro")
            if st.form_submit_button("Solicitar acesso"):
                ok, msg, codigo = auth.registrar_usuario(db(), login_c, nome, senha_c)
                if ok:
                    st.session_state["codigo_novo"] = codigo
                    st.rerun()
                st.error(msg)

    with esqueci:
        st.caption("Use o código de recuperação que você recebeu no cadastro. "
                   "Se o perdeu, peça ao administrador uma senha temporária.")
        with st.form("esqueci"):
            login_e = st.text_input("Usuário", key="usuario_esqueci")
            codigo_e = st.text_input("Código de recuperação", placeholder="XXXX-XXXX-XXXX")
            nova_e = st.text_input("Nova senha (mínimo 8 caracteres)", type="password", key="senha_esqueci")
            if st.form_submit_button("Redefinir senha"):
                ok, msg, novo = auth.redefinir_com_codigo(db(), login_e, codigo_e, nova_e)
                if ok:
                    st.session_state["codigo_novo"] = novo
                    st.rerun()
                st.error(msg)


restaurar_sessao()
diagnostico_sessao()
if st.session_state.get("usuario"):
    tela_logada()
    st.stop()

caixa = st.empty()
with caixa.container():
    tela_login()
if st.session_state.get("usuario"):  # acabou de entrar: mostra a tela logada sem recarregar a pagina
    caixa.empty()
    aplicar_cookie_pendente()
    tela_logada()
