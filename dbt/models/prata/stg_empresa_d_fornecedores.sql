{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/prata/stg_empresa_d_fornecedores.parquet'
  )
}}

with src as (
  select * from {{ source('bronze', 'empresa_d_fornecedores') }}
  qualify row_number() over (
    partition by "Documento", "Nome" order by _ingested_at desc
  ) = 1
),
extracted as (
  select
    *,
    {{ clean_doc('"Documento"') }} as doc_limpo,
    regexp_extract("Endereco", '-[[:space:]]*([A-Za-z]{2})[[:space:]]*$', 1) as uf_extraida,
    regexp_extract("Endereco", ',[[:space:]]*([^,]+?)[[:space:]]*-[[:space:]]*[A-Za-z]{2}[[:space:]]*$', 1) as cidade_extraida
  from src
),
cleaned as (
  select
    {{ id_unicad("'empresa_d_forn'", "doc_limpo || '|' || coalesce(\"Nome\", '')") }} as id_unicad,
    'empresa_d'                                                       as fonte,
    {{ clean_doc('"Documento"') }}                                    as id_origem,
    'fornecedor'                                                      as tipo_cadastro,
    {{ tipo_pessoa_from_doc('doc_limpo') }}                           as tipo_pessoa,
    {{ clean_nome('"Nome"') }}                                        as nome_razao_social,
    doc_limpo                                                         as cpf_cnpj,
    {{ doc_kind('doc_limpo') }}                                       as cpf_cnpj_kind,
    {{ doc_valid('doc_limpo') }}                                      as cpf_cnpj_valido,
    {{ clean_email('"Email"') }}                                      as email,
    {{ to_e164('"Fone"') }}                                           as telefone_principal,
    nullif({{ clean_nome('cidade_extraida') }}, '')                   as cidade,
    {{ clean_uf('uf_extraida') }}                                     as uf,
    to_json(struct_pack(
      endereco_original := "Endereco",
      observacoes       := "Obs",
      documento_bruto   := "Documento",
      telefone_bruto    := "Fone"
    ))                                                                as atributos_extras,
    _source,
    _ingested_at,
    _batch_id,
    current_timestamp                                                 as _processed_at
  from extracted
)
select * from cleaned
