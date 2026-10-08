# Reset de senha por código de recuperação (para reaproveitar no SIA)

Autoatendimento: a pessoa redefine a própria senha **sem passar pelo admin**, usando um **código de recuperação** que recebeu no cadastro. O admin continua podendo gerar senha temporária ou novo código para quem perdeu o dele. Tudo vive em `core/auth.py` (regras puras, sem Streamlit) e é chamado pelas telas.

Stack: Python + Streamlit + Turso (HTTP). Os exemplos usam `db.query(sql, args)`, `db.execute(sql, args)` e `db.batch([(sql, args), ...])` (lote atômico); adapte aos nomes do SIA.

## 1. Resumo do fluxo

| Situação | O que acontece |
|---|---|
| **Cadastro** | A pessoa cria a conta e a tela mostra **uma única vez** o código (ex.: `K7QM-4XD2-9PBT`). No banco fica só o hash. |
| **"Esqueci minha senha"** (tela de login) | Informa usuário + código + nova senha. Se o código confere, a senha muda, **o código usado é trocado por um novo** (mostrado uma vez) e **todas as sessões abertas da pessoa são encerradas**. |
| **Código perdido** | Admin gera **novo código** (invalida o anterior) ou **senha temporária** (obriga a troca no próximo login). |
| **Troca voluntária** ("Minha conta") | Senha atual + nova. Derruba as *outras* sessões; mantém a atual. Quem nunca teve código ganha um. |
| **Novo código por conta própria** ("Minha conta") | Confirma a senha e gera outro código; o anterior deixa de valer. |

## 2. Banco

Colunas na tabela de usuários (as quatro últimas são as do reset/bloqueio):

```sql
CREATE TABLE IF NOT EXISTS ori_usuarios (
  usuario TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  senha_hash TEXT NOT NULL,
  perfil TEXT NOT NULL DEFAULT 'contas',
  status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','ativo','inativo')),
  tentativas INTEGER NOT NULL DEFAULT 0,   -- erros seguidos (login E código de recuperação compartilham o contador)
  bloqueado_ate TEXT,                      -- datetime UTC do SQLite; NULL = livre
  codigo_hash TEXT,                        -- hash scrypt do código; NULL = pessoa ainda não tem código
  trocar_senha INTEGER NOT NULL DEFAULT 0, -- 1 = senha temporária, obriga trocar no próximo acesso
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ori_sessoes (
  token_hash TEXT PRIMARY KEY,
  usuario TEXT NOT NULL,
  expira_em TEXT NOT NULL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Se o SIA já tem a tabela de usuários, basta `ALTER TABLE ... ADD COLUMN` para `tentativas`, `bloqueado_ate`, `codigo_hash` e `trocar_senha`.

## 3. Regras de segurança (o porquê de cada escolha)

- **Senha e código só em hash**: scrypt (`n=2**14, r=8, p=1`) com sal de 16 bytes, formato `scrypt$<sal_hex>$<hash_hex>`; comparação com `hmac.compare_digest`. O código é normalizado (maiúsculas, sem hífen/espaço) antes do hash, então `k7qm 4xd2-9pbt` funciona.
- **Código de 12 caracteres** de um alfabeto sem `0/O/1/I` (evita confusão ao digitar), via `secrets.choice` (~60 bits).
- **Código de uso único na prática**: ao redefinir, um novo código substitui o usado.
- **Limite de 5 tentativas, compartilhado**: erro de senha no login **e** erro de código no "esqueci" contam no mesmo contador; no 5º erro a conta bloqueia por 15 minutos. Isso impede adivinhar o código por força bruta.
- **Mensagem igual para usuário existente e inexistente** ("Usuário ou código de recuperação inválidos"), para não revelar quem tem conta.
- **Redefinir encerra todas as sessões** da pessoa (quem roubou a sessão antiga perde o acesso).
- **Segredo mostrado uma vez**: código e senha temporária ficam em `st.session_state` só até a pessoa clicar "Já guardei".
- **Senha mínima de 8 caracteres**; a troca exige que a nova seja diferente da atual.
- **Ações do admin são auditadas** (`RESET_SENHA`, `NOVO_CODIGO`).

## 4. Código (`core/auth.py`, trechos do reset)

```python
import hashlib, hmac, os, re, secrets

MIN_SENHA = 8
MAX_TENTATIVAS = 5
BLOQUEIO_MIN = 15
_ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I


