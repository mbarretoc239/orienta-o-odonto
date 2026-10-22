from core import db as banco
from core import textos
from core.db import LocalDb, criar_schema


class Contador(LocalDb):
    """Conta as idas ao banco (no Turso cada uma custa cerca de meio segundo)."""

    def __init__(self):
        super().__init__(":memory:")
        self.idas = 0

    def query(self, sql, args=()):
        self.idas += 1
        return super().query(sql, args)

    def batch(self, comandos):
        self.idas += 1
        return super().batch(comandos)


def test_primeiro_arranque_cria_tudo_e_grava_a_impressao_do_schema():
    d = Contador()
    criar_schema(d)
    assert d.query("SELECT valor FROM ori_meta WHERE chave='schema'")[0]["valor"] == banco._impressao_do_schema()
    colunas = {r["name"] for r in d.query("SELECT name FROM pragma_table_info('ori_desvios')")}
    assert {"trecho_grupo", "orientacao_forms"} <= colunas


def test_arranque_seguinte_faz_uma_unica_ida_ao_banco():
    d = Contador()
    criar_schema(d)
    d.idas = 0
    criar_schema(d)
    assert d.idas == 1  # so a comparacao da impressao


def test_schema_que_mudou_e_atualizado_de_novo(monkeypatch):
    d = Contador()
    criar_schema(d)
    monkeypatch.setattr(banco, "COLUNAS_NOVAS", banco.COLUNAS_NOVAS + [("ori_desvios", "campo_novo", "TEXT")])
    criar_schema(d)
    assert "campo_novo" in {r["name"] for r in d.query("SELECT name FROM pragma_table_info('ori_desvios')")}
    d.idas = 0
    criar_schema(d)
    assert d.idas == 1  # e volta a ser uma ida so


def test_banco_anterior_a_ori_meta_e_migrado_sem_perder_dados():
    d = LocalDb(":memory:")
    criar_schema(d)
    d.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('X', 'x')")
    d.execute("DROP TABLE ori_meta")  # como um banco criado antes desta versao
    criar_schema(d)
    assert d.query("SELECT COUNT(*) n FROM ori_desvios")[0]["n"] == 1
    assert d.query("SELECT COUNT(*) n FROM ori_meta")[0]["n"] == 1


def test_preencher_estrutura_faz_uma_consulta_dos_desvios_e_uma_dos_textos():
    d = Contador()
    criar_schema(d)
    d.execute("INSERT INTO ori_desvios (nome, texto_padrao) VALUES ('FALTA DOCUMENTACAO', 'Titulo\nCorpo do texto')")
    textos.preencher_estrutura(d)  # preenche
    d.idas = 0
    textos.preencher_estrutura(d)  # nada a fazer: 2 consultas, nenhuma gravacao
    assert d.idas == 2
