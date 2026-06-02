-- Empresa A — Rede de Varejo
-- Schema relacional normalizado conforme seção 4.2 do documento.

CREATE TABLE IF NOT EXISTS clientes (
    id              SERIAL PRIMARY KEY,
    tipo_pessoa     CHAR(2) NOT NULL CHECK (tipo_pessoa IN ('PF', 'PJ')),
    nome_razao_social TEXT NOT NULL,
    cpf_cnpj        VARCHAR(20) NOT NULL,
    endereco_rua    TEXT,
    endereco_numero VARCHAR(20),
    endereco_bairro TEXT,
    endereco_cidade TEXT,
    endereco_uf     CHAR(2),
    endereco_cep    VARCHAR(10),
    telefone_principal VARCHAR(20),
    email           TEXT,
    data_cadastro   DATE NOT NULL DEFAULT CURRENT_DATE,
    status          VARCHAR(20) NOT NULL DEFAULT 'ativo',
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id              SERIAL PRIMARY KEY,
    tipo_pessoa     CHAR(2) NOT NULL CHECK (tipo_pessoa IN ('PF', 'PJ')),
    nome_razao_social TEXT NOT NULL,
    cpf_cnpj        VARCHAR(20) NOT NULL,
    endereco_rua    TEXT,
    endereco_numero VARCHAR(20),
    endereco_bairro TEXT,
    endereco_cidade TEXT,
    endereco_uf     CHAR(2),
    endereco_cep    VARCHAR(10),
    telefone_principal VARCHAR(20),
    email           TEXT,
    data_cadastro   DATE NOT NULL DEFAULT CURRENT_DATE,
    status          VARCHAR(20) NOT NULL DEFAULT 'ativo',
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clientes_cpf_cnpj ON clientes(cpf_cnpj);
CREATE INDEX IF NOT EXISTS idx_fornecedores_cpf_cnpj ON fornecedores(cpf_cnpj);
