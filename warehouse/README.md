# `warehouse/` — Analytics Engineering con dbt + DuckDB

Este es el warehouse propuesto en [`database/README.md`](../database/README.md),
construido de verdad: **dbt + DuckDB**, sin servidor que pagar. DuckDB corre
como un archivo local (o temporal en CI); todo el pipeline — seeds,
staging, marts, tests, docs — se ejecuta igual en tu laptop que en un
runner gratuito de GitHub Actions.

**Este proyecto es la única fuente de verdad ejecutable.** El diseño original en DDL
(`database/schema/`) se migró aquí capa por capa y ya se eliminó; el estado de cada tabla está en
[`database/LEGACY_TABLES.md`](../database/LEGACY_TABLES.md). **Bronze (21/21),
silver (35/35), meta (5/5) y gold (19/19) ya están migrados y verificados**.

## Bronze: 21 seeds, uno por tabla del DDL

Cada tabla `bronze.<t>` del diseño original es el seed `<t>.csv`, en schema
`raw`, declarado como `source` de dbt. Todos aterrizan como `varchar`
(macro `duckdb__create_csv_table`): bronze no interpreta nada, tipar es
trabajo de staging.

| Sistema fuente (source dbt) | Seeds |
|---|---|
| `crm` | `crm_cliente`, `crm_equipo`, `crm_vendedor`, `crm_meta_venta`, `crm_oportunidad_evento`, `cancelacion` |
| `erp` | `producto`, `calendario`, `factura_linea`, `pago`, `suscripcion_cargo` |
| `pos` | `pedido_linea` |
| `sucursales` | `pedido_sucursal_cdmx`, `pedido_sucursal_guadalajara`, `pedido_sucursal_monterrey` |
| `wms` | `inventario_snapshot` |
| `helpdesk` | `ticket_soporte` |
| `producto_analytics` | `evento_actividad` |
| `ads` | `marketing_gasto` |
| `encuestas` | `encuesta_nps` |
| `scorecard` | `kpi_captura_manual` |

De dónde sale cada dato:

- **Idénticos a `projects/`** (4): `calendario` (de `projects/13`) y las 3
  sucursales (de `projects/11`) — el CSV es byte a byte el original.
- **Aumentados** (3): `crm_cliente`, `producto` y `factura_linea` parten de
  `projects/13` y **conservan todas las filas y columnas originales, con su
  suciedad** (nulos, duplicados, fechas mixtas, precios negativos, referencias
  rotas), más las columnas que el DDL definía y el CSV no tenía.
- **Generados** (14): el resto, con `seeds/generators/generate_bronze.py`
  (semilla fija; cada tabla tiene su propio generador aleatorio, así que
  cambiar una no mueve las demás). Referencian los clientes, productos y
  vendedores reales de las tablas anteriores.
- **Sin equivalente legacy** (1): `scorecard/kpi_meta.csv`, las metas por KPI.
  Cierra un hueco del diseño original: `silver.fact_kpi_meta` no tenía tabla de origen.

## Cómo correrlo

```bash
cd warehouse
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DBT_PROFILES_DIR=profiles

dbt deps          # instala dbt_utils
dbt seed          # carga los 22 CSV a DuckDB (schema "raw")
dbt run           # staging -> intermediate -> marts -> meta -> gold (87 modelos)
dbt test          # 430 tests (sources, llaves, integridad, contratos, genéricos, custom y singulares)
dbt docs generate && dbt docs serve   # catálogo + lineage DAG en localhost

```

**Importante: `dbt seed` va aparte de `dbt run`/`dbt test`, no dentro de un
solo `dbt build`.** dbt no sabe que un seed llena la tabla que un modelo
referencia vía `source()` — esa conexión existe en la vida real porque una
herramienta de EL (Fivetran, Airbyte...) carga la fuente por fuera de dbt,
así que dbt tampoco la infiere aquí. En una base nueva, `dbt build` puede
intentar correr un modelo antes de que su seed haya cargado. Dos comandos
en orden lo resuelve siempre.

Para regenerar los seeds sintéticos desde cero (no hace falta, ya están
commiteados, pero es reproducible):

```bash
python3 seeds/generators/generate_bronze.py
```

## Estructura

