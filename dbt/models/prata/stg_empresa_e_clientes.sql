{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/prata/stg_empresa_e_clientes.parquet'
  )
}}

{# Empresa E (API REST): JSON bem estruturado. address vem como subdoc
   serializado em string pela Bronze; parseamos aqui. Type ('individual' ou
   'business') determina tipo_pessoa. #}

with src as (
  select * from {{ source('bronze', 'empresa_e_clientes') }}
  qualify row_number() over (partition by id order by _ingested_at desc) = 1
),
parsed as (
  select
    *,
    case when address is not null then address::JSON else null end as address_json
  from src
),
cleaned as (
  select
    {{ id_unicad("'empresa_e'", "id") }}                              as id_unicad,
    'empresa_e'                                                       as fonte,
    id                                                                as id_origem,
    'cliente'                                                         as tipo_cadastro,
    case type when 'business' then 'PJ' else 'PF' end                 as tipo_pessoa,
    {{ clean_nome('name') }}                                          as nome_razao_social,
    {{ clean_doc('document') }}                                       as cpf_cnpj,
    {{ doc_kind(clean_doc('document')) }}                             as cpf_cnpj_kind,
    {{ doc_valid(clean_doc('document')) }}                            as cpf_cnpj_valido,
    {{ clean_email('email') }}                                        as email,
    {{ to_e164('phone') }}                                            as telefone_principal,
    {{ clean_nome("address_json ->> 'city'") }}                       as cidade,
    {{ clean_uf("address_json ->> 'state'") }}                        as uf,
    to_json(struct_pack(
      type       := type,
      tags       := tags,
      created_at := created_at,
      updated_at := updated_at,
      address    := address
    ))                                                                as atributos_extras,
    _source,
    _ingested_at,
    _batch_id,
    current_timestamp                                                 as _processed_at
  from parsed
)
select * from cleaned
