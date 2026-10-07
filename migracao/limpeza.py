"""Funcoes puras de limpeza dos dados da planilha (sem acesso a arquivo nem a banco)."""
import re
import unicodedata
from datetime import datetime


def vazio(v) -> bool:
    return v is None or (isinstance(v, float) and v != v) or str(v).strip() == ""


def sem_acento(s) -> str:
    """Maiusculas, sem acento e sem espacos repetidos; usado so para comparar nomes."""
    if vazio(s):
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).upper().split())


def nome_desvio(s) -> str:
    """Nome do desvio como esta na aba Base (com acento), em maiusculas."""
    return " ".join(str(s).upper().split())


def _data(d, m, a):
    try:
        return datetime(int(a), int(m), int(d)).date().isoformat()
    except ValueError:
        return None


def parse_data(v):
    """Retorna (iso|None, corrigida). Corrige tres erros de digitacao inequivocos e informa que corrigiu."""
    if vazio(v):
        return None, False
    v = str(v).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", v):
        return v[:10], False
    if m := re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", v):
        return _data(m[1], m[2], m[3]), False
    if m := re.match(r"^(\d{1,2})/(\d{2})(\d{4})$", v):  # 17/082026
        return _data(m[1], m[2], m[3]), True
    if m := re.match(r"^(\d{2})(\d{2})/(\d{4})$", v):  # 2907/2026
        return _data(m[1], m[2], m[3]), True
    if m := re.match(r"^(\d{1,2})/(\d{1,2})/(\d{3})$", v):  # 25/08/206
        return _data(m[1], m[2], m[3][:2] + "2" + m[3][2:]), True
    return None, False


def normalizar_sinal(valor):
    """Retorna (SIM|NAO|None, texto_para_observacao|None, era_documento_digitado_por_engano)."""
    if vazio(valor):
        return None, None, False
    s = sem_acento(valor)
    if s in ("SIM", "SM"):
        return "SIM", None, False
    if s == "NAO":
        return "NAO", None, False
    if s.startswith("SINALIZADO"):
        return "SIM", f"Planilha: {str(valor).strip()}", False
    if s.isdigit():
        return None, None, True
    return None, f"Planilha: {str(valor).strip()}", False
