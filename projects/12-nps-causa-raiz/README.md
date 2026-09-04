# 12 · NPS y Análisis de Causa Raíz

**Servicio:** Data Storytelling Express / Micro Data Office
**Conecta con:** *"Sabes que algo bajó, pero no por qué ni qué hacer al respecto"* — aquí la causa raíz sale directo de la voz del cliente.

## El problema de negocio

El NPS mensual se reporta como un solo número. Cuando baja, dirección lo sabe, pero nadie traduce ese número en una causa específica y accionable — el resultado suele ser un plan genérico de "mejorar la experiencia del cliente" que no ataca el problema real.

## Qué resuelve este dashboard

- Calcula el NPS mensual (% promotores − % detractores) y lo compara contra el promedio histórico.
- Cruza los detractores recientes con el motivo que ellos mismos declararon, no una suposición del equipo interno.
- Aísla la causa raíz dominante detrás de una caída de NPS, para dirigir la corrección a un proceso específico.
- Deja trazabilidad mes a mes del NPS y del volumen de respuestas para dar seguimiento a si la corrección funcionó.

## Cómo se ve

![NPS mensual y causa raíz de detractores](assets/chart_overview.png)

Abre `dashboard.html` para la versión interactiva.

## Datos

`data/generate_data.py` simula 12 meses de respuestas de encuesta NPS con una caída deliberada en los últimos 2 meses, concentrada en un solo motivo declarado por los detractores (tiempo de respuesta de soporte) — el patrón real de una causa raíz aislable, no un deterioro generalizado.

## Stack

Python (pandas, numpy, matplotlib) + HTML/Chart.js.

## Cómo correrlo

```bash
cd projects/12-nps-causa-raiz
python3 data/generate_data.py
python3 run_analysis.py
open dashboard.html
```

## De demo a real

Este es el tipo de análisis de voz del cliente (NPS/CSAT + causa raíz de comentarios) que Diego desarrolló de forma extensa en su etapa en Qualtrics. Con datos reales de encuesta (Qualtrics, SurveyMonkey, Google Forms o un CRM con NPS integrado) el mismo pipeline corre directo sobre el export de respuestas.
