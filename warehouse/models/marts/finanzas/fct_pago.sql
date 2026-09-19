-- Pagos aplicados a una factura. Solo entran los de facturas que sobrevivieron
-- a la validación (un pago de una factura rechazada no tiene a qué colgarse).
-- El estatus (Pagada/Pendiente/Vencida) NO es una columna: se deriva de
-- comparar lo pagado contra el total de la factura.
select
    {{ dbt_utils.generate_surrogate_key(['p.pago_id']) }} as pago_key,
    p.pago_id,
    f.factura_key,
    p.fecha_pago,
    p.monto_pagado,
    p.metodo_pago
from {{ ref('stg_erp__pago') }} p
join {{ ref('fct_factura') }} f on f.factura_id = p.factura_id
where p.fecha_pago is not null and p.monto_pagado is not null
