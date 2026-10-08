# Identidade visual — Orientações a Prestadores (para reaproveitar no SIA)

App Streamlit 1.65 com a marca **Hapvida +odonto**. Toda a identidade vem de 4 peças: **logo/ícone**, **faixa de cores no topo**, **tema claro/escuro** e **paleta dos gráficos**. Nada é customizado além disso (sem CSS pesado): o resto é o visual padrão do Streamlit, que herda as cores do tema.

## 1. Cores da marca (extraídas do PDF do logo)

| Uso no logo | Hex |
|---|---|
| Texto "Hapvida" | `#1539AA` (azul) |
| Pétala de cima | `#FF222B` (vermelho) |
| Pétalas laterais de cima e "+odonto" | `#FF4E05` (laranja) |
| Pétalas laterais de baixo | `#FF8800` (laranja-claro) |
| Pétala de baixo | `#FFCC23` (amarelo) |

## 2. Arquivos de imagem (`assets/`)

Gerados a partir do PDF (PyMuPDF, 144 dpi, fundo transparente, recortados na caixa do desenho).

| Arquivo | O que é |
|---|---|
| `assets/logo.png` | Logo completo, para tema **claro** (2290×736) |
| `assets/logo_escuro.png` | Mesmo logo para tema **escuro**: só o azul do texto vira branco (`b > r + 60` → `#FFFFFF`); pétalas e "+odonto" ficam iguais |
| `assets/icone.png` | Só a flor, quadrado 256×256 com respiro de 12 px, usado como ícone da aba e ícone da barra lateral recolhida |

Copiar a pasta `assets/` inteira para o SIA.

## 3. Tema (`.streamlit/config.toml`)

```toml
[theme.light]
primaryColor = "#1539aa"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f3fc"   # barra lateral e campos, azulado bem claro
textColor = "#0b0b0b"

[theme.dark]
primaryColor = "#5a7ff0"               # azul mais claro: contraste com o fundo escuro
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#171c2a"
textColor = "#ffffff"
```

Efeito: botões primários, aba selecionada, links, checkbox e foco dos campos ficam azuis; barra lateral e campos de texto ficam num azul-acinzentado discreto. O laranja **não** é cor de destaque de interface (branco sobre `#FF4E05` tem pouco contraste); ele aparece só no logo, na faixa e nos gráficos.

## 4. Módulo da marca (`core/marca.py`)

Chamado em **toda página**, logo depois de `st.set_page_config(..., page_icon=marca.ICONE)`:

```python
import streamlit as st
from core import marca

st.set_page_config(page_title="...", layout="wide", page_icon=marca.ICONE)
marca.aplicar()
```

```python
"""Identidade visual: logo na barra lateral (versao clara ou escura conforme o tema), icone da aba e faixa com as
cores da marca. As cores do tema ficam em .streamlit/config.toml."""
from pathlib import Path

import streamlit as st

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
ICONE = str(_ASSETS / "icone.png")

# azul do texto, vermelho/laranja/laranja-claro/amarelo das petalas (cores do PDF da marca)
CORES = ["#1539aa", "#ff222b", "#ff4e05", "#ff8800", "#ffcc23"]

_FAIXA = (
    "<style>[data-testid='stHeader']{border-bottom:3px solid transparent;border-image:linear-gradient(90deg,"
    + ",".join(CORES) + ") 1;}</style>"
)


def _escuro() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:  # fora do Streamlit (testes) ou versao sem st.context.theme
        return False


def aplicar():
    """Chamar em toda pagina, logo depois de st.set_page_config."""
    try:
        logo = _ASSETS / ("logo_escuro.png" if _escuro() else "logo.png")
        st.logo(str(logo), size="large", icon_image=ICONE)
        st.html(_FAIXA)
    except Exception:  # a marca nunca deve derrubar a pagina
        pass
```

Pontos que valem lembrar:
- `st.logo` **não tem imagem separada para tema escuro**; por isso o módulo escolhe o arquivo lendo `st.context.theme.type` a cada execução.
- A faixa é uma linha de 3 px com degradê das 5 cores, aplicada na borda de baixo do cabeçalho (`[data-testid='stHeader']`) com `border-image`. Ela depende desse `data-testid` do Streamlit; se uma versão futura mudar o nome, é só ajustar o seletor.
- O `try/except` evita que um problema de imagem derrube a página.
- `st.logo(size="large")` é o maior tamanho permitido; o "+odonto" fica pequeno na barra lateral.

