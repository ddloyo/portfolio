"""
XIA Insights x Analytics — shared, self-contained HTML dashboard renderer.

Every project in this portfolio calls `render()` with its own KPIs, charts,
insights and table. The template is shared so all 12 dashboards look like
one coherent product line instead of 12 one-off pages — same reasoning a
client would want from a real "Micro Data Office" engagement.

Design: the XIA brand palette (Teal / Dark Teal / Gold / Light Teal / Cream —
visualization-builder skill), fixed hue order, light + dark mode via CSS
variables, Chart.js (pinned, cdnjs) for the interactive charts, a plain
HTML table under each chart so the data is never color-only. Gold is
reserved for one-per-view emphasis (see the `hero` KPI flag below) — never
Anthropic's "Claude clay" orange.
"""

import json
from pathlib import Path

# Base teal + gold accent + grays desaturated from teal — same order as
# xia_style.CATEGORICAL, with a brightened variant for dark backgrounds.
CATEGORICAL_LIGHT = ["#71A8A3", "#B8842C", "#163832", "#9CB8B4", "#D4A94F", "#4F6360", "#C7D6D3", "#8C6220"]
CATEGORICAL_DARK = ["#8FC2BC", "#D4A94F", "#DCEAE7", "#A9C7C2", "#E8C878", "#6E8B86", "#C79A52", "#557D77"]

# Sequential teal used for funnel-chart stages (big -> small stage).
# Dark-mode stops stay lighter than the dark-teal card surface so stages
# never blend into the background.
FUNNEL_LIGHT = ["#DCEAE7", "#BFDAD5", "#9FC7C0", "#71A8A3", "#4F8880", "#163832"]
FUNNEL_DARK = ["#2F5850", "#3D7268", "#4F9285", "#63AC9E", "#84C9BB", "#B3E2D6"]

STATUS = {
    "good": ("#3E8F72", "#3E8F72"),
    "warning": ("#B8842C", "#B8842C"),
    "serious": ("#8C5A1E", "#8C5A1E"),
    "critical": ("#d03b3b", "#d03b3b"),
    "neutral": ("#9CB8B4", "#9CB8B4"),
}

CHARTJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js"


def _kpi_html(kpis):
    cards = []
    for k in kpis:
        status = k.get("status")
        badge = ""
        if status:
            badge = f'<span class="kpi-badge kpi-{status}">{k.get("status_label", status)}</span>'
        delta_html = ""
        if k.get("delta") is not None:
            direction = k.get("delta_direction", "up")
            arrow = "&uarr;" if direction == "up" else "&darr;"
            sign_class = "delta-up" if direction == "up" else "delta-down"
            delta_html = f'<div class="kpi-delta {sign_class}">{arrow} {k["delta"]}</div>'
        # "hero" is gold, one-per-dashboard emphasis for the single number
        # that carries the message — never set it on more than one KPI.
        card_class = "kpi-card kpi-hero" if k.get("hero") else "kpi-card"
        cards.append(f"""
        <div class="{card_class}">
          <div class="kpi-label">{k['label']}</div>
          <div class="kpi-value">{k['value']}</div>
          {delta_html}
          {badge}
        </div>""")
    return "\n".join(cards)


def _hero_widget_html(kpi, chart_id):
    """Gold-bordered score tile with its own trend chart embedded below the
    number, meant to sit to the left of the per-metric kpi-grid-5 — one
    combined 'headline + trend' widget instead of two separate cards."""
    status = kpi.get("status")
    badge = ""
    if status:
        badge = f'<span class="kpi-badge kpi-{status}">{kpi.get("status_label", status)}</span>'
    return f"""
    <div class="hero-widget">
      <div class="kpi-label">{kpi['label']}</div>
      <div class="kpi-value hero-value">{kpi['value']}</div>
      {badge}
      <div class="hero-chart-wrap">
        <canvas id="{chart_id}"></canvas>
      </div>
    </div>"""


def _insights_html(insights):
    items = "\n".join(f"<li>{i}</li>" for i in insights)
    return f'<ul class="insights">{items}</ul>'


def _table_html(table, open=False):
    """`open=True` renders an always-visible summary table instead of a
    collapsed <details> — for table_position="top" (Minto pyramid: the
    overview is part of the answer, not a "show more" toggle buried below
    the charts)."""
    if not table:
        return ""
    headers = "".join(f"<th>{h}</th>" for h in table["headers"])
    rows = ""
    for row in table["rows"]:
        cells = "".join(f"<td>{c}</td>" for c in row)
        rows += f"<tr>{cells}</tr>\n"
    table_markup = f"""<table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{rows}</tbody>
      </table>"""
    if open:
        title_html = f'<p class="section-label">{table["title"]}</p>' if table.get("title") else ""
        return f"""
    <div class="table-wrap table-wrap-open">
      {title_html}
      {table_markup}
    </div>
    """
    return f"""
    <details class="table-wrap">
      <summary>Ver tabla de datos</summary>
      {table_markup}
    </details>
    """


def _chart_block(chart, idx):
    cid = chart["id"]
    title = chart["title"]
    subtitle = chart.get("subtitle", "")
    card_class = "chart-card chart-card-wide" if chart.get("full_width") else "chart-card"
    return f"""
    <div class="{card_class}">
      <div class="chart-head">
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
      <div class="chart-canvas-wrap">
        <canvas id="{cid}"></canvas>
      </div>
    </div>
    """


