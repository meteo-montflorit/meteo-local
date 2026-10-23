#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La previsión de la semana: cuánto se equivoca ECMWF en las máximas y las
mínimas de Montflorit de 1 a 7 días vista, y si una corrección con la
estación de casa lo mejora (ADR 0122; Juanjo, 23-10-2026: «la prevision de
los dias siguientes mejorará con el tiempo?»).

- Lo medido: la máxima y la mínima de cada día (hora local) de la estación de
  casa, con las lecturas en punto y a la media de Ecowitt (calibracio/dades,
  casa_30min.csv y casa_5min.csv: del 08-10-2025 al 06-10-2026). Solo los días
  con al menos 44 de las 48 lecturas.
- Lo previsto: ECMWF IFS de la API de ejecuciones anteriores de Open-Meteo
  (`temperature_2m_previous_dayN`, la previsión hecha N días antes para cada
  hora), la máxima y la mínima de las 24 horas del día.
- Las correcciones, como se harían de verdad: el día en que se prevé solo se
  conocen los días ya medidos. «Sesgo de D días»: se suma el error medio
  (medido − previsto) de esa misma antelación en los D días anteriores al de
  la previsión. «Regresión»: medido = a + b·previsto, ajustada sin el mes que
  se evalúa (validación cruzada por meses).
- Si una mejora es segura, con la regla de toda la app
  (remostreig.seguretat, ADR 0105), con semanas como bloques: los días
  seguidos se parecen y no son casos independientes.

  python3 calibracio/setmana.py [--descarrega] [--model ecmwf_ifs025] [--hores]
"""
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
import remostreig as R  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(AQUI, "dades")
TZ = ZoneInfo("Europe/Madrid")
INICI, FI = dt.date(2025, 10, 8), dt.date(2026, 10, 5)
ANTELACIONS = range(1, 8)
# ECMWF a 9 km, el de la app (config.MODEL_ECMWF); con --model, otro.
MODEL = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else C.MODEL_ECMWF
PREVIST = os.path.join(DIR, f"setmana_{MODEL}.json")
FINESTRES = (14, 30, 60)
MIN_LECTURES = 44
# Con --hores, solo las lecturas en punto, como el registro del NAS
# (estacio-casa.csv), que es lo que usa la corrección de verdad (setmana.py).
HORES = "--hores" in sys.argv
if HORES:
    MIN_LECTURES = 22


def descarrega():
    v = ",".join(f"temperature_2m_previous_day{k}" for k in ANTELACIONS)
    q = urllib.parse.urlencode({"latitude": C.CASA[0], "longitude": C.CASA[1], "hourly": v, "models": MODEL,
                                "timezone": "Europe/Madrid", "start_date": INICI.isoformat(),
                                "end_date": FI.isoformat()})
    with urllib.request.urlopen(f"https://previous-runs-api.open-meteo.com/v1/forecast?{q}", timeout=300) as r:
        with open(PREVIST, "w", encoding="utf-8") as f:
            json.dump(json.loads(r.read())["hourly"], f)


def mesurat():
    """{dia: (màxima, mínima)} de la estación, con las lecturas en punto y a la media."""
    lect = {}
    for nom in ("casa_30min.csv", "casa_5min.csv"):
        with open(os.path.join(DIR, nom), encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                t = dt.datetime.fromisoformat(fila["t"]).astimezone(TZ)
                if t.minute in ((0,) if HORES else (0, 30)) and fila["temperatura"]:
                    lect[t.replace(second=0)] = float(fila["temperatura"])
    dies = {}
    for t, v in lect.items():
        dies.setdefault(t.date(), []).append(v)
    return {d: (max(v), min(v)) for d, v in dies.items() if len(v) >= MIN_LECTURES}


def previst():
    """{antelació: {dia: (màxima, mínima)}} de ECMWF, solo los días con las 24 horas."""
    with open(PREVIST, encoding="utf-8") as f:
        h = json.load(f)
    res = {}
    for k in ANTELACIONS:
        dies = {}
        for t, v in zip(h["time"], h[f"temperature_2m_previous_day{k}"]):
            if v is not None:
                dies.setdefault(dt.date.fromisoformat(t[:10]), []).append(v)
        res[k] = {d: (max(v), min(v)) for d, v in dies.items() if len(v) == 24}
    return res


def avalua(obs, prev):
    """Para cada antelación y para la máxima y la mínima: el error medio
    absoluto de cada método y si la mejora sobre el modelo tal cual es segura."""
    informe = {}
    for k in ANTELACIONS:
        dies = sorted(d for d in prev[k] if d in obs)
        for i, nom in enumerate(("maxima", "minima")):
            x = {d: prev[k][d][i] for d in dies}
            y = {d: obs[d][i] for d in dies}
            err = {d: y[d] - x[d] for d in dies}
            metodes = {"model": {d: x[d] for d in dies}}
            for w in FINESTRES:
                # El día de la previsión (d − k) solo se conocen los días medidos hasta d − k − 1.
                c = {}
                for d in dies:
                    fins = d - dt.timedelta(days=k)
                    passat = [err[e] for e in dies if fins - dt.timedelta(days=w) <= e < fins]
                    if len(passat) >= w // 2:
                        c[d] = x[d] + float(np.mean(passat))
                metodes[f"sesgo_{w}"] = c
            reg = {}
            for d in dies:
                ent = [e for e in dies if (e.year, e.month) != (d.year, d.month)]
                b, a = np.polyfit([x[e] for e in ent], [y[e] for e in ent], 1)
                reg[d] = a + b * x[d]
            metodes["regressio"] = reg
            # Mismos días para todos: los que tienen todas las correcciones.
            comuns = [d for d in dies if all(d in m for m in metodes.values())]
            blocs = ["%d-%02d" % d.isocalendar()[:2] for d in comuns]
            base = [abs(y[d] - metodes["model"][d]) for d in comuns]
            fila = {"dies": len(comuns), "biaix_model": round(float(np.mean([err[d] for d in comuns])), 2)}
            for m, v in metodes.items():
                e = [abs(y[d] - v[d]) for d in comuns]
                fila[m] = {"mae": round(float(np.mean(e)), 2),
                           "seguretat": None if m == "model" else R.seguretat(e, base, blocs)}
            informe[f"{k}_{nom}"] = fila
    return informe


def main():
    if "--descarrega" in sys.argv or not os.path.exists(PREVIST):
        descarrega()
    informe = avalua(mesurat(), previst())
    print(f"{'':12} {'dies':>4} {'biaix':>6} " + " ".join(f"{m:>16}" for m in
          ["model"] + [f"sesgo_{w}" for w in FINESTRES] + ["regressio"]))
    for clau, f in informe.items():
        cel = []
        for m in ["model"] + [f"sesgo_{w}" for w in FINESTRES] + ["regressio"]:
            s = f[m]["seguretat"]
            cel.append(f"{f[m]['mae']:>6.2f}" + (f" ({s:.2f})" if s is not None else "") .rjust(10))
        print(f"{clau:12} {f['dies']:>4} {f['biaix_model']:>6.2f} " + " ".join(f"{c:>16}" for c in cel))
    return informe


if __name__ == "__main__":
    main()
