from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from core import auditoria, auth, backup, desvios, logs, prestadores, textos, usuarios
from core.exportacao import blindar_formulas
from core.ui import db, erro_banco, exigir_login, limpar_contagens, mostrar_segredo

st.set_page_config(page_title="Administração", layout="wide")
admin = exigir_login(perfis=("admin",))
st.title("Administração")


def excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    blindar_formulas(df).to_excel(buf, index=False)
    return buf.getvalue()


try:
    n_pendentes = usuarios.contar_pendentes(db())
    aba_u, aba_d, aba_p, aba_a, aba_l, aba_b = st.tabs([
        f"Usuários ({n_pendentes} pendente(s))" if n_pendentes else "Usuários",
        "Desvios", "Prestadores", "Auditoria", "Logs", "Backup"])

    with aba_u:
        if n_pendentes:
            with st.container(border=True):
                st.markdown(f"**Cadastros aguardando aprovação ({n_pendentes})**")
                for p in usuarios.pendentes(db()):
                    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                    c1.write(f"{p['nome']} · `{p['usuario']}`")
                    perfil_novo = c2.selectbox("Perfil", auth.PERFIS, key=f"perfil_{p['usuario']}",
                                               label_visibility="collapsed")
                    if c3.button("Aprovar", key=f"aprovar_{p['usuario']}", type="primary"):
                        usuarios.aprovar(db(), admin, p["usuario"], perfil_novo)
                        limpar_contagens()
                        st.rerun()
                    if c4.button("Recusar", key=f"recusar_{p['usuario']}"):
                        usuarios.recusar(db(), admin, p["usuario"])
                        limpar_contagens()
                        st.rerun()
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
                    st.cache_data.clear()  # a mudanca de perfil/status vale na hora para quem esta logado
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
        with st.expander("Textos gerais da mensagem com mais de um desvio"):
            st.caption("Usados só quando 2 ou mais desvios são registrados juntos. Em {desvios}, entram os "
                       "resumos de cada desvio.")
            gerais = textos.carregar_gerais(db())
            novos = {
                "saudacao": st.text_input("Saudação", gerais["saudacao"]),
                "abertura": st.text_area("Frase de abertura", gerais["abertura"], height=90),
                "fechamento": st.text_area("Fechamento padrão", gerais["fechamento"], height=140),
                "fechamento_imagens": st.text_area("Fechamento (desvios com imagens/anexos)",
                                                   gerais["fechamento_imagens"], height=140),
            }
            if st.button("Salvar textos gerais", key="salvar_gerais"):
                textos.salvar_gerais(db(), novos)
                st.success("Textos gerais atualizados.")

        for d in desvios.listar(db(), so_ativos=False):
            with st.expander(d["nome"] + ("" if d["ativo"] else " (inativo)")):
                texto = st.text_area("Texto padrão (usado quando só este desvio é registrado)", d["texto_padrao"],
                                     key=f"t{d['id']}", height=200)
                st.caption("Para a mensagem com mais de um desvio:")
                resumo = st.text_input("Resumo (entra na frase de abertura)", d["resumo"] or "", key=f"r{d['id']}")
                titulo = st.text_input("Título da orientação", d["titulo"] or "", key=f"ti{d['id']}")
                corpo = st.text_area("Corpo da orientação", d["corpo"] or "", key=f"c{d['id']}", height=140)
                tipos = ["padrao", "imagens", "nenhum"]
                atual = d["fechamento_tipo"] or "nenhum"
                tipo = st.selectbox("Fechamento", tipos, index=tipos.index(atual), key=f"f{d['id']}")
                st.caption("Para o texto do FORMS (o que o credenciamento deve orientar ao prestador):")
                orient = st.text_area("Orientação do FORMS (frase curta, começa com um verbo no infinitivo)",
                                      d["orientacao_forms"] or "", key=f"o{d['id']}", height=70)
                ativo = st.checkbox("Ativo", bool(d["ativo"]), key=f"a{d['id']}")
                if st.button("Salvar", key=f"s{d['id']}"):
                    desvios.atualizar(db(), d["id"], texto, ativo, resumo or None, titulo, corpo,
                                      None if tipo == "nenhum" else tipo, orient.strip())
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
        st.caption("Quem fez o quê nos dados (registros, edições, exclusões, renumerações, pendências, "
                   "aprovações). Os filtros se combinam.")
        op = auditoria.opcoes(db())
        f1, f2, f3, f4, f5 = st.columns(5)
        f_quem = f1.selectbox("Quem", op["quem"], index=None, placeholder="Todos", key="aud_quem")
        f_tabela = f2.selectbox("Tabela", op["tabela"], index=None, placeholder="Todas", key="aud_tabela")
        f_acao = f3.selectbox("Ação", op["acao"], index=None, placeholder="Todas", key="aud_acao")
        f_ini = f4.date_input("De", value=None, format="DD/MM/YYYY", key="aud_ini")
        f_fim = f5.date_input("Até", value=None, format="DD/MM/YYYY", key="aud_fim")
        g1, g2 = st.columns([1, 1])
        f_registro = g1.text_input("Registro (id ou documento)", key="aud_registro")
        f_limite = g2.number_input("Máximo de linhas", 50, 5000, 500, step=50, key="aud_limite")
        aud = pd.DataFrame(auditoria.listar(db(), f_quem, f_tabela, f_acao, f_ini, f_fim, f_registro or None,
                                            f_limite))
        st.caption(f"{len(aud)} linha(s)")
        st.dataframe(aud, width="stretch", hide_index=True)
        if not aud.empty:
            st.download_button("Exportar auditoria (Excel)", excel(aud), "auditoria.xlsx", key="aud_export")

    with aba_l:
        st.caption(f"Erros e eventos de segurança do sistema, para analisar bugs. Guardados por "
                   f"{logs.RETENCAO_DIAS} dias. Os erros mostram o detalhe técnico completo.")
        l1, l2, l3, l4, l5 = st.columns(5)
        l_nivel = l1.selectbox("Nível", logs.NIVEIS, index=None, placeholder="Todos", key="log_nivel")
        l_usuario = l2.text_input("Usuário", key="log_usuario")
        l_pagina = l3.text_input("Página", key="log_pagina")
        l_ini = l4.date_input("De", value=None, format="DD/MM/YYYY", key="log_ini")
        l_fim = l5.date_input("Até", value=None, format="DD/MM/YYYY", key="log_fim")
        l_texto = st.text_input("Buscar no texto do evento ou no detalhe", key="log_texto")
        registros = logs.listar(db(), l_nivel, l_usuario or None, l_pagina or None, l_ini, l_fim, l_texto or None)
        if not registros:
            st.info("Nenhum registro de log com esses filtros.")
        else:
            tabela_logs = pd.DataFrame(registros)
            st.caption(f"{len(tabela_logs)} registro(s) · clique em uma linha para ver o detalhe")
            evento = st.dataframe(tabela_logs.drop(columns=["detalhe"]), width="stretch", hide_index=True,
                                  on_select="rerun", selection_mode="single-row", key="log_tabela")
            marcadas = evento.selection.rows if evento else []
            if marcadas:
                escolhido = registros[marcadas[0]]
                st.markdown(f"**{escolhido['evento']}**")
                st.code(escolhido["detalhe"] or "(sem detalhe)", language=None, wrap_lines=True)
            st.download_button("Exportar logs (Excel)", excel(tabela_logs), "logs.xlsx", key="log_export")

    with aba_b:
        st.caption("Planilha com o histórico de orientações (inclusive as excluídas), prestadores, desvios e "
                   "auditoria. Não inclui usuários nem senhas. Guarde em local seguro: tem CPFs e CNPJs.")
        if st.button("Gerar backup agora", type="primary"):
            with st.spinner("Lendo os dados..."):
                dfs = backup.exportar(db())
                agora = datetime.now()
                st.session_state["backup"] = (backup.NOME_ARQUIVO.format(agora), backup.para_bytes(dfs, agora),
                                              backup.contagens(dfs))
        if st.session_state.get("backup"):
            nome_arquivo, conteudo, contagens = st.session_state["backup"]
            st.success("Backup gerado: " + " · ".join(f"{aba}: {n}" for aba, n in contagens.items()))
            st.download_button("Baixar a planilha", conteudo, nome_arquivo,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
except Exception as e:  # noqa: BLE001
    erro_banco(e, "Administração")
