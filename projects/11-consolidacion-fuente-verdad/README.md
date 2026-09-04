# 11 · Consolidación de Datos Dispersos: Una Sola Fuente de Verdad

**Servicio:** Micro Data Office (la base de todo lo demás)
**Conecta directo con el problema #1 de la propuesta de valor de XIA:** *"Cada área llega con su propio número y la reunión se va en discutir cuál es el correcto."*

## El problema de negocio

Tres sucursales, tres Excels, tres formatos. CDMX manda fechas en `DD/MM/YYYY` con columnas en español; Monterrey manda `YYYY-MM-DD` con otros nombres de columna; Guadalajara todavía usa un sistema viejo que exporta en inglés y escribe el nombre de la sucursal de tres formas distintas (`guadalajara`, `GDL `, `Guadalajara`). Sumar los tres archivos "tal cual" duplica ventas y pierde otras.

## Qué resuelve este proyecto

- Ingiere los 3 exports con sus propios formatos y los estandariza a un esquema único.
- Normaliza nombres de sucursal inconsistentes (mayúsculas, espacios, abreviaciones) a un catálogo único.
- Elimina duplicados exactos entre fuentes — sin esto, el total de ventas queda inflado.
- Separa (no inventa) los registros con datos faltantes en una cola de revisión manual explícita.
- Entrega un único archivo limpio (`data/fuente_unica.csv`) del que parte cualquier reporte posterior.

## Cómo se ve

![Embudo de calidad de datos y ventas consolidadas](assets/chart_overview.png)

Abre `dashboard.html` para la versión interactiva.

## Datos

`data/generate_data.py` genera 3 exports "crudos" deliberadamente inconsistentes entre sí (columnas, formato de fecha, nombres de sucursal) con duplicados y datos faltantes inyectados a propósito, simulando exactamente el desorden real de tener tres sucursales reportando por su cuenta.

## Stack

Python (pandas) para el pipeline de limpieza y estandarización + HTML/Chart.js para el dashboard. La lógica de mapeo de columnas y normalización de categorías es el mismo patrón que un modelo de `staging` en dbt — aquí resuelto en un script simple para que sea legible sin infraestructura adicional.

## Cómo correrlo

```bash
cd projects/11-consolidacion-fuente-verdad
python3 data/generate_data.py
python3 run_analysis.py
open dashboard.html
```

Revisa también `data/revision_manual_monto_faltante.csv` — la cola de registros que requieren revisión humana en vez de un dato inventado.

## De demo a real

Este es el primer entregable real de casi cualquier engagement de Micro Data Office: antes de poder construir un dashboard confiable, hay que resolver de dónde sale "el número correcto". Con fuentes reales (Excel, CRM, POS, ERP) el mapeo de columnas se ajusta una vez por fuente y el pipeline corre en automático en cada actualización.
