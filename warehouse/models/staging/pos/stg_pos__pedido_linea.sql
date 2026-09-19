with source as (
    select * from {{ source('pos', 'pedido_linea') }}
),

cleaned as (
    select
        pedido_id,
        linea_id,
        fecha::date as fecha,
        cliente_id,
        nullif(trim(vendedor_id), '') as vendedor_id,
        trim(canal_venta) as canal_venta,
        sku,
        try_cast(cantidad as int) as cantidad,
        try_cast(precio_unitario as decimal(14,2)) as precio_unitario,
        try_cast(descuento_pct as decimal(5,4)) as descuento_pct
    from source
)

select * from cleaned
