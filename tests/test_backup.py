from datetime import datetime, timedelta

import pandas as pd
import pytest

from core import auth, backup, orientacoes, prestadores
from tests.conftest import CPF_OK, GESTOR, USR


@pytest.fixture
def banco(db):
    prestadores.cadastrar(db, GESTOR, CPF_OK, "maria da silva")
    auth.criar_admin(db, "adm", "Adm", "senha-bem-segura")
    auth.registrar_usuario(db, "fulano.x", "Fulano", "outra-senha-1")
    return db


def test_backup_traz_historico_inclusive_excluidas_e_nao_traz_usuarios_nem_hashes(banco, tmp_path):
    a = orientacoes.registrar(banco, USR, CPF_OK, 1, "2026-10-01", "SIM", "primeira")[0]
    orientacoes.registrar(banco, USR, CPF_OK, 1, "2026-10-02", None, "=SOMA(1)")
    orientacoes.excluir(banco, GESTOR, a["id"])  # exclusao logica: continua no backup

    caminho, cont, _ = backup.salvar(banco, tmp_path, agora=datetime(2026, 10, 8, 12, 0, 0))
    assert caminho.name == "orientacoes_backup_20261008_120000.xlsx"
    assert cont["Orientações"] == 2 and cont["Prestadores"] == 2 and cont["Desvios"] == 1

    abas = pd.read_excel(caminho, sheet_name=None, dtype=str)
    assert set(abas) == {"Resumo", "Orientações", "Prestadores", "Desvios", "Auditoria"}  # sem aba de usuarios
    o = abas["Orientações"]
    assert o["excluido_em"].notna().sum() == 1 and set(o["prestador"].dropna()) == {"MARIA DA SILVA"}
    assert (o["observacao"] == "'=SOMA(1)").any()  # texto que viraria formula foi blindado

    tudo = " ".join(df.to_string() for df in abas.values())
    assert "scrypt" not in tudo and "fulano.x" not in tudo and "senha_hash" not in tudo and "codigo_hash" not in tudo


def test_documento_mantem_zeros_a_esquerda(banco, tmp_path):
    banco.execute("INSERT INTO ori_prestadores (documento, nome) VALUES ('00123456789', 'COM ZERO')")
    caminho, _, _ = backup.salvar(banco, tmp_path)
    docs = pd.read_excel(caminho, sheet_name="Prestadores", dtype=str)["documento"]
    assert "00123456789" in set(docs)


def test_retencao_mantem_os_mais_novos_e_so_apaga_arquivos_de_backup(banco, tmp_path):
    base = datetime(2026, 10, 1, 8, 0, 0)
    for dia in range(5):
        backup.salvar(banco, tmp_path, manter=99, agora=base + timedelta(days=dia))
    (tmp_path / "anotacao.xlsx").write_text("nao e backup")
    (tmp_path / "orientacoes_backup_qualquer.xlsx").write_text("nome fora do padrao")

    _, _, apagados = backup.salvar(banco, tmp_path, manter=3, agora=base + timedelta(days=5))
    restantes = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("orientacoes_backup_2026"))
    assert restantes == ["orientacoes_backup_20261004_080000.xlsx", "orientacoes_backup_20261005_080000.xlsx",
                         "orientacoes_backup_20261006_080000.xlsx"]
    assert len(apagados) == 3
    assert (tmp_path / "anotacao.xlsx").exists() and (tmp_path / "orientacoes_backup_qualquer.xlsx").exists()


def test_retencao_exige_manter_pelo_menos_um(tmp_path):
    with pytest.raises(ValueError):
        backup.rotacionar(tmp_path, 0)


def test_banco_vazio_gera_backup_valido(db, tmp_path):
    caminho, cont, _ = backup.salvar(db, tmp_path)
    assert cont["Orientações"] == 0 and caminho.exists()
