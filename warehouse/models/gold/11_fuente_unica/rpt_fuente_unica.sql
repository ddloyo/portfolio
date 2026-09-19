-- Dashboard 11 · projects/11-consolidacion-fuente-verdad/data/fuente_unica.csv
-- Ventas de las 3 sucursales ya unidas, normalizadas y sin duplicados: el único
-- número correcto sobre el que se calcula cualquier reporte de sucursales.
select
    v.date_key as fecha,
    s.nombre_normalizado as sucursal,
    v.monto_mxn::double as monto_mxn,
    v.fuente
from {{ ref('fct_venta_sucursal') }} v
join {{ ref('dim_sucursal') }} s on s.sucursal_key = v.sucursal_key
where not v.es_duplicado_descartado
