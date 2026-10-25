#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La estación de casa en Weather Underground y las estaciones vecinas de
esa red (ADR 0059 y 0060).

Subida: en cada pasada de la página, con la lectura de Ecowitt que ya se ha
hecho, se manda a la red de estaciones personales de Weather Underground lo
que mide la estación: temperatura, humedad, punto de rocío, presión al nivel
del mar, lluvia de la última hora y del día, radiación y UV. El viento no,
porque el anemómetro no funciona bien (ADR 0017). Así la estación cuenta
como contribuidora y tiene la clave de lectura de esa red.

Lectura: con esa clave, las estaciones vecinas de config.VEINES (una
consulta por estación y pasada: las lecturas de hoy, cada 5 minutos). Si
alguna de las fiables marca lluvia en los últimos PLOU_ARA_MIN minutos,
llueve (casa.py); sus horas completas van al registro del NAS
(registre.py, veina-<id>.csv) y la más fiable confirma las horas secas para
aprender (aprenentatge.py).

Las claves no están en el repositorio: WU_STATION_ID, WU_STATION_KEY y
WU_API_KEY en el entorno o en ~/.config/meteo-local/wunderground.env. Sin
las dos primeras no se sube; sin la tercera no se lee.

Uso:
  python3 wunderground.py puja      lee Ecowitt y sube una vez
  python3 wunderground.py mostra    enseña lo que se mandaría, sin subir
  python3 wunderground.py veines    lo que miden ahora las vecinas
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import config as C
import hora as H
import ecowitt as E

URL = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
PROGRAMA = "meteo-local"
# Con una estación recién dada de alta, Weather Underground contesta
# «unauthorized» a ratos, hasta que las credenciales llegan a todos sus
# servidores (09-10-2026: la misma petición, aceptada y rechazada en
# minutos): se vuelve a probar un par de veces antes de darlo por fallido.
INTENTS = 3
PAUSA_S = 3


URL_API = "https://api.weather.com/v2/pws"
# Una lectura de «ahora» con más de estos minutos no vale (como casa.py).
ARA_MAX_MIN = 30


def _entorn(noms):
    e = {k: os.environ.get(k) for k in noms}
    if all(e.values()):
        return e
    ruta = os.path.expanduser("~/.config/meteo-local/wunderground.env")
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                k, _, v = linea.strip().partition("=")
                if k in e and not e[k]:
                    e[k] = v
    except OSError:
        pass
    return e if all(e.values()) else None


def claves():
    """Las de subida de la estación de casa."""
    return _entorn(("WU_STATION_ID", "WU_STATION_KEY"))


def disponible():
    return claves() is not None


def clau_lectura():
    """La clave de lectura de la red (la da a quien aporta una estación)."""
    e = _entorn(("WU_API_KEY",))
    return e and e["WU_API_KEY"]


def lectura_disponible():
    return clau_lectura() is not None


def dies_fins_caducitat(ahora=None):
    """Días que le quedan a la clave de lectura (config.WU_CLAU_CADUCA)."""
    ahora = ahora or H.ara()
    return (dt.date.fromisoformat(C.WU_CLAU_CADUCA) - H.dia_local(ahora)).days


def _f(c):
    return None if c is None else round(c * 9 / 5 + 32, 1)


def _polzades(mm):
    return None if mm is None else round(mm / 25.4, 3)


def parametres(casa, ahora=None):
    """Lo que se manda, en las unidades de Weather Underground (°F, inHg,
    pulgadas), a partir de la lectura de ecowitt.resum_ara o ecowitt.ara."""
    hora = H.llegeix(casa["hora"]) if casa.get("hora") else (ahora or H.ara())
    d = {"dateutc": hora.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
         "tempf": _f(casa.get("temperatura")), "humidity": casa.get("humitat"),
         "dewptf": _f(casa.get("rosada")),
         "baromin": None if casa.get("pressio") is None else round(casa["pressio"] / 33.8639, 3),
         "rainin": _polzades(casa.get("pluja_1h")), "dailyrainin": _polzades(casa.get("pluja_avui")),
         "solarradiation": casa.get("solar"), "UV": casa.get("uv"),
         "softwaretype": PROGRAMA, "action": "updateraw"}
    return {k: v for k, v in d.items() if v is not None}


