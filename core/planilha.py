"""Linha para colar na planilha antiga (fluxo temporario, ate o aplicativo substitui-la por completo)."""
from datetime import date

from core.regras import rotulo_orientacao

# ordem das colunas da planilha: CNPJ/CPF, PRESTADOR, DESVIO, DATA DA ORIENTACAO, QUANTIDADE DE ORIENTACAO,
# ACAO, CREDENCIAMENTO SINALIZADO?


def _celula(valor) -> str:
    """Uma celula nao pode ter tabulacao nem quebra de linha, senao a colagem desloca as colunas."""
    return " ".join(str(valor or "").split())


def linha_da_planilha(item: dict, sinal: str | None = None) -> str:
    """Uma orientacao registrada (dict de `ultimo_registro`) como linha separada por tabulacao."""
    return "\t".join(_celula(c) for c in (
        item["documento"], item["prestador"], item["desvio"],
        date.fromisoformat(item["data"]).strftime("%d/%m/%Y"), rotulo_orientacao(item["numero"]),
        item["acao"], sinal))


def linhas_da_planilha(itens: list[dict], sinal: str | None = None) -> str:
    """Uma linha por desvio registrado; ao colar, cada uma cai numa linha da planilha."""
    return "\n".join(linha_da_planilha(i, sinal) for i in itens)


def item_da_consulta(linha: dict) -> dict:
    """Linha de `orientacoes.listar` no formato de `linha_da_planilha`."""
    return {"documento": linha["documento"], "prestador": linha["prestador"], "desvio": linha["desvio"],
            "data": linha["data_orientacao"], "numero": linha["numero_orientacao"], "acao": linha["acao"]}
