{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Dashboard 10 · projects/10-reporte-ejecutivo-mensual/data/transacciones.csv
-- Ingreso por mes x región x cliente x perfil x categoría x subcategoría. Solo
-- meses completos: el reporte compara mes contra mes (y contra el mismo mes del
-- año anterior), y un mes a medias parecería una caída.
-- perfil es el segmento comercial del cliente (Básico / Estándar / Premium); en el
-- proyecto 10 original era un perfil de comportamiento de compra, que no se calcula
-- en este warehouse.
select
    strftime(date_trunc('month', fp.date_key), '%Y-%m') as mes,
    r.nombre_region as region,
    c.cliente_id,
    c.segmento as perfil,
    dp.categoria,
    dp.subcategoria,
    sum(fp.importe_neto)::double as ingreso_mxn
from {{ ref('fct_pedido') }} fp
join {{ ref('dim_cliente') }} c on c.cliente_key = fp.cliente_key
join {{ ref('dim_region') }} r on r.region_key = c.region_key
join {{ ref('dim_producto') }} dp on dp.producto_key = fp.producto_key
where fp.date_key < date_trunc('month', {{ ref_date }})
group by 1, 2, 3, 4, 5, 6
