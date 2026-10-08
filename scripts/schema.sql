CREATE TABLE IF NOT EXISTS ori_prestadores (
  documento TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  codigo TEXT,
  tipo TEXT,
  cidade TEXT,
  uf TEXT,
  origem TEXT NOT NULL DEFAULT 'base',
  criado_por TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ori_desvios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL UNIQUE,
  texto_padrao TEXT NOT NULL DEFAULT '',
  ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ori_usuarios (
  usuario TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  senha_hash TEXT NOT NULL,
  perfil TEXT NOT NULL DEFAULT 'contas' CHECK (perfil IN ('contas','gestor','admin')),
  status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','ativo','inativo')),
  tentativas INTEGER NOT NULL DEFAULT 0,
  bloqueado_ate TEXT,
  codigo_hash TEXT,
  trocar_senha INTEGER NOT NULL DEFAULT 0,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ori_sessoes (
  token_hash TEXT PRIMARY KEY,
  usuario TEXT NOT NULL,
  expira_em TEXT NOT NULL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ori_orientacoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  documento TEXT NOT NULL REFERENCES ori_prestadores(documento),
  desvio_id INTEGER NOT NULL REFERENCES ori_desvios(id),
  data_orientacao TEXT NOT NULL,
  numero_orientacao INTEGER NOT NULL,
  acao TEXT,
  credenciamento_sinalizado TEXT CHECK (credenciamento_sinalizado IN ('SIM','NAO')),
  observacao TEXT,
  criado_por TEXT NOT NULL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  excluido_em TEXT,
  excluido_por TEXT
);
CREATE INDEX IF NOT EXISTS ix_ori_doc_desvio ON ori_orientacoes(documento, desvio_id) WHERE excluido_em IS NULL;
CREATE TABLE IF NOT EXISTS ori_auditoria (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quando TEXT NOT NULL DEFAULT (datetime('now')),
  quem TEXT NOT NULL,
  tabela TEXT NOT NULL,
  registro TEXT NOT NULL,
  acao TEXT NOT NULL,
  antes TEXT,
  depois TEXT
)
