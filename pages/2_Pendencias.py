from datetime import date

import pandas as pd
import streamlit as st

from core import marca, tarefas, textos
from core.regras import formatar_documento, rotulo_orientacao
from core.ui import botao_forms, db, erro_banco, exigir_login, limpar_contagens

st.set_page_config(page_title="Pendências", layout="wide", page_icon=marca.ICONE)
marca.aplicar()
usuario = exigir_login()
ver_todas = usuario["perfil"] in tarefas.PODE_VER_TODAS
st.title("Pendências")
st.caption("Quando a ação da orientação for FORMS (3ª, 6ª, 9ª…), CONTATO DIRETO (12ª) ou RELATAR PARA GESTÃO "
           "(13ª em diante), fica uma pendência aqui até ser marcada como feita. Abra cada uma para ver o que fazer; "
           "nas de FORMS, o texto do relato já está pronto para copiar. O relato para a gestão só o gestor marca; "
           "quando ele marca, a pendência sai da lista de quem registrou.")

ROTULO = {"forms": "FORMS", "contato_direto": "Contato direto", "relatar_gestao": "Relatar à gestão"}

if st.session_state.get("msg_pendencias"):
    st.success(st.session_state.pop("msg_pendencias"))
if st.session_state.get("erro_pendencias"):
    st.error(st.session_state.pop("erro_pendencias"))


def br(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def titulo(item: dict) -> str:
    d = item["desvios"]
    resumo = f"{d[0]['desvio']} ({rotulo_orientacao(d[0]['numero'])})" if len(d) == 1 else f"{len(d)} desvios"
    dias = f"há {item['dias']} dia(s)" if item["dias"] else "hoje"
    return f"{'✔ Concluída · ' if item['feita_em'] else ''}{ROTULO[item['tipo']]} · {item['prestador']} · {resumo} · {dias}"


def pode_marcar(item: dict) -> bool:
    return not (item["tipo"] in tarefas.SO_GESTAO_MARCA and not ver_todas)


def marcar(tarefa_id: int, feita: bool):
    """Callback do botao: roda antes de a pagina ser redesenhada, entao a lista ja nasce atualizada (um st.rerun() dentro
    do bloco deixava na tela o bloco antigo)."""
    ok, msg = tarefas.marcar(db(), usuario, tarefa_id, feita=feita)
    limpar_contagens()
    st.session_state["msg_pendencias" if ok else "erro_pendencias"] = msg


def bloco(item: dict):
    st.markdown(f"**{item['prestador']}**  \n{formatar_documento(item['documento'])}")
    for d in item["desvios"]:
        st.write(f"• {d['desvio']} · {rotulo_orientacao(d['numero'])} · {br(d['data'])}")
    if ver_todas:
        st.caption(f"Registrada por {item['criado_por']}")

    if item["tipo"] == "forms":
        st.caption("Abra o formulário, cole o texto do relato (use o ícone de copiar; acrescente o que quiser) e, "
                   "depois de enviar, marque como feito." + (" Um único FORMS cobre estes desvios."
                                                              if len(item["desvios"]) > 1 else ""))
        botao_forms(f"forms_{item['tarefa_id']}")
        st.code(textos.relato_forms(item["prestador"], item["documento"], item["desvios"]),
                language=None, wrap_lines=True)
    elif item["tipo"] == "contato_direto":
        st.info("Direcionar para contato direto por parte do credenciamento.")
    else:
        st.warning("Relatar para a gestão. Só o gestor marca como feito; depois disso a pendência sai da lista.")

    if item["feita_em"]:
        st.caption(f"Concluída por {item['feita_por']} em {item['feita_em'][:16]}")
    if not pode_marcar(item):
        st.caption("Quem marca é o gestor.")
        return
    st.button("Reabrir" if item["feita_em"] else "Marcar como feito", key=f"marcar_{item['tarefa_id']}",
              type="secondary" if item["feita_em"] else "primary", on_click=marcar,
              args=(item["tarefa_id"], not item["feita_em"]))


try:
    filtro = usuario["usuario"]
    if ver_todas:
        resumo = tarefas.resumo_por_usuario(db())
        if resumo:
            st.subheader("Em aberto por usuário")
            st.dataframe(pd.DataFrame(resumo).rename(columns={
                "usuario": "Usuário", "forms": "FORMS", "contato_direto": "Contato direto",
                "relatar_gestao": "Relatar à gestão", "total": "Total", "mais_antiga": "Mais antiga desde"}),
                hide_index=True, width="stretch")
        escolhido = st.selectbox("Ver as pendências de", ["Todos"] + [r["usuario"] for r in resumo])
        filtro = None if escolhido == "Todos" else escolhido

    incluir = st.checkbox("Mostrar também as concluídas nos últimos 30 dias")
    itens = tarefas.agrupar(tarefas.pendencias(db(), filtro, 30 if incluir else 0))
    if not itens:  # sem st.stop(): ele deixaria na tela os blocos da execucao anterior (ex.: logo apos marcar o ultimo)
        st.success("Nenhuma pendência. Tudo em dia.")
    else:
        abertas = [i for i in itens if not i["feita_em"]]
        st.caption(f"{len(abertas)} em aberto" + (f" · {len(itens) - len(abertas)} concluída(s)" if incluir else ""))
        for item in itens:
            with st.expander(titulo(item), key=f"exp_{item['tarefa_id']}"):
                bloco(item)
except Exception as e:  # noqa: BLE001
    erro_banco(e, "Pendências")
