# XIA Insights × Analytics — [Portafolio de Demostración](https://ddloyo.github.io/portfolio/)

**Preguntas un lunes. Respuesta el jueves. El viernes ya decidiste sin ella.**

Este repositorio es un portafolio de 16 proyectos de demostración que muestran, con datos sintéticos pero con código funcional real, lo que un **equipo de datos a demanda** puede resolver en semanas en lugar de trimestres. Catorce son casos de negocio completos, con datos, análisis y un dashboard interactivo que se abre en el navegador. Los otros dos son la capa que los sostiene. El 14 es la arquitectura de datos (dbt) que los respalda y el 15 es el catálogo que documenta ese mismo warehouse y define, en lenguaje de negocio, qué significa cada métrica.

No vendemos dashboards. Vendemos el momento en que la respuesta todavía importaba.

## Los dos servicios que ilustra este portafolio

| Servicio | Qué es | Proyectos de ejemplo |
|---|---|---|
| **Data Storytelling Express** | Proyecto puntual · primera versión en días. Un reporte convertido en la decisión: diagnóstico, narrativa clara (qué pasa, por qué, qué hacer) y presentación ejecutiva. | 03, 05, 06, 09, 10, 12 |
| **Micro Data Office** | Suscripción mensual, sin mínimos. El equipo de datos que no se justifica contratar todavía: dashboards siempre actualizados, limpieza de datos, iteración continua. | 01, 02, 04, 07, 08, 11, 13, 14, 15, 16 |

## Los 16 proyectos, en tres pilares

El portafolio avanza en madurez: primero se asegura que los datos sean confiables (**Data Foundation**), luego responde qué está pasando y por qué (**Data Analysis**), y finalmente anticipa qué va a pasar y qué hacer al respecto (**Advanced Analytics**).

### Data Foundation

Datos limpios, consolidados y confiables antes de empezar a analizar.

| # | Proyecto | Servicio | Qué resuelve |
|---|---|---|---|
| 11 | [Consolidación de Datos Dispersos](projects/11-consolidacion-fuente-verdad) | Micro Data Office | Tres Excels de tres sucursales, un solo número correcto. |
| 13 | [Data Health Check: Auditoría de Calidad de Datos](projects/13-data-health-check) | Micro Data Office | Un score de calidad por tabla y un plan que dice qué corregir primero y por qué. |
| 14 | [Arquitectura de Datos: del DDL a un Warehouse dbt](database/architecture.html) | Micro Data Office | El mismo diseño de warehouse, ahora con 87 modelos, 429 tests y un lineage que genera dbt en lugar de dibujarse a mano. |
| 15 | [Catálogo de Datos y Definición de Métricas](projects/15-catalogo-datos-metricas) | Micro Data Office | Qué datos hay, de dónde vienen y qué significa cada métrica, sobre un warehouse dbt real y con 46 definiciones en lenguaje de negocio. |
| 16 | [Disponibilidad y Frescura de Datos (SLA)](projects/16-frescura-disponibilidad-datos) | Micro Data Office | ¿Los datos de hoy son de hoy? Qué fuente llegó tarde, hace cuánto y qué dashboards alimenta, medido con `dbt source freshness` real. |

### Data Analysis

Qué está pasando y por qué, con el detalle suficiente para tomar una decisión.

| # | Proyecto | Servicio | Qué resuelve |
|---|---|---|---|
| 01 | [Ventas por Equipo en Tiempo Real](projects/01-sales-performance-dashboard) | Micro Data Office | Deja de esperar el cierre de mes para saber qué equipo va bien y cuál no. |
| 02 | [Funnel de Ventas con Alertas de Fuga](projects/02-funnel-fuga-ventas) | Micro Data Office | Detecta una fuga de conversión semanas antes del cierre. |
| 03 | [Scorecard Ejecutivo: Metas vs. Resultados](projects/03-scorecard-metas-vs-resultados) | Data Storytelling Express | Una pantalla con una conclusión y un responsable por indicador, para todas las áreas. |
| 05 | [Segmentación RFM y Priorización Comercial](projects/05-segmentacion-rfm) | Data Storytelling Express | A quién llamar hoy y a quién dejar de perseguir. |
| 08 | [Flujo de Caja y Cartera Vencida](projects/08-flujo-caja-cartera) | Data Storytelling Express | Cuánto de la cartera es cobrable de verdad en las próximas 4 semanas. |
| 09 | [ROI de Marketing: CAC vs. LTV por Canal](projects/09-roi-marketing-canal) | Data Storytelling Express | Qué canal escalar y cuál replantear, más allá del gasto. |
| 10 | [Reporte Ejecutivo Mensual](projects/10-reporte-ejecutivo-mensual) | Data Storytelling Express | El entregable insignia: qué pasó, por qué y qué hacer, explicado en una sesión de 15 minutos. |
| 12 | [NPS y Análisis de Causa Raíz](projects/12-nps-causa-raiz) | Data Storytelling Express | De "el NPS bajó" a "sabemos exactamente qué corregir". |

