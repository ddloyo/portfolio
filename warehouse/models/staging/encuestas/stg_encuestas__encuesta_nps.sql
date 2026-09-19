select
    respuesta_id,
    cliente_id,
    try_cast(fecha as date) as fecha,
    try_cast(score as smallint) as score,
    nullif(trim(motivo_detractor), '') as motivo_detractor
from {{ source('encuestas', 'encuesta_nps') }}
