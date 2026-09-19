select
    equipo_id,
    trim(nombre_equipo) as nombre_equipo
from {{ source('crm', 'crm_equipo') }}
