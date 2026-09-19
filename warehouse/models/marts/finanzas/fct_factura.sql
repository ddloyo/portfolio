-- Línea de facturación ya limpia: solo las que pasan la validación de
-- int_factura_linea_validada (integridad referencial y fechas resueltas) y con
-- total = cantidad * precio_unitario recalculado.
select
    {{ dbt_utils.generate_surrogate_key(['v.factura_id']) }} as factura_key,
    v.factura_id,
    v.fecha as date_key,
    v.fecha_vencimiento,
    dc.cliente_key,
    dp.producto_key,
    dca.canal_key,
    v.cantidad,
    v.precio_unitario,
    v.total_calculado as total
from {{ ref('int_factura_linea_validada') }} v
join {{ ref('dim_cliente') }} dc on dc.cliente_id = v.cliente_id
join {{ ref('dim_producto') }} dp on dp.sku = v.sku
join {{ ref('dim_canal') }} dca on dca.nombre_canal = v.canal_venta
where v.motivo_rechazo is null
