-- Se genera por date_spine (dbt_utils) en vez de depender de
-- stg_erp__calendario: ese seed real solo cubre 2024-01-01 a 2025-12-31, y
-- fct_pedidos necesita fechas hasta 2026-09. date_spine garantiza cobertura
-- completa y sin huecos del rango que el resto del warehouse realmente usa.
with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2025-01-01' as date)",
        end_date="cast('2026-09-19' as date)"
    ) }}
)

select
    date_day::date as date_key,
    extract(year from date_day)::smallint as anio,
    extract(month from date_day)::smallint as mes,
    {{ nombre_mes_es('extract(month from date_day)') }} as nombre_mes,
    'Q' || extract(quarter from date_day)::varchar as trimestre,
    isodow(date_day)::smallint as numero_dia_semana_iso,
    {{ nombre_dia_es('isodow(date_day)') }} as dia_semana,
    (isodow(date_day) in (6, 7)) as es_fin_de_semana,
    isoyear(date_day)::varchar || '-W' || lpad(weekofyear(date_day)::varchar, 2, '0') as semana_iso
from spine
