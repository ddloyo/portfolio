# Base de datos del portafolio — arquitectura bronze / silver / gold

> **Diseño original, en migración a dbt.** La única fuente de verdad
> ejecutable es el proyecto [`warehouse/`](../warehouse/); los `.sql` de
> `schema/` son referencia y se borrarán cuando cada capa esté migrada. Qué
> está migrado y qué falta: [`LEGACY_TABLES.md`](LEGACY_TABLES.md). Este
> documento sigue siendo válido como explicación del *por qué* del diseño.

Este diseño simula **el sistema operativo real de una empresa** (CRM, ventas, catálogo
e inventario, facturación, soporte, marketing, encuestas) y, sobre él, las consultas
que producirían los 13 datasets que hoy existen como CSV en `projects/*/data/`. Sigue el
patrón *medallion* (Databricks/dbt):

```
   BRONZE                       SILVER                          GOLD
   sistemas fuente reales   →   bodega operativa conformada  →  los 13 CSV del portafolio
   (CRM, POS, ERP, ads...)      dims + hechos + features         (VIEW, agregación real)
   sin transformar              + salidas de modelo
```

Este documento describe el diseño original, que era **solo estructura** (DDL).
Los DDL originales (`schema/01_bronze.sql` a `04_gold.sql`) **ya se migraron a dbt y se
eliminaron**; siguen en el historial de git (ver [`LEGACY_TABLES.md`](LEGACY_TABLES.md)).
Su contraparte ejecutable: bronze en `warehouse/seeds/`, silver en `warehouse/models/marts/`,
meta en `warehouse/models/meta/` y gold en `warehouse/models/gold/`.

## El cambio de enfoque respecto a la primera versión

La primera versión de este diseño trataba cada CSV de `projects/*/data/` como si ya
fuera un dato limpio (silver) y montaba encima un gold casi de pase directo. Es al
revés: **la mayoría de esos CSV ya SON un reporte gold** — `ventas_diarias.csv` es una
agregación por equipo/vendedor/día, `marketing_canales.csv` trae CAC y LTV ya
calculados, `transacciones.csv` (05) es RFM a medio calcular. Lo que faltaba diseñar era
el sistema operativo real *detrás* de esos reportes: el CRM, el pedido, la factura, el
ticket de soporte — de donde salen, agregando y calculando, los 13 datasets.

Dos proyectos son la excepción y se quedan igual: **11** (consolidación de sucursales) y
**13** (auditoría de calidad) son, por diseño, ejercicios de bronze — sus CSV YA son
datos crudos de sistemas fuente, no reportes. Por eso sus tablas bronze
(`pedido_sucursal_cdmx/guadalajara/monterrey`, `crm_cliente`, `producto`, `calendario`,
`factura_linea`) son literalmente el maestro real de la empresa en este diseño.

## Perfil de negocio asumido

No es derivable del código — es una decisión de diseño necesaria para que las 13 piezas
encajen en un solo negocio: una PyME que vende producto físico por equipos comerciales,
sucursales y e-commerce (proyectos 01, 05, 06, 07, 09, 10, 11), y que además tiene una
cartera de clientes con plan de servicio recurrente mensual/anual con soporte y uso
medible (proyecto 04, churn). Antes documentado en la cabecera de `01_bronze.sql`, ya eliminado.

## Por qué bronze sigue siendo casi todo TEXT

Zona de aterrizaje: nunca debe fallar al cargar sin importar qué tan sucio venga el
sistema fuente. `bronze.crm_cliente`, `bronze.producto`, `bronze.calendario` y
`bronze.factura_linea` conservan la suciedad real que ya modelaban los proyectos 11 y
13 (fechas mixtas, catálogos sin normalizar, nulos, referencias rotas, `total ≠
cantidad × precio`) — porque esa ES la fuente real de la que sale el score de calidad
del proyecto 13.

## Silver tiene dos tipos de tabla

1. **Hechos operativos** — traducción tipada y deduplicada de bronze: `fact_pedido`,
   `fact_factura`, `fact_ticket_soporte`, `fact_oportunidad_evento`... Nadie calculó
   nada todavía, solo se limpió.
2. **Hechos enriquecidos** — features y salidas de modelo, calculadas a partir de los
   hechos operativos: `fact_cliente_features_churn` (agrega facturación + soporte +
   actividad + cancelaciones), `fact_cliente_rfm_score`, `fact_producto_elasticidad`,
   `fact_producto_forecast`, `fact_canal_roi`. La regresión/RFM/forecast en sí corre en
   un job de Python fuera de SQL; su salida se conforma aquí para que gold solo tenga
   que leer y dar formato.

## Un solo hecho, seis reportes

`silver.fact_pedido` (línea de pedido del canal gestionado) es el hecho central: 01 lo
agrega por equipo/vendedor/día, 05 por cliente/día, 06 por producto/semana, 07 por
SKU/día, 09 lo usa para ticket promedio y margen por canal, y 10 por mes/región/
categoría. No son 6 fuentes distintas — es la misma venta, cortada 6 formas.

