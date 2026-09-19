{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Dashboard 02 · projects/02-funnel-fuga-ventas/data/funnel_semanal.csv
-- Eventos del pipeline contados por semana ISO y etapa. semana es el índice
-- consecutivo (1, 2, 3...) de las semanas del reporte, no el número ISO.
-- Solo semanas completas: la semana en curso se excluiría del conteo o parecería
-- una fuga de conversión que no existe.
with semanas_completas as (
    select semana_key
    from {{ ref('dim_semana') }}
    where fecha_inicio + 6 < {{ ref_date }}
),

conteo as (
    select
        (isoyear(e.date_key) * 100 + weekofyear(e.date_key))::int as semana_key,
        count(*) filter (where e.etapa = 'lead') as leads,
        count(*) filter (where e.etapa = 'contactado') as contactados,
        count(*) filter (where e.etapa = 'calificado') as calificados,
        count(*) filter (where e.etapa = 'propuesta') as propuestas,
        count(*) filter (where e.etapa = 'cierre') as cierres
    from {{ ref('fct_oportunidad_evento') }} e
    group by 1
)

select
    dense_rank() over (order by c.semana_key)::bigint as semana,
    c.leads::bigint as leads,
    c.contactados::bigint as contactados,
    c.calificados::bigint as calificados,
    c.propuestas::bigint as propuestas,
    c.cierres::bigint as cierres
from conteo c
join semanas_completas s on s.semana_key = c.semana_key
order by semana
