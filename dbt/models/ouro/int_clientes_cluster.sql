{{
  config(
    materialized='external',
    format='parquet',
    location='s3://lakehouse/ouro/int_clientes_cluster.parquet'
  )
}}

{# Atribui um cluster_key a cada cliente Prata em 3 níveis de confiança:
     1. doc:<cpf_cnpj>     — registros com documento válido formam o cluster.
     2. doc:<cpf_cnpj>     — registros SEM documento que compartilham email
                             com um cluster do nível 1 são incorporados.
     3. lone:<id_unicad>   — registros isolados (sem doc e sem email-match)
                             ficam em cluster próprio.
   Também produz match_method para rastreabilidade. #}

with prata as (
  select * from {{ ref('int_clientes_padronizados') }}
),
nivel_1 as (
  select
    *,
    case when cpf_cnpj_valido then 'doc:' || cpf_cnpj else null end as cluster_via_doc
  from prata
),
email_to_cluster as (
  select
    email,
    min(cluster_via_doc) as cluster_via_email
  from nivel_1
  where email is not null and cluster_via_doc is not null
  group by email
)
select
  n.id_unicad,
  n.fonte,
  n.id_origem,
  n.tipo_cadastro,
  n.tipo_pessoa,
  n.nome_razao_social,
  n.cpf_cnpj,
  n.cpf_cnpj_kind,
  n.cpf_cnpj_valido,
  n.email,
  n.telefone_principal,
  n.cidade,
  n.uf,
  n.atributos_extras,
  n._source,
  n._ingested_at,
  n._batch_id,
  n._processed_at,
  coalesce(
    n.cluster_via_doc,
    e.cluster_via_email,
    'lone:' || n.id_unicad
  ) as cluster_key,
  case
    when n.cluster_via_doc is not null     then 'doc_match'
    when e.cluster_via_email is not null   then 'email_to_doc_match'
    else                                        'singleton'
  end as match_method
from nivel_1 n
left join email_to_cluster e using (email)
