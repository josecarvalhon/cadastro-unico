{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/prata/stg_empresa_a_clientes.parquet'
  )
}}

with src as (
  -- Bronze é imutável: novos runs acumulam Parquets. Aqui escolhemos o
  -- último _ingested_at por id de origem.
  select * from {{ source('bronze', 'empresa_a_clientes') }}
  qualify row_number() over (partition by id order by _ingested_at desc) = 1
),
cleaned as (
  select
    {{ id_unicad("'empresa_a'", "id") }}                          as id_unicad,
    'empresa_a'                                                   as fonte,
    cast(id as varchar)                                           as id_origem,
    'cliente'                                                     as tipo_cadastro,
    coalesce(tipo_pessoa, {{ tipo_pessoa_from_doc(clean_doc('cpf_cnpj')) }}) as tipo_pessoa,
    {{ clean_nome('nome_razao_social') }}                         as nome_razao_social,
    {{ clean_doc('cpf_cnpj') }}                                   as cpf_cnpj,
    {{ doc_kind(clean_doc('cpf_cnpj')) }}                         as cpf_cnpj_kind,
    {{ doc_valid(clean_doc('cpf_cnpj')) }}                        as cpf_cnpj_valido,
    {{ clean_email('email') }}                                    as email,
    {{ to_e164('telefone_principal') }}                           as telefone_principal,
    {{ clean_nome('endereco_cidade') }}                           as cidade,
    {{ clean_uf('endereco_uf') }}                                 as uf,
    to_json(struct_pack(
      endereco_rua    := endereco_rua,
      endereco_numero := endereco_numero,
      endereco_bairro := endereco_bairro,
      endereco_cep    := endereco_cep,
      data_cadastro   := data_cadastro,
      status          := status,
      updated_at      := updated_at
    ))                                                            as atributos_extras,
    _source,
    _ingested_at,
    _batch_id,
    current_timestamp                                             as _processed_at
  from src
)
select * from cleaned
