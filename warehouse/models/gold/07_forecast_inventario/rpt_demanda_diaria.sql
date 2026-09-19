{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Dashboard 07 · projects/07-forecast-demanda-inventario/data/demanda_diaria.csv
-- Grano: 1 fila por SKU x día, con los días sin venta como 0 (la serie debe ser
-- continua: el dashboard calcula tendencia móvil e índices por día de la semana, y
-- si faltaran los días sin venta sobreestimaría la demanda de los productos de
-- baja rotación). Cubre desde la primera venta hasta el día anterior a la fecha
-- de referencia, solo para SKUs con al menos una venta.
with rango as (
    select min(date_key) as desde, {{ ref_date }} - 1 as hasta from {{ ref('fct_pedido') }}
),

skus as (
    select distinct producto_key from {{ ref('fct_pedido') }}
),

diario as (
    select producto_key, date_key, sum(cantidad) as unidades, sum(importe_neto) as ingreso, sum(costo_total) as costo
    from {{ ref('fct_pedido') }}
    group by 1, 2
)

select
    dp.sku,
    d.date_key as fecha,
    coalesce(v.unidades, 0)::bigint as unidades_vendidas,
    dp.costo_unitario::double as costo_unitario,
    dp.precio_unitario::double as precio_unitario,
    coalesce(v.ingreso, 0)::double as ingreso,
    coalesce(v.costo, 0)::double as costo_total
from skus s
join {{ ref('dim_producto') }} dp on dp.producto_key = s.producto_key
cross join rango r
join {{ ref('dim_fecha') }} d on d.date_key between r.desde and r.hasta
left join diario v on v.producto_key = s.producto_key and v.date_key = d.date_key
