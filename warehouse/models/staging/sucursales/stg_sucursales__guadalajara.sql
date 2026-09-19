with source as (
    select * from {{ source('sucursales', 'pedido_sucursal_guadalajara') }}
),

cleaned as (
    select
        {{ parse_messy_date('Date', ['%m/%d/%Y']) }} as fecha,
        -- la misma sucursal llega escrita 3 formas distintas EN EL MISMO
        -- ARCHIVO: 'guadalajara', 'GDL ', 'Guadalajara' — se normaliza aquí,
        -- no se asume por nombre de archivo.
        case
            when lower(trim(Store)) in ('guadalajara', 'gdl') then 'Guadalajara'
            -- DuckDB no trae initcap(); Store siempre es una sola palabra
            else upper(substr(trim(Store), 1, 1)) || lower(substr(trim(Store), 2))
        end as sucursal,
        {{ cast_messy_amount('Amount_MXN') }} as monto_mxn,
        'pedido_sucursal_guadalajara.csv' as fuente
    from source
)

select * from cleaned
