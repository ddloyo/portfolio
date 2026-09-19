{#
  Override del macro estándar de dbt: si un modelo/seed declara +schema
  (raw, staging, intermediate, marts), úsalo tal cual en vez de concatenarlo
  al schema del target (el default de dbt produce nombres como
  "main_staging"; aquí queremos "staging" a secas para que el DAG y el
  catálogo de dbt docs se lean limpios).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
