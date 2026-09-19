-- Dimensión pequeña (12 vendedores, 4 equipos): se modela en una sola tabla
-- en vez de separar dim_equipo — normalizar más no aporta nada a este grano.
select
    v.vendedor_id,
    v.codigo_vendedor,
    v.equipo_id,
    e.nombre_equipo as equipo
from {{ ref('stg_crm__vendedor') }} v
join {{ ref('stg_crm__equipo') }} e on e.equipo_id = v.equipo_id
