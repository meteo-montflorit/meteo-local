#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La previsión de la semana, de hoy a seis días vista (ADR 0122; Juanjo,
23-10-2026: «la previsión de los proximos 6 días… del cielo, temperatura y
lluvia»).

Los modelos finos de la página (AROME, ICON-EU) no llegan a una semana: la
semana sale de ECMWF a 9 km (config.MODEL_ECMWF), que sí. Hoy y mañana los
pone la página con su propia previsión (casa.js, diesSetmana), para que digan
lo mismo que la gráfica y los tramos; estos datos cubren los siete días por
si faltan.

- **Temperatura**: la máxima y la mínima de las 24 horas de cada día, con la
  corrección de la estación de casa: a cada antelación (días vista), el error
  medio de ECMWF a esa misma antelación en los FINESTRA_DIES días anteriores,
  la máxima y la mínima por separado. ECMWF da las máximas más bajas y las
  mínimas más altas que lo que mide la estación vora la riera; con la
  corrección, el error medio baja de 1,4–2,4 °C a 1,2–2,1 °C según los días
  vista (calibracio/setmana.py, un año de la estación). Sin el registro (la
  reserva de IONOS) o con menos de MIN_DIES días medidos, sin corrección, y
  se dice (`corregit`).
- **La parte alta** (ADR 0123): la misma cuenta con la temperatura de cada
  hora más la diferencia de la parte alta de esa hora (part_alta.a_les_hores),
  y la misma corrección: la parte alta es la riera más esa diferencia.
- **Cielo**: la nubosidad media de ECMWF de 7 a 21 h.
- **Lluvia**: del ensemble de ECMWF (51 miembros, ENSEMBLE_SETMANA), la
  parte de los miembros a los que llueve ese día (C.UMBRAL_MM o más en el
  día) y la lluvia esperada, la media de lo que da cada miembro (ADR 0103).
  Probabilidad sin calibrar: se apunta cada hora (registre.apunta_setmana)
  para comprobarla con lo que llueve.

