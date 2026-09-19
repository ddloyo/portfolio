{#
  Llave de dim_mes: año * 100 + mes (2026-08-15 → 202608). Determinista y
  legible; se calcula igual en los hechos y en dim_mes, así no hace falta un
  join solo para obtener la llave.
#}
{% macro mes_key(date_expr) %}
(extract(year from {{ date_expr }}) * 100 + extract(month from {{ date_expr }}))::int
{% endmacro %}
