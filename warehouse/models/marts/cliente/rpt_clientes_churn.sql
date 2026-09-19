-- Reproduce projects/04-prediccion-churn/data/clientes.csv, + el cuadrante
-- riesgo x valor que arma el dashboard (mismo macro quadrant_segment que usa
-- RFM). Ya no parte de un seed de features: se calcula desde bronze
-- (fct_cliente_features_churn) y el riesgo es el proxy de fct_cliente_churn_score.
with base as (
    select
        dc.cliente_id,
        f.antiguedad_meses,
        f.gasto_mensual_mxn,
        f.tickets_soporte_90d,
        f.dias_desde_ultima_actividad,
        f.usage_score,
        f.tipo_contrato,
        f.plan,
        f.churn_historico,
        s.percentil_riesgo
    from {{ ref('fct_cliente_features_churn') }} f
    join {{ ref('fct_cliente_churn_score') }} s on s.cliente_key = f.cliente_key
    join {{ ref('dim_cliente') }} dc on dc.cliente_key = f.cliente_key
),

mediana_gasto as (
    select median(gasto_mensual_mxn) as valor from base
)

select
    r.*,
    {{ quadrant_segment(
        x_col='r.percentil_riesgo', x_threshold='50',
        y_col='r.gasto_mensual_mxn', y_threshold='m.valor',
        labels=['Alto riesgo / alto valor', 'Alto riesgo / bajo valor', 'Bajo riesgo / alto valor', 'Bajo riesgo / bajo valor']
    ) }} as cuadrante_accion
from base r
cross join mediana_gasto m
