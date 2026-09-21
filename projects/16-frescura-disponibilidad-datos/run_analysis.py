"""
Disponibilidad y Frescura de Datos (SLA): ¿los datos que estoy viendo son de ayer
o de hace dos semanas? El segundo pilar de gobernanza de datos, junto con la
calidad (proyecto 13).

Lee lo que dejó data/generate_data.py y arma el dashboard:
  - "Ahora": el estado real de las 22 tablas, tal cual lo midió `dbt source freshness`
    (data/dbt_sources_freshness.json -> data/frescura_actual.csv).
  - "Historia": 30 días de chequeos horarios SIMULADOS, clasificados con los MISMOS
    umbrales que están en los `_*__sources.yml` del warehouse
    (data/sla_thresholds.csv). Cada dashboard lo declara así.

Genera:
  dashboard.html     -- ES
  dashboard.en.html  -- EN (mismo dato, textos en inglés)

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) -- se usa como vista previa en el README y en index.html.
Para regenerarla tras un cambio visual: abre dashboard.html en el navegador y
toma un screenshot de la página completa.

Antes de correr esto (ver README): sync_from_dbt.py --run  ->  generate_data.py
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))
sys.path.insert(0, str(ROOT / "data"))
sys.path.insert(0, str(REPO_ROOT / "projects" / "15-catalogo-datos-metricas" / "data"))

import pandas as pd
from xia_style import STATUS
import dashboard as dash
from freshness_rules import parse_ts, to_seconds
from taxonomy import DASHBOARDS

DATA = ROOT / "data"
N_TABLAS_ESPERADAS = 22
SEV = {"pass": 0, "warn": 1, "error": 2}
BADGE = {"pass": "good", "warn": "warning", "error": "critical"}
ES_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
EN_MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOW_ES = ["L", "M", "X", "J", "V", "S", "D"]
DOW_EN = ["M", "T", "W", "T", "F", "S", "S"]
HEAT_BANDS = [{"min": 95, "status": "good"}, {"min": 80, "status": "warning"}, {"min": 0, "status": "critical"}]


def band_status(pct):
    return "good" if pct >= 95 else ("warning" if pct >= 80 else "critical")


# ============================================================================
# Datos
# ============================================================================
thr = pd.read_csv(DATA / "sla_thresholds.csv")
act = pd.read_csv(DATA / "frescura_actual.csv")
res = pd.read_csv(DATA / "resumen_fuentes.csv")
fd = pd.read_csv(DATA / "sla_diario_fuente.csv")
dep = pd.read_csv(DATA / "dashboards_por_fuente.csv", dtype=str, keep_default_na=False).set_index("source")
parity = pd.read_csv(DATA / "parity_report.csv")

assert len(act) == N_TABLAS_ESPERADAS, f"dbt reportó {len(act)} tablas, se esperaban {N_TABLAS_ESPERADAS}"
assert (parity["coincide"].astype(str) == "True").all(), "parity_report.csv tiene diferencias: corre verify_dbt_parity.py"

act = act.merge(thr, on=["source", "table"])
act["warn_s"] = [to_seconds(c, p) for c, p in zip(act["warn_after_count"], act["warn_after_period"])]
act["error_s"] = [to_seconds(c, p) for c, p in zip(act["error_after_count"], act["error_after_period"])]
act["ratio"] = act["age_s"] / act["warn_s"]
act["sev"] = act["status"].map(SEV)

snap_at = max(parse_ts(x) for x in act["snapshotted_at"])
snap_label = snap_at.strftime("%Y-%m-%d %H:%M UTC")

src_now = act.groupby("source")["sev"].max()
sources = res["source"].tolist()               # ya viene del peor al mejor cumplimiento
n_src = len(sources)
n_src_ok = int((src_now == 0).sum())
src_err = [s for s in sources if src_now[s] == 2]
src_warn = [s for s in sources if src_now[s] == 1]
n_tab_ok = int((act["sev"] == 0).sum())
pct_src_ok = round(100 * n_src_ok / n_src)
stale_prom = round(100 * act["ratio"].mean())
stale_pass = round(100 * act.loc[act["sev"] == 0, "ratio"].mean())
stale_fail = round(100 * act.loc[act["sev"] > 0, "ratio"].mean())

dias = sorted(fd["fecha"].unique())
n_dias = len(dias)
pivot = fd.pivot(index="source", columns="fecha", values="pct_cumplimiento").reindex(index=sources, columns=dias)
trend = fd.groupby("fecha")["pct_cumplimiento"].mean().reindex(dias).round(1)
cierre = fd.pivot(index="fecha", columns="source", values="status_cierre").reindex(dias)

worst_freq = res.sort_values(["dias_fuera_de_sla", "episodios"], ascending=False).iloc[0]
longest = res.sort_values("racha_max_h", ascending=False).iloc[0]
rr = res.set_index("source")

# patrón de fin de semana de la fuente más frecuentemente tardía (días completos)
fd["dow"] = pd.to_datetime(fd["fecha"]).dt.dayofweek
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
wk = fd[(fd["source"] == worst_freq["source"]) & (~fd["dia_parcial"])]
by_dow = wk.groupby("dow")["pct_cumplimiento"].mean()
weak_dow = sorted((d for d in range(7) if by_dow.get(d, 100) < 50), key=lambda d: (d + 1) % 7)  # días donde casi nunca cumple; domingo primero
pct_weak = wk[wk["dow"].isin(weak_dow)]["pct_cumplimiento"].mean() if weak_dow else float("nan")
pct_rest = wk[~wk["dow"].isin(weak_dow)]["pct_cumplimiento"].mean()


def th_of(source):
    """(warn_h, error_h) de la primera tabla del source; sirve para los sources de umbral homogéneo."""
    r = act[act["source"] == source].iloc[0]
    return r["warn_s"] / 3600, r["error_s"] / 3600


def fmt_age(s):
    """Edad legible; el espacio es no-separable para que "79.0 h" no se parta en dos líneas en la tabla."""
    if s < 3600:
        return f"{s / 60:.0f}&nbsp;min"
    if s < 100 * 3600:
        return f"{s / 3600:.1f}&nbsp;h"
    return f"{s / 86400:.1f}&nbsp;d"


def fmt_thr(count, period):
    return f"{count} {'h' if period == 'hour' else 'd'}"


def fmt_ts(iso):
    return parse_ts(iso).strftime("%Y-%m-%d %H:%M:%S")


def dash_list(source, lang):
    nums = [int(x) for x in dep.loc[source, "dashboards"].split("|") if x]
    names = [f"{n:02d} {DASHBOARDS[n][1 if lang == 'es' else 2].split(':')[0]}" for n in nums]
    return ", ".join(names[:3]) + (f" +{len(names) - 3}" if len(names) > 3 else "") if names else "—"


def day_label(iso, lang):
    d = datetime.fromisoformat(iso)
    return f"{d.day} {(ES_MESES if lang == 'es' else EN_MESES)[d.month - 1]}"


# ============================================================================
# Dashboard (ES / EN)
# ============================================================================
def build(lang):
    L = (lambda es, en: es if lang == "es" else en)
    label_sev = {"good": L("Sano", "Healthy"), "warning": L("Atención", "Attention"),
                 "serious": L("En riesgo", "At risk"), "critical": L("Crítico", "Critical")}

    hero_status = "good" if pct_src_ok >= 90 else "warning" if pct_src_ok >= 75 else "serious" if pct_src_ok >= 60 else "critical"
    hero_kpi = {"label": L(f"Fuentes dentro de SLA hoy · {n_src_ok} de {n_src}", f"Sources within SLA today · {n_src_ok} of {n_src}"),
                "value": f"{pct_src_ok}%", "status": hero_status, "status_label": label_sev[hero_status]}
    hero_chart = {
        "id": "chart_sla_trend", "type": "line",
        "title": L("Cumplimiento de SLA — tendencia", "SLA compliance — trend"),
        "subtitle": L(f"Promedio de las {n_src} fuentes, últimos {n_dias} días", f"Average across {n_src} sources, last {n_dias} days"),
        "labels": [day_label(d, lang) for d in dias],
        "datasets": [{"label": L("% de chequeos en SLA", "% of checks within SLA"), "data": [float(v) for v in trend], "fill": True}],
        "value_format": "percent", "value_min": 0, "value_max": 100,
    }

    kpis = [
        {"label": L("Tablas dentro de SLA hoy", "Tables within SLA today"), "value": f"{n_tab_ok} / {len(act)}",
         "status": "warning", "status_label": label_sev["warning"]},
        {"label": L("Fuentes en error hoy", "Sources in error today"), "value": f"{len(src_err)}",
         "status": "critical" if src_err else "good", "status_label": label_sev["critical" if src_err else "good"]},
        {"label": L("Fuente más frecuentemente tardía", "Most frequently late source"), "value": worst_freq["source"],
         "status": "serious", "status_label": L(f"{worst_freq['dias_fuera_de_sla']} de {n_dias} días", f"{worst_freq['dias_fuera_de_sla']} of {n_dias} days")},
        {"label": L("Staleness promedio hoy", "Average staleness today"), "value": L(f"{stale_prom}% del umbral", f"{stale_prom}% of threshold"),
         "status": None},
        {"label": L("Racha más larga fuera de SLA", "Longest run outside SLA"), "value": f"{int(longest['racha_max_h'])} h",
         "status": "warning", "status_label": longest["source"]},
    ]
    kpis[3].pop("status")

    banner = {
        "label": L(f"Estado de frescura — {snap_label}", f"Freshness status — {snap_label}"),
        "headline": L(
            f"Hoy {n_src_ok} de {n_src} fuentes están dentro de su SLA: {' y '.join(src_err)} están en error y {' y '.join(src_warn)} en advertencia.",
            f"Today {n_src_ok} of {n_src} sources are within their SLA: {' and '.join(src_err)} are in error and {' and '.join(src_warn)} in warning."),
        "subtext": L(
            f"<code>dbt source freshness</code> midió {len(act)} tablas contra sus umbrales. Las fuentes en error alimentan, según el lineage de dbt, "
            f"{'; '.join(f'{s} → ' + dash_list(s, lang) for s in src_err)}: quien abra esos dashboards hoy ve datos que ya rebasaron su límite.",
            f"<code>dbt source freshness</code> measured {len(act)} tables against their thresholds. The sources in error feed, per dbt lineage, "
            f"{'; '.join(f'{s} → ' + dash_list(s, lang) for s in src_err)}: anyone opening those dashboards today is looking at data past its limit."),
    }

    # ---- tabla: mismas columnas que `dbt source freshness` -------------------------------------
    order = act.sort_values(["sev", "ratio"], ascending=[False, False])
    table = {
        "title": L("Estado de frescura ahora — las columnas de <code>dbt source freshness</code>",
                   "Freshness status now — the columns of <code>dbt source freshness</code>"),
        "headers": ["source", "table", "max_loaded_at (UTC)", "snapshotted_at (UTC)", "age",
                    L("umbral warn / error", "warn / error threshold"), "status"],
        "rows": [[r.source, r.table, fmt_ts(r.max_loaded_at), fmt_ts(r.snapshotted_at), fmt_age(r.age_s),
                  f"{fmt_thr(r.warn_after_count, r.warn_after_period)} / {fmt_thr(r.error_after_count, r.error_after_period)}",
                  f'<span class="kpi-badge kpi-{BADGE[r.status]}">{r.status}</span>'] for r in order.itertuples()],
    }

    # ---- gráficas ------------------------------------------------------------------------------
    letters = DOW_ES if lang == "es" else DOW_EN
    col_labels = [letters[datetime.fromisoformat(d).weekday()] for d in dias]
    charts = [
        {
            "id": "chart_heatmap_sla", "type": "heatmap", "full_width": True, "value_format": "int", "color_mode": "sequential", "bands": HEAT_BANDS,
            "title": L("Cumplimiento de SLA por fuente y día", "SLA compliance by source and day"),
            "subtitle": L(
                f"% de chequeos horarios en pass · verde ≥95, dorado ≥80, rojo <80 · columnas: días del {day_label(dias[0], lang)} al {day_label(dias[-1], lang)} "
                f"(UTC, la última es hoy, parcial), con la inicial del día de la semana",
                f"% of hourly checks in pass · green ≥95, gold ≥80, red <80 · columns: days from {day_label(dias[0], lang)} to {day_label(dias[-1], lang)} "
                f"(UTC, the last is today, partial), labelled with the weekday initial"),
            "row_labels": sources, "col_labels": col_labels,
            "matrix": [[float(v) for v in pivot.loc[s]] for s in sources],
        },
        {
            "id": "chart_sla_fuente", "type": "progress_bars",
            "title": L(f"Cumplimiento de SLA por fuente, {n_dias} días", f"SLA compliance by source, {n_dias} days"),
            "subtitle": L("% de chequeos en pass · de la peor a la mejor", "% of checks in pass · worst to best"),
            "labels": sources, "values": [float(rr.loc[s, "pct_cumplimiento"]) for s in sources],
            "colors": [STATUS[band_status(rr.loc[s, "pct_cumplimiento"])] for s in sources], "max": 100,
            "value_suffix": "%",
        },
        {
            "id": "chart_estado_diario", "type": "bar", "stacked": True,
            "title": L("Fuentes por estado al cierre de cada día", "Sources by status at each day's close"),
            "subtitle": L(f"Cuántas de las {n_src} fuentes estaban en pass, warn o error en el último chequeo del día",
                          f"How many of the {n_src} sources were in pass, warn or error at the day's last check"),
            "labels": [day_label(d, lang) for d in dias],
            "datasets": [
                {"label": L("pass (en SLA)", "pass (within SLA)"), "data": [int((cierre.loc[d] == "pass").sum()) for d in dias], "colors": STATUS["good"]},
                {"label": L("warn (advertencia)", "warn (warning)"), "data": [int((cierre.loc[d] == "warn").sum()) for d in dias], "colors": STATUS["warning"]},
                {"label": "error", "data": [int((cierre.loc[d] == "error").sum()) for d in dias], "colors": STATUS["critical"]},
            ],
            "y_label": L("Fuentes", "Sources"), "value_max": n_src,
        },
    ]

    # ---- small multiples: las 4 fuentes de umbral homogéneo con peor cumplimiento --------------
    homogeneous = [s for s in sources if act[act["source"] == s][["warn_s", "error_s"]].drop_duplicates().shape[0] == 1]
    drill_sources = homogeneous[:4]
    drilldown_charts = []
    for s in drill_sources:
        wh, eh = th_of(s)
        ratio_series = fd[fd["source"] == s].set_index("fecha")["max_ratio_warn"].reindex(dias)
        drilldown_charts.append({
            "id": f"chart_dd_{s}", "type": "line",
            "title": s,
            "subtitle": L(f"Edad máxima del día · warn {wh:g} h, error {eh:g} h · {rr.loc[s, 'pct_cumplimiento']}% en SLA",
                          f"Peak age of the day · warn {wh:g} h, error {eh:g} h · {rr.loc[s, 'pct_cumplimiento']}% within SLA"),
            "labels": [day_label(d, lang) for d in dias],
            "datasets": [
                {"label": L("Edad máx. (% del umbral warn)", "Peak age (% of warn threshold)"), "data": [round(float(v) * 100) for v in ratio_series],
                 "emphasis": True, "color_index": 1},
                {"label": L("Umbral warn", "Warn threshold"), "data": [100] * n_dias, "muted": True},
                {"label": L("Umbral error", "Error threshold"), "data": [round(100 * eh / wh)] * n_dias, "muted": True},
            ],
            "value_format": "percent",
        })

    # ---- insights ------------------------------------------------------------------------------
    err_rows = act[(act["sev"] == 2)].sort_values("ratio", ascending=False)
    pos_w, pos_e = th_of("pos")
    ads_w, ads_e = th_of("ads")
    insights = []
    err_txt_es = "; ".join(f"<b>{r.source}.{r.table}</b> lleva {fmt_age(r.age_s)} sin cargar (error a las {fmt_thr(r.error_after_count, r.error_after_period)})" for r in err_rows.itertuples())
    err_txt_en = "; ".join(f"<b>{r.source}.{r.table}</b> has gone {fmt_age(r.age_s)} without loading (error at {fmt_thr(r.error_after_count, r.error_after_period)})" for r in err_rows.itertuples())
    insights.append(L(
        f"Hoy <b>{n_tab_ok} de {len(act)} tablas</b> ({n_src_ok} de {n_src} fuentes) están dentro de su SLA. En error: {err_txt_es}. En advertencia: "
        f"{', '.join(f'<b>{r.source}.{r.table}</b> ({fmt_age(r.age_s)})' for r in act[act['sev'] == 1].sort_values('ratio', ascending=False).itertuples())}.",
        f"Today <b>{n_tab_ok} of {len(act)} tables</b> ({n_src_ok} of {n_src} sources) are within their SLA. In error: {err_txt_en}. In warning: "
        f"{', '.join(f'<b>{r.source}.{r.table}</b> ({fmt_age(r.age_s)})' for r in act[act['sev'] == 1].sort_values('ratio', ascending=False).itertuples())}."))
    w = worst_freq["source"]
    insights.append(L(
        f"<b>{w}</b> es la fuente más frecuentemente tardía: fuera de SLA <b>{worst_freq['dias_fuera_de_sla']} de {n_dias} días</b> ({rr.loc[w, 'pct_cumplimiento']}% de los chequeos en pass). "
        + (f"El patrón es semanal: el {' y el '.join(DIAS_ES[d] for d in weak_dow)} cumple {pct_weak:.0f}% de los chequeos y el resto de la semana {pct_rest:.0f}%. Ese proceso no carga en fin de semana, "
           f"así que el umbral warn de {th_of(w)[0]:g} h se rompe cada semana sin que nada esté mal. Un umbral que suena cada semana enseña a ignorar la alerta: hay que corregir el proceso o el umbral." if weak_dow else ""),
        f"<b>{w}</b> is the most frequently late source: outside SLA on <b>{worst_freq['dias_fuera_de_sla']} of {n_dias} days</b> ({rr.loc[w, 'pct_cumplimiento']}% of checks in pass). "
        + (f"The pattern is weekly: {' and '.join(DIAS_EN[d] for d in weak_dow)} meet {pct_weak:.0f}% of checks and the rest of the week {pct_rest:.0f}%. That process does not load on weekends, "
           f"so the {th_of(w)[0]:g} h warn threshold breaks every week with nothing actually wrong. A threshold that fires every week teaches people to ignore the alert: fix the process or the threshold." if weak_dow else "")))
    a = rr.loc["ads"]
    insights.append(L(
        f"<b>ads</b> es el otro caso crónico: {a['dias_fuera_de_sla']} días fuera de SLA en {a['episodios']} episodios, aun con un umbral mucho más holgado que el de pos "
        f"(warn {ads_w:g} h / error {ads_e:g} h, contra {pos_w:g} h / {pos_e:g} h). Un feed de pauta tolera rezago por la ventana de atribución, pero no {fmt_age(act[act['source'] == 'ads'].iloc[0]['age_s'])}. "
        f"Alimenta el dashboard {dash_list('ads', lang)}.",
        f"<b>ads</b> is the other chronic case: {a['dias_fuera_de_sla']} days outside SLA across {a['episodios']} episodes, even with a threshold far looser than pos's "
        f"(warn {ads_w:g} h / error {ads_e:g} h, versus {pos_w:g} h / {pos_e:g} h). An ads feed tolerates lag because of the attribution window, but not {fmt_age(act[act['source'] == 'ads'].iloc[0]['age_s'])}. "
        f"It feeds the dashboard {dash_list('ads', lang)}."))
    healthy = [s for s in sources if rr.loc[s, "pct_cumplimiento"] >= 95]
    insights.append(L(
        f"{len(healthy)} de {n_src} fuentes cumplen ≥95% de los chequeos ({', '.join(healthy)}); sus fallas son incidentes puntuales, no un patrón. "
        f"La racha más larga fuera de SLA fue de <b>{int(longest['racha_max_h'])} h</b> ({longest['source']}). "
        f"La staleness promedio de hoy es {stale_prom}% del umbral warn: las tablas en pass van en {stale_pass}% de su margen y las que fallan ya van en {stale_fail}%.",
        f"{len(healthy)} of {n_src} sources meet ≥95% of checks ({', '.join(healthy)}); their failures are one-off incidents, not a pattern. "
        f"The longest run outside SLA was <b>{int(longest['racha_max_h'])} h</b> ({longest['source']}). "
        f"Today's average staleness is {stale_prom}% of the warn threshold: tables in pass sit at {stale_pass}% of their margin and the failing ones are already at {stale_fail}%."))
    n_par = len(parity)
    insights.append(L(
        f"Cómo leer este dashboard: los umbrales y el estado de hoy son <b>reales</b> (bloques <code>freshness</code> de los <code>_*__sources.yml</code> del warehouse y el "
        f"<code>sources.json</code> de dbt). El historial de {n_dias} días es <b>simulado</b>, pero se clasifica con la misma regla: {n_par} comparaciones contra "
        f"<code>dbt source freshness</code> en vivo coinciden (ver <code>data/verify_dbt_parity.py</code>).",
        f"How to read this dashboard: the thresholds and today's status are <b>real</b> (the <code>freshness</code> blocks in the warehouse's <code>_*__sources.yml</code> and dbt's "
        f"<code>sources.json</code>). The {n_dias}-day history is <b>simulated</b>, but classified with the same rule: {n_par} comparisons against live "
        f"<code>dbt source freshness</code> match (see <code>data/verify_dbt_parity.py</code>)."))

    # ---- checklist accionable ------------------------------------------------------------------
    ACTIONS = {
        "ads": ("Marketing ops", L("Reintentar la carga de la API de pauta y confirmar que el reproceso de atribución no ocupa la ventana diaria. Si el retraso es estructural, acordar un warn de 72 h con el dueño de Marketing.",
                                   "Retry the ads API load and confirm the attribution reprocess isn't taking the daily window. If the lag is structural, agree a 72 h warn with the Marketing owner.")),
        "sucursales": (L("Ops de sucursales", "Branch ops"), L("Pedir el Excel de {table} (último recibido hace {age}) y fijar un responsable de envío diario, incluido el fin de semana.",
                                                                  "Request the {table} Excel (last received {age} ago) and name an owner for the daily send, weekends included.")),
        "wms": ("IT / Almacén", L("Revisar el log del batch nocturno de inventario (última carga hace {age}, warn a las {warn}) y re-ejecutarlo.",
                                   "Check the nightly inventory batch log (last load {age} ago, warn at {warn}) and re-run it.")),
        "scorecard": (L("Dueño del KPI", "KPI owner"), L("Recordar la captura mensual de {table} (última hace {age}, warn a las {warn}).",
                                                          "Nudge the monthly capture of {table} (last {age} ago, warn at {warn}).")),
    }
    rows = []
    for r in act[act["sev"] > 0].sort_values(["sev", "ratio"], ascending=[False, False]).itertuples():
        owner, text = ACTIONS.get(r.source, (L("Data owner", "Data owner"), L("Revisar la carga de {table} ({age} sin cargar).", "Check the load of {table} ({age} without loading).")))
        rows.append({"id": f"{r.source}_{r.table}", "cells": [
            f"<b>{r.source}.{r.table}</b>", f'<span class="kpi-badge kpi-{BADGE[r.status]}">{r.status}</span>', fmt_age(r.age_s),
            text.format(table=r.table, age=fmt_age(r.age_s), warn=fmt_thr(r.warn_after_count, r.warn_after_period)), owner, dash_list(r.source, lang)]})
    rows += [
        {"id": "umbral_finde", "cells": [
            f"<b>{w}</b> ({L('umbral', 'threshold')})", '<span class="kpi-badge kpi-warning">warn</span>', L("cada semana", "every week"),
            L(f"Decidir: pedir envío en fin de semana o subir el warn de {w} a 72 h. Hoy suena cada semana sin que haya falla.",
              f"Decide: ask for a weekend send or raise the {w} warn to 72 h. Today it fires every week with no real failure."),
            "Data owner", dash_list(w, lang)]},
        {"id": "orquestar", "cells": [
            "<b>dbt source freshness</b>", '<span class="kpi-badge kpi-neutral">—</span>', "—",
            L("Correrlo cada hora en el orquestador y mandar warn/error a un canal de alertas, para enterarse antes de la junta.",
              "Run it hourly in the orchestrator and send warn/error to an alerts channel, so you find out before the meeting."),
            "Data owner", "—"]},
        {"id": "banner_datos", "cells": [
            "<b>Dashboards</b>", '<span class="kpi-badge kpi-neutral">—</span>', "—",
            L("Mostrar en cada dashboard la fecha de su último dato (\"datos al …\") y pintarla de rojo si su fuente está en error.",
              "Show each dashboard's last-data date (\"data as of …\") and turn it red when its source is in error."),
            "Data owner", "—"]},
    ]
    checklist = {
        "id": "plan_frescura",
        "title": L("Plan de acción de frescura", "Freshness action plan"),
        "subtitle": L(f"{len(act[act['sev'] > 0])} tablas fuera de SLA hoy y 3 acciones estructurales. Marca cada acción al cerrarla; el avance se queda guardado en tu navegador.",
                      f"{len(act[act['sev'] > 0])} tables outside SLA today and 3 structural actions. Tick each action when done; progress is kept in your browser."),
        "progress_noun": L("cerradas", "closed"),
        "headers": [L("Fuente / tabla", "Source / table"), L("Estado", "Status"), L("Sin cargar", "Since last load"), L("Acción", "Action"),
                    L("Responsable propuesto", "Suggested owner"), L("Dashboards afectados", "Affected dashboards")],
        "rows": rows,
    }

    tagline = L(
        f"{len(act)} tablas de {n_src} fuentes con umbrales de frescura distintos, medidas con <code>dbt source freshness</code> de verdad — y {n_dias} días de historial para ver qué fuente llega tarde siempre.",
        f"{len(act)} tables from {n_src} sources with different freshness thresholds, measured with the real <code>dbt source freshness</code> — and {n_dias} days of history to see which source is always late.")
    return dict(
        title=L("Disponibilidad y Frescura de Datos (SLA)", "Data Availability & Freshness (SLA)"), tagline=tagline,
        kpis=kpis, charts=charts, insights=insights, table=table, banner=banner, checklist=checklist,
        hero_kpi=hero_kpi, hero_chart=hero_chart, drilldown_charts=drilldown_charts,
        drilldown_title=L(f"Las {len(drill_sources)} fuentes con peor cumplimiento: edad máxima diaria vs. sus umbrales",
                          f"The {len(drill_sources)} worst-performing sources: peak daily age vs. their thresholds"))


def finalize(html, lang):
    """La librería compartida aún trae el placeholder "X" del logo y sus textos fijos en español:
    aquí se aplica lo mismo que ya tienen los dashboards 01-13 (logo real; EN traducido)."""
    old_css = "color: var(--brand-cream); font-weight:700; font-size:13px; }"
    new_css = ("color: var(--brand-cream); font-weight:700; font-size:13px;\n"
               "                  overflow: hidden; }\n"
               "  .brand .mark img { width:100%; height:100%; object-fit: cover; display:block; }")
    old_logo = '<div class="mark">X</div>'
    new_logo = '<div class="mark"><img src="../../assets/xia-logo.png" alt="XIA logo"></div>'
    replacements = [(old_css, new_css), (old_logo, new_logo)]
    if lang == "en":
        replacements += [
            ('<html lang="es">', '<html lang="en">'),
            ("Portafolio de demostración", "Portfolio Demonstration"),
            ("Proyecto 16 ·", "Project 16 ·"),
            ("Lo que dice el dato", "What the data shows"),
            ("Dataset sintético generado para fines demostrativos. Servicio real:",
             "Synthetic dataset generated for demonstration purposes. Actual service:"),
            ("toLocaleString('es-MX')", "toLocaleString('en-US')"),
        ]
    for old, new in replacements:
        assert old in html, f"la plantilla de _lib/dashboard.py cambió: no encuentro {old[:50]!r}"
        html = html.replace(old, new)
    return html


for lang, fname in (("es", "dashboard.html"), ("en", "dashboard.en.html")):
    cfg = build(lang)
    out = ROOT / fname
    dash.render(out, project_no=16, table_position="top", chart_cols=2, **cfg)
    out.write_text(finalize(out.read_text(encoding="utf-8"), lang), encoding="utf-8")

print(f"Foto de dbt: {snap_label} | Fuentes en SLA: {n_src_ok}/{n_src} | Tablas en SLA: {n_tab_ok}/{len(act)}")
print(f"En error: {', '.join(src_err) or '-'} | En warn: {', '.join(src_warn) or '-'} | Más tardía: {worst_freq['source']} ({worst_freq['dias_fuera_de_sla']}/{n_dias} días)")
print("OK -> dashboard.html, dashboard.en.html")