```
warehouse/
├── seeds/              22 CSV por sistema fuente (crm/, erp/, pos/, sucursales/, wms/...)
│   └── generators/      generate_bronze.py (+ generate_pedido_linea.py, que este invoca)
├── models/              87 modelos
│   ├── staging/         22 modelos stg_<source>__<entidad> — 1:1 con cada fuente; los 10
│   │                    sources de bronze se declaran aquí (_*__sources.yml, con tests)
│   ├── intermediate/    6 modelos: depuración y reglas de negocio (int_producto_depurado,
│   │                    int_factura_linea_validada, dedup de sucursales, pedidos enriquecidos,
│   │                    métricas de canal por mes)
│   ├── marts/           silver: 11 dims + 24 hechos
│       ├── core/        11 dimensiones: dim_fecha, dim_cliente, dim_producto, dim_canal...
│       ├── ventas/      fct_pedido (incremental), RFM, elasticidad, tendencia
│       ├── finanzas/    facturas, pagos, cargos de suscripción, segmento de pago
│       ├── cliente/     soporte, actividad, cancelación, NPS, features y score de churn
│       ├── marketing/   gasto de pauta y ROI por canal
│       ├── inventario/  snapshot de inventario y forecast de demanda
│       ├── scorecard/   KPIs manuales y metas
│       └── sucursales/  ventas de sucursal y cola de revisión
│   ├── meta/            5 modelos: motor de calidad de datos (batch, reglas, resultados, scorecard, plan)
│   └── gold/            19 rpt_*, en una carpeta por dashboard (01_ventas_por_equipo ... 13_data_health)
├── macros/              11 macros Jinja reutilizables (ver abajo)
├── scripts/             verify_dashboard_coverage.py: cada dashboard tiene su reporte gold
├── tests/               6 tests singulares + 1 test genérico custom
└── snapshots/, analyses/  (vacíos por ahora)
```

## Qué demuestra cada pieza

| Pieza | Dónde |
|---|---|
| **sources** | `models/staging/*/_*__sources.yml` — 10 sistemas fuente, 21 tablas, cada una anclada a su tabla legacy con `meta.legacy_table`. Los sistemas limpios llevan tests de llave única, `accepted_values` e integridad referencial entre sources. |
| **staging** | `stg_<source>__<entidad>.sql` — 22 modelos, materializados como view |
| **intermediate** | `models/intermediate/` — depuración de producto (`QUALIFY`, ventana para recuperar categorías), validación de facturas con motivo de rechazo, dedup de sucursales |
| **marts** | `models/marts/core` (11 dimensiones) + hechos por dominio (24). Los hechos "enriquecidos" (churn, RFM, elasticidad, forecast, ROI, tendencia) se calculan en SQL puro |
| **contratos** | Los 19 `rpt_*` de gold llevan `contract: enforced`: dbt no los materializa si cambia una columna o un tipo respecto al CSV del dashboard |
| **meta** | `models/meta/` — motor de calidad persistido: cada `dbt run` es un batch (`invocation_id`), evalúa 33 reglas sobre bronze y guarda resultado, scorecard y plan de remediación. Reproduce exactamente las salidas de `projects/13` |
| **incremental** | `fct_pedido.sql` — watermark por fecha, `unique_key`, `delete+insert`. Verificado a mano: correr dos veces sin datos nuevos no reprocesa nada; agregar un día nuevo solo inserta esas filas. |
| **tests** | 430: PK (`unique`/`not_null`) y FK (`relationships`) de las 35 tablas de silver y las 5 de meta, valores aceptados y rangos, contratos de los 19 reportes gold, 1 genérico custom (`total_matches_lineas`) y 6 singulares (reconciliación entre marts, líneas que no se pierden, fechas futuras, regla del NPS, reglas de calidad evaluadas en cada batch) |
| **schema.yml** | Uno por dominio, no un YAML monolítico |
| **documentación** | Descripciones inline + bloques `{% docs %}` largos (`dim_cliente_dedupe`) |
| **lineage/DAG** | `dbt docs generate` + `dbt docs serve` — el grafo interactivo real |
| **macros** | `duckdb__create_csv_table` (todo seed aterriza como TEXT), `generate_schema_name`, `parse_messy_date` (fechas mixtas; la ambigüedad DD/MM vs MM/DD está documentada, no oculta), `cast_messy_amount`, `quadrant_segment` (un macro en vez de 4 `CASE WHEN`), `nombre_mes_es`/`nombre_dia_es`, `canonical_case` (normaliza catálogos), `mes_key`, `dq_reglas` (las 33 reglas de calidad como datos, no como 33 tests sueltos) y `cerrar_batch` (hook `on-run-end`) |
| **Jinja** | `{% for %}` sobre la lista de formatos de fecha, `{% if is_incremental() %}`, `ref()`/`source()` en todo, `{{ var(...) }}` |
| **SQL** | CTEs en cascada, `ROW_NUMBER()`/`QUALIFY`, `PERCENT_RANK()`, ventanas móviles, regresión nativa (`regr_slope`/`regr_r2`), agregaciones con `FILTER` |
| **Git** | rama por feature → PR → CI en verde → merge a main |
| **CI/CD** | `dbt_ci.yml`: seed → run → test → cobertura de dashboards en cada PR, DuckDB efímero, sin credenciales. `dbt_docs.yml`: genera el sitio de docs como artifact en cada push a main |

