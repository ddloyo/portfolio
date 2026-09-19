-- Catálogo único de sucursal, con todas las variantes crudas con las que cada
-- export la escribió (p.ej. Guadalajara: 'guadalajara', 'GDL ', 'Guadalajara').
with origen as (
    select sucursal, sucursal_raw from {{ ref('stg_sucursales__cdmx') }}
    union all
    select sucursal, sucursal_raw from {{ ref('stg_sucursales__guadalajara') }}
    union all
    select sucursal, sucursal_raw from {{ ref('stg_sucursales__monterrey') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['sucursal']) }} as sucursal_key,
    sucursal as nombre_normalizado,
    list_sort(list_distinct(list(sucursal_raw))) as nombre_origen_raw
from origen
group by sucursal
