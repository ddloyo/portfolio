-- Reproduce projects/05-segmentacion-rfm/data/transacciones.csv
-- Grano: 1 fila por cliente x día. Insumo directo de un cálculo RFM.
select
    fp.cliente_id,
    fp.date_key as fecha,
    sum(fp.importe_neto) as monto_mxn
from {{ ref('fct_pedidos') }} fp
group by fp.cliente_id, fp.date_key
