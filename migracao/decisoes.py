"""Decisoes manuais sobre datas da planilha. Tem precedencia sobre a regra automatica de migracao/datas.py.

Chave: numero da linha no Excel. Valor: (data certa, justificativa).
"""
from datetime import date

_BLOCO_JULHO = ("bloco das linhas 809-815 em julho: os dias só crescem (08, 08, 08, 09, 09, 10, 10) e a linha "
                "816, do mesmo prestador da 815, é 13/07 com certeza")

_ULTIMA_LINHA = ("última linha da planilha, recebida em 07/10/2026, logo depois da linha 1190 (07/10): a pessoa "
                 "digitou 07/11 querendo 07/10 (07/11 seria no futuro)")

_TECLA = ("as linhas 510 e 511, logo acima, estão em 11/05/2026: a pessoa digitou 11/02 querendo 11/05 "
          "(o 2 e o 5 ficam lado a lado no teclado)")

DATAS_MANUAIS: dict[int, tuple[date, str]] = {
    512: (date(2026, 5, 11), _TECLA),
    1191: (date(2026, 10, 7), _ULTIMA_LINHA),
    809: (date(2026, 7, 8), _BLOCO_JULHO),
    810: (date(2026, 7, 8), _BLOCO_JULHO),
    811: (date(2026, 7, 8), _BLOCO_JULHO),
    812: (date(2026, 7, 9), _BLOCO_JULHO),
    813: (date(2026, 7, 9), _BLOCO_JULHO),
}
