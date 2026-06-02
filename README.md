# Cadastro Único — Plataforma Unificada de Cadastros para Holdings

Projeto da disciplina **Engenharia de Dados — CEUB**. Implementa um **Data Lakehouse com Arquitetura Medalhão** (Bronze → Prata → Ouro
) que unifica cadastros de clientes e fornecedores fragmentados entre 5 subsidiárias fictícias de uma holding, cada uma com sistema e schema diferentes.

A especificação está em [`Cadastro_Unico_Projeto_para_gerar.pdf`](Cadastro_Unico_Projeto_para_gerar.pdf).

## Arquitetura

```
┌──────────────────────┐ ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│   MONITORAMENTO      │ │ Empresa A  │  │ Empresa B  │  │ Empresa C  │  │ Empresa D  │  │ Empresa E  │
│     Elementary       │ │ PostgreSQL │  │   MySQL    │  │  MongoDB   │  │   CSV      │  │  API REST  │
│ ──────────────────── │ └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
│                      │       │               │               │               │               │
│ • freshness          │       └──────┬────────┴───────┬───────┴───────┬───────┴───────┬───────┘
│ • volume_anomalies   │              │ ingest.bronze.*│               │               │
│ • dimension_anomalies│              ▼                ▼               ▼               ▼
│ • schema_changes     │     ┌───────────────────────────────────────────────────────────┐
│ • test runs          │ ──► │           Bronze — Parquet bruto no MinIO                 │
│                      │     │           s3://lakehouse/bronze/{empresa}/{tipo}/         │
│                      │     └─────────────────────────────┬─────────────────────────────┘
│                      │                          dbt run  │ (stg_*)
│                      │                                   ▼
│                      │     ┌───────────────────────────────────────────────────────────┐
│                      │ ──► │     Prata — schema comum + atributos_extras (JSON)        │
│                      │     │   int_clientes_padronizados • int_fornecedores_padroniz.  │
│                      │     └─────────────────────────────┬─────────────────────────────┘
│                      │                          dbt run  │ (clusters + golden)
│                      │                                   ▼
│                      │     ┌───────────────────────────────────────────────────────────┐
│ → docs/              │ ──► │       Ouro — Golden Records (1 linha = 1 entidade)        │
│   elementary_        │     │   golden_clientes • golden_fornecedores • metricas_qual.  │
│   report.html        │     └─────────────────────────────┬─────────────────────────────┘
│                      │                                   │
└──────────────────────┘                ┌──────────────────┴──────────────────┐
                                        ▼                                     ▼
                                ┌───────────────┐                    ┌────────────────┐
                                │ FastAPI       │                    │ Shell DuckDB   │
                                │ /clientes/... │                    │ ad-hoc SQL     │
                                └───────────────┘                    └────────────────┘
```

**Stack:** Python · MinIO · Parquet · DuckDB · dbt-duckdb · Airflow 2.10 · FastAPI · Elementary · Docker Compose.

## Pré-requisitos

- Docker Desktop
- Python 3.11+
- `make`

## Quick start

```bash
make generate         # gera dados sintéticos das 5 fontes (universo determinístico, seed 42)
make up               # sobe a infra (5 fontes + MinIO + Airflow)
make ingest-bronze    # extrai das fontes para Parquet/Bronze no MinIO
make dbt-run          # roda Prata + Ouro (instala packages dbt na primeira vez)
make dbt-test         # 45 testes de qualidade
make monitor          # source freshness + relatório Elementary em docs/elementary_report.html
make api-run          # API em http://localhost:8000 (Swagger em /docs)
```

Ou tudo via Airflow:

```bash
make up                  # já inclui o Airflow
make airflow-password    # imprime/reseta senha admin
# → http://localhost:8080  (login: admin)
make airflow-trigger     # dispara a DAG cadastro_unico_etl
```

## Acessos

