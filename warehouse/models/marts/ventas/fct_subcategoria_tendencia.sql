{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Tendencia y anomalías del ingreso por categoría x subcategoría x mes.
-- Excluye el mes en curso (incompleto: compararlo contra meses cerrados lo haría
-- parecer una caída).
--
--   variacion_yoy_pct   ingreso vs el mismo mes del año anterior (NULL sin año previo)
--   pendiente_tendencia pendiente de los últimos 6 meses, relativa a su media
--                       (0.03 = crece 3% del ingreso medio por mes)
--   volatilidad         desviación estándar del % de cambio mensual, últimos 6 meses
--   z_score_anomalia    qué tan lejos cae el mes de la media de los 6 anteriores
--   segmento            |z| >= 2 → Alerta puntual; pendiente <= -2% → En riesgo;
--                       >= +2% → Motor de crecimiento; si no, Estable.
--                       NULL con menos de 4 meses de historia.
with mensual as (
    select
        dp.categoria,
        dp.subcategoria,
        {{ mes_key('p.date_key') }} as mes_key,
        sum(p.importe_neto) as ingreso
    from {{ ref('fct_pedido') }} p
    join {{ ref('dim_producto') }} dp on dp.producto_key = p.producto_key
    where p.date_key < date_trunc('month', {{ ref_date }})
    group by 1, 2, 3
),

con_previo as (
    select
        m.*,
        y.ingreso as ingreso_anio_previo,
        row_number() over (partition by m.categoria, m.subcategoria order by m.mes_key) as n,
        m.ingreso / nullif(lag(m.ingreso) over (partition by m.categoria, m.subcategoria order by m.mes_key), 0) - 1 as cambio_pct
    from mensual m
    left join mensual y
        on y.categoria = m.categoria and y.subcategoria = m.subcategoria and y.mes_key = m.mes_key - 100
),

ventanas as (
    select
        *,
        -- con una sola observación la regresión da NaN (0/0): se convierte en NULL
        case when isnan(regr_slope(ingreso, n) over ult6) then null
             else regr_slope(ingreso, n) over ult6 / nullif(avg(ingreso) over ult6, 0) end as pendiente_relativa,
        stddev_samp(cambio_pct) over ult6 as volatilidad,
        avg(ingreso) over prev6 as media_prev,
        stddev_samp(ingreso) over prev6 as desv_prev
    from con_previo
    window
        ult6 as (partition by categoria, subcategoria order by mes_key rows between 5 preceding and current row),
        prev6 as (partition by categoria, subcategoria order by mes_key rows between 6 preceding and 1 preceding)
)

select
    categoria,
    subcategoria,
    mes_key,
    round((ingreso / nullif(ingreso_anio_previo, 0) - 1) * 100, 2)::decimal(6,2) as variacion_yoy_pct,
    round(pendiente_relativa, 4)::decimal(10,4) as pendiente_tendencia,
    round(volatilidad, 4)::decimal(10,4) as volatilidad,
    round((ingreso - media_prev) / nullif(desv_prev, 0), 2)::decimal(6,2) as z_score_anomalia,
    case
        when n < 4 then null
        when abs((ingreso - media_prev) / nullif(desv_prev, 0)) >= 2 then 'Alerta puntual'
        when pendiente_relativa <= -0.02 then 'En riesgo'
        when pendiente_relativa >= 0.02 then 'Motor de crecimiento'
        else 'Estable'
    end as segmento
from ventanas
