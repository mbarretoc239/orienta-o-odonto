import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.db import LocalDb, criar_schema

CPF_OK = "52998224725"
CNPJ_OK = "11222333000181"
USR = {"usuario": "a.b", "nome": "A", "perfil": "contas"}
GESTOR = {**USR, "perfil": "gestor"}


@pytest.fixture
def db():
    d = LocalDb(":memory:")
    criar_schema(d)
    d.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('DESVIO A', 'texto')")
    d.execute("INSERT INTO ori_prestadores (documento, nome) VALUES (?, 'CLINICA TESTE')", (CNPJ_OK,))
    return d
