-- Reproduce projects/07-forecast-demanda-inventario/data/demanda_diaria.csv
-- Grano: 1 fila por SKU x día. Insumo directo de un forecast de demanda.
select
    fp.sku,
    fp.date_key as fecha,
    sum(fp.cantidad) as unidades_vendidas,
    sum(fp.importe_neto) as ingreso,
    sum(fp.costo_total) as costo_total
from {{ ref('fct_pedido') }} fp
group by fp.sku, fp.date_key
