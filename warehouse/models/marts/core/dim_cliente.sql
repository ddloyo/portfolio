-- stg_crm__cliente puede traer cliente_id duplicado (la fuente real de
-- projects/13 lo hace a propósito). Se resuelve aquí, no antes: staging
-- limpia tipos, el mart decide la regla de negocio para quedarse con una
-- sola fila por cliente (la más completa: prioriza no-nulos). Además
-- normaliza los catálogos (ciudad, segmento) que llegan con mayúsculas y
-- espacios inconsistentes.
with clientes as (
    select * from {{ ref('stg_crm__cliente') }}
    where cliente_id is not null
),

priorizado as (
    select
        *,
        row_number() over (
            partition by cliente_id
            order by (email is null), (telefono is null), (fecha_alta is null), nombre_completo
        ) as rn
    from clientes
),

unico as (
    select * from priorizado where rn = 1
)

select
    {{ dbt_utils.generate_surrogate_key(['u.cliente_id']) }} as cliente_key,
    u.cliente_id,
    u.nombre_completo,
    u.email,
    u.telefono,
    {{ canonical_case('u.ciudad', ['Ciudad de México', 'Toluca', 'Puebla', 'Querétaro', 'Guadalajara', 'León', 'Monterrey', 'Tijuana', 'Mérida', 'Cancún']) }} as ciudad,
    r.region_key,
    {{ canonical_case('u.segmento', ['Básico', 'Estándar', 'Premium']) }} as segmento,
    u.fecha_alta,
    u.tipo_contrato,
    u.plan,
    u.canal_adquisicion
from unico u
left join {{ ref('dim_region') }} r on r.nombre_region = u.region
