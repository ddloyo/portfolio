"""
Harness sintético de frescura: simula N días de cargas por tabla de las 10
fuentes del warehouse y mide, hora a hora, si cada una estuvo dentro de su SLA.

Qué es real y qué es simulado:
  REAL       Los umbrales (data/sla_thresholds.csv, leídos de los `_*__sources.yml`
             del warehouse) y la foto de "ahora" (data/dbt_sources_freshness.json,
             el sources.json que produjo `dbt source freshness`).
  SIMULADO   El historial: cuándo cargó cada fuente en los N días previos. dbt
             solo mide un instante, no guarda historia; aquí se genera un proceso
             de cargas por fuente (cadencia, retraso, fallas, incidentes) que
             termina EXACTAMENTE en el max_loaded_at real de cada tabla, así el
             último chequeo del historial es el estado que dbt reportó.

La clasificación pass/warn/error de cada chequeo usa `freshness_rules.classify`,
la réplica de la lógica de dbt-core; `verify_dbt_parity.py` demuestra contra dbt
en vivo que coincide (incluida la frontera de cada umbral).

Modelo de chequeo: se corre `dbt source freshness` cada hora. En cada chequeo, el
age de una tabla es (hora del chequeo - última carga anterior). El % de
cumplimiento de SLA de un día es el % de chequeos con status `pass`; el de una
fuente usa el peor status entre sus tablas.

Genera (en data/):
  cargas_simuladas.csv     -- una fila por carga: source, table, loaded_at, origen
  sla_diario_tabla.csv     -- chequeos y % de cumplimiento por tabla y día
  sla_diario_fuente.csv    -- ídem por fuente (peor status entre sus tablas)
  resumen_fuentes.csv      -- 30 días por fuente: % en SLA, días con incidente, racha máxima
  frescura_actual.csv      -- estado de ahora, con las columnas de `dbt source freshness`
  dashboards_por_fuente.csv -- qué dashboards del portafolio dependen de cada fuente (lineage de dbt)

Correr (con la foto de dbt ya sincronizada por sync_from_dbt.py):
  python3 data/generate_data.py
"""

import json
import zlib
from bisect import bisect_right
from datetime import timedelta

import numpy as np
import pandas as pd

from freshness_rules import (DATA_DIR, classify, load_dbt_snapshot, load_thresholds, parse_ts)

CATALOG_SNAPSHOT = DATA_DIR.parents[1] / "15-catalogo-datos-metricas" / "data" / "catalog_snapshot.json"
SEED = 16
N_DAYS = 30          # ventana del dashboard (días UTC, el último es el de la foto de dbt)
WARMUP_DAYS = 150    # historia previa, para que las fuentes trimestrales tengan cargas antes de la ventana
SEVERITY = {"pass": 0, "warn": 1, "error": 2}

