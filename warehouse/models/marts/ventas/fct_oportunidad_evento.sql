-- Bitácora del pipeline comercial: 1 fila por cambio de etapa de una oportunidad.
select
    {{ dbt_utils.generate_surrogate_key(['o.evento_id']) }} as evento_key,
    o.evento_id,
    o.oportunidad_id,
    o.fecha_evento as date_key,
    v.vendedor_key,
    o.etapa
from {{ ref('stg_crm__oportunidad_evento') }} o
left join {{ ref('dim_vendedor') }} v on v.vendedor_id = o.vendedor_id
