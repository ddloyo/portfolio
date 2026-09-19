-- Dashboard 13 · projects/13-data-health-check/data/plan_remediacion.csv
-- Plan de remediación de la corrida (batch) más reciente: cada hallazgo con su
-- acción recomendada, por impacto descendente; al final, los campos huérfanos
-- (severidad "Limpieza de esquema", sin puntos de impacto). Excluye lo ya resuelto.
with ultimo as (
    select batch_id from {{ ref('dq_scorecard_tabla') }} order by fecha_evaluacion desc limit 1
)

select
    p.prioridad::bigint as prioridad,
    g.tabla_reporte as tabla,
    g.campo,
    g.tipo_label as tipo,
    case when g.severidad = 'info' then 'Limpieza de esquema' else g.severidad_label end as severidad,
    p.filas_afectadas::bigint as filas_afectadas,
    p.pct_filas::double as pct_filas,
    p.impacto_pts::double as impacto_pts,
    p.accion_recomendada
from {{ ref('dq_plan_remediacion') }} p
join ultimo u on u.batch_id = p.batch_id
join {{ ref('dq_regla') }} g on g.regla_key = p.regla_key
where not p.resuelto
order by p.prioridad
