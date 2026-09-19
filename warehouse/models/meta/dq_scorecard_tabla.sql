{{ config(materialized='incremental', incremental_strategy='append') }}

-- Score 0-100 por tabla auditada, en esta corrida: 100 - suma del impacto de sus
-- reglas. Los campos huérfanos (severidad info) pesan 0: son limpieza de
-- esquema, no un defecto del dato capturado.
--   status: >= 90 Sano · >= 75 Atención · >= 60 En riesgo · resto Crítico
with filas as (
    {% for t in dq_tablas() -%}
    select '{{ t["tabla"] }}' as tabla, count(*) as filas from {{ t['relacion'] }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

por_tabla as (
    select
        g.schema_tabla,
        g.tabla,
        round_even(greatest(0, 100 - sum(r.impacto_pts)), 1) as score,
        count(*) as reglas_evaluadas,
        count(*) filter (where r.n_fallas > 0 and g.severidad <> 'info') as reglas_con_hallazgo
    from {{ ref('dq_resultado_regla') }} r
    join {{ ref('dq_regla') }} g on g.regla_key = r.regla_key
    where r.batch_id = '{{ invocation_id }}'
    group by g.schema_tabla, g.tabla
)

select
    md5(p.tabla || '-{{ invocation_id }}') as scorecard_key,
    '{{ invocation_id }}'::varchar as batch_id,
    p.schema_tabla,
    p.tabla,
    now() as fecha_evaluacion,
    f.filas::bigint as filas,
    p.score,
    case when p.score >= 90 then 'good' when p.score >= 75 then 'warning' when p.score >= 60 then 'serious' else 'critical' end as status,
    case when p.score >= 90 then 'Sano' when p.score >= 75 then 'Atención' when p.score >= 60 then 'En riesgo' else 'Crítico' end as status_label,
    p.reglas_evaluadas::bigint as reglas_evaluadas,
    p.reglas_con_hallazgo::bigint as reglas_con_hallazgo
from por_tabla p
join filas f on f.tabla = p.tabla