def _funnel_js(chart):
    """Draws a true funnel (trapezoid stages, tapering to the next stage's
    count) directly on the canvas — Chart.js has no native funnel type.
    Auto-highlights the weakest step-to-step conversion so the chart points
    at the leak instead of just showing volume."""
    cid = chart["id"]
    labels = json.dumps(chart["labels"], ensure_ascii=False)
    values = json.dumps(chart["datasets"][0]["data"])
    colors_light = json.dumps(FUNNEL_LIGHT)
    colors_dark = json.dumps(FUNNEL_DARK)
    return f"""
    (function() {{
      const canvas = document.getElementById('{cid}');
      const wrap = canvas.parentElement;
      const labels = {labels};
      const values = {values};
      const colorsLight = {colors_light};
      const colorsDark = {colors_dark};

      function draw() {{
        const dpr = window.devicePixelRatio || 1;
        const w = wrap.clientWidth, h = wrap.clientHeight;
        canvas.width = w * dpr; canvas.height = h * dpr;
        canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);

        const n = values.length;
        const maxVal = values[0];
        const colors = isDark() ? colorsDark : colorsLight;
        const padY = 8;
        // Fixed label columns (not sized off the shape) so text never
        // overflows a narrow late-stage trapezoid when values span a wide range.
        const padLeft = Math.min(140, w * 0.34);
        const padRight = Math.min(90, w * 0.24);
        const bandW = Math.max(w - padLeft - padRight, 20);
        const bandCx = padLeft + bandW / 2;
        const rowH = (h - padY * 2) / n;

        let weakestIdx = 0, weakestRate = 100;
        for (let i = 0; i < n - 1; i++) {{
          const r = values[i + 1] / values[i] * 100;
          if (r < weakestRate) {{ weakestRate = r; weakestIdx = i; }}
        }}

        for (let i = 0; i < n; i++) {{
          const topW = Math.max((values[i] / maxVal) * bandW, 4);
          const botW = Math.max((i + 1 < n ? values[i + 1] / maxVal : values[i] / maxVal) * bandW, 4);
          const yTop = padY + i * rowH;
          const yBot = yTop + rowH;

          ctx.beginPath();
          ctx.moveTo(bandCx - topW / 2, yTop);
          ctx.lineTo(bandCx + topW / 2, yTop);
          ctx.lineTo(bandCx + botW / 2, yBot);
          ctx.lineTo(bandCx - botW / 2, yBot);
          ctx.closePath();
          ctx.fillStyle = colors[i % colors.length];
          ctx.fill();
          ctx.strokeStyle = surfaceColor();
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.textBaseline = 'middle';
          ctx.textAlign = 'right';
          ctx.fillStyle = inkColor('primary');
          ctx.font = '600 12px -apple-system, sans-serif';
          ctx.fillText(labels[i], padLeft - 12, yTop + rowH / 2 - 8);
          ctx.fillStyle = inkColor('secondary');
          ctx.font = '700 12.5px -apple-system, sans-serif';
          ctx.fillText(values[i].toLocaleString('es-MX'), padLeft - 12, yTop + rowH / 2 + 9);

          if (i + 1 < n) {{
            const rate = values[i + 1] / values[i] * 100;
            const isWeak = i === weakestIdx;
            ctx.fillStyle = isWeak ? '#d03b3b' : inkColor('muted');
            ctx.font = (isWeak ? '700 12px' : '600 11.5px') + ' -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(`${{rate.toFixed(0)}}% ${{isWeak ? '\\u26A0' : '\\u2192'}}`, padLeft + bandW + 12, yBot);
          }}
        }}
      }}

      draw();
      window.addEventListener('resize', draw);
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
      new ResizeObserver(draw).observe(wrap);
    }})();
    """


def _scatter_js(chart):
    """Chart.js native scatter — one dataset per status so the legend reads
    as good/warning/critical instead of one undifferentiated point cloud.
    Points carry a `label` (the KPI/entity name) for the tooltip.

    Optional per-chart overrides for quadrant-style scatters (e.g. a
    risk-vs-value matrix): `status_labels` (dict, merged over the generic
    defaults), `point_radius`/`point_alpha` (denser point clouds need smaller,
    semi-transparent markers), `quadrant_lines` ({"x": v, "y": v} data-value
    dashed dividers), and `quadrant_labels` (list of {"corner", "text"} corner
    annotations, corner in top-left/top-right/bottom-left/bottom-right)."""
    cid = chart["id"]
    points = chart["points"]
    x_label = chart.get("x_label", "")
    y_label = chart.get("y_label", "")
    x_unit = chart.get("x_unit", "")
    y_unit = chart.get("y_unit", "")
    status_labels = {"good": "En meta", "warning": "Cerca de meta", "critical": "En riesgo"}
    status_labels.update(chart.get("status_labels", {}))
    point_radius = chart.get("point_radius", 6)
    point_alpha = chart.get("point_alpha", 1)
    quadrant_lines = json.dumps(chart.get("quadrant_lines"))
    quadrant_labels = json.dumps(chart.get("quadrant_labels", []), ensure_ascii=False)

    groups = {}
    order = []
    for p in points:
        status = p.get("status", "default")
        if status not in groups:
            groups[status] = []
            order.append(status)
        groups[status].append(p)

    datasets_js = []
    for status in order:
        pts = groups[status]
        color_l, color_d = STATUS.get(status, (CATEGORICAL_LIGHT[0], CATEGORICAL_DARK[0]))
        data = json.dumps([{"x": p["x"], "y": p["y"], "label": p.get("label", "")} for p in pts], ensure_ascii=False)
        label = json.dumps(status_labels.get(status, status), ensure_ascii=False)
        datasets_js.append(f"""{{
            label: {label},
            data: {data},
            backgroundColor: withAlpha(seriesColorHex({json.dumps(color_l)}, {json.dumps(color_d)}), {point_alpha}),
            borderColor: seriesColorHex({json.dumps(color_l)}, {json.dumps(color_d)}),
            pointRadius: {point_radius},
            pointHoverRadius: {point_radius + 2},
        }}""")
    datasets_str = ",\n".join(datasets_js)

    return f"""
    (function() {{
      const quadrantLines_{cid} = {quadrant_lines};
      const quadrantLabels_{cid} = {quadrant_labels};
      new Chart(document.getElementById('{cid}').getContext('2d'), {{
        type: 'scatter',
        data: {{ datasets: [{datasets_str}] }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ display: true, position: 'top', align: 'start',
                       labels: {{ color: inkColor('secondary'), boxWidth: 12, usePointStyle: true }} }},
            tooltip: {{
              backgroundColor: surfaceColor(), titleColor: inkColor('primary'), bodyColor: inkColor('secondary'),
              borderColor: inkColor('grid'), borderWidth: 1, padding: 10,
              callbacks: {{
                label: (ctx) => `${{ctx.raw.label}}: ${{ctx.parsed.x.toFixed(1)}}{x_unit}, ${{ctx.parsed.y.toFixed(1)}}{y_unit}`
              }}
            }}
          }},
          scales: {{
            x: {{ title: {{ display: {str(bool(x_label)).lower()}, text: {json.dumps(x_label, ensure_ascii=False)}, color: inkColor('secondary') }},
                  grid: {{ color: inkColor('grid') }}, ticks: {{ color: inkColor('muted') }} }},
            y: {{ title: {{ display: {str(bool(y_label)).lower()}, text: {json.dumps(y_label, ensure_ascii=False)}, color: inkColor('secondary') }},
                  grid: {{ color: inkColor('grid') }}, ticks: {{ color: inkColor('muted') }} }}
          }}
        }},
        plugins: [{{
          id: 'quadrantOverlay_{cid}',
          afterDraw: (chartInstance) => {{
            const {{ ctx, chartArea }} = chartInstance;
            if (!chartArea) return;
            const {{ left, right, top, bottom }} = chartArea;
            const scales = chartInstance.scales;
            ctx.save();
            if (quadrantLines_{cid}) {{
              ctx.strokeStyle = withAlpha(inkColor('grid'), 0.55);
              ctx.setLineDash([4, 4]);
              ctx.lineWidth = 1;
              if (quadrantLines_{cid}.x !== undefined && quadrantLines_{cid}.x !== null) {{
                const xPix = scales.x.getPixelForValue(quadrantLines_{cid}.x);
                ctx.beginPath(); ctx.moveTo(xPix, top); ctx.lineTo(xPix, bottom); ctx.stroke();
              }}
              if (quadrantLines_{cid}.y !== undefined && quadrantLines_{cid}.y !== null) {{
                const yPix = scales.y.getPixelForValue(quadrantLines_{cid}.y);
                ctx.beginPath(); ctx.moveTo(left, yPix); ctx.lineTo(right, yPix); ctx.stroke();
              }}
              ctx.setLineDash([]);
            }}
            if (quadrantLabels_{cid}.length) {{
              ctx.font = '700 10px -apple-system, sans-serif';
              ctx.fillStyle = withAlpha(inkColor('muted'), 0.95);
              const pad = 10;
              quadrantLabels_{cid}.forEach((q) => {{
                let x, y, align;
                if (q.corner === 'top-left') {{ x = left + pad; y = top + pad + 9; align = 'left'; }}
                else if (q.corner === 'top-right') {{ x = right - pad; y = top + pad + 9; align = 'right'; }}
                else if (q.corner === 'bottom-left') {{ x = left + pad; y = bottom - pad; align = 'left'; }}
                else {{ x = right - pad; y = bottom - pad; align = 'right'; }}
                ctx.textAlign = align;
                ctx.fillText(q.text, x, y);
              }});
            }}
            ctx.restore();
          }}
        }}]
      }});
    }})();
    """


