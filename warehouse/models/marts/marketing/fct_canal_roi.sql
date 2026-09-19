-- CAC, LTV y ROI por canal de adquisición x mes, sobre las métricas de
-- int_canal_mes_metricas.
--
--   CAC          = gasto del mes / clientes nuevos del mes
--   LTV          = ticket promedio x margen bruto x meses de retención promedio
--   payback      = CAC / (ticket x margen), en meses (supone 1 ticket al mes)
--   cuadrante    = gasto (mediana) x ratio LTV:CAC (referencia 3.0)
--
-- Solo hay fila cuando el canal tuvo gasto Y altas en el mes: sin clientes nuevos
-- el CAC no está definido, y los canales sin inversión (Orgánico) no aparecen.
with base as (
    select
        canal_key,
        mes_key,
        gasto_mxn,
        gasto_mxn / clientes_nuevos as cac,
        ticket_promedio * margen_bruto * meses_retencion as ltv,
        ticket_promedio * margen_bruto as margen_por_ticket
    from {{ ref('int_canal_mes_metricas') }}
    where clientes_nuevos > 0
      and ticket_promedio is not null
      and margen_bruto is not null
      and meses_retencion is not null
),

umbral as (
    select median(gasto_mxn) as mediana_gasto from base
)

select
    b.canal_key,
    b.mes_key,
    round(b.cac, 2)::decimal(14,2) as cac,
    round(b.ltv, 2)::decimal(14,2) as ltv,
    round(b.ltv / nullif(b.cac, 0), 2)::decimal(8,2) as ratio_ltv_cac,
    round(b.cac / nullif(b.margen_por_ticket, 0), 2)::decimal(6,2) as payback_meses,
    {{ quadrant_segment(
        x_col='b.gasto_mxn', x_threshold='u.mediana_gasto',
        y_col='(b.ltv / nullif(b.cac, 0))', y_threshold='3.0',
        labels=['Estrella: mantener', 'Replantear', 'Escalar', 'Monitorear']
    ) }} as cuadrante
from base b
cross join umbral u
