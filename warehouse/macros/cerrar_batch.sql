{#
  Hook on-run-end: cierra el batch de esta corrida en meta.batch_ingesta
  (finalizado_en + estatus). Es el equivalente de la columna estatus del DDL
  legacy: 'ok' si nada tronó, 'fallido' si algún modelo o test falló.

  Corre al final de CUALQUIER comando dbt; solo actúa si esta invocación creó
  una fila de batch (es decir, si corrió el modelo batch_ingesta): `dbt test`
  o `dbt seed` no la crean y el UPDATE no toca nada.
#}
{% macro cerrar_batch(results) %}
    {% if execute %}
        {% set batch = adapter.get_relation(database=target.database, schema='meta', identifier='batch_ingesta') %}
        {% if batch is not none %}
            {% set fallos = results | selectattr('status', 'in', ['error', 'fail']) | list | length %}
            {% do run_query(
                "update " ~ batch ~ " set finalizado_en = now(), estatus = '" ~ ('fallido' if fallos > 0 else 'ok')
                ~ "' where batch_id = '" ~ invocation_id ~ "'"
            ) %}
        {% endif %}
    {% endif %}
{% endmacro %}
