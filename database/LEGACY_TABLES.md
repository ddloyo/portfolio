# Legacy tables — inventario de migración a dbt

**Decisión:** la única fuente de verdad ejecutable del warehouse es el proyecto
dbt de [`warehouse/`](../warehouse/). Los archivos de `database/schema/*.sql`
son el **diseño original en DDL**: quedan como referencia mientras se migra y
se **borran cuando cada capa esté migrada y verificada** — no antes.

Este documento identifica qué es legacy, a qué se migró cada objeto y qué
falta. La migración es **1:1**: cada tabla del DDL tiene su contraparte en
dbt, y el estado de cada una se puede comprobar (ver [Verificación](#verificación)).

## Archivos legacy

| Archivo | Objetos | Contraparte en dbt | Estado | Se borra cuando… |
|---|---|---|---|---|
| `schema/01_bronze.sql` | 21 tablas | `warehouse/seeds/` + `sources` (`models/staging/*/_*__sources.yml`) | **Migrado, verificado y eliminado** | — (recuperable: `git show 2e221a8:database/schema/01_bronze.sql`) |
| `schema/02_silver.sql` | 35 tablas | `marts/core` (dimensiones) y `marts/<dominio>` (hechos) | **Migrado, verificado y eliminado** | — (recuperable: `git show 2e221a8:database/schema/02_silver.sql`) |
| `schema/03_meta_dq.sql` | 5 tablas | tests de dbt + `store_failures` / modelo sobre `run_results.json` | Pendiente | el motor de calidad exista en dbt |
| `schema/04_gold.sql` | 19 vistas | `marts/*/rpt_*` | En curso (7 migradas, 12 pendientes) | las 19 estén migradas |

Otros documentos que describen el diseño legacy y habrá que reescribir o retirar
al final: `database/README.md`, `database/architecture.html` (y su artifact publicado).

| Capa | Migradas | Parciales | Pendientes | Total |
|---|---|---|---|---|
| Bronze | 21 | 0 | 0 | 21 |
| Silver | 35 | 0 | 0 | 35 |
| Meta | 0 | 0 | 5 | 5 |
| Gold | 7 | 0 | 12 | 19 |

---

## Bronze — 21/21 migradas

Cada tabla `bronze.<t>` es ahora el seed `<t>.csv` (schema `raw` en DuckDB),
declarado como `source` de dbt con `meta.legacy_table: bronze.<t>`. Todas
aterrizan como `varchar` (macro `duckdb__create_csv_table`), igual que el
DDL: tipar es trabajo de staging.

**Fidelidad** — *idéntica*: el CSV es byte a byte el original de `projects/`;
*aumentada*: conserva todas las filas y columnas originales sin alterar un
valor (con su suciedad) y agrega las columnas que el DDL definía y el CSV
original no tenía; *generada*: dato sintético nuevo, reproducible
(`seeds/generators/generate_bronze.py`, semilla fija).

| Tabla legacy | Seed (`warehouse/seeds/`) | Source dbt | Fidelidad |
|---|---|---|---|
| `bronze.crm_cliente` | `crm/crm_cliente.csv` | `crm` | aumentada (de `projects/13`: + region, tipo_contrato, plan, canal_adquisicion) |
| `bronze.crm_equipo` | `crm/crm_equipo.csv` | `crm` | generada |
| `bronze.crm_vendedor` | `crm/crm_vendedor.csv` | `crm` | generada |
| `bronze.crm_meta_venta` | `crm/crm_meta_venta.csv` | `crm` | generada (valores de `projects/01/metas_mensuales.csv`) |
| `bronze.crm_oportunidad_evento` | `crm/crm_oportunidad_evento.csv` | `crm` | generada |
| `bronze.cancelacion` | `crm/cancelacion.csv` | `crm` | generada |
| `bronze.pedido_linea` | `pos/pedido_linea.csv` | `pos` | generada (sin `sucursal`, ver divergencias) |
| `bronze.pedido_sucursal_cdmx` | `sucursales/pedido_sucursal_cdmx.csv` | `sucursales` | idéntica a `projects/11` |
| `bronze.pedido_sucursal_guadalajara` | `sucursales/pedido_sucursal_guadalajara.csv` | `sucursales` | idéntica a `projects/11` |
| `bronze.pedido_sucursal_monterrey` | `sucursales/pedido_sucursal_monterrey.csv` | `sucursales` | idéntica a `projects/11` |
| `bronze.producto` | `erp/producto.csv` | `erp` | aumentada (de `projects/13`: + subcategoria) |
| `bronze.inventario_snapshot` | `wms/inventario_snapshot.csv` | `wms` | generada |
| `bronze.factura_linea` | `erp/factura_linea.csv` | `erp` | aumentada (de `projects/13`: + fecha_vencimiento) |
| `bronze.pago` | `erp/pago.csv` | `erp` | generada (a partir de `factura_linea`) |
| `bronze.suscripcion_cargo` | `erp/suscripcion_cargo.csv` | `erp` | generada |
| `bronze.ticket_soporte` | `helpdesk/ticket_soporte.csv` | `helpdesk` | generada |
| `bronze.evento_actividad` | `producto_analytics/evento_actividad.csv` | `producto_analytics` | generada |
| `bronze.marketing_gasto` | `ads/marketing_gasto.csv` | `ads` | generada |
| `bronze.encuesta_nps` | `encuestas/encuesta_nps.csv` | `encuestas` | generada |
| `bronze.calendario` | `erp/calendario.csv` | `erp` | idéntica a `projects/13` |
| `bronze.kpi_captura_manual` | `scorecard/kpi_captura_manual.csv` | `scorecard` | generada |

### `_source_system` del DDL → source de dbt

| `_source_system` legacy | Source dbt |
|---|---|
| `crm` | `crm` |
| `pos_crm` | `pos` |
| `export_sucursal_cdmx` / `_guadalajara` / `_monterrey` | `sucursales` |
| `erp_catalogo`, `erp_facturacion`, `erp_calendario` | `erp` (los tres son el mismo ERP) |
| `wms` | `wms` |
| `helpdesk` | `helpdesk` |
| `producto_analytics` | `producto_analytics` |
| `ads_platforms` | `ads` |
| `encuestas_voc` | `encuestas` |
| `scorecard_manual` | `scorecard` |

### Divergencias deliberadas respecto al DDL

Todo lo que no es 1:1 está aquí (el script de verificación, ya eliminado, las
tenía codificadas y fallaba con cualquier otra).

1. **Columnas de linaje** (`_source_system`, `_batch_id`, `_loaded_at`) no son
   columnas de los seeds. El linaje lo da dbt: el DAG, el `source` y
   `meta.legacy_table`. `_batch_id` / `meta.batch_ingesta` se resuelve con la
   capa meta (pendiente).
2. **`pedido_linea.sucursal` no se migra.** El DDL la describía como "venta
   atendida por un vendedor/equipo", pero las sucursales son justamente el
   canal *no integrado* al sistema de ventas gestionado (`pedido_sucursal_*`),
   y ningún reporte la usa. Es reversible: agregarla es una columna más en
   el generador.
3. **`pedido_sucursal_*`: el valor de la columna `fuente`** que emiten
   staging y `rpt_fuente_unica` cambió de `raw_export_cdmx.csv` a
   `pedido_sucursal_cdmx.csv` (y análogos), porque describe el archivo y este
   se renombró. Es el único valor de salida de un mart que cambió; los
   montos, conteos y checksums de los marts son idénticos a los previos a la migración.
4. **Se retiró el seed `ventas/equipo_vendedor.csv`**, que no existía en el DDL
   (era una fusión de `crm_equipo` + `crm_vendedor` hecha para la primera
   versión de dbt). `dim_vendedor` ahora sale de `crm_vendedor` + `crm_equipo`.
5. **Modelos de staging renombrados** al estándar `stg_<source>__<entidad>`:
   `stg_crm__clientes` → `stg_crm__cliente`; `stg_crm__productos` →
   `stg_erp__producto`; `stg_crm__calendario` → `stg_erp__calendario`;
   `stg_crm__facturas` → `stg_erp__factura_linea`; `stg_ventas__pedido_linea`
   → `stg_pos__pedido_linea`.

### Seeds de dbt sin tabla legacy

| Seed | Por qué existe |
|---|---|
| `scorecard/kpi_meta.csv` | Meta vigente por KPI (insumo de planeación). **Cierra un hueco del diseño legacy**: `silver.fact_kpi_meta` no tenía tabla bronze de origen (`kpi_captura_manual` solo trae el resultado, no la meta). Valores ilustrativos. |

Se retiró `cliente/clientes_churn.csv` (de `projects/04`), que era un feature set de
churn ya calculado y no un sistema fuente: las features ahora se calculan desde
bronze en `fct_cliente_features_churn` (ver Silver).

---|---|---|
| `cliente/clientes_churn.csv` (de `projects/04`) | Es un dataset de features de churn ya calculado (gold), no un sistema fuente. Alimenta el dominio churn actual. | Al migrar `fact_cliente_features_churn`: las features se calcularán desde `suscripcion_cargo`, `ticket_soporte`, `evento_actividad`, `cancelacion` y `crm_cliente`, que ya están en bronze. |

---

## Silver — 35/35 migradas

Cada tabla `silver.<t>` es ahora un modelo dbt: dimensiones en `marts/core`,
hechos en `marts/<dominio>` (regla de nombre: `fact_X` → `fct_X`). Se verifica
contra el DDL con un script que ya se eliminó (ver [Verificación](#verificación)).

| Tabla legacy | Modelo dbt | Nota |
|---|---|---|
| `silver.dim_fecha` | `marts/core/dim_fecha` | Por `date_spine` (2024-01-01 a 2026-09-19), no desde `bronze.calendario` (solo cubre 2024–2025). `es_feriado` siempre `false`: la columna de origen está 100% vacía. |
| `silver.dim_semana` | `marts/core/dim_semana` | `semana_key` = año ISO × 100 + semana |
| `silver.dim_mes` | `marts/core/dim_mes` | `mes_key` = año × 100 + mes |
| `silver.dim_region` | `marts/core/dim_region` | |
| `silver.dim_cliente` | `marts/core/dim_cliente` | Dedup + normalización de ciudad y segmento |
| `silver.dim_producto` | `marts/core/dim_producto` | Sobre `int_producto_depurado` (ver divergencias) |
| `silver.dim_sucursal` | `marts/core/dim_sucursal` | `nombre_origen_raw` guarda las grafías crudas |
| `silver.dim_equipo` | `marts/core/dim_equipo` | |
| `silver.dim_vendedor` | `marts/core/dim_vendedor` | Con `equipo_id` y `equipo` denormalizados |
| `silver.dim_canal` | `marts/core/dim_canal` | Une canal de venta y de marketing |
| `silver.dim_kpi` | `marts/core/dim_kpi` | Manuales desde bronze + 3 derivables declarados en el modelo |
| `silver.fact_pedido` | `marts/ventas/fct_pedido` | Incremental. Renombrada desde `fct_pedidos`. |
| `silver.fact_venta_sucursal` | `marts/sucursales/fct_venta_sucursal` | |
| `silver.venta_sucursal_pendiente_revision` | `marts/sucursales/fct_venta_sucursal_pendiente_revision` | |
| `silver.fact_meta_venta` | `marts/ventas/fct_meta_venta` | |
| `silver.fact_oportunidad_evento` | `marts/ventas/fct_oportunidad_evento` | |
| `silver.fact_factura` | `marts/finanzas/fct_factura` | Solo líneas válidas (ver hallazgos) |
| `silver.fact_pago` | `marts/finanzas/fct_pago` | Solo pagos de facturas válidas |
| `silver.fact_suscripcion_cargo` | `marts/finanzas/fct_suscripcion_cargo` | |
| `silver.fact_ticket_soporte` | `marts/cliente/fct_ticket_soporte` | |
| `silver.fact_evento_actividad` | `marts/cliente/fct_evento_actividad` | |
| `silver.fact_cancelacion` | `marts/cliente/fct_cancelacion` | |
| `silver.fact_marketing_gasto` | `marts/marketing/fct_marketing_gasto` | |
| `silver.fact_encuesta_nps` | `marts/cliente/fct_encuesta_nps` | `categoria` derivada de `score` |
| `silver.fact_kpi_manual` | `marts/scorecard/fct_kpi_manual` | |
| `silver.fact_kpi_meta` | `marts/scorecard/fct_kpi_meta` | Sale del seed nuevo `kpi_meta` |
| `silver.fact_inventario_snapshot` | `marts/inventario/fct_inventario_snapshot` | |
| `silver.fact_cliente_features_churn` | `marts/cliente/fct_cliente_features_churn` | Calculada desde bronze; sustituye al seed `clientes_churn` |
| `silver.fact_cliente_churn_score` | `marts/cliente/fct_cliente_churn_score` | **Proxy por reglas, no un modelo entrenado** (ver hallazgos) |
| `silver.fact_cliente_rfm_score` | `marts/ventas/fct_cliente_rfm_score` | |
| `silver.fact_producto_elasticidad` | `marts/ventas/fct_producto_elasticidad` | Regresión log-log real en SQL (`regr_slope`, `regr_r2`) |
| `silver.fact_producto_forecast` | `marts/inventario/fct_producto_forecast` | Tendencia + estacionalidad por día de la semana, con backtest |
| `silver.fact_cliente_pago_segmento` | `marts/finanzas/fct_cliente_pago_segmento` | |
| `silver.fact_canal_roi` | `marts/marketing/fct_canal_roi` | Solo 25 filas: ver hallazgos |
| `silver.fact_subcategoria_tendencia` | `marts/ventas/fct_subcategoria_tendencia` | |

### Divergencias deliberadas respecto al DDL (silver)

El verificador (ya eliminado) las tenía codificadas y fallaba con cualquier otra.

1. **Nombres:** `fact_X` → `fct_X`; `venta_sucursal_pendiente_revision` →
   `fct_venta_sucursal_pendiente_revision`. Columnas: `cliente_id_origen` →
   `cliente_id`, `factura_id_origen` → `factura_id`, `respuesta_id_origen` →
   `respuesta_id` (el sufijo `_origen` era de cuando el diseño conformaba varios
   sistemas fuente; con uno solo es ruido).
2. **Llaves subrogadas:** hash determinista (`dbt_utils.generate_surrogate_key`,
   `varchar`) en vez de `SERIAL`. Con una secuencia, la llave de un cliente cambia
   cuando entran clientes nuevos y los hechos incrementales quedarían apuntando
   a llaves viejas. Excepción: `dim_mes` y `dim_semana` usan enteros legibles
   (`202608`, `202611`), que son igual de estables.
3. **Columnas extra permitidas** sobre el DDL (llaves naturales y denormalizaciones que
   usan los reportes): p.ej. `fct_pedido` (`linea_id`, `cliente_id`, `sku`,
   `categoria`, `costo_total`...), `dim_vendedor` (`vendedor_id`, `equipo`...),
   `dim_fecha` (`semana_iso`...). El verificador solo falla si **falta** una del DDL.
4. **Constraints → tests:** `PRIMARY KEY`, `REFERENCES`, `NOT NULL`, `CHECK` y
   valores válidos del DDL son tests de dbt (`unique`, `relationships`, `not_null`,
   `accepted_range`, `accepted_values`). El verificador comprueba además, directo
   en los datos, que las PK sean únicas y que no haya huérfanos.
5. **Dos modelos intermedios nuevos** que el DDL no tenía y que hacen la limpieza:
   `int_producto_depurado` (un SKU por fila, precios/costos no positivos anulados,
   categorías normalizadas y recuperadas desde la subcategoría en los 6 productos que
   la traían vacía) e `int_factura_linea_validada` (motivo de rechazo por línea).
6. **Normalización de catálogos** en silver: ciudad, segmento y categoría dejan de
   venir como `'MONTERREY'`, `' León '`, `'BELLEZA'`. Efecto en reportes existentes:
   `rpt_ventas_diarias` pasa de 11,144 a 10,766 filas y `rpt_precio_demanda` de
   7,443 a 7,365 (etiquetas que se fusionan), **con los mismos totales**
   (24,824,410.46 y 44,895 unidades).
7. **`dim_fecha` arranca en 2024** (antes 2025), porque las facturas son de 2024.
8. **`dim_kpi`:** los KPIs derivables (Ingresos mensuales, Nuevos clientes, NPS) no
   tienen fuente para su metadata; se declaran en el modelo, con responsables ilustrativos.
9. **`fecha_referencia`** (variable de dbt, `2026-09-18`) es la "fecha de hoy" de los
   hechos enriquecidos, para que las corridas sean reproducibles.

### Hallazgos y decisiones (a tener presente)

- **El modelo de churn anterior tenía la orientación invertida.** La heurística que
  se mergeó en el PR de bronze (`int_cliente_riesgo_churn`) daba *menor* riesgo a
  quienes cancelaron (riesgo medio 30.8 vs. 45.7 sobre los datos de `projects/04`).
  `fct_cliente_churn_score` corrige la orientación (59.6 vs. 43.4 sobre esos mismos
  datos; 80.7 vs. 45.2 sobre el bronze nuevo). Cualquier salida previa de
  `rpt_clientes_churn` (`percentil_riesgo`, `cuadrante_accion`) estaba al revés.
- **`fct_cliente_churn_score` es un proxy**, no la regresión logística del diseño
  original: ordena bien (ver arriba) pero `probabilidad_churn` no es una probabilidad calibrada.
- **22% de las líneas de factura no entran a silver** (791 de 3,595), con motivo
  consultable en `int_factura_linea_validada`: `cliente_inexistente` 266,
  `fecha_invalida` 258, `sku_inexistente` 97, `factura_duplicada` 95,
  `cantidad_o_precio_invalido` 75. Es el hallazgo de calidad de `projects/13`, ahora
  aplicado. ¿Hay que recuperar alguno (p.ej. reparar fechas) en vez de rechazarlo?
- **Moneda — decisión: no se harán conversiones de tipo de cambio.** 421 líneas de
  factura (12%; 338 de ellas válidas) vienen marcadas USD y no hay tipo de cambio.
  Silver no modela moneda (igual que el DDL original) y usa los montos tal como están
  capturados; los totales de facturación y cartera mezclan, por tanto, líneas marcadas
  MXN y USD sin convertir. Se acordó dejarlo así: se puede resolver más adelante y no es
  prioridad del proyecto. Cuando se aborde, el punto de partida es
  `int_factura_linea_validada` (que conserva `moneda` vía `stg_erp__factura_linea`).
- **Elasticidad ≈ 0 con R² ≈ 0.** No es un error: en los datos sintéticos el precio
  varía al azar, sin relación con la demanda, así que no hay elasticidad que encontrar.
  El cálculo (regresión log-log real) sí es correcto.
- **`fct_canal_roi` tiene 25 filas** (2025-01 a 2025-07): el ROI necesita clientes
  nuevos en el mes y las altas de `projects/13` terminan en 2025-07-20. Además, 27
  clientes vienen sin `fecha_alta`.

## Meta — 0 migradas · 5 pendientes

Hoy los tests de dbt hacen la validación (y son el equivalente de
`dq_regla`), pero no se persisten resultados, scorecard ni plan de remediación.

| Tabla legacy | Modelo dbt | Estado |
|---|---|---|
| `meta.batch_ingesta` | — | Pendiente (candidato: `invocation_id` de dbt) |
| `meta.dq_regla` | — | Pendiente |
| `meta.dq_resultado_regla` | — | Pendiente (candidato: `store_failures` / `run_results.json`) |
| `meta.dq_scorecard_tabla` | — | Pendiente |
| `meta.dq_plan_remediacion` | — | Pendiente |

## Gold — 7 migradas · 12 pendientes

| Vista legacy | Modelo dbt | Estado | Nota |
|---|---|---|---|
| `gold.rpt_01_ventas_diarias` | `marts.rpt_ventas_diarias` | Migrada | |
| `gold.rpt_01_metas_mensuales` | — | Pendiente | |
| `gold.rpt_02_funnel_semanal` | — | Pendiente | |
| `gold.rpt_03_kpi_historico` | — | Pendiente | |
| `gold.rpt_03_scorecard` | — | Pendiente | |
| `gold.rpt_04_clientes` | `marts.rpt_clientes_churn` | Migrada | Ahora calculada desde bronze; 200 clientes con plan (antes 1,200 del seed) |
| `gold.rpt_05_transacciones` | `marts.rpt_transacciones` | Migrada | |
| `gold.rpt_06_precio_demanda` | `marts.rpt_precio_demanda` | Migrada | |
| `gold.rpt_07_demanda_diaria` | `marts.rpt_demanda_diaria` | Migrada | |
| `gold.rpt_07_inventario_actual` | — | Pendiente | |
| `gold.rpt_08_facturas` | — | Pendiente | |
| `gold.rpt_09_marketing_canales` | — | Pendiente | |
| `gold.rpt_10_transacciones` | — | Pendiente | |
| `gold.rpt_11_fuente_unica` | `marts.rpt_fuente_unica` | Migrada | |
| `gold.rpt_11_revision_manual_monto_faltante` | `marts.rpt_revision_manual_monto_faltante` | Migrada | |
| `gold.rpt_12_encuestas_nps` | — | Pendiente | |
| `gold.rpt_13_plan_remediacion` | — | Pendiente | Depende de la capa meta |
| `gold.rpt_13_reglas_validacion` | — | Pendiente | Depende de la capa meta |
| `gold.rpt_13_scorecard_calidad_tablas` | — | Pendiente | Depende de la capa meta |

---

## Verificación

Bronze y silver se verificaron automáticamente contra su DDL legacy **antes de
eliminarlo**, con dos scripts temporales (`verify_bronze_migration.py`,
`verify_silver_migration.py`) que se eliminaron junto con los `.sql` que leían.
Quedan en el commit `91e1f91` de la rama `feat/silver`, visible en su PR aunque el
merge sea *squash* (los `.sql` legacy, en cambio, siguen en `main`: commit `2e221a8`).

**Bronze** (21 tablas, 21/21): que existiera el seed, que las columnas coincidieran con
el DDL (menos linaje y las exclusiones documentadas), que estuviera declarada como
`source` con `meta.legacy_table`, que hubiera cargado en DuckDB con las mismas columnas
y filas, y que los datos de `projects/` estuvieran intactos.

**Silver** (35 tablas, 35/35): que existiera el modelo con todas las columnas del DDL
(con los renombres documentados) y filas; que su PK tuviera test `unique`/`not_null` **y**
fuera única en los datos; que cada FK tuviera su test `relationships` **y** no tuviera
huérfanos en los datos.

Ambos se probaron en negativo (corrompiendo datos, quitando columnas, creando huérfanos
y PK duplicadas) y fallaron como debían. Los marts que ya existían se compararon antes y
después de cada fase: en bronze, 14 consultas idénticas; en silver, solo las diferencias
de "Divergencias deliberadas" (6 y 7) y el reemplazo de `rpt_clientes_churn`.

**Hacia adelante**, la integridad la protegen los propios tests de dbt (llaves, integridad
referencial y valores aceptados de bronze y silver), que corren en CI en cada PR.
`03_meta_dq.sql` y `04_gold.sql` siguen como referencia y se borrarán al migrar sus capas.