def _heatmap_js(chart):
    """No native Chart.js heatmap — drawn on canvas like the funnel chart.

    Two shapes: a square correlation matrix (`labels` shared by both axes,
    values in [-1, 1], `color_mode` defaults to "diverging" — teal for
    positive, gold for negative) or a rectangular matrix (`row_labels` +
    `col_labels`, independent lengths, e.g. category x weekday). Alpha is
    always scaled against the matrix's own max magnitude, so a rectangular
    matrix with values outside [-1, 1] (an index, a deviation in pp) still
    renders with a full-intensity range instead of clipping to alpha=1.
    `color_mode="sequential"` uses a single teal hue (no negative/gold
    branch) for intensity-only data (e.g. raw counts). `value_format="int"`
    renders whole numbers (with a +/- sign for diverging data) instead of
    the 2-decimal correlation format.
    """
    cid = chart["id"]
    row_labels = chart.get("row_labels", chart.get("labels", []))
    col_labels = chart.get("col_labels", chart.get("labels", []))
    row_labels_js = json.dumps(row_labels, ensure_ascii=False)
    col_labels_js = json.dumps(col_labels, ensure_ascii=False)
    matrix = json.dumps(chart["matrix"])
    diverging = "true" if chart.get("color_mode", "diverging") == "diverging" else "false"
    int_format = "true" if chart.get("value_format") == "int" else "false"
    return f"""
    (function() {{
      const canvas = document.getElementById('{cid}');
      const wrap = canvas.parentElement;
      const rowLabels = {row_labels_js};
      const colLabels = {col_labels_js};
      const matrix = {matrix};
      const nRows = rowLabels.length, nCols = colLabels.length;
      const diverging = {diverging};
      const intFormat = {int_format};
      let maxAbs = 0;
      matrix.forEach(row => row.forEach(v => {{ maxAbs = Math.max(maxAbs, Math.abs(v)); }}));
      maxAbs = maxAbs || 1;

      function cellColor(v) {{
        const alpha = Math.min(Math.abs(v) / maxAbs, 1);
        const teal = isDark() ? [143, 194, 188] : [113, 168, 163];
        const gold = isDark() ? [212, 169, 79] : [184, 132, 44];
        const [r, g, b] = (diverging && v < 0) ? gold : teal;
        return `rgba(${{r}},${{g}},${{b}},${{(0.10 + alpha * 0.80).toFixed(2)}})`;
      }}

      function fmt(v) {{
        if (intFormat) {{
          const sign = diverging && v >= 0 ? '+' : '';
          return sign + Math.round(v).toLocaleString('es-MX');
        }}
        return v.toFixed(2);
      }}

      function draw() {{
        const dpr = window.devicePixelRatio || 1;
        const w = wrap.clientWidth, h = wrap.clientHeight;
        canvas.width = w * dpr; canvas.height = h * dpr;
        canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);

        const padLeft = Math.min(150, w * 0.28);
        const padTop = 8;
        const padBottom = 30;
        const gridW = w - padLeft - 12;
        const gridH = h - padTop - padBottom;
        const cellW = gridW / nCols;
        const cellH = gridH / nRows;
        const gap = 3;

        for (let i = 0; i < nRows; i++) {{
          for (let j = 0; j < nCols; j++) {{
            const x = padLeft + j * cellW, y = padTop + i * cellH;
            ctx.fillStyle = cellColor(matrix[i][j]);
            ctx.fillRect(x, y, cellW - gap, cellH - gap);
            ctx.fillStyle = inkColor('primary');
            ctx.font = '600 11px -apple-system, sans-serif';
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(fmt(matrix[i][j]), x + (cellW - gap) / 2, y + (cellH - gap) / 2);
          }}
        }}

        ctx.fillStyle = inkColor('secondary');
        ctx.font = '600 11px -apple-system, sans-serif';
        for (let i = 0; i < nRows; i++) {{
          ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
          ctx.fillText(rowLabels[i], padLeft - 10, padTop + i * cellH + (cellH - gap) / 2);
        }}
        for (let j = 0; j < nCols; j++) {{
          ctx.textAlign = 'center'; ctx.textBaseline = 'top';
          ctx.fillText(colLabels[j], padLeft + j * cellW + (cellW - gap) / 2, padTop + nRows * cellH + 6);
        }}
      }}

      draw();
      window.addEventListener('resize', draw);
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
      new ResizeObserver(draw).observe(wrap);
    }})();
    """


