-- Enriquece cada línea de pedido con el producto (categoría, costo) y
-- calcula el importe neto. No es incremental: esa decisión vive en el mart
-- (fct_pedido) — intermediate solo describe la transformación de negocio.
with pedidos as (
    select * from {{ ref('stg_pos__pedido_linea') }}
),

-- int_producto_depurado ya trae un solo sku por fila; sin eso, el join de
-- abajo multiplicaría cada línea por cada copia recapturada del SKU.
productos as (
    select * from {{ ref('int_producto_depurado') }}
)

select
    p.pedido_id,
    p.linea_id,
    p.fecha,
    p.cliente_id,
    p.vendedor_id,
    p.canal_venta,
    p.sku,
    pr.categoria,
    p.cantidad,
    p.precio_unitario,
    p.descuento_pct,
    round(p.cantidad * p.precio_unitario * (1 - p.descuento_pct), 2) as importe_neto,
    pr.costo_unitario,
    round(p.cantidad * pr.costo_unitario, 2) as costo_total
from pedidos p
left join productos pr on pr.sku = p.sku
