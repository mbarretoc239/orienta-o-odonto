"""Helpers de interface: conexao, sessao persistente, guarda de login/perfil e barra lateral."""
import json

import streamlit as st

from core import auth, sessao, textos
from core.db import BancoNaoConfiguradoError, TursoIndisponivelError, criar_schema, get_db


@st.cache_resource
def _banco():
    d = get_db()
    criar_schema(d)
    textos.preencher_estrutura(d)
    return d


def db():
    try:
        return _banco()
    except BancoNaoConfiguradoError as e:
        st.error(str(e))
        st.stop()


def _cookies_do_navegador():
    """Cookies lidos NO NAVEGADOR por um componente. None enquanto o navegador nao respondeu; depois um dict.
    No Streamlit Cloud o servidor nao recebe cookies (st.context.cookies vem vazio), entao a leitura tem de
    ser feita pelo navegador."""
    from streamlit_cookies_controller.cookie_controller import _cookie_controller

    cookies = _cookie_controller(method="getAll", key="ori_cookies_navegador", default=None)
    st.session_state["_cookies_navegador"] = cookies  # copia para o diagnostico (a chave do componente e dele)
    return cookies


def restaurar_sessao():
    """Se a pessoa recarregou a pagina, recupera o login a partir do cookie (valido por 8h).
    A primeira execucao depois do F5 espera o navegador informar os cookies; o componente dispara a
    reexecucao assim que responde."""
    if st.session_state.get("usuario"):
        return
    cookies = _cookies_do_navegador()
    if cookies is None:
        st.caption("Carregando sessão…")
        st.stop()
    token = cookies.get(sessao.COOKIE)
    nome = sessao.usuario_da_sessao(db(), token)
    usuario = auth.dados_usuario(db(), nome) if nome else None
    if usuario:
        st.session_state["usuario"] = usuario
        st.session_state["token_sessao"] = token


def _gravar_cookie(token: str, max_age: int):
    """Grava o cookie direto na pagina (sem componente nem espera). Chamar sem st.rerun() logo em seguida,
    para o navegador executar o script antes de a pagina ser redesenhada.

    Em https (Streamlit Cloud) o app roda dentro de um iframe, onde o navegador pode tratar o cookie como de
    terceiros: por isso SameSite=None; Secure; Partitioned, com recuo para Lax se for recusado."""
    nome, valor, idade = json.dumps(sessao.COOKIE), json.dumps(token), int(max_age)
    st.html(f"""<script>(function () {{
  var nome = {nome}, valor = {valor}, base = '; path=/; max-age={idade}';
  if (location.protocol === 'https:') {{
    document.cookie = nome + '=' + valor + base + '; SameSite=None; Secure; Partitioned';
    if ({idade} > 0 && document.cookie.indexOf(nome + '=') === -1) {{
      document.cookie = nome + '=' + valor + base + '; SameSite=Lax; Secure';
    }}
    if ({idade} === 0) document.cookie = nome + '=' + base + '; SameSite=Lax; Secure';
  }} else {{
    document.cookie = nome + '=' + valor + base + '; SameSite=Lax';
  }}
}})();</script>""", unsafe_allow_javascript=True)


def diagnostico_sessao():
    """Abra o app com ?diag=1 para ver onde a sessao se perde depois do F5 (nao mostra o token)."""
    if not st.query_params.get("diag"):
        return
    navegador = st.session_state.get("_cookies_navegador")  # lidos pelo componente (None se ja estava logado)
    token = (navegador or {}).get(sessao.COOKIE)
    with st.expander("Diagnóstico de sessão", expanded=True):
        st.write({
            "cookies que o servidor recebeu": sorted(st.context.cookies.keys()),
            "cookies lidos no navegador (componente)": None if navegador is None else sorted(navegador.keys()),
            "cookie ori_sessao existe no navegador": bool(token),
            "sessao valida no banco": bool(sessao.usuario_da_sessao(db(), token)),
            "usuario na sessao do Streamlit": (st.session_state.get("usuario") or {}).get("usuario"),
            "host": st.context.headers.get("Host"),
            "origem": st.context.headers.get("Origin"),
        })
    st.html("""<script>(function () {
  var d = document.createElement('pre');
  var topo = ''; try { topo = window.top.location.host; } catch (e) { topo = '(outro site)'; }
  d.textContent = 'No navegador -> em iframe: ' + (window.top !== window.self) + ' | https: ' +
    (location.protocol === 'https:') + ' | cookie ori_sessao visivel: ' +
    (document.cookie.indexOf('ori_sessao=') !== -1) + ' | pagina de cima: ' + topo;
  document.body.appendChild(d);
})();</script>""", unsafe_allow_javascript=True)


def iniciar_sessao(usuario: dict):
    """Cria a sessao (8h). O cookie e gravado por aplicar_cookie_pendente(), chamado fora de qualquer
    container que a pagina esvazie (senao o navegador descarta o script antes de executar)."""
    token = sessao.criar(db(), usuario["usuario"])
    st.session_state["usuario"] = usuario
    st.session_state["token_sessao"] = token
    st.session_state["cookie_pendente"] = token


def aplicar_cookie_pendente():
    token = st.session_state.pop("cookie_pendente", None)
    if token:
        _gravar_cookie(token, sessao.DURACAO_H * 3600)


def encerrar_sessao():
    token = st.session_state.pop("token_sessao", None)
    sessao.encerrar(db(), token)  # o token deixa de valer no banco, mesmo que o cookie fique no navegador
    st.session_state.pop("usuario", None)
    _gravar_cookie("", 0)
    st.success("Sessão encerrada.")
    st.page_link("app.py", label="Entrar novamente")
    st.stop()


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
