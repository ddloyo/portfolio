{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Dashboard 12 · projects/12-nps-causa-raiz/data/encuestas_nps.csv
-- Una fila por respuesta de encuesta. categoria se deriva del score (9-10 Promotor,
-- 7-8 Pasivo, 0-6 Detractor); motivo_detractor solo viene en detractores. Solo meses
-- completos: el dashboard compara el NPS reciente contra su línea base mensual.
select
    n.respuesta_id,
    strftime(date_trunc('month', n.date_key), '%Y-%m') as mes,
    n.score::bigint as score,
    n.categoria,
    n.motivo_detractor
from {{ ref('fct_encuesta_nps') }} n
where n.date_key < date_trunc('month', {{ ref_date }})
