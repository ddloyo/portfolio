select
    {{ dbt_utils.generate_surrogate_key(['equipo_id']) }} as equipo_key,
    equipo_id,
    nombre_equipo
from {{ ref('stg_crm__equipo') }}
