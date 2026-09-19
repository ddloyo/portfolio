-- CAC, LTV y ROI por canal de adquisición x mes. Combina 4 hechos distintos:
--   gasto de pauta            (fct_marketing_gasto)
--   altas por canal           (dim_cliente.canal_adquisicion x fecha_alta)
--   ticket y margen del pedido (fct_pedido, de los clientes de ese canal)
--   antigüedad / retención    (dim_cliente + fct_cancelacion)
--
--   CAC          = gasto del mes / clientes nuevos del mes
--   LTV          = ticket promedio x margen bruto x meses de retención promedio
--   payback      = CAC / (ticket x margen), en meses (supone 1 ticket al mes)
--   cuadrante    = gasto (mediana) x ratio LTV:CAC (referencia 3.0)
--
-- Solo hay fila cuando el canal tuvo gasto Y altas en el mes: sin clientes nuevos
-- el CAC no está definido, y los canales sin inversión (Orgánico) no aparecen.
with gasto as (
    select canal_key, {{ mes_key('date_key') }} as mes_key, sum(gasto_mxn) as gasto_mxn
    from {{ ref('fct_marketing_gasto') }}
    group by 1, 2
),

altas as (
    select ca.canal_key, {{ mes_key('c.fecha_alta') }} as mes_key, count(*) as clientes_nuevos
    from {{ ref('dim_cliente') }} c
    join {{ ref('dim_canal') }} ca on ca.nombre_canal = c.canal_adquisicion
    where c.fecha_alta is not null
    group by 1, 2
),

-- un pedido = todas sus líneas
pedido as (
    select pedido_id, cliente_key, min(date_key) as fecha, sum(importe_neto) as monto, sum(costo_total) as costo
    from {{ ref('fct_pedido') }}
    group by 1, 2
),

ticket as (
    select
        ca.canal_key,
        {{ mes_key('pd.fecha') }} as mes_key,
        avg(pd.monto) as ticket_promedio,
        avg((pd.monto - pd.costo) / nullif(pd.monto, 0)) as margen_bruto
    from pedido pd
    join {{ ref('dim_cliente') }} c on c.cliente_key = pd.cliente_key
    join {{ ref('dim_canal') }} ca on ca.nombre_canal = c.canal_adquisicion
    group by 1, 2
),

-- antigüedad de los clientes del canal al inicio de cada mes, o hasta su baja
retencion as (
    select
        ca.canal_key,
        m.mes_key,
        avg(date_diff('month', c.fecha_alta,
            least(coalesce(can.fecha_cancelacion, make_date(m.anio, m.mes, 1)), make_date(m.anio, m.mes, 1)))) as meses_retencion
    from {{ ref('dim_cliente') }} c
    join {{ ref('dim_canal') }} ca on ca.nombre_canal = c.canal_adquisicion
    join {{ ref('dim_mes') }} m on c.fecha_alta <= make_date(m.anio, m.mes, 1)
    left join {{ ref('fct_cancelacion') }} can on can.cliente_key = c.cliente_key
    group by 1, 2
),

base as (
    select
        g.canal_key,
        g.mes_key,
        g.gasto_mxn,
        g.gasto_mxn / a.clientes_nuevos as cac,
        t.ticket_promedio * t.margen_bruto * r.meses_retencion as ltv,
        t.ticket_promedio * t.margen_bruto as margen_por_ticket
    from gasto g
    join altas a on a.canal_key = g.canal_key and a.mes_key = g.mes_key
    join ticket t on t.canal_key = g.canal_key and t.mes_key = g.mes_key
    join retencion r on r.canal_key = g.canal_key and r.mes_key = g.mes_key
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
