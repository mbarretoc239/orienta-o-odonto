import pandas as pd
import streamlit as st

from core import auth, desvios, prestadores, usuarios
from core.ui import db, erro_banco, exigir_login, mostrar_segredo

st.set_page_config(page_title="Administração", layout="wide")
admin = exigir_login(perfis=("admin",))
st.title("Administração")

try:
    aba_u, aba_d, aba_p, aba_a = st.tabs(["Usuários", "Desvios", "Prestadores", "Auditoria"])

    with aba_u:
        lista = usuarios.listar(db())
        st.dataframe(pd.DataFrame(lista), width="stretch", hide_index=True)
        if lista:
            login = st.selectbox("Usuário", [u["usuario"] for u in lista])
            atual = next(u for u in lista if u["usuario"] == login)
            perfil = st.selectbox("Perfil", auth.PERFIS, index=auth.PERFIS.index(atual["perfil"]))
            status = st.selectbox("Status", usuarios.STATUS, index=usuarios.STATUS.index(atual["status"]))
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("Salvar usuário", type="primary"):
                ok, msg = usuarios.atualizar(db(), admin, login, perfil, status)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
            if c2.button("Desbloquear login"):
                usuarios.desbloquear(db(), login)
                st.success("Tentativas zeradas.")
            if c3.button("Redefinir senha"):
                st.session_state["segredo_admin"] = (
                    f"Usuário: {login}\nSenha temporária: {usuarios.redefinir_senha(db(), admin, login)}")
            if c4.button("Novo código de recuperação"):
                st.session_state["segredo_admin"] = (
                    f"Usuário: {login}\nCódigo: {usuarios.gerar_codigo_recuperacao(db(), admin, login)}")
        mostrar_segredo("segredo_admin", "Entregue à pessoa (não será mostrado novamente)",
                        "A senha temporária obriga a troca no próximo acesso e encerra as sessões abertas dela.")

    with aba_d:
        for d in desvios.listar(db(), so_ativos=False):
            with st.expander(d["nome"] + ("" if d["ativo"] else " (inativo)")):
                texto = st.text_area("Texto padrão", d["texto_padrao"], key=f"t{d['id']}", height=200)
                ativo = st.checkbox("Ativo", bool(d["ativo"]), key=f"a{d['id']}")
                if st.button("Salvar", key=f"s{d['id']}"):
                    desvios.atualizar(db(), d["id"], texto, ativo)
                    st.cache_data.clear()
                    st.success("Desvio atualizado.")
        with st.form("novo_desvio", clear_on_submit=True):
            nome = st.text_input("Novo desvio")
            texto = st.text_area("Texto padrão")
            if st.form_submit_button("Adicionar"):
                ok, msg = desvios.adicionar(db(), nome, texto)
                if ok:
                    st.cache_data.clear()
                    st.rerun()
                st.error(msg)

    with aba_p:
        st.caption("Corrigir o nome de um prestador (o documento não muda).")
        termo = st.text_input("Buscar por nome ou documento")
        achados = []
        if termo.strip():
            doc = "".join(ch for ch in termo if ch.isdigit())
            if len(doc) >= 8:
                p = prestadores.buscar(db(), doc)
                achados = [p] if p else []
            else:
                achados = prestadores.buscar_por_nome(db(), termo)
        if achados:
            st.dataframe(pd.DataFrame(achados)[["documento", "nome", "cidade", "uf", "origem"]],
                         width="stretch", hide_index=True)
            escolhido = st.selectbox("Prestador", achados, format_func=lambda p: f"{p['nome']} ({p['documento']})")
            novo = st.text_input("Novo nome", value=escolhido["nome"], key=f"nome_{escolhido['documento']}")
            if st.button("Salvar nome", type="primary"):
                ok, msg = prestadores.renomear(db(), admin, escolhido["documento"], novo)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.cache_data.clear()
        elif termo.strip():
            st.info("Nenhum prestador encontrado (use ao menos 3 letras do nome).")

    with aba_a:
        aud = db().query("SELECT * FROM ori_auditoria ORDER BY id DESC LIMIT 500")
        st.dataframe(pd.DataFrame(aud), width="stretch", hide_index=True)
except Exception as e:  # noqa: BLE001
    erro_banco(e)
