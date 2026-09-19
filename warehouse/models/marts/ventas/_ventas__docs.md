{% docs un_hecho_seis_reportes %}
Reproduce `projects/01-sales-performance-dashboard/data/ventas_diarias.csv`.

`fct_pedidos` es el hecho central del warehouse — 1 fila por SKU vendido en
el canal gestionado (equipo comercial / e-commerce / marketplace). No son
fuentes de datos distintas: es la misma venta, agregada de formas distintas
para varios de los datasets del portafolio:

| Mart | Grano del GROUP BY |
|---|---|
| `rpt_ventas_diarias` (este modelo) | fecha × equipo × vendedor × categoría |
| `rpt_transacciones` | cliente × día |
| `rpt_precio_demanda` | producto × semana |
| `rpt_demanda_diaria` | SKU × día |

El diseño original (`database/README.md`) documenta dos marts adicionales
sobre el mismo hecho (ROI de marketing, reporte ejecutivo) que quedaron
fuera del alcance de este núcleo por requerir datos de marketing/cancelación
que no se generaron todavía — el patrón para agregarlos es idéntico: otro
`GROUP BY` sobre `fct_pedidos`.
{% enddocs %}
