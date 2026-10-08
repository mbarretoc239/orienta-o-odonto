from datetime import date

import streamlit as st

from core import orientacoes, prestadores
from core.config import url_forms
from core.regras import formatar_documento, normalizar_documento, rotulo_orientacao
from core.ui import db, desvios_ativos, erro_banco, exigir_login

st.set_page_config(page_title="Registrar orientação", layout="centered")
usuario = exigir_login()
st.title("Registrar orientação")


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


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


def alternar_blocos():
    """'Minimizar todos' / 'Expandir todos': a nova versao recria os expansores no estado escolhido."""
    st.session_state["blocos_abertos"] = not st.session_state.get("blocos_abertos", True)
    st.session_state["blocos_versao"] = st.session_state.get("blocos_versao", 0) + 1


def controle_blocos(itens, chave):
    if len(itens) > 1:
        aberto = st.session_state.get("blocos_abertos", True)
        st.button("Minimizar todos" if aberto else "Expandir todos", key=f"alternar_{chave}",
                  on_click=alternar_blocos)


def bloco_desvio(i, chave):
    """Um bloco expansivel por desvio (mesmo layout para um ou varios): orientacao, acao e o aviso do desvio.
    Fechado, o titulo mostra o resumo. Por padrao todos abrem expandidos."""
    resumo = f"**{i['desvio']}** · {rotulo_orientacao(i['numero'])} · AÇÃO: {i['acao'] or '—'}"
    chave_exp = f"exp_{chave}_{i['desvio']}_{st.session_state.get('blocos_versao', 0)}"
    with st.expander(resumo, expanded=st.session_state.get("blocos_abertos", True), key=chave_exp):
        c1, c2 = st.columns(2)
        c1.metric("Orientação", rotulo_orientacao(i["numero"]))
        c2.metric("Ação", i["acao"] or "—")
        if i["acao"] == "CONTATO DIRETO":
            st.error(f"Prestador já conta com {i['numero']} orientações. "
                     "Direcionar para contato direto por parte do credenciamento.")
        elif i["acao"] == "FORMS":
            st.info("Exige o preenchimento do FORMS.")


def botao_forms_grupo(itens, chave):
    """Um unico FORMS cobre todos os desvios que o exigem."""
    forms = [i for i in itens if i["acao"] == "FORMS"]
    if not forms:
        return
    if len(forms) > 1:
        st.info("Um único FORMS cobre estes desvios: " + "; ".join(i["desvio"] for i in forms) + ".")
    botao_forms(chave)


@st.dialog("Confirmar registro")
def confirmar(prestador, escolhidos, itens, data, sinal, obs):
    st.markdown(f"**{prestador['nome']}**  \n{formatar_documento(prestador['documento'])}")
    st.write(f"Data: {data.strftime('%d/%m/%Y')}")
    for i in itens:
        st.write(f"• {i['desvio']} · {i['rotulo']}" + (f" · **AÇÃO: {i['acao']}**" if i["acao"] else ""))
    for i in itens:
        if i["acao"] == "CONTATO DIRETO":
            st.error(f"{i['desvio']}: Prestador já conta com {i['numero']} orientações. "
                     "Direcionar para contato direto por parte do credenciamento.")
    if st.button("Confirmar e registrar", type="primary"):
        regs, msg = orientacoes.registrar_varios(
            db(), usuario, prestador["documento"], [d["id"] for d in escolhidos], data, sinal, obs)
        if not regs:
            st.error(msg)
            return
        por_id = {d["id"]: d for d in escolhidos}
        st.session_state["ultimo_registro"] = [
            {"desvio": por_id[r["desvio_id"]]["nome"], "numero": r["numero_orientacao"], "acao": r["acao"],
             "texto": por_id[r["desvio_id"]]["texto_padrao"]}
            for r in regs
        ]
        st.rerun()


if st.session_state.get("ultimo_registro"):
    itens = st.session_state.pop("ultimo_registro")
    st.success("Orientação registrada." if len(itens) == 1 else f"{len(itens)} orientações registradas.")
    controle_blocos(itens, "pos")
    for i in itens:
        bloco_desvio(i, "pos")
    botao_forms_grupo(itens, "forms_pos_registro")
    st.caption("Texto padrão para enviar ao prestador (use o ícone de copiar):")
    for i in itens:
        if len(itens) > 1:
            st.markdown(f"**{i['desvio']}**")
        st.code(i["texto"], language=None, wrap_lines=True)

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
        desvios = desvios_ativos()
        hoje = date.today()
        ja_registradas = orientacoes.registradas_no_mes(db(), doc, hoje)
        if ja_registradas:
            with st.container(border=True):
                st.markdown(f"**Já registrado em {MESES[hoje.month - 1]}/{hoje.year} para este prestador:**")
                for r in ja_registradas:
                    st.write(f"• {r['desvio']} · {r['numero']}ª orientação · "
                             f"{date.fromisoformat(r['data_orientacao']).strftime('%d/%m/%Y')}")
        mais_de_um = st.checkbox(
            "Mais de um desvio neste mês",
            help="Para lançar 2 ou mais desvios de uma vez. Cada desvio é registrado em uma linha, "
                 "com a própria numeração e a própria ação.")

        if mais_de_um:
            escolhidos = st.multiselect("Desvios", desvios, format_func=lambda d: d["nome"],
                                        placeholder="Escolha os desvios")
        else:
            um = st.selectbox("Desvio", desvios, format_func=lambda d: d["nome"],
                              index=None, placeholder="Escolha o desvio")
            escolhidos = [um] if um else []

        if escolhidos:
            itens = []
            for d in escolhidos:
                p = orientacoes.previa(db(), doc, d["id"])
                itens.append({"desvio": d["nome"], "numero": p["numero"], "rotulo": p["rotulo"], "acao": p["acao"]})
            controle_blocos(itens, "previa")
            for i in itens:
                bloco_desvio(i, "previa")
            botao_forms_grupo(itens, "forms_previa")
            data = st.date_input("Data da orientação", value=hoje, format="DD/MM/YYYY")
            sinal = st.radio("Credenciamento sinalizado?", ["—", "SIM", "NAO"], horizontal=True)
            obs = st.text_area("Observação (opcional)")
            if st.button("Salvar orientação", type="primary"):
                confirmar(prestador, escolhidos, itens, data, None if sinal == "—" else sinal, obs)
except Exception as e:  # noqa: BLE001
    erro_banco(e)
