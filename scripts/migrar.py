"""Carga inicial: desvios, prestadores (dPrestadores) e historico de orientacoes (planilha).

Uso: python scripts/migrar.py [--dry-run]
Gera data/conflitos_*.csv para revisao humana. Nao apaga nada: roda apenas em banco sem orientacoes.
"""
import re
import sys
import unicodedata
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
warnings.filterwarnings("ignore")

from core.db import criar_schema, get_db  # noqa: E402
from core.regras import normalizar_documento, valida_documento  # noqa: E402

DADOS = RAIZ / "data"
ARQ_PRESTADORES = DADOS / "dPrestadores.xlsx"
ARQ_PLANILHA = DADOS / "orientacao_adm_interna.xlsx"


def sem_acento(s) -> str:
    if s is None or (isinstance(s, float) and s != s):
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).upper().split())


def parse_data(v):
    v = str(v or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", v):
        return v[:10]
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        try:
            return datetime(int(m[3]), int(m[2]), int(m[1])).date().isoformat()
        except ValueError:
            return None
    return None


def carregar_desvios():
    b = pd.read_excel(ARQ_PLANILHA, sheet_name="Base", header=None, dtype=str).iloc[1:, 1:3]
    b.columns = ["nome", "texto"]
    b = b.dropna(subset=["nome"])
    return [(" ".join(str(n).upper().split()), str(t or "").strip()) for n, t in zip(b.nome, b.texto)]


def carregar_prestadores(conflitos):
    """Nome oficial = 1a ocorrencia na aba 'PRESTADOR - CNPJ.CPF' (mesma regra da coluna BASE);
    senao, CREDENCIADO da aba 'prestadores'."""
    oficial = pd.read_excel(ARQ_PRESTADORES, sheet_name="PRESTADOR - CNPJ.CPF", dtype=str)
    oficial.columns = ["nome", "doc", "cod"]
    nome_oficial, variantes = {}, {}
    for nome, doc in zip(oficial.nome, oficial.doc):
        d = normalizar_documento(doc)
        if not d or not nome:
            continue
        nome_oficial.setdefault(d, sem_acento(nome))
        variantes.setdefault(d, set()).add(sem_acento(nome))
    for d, v in variantes.items():
        if len(v) > 1:
            conflitos.append({"tipo": "nome_divergente_base", "documento": d,
                              "detalhe": " | ".join(sorted(v)), "usado": nome_oficial[d]})

    ficha = pd.read_excel(ARQ_PRESTADORES, sheet_name="prestadores", dtype=str)
    prest = {}
    for _, r in ficha.iterrows():
        d = normalizar_documento(r["CNPJ_CPF"])
        if not d or d in prest:
            continue
        nome = nome_oficial.get(d) or sem_acento(r["CREDENCIADO"])
        if d not in nome_oficial:
            conflitos.append({"tipo": "fora_da_aba_oficial", "documento": d, "detalhe": "", "usado": nome})
        prest[d] = {"nome": nome, "codigo": r["CODIGO"], "tipo": r["TIPO_PRESTADOR"],
                    "cidade": r["CIDADE"], "uf": r["UF"], "origem": "base"}
    return prest


def carregar_orientacoes(desvios, prest, conflitos):
    a = pd.read_excel(ARQ_PLANILHA, sheet_name="Acompanhamento", dtype=str)
    a.columns = ["doc", "nome", "desvio", "data", "qtd", "acao", "sinal", "obs"]
    ids = {sem_acento(nome): i + 1 for i, (nome, _) in enumerate(desvios)}
    linhas, nomes_planilha = [], {}
    for pos, r in a.iterrows():
        doc_bruto, dev = r["doc"], sem_acento(r["desvio"])
        if (pd.isna(doc_bruto) or not str(doc_bruto).strip()) and not dev:
            continue  # linha pre-preenchida vazia
        doc = normalizar_documento(doc_bruto)
        if not doc or dev not in ids:
            conflitos.append({"tipo": "linha_descartada", "documento": doc, "detalhe": f"linha {pos + 2}: desvio='{r['desvio']}'", "usado": ""})
            continue
        data = parse_data(r["data"])
        if not data:
            conflitos.append({"tipo": "data_invalida", "documento": doc, "detalhe": f"linha {pos + 2}: '{r['data']}'", "usado": ""})
            continue
        if not valida_documento(doc):
            conflitos.append({"tipo": "documento_invalido", "documento": doc, "detalhe": f"linha {pos + 2}", "usado": ""})
        obs = [] if pd.isna(r["obs"]) else [str(r["obs"]).strip()]
        s = sem_acento(r["sinal"])
        if s in ("SIM", "SM"):
            sinal = "SIM"
        elif s.startswith("SINALIZADO"):
            sinal = "SIM"
            obs.append(f"Planilha: {str(r['sinal']).strip()}")
        elif s in ("NAO", "NAO "):
            sinal = "NAO"
        else:
            sinal = None
            if s and not s.isdigit():
                obs.append(f"Planilha: {str(r['sinal']).strip()}")
            elif s:
                conflitos.append({"tipo": "sinalizado_com_documento", "documento": doc, "detalhe": f"linha {pos + 2}: '{r['sinal']}' descartado", "usado": ""})
        nomes_planilha.setdefault(doc, []).append(sem_acento(r["nome"]))
        linhas.append({"documento": doc, "desvio_id": ids[dev], "data": data, "pos": pos,
                       "sinal": sinal, "obs": " | ".join(o for o in obs if o) or None})
    for doc, nomes in nomes_planilha.items():
        if doc not in prest:
            usado = Counter(n for n in nomes if n).most_common(1)[0][0] if any(nomes) else "SEM NOME"
            variantes = sorted(set(nomes))
            prest[doc] = {"nome": usado, "codigo": None, "tipo": None, "cidade": None, "uf": None, "origem": "planilha"}
            conflitos.append({"tipo": "prestador_novo_da_planilha", "documento": doc,
                              "detalhe": " | ".join(variantes), "usado": usado})
    df = pd.DataFrame(linhas).sort_values(["documento", "desvio_id", "data", "pos"])
    df["numero"] = df.groupby(["documento", "desvio_id"]).cumcount() + 1
    return df


def main(dry_run=False):
    db = get_db()
    criar_schema(db)
    if db.query("SELECT 1 FROM ori_orientacoes LIMIT 1"):
        sys.exit("Banco ja tem orientacoes: migracao cancelada para nao duplicar.")
    conflitos = []
    desvios = carregar_desvios()
    prest = carregar_prestadores(conflitos)
    orient = carregar_orientacoes(desvios, prest, conflitos)

    DADOS.mkdir(exist_ok=True)
    pd.DataFrame(conflitos).to_csv(DADOS / "conflitos_migracao.csv", index=False, encoding="utf-8-sig", sep=";")
    resumo = Counter(c["tipo"] for c in conflitos)
    print(f"desvios={len(desvios)} prestadores={len(prest)} orientacoes={len(orient)}")
    print("conflitos:", dict(resumo))
    if dry_run:
        print("dry-run: nada gravado.")
        return

    from core.regras import ACAO_A_CADA
    db.batch([("INSERT INTO ori_desvios (nome, texto_padrao) VALUES (?,?)", d) for d in desvios])
    cmds = [("INSERT INTO ori_prestadores (documento, nome, codigo, tipo, cidade, uf, origem) VALUES (?,?,?,?,?,?,?)",
             (d, p["nome"], p["codigo"], p["tipo"], p["cidade"], p["uf"], p["origem"])) for d, p in prest.items()]
    for i in range(0, len(cmds), 500):
        db.batch(cmds[i:i + 500])
    cmds = [("INSERT INTO ori_orientacoes (documento, desvio_id, data_orientacao, numero_orientacao, acao, "
             "credenciamento_sinalizado, observacao, criado_por) VALUES (?,?,?,?,?,?,?,'migracao')",
             (r.documento, int(r.desvio_id), r.data, int(r.numero), "FORMS" if r.numero % ACAO_A_CADA == 0 else None,
              r.sinal, r.obs)) for r in orient.itertuples()]
    for i in range(0, len(cmds), 500):
        db.batch(cmds[i:i + 500])
    n = db.query("SELECT COUNT(*) AS n FROM ori_orientacoes")[0]["n"]
    print(f"gravado. orientacoes no banco={n} (esperado {len(orient)})")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
