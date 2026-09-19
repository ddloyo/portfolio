-- Dashboard 11 · projects/11-consolidacion-fuente-verdad/data/revision_manual_monto_faltante.csv
-- Cola de revisión manual: filas de sucursal sin monto. monto_mxn siempre es NULL
-- (a estas filas nunca se les inventa un valor).
select
    p.date_key as fecha,
    s.nombre_normalizado as sucursal,
    cast(null as double) as monto_mxn,
    p.fuente
from {{ ref('fct_venta_sucursal_pendiente_revision') }} p
join {{ ref('dim_sucursal') }} s on s.sucursal_key = p.sucursal_key
