with source as (
    select * from {{ source('erp', 'factura_linea') }}
),

cleaned as (
    select
        factura_id,
        {{ parse_messy_date('fecha', ['%Y-%m-%d', '%d/%m/%Y']) }} as fecha,
        nullif(trim(cliente_id), '') as cliente_id,   -- puede no existir en stg_crm__cliente
        nullif(trim(sku), '') as sku,                 -- puede no existir en stg_erp__producto
        try_cast(cantidad as int) as cantidad,
        {{ cast_messy_amount('precio_unitario') }} as precio_unitario,
        upper(trim(moneda)) as moneda,
        {{ cast_messy_amount('total') }} as total,    -- puede no cuadrar con cantidad * precio_unitario
        trim(canal_venta) as canal_venta
    from source
)

select * from cleaned
