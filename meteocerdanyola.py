#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Las estaciones de MeteoCerdanyola (ADR 0130), con el permiso de su
responsable (22-11-2026).

Dos estaciones de config.VEINES con «font»: «meteocerdanyola»:

- **Montflorit** (Davis Vantage Vue, en un tejado a 1,5 m, junto a la riera):
  una vecina más para la lluvia y la temperatura. Su pluviómetro coincide con
  los del barrio, pero tiene marcas sueltas de 0,2 mm con calma y humedad alta
  (rocío): solo cuenta como «plou» con `plou_min_mm` en 15 minutos. Su
  anemómetro está resguardado (marca cero el 73 % de las medias horas en que
  sopla en Sant Cugat): su viento no se usa.
- **Cerdanyola Centre** (Davis Vantage Pro2, en una azotea de cinco plantas,
  a unos 900 m): el viento medio de «Ara» (`vent_ara`), al nivel de las
  estaciones de Meteocat y al minuto. Su temperatura, su humedad y su presión son las de
  la ciudad, no las del barrio: no se leen (`temperatura`: False).

Se lee la serie de las últimas 24 horas de la web, minuto a minuto (unos 25
KB comprimida), una vez por pasada y estación. Da el acumulado de lluvia del
día (PREC, a cero a medianoche), la intensidad (PINT) y el viento de cada
minuto (VEL). La racha no la publica (el campo AGV sale siempre a cero), y el
minuto más alto no la sustituye: el 22-11-2026, con rachas de 55 a 73 km/h en
Sant Cugat, se quedaba en 34 a 42. La racha de «Ara» es la de Sant Cugat
(casa.py).

Uso:
  python3 meteocerdanyola.py            lo que miden ahora las dos estaciones
"""
import datetime as dt
import gzip
import json
import sys
import urllib.request

import config as C
import hora as H
import wunderground as WU

URL = "https://meteocerdanyola.com/2026/api/graphs-series.php?slug={slug}"
PROGRAMA = "meteo-local (Temps a Montflorit)"
FONT = "meteocerdanyola"
# El viento de «Ara»: la media de la última media hora, con lecturas
# suficientes y la última reciente; si no, el de Sant Cugat.
VENT_MINUTS = 30
VENT_LECTURES_MIN = 15
VENT_FRESCA_MIN = 10


def estacions():
    """Las estaciones de MeteoCerdanyola de config.VEINES."""
    return [e for e, v in C.VEINES.items() if v.get("font") == FONT]


def _get(url, lector=None):
    if lector:
        return lector(url)
    req = urllib.request.Request(url, headers={"User-Agent": PROGRAMA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=20) as r:
        dades = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            dades = gzip.decompress(dades)
    return dades.decode("utf-8", "replace")


def _num(x):
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


def files(rows, temperatura=True):
    """Las filas de la serie con la forma de las lecturas de las vecinas
    (wunderground.files): «t» en UTC, «pluja_avui» (el acumulado del día) y el
    resto. Sin presión, que no está reducida como la de casa; sin temperatura
    ni humedad si la estación no es del barrio."""
    res = []
    for r in rows or []:
        if r.get("ts") is None:
            continue
        t = dt.datetime.fromtimestamp(r["ts"] / 1000, dt.timezone.utc)
        f = {"t": t, "pluja_avui": _num(r.get("PREC")), "intensitat": _num(r.get("PINT")),
             "vent": _num(r.get("VEL")), "ratxa": None, "pressio": None,
             "temperatura": None, "humitat": None, "rosada": None}
        if temperatura:
            f.update({"temperatura": _num(r.get("TEMP")), "humitat": _num(r.get("HUM")),
                      "rosada": _num(r.get("DEWPOINT"))})
        res.append(f)
    return sorted(res, key=lambda f: f["t"])


def llegeix(estacio, lector=None):
    """Las lecturas de las últimas 24 horas de una estación."""
    cfg = C.VEINES[estacio]
    d = json.loads(_get(URL.format(slug=cfg["slug"]), lector))
    if not d.get("ok"):
        raise RuntimeError("la web no ha donat dades")
    return files(d.get("rows"), temperatura=cfg.get("temperatura", True))


def veines_ara(ahora=None, lector=None):
    """Las estaciones de MeteoCerdanyola que se han podido leer, con la forma
    de las vecinas (wunderground.veina_ara), y los fallos."""
    ahora = ahora or H.ara()
    res, errors = [], []
    for estacio in estacions():
        try:
            res.append(WU.veina_ara(estacio, llegeix(estacio, lector), ahora))
        except Exception as ex:
            errors.append(f"{estacio}: {ex}")
    return res, errors


def vent_ara(veines, ahora=None):
    """El viento medio de «Ara» de la estación de C.VENT_ARA si tiene
    lecturas recientes: la media de los últimos VENT_MINUTS minutos, sin
    racha (no la publica). None si no: entonces manda Sant Cugat."""
    ahora = ahora or H.ara()
    v = next((x for x in veines or [] if x.get("estacio") == C.VENT_ARA), None)
    if not v:
        return None
    fs = [f for f in v.get("files") or [] if f.get("vent") is not None
          and dt.timedelta(0) <= ahora - f["t"] <= dt.timedelta(minutes=VENT_MINUTS)]
    if len(fs) < VENT_LECTURES_MIN or ahora - fs[-1]["t"] > dt.timedelta(minutes=VENT_FRESCA_MIN):
        return None
    vals = [f["vent"] for f in fs]
    return {"estacio": C.VEINES[C.VENT_ARA]["estacio"], "font": FONT,
            "mitja": round(sum(vals) / len(vals), 1), "ratxa": None,
            "fins": H.iso_local(fs[-1]["t"])}


if __name__ == "__main__":
    veines, errors = veines_ara()
    for v in veines:
        print(v["estacio"], v["hora"], f"{v['temperatura']} °C", f"vent {v['vent']} km/h",
              f"pluja avui {v['pluja_avui']} mm", "plou" if v["plou"] else "")
    print("Vent d'ara:", vent_ara(veines))
    for e in errors:
        print("Error:", e, file=sys.stderr)
