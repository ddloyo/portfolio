select
    c.canal_key,
    g.fecha as date_key,
    g.gasto_mxn
from {{ ref('stg_ads__marketing_gasto') }} g
join {{ ref('dim_canal') }} c on c.nombre_canal = g.canal
where g.fecha is not null and g.gasto_mxn is not null
