-- Validación de la facturación: cada línea de stg_erp__factura_linea con el
-- motivo por el que NO puede entrar a silver (NULL = válida). Las rechazadas
-- no se borran: se pueden consultar filtrando motivo_rechazo, igual que la
-- cola de revisión de las sucursales.
--
-- Reglas, en orden de precedencia (la primera que aplique es el motivo):
--   factura_id_nulo, factura_duplicada, fecha_invalida, cliente_inexistente,
--   sku_inexistente, canal_invalido, cantidad_o_precio_invalido.
--
-- El total NO es motivo de rechazo: se recalcula (cantidad * precio_unitario)
-- y se conserva el capturado en total_capturado para poder auditarlo. Tampoco
-- lo es la moneda: ~12% de las líneas vienen marcadas USD y NO se hace conversión
-- de tipo de cambio (decisión de alcance: se puede resolver después, no es
-- prioridad del proyecto). Silver no modela moneda y usa los montos tal como están
-- capturados, así que los totales mezclan líneas MXN y USD. Ver
-- database/LEGACY_TABLES.md.
--
-- Valida contra staging/intermediate y no contra las dimensiones, para que
-- intermediate no dependa de marts.
with numeradas as (
    select
        *,
        row_number() over (partition by factura_id order by fecha, sku, cliente_id) as rn
    from {{ ref('stg_erp__factura_linea') }}
),

clientes as (
    select distinct cliente_id from {{ ref('stg_crm__cliente') }} where cliente_id is not null
)

select
    n.factura_id,
    n.fecha,
    n.fecha_vencimiento,
    n.cliente_id,
    n.sku,
    n.canal_venta,
    n.cantidad,
    n.precio_unitario,
    n.total as total_capturado,
    round(n.cantidad * n.precio_unitario, 2) as total_calculado,
    case
        when n.factura_id is null then 'factura_id_nulo'
        when n.rn > 1 then 'factura_duplicada'
        when n.fecha is null or n.fecha_vencimiento is null then 'fecha_invalida'
        when n.cliente_id is null or c.cliente_id is null then 'cliente_inexistente'
        when n.sku is null or p.sku is null then 'sku_inexistente'
        when n.canal_venta is null then 'canal_invalido'
        when n.cantidad is null or n.cantidad <= 0 or n.precio_unitario is null or n.precio_unitario <= 0 then 'cantidad_o_precio_invalido'
    end as motivo_rechazo
from numeradas n
left join clientes c on c.cliente_id = n.cliente_id
left join {{ ref('int_producto_depurado') }} p on p.sku = n.sku
