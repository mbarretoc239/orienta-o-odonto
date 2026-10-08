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


def curto(nome, frase, grupo=None, complemento=None, tipo="padrao", trecho=None):
    return {"nome": nome, "texto_padrao": "x", "resumo": nome.lower(), "orientacao_curta": frase,
            "grupo_curto": grupo, "complemento_curto": complemento, "fechamento_tipo": tipo, "trecho_grupo": trecho}


A = curto("DESVIO A", "Fazer A.")
B = curto("DESVIO B", "Fazer B.")
GA = curto("GRUPO 1", "Fazer G1.", grupo="Tema", complemento="Antes, preparar.", trecho="fazer g1")
GB = curto("GRUPO 2", "Fazer G2.", grupo="Tema", complemento="Antes, preparar.", trecho="fazer g2")


def test_versao_curta_numera_os_itens_e_traz_um_fechamento_so():
    m = textos.montar_mensagem([A, B], textos.GERAIS_PADRAO)
    assert m == ("Caro(a) prestador(a),\n\nIdentificamos pendências referentes a desvio a e desvio b. Orientamos:\n"
                 "1. Fazer A.\n2. Fazer B.\n\n" + textos.GERAIS_PADRAO["fechamento_multi"])
    assert m.count("Recomendamos") == 1 and m.count("Caro(a)") == 1


def test_desvios_do_mesmo_grupo_viram_um_item_com_os_trechos_emendados_e_o_complemento_uma_vez():
    m = textos.montar_mensagem([GA, A, GB], textos.GERAIS_PADRAO)
    assert "1. Tema: fazer g1 e fazer g2. Antes, preparar.\n2. Fazer A." in m
    assert m.count("Antes, preparar.") == 1 and "Fazer G1." not in m  # no grupo, a frase inteira nao repete


def test_um_so_item_nao_leva_numero_e_um_so_membro_do_grupo_nao_leva_rotulo():
    m = textos.montar_mensagem([GA, GB], textos.GERAIS_PADRAO)
    assert "Orientamos:\nTema: fazer g1 e fazer g2. Antes, preparar.\n\n" in m
    assert not any(l.startswith(("1. ", "2. ")) for l in m.splitlines())  # um item so: sem numeracao
    m = textos.montar_mensagem([GA, A], textos.GERAIS_PADRAO)
    assert "1. Fazer G1. Antes, preparar.\n2. Fazer A." in m  # so um do grupo: frase inteira, sem 'Tema:'


def test_tres_do_mesmo_grupo_usam_virgula_e_e():
    g3 = curto("GRUPO 3", "Fazer G3.", grupo="Tema", trecho="fazer g3")
    m = textos.montar_mensagem([GA, GB, g3], textos.GERAIS_PADRAO)
    assert "Tema: fazer g1, fazer g2 e fazer g3. Antes, preparar." in m


def test_trechos_que_terminam_igual_sao_fundidos():
    fundir = textos._fundir_trechos
    assert fundir(["não rasurar a data de atendimento", "preencher a data de atendimento"]) == [
        "não rasurar e preencher a data de atendimento"]
    assert fundir(["colher x (campos 40 e 50)", "carimbar e assinar (campo 49)"]) == [
        "colher x (campos 40 e 50)", "carimbar e assinar (campo 49)"]  # finais diferentes: nada muda
    assert fundir(["a b", "c b"]) == ["a b", "c b"]  # final igual curto demais (menos de 3 palavras)
    assert fundir(["ligar", "não rasurar a data de atendimento", "preencher a data de atendimento"]) == [
        "ligar", "não rasurar e preencher a data de atendimento"]


def test_membro_do_grupo_sem_trecho_entra_com_a_frase_inteira():
    sem_trecho = curto("GRUPO 3", "Fazer G3.", grupo="Tema")
    m = textos.montar_mensagem([GA, sem_trecho], textos.GERAIS_PADRAO)
    assert "Tema: fazer g1. Fazer G3. Antes, preparar." in m
    so_frases = textos.montar_mensagem([sem_trecho, curto("GRUPO 4", "Fazer G4.", grupo="Tema")], textos.GERAIS_PADRAO)
    assert "Fazer G3. Fazer G4." in so_frases and "Tema:" not in so_frases  # sem trechos: sem rotulo


def test_fechamento_com_imagens_quando_algum_desvio_pede():
    m = textos.montar_mensagem([curto("RAIO X", "Subir a imagem.", tipo="imagens"), A], textos.GERAIS_PADRAO)
    assert "execução dos procedimentos e anexo de imagens:" in m
    assert "anexo de imagens" not in textos.montar_mensagem([A, B], textos.GERAIS_PADRAO)


