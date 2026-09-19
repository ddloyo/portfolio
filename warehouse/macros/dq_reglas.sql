{#
  Catálogo ÚNICO de reglas de calidad de datos: las 33 reglas de
  projects/13-data-health-check/run_analysis.py, traducidas a SQL y ejecutadas
  contra las tablas bronze reales (crm_cliente, producto, calendario,
  factura_linea). De este macro salen tanto la metadata (meta.dq_regla) como el
  resultado de cada regla (meta.dq_resultado_regla): así el catálogo y su
  evaluación no pueden desincronizarse.

  Cada regla trae `sql`: un SELECT que devuelve n_filas (a cuántas filas aplica
  la regla) y n_fallas (cuántas la incumplen). Todo se evalúa sobre el texto
  crudo (bronze es varchar): si se tipara antes, "$1,234.50" pasaría inadvertido,
  que es justo lo que una auditoría no debe hacer.
#}

{% macro dq_es_nulo(col) -%}
({{ col }} is null or trim({{ col }}) = '' or lower({{ col }}) = 'nan')
{%- endmacro %}

{# número desde texto de moneda: '$1,234.50' o plano → double; NULL si no se puede #}
{% macro dq_numero(col) -%}
try_cast(replace(replace(trim({{ col }}), '$', ''), ',', '') as double)
{%- endmacro %}

{# el valor no está escrito como el catálogo pero sí una vez normalizado (mayúsculas/espacios) #}
{% macro dq_mal_escrito(col, valores) -%}
({{ col }} is not null and trim({{ col }}) <> ''
 and {{ col }} not in ({% for v in valores %}'{{ v }}'{% if not loop.last %}, {% endif %}{% endfor %})
 and lower(trim({{ col }})) in ({% for v in valores %}lower('{{ v }}'){% if not loop.last %}, {% endif %}{% endfor %}))
{%- endmacro %}

{# 'select n_filas, n_fallas' sobre una tabla, con predicado de denominador y de falla #}
{% macro dq_sql(rel, denominador, falla, extra_from='') -%}
select count(*) filter (where {{ denominador }}) as n_filas, count(*) filter (where {{ falla }}) as n_fallas
from {{ rel }}{{ extra_from }}
{%- endmacro %}

{% macro dq_sql_dup(rel, partido, aplica='true', denominador='true') -%}
select count(*) filter (where {{ denominador }}) as n_filas,
       count(*) filter (where {{ aplica }} and dup) as n_fallas
from (select *, count(*) over (partition by {{ partido }}) > 1 as dup from {{ rel }})
{%- endmacro %}

{% macro dq_pesos() -%}
{{ return({'critical': 65, 'high': 40, 'medium': 20, 'low': 9, 'info': 0}) }}
{%- endmacro %}

{% macro dq_etiquetas_severidad() -%}
{{ return({'critical': 'Crítica', 'high': 'Alta', 'medium': 'Media', 'low': 'Baja', 'info': 'Informativa'}) }}
{%- endmacro %}

{% macro dq_etiquetas_tipo() -%}
{{ return({'completeness': 'Completitud', 'uniqueness': 'Unicidad', 'validity': 'Validez/Formato',
           'integrity': 'Integridad referencial', 'consistency': 'Consistencia de cálculo', 'orphan_field': 'Campo huérfano'}) }}
{%- endmacro %}

{# plantillas del plan de remediación, con {campo} y {n} #}
{% macro dq_plantillas_remediacion() -%}
{{ return({
    'completeness': "Hacer obligatorio `{campo}` en el formulario/ETL de origen; las {n} filas ya capturadas van a una cola de revisión manual, no a imputación automática.",
    'uniqueness': "Definir `{campo}` (o la combinación de campos) como llave única en la base; deduplicar las {n} filas detectadas antes de usar la tabla en cualquier agregado.",
    'validity': "Agregar validación de formato/rango en el punto de captura para `{campo}`; poner en cuarentena o corregir las {n} filas fuera de rango.",
    'integrity': "Bloquear la inserción de filas cuyo `{campo}` no exista en el catálogo maestro; investigar el origen de las {n} referencias huérfanas (¿catálogo desactualizado o borrado sin cascada?).",
    'consistency': "Recalcular `{campo}` desde sus componentes en vez de aceptar el valor capturado manualmente; revisar las {n} filas donde no cuadra con la fórmula esperada.",
    'orphan_field': "Confirmar con el dueño del sistema si `{campo}` sigue en uso; si no, retirarlo del esquema para que ningún reporte futuro asuma que existe."
}) }}
{%- endmacro %}

{# Tablas auditadas: nombre real en bronze, y el nombre con el que las conoce el reporte del proyecto 13 #}
{% macro dq_tablas() -%}
{{ return([
    {'tabla': 'crm_cliente', 'alias': 'clientes', 'relacion': source('crm', 'crm_cliente')},
    {'tabla': 'producto', 'alias': 'productos', 'relacion': source('erp', 'producto')},
    {'tabla': 'calendario', 'alias': 'calendario', 'relacion': source('erp', 'calendario')},
    {'tabla': 'factura_linea', 'alias': 'facturas', 'relacion': source('erp', 'factura_linea')}
]) }}
{%- endmacro %}

{% macro dq_reglas() -%}
{% set C = source('crm', 'crm_cliente') %}
{% set P = source('erp', 'producto') %}
{% set K = source('erp', 'calendario') %}
{% set F = source('erp', 'factura_linea') %}
{% set CIUDADES = ['Ciudad de México', 'Guadalajara', 'Monterrey', 'Puebla', 'Tijuana', 'Querétaro', 'León', 'Mérida', 'Toluca', 'Cancún'] %}
{% set SEGMENTOS = ['Premium', 'Estándar', 'Básico'] %}
{% set CATEGORIAS = ['Electrónica', 'Ropa', 'Hogar', 'Alimentos', 'Juguetes', 'Deportes', 'Belleza', 'Papelería'] %}
{% set MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] %}
{% set DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'] %}
{% set MONEDAS = ['MXN', 'USD'] %}
{% set R = [] %}

{# ------------------------------------------------------------------ clientes #}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'email', 'tipo': 'completeness', 'severidad': 'high',
    'descripcion': 'El email no debe estar vacío -- es el canal principal de retención/cobranza.',
    'sql': dq_sql(C, 'true', dq_es_nulo('email'))}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'telefono', 'tipo': 'completeness', 'severidad': 'medium',
    'descripcion': 'El teléfono no debe estar vacío.',
    'sql': dq_sql(C, 'true', dq_es_nulo('telefono'))}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'email', 'tipo': 'validity', 'severidad': 'high',
    'descripcion': 'El email debe tener formato válido (usuario@dominio.tld), sin espacios.',
    'sql': dq_sql(C, "email is not null and trim(email) <> ''", "email is not null and trim(email) <> '' and not regexp_matches(trim(email), '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')")}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'cliente_id', 'tipo': 'uniqueness', 'severidad': 'critical',
    'descripcion': 'cliente_id debe ser único -- llave primaria del catálogo.',
    'sql': dq_sql_dup(C, 'cliente_id', aplica='cliente_id is not null')}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'email', 'tipo': 'uniqueness', 'severidad': 'high',
    'descripcion': 'El mismo email no debería repetirse en dos cliente_id distintos (alta duplicada).',
    'sql': "select count(*) as n_filas, count(*) filter (where dup) as n_fallas from (select *, count(*) over (partition by email) > 1 as dup from " ~ C ~ " where email is not null and trim(email) <> '')"}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'ciudad', 'tipo': 'validity', 'severidad': 'medium',
    'descripcion': 'ciudad debe respetar la capitalización del catálogo maestro (evita fragmentar el mismo valor en variantes).',
    'sql': dq_sql(C, 'true', dq_mal_escrito('ciudad', CIUDADES))}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'segmento', 'tipo': 'validity', 'severidad': 'medium',
    'descripcion': 'segmento debe ser uno de {Premium, Estándar, Básico} con capitalización exacta.',
    'sql': dq_sql(C, 'true', dq_mal_escrito('segmento', SEGMENTOS))}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'fecha_alta', 'tipo': 'validity', 'severidad': 'high',
    'descripcion': 'fecha_alta debe capturarse en formato estándar ISO (YYYY-MM-DD), no mezclado con DD/MM/YYYY o MM/DD/YYYY.',
    'sql': dq_sql(C, 'true', "fecha_alta is not null and try_strptime(fecha_alta, '%Y-%m-%d') is null")}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'nombre_completo', 'tipo': 'validity', 'severidad': 'low',
    'descripcion': 'nombre_completo no debe traer espacios al inicio/final ni dobles espacios.',
    'sql': dq_sql(C, 'true', "nombre_completo is not null and (nombre_completo <> trim(nombre_completo) or nombre_completo like '%  %')")}) %}
{% do R.append({'tabla': 'crm_cliente', 'campo': 'campo_legacy_crm_id', 'tipo': 'orphan_field', 'severidad': 'info',
    'descripcion': 'Columna heredada de un CRM anterior, 100% vacía -- nunca se migró ni se usa en ningún reporte.',
    'sql': dq_sql(C, 'true', dq_es_nulo('campo_legacy_crm_id'))}) %}

