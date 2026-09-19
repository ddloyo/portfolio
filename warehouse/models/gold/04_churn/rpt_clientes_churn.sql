-- Dashboard 04 · projects/04-prediccion-churn/data/clientes.csv
-- Feature set de churn por cliente con plan de servicio, calculado desde bronze
-- (fct_cliente_features_churn). El dashboard entrena su propio modelo y arma su
-- cuadrante riesgo x valor sobre estas columnas; el proxy de riesgo del warehouse
-- (fct_cliente_churn_score) vive aparte y no forma parte de este contrato.
select
    dc.cliente_id,
    f.antiguedad_meses::double as antiguedad_meses,
    f.gasto_mensual_mxn::double as gasto_mensual_mxn,
    f.tickets_soporte_90d::bigint as tickets_soporte_90d,
    f.dias_desde_ultima_actividad::double as dias_desde_ultima_actividad,
    f.usage_score::double as usage_score,
    f.tipo_contrato,
    f.plan,
    f.churn_historico::int::bigint as churn_historico
from {{ ref('fct_cliente_features_churn') }} f
join {{ ref('dim_cliente') }} dc on dc.cliente_key = f.cliente_key
