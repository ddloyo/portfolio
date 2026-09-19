-- Producto/SKU listo para silver: un sku por fila, valores inválidos fuera y
-- categorías normalizadas. Lo comparten dim_producto y int_pedidos_enriquecidos
-- para que ambos vean exactamente el mismo precio/costo/categoría.
--
-- stg_erp__producto trae (a propósito, es la fuente sucia de projects/13):
--   * el mismo sku recapturado con otro precio
--   * precios y costos negativos
--   * categoría con mayúsculas/espacios inconsistentes, y 6 vacías
with productos as (
    select
        sku,
        nombre_producto,
        {{ canonical_case('categoria', ['Alimentos', 'Belleza', 'Deportes', 'Electrónica', 'Hogar', 'Juguetes', 'Papelería', 'Ropa']) }} as categoria_normalizada,
        subcategoria,
        unidad_medida,
        case when precio_unitario > 0 then precio_unitario end as precio_unitario,
        case when costo_unitario > 0 then costo_unitario end as costo_unitario,
        activo
    from {{ ref('stg_erp__producto') }}
    where sku is not null
),

un_sku_por_fila as (
    select *
    from productos
    qualify row_number() over (
        partition by sku
        order by (precio_unitario is null), (costo_unitario is null), nombre_producto
    ) = 1
)

select
    sku,
    nombre_producto,
    -- cada subcategoría pertenece a una sola categoría: una categoría vacía
    -- se recupera de los otros productos de su subcategoría
    coalesce(
        categoria_normalizada,
        max(categoria_normalizada) over (partition by subcategoria)
    ) as categoria,
    subcategoria,
    unidad_medida,
    precio_unitario,
    costo_unitario,
    activo
from un_sku_por_fila