{# ----------------------------------------------------------------- productos #}
{% do R.append({'tabla': 'producto', 'campo': 'sku', 'tipo': 'uniqueness', 'severidad': 'critical',
    'descripcion': 'sku debe ser único -- llave primaria del catálogo de productos.',
    'sql': dq_sql_dup(P, 'sku', aplica='sku is not null')}) %}
{% do R.append({'tabla': 'producto', 'campo': 'precio_unitario', 'tipo': 'completeness', 'severidad': 'high',
    'descripcion': 'precio_unitario no debe estar vacío -- sin él no se puede facturar ni auditar el total.',
    'sql': dq_sql(P, 'true', dq_es_nulo('precio_unitario'))}) %}
{% do R.append({'tabla': 'producto', 'campo': 'categoria', 'tipo': 'completeness', 'severidad': 'medium',
    'descripcion': 'categoria no debe estar vacía -- se usa para reportes de mezcla de producto.',
    'sql': dq_sql(P, 'true', dq_es_nulo('categoria'))}) %}
{% do R.append({'tabla': 'producto', 'campo': 'precio_unitario', 'tipo': 'validity', 'severidad': 'high',
    'descripcion': "precio_unitario debe almacenarse como número plano, no como texto de moneda ('$1,234.50').",
    'sql': dq_sql(P, 'true', "precio_unitario is not null and regexp_matches(precio_unitario, '[$,]')")}) %}
{% do R.append({'tabla': 'producto', 'campo': 'precio_unitario', 'tipo': 'validity', 'severidad': 'high',
    'descripcion': 'precio_unitario debe ser mayor a cero.',
    'sql': dq_sql(P, dq_numero('precio_unitario') ~ ' is not null', dq_numero('precio_unitario') ~ ' <= 0')}) %}
{% do R.append({'tabla': 'producto', 'campo': 'categoria', 'tipo': 'validity', 'severidad': 'medium',
    'descripcion': 'categoria debe respetar la capitalización del catálogo maestro (8 categorías fijas).',
    'sql': dq_sql(P, 'true', dq_mal_escrito('categoria', CATEGORIAS))}) %}
{% do R.append({'tabla': 'producto', 'campo': 'nombre_producto', 'tipo': 'validity', 'severidad': 'low',
    'descripcion': 'nombre_producto no debe traer espacios al inicio/final.',
    'sql': dq_sql(P, 'true', 'nombre_producto is not null and nombre_producto <> trim(nombre_producto)')}) %}
{% do R.append({'tabla': 'producto', 'campo': 'campo_obsoleto_bodega_2019', 'tipo': 'orphan_field', 'severidad': 'info',
    'descripcion': 'Columna de una bodega que ya no opera, 100% vacía -- candidata a eliminarse del esquema.',
    'sql': dq_sql(P, 'true', dq_es_nulo('campo_obsoleto_bodega_2019'))}) %}

{# ---------------------------------------------------------------- calendario #}
{% do R.append({'tabla': 'calendario', 'campo': 'fecha', 'tipo': 'uniqueness', 'severidad': 'high',
    'descripcion': 'fecha debe ser única -- es la llave de la dimensión de tiempo.',
    'sql': dq_sql_dup(K, 'fecha', aplica='fecha is not null')}) %}
{% do R.append({'tabla': 'calendario', 'campo': 'fecha', 'tipo': 'validity', 'severidad': 'medium',
    'descripcion': 'El rango de fechas no debe tener huecos -- cada día del periodo debe existir exactamente una vez.',
    'sql': "select date_diff('day', min(f), max(f)) + 1 as n_filas, greatest(date_diff('day', min(f), max(f)) + 1 - count(distinct f), 0) as n_fallas from (select try_cast(fecha as date) as f from " ~ K ~ ") where f is not null"}) %}
{% do R.append({'tabla': 'calendario', 'campo': 'es_feriado', 'tipo': 'orphan_field', 'severidad': 'info',
    'descripcion': 'Columna planeada para el calendario oficial de feriados MX, 100% vacía -- nunca se pobló.',
    'sql': dq_sql(K, 'true', dq_es_nulo('es_feriado'))}) %}
{% do R.append({'tabla': 'calendario', 'campo': 'nombre_mes', 'tipo': 'validity', 'severidad': 'low',
    'descripcion': "nombre_mes debe respetar la capitalización estándar (p.ej. 'Enero', no 'enero' ni ' Enero ').",
    'sql': dq_sql(K, 'true', dq_mal_escrito('nombre_mes', MESES))}) %}
{% do R.append({'tabla': 'calendario', 'campo': 'dia_semana', 'tipo': 'validity', 'severidad': 'low',
    'descripcion': 'dia_semana debe respetar la capitalización estándar.',
    'sql': dq_sql(K, 'true', dq_mal_escrito('dia_semana', DIAS))}) %}

{# ------------------------------------------------------------------ facturas #}
{% do R.append({'tabla': 'factura_linea', 'campo': 'cliente_id', 'tipo': 'completeness', 'severidad': 'high',
    'descripcion': 'cliente_id no debe estar vacío -- sin él la venta no se puede atribuir a ningún cliente.',
    'sql': dq_sql(F, 'true', dq_es_nulo('cliente_id'))}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'total', 'tipo': 'completeness', 'severidad': 'high',
    'descripcion': 'total no debe estar vacío.',
    'sql': dq_sql(F, 'true', dq_es_nulo('total'))}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'cliente_id', 'tipo': 'integrity', 'severidad': 'critical',
    'descripcion': 'cliente_id debe existir en el catálogo de clientes (integridad referencial) -- si no, la venta queda huérfana en cualquier reporte por cliente.',
    'sql': dq_sql(F, "cliente_id is not null and trim(cliente_id) <> ''", "cliente_id is not null and trim(cliente_id) <> '' and cliente_id not in (select cliente_id from " ~ C ~ " where cliente_id is not null)")}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'sku', 'tipo': 'integrity', 'severidad': 'critical',
    'descripcion': 'sku debe existir en el catálogo de productos (integridad referencial) -- si no, la venta queda huérfana en cualquier reporte por producto/categoría.',
    'sql': dq_sql(F, "sku is not null and trim(sku) <> ''", "sku is not null and trim(sku) <> '' and sku not in (select sku from " ~ P ~ " where sku is not null)")}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'cantidad', 'tipo': 'validity', 'severidad': 'high',
    'descripcion': 'cantidad debe ser mayor a cero (una devolución/nota de crédito no debería capturarse como venta negativa).',
    'sql': dq_sql(F, 'try_cast(cantidad as double) is not null', 'try_cast(cantidad as double) <= 0')}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'precio_unitario', 'tipo': 'validity', 'severidad': 'high',
    'descripcion': 'precio_unitario debe almacenarse como número plano, no como texto de moneda.',
    'sql': dq_sql(F, 'true', "precio_unitario is not null and regexp_matches(precio_unitario, '[$,]')")}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'moneda', 'tipo': 'validity', 'severidad': 'medium',
    'descripcion': "moneda debe ser 'MXN' o 'USD' con capitalización exacta.",
    'sql': dq_sql(F, 'true', dq_mal_escrito('moneda', MONEDAS))}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'fecha', 'tipo': 'validity', 'severidad': 'high',
    'descripcion': 'fecha debe capturarse en formato estándar ISO (YYYY-MM-DD), no mezclado con DD/MM/YYYY o MM/DD/YYYY.',
    'sql': dq_sql(F, 'true', "fecha is not null and try_strptime(fecha, '%Y-%m-%d') is null")}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'factura_id', 'tipo': 'uniqueness', 'severidad': 'high',
    'descripcion': 'No debe existir la misma línea de factura (fecha + cliente + sku + cantidad + precio) capturada más de una vez.',
    'sql': dq_sql_dup(F, 'fecha, cliente_id, sku, cantidad, precio_unitario')}) %}
{% do R.append({'tabla': 'factura_linea', 'campo': 'total', 'tipo': 'consistency', 'severidad': 'critical',
    'descripcion': 'total debe ser igual a cantidad × precio_unitario (tolerancia $1) -- un valor distinto implica un override manual sin recalcular (p.ej. un descuento no reflejado).',
    'sql': "select count(*) as n_filas, count(*) filter (where abs(t - e) > 1.0) as n_fallas from (select " ~ dq_numero('total') ~ " as t, round(try_cast(cantidad as double) * " ~ dq_numero('precio_unitario') ~ ", 2) as e from " ~ F ~ ") where t is not null and e is not null"}) %}

{{ return(R) }}
{%- endmacro %}
