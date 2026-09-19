-- Dashboard 03 · projects/03-scorecard-metas-vs-resultados/data/scorecard.csv
-- Un renglón por KPI: el resultado del último mes completo contra su meta vigente.
with ultimo as (
    select kpi, area, resultado
    from {{ ref('rpt_kpi_historico') }}
    qualify row_number() over (partition by kpi order by mes desc) = 1
)

select
    u.kpi,
    u.area,
    k.responsable,
    m.meta::double as meta,
    u.resultado,
    k.unidad,
    k.menor_es_mejor
from ultimo u
join {{ ref('dim_kpi') }} k on k.nombre_kpi = u.kpi
join {{ ref('fct_kpi_meta') }} m on m.kpi_key = k.kpi_key
