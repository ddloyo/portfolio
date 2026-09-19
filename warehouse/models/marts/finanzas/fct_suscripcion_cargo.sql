select
    dc.cliente_key,
    {{ mes_key('s.mes_inicio') }} as mes_key,
    s.gasto_mensual_mxn
from {{ ref('stg_erp__suscripcion_cargo') }} s
join {{ ref('dim_cliente') }} dc on dc.cliente_id = s.cliente_id
where s.mes_inicio is not null and s.gasto_mensual_mxn is not null
