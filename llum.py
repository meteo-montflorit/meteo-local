#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Los cortes de luz cerca de Montflorit, para la consulta «Llum» (ADR 0072).

Salen de la capa pública que dibuja el mapa de averías de e-distribución
(la distribuidora de Endesa, que es la de Cerdanyola), en el servidor ArcGIS
de Enel: averías y trabajos programados en curso, con el municipio, los
clientes afectados, el inicio, la hora prevista de vuelta y una nota. **No
lleva calles**: el punto es aproximado a propósito («la ubicación … es
orientativa», dice e-distribución), así que no se da una calle que podría ser
otra. Solo cuentan los del barrio: dentro de los límites de Montflorit
(montflorit-limits.geojson, retocados por Juanjo el 11-10-2026) o a
LLUM_MARGE_KM o menos de ellos, por lo aproximado del punto.

Como e-distribución no da la calle, se estima (Juanjo, 11-10-2026: «da una
calle probable o un par … avisando que el servicio no ofrece este dato y es
una estimación»): la calle con nombre más cercana al punto, de las de
montflorit-carrers.geojson (OpenStreetMap), y una segunda si está casi igual
de cerca (CARRER_SEGON_M de diferencia como mucho); ninguna si la más cercana
está a más de CARRER_MAX_M.

Las calles y los portales de los trabajos programados sí están en el
buscador de Endesa (wtp-pro.endesa.com), pero está protegido contra la
lectura automática: no se lee, se enlaza (Juanjo, 11-10-2026).

    python3 llum.py        lo que hay ahora, en JSON
"""
import datetime as dt
import json
import math
import re
import sys
import urllib.parse
import urllib.request

import os

import config as C
import hora as H

CAPA = ("https://dpa-portalgis.enel.com/server/rest/services/Hosted/"
        "ESP_Prod_power_cut_View/FeatureServer/0")
UA = {"User-Agent": "Temps a Montflorit (https://meteo-montflorit.github.io/)"}
CAMPS = ("cd_code,service_type,service_des_ca,service_des_es,des_cause_ca,des_cause_es,affected_client,"
         "interruption_date,reposition_date,note,update_time,municipality")


def get(url, params):
    url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    return 6371 * math.hypot((lo2 - lo1) * math.cos((la1 + la2) / 2), la2 - la1)


def hora(text):
    """«10/10/2026 23:12» (hora peninsular) → ISO con zona; None si no se entiende."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2})", text or "")
    if not m:
        return None
    d, mes, a, h, mi = (int(x) for x in m.groups())
    return H.clau(dt.datetime(a, mes, d, h, mi, tzinfo=H.ZONA))


LIMITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "montflorit-limits.geojson")
CARRERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "montflorit-carrers.geojson")
CARRER_MAX_M = 150
CARRER_SEGON_M = 40


def limits():
    """Los anillos del barrio, como [(lat, lon), …]."""
    with open(LIMITS, encoding="utf-8") as f:
        return [[(y, x) for x, y in f["geometry"]["coordinates"][0]] for f in json.load(f)["features"]]


