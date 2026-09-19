-- Dashboard 08 · projects/08-flujo-caja-cartera/data/facturas.csv
-- Una fila por factura. estatus y fecha_pago NO son columnas capturadas: se
-- derivan de los pagos (fct_pago), que pueden ser parciales.
--   Pagada     lo pagado cubre el total (tolerancia de $1)
--   Pendiente  todo lo demás, vencido o no
-- El dashboard solo conoce esos dos estatus: la antigüedad de la cartera
-- (vigente, 1-30, 31-60, ...) la calcula él con fecha_vencimiento, por lo que
-- aquí NO hay un estatus "Vencida".
-- Ojo: una factura con pagos por menos de su total RECALCULADO (p.ej. porque en
-- origen el total capturado traía un descuento manual) aparece como Pendiente,
-- no como Pagada. fecha_pago es la del último pago y solo se informa si la
-- factura quedó Pagada.
with pagos as (
    select factura_key, sum(monto_pagado) as pagado, max(fecha_pago) as ultimo_pago
    from {{ ref('fct_pago') }}
    group by 1
)

select
    f.factura_id,
    c.nombre_completo as cliente,
    f.date_key as fecha_emision,
    f.fecha_vencimiento,
    f.total::double as monto_mxn,
    case
        when coalesce(p.pagado, 0) >= f.total - 1 then 'Pagada'
        else 'Pendiente'
    end as estatus,
    case when coalesce(p.pagado, 0) >= f.total - 1 then p.ultimo_pago end as fecha_pago
from {{ ref('fct_factura') }} f
join {{ ref('dim_cliente') }} c on c.cliente_key = f.cliente_key
left join pagos p on p.factura_key = f.factura_key
