import pandas as pd
import streamlit as st

from core import auth
from core.ui import db, erro_banco, exigir_login

st.set_page_config(page_title="Administração", layout="wide")
usuario = exigir_login(perfis=("admin",))
st.title("Administração")

try:
    aba_u, aba_d, aba_a = st.tabs(["Usuários", "Desvios", "Auditoria"])

    with aba_u:
        usuarios = db().query("SELECT usuario, nome, perfil, status, criado_em FROM ori_usuarios ORDER BY status, nome")
        st.dataframe(pd.DataFrame(usuarios), width="stretch", hide_index=True)
        if usuarios:
            login = st.selectbox("Usuário", [u["usuario"] for u in usuarios])
            atual = next(u for u in usuarios if u["usuario"] == login)
            perfil = st.selectbox("Perfil", auth.PERFIS, index=auth.PERFIS.index(atual["perfil"]))
            status = st.selectbox("Status", ["pendente", "ativo", "inativo"],
                                  index=["pendente", "ativo", "inativo"].index(atual["status"]))
            if st.button("Salvar usuário", type="primary"):
                if login == usuario["usuario"] and (perfil != "admin" or status != "ativo"):
                    st.error("Você não pode remover seu próprio acesso de admin.")
                else:
                    db().execute("UPDATE ori_usuarios SET perfil=?, status=? WHERE usuario=?", (perfil, status, login))
                    st.success("Usuário atualizado.")
                    st.rerun()

    with aba_d:
        desvios = db().query("SELECT id, nome, texto_padrao, ativo FROM ori_desvios ORDER BY id")
        for d in desvios:
            with st.expander(d["nome"]):
                texto = st.text_area("Texto padrão", d["texto_padrao"], key=f"t{d['id']}", height=200)
                ativo = st.checkbox("Ativo", bool(d["ativo"]), key=f"a{d['id']}")
                if st.button("Salvar", key=f"s{d['id']}"):
                    db().execute("UPDATE ori_desvios SET texto_padrao=?, ativo=? WHERE id=?", (texto, int(ativo), d["id"]))
                    st.cache_data.clear()
                    st.success("Desvio atualizado.")
        with st.form("novo_desvio", clear_on_submit=True):
            nome = st.text_input("Novo desvio")
            texto = st.text_area("Texto padrão")
            if st.form_submit_button("Adicionar") and nome.strip():
                db().execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES (?,?)", (nome.strip().upper(), texto))
                st.cache_data.clear()
                st.rerun()

    with aba_a:
        aud = db().query("SELECT * FROM ori_auditoria ORDER BY id DESC LIMIT 500")
        st.dataframe(pd.DataFrame(aud), width="stretch", hide_index=True)
except Exception as e:  # noqa: BLE001
    erro_banco(e)
