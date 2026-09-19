select
    trim(kpi) as kpi,
    try_cast(meta as decimal(14,2)) as meta
from {{ source('scorecard', 'kpi_meta') }}
