-- stg_crm__cliente puede traer cliente_id duplicado (la fuente real de
-- projects/13 lo hace a propósito). Se resuelve aquí, no antes: staging
-- limpia tipos, el mart decide la regla de negocio para quedarse con una
-- sola fila por cliente (la más completa: prioriza no-nulos).
with clientes as (
    select * from {{ ref('stg_crm__cliente') }}
    where cliente_id is not null
),

priorizado as (
    select
        *,
        row_number() over (
            partition by cliente_id
            order by (email is null), (telefono is null), (fecha_alta is null)
        ) as rn
    from clientes
)

select
    cliente_id,
    nombre_completo,
    email,
    telefono,
    ciudad,
    segmento,
    fecha_alta
from priorizado
where rn = 1
