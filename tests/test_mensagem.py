import pytest

from core import desvios, textos
from core.db import LocalDb, criar_schema

FECHO = ("Recomendamos fortemente a utilização do aplicativo para execução dos procedimentos. Com ele, você "
         "elimina a necessidade de envio de malotes físicos, assegurando maior agilidade na auditoria e no "
         "pagamento da sua produção. Além disso, o uso do aplicativo gera economia com impressão e postagem, "
         "tornando o processo mais rápido, seguro e eficiente.")
FECHO_IMG = FECHO.replace("procedimentos.", "procedimentos e anexo de imagens.")

GUIA = ("Caro(a) prestador(a),\nAtenção ao correto preenchimento da guia física\n"
        "•\tAs guias devem conter as assinaturas obrigatórias:\n"
        "o\tBeneficiário ou responsável: campos 40 e 50\no\tPrestador: campo 49\n"
        "•\tOs procedimentos devem ser executados no sistema antes da impressão da guia.\n"
        "O preenchimento incorreto ou incompleto pode gerar pendências na auditoria e atraso no pagamento.\n" + FECHO)
MALOTE = ("Caro(a) prestador(a),\nEvite atrasos no pagamento da sua produção\n"
          "Fique atento aos prazos estabelecidos em contrato.\n" + FECHO)
RAIOX = ("CARO(A) PRESTADOR(A),\nREALIZE O UPLOAD DA IMAGEM RADIOGRÁFICA NO SISTEMA.\n"
         "EVITE PERDAS, EXTRAVIOS E DANOS NO TRANSPORTE DE RADIOGRAFIAS FÍSICAS.\n" + FECHO_IMG.upper())
SO_APP = ("Caro(a) prestador(a),\nEvite atrasos na entrega dos serviços postais.\n"
          "Com essa ferramenta, você elimina a necessidade de enviar malotes físicos.")


def desvio(nome, texto):
    e = textos.estruturar(texto)
    return {"nome": nome, "texto_padrao": texto, "resumo": nome.lower(), **e}


G1, G3 = desvio("DESVIO GUIA 1", GUIA), desvio("DESVIO GUIA 2", GUIA)
MAL, RX, APP = desvio("MALOTE", MALOTE), desvio("RAIO X", RAIOX), desvio("SO APP", SO_APP)


def test_estruturar_guia_limpa_marcadores_e_separa_fechamento():
    e = textos.estruturar(GUIA)
    assert e["titulo"] == "Atenção ao correto preenchimento da guia física"
    assert "\t" not in e["corpo"] and "• As guias devem" in e["corpo"]
    assert "   – Prestador: campo 49" in e["corpo"]
    assert "Recomendamos" not in e["corpo"] and e["fechamento_tipo"] == "padrao"


def test_estruturar_texto_em_maiusculas_vira_caixa_normal():
    e = textos.estruturar(RAIOX)
    assert e["titulo"] == "Realize o upload da imagem radiográfica no sistema."
    assert e["corpo"].startswith("Evite perdas, extravios") and e["fechamento_tipo"] == "imagens"


def test_estruturar_texto_so_com_titulo():
    e = textos.estruturar(SO_APP)
    assert e["titulo"] == "Evite atrasos na entrega dos serviços postais." and e["corpo"] == ""
    assert e["fechamento_tipo"] == "padrao"


def test_um_desvio_mantem_o_texto_original():
    assert textos.montar_mensagem([MAL], textos.GERAIS_PADRAO) == MALOTE.strip()


def test_desvios_com_o_mesmo_texto_aparecem_uma_vez():
    m = textos.montar_mensagem([G1, G3], textos.GERAIS_PADRAO)
    assert m.count("Atenção ao correto preenchimento da guia física") == 1
    assert "desvio guia 1 e desvio guia 2" in m
    assert "1. " not in m  # uma unica orientacao: sem numeracao


def test_mensagem_com_orientacoes_diferentes_e_fechamento_unico():
    m = textos.montar_mensagem([G1, MAL, G3], textos.GERAIS_PADRAO)
    assert m.startswith("Caro(a) prestador(a),\n\nIdentificamos pendências referentes a desvio guia 1, malote e "
                        "desvio guia 2. Seguem as orientações:")
    assert "1. Atenção ao correto" in m and "2. Evite atrasos no pagamento" in m and "3. " not in m
    assert m.count("Recomendamos fortemente") == 1 and m.endswith("seguro e eficiente.")
    assert m.count("Caro(a)") == 1


def test_fechamento_com_imagens_quando_algum_desvio_pede():
    m = textos.montar_mensagem([RX, MAL], textos.GERAIS_PADRAO)
    assert "execução dos procedimentos e anexo de imagens." in m


def test_fechamento_usa_o_texto_editado_na_administracao():
    gerais = {**textos.GERAIS_PADRAO, "fechamento": "FECHO NOVO", "abertura": "Pontos: {desvios}."}
    m = textos.montar_mensagem([MAL, APP], gerais)
    assert "Pontos: malote e so app." in m and m.endswith("FECHO NOVO")


def test_desvio_sem_estrutura_usa_o_nome():
    solto = {"nome": "NOVO DESVIO", "texto_padrao": "x", "titulo": None, "corpo": None}
    assert "1. NOVO DESVIO" in textos.montar_mensagem([solto, MAL], textos.GERAIS_PADRAO)


@pytest.fixture
def banco():
    d = LocalDb(":memory:")
    criar_schema(d)
    d.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('MALOTE POSTADO FORA DO PRAZO CONTRATUAL', ?)",
              (MALOTE,))
    return d


def test_preencher_estrutura_e_idempotente_e_respeita_edicao(banco):
    textos.preencher_estrutura(banco)
    d = desvios.listar(banco)[0]
    assert d["resumo"] == "malote postado fora do prazo contratual"
    assert d["titulo"] == "Evite atrasos no pagamento da sua produção" and d["fechamento_tipo"] == "padrao"
    assert len(banco.query("SELECT * FROM ori_textos")) == 4
    desvios.atualizar(banco, d["id"], MALOTE, True, "resumo editado", "Titulo novo", "corpo novo", "imagens")
    textos.preencher_estrutura(banco)  # nao sobrescreve o que foi editado
    d = desvios.listar(banco)[0]
    assert (d["resumo"], d["titulo"], d["corpo"], d["fechamento_tipo"]) == (
        "resumo editado", "Titulo novo", "corpo novo", "imagens")


def test_textos_gerais_editaveis(banco):
    textos.preencher_estrutura(banco)
    textos.salvar_gerais(banco, {"saudacao": "Olá,", "chave_invalida": "x"})
    g = textos.carregar_gerais(banco)
    assert g["saudacao"] == "Olá," and "chave_invalida" not in g and g["fechamento"] == textos.GERAIS_PADRAO["fechamento"]


def test_adicionar_desvio_ja_preenche_a_estrutura(banco):
    ok, _ = desvios.adicionar(banco, "desvio novo", "Caro(a) prestador(a),\nTitulo qualquer\nCorpo do texto.")
    assert ok
    novo = [d for d in desvios.listar(banco) if d["nome"] == "DESVIO NOVO"][0]
    assert novo["titulo"] == "Titulo qualquer" and novo["corpo"] == "Corpo do texto." and novo["resumo"] == "desvio novo"
