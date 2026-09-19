{{ config(materialized='incremental', incremental_strategy='append') }}
-- depends_on: {{ ref('batch_ingesta') }}

-- Resultado de aplicar cada regla en ESTA corrida (batch). Incremental: cada
-- `dbt run` agrega 33 filas con su batch_id, así que queda la serie histórica.
--   pct_fallas  = n_fallas / n_filas * 100
--   impacto_pts = peso máximo de la severidad * (n_fallas / n_filas)
-- round_even (redondeo al par) y no round: es la semántica de Python, que es como
-- calcula estos números projects/13; con round, 5.625 daría 5.63 en vez de 5.62.
with medidas as (
    {% for r in dq_reglas() -%}
    select
        '{{ local_md5(r["tabla"] ~ "|" ~ r["campo"] ~ "|" ~ r["tipo"] ~ "|" ~ r["descripcion"]) }}' as regla_key,
        m.n_filas,
        m.n_fallas
    from ({{ r['sql'] }}) m
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    md5(m.regla_key || '-{{ invocation_id }}') as resultado_key,
    m.regla_key,
    '{{ invocation_id }}'::varchar as batch_id,
    now() as fecha_evaluacion,
    m.n_filas::bigint as n_filas,
    m.n_fallas::bigint as n_fallas,
    coalesce(round_even(100.0 * m.n_fallas / nullif(m.n_filas, 0), 2), 0.0) as pct_fallas,
    coalesce(round_even(g.peso_max_pts * (m.n_fallas * 1.0 / nullif(m.n_filas, 0)), 2), 0.0) as impacto_pts
from medidas m
join {{ ref('dq_regla') }} g on g.regla_key = m.regla_key
