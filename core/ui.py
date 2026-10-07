"""Helpers de interface: conexao, guarda de login/perfil e barra lateral."""
import streamlit as st

from core.db import TursoIndisponivelError, criar_schema, get_db


@st.cache_resource
def db():
    d = get_db()
    criar_schema(d)
    return d


@st.cache_data(ttl=300, show_spinner=False)
def desvios_ativos():
    return db().query("SELECT id, nome, texto_padrao FROM ori_desvios WHERE ativo=1 ORDER BY id")


def exigir_login(perfis=None):
    """Para a execucao da pagina se nao houver usuario logado com um dos perfis."""
    u = st.session_state.get("usuario")
    if not u:
        st.warning("Faça login na página inicial.")
        st.page_link("app.py", label="Ir para o login")
        st.stop()
    if perfis and u["perfil"] not in perfis:
        st.error("Você não tem permissão para acessar esta página.")
        st.stop()
    with st.sidebar:
        st.caption(f"{u['nome']} · {u['perfil']}")
        if st.button("Sair"):
            st.session_state.pop("usuario", None)
            st.rerun()
    return u


def erro_banco(e: Exception):
    if isinstance(e, TursoIndisponivelError):
        st.error("Banco indisponível no momento (limite do plano ou rede). Tente novamente em instantes.")
    else:
        st.error(f"Erro inesperado: {e}")
