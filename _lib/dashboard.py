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


def _insights_html(insights):
    items = "\n".join(f"<li>{i}</li>" for i in insights)
    return f'<ul class="insights">{items}</ul>'


def _table_html(table):
    if not table:
        return ""
    headers = "".join(f"<th>{h}</th>" for h in table["headers"])
    rows = ""
    for row in table["rows"]:
        cells = "".join(f"<td>{c}</td>" for c in row)
        rows += f"<tr>{cells}</tr>\n"
    return f"""
    <details class="table-wrap">
      <summary>Ver tabla de datos</summary>
      <table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </details>
    """


def _chart_block(chart, idx):
    cid = chart["id"]
    title = chart["title"]
    subtitle = chart.get("subtitle", "")
    return f"""
    <div class="chart-card">
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


def _chart_js(chart):
    if chart["type"] == "funnel":
        return _funnel_js(chart)
    cid = chart["id"]
    ctype = chart["type"]
    horizontal = bool(chart.get("horizontal"))
    value_format = chart.get("value_format")
    labels = json.dumps(chart["labels"], ensure_ascii=False)
    datasets_js = []
    for i, ds in enumerate(chart["datasets"]):
        color_l = CATEGORICAL_LIGHT[i % len(CATEGORICAL_LIGHT)]
        color_d = CATEGORICAL_DARK[i % len(CATEGORICAL_DARK)]
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
            bg = f"seriesColor({i}, {json.dumps(color_l)}, {json.dumps(color_d)}, {0.85 if ctype != 'line' else 0.12})"
            border = f"seriesColor({i}, {json.dumps(color_l)}, {json.dumps(color_d)}, 1)"

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
    tick_callback = ", callback: (v) => v + '%'" if value_format == "percent" else ""
    tooltip_callback = (
        "label: (ctx) => `${ctx.dataset.label}: ${ctx.formattedValue}%`" if value_format == "percent" else
        "label: (ctx) => `${ctx.dataset.label}: $${Number(ctx.parsed[ctx.chart.options.indexAxis === 'y' ? 'x' : 'y']).toLocaleString('es-MX')}`" if value_format == "currency" else
        ""
    )
    value_axis = "x" if horizontal else "y"
    category_axis = "y" if horizontal else "x"
    index_axis_opt = "indexAxis: 'y'," if horizontal else ""
    tooltip_callbacks_js = f",\n                      callbacks: {{ {tooltip_callback} }}" if tooltip_callback else ""
    suggested_max_js = f", suggestedMax: {json.dumps(value_max)}" if value_max is not None else ""

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
            ticks: {{ color: inkColor('muted') }}{tick_callback},
            title: {{ display: {str(bool(y_label)).lower()}, text: {json.dumps(y_label, ensure_ascii=False)}, color: inkColor('secondary') }}{suggested_max_js}
          }}
        }}
      }}
    }});
    """


TEMPLATE = """<!doctype html>
<html lang="es">
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
  .charts-grid {{ display: grid; grid-template-columns: {chart_grid_cols}; gap: 18px; margin-bottom: 26px; }}
  .chart-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }}
  .chart-head h3 {{ margin: 0 0 2px; font-size: 15px; }}
  .chart-head p {{ margin: 0 0 12px; color: var(--text-muted); font-size: 12.5px; }}
  .chart-canvas-wrap {{ position: relative; height: 280px; }}
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

  <div class="kpi-row">
    {kpi_html}
  </div>

  <div class="charts-grid">
    {chart_blocks}
  </div>

  <div class="insights-card">
    <h3>Lo que dice el dato</h3>
    {insights_html}
  </div>

  {table_html}

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


def render(filename, project_no, title, tagline, kpis, charts, insights, table=None, chart_cols=2):
    tag = f"Proyecto {project_no:02d} · Portafolio de demostración"
    kpi_html = _kpi_html(kpis)
    chart_blocks = "\n".join(_chart_block(c, i) for i, c in enumerate(charts))
    charts_js = "\n".join(_chart_js(c) for c in charts)
    insights_html = _insights_html(insights)
    table_html = _table_html(table) if table else ""
    grid_cols = "1fr" if chart_cols == 1 or len(charts) == 1 else "repeat(2, 1fr)"

    html = TEMPLATE.format(
        page_title=f"XIA · {title}",
        chartjs_url=CHARTJS_URL,
        tag=tag,
        title=title,
        tagline=tagline,
        kpi_html=kpi_html,
        chart_blocks=chart_blocks,
        chart_grid_cols=grid_cols,
        insights_html=insights_html,
        table_html=table_html,
        charts_js=charts_js,
    )
    Path(filename).write_text(html, encoding="utf-8")
    return filename
