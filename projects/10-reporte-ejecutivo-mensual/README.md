# 10 · Reporte Ejecutivo Mensual

**Servicio:** Data Storytelling Express — este es el entregable insignia del servicio, tal cual se describe en la propuesta de valor de XIA.
**Frase que resume el servicio:** *"Tu reporte, convertido en la decisión — a tiempo para tomarla."*

## El problema de negocio

El reporte mensual llega como una tabla de números. Dirección ve que el ingreso bajó, pero no por qué, y para averiguarlo hay que pedirle a alguien que "le meta mano" al Excel — para cuando hay respuesta, ya pasó la semana en la que importaba.

## Qué resuelve este reporte

Sigue una estructura fija de tres preguntas, no una tabla:

1. **Qué pasó** — el número consolidado del mes y su variación.
2. **Por qué** — qué categoría, producto o región explica la variación (no "todo bajó parejo").
3. **Qué hacer** — una recomendación concreta y acotada, no un llamado genérico a "mejorar".

## Cómo se ve

![Tendencia de ingreso y causa de la variación](assets/chart_overview.png)

Abre `dashboard.html` para la versión interactiva — pensada para proyectarse en una reunión ejecutiva de 15 minutos.

## Datos

`data/generate_data.py` simula 12 meses de ingreso para 4 categorías de producto, con una caída aislada y explicable en una sola categoría el último mes — el patrón real más común (un cliente grande que pausa pedidos, una línea que pierde tracción) frente al que un promedio general no dice nada.

## Stack

Python (pandas, numpy, matplotlib) + HTML/Chart.js.

## Cómo correrlo

```bash
cd projects/10-reporte-ejecutivo-mensual
python3 data/generate_data.py
python3 run_analysis.py
open dashboard.html
```

## De demo a real

Este es exactamente el formato de la primera entrega de un diagnóstico XIA: se arma en días a partir de los reportes que el cliente ya tiene, y la sesión de entrega de 45 minutos se dedica a decidir la acción, no a explicar de dónde salió el número.
