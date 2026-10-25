#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Incidencias de tráfico cerca de Montflorit (ADR 0052).

Las publica el Servei Català de Trànsit en el portal de datos abiertos de la
Generalitat, las mismas que muestra su mapa:

- `incidenciesGML.xml`: cada incidencia con un punto (el inicio del tramo
  afectado), la carretera, los puntos kilométricos, el tipo (2, retención; 3,
  obras), el nivel (2, circulación intensa o calzada restringida; 3,
  retenciones o desvíos; 4, congestión o corte con desvíos; 5, calzada
  cortada), la causa, el texto «cap a» y la hora de su última actualización,
  que no se usa: no es la del inicio, y vista sola parecía que el dato no
  estaba al día (ADR 0052).
- `incidenciesRSS.xml`: las mismas, con el municipio y el sentido escritos
  («Sentit Sud cap a TARRAGONA»). Se cruzan por el identificador; si falla,
  las incidencias salen sin ellos.

Se quedan las que empiezan a C.TRANSIT_RADI_KM o menos de casa: todas las
retenciones (accidentes, averías, circulación) y, de las obras, solo las que
desvían o cortan la vía; el resto son trabajos con un carril restringido que
duran semanas y taparían lo que importa. Los textos son los del Servei Català
de Trànsit, en catalán, y no se traducen. Sin IA.

    python3 transit.py        las de ahora, en JSON
"""
import json
import math
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

import config as C
import hora as H

GML = "https://www.gencat.cat/transit/opendata/incidenciesGML.xml"
RSS = "https://www.gencat.cat/transit/opendata/incidenciesRSS.xml"
UA = {"User-Agent": "Temps a Montflorit (https://meteo-montflorit.github.io/)"}
CITE = "{http://www.opengeospatial.net/cite}"
GMLNS = "{http://www.opengis.net/gml}"
# Particles que van en minúscula en els noms de municipi.
MINUSCULES = {"de", "del", "dels", "la", "les", "el", "els", "i"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    return 6371 * math.hypot((lo2 - lo1) * math.cos((la1 + la2) / 2), la2 - la1)


def nom_municipi(text):
    """«CERDANYOLA DEL VALLÈS» → «Cerdanyola del Vallès»; «SANT ADRIÀ DE BESÒS» →
    «Sant Adrià de Besòs»; «L'HOSPITALET DE LLOBREGAT» → «L'Hospitalet de Llobregat»."""
    res = []
    for n, p in enumerate(text.strip().lower().split()):
        if n and p in MINUSCULES:
            res.append(p)
            continue
        apostrof = re.match(r"^([ld]')(.*)$", p)
        if apostrof:
            article, resta = apostrof.groups()
            res.append((article.capitalize() if n == 0 else article) + resta.capitalize())
        else:
            res.append(p.capitalize())
    return " ".join(res)


def llegeix_gml(dades):
    res = []
    for f in ET.fromstring(dades).iter(CITE + "mct2_v_afectacions_data"):
        d = {e.tag.replace(CITE, ""): (e.text or "").strip() for e in f}
        coords = f.find(".//" + GMLNS + "coordinates")
        try:
            lon, lat = map(float, coords.text.split(","))
            res.append({"id": d["identificador"], "tipus": int(d["tipus"]), "nivell": int(d["nivell"]),
                        "carretera": d.get("carretera"), "pk": (d.get("pk_inici"), d.get("pk_fi")),
                        "causa": d.get("causa") or None, "descripcio": d.get("descripcio") or None,
                        "cap_a": d.get("cap_a") or None, "sentit_gml": d.get("sentit") or None, "lat": lat, "lon": lon})
        except (AttributeError, KeyError, ValueError):
            continue
    return res


def llegeix_rss(dades):
    """{identificador: (municipi, sentit)} de la descripció «AP-7 | MUNICIPI | Sentit … | Punt km. … | hh:mm»."""
    res = {}
    for item in ET.fromstring(dades).iter("item"):
        parts = [p.strip() for p in (item.findtext("description") or "").split("|")]
        if len(parts) >= 3:
            sentit = parts[2]
            res[(item.findtext("guid") or "").strip()] = (nom_municipi(parts[1]) if parts[1] else None, sentit or None)
    return res


def pk(inici, fi):
    """«150.00», «149.50» → «150-149,5»; un sol punt si coincideixen."""
    def net(x):
        try:
            return f"{float(x):g}".replace(".", ",")
        except (TypeError, ValueError):
            return None
    a, b = net(inici), net(fi)
    return a if not b or a == b else f"{a}-{b}" if a else b


def tallada(i):
    text = f"{i['descripcio'] or ''} {i['cap_a'] or ''}".upper()
    return "TALLADA" in text or "TALL TOTAL" in text


def tram_km(i):
    """Llargada del tram afectat, dels punts quilomètrics; None sense."""
    try:
        return abs(float(i["pk"][0]) - float(i["pk"][1]))
    except (TypeError, ValueError, IndexError):
        return None


def es_mostra(i):
    """Retencions, sempre; obres, només si desvien o tallen la via i diuen on:
    amb punt quilomètric i en un tram curt."""
    if i["tipus"] == 2:
        return True
    if i["tipus"] != 3 or not (i["nivell"] >= C.TRANSIT_NIVELL_OBRES or tallada(i)):
        return False
    tram = tram_km(i)
    return tram is not None and tram <= C.TRANSIT_OBRES_TRAM_MAX_KM


def filtra(gml, rss=None, casa=C.CASA):
    rss = rss or {}
    res = []
    for i in gml:
        dist = km(casa, (i["lat"], i["lon"]))
        if dist > C.TRANSIT_RADI_KM or not es_mostra(i):
            continue
        municipi, sentit = rss.get(i["id"], (None, None))
        res.append({"id": i["id"], "tipus": "retencio" if i["tipus"] == 2 else "obres", "nivell": i["nivell"],
                    "carretera": i["carretera"], "municipi": municipi,
                    "sentit": sentit or (i["cap_a"] and f"Cap a {i['cap_a']}"),
                    "causa": i["causa"], "descripcio": i["descripcio"], "pk": pk(*i["pk"]), "km": round(dist, 2)})
    # Primer les retencions, de la més greu a la més lleu; després les obres.
    return sorted(res, key=lambda i: (i["tipus"] != "retencio", -i["nivell"], i["km"]))


def llegeix_sencer(url, llegeix, espera=3):
    """Si el fitxer arriba tallat (el 09-10-2026 a les 12:27, «unclosed token»:
    el Servei Català de Trànsit el devia estar reescrivint), es torna a demanar
    una vegada al cap d'uns segons."""
    try:
        return llegeix(get(url))
    except ET.ParseError:
        time.sleep(espera)
        return llegeix(get(url))


def calcula(ara=None):
    """Per a casa.json i les dades públiques. Sense GML, None (es diu que falla)."""
    ara = ara or H.ara()
    gml = llegeix_sencer(GML, llegeix_gml)
    try:
        rss = llegeix_sencer(RSS, llegeix_rss)
    except Exception:
        rss = None
    return {"hora": H.clau(ara), "incidencies": filtra(gml, rss)}


if __name__ == "__main__":
    print(json.dumps(calcula(), ensure_ascii=False, indent=1))
