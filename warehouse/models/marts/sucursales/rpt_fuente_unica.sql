-- Reproduce projects/11-consolidacion-fuente-verdad/data/fuente_unica.csv
select
    fecha,
    sucursal,
    monto_mxn,
    fuente
from {{ ref('int_ventas_sucursal_unificada') }}
where not es_duplicado_descartado
