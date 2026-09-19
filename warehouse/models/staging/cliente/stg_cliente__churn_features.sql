with source as (
    select * from {{ source('cliente', 'clientes_churn') }}
),

cleaned as (
    select
        cliente_id,
        try_cast(antiguedad_meses as decimal(10,2)) as antiguedad_meses,
        try_cast(gasto_mensual_mxn as decimal(14,2)) as gasto_mensual_mxn,
        try_cast(tickets_soporte_90d as int) as tickets_soporte_90d,
        try_cast(dias_desde_ultima_actividad as decimal(10,2)) as dias_desde_ultima_actividad,
        try_cast(usage_score as decimal(6,2)) as usage_score,
        trim(tipo_contrato) as tipo_contrato,
        trim(plan) as plan,
        (try_cast(churn_historico as int) = 1) as churn_historico
    from source
)

select * from cleaned
