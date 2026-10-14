import re
from pathlib import Path

from core import paginas

RAIZ = Path(__file__).resolve().parent.parent


def titulos(perfil):
    return [titulo for _, titulo in paginas.paginas_do_perfil(perfil)]


def test_contas_ve_so_o_basico():
    assert titulos("contas") == ["Início", "Registrar ocorrência", "Minhas ocorrências", "Pendências",
                                 "Consultar Base", "Minha conta"]


def test_gestor_ve_o_basico_e_o_painel_mas_nao_o_admin():
    assert titulos("gestor") == titulos("contas")[:5] + ["Painel", "Minha conta"]
    assert "Admin" not in titulos("gestor")


def test_admin_ve_tudo_e_so_ele_ve_a_administracao():
    assert "Painel" in titulos("admin") and "Admin" in titulos("admin")
    assert "Admin" not in titulos("contas") and "Painel" not in titulos("contas")


def test_o_menu_bate_com_o_bloqueio_dentro_de_cada_pagina():
    """O link escondido nao protege nada: cada pagina precisa bloquear os mesmos perfis que o menu esconde."""
    for arquivo, titulo, _, perfis in paginas.PAGINAS:
        if arquivo == "inicio.py":
            continue
        texto = (RAIZ / arquivo).read_text(encoding="utf-8")
        achou = re.search(r"exigir_login\((?:perfis=\(([^)]*)\))?\)", texto)
        assert achou, f"{arquivo} nao chama exigir_login"
        no_codigo = tuple(re.findall(r'"(\w+)"', achou.group(1) or ""))
        assert no_codigo == perfis, f"{titulo}: menu {perfis} x pagina {no_codigo}"