def hash_senha(senha: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=2**14, r=8, p=1)
    return f"scrypt${sal.hex()}${h.hex()}"


def confere_senha(senha: str, armazenado: str) -> bool:
    try:
        _, sal, h = armazenado.split("$")
        novo = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=2**14, r=8, p=1)
        return hmac.compare_digest(novo.hex(), h)
    except (ValueError, AttributeError):
        return False


# ---------- código de recuperação ----------
def gerar_codigo() -> str:
    """Ex.: K7QM-4XD2-9PBT"""
    c = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(12))
    return f"{c[:4]}-{c[4:8]}-{c[8:]}"

def _normalizar_codigo(codigo) -> str:
    return re.sub(r"[^A-Z0-9]", "", (codigo or "").upper())

def _hash_codigo(codigo: str) -> str:
    return hash_senha(_normalizar_codigo(codigo))

def _confere_codigo(codigo, armazenado) -> bool:
    return bool(armazenado) and confere_senha(_normalizar_codigo(codigo), armazenado)


# ---------- bloqueio por tentativas (compartilhado entre login e redefinição) ----------
def _carregar(db, usuario):
    r = db.query(
        "SELECT *, MAX(0, CAST((julianday(bloqueado_ate) - julianday('now')) * 1440 AS INTEGER) + 1) AS min_restantes, "
        "(bloqueado_ate IS NOT NULL AND bloqueado_ate > datetime('now')) AS bloqueado "
        "FROM ori_usuarios WHERE usuario=?", (usuario,))
    return r[0] if r else None


def _falha(db, u, usuario, o_que):
    """Conta um erro; após MAX_TENTATIVAS bloqueia a conta. Retorna a mensagem a mostrar."""
    erros = (u["tentativas"] or 0) + 1
    if erros >= MAX_TENTATIVAS:
        db.execute("UPDATE ori_usuarios SET tentativas=0, bloqueado_ate=datetime('now', ?) WHERE usuario=?",
                   (f"+{BLOQUEIO_MIN} minutes", usuario))
        return f"Muitas tentativas incorretas. Conta bloqueada por {BLOQUEIO_MIN} minutos."
    db.execute("UPDATE ori_usuarios SET tentativas=? WHERE usuario=?", (erros, usuario))
    return o_que


def _msg_bloqueio(u):
    return f"Muitas tentativas incorretas. Tente novamente em {u['min_restantes']} minuto(s)."


def _sem_sessoes(usuario):
    return ("DELETE FROM ori_sessoes WHERE usuario=?", (usuario,))


# ---------- "Esqueci minha senha" ----------
def redefinir_com_codigo(db, usuario, codigo, nova_senha):
    """Retorna (ok, mensagem, novo_codigo|None). Erros contam nas mesmas 5 tentativas do login."""
    usuario = (usuario or "").strip().lower()
    invalido = "Usuário ou código de recuperação inválidos."
    u = _carregar(db, usuario)
    if not u:
        return False, invalido, None
    if u["bloqueado"]:
        return False, _msg_bloqueio(u), None
    if len(nova_senha or "") < MIN_SENHA:
        return False, f"A nova senha precisa ter ao menos {MIN_SENHA} caracteres.", None
    if not _confere_codigo(codigo, u["codigo_hash"]):
        return False, _falha(db, u, usuario, invalido), None
    novo = gerar_codigo()
    db.batch([  # atômico: ou muda tudo ou nada
        ("UPDATE ori_usuarios SET senha_hash=?, codigo_hash=?, tentativas=0, bloqueado_ate=NULL, trocar_senha=0 "
         "WHERE usuario=?", (hash_senha(nova_senha), _hash_codigo(novo), usuario)),
        _sem_sessoes(usuario),
    ])
    return True, "Senha redefinida. Guarde o novo código de recuperação.", novo


