{#
  Recibe isodow(fecha) (1=lunes .. 7=domingo) y devuelve el nombre en español.
#}
{% macro nombre_dia_es(isodow_col) %}
case {{ isodow_col }}
    when 1 then 'Lunes' when 2 then 'Martes' when 3 then 'Miércoles'
    when 4 then 'Jueves' when 5 then 'Viernes' when 6 then 'Sábado'
    when 7 then 'Domingo'
end
{% endmacro %}