Las consultas a Open-Meteo, como mucho una vez cada CADA_MIN minutos (ECMWF
sale cada seis horas), y la corrección, una vez al día.
"""
import datetime as dt
import json
import os
import statistics
import sys
import urllib.parse

import config as C
import part_alta as PA
import prevision as P
import registre as R

DIES = 7
FINESTRA_DIES = 30
MIN_DIES = FINESTRA_DIES // 2
MIN_HORES = 22          # horas medidas para dar por buena la máxima y la mínima de un día
ENSEMBLE_SETMANA = "ecmwf_ifs025"
CADA_MIN = 60
CACHE = os.path.join(R.DIR, "setmana-cache.json")
URL = "https://api.open-meteo.com/v1/forecast?"
URL_ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble?"
URL_ANTERIORS = "https://previous-runs-api.open-meteo.com/v1/forecast?"


def _consulta(url, **params):
    q = urllib.parse.urlencode({"latitude": C.CASA[0], "longitude": C.CASA[1], "timezone": P.TZ, **params})
    return P.horas_locales(json.loads(P.get_reintenta(url + q)))["hourly"]


def _per_dies(temps, valors):
    """{dia: [valors]} de una serie por horas (claves de clau_hora)."""
    res = {}
    for t, v in zip(temps, valors):
        if v is not None:
            res.setdefault(t[:10], []).append((int(t[11:13]), v))
    return res


def dies_mesurats(mesurada):
    """{dia: (màxima, mínima)} de lo medido por horas, los días con MIN_HORES o más."""
    dies = {}
    for clau, v in (mesurada or {}).items():
        dies.setdefault(clau[:10], []).append(v)
    return {d: (max(v), min(v)) for d, v in dies.items() if len(v) >= MIN_HORES}


def correccio(avui, mesurada, anteriors=None):
    """{antelació: [màxima, mínima]}: el error medio (medido − previsto) de
    ECMWF a esa antelación en los FINESTRA_DIES días anteriores a hoy. La
    antelación de un día es cuántos días después de hoy cae (de 1 a DIES − 1).
    anteriors: la respuesta de la API de ejecuciones anteriores (para las
    pruebas)."""
    ini = avui - dt.timedelta(days=FINESTRA_DIES)
    if anteriors is None:
        anteriors = _consulta(URL_ANTERIORS, models=C.MODEL_ECMWF, start_date=ini.isoformat(),
                              end_date=(avui - dt.timedelta(days=1)).isoformat(),
                              hourly=",".join(f"temperature_2m_previous_day{k}" for k in range(1, DIES)))
    obs = dies_mesurats(mesurada)
    res = {}
    for k in range(1, DIES):
        prev = _per_dies(anteriors["time"], anteriors.get(f"temperature_2m_previous_day{k}") or [])
        errors = [(obs[d][0] - max(v for _, v in h), obs[d][1] - min(v for _, v in h))
                  for d, h in prev.items() if d in obs and len(h) >= 23 and ini.isoformat() <= d < avui.isoformat()]
        if len(errors) >= MIN_DIES:
            res[k] = [round(statistics.fmean(e[0] for e in errors), 2), round(statistics.fmean(e[1] for e in errors), 2)]
    return res


def alta_per_dies(model, taula, ajust=None):
    """{dia: [temperatura de la parte alta a cada hora]}: la de ECMWF más la
    diferencia de la parte alta de su hora, con el ajuste de las noches por
    las nubes y el viento, lo mismo que la previsión por horas
    (part_alta.a_les_hores; ADR 0087 y 0123)."""
    temps = model["time"]
    files = [{"hora": t, "fins": temps[i + 1] if i + 1 < len(temps) else t, "temperatura": v,
              "nuvols": (model.get("cloud_cover") or [None] * len(temps))[i],
              "vent": (model.get("wind_speed_10m") or [None] * len(temps))[i]}
             for i, (t, v) in enumerate(zip(temps, model.get("temperature_2m") or [])) if v is not None]
    PA.a_les_hores(files, taula, ajust)
    res = {}
    for f in files:
        res.setdefault(f["hora"][:10], []).append(f["temperatura"] + (f["dif_alta"] or 0))
    return res


def dies(avui, model, ensemble, corr, taula=None, ajust=None):
    """Los DIES días desde hoy: máxima y mínima (corregidas si hay
    corrección para esa antelación), también en la parte alta si hay
    tabla de diferencias (taula), nubosidad media de 7 a 21 h, probabilidad
    de lluvia y lluvia esperada."""
    temp = _per_dies(model["time"], model.get("temperature_2m") or [])
    altes = alta_per_dies(model, taula, ajust) if taula else {}
    nuvols = _per_dies(model["time"], model.get("cloud_cover") or [])
    codis = _per_dies(model["time"], model.get("weather_code") or [])
    membres = [_per_dies(ensemble["time"], v) for k, v in ensemble.items() if k.startswith("precipitation")]
    res = []
    for i in range(DIES):
        d = (avui + dt.timedelta(days=i)).isoformat()
        t = [v for _, v in temp.get(d, [])]
        if len(t) < 23:
            continue
        c = corr.get(i) if i else corr.get(1)
        dia = {"dia": d, "max": round(max(t) + (c[0] if c else 0), 1), "min": round(min(t) + (c[1] if c else 0), 1),
               "corregit": bool(c)}
        if len(altes.get(d, [])) >= 23:
            dia["max_alta"] = round(max(altes[d]) + (c[0] if c else 0), 1)
            dia["min_alta"] = round(min(altes[d]) + (c[1] if c else 0), 1)
        n = [v for h, v in nuvols.get(d, []) if 7 <= h < 21]
        dia["nuvols"] = round(statistics.fmean(n)) if n else None
        dia["codi"] = max((v for _, v in codis.get(d, [])), default=None)
        totals = [sum(v for _, v in m[d]) for m in membres if len(m.get(d, [])) >= 23]
        if totals:
            dia["probabilitat"] = round(sum(x >= C.UMBRAL_MM for x in totals) / len(totals), 2)
            dia["pluja_mm"] = round(max(statistics.fmean(totals), 0), 1)
            dia["membres"] = len(totals)
        res.append(dia)
    return res


def calcula(ahora, taula=None):
    """La semana para la página. Con registro, lo guardado si tiene menos de
    CADA_MIN minutos; la corrección, la del día si ya está calculada."""
    avui = ahora.date()
    cache = {}
    if R.hay_registro() and os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("llegit") and ahora - dt.datetime.fromisoformat(cache["llegit"]) < dt.timedelta(minutes=CADA_MIN) \
                and cache.get("dies") and cache["dies"][0]["dia"] == avui.isoformat():
            return cache["dies"]
    corr, dia_corr = {}, None
    if R.hay_registro():
        if cache.get("correccio_dia") == avui.isoformat():
            corr, dia_corr = {int(k): v for k, v in cache["correccio"].items()}, avui.isoformat()
        else:
            # Lo medido cada hora en los días de la ventana, del registro. Si
            # falla, sin corrección y se vuelve a probar en la próxima consulta.
            try:
                corr = correccio(avui, R.temperatures_casa(ahora, hores=24 * (FINESTRA_DIES + 1)))
                dia_corr = avui.isoformat()
            except Exception as ex:
                print("No he pogut calcular la correcció de la setmana:", ex, file=sys.stderr)
    fi = (avui + dt.timedelta(days=DIES - 1)).isoformat()
    model = _consulta(URL, models=C.MODEL_ECMWF, start_date=avui.isoformat(), end_date=fi,
                      hourly="temperature_2m,cloud_cover,weather_code,wind_speed_10m")
    try:
        ensemble = _consulta(URL_ENSEMBLE, models=ENSEMBLE_SETMANA, start_date=avui.isoformat(), end_date=fi,
                             hourly="precipitation")
    except Exception as ex:
        # Sin el ensemble, la semana sigue sin la lluvia.
        print("No he pogut llegir l'ensemble de la setmana:", ex, file=sys.stderr)
        ensemble = {"time": []}
    res = dies(avui, model, ensemble, corr, taula, PA.ajust_nit())
    if R.hay_registro():
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump({"llegit": ahora.isoformat(timespec="minutes"), "dies": res,
                       "correccio_dia": dia_corr, "correccio": corr}, f)
        R.apunta_setmana(ahora, res)
    return res
