{#
  Limpia un monto capturado como texto ("$1,234.50", " 684.94 ", NULL) a
  NUMERIC(14,2). try_cast nunca truena la corrida: una fila que no se pueda
  convertir queda NULL, visible para un test not_null aguas abajo en vez de
  reventar el build completo.
#}
{% macro cast_messy_amount(column_name) %}
try_cast(replace(replace(trim({{ column_name }}), '$', ''), ',', '') as decimal(14,2))
{% endmacro %}
