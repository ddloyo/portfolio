with source as (
    select * from {{ source('crm', 'crm_cliente') }}
),

cleaned as (
    select
        cliente_id,
        trim(nombre_completo) as nombre_completo,
        lower(trim(email)) as email,
        nullif(trim(telefono), '') as telefono,
        trim(ciudad) as ciudad,
        trim(segmento) as segmento,
        -- fuente real: ISO y DD/MM/AAAA *y* MM/DD/AAAA mezclados en la misma
        -- columna (confirmado: hay filas con día > 12 en la 1a posición y
        -- filas donde solo puede ser mes en la 1a posición). Es una
        -- ambigüedad real e irresoluble sin más contexto — se prioriza
        -- DD/MM (el formato mexicano) y se documenta como limitación
        -- conocida en vez de ocultarla.
        {{ parse_messy_date('fecha_alta', ['%Y-%m-%d', '%d/%m/%Y']) }} as fecha_alta
        -- campo_legacy_crm_id: columna huérfana de un CRM anterior, 100% vacía — se descarta aquí
    from source
)

select * from cleaned