def _chart_js(chart):
    if chart["type"] == "funnel":
        return _funnel_js(chart)
    if chart["type"] == "scatter":
        return _scatter_js(chart)
    if chart["type"] == "heatmap":
        return _heatmap_js(chart)
    cid = chart["id"]
    ctype = chart["type"]
    horizontal = bool(chart.get("horizontal"))
    value_format = chart.get("value_format")
    labels = json.dumps(chart["labels"], ensure_ascii=False)
    datasets_js = []
    for i, ds in enumerate(chart["datasets"]):
        # color_index lets a single-dataset chart (e.g. a per-KPI drill-down)
        # borrow the same palette slot another chart uses for that series
        # (e.g. its area's line in the "cumplimiento por área" chart),
        # instead of always defaulting to slot 0.
        color_idx = ds.get("color_index", i)
        color_l = CATEGORICAL_LIGHT[color_idx % len(CATEGORICAL_LIGHT)]
        color_d = CATEGORICAL_DARK[color_idx % len(CATEGORICAL_DARK)]
        data = json.dumps(ds["data"])
        label = json.dumps(ds["label"], ensure_ascii=False)
        fill = "true" if ctype == "line" and ds.get("fill") else "false"
        tension = ds.get("tension", 0.3 if ctype == "line" else 0)
        muted = bool(ds.get("muted"))
        emphasis = bool(ds.get("emphasis"))

        if ds.get("colors"):
            bg = json.dumps(ds["colors"])
            border = json.dumps(ds["colors"])
        elif muted:
            bg = "withAlpha(inkColor('muted'), 0.12)"
            border = "withAlpha(inkColor('muted'), 0.75)"
        else:
            bg = f"seriesColor({color_idx}, {json.dumps(color_l)}, {json.dumps(color_d)}, {0.85 if ctype != 'line' else 0.12})"
            border = f"seriesColor({color_idx}, {json.dumps(color_l)}, {json.dumps(color_d)}, 1)"

        border_width = 3 if emphasis else (1.5 if muted else (2 if ctype == "line" else 1))
        point_radius = (0 if ctype != "line" else (4 if emphasis else (0 if muted else 3)))
        border_dash = "[3, 3]" if (muted and ctype == "line") else "[]"
        value_labels = json.dumps(ds["value_labels"], ensure_ascii=False) if ds.get("value_labels") else "null"

        datasets_js.append(f"""{{
            label: {label},
            data: {data},
            valueLabels: {value_labels},
            backgroundColor: {bg},
            borderColor: {border},
            borderWidth: {border_width},
            borderDash: {border_dash},
            borderRadius: {4 if ctype == 'bar' else 0},
            fill: {fill},
            tension: {tension},
            pointRadius: {point_radius},
            pointHoverRadius: 5,
        }}""")
    datasets_str = ",\n".join(datasets_js)
    y_label = chart.get("y_label", "")
    stacked = "true" if chart.get("stacked") else "false"
    value_max = chart.get("value_max")
    value_min = chart.get("value_min")
    tick_callback = (
        ", callback: (v) => v + '%'" if value_format == "percent" else
        ", callback: (v) => Math.abs(v)" if value_format == "abs_count" else
        ""
    )
    tooltip_callback = (
        "label: (ctx) => `${ctx.dataset.label}: ${ctx.formattedValue}%`" if value_format == "percent" else
        "label: (ctx) => `${ctx.dataset.label}: $${Number(ctx.parsed[ctx.chart.options.indexAxis === 'y' ? 'x' : 'y']).toLocaleString('es-MX')}`" if value_format == "currency" else
        "label: (ctx) => `${ctx.dataset.label}: ${Math.abs(ctx.parsed[ctx.chart.options.indexAxis === 'y' ? 'x' : 'y'])} clientes`" if value_format == "abs_count" else
        ""
    )
    value_axis = "x" if horizontal else "y"
    category_axis = "y" if horizontal else "x"
    index_axis_opt = "indexAxis: 'y'," if horizontal else ""
    tooltip_callbacks_js = f",\n                      callbacks: {{ {tooltip_callback} }}" if tooltip_callback else ""
    suggested_max_js = f", suggestedMax: {json.dumps(value_max)}" if value_max is not None else ""
    suggested_min_js = f", suggestedMin: {json.dumps(value_min)}" if value_min is not None else ""

    annotate_parts = []
    if chart.get("value_labels"):
        annotate_parts.append("""
      chart.data.datasets.forEach((dataset, di) => {
        if (!dataset.valueLabels) return;
        const meta = chart.getDatasetMeta(di);
        const horiz = chart.options.indexAxis === 'y';
        meta.data.forEach((el, i) => {
          const vl = dataset.valueLabels[i];
          if (vl === undefined) return;
          ctx.fillStyle = inkColor('primary');
          ctx.font = '600 12px -apple-system, sans-serif';
          if (horiz) {
            ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
            ctx.fillText(vl, el.x + 8, el.y);
          } else {
            ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
            ctx.fillText(vl, el.x, el.y - 6);
          }
        });
      });""")
    if chart.get("reference_line"):
        ref = chart["reference_line"]
        annotate_parts.append(f"""
      {{
        const val = {json.dumps(ref["value"])};
        const horiz = chart.options.indexAxis === 'y';
        const axisScale = horiz ? scales.x : scales.y;
        ctx.strokeStyle = inkColor('muted');
        ctx.setLineDash([5, 4]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        if (horiz) {{
          const px = axisScale.getPixelForValue(val);
          ctx.moveTo(px, chartArea.top); ctx.lineTo(px, chartArea.bottom);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = inkColor('secondary');
          ctx.font = '600 11px -apple-system, sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText({json.dumps(ref["label"], ensure_ascii=False)}, px, chartArea.top - 8);
        }} else {{
          const py = axisScale.getPixelForValue(val);
          ctx.moveTo(chartArea.left, py); ctx.lineTo(chartArea.right, py);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = inkColor('secondary');
          ctx.font = '600 11px -apple-system, sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText({json.dumps(ref["label"], ensure_ascii=False)}, chartArea.left + 4, py - 6);
        }}
      }}""")
    if chart.get("marker"):
        mk = chart["marker"]
        annotate_parts.append(f"""
      {{
        const px = scales.x.getPixelForValue({json.dumps(mk["index"])});
        ctx.strokeStyle = withAlpha(inkColor('muted'), 0.7);
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px, chartArea.top); ctx.lineTo(px, chartArea.bottom);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = inkColor('secondary');
        ctx.font = '600 11px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText({json.dumps(mk["label"], ensure_ascii=False)}, px, chartArea.top + 12);
      }}""")
    annotate_plugin = ""
    if annotate_parts:
        annotate_plugin = f"""
      plugins: [{{
        id: 'xiaAnnotate_{cid}',
        afterDatasetsDraw(chart) {{
          const {{ ctx, chartArea, scales }} = chart;
          ctx.save();
          {"".join(annotate_parts)}
          ctx.restore();
        }}
      }}],"""

    return f"""
    new Chart(document.getElementById('{cid}').getContext('2d'), {{
      type: {json.dumps('bar' if ctype == 'stacked-bar' else ctype)},
      data: {{
        labels: {labels},
        datasets: [{datasets_str}]
      }},{annotate_plugin}
      options: {{
        {index_axis_opt}
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: {str(len(chart["datasets"]) > 1).lower()}, position: 'top', align: 'start',
                     labels: {{ color: inkColor('secondary'), boxWidth: 12, usePointStyle: true }} }},
          tooltip: {{ backgroundColor: surfaceColor(), titleColor: inkColor('primary'), bodyColor: inkColor('secondary'),
                      borderColor: inkColor('grid'), borderWidth: 1, padding: 10{tooltip_callbacks_js} }}
        }},
        scales: {{
          {category_axis}: {{ stacked: {stacked}, grid: {{ display: false }}, ticks: {{ color: inkColor('muted') }} }},
          {value_axis}: {{
            stacked: {stacked},
            grid: {{ color: inkColor('grid') }},
            ticks: {{ color: inkColor('muted'){tick_callback} }},
            title: {{ display: {str(bool(y_label)).lower()}, text: {json.dumps(y_label, ensure_ascii=False)}, color: inkColor('secondary') }}{suggested_max_js}{suggested_min_js}
          }}
        }}
      }}
    }});
    """


