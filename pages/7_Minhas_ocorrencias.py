from datetime import date, timedelta

import streamlit as st

from core import marca, planilha
from core.regras import formatar_documento, rotulo_orientacao
from core.ui import botao_copiar, consulta_orientacoes, erro_banco, exigir_login

st.set_page_config(page_title="Minhas ocorrências", layout="wide", page_icon=marca.ICONE)
marca.aplicar()
usuario = exigir_login()
st.title("Minhas ocorrências")
st.caption("O que você registrou, da mais recente para a mais antiga. Use \"Copiar linha da planilha\" para colar a "
           "ocorrência na planilha (fluxo temporário, até o aplicativo substituí-la).")

MOSTRAR = [20, 50, 100, 200]

try:
    c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
    ini = c1.date_input("De", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
    fim = c2.date_input("Até", value=date.today(), format="DD/MM/YYYY")
    busca = c3.text_input("Prestador ou CNPJ/CPF", placeholder="Parte do nome ou do documento")
    quantas = c4.selectbox("Mostrar", MOSTRAR, format_func=lambda n: f"as {n} mais recentes")

    dados = consulta_orientacoes(None, None, ini, fim, usuario["usuario"])
    termo = busca.strip().lower()
    if termo:
        so_digitos = "".join(ch for ch in termo if ch.isdigit())
        dados = [r for r in dados if termo in r["prestador"].lower() or (so_digitos and so_digitos in r["documento"])]
    st.caption(f"{len(dados)} ocorrência(s) no período" + (f" (mostrando {quantas})" if len(dados) > quantas else ""))
    if not dados:
        st.info("Nenhuma ocorrência sua neste período.")
        st.stop()

    cab = st.columns([1.2, 3, 3, 1.4, 1.6, 1.6, 2.4])
    for coluna, titulo in zip(cab, ["Data", "Prestador", "Desvio", "Orientação", "Ação", "Sinalizado", ""]):
        coluna.markdown(f"**{titulo}**")
    for r in dados[:quantas]:
        col = st.columns([1.2, 3, 3, 1.4, 1.6, 1.6, 2.4], vertical_alignment="center")
        col[0].write(date.fromisoformat(r["data_orientacao"]).strftime("%d/%m/%Y"))
        col[1].markdown(f"{r['prestador']}  \n<small>{formatar_documento(r['documento'])}</small>", unsafe_allow_html=True)
        col[2].write(r["desvio"])
        col[3].write(rotulo_orientacao(r["numero_orientacao"]))
        col[4].write(r["acao"] or "—")
        col[5].write(r["credenciamento_sinalizado"] or "—")
        with col[6]:
            botao_copiar(planilha.linha_da_planilha(planilha.item_da_consulta(r), r["credenciamento_sinalizado"]),
                         "Copiar linha da planilha", f"o{r['id']}")
except Exception as e:  # noqa: BLE001
    erro_banco(e, "Minhas ocorrências")
