"""Deteccao de datas com dia e mes trocados (o Excel leu dd/mm como mm/dd).

Uma data real do Excel com dia <= 12 e dia != mes e ambigua: pode ser a data certa ou a trocada. A planilha foi
preenchida em ordem cronologica, entao a vizinhanca (linhas anteriores ja resolvidas e proximas datas sem
ambiguidade) indica qual das duas e a certa. Nada aqui grava no banco: so sugere.
"""
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from statistics import median

ALTA, MEDIA, BAIXA = "alta", "média", "baixa"
MARGEM_ALTA, MARGEM_MEDIA = 60, 20  # dias de diferenca entre as duas hipoteses
DESTOA_DIAS = 60  # a data escolhida a mais que isto (em media) das vizinhas vai para revisao
ANCORAS = 3


@dataclass
class Linha:
    linha: int
    data: date | None  # data como o sistema leu
    ambigua: bool


@dataclass
class Sugestao:
    linha: int
    sugerida: date | None
    confianca: str
    motivo: str


def linhas_da_planilha(registros) -> tuple[list[Linha], dict[int, date]]:
    """`registros`: pares (numero da linha no Excel, valor bruto da celula de data), so das linhas com desvio.
    Devolve as linhas (com a ambiguidade marcada) e as datas que tiveram erro de digitacao corrigido."""
    from migracao import limpeza

    linhas, corrigidas = [], {}
    for numero, bruto in registros:
        iso, corrigida = limpeza.parse_data(bruto)
        d = date.fromisoformat(iso) if iso else None
        texto = isinstance(bruto, str) and "/" in bruto
        linhas.append(Linha(numero, d, bool(d) and e_ambigua(d, texto)))
        if corrigida:
            corrigidas[numero] = d
    return linhas, corrigidas


def e_ambigua(d: date, veio_de_texto: bool) -> bool:
    """So datas reais do Excel (nao digitadas como texto) com dia ate 12 podem ter sido trocadas."""
    return (not veio_de_texto) and d.day <= 12 and d.day != d.month


def trocada(d: date) -> date:
    return date(d.year, d.day, d.month)


def _mediana(datas: list[date]) -> date | None:
    return date.fromordinal(int(median(x.toordinal() for x in datas))) if datas else None


def _custo(candidata: date, anteriores: date | None, seguintes: date | None) -> int | None:
    partes = [abs((candidata - ref).days) for ref in (anteriores, seguintes) if ref]
    return sum(partes) if partes else None


def resolver(linhas: list[Linha], hoje: date, ancoras_n: int = ANCORAS) -> dict[int, Sugestao]:
    """Sugere a data de cada linha ambigua, na ordem da planilha. `ancoras_n`: quantas vizinhas comparar."""
    claras = [(x.linha, x.data) for x in linhas if x.data and not x.ambigua]
    numeros_claros = [n for n, _ in claras]
    ancoras: list[date] = []  # datas ja resolvidas (claras e ambiguas de confianca alta/media), em ordem
    saida: dict[int, Sugestao] = {}
    for x in sorted(linhas, key=lambda y: y.linha):
        if not x.data:
            continue
        if not x.ambigua:
            ancoras.append(x.data)
            continue
        a, b = x.data, trocada(x.data)
        i = bisect_right(numeros_claros, x.linha)
        seguintes = _mediana([d for _, d in claras[i:i + ancoras_n]])
        anteriores = _mediana(ancoras[-ancoras_n:])

        def destoa(candidata: date) -> bool:
            """A candidata fica longe das vizinhas (possivel erro de ano ou de digitacao)."""
            refs = [r for r in (anteriores, seguintes) if r]
            return bool(refs) and sum(abs((candidata - r).days) for r in refs) / len(refs) > DESTOA_DIAS

        validas = [c for c in (a, b) if c <= hoje]
        if len(validas) == 1:
            unica = validas[0]
            motivo = ("data no futuro: a troca de dia e mês dá uma data possível" if unica == b
                      else "a troca de dia e mês daria uma data no futuro")
            if destoa(unica):
                saida[x.linha] = Sugestao(x.linha, unica, BAIXA, motivo + ", mas destoa das linhas vizinhas: conferir")
            else:
                saida[x.linha] = Sugestao(x.linha, unica, ALTA, motivo)
                ancoras.append(unica)
            continue
        if not validas:
            saida[x.linha] = Sugestao(x.linha, a, BAIXA, "as duas hipóteses caem no futuro")
            continue
        ca, cb = _custo(a, anteriores, seguintes), _custo(b, anteriores, seguintes)
        if ca is None:
            saida[x.linha] = Sugestao(x.linha, a, BAIXA, "sem linhas vizinhas para comparar")
            continue
        escolhida, margem = (a, cb - ca) if ca <= cb else (b, ca - cb)
        if destoa(escolhida):
            saida[x.linha] = Sugestao(
                x.linha, a, BAIXA,
                "nenhuma das duas leituras combina com as vizinhas (possível erro de ano ou digitação): "
                "mantida a data lida")
            continue
        confianca = ALTA if margem >= MARGEM_ALTA else MEDIA if margem >= MARGEM_MEDIA else BAIXA
        motivo = ("a data lida combina com as vizinhas" if escolhida == a
                  else "dia e mês trocados: a outra leitura combina com as vizinhas")
        saida[x.linha] = Sugestao(x.linha, escolhida, confianca, f"{motivo} (diferença de {margem} dias)")
        if confianca != BAIXA:
            ancoras.append(escolhida)
    return saida


def sugerir_sem_data(linhas: list[Linha], numero: int) -> Sugestao:
    """Linha sem data: usa as vizinhas da planilha (2 antes e 2 depois, com data)."""
    com_data = sorted((x for x in linhas if x.data), key=lambda y: y.linha)
    antes = [x.data for x in com_data if x.linha < numero][-2:]
    depois = [x.data for x in com_data if x.linha > numero][:2]
    viz = antes + depois
    if not viz:
        return Sugestao(numero, None, BAIXA, "sem vizinhas com data")
    escolhida = _mediana(viz)
    iguais = len(set(viz)) == 1
    return Sugestao(numero, escolhida, ALTA if iguais else MEDIA,
                    "vizinhas da planilha (2 antes e 2 depois) na mesma data" if iguais
                    else "mediana das vizinhas da planilha (2 antes e 2 depois)")
