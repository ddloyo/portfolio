-- Foto semanal de inventario por SKU. margen_pct y segmento_demanda NO están
-- aquí: el margen sale de dim_producto y el segmento de demanda se calcula en
-- fct_producto_forecast a partir del historial de ventas.
select
    dp.producto_key,
    s.fecha_snapshot,
    s.stock_actual,
    s.lead_time_dias
from {{ ref('stg_wms__inventario_snapshot') }} s
join {{ ref('dim_producto') }} dp on dp.sku = s.sku
where s.fecha_snapshot is not null
