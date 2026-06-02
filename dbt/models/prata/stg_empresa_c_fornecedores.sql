{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/prata/stg_empresa_c_fornecedores.parquet'
  )
}}

{# Empresa C (MongoDB): documentos com schema flexível. Bronze já transformou
   subdocs/arrays em JSON-string para Parquet. Aqui parseamos esses JSONs
   para extrair endereço estruturado e levar o resto para atributos_extras. #}

with src as (
  select * from {{ source('bronze', 'empresa_c_fornecedores') }}
  qualify row_number() over (partition by _id order by _ingested_at desc) = 1
),
parsed as (
  select
    *,
    case when endereco is not null then endereco::JSON else null end as endereco_json
  from src
),
cleaned as (
  select
    {{ id_unicad("'empresa_c'", "_id") }}                             as id_unicad,
    'empresa_c'                                                       as fonte,
    _id                                                               as id_origem,
    'fornecedor'                                                      as tipo_cadastro,
    'PJ'                                                              as tipo_pessoa,
    {{ clean_nome('razao_social') }}                                  as nome_razao_social,
    {{ clean_doc('cnpj') }}                                           as cpf_cnpj,
    {{ doc_kind(clean_doc('cnpj')) }}                                 as cpf_cnpj_kind,
    {{ doc_valid(clean_doc('cnpj')) }}                                as cpf_cnpj_valido,
    {{ clean_email('contato_email') }}                                as email,
    {{ to_e164('contato_telefone') }}                                 as telefone_principal,
    {{ clean_nome("endereco_json ->> 'cidade'") }}                    as cidade,
    {{ clean_uf("endereco_json ->> 'uf'") }}                          as uf,
    to_json(struct_pack(
      contato_nome    := contato_nome,
      categorias      := categorias,
      certificacoes   := certificacoes,
      avaliacao_media := avaliacao_media,
      data_cadastro   := data_cadastro,
      dados_bancarios := dados_bancarios,
      observacoes     := observacoes,
      endereco        := endereco
    ))                                                                as atributos_extras,
    _source,
    _ingested_at,
    _batch_id,
    current_timestamp                                                 as _processed_at
  from parsed
)
select * from cleaned
