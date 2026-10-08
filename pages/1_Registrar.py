from datetime import date

import pandas as pd
import streamlit as st

from core import orientacoes, prestadores, tarefas, textos
from core.config import url_forms
from core.regras import formatar_documento, normalizar_documento, rotulo_orientacao
from core.ui import (
    consulta_orientacoes,
    db,
    desvios_ativos,
    erro_banco,
    exigir_login,
    limpar_contagens,
    link_pagina,
)

st.set_page_config(page_title="Registrar orientação", layout="centered")
usuario = exigir_login()
st.title("Registrar orientação")


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


@st.cache_data(ttl=120, show_spinner=False)
def prestador_por_documento(doc):
    return prestadores.buscar(db(), doc)


@st.cache_data(ttl=120, show_spinner=False)
def busca_por_nome(termo):
    return prestadores.buscar_por_nome(db(), termo, limite=15)


def usar_prestador_da_busca():
    """Ao escolher um resultado da busca por nome, preenche o campo do CNPJ/CPF."""
    escolhido = st.session_state.get("busca_sel")
    if escolhido:
        st.session_state["doc_txt"] = escolhido["documento"]


def quadro_historico(doc):
    """Orientacoes que o prestador ja tem e o que a proxima de cada desvio vai acionar."""
    historico = orientacoes.historico(db(), doc)
    if not historico:
        st.caption("Este prestador ainda não tem orientações registradas.")
        return
    with st.expander(f"Histórico deste prestador ({len(historico)} orientação(ões))"):
        situacao = orientacoes.situacao_por_desvio(db(), doc)
        st.markdown("**Situação por desvio**")
        st.dataframe(pd.DataFrame(situacao).rename(columns={
            "desvio": "Desvio", "ja_tem": "Já tem", "proxima": "Próxima será", "acao_da_proxima": "Ação da próxima"}),
            hide_index=True, width="stretch")
        st.markdown("**Todas as orientações**")
        st.dataframe(pd.DataFrame([{
            "Data": date.fromisoformat(h["data"]).strftime("%d/%m/%Y"), "Desvio": h["desvio"],
            "Orientação": rotulo_orientacao(h["numero"]), "Ação": h["acao"] or "—", "Registrada por": h["registrado_por"]}
            for h in historico]), hide_index=True, width="stretch")


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
        consulta_orientacoes.clear()  # a consulta passa a mostrar o que acabou de ser registrado
        limpar_contagens()  # as pendencias novas entram no contador da barra lateral
        por_id = {d["id"]: d for d in escolhidos}
        st.session_state["ultimo_registro"] = {
            "itens": [
                {"desvio": por_id[r["desvio_id"]]["nome"], "numero": r["numero_orientacao"], "acao": r["acao"],
                 "data": r["data_orientacao"], "prestador": prestador["nome"], "documento": prestador["documento"],
                 "orientacao": por_id[r["desvio_id"]].get("orientacao_forms")}
                for r in regs
            ],
            "mensagem": textos.montar_mensagem([por_id[r["desvio_id"]] for r in regs], textos.carregar_gerais(db())),
        }
        st.rerun()


if st.session_state.get("ultimo_registro"):
    ultimo = st.session_state.pop("ultimo_registro")
    itens, mensagem = ultimo["itens"], ultimo["mensagem"]
    st.success("Orientação registrada." if len(itens) == 1 else f"{len(itens)} orientações registradas.")
    with st.container(border=True):
        st.markdown("**Pendências criadas para você marcar quando fizer:**")
        st.write("• " + tarefas.TIPOS["capa"] + (" (uma por desvio)" if len(itens) > 1 else ""))
        if any(i["acao"] == "FORMS" for i in itens):
            st.write("• " + tarefas.TIPOS["forms"])
        if any(i["acao"] == "CONTATO DIRETO" for i in itens):
            st.write("• " + tarefas.TIPOS["contato_direto"])
        link_pagina("pages/2_Pendencias.py", "Ir para as pendências")
    controle_blocos(itens, "pos")
    for i in itens:
        bloco_desvio(i, "pos")
    botao_forms_grupo(itens, "forms_pos_registro")
    com_forms = [i for i in itens if i["acao"] == "FORMS"]
    if com_forms:
        st.caption("Texto do relato do FORMS (use o ícone de copiar; acrescente o que quiser no formulário):")
        st.code(textos.relato_forms(com_forms[0]["prestador"], com_forms[0]["documento"], com_forms),
                language=None, wrap_lines=True)
    st.caption("Texto para enviar ao prestador (use o ícone de copiar):")
    st.code(mensagem, language=None, wrap_lines=True)

try:
    doc_txt = st.text_input("CNPJ/CPF do prestador", placeholder="Somente números ou com pontuação", key="doc_txt")
    with st.expander("Não sabe o CNPJ/CPF? Busque pelo nome"):
        termo = st.text_input("Nome do prestador (a partir de 3 letras)", key="busca_nome")
        achados = busca_por_nome(termo) if len(termo.strip()) >= 3 else []
        if achados:
            st.selectbox("Resultados", achados, index=None, key="busca_sel", on_change=usar_prestador_da_busca,
                         placeholder="Escolha para usar este prestador",
                         format_func=lambda p: f"{p['nome']} · {formatar_documento(p['documento'])}"
                                               + (f" · {p['cidade']}/{p['uf']}" if p.get("cidade") else ""))
        elif len(termo.strip()) >= 3:
            st.caption("Nenhum prestador encontrado com esse nome.")
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
        quadro_historico(doc)
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
    erro_banco(e, "Registrar")
