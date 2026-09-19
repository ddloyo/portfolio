-- Un producto por SKU. Toda la depuración (duplicados, precios inválidos,
-- categorías) vive en int_producto_depurado; aquí solo se le pone llave.
select
    {{ dbt_utils.generate_surrogate_key(['sku']) }} as producto_key,
    sku,
    nombre_producto,
    categoria,
    subcategoria,
    unidad_medida,
    costo_unitario,
    precio_unitario,
    activo
from {{ ref('int_producto_depurado') }}
