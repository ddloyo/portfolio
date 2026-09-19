# `warehouse/` — Analytics Engineering con dbt + DuckDB

Este es el warehouse propuesto en [`database/README.md`](../database/README.md),
construido de verdad: **dbt + DuckDB**, sin servidor que pagar. DuckDB corre
como un archivo local (o temporal en CI); todo el pipeline — seeds,
staging, marts, tests, docs — se ejecuta igual en tu laptop que en un
runner gratuito de GitHub Actions.

**Este proyecto es la única fuente de verdad ejecutable.** Los `.sql` de
`database/schema/` son el diseño original en DDL y se están migrando aquí capa
por capa; el estado de cada tabla está en
[`database/LEGACY_TABLES.md`](../database/LEGACY_TABLES.md). **Bronze (21/21) y
silver (35/35) ya están migrados 1:1 y verificados**; meta y gold están en curso.

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
dbt run           # staging -> intermediate -> marts (69 modelos)
dbt test          # 326 tests (sources, llaves, integridad, genéricos, custom y singulares)
dbt docs generate && dbt docs serve   # catálogo + lineage DAG en localhost

python3 scripts/verify_bronze_migration.py   # bronze 1:1 contra el DDL legacy (21 tablas)
python3 scripts/verify_silver_migration.py   # silver 1:1 contra el DDL legacy (35 tablas); requiere `dbt test` antes
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
├── models/              69 modelos
│   ├── staging/         22 modelos stg_<source>__<entidad> — 1:1 con cada fuente; los 10
│   │                    sources de bronze se declaran aquí (_*__sources.yml, con tests)
│   ├── intermediate/    5 modelos: depuración y reglas de negocio (int_producto_depurado,
│   │                    int_factura_linea_validada, dedup de sucursales, pedidos enriquecidos)
│   └── marts/           silver (11 dims + 24 hechos) y reportes (7 rpt_*)
│       ├── core/        11 dimensiones: dim_fecha, dim_cliente, dim_producto, dim_canal...
│       ├── ventas/      fct_pedido (incremental), RFM, elasticidad, tendencia + 4 rpt_*
│       ├── finanzas/    facturas, pagos, cargos de suscripción, segmento de pago
│       ├── cliente/     soporte, actividad, cancelación, NPS, features y score de churn
│       ├── marketing/   gasto de pauta y ROI por canal
│       ├── inventario/  snapshot de inventario y forecast de demanda
│       ├── scorecard/   KPIs manuales y metas
│       └── sucursales/  ventas de sucursal, cola de revisión + 2 rpt_*
├── macros/              9 macros Jinja reutilizables (ver abajo)
├── tests/               5 tests singulares + 1 test genérico custom
├── scripts/             verify_{bronze,silver}_migration.py (temporales: se borran con los archivos legacy)
└── snapshots/, analyses/  (vacíos por ahora)
```

## Qué demuestra cada pieza

| Pieza | Dónde |
|---|---|
| **sources** | `models/staging/*/_*__sources.yml` — 10 sistemas fuente, 21 tablas, cada una anclada a su tabla legacy con `meta.legacy_table`. Los sistemas limpios llevan tests de llave única, `accepted_values` e integridad referencial entre sources. |
| **staging** | `stg_<source>__<entidad>.sql` — 22 modelos, materializados como view |
| **intermediate** | `models/intermediate/` — depuración de producto (`QUALIFY`, ventana para recuperar categorías), validación de facturas con motivo de rechazo, dedup de sucursales |
| **marts** | `models/marts/core` (11 dimensiones) + hechos por dominio (24) + `rpt_*` (7). Los hechos "enriquecidos" (churn, RFM, elasticidad, forecast, ROI, tendencia) se calculan en SQL puro |
| **incremental** | `fct_pedido.sql` — watermark por fecha, `unique_key`, `delete+insert`. Verificado a mano: correr dos veces sin datos nuevos no reprocesa nada; agregar un día nuevo solo inserta esas filas. |
| **tests** | 326: PK (`unique`/`not_null`) y FK (`relationships`) de las 35 tablas de silver, valores aceptados y rangos, 1 genérico custom (`total_matches_lineas`) y 5 singulares (reconciliación entre marts, líneas que no se pierden, fechas futuras, regla del NPS) |
| **schema.yml** | Uno por dominio, no un YAML monolítico |
| **documentación** | Descripciones inline + 2 bloques `{% docs %}` largos (`dim_cliente_dedupe`, `un_hecho_seis_reportes`) |
| **lineage/DAG** | `dbt docs generate` + `dbt docs serve` — el grafo interactivo real |
| **macros** | `duckdb__create_csv_table` (todo seed aterriza como TEXT), `generate_schema_name`, `parse_messy_date` (fechas mixtas; la ambigüedad DD/MM vs MM/DD está documentada, no oculta), `cast_messy_amount`, `quadrant_segment` (un macro en vez de 4 `CASE WHEN`), `nombre_mes_es`/`nombre_dia_es`, `canonical_case` (normaliza catálogos), `mes_key` |
| **Jinja** | `{% for %}` sobre la lista de formatos de fecha, `{% if is_incremental() %}`, `ref()`/`source()` en todo, `{{ var(...) }}` |
| **SQL** | CTEs en cascada, `ROW_NUMBER()`/`QUALIFY`, `PERCENT_RANK()`, ventanas móviles, regresión nativa (`regr_slope`/`regr_r2`), agregaciones con `FILTER` |
| **Git** | rama por feature → PR → CI en verde → merge a main |
| **CI/CD** | `dbt_ci.yml`: seed → verificación 1:1 de bronze → run → test → verificación 1:1 de silver en cada PR, DuckDB efímero, sin credenciales. `dbt_docs.yml`: genera el sitio de docs como artifact en cada push a main |

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

Bronze y silver están migrados. Faltan, en este orden: **meta** (motor de calidad de
datos, 5 tablas) y **gold** (19 vistas; 7 migradas). Además, hay hallazgos abiertos que
piden decisión (moneda de las facturas, 22% de facturas rechazadas, churn como proxy): están
en [`database/LEGACY_TABLES.md`](../database/LEGACY_TABLES.md), junto con el modelo dbt
correspondiente a cada objeto del diseño legacy.
