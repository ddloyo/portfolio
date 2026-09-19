-- Grano semanal (semana ISO). semana_key = año ISO * 100 + n° de semana,
-- p.ej. 202611: determinista y legible. Las semanas de los extremos del rango
-- de dim_fecha pueden quedar incompletas.
select
    (isoyear(date_key) * 100 + numero_semana_iso)::int as semana_key,
    isoyear(date_key)::smallint as anio,
    numero_semana_iso as numero_semana,
    min(date_key) as fecha_inicio,
    max(date_key) as fecha_fin
from {{ ref('dim_fecha') }}
group by 1, 2, 3
