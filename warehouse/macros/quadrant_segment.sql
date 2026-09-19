{#
  El patrón de cuadrante (mediana de X × mediana de Y → 4 etiquetas) se repite
  en churn (riesgo × valor), RFM (recencia × valor) y ROI de marketing
  (gasto × retorno) en el diseño original del warehouse. En vez de repetir el
  CASE WHEN cuatro veces, es una sola macro parametrizada.

  x_col / y_col: expresiones SQL (columna o expresión) a comparar.
  x_threshold / y_threshold: expresiones SQL (subconsulta, literal, o
    referencia a otra CTE) — no tienen que ser literales.
  labels: [alto_alto, alto_bajo, bajo_alto, bajo_bajo]

  Uso:
    {{ quadrant_segment(
         x_col='percentil_riesgo', x_threshold='50',
         y_col='gasto_mensual_mxn', y_threshold='(select median(gasto_mensual_mxn) from ' ~ ref('int_cliente_churn_features') ~ ')',
         labels=['Alto riesgo / alto valor','Alto riesgo / bajo valor','Bajo riesgo / alto valor','Bajo riesgo / bajo valor']
    ) }}
#}
{% macro quadrant_segment(x_col, x_threshold, y_col, y_threshold, labels) %}
case
    when {{ x_col }} >= {{ x_threshold }} and {{ y_col }} >= {{ y_threshold }} then '{{ labels[0] }}'
    when {{ x_col }} >= {{ x_threshold }} and {{ y_col }} <  {{ y_threshold }} then '{{ labels[1] }}'
    when {{ x_col }} <  {{ x_threshold }} and {{ y_col }} >= {{ y_threshold }} then '{{ labels[2] }}'
    else '{{ labels[3] }}'
end
{% endmacro %}
