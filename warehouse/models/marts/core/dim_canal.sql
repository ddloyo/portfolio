-- Un solo catálogo para dos usos del mismo concepto: el canal por el que se
-- VENDE (pedidos, facturas) y el canal por el que se ADQUIRIÓ al cliente o al
-- que se le invierte (marketing). tipo_canal dice cuál es; 'ambos' si un
-- nombre aparece en los dos mundos.
with nombres as (
    select canal_venta as nombre_canal, 'venta' as origen from {{ ref('stg_pos__pedido_linea') }}
    union all
    select canal_venta, 'venta' from {{ ref('stg_erp__factura_linea') }}
    union all
    select canal, 'marketing' from {{ ref('stg_ads__marketing_gasto') }}
    union all
    select canal_adquisicion, 'marketing' from {{ ref('stg_crm__cliente') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['nombre_canal']) }} as canal_key,
    nombre_canal,
    case when count(distinct origen) > 1 then 'ambos' else min(origen) end as tipo_canal
from nombres
where nombre_canal is not null and nombre_canal <> ''
group by nombre_canal
