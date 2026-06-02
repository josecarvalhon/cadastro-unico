{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/prata/int_fornecedores_padronizados.parquet'
  )
}}

select * from {{ ref('stg_empresa_a_fornecedores') }}
union all by name
select * from {{ ref('stg_empresa_c_fornecedores') }}
union all by name
select * from {{ ref('stg_empresa_d_fornecedores') }}
