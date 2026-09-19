# Legacy tables — inventario de migración a dbt

**Decisión:** la única fuente de verdad ejecutable del warehouse es el proyecto
dbt de [`warehouse/`](../warehouse/). Los archivos de `database/schema/*.sql`
son el **diseño original en DDL**: se conservaron como referencia mientras se migraba
y se **borraron capa por capa, una vez migrada y verificada** — no antes. Ya no queda
ninguno; siguen en el historial de git (ver la tabla).

Este documento identifica qué es legacy, a qué se migró cada objeto y qué
falta. La migración es **1:1**: cada tabla del DDL tiene su contraparte en
dbt, y el estado de cada una se puede comprobar (ver [Verificación](#verificación)).

## Archivos legacy

| Archivo | Objetos | Contraparte en dbt | Estado | Se borra cuando… |
|---|---|---|---|---|
| `schema/01_bronze.sql` | 21 tablas | `warehouse/seeds/` + `sources` (`models/staging/*/_*__sources.yml`) | **Migrado, verificado y eliminado** | — (recuperable: `git show 2e221a8:database/schema/01_bronze.sql`) |
| `schema/02_silver.sql` | 35 tablas | `marts/core` (dimensiones) y `marts/<dominio>` (hechos) | **Migrado, verificado y eliminado** | — (recuperable: `git show 2e221a8:database/schema/02_silver.sql`) |
| `schema/03_meta_dq.sql` | 5 tablas | `warehouse/models/meta/` | **Migrado, verificado y eliminado** | — (recuperable: `git show c712ad8:database/schema/03_meta_dq.sql`) |
| `schema/04_gold.sql` | 19 vistas | `warehouse/models/gold/` | **Migrado, verificado y eliminado** | — (recuperable: `git show c712ad8:database/schema/04_gold.sql`) |

Con esto termina la migración. Otros documentos que describen el diseño legacy y
habrá que reescribir o retirar: `database/README.md`, `database/architecture.html` (y su artifact publicado).

| Capa | Migradas | Parciales | Pendientes | Total |
|---|---|---|---|---|
| Bronze | 21 | 0 | 0 | 21 |
| Silver | 35 | 0 | 0 | 35 |
| Meta | 5 | 0 | 0 | 5 |
| Gold | 19 | 0 | 0 | 19 |

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
   `meta.legacy_table`. `meta.batch_ingesta` se resuelve en la capa meta
   (el `batch_id` es el `invocation_id` de dbt).
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

## Meta — 5/5 migradas

El motor de calidad del DDL corre ahora como modelos dbt. Cada `dbt run` es un
batch (`batch_id` = `invocation_id` de dbt); las 33 reglas se declaran una sola vez
en el macro `dq_reglas` y de él salen tanto el catálogo (`dq_regla`) como su
evaluación (`dq_resultado_regla`), así que no pueden desalinearse.

| Tabla legacy | Modelo dbt | Materialización | Estado |
|---|---|---|---|
| `meta.batch_ingesta` | `meta.batch_ingesta` | incremental (append) + hook `on-run-end` (`cerrar_batch`) que cierra el batch | Migrada |
| `meta.dq_regla` | `meta.dq_regla` | tabla | Migrada |
| `meta.dq_resultado_regla` | `meta.dq_resultado_regla` | incremental (append) | Migrada |
| `meta.dq_scorecard_tabla` | `meta.dq_scorecard_tabla` | tabla | Migrada |
| `meta.dq_plan_remediacion` | `meta.dq_plan_remediacion` | tabla | Migrada |

### Divergencias deliberadas respecto al DDL (meta)

1. **Llaves:** `batch_id` es el `invocation_id` de dbt (texto, no `UUID` generado por
   la base); `regla_key` es un hash md5 de (tabla, campo, tipo, descripción), estable
   entre corridas, en vez de `SERIAL`; el resto de las llaves son hashes deterministas.
2. **Códigos en inglés** (`completeness`, `critical`/`high`/`medium`/`low`/`info`,
   `good`/`warning`/`serious`/`critical`), como los usa `projects/13`, en vez de los
   `completitud`/`critica`/`sano`/... del comentario del DDL. Las etiquetas (`*_label`)
   sí están en español. Los umbrales de estado son los del proyecto: ≥90 `good`,
   ≥75 `warning`, ≥60 `serious`, el resto `critical`.
3. **Columna extra** en `dq_regla`: `tabla_reporte`, el nombre con el que `projects/13`
   conoce cada tabla (`clientes`, `productos`, `calendario`, `facturas`).
4. **Todas las reglas apuntan a bronze** (`schema_tabla = 'bronze'`): las 4 tablas que
   audita el proyecto 13 son bronze; el DDL preveía también reglas sobre silver, pero no
   hay ninguna definida.
5. **`resuelto` nace en `false`**: el plan se regenera en cada batch; no hay flujo que lo marque.
6. **Historia:** `batch_ingesta` y `dq_resultado_regla` acumulan una fila por corrida.
   `dq_scorecard_tabla` y `dq_plan_remediacion` son tablas que se reconstruyen en cada
   corrida solo con el batch actual: no guardan historia (el DDL sí la preveía). Por eso
   se deben correr junto con `dq_resultado_regla` (un `dbt run` completo lo hace); si se corren
   solos en una corrida nueva salen vacías. En un ambiente nuevo (CI) hay un solo batch.
7. **`store_failures` / `run_results.json` no se usaron**: las reglas se evalúan con SQL
   propio sobre bronze (varchar), que es exactamente lo que hace `projects/13`.

**Verificación contra `projects/13`** (mismos datos crudos): las 33 reglas dan
resultados idénticos (`n_filas`, `n_fallas`, `pct_fallas`, `impacto_pts`); los 4
scorecards coinciden (calendario 98.1, clientes 69.2, facturas 68.1, productos 83.2);
el plan tiene 33 filas idénticas, texto incluido. Lo único que difirió fue el redondeo
(`round_even` = banker's rounding, el de Python, en vez del *half-up* de SQL).

## Gold — 19/19 migradas

**Criterio:** el reporte gold reproduce el CSV que lee el dashboard — mismas columnas,
mismo orden, mismo tipo — no la vista legacy, que solo prometía reproducirlo "en
estructura" y en al menos 3 casos no lo hacía (ver divergencia 2). Cada modelo lleva un contrato
de dbt (`contract: enforced`) copiado del CSV.

| Dashboard | Vista legacy | Modelo dbt (`gold.*`) | Nota |
|---|---|---|---|
| 01 | `rpt_01_ventas_diarias` | `rpt_ventas_diarias` | |
| 01 | `rpt_01_metas_mensuales` | `rpt_metas_mensuales` | |
| 02 | `rpt_02_funnel_semanal` | `rpt_funnel_semanal` | `semana` es un índice consecutivo; el legacy traía `anio` + `semana` |
| 03 | `rpt_03_kpi_historico` | `rpt_kpi_historico` | KPIs derivados (ingresos, nuevos clientes, NPS) + captura manual |
| 03 | `rpt_03_scorecard` | `rpt_scorecard` | Último mes completo de cada KPI contra su meta |
| 04 | `rpt_04_clientes` | `rpt_clientes_churn` | 9 columnas, 200 clientes con plan (antes 1,200 del seed) |
| 05 | `rpt_05_transacciones` | `rpt_transacciones` | |
| 06 | `rpt_06_precio_demanda` | `rpt_precio_demanda` | `semana` es un índice consecutivo; solo semanas completas |
| 07 | `rpt_07_demanda_diaria` | `rpt_demanda_diaria` | Serie continua por SKU, con ceros |
| 07 | `rpt_07_inventario_actual` | `rpt_inventario_actual` | |
| 08 | `rpt_08_facturas` | `rpt_facturas` | Solo `Pagada`/`Pendiente` (ver divergencia 2) |
| 09 | `rpt_09_marketing_canales` | `rpt_marketing_canales` | Sobre `int_canal_mes_metricas` |
| 10 | `rpt_10_transacciones` | `rpt_transacciones_ejecutivo` | Renombrado: chocaba con `rpt_05_transacciones` sin el prefijo numérico |
| 11 | `rpt_11_fuente_unica` | `rpt_fuente_unica` | |
| 11 | `rpt_11_revision_manual_monto_faltante` | `rpt_revision_manual_monto_faltante` | `monto_mxn` siempre `NULL` (la cola es de filas sin monto) |
| 12 | `rpt_12_encuestas_nps` | `rpt_encuestas_nps` | |
| 13 | `rpt_13_scorecard_calidad_tablas` | `rpt_scorecard_calidad_tablas` | Batch más reciente de `meta` |
| 13 | `rpt_13_reglas_validacion` | `rpt_reglas_validacion` | Batch más reciente de `meta` |
| 13 | `rpt_13_plan_remediacion` | `rpt_plan_remediacion` | Batch más reciente de `meta` |

Los modelos viven en `models/gold/<NN_dashboard>/`, un directorio por dashboard.

### Divergencias deliberadas respecto al DDL (gold)

1. **Nombres:** sin el número de dashboard (`rpt_01_ventas_diarias` → `rpt_ventas_diarias`),
   que ahora es el directorio; `rpt_10_transacciones` → `rpt_transacciones_ejecutivo`.
2. **El legacy no coincidía con el CSV en al menos 3 vistas y gold sigue al CSV** (no se pudieron comparar las vistas con CTE): `rpt_02`
   y `rpt_06` traían `anio` + `semana` (el CSV, un índice `semana`); `rpt_08` calculaba un
   tercer estatus `Vencida` que el CSV no tiene y que el dashboard no entiende (lo que
   está vencido lo deduce él con `fecha_vencimiento`). *Este último es un defecto que
   la prueba de extremo a extremo detectó en la primera versión de gold.*
3. **Solo periodos completos** en los reportes que comparan semana con semana o mes
   con mes (02, 03, 06, 09, 10, 12): un periodo a medias parecería una caída. El corte
   es `fecha_referencia`.
4. **`rpt_transacciones_ejecutivo.perfil` es el segmento comercial** del cliente
   (Básico / Estándar / Premium). En el proyecto 10 era un perfil de comportamiento de
   compra que este warehouse no calcula.
5. **`rpt_demanda_diaria` completa los días sin venta con 0** (65,625 filas; antes 16,818
   solo con días con venta), como espera el forecast.
6. **`rpt_clientes_churn` se reduce a las 9 columnas del CSV** (`rpt_04_clientes`); el score
   y el cuadrante siguen en `fct_cliente_churn_score`.
7. **`rpt_facturas`:** 177 de 2,804 facturas tienen pagos por menos de su total
   recalculado (el total capturado traía un descuento manual) y salen `Pendiente`.
8. **Cambios en reportes que ya existían**, el resto quedó idéntico (mismas filas y
   totales): `rpt_precio_demanda` 7,365 → 7,287 filas (solo semanas completas),
   `rpt_demanda_diaria` 16,818 → 65,625 (ceros), `rpt_clientes_churn` pierde columnas.
   `fct_canal_roi` se refactorizó sobre `int_canal_mes_metricas` y da exactamente las
   mismas 25 filas (diferencia de conjuntos vacía en ambos sentidos).

### Cobertura de dashboards

`warehouse/scripts/verify_dashboard_coverage.py` comprueba, por cada CSV de
`projects/*/data/` que alimenta o produce un dashboard, que existe su reporte gold con
las mismas columnas, orden y tipo, con filas y con el contrato forzado. Corre en CI.
Resultado: **13 dashboards, 19 datasets, 0 fallas**. Con `--e2e` además construye cada
dashboard con los datos de gold en un directorio temporal:

- Se construyen: 01, 02, 03, 04, 05, 06, 09 y 12.
- 11 y 13: su CSV es la *salida* del análisis (la entrada son exports crudos), solo se compara la forma.
- **No se construyen: 07, 08 y 10**, por supuestos fijos de su `run_analysis.py`, no por el
  reporte: 07 tiene una paleta para exactamente 5 categorías (el catálogo tiene 8); 08 fija
  `TODAY = 2026-08-31` y narra 8 clientes (las facturas del warehouse terminan en 2025-12);
  10 fija cuatro categorías (`Línea Premium`...) que el catálogo no usa. Arreglarlo es
  cambiar esos scripts o alinear el catálogo: decisión pendiente.

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

**Meta** (5 tablas, 5/5): mismas columnas y orden que el DDL (más `tabla_reporte`);
PK con `unique`/`not_null`, FK (`batch_id`, `regla_key`) con `relationships`, valores
aceptados y rangos como tests; y salidas idénticas a `projects/13` (arriba).

**Gold** (19 vistas, 19/19): el script de cobertura (arriba), probado en negativo
(columna renombrada, tipo cambiado, tabla ausente: falló las tres veces), más la
comparación de `fct_canal_roi` antes y después de su refactor y de los totales de
los reportes que ya existían.

**Hacia adelante**, la integridad la protegen los propios tests de dbt (llaves, integridad
referencial y valores aceptados de bronze y silver), que corren en CI en cada PR.
Meta y gold se verificaron con la comparación descrita arriba (no hay script que
conservar: la de meta fue un chequeo puntual de columnas y tests; la de gold es
`warehouse/scripts/verify_dashboard_coverage.py`, que se queda y corre en CI).
