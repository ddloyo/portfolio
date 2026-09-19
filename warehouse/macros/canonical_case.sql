{#
  Normaliza un campo de catálogo a su forma canónica: 'BELLEZA', ' belleza '
  y 'Belleza' → 'Belleza'. DuckDB no trae initcap() y los valores llevan
  acentos y varias palabras ('Ciudad de México'), así que se compara contra la
  lista de valores válidos en vez de intentar poner mayúsculas por regla.

  Un valor que no esté en la lista NO se descarta: se conserva recortado,
  para que un test accepted_values lo haga visible en vez de volverse NULL en
  silencio. Vacío/nulo → NULL.

  Uso: {{ canonical_case('segmento', ['Básico', 'Estándar', 'Premium']) }}
#}
{% macro canonical_case(column_name, values) %}
case lower(trim({{ column_name }}))
    {%- for v in values %}
    when lower('{{ v }}') then '{{ v }}'
    {%- endfor %}
    else nullif(trim({{ column_name }}), '')
end
{% endmacro %}
