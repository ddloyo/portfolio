-- Reproduce projects/04-prediccion-churn/data/clientes.csv, + el cuadrante
-- riesgo x valor que arma el dashboard (mismo macro quadrant_segment que
-- usarían RFM y ROI de marketing si se agregan más adelante).
with riesgo as (
    select * from {{ ref('int_cliente_riesgo_churn') }}
),

mediana_gasto as (
    select median(gasto_mensual_mxn) as valor from riesgo
)

select
    r.cliente_id,
    r.antiguedad_meses,
    r.gasto_mensual_mxn,
    r.tickets_soporte_90d,
    r.dias_desde_ultima_actividad,
    r.usage_score,
    r.tipo_contrato,
    r.plan,
    r.churn_historico,
    r.percentil_riesgo,
    {{ quadrant_segment(
        x_col='r.percentil_riesgo', x_threshold='50',
        y_col='r.gasto_mensual_mxn', y_threshold='m.valor',
        labels=['Alto riesgo / alto valor', 'Alto riesgo / bajo valor', 'Bajo riesgo / alto valor', 'Bajo riesgo / bajo valor']
    ) }} as cuadrante_accion
from riesgo r
cross join mediana_gasto m
