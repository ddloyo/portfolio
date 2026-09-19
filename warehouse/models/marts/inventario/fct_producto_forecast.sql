{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Forecast de demanda a 28 días, punto de reorden y riesgo de quiebre por SKU.
--
-- Método (tendencia + estacionalidad por día de la semana):
--   nivel  = venta diaria promedio de los últimos 14 días
--   índice = venta promedio de ese día de la semana / venta promedio general,
--            sobre los últimos 91 días
--   forecast del día = nivel * índice; forecast 28d = suma de los 28 días futuros
--
-- Backtest (mae, mape): el mismo método aplicado con 28 días de retraso, contra
-- lo que realmente se vendió esos 28 días. Índice y nivel del backtest solo usan
-- datos anteriores a la ventana evaluada (sin fuga).
--
-- reorder_point = demanda durante el lead time + colchón de seguridad
--   (Z = 1.65 ≈ 95% de nivel de servicio x desviación diaria x √lead_time)
-- La serie diaria incluye los días sin venta como 0; sin eso el promedio
-- sobreestimaría la demanda de los productos de baja rotación.
with serie as (
    select
        p.producto_key,
        d.date_key as fecha,
        isodow(d.date_key) as dow,
        coalesce(v.unidades, 0) as unidades
    from {{ ref('dim_producto') }} p
    cross join (
        select date_key from {{ ref('dim_fecha') }}
        where date_key > {{ ref_date }} - 119 and date_key <= {{ ref_date }}
    ) d
    left join (
        select producto_key, date_key, sum(cantidad) as unidades
        from {{ ref('fct_pedido') }}
        group by 1, 2
    ) v on v.producto_key = p.producto_key and v.date_key = d.date_key
),

-- nivel y dispersión, al día de hoy (a0) y 28 días atrás (a1)
nivel as (
    select
        producto_key,
        avg(unidades) filter (where fecha > {{ ref_date }} - 14) as nivel_a0,
        avg(unidades) filter (where fecha > {{ ref_date }} - 91) as media_a0,
        stddev_samp(unidades) filter (where fecha > {{ ref_date }} - 91) as desv_a0,
        sum(unidades) filter (where fecha > {{ ref_date }} - 91) as total_91d,
        avg(unidades) filter (where fecha > {{ ref_date }} - 42 and fecha <= {{ ref_date }} - 28) as nivel_a1,
        avg(unidades) filter (where fecha > {{ ref_date }} - 119 and fecha <= {{ ref_date }} - 28) as media_a1
    from serie
    group by 1
),

indice_a0 as (
    select s.producto_key, s.dow, avg(s.unidades) / nullif(n.media_a0, 0) as indice
    from serie s
    join nivel n on n.producto_key = s.producto_key
    where s.fecha > {{ ref_date }} - 91
    group by s.producto_key, s.dow, n.media_a0
),

indice_a1 as (
    select s.producto_key, s.dow, avg(s.unidades) / nullif(n.media_a1, 0) as indice
    from serie s
    join nivel n on n.producto_key = s.producto_key
    where s.fecha > {{ ref_date }} - 119 and s.fecha <= {{ ref_date }} - 28
    group by s.producto_key, s.dow, n.media_a1
),

pronostico as (
    select
        n.producto_key,
        sum(n.nivel_a0 * coalesce(i.indice, 1)) as demanda_28d
    from nivel n
    cross join (
        select k, isodow({{ ref_date }} + k::int) as dow from range(1, 29) as t (k)
    ) f
    left join indice_a0 i on i.producto_key = n.producto_key and i.dow = f.dow
    group by 1
),

backtest as (
    select
        s.producto_key,
        avg(abs(s.unidades - n.nivel_a1 * coalesce(i.indice, 1))) as mae,
        avg(abs(s.unidades - n.nivel_a1 * coalesce(i.indice, 1)) / s.unidades) filter (where s.unidades > 0) as mape
    from serie s
    join nivel n on n.producto_key = s.producto_key
    left join indice_a1 i on i.producto_key = s.producto_key and i.dow = s.dow
    where s.fecha > {{ ref_date }} - 28 and s.fecha <= {{ ref_date }}
    group by 1
),

inventario as (
    select producto_key, fecha_snapshot, stock_actual, lead_time_dias
    from {{ ref('fct_inventario_snapshot') }}
    qualify row_number() over (partition by producto_key order by fecha_snapshot desc) = 1
)

select
    n.producto_key,
    i.fecha_snapshot as fecha_forecast,
    case ntile(3) over (order by n.total_91d desc)
        when 1 then 'alta'
        when 2 then 'media'
        else 'baja'
    end as segmento_demanda,
    round(p.demanda_28d, 2)::decimal(14,2) as demanda_pronosticada_28d,
    round(n.nivel_a0 * i.lead_time_dias + 1.65 * coalesce(n.desv_a0, 0) * sqrt(i.lead_time_dias), 2)::decimal(14,2) as reorder_point,
    -- tope de 999 días: sin ventas recientes la cobertura es "infinita"
    least(999, case when n.nivel_a0 > 0 then i.stock_actual / n.nivel_a0 else 999 end)::decimal(10,2) as dias_cobertura,
    (i.stock_actual < n.nivel_a0 * i.lead_time_dias + 1.65 * coalesce(n.desv_a0, 0) * sqrt(i.lead_time_dias)) as riesgo_quiebre,
    round(b.mape, 4)::decimal(6,4) as mape,
    round(b.mae, 4)::decimal(14,4) as mae
from nivel n
join inventario i on i.producto_key = n.producto_key
join pronostico p on p.producto_key = n.producto_key
left join backtest b on b.producto_key = n.producto_key