def puja(casa, ahora=None, lector=None):
    """Sube una lectura. Devuelve la respuesta («success») o None sin claves."""
    k = claves()
    if not k:
        return None
    q = urllib.parse.urlencode({"ID": k["WU_STATION_ID"], "PASSWORD": k["WU_STATION_KEY"],
                                **parametres(casa, ahora)})
    if lector:
        return lector(f"{URL}?{q}")
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": PROGRAMA})
    for intent in range(INTENTS):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                resposta = r.read().decode("utf-8", "replace").strip()
            break
        except urllib.error.HTTPError as ex:
            if ex.code != 401 or intent == INTENTS - 1:
                raise
            time.sleep(PAUSA_S)
    if resposta != "success":
        raise RuntimeError(f"Weather Underground: {resposta[:80]}")
    return resposta


# --- Las estaciones vecinas -------------------------------------------------------

def _get(url, lector=None):
    if lector:
        return lector(url)
    req = urllib.request.Request(url, headers={"User-Agent": PROGRAMA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _consulta(ruta, params, lector=None):
    """Una consulta a la API de contribuidores. Sin datos (204), lista vacía."""
    q = urllib.parse.urlencode({**params, "format": "json", "units": "m", "apiKey": clau_lectura()})
    try:
        text = _get(f"{URL_API}/{ruta}?{q}", lector)
    except urllib.error.HTTPError as ex:
        if ex.code == 204:
            return []
        if ex.code in (401, 403):
            raise RuntimeError(f"la clau de lectura no val (HTTP {ex.code}): caduca el {C.WU_CLAU_CADUCA}") from ex
        raise
    if not text.strip():
        return []
    return json.loads(text).get("observations") or []


def files(observacions):
    """Las observaciones de la API (all/1day o history/all) con la forma de
    las lecturas de Ecowitt: «t», «pluja_avui» (acumulada del día, que
    vuelve a cero cuando la estación cambia de día: no siempre a
    medianoche local), temperatura, humedad, rocío, presión (la que publica
    la estación, que no todas reducen al nivel del mar), viento y racha en
    km/h e intensidad en mm/h."""
    res = []
    for o in observacions:
        m = o.get("metric") or {}
        t = H.utc(o["obsTimeUtc"])
        pressio = [m.get("pressureMax"), m.get("pressureMin")]
        pressio = [p for p in pressio if p is not None]
        res.append({"t": t, "pluja_avui": m.get("precipTotal"), "temperatura": m.get("tempAvg"),
                    "humitat": o.get("humidityAvg"), "rosada": m.get("dewptAvg"),
                    "pressio": round(sum(pressio) / len(pressio), 1) if pressio else None,
                    "vent": m.get("windspeedAvg"), "ratxa": m.get("windgustHigh"),
                    "intensitat": m.get("precipRate")})
    return sorted(res, key=lambda f: f["t"])


def veina_ara(estacio, filas, ahora=None):
    """Lo que mide ahora una vecina, con la lluvia de los últimos
    PLOU_ARA_MIN minutos y de la última hora. Solo cuenta el sí, como en casa
    (ADR 0017). Falla si la última lectura es vieja."""
    ahora = ahora or H.ara()
    if not filas:
        raise RuntimeError("sense lectures d'avui")
    ultima = filas[-1]
    if ahora - ultima["t"] > dt.timedelta(minutes=ARA_MAX_MIN):
        raise RuntimeError(f"l'última lectura és de les {H.local(ultima['t']):%H:%M}")
    hora = ultima["t"]
    # Toda la lluvia sale de las mismas lecturas y hasta el mismo instante
    # (hora, con sus segundos), también la de hoy: la suma de lo que sube el
    # total desde la medianoche local, porque el total del día de Weather
    # Underground no siempre vuelve a cero a medianoche. Hasta la 3.145.0 la
    # de hoy se calculaba en casa.py hasta la hora sin segundos y perdía la
    # última lectura: el 19-10-2026 a las 06:09, 0,1 mm de hoy con 0,2 en la
    # última hora (ADR 0085).
    v = {"estacio": estacio, "nom": C.VEINES.get(estacio, {}).get("nom", estacio),
         "hora": H.iso_local(hora),
         **{k: ultima.get(k) for k in ("temperatura", "humitat", "rosada", "pressio", "vent", "ratxa",
                                       "intensitat")},
         "pluja_avui_wu": ultima.get("pluja_avui"),
         # Des de la mitjanit de Madrid (fins a la 3.200.0, el dia del canvi
         # d'hora es comptava des d'una hora de més o de menys).
         "pluja_avui": E.pluja_entre(filas, H.mitjanit(H.dia_local(hora)), hora),
         "pluja_15min": E.pluja_entre(filas, hora - dt.timedelta(minutes=C.PLOU_ARA_MIN), hora),
         "pluja_30min": E.pluja_entre(filas, hora - dt.timedelta(minutes=30), hora),
         "pluja_1h": E.pluja_entre(filas, hora - dt.timedelta(hours=1), hora),
         "pluja_3h": E.pluja_entre(filas, hora - dt.timedelta(hours=3), hora)}
    v["plou"] = v["pluja_15min"] > 0
    v["compta"] = bool(C.VEINES.get(estacio, {}).get("plou"))
    v["files"] = filas
    return v


def veines_ara(ahora=None, lector=None):
    """Las vecinas de config.VEINES que se han podido leer y los fallos
    («ICERDA18: l'última lectura és de les 23:52»). Una consulta por
    estación: las lecturas de hoy."""
    ahora = ahora or H.ara()
    res, errors = [], []
    for estacio in C.VEINES:
        try:
            res.append(veina_ara(estacio, files(_consulta("observations/all/1day", {"stationId": estacio},
                                                           lector)), ahora))
        except Exception as ex:
            errors.append(f"{estacio}: {ex}")
    return res, errors


def hores_ahir(estacio, ahora, lector=None):
    """Las lecturas de ayer (cada 5 minutos), para cerrar en el registro la
    última hora del día, que las de hoy no cubren."""
    ahir = (H.dia_local(ahora) - dt.timedelta(days=1)).strftime("%Y%m%d")
    return files(_consulta("history/all", {"stationId": estacio, "date": ahir}, lector))


def observacio(v):
    """Una vecina con la forma de las demás estaciones (prevision.observaciones),
    solo si marca lluvia y cuenta para «plou ara»."""
    if not v or not v.get("plou") or not v.get("compta"):
        return None
    return {"estacion": v["estacio"], "font": "Weather Underground", "mm_hoy": v.get("pluja_avui"),
            "mm_ultima_media_hora": E.pluja_entre(v["files"], H.llegeix(v["hora"]) - dt.timedelta(minutes=30),
                                                  H.llegeix(v["hora"])) if v.get("files") else v["pluja_15min"],
            "intensitat": v.get("intensitat"), "hasta": v["hora"]}


def plou_a_les_veines(veines):
    """Llueve en alguna vecina que cuenta para «plou ara»."""
    return any(v.get("plou") and v.get("compta") for v in veines or [])


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden in ("puja", "mostra"):
        if not E.disponible():
            sys.exit("sense claus d'Ecowitt")
        casa = E.resum_ara()
        print(parametres(casa))
        if orden == "puja":
            print(puja(casa) or "sense claus de Weather Underground: no es puja")
    elif orden == "veines":
        if not lectura_disponible():
            sys.exit("sense clau de lectura de Weather Underground")
        veines, errors = veines_ara()
        for v in veines:
            print(v["estacio"], v["nom"], v["hora"], "PLOU" if v["plou"] else "no plou",
                  f"{v['pluja_1h']} mm/1h", f"{v['pluja_avui']} mm avui", f"{v['temperatura']} °C",
                  f"{v['pressio']} hPa", f"vent {v['vent']} km/h", "(no compta)" if not v["compta"] else "")
        for e in errors:
            print("fallo:", e)
        print("La clau de lectura caduca d'aquí a", dies_fins_caducitat(), "dies")
    else:
        print(__doc__)
