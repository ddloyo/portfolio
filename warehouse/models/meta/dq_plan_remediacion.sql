{{ config(materialized='incremental', incremental_strategy='append') }}
{% set plantillas = dq_plantillas_remediacion() %}

-- Plan de remediación de esta corrida: primero los hallazgos reales, por
-- impacto descendente; después los campos huérfanos (limpieza de esquema, no un
-- defecto del dato), que no tienen prioridad de impacto. `resuelto` nace en
-- false: una corrida posterior que ya no encuentre el hallazgo deja de listarlo.
with hallazgos as (
    select
        r.regla_key,
        r.n_fallas,
        r.pct_fallas,
        r.impacto_pts,
        g.tipo,
        g.campo,
        g.tabla_reporte,
        (g.severidad = 'info') as es_huerfano
    from {{ ref('dq_resultado_regla') }} r
    join {{ ref('dq_regla') }} g on g.regla_key = r.regla_key
    where r.batch_id = '{{ invocation_id }}'
      and ((r.n_fallas > 0 and g.severidad <> 'info') or g.tipo = 'orphan_field')
)

select
    md5(regla_key || '-{{ invocation_id }}') as plan_key,
    '{{ invocation_id }}'::varchar as batch_id,
    row_number() over (order by es_huerfano, impacto_pts desc, tabla_reporte, campo, tipo)::int as prioridad,
    regla_key,
    n_fallas::bigint as filas_afectadas,
    pct_fallas as pct_filas,
    impacto_pts,
    case tipo
        {% for tipo, texto in plantillas.items() -%}
        when '{{ tipo }}' then replace(replace('{{ texto | replace("'", "''") }}', '{campo}', campo), '{n}', n_fallas::varchar)
        {% endfor -%}
    end as accion_recomendada,
    now() as fecha_generado,
    false as resuelto
from hallazgos
