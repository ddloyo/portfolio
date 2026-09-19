-- Meta vigente por KPI (insumo de planeación). Sale del seed kpi_meta, que no
-- existía en el DDL de bronze: el diseño legacy no tenía origen para esta tabla.
select
    k.kpi_key,
    m.meta
from {{ ref('stg_scorecard__kpi_meta') }} m
join {{ ref('dim_kpi') }} k on k.nombre_kpi = m.kpi
