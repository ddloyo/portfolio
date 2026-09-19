-- Une las 3 sucursales ya normalizadas y marca (sin descartar todavía) las
-- filas duplicadas exactas entre fuentes — mismo día, misma sucursal, mismo
-- monto, capturado más de una vez. El mart decide si las excluye.
with unido as (
    select * from {{ ref('stg_sucursales__cdmx') }}
    union all
    select * from {{ ref('stg_sucursales__guadalajara') }}
    union all
    select * from {{ ref('stg_sucursales__monterrey') }}
),

con_monto as (
    select * from unido where monto_mxn is not null
),

marcado as (
    select
        *,
        row_number() over (
            partition by fecha, sucursal, monto_mxn
            order by fuente
        ) as rn
    from con_monto
)

select
    fecha,
    sucursal,
    monto_mxn,
    fuente,
    (rn > 1) as es_duplicado_descartado
from marcado
