# XIA Insights × Analytics — Portafolio de Demostración

**Preguntas un lunes. Respuesta el jueves. El viernes ya decidiste sin ella.**

Este repositorio es un portafolio de 12 proyectos de demostración que muestran, con datos sintéticos pero con código funcional real, lo que un **equipo de datos a demanda** puede resolver en semanas — no en trimestres. Cada proyecto es un caso de negocio completo: datos, análisis y un dashboard interactivo, listo para abrirse en el navegador.

No vendemos dashboards. Vendemos el momento en que la respuesta todavía importaba.

## Los dos servicios que ilustra este portafolio

| Servicio | Qué es | Proyectos de ejemplo |
|---|---|---|
| **Data Storytelling Express** | Proyecto puntual · primera versión en días. Un reporte convertido en la decisión: diagnóstico, narrativa clara (qué pasa, por qué, qué hacer) y presentación ejecutiva. | 03, 05, 06, 09, 10, 12 |
| **Micro Data Office** | Suscripción mensual, sin mínimos. El equipo de datos que no se justifica contratar todavía: dashboards siempre actualizados, limpieza de datos, iteración continua. | 01, 02, 04, 07, 08, 11 |

## Los 12 proyectos

| # | Proyecto | Servicio | Qué resuelve |
|---|---|---|---|
| 01 | [Ventas por Equipo en Tiempo Real](projects/01-sales-performance-dashboard) | Micro Data Office | Deja de esperar el cierre de mes para saber qué equipo va bien y cuál no. |
| 02 | [Funnel de Ventas con Alertas de Fuga](projects/02-funnel-fuga-ventas) | Micro Data Office | Detecta una fuga de conversión con semanas de anticipación, no al cierre. |
| 03 | [Scorecard Ejecutivo: Metas vs. Resultados](projects/03-scorecard-metas-vs-resultados) | Data Storytelling Express | Una pantalla, una conclusión, un responsable por indicador — cruzando áreas. |
| 04 | [Predicción de Riesgo de Churn](projects/04-prediccion-churn) | Micro Data Office | Modelo de ML que dice qué cliente se va y por qué, con tiempo para retenerlo. |
| 05 | [Segmentación RFM y Priorización Comercial](projects/05-segmentacion-rfm) | Data Storytelling Express | A quién llamar hoy y a quién dejar de perseguir. |
| 06 | [Elasticidad de Precios y Price Intelligence](projects/06-elasticidad-precios) | Micro Data Office | Qué productos aguantan subir de precio sin perder ingreso. |
| 07 | [Forecasting de Demanda e Inventario](projects/07-forecast-demanda-inventario) | Micro Data Office | Cuántos días de inventario quedan realmente, antes del quiebre de stock. |
| 08 | [Flujo de Caja y Cartera Vencida](projects/08-flujo-caja-cartera) | Data Storytelling Express | Cuánto de la cartera es cobrable de verdad en las próximas 4 semanas. |
| 09 | [ROI de Marketing: CAC vs. LTV por Canal](projects/09-roi-marketing-canal) | Data Storytelling Express | Qué canal escalar y cuál replantear, más allá del gasto. |
| 10 | [Reporte Ejecutivo Mensual](projects/10-reporte-ejecutivo-mensual) | Data Storytelling Express | El entregable insignia: qué pasó, por qué, y qué hacer — en una sesión de 15 min. |
| 11 | [Consolidación de Datos Dispersos](projects/11-consolidacion-fuente-verdad) | Micro Data Office | Tres Excels de tres sucursales, un solo número correcto. |
| 12 | [NPS y Análisis de Causa Raíz](projects/12-nps-causa-raiz) | Data Storytelling Express | De "el NPS bajó" a "sabemos exactamente qué corregir". |

Cada carpeta de proyecto incluye:

- `data/generate_data.py` — genera un dataset sintético pero realista (nunca datos de un cliente real).
- `run_analysis.py` — el análisis completo: procesamiento, métricas de negocio, gráfico estático (`assets/chart_overview.png`) y el dashboard interactivo (`dashboard.html`).
- `README.md` — el caso de negocio: el problema, qué resuelve el entregable, cómo correrlo, y cómo se adapta a datos reales de un cliente.

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

El mismo patrón aplica a cualquiera de los 12 proyectos.

## Diseño y stack

- **Python** (pandas, numpy, matplotlib, scikit-learn) para generación de datos sintéticos y análisis.
- **HTML + Chart.js** para los dashboards interactivos — se abren en cualquier navegador, sin instalar nada del lado del cliente.
- Los 12 dashboards comparten una sola librería de estilo (`_lib/`) con una paleta validada para accesibilidad (contraste y distinción para daltonismo), para que el portafolio se sienta como un solo producto, no como 12 experimentos sueltos.
- Todos los datasets son **100% sintéticos**, generados con semillas fijas para que cada proyecto sea reproducible.

## Sobre XIA

XIA pone un dueño fraccional a los datos de PyMEs en crecimiento, equipos comerciales y direcciones que aún no justifican un equipo de datos interno — para que la respuesta llegue a tiempo de importar.

**Diagnóstico inicial de 30 minutos, sin costo.**
📧 xianalytics20@gmail.com · 💬 WhatsApp +52 55 3566 6166
