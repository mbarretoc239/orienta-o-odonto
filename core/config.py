"""Configuracoes que nao vao para o git: ambiente (Streamlit Cloud), secrets.toml ou st.secrets."""
import os

from core.db import _ler_secrets


def segredo(nome: str):
    valor = os.environ.get(nome) or _ler_secrets().get(nome)
    if not valor:
        try:
            import streamlit as st

            valor = st.secrets.get(nome)
        except Exception:  # noqa: BLE001 - sem streamlit/secrets
            valor = None
    return valor or None


def url_forms():
    """Link do formulario (Microsoft Forms) aberto nas orientacoes com acao FORMS."""
    return segredo("FORMS_URL")
