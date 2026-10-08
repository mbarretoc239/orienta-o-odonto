"""Textos montados a partir dos dados do registro: relato do FORMS e mensagem ao prestador."""
import re
import unicodedata
from datetime import date

from core.regras import formatar_documento, rotulo_orientacao

_FECHAMENTO_MULTI = ("Recomendamos fortemente o uso do aplicativo para execução dos procedimentos{extra}: ele "
                     "elimina o envio de malotes físicos e agiliza a auditoria e o pagamento da sua produção.")

# Textos da mensagem com mais de um desvio (versao curta). Com um desvio so, vale o texto padrao dele, inteiro.
GERAIS_PADRAO = {
    "saudacao": "Caro(a) prestador(a),",
    "abertura_multi": "Identificamos pendências referentes a {desvios}. Orientamos:",
    "fechamento_multi": _FECHAMENTO_MULTI.format(extra=""),
    "fechamento_multi_imagens": _FECHAMENTO_MULTI.format(extra=" e anexo de imagens"),
}

_COMPLEMENTO_DATA = ("Executar o procedimento no sistema antes de imprimir a guia, para que o campo 39 seja "
                     "preenchido automaticamente.")
_GRUPO_GUIA = "Preenchimento da guia física"
_GRUPO_MALOTE = "Prazo do malote"

_GRUPO_EXECUCAO = "Execução no sistema"
_COMPLEMENTO_EXECUCAO = "Isso garante a cobrança correta e evita glosas."
_COMPLEMENTO_MALOTE = "O aplicativo ajuda nesse ponto por dispensar o envio físico."

# Orientacao curta de cada desvio para a mensagem com varios: (frase, grupo, complemento, trecho).
# - frase: o item da lista quando o desvio aparece sozinho no seu grupo;
# - grupo: desvios do mesmo grupo viram UM item; com 2 ou mais, usam-se os `trecho`s, emendados numa frase so
#   (trechos que terminam igual sao fundidos: "nao rasurar" + "preencher a data" -> "nao rasurar e preencher a data");
# - complemento: frase extra que aparece uma vez por item.
CURTAS_PADRAO = {
    "FALTA ASSINATURA DO USUARIO/RESPONSAVEL": (
        "Colher as assinaturas obrigatórias do beneficiário ou responsável na guia física (campos 40 e 50).",
        _GRUPO_GUIA, None, "colher as assinaturas obrigatórias do beneficiário ou responsável (campos 40 e 50)"),
    "FALTA CARIMBO/ASSINATURA DO CREDENCIADO": (
        "Carimbar e assinar a guia física (campo 49).", _GRUPO_GUIA, None, "carimbar e assinar (campo 49)"),
    "RASURA NA DATA DE ATENDIMENTO": (
        "Não rasurar a data de atendimento.", _GRUPO_GUIA, _COMPLEMENTO_DATA, "não rasurar a data de atendimento"),
    "FALTA DATA DO ATENDIMENTO": (
        "Preencher a data de atendimento.", _GRUPO_GUIA, _COMPLEMENTO_DATA, "preencher a data de atendimento"),
    "FALTA DOCUMENTACAO": (
        "Enviar fisicamente as guias executadas pelo Portal do Dentista, preenchidas, assinadas e sem rasuras. "
        "A falta da guia física ou o preenchimento incorreto pode gerar glosas e atrasos no pagamento.",
        None, None, None),
    "ENVIO DE RAIO X FISICO": (
        "Fazer o upload da imagem radiográfica no sistema, evitando perdas, extravios e danos no transporte das "
        "radiografias físicas.", None, None, None),
    "DATA DE ATENDIMENTO POSTERIOR AO PERIODO ANALISADO": (
        "Registrar o procedimento no sistema no mesmo dia em que for realizado.", _GRUPO_EXECUCAO,
        _COMPLEMENTO_EXECUCAO, "registrar cada procedimento no sistema no mesmo dia em que for realizado"),
    "MALOTE POSTADO FORA DO PRAZO CONTRATUAL": (
        "Postar a produção física até o dia 05 de cada mês, conforme a Cláusula 10, item 10.1 do contrato.",
        _GRUPO_MALOTE, None, "postar a produção física até o dia 05 de cada mês (Cláusula 10, item 10.1 do contrato)"),
    "MALOTE ENTREGUE APOS DIA 20": (
        "Atentar-se aos prazos de envio do malote, que depende do correio.", _GRUPO_MALOTE, _COMPLEMENTO_MALOTE,
        "atentar-se aos prazos de envio do malote, que depende do correio"),
    "FALTA EXECUCAO DO PROCEDIMENTO": (
        "Executar corretamente os procedimentos no sistema.", _GRUPO_EXECUCAO, _COMPLEMENTO_EXECUCAO,
        "executar corretamente os procedimentos"),
}

