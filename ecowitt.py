#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La estación de casa, con la API oficial de Ecowitt (v3) (ADR 0017).

Las claves y la dirección MAC no están en el repositorio: se leen de las
variables ECOWITT_APPLICATION_KEY, ECOWITT_API_KEY y ECOWITT_MAC o, si no
están, de ~/.config/meteo-local/ecowitt.env. Sin ellas, la estación
simplemente no está disponible y todo sigue con Montflorit.

El anemómetro no funciona bien y no se usa. El pluviómetro fue bien hasta
principios de septiembre de 2026; desde entonces a veces no marca la lluvia
débil: si marca lluvia, llueve, pero un cero no asegura que no llueva
(config.PLUVIOMETRE_CASA_FIABLE_FINS).

Uso:
  python3 ecowitt.py ara                       lo que mide ahora
  python3 ecowitt.py historial INICI FI FITXER  descarga a CSV (fechas AAAA-MM-DD)
"""
import csv
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

import config as C
import hora as H

API = "https://api.ecowitt.net/api/v3/device/"
UNIDADES = {"temp_unitid": 1, "pressure_unitid": 3, "rainfall_unitid": 12,
            "solar_irradiance_unitid": 16}
CAMPOS = "outdoor,pressure,solar_and_uvi,rainfall"
# Días que admite cada consulta del historial según su resolución, y cuánto
# tiempo atrás la guarda Ecowitt.
TRAMOS = {"5min": (1, 90), "30min": (7, 365)}
PAUSA_S = 1.5   # entre consultas del historial
COLUMNAS = ["t", "temperatura", "humitat", "rosada", "pressio", "solar", "intensitat", "pluja_avui"]


def claves():
    e = {k: os.environ.get(k) for k in ("ECOWITT_APPLICATION_KEY", "ECOWITT_API_KEY", "ECOWITT_MAC")}
    if all(e.values()):
        return e
    ruta = os.path.expanduser("~/.config/meteo-local/ecowitt.env")
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                k, _, v = linea.strip().partition("=")
                if k in e and not e[k]:
                    e[k] = v
    except OSError:
        pass
    return e if all(e.values()) else None


def disponible():
    return claves() is not None


def consulta(orden, **params):
    k = claves()
    if not k:
        raise RuntimeError("sense claus d'Ecowitt")
    q = urllib.parse.urlencode({"application_key": k["ECOWITT_APPLICATION_KEY"],
                                "api_key": k["ECOWITT_API_KEY"], "mac": k["ECOWITT_MAC"],
                                **UNIDADES, **params})
    req = urllib.request.Request(f"{API}{orden}?{q}", headers={"User-Agent": "meteo-local"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    if d.get("code") != 0:
        raise RuntimeError(f"Ecowitt: {d.get('msg')}")
    return d["data"]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _valor(d, grupo, campo):
    return _num(((d.get(grupo) or {}).get(campo) or {}).get("value"))


def pressio_mar(p_estacio, temperatura, altitud=None):
    """Presión reducida al nivel del mar (hPa) a partir de la medida a la
    altura de la estación, con la fórmula hipsométrica y la temperatura del
    aire (a falta de ella, 15 °C). La «relativa» de Ecowitt no está calibrada
    y sale igual que la absoluta (ADR 0037)."""
    if p_estacio is None:
        return None
    h = C.ALTITUD_CASA_M if altitud is None else altitud
    t = 15.0 if temperatura is None else temperatura
    # Temperatura media de la columna, en K: la de la estación más la mitad
    # del gradiente estándar (0,0065 K/m).
    tm = t + 273.15 + 0.0065 * h / 2
    return round(p_estacio * math.exp(9.80665 * h / (287.05 * tm)), 1)


def ara():
    """Lo que mide ahora, con la hora de la lectura."""
    d = consulta("real_time", call_back=CAMPOS)
    t = int(d["outdoor"]["temperature"]["time"])
    temperatura = _valor(d, "outdoor", "temperature")
    return {"hora": H.iso_local(dt.datetime.fromtimestamp(t, H.UTC)),
            "temperatura": temperatura,
            "humitat": _valor(d, "outdoor", "humidity"),
            "rosada": _valor(d, "outdoor", "dew_point"),
            "pressio": pressio_mar(_valor(d, "pressure", "absolute"), temperatura),
            "solar": _valor(d, "solar_and_uvi", "solar"),
            "uv": _valor(d, "solar_and_uvi", "uvi"),
            "intensitat": _valor(d, "rainfall", "rain_rate"),
            "pluja_1h": _valor(d, "rainfall", "1_hour"),
            "pluja_avui": _valor(d, "rainfall", "daily")}


def _filas(d):
    series = {"temperatura": ("outdoor", "temperature"), "humitat": ("outdoor", "humidity"),
              "rosada": ("outdoor", "dew_point"), "pressio": ("pressure", "absolute"),
              "solar": ("solar_and_uvi", "solar"), "intensitat": ("rainfall", "rain_rate"),
              "pluja_avui": ("rainfall", "daily")}
    filas = {}
    for nombre, (g, c) in series.items():
        for t, v in (((d.get(g) or {}).get(c) or {}).get("list") or {}).items():
            filas.setdefault(int(t), {})[nombre] = _num(v)
    for f in filas.values():
        if "pressio" in f:
            f["pressio"] = pressio_mar(f["pressio"], f.get("temperatura"))
    return [{"t": dt.datetime.fromtimestamp(t, H.UTC), **filas[t]} for t in sorted(filas)]


def historial(inici, fi, cicle="5min"):
    """Lecturas entre dos momentos (con zona horaria), en tramos que la API
    admite. 5min: los últimos 90 días; 30min: el último año."""
    dias, _ = TRAMOS[cicle]
    res, a = [], inici
    while a < fi:
        b = min(a + dt.timedelta(days=dias) - dt.timedelta(seconds=1), fi)
        # La API corta si se le pregunta muy seguido: pausa entre tramos y,
        # si corta, espera y vuelve a probar.
        for intento in range(6):
            try:
                # L'API vol l'hora de rellotge de l'estació, la de Madrid.
                d = consulta("history", start_date=H.local(a).strftime("%Y-%m-%d %H:%M:%S"),
                             end_date=H.local(b).strftime("%Y-%m-%d %H:%M:%S"), cycle_type=cicle,
                             call_back="outdoor.temperature,outdoor.humidity,outdoor.dew_point,"
                                       "pressure.absolute,solar_and_uvi.solar,rainfall.rain_rate,"
                                       "rainfall.daily")
                break
            except RuntimeError as ex:
                if not any(m in str(ex) for m in ("upper limit", "too frequent")) or intento == 5:
                    raise
                time.sleep(30 * (intento + 1))
        res += _filas(d or {})
        time.sleep(PAUSA_S)
        a = b + dt.timedelta(seconds=1)
    vistos, unicas = set(), []
    for f in res:
        if f["t"] not in vistos:
            vistos.add(f["t"])
            unicas.append(f)
    return unicas


def pluja_entre(filas, ini, fin):
    """mm entre ini y fin con el acumulado diario (vuelve a cero a medianoche)."""
    mm = 0.0
    for antes, despues in zip(filas, filas[1:]):
        if ini < despues["t"] <= fin and antes.get("pluja_avui") is not None \
                and despues.get("pluja_avui") is not None:
            salto = despues["pluja_avui"] - antes["pluja_avui"]
            mm += despues["pluja_avui"] if salto < 0 else salto
    return round(mm, 1)


def tendencia_pressio(filas, hora, horas=3):
    """Cambio de presión en las últimas horas (hPa), con las lecturas más
    cercanas a hora y a hora - horas (a 15 minutos como mucho)."""
    def cerca(t):
        c = [f for f in filas if f.get("pressio") is not None and abs((f["t"] - t).total_seconds()) <= 900]
        return min(c, key=lambda f: abs((f["t"] - t).total_seconds()))["pressio"] if c else None
    a, b = cerca(hora - dt.timedelta(hours=horas)), cerca(hora)
    return None if a is None or b is None else round(b - a, 1)


def resum_ara(ahora=None):
    """Lo que mide ahora la estación, con la lluvia de la última media hora y
    de la última hora y el cambio de presión en tres horas. Dos consultas:
    la lectura de ahora (cada minuto) y las tres últimas horas (cada cinco)."""
    ahora = ahora or H.ara()
    a = ara()
    hora = H.llegeix(a["hora"])
    filas = historial(ahora - dt.timedelta(hours=3, minutes=15), ahora, "5min")
    if a["pluja_avui"] is not None:
        filas.append({"t": hora, "pluja_avui": a["pluja_avui"], "pressio": a["pressio"]})
    a["pluja_15min"] = pluja_entre(filas, hora - dt.timedelta(minutes=C.PLOU_ARA_MIN), hora)
    a["pluja_30min"] = pluja_entre(filas, hora - dt.timedelta(minutes=30), hora)
    a["pluja_1h"] = pluja_entre(filas, hora - dt.timedelta(hours=1), hora)
    a["pluja_3h"] = pluja_entre(filas, hora - dt.timedelta(hours=3), hora)
    a["pressio_3h"] = tendencia_pressio(filas, hora)
    # Solo vale en positivo: un cero no asegura que no llueva. Ni la
    # intensidad, que tarda en volver a cero, ni la media hora (config.PLOU_ARA_MIN).
    a["plou"] = a["pluja_15min"] > 0
    a["files"] = filas
    return a


def observacio(a, nom):
    """La estación de casa con la forma de las demás (prevision.observaciones),
    solo si marca lluvia: su cero no es fiable."""
    if not a or not a.get("plou"):
        return None
    return {"estacion": nom, "font": "estació de casa (Ecowitt)", "mm_hoy": a["pluja_avui"],
            "mm_ultima_media_hora": a["pluja_30min"], "intensitat": a["intensitat"], "hasta": a["hora"]}


def hores(filas):
    """Horas completas: la lluvia de la hora que acaba en «fins» y las
    lecturas más cercanas a la hora en punto (a 5 minutos como mucho)."""
    if not filas:
        return {}
    filas = sorted(filas, key=lambda f: f["t"])
    lluvia, lecturas, cerca = {}, {}, {}
    for antes, despues in zip(filas, filas[1:]):
        t = despues["t"]
        fin = t.replace(minute=0, second=0, microsecond=0)
        if t != fin:
            fin += dt.timedelta(hours=1)
        lecturas[fin] = lecturas.get(fin, 0) + 1
        if antes.get("pluja_avui") is not None and despues.get("pluja_avui") is not None:
            salto = despues["pluja_avui"] - antes["pluja_avui"]
            lluvia[fin] = lluvia.get(fin, 0.0) + (despues["pluja_avui"] if salto < 0 else salto)
    for f in filas:
        if f.get("temperatura") is None:
            continue
        marca = (f["t"] + dt.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
        dist = abs((f["t"] - marca).total_seconds())
        if dist <= 300 and dist < cerca.get(marca, (999, None))[0]:
            cerca[marca] = (dist, f)
    res = {}
    primera, ultima = filas[0]["t"], filas[-1]["t"]
    # Solo las horas enteras: la primera, cortada, daba la lluvia de unos
    # minutos y en cada pasada se guardaba encima de la buena (el 06-10-2026,
    # 1,3 mm en lugar de 3,5; ADR 0017).
    fin = primera.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    if fin - dt.timedelta(hours=1) < primera:
        fin += dt.timedelta(hours=1)
    while fin <= ultima:
        f = cerca.get(fin, (None, {}))[1]
        res[fin] = {"pluja_mm": round(lluvia.get(fin, 0.0), 1) if lecturas.get(fin) else None,
                    **{k: f.get(k) for k in ("temperatura", "humitat", "rosada", "pressio", "solar")}}
        fin += dt.timedelta(hours=1)
    return res


def guarda_csv(filas, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for fila in filas:
            w.writerow({**fila, "t": fila["t"].isoformat()})


def lee_csv(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [{k: (H.llegeix(v) if k == "t" else _num(v)) for k, v in r.items()}
                for r in csv.DictReader(f)]


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "ara":
        print(json.dumps(ara(), ensure_ascii=False))
    elif orden == "historial":
        ini = H.llegeix(sys.argv[2])
        fin = H.llegeix(sys.argv[3]) + dt.timedelta(days=1)
        hace = (H.ara() - ini).days
        filas = historial(ini, fin, "5min" if hace < TRAMOS["5min"][1] else "30min")
        guarda_csv(filas, sys.argv[4])
        print(len(filas), "lectures")
    else:
        print(__doc__)
