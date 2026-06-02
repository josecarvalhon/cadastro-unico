{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/prata/stg_empresa_b_clientes.parquet'
  )
}}

{# Empresa B (CRM digital): só PF, sem CPF nem endereço. Redes sociais e
   preferências de canal vão para atributos_extras. #}

with src as (
  select * from {{ source('bronze', 'empresa_b_clientes') }}
  qualify row_number() over (partition by client_id order by _ingested_at desc) = 1
),
cleaned as (
  select
    {{ id_unicad("'empresa_b'", "client_id") }}                   as id_unicad,
    'empresa_b'                                                   as fonte,
    cast(client_id as varchar)                                    as id_origem,
    'cliente'                                                     as tipo_cadastro,
    'PF'                                                          as tipo_pessoa,
    {{ clean_nome('full_name') }}                                 as nome_razao_social,
    null                                                          as cpf_cnpj,
    null                                                          as cpf_cnpj_kind,
    false                                                         as cpf_cnpj_valido,
    {{ clean_email('email') }}                                    as email,
    {{ to_e164('phone') }}                                        as telefone_principal,
    null                                                          as cidade,
    null                                                          as uf,
    to_json(struct_pack(
      instagram_handle  := instagram_handle,
      twitter_handle    := twitter_handle,
      facebook_url      := facebook_url,
      preferred_channel := preferred_channel,
      signup_date       := signup_date,
      last_active       := last_active
    ))                                                            as atributos_extras,
    _source,
    _ingested_at,
    _batch_id,
    current_timestamp                                             as _processed_at
  from src
)
select * from cleaned
