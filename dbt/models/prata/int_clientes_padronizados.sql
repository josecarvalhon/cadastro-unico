{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/prata/int_clientes_padronizados.parquet'
  )
}}

{# União de todos os staging de clientes. Schema é homogêneo por construção:
   cada stg_ já produz exatamente as mesmas colunas. #}

select * from {{ ref('stg_empresa_a_clientes') }}
union all by name
select * from {{ ref('stg_empresa_b_clientes') }}
union all by name
select * from {{ ref('stg_empresa_d_clientes') }}
union all by name
select * from {{ ref('stg_empresa_e_clientes') }}
