"""Helpers de interface: conexao, sessao persistente, guarda de login/perfil e barra lateral."""
import json
import logging

import streamlit as st

from core import auth, logs, sessao, tarefas, textos, usuarios
from core.db import BancoNaoConfiguradoError, TursoIndisponivelError, criar_schema, get_db

LOG = logging.getLogger("orientacoes")


@st.cache_resource
def _banco():
    d = get_db()
    criar_schema(d)
    textos.preencher_estrutura(d)
    logs.limpar_antigos(d)
    tarefas.remover_pendencias_da_capa(d)
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


@st.cache_data(ttl=30, show_spinner=False)
def _usuario_no_banco(login: str):
    return auth.dados_usuario(db(), login)


def revalidar_usuario():
    """Mantem a sessao em dia com o banco (com no maximo 30s de atraso): quem for desativado perde o acesso e
    mudanca de perfil vale na hora, sem esperar a pessoa sair e entrar de novo."""
    u = st.session_state.get("usuario")
    if not u:
        return
    atual = _usuario_no_banco(u["usuario"])
    if atual is None:  # desativado, removido ou pendente
        sessao.encerrar(db(), st.session_state.pop("token_sessao", None))
        st.session_state.pop("usuario", None)
        _gravar_cookie("", 0)
        st.error("Seu acesso foi desativado. Procure o administrador.")
        st.stop()
    if atual["perfil"] != u["perfil"]:
        st.session_state["usuario"] = {**u, "perfil": atual["perfil"]}


def restaurar_sessao():
    """Se a pessoa recarregou a pagina, recupera o login a partir do cookie (valido por 8h).
    A primeira execucao depois do F5 espera o navegador informar os cookies; o componente dispara a
    reexecucao assim que responde."""
    if st.session_state.get("usuario"):
        revalidar_usuario()
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
    """Abra o app com ?diag=1 para ver onde a sessao se perde depois do F5 (nao mostra o token).
    So aparece para o admin."""
    u = st.session_state.get("usuario") or {}
    if not st.query_params.get("diag") or u.get("perfil") != "admin":
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
        logs.registrar(db(), "aviso", "acesso_negado", f"perfil {u['perfil']} tentou uma pagina restrita a {perfis}",
                       u["usuario"])
        st.error("Você não tem permissão para acessar esta página.")
        st.stop()
    with st.sidebar:
        st.caption(f"{u['nome']} · {u['perfil']}")
        _avisos_da_barra_lateral(u)
        if st.button("Sair"):
            encerrar_sessao()
    return u


def link_pagina(pagina: str, rotulo: str):
    try:
        st.page_link(pagina, label=rotulo)
    except Exception:  # noqa: BLE001 - fora do app multipagina (testes) o link nao existe: mostra so o texto
        st.caption(rotulo)


@st.cache_data(ttl=30, show_spinner=False)
def _contagens(login: str, e_admin: bool):
    return {"pendencias": tarefas.contagem(db(), login),
            "cadastros": usuarios.contar_pendentes(db()) if e_admin else 0}


def limpar_contagens():
    """Chamar depois de registrar, concluir pendencia ou aprovar cadastro: o numero da barra lateral atualiza."""
    _contagens.clear()


def _avisos_da_barra_lateral(u: dict):
    n = _contagens(u["usuario"], u["perfil"] == "admin")
    link_pagina("pages/2_Pendencias.py",
                f"Minhas pendências ({n['pendencias']})" if n["pendencias"] else "Minhas pendências")
    if n["cadastros"]:
        link_pagina("pages/6_Admin.py", f"⚠ {n['cadastros']} cadastro(s) aguardando aprovação")


@st.cache_data(ttl=300, show_spinner=False)
def desvios_ativos():
    from core import desvios

    return desvios.listar(db())


@st.cache_data(ttl=60, show_spinner="Buscando...")
def consulta_orientacoes(documento, desvio_id, data_ini, data_fim, registrado_por=None):
    """Cache da consulta; quem registra, edita ou exclui uma orientacao chama consulta_orientacoes.clear()."""
    from core import orientacoes

    return orientacoes.listar(db(), documento, desvio_id, data_ini, data_fim, registrado_por)


def erro_banco(e: Exception, pagina: str | None = None):
    """Mostra uma mensagem simples para a pessoa. O detalhe tecnico vai para o log do servidor e para a aba
    Logs da Administracao (que sobrevive a reinicios)."""
    usuario = (st.session_state.get("usuario") or {}).get("usuario")
    try:
        banco = _banco()
    except Exception:  # noqa: BLE001 - sem banco nao ha onde gravar
        banco = None
    if isinstance(e, TursoIndisponivelError):
        LOG.warning("Banco indisponivel: %s", e)
        st.error("Banco indisponível no momento (limite do plano ou rede). Tente novamente em instantes.")
    else:
        LOG.error("Erro inesperado na pagina", exc_info=e)
        if banco:
            logs.registrar_excecao(banco, e, usuario, pagina)
        st.error("Ocorreu um erro inesperado. Tente novamente e, se continuar, avise o administrador.")
