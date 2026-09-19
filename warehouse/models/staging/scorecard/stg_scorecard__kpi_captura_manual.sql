select
    trim(kpi) as kpi,
    trim(area) as area,
    trim(responsable) as responsable,
    mes,
    try_cast(mes || '-01' as date) as mes_inicio,
    try_cast(resultado as decimal(14,2)) as resultado,
    trim(unidad) as unidad,
    (trim(menor_es_mejor) = 'True') as menor_es_mejor
from {{ source('scorecard', 'kpi_captura_manual') }}
