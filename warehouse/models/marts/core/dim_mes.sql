-- Grano mensual. mes_key = año * 100 + mes, p.ej. 202608: determinista y legible.
select distinct
    (anio::int * 100 + mes)::int as mes_key,
    anio,
    mes,
    nombre_mes
from {{ ref('dim_fecha') }}