def _banner_html(banner):
    """Banner de 'la respuesta primero' (principio de la pirámide de Minto):
    va arriba de todo, antes incluso de los KPIs, para que la conclusión
    accionable de la semana se lea sin tener que interpretar ningún gráfico."""
    if not banner:
        return ""
    label = banner.get("label", "Esta semana")
    return f"""
    <div class="minto-banner">
      <p class="minto-label">{label}</p>
      <h2>{banner["headline"]}</h2>
      <p class="minto-sub">{banner.get("subtext", "")}</p>
    </div>
    """


def _checklist_html(checklist):
    """Lista de tareas con checkboxes persistidos en localStorage (por
    navegador, sin backend) -- convierte la tabla estática de 'top clientes'
    en una herramienta de seguimiento diario real: marcar, ver progreso,
    y que quede marcado la próxima vez que se abra el dashboard."""
    if not checklist:
        return ""
    cid = checklist["id"]
    headers = "".join(f"<th>{h}</th>" for h in checklist["headers"])
    rows_html = []
    for row in checklist["rows"]:
        cells = "".join(f"<td>{c}</td>" for c in row["cells"])
        rows_html.append(
            f'<tr data-row="{row["id"]}">'
            f'<td class="check-col"><input type="checkbox" class="xia-check" data-scope="{cid}" data-row="{row["id"]}"></td>'
            f'{cells}</tr>'
        )
    total = len(checklist["rows"])
    return f"""
    <div class="checklist-card">
      <h3>{checklist["title"]}</h3>
      <p class="checklist-sub">{checklist.get("subtitle", "")}</p>
      <div class="checklist-progress">
        <div class="progress-bar"><div class="progress-fill" id="{cid}-fill" style="width:0%"></div></div>
        <span id="{cid}-count">0 / {total} {checklist.get("progress_noun", "contactados")}</span>
      </div>
      <div class="checklist-table-wrap">
        <table class="checklist-table">
          <thead><tr><th></th>{headers}</tr></thead>
          <tbody>{"".join(rows_html)}</tbody>
        </table>
      </div>
    </div>
    """


def _checklist_js(checklist):
    if not checklist:
        return ""
    cid = checklist["id"]
    total = len(checklist["rows"])
    noun = json.dumps(checklist.get("progress_noun", "contactados"), ensure_ascii=False)
    return f"""
    (function() {{
      const scopeId = {json.dumps(cid)};
      const total = {total};
      const storageKey = 'xia_checklist_' + scopeId;
      let state = {{}};
      try {{ state = JSON.parse(localStorage.getItem(storageKey) || '{{}}'); }} catch (e) {{}}
      const boxes = document.querySelectorAll(`input.xia-check[data-scope="${{scopeId}}"]`);
      function updateProgress() {{
        const checked = document.querySelectorAll(`input.xia-check[data-scope="${{scopeId}}"]:checked`).length;
        const fill = document.getElementById(scopeId + '-fill');
        const count = document.getElementById(scopeId + '-count');
        if (fill) fill.style.width = (total ? (checked / total * 100) : 0) + '%';
        if (count) count.textContent = `${{checked}} / ${{total}} ${{{noun}}}`;
      }}
      boxes.forEach((b) => {{
        const rowId = b.dataset.row;
        if (state[rowId]) {{
          b.checked = true;
          const tr = b.closest('tr');
          if (tr) tr.classList.add('done');
        }}
        b.addEventListener('change', () => {{
          state[rowId] = b.checked;
          try {{ localStorage.setItem(storageKey, JSON.stringify(state)); }} catch (e) {{}}
          const tr = b.closest('tr');
          if (tr) tr.classList.toggle('done', b.checked);
          updateProgress();
        }});
      }});
      updateProgress();
    }})();
    """


def _explorer_html(explorer):
    """Category -> top-N table -> per-item demand chart, all client-side.
    One dropdown (category) drives a ranked table; clicking a row swaps the
    line chart below it (history + forecast) for that item — a drill-down
    explorer for a catalog too large to chart item-by-item on the page."""
    if not explorer:
        return ""
    eid = explorer["id"]
    headers = "".join(f"<th>{h}</th>" for h in explorer["table_headers"])
    options = "".join(f'<option value="{c}">{c}</option>' for c in explorer["categories"])
    return f"""
    <div class="explorer-card" id="{eid}">
      <h3>{explorer["title"]}</h3>
      <p class="checklist-sub">{explorer.get("subtitle", "")}</p>
      <div class="explorer-controls">
        <label for="{eid}-cat">Categoría</label>
        <select id="{eid}-cat" class="explorer-select">{options}</select>
      </div>
      <div class="explorer-grid">
        <div class="explorer-table-wrap">
          <table class="checklist-table explorer-table">
            <thead><tr><th></th>{headers}</tr></thead>
            <tbody id="{eid}-tbody"></tbody>
          </table>
        </div>
        <div class="explorer-chart-card">
          <div class="chart-head">
            <h4 id="{eid}-chart-title">Demanda</h4>
            <p id="{eid}-chart-sub"></p>
          </div>
          <div class="chart-canvas-wrap">
            <canvas id="{eid}-canvas"></canvas>
          </div>
        </div>
      </div>
    </div>
    """


