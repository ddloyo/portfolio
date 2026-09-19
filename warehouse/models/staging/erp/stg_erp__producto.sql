with source as (
    select * from {{ source('erp', 'producto') }}
),

cleaned as (
    select
        sku,
        trim(nombre_producto) as nombre_producto,
        trim(categoria) as categoria,
        {{ cast_messy_amount('precio_unitario') }} as precio_unitario,
        {{ cast_messy_amount('costo_unitario') }} as costo_unitario,
        trim(unidad_medida) as unidad_medida,
        case trim(activo)
            when 'True' then true
            when 'False' then false
            else null
        end as activo
        -- campo_obsoleto_bodega_2019: columna huérfana, 100% vacía — se descarta aquí
    from source
)

select * from cleaned
