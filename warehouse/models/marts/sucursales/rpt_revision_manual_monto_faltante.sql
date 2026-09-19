-- Reproduce projects/11-consolidacion-fuente-verdad/data/revision_manual_monto_faltante.csv
select
    fecha,
    sucursal,
    cast(null as decimal(14,2)) as monto_mxn,
    fuente
from {{ ref('int_ventas_sucursal_pendiente') }}
