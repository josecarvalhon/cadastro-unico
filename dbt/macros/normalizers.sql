{# ---------- Documento (CPF/CNPJ) ---------- #}
{# Devolve apenas dígitos. NULL se entrada nula/vazia. #}
{% macro clean_doc(col) %}
  nullif(regexp_replace(coalesce({{ col }}, ''), '[^0-9]', '', 'g'), '')
{% endmacro %}

{# Classifica o documento limpo: 'CPF' (11), 'CNPJ' (14), NULL caso contrário. #}
{% macro doc_kind(clean_col) %}
  case length({{ clean_col }})
    when 11 then 'CPF'
    when 14 then 'CNPJ'
    else null
  end
{% endmacro %}

{# Marca se o documento tem comprimento legal (sem checar dígito verificador,
   que requereria função Python — fica para um modelo Python futuro).
   Rejeita também "11111111111" e similares verificando se sobra algum
   caractere após remover repetições do primeiro. #}
{% macro doc_valid(clean_col) %}
  length({{ clean_col }}) in (11, 14)
  and length(replace({{ clean_col }}, substr({{ clean_col }}, 1, 1), '')) > 0
{% endmacro %}

{# ---------- Telefone ---------- #}
{# Heurística: extrai só dígitos. Se tem 11 ou 10, adiciona '55' na frente.
   Se já tem 12-13 (com 55), mantém. Caso contrário NULL. #}
{% macro to_e164(col) %}
  case
    when {{ col }} is null then null
    when length(regexp_replace({{ col }}, '[^0-9]', '', 'g')) in (10, 11)
      then '+55' || regexp_replace({{ col }}, '[^0-9]', '', 'g')
    when length(regexp_replace({{ col }}, '[^0-9]', '', 'g')) in (12, 13)
      then '+' || regexp_replace({{ col }}, '[^0-9]', '', 'g')
    else null
  end
{% endmacro %}

{# ---------- E-mail ---------- #}
{% macro clean_email(col) %}
  case
    when {{ col }} is null then null
    when trim(lower({{ col }})) = '' then null
    when trim(lower({{ col }})) ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then trim(lower({{ col }}))
    else null
  end
{% endmacro %}

{# ---------- Nome ---------- #}
{# Colapsa espaços, faz trim, padroniza title case. #}
{% macro clean_nome(col) %}
  nullif(regexp_replace(trim({{ col }}), '[[:space:]]+', ' ', 'g'), '')
{% endmacro %}

{# ---------- UF ---------- #}
{% macro clean_uf(col) %}
  case
    when {{ col }} is null then null
    when length(trim(upper({{ col }}))) = 2 then trim(upper({{ col }}))
    else null
  end
{% endmacro %}

{# ---------- ID único determinístico ---------- #}
{# md5(_source || '|' || id_origem) gera UUID estável que sobrevive a
   reprocessamentos. Permite rerun idempotente. #}
{% macro id_unicad(source_col, id_origem_col) %}
  md5({{ source_col }} || '|' || cast({{ id_origem_col }} as varchar))
{% endmacro %}

{# ---------- Tipo de pessoa derivado do documento ---------- #}
{% macro tipo_pessoa_from_doc(clean_col) %}
  case length({{ clean_col }})
    when 11 then 'PF'
    when 14 then 'PJ'
    else null
  end
{% endmacro %}
