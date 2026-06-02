{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/ouro/metricas_qualidade.parquet'
  )
}}

{# Métricas agregadas das camadas Prata e Ouro, lado a lado. Útil para o
   Metabase montar dashboards de qualidade do Cadastro Único. #}

with prata_clientes as (
  select
    'clientes'  as tipo_cadastro,
    fonte,
    count(*) as registros_prata,
    sum(case when cpf_cnpj_valido               then 1 else 0 end) as com_doc_valido,
    sum(case when email is not null             then 1 else 0 end) as com_email,
    sum(case when telefone_principal is not null then 1 else 0 end) as com_telefone,
    sum(case when cidade is not null            then 1 else 0 end) as com_cidade,
    sum(case when uf is not null                then 1 else 0 end) as com_uf
  from {{ ref('int_clientes_padronizados') }}
  group by fonte
),
prata_fornecedores as (
  select
    'fornecedores' as tipo_cadastro,
    fonte,
    count(*) as registros_prata,
    sum(case when cpf_cnpj_valido               then 1 else 0 end) as com_doc_valido,
    sum(case when email is not null             then 1 else 0 end) as com_email,
    sum(case when telefone_principal is not null then 1 else 0 end) as com_telefone,
    sum(case when cidade is not null            then 1 else 0 end) as com_cidade,
    sum(case when uf is not null                then 1 else 0 end) as com_uf
  from {{ ref('int_fornecedores_padronizados') }}
  group by fonte
),
prata as (
  select * from prata_clientes union all by name select * from prata_fornecedores
),
ouro_clientes as (
  select 'clientes' as tipo_cadastro, count(*) as registros_ouro,
         avg(score_completude) as score_completude_medio,
         avg(total_fontes::DOUBLE) as fontes_medias_por_registro,
         sum(case when total_fontes > 1 then 1 else 0 end) as registros_multi_fonte
  from {{ ref('golden_clientes') }}
),
ouro_fornecedores as (
  select 'fornecedores' as tipo_cadastro, count(*) as registros_ouro,
         avg(score_completude) as score_completude_medio,
         avg(total_fontes::DOUBLE) as fontes_medias_por_registro,
         sum(case when total_fontes > 1 then 1 else 0 end) as registros_multi_fonte
  from {{ ref('golden_fornecedores') }}
),
ouro as (
  select * from ouro_clientes union all by name select * from ouro_fornecedores
),
por_fonte as (
  select
    p.tipo_cadastro,
    p.fonte,
    p.registros_prata,
    p.com_doc_valido,
    p.com_email,
    p.com_telefone,
    p.com_cidade,
    p.com_uf,
    round(p.com_doc_valido * 1.0 / nullif(p.registros_prata, 0), 3) as pct_doc_valido,
    round(p.com_email      * 1.0 / nullif(p.registros_prata, 0), 3) as pct_email,
    round(p.com_telefone   * 1.0 / nullif(p.registros_prata, 0), 3) as pct_telefone,
    round(p.com_cidade     * 1.0 / nullif(p.registros_prata, 0), 3) as pct_cidade,
    null::DOUBLE as score_completude_medio,
    null::DOUBLE as fontes_medias_por_registro,
    null::BIGINT as registros_multi_fonte,
    null::BIGINT as registros_ouro,
    null::DOUBLE as taxa_deduplicacao
  from prata p
),
totais_prata as (
  select tipo_cadastro, sum(registros_prata) as total_prata
  from prata group by tipo_cadastro
),
agregado as (
  select
    o.tipo_cadastro,
    '_TOTAL'                                       as fonte,
    tp.total_prata                                 as registros_prata,
    null::BIGINT                                   as com_doc_valido,
    null::BIGINT                                   as com_email,
    null::BIGINT                                   as com_telefone,
    null::BIGINT                                   as com_cidade,
    null::BIGINT                                   as com_uf,
    null::DOUBLE                                   as pct_doc_valido,
    null::DOUBLE                                   as pct_email,
    null::DOUBLE                                   as pct_telefone,
    null::DOUBLE                                   as pct_cidade,
    round(o.score_completude_medio, 3)             as score_completude_medio,
    round(o.fontes_medias_por_registro, 3)         as fontes_medias_por_registro,
    o.registros_multi_fonte                        as registros_multi_fonte,
    o.registros_ouro                               as registros_ouro,
    round(1.0 - (o.registros_ouro * 1.0 / nullif(tp.total_prata, 0)), 3) as taxa_deduplicacao
  from ouro o
  join totais_prata tp using (tipo_cadastro)
)
select * from por_fonte
union all by name
select * from agregado
order by tipo_cadastro, fonte
