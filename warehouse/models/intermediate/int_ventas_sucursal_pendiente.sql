-- Filas de sucursal sin monto capturado. Se separan aquí en vez de
-- imputarse con un valor inventado — quedan en una cola de revisión manual
-- explícita (ver rpt_revision_manual_monto_faltante).
-- rn numera las filas del mismo día/sucursal/fuente para que cada una tenga
-- una llave propia en la tabla de pendientes.
select
    fecha,
    sucursal,
    fuente,
    row_number() over (partition by fecha, sucursal, fuente order by sucursal_raw) as rn
from (
    select * from {{ ref('stg_sucursales__cdmx') }}
    union all
    select * from {{ ref('stg_sucursales__guadalajara') }}
    union all
    select * from {{ ref('stg_sucursales__monterrey') }}
)
where monto_mxn is null
