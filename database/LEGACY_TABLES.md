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
| `schema/01_bronze.sql` | 21 tablas | `warehouse/seeds/` + `sources` (`models/staging/*/_*__sources.yml`) | **Migrado y verificado** | se apruebe esta fase (junto con `warehouse/scripts/verify_bronze_migration.py`, que depende de él) |
| `schema/02_silver.sql` | 35 tablas | `staging/` → `intermediate/` → `marts/core` | En curso (3 migradas, 7 parciales, 25 pendientes) | las 35 estén migradas |
| `schema/03_meta_dq.sql` | 5 tablas | tests de dbt + `store_failures` / modelo sobre `run_results.json` | Pendiente | el motor de calidad exista en dbt |
| `schema/04_gold.sql` | 19 vistas | `marts/*/rpt_*` | En curso (6 migradas, 1 parcial, 12 pendientes) | las 19 estén migradas |

Otros documentos que describen el diseño legacy y habrá que reescribir o retirar
al final: `database/README.md`, `database/architecture.html` (y su artifact publicado).

| Capa | Migradas | Parciales | Pendientes | Total |
|---|---|---|---|---|
| Bronze | 21 | 0 | 0 | 21 |
| Silver | 3 | 7 | 25 | 35 |
| Meta | 0 | 0 | 5 | 5 |
| Gold | 6 | 1 | 12 | 19 |

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

Todo lo que no es 1:1 está aquí; el script de verificación las tiene
codificadas y falla si aparece cualquier otra.

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

| Seed | Por qué existe | Cuándo se retira |
|---|---|---|
| `cliente/clientes_churn.csv` (de `projects/04`) | Es un dataset de features de churn ya calculado (gold), no un sistema fuente. Alimenta el dominio churn actual. | Al migrar `fact_cliente_features_churn`: las features se calcularán desde `suscripcion_cargo`, `ticket_soporte`, `evento_actividad`, `cancelacion` y `crm_cliente`, que ya están en bronze. |

---

## Silver — 3 migradas · 7 parciales · 25 pendientes

Estado contra los modelos dbt actuales. **Migrada** = existe con la misma
lógica; **parcial** = existe pero con menos columnas/lógica que el DDL;
**pendiente** = no existe todavía.

| Tabla legacy | Modelo dbt | Estado | Nota |
|---|---|---|---|
| `silver.dim_fecha` | `marts.dim_fecha` | Parcial | Se genera por `date_spine`, no desde `bronze.calendario` (solo cubre 2024–2025); sin `es_feriado` |
| `silver.dim_semana` | — | Pendiente | Hoy `semana_iso` es una columna de `dim_fecha` |
| `silver.dim_mes` | — | Pendiente | |
| `silver.dim_region` | — | Pendiente | `region` ya está en bronze (`crm_cliente`) |
| `silver.dim_cliente` | `marts.dim_cliente` | Parcial | Dedup hecha; aún sin region, tipo_contrato, plan, canal_adquisicion |
| `silver.dim_producto` | `marts.dim_producto` | Parcial | Aún sin subcategoria |
| `silver.dim_sucursal` | — | Pendiente | Hoy la sucursal es texto normalizado en staging |
| `silver.dim_equipo` | `marts.dim_vendedor` | Parcial | Aplanada dentro de `dim_vendedor` |
| `silver.dim_vendedor` | `marts.dim_vendedor` | Parcial | Sin llave subrogada |
| `silver.dim_canal` | — | Pendiente | |
| `silver.dim_kpi` | — | Pendiente | |
| `silver.fact_pedido` | `marts.fct_pedidos` | Migrada | Renombrada; incremental; llaves naturales + surrogate propia |
| `silver.fact_venta_sucursal` | `intermediate.int_ventas_sucursal_unificada` | Migrada | |
| `silver.venta_sucursal_pendiente_revision` | `intermediate.int_ventas_sucursal_pendiente` | Migrada | |
| `silver.fact_meta_venta` | — | Pendiente | Bronze migrado (`crm_meta_venta`) |
| `silver.fact_oportunidad_evento` | — | Pendiente | Bronze migrado |
| `silver.fact_factura` | — | Pendiente | Bronze migrado (`factura_linea`) |
| `silver.fact_pago` | — | Pendiente | Bronze migrado |
| `silver.fact_suscripcion_cargo` | — | Pendiente | Bronze migrado |
| `silver.fact_ticket_soporte` | — | Pendiente | Bronze migrado |
| `silver.fact_evento_actividad` | — | Pendiente | Bronze migrado |
| `silver.fact_cancelacion` | — | Pendiente | Bronze migrado |
| `silver.fact_marketing_gasto` | — | Pendiente | Bronze migrado |
| `silver.fact_encuesta_nps` | — | Pendiente | Bronze migrado; `categoria` se deriva de `score` |
| `silver.fact_kpi_manual` | — | Pendiente | Bronze migrado |
| `silver.fact_kpi_meta` | — | Pendiente | **Sin tabla bronze de origen en el diseño legacy** (`kpi_captura_manual` solo trae el resultado, no la meta). Hay que decidir de dónde sale la meta por KPI. |
| `silver.fact_inventario_snapshot` | — | Pendiente | Bronze migrado |
| `silver.fact_cliente_features_churn` | seed `clientes_churn` + `int_cliente_riesgo_churn` | Parcial | Temporal: hoy no se calcula desde bronze (ver seeds sin tabla legacy) |
| `silver.fact_cliente_churn_score` | `intermediate.int_cliente_riesgo_churn` | Parcial | Heurística por reglas, no modelo entrenado |
| `silver.fact_cliente_rfm_score` | — | Pendiente | |
| `silver.fact_producto_elasticidad` | — | Pendiente | |
| `silver.fact_producto_forecast` | — | Pendiente | |
| `silver.fact_cliente_pago_segmento` | — | Pendiente | |
| `silver.fact_canal_roi` | — | Pendiente | |
| `silver.fact_subcategoria_tendencia` | — | Pendiente | |

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

## Gold — 6 migradas · 1 parcial · 12 pendientes

| Vista legacy | Modelo dbt | Estado | Nota |
|---|---|---|---|
| `gold.rpt_01_ventas_diarias` | `marts.rpt_ventas_diarias` | Migrada | |
| `gold.rpt_01_metas_mensuales` | — | Pendiente | |
| `gold.rpt_02_funnel_semanal` | — | Pendiente | |
| `gold.rpt_03_kpi_historico` | — | Pendiente | |
| `gold.rpt_03_scorecard` | — | Pendiente | |
| `gold.rpt_04_clientes` | `marts.rpt_clientes_churn` | Parcial | Hoy sobre el seed `clientes_churn`, no calculado desde bronze |
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

Bronze se verifica automáticamente contra el DDL legacy:

```bash
cd warehouse && source .venv/bin/activate && export DBT_PROFILES_DIR=profiles
dbt seed
python3 scripts/verify_bronze_migration.py
```

Por cada una de las 21 tablas comprueba: que exista el seed, que las columnas
coincidan con el DDL (menos linaje y las exclusiones documentadas arriba),
que esté declarada como `source` con `meta.legacy_table`, que haya cargado en
DuckDB con las mismas columnas y filas, que los datos de `projects/` estén
intactos (idénticos o conservados en las tablas aumentadas) y que aparezca en
este documento. Además falla si hay un seed sin tabla legacy que no esté
documentado en la sección de seeds sin tabla legacy.

Además, los marts existentes se compararon antes y después de migrar bronze
(conteos, sumas y checksums de 14 consultas): idénticos.
