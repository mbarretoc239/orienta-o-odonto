"""Confere a mensagem curta em TODAS as combinacoes de 2 a 10 desvios (2^10 - 10 - 1 = 1013)."""
import re
from itertools import combinations

import pytest

from core import textos

NOMES = list(textos.RESUMOS_PADRAO)  # os 10 desvios, na ordem da planilha


def limite_de_caracteres(quantos: int) -> int:
    """O texto cresce de forma regular: ate ~155 caracteres por desvio acrescentado (o antigo, longo, passava de
    1.500 com so 3 desvios)."""
    return 470 + 155 * quantos


def montar_desvio(i: int, nome: str) -> dict:
    frase, grupo, complemento, trecho = textos.CURTAS_PADRAO[nome]
    return {"id": i, "nome": nome, "texto_padrao": "texto completo", "resumo": textos.RESUMOS_PADRAO[nome],
            "orientacao_curta": frase, "grupo_curto": grupo, "complemento_curto": complemento, "trecho_grupo": trecho,
            "fechamento_tipo": "imagens" if nome in ("FALTA DOCUMENTACAO", "ENVIO DE RAIO X FISICO") else "padrao"}


DESVIOS = [montar_desvio(i, n) for i, n in enumerate(NOMES, start=1)]
COMBINACOES = [c for r in range(2, len(DESVIOS) + 1) for c in combinations(DESVIOS, r)]
GERAIS = textos.GERAIS_PADRAO


def itens_da_lista(msg: str) -> list[str]:
    """Linhas entre a abertura e o fechamento (ja sem a numeracao '1. ', '2. '...)."""
    corpo = msg.split("\n\n")[1].split("\n")[1:]  # [0] saudacao, [1] abertura + lista
    return corpo


def test_sao_1013_combinacoes():
    assert len(COMBINACOES) == 2 ** 10 - 10 - 1 == 1013


@pytest.mark.parametrize("escolhidos", COMBINACOES, ids=lambda c: "-".join(str(d["id"]) for d in c))
def test_cada_combinacao_gera_uma_mensagem_correta(escolhidos):
    msg = textos.montar_mensagem(list(escolhidos), GERAIS)
    ids = {d["id"] for d in escolhidos}

    # estrutura: saudacao, abertura + lista, fechamento
    blocos = msg.split("\n\n")
    assert len(blocos) == 3 and blocos[0] == GERAIS["saudacao"]
    assert msg.count("Caro(a)") == 1

    # abertura cita os resumos dos desvios escolhidos, na ordem
    abertura = blocos[1].split("\n")[0]
    resumos = [d["resumo"] for d in escolhidos]
    assert abertura == GERAIS["abertura_multi"].replace("{desvios}", textos._lista(resumos))
    assert all(d["resumo"] not in abertura for d in DESVIOS if d["id"] not in ids)

    # a frase inteira de cada desvio aparece uma vez quando ele esta sozinho no seu grupo (ou sem grupo); quando ha
    # 2+ do mesmo grupo, vale a frase emendada pelos trechos e a frase inteira nao repete; nao escolhidos: nenhuma
    for d in DESVIOS:
        do_grupo = [x for x in escolhidos if d["grupo_curto"] and x["grupo_curto"] == d["grupo_curto"]]
        inteira = d["id"] in ids and len(do_grupo) <= 1
        assert msg.count(d["orientacao_curta"]) == (1 if inteira else 0), d["nome"]
    for comp in {d["complemento_curto"] for d in DESVIOS if d["complemento_curto"]}:
        esperado = 1 if any(d["complemento_curto"] == comp for d in escolhidos) else 0
        assert msg.count(comp) == esperado

    # no grupo, cada desvio contribui com a sua palavra-chave exatamente uma vez
    palavras = {1: "assinaturas obrigatórias", 2: "carimbar e assinar", 3: "rasurar", 4: "preencher a data",
                7: "no mesmo dia em que for realizado", 8: "dia 05", 9: "correio", 10: "executar corretamente"}
    for d in escolhidos:
        if d["id"] in palavras:
            assert msg.lower().count(palavras[d["id"]].lower()) == 1, d["nome"]

    # itens: numerados em sequencia (ou sem numero se for um so); desvios do mesmo grupo juntos
    grupos = {d["grupo_curto"] for d in escolhidos if d["grupo_curto"]}
    sem_grupo = [d for d in escolhidos if not d["grupo_curto"]]
    esperados = len(grupos) + len(sem_grupo)
    linhas = blocos[1].split("\n")[1:]
    assert len(linhas) == esperados
    if esperados > 1:
        assert [l.split(". ", 1)[0] for l in linhas] == [str(n) for n in range(1, esperados + 1)]
    else:
        assert not re.match(r"^\d+\. ", linhas[0])
    for g in grupos:
        membros = [d for d in escolhidos if d["grupo_curto"] == g]
        assert (f"{g}: " in msg) == (len(membros) > 1)  # rotulo so quando ha mais de um do grupo
        assert msg.count(g) == (1 if len(membros) > 1 else 0)
        if len(membros) > 1:  # o item do grupo e uma frase emendada, sem repetir as mesmas palavras
            item = next(l for l in linhas if g in l)
            assert item.count("guia física") <= 1 and item.count("campo 39") <= 1 and item.count("data de atendimento") <= 1
            sem_numero = re.sub(r"^\d+\. ", "", item)
            frases = re.findall(r"[\w)]\.(?: |$)", sem_numero)  # fim de frase: ponto seguido de espaco ou do fim ('10.1' nao conta)
            assert len(frases) == 1 + len({m["complemento_curto"] for m in membros if m["complemento_curto"]})

    # fechamento: um so, e a variante com imagens so quando 5 (documentacao) ou 6 (raio X) esta na lista
    com_imagens = bool(ids & {5, 6})
    assert blocos[2] == GERAIS["fechamento_multi_imagens" if com_imagens else "fechamento_multi"]
    assert msg.count("Recomendamos") == 1 and ("anexo de imagens" in msg) == com_imagens

    # tipografia: sem espacos duplos, ponto solto, "None", linhas com espaco nas pontas, e termina no fechamento
    assert "  " not in msg and " ." not in msg and ".." not in msg and "None" not in msg
    assert msg == msg.strip() and msg.endswith(blocos[2])
    for linha in msg.split("\n"):
        assert linha == linha.strip()
        if linha:
            assert linha[0].isupper() or linha[0].isdigit(), linha

    # tamanho proporcional ao numero de desvios
    assert len(msg) <= limite_de_caracteres(len(escolhidos)), len(msg)


def test_com_ate_3_desvios_a_mensagem_nunca_e_maior_que_um_desvio_sozinho_no_formato_completo():
    # o texto completo de um unico desvio chega a 884 caracteres
    maior = max(len(textos.montar_mensagem(list(c), GERAIS)) for c in COMBINACOES if len(c) <= 3)
    assert maior <= 884


def test_o_caso_reclamado_ficou_bem_menor_que_o_texto_longo_antigo():
    # documentacao + raio X + rasura media 1.589 caracteres no formato longo
    caso = [d for d in DESVIOS if d["id"] in (3, 5, 6)]
    assert len(textos.montar_mensagem(caso, GERAIS)) < 850
