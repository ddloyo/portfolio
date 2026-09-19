with source as (
    select * from {{ source('sucursales', 'pedido_sucursal_cdmx') }}
),

cleaned as (
    select
        {{ parse_messy_date('Fecha', ['%d/%m/%Y']) }} as fecha,
        'CDMX' as sucursal,
        Sucursal as sucursal_raw,
        {{ cast_messy_amount('Monto') }} as monto_mxn,
        'pedido_sucursal_cdmx.csv' as fuente
    from source
)

select * from cleaned
