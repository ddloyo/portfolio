-- Reproduce projects/06-elasticidad-precios/data/precio_demanda.csv
-- Grano: 1 fila por producto x semana ISO. Insumo directo de una regresión
-- de elasticidad log-log (fuera de dbt).
select
    dp.nombre_producto as producto,
    df.semana_iso as semana,
    round(avg(fp.precio_unitario), 2) as precio_mxn,
    sum(fp.cantidad) as unidades_vendidas
from {{ ref('fct_pedidos') }} fp
join {{ ref('dim_producto') }} dp on dp.sku = fp.sku
join {{ ref('dim_fecha') }} df on df.date_key = fp.date_key
group by dp.nombre_producto, df.semana_iso
