"""Textos montados a partir dos dados do registro: relato do FORMS e mensagem ao prestador."""
import re
import unicodedata
from datetime import date

from core.regras import formatar_documento, rotulo_orientacao

_FECHAMENTO = ("Recomendamos fortemente a utilização do aplicativo para execução dos procedimentos{extra}. "
               "Com ele, você elimina a necessidade de envio de malotes físicos, assegurando maior agilidade na "
               "auditoria e no pagamento da sua produção. Além disso, o uso do aplicativo gera economia com "
               "impressão e postagem, tornando o processo mais rápido, seguro e eficiente.")

GERAIS_PADRAO = {
    "saudacao": "Caro(a) prestador(a),",
    "abertura": "Identificamos pendências referentes a {desvios}. Seguem as orientações:",
    "fechamento": _FECHAMENTO.format(extra=""),
    "fechamento_imagens": _FECHAMENTO.format(extra=" e anexo de imagens"),
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


# ---------- relato do FORMS ----------

def relato_forms(nome: str, documento: str, itens: list[dict]) -> str:
    """Texto-base do relato do FORMS: identifica o prestador e os desvios cobertos por aquele formulario.
    `itens`: dicts com `desvio`, `numero` e `data` (ISO). Quem preenche so continua depois de 'Relato:'."""
    tipo = "CPF" if len(documento) == 11 else "CNPJ"
    cabecalho = f"Prestador {nome} ({tipo} {formatar_documento(documento)})"
    if len(itens) == 1:
        i = itens[0]
        corpo = (f'{cabecalho} recebeu a {rotulo_orientacao(i["numero"])} pelo desvio "{i["desvio"]}" '
                 f"em {_data_br(i['data'])}, com encaminhamento para o FORMS.")
    else:
        linhas = "\n".join(
            f'• {rotulo_orientacao(i["numero"])} pelo desvio "{i["desvio"]}" em {_data_br(i["data"])}' for i in itens)
        corpo = f"{cabecalho} recebeu as orientações abaixo, com encaminhamento para o FORMS:\n{linhas}"
    return f"{corpo}\n\nRelato:\n"


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
    if db.query("SELECT COUNT(*) AS n FROM ori_textos")[0]["n"] < len(GERAIS_PADRAO):
        comandos += [("INSERT OR IGNORE INTO ori_textos (chave, valor) VALUES (?,?)", (k, v))
                     for k, v in GERAIS_PADRAO.items()]
    if comandos:
        db.batch(comandos)


def carregar_gerais(db) -> dict:
    gerais = dict(GERAIS_PADRAO)
    gerais.update({r["chave"]: r["valor"] for r in db.query("SELECT chave, valor FROM ori_textos")})
    return gerais


def salvar_gerais(db, valores: dict) -> None:
    db.batch([("INSERT INTO ori_textos (chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET "
               "valor=excluded.valor", (k, v)) for k, v in valores.items() if k in GERAIS_PADRAO])


def _lista(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def montar_mensagem(desvios: list[dict], gerais: dict) -> str:
    """Mensagem ao prestador. Um desvio: o texto padrao, sem mudanca. Varios: saudacao unica, abertura com
    os problemas, cada orientacao uma so vez (as identicas se fundem) e um unico fechamento."""
    if len(desvios) == 1:
        return desvios[0]["texto_padrao"].strip()
    topicos, vistos = [], set()
    for d in desvios:
        titulo, corpo = (d.get("titulo") or "").strip(), (d.get("corpo") or "").strip()
        if not titulo and not corpo:
            titulo = d["nome"]
        chave = (titulo.lower(), corpo.lower())
        if chave not in vistos:
            vistos.add(chave)
            topicos.append((titulo, corpo))
    resumos = list(dict.fromkeys(d.get("resumo") or d["nome"].lower() for d in desvios))
    blocos = [gerais["saudacao"], gerais["abertura"].replace("{desvios}", _lista(resumos))]
    for n, (titulo, corpo) in enumerate(topicos, start=1):
        cabecalho = f"{n}. {titulo}" if len(topicos) > 1 else titulo
        blocos.append(cabecalho + (f"\n{corpo}" if corpo else ""))
    tipos = {d.get("fechamento_tipo") for d in desvios}
    if "imagens" in tipos:
        blocos.append(gerais["fechamento_imagens"])
    elif "padrao" in tipos:
        blocos.append(gerais["fechamento"])
    return "\n\n".join(blocos)
