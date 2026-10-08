"""Backup dos dados em planilha: historico de orientacoes, prestadores, desvios e auditoria.

Nao inclui usuarios, senhas, codigos de recuperacao nem sessoes: so o que e historico de trabalho.
"""
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd

from core.exportacao import blindar_formulas

NOME_ARQUIVO = "orientacoes_backup_{:%Y%m%d_%H%M%S}.xlsx"
_PADRAO_ARQUIVO = re.compile(r"^orientacoes_backup_\d{8}_\d{6}\.xlsx$")

CONSULTAS = {
    "Orientações": (
        "SELECT o.id, o.documento, p.nome AS prestador, d.nome AS desvio, o.data_orientacao, "
        "o.numero_orientacao, o.acao, o.credenciamento_sinalizado, o.observacao, o.criado_por, o.criado_em, "
        "o.excluido_em, o.excluido_por, o.lote_id FROM ori_orientacoes o "
        "LEFT JOIN ori_prestadores p ON p.documento = o.documento "
        "LEFT JOIN ori_desvios d ON d.id = o.desvio_id ORDER BY o.id"
    ),
    "Prestadores": (
        "SELECT documento, nome, codigo, tipo, cidade, uf, origem, criado_por, criado_em "
        "FROM ori_prestadores ORDER BY documento"
    ),
    "Desvios": (
        "SELECT id, nome, texto_padrao, ativo, resumo, titulo, corpo, fechamento_tipo, orientacao_forms "
        "FROM ori_desvios ORDER BY id"
    ),
    "Auditoria": "SELECT id, quando, quem, tabela, registro, acao, antes, depois FROM ori_auditoria ORDER BY id",
}


def exportar(db) -> dict[str, pd.DataFrame]:
    """Le as tabelas de dados. Orientacoes excluidas (exclusao logica) tambem entram: sao historico."""
    return {nome: pd.DataFrame(db.query(sql)) for nome, sql in CONSULTAS.items()}


def contagens(dfs: dict[str, pd.DataFrame]) -> dict[str, int]:
    return {nome: len(df) for nome, df in dfs.items()}


def para_bytes(dfs: dict[str, pd.DataFrame], gerado_em: datetime) -> bytes:
    resumo = pd.DataFrame({
        "Item": ["Gerado em", *dfs.keys()],
        "Valor": [f"{gerado_em:%d/%m/%Y %H:%M:%S}", *[f"{n} linhas" for n in contagens(dfs).values()]],
    })
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        resumo.to_excel(w, sheet_name="Resumo", index=False)
        w.sheets["Resumo"].column_dimensions["A"].width = 18
        w.sheets["Resumo"].column_dimensions["B"].width = 28
        for nome, df in dfs.items():
            blindar_formulas(df).to_excel(w, sheet_name=nome, index=False)
            ws = w.sheets[nome]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
    return buf.getvalue()


def rotacionar(pasta: Path, manter: int) -> list[str]:
    """Apaga os backups mais antigos, mantendo os `manter` mais novos. So mexe em arquivos com o nome padrao
    de backup desta pasta; qualquer outro arquivo e ignorado."""
    if manter < 1:
        raise ValueError("manter precisa ser pelo menos 1")
    arquivos = sorted((p for p in pasta.iterdir() if p.is_file() and _PADRAO_ARQUIVO.match(p.name)),
                      key=lambda p: p.name)
    antigos = arquivos[:-manter] if len(arquivos) > manter else []
    for p in antigos:
        p.unlink()
    return [p.name for p in antigos]


def salvar(db, pasta: Path, manter: int = 30, agora: datetime | None = None):
    """Gera o backup na pasta, confere o arquivo gravado e aplica a retencao.
    Retorna (caminho, contagens, nomes apagados)."""
    agora = agora or datetime.now()
    pasta.mkdir(parents=True, exist_ok=True)
    dfs = exportar(db)
    caminho = pasta / NOME_ARQUIVO.format(agora)
    caminho.write_bytes(para_bytes(dfs, agora))
    for nome, esperado in contagens(dfs).items():  # confere o que foi realmente gravado
        gravado = len(pd.read_excel(caminho, sheet_name=nome, dtype=str)) if esperado else 0
        if gravado != esperado:
            caminho.unlink()
            raise RuntimeError(f"Backup inconsistente na aba {nome}: {gravado} linhas gravadas, {esperado} esperadas.")
    return caminho, contagens(dfs), rotacionar(pasta, manter)
