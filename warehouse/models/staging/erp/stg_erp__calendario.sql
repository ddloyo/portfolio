with source as (
    select * from {{ source('erp', 'calendario') }}
),

-- fecha debería ser la llave única de esta dimensión; la fuente trae
-- duplicados a propósito (ver reglas_validacion.csv de projects/13) —
-- se queda con una sola fila por fecha.
deduped as (
    select
        *,
        row_number() over (partition by fecha order by fecha) as rn
    from source
)

select
    fecha::date as fecha,
    try_cast(anio as int) as anio,
    try_cast(mes as int) as mes,
    -- DuckDB no trae initcap(); nombre_mes siempre es una sola palabra
    upper(substr(trim(nombre_mes), 1, 1)) || lower(substr(trim(nombre_mes), 2)) as nombre_mes,
    trim(trimestre) as trimestre,
    trim(dia_semana) as dia_semana,
    case trim(es_fin_de_semana)
        when 'True' then true
        when 'False' then false
        else null
    end as es_fin_de_semana
    -- es_feriado: columna huérfana, prácticamente vacía — se descarta aquí
from deduped
where rn = 1
