-- Días promedio de pago (DSO) por cliente y su segmento de riesgo de cobranza,
-- con los cortes de projects/08: hasta 20 días Puntual, hasta 70 Lento, más
-- Moroso. Solo entran clientes con al menos una factura con algún pago; el
-- plazo de cada factura se mide hasta su ÚLTIMO pago (una factura pagada en
-- parcialidades no se da por cobrada al primer abono).
with dias_por_factura as (
    select
        f.cliente_key,
        f.factura_key,
        date_diff('day', f.date_key, max(p.fecha_pago)) as dias_a_pago
    from {{ ref('fct_factura') }} f
    join {{ ref('fct_pago') }} p on p.factura_key = f.factura_key
    group by f.cliente_key, f.factura_key, f.date_key
)

select
    cliente_key,
    round(avg(dias_a_pago), 2)::decimal(10,2) as dso_promedio_dias,
    case
        when avg(dias_a_pago) <= 20 then 'Puntual'
        when avg(dias_a_pago) <= 70 then 'Lento'
        else 'Moroso'
    end as segmento_pago
from dias_por_factura
group by cliente_key
