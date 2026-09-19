-- Dashboard 13 · projects/13-data-health-check/data/scorecard_calidad_tablas.csv
-- Score de calidad 0-100 por tabla auditada, en la corrida (batch) más reciente
-- del motor de calidad. tabla usa los nombres del proyecto 13 (clientes, productos,
-- calendario, facturas), no los de bronze.
with ultimo as (
    select batch_id from {{ ref('dq_scorecard_tabla') }} order by fecha_evaluacion desc limit 1
),

nombres as (
    select distinct tabla, tabla_reporte from {{ ref('dq_regla') }}
)

select
    n.tabla_reporte as tabla,
    s.filas::bigint as filas,
    s.score::double as score,
    s.status,
    s.status_label,
    s.reglas_evaluadas::bigint as reglas_evaluadas,
    s.reglas_con_hallazgo::bigint as reglas_con_hallazgo
from {{ ref('dq_scorecard_tabla') }} s
join ultimo u on u.batch_id = s.batch_id
join nombres n on n.tabla = s.tabla
order by n.tabla_reporte