# ---------- troca voluntária (pessoa logada) ----------
def trocar_senha(db, usuario, senha_atual, nova_senha):
    """Retorna (ok, mensagem, codigo|None); gera código se a pessoa ainda não tinha um."""
    u = _carregar(db, (usuario or "").strip().lower())
    if not u or not confere_senha(senha_atual or "", u["senha_hash"]):
        return False, "Senha atual incorreta.", None
    if len(nova_senha or "") < MIN_SENHA:
        return False, f"A nova senha precisa ter ao menos {MIN_SENHA} caracteres.", None
    if confere_senha(nova_senha, u["senha_hash"]):
        return False, "A nova senha deve ser diferente da atual.", None
    codigo = None if u["codigo_hash"] else gerar_codigo()
    db.execute("UPDATE ori_usuarios SET senha_hash=?, trocar_senha=0, codigo_hash=COALESCE(?, codigo_hash) "
               "WHERE usuario=?",
               (hash_senha(nova_senha), _hash_codigo(codigo) if codigo else None, u["usuario"]))
    return True, "Senha alterada.", codigo


# ---------- ações do admin ----------
def senha_temporaria(db, usuario):
    """Gera senha temporária, obriga a troca no próximo acesso e derruba as sessões. Retorna a senha."""
    temporaria = secrets.token_urlsafe(9)
    db.batch([
        ("UPDATE ori_usuarios SET senha_hash=?, trocar_senha=1, tentativas=0, bloqueado_ate=NULL WHERE usuario=?",
         (hash_senha(temporaria), usuario)),
        _sem_sessoes(usuario),
    ])
    return temporaria


def novo_codigo(db, usuario):
    """Admin: outro código para quem perdeu o seu (o anterior deixa de valer)."""
    codigo = gerar_codigo()
    db.execute("UPDATE ori_usuarios SET codigo_hash=? WHERE usuario=?", (_hash_codigo(codigo), usuario))
    return codigo


# ---------- "Minha conta": novo código por conta própria ----------
def novo_codigo_com_senha(db, usuario, senha):
    """Confirma a senha e gera outro código. Erros de senha contam nas tentativas do login."""
    usuario = (usuario or "").strip().lower()
    u = _carregar(db, usuario)
    if not u:
        return False, "Usuário não encontrado.", None
    if u["bloqueado"]:
        return False, _msg_bloqueio(u), None
    if not confere_senha(senha or "", u["senha_hash"]):
        return False, _falha(db, u, usuario, "Senha incorreta."), None
    if u["tentativas"]:
        db.execute("UPDATE ori_usuarios SET tentativas=0 WHERE usuario=?", (usuario,))
    codigo = gerar_codigo()
    db.execute("UPDATE ori_usuarios SET codigo_hash=? WHERE usuario=?", (_hash_codigo(codigo), usuario))
    return True, "Novo código gerado. O anterior deixou de valer.", codigo
```

No cadastro (`registrar_usuario`), gere o código junto com o hash da senha e devolva-o para a tela mostrar: `INSERT INTO ori_usuarios (usuario, nome, senha_hash, codigo_hash) VALUES (?,?,?,?)` com `hash_senha(senha)` e `_hash_codigo(codigo)`. Para o login, `autenticar` deve usar as mesmas `_carregar/_falha/_msg_bloqueio` (é isso que faz login e código dividirem o contador) e zerar `tentativas`/`bloqueado_ate` no acerto.

Sessões que o reset derruba (`core/sessao.py`): o banco guarda só o hash SHA-256 do token do navegador.

```python
def encerrar_outras(db, usuario, token_atual):
    """Depois de trocar a senha: derruba as outras sessões abertas e mantém a atual."""
    db.execute("DELETE FROM ori_sessoes WHERE usuario=? AND token_hash<>?",
               (usuario, hashlib.sha256(token_atual.encode()).hexdigest() if token_atual else ""))
```

Se o SIA não usa tabela de sessões, o equivalente é invalidar o que ele usa para manter o login (cookie/token) quando a senha muda.

## 5. Telas (Streamlit)

**Exibir segredo uma vez** (`core/ui.py`) — usado para código novo e senha temporária:

```python
def mostrar_segredo(chave: str, titulo: str, aviso: str):
    valor = st.session_state.get(chave)
    if not valor:
        return
    with st.container(border=True):
        st.markdown(f"**{titulo}**")
        st.code(valor, language=None)
        st.warning(aviso)
        if st.button("Já guardei", key=f"ok_{chave}"):
            st.session_state.pop(chave, None)
            st.rerun()
```

**Login — aba "Esqueci minha senha"** (`inicio.py`):

```python
AVISO_CODIGO = ("Guarde este código em local seguro. Ele é a única forma de redefinir sua senha sem o "
                "administrador e não será mostrado novamente.")

