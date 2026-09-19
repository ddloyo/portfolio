-- Respuesta de encuesta ya tipada. La categoría NO es un dato capturado: es la
-- regla estándar de NPS sobre el score (9-10 Promotor, 7-8 Pasivo, 0-6 Detractor).
select
    {{ dbt_utils.generate_surrogate_key(['n.respuesta_id']) }} as respuesta_key,
    n.respuesta_id,
    dc.cliente_key,
    n.fecha as date_key,
    n.score,
    case
        when n.score >= 9 then 'Promotor'
        when n.score >= 7 then 'Pasivo'
        else 'Detractor'
    end as categoria,
    n.motivo_detractor
from {{ ref('stg_encuestas__encuesta_nps') }} n
left join {{ ref('dim_cliente') }} dc on dc.cliente_id = n.cliente_id   -- respuesta anónima → cliente_key NULL
where n.fecha is not null and n.score is not null
