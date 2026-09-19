with source as (
    select * from {{ source('sucursales', 'pedido_sucursal_monterrey') }}
),

cleaned as (
    select
        {{ parse_messy_date('fecha_venta', ['%Y-%m-%d']) }} as fecha,
        'Monterrey' as sucursal,
        tienda as sucursal_raw,
        {{ cast_messy_amount('importe_mxn') }} as monto_mxn,   -- NULL en ~12 filas a propósito
        'pedido_sucursal_monterrey.csv' as fuente
    from source
)

select * from cleaned
