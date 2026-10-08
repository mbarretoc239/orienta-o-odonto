"""Monta desvios, prestadores e orientacoes limpos, e junta os conflitos para revisao humana."""
from collections import Counter

import pandas as pd

from datetime import date

from core.regras import normalizar_documento, valida_documento
from migracao import datas, decisoes
from migracao import limpeza as lp


def conflito(tipo, documento="", detalhe="", usado=""):
    return {"tipo": tipo, "documento": documento, "detalhe": detalhe, "usado": usado}


def montar_desvios(frame):
    return [(lp.nome_desvio(n), str(t or "").strip()) for n, t in zip(frame.nome, frame.texto)]


def montar_prestadores(oficial, ficha, conflitos):
    """Nome oficial = 1a ocorrencia na aba oficial (mesma regra da coluna BASE da planilha de prestadores);
    se o documento nao estiver la, usa CREDENCIADO da aba 'prestadores'."""
    nome_oficial, variantes = {}, {}
    for nome, doc in zip(oficial.nome, oficial.doc):
        d = normalizar_documento(doc)
        if not d or lp.vazio(nome):
            continue
        nome_oficial.setdefault(d, lp.sem_acento(nome))
        variantes.setdefault(d, set()).add(lp.sem_acento(nome))
    for d, v in variantes.items():
        if len(v) > 1:
            conflitos.append(conflito("nome_divergente_base", d, " | ".join(sorted(v)), nome_oficial[d]))

    prest = {}
    for _, r in ficha.iterrows():
        d = normalizar_documento(r["CNPJ_CPF"])
        if not d or d in prest:
            continue
        nome = nome_oficial.get(d) or lp.sem_acento(r["CREDENCIADO"])
        if d not in nome_oficial:
            conflitos.append(conflito("fora_da_aba_oficial", d, "", nome))
        prest[d] = {"nome": nome, "codigo": r["CODIGO"], "tipo": r["TIPO_PRESTADOR"],
                    "cidade": r["CIDADE"], "uf": r["UF"], "origem": "base"}
    return prest


def montar_orientacoes(acompanhamento, desvios, prest, conflitos):
    """Limpa as linhas, cadastra prestadores que so existem na planilha e recalcula a numeracao
    por documento + desvio em ordem de data."""
    ids = {lp.sem_acento(nome): i + 1 for i, (nome, _) in enumerate(desvios)}
    linhas, nomes_planilha = [], {}

    # datas: o Excel leu algumas como mes/dia; a planilha foi preenchida em ordem cronologica, entao as
    # linhas vizinhas dizem qual leitura vale (ver migracao/datas.py e scripts/revisar_datas.py)
    com_desvio = acompanhamento[~acompanhamento["desvio"].map(lp.vazio)]
    linhas_datas, corrigidas = datas.linhas_da_planilha((pos + 2, r["data"]) for pos, r in com_desvio.iterrows())
    por_linha = {x.linha: x for x in linhas_datas}
    sugestoes = datas.aplicar_decisoes(datas.resolver(linhas_datas, date.today()), decisoes.DATAS_MANUAIS)

    for pos, r in acompanhamento.iterrows():
        linha = pos + 2  # numero da linha no Excel
        if lp.vazio(r["doc"]) and lp.vazio(r["desvio"]):
            continue  # linha pre-preenchida vazia
        doc = normalizar_documento(r["doc"])
        dev = lp.sem_acento(r["desvio"])
        if not doc or dev not in ids:
            conflitos.append(conflito("linha_descartada", doc, f"linha {linha}: desvio='{r['desvio']}'"))
            continue
        lida = por_linha[linha].data
        obs = [] if lp.vazio(r["obs"]) else [str(r["obs"]).strip()]
        if lida is None:
            sug = datas.sugerir_sem_data(linhas_datas, linha)
            if sug.sugerida is None:
                conflitos.append(conflito("data_ausente_ou_invalida", doc, f"linha {linha}: '{r['data']}' ({dev})"))
                continue
            data = sug.sugerida.isoformat()
            obs.append("Data estimada pelas linhas vizinhas da planilha (célula vazia)")
            conflitos.append(conflito("data_estimada", doc, f"linha {linha}: sem data -> {data} ({sug.motivo})"))
        elif por_linha[linha].ambigua and sugestoes[linha].sugerida != lida:
            sug = sugestoes[linha]
            data = sug.sugerida.isoformat()
            obs.append(f"Data ajustada na migração (planilha: {lida.strftime('%d/%m/%Y')})")
            conflitos.append(conflito(
                "data_ajustada", doc, f"linha {linha}: {lida.isoformat()} -> {data} (confiança {sug.confianca})"))
        else:
            data = lida.isoformat()
        if linha in corrigidas:
            obs.append(f"Data corrigida na migracao (planilha: {r['data']})")
            conflitos.append(conflito("data_corrigida", doc, f"linha {linha}: '{r['data']}' -> {data}"))
        if not valida_documento(doc):
            conflitos.append(conflito("documento_invalido", doc, f"linha {linha}"))
        sinal, extra, era_documento = lp.normalizar_sinal(r["sinal"])
        if extra:
            obs.append(extra)
        if era_documento:
            conflitos.append(conflito("sinalizado_com_documento", doc, f"linha {linha}: '{r['sinal']}' descartado"))
        nomes_planilha.setdefault(doc, []).append(lp.sem_acento(r["nome"]))
        linhas.append({"documento": doc, "desvio_id": ids[dev], "data": data, "pos": pos,
                       "sinal": sinal, "obs": " | ".join(obs) or None})

    for doc, nomes in nomes_planilha.items():
        if doc not in prest:
            nomes_ok = [n for n in nomes if n]
            usado = Counter(nomes_ok).most_common(1)[0][0] if nomes_ok else "SEM NOME"
            prest[doc] = {"nome": usado, "codigo": None, "tipo": None, "cidade": None, "uf": None,
                          "origem": "planilha"}
            conflitos.append(conflito("prestador_novo_da_planilha", doc, " | ".join(sorted(set(nomes))), usado))

    df = pd.DataFrame(linhas).sort_values(["documento", "desvio_id", "data", "pos"])
    df["numero"] = df.groupby(["documento", "desvio_id"]).cumcount() + 1
    return df
