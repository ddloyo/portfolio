-- Enriquece cada línea de pedido con el producto (categoría, costo) y
-- calcula el importe neto. No es incremental: esa decisión vive en el mart
-- (fct_pedidos) — intermediate solo describe la transformación de negocio.
with pedidos as (
    select * from {{ ref('stg_pos__pedido_linea') }}
),

productos as (
    -- stg_erp__producto puede traer el mismo sku recapturado más de una
    -- vez (con otro precio) — sin deduplicar aquí, el join de abajo
    -- multiplicaría cada línea de pedido por cada copia del SKU.
    select *
    from {{ ref('stg_erp__producto') }}
    where sku is not null
    qualify row_number() over (
        partition by sku
        order by (precio_unitario is null), (costo_unitario is null)
    ) = 1
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