def _explorer_js(explorer):
    if not explorer:
        return ""
    eid = explorer["id"]
    data = json.dumps({
        "categories": explorer["categories"],
        "topByCategory": explorer["top_by_category"],
        "histDates": explorer["hist_dates"],
        "forecastDates": explorer["forecast_dates"],
        "demand": explorer["demand"],
        "rowFields": explorer["row_fields"],
    }, ensure_ascii=False)
    hist_light, hist_dark = CATEGORICAL_LIGHT[0], CATEGORICAL_DARK[0]
    forecast_color = STATUS["critical"]
    return f"""
    (function() {{
      const D = {data};
      const eid = {json.dumps(eid)};
      const catSelect = document.getElementById(eid + '-cat');
      const tbody = document.getElementById(eid + '-tbody');
      const chartTitle = document.getElementById(eid + '-chart-title');
      const chartSub = document.getElementById(eid + '-chart-sub');
      let chart = null;
      let selectedSku = null;

      function renderTable(cat) {{
        const rows = D.topByCategory[cat] || [];
        tbody.innerHTML = '';
        rows.forEach((r, i) => {{
          const tr = document.createElement('tr');
          tr.dataset.sku = r.sku;
          const cells = D.rowFields.map(f => `<td>${{r[f]}}</td>`).join('');
          tr.innerHTML = `<td class="rank-col">${{i + 1}}</td>${{cells}}`;
          tr.addEventListener('click', () => selectSku(r.sku, cat));
          tbody.appendChild(tr);
        }});
        if (rows.length) selectSku(rows[0].sku, cat);
      }}

      function selectSku(sku, cat) {{
        selectedSku = sku;
        tbody.querySelectorAll('tr').forEach(tr => tr.classList.toggle('selected', tr.dataset.sku === sku));
        const d = D.demand[sku];
        if (!d) return;
        chartTitle.textContent = `Demanda: ${{sku}}`;
        chartSub.textContent = `${{cat}} — histórico (${{D.histDates.length}} días) + pronóstico (${{D.forecastDates.length}} días)`;
        const labels = D.histDates.concat(D.forecastDates);
        const histData = d.hist.concat(Array(D.forecastDates.length).fill(null));
        const forecastData = Array(D.histDates.length - 1).fill(null).concat([d.hist[d.hist.length - 1]]).concat(d.forecast);
        if (chart) chart.destroy();
        chart = new Chart(document.getElementById(eid + '-canvas').getContext('2d'), {{
          type: 'line',
          data: {{
            labels: labels,
            datasets: [
              {{ label: 'Histórico', data: histData, borderColor: seriesColorHex({json.dumps(hist_light)}, {json.dumps(hist_dark)}),
                 backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.25 }},
              {{ label: 'Pronóstico', data: forecastData, borderColor: {json.dumps(forecast_color)},
                 backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 4], pointRadius: 0, tension: 0.25 }},
            ]
          }},
          options: {{
            responsive: true, maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{
              legend: {{ display: true, position: 'top', align: 'start',
                         labels: {{ color: inkColor('secondary'), boxWidth: 12, usePointStyle: true }} }},
              tooltip: {{ backgroundColor: surfaceColor(), titleColor: inkColor('primary'), bodyColor: inkColor('secondary'),
                          borderColor: inkColor('grid'), borderWidth: 1, padding: 10 }}
            }},
            scales: {{
              x: {{ grid: {{ display: false }}, ticks: {{ color: inkColor('muted'), maxTicksLimit: 10 }} }},
              y: {{ grid: {{ color: inkColor('grid') }}, ticks: {{ color: inkColor('muted') }}, title: {{ display: true, text: 'Unidades/día', color: inkColor('secondary') }} }}
            }}
          }}
        }});
      }}

      catSelect.addEventListener('change', () => renderTable(catSelect.value));
      renderTable(D.categories[0]);
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {{ if (selectedSku) selectSku(selectedSku, catSelect.value); }});
    }})();
    """


