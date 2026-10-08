import streamlit as st

from core import auth, marca, sessao
from core.ui import db, erro_banco, exigir_login, mostrar_segredo

st.set_page_config(page_title="Minha conta", layout="centered", page_icon=marca.ICONE)
marca.aplicar()
usuario = exigir_login()
st.title("Minha conta")
st.write(f"**{usuario['nome']}** · usuário `{usuario['usuario']}` · perfil **{usuario['perfil']}**")

mostrar_segredo("codigo_novo", "Seu código de recuperação",
                "Guarde este código em local seguro. Ele é a única forma de redefinir sua senha sem o administrador "
                "e não será mostrado novamente.")

try:
    st.subheader("Trocar a senha")
    with st.form("trocar_senha_voluntaria"):
        atual = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha (mínimo 8 caracteres)", type="password")
        confirma = st.text_input("Repita a nova senha", type="password")
        if st.form_submit_button("Trocar senha", type="primary"):
            if nova != confirma:
                st.error("As duas senhas novas não são iguais.")
            else:
                ok, msg, codigo = auth.trocar_senha(db(), usuario["usuario"], atual, nova)
                if ok:
                    sessao.encerrar_outras(db(), usuario["usuario"], st.session_state.get("token_sessao"))
                    if codigo:  # quem ainda nao tinha codigo de recuperacao ganha um
                        st.session_state["codigo_novo"] = codigo
                    st.success("Senha alterada. Seus outros acessos abertos foram encerrados.")
                    if codigo:
                        st.rerun()
                else:
                    st.error(msg)

    st.subheader("Código de recuperação")
    st.caption("É o que permite redefinir a senha pela tela de login (\"Esqueci minha senha\"). "
               "Gerar um novo invalida o anterior.")
    with st.form("novo_codigo"):
        senha = st.text_input("Confirme sua senha", type="password")
        if st.form_submit_button("Gerar novo código"):
            ok, msg, codigo = auth.novo_codigo_com_senha(db(), usuario["usuario"], senha)
            if ok:
                st.session_state["codigo_novo"] = codigo
                st.rerun()
            st.error(msg)
except Exception as e:  # noqa: BLE001
    erro_banco(e, "Minha conta")
