{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Dashboard 06 · projects/06-elasticidad-precios/data/precio_demanda.csv
-- Grano: 1 fila por producto x semana. semana es el índice consecutivo (1, 2, 3...)
-- de las semanas con ventas, no el número ISO. Solo semanas completas: una semana
-- a medias subestimaría las unidades y torcería la regresión log-log del dashboard.
with semanas_completas as (
    select semana_key
    from {{ ref('dim_semana') }}
    where fecha_inicio + 6 < {{ ref_date }}
),

semanal as (
    select
        dp.nombre_producto,
        (isoyear(fp.date_key) * 100 + weekofyear(fp.date_key))::int as semana_key,
        avg(fp.precio_unitario) as precio,
        sum(fp.cantidad) as unidades
    from {{ ref('fct_pedido') }} fp
    join {{ ref('dim_producto') }} dp on dp.producto_key = fp.producto_key
    group by 1, 2
)

select
    s.nombre_producto as producto,
    dense_rank() over (order by s.semana_key)::bigint as semana,
    round(s.precio, 2)::double as precio_mxn,
    s.unidades::double as unidades_vendidas
from semanal s
join semanas_completas c on c.semana_key = s.semana_key