# Perfil operativo de cada fuente. Los umbrales de SLA NO están aquí (salen de dbt);
# esto describe cómo se comporta el proceso de carga.
#   every_h        horas entre cargas programadas (24 = diario). El horario se ancla a la última
#                  carga REAL de dbt (la carga de las 22:58 de ayer implica cargas a las 22:58)
#   weekdays_only  no hay carga en sábado/domingo (Excel que mandan las sucursales)
#   random_cadence cargas manuales o semanales sin horario fijo: intervalo ~ N(every_h, jitter_h)
#   delay_med_min  mediana del retraso normal (lognormal, sigma delay_sigma)
#   skip_p         prob. de que una carga programada simplemente no ocurra
#   late_p         prob. de una demora larga extra (media late_extra_h horas)
#   incidents      caídas de N horas: (días atrás, hora UTC de inicio, duración h)
PROFILES = {
    "pos":                {"every_h": 1, "delay_med_min": 6, "delay_sigma": 0.5, "skip_p": 0.008,
                           "incidents": [(11, 4, 8)]},
    "producto_analytics": {"every_h": 1, "delay_med_min": 4, "delay_sigma": 0.4, "skip_p": 0.006,
                           "incidents": [(20, 3, 13)]},
    "crm":                {"every_h": 4, "delay_med_min": 10, "delay_sigma": 0.5, "skip_p": 0.05,
                           "incidents": [(6, 2, 29)]},   # token de la API vencido
    "helpdesk":           {"every_h": 6, "delay_med_min": 12, "delay_sigma": 0.5, "skip_p": 0.04,
                           "incidents": []},
    "erp":                {"every_h": 24, "delay_med_min": 40, "delay_sigma": 0.6, "skip_p": 0.03,
                           "incidents": [(15, 0, 58)]},  # dos noches sin batch tras un cambio de esquema
    "wms":                {"every_h": 24, "delay_med_min": 25, "delay_sigma": 0.6, "skip_p": 0.07,
                           "incidents": []},
    "sucursales":         {"every_h": 24, "delay_med_min": 130, "delay_sigma": 0.8, "weekdays_only": True,
                           "skip_p": 0.10, "late_p": 0.10, "late_extra_h": 14, "incidents": [],
                           "table_skip_p": {"pedido_sucursal_cdmx": 0.05, "pedido_sucursal_guadalajara": 0.12,
                                            "pedido_sucursal_monterrey": 0.22}},
    "ads":                {"every_h": 24, "delay_med_min": 240, "delay_sigma": 0.6, "skip_p": 0.45,
                           "incidents": []},   # se salta cargas mientras se reprocesa la atribución
    "encuestas":          {"random_cadence": True, "every_h": 168, "jitter_h": 10, "incidents": []},
    "scorecard":          {"random_cadence": True, "every_h": 720, "jitter_h": 120, "incidents": [],
                           "table_every_h": {"kpi_meta": 2160}, "table_jitter_h": {"kpi_meta": 240}},
}
# Tablas de un mismo source que cargan en un solo job (mismos timestamps de carga);
# el resto son procesos independientes (un Excel por sucursal, una captura manual por KPI).
INDEPENDENT_STREAMS = {"sucursales", "scorecard"}


def simulate_events(p, table, pinned, now, start, rng):
    """Cargas simuladas de una tabla entre `start` y la última carga real (`pinned`, de dbt).

    Se genera hacia atrás desde `pinned`: cada carga programada cae en pinned - k*cadencia
    (más un retraso), así el historial es continuo con lo que dbt midió y no hay un
    "salto" artificial junto a la última carga.
    """
    every_h = p.get("table_every_h", {}).get(table, p["every_h"])
    jitter_h = p.get("table_jitter_h", {}).get(table, p.get("jitter_h"))
    skip_p = p.get("table_skip_p", {}).get(table, p.get("skip_p", 0))
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    outages = [(today0 - timedelta(days=d) + timedelta(hours=h), today0 - timedelta(days=d) + timedelta(hours=h + dur))
               for d, h, dur in p["incidents"]]
    events = []
    if p.get("random_cadence"):
        t = pinned
        while True:
            t -= timedelta(hours=max(every_h * 0.5, float(rng.normal(every_h, jitter_h))))
            if t < start:
                break
            events.append(t)
        return sorted(events)
    k = 1
    while True:
        slot = pinned - timedelta(hours=every_h * k)
        k += 1
        if slot < start - timedelta(days=3):
            break
        if p.get("weekdays_only") and slot.weekday() >= 5:
            continue
        if rng.random() < skip_p:
            continue
        delay = timedelta(minutes=float(rng.lognormal(np.log(p["delay_med_min"]), p["delay_sigma"])))
        if p.get("late_p") and rng.random() < p["late_p"]:
            delay += timedelta(hours=float(rng.exponential(p["late_extra_h"])))
        t = slot + delay
        if t < start or t >= pinned - timedelta(minutes=1) or any(a <= t < b for a, b in outages):
            continue
        events.append(t)
    return sorted(events)


def dashboards_por_fuente():
    """Qué dashboards (carpetas gold NN_*) dependen, río arriba, de cada source. Sale del
    lineage de dbt que el proyecto 15 ya extrajo del manifest (catalog_snapshot.json).

    No se cruzan las dimensiones compartidas (`dim_*`): dim_canal se construye con los canales
    de ads y la usa fct_pedido, así que por lineage puro TODO dashboard de ventas "depende" de
    ads, aunque un gasto de pauta atrasado no vuelva rancias las ventas. Cuenta la dependencia
    del dato (hechos y sus insumos), no la del catálogo de referencia."""
    nodes = {n["id"]: n for n in json.loads(CATALOG_SNAPSHOT.read_text(encoding="utf-8"))["nodes"]}
    deps = {}
    for gold in (n for n in nodes.values() if n["layer"] == "gold"):
        num = int(gold["group"][:2])
        seen, stack = set(), list(gold["upstream"])
        while stack:
            nid = stack.pop()
            if nid in seen or nid not in nodes:
                continue
            seen.add(nid)
            node = nodes[nid]
            if node["kind"] == "source":
                deps.setdefault(node["group"], set()).add(num)
            if not node["name"].startswith("dim_"):
                stack.extend(node["upstream"])
    return deps


