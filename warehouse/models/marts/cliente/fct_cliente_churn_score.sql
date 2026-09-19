{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Riesgo de churn por cliente — PROXY por reglas, NO un modelo entrenado.
-- El diseño legacy asumía una regresión logística corrida fuera de SQL (Python);
-- aquí se aproxima con 3 señales de riesgo, cada una convertida a percentil
-- (0 = menor riesgo, 1 = mayor):
--   uso bajo, inactividad alta y tickets de soporte altos.
-- riesgo es su promedio; percentil_riesgo es el percentil de ese promedio
-- entre todos los clientes, y probabilidad_churn es una transformación
-- logística del mismo (NO una probabilidad calibrada: sirve para ordenar y
-- para el rango 0-1 que espera el DDL, no para leerla como "% de churn").
-- Si algún día se entrena un modelo real, su salida sustituye a esta tabla sin
-- tocar a quien la consume.
with percentiles as (
    select
        cliente_key,
        percent_rank() over (order by usage_score desc)                  as riesgo_uso,
        percent_rank() over (order by dias_desde_ultima_actividad asc)   as riesgo_inactividad,
        percent_rank() over (order by tickets_soporte_90d asc)           as riesgo_tickets
    from {{ ref('fct_cliente_features_churn') }}
),

riesgo as (
    select cliente_key, (riesgo_uso + riesgo_inactividad + riesgo_tickets) / 3 as riesgo
    from percentiles
)

select
    cliente_key,
    {{ ref_date }} as fecha_scoring,
    round(1 / (1 + exp(-6 * (riesgo - 0.5))), 4)::decimal(5,4) as probabilidad_churn,
    round(percent_rank() over (order by riesgo) * 100, 2)::decimal(5,2) as percentil_riesgo
from riesgo