| Serviço          | URL                          | Credenciais                              |
| ---------------- | ---------------------------- | ---------------------------------------- |
| MinIO Console    | http://localhost:9003        | `minioadmin` / `minioadmin`              |
| MinIO S3 API     | http://localhost:9002        | `minioadmin` / `minioadmin`              |
| Airflow UI       | http://localhost:8080        | `admin` / (ver `make airflow-password`)  |
| FastAPI          | http://localhost:8000        | sem auth (dev)                           |
| PostgreSQL (A)   | `localhost:5433/varejo`      | `empresa_a` / `empresa_a`                |
| MySQL (B)        | `localhost:3306/servicos_digitais` | `empresa_b` / `empresa_b`          |
| MongoDB (C)      | `localhost:27017/industria`  | `empresa_c` / `empresa_c`                |
| Mock API (E)     | http://localhost:8081/health | —                                        |

Empresa D não tem container — os CSVs ficam em `data/seed/empresa_d/`.

## Como consumir os dados

São dois caminhos previstos:

### 1. Pela API (FastAPI)

Pensada para uso programático por sistemas (CRMs, integrações). Lê os Parquets da Ouro direto do MinIO via DuckDB embarcado. Documentação interativa em http://localhost:8000/docs.

| Endpoint                                  | Função                                                                 |
| ----------------------------------------- | ---------------------------------------------------------------------- |
| `GET /health`                             | Conta golden_clientes e golden_fornecedores                            |
| `GET /api/v1/metricas`                    | Devolve `metricas_qualidade` em JSON                                   |
| `GET /api/v1/clientes/buscar`             | Filtros: `q`, `doc`, `email`, `telefone`, `cidade`, `uf`, `page`, `per_page` |
| `GET /api/v1/clientes/{id_golden}`        | Detalhes completos do cliente                                          |
| `GET /api/v1/fornecedores/buscar`         | Idem para fornecedores                                                 |
| `GET /api/v1/fornecedores/{id_golden}`    | Detalhes do fornecedor                                                 |
| `GET /api/v1/entidade/{id_golden}`        | Resolve em ambos os cadastros (cliente OU fornecedor)                  |

Filtros combinam com AND. CPF/CNPJ são normalizados (`265.423.511-40` ou `26542351140` produzem o mesmo resultado). Strings de texto usam ILIKE; arrays (emails, telefones, endereços) usam matching parcial.

### 2. Por consulta direta no banco

Pensado para análise exploratória, auditoria e relatórios ad-hoc. O script abre um shell DuckDB já conectado ao MinIO com **todas as views Bronze/Prata/Ouro registradas**.

```bash
make sql                                  # REPL interativo
python scripts/sql.py -c "SELECT ..."     # query única
python scripts/sql.py -f query.sql        # roda um arquivo
```

Views disponíveis: `bronze_all`, `stg_empresa_*` (7), `int_*_padronizados` (2), `int_*_cluster` (2), `golden_clientes`, `golden_fornecedores`, `metricas_qualidade`.

Quem preferir outras ferramentas (DBeaver, TablePlus, jupyter, etc.) pode conectar diretamente no DuckDB — basta replicar o setup do secret S3 do script.

## 5 exemplos via API

### 1. Sanity check da plataforma

```bash
curl http://localhost:8000/health
```
```json
{"status":"ok","clientes":250,"fornecedores":150}
```

### 2. Buscar cliente pelo CPF (com ou sem pontuação)

```bash
curl 'http://localhost:8000/api/v1/clientes/buscar?doc=265.423.511-40' | jq '.data[0] | {nome:.nome_razao_social, fontes, total_fontes}'
```
```json
{
  "nome": "Caleb Garcia",
  "fontes": ["empresa_a", "empresa_b", "empresa_d", "empresa_e"],
  "total_fontes": 4
}
```
A API normaliza o documento removendo pontuação antes de comparar — usar `26542351140` produz o mesmo resultado.

### 3. Listar fornecedores em uma UF, paginado

```bash
curl 'http://localhost:8000/api/v1/fornecedores/buscar?uf=MG&per_page=3' | jq '{total, retornados:(.data|length), nomes:[.data[].nome_razao_social]}'
```
```json
{
  "total": 8,
  "retornados": 3,
  "nomes": ["Oliveira", "Pimenta e Filhos", "Brito Cunha - EI"]
}
```

### 4. Detalhes completos de uma entidade (rastreabilidade por fonte)

