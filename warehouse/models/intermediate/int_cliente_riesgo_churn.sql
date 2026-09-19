-- Proxy de riesgo de churn basado en reglas — NO es un modelo entrenado.
-- Combina 3 señales normalizadas a percentil (usage bajo, inactividad,
-- tickets de soporte) en un solo percentil de riesgo. En producción esta
-- tabla la llenaría la salida de un job de scoring (Python/ML) corrido
-- fuera de dbt; se aproxima en SQL para no salir del alcance del warehouse
-- — y se documenta como lo que es, para no pasar una heurística por modelo.
with churn as (
    select * from {{ ref('stg_cliente__churn_features') }}
),

percentiles as (
    select
        *,
        percent_rank() over (order by usage_score asc)                     as pct_usage_bajo,
        percent_rank() over (order by dias_desde_ultima_actividad desc)    as pct_inactividad,
        percent_rank() over (order by tickets_soporte_90d desc)            as pct_tickets
    from churn
)

select
    cliente_id,
    antiguedad_meses,
    gasto_mensual_mxn,
    tickets_soporte_90d,
    dias_desde_ultima_actividad,
    usage_score,
    tipo_contrato,
    plan,
    churn_historico,
    round((pct_usage_bajo + pct_inactividad + pct_tickets) / 3 * 100, 1) as percentil_riesgo
from percentiles