def test_textos_editados_na_administracao_valem():
    gerais = {**textos.GERAIS_PADRAO, "fechamento_multi": "FECHO NOVO", "abertura_multi": "Pontos: {desvios}."}
    m = textos.montar_mensagem([A, B], gerais)
    assert "Pontos: desvio a e desvio b." in m and m.endswith("FECHO NOVO")


def test_desvio_sem_orientacao_curta_usa_o_titulo_e_depois_o_nome():
    com_titulo = {"nome": "N1", "texto_padrao": "x", "titulo": "Titulo do texto", "orientacao_curta": None}
    sem_nada = {"nome": "N2", "texto_padrao": "x"}
    m = textos.montar_mensagem([com_titulo, sem_nada], textos.GERAIS_PADRAO)
    assert "1. Titulo do texto\n2. N2" in m


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
    assert {r["chave"] for r in banco.query("SELECT chave FROM ori_textos")} >= set(textos.GERAIS_PADRAO)
    assert (d["orientacao_curta"], d["grupo_curto"]) == (
        textos.CURTAS_PADRAO["MALOTE POSTADO FORA DO PRAZO CONTRATUAL"][0], "Prazo do malote")
    desvios.atualizar(banco, d["id"], MALOTE, True, "resumo editado", "Titulo novo", "corpo novo", "imagens")
    textos.preencher_estrutura(banco)  # nao sobrescreve o que foi editado
    d = desvios.listar(banco)[0]
    assert (d["resumo"], d["titulo"], d["corpo"], d["fechamento_tipo"]) == (
        "resumo editado", "Titulo novo", "corpo novo", "imagens")


def test_orientacao_do_forms_vem_preenchida_e_nao_sobrescreve_edicao(banco):
    textos.preencher_estrutura(banco)
    d = desvios.listar(banco)[0]
    assert d["orientacao_forms"] == textos.ORIENTACOES_FORMS_PADRAO["MALOTE POSTADO FORA DO PRAZO CONTRATUAL"]
    desvios.atualizar(banco, d["id"], MALOTE, True, d["resumo"], d["titulo"], d["corpo"], d["fechamento_tipo"], "")
    textos.preencher_estrutura(banco)  # vazio de proposito: nao volta o padrao
    assert desvios.listar(banco)[0]["orientacao_forms"] == ""


def test_orientacao_curta_editada_ou_apagada_de_proposito_nao_volta_ao_padrao(banco):
    textos.preencher_estrutura(banco)
    d = desvios.listar(banco)[0]
    desvios.atualizar(banco, d["id"], MALOTE, True, d["resumo"], d["titulo"], d["corpo"], d["fechamento_tipo"],
                      d["orientacao_forms"], "Frase minha.", None, None)
    textos.preencher_estrutura(banco)
    d = desvios.listar(banco)[0]
    assert (d["orientacao_curta"], d["grupo_curto"]) == ("Frase minha.", None)


def test_todos_os_desvios_da_planilha_tem_orientacao_padrao():
    nomes = set(textos.RESUMOS_PADRAO)
    assert nomes == set(textos.ORIENTACOES_FORMS_PADRAO) == set(textos.CURTAS_PADRAO)
    assert all(not f.endswith(".") and f[0].islower() for f in textos.ORIENTACOES_FORMS_PADRAO.values())
    assert all(c[0].endswith(".") and c[0][0].isupper() for c in textos.CURTAS_PADRAO.values())


def test_textos_gerais_editaveis(banco):
    textos.preencher_estrutura(banco)
    textos.salvar_gerais(banco, {"saudacao": "Olá,", "chave_invalida": "x"})
    g = textos.carregar_gerais(banco)
    assert g["saudacao"] == "Olá," and "chave_invalida" not in g
    assert g["fechamento_multi"] == textos.GERAIS_PADRAO["fechamento_multi"]


def test_adicionar_desvio_ja_preenche_a_estrutura(banco):
    ok, _ = desvios.adicionar(banco, "desvio novo", "Caro(a) prestador(a),\nTitulo qualquer\nCorpo do texto.")
    assert ok
    novo = [d for d in desvios.listar(banco) if d["nome"] == "DESVIO NOVO"][0]
    assert novo["titulo"] == "Titulo qualquer" and novo["corpo"] == "Corpo do texto." and novo["resumo"] == "desvio novo"
