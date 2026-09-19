{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Elasticidad precio-demanda por producto: pendiente de la regresión log-log
-- ln(unidades) ~ ln(precio) sobre la serie semanal (regr_slope / regr_r2 son
-- nativas de DuckDB, no hace falta salir de SQL). Solo productos con al menos
-- 10 semanas con ventas.
--
-- impacto_proyectado_10pct: cambio esperado del ingreso anual si el precio
-- sube 10%. Con elasticidad e, el ingreso se multiplica por 1.10^(1+e).
-- accion_recomendada: cuadrante |elasticidad| x confianza (R²), cada eje
-- partido por su mediana.
with semanal as (
    select
        p.producto_key,
        d.semana_iso,
        avg(p.precio_unitario) as precio,
        sum(p.cantidad) as unidades
    from {{ ref('fct_pedido') }} p
    join {{ ref('dim_fecha') }} d on d.date_key = p.date_key
    group by 1, 2
),

regresion as (
    select
        producto_key,
        regr_slope(ln(unidades), ln(precio)) as elasticidad,
        regr_r2(ln(unidades), ln(precio)) as r2
    from semanal
    where unidades > 0 and precio > 0
    group by 1
    having count(*) >= 10
),

ingreso as (
    select producto_key, sum(importe_neto) as ingreso_anual_actual
    from {{ ref('fct_pedido') }}
    where date_key > {{ ref_date }} - 364 and date_key <= {{ ref_date }}
    group by 1
),

umbral as (
    select median(abs(elasticidad)) as mediana_elasticidad, median(r2) as mediana_r2 from regresion
)

select
    r.producto_key,
    round(r.elasticidad, 4)::decimal(10,4) as elasticidad,
    round(r.r2, 4)::decimal(5,4) as r2,
    coalesce(i.ingreso_anual_actual, 0)::decimal(16,2) as ingreso_anual_actual,
    round(coalesce(i.ingreso_anual_actual, 0) * (power(1.10, 1 + r.elasticidad) - 1), 2)::decimal(16,2) as impacto_proyectado_10pct,
    {{ quadrant_segment(
        x_col='abs(r.elasticidad)', x_threshold='u.mediana_elasticidad',
        y_col='r.r2', y_threshold='u.mediana_r2',
        labels=['Evitar subir precio', 'Validar antes de mover precio', 'Subir precio', 'Recolectar más datos']
    ) }} as accion_recomendada
from regresion r
cross join umbral u
left join ingreso i on i.producto_key = r.producto_key
