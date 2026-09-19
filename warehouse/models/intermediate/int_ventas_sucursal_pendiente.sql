-- Filas de sucursal sin monto capturado. Se separan aquí en vez de
-- imputarse con un valor inventado — quedan en una cola de revisión manual
-- explícita (ver rpt_revision_manual_monto_faltante).
select
    fecha,
    sucursal,
    fuente
from (
    select * from {{ ref('stg_sucursales__cdmx') }}
    union all
    select * from {{ ref('stg_sucursales__guadalajara') }}
    union all
    select * from {{ ref('stg_sucursales__monterrey') }}
)
where monto_mxn is null
