{% docs dim_cliente_dedupe %}
Un cliente, una fila. La fuente (`stg_crm__cliente`, reutilizada de
`projects/13-data-health-check`) trae duplicados suaves a propósito: el
mismo `cliente_id` puede aparecer más de una vez con distintos campos
llenos o vacíos.

La regla de desduplicación es: para cada `cliente_id`, quedarse con la fila
que tiene **menos columnas nulas** entre `email`, `telefono` y `fecha_alta`
(`ROW_NUMBER() OVER (PARTITION BY cliente_id ORDER BY (col IS NULL), ...)`).
No es una fusión de campos (no se combina el email de una fila con el
teléfono de otra) — es una elección determinista de "la fila más completa
gana", que es reproducible entre corridas y fácil de auditar.
{% enddocs %}