TEMPLATE = """<!doctype html>
<html lang="es"{html_theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<script src="{chartjs_url}"></script>
<style>
  :root {{
    color-scheme: light;
    --brand-ink: #163832;
    --brand-cream: #F6EFE1;
    --gold: #B8842C;
    --surface: #FFFFFF;
    --page: #F6EFE1;
    --text-primary: #163832;
    --text-secondary: #4A625D;
    --text-muted: #7E948F;
    --grid: rgba(22,56,50,0.15);
    --border: rgba(22,56,50,0.12);
    --accent: #71A8A3;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      color-scheme: dark;
      --surface: #163832;
      --page: #0E1F1B;
      --text-primary: #F6EFE1;
      --text-secondary: #C7D9D5;
      --text-muted: #8FA8A3;
      --grid: rgba(246,239,225,0.14);
      --border: rgba(246,239,225,0.12);
      --accent: #8FC2BC;
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --surface: #163832;
    --page: #0E1F1B;
    --text-primary: #F6EFE1;
    --text-secondary: #C7D9D5;
    --text-muted: #8FA8A3;
    --grid: rgba(246,239,225,0.14);
    --border: rgba(246,239,225,0.12);
    --accent: #8FC2BC;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--page); color: var(--text-primary);
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    padding: 32px 20px 60px;
  }}
  .wrap {{ max-width: 1080px; margin: 0 auto; }}
  .brand {{ display:flex; align-items:center; gap:10px; margin-bottom:22px; }}
  .brand .mark {{ width:28px; height:28px; border-radius:7px; background: var(--brand-ink);
                  display:flex; align-items:center; justify-content:center; color: var(--brand-cream); font-weight:700; font-size:13px; }}
  .brand span {{ color: var(--text-muted); font-size:13px; letter-spacing: .04em; text-transform: uppercase; }}
  header.page-head {{ margin-bottom: 28px; }}
  header.page-head .tag {{ color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
  header.page-head h1 {{ font-size: 26px; margin: 0 0 8px; }}
  header.page-head p.tagline {{ color: var(--text-secondary); font-size: 15px; max-width: 720px; margin: 0; line-height:1.5; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .top-row {{ display: grid; grid-template-columns: minmax(220px, 300px) 1fr; gap: 14px; margin-bottom: 28px; align-items: stretch; }}
  .hero-widget {{ background: var(--surface); border: 1px solid var(--gold); border-radius: 10px; padding: 16px 18px; display: flex; flex-direction: column; }}
  .hero-widget .hero-value {{ color: var(--gold); }}
  .hero-chart-wrap {{ position: relative; flex: 1; min-height: 130px; margin-top: 12px; }}
  .kpi-grid-5 {{ display: grid; grid-template-columns: repeat(5, 1fr); grid-auto-rows: 1fr; gap: 14px; }}
  .kpi-grid-5 .kpi-card {{ padding: 12px 14px; }}
  .kpi-grid-5 .kpi-label {{ font-size: 10.5px; }}
  .kpi-grid-5 .kpi-value {{ font-size: 18px; }}
  @media (max-width: 860px) {{
    .top-row {{ grid-template-columns: 1fr; }}
    .kpi-grid-5 {{ grid-template-columns: repeat(3, 1fr); }}
  }}
  @media (max-width: 520px) {{
    .kpi-grid-5 {{ grid-template-columns: repeat(2, 1fr); }}
    .drilldown-grid {{ grid-template-columns: 1fr !important; }}
  }}
  .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; position: relative; }}
  .kpi-hero {{ border: 1px solid var(--gold); }}
  .kpi-hero .kpi-value {{ color: var(--gold); }}
  .kpi-label {{ color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 26px; font-weight: 600; }}
  .kpi-delta {{ font-size: 13px; margin-top: 4px; font-weight: 600; }}
  .delta-up {{ color: #2f6e57; }}
  .delta-down {{ color: #d03b3b; }}
  .kpi-badge {{ display:inline-block; margin-top:8px; font-size: 11px; font-weight: 700; text-transform: uppercase;
                letter-spacing: .03em; padding: 3px 8px; border-radius: 999px; }}
  .kpi-good {{ background: rgba(62,143,114,0.16); color: #2f6e57; }}
  .kpi-warning {{ background: rgba(184,132,44,0.18); color: #8c6220; }}
  .kpi-serious {{ background: rgba(140,90,30,0.18); color: #6b4517; }}
  .kpi-critical {{ background: rgba(208,59,59,0.14); color: #d03b3b; }}
  .minto-banner {{ background: var(--surface); border: 1px solid var(--border); border-left: 5px solid var(--gold);
                   border-radius: 10px; padding: 18px 22px; margin-bottom: 22px; }}
  .minto-banner .minto-label {{ margin: 0 0 6px; color: var(--gold); font-size: 12px; font-weight: 700;
                                 text-transform: uppercase; letter-spacing: .06em; }}
  .minto-banner h2 {{ margin: 0 0 8px; font-size: 21px; line-height: 1.35; color: var(--text-primary); }}
  .minto-banner p.minto-sub {{ margin: 0; color: var(--text-secondary); font-size: 14px; line-height: 1.55; max-width: 780px; }}
  .checklist-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
                      padding: 18px 22px; margin-bottom: 22px; }}
  .checklist-card h3 {{ margin: 0 0 2px; font-size: 16px; }}
  .checklist-card p.checklist-sub {{ margin: 0 0 14px; color: var(--text-muted); font-size: 13px; }}
  .checklist-progress {{ display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }}
  .progress-bar {{ flex: 1; max-width: 320px; height: 8px; border-radius: 999px; background: var(--grid); overflow: hidden; }}
  .progress-fill {{ height: 100%; background: var(--accent); border-radius: 999px; transition: width .2s ease; }}
  .checklist-progress span {{ color: var(--text-secondary); font-size: 13px; font-weight: 600; white-space: nowrap; }}
  .checklist-table-wrap {{ overflow-x: auto; }}
  table.checklist-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  table.checklist-table th, table.checklist-table td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--grid); color: var(--text-secondary); }}
  table.checklist-table th {{ color: var(--text-muted); text-transform: uppercase; font-size: 11px; letter-spacing: .03em; }}
  table.checklist-table td.check-col {{ width: 30px; }}
  table.checklist-table input.xia-check {{ width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; }}
  table.checklist-table tr.done td {{ color: var(--text-muted); text-decoration: line-through; opacity: .7; }}
  table.checklist-table tr.done td.check-col {{ text-decoration: none; }}
  .explorer-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
                     padding: 18px 22px; margin-bottom: 22px; }}
  .explorer-card h3 {{ margin: 0 0 2px; font-size: 16px; }}
  .explorer-card p.checklist-sub {{ margin: 0 0 14px; color: var(--text-muted); font-size: 13px; }}
  .explorer-controls {{ display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }}
  .explorer-controls label {{ color: var(--text-secondary); font-size: 13px; font-weight: 600; }}
  .explorer-select {{ background: var(--page); color: var(--text-primary); border: 1px solid var(--border);
                       border-radius: 8px; padding: 7px 10px; font-size: 13.5px; font-family: inherit; cursor: pointer; }}
  .explorer-grid {{ display: grid; grid-template-columns: minmax(260px, 380px) 1fr; gap: 18px; align-items: start; }}
  .explorer-table-wrap {{ overflow-x: auto; }}
  table.explorer-table tr {{ cursor: pointer; }}
  table.explorer-table tr:hover td {{ color: var(--text-primary); }}
  table.explorer-table tr.selected td {{ color: var(--text-primary); font-weight: 600; }}
  table.explorer-table tr.selected {{ background: var(--page); }}
  table.explorer-table td.rank-col {{ color: var(--text-muted); width: 22px; }}
  .explorer-chart-card {{ background: var(--page); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
  .explorer-chart-card .chart-head h4 {{ margin: 0 0 2px; font-size: 14.5px; color: var(--text-primary); }}
  .explorer-chart-card .chart-head p {{ margin: 0 0 10px; color: var(--text-muted); font-size: 12px; }}
  @media (max-width: 760px) {{ .explorer-grid {{ grid-template-columns: 1fr; }} }}
  .charts-grid {{ display: grid; grid-template-columns: {chart_grid_cols}; gap: 18px; margin-bottom: 26px; }}
  .chart-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }}
  .chart-card-wide {{ grid-column: 1 / -1; }}
  .chart-head h3 {{ margin: 0 0 2px; font-size: 15px; }}
  .chart-head p {{ margin: 0 0 12px; color: var(--text-muted); font-size: 12.5px; }}
  .chart-canvas-wrap {{ position: relative; height: 280px; }}
  .section-label {{ color: var(--text-muted); font-size: 13px; text-transform: uppercase; letter-spacing: .04em; margin: 0 0 12px; }}
  .drilldown-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-bottom: 26px; }}
  .drilldown-grid .chart-card {{ padding: 14px 16px; }}
  .drilldown-grid .chart-head h3 {{ font-size: 13.5px; }}
  .drilldown-grid .chart-head p {{ margin: 0 0 8px; font-size: 11.5px; }}
  .drilldown-grid .chart-canvas-wrap {{ height: 190px; }}
  .insights-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px 22px; margin-bottom: 22px; }}
  .insights-card h3 {{ margin: 0 0 10px; font-size: 14px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted); }}
  ul.insights {{ margin: 0; padding-left: 18px; color: var(--text-secondary); line-height: 1.65; font-size: 14.5px; }}
  ul.insights li::marker {{ color: var(--accent); }}
  .table-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 18px; margin-bottom: 22px; }}
  .table-wrap summary {{ cursor: pointer; color: var(--text-secondary); font-size: 13.5px; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
  th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--grid); color: var(--text-secondary); }}
  th {{ color: var(--text-muted); text-transform: uppercase; font-size: 11px; letter-spacing: .03em; }}
  footer {{ color: var(--text-muted); font-size: 12px; margin-top: 30px; border-top: 1px solid var(--border); padding-top: 16px; }}
  footer a {{ color: var(--text-primary); text-decoration: underline; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand"><div class="mark">X</div><span>XIA Insights &times; Analytics &mdash; Portfolio Demo</span></div>
  <header class="page-head">
    <div class="tag">{tag}</div>
    <h1>{title}</h1>
    <p class="tagline">{tagline}</p>
  </header>

  {banner_html}

  {top_html}

  {table_top_html}

  <div class="charts-grid">
    {chart_blocks}
  </div>

  {drilldown_html}

  <div class="insights-card">
    <h3>Lo que dice el dato</h3>
    {insights_html}
  </div>

  {table_bottom_html}

  {checklist_html}

  {explorer_html}

  <footer>
    Dataset sintético generado para fines demostrativos. Servicio real: Data Storytelling Express / Micro Data Office &middot;
    <a href="mailto:xianalytics20@gmail.com">xianalytics20@gmail.com</a> &middot; WhatsApp +52 55 3566 6166
  </footer>
</div>

<script>
function isDark() {{
  const t = document.documentElement.getAttribute('data-theme');
  if (t === 'dark') return true;
  if (t === 'light') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}}
function withAlpha(hex, alpha) {{
  if (alpha >= 1) return hex;
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{alpha}})`;
}}
function seriesColor(i, light, dark, alpha) {{
  const hex = isDark() ? dark : light;
  return withAlpha(hex, alpha);
}}
function seriesColorHex(light, dark) {{ return isDark() ? dark : light; }}
function cssVar(name) {{ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }}
function inkColor(role) {{
  return {{ primary: cssVar('--text-primary'), secondary: cssVar('--text-secondary'),
            muted: cssVar('--text-muted'), grid: cssVar('--grid') }}[role];
}}
function surfaceColor() {{ return cssVar('--surface'); }}

{charts_js}
</script>
</body>
</html>
"""


