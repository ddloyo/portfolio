with productos as (
    select * from {{ ref('stg_erp__producto') }}
    where sku is not null
),

priorizado as (
    select
        *,
        row_number() over (
            partition by sku
            order by (precio_unitario is null), (costo_unitario is null)
        ) as rn
    from productos
)

select
    sku,
    nombre_producto,
    categoria,
    precio_unitario,
    costo_unitario,
    unidad_medida,
    activo
from priorizado
where rn = 1