## Gold: un reporte por cada dataset de dashboard

Cada CSV que consume (o produce) un dashboard de `projects/` tiene un modelo
`rpt_*` en `models/gold/`, con **las mismas columnas, en el mismo orden y del
mismo tipo** que el CSV (contrato de dbt). Casi toda la lógica vive en
silver; gold agrega y da formato. Los que comparan periodos usan semanas o
meses **completos** al corte de `fecha_referencia`.

| # | Dashboard | Reportes gold |
|---|---|---|
| 01 | Sales performance | `rpt_ventas_diarias`, `rpt_metas_mensuales` |
| 02 | Funnel de ventas | `rpt_funnel_semanal` |
| 03 | Scorecard metas vs resultados | `rpt_kpi_historico`, `rpt_scorecard` |
| 04 | Predicción de churn | `rpt_clientes_churn` |
| 05 | Segmentación RFM | `rpt_transacciones` |
| 06 | Elasticidad de precios | `rpt_precio_demanda` |
| 07 | Forecast de demanda e inventario | `rpt_demanda_diaria`, `rpt_inventario_actual` |
| 08 | Flujo de caja y cartera | `rpt_facturas` |
| 09 | ROI de marketing por canal | `rpt_marketing_canales` |
| 10 | Reporte ejecutivo mensual | `rpt_transacciones_ejecutivo` |
| 11 | Consolidación a una fuente de verdad | `rpt_fuente_unica`, `rpt_revision_manual_monto_faltante` |
| 12 | NPS y causa raíz | `rpt_encuestas_nps` |
| 13 | Data health check | `rpt_scorecard_calidad_tablas`, `rpt_reglas_validacion`, `rpt_plan_remediacion` |

Para comprobar que la cobertura sigue completa (tras `dbt run`, con el manifest generado):

```bash
python scripts/verify_dashboard_coverage.py --db xia_warehouse.duckdb          # forma: columnas, tipos, filas, contrato
python scripts/verify_dashboard_coverage.py --e2e --python /ruta/con/pandas    # además, construye cada dashboard con datos de gold
```

La prueba de extremo a extremo copia el repo a un directorio temporal, exporta
cada reporte gold como el CSV del proyecto y corre su `run_analysis.py`; nunca
toca `projects/`. Hoy se construyen con datos del warehouse los dashboards 01–06,
09 y 12. **07, 08 y 10 no**, porque su `run_analysis.py` trae supuestos fijos del
dataset autónomo del proyecto (paleta para 5 categorías, `TODAY` fijo, catálogo de
4 categorías); no son fallas del reporte gold y están listados en el script.

## Los 3 hallazgos reales que los tests atrapan (a propósito)

`dbt test` termina sin errores pero con **3 warnings esperados** — el mismo
hallazgo que audita `projects/13-data-health-check`, ahora vivo como test:

- 158 líneas de `factura_linea` con `cliente_id` que ya no existe en el catálogo.
- 124 líneas de `factura_linea` con `sku` descontinuado.
- 424 líneas de `factura_linea` donde `total ≠ cantidad × precio_unitario`.

Están en `severity: warn`, no `error`, porque es un hallazgo real y esperado de
la fuente, no un bug del pipeline: no se bloquea un deploy por una regla de
calidad ya conocida, se le da seguimiento.

## Qué sigue

Todas las capas del diseño legacy están migradas. Quedan hallazgos abiertos que
piden decisión (moneda de las facturas, 22% de facturas rechazadas, churn como proxy): están
en [`database/LEGACY_TABLES.md`](../database/LEGACY_TABLES.md), junto con el modelo dbt
correspondiente a cada objeto del diseño legacy.