def render(filename, project_no, title, tagline, kpis, charts, insights, table=None, chart_cols=2,
           hero_kpi=None, hero_chart=None, drilldown_charts=None, drilldown_title=None,
           banner=None, checklist=None, table_position="bottom", explorer=None, default_theme=None):
    tag = f"Proyecto {project_no:02d} · Portafolio de demostración"
    # default_theme stamps data-theme on <html> so the page ignores the
    # viewer's OS/browser preference and always opens in that theme (still
    # toggleable by whatever in-page control reads/writes the attribute).
    # Leave it None (every other project's current behavior) to follow
    # prefers-color-scheme instead.
    html_theme_attr = f' data-theme="{default_theme}"' if default_theme else ""

    banner_html = _banner_html(banner)
    checklist_html = _checklist_html(checklist)
    explorer_html = _explorer_html(explorer)

    extra_charts_js = []
    if checklist:
        extra_charts_js.append(_checklist_js(checklist))
    if explorer:
        extra_charts_js.append(_explorer_js(explorer))
    if hero_kpi and hero_chart:
        top_html = f"""<div class="top-row">
    {_hero_widget_html(hero_kpi, hero_chart["id"])}
    <div class="kpi-grid-5">
      {_kpi_html(kpis)}
    </div>
  </div>"""
        extra_charts_js.append(_chart_js(hero_chart))
    else:
        top_html = f'<div class="kpi-row">\n    {_kpi_html(kpis)}\n  </div>'

    chart_blocks = "\n".join(_chart_block(c, i) for i, c in enumerate(charts))
    charts_js_parts = extra_charts_js + [_chart_js(c) for c in charts]

    drilldown_html = ""
    if drilldown_charts:
        heading = f'<p class="section-label">{drilldown_title}</p>' if drilldown_title else ""
        blocks = "\n".join(_chart_block(c, i) for i, c in enumerate(drilldown_charts))
        drilldown_html = f'<div>\n    {heading}\n    <div class="drilldown-grid">\n      {blocks}\n    </div>\n  </div>'
        charts_js_parts += [_chart_js(c) for c in drilldown_charts]

    charts_js = "\n".join(charts_js_parts)
    insights_html = _insights_html(insights)
    # table_position="top" surfaces the segment/status summary right under
    # the KPIs, always expanded (Minto pyramid: the overview belongs with
    # the answer, not a "show more" toggle after the charts) — default
    # "bottom" keeps every other project's existing collapsed-table layout.
    table_top_html = _table_html(table, open=True) if (table and table_position == "top") else ""
    table_bottom_html = _table_html(table) if (table and table_position != "top") else ""
    grid_cols = "1fr" if chart_cols == 1 or len(charts) == 1 else "repeat(2, 1fr)"

    html = TEMPLATE.format(
        page_title=f"XIA · {title}",
        html_theme_attr=html_theme_attr,
        chartjs_url=CHARTJS_URL,
        tag=tag,
        title=title,
        tagline=tagline,
        banner_html=banner_html,
        top_html=top_html,
        checklist_html=checklist_html,
        chart_blocks=chart_blocks,
        chart_grid_cols=grid_cols,
        drilldown_html=drilldown_html,
        insights_html=insights_html,
        table_top_html=table_top_html,
        table_bottom_html=table_bottom_html,
        explorer_html=explorer_html,
        charts_js=charts_js,
    )
    Path(filename).write_text(html, encoding="utf-8")
    return filename
