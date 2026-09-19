{#
  Prueba una lista ordenada de formatos de fecha y devuelve el primero que
  parsea (try_strptime devuelve NULL si no matchea, nunca truena). El orden
  importa: se declara explícito por modelo en vez de "adivinar" un orden
  genérico, porque DD/MM y MM/DD son ambiguos para días <= 12 — cada fuente
  conoce su propio formato, staging no debería tener que adivinarlo.

  Uso: {{ parse_messy_date('fecha_alta', ['%m/%d/%Y', '%Y-%m-%d']) }}
#}
{% macro parse_messy_date(column_name, formats=['%Y-%m-%d']) %}
coalesce(
    {%- for fmt in formats %}
    try_strptime(trim({{ column_name }}), '{{ fmt }}')::date{% if not loop.last %},{% endif %}
    {%- endfor %}
)
{% endmacro %}
