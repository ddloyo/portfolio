{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Dashboard 03 · projects/03-scorecard-metas-vs-resultados/data/kpi_historico.csv
-- Serie mensual por KPI: los que se DERIVAN de otros hechos (ingresos, nuevos
-- clientes, NPS) unidos a los de captura manual. Solo meses completos, desde el
-- primer mes con ventas.
-- El mismo patrón (agregar el hecho correspondiente por mes) extiende a cualquier
-- otro KPI derivable agregando otro bloque al union all.
with meses as (
    select mes_key, anio, mes
    from {{ ref('dim_mes') }}
    where make_date(anio, mes, 1) >= (select date_trunc('month', min(date_key)) from {{ ref('fct_pedido') }})
      and make_date(anio, mes, 1) < date_trunc('month', {{ ref_date }})
),

ingresos as (
    select {{ mes_key('date_key') }} as mes_key, sum(monto) as monto
    from (
        select date_key, importe_neto as monto from {{ ref('fct_pedido') }}
        union all
        select date_key, monto_mxn from {{ ref('fct_venta_sucursal') }} where not es_duplicado_descartado
    )
    group by 1
),

altas as (
    select {{ mes_key('fecha_alta') }} as mes_key, count(*) as altas
    from {{ ref('dim_cliente') }}
    where fecha_alta is not null
    group by 1
),

nps as (
    select
        {{ mes_key('date_key') }} as mes_key,
        round((count(*) filter (where categoria = 'Promotor') - count(*) filter (where categoria = 'Detractor')) * 100.0 / count(*), 1) as nps
    from {{ ref('fct_encuesta_nps') }}
    group by 1
),

kpis as (
    select m.mes_key, m.anio, m.mes, 'Ingresos mensuales' as kpi, 'Ventas' as area, coalesce(i.monto, 0)::double as resultado
    from meses m left join ingresos i on i.mes_key = m.mes_key
    union all
    select m.mes_key, m.anio, m.mes, 'Nuevos clientes', 'Ventas', coalesce(a.altas, 0)::double
    from meses m left join altas a on a.mes_key = m.mes_key
    union all
    select m.mes_key, m.anio, m.mes, 'NPS', 'Experiencia de cliente', n.nps::double
    from meses m join nps n on n.mes_key = m.mes_key
    union all
    select m.mes_key, m.anio, m.mes, k.nombre_kpi, k.area, x.resultado::double
    from {{ ref('fct_kpi_manual') }} x
    join {{ ref('dim_kpi') }} k on k.kpi_key = x.kpi_key
    join meses m on m.mes_key = x.mes_key
)

select
    strftime(make_date(anio, mes, 1), '%Y-%m') as mes,
    kpi,
    area,
    resultado
from kpis
order by kpi, mes