### Advanced Analytics

Modelos predictivos y de optimización para pasar de lo que ya pasó a lo que probablemente viene.

| # | Proyecto | Servicio | Qué resuelve |
|---|---|---|---|
| 04 | [Predicción de Riesgo de Churn](projects/04-prediccion-churn) | Micro Data Office | Modelo de ML que dice qué cliente se va y por qué, con tiempo para retenerlo. |
| 06 | [Elasticidad de Precios y Price Intelligence](projects/06-elasticidad-precios) | Micro Data Office | Qué productos aguantan subir de precio sin perder ingreso. |
| 07 | [Forecasting de Demanda e Inventario](projects/07-forecast-demanda-inventario) | Micro Data Office | Cuántos días de inventario quedan realmente, antes del quiebre de stock. |

Cada carpeta de proyecto de negocio (01–13 y 16) incluye:

- `data/generate_data.py`: genera un dataset sintético pero realista (nunca datos de un cliente real).
- `run_analysis.py`: el análisis completo: procesamiento, métricas de negocio, gráfico estático (`assets/chart_overview.png`) y el dashboard interactivo (`dashboard.html`).
- `README.md`: el caso de negocio, con el problema, qué resuelve el entregable, cómo correrlo y cómo se adapta a datos reales de un cliente.

El proyecto 15 es la excepción: no genera datos sintéticos, sino que extrae un snapshot de los artefactos de dbt del [`warehouse/`](warehouse/) real (`data/extract_catalog.py`) y construye el catálogo sobre él (`run_analysis.py`). Los proyectos 14 y 15 son la cara «infraestructura» del portafolio; los otros 14, la cara «respuesta».

El 16 es un híbrido: su estado de hoy y sus umbrales salen del warehouse real (`freshness` en los `_*__sources.yml` + `dbt source freshness`), y solo el historial de 30 días se simula, con una prueba de que clasifica igual que dbt (`data/verify_dbt_parity.py`).

## El warehouse detrás de los 13 datasets

[`warehouse/`](warehouse/) es una segunda capa del portafolio: un proyecto
**dbt + DuckDB** que demuestra Analytics Engineering con sources, staging,
intermediate, marts, un modelo incremental, tests (genéricos, custom y
singulares), documentación con lineage/DAG, macros en Jinja y CI/CD en
GitHub Actions, sin pagar un servidor. La mayoría de los 13 CSV de
`projects/*/data/` son en realidad un reporte *gold*; `warehouse/` simula
el operativo real (CRM, pedidos, facturación...) del que esos reportes se
calcularían, reusando los datasets ya sucios de los proyectos 04, 11 y 13
como fuente en vez de inventar datos desde cero. El diseño completo está en
[`database/README.md`](database/README.md); cómo correrlo, en
[`warehouse/README.md`](warehouse/README.md). La transformación de ese diseño
en DDL a este proyecto dbt, con sus ventajas, está ilustrada en
[`database/architecture.html`](database/architecture.html) (proyecto 14).

## Cómo explorar el portafolio

```bash
git clone <este-repositorio>
cd xia-analytics-portfolio
python3 -m venv .venv && source .venv/bin/activate
pip install pandas numpy matplotlib scikit-learn

cd projects/01-sales-performance-dashboard
python3 data/generate_data.py
python3 run_analysis.py
open dashboard.html   # o doble clic en el archivo
```

El mismo patrón aplica a cualquiera de los proyectos 01–13. El 16 se construye igual, pero parte de una foto de dbt ya sincronizada (ver su [README](projects/16-frescura-disponibilidad-datos/README.md) para regenerarla). El 15 se construye con `python3 run_analysis.py` (solo librería estándar; ver su [README](projects/15-catalogo-datos-metricas/README.md) para regenerar el snapshot desde dbt).

## Diseño y stack

- **Python** (pandas, numpy, matplotlib, scikit-learn) para generación de datos sintéticos y análisis.
- **HTML + Chart.js** para los dashboards interactivos, que se abren en cualquier navegador, sin instalar nada del lado del cliente.
- Los 14 dashboards de KPI + gráficas (01–13 y 16) comparten una sola librería de estilo (`_lib/`) con una paleta validada para accesibilidad (contraste y distinción para daltonismo), para que el portafolio se vea como un solo producto y no como 14 experimentos sueltos. El catálogo (15) es una página a medida, porque un buscador con filas expandibles no cabe en el patrón KPI + gráficas, pero comparte los mismos tokens de color, tipografía y estructura de encabezado.
- Todos los datasets son **100% sintéticos**, generados con semillas fijas para que cada proyecto sea reproducible.

## Sobre XIA

XIA pone un dueño fraccional a los datos de PyMEs en crecimiento, equipos comerciales y direcciones que aún no justifican un equipo de datos interno, para que la respuesta llegue cuando todavía sirve.

**Diagnóstico inicial de 30 minutos, sin costo.**
📧 xianalytics20@gmail.com · 💬 WhatsApp +52 55 3566 6166
