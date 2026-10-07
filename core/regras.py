"""Regras puras de negocio: documento, numeracao e acao."""
import re

ACAO_A_CADA = 3  # "FORMS" em todo multiplo de 3 (confirmado)
LIMITE_CONTATO_DIRETO = 12  # a partir daqui: encaminhar ao credenciamento para contato direto


def exige_contato_direto(numero: int) -> bool:
    return numero >= LIMITE_CONTATO_DIRETO


def so_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def normalizar_documento(valor) -> str:
    """Somente digitos; CPF com 11 e CNPJ com 14 (restaura zeros a esquerda)."""
    d = so_digitos(valor)
    if not d:
        return ""
    return d.zfill(11) if len(d) <= 11 else d.zfill(14)


def _dv(digitos: str, pesos) -> int:
    resto = sum(int(n) * p for n, p in zip(digitos, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def valida_cpf(doc: str) -> bool:
    if len(doc) != 11 or not doc.isdigit() or doc == doc[0] * 11:
        return False
    d1 = _dv(doc[:9], range(10, 1, -1))
    d2 = _dv(doc[:9] + str(d1), range(11, 1, -1))
    return doc[9:] == f"{d1}{d2}"


def valida_cnpj(doc: str) -> bool:
    if len(doc) != 14 or not doc.isdigit() or doc == doc[0] * 14:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _dv(doc[:12], p1)
    d2 = _dv(doc[:12] + str(d1), [6] + p1)
    return doc[12:] == f"{d1}{d2}"


def valida_documento(doc: str) -> bool:
    return valida_cpf(doc) if len(doc) == 11 else valida_cnpj(doc)


def formatar_documento(doc: str) -> str:
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    return doc


def acao_para(numero: int) -> str | None:
    return "FORMS" if numero > 0 and numero % ACAO_A_CADA == 0 else None


def rotulo_orientacao(numero: int) -> str:
    return f"{numero}ª orientação"
