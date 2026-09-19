{#
  Bronze aterriza TODO como TEXT (así lo definía el DDL original de bronze): la zona de
  aterrizaje no debe fallar ni interpretar nada, sin importar qué tan sucia
  venga la fuente. Por defecto dbt infiere el tipo de cada columna del seed
  y DuckDB truena si una fila tardía no calza con lo que infirió de las
  primeras ("$1,234.50" en una columna numérica, fechas mixtas).

  Este override del macro de dbt-duckdb crea todas las columnas como varchar.
  Sigue respetando `+column_types` por si algún seed necesitara un tipo
  específico, pero ninguno lo necesita: tipar es trabajo de staging.
#}
{% macro duckdb__create_csv_table(model, agate_table) %}
  {%- set column_override = model['config'].get('column_types', {}) -%}
  {%- set quote_seed_column = model['config'].get('quote_columns', None) -%}

  {% set sql %}
    create table {{ this.render() }} (
        {%- for col_name in agate_table.column_names -%}
            {%- set type = column_override.get(col_name, 'varchar') -%}
            {%- set column_name = (col_name | string) -%}
            {{ adapter.quote_seed_column(column_name, quote_seed_column) }} {{ type }} {%- if not loop.last -%}, {%- endif -%}
        {%- endfor -%}
    )
  {% endset %}

  {% call statement('_') -%}
    {{ sql }}
  {%- endcall %}

  {{ return(sql) }}
{% endmacro %}
