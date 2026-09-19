-- =============================================================================
-- META LAYER — motor de calidad de datos (data quality control plane)
-- =============================================================================
-- Generaliza el patrón de 13-data-health-check (reglas_validacion.csv,
-- scorecard_calidad_tablas.csv, plan_remediacion.csv) para que aplique a
-- CUALQUIER tabla bronze/silver del warehouse. Las 4 tablas que ese proyecto
-- audita (clientes, productos, calendario, facturas) ya NO son un "mini-ERP"
-- aparte: SON bronze.crm_cliente, bronze.producto, bronze.calendario y
-- bronze.factura_linea — el maestro real de la empresa, con su suciedad real.
-- El motor corre contra ellas (y puede correr contra cualquier otra tabla del
-- warehouse) y alimenta un solo scorecard de calidad para todo el pipeline.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE meta.batch_ingesta (
    batch_id                   UUID PRIMARY KEY,
    iniciado_en                TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizado_en              TIMESTAMPTZ,
    estatus                    TEXT NOT NULL DEFAULT 'en_progreso'   -- en_progreso | ok | fallido
);
COMMENT ON TABLE meta.batch_ingesta IS 'Una fila por corrida de ingesta bronze->silver; referenciada por _batch_id y por meta.dq_*.';

CREATE TABLE meta.dq_regla (
    regla_key                  SERIAL PRIMARY KEY,
    schema_tabla               TEXT NOT NULL,     -- 'bronze' | 'silver'
    tabla                      TEXT NOT NULL,
    campo                      TEXT NOT NULL,
    tipo                       TEXT NOT NULL,   -- completitud | unicidad | validez | integridad_referencial | consistencia
    tipo_label                 TEXT NOT NULL,
    severidad                  TEXT NOT NULL,   -- critica | alta | media | baja | informativa
    severidad_label            TEXT NOT NULL,
    peso_max_pts               NUMERIC(5,2) NOT NULL,   -- 65 / 40 / 20 / 9 / 0
    descripcion                TEXT NOT NULL
);
COMMENT ON TABLE meta.dq_regla IS 'Catálogo de reglas de validación reutilizable, generaliza data/reglas_validacion.csv de 13-data-health-check.';

CREATE TABLE meta.dq_resultado_regla (
    resultado_key              BIGSERIAL PRIMARY KEY,
    regla_key                  INTEGER NOT NULL REFERENCES meta.dq_regla(regla_key),
    batch_id                   UUID NOT NULL REFERENCES meta.batch_ingesta(batch_id),
    fecha_evaluacion           TIMESTAMPTZ NOT NULL DEFAULT now(),
    n_filas                    INTEGER NOT NULL,
    n_fallas                   INTEGER NOT NULL,
    pct_fallas                 NUMERIC(6,2) NOT NULL,
    impacto_pts                NUMERIC(6,2) NOT NULL   -- severidad.peso_max_pts * pct_fallas
);
COMMENT ON TABLE meta.dq_resultado_regla IS 'Resultado de aplicar una regla en una corrida de ingesta. Serie histórica por batch.';

CREATE TABLE meta.dq_scorecard_tabla (
    scorecard_key              BIGSERIAL PRIMARY KEY,
    batch_id                   UUID NOT NULL REFERENCES meta.batch_ingesta(batch_id),
    schema_tabla               TEXT NOT NULL,
    tabla                      TEXT NOT NULL,
    fecha_evaluacion           TIMESTAMPTZ NOT NULL DEFAULT now(),
    filas                      INTEGER NOT NULL,
    score                      NUMERIC(5,2) NOT NULL,   -- 100 - SUM(impacto_pts)
    status                     TEXT NOT NULL,          -- sano | atencion | en_riesgo | critico
    status_label               TEXT NOT NULL,
    reglas_evaluadas           INTEGER NOT NULL,
    reglas_con_hallazgo        INTEGER NOT NULL,
    UNIQUE (batch_id, schema_tabla, tabla)
);
COMMENT ON TABLE meta.dq_scorecard_tabla IS 'Score 0-100 por tabla y por corrida. Generaliza scorecard_calidad_tablas.csv.';

CREATE TABLE meta.dq_plan_remediacion (
    plan_key                BIGSERIAL PRIMARY KEY,
    batch_id                   UUID NOT NULL REFERENCES meta.batch_ingesta(batch_id),
    prioridad                  INTEGER NOT NULL,
    regla_key                  INTEGER NOT NULL REFERENCES meta.dq_regla(regla_key),
    filas_afectadas            INTEGER NOT NULL,
    pct_filas                  NUMERIC(6,2) NOT NULL,
    impacto_pts                NUMERIC(6,2) NOT NULL,
    accion_recomendada         TEXT NOT NULL,
    fecha_generado             TIMESTAMPTZ NOT NULL DEFAULT now(),
    resuelto                   BOOLEAN NOT NULL DEFAULT false
);
COMMENT ON TABLE meta.dq_plan_remediacion IS 'Lista priorizada de issues con acción recomendada, ordenada por impacto_pts. Generaliza plan_remediacion.csv.';
