-- Reproduce projects/01-sales-performance-dashboard/data/ventas_diarias.csv
-- Grano: 1 fila por fecha x equipo x vendedor x categoría.
select
    fp.date_key as fecha,
    dv.equipo,
    dv.codigo_vendedor as vendedor,
    fp.categoria as linea_producto,
    sum(fp.importe_neto) as monto_mxn
from {{ ref('fct_pedidos') }} fp
join {{ ref('dim_vendedor') }} dv on dv.vendedor_id = fp.vendedor_id
group by fp.date_key, dv.equipo, dv.codigo_vendedor, fp.categoria
