"""Helpers de interface: conexao, sessao persistente, guarda de login/perfil e barra lateral."""
import time

import streamlit as st

from core import auth, sessao
from core.db import BancoNaoConfiguradoError, TursoIndisponivelError, criar_schema, get_db


@st.cache_resource
def _banco():
    d = get_db()
    criar_schema(d)
    return d


def db():
    try:
        return _banco()
    except BancoNaoConfiguradoError as e:
        st.error(str(e))
        st.stop()


def restaurar_sessao():
    """Se a pessoa recarregou a pagina, recupera o login a partir do cookie (valido por 8h)."""
    if st.session_state.get("usuario"):
        return
    token = st.context.cookies.get(sessao.COOKIE)
    nome = sessao.usuario_da_sessao(db(), token)
    usuario = auth.dados_usuario(db(), nome) if nome else None
    if usuario:
        st.session_state["usuario"] = usuario
        st.session_state["token_sessao"] = token


def _cookies():
    from streamlit_cookies_controller import CookieController

    return CookieController()


def iniciar_sessao(usuario: dict):
    token = sessao.criar(db(), usuario["usuario"])
    st.session_state["usuario"] = usuario
    st.session_state["token_sessao"] = token
    _cookies().set(sessao.COOKIE, token, max_age=sessao.DURACAO_H * 3600, same_site="lax")
    time.sleep(1)  # deixa o navegador gravar o cookie antes do rerun
    st.rerun()


def encerrar_sessao():
    token = st.session_state.pop("token_sessao", None) or st.context.cookies.get(sessao.COOKIE)
    sessao.encerrar(db(), token)
    st.session_state.pop("usuario", None)
    _cookies().remove(sessao.COOKIE)
    time.sleep(1)
    st.rerun()


def mostrar_segredo(chave: str, titulo: str, aviso: str):
    """Exibe um segredo gerado (codigo/senha temporaria) ate a pessoa confirmar que guardou."""
    valor = st.session_state.get(chave)
    if not valor:
        return
    with st.container(border=True):
        st.markdown(f"**{titulo}**")
        st.code(valor, language=None)
        st.warning(aviso)
        if st.button("Já guardei", key=f"ok_{chave}"):
            st.session_state.pop(chave, None)
            st.rerun()


def exigir_login(perfis=None):
    """Para a execucao da pagina se nao houver usuario logado com um dos perfis."""
    restaurar_sessao()
    u = st.session_state.get("usuario")
    if not u:
        st.warning("Faça login na página inicial.")
        st.page_link("app.py", label="Ir para o login")
        st.stop()
    if u.get("trocar_senha"):
        st.warning("Defina uma nova senha antes de continuar.")
        st.page_link("app.py", label="Trocar senha")
        st.stop()
    if perfis and u["perfil"] not in perfis:
        st.error("Você não tem permissão para acessar esta página.")
        st.stop()
    with st.sidebar:
        st.caption(f"{u['nome']} · {u['perfil']}")
        if st.button("Sair"):
            encerrar_sessao()
    return u


@st.cache_data(ttl=300, show_spinner=False)
def desvios_ativos():
    from core import desvios

    return desvios.listar(db())


def erro_banco(e: Exception):
    if isinstance(e, TursoIndisponivelError):
        st.error("Banco indisponível no momento (limite do plano ou rede). Tente novamente em instantes.")
    else:
        st.error(f"Erro inesperado: {e}")
