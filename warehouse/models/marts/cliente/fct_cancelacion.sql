-- Baja de contrato/plan. Un cliente cancela como máximo una vez.
select
    dc.cliente_key,
    c.fecha_cancelacion,
    c.motivo
from {{ ref('stg_crm__cancelacion') }} c
join {{ ref('dim_cliente') }} dc on dc.cliente_id = c.cliente_id
where c.fecha_cancelacion is not null
