{{
    config(
        materialized='incremental',
        unique_key='linea_key',
        incremental_strategy='delete+insert',
        on_schema_change='sync_all_columns'
    )
}}

-- Hecho central del warehouse (~20k líneas de pedido, crece día a día).
-- Incremental por watermark de fecha: cada corrida solo procesa pedidos con
-- fecha posterior a la última fecha ya cargada, en vez de reescanear todo
-- el historial. `dbt run --full-refresh --select fct_pedido` reconstruye
-- desde cero (necesario si cambia la lógica de int_pedidos_enriquecidos,
-- no solo cuando llegan datos nuevos).
--
-- Trae las llaves subrogadas de las dimensiones (cliente_key, producto_key...)
-- y, denormalizadas, las llaves naturales y la categoría que usan los
-- reportes. Los joins son inner: una línea con cliente/producto/canal que no
-- exista en su dimensión desaparecería en silencio, por eso
-- assert_fct_pedido_conserva_todas_las_lineas compara contra staging.
select
    {{ dbt_utils.generate_surrogate_key(['p.linea_id']) }} as linea_key,
    p.linea_id,
    p.pedido_id,
    p.fecha as date_key,
    dc.cliente_key,
    dp.producto_key,
    dv.vendedor_key,
    dca.canal_key,
    p.cliente_id,
    p.vendedor_id,
    p.canal_venta,
    p.sku,
    p.categoria,
    p.cantidad,
    p.precio_unitario,
    p.descuento_pct,
    p.importe_neto,
    p.costo_total
from {{ ref('int_pedidos_enriquecidos') }} p
join {{ ref('dim_cliente') }} dc on dc.cliente_id = p.cliente_id
join {{ ref('dim_producto') }} dp on dp.sku = p.sku
join {{ ref('dim_canal') }} dca on dca.nombre_canal = p.canal_venta
left join {{ ref('dim_vendedor') }} dv on dv.vendedor_id = p.vendedor_id   -- NULL en autoservicio (e-commerce, marketplace)

{% if is_incremental() %}
where p.fecha > (select coalesce(max(date_key), date '1900-01-01') from {{ this }})
{% endif %}
