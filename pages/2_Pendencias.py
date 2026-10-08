from datetime import date

import pandas as pd
import streamlit as st

from core import tarefas
from core.regras import rotulo_orientacao
from core.ui import db, erro_banco, exigir_login, limpar_contagens

st.set_page_config(page_title="Pendências", layout="wide")
usuario = exigir_login()
ver_todas = usuario["perfil"] in tarefas.PODE_VER_TODAS
st.title("Pendências")
st.caption("Quando a ação da orientação for FORMS (3ª, 6ª, 9ª…) ou CONTATO DIRETO (a partir da 12ª), fica uma "
           "pendência aqui até você marcar que o FORMS foi preenchido ou que o contato direto foi feito.")

if st.session_state.get("msg_pendencias"):
    st.success(st.session_state.pop("msg_pendencias"))

try:
    filtro = usuario["usuario"]
    if ver_todas:
        resumo = tarefas.resumo_por_usuario(db())
        if resumo:
            st.subheader("Em aberto por usuário")
            st.dataframe(pd.DataFrame(resumo).rename(columns={
                "usuario": "Usuário", "forms": "FORMS", "contato_direto": "Contato direto",
                "total": "Total", "mais_antiga": "Mais antiga desde"}), hide_index=True, width="stretch")
        escolhido = st.selectbox("Ver as pendências de", ["Todos"] + [r["usuario"] for r in resumo])
        filtro = None if escolhido == "Todos" else escolhido

    incluir = st.checkbox("Mostrar também as concluídas nos últimos 30 dias")
    dados = tarefas.pendencias(db(), filtro, 30 if incluir else 0)
    if not dados:
        st.success("Nenhuma pendência. Tudo em dia.")
        st.stop()

    df = pd.DataFrame(dados)
    tabela = pd.DataFrame({
        "Feito": df["feita_em"].notna(),
        "Pendência": df["tipo"].map(tarefas.TIPOS),
        "Prestador": df["prestador"],
        "Desvio": df["desvio"],
        "Orientação": df["numero"].map(rotulo_orientacao),
        "Data": df["data_orientacao"].map(lambda d: date.fromisoformat(d).strftime("%d/%m/%Y")),
        **({"Registrada por": df["criado_por"]} if ver_todas else {}),
        "Há (dias)": df["dias"],
    })
    versao = st.session_state.get("versao_pendencias", 0)
    editada = st.data_editor(
        tabela, hide_index=True, width="stretch", key=f"editor_pendencias_{versao}",
        disabled=[c for c in tabela.columns if c != "Feito"],
        column_config={"Feito": st.column_config.CheckboxColumn("Feito", help="Marque quando concluir; "
                                                                  "desmarque para reabrir.")})
    mudou = [i for i in range(len(df)) if bool(editada.loc[i, "Feito"]) != bool(tabela.loc[i, "Feito"])]
    st.caption("Um FORMS vale para todos os desvios registrados juntos: marcar um marca os do mesmo registro.")
    if st.button(f"Salvar marcações ({len(mudou)})", type="primary", disabled=not mudou):
        erros = []
        for i in mudou:
            ok, msg = tarefas.marcar(db(), usuario, int(df.loc[i, "tarefa_id"]), bool(editada.loc[i, "Feito"]))
            if not ok:
                erros.append(msg)
        limpar_contagens()
        st.session_state["versao_pendencias"] = versao + 1
        if erros:
            st.error(" ".join(sorted(set(erros))))
        else:
            st.session_state["msg_pendencias"] = f"{len(mudou)} marcação(ões) salva(s)."
            st.rerun()
except Exception as e:  # noqa: BLE001
    erro_banco(e, "Pendências")
