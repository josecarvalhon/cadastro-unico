{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/ouro/golden_fornecedores.parquet'
  )
}}

with cluster as (
  select * from {{ ref('int_fornecedores_cluster') }}
),
agg as (
  select
    cluster_key,
    mode(tipo_pessoa)                              as tipo_pessoa,
    arg_max(nome_razao_social, length(coalesce(nome_razao_social, '')))
                                                   as nome_razao_social,
    any_value(cpf_cnpj) filter (where cpf_cnpj_valido)
                                                   as cpf_cnpj,
    any_value(cpf_cnpj_kind) filter (where cpf_cnpj_valido)
                                                   as cpf_cnpj_kind,
    array_agg(distinct email) filter (where email is not null)
                                                   as emails,
    array_agg(distinct telefone_principal) filter (where telefone_principal is not null)
                                                   as telefones,
    array_agg(distinct struct_pack(cidade := cidade, uf := uf, fonte := fonte))
      filter (where cidade is not null or uf is not null)
                                                   as enderecos,
    array_agg(distinct fonte order by fonte)       as fontes,
    count(distinct fonte)                          as total_fontes,
    array_agg(distinct match_method)               as metodos_match,
    map_from_entries(
      list(distinct struct_pack(k := fonte, v := id_origem))
    )                                              as ids_origem,
    array_agg(struct_pack(fonte := fonte, atributos := atributos_extras))
                                                   as atributos_por_fonte,
    min(_ingested_at)                              as primeira_aparicao,
    max(_ingested_at)                              as ultima_atualizacao
  from cluster
  group by cluster_key
)
select
  md5(cluster_key)                                 as id_golden,
  cluster_key,
  tipo_pessoa,
  nome_razao_social,
  cpf_cnpj,
  cpf_cnpj_kind,
  emails,
  telefones,
  enderecos,
  fontes,
  total_fontes,
  metodos_match,
  ids_origem,
  atributos_por_fonte,
  (
    (case when nome_razao_social is not null then 1 else 0 end)
  + (case when cpf_cnpj         is not null then 1 else 0 end)
  + (case when array_length(emails)    > 0  then 1 else 0 end)
  + (case when array_length(telefones) > 0  then 1 else 0 end)
  + (case when array_length(enderecos) > 0  then 1 else 0 end)
  + (case when tipo_pessoa      is not null then 1 else 0 end)
  + (case when total_fontes      > 1        then 1 else 0 end)
  + (case when array_length(atributos_por_fonte) > 0 then 1 else 0 end)
  ) / 8.0                                          as score_completude,
  primeira_aparicao,
  ultima_atualizacao,
  1                                                as versao,
  current_timestamp                                as _processed_at
from agg
