{#
  Test genérico reutilizable: reproduce la regla "consistencia de cálculo"
  de projects/13-data-health-check (total debe ser cantidad × precio_unitario).
  A diferencia de un test singular, este se puede aplicar a cualquier modelo
  con ese patrón de columnas declarándolo en su schema.yml — no hay que
  reescribir la lógica por tabla.
#}
{% test total_matches_lineas(model, column_name, cantidad_column, precio_column, tolerance=0.01) %}

select
    *,
    {{ column_name }} as total_capturado,
    {{ cantidad_column }} * {{ precio_column }} as total_esperado
from {{ model }}
where {{ column_name }} is null
   or abs({{ column_name }} - ({{ cantidad_column }} * {{ precio_column }})) > {{ tolerance }}

{% endtest %}