```bash
curl http://localhost:8000/api/v1/entidade/79c8d460663307a654c022a90ea6071f | jq '{nome:.nome_razao_social, ids_origem, contribuiram:[.atributos_por_fonte[].fonte]}'
```
```json
{
  "nome": "Caleb Garcia",
  "ids_origem": {
    "empresa_a": "3",
    "empresa_b": "3",
    "empresa_d": "26542351140",
    "empresa_e": "90261d4c-88ba-135e-bd3b-17eb29529420"
  },
  "contribuiram": ["empresa_a", "empresa_b", "empresa_d", "empresa_e"]
}
```
O campo `ids_origem` mapeia cada subsidiária ao ID original do registro lá — base para LGPD/auditoria.

### 5. KPIs de qualidade por fonte

```bash
curl http://localhost:8000/api/v1/metricas | jq '.[] | select(.tipo_cadastro=="clientes") | {fonte, registros_prata, pct_doc_valido, pct_email}'
```
```json
{"fonte":"_TOTAL",   "registros_prata":310,"pct_doc_valido":null,"pct_email":null}
{"fonte":"empresa_a","registros_prata":60, "pct_doc_valido":1.0, "pct_email":1.0}
{"fonte":"empresa_b","registros_prata":100,"pct_doc_valido":0.0, "pct_email":1.0}
{"fonte":"empresa_d","registros_prata":50, "pct_doc_valido":1.0, "pct_email":0.86}
{"fonte":"empresa_e","registros_prata":100,"pct_doc_valido":1.0, "pct_email":1.0}
```

## 5 exemplos via SQL direto

### 1. "Quantos clientes únicos a holding atende?" (pergunta literal do PDF)

```sql
SELECT
  COUNT(*) AS clientes_unicos,
  COUNT(*) FILTER (WHERE total_fontes > 1) AS em_mais_de_uma_subsidiaria
FROM golden_clientes;
```
```
 clientes_unicos  em_mais_de_uma_subsidiaria
             250                          25
```

### 2. Fornecedores compartilhados entre subsidiárias (TOP 5)

```sql
SELECT nome_razao_social, cpf_cnpj, total_fontes, fontes
FROM golden_fornecedores
WHERE total_fontes > 1
ORDER BY total_fontes DESC, nome_razao_social
LIMIT 5;
```
```
nome_razao_social       cpf_cnpj  total_fontes                            fontes
   Aparecida S.A. 69691557000111             3 [empresa_a, empresa_c, empresa_d]
             Leão 22579050000100             3 [empresa_a, empresa_c, empresa_d]
         Oliveira 82586736000155             3 [empresa_a, empresa_c, empresa_d]
Rezende Rios - ME 33419182000199             3 [empresa_a, empresa_c, empresa_d]
      Vargas - ME 34125286000155             3 [empresa_a, empresa_c, empresa_d]
```

### 3. Distribuição geográfica dos clientes por UF (TOP 5)

```sql
SELECT e.uf, COUNT(DISTINCT id_golden) AS clientes
FROM golden_clientes, unnest(enderecos) AS t(e)
GROUP BY e.uf
ORDER BY clientes DESC
LIMIT 5;
```
```
uf  clientes
MT        13
SC        11
TO        10
PB         9
GO         9
```
Usa `UNNEST` para explodir o array de endereços (1 cliente pode ter múltiplos endereços, vindos de fontes diferentes).

### 4. Qualidade dos dados por fonte (visão diretoria)

```sql
SELECT fonte,
       registros_prata,
       pct_doc_valido,
       pct_email,
       pct_cidade
FROM metricas_qualidade
WHERE tipo_cadastro = 'clientes' AND fonte != '_TOTAL'
ORDER BY fonte;
```
```
    fonte  registros_prata  pct_doc_valido  pct_email  pct_cidade
empresa_a               60            1.00       1.00        1.00
empresa_b              100            0.00       1.00        0.00
empresa_d               50            1.00       0.86        1.00
empresa_e              100            1.00       1.00        1.00
```
Empresa B (CRM digital) não coleta CPF nem endereço — esperado. Empresa D tem qualidade média no email (CSV legado com campos vazios).