# Frase usada na abertura da mensagem com mais de um desvio (editavel na tela de Administracao).
RESUMOS_PADRAO = {
    "FALTA ASSINATURA DO USUARIO/RESPONSAVEL": "falta de assinatura do usuário/responsável",
    "FALTA CARIMBO/ASSINATURA DO CREDENCIADO": "falta de carimbo/assinatura do credenciado",
    "RASURA NA DATA DE ATENDIMENTO": "rasura na data de atendimento",
    "FALTA DATA DO ATENDIMENTO": "falta da data do atendimento",
    "FALTA DOCUMENTACAO": "falta de documentação",
    "ENVIO DE RAIO X FISICO": "envio de raio X físico",
    "DATA DE ATENDIMENTO POSTERIOR AO PERIODO ANALISADO": "data de atendimento posterior ao período analisado",
    "MALOTE POSTADO FORA DO PRAZO CONTRATUAL": "malote postado fora do prazo contratual",
    "MALOTE ENTREGUE APOS DIA 20": "malote entregue após o dia 20",
    "FALTA EXECUCAO DO PROCEDIMENTO": "falta de execução do procedimento",
}


def _sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).upper().split())


def _data_br(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _lista(itens: list[str]) -> str:
    """'a', 'a e b' ou 'a, b e c'."""
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


# ---------- relato do FORMS ----------

# Frase curta do que o credenciamento deve orientar ao prestador em cada desvio (editavel na Administracao).
ORIENTACOES_FORMS_PADRAO = {
    "FALTA ASSINATURA DO USUARIO/RESPONSAVEL":
        "colher as assinaturas obrigatórias do beneficiário ou responsável na guia física (campos 40 e 50)",
    "FALTA CARIMBO/ASSINATURA DO CREDENCIADO": "carimbar e assinar a guia (campo 49)",
    "RASURA NA DATA DE ATENDIMENTO": "não rasurar a data de atendimento (campo 39), executando o procedimento "
                                     "no sistema antes de imprimir a guia",
    "FALTA DATA DO ATENDIMENTO": "preencher a data de atendimento (campo 39), executando o procedimento "
                                 "no sistema antes de imprimir a guia",
    "FALTA DOCUMENTACAO": "enviar fisicamente as guias executadas pelo Portal do Dentista, preenchidas, "
                          "assinadas e sem rasuras",
    "ENVIO DE RAIO X FISICO": "fazer o upload da imagem radiográfica no sistema, em vez de enviar a "
                              "radiografia física",
    "DATA DE ATENDIMENTO POSTERIOR AO PERIODO ANALISADO":
        "executar o procedimento no sistema no mesmo dia da realização",
    "MALOTE POSTADO FORA DO PRAZO CONTRATUAL":
        "postar a produção física até o dia 05 de cada mês (cláusula 10, item 10.1 do contrato)",
    "MALOTE ENTREGUE APOS DIA 20":
        "atentar-se aos prazos de envio do malote, que depende do correio, lembrando que o aplicativo ajuda "
        "nesse ponto por dispensar o envio físico",
    "FALTA EXECUCAO DO PROCEDIMENTO":
        "executar corretamente os procedimentos no sistema, para garantir a cobrança adequada",
}


def relato_forms(nome: str, documento: str, itens: list[dict]) -> str:
    """Texto do relato do FORMS, em texto corrido (o campo do formulario nao aceita topicos nem quebras de
    linha): identifica o prestador e os desvios cobertos por aquele formulario e diz o que o credenciamento
    deve orientar. `itens`: dicts com `desvio`, `numero`, `data` (ISO) e, opcionalmente, `orientacao`."""
    tipo = "CPF" if len(documento) == 11 else "CNPJ"
    cabecalho = f"Prestador {nome} ({tipo} {formatar_documento(documento)})"
    mesma_data = len(itens) > 1 and len({i["data"] for i in itens}) == 1
    if mesma_data:
        partes = [f'a {rotulo_orientacao(i["numero"])} pelo desvio "{i["desvio"]}"' for i in itens]
        recebeu = f"recebeu, em {_data_br(itens[0]['data'])}, {_lista(partes)}"
    else:
        partes = [f'a {rotulo_orientacao(i["numero"])} pelo desvio "{i["desvio"]}" em {_data_br(i["data"])}'
                  for i in itens]
        recebeu = f"recebeu {_lista(partes)}"
    texto = f"{cabecalho} {recebeu}."
    orientacoes = list(dict.fromkeys(  # sem repetir frases iguais, na ordem dos desvios
        (i.get("orientacao") or "").strip().rstrip(".") for i in itens if (i.get("orientacao") or "").strip()))
    if len(orientacoes) == 1:
        texto += f" Orientar o prestador a {orientacoes[0]}."
    elif orientacoes:
        numeradas = "; ".join(f"({n}) {o}" for n, o in enumerate(orientacoes, start=1))
        texto += f" Orientar o prestador a: {numeradas}."
    return texto


# ---------- mensagem ao prestador ----------

def _predominio_de_maiusculas(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.9


def _caixa_de_frase(linha: str) -> str:
    return re.sub(r"(^|[.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), linha.lower())


def _limpar_marcador(bruta: str) -> str:
    s = bruta.strip()
    if s.startswith("•"):
        return "• " + s[1:].strip()
    if re.match(r"^o\t", bruta.lstrip(" ")):
        return "   – " + bruta.lstrip(" ")[2:].strip()
    return s


def estruturar(texto: str) -> dict:
    """Separa um texto padrao em titulo, corpo e tipo de fechamento ('padrao', 'imagens' ou None).
    Saudacao e paragrafo final sobre o aplicativo saem do texto: viram partes unicas da mensagem."""
    caixa = _predominio_de_maiusculas(texto)
    linhas = [_limpar_marcador(b) for b in texto.splitlines() if b.strip()]
    if caixa:
        linhas = [_caixa_de_frase(linha) for linha in linhas]
    if linhas and linhas[0].lower().startswith("caro"):
        linhas = linhas[1:]
    fechamento, restante = None, []
    for linha in linhas:
        baixo = linha.lower()
        if baixo.startswith("recomendamos fortemente"):
            fechamento = "imagens" if "anexo de imagens" in baixo else "padrao"
        elif baixo.startswith("com essa ferramenta"):
            fechamento = fechamento or "padrao"
        else:
            restante.append(linha)
    return {"titulo": restante[0] if restante else "", "corpo": "\n".join(restante[1:]),
            "fechamento_tipo": fechamento}


def preencher_estrutura(db) -> None:
    """Preenche (so onde ainda esta vazio) resumo, titulo, corpo e fechamento de cada desvio e cria os textos
    gerais padrao. Idempotente; os valores editados na Administracao nao sao sobrescritos."""
    comandos = []
    for d in db.query("SELECT id, nome, texto_padrao FROM ori_desvios WHERE titulo IS NULL"):
        e = estruturar(d["texto_padrao"])
        resumo = RESUMOS_PADRAO.get(_sem_acento(d["nome"])) or d["nome"].lower()
        comandos.append((
            "UPDATE ori_desvios SET resumo=COALESCE(resumo, ?), titulo=?, corpo=?, fechamento_tipo=? WHERE id=?",
            (resumo, e["titulo"], e["corpo"], e["fechamento_tipo"], d["id"]),
        ))
    for d in db.query("SELECT id, nome FROM ori_desvios WHERE orientacao_forms IS NULL"):
        frase = ORIENTACOES_FORMS_PADRAO.get(_sem_acento(d["nome"]))
        if frase:
            comandos.append(("UPDATE ori_desvios SET orientacao_forms=? WHERE id=? AND orientacao_forms IS NULL",
                             (frase, d["id"])))
    for d in db.query("SELECT id, nome FROM ori_desvios WHERE orientacao_curta IS NULL"):
        curta = CURTAS_PADRAO.get(_sem_acento(d["nome"]))
        if curta:  # desvio novo, sem frase padrao: fica NULL e a mensagem usa o titulo do texto
            comandos.append(("UPDATE ori_desvios SET orientacao_curta=?, grupo_curto=?, complemento_curto=?, "
                             "trecho_grupo=? WHERE id=? AND orientacao_curta IS NULL", (*curta, d["id"])))
    for d in db.query("SELECT id, nome FROM ori_desvios WHERE trecho_grupo IS NULL AND orientacao_curta IS NOT NULL"):
        trecho = (CURTAS_PADRAO.get(_sem_acento(d["nome"])) or (None,) * 4)[3]
        if trecho:  # coluna criada depois da frase curta: completa so quem ainda nao tem trecho
            comandos.append(("UPDATE ori_desvios SET trecho_grupo=? WHERE id=? AND trecho_grupo IS NULL",
                             (trecho, d["id"])))
    existentes = {r["chave"] for r in db.query("SELECT chave FROM ori_textos")}
    comandos += [("INSERT OR IGNORE INTO ori_textos (chave, valor) VALUES (?,?)", (k, v))
                 for k, v in GERAIS_PADRAO.items() if k not in existentes]
    if comandos:
        db.batch(comandos)


def carregar_gerais(db) -> dict:
    gerais = dict(GERAIS_PADRAO)
    gerais.update({r["chave"]: r["valor"] for r in db.query("SELECT chave, valor FROM ori_textos")})
    return gerais


def salvar_gerais(db, valores: dict) -> None:
    db.batch([("INSERT INTO ori_textos (chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET "
               "valor=excluded.valor", (k, v)) for k, v in valores.items() if k in GERAIS_PADRAO])


def _fundir_trechos(trechos: list[str]) -> list[str]:
    """Junta trechos vizinhos que terminam igual (3 palavras ou mais): 'nao rasurar a data de atendimento' +
    'preencher a data de atendimento' -> 'nao rasurar e preencher a data de atendimento'."""
    saida: list[str] = []
    for trecho in trechos:
        if saida:
            anterior, atual = saida[-1].split(), trecho.split()
            n = 0
            while n < min(len(anterior), len(atual)) and anterior[-1 - n] == atual[-1 - n]:
                n += 1
            if n >= 3 and len(anterior) > n and len(atual) > n:
                saida[-1] = " ".join(anterior[:-n]) + " e " + trecho
                continue
        saida.append(trecho)
    return saida


def _emendar(trechos: list[str]) -> str:
    """'a', 'a e b' ou 'a, b e c', ja com os trechos de final igual fundidos."""
    return _lista(_fundir_trechos(trechos))


def _itens_da_lista(desvios: list[dict]) -> list[str]:
    """Uma orientacao por item. Desvios do mesmo grupo viram um item so: com um unico membro vale a frase dele;
    com 2 ou mais, os trechos sao emendados numa frase so, sob o rotulo do grupo. Frases e complementos repetidos
    aparecem uma vez. Sem frase curta cadastrada, usa o titulo do texto padrao (ou o nome)."""
    itens, por_grupo = [], {}
    for d in desvios:
        frase = ((d.get("orientacao_curta") or "").strip() or (d.get("titulo") or "").strip() or d["nome"])
        grupo = (d.get("grupo_curto") or "").strip() or None
        membro = {"frase": frase, "trecho": (d.get("trecho_grupo") or "").strip() or None,
                  "complemento": (d.get("complemento_curto") or "").strip() or None}
        if grupo and grupo in por_grupo:
            itens[por_grupo[grupo]]["membros"].append(membro)
        else:
            itens.append({"grupo": grupo, "membros": [membro]})
            if grupo:
                por_grupo[grupo] = len(itens) - 1
    textos_dos_itens = []
    for item in itens:
        membros, complementos = item["membros"], []
        for m in membros:
            if m["complemento"] and m["complemento"] not in complementos:
                complementos.append(m["complemento"])
        if item["grupo"] and len(membros) > 1:
            trechos = list(dict.fromkeys(m["trecho"] for m in membros if m["trecho"]))
            soltas = list(dict.fromkeys(m["frase"] for m in membros if not m["trecho"]))  # sem trecho: frase inteira
            partes = [f"{item['grupo']}: {_emendar(trechos)}."] if trechos else []
            texto = " ".join(partes + soltas + complementos)
        else:
            texto = " ".join(list(dict.fromkeys(m["frase"] for m in membros)) + complementos)
        textos_dos_itens.append(texto)
    return textos_dos_itens


def montar_mensagem(desvios: list[dict], gerais: dict) -> str:
    """Mensagem ao prestador. Um desvio: o texto padrao, inteiro e sem mudanca. Varios: versao curta, com
    saudacao unica, abertura com os problemas, uma orientacao curta por item (desvios do mesmo grupo juntos)
    e um unico fechamento."""
    if len(desvios) == 1:
        return desvios[0]["texto_padrao"].strip()
    resumos = list(dict.fromkeys(d.get("resumo") or d["nome"].lower() for d in desvios))
    itens = _itens_da_lista(desvios)
    lista = itens[0] if len(itens) == 1 else "\n".join(f"{n}. {t}" for n, t in enumerate(itens, start=1))
    abertura = gerais["abertura_multi"].replace("{desvios}", _lista(resumos))
    imagens = any(d.get("fechamento_tipo") == "imagens" for d in desvios)
    fechamento = gerais["fechamento_multi_imagens" if imagens else "fechamento_multi"]
    return f"{gerais['saudacao']}\n\n{abertura}\n{lista}\n\n{fechamento}"
