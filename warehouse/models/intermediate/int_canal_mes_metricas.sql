-- Las 5 métricas de marketing por canal x mes, calculadas UNA vez y compartidas
-- por fct_canal_roi (silver: CAC, LTV, ROI) y rpt_marketing_canales (gold: el
-- reporte que consume el dashboard 09), para que ambos no puedan divergir.
-- Combina 4 hechos distintos:
--   gasto de pauta            (fct_marketing_gasto)
--   altas por canal           (dim_cliente.canal_adquisicion x fecha_alta)
--   ticket y margen del pedido (fct_pedido, de los clientes de ese canal)
--   antigüedad / retención    (dim_cliente + fct_cancelacion)
-- Una fila por canal con gasto y mes con gasto; el resto puede ser NULL/0 (sin
-- altas en el mes, por ejemplo).
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
)

select
    g.canal_key,
    g.mes_key,
    g.gasto_mxn,
    coalesce(a.clientes_nuevos, 0) as clientes_nuevos,
    t.ticket_promedio,
    t.margen_bruto,
    r.meses_retencion
from gasto g
left join altas a on a.canal_key = g.canal_key and a.mes_key = g.mes_key
left join ticket t on t.canal_key = g.canal_key and t.mes_key = g.mes_key
left join retencion r on r.canal_key = g.canal_key and r.mes_key = g.mes_key
