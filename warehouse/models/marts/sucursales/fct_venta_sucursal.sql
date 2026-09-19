-- "Fuente única" de las 3 sucursales no integradas: ya unidas, normalizadas y
-- con los duplicados exactos marcados (no descartados: quien consume decide,
-- rpt_fuente_unica los excluye). Sin detalle de línea/SKU.
select
    {{ dbt_utils.generate_surrogate_key(['u.fecha', 'u.sucursal', 'u.monto_mxn', 'u.fuente', 'u.rn']) }} as venta_sucursal_key,
    u.fecha as date_key,
    s.sucursal_key,
    u.monto_mxn,
    u.es_duplicado_descartado,
    u.fuente
from {{ ref('int_ventas_sucursal_unificada') }} u
join {{ ref('dim_sucursal') }} s on s.nombre_normalizado = u.sucursal
