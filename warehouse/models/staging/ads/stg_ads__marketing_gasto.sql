select
    trim(canal) as canal,
    try_cast(fecha as date) as fecha,
    try_cast(gasto_mxn as decimal(14,2)) as gasto_mxn
from {{ source('ads', 'marketing_gasto') }}
