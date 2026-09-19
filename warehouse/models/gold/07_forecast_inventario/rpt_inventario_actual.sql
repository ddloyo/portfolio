-- Dashboard 07 · projects/07-forecast-demanda-inventario/data/inventario_actual.csv
-- Última foto de inventario por SKU, con su segmento de demanda (calculado en
-- fct_producto_forecast a partir del historial de ventas, no viene de bronze).
select
    dp.sku,
    dp.categoria,
    f.segmento_demanda,
    i.lead_time_dias::bigint as lead_time_dias,
    i.stock_actual::bigint as stock_actual,
    dp.costo_unitario::double as costo_unitario,
    dp.precio_unitario::double as precio_unitario,
    round((dp.precio_unitario - dp.costo_unitario) / nullif(dp.precio_unitario, 0) * 100, 1)::double as margen_pct
from {{ ref('fct_producto_forecast') }} f
join {{ ref('fct_inventario_snapshot') }} i
    on i.producto_key = f.producto_key and i.fecha_snapshot = f.fecha_forecast
join {{ ref('dim_producto') }} dp on dp.producto_key = f.producto_key
