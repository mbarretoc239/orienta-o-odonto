"""Sessao persistente (8h): o navegador guarda um token aleatorio; o banco guarda apenas o hash dele."""
import hashlib
import secrets

DURACAO_H = 8
COOKIE = "ori_sessao"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def criar(db, usuario: str) -> str:
    token = secrets.token_urlsafe(32)
    db.batch([
        ("DELETE FROM ori_sessoes WHERE expira_em < datetime('now')", ()),
        (
            "INSERT INTO ori_sessoes (token_hash, usuario, expira_em) VALUES (?,?,datetime('now', ?))",
            (_hash(token), usuario, f"+{DURACAO_H} hours"),
        ),
    ])
    return token


def usuario_da_sessao(db, token):
    """Nome do usuario dono de um token valido (nao expirado), ou None."""
    if not isinstance(token, str) or not token:
        return None
    r = db.query(
        "SELECT usuario FROM ori_sessoes WHERE token_hash=? AND expira_em > datetime('now')", (_hash(token),)
    )
    return r[0]["usuario"] if r else None


def encerrar(db, token):
    if token:
        db.execute("DELETE FROM ori_sessoes WHERE token_hash=?", (_hash(token),))