### 5. Drill-down LGPD: todos os registros de origem de um cliente

```sql
SELECT g.nome_razao_social AS golden,
       c.fonte,
       c.id_origem,
       c.nome_razao_social AS nome_na_fonte,
       c.email,
       c.telefone_principal
FROM golden_clientes g
JOIN int_clientes_cluster c USING (cluster_key)
WHERE g.id_golden = '79c8d460663307a654c022a90ea6071f'
ORDER BY c.fonte;
```
```
      golden     fonte                            id_origem nome_na_fonte                  email telefone_principal
Caleb Garcia empresa_a                                    3  Caleb Garcia caleb.garcia@gmail.com     +5571912981052
Caleb Garcia empresa_b                                    3  Caleb Garcia caleb.garcia@gmail.com     +5571912981052
Caleb Garcia empresa_d                          26542351140  Caleb Garcia caleb.garcia@gmail.com     +5571912981052
Caleb Garcia empresa_e 90261d4c-88ba-135e-bd3b-17eb29529420  Caleb Garcia caleb.garcia@gmail.com     +5571912981052
```
Cumpre o requisito de **rastreabilidade reversa**: do Golden Record para os registros originais em cada sistema.

## Camadas e modelos

### Bronze — dados brutos

Cada conector grava `bronze/{empresa}/{tipo}/year=YYYY/month=MM/{batch_id}.parquet`. Adiciona 3 colunas de metadados:

| Coluna         | Função                                |
| -------------- | ------------------------------------- |
| `_source`      | Empresa de origem                     |
| `_ingested_at` | Timestamp ISO 8601 UTC da ingestão    |
| `_batch_id`    | UUID do lote                          |

Bronze é **imutável** — runs sucessivos acumulam batches. Reprocessamento e auditoria.

### Prata — schema comum

Os 7 modelos `stg_empresa_*` mapeiam cada fonte para um schema único:

```
id_unicad · fonte · id_origem · tipo_cadastro · tipo_pessoa
nome_razao_social · cpf_cnpj · cpf_cnpj_kind · cpf_cnpj_valido
email · telefone_principal · cidade · uf
atributos_extras (JSON com tudo que não cabe acima)
_source · _ingested_at · _batch_id · _processed_at
```

Normalizações (em [`dbt/macros/normalizers.sql`](dbt/macros/normalizers.sql)):

- **CPF/CNPJ**: só dígitos + flag de validade (tamanho + não-repetido).
- **Telefone**: E.164 (`+55DDDNNNNNNNN`).
- **Email**: trim + lowercase + regex.
- **Nome/UF**: trim + colapso de espaços / maiúsculas.
- **id_unicad**: `md5(fonte || '|' || id_origem)` — determinístico (idempotência).

Cada `stg_*` aplica `QUALIFY ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _ingested_at DESC) = 1` para escolher apenas o último batch por registro — permite Bronze acumular sem duplicar a Ouro.

`int_clientes_padronizados` (310 linhas) e `int_fornecedores_padronizados` (175) fazem `UNION ALL BY NAME` dos staging.

### Ouro — Golden Records

`int_*_cluster` atribui um `cluster_key` por registro em 3 níveis:

1. **doc_match** — mesmo CPF/CNPJ válido → mesmo cluster.
2. **email_to_doc_match** — sem doc, mas email bate com um cluster doc-based → incorporado.
3. **singleton** — fica sozinho.

`golden_clientes` (250) e `golden_fornecedores` (150) agregam por `cluster_key` produzindo Golden Records com:

- `cpf_cnpj` único e validado.
- Arrays `emails[]`, `telefones[]`, `enderecos[]` (todas as variantes conhecidas).
- `fontes[]`, `total_fontes`, `ids_origem` (MAP fonte→id_origem).
- `score_completude` (0–1) sobre 8 dimensões.
- `atributos_por_fonte` preserva tudo o que cada fonte aportou.
- `primeira_aparicao`, `ultima_atualizacao`.

`metricas_qualidade` calcula KPIs lado a lado Prata × Ouro.

**Resultado da deduplicação:**

