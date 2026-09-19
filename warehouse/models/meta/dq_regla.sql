{% set pesos = dq_pesos() %}
{% set etiqueta_severidad = dq_etiquetas_severidad() %}
{% set etiqueta_tipo = dq_etiquetas_tipo() %}
{% set alias = {} %}
{% for t in dq_tablas() %}{% do alias.update({t['tabla']: t['alias']}) %}{% endfor %}

-- Catálogo de reglas de calidad (33). Sale del mismo macro que las evalúa
-- (dq_reglas), así que no puede desalinearse de sus resultados.
-- regla_key es el md5 de (tabla, campo, tipo, descripción): estable entre corridas.
-- tabla_reporte es el nombre con el que projects/13 conoce cada tabla
-- (clientes, productos, calendario, facturas); lo usan los reportes gold.
select
    regla_key,
    schema_tabla,
    tabla,
    tabla_reporte,
    campo,
    tipo,
    tipo_label,
    severidad,
    severidad_label,
    peso_max_pts::decimal(5,2) as peso_max_pts,
    descripcion
from (values
    {% for r in dq_reglas() -%}
    ('{{ local_md5(r["tabla"] ~ "|" ~ r["campo"] ~ "|" ~ r["tipo"] ~ "|" ~ r["descripcion"]) }}',
     'bronze', '{{ r["tabla"] }}', '{{ alias[r["tabla"]] }}', '{{ r["campo"] }}', '{{ r["tipo"] }}', '{{ etiqueta_tipo[r["tipo"]] }}',
     '{{ r["severidad"] }}', '{{ etiqueta_severidad[r["severidad"]] }}', {{ pesos[r["severidad"]] }},
     '{{ r["descripcion"] | replace("'", "''") }}'){% if not loop.last %},{% endif %}
    {% endfor %}
) as t (regla_key, schema_tabla, tabla, tabla_reporte, campo, tipo, tipo_label, severidad, severidad_label, peso_max_pts, descripcion)