def dins(p, anell):
    y, x = p
    c = False
    for (y1, x1), (y2, x2) in zip(anell, anell[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def km_segment(p, a, b):
    """Distancia del punto al segmento, en km (plano local)."""
    cos = math.cos(math.radians(p[0]))
    px, py = p[1] * cos, p[0]
    ax, ay, bx, by = a[1] * cos, a[0], b[1] * cos, b[0]
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy) * math.pi / 180 * 6371


def carrers():
    """{nom: [tram, …]}, cada tram como [(lat, lon), …]."""
    with open(CARRERS, encoding="utf-8") as f:
        return {c["properties"]["nom"]: [[(y, x) for x, y in tram] for tram in c["geometry"]["coordinates"]]
                for c in json.load(f)["features"]}


def carrers_probables(p, vies=None):
    """La calle más cercana al punto y, si hay otra casi igual de cerca, esa
    también; [] si no hay ninguna a CARRER_MAX_M o menos. Es una estimación:
    el punto de e-distribución es aproximado."""
    vies = vies if vies is not None else carrers()
    dist = sorted((min(km_segment(p, a, b) for tram in trams for a, b in zip(tram, tram[1:])) * 1000, nom)
                  for nom, trams in vies.items())
    if not dist or dist[0][0] > CARRER_MAX_M:
        return []
    res = [dist[0][1]]
    if len(dist) > 1 and dist[1][0] <= min(CARRER_MAX_M, dist[0][0] + CARRER_SEGON_M):
        res.append(dist[1][1])
    return res


def al_barri(p, anells):
    """«dins», «vora» (a LLUM_MARGE_KM o menos del límite) o None."""
    if any(dins(p, a) for a in anells):
        return "dins"
    if min(km_segment(p, a, b) for anell in anells for a, b in zip(anell, anell[1:])) <= C.LLUM_MARGE_KM:
        return "vora"
    return None


def calcula(ara=None, dades=None):
    """Los cortes en curso de Montflorit (al_barri), del más cercano a casa
    al más lejano, y la hora de la consulta."""
    ara = ara or H.ara()
    anells = limits()
    vies = carrers()
    marge = C.LLUM_MARGE_KM / 100            # en grados, de sobra
    lats = [y for a in anells for y, _ in a]
    lons = [x for a in anells for _, x in a]
    d = dades or get(CAPA + "/query", {
        "where": "1=1", "geometry": f"{min(lons) - marge},{min(lats) - marge},{max(lons) + marge},{max(lats) + marge}",
        "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
        "outFields": CAMPS, "returnGeometry": "true", "outSR": 4326, "f": "json"})
    if "error" in d:
        raise RuntimeError(d["error"].get("message"))
    talls = []
    for f in d.get("features") or []:
        a, g = f["attributes"], f.get("geometry") or {}
        if "x" not in g:
            continue
        on = al_barri((g["y"], g["x"]), anells)
        if not on:
            continue
        talls.append({
            "id": f"{a.get('cd_code') or '?'}:{a.get('interruption_date') or '?'}",
            "on": on,
            "carrers": carrers_probables((g["y"], g["x"]), vies),
            "programat": a.get("service_type") == "LV",
            "tipus": {"ca": a.get("service_des_ca") or a.get("service_des_es"), "es": a.get("service_des_es")},
            "causa": {"ca": a.get("des_cause_ca") or a.get("des_cause_es"), "es": a.get("des_cause_es")},
            "clients": a.get("affected_client"),
            "inici": hora(a.get("interruption_date")),
            "fins": hora(a.get("reposition_date")),
            "nota": (a.get("note") or "").strip() or None,
            "municipi": a.get("municipality"),
            "km": round(km(C.CASA, (g["y"], g["x"])), 2),
            # El punt aproximat d'e-distribució, per al mapa de «Llum» (ADR 0077),
            # arrodonit a uns 10 m: el punt mateix ja és aproximat.
            "lat": round(g["y"], 4), "lon": round(g["x"], 4),
            "actualitzat": hora(a.get("update_time")),
        })
    return {"hora": H.clau(ara), "talls": sorted(talls, key=lambda t: t["km"])}


# Lo que la consulta necesita de la capa: si falta, ha cambiado.
CAMPS_NECESSARIS = {"service_type", "affected_client", "interruption_date", "reposition_date", "municipality"}


def prova(get_json=None):
    """Si la capa responde con lo que hace falta. None si va bien; si no, por qué."""
    get_json = get_json or get
    try:
        d = get_json(CAPA, {"f": "json"})
        if "error" in d:
            return f"la capa respon amb un error: {d['error'].get('message')}"
        falten = CAMPS_NECESSARIS - {f["name"] for f in d.get("fields") or []}
        if falten:
            return "a la capa li falten camps: " + ", ".join(sorted(falten))
        q = get_json(CAPA + "/query", {"where": "1=1", "returnCountOnly": "true", "f": "json"})
        if "count" not in q:
            return "la capa no respon a les consultes"
    except Exception as ex:
        return str(ex)[:200]
    return None


def comprova(marca, avisa=True, get_json=None):
    """La prueba diaria (aprenentatge.diari; Juanjo, 11-10-2026: «hay que vigilar
    que este servicio funcione»): como la capa no es un servicio documentado,
    si deja de responder o cambia se le dice una vez a Juanjo, y otra cuando
    vuelve (marca llum-falla). Mientras falla, la consulta dice que no hay datos."""
    import os
    import subprocess
    error = prova(get_json)
    text = None
    if error and not os.path.exists(marca):
        open(marca, "w").close()
        text = (f"Temps a Montflorit: el mapa de talls de llum d'e-distribució ha deixat de funcionar ({error}). "
                "La consulta «Llum» i /llum diuen que no hi ha dades fins que es torni a llegir: mira llum.py.")
    elif not error and os.path.exists(marca):
        os.remove(marca)
        text = "Temps a Montflorit: el mapa de talls de llum d'e-distribució torna a funcionar."
    if text:
        print(text)
        if avisa:
            subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", text], check=False)
    return error


if __name__ == "__main__":
    json.dump(calcula(), sys.stdout, ensure_ascii=False, indent=1)
    print()