| | 1 fonte | 2 fontes | 3 fontes | 4 fontes |
| --- | ---: | ---: | ---: | ---: |
| `golden_clientes`     | 225 | 5  | 5 | 15 |
| `golden_fornecedores` | 130 | 15 | 5 | —  |

## Orquestração com Airflow

A DAG [`cadastro_unico_etl`](airflow/dags/cadastro_unico_etl.py) modela o pipeline analítico:

```
ingest_bronze_empresa_a ─┐
ingest_bronze_empresa_b ─┤
ingest_bronze_empresa_c ─┼─► dbt_run ─► dbt_test
ingest_bronze_empresa_d ─┤
ingest_bronze_empresa_e ─┘
```

Roda dentro do container `cu-airflow` (Airflow 2.10 standalone, SequentialExecutor + SQLite). As 5 tasks Bronze são independentes no grafo — quando migrarmos para LocalExecutor, executam em paralelo sem mudança de código.

A DAG inclui ainda, após `dbt_test`: `dbt_source_freshness` e `edr_report` — alimentam o dashboard de monitoramento (próxima seção). Ambas com `trigger_rule="all_done"` para publicar o relatório mesmo quando algum teste falha (é justamente quando ele importa).

## Monitoramento de dados

[**Elementary**](https://www.elementary-data.com/) como dbt package adiciona observabilidade ao pipeline sem subir nenhum serviço extra. Cobre três lacunas que o `dbt test` puro não cobre:

- **Freshness das fontes Bronze** — `_ingested_at` em cada Parquet alimenta `dbt source freshness`; warn em 12h sem batch, error em 36h.
- **Anomalias de volume e dimensões** — testes em `int_clientes_padronizados`, `int_fornecedores_padronizados` (volume) e na coluna `fonte` (distribuição por subsidiária). Precisam de ~7 runs históricos para baseline confiável.
- **Schema changes** — em `golden_clientes`, sinaliza alterações que possam quebrar o contrato da API.

Estado interno fica no schema `elementary` do DuckDB local (tabelas mutáveis — sobrescreve o default `external`).

```bash
make dbt-deps    # instala Elementary (1ª vez)
make monitor     # roda freshness + testes + gera o HTML
open docs/elementary_report.html
```

O HTML é estático (aplicativo React empacotado num único arquivo) — basta abrir no browser. 4 abas: **Test Results**, **Models** (com freshness + run history), **Dashboard** (anomalias) e **Lineage**. Em produção, dá para publicar num bucket MinIO público; aqui fica em `docs/` gitignored.

## Estrutura de pastas

```
cadastro-unico/
├── infra/                         # docker-compose e configs de cada serviço
│   ├── docker-compose.yml
│   ├── postgres/                  # init.sql + seed.sql (gerado)
│   ├── mysql/                     # init.sql + seed.sql (gerado)
│   ├── mock-api/                  # FastAPI da Empresa E
│   └── airflow/                   # Dockerfile + requirements do Airflow
├── scripts/
│   ├── generate_all.py            # roda os 5 geradores
│   ├── generate/                  # 1 gerador por fonte + universo comum
│   └── sql.py                     # shell DuckDB pré-conectado ao MinIO
├── data/seed/                     # saída dos geradores (gitignored)
├── ingest/
│   ├── config.py                  # configs centralizadas
│   └── bronze/                    # 5 conectores Bronze + utils
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── macros/normalizers.sql     # CPF, telefone, email, etc.
│   └── models/
│       ├── _sources.yml
│       ├── prata/                 # 9 modelos (7 staging + 2 union)
│       └── ouro/                  # 5 modelos (2 cluster + 2 golden + métricas)
├── airflow/dags/                  # DAG analítica
├── api/app/                       # FastAPI (settings, db, search, routers)
└── docs/
```

## Próximas etapas possíveis

- Fuzzy matching de nomes (terceiro nível de dedup com `jaro_winkler_similarity` + blocking).
- Materialização incremental dos modelos dbt (em vez de full-refresh) para escalar.
- Upgrade do Airflow para LocalExecutor com Postgres dedicado (paraleliza Bronze).
- CDC com Debezium + Kafka para uma das fontes (citado na seção 4.2 do PDF).
