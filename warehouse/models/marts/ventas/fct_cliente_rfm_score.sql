{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Recencia / frecuencia / monto de los últimos 12 meses por cliente, y su
-- segmento: cuadrante recencia x valor, cada eje partido por su mediana.
--   reciente + alto valor → Campeones     reciente + bajo valor → Nuevos
--   inactivo + alto valor → En riesgo     inactivo + bajo valor → Hibernando
-- Solo entran clientes con al menos un pedido en la ventana.
with ventana as (
    select cliente_key, date_key, pedido_id, importe_neto
    from {{ ref('fct_pedido') }}
    where date_key > {{ ref_date }} - 365 and date_key <= {{ ref_date }}
),

rfm as (
    select
        cliente_key,
        date_diff('day', max(date_key), {{ ref_date }}) as recencia_dias,
        count(distinct pedido_id) as frecuencia,
        sum(importe_neto) as monto_total_12m
    from ventana
    group by 1
),

umbral as (
    select median(recencia_dias) as mediana_recencia, median(monto_total_12m) as mediana_monto from rfm
)

select
    r.cliente_key,
    r.recencia_dias::int as recencia_dias,
    r.frecuencia::int as frecuencia,
    r.monto_total_12m::decimal(14,2) as monto_total_12m,
    round(percent_rank() over (order by r.monto_total_12m) * 100, 2)::decimal(5,2) as percentil_valor,
    {{ quadrant_segment(
        x_col='r.recencia_dias', x_threshold='u.mediana_recencia',
        y_col='r.monto_total_12m', y_threshold='u.mediana_monto',
        labels=['En riesgo', 'Hibernando', 'Campeones', 'Nuevos']
    ) }} as segmento_rfm
from rfm r
cross join umbral u