mostrar_segredo("codigo_novo", "Seu código de recuperação", AVISO_CODIGO)
entrar, cadastrar, esqueci = st.tabs(["Entrar", "Primeiro acesso", "Esqueci minha senha"])
with esqueci:
    st.caption("Use o código de recuperação que você recebeu no cadastro. "
               "Se o perdeu, peça ao administrador uma senha temporária.")
    with st.form("esqueci"):
        login_e = st.text_input("Usuário", key="usuario_esqueci")
        codigo_e = st.text_input("Código de recuperação", placeholder="XXXX-XXXX-XXXX")
        nova_e = st.text_input("Nova senha (mínimo 8 caracteres)", type="password", key="senha_esqueci")
        if st.form_submit_button("Redefinir senha"):
            ok, msg, novo = auth.redefinir_com_codigo(db(), login_e, codigo_e, nova_e)
            if ok:
                st.session_state["codigo_novo"] = novo   # o código novo aparece na próxima execução
                st.rerun()
            st.error(msg)
```

**Senha temporária (admin → pessoa)**: na primeira tela depois do login, se `usuario["trocar_senha"]` for verdadeiro, mostrar só um formulário "Senha temporária + Nova senha" que chama `auth.trocar_senha(...)` e bloquear o resto do app (as demais páginas fazem `st.stop()` enquanto `trocar_senha` estiver ativo).

**Minha conta**: formulário "Trocar a senha" (atual + nova + repita) chamando `auth.trocar_senha`, seguido de `sessao.encerrar_outras(...)`; e formulário "Gerar novo código" (confirma senha) chamando `auth.novo_codigo_com_senha`. Ambos guardam o código em `st.session_state["codigo_novo"]` e chamam `st.rerun()` para `mostrar_segredo` exibi-lo.

**Admin → Usuários** (somente perfil admin):

```python
if c3.button("Redefinir senha"):
    st.session_state["segredo_admin"] = f"Usuário: {login}\nSenha temporária: {usuarios.redefinir_senha(db(), admin, login)}"
if c4.button("Novo código de recuperação"):
    st.session_state["segredo_admin"] = f"Usuário: {login}\nCódigo: {usuarios.gerar_codigo_recuperacao(db(), admin, login)}"
mostrar_segredo("segredo_admin", "Entregue à pessoa (não será mostrado novamente)",
                "A senha temporária obriga a troca no próximo acesso e encerra as sessões abertas dela.")
```

As funções `usuarios.redefinir_senha` / `gerar_codigo_recuperacao` apenas chamam `auth.senha_temporaria` / `auth.novo_codigo` e registram a auditoria (`RESET_SENHA`, `NOVO_CODIGO`) no mesmo lote. Há também um botão "Desbloquear login" que zera `tentativas` e `bloqueado_ate`.

## 6. Testes que valem copiar (`tests/test_auth.py`)

- redefinir com código correto troca a senha, gera **novo** código, o antigo deixa de valer e as sessões da pessoa somem;
- código errado conta tentativas e **bloqueia no 5º erro**; o bloqueio vale também para o login;
- código e senha **não ficam em texto** no banco (`codigo_hash` começa com `scrypt$` e não contém o código);
- usuário sem código não consegue recuperar; usuário inexistente recebe a mesma mensagem que código errado;
- senha nova curta é recusada antes de gastar tentativa;
- senha temporária obriga a troca (`trocar_senha=1`) e derruba sessões; trocar a senha limpa a flag;
- quem não tinha código ganha um ao trocar a senha; o admin consegue gerar outro código; o admin não remove o próprio acesso.

## 7. Cuidados ao levar para o SIA

- O **contador de tentativas é por usuário**, não por IP (o Streamlit não expõe o IP de forma confiável). Aceitável aqui porque o bloqueio é curto e o código tem ~60 bits.
- O app roda no Streamlit Cloud, onde `datetime('now')` do SQLite/Turso é UTC; todo o bloqueio usa o relógio do **banco**, não o do Python, para não depender do fuso.
- Se o SIA usa e-mail para recuperar senha, este fluxo é uma alternativa sem e-mail; o código de recuperação precisa ser entregue/guardado pela pessoa, daí o aviso "não será mostrado novamente".
- O usuário é texto livre (login igual ao do SIGO), normalizado em minúsculas; adapte `_USUARIO` (regex) se o SIA tiver outra regra de login.
