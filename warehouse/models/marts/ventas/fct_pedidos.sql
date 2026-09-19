{{
    config(
        materialized='incremental',
        unique_key='linea_id',
        incremental_strategy='delete+insert',
        on_schema_change='sync_all_columns'
    )
}}

-- Hecho central del warehouse (18-19k líneas de pedido, crece día a día).
-- Incremental por watermark de fecha: cada corrida solo procesa pedidos con
-- fecha posterior a la última fecha ya cargada, en vez de reescanear todo
-- el historial. `dbt run --full-refresh --select fct_pedidos` reconstruye
-- desde cero (necesario si cambia la lógica de int_pedidos_enriquecidos,
-- no solo cuando llegan datos nuevos).
with pedidos as (
    select * from {{ ref('int_pedidos_enriquecidos') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['linea_id']) }} as pedido_linea_key,
    linea_id,
    pedido_id,
    fecha as date_key,
    cliente_id,
    vendedor_id,
    canal_venta,
    sku,
    categoria,
    cantidad,
    precio_unitario,
    descuento_pct,
    importe_neto,
    costo_total
from pedidos

{% if is_incremental() %}
where fecha > (select coalesce(max(date_key), date '1900-01-01') from {{ this }})
{% endif %}
