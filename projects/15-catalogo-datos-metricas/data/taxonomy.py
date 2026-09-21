"""
Taxonomía curada del catálogo: lo que dbt NO sabe y alguien tiene que decidir.

  * DOMINIOS de negocio (los 8 de marts/ más "calidad" para el motor de calidad de datos).
  * A qué dominio pertenece cada modelo que no vive en una carpeta de dominio
    (staging, intermediate, gold, meta). Los marts usan su carpeta.
  * Qué dashboard del portafolio consume cada carpeta de gold.

run_analysis.py falla si aparece un modelo sin dominio, así que un modelo nuevo
en el warehouse obliga a decidir dónde vive en el catálogo en vez de quedar
huérfano en silencio.
"""

DOMAINS = {
    "core": {"es": "Core (dimensiones compartidas)", "en": "Core (shared dimensions)"},
    "ventas": {"es": "Ventas", "en": "Sales"},
    "finanzas": {"es": "Finanzas", "en": "Finance"},
    "cliente": {"es": "Cliente", "en": "Customer"},
    "marketing": {"es": "Marketing", "en": "Marketing"},
    "inventario": {"es": "Inventario", "en": "Inventory"},
    "scorecard": {"es": "Scorecard", "en": "Scorecard"},
    "sucursales": {"es": "Sucursales", "en": "Branches"},
    "calidad": {"es": "Calidad de datos", "en": "Data quality"},
}

LAYERS = {
    "bronze": {"es": "Fuentes (bronze)", "en": "Sources (bronze)"},
    "staging": {"es": "Staging", "en": "Staging"},
    "intermediate": {"es": "Intermediate", "en": "Intermediate"},
    "marts": {"es": "Marts (silver)", "en": "Marts (silver)"},
    "meta": {"es": "Meta", "en": "Meta"},
    "gold": {"es": "Gold (reportes)", "en": "Gold (reports)"},
}

# Staging: por entidad, no por sistema fuente. crm y erp reparten entidades entre
# varios dominios (el maestro de clientes es core; las metas y el pipeline son ventas).
STAGING_DOMAIN = {
    "stg_ads__marketing_gasto": "marketing",
    "stg_crm__cancelacion": "cliente",
    "stg_crm__cliente": "core",
    "stg_crm__equipo": "core",
    "stg_crm__meta_venta": "ventas",
    "stg_crm__oportunidad_evento": "ventas",
    "stg_crm__vendedor": "core",
    "stg_encuestas__encuesta_nps": "cliente",
    "stg_erp__calendario": "core",
    "stg_erp__factura_linea": "finanzas",
    "stg_erp__pago": "finanzas",
    "stg_erp__producto": "core",
    "stg_erp__suscripcion_cargo": "finanzas",
    "stg_helpdesk__ticket_soporte": "cliente",
    "stg_pos__pedido_linea": "ventas",
    "stg_producto_analytics__evento_actividad": "cliente",
    "stg_scorecard__kpi_captura_manual": "scorecard",
    "stg_scorecard__kpi_meta": "scorecard",
    "stg_sucursales__cdmx": "sucursales",
    "stg_sucursales__guadalajara": "sucursales",
    "stg_sucursales__monterrey": "sucursales",
    "stg_wms__inventario_snapshot": "inventario",
}

INTERMEDIATE_DOMAIN = {
    "int_canal_mes_metricas": "marketing",
    "int_factura_linea_validada": "finanzas",
    "int_pedidos_enriquecidos": "ventas",
    "int_producto_depurado": "core",
    "int_ventas_sucursal_pendiente": "sucursales",
    "int_ventas_sucursal_unificada": "sucursales",
}

# Gold: una carpeta por dashboard -> dominio de negocio del dashboard.
GOLD_DOMAIN = {
    "01_ventas_por_equipo": "ventas",
    "02_funnel_fuga": "ventas",
    "03_scorecard": "scorecard",
    "04_churn": "cliente",
    "05_rfm": "cliente",
    "06_elasticidad": "ventas",
    "07_forecast_inventario": "inventario",
    "08_flujo_caja": "finanzas",
    "09_roi_marketing": "marketing",
    "10_reporte_ejecutivo": "ventas",
    "11_fuente_unica": "sucursales",
    "12_nps": "cliente",
    "13_data_health": "calidad",
}

# Dashboard del portafolio que consume cada carpeta de gold (número -> carpeta y título).
DASHBOARDS = {
    1: ("01-sales-performance-dashboard", "Ventas por Equipo en Tiempo Real", "Real-Time Sales by Team"),
    2: ("02-funnel-fuga-ventas", "Funnel de Ventas con Alertas de Fuga", "Sales Funnel with Leak Alerts"),
    3: ("03-scorecard-metas-vs-resultados", "Scorecard Ejecutivo: Metas vs. Resultados", "Executive Scorecard: Targets vs. Results"),
    4: ("04-prediccion-churn", "Predicción de Riesgo de Churn", "Churn Risk Prediction"),
    5: ("05-segmentacion-rfm", "Segmentación RFM y Priorización Comercial", "RFM Segmentation & Sales Prioritization"),
    6: ("06-elasticidad-precios", "Elasticidad de Precios y Price Intelligence", "Price Elasticity & Price Intelligence"),
    7: ("07-forecast-demanda-inventario", "Forecasting de Demanda e Inventario", "Demand & Inventory Forecasting"),
    8: ("08-flujo-caja-cartera", "Flujo de Caja y Cartera Vencida", "Cash Flow & Overdue Receivables"),
    9: ("09-roi-marketing-canal", "ROI de Marketing: CAC vs. LTV por Canal", "Marketing ROI: CAC vs. LTV by Channel"),
    10: ("10-reporte-ejecutivo-mensual", "Reporte Ejecutivo Mensual", "Monthly Executive Report"),
    11: ("11-consolidacion-fuente-verdad", "Consolidación de Datos Dispersos", "Consolidating Scattered Data"),
    12: ("12-nps-causa-raiz", "NPS y Análisis de Causa Raíz", "NPS & Root Cause Analysis"),
    13: ("13-data-health-check", "Data Health Check: Auditoría de Calidad de Datos", "Data Health Check: Data Quality Audit"),
}


def dashboard_of_gold_folder(folder):
    """'03_scorecard' -> 3"""
    return int(folder.split("_", 1)[0])
