from datetime import date

import streamlit as st

from core import orientacoes, prestadores
from core.config import url_forms
from core.regras import formatar_documento, normalizar_documento
from core.ui import db, desvios_ativos, erro_banco, exigir_login

st.set_page_config(page_title="Registrar orientação", layout="centered")
usuario = exigir_login()
st.title("Registrar orientação")


@st.cache_data(ttl=120, show_spinner=False)
def prestador_por_documento(doc):
    return prestadores.buscar(db(), doc)


def botao_forms(chave):
    """Atalho para o formulario do FORMS (link guardado nos secrets, nao no repositorio publico)."""
    link = url_forms()
    if link:
        st.link_button("Abrir formulário do FORMS", link, key=chave)
    else:
        st.caption("Link do FORMS não configurado (FORMS_URL nos secrets).")


def texto_contato_direto(numero):
    return f"Prestador já conta com {numero} orientações. Direcionar para contato direto por parte do credenciamento."


@st.dialog("Confirmar registro")
def confirmar(prestador, desvio, previa, data, sinal, obs):
    st.markdown(f"**{prestador['nome']}**  \n{formatar_documento(prestador['documento'])}")
    st.write(f"{desvio['nome']} · {previa['rotulo']} · {data.strftime('%d/%m/%Y')}"
             + (f" · **AÇÃO: {previa['acao']}**" if previa["acao"] else ""))
    if previa["contato_direto"]:
        st.error(texto_contato_direto(previa["numero"]))
    if st.button("Confirmar e registrar", type="primary"):
        reg, msg = orientacoes.registrar(db(), usuario, prestador["documento"], desvio["id"], data, sinal, obs)
        if not reg:
            st.error(msg)
            return
        st.session_state["ultimo_registro"] = {
            "numero": reg["numero_orientacao"], "acao": reg["acao"], "texto": desvio["texto_padrao"],
        }
        st.rerun()


if st.session_state.get("ultimo_registro"):
    r = st.session_state.pop("ultimo_registro")
    st.success(f"{r['numero']}ª orientação registrada" + (f" · AÇÃO: {r['acao']}" if r["acao"] else "") + ".")
    st.caption("Texto padrão para enviar ao prestador (use o ícone de copiar):")
    st.code(r["texto"], language=None, wrap_lines=True)
    if r["acao"] == "FORMS":
        botao_forms("forms_pos_registro")

try:
    doc_txt = st.text_input("CNPJ/CPF do prestador", placeholder="Somente números ou com pontuação")
    doc = normalizar_documento(doc_txt)
    prestador = prestador_por_documento(doc) if doc else None

    if doc and not prestador:
        if usuario["perfil"] not in prestadores.PODE_CADASTRAR:
            st.error(prestadores.MSG_NAO_CADASTRADO)
        else:
            st.info("Documento não encontrado. Cadastre o prestador para continuar.")
            nome_novo = st.text_input("Nome do prestador")
            if st.button("Cadastrar prestador"):
                ok, msg = prestadores.cadastrar(db(), usuario, doc, nome_novo)
                if ok:
                    prestador_por_documento.clear()
                    st.rerun()
                st.error(msg)
    elif prestador:
        st.markdown(f"**{prestador['nome']}**  \n{formatar_documento(doc)}")
        desvio = st.selectbox("Desvio", desvios_ativos(), format_func=lambda d: d["nome"],
                              index=None, placeholder="Escolha o desvio")
        if desvio:
            previa = orientacoes.previa(db(), doc, desvio["id"])
            c1, c2 = st.columns(2)
            c1.metric("Orientação", previa["rotulo"])
            c2.metric("Ação", previa["acao"] or "—")
            if previa["contato_direto"]:
                st.error(texto_contato_direto(previa["numero"]))
            elif previa["acao"] == "FORMS":
                st.info("Esta orientação exige o preenchimento do FORMS.")
                botao_forms("forms_previa")
            data = st.date_input("Data da orientação", value=date.today(), format="DD/MM/YYYY")
            sinal = st.radio("Credenciamento sinalizado?", ["—", "SIM", "NAO"], horizontal=True)
            obs = st.text_area("Observação (opcional)")
            if st.button("Salvar orientação", type="primary"):
                confirmar(prestador, desvio, previa, data, None if sinal == "—" else sinal, obs)
except Exception as e:  # noqa: BLE001
    erro_banco(e)
