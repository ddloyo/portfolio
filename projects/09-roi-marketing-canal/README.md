# 09 · ROI de Marketing: CAC vs. LTV por Canal

**Servicio:** Data Storytelling Express
**Aplica a:** cualquier negocio que invierte en más de un canal de adquisición (ads, orgánico, referidos, eventos) y reparte presupuesto sin comparar el retorno real.

## El problema de negocio

Marketing reporta "leads generados" o "gasto invertido" por canal, pero rara vez se compara el costo de adquisición (CAC) contra el valor real que ese cliente deja en el tiempo (LTV). El resultado: se sigue invirtiendo fuerte en el canal más visible, no en el más rentable.

## Qué resuelve este dashboard

- Calcula CAC real por canal a partir del gasto y los clientes efectivamente adquiridos.
- Estima LTV usando retención observada y margen bruto — no un supuesto optimista.
- Compara cada canal contra un benchmark saludable de LTV:CAC (3:1) para decidir escalar, mantener o replantear.
- Traduce el análisis en una recomendación por canal, no solo en el número.

## Cómo se ve

![CAC y ratio LTV:CAC por canal](assets/chart_overview.png)

Abre `dashboard.html` para la versión interactiva.

## Datos

`data/generate_data.py` simula 6 meses de gasto y clientes adquiridos para 6 canales (Referidos, SEO, Google Ads, Meta Ads, Email, Eventos) con retención y ticket promedio distintos por canal — para que el resultado no sea "más gasto = peor" de forma trivial, sino que dependa de la calidad real del cliente que trae cada canal.

## Stack

Python (pandas, numpy, matplotlib) + HTML/Chart.js.

## Cómo correrlo

```bash
cd projects/09-roi-marketing-canal
python3 data/generate_data.py
python3 run_analysis.py
open dashboard.html
```

## De demo a real

Con los reportes de gasto de cada plataforma (Google Ads, Meta Ads Manager, CRM) y el histórico de compras del cliente, el CAC y LTV se calculan con datos reales en vez de supuestos — el resto del análisis no cambia.
