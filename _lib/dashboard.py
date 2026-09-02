"""
XIA Insights x Analytics — shared, self-contained HTML dashboard renderer.

Every project in this portfolio calls `render()` with its own KPIs, charts,
insights and table. The template is shared so all 12 dashboards look like
one coherent product line instead of 12 one-off pages — same reasoning a
client would want from a real "Micro Data Office" engagement.

Design: validated categorical/status palette from the dataviz skill
(references/palette.md), fixed hue order, light + dark mode via CSS
variables, Chart.js (pinned, cdnjs) for the interactive charts, a plain
HTML table under each chart so the data is never color-only.
"""

import json
from pathlib import Path

CATEGORICAL_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
CATEGORICAL_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]

STATUS = {
    "good": ("#0ca30c", "#0ca30c"),
    "warning": ("#fab219", "#fab219"),
    "serious": ("#ec835a", "#ec835a"),
    "critical": ("#d03b3b", "#d03b3b"),
}

CHARTJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"


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
        cards.append(f"""
        <div class="kpi-card">
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


def _chart_js(chart):
    cid = chart["id"]
    ctype = chart["type"]
    labels = json.dumps(chart["labels"], ensure_ascii=False)
    datasets_js = []
    for i, ds in enumerate(chart["datasets"]):
        color_l = CATEGORICAL_LIGHT[i % len(CATEGORICAL_LIGHT)]
        color_d = CATEGORICAL_DARK[i % len(CATEGORICAL_DARK)]
        data = json.dumps(ds["data"])
        label = json.dumps(ds["label"], ensure_ascii=False)
        fill = "true" if ctype == "line" and ds.get("fill") else "false"
        tension = ds.get("tension", 0.3 if ctype == "line" else 0)
        datasets_js.append(f"""{{
            label: {label},
            data: {data},
            backgroundColor: seriesColor({i}, {json.dumps(color_l)}, {json.dumps(color_d)}, {0.85 if ctype != 'line' else 0.15}),
            borderColor: seriesColor({i}, {json.dumps(color_l)}, {json.dumps(color_d)}, 1),
            borderWidth: {2 if ctype == 'line' else 1},
            borderRadius: {4 if ctype == 'bar' else 0},
            fill: {fill},
            tension: {tension},
            pointRadius: {3 if ctype == 'line' else 0},
            pointHoverRadius: 5,
        }}""")
    datasets_str = ",\n".join(datasets_js)
    y_label = chart.get("y_label", "")
    stacked = "true" if chart.get("stacked") else "false"
    return f"""
    new Chart(document.getElementById('{cid}').getContext('2d'), {{
      type: {json.dumps('bar' if ctype == 'stacked-bar' else ctype)},
      data: {{
        labels: {labels},
        datasets: [{datasets_str}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: {str(len(chart["datasets"]) > 1).lower()}, position: 'top', align: 'start',
                     labels: {{ color: inkColor('secondary'), boxWidth: 12, usePointStyle: true }} }},
          tooltip: {{ backgroundColor: surfaceColor(), titleColor: inkColor('primary'), bodyColor: inkColor('secondary'),
                      borderColor: inkColor('grid'), borderWidth: 1, padding: 10 }}
        }},
        scales: {{
          x: {{ stacked: {stacked}, grid: {{ display: false }}, ticks: {{ color: inkColor('muted') }} }},
          y: {{ stacked: {stacked}, grid: {{ color: inkColor('grid') }}, ticks: {{ color: inkColor('muted') }},
                title: {{ display: {str(bool(y_label)).lower()}, text: {json.dumps(y_label, ensure_ascii=False)}, color: inkColor('secondary') }} }}
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
    --surface: #fcfcfb;
    --page: #f9f9f7;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted: #898781;
    --grid: #e1e0d9;
    --border: rgba(11,11,11,0.10);
    --accent: #2a78d6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      color-scheme: dark;
      --surface: #1a1a19;
      --page: #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #898781;
      --grid: #2c2c2a;
      --border: rgba(255,255,255,0.10);
      --accent: #3987e5;
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --surface: #1a1a19;
    --page: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --border: rgba(255,255,255,0.10);
    --accent: #3987e5;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--page); color: var(--text-primary);
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    padding: 32px 20px 60px;
  }}
  .wrap {{ max-width: 1080px; margin: 0 auto; }}
  .brand {{ display:flex; align-items:center; gap:10px; margin-bottom:22px; }}
  .brand .mark {{ width:28px; height:28px; border-radius:7px; background: var(--accent);
                  display:flex; align-items:center; justify-content:center; color:#fff; font-weight:700; font-size:13px; }}
  .brand span {{ color: var(--text-muted); font-size:13px; letter-spacing: .04em; text-transform: uppercase; }}
  header.page-head {{ margin-bottom: 28px; }}
  header.page-head .tag {{ color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
  header.page-head h1 {{ font-size: 26px; margin: 0 0 8px; }}
  header.page-head p.tagline {{ color: var(--text-secondary); font-size: 15px; max-width: 720px; margin: 0; line-height:1.5; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; position: relative; }}
  .kpi-label {{ color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 26px; font-weight: 600; }}
  .kpi-delta {{ font-size: 13px; margin-top: 4px; font-weight: 600; }}
  .delta-up {{ color: #0ca30c; }}
  .delta-down {{ color: #d03b3b; }}
  .kpi-badge {{ display:inline-block; margin-top:8px; font-size: 11px; font-weight: 700; text-transform: uppercase;
                letter-spacing: .03em; padding: 3px 8px; border-radius: 999px; }}
  .kpi-good {{ background: rgba(12,163,12,0.14); color: #0ca30c; }}
  .kpi-warning {{ background: rgba(250,178,25,0.18); color: #9a6a00; }}
  .kpi-serious {{ background: rgba(236,131,90,0.16); color: #b1481f; }}
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
  footer a {{ color: var(--accent); text-decoration: none; }}
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
function seriesColor(i, light, dark, alpha) {{
  const hex = isDark() ? dark : light;
  if (alpha >= 1) return hex;
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{alpha}})`;
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
