{#
  DuckDB no trae una función de locale para nombres de mes en español
  (strftime %B da inglés) — se resuelve con un CASE explícito en vez de
  depender de la configuración regional del sistema donde corra dbt, que en
  CI puede no ser la misma que en local.
#}
{% macro nombre_mes_es(mes_col) %}
case {{ mes_col }}
    when 1 then 'Enero' when 2 then 'Febrero' when 3 then 'Marzo'
    when 4 then 'Abril' when 5 then 'Mayo' when 6 then 'Junio'
    when 7 then 'Julio' when 8 then 'Agosto' when 9 then 'Septiembre'
    when 10 then 'Octubre' when 11 then 'Noviembre' when 12 then 'Diciembre'
end
{% endmacro %}
