-- Catálogo de indicadores del scorecard. Dos orígenes:
--   * los KPIs de captura manual traen su propio catálogo (área, responsable,
--     unidad) en bronze.kpi_captura_manual;
--   * los KPIs derivables (se calculan sobre otros hechos, no se capturan)
--     no tienen fuente para su metadata, así que se declaran aquí. Los
--     responsables son ilustrativos, igual que las metas de kpi_meta.
with manuales as (
    select distinct kpi as nombre_kpi, area, responsable, unidad, menor_es_mejor
    from {{ ref('stg_scorecard__kpi_captura_manual') }}
),

derivables as (
    select * from (values
        ('Ingresos mensuales', 'Ventas', 'Dir. Comercial', 'MXN', false),
        ('Nuevos clientes', 'Ventas', 'Dir. Comercial', 'clientes', false),
        ('NPS', 'Experiencia de cliente', 'Dir. Experiencia de Cliente', 'puntos', false)
    ) as t (nombre_kpi, area, responsable, unidad, menor_es_mejor)
)

select
    {{ dbt_utils.generate_surrogate_key(['nombre_kpi']) }} as kpi_key,
    nombre_kpi,
    area,
    responsable,
    unidad,
    menor_es_mejor
from (
    select * from manuales
    union all
    select * from derivables
)
