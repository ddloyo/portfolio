-- Test singular (no genérico: es una comparación específica entre 2 marts,
-- no una regla reutilizable). El total de rpt_ventas_diarias (solo líneas
-- con vendedor asignado) debe reconciliar exacto con el mismo filtro sobre
-- fct_pedidos — si un JOIN en el mart alguna vez descarta o duplica filas,
-- esto lo detecta antes que un dashboard construido encima.
with mart as (
    select round(sum(monto_mxn), 2) as total
    from {{ ref('rpt_ventas_diarias') }}
),

hecho as (
    select round(sum(importe_neto), 2) as total
    from {{ ref('fct_pedidos') }}
    where vendedor_id is not null
)

select
    mart.total as total_rpt_ventas_diarias,
    hecho.total as total_fct_pedidos_con_vendedor
from mart, hecho
where abs(mart.total - hecho.total) > 0.01
