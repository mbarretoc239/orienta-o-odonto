import json
import re

from core import ui


def test_texto_do_botao_copiar_nao_consegue_fechar_o_script(monkeypatch):
    pego = []
    monkeypatch.setattr(ui.st, "html", lambda html, **kw: pego.append(html))
    malicioso = 'X</script><img src=x onerror=alert(1)> & "aspas"\ttab'
    ui.botao_copiar(malicioso, "Copiar", "t1")
    html = pego[0]
    assert html.count("</script>") == 1  # so o fechamento do proprio script
    assert "<img" not in html  # o "<" do texto saiu escapado (\u003c), nao como tag
    literal = re.search(r"texto = (\".*?\"), rotulo", html, re.S).group(1)
    assert json.loads(literal) == malicioso  # o navegador recebe exatamente o texto original
