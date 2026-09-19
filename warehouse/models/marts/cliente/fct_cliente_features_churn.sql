{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Feature set de churn, 1 fila por cliente con plan de servicio, CALCULADO a
-- partir de los hechos operativos (cargos, tickets, actividad, cancelación).
-- Reemplaza al seed clientes_churn de projects/04, que traía estas features ya
-- hechas.
--
-- Todas las features se miden a la fecha de corte del cliente: su fecha de
-- cancelación si ya canceló (es lo que el modelo habría visto justo antes de
-- perderlo) o la fecha de referencia del proyecto si sigue activo. Medirlas
-- contra "hoy" para quien canceló hace un año daría dias_desde_ultima_actividad
-- enormes y separaría a los cancelados por una razón trivial.
--
-- usage_score: puntos de uso de los últimos 90 días sobre 30 puntos
-- (≈ actividad "normal"), acotado a 0-100. Definición propia: el DDL solo dice
-- que sale de fct_evento_actividad.
with clientes as (
    select cliente_key, fecha_alta, tipo_contrato, plan
    from {{ ref('dim_cliente') }}
    where plan is not null
),

base as (
    select
        c.*,
        can.fecha_cancelacion,
        coalesce(can.fecha_cancelacion, {{ ref_date }}) as fecha_snapshot
    from clientes c
    left join {{ ref('fct_cancelacion') }} can on can.cliente_key = c.cliente_key
),

cargos as (
    select
        s.cliente_key,
        s.gasto_mensual_mxn,
        make_date(min(s.mes_key) over (partition by s.cliente_key) // 100,
                  min(s.mes_key) over (partition by s.cliente_key) % 100, 1) as primer_cargo,
        row_number() over (partition by s.cliente_key order by s.mes_key desc) as rn
    from {{ ref('fct_suscripcion_cargo') }} s
    join base b on b.cliente_key = s.cliente_key
    where make_date(s.mes_key // 100, s.mes_key % 100, 1) <= b.fecha_snapshot
),

tickets as (
    select b.cliente_key, count(*) as tickets_90d
    from {{ ref('fct_ticket_soporte') }} t
    join base b on b.cliente_key = t.cliente_key
    where t.fecha_apertura > b.fecha_snapshot - 90 and t.fecha_apertura <= b.fecha_snapshot
    group by 1
),

actividad as (
    select
        b.cliente_key,
        max(e.date_key) as ultima_actividad,
        sum(case when e.date_key > b.fecha_snapshot - 90 then e.usage_points else 0 end) as puntos_90d
    from {{ ref('fct_evento_actividad') }} e
    join base b on b.cliente_key = e.cliente_key
    where e.date_key <= b.fecha_snapshot
    group by 1
)

select
    b.cliente_key,
    b.fecha_snapshot,
    date_diff('month', coalesce(b.fecha_alta, c.primer_cargo), b.fecha_snapshot)::decimal(10,2) as antiguedad_meses,
    c.gasto_mensual_mxn,
    coalesce(t.tickets_90d, 0)::int as tickets_soporte_90d,
    date_diff('day', coalesce(a.ultima_actividad, coalesce(b.fecha_alta, c.primer_cargo)), b.fecha_snapshot)::decimal(10,2) as dias_desde_ultima_actividad,
    least(100, 100 * coalesce(a.puntos_90d, 0) / 30)::decimal(6,2) as usage_score,
    b.tipo_contrato,
    b.plan,
    (b.fecha_cancelacion is not null) as churn_historico
from base b
join cargos c on c.cliente_key = b.cliente_key and c.rn = 1
left join tickets t on t.cliente_key = b.cliente_key
left join actividad a on a.cliente_key = b.cliente_key
