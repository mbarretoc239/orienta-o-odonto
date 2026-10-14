"""Paginas do app, os nomes mostrados no menu e quem pode ver cada uma (uma fonte so, usada pelo roteador, pelo menu
lateral e conferida contra os bloqueios de cada pagina nos testes).

`perfis` vazio = todos os perfis. O bloqueio de verdade continua dentro da pagina (`exigir_login(perfis=...)`):
esconder o link do menu nao basta, porque o endereco da pagina pode ser digitado."""
from core.auth import PERFIS

TODOS = ()
GESTAO = ("gestor", "admin")
SO_ADMIN = ("admin",)

# (arquivo, titulo no menu, endereco, perfis que podem ver)
PAGINAS = [
    ("inicio.py", "Início", "", TODOS),
    ("pages/1_Registrar.py", "Registrar ocorrência", "registrar", TODOS),
    ("pages/7_Minhas_ocorrencias.py", "Minhas ocorrências", "minhas-ocorrencias", TODOS),
    ("pages/2_Pendencias.py", "Pendências", "pendencias", TODOS),
    ("pages/3_Consultar.py", "Consultar Base", "consultar", TODOS),
    ("pages/4_Painel.py", "Painel", "painel", GESTAO),
    ("pages/5_Minha_conta.py", "Minha conta", "minha-conta", TODOS),
    ("pages/6_Admin.py", "Admin", "admin", SO_ADMIN),
]


def paginas_do_perfil(perfil: str):
    """Paginas que o perfil enxerga no menu, na ordem do menu."""
    return [(arquivo, titulo) for arquivo, titulo, _, perfis in PAGINAS if not perfis or perfil in perfis]


assert all(p in PERFIS for _, _, _, perfis in PAGINAS for p in perfis)
