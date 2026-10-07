"""Acesso ao banco: SQLite local (desenvolvimento) ou Turso via API HTTP /v2/pipeline."""
import os
import sqlite3
import tomllib
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = RAIZ / "scripts" / "schema.sql"
LOCAL_PADRAO = RAIZ / "data" / "orientacoes.db"


class TursoIndisponivelError(RuntimeError):
    pass


def _ler_secrets() -> dict:
    caminho = RAIZ / ".streamlit" / "secrets.toml"
    if caminho.exists():
        with open(caminho, "rb") as f:
            return tomllib.load(f)
    return {}


def _declarar_schema() -> list[str]:
    return [s.strip() for s in SCHEMA.read_text(encoding="utf-8").split(";") if s.strip()]


class LocalDb:
    nome = "local"

    def __init__(self, caminho: Path | str = LOCAL_PADRAO):
        self.caminho = str(caminho)
        if self.caminho != ":memory:":
            Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)
        self._mem = sqlite3.connect(":memory:") if self.caminho == ":memory:" else None

    def _conn(self):
        conn = self._mem or sqlite3.connect(self.caminho)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql, args=()):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            if not self._mem:
                conn.close()

    def batch(self, comandos):
        """Executa (sql, args) numa unica transacao; devolve o rowcount de cada um."""
        conn = self._conn()
        try:
            contagens = []
            for sql, args in comandos:
                contagens.append(conn.execute(sql, args).rowcount)
            conn.commit()
            return contagens
        except Exception:
            conn.rollback()
            raise
        finally:
            if not self._mem:
                conn.close()

    def execute(self, sql, args=()):
        return self.batch([(sql, args)])[0]


class TursoDb:
    nome = "turso"

    def __init__(self, url: str, token: str):
        self.url = url.replace("libsql://", "https://").rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    @staticmethod
    def _arg(v):
        if v is None:
            return {"type": "null"}
        if isinstance(v, bool):
            return {"type": "integer", "value": str(int(v))}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": v}
        return {"type": "text", "value": str(v)}

    @staticmethod
    def _celula(c):
        t = c.get("type")
        if t == "null":
            return None
        if t == "integer":
            return int(c["value"])
        if t == "float":
            return float(c["value"])
        return c.get("value")

    def _post(self, requisicoes):
        corpo = {"requests": requisicoes + [{"type": "close"}]}
        try:
            r = requests.post(f"{self.url}/v2/pipeline", json=corpo, headers=self.headers, timeout=30)
        except requests.RequestException as e:
            raise TursoIndisponivelError(str(e)) from e
        if r.status_code in (401, 403, 429) or r.status_code >= 500:
            raise TursoIndisponivelError(f"Turso respondeu {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        return r.json()["results"]

    def _stmt(self, sql, args):
        return {"sql": sql, "args": [self._arg(a) for a in args]}

    def query(self, sql, args=()):
        res = self._post([{"type": "execute", "stmt": self._stmt(sql, args)}])[0]
        if res["type"] == "error":
            raise RuntimeError(res["error"]["message"])
        r = res["response"]["result"]
        cols = [c["name"] for c in r["cols"]]
        return [dict(zip(cols, (self._celula(c) for c in linha))) for linha in r["rows"]]

    def batch(self, comandos):
        """BEGIN + comandos + COMMIT; qualquer falha dispara ROLLBACK (tudo ou nada)."""
        comandos = list(comandos)
        passos = [{"stmt": {"sql": "BEGIN"}}]
        for i, (sql, args) in enumerate(comandos):
            passos.append({"stmt": self._stmt(sql, args), "condition": {"type": "ok", "step": i}})
        n = len(comandos)
        passos.append({"stmt": {"sql": "COMMIT"}, "condition": {"type": "ok", "step": n}})
        passos.append({
            "stmt": {"sql": "ROLLBACK"},
            "condition": {"type": "not", "cond": {"type": "ok", "step": n + 1}},
        })
        res = self._post([{"type": "batch", "batch": {"steps": passos}}])[0]
        if res["type"] == "error":
            raise RuntimeError(res["error"]["message"])
        resultado = res["response"]["result"]
        erros = [e for e in resultado["step_errors"][: n + 2] if e]
        if erros:
            raise RuntimeError(erros[0]["message"])
        return [(resultado["step_results"][i + 1] or {}).get("affected_row_count", 0) for i in range(n)]

    def execute(self, sql, args=()):
        return self.batch([(sql, args)])[0]


_instancia = None


def get_db():
    """Turso se houver TURSO_URL/TURSO_TOKEN (secrets.toml ou ambiente); senao SQLite local."""
    global _instancia
    if _instancia is None:
        sec = _ler_secrets()
        url = os.environ.get("TURSO_URL") or sec.get("TURSO_URL")
        token = os.environ.get("TURSO_TOKEN") or sec.get("TURSO_TOKEN")
        _instancia = TursoDb(url, token) if url and token else LocalDb(
            os.environ.get("ORI_DB_LOCAL", LOCAL_PADRAO)
        )
    return _instancia


def criar_schema(db) -> None:
    db.batch([(s, ()) for s in _declarar_schema()])
