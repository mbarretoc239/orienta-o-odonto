from datetime import date

import streamlit as st

from core import servico
from core.regras import (
    LIMITE_CONTATO_DIRETO,
    acao_para,
    exige_contato_direto,
    formatar_documento,
    normalizar_documento,
    rotulo_orientacao,
)
from core.ui import db, desvios_ativos, erro_banco, exigir_login

st.set_page_config(page_title="Registrar orientação", layout="centered")
usuario = exigir_login()
st.title("Registrar orientação")


@st.dialog("Contato direto com o prestador")
def aviso_contato_direto(numero):
    st.warning(
        f"Prestador já conta com {numero} orientações. "
        "Direcionar para contato direto por parte do credenciamento."
    )
    if st.button("Entendi"):
        st.rerun()


if st.session_state.get("ultimo_registro"):
    r = st.session_state.pop("ultimo_registro")
    st.success(f"{rotulo_orientacao(r['numero'])} registrada" + (" · AÇÃO: FORMS" if r["acao"] else "") + ".")
    st.caption("Texto padrão para enviar ao prestador (use o ícone de copiar):")
    st.code(r["texto"], language=None, wrap_lines=True)
    if exige_contato_direto(r["numero"]):
        aviso_contato_direto(r["numero"])

try:
    doc_txt = st.text_input("CNPJ/CPF do prestador", placeholder="Somente números ou com pontuação")
    doc = normalizar_documento(doc_txt)
    prestador = servico.buscar_prestador(db(), doc) if doc else None

    if doc and not prestador:
        st.info("Documento não encontrado. Cadastre o prestador para continuar.")
        nome_novo = st.text_input("Nome do prestador")
        if st.button("Cadastrar prestador"):
            ok, msg = servico.cadastrar_prestador(db(), usuario, doc, nome_novo)
            if ok:
                st.rerun()
            st.error(msg)
    elif prestador:
        st.markdown(f"**{prestador['nome']}**  \n{formatar_documento(doc)}")
        desvios = desvios_ativos()
        desvio = st.selectbox("Desvio", desvios, format_func=lambda d: d["nome"], index=None, placeholder="Escolha o desvio")
        if desvio:
            numero = servico.proximo_numero(db(), doc, desvio["id"])
            c1, c2 = st.columns(2)
            c1.metric("Orientação", rotulo_orientacao(numero))
            c2.metric("Ação", acao_para(numero) or "—")
            if exige_contato_direto(numero):
                st.warning(f"Prestador já conta com {numero - 1} orientações neste desvio. "
                           "Direcionar para contato direto por parte do credenciamento.")
            data = st.date_input("Data da orientação", value=date.today(), format="DD/MM/YYYY")
            sinal = st.radio("Credenciamento sinalizado?", ["—", "SIM", "NAO"], horizontal=True)
            obs = st.text_area("Observação (opcional)")
            if st.button("Salvar orientação", type="primary"):
                reg, msg = servico.registrar_orientacao(
                    db(), usuario, doc, desvio["id"], data, None if sinal == "—" else sinal, obs
                )
                if reg:
                    st.session_state["ultimo_registro"] = {
                        "numero": reg["numero_orientacao"], "acao": reg["acao"], "texto": desvio["texto_padrao"],
                    }
                    st.rerun()
                st.error(msg)
except Exception as e:  # noqa: BLE001
    erro_banco(e)
