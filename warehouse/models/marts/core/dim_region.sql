-- Territorio comercial asignado por el CRM a cada cliente.
select distinct
    {{ dbt_utils.generate_surrogate_key(['region']) }} as region_key,
    region as nombre_region
from {{ ref('stg_crm__cliente') }}
where region is not null