## 5. Layout das páginas

- `st.set_page_config(layout="centered")` nas páginas de formulário (login/inicial, Registrar, Minha conta) e `layout="wide"` nas de tabela/painel (Pendências, Consultar, Painel, Admin).
- Navegação: `app.py` é só um roteador (`st.navigation(..., position="hidden")`) com os nomes do menu em `core/paginas.py`; a tela inicial é `inicio.py` e as demais ficam em `pages/`.
- Barra lateral, de cima para baixo: logo; `usuário · perfil`, "Minhas pendências (n)" e botão **Sair**; um divisor; e o menu (Início, Registrar ocorrência, Pendências, Consultar Base, Painel, Minha conta, Admin), desenhado com `st.page_link` em `core/ui.py:barra_lateral`. A página atual fica destacada.
- Cada página: `st.title(...)` simples, sem ícones/emoji no título.
- Botão principal de cada ação: `type="primary"` (fica azul pelo tema).
- Listas longas em **blocos expansíveis** (`st.expander`) em vez de tabelas quando cada linha tem muitos campos; tabelas com `st.dataframe(..., hide_index=True, width="stretch")`.
- Abas (`st.tabs`) na tela de login: Entrar · Primeiro acesso · Esqueci minha senha.

## 6. Gráficos (Altair 6, `core/graficos.py`)

Escolhidos com o método de dataviz (uma cor por função, marcas finas, grade discreta, claro e escuro **escolhidos**, não invertidos) e **validados** com o validador de paleta (faixa de luminosidade, croma, separação para daltonismo, contraste). Todo gráfico vem com a **mesma informação em tabela** (`st.expander("Ver como tabela")`).

| Papel | Claro | Escuro |
|---|---|---|
| Série 1 (azul) | `#2B52C8` | `#6B8CF2` |
| Série 2 (laranja) | `#EB6834` | `#D95926` |
| Série 3 (verde) | `#1BAF7A` | `#199E70` |
| Escala sequencial (pouco → muito) | `#DBE3FB #A9BCF3 #6B8CF2 #2B52C8 #1539AA` | `#16296B #1F3F9E #3A5FD0 #7F9BF3 #C3D0FA` |
| Texto / texto secundário / mudo | `#0B0B0B / #52514E / #898781` | `#FFFFFF / #C3C2B7 / #898781` |
| Grade / eixo base | `#E1E0D9 / #C3C2B7` | `#2C2C2A / #383835` |
| Superfície (fundo do gráfico) | `#FFFFFF` | `#0E1117` |

Por que o azul dos gráficos **não** é o `#1539AA` da marca: ele é escuro demais para série de gráfico (fica fora da faixa de luminosidade do validador), então usa-se um tom um pouco mais claro; o `#1539AA` só aparece como fim da escala sequencial.

Regras aplicadas em todos os gráficos:
- Tema detectado com `st.context.theme.type`; `st.altair_chart(..., theme=None)` para o Streamlit não sobrescrever as cores.
- Fundo transparente, sem contorno de vista, grade e eixos discretos.
- Colunas/barras finas (16–22 px) com cantos de 4 px só na ponta; 2 px da cor da superfície entre segmentos empilhados.
- Legenda sempre no topo quando há 2+ séries; rótulo numérico só no valor de destaque (último mês, maior barra), o resto no tooltip.
- Cores atribuídas em ordem fixa por série (a cor segue a entidade, nunca o ranking).
- Mapa de calor (desvio × mês) usa só a escala sequencial azul.

## 7. Como levar para o SIA

1. Copiar `assets/`, `core/marca.py` e `.streamlit/config.toml` (se o SIA já tiver `config.toml`, mesclar só as seções `[theme.light]` e `[theme.dark]`).
2. Em cada página do SIA: `page_icon=marca.ICONE` no `set_page_config` e `marca.aplicar()` logo em seguida.
3. Para gráficos, copiar as paletas `CLARO`/`ESCURO` e as funções de `core/graficos.py`.
4. O app usa Streamlit 1.65. As seções `[theme.light]/[theme.dark]`, `st.context.theme` e `st.logo(icon_image=...)` exigem uma versão recente; se o SIA estiver em outra, vale testar antes.
5. Se o SIA já tiver CSS próprio no cabeçalho, conferir se a faixa (`border-image`) não conflita.
