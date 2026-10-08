"""Roteador: define as paginas e os nomes do menu. O menu em si e desenhado em core/ui.py (barra_lateral), para
ficar abaixo do bloco do usuario."""
import streamlit as st

from core.paginas import PAGINAS

paginas = [st.Page(arquivo, title=titulo, url_path=url or None, default=not url) for arquivo, titulo, url in PAGINAS]
st.navigation(paginas, position="hidden").run()
