{#
  Sella `_loaded_at` en cada seed de bronze: el timestamp de carga que sobre
  una fuente real escribe la herramienta de EL (Fivetran: `_fivetran_synced`,
  Airbyte: `_airbyte_extracted_at`) y que `dbt source freshness` lee vía
  `loaded_at_field`.

  Aquí no hay EL: los seeds son CSV estáticos. Este hook (post-hook de todos
  los seeds, ver dbt_project.yml) hace ese papel: agrega la columna y le pone
  `now() - <rezago>`, donde el rezago sale del escenario declarado en
  `var('freshness_demo_lag_hours')`. Así `dbt source freshness` da el mismo
  resultado el día que se corra, en vez de degradarse solo por el paso del
  tiempo (un timestamp fijo en el CSV terminaría en `error` en todas las
  fuentes a las pocas semanas).

  Por qué no `models/meta/batch_ingesta`: registra una fila por corrida de
  dbt (cuándo se transformó), con el mismo timestamp para todas las fuentes.
  No dice cuándo llegó el dato de cada fuente, que es lo que un SLA de
  frescura mide.

  Búsqueda del rezago: `<fuente>.<tabla>` primero, luego `<fuente>`. Sin
  entrada, rezago 0 (recién cargado). El nombre de la fuente es la carpeta del
  seed (seeds/<fuente>/<tabla>.csv), que coincide con el `name` del source.
#}
{% macro stamp_loaded_at(relation, node) %}
  {%- if execute -%}
    {%- set source_name = node.fqn[1] -%}
    {%- set lags = var('freshness_demo_lag_hours', {}) -%}
    {%- set lag_hours = lags.get(source_name ~ '.' ~ node.name, lags.get(source_name, 0)) -%}
    {%- set lag_minutes = (lag_hours * 60) | round | int -%}

    {% call statement('add_loaded_at', auto_begin=False) -%}
      alter table {{ relation }} add column if not exists _loaded_at timestamptz
    {%- endcall %}
    {% call statement('stamp_loaded_at', auto_begin=False) -%}
      update {{ relation }} set _loaded_at = now() - interval '{{ lag_minutes }} minutes'
    {%- endcall %}
  {%- endif -%}
{% endmacro %}
