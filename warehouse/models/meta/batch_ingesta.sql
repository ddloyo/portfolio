{{ config(materialized='incremental', incremental_strategy='append') }}

-- Una fila por corrida de dbt: el batch_id ES el invocation_id de dbt. Al
-- terminar la corrida, el hook on-run-end (macro cerrar_batch) completa
-- finalizado_en y estatus. Al ser incremental, cada `dbt run` agrega un batch y
-- se conserva el historial; `--full-refresh` lo reinicia.
select
    '{{ invocation_id }}'::varchar as batch_id,
    now() as iniciado_en,
    cast(null as timestamptz) as finalizado_en,
    'en_progreso'::varchar as estatus