## El motor de calidad de datos (`meta`) audita el maestro real

`meta.dq_regla` / `dq_resultado_regla` / `dq_scorecard_tabla` / `dq_plan_remediacion`
generalizan el catálogo de 33 reglas del proyecto 13 para correr contra cualquier tabla
bronze o silver. Hoy evalúan `bronze.crm_cliente`, `bronze.producto`,
`bronze.calendario` y `bronze.factura_linea` — el mismo maestro que usan 04, 10 y 13,
no una copia aislada.

## Mapa completo: bronze → silver → gold, por proyecto

| # Proyecto | Bronze (sistema fuente) | Silver (hechos clave) | Gold (reproduce el CSV) |
|---|---|---|---|
| 01 Ventas por equipo | `pedido_linea`, `crm_equipo`, `crm_vendedor`, `crm_meta_venta` | `fact_pedido` (agregado), `fact_meta_venta` | `rpt_01_ventas_diarias`, `rpt_01_metas_mensuales` |
| 02 Funnel de fuga | `crm_oportunidad_evento` | `fact_oportunidad_evento` (agregado por semana) | `rpt_02_funnel_semanal` |
| 03 Scorecard ejecutivo | `kpi_captura_manual` + todos los hechos que alimentan cada KPI | `fact_kpi_manual`, `fact_kpi_meta` + KPIs calculados (ingresos, nuevos clientes, NPS...) | `rpt_03_kpi_historico`, `rpt_03_scorecard` |
| 04 Predicción de churn | `crm_cliente`, `suscripcion_cargo`, `ticket_soporte`, `evento_actividad`, `cancelacion` | `fact_cliente_features_churn` → `fact_cliente_churn_score` | `rpt_04_clientes` |
| 05 Segmentación RFM | `pedido_linea`, `crm_cliente` | `fact_pedido` (agregado por cliente/día) → `fact_cliente_rfm_score` | `rpt_05_transacciones` |
| 06 Elasticidad de precios | `pedido_linea`, `producto` | `fact_pedido` (agregado por producto/semana) → `fact_producto_elasticidad` | `rpt_06_precio_demanda` |
| 07 Forecast de inventario | `pedido_linea`, `producto`, `inventario_snapshot` | `fact_pedido` (agregado por SKU/día), `fact_inventario_snapshot` → `fact_producto_forecast` | `rpt_07_demanda_diaria`, `rpt_07_inventario_actual` |
| 08 Flujo de caja / cartera | `factura_linea`, `pago` | `fact_factura`, `fact_pago` → `fact_cliente_pago_segmento` | `rpt_08_facturas` |
| 09 ROI de marketing | `marketing_gasto`, `crm_cliente.canal_adquisicion`, `pedido_linea`, `cancelacion` | `fact_marketing_gasto` → `fact_canal_roi` | `rpt_09_marketing_canales` |
| 10 Reporte ejecutivo | `pedido_linea`, `crm_cliente`, `producto` | `fact_pedido` (agregado por mes/región/categoría) → `fact_subcategoria_tendencia` | `rpt_10_transacciones` |
| 11 Fuente única | `pedido_sucursal_cdmx`, `_guadalajara`, `_monterrey` (bronze, sin cambios) | `fact_venta_sucursal`, `venta_sucursal_pendiente_revision` | `rpt_11_fuente_unica`, `rpt_11_revision_manual_monto_faltante` |
| 12 NPS y causa raíz | `encuesta_nps` | `fact_encuesta_nps` | `rpt_12_encuestas_nps` |
| 13 Data health check | `crm_cliente`, `producto`, `calendario`, `factura_linea` (bronze, sin cambios) | — (audita bronze directo) | `rpt_13_scorecard_calidad_tablas`, `rpt_13_reglas_validacion`, `rpt_13_plan_remediacion` (via `meta.dq_*`) |

`silver.dim_fecha` (limpio a partir de `bronze.calendario`) es la única dimensión que
**todos** los demás hechos con fecha referencian.

## Qué falta a propósito (fuera de alcance de esta fase)

- Sin datos: no hay `INSERT`, seeds, ni carga de los CSV reales.
- Sin ETL/ML: no hay job Python real que calcule churn/RFM/elasticidad/forecast — las
  tablas de salida (`fact_*_score`, `fact_*_forecast`, `fact_*_elasticidad`) están
  definidas, pero quién las llena queda fuera de este alcance.
- Sin motor elegido: el DDL usa sintaxis PostgreSQL (`SERIAL`, `NUMERIC`, schemas,
  `FILTER`, CTEs) por ser la más legible como referencia; es portable a
  Snowflake/BigQuery/DuckDB con cambios menores de tipos.

## Formatear el schema

El formatter alinea los tipos de datos dentro de cada bloque `CREATE TABLE` y
preserva comentarios, defaults y el resto del SQL:

```bash
python3 database/format_schema.py
```

Para usarlo como validación sin modificar archivos:

```bash
python3 database/format_schema.py --check
```
