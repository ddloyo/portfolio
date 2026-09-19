-- Vendedor con su equipo. equipo_id y equipo (nombre) van denormalizados junto
-- a equipo_key porque los reportes agrupan por nombre de equipo sin tener que
-- volver a unir dim_equipo.
select
    {{ dbt_utils.generate_surrogate_key(['v.vendedor_id']) }} as vendedor_key,
    v.vendedor_id,
    v.codigo_vendedor,
    e.equipo_key,
    e.equipo_id,
    e.nombre_equipo as equipo
from {{ ref('stg_crm__vendedor') }} v
join {{ ref('dim_equipo') }} e on e.equipo_id = v.equipo_id
