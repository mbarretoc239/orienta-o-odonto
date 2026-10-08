"""Prestadores: busca, cadastro de novos e correcao de nome."""
from core import auditoria
from core.regras import normalizar_documento, valida_documento


PODE_CADASTRAR = ("gestor", "admin")
MSG_NAO_CADASTRADO = "Prestador não cadastrado, contate o gestor para verificar."


def padronizar_nome(nome) -> str:
    return " ".join((nome or "").upper().split())


def buscar(db, documento):
    linhas = db.query("SELECT * FROM ori_prestadores WHERE documento=?", (normalizar_documento(documento),))
    return linhas[0] if linhas else None


def buscar_por_nome(db, termo, limite=50):
    termo = padronizar_nome(termo)
    if len(termo) < 3:
        return []
    return db.query(
        "SELECT documento, nome, codigo, cidade, uf, origem FROM ori_prestadores "
        "WHERE nome LIKE ? ORDER BY nome LIMIT ?",
        (f"%{termo}%", limite),
    )


def cadastrar(db, usuario, documento, nome):
    """Cadastro de prestador fora da base (so gestor e admin). Retorna (ok, mensagem)."""
    if usuario["perfil"] not in PODE_CADASTRAR:
        return False, MSG_NAO_CADASTRADO
    doc = normalizar_documento(documento)
    nome = padronizar_nome(nome)
    if not valida_documento(doc):
        return False, "CPF/CNPJ invalido (confira os digitos)."
    if not nome:
        return False, "Informe o nome do prestador."
    if buscar(db, doc):
        return False, "Prestador ja cadastrado."
    db.batch([
        (
            "INSERT INTO ori_prestadores (documento, nome, origem, criado_por) VALUES (?,?,'cadastro',?)",
            (doc, nome, usuario["usuario"]),
        ),
        auditoria.registrar(usuario["usuario"], "ori_prestadores", doc, "INSERT", None, {"nome": nome}),
    ])
    return True, "Prestador cadastrado."


def renomear(db, usuario, documento, novo_nome):
    """Corrige o nome de um prestador (admin). Retorna (ok, mensagem)."""
    antes = buscar(db, documento)
    novo = padronizar_nome(novo_nome)
    if not antes:
        return False, "Prestador nao encontrado."
    if not novo:
        return False, "Informe o nome."
    if novo == antes["nome"]:
        return False, "O nome nao mudou."
    db.batch([
        ("UPDATE ori_prestadores SET nome=? WHERE documento=?", (novo, antes["documento"])),
        auditoria.registrar(usuario["usuario"], "ori_prestadores", antes["documento"], "UPDATE",
                            {"nome": antes["nome"]}, {"nome": novo}),
    ])
    return True, "Nome atualizado."
