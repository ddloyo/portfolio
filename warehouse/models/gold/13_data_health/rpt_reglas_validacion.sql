-- Dashboard 13 · projects/13-data-health-check/data/reglas_validacion.csv
-- Catálogo de las 33 reglas de calidad con su resultado en la corrida (batch) más
-- reciente. Es a la vez el checklist reutilizable de la auditoría y la lista de issues.
with ultimo as (
    select batch_id from {{ ref('dq_scorecard_tabla') }} order by fecha_evaluacion desc limit 1
)

select
    g.tabla_reporte as tabla,
    g.campo,
    g.tipo,
    g.tipo_label,
    g.severidad,
    g.severidad_label,
    g.descripcion,
    r.n_filas::bigint as n_filas,
    r.n_fallas::bigint as n_fallas,
    r.pct_fallas::double as pct_fallas,
    r.impacto_pts::double as impacto_pts
from {{ ref('dq_resultado_regla') }} r
join ultimo u on u.batch_id = r.batch_id
join {{ ref('dq_regla') }} g on g.regla_key = r.regla_key
order by g.tabla_reporte, r.impacto_pts desc, g.campo, g.tipo