def build():
    thresholds = load_thresholds()
    snap, meta = load_dbt_snapshot()
    missing = set(thresholds) ^ set(snap)
    if missing:
        raise SystemExit(f"sla_thresholds.csv y dbt_sources_freshness.json no coinciden en: {sorted(missing)} "
                         "(vuelve a correr sync_from_dbt.py --run)")

    now = max(parse_ts(r["snapshotted_at"]) for r in snap.values())
    last_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = last_day - timedelta(days=N_DAYS - 1)
    sim_start = window_start - timedelta(days=WARMUP_DAYS)

    # ---- cargas por tabla, terminando en el max_loaded_at real de dbt -------------------------
    loads = {}
    prefix_cache = {}
    for (source, table), r in snap.items():
        p = PROFILES[source]
        stream = f"{source}.{table}" if source in INDEPENDENT_STREAMS else source
        pinned = parse_ts(r["max_loaded_at"])
        if stream not in prefix_cache:
            rng = np.random.default_rng(zlib.crc32(stream.encode()) ^ SEED)
            prefix_cache[stream] = simulate_events(p, table, pinned, now, sim_start, rng)
        # la última carga de cada tabla es la real de dbt (las tablas de un mismo job difieren por segundos)
        loads[(source, table)] = [e for e in prefix_cache[stream] if e < pinned] + [pinned]

    # ---- chequeos horarios: el último es el instante de la foto de dbt ------------------------
    checks = []
    t = now
    while t >= window_start:
        checks.append(t)
        t -= timedelta(hours=1)
    checks.reverse()

    rows = []
    status_by_check = {}   # (source, i) -> peor status entre sus tablas
    ratio_by_check = {}    # (source, i) -> máx. age/warn entre sus tablas
    for (source, table), evs in loads.items():
        th = thresholds[(source, table)]
        for i, c in enumerate(checks):
            j = bisect_right(evs, c) - 1
            if j < 0:
                continue
            age_s = (c - evs[j]).total_seconds()
            st = classify(age_s, th["warn_s"], th["error_s"])
            rows.append((source, table, c, age_s, st))
            key = (source, i)
            if SEVERITY[st] >= SEVERITY.get(status_by_check.get(key, "pass"), 0):
                status_by_check[key] = st
            ratio_by_check[key] = max(ratio_by_check.get(key, 0), age_s / th["warn_s"])
    chk = pd.DataFrame(rows, columns=["source", "table", "check_at", "age_s", "status"])
    chk["fecha"] = chk["check_at"].map(lambda x: x.date().isoformat())

    def summarize(df, by):
        g = df.groupby(by)
        out = g.agg(chequeos=("status", "size"),
                    n_pass=("status", lambda s: int((s == "pass").sum())),
                    n_warn=("status", lambda s: int((s == "warn").sum())),
                    n_error=("status", lambda s: int((s == "error").sum())),
                    max_age_h=("age_s", lambda s: round(s.max() / 3600, 2))).reset_index()
        out["pct_cumplimiento"] = (100 * out["n_pass"] / out["chequeos"]).round(1)
        out["dia_parcial"] = out["fecha"] == last_day.date().isoformat()
        return out

    tabla_dia = summarize(chk, ["fecha", "source", "table"])
    fuente_rows = [(s, checks[i], status_by_check[(s, i)], ratio_by_check[(s, i)]) for (s, i) in status_by_check]
    fuente = pd.DataFrame(fuente_rows, columns=["source", "check_at", "status", "ratio_warn"])
    fuente["fecha"] = fuente["check_at"].map(lambda x: x.date().isoformat())
    fuente_dia = fuente.groupby(["fecha", "source"]).agg(
        chequeos=("status", "size"),
        n_pass=("status", lambda s: int((s == "pass").sum())),
        n_warn=("status", lambda s: int((s == "warn").sum())),
        n_error=("status", lambda s: int((s == "error").sum())),
        max_ratio_warn=("ratio_warn", lambda s: round(s.max(), 3))).reset_index()
    fuente_dia["pct_cumplimiento"] = (100 * fuente_dia["n_pass"] / fuente_dia["chequeos"]).round(1)
    cierre = fuente.sort_values("check_at").groupby(["fecha", "source"])["status"].last().rename("status_cierre")
    fuente_dia = fuente_dia.merge(cierre.reset_index(), on=["fecha", "source"])
    fuente_dia["dia_parcial"] = fuente_dia["fecha"] == last_day.date().isoformat()

    # ---- resumen de la ventana por fuente -----------------------------------------------------
    resumen = []
    for source, g in fuente.sort_values("check_at").groupby("source"):
        st = g["status"].tolist()
        longest = run = 0
        episodes = 0
        for k, s in enumerate(st):
            if s != "pass":
                run += 1
                longest = max(longest, run)
                if k == 0 or st[k - 1] == "pass":
                    episodes += 1
            else:
                run = 0
        dias_mal = g.loc[g["status"] != "pass", "fecha"].nunique()
        resumen.append({
            "source": source,
            "tablas": sum(1 for (s, _) in loads if s == source),
            "chequeos": len(g),
            "pct_cumplimiento": round(100 * (g["status"] == "pass").mean(), 1),
            "pct_sin_error": round(100 * (g["status"] != "error").mean(), 1),
            "dias_fuera_de_sla": int(dias_mal),
            "episodios": episodes,
            "racha_max_h": longest,
            "status_ahora": g.iloc[-1]["status"],
        })
    resumen = pd.DataFrame(resumen).sort_values(["pct_cumplimiento", "source"]).reset_index(drop=True)

    # ---- estado actual: tal cual lo reporta dbt (mismas columnas que `dbt source freshness`) ---
    actual = pd.DataFrame([{
        "source": s, "table": t, "max_loaded_at": r["max_loaded_at"], "snapshotted_at": r["snapshotted_at"],
        "age_s": round(r["max_loaded_at_time_ago_in_s"], 1), "status": r["status"],
        "warn_after": f'{r["criteria"]["warn_after"]["count"]} {r["criteria"]["warn_after"]["period"]}',
        "error_after": f'{r["criteria"]["error_after"]["count"]} {r["criteria"]["error_after"]["period"]}',
    } for (s, t), r in sorted(snap.items())])

    deps = dashboards_por_fuente()
    dash_df = pd.DataFrame([{"source": src, "dashboards": "|".join(f"{n:02d}" for n in sorted(deps.get(src, ()))),
                             "n_dashboards": len(deps.get(src, ()))} for src in sorted({k[0] for k in loads})])
    dash_df.to_csv(DATA_DIR / "dashboards_por_fuente.csv", index=False)

    cargas = pd.DataFrame([(s, t, e.strftime("%Y-%m-%dT%H:%M:%SZ"), "dbt" if k == len(evs) - 1 else "simulado")
                           for (s, t), evs in sorted(loads.items()) for k, e in enumerate(evs)
                           if e >= window_start - timedelta(days=45)],
                          columns=["source", "table", "loaded_at", "origen"])

    cargas.to_csv(DATA_DIR / "cargas_simuladas.csv", index=False)
    tabla_dia.sort_values(["source", "table", "fecha"]).to_csv(DATA_DIR / "sla_diario_tabla.csv", index=False)
    fuente_dia.sort_values(["source", "fecha"]).to_csv(DATA_DIR / "sla_diario_fuente.csv", index=False)
    resumen.to_csv(DATA_DIR / "resumen_fuentes.csv", index=False)
    actual.to_csv(DATA_DIR / "frescura_actual.csv", index=False)

    print(f"Ventana: {window_start.date()} -> {now.isoformat()} ({N_DAYS} días, {len(checks)} chequeos horarios)")
    print(resumen.to_string(index=False))
    print(f"OK -> {len(cargas)} cargas, {len(tabla_dia)} filas tabla-día, {len(fuente_dia)} fuente-día, {len(actual)} tablas ahora")


if __name__ == "__main__":
    build()
