# 08 · Flujo de Caja y Cartera Vencida (AR Aging)

**Servicio:** Data Storytelling Express / Micro Data Office
**Aplica a:** cualquier negocio B2B que factura a crédito — y también a la gestión financiera de comunidades/condominios que Diego ha llevado directamente.

## El problema de negocio

Finanzas sabe cuánto hay pendiente de cobrar, pero no cuánto de eso realmente va a entrar en las próximas semanas ni qué tan grave es la mora por cliente. El resultado: proyecciones de flujo de caja optimistas que no se cumplen, y llamadas de cobranza que llegan tarde o al cliente equivocado.

## Qué resuelve este dashboard

- Clasifica la cartera pendiente en buckets de antigüedad (vigente, 1-30, 31-60, 61-90, 90+ días).
- Calcula el DSO (días promedio para cobrar una venta) como métrica única de salud de cobranza.
- Proyecta el flujo de cobranza de las próximas 4 semanas usando una curva de probabilidad de cobro distinta por antigüedad — no asume que toda la cartera se cobra igual de rápido.
- Identifica qué clientes concentran el riesgo de cartera vieja, para priorizar la gestión de cobranza.

## Cómo se ve

![Antigüedad de cartera y proyección de cobranza](assets/chart_overview.png)

Abre `dashboard.html` para la versión interactiva.

## Datos

`data/generate_data.py` genera facturas sintéticas para 8 clientes con tres perfiles de pago (puntual, lento, moroso), de forma que la cartera pendiente que queda en el sistema esté realista y deliberadamente concentrada en los clientes más problemáticos — como suele pasar en la vida real.

## Stack

Python (pandas, numpy, matplotlib) + HTML/Chart.js.

## Cómo correrlo

```bash
cd projects/08-flujo-caja-cartera
python3 data/generate_data.py
python3 run_analysis.py
open dashboard.html
```

## De demo a real

Con el reporte de cuentas por cobrar del cliente (la mayoría de los ERPs y sistemas contables lo exportan a Excel) este análisis corre directo, y la curva de cobranza por antigüedad se calibra con el historial real de pagos del negocio en vez de la curva genérica usada aquí.
