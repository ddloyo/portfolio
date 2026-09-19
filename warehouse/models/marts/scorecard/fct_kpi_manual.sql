-- Resultado mensual de los KPIs que ningún hecho operativo permite derivar.
select
    k.kpi_key,
    {{ mes_key('m.mes_inicio') }} as mes_key,
    m.resultado
from {{ ref('stg_scorecard__kpi_captura_manual') }} m
join {{ ref('dim_kpi') }} k on k.nombre_kpi = m.kpi
where m.mes_inicio is not null and m.resultado is not null
