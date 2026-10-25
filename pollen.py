#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El polen y las esporas de la semana en Bellaterra (ADR 0054).

Los publica el Punt d'Informació Aerobiològica (PIA) de la UAB, de la Xarxa
Aerobiològica de Catalunya, con su API (`aerobiologia.cat/api/v0/forecast/…`,
XML, sin clave): para cada tipo de polen y de espora, el nivel de la semana
(0 nulo, 1 bajo, 2 medio, 3 alto, 4 máximo) y la tendencia («A» aumento, «=»
estable, «D» descenso, «!» situación excepcional). La estación está en el
campus de la UAB, a unos 3 km de Montflorit. No es en tiempo real: lo cuentan
al microscopio y lo publican cada semana o diez días.

Licencia CC BY-NC-SA 4.0: se enlaza la web del PIA allí donde se muestra y se
dice la licencia en los créditos. Se pide en catalán y en castellano, que traen
los nombres de cada tipo en su idioma. En el NAS (con /estat) se guarda la
última respuesta 3 horas: los datos cambian una vez por semana.

    python3 pollen.py        lo de ahora, en JSON
"""
import datetime as dt
import json
import math
import os
import urllib.request
import xml.etree.ElementTree as ET

import config as C
import hora as H

API = "https://aerobiologia.cat/api/v0/forecast/bellaterra/{}/xml"
UA = {"User-Agent": "Temps a Montflorit (https://meteo-montflorit.github.io/)"}
CACHE = os.path.join(os.environ.get("POLLEN_DIR", "/estat"), "pollen.json")
CACHE_H = 3


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    return 6371 * math.hypot((lo2 - lo1) * math.cos((la1 + la2) / 2), la2 - la1)


def llegeix(xml_ca, xml_es):
    """De las dos respuestas (catalán y castellano), lo que usa la web."""
    ca, es = ET.fromstring(xml_ca), ET.fromstring(xml_es)
    noms = {}
    for arrel, idioma in ((ca, "ca"), (es, "es")):
        for grup in ("pollens", "spores"):
            for t in arrel.find("taxons").find(grup):
                noms.setdefault(t.tag, {})[idioma] = t.get(idioma) or t.text
    report = ca.find("report")
    estacio = report.find("station")
    lloc = (float(estacio.findtext("latitude")), float(estacio.findtext("longitude")))
    res = {"estacio": estacio.findtext("name"), "km": round(km(C.CASA, lloc), 1),
           "url": {"ca": estacio.findtext("url"),
                   "es": es.find("report").find("station").findtext("url")},
           "inici": report.findtext("date/start"), "fi": report.findtext("date/end")}
    for grup, clau in (("pollens", "pollens"), ("spores", "espores")):
        res[clau] = [{"codi": t.tag, "nom": noms.get(t.tag, {"ca": t.tag, "es": t.tag}), "nivell": int(t.text),
                      "tendencia": (report.findtext(f"forecast/{grup}/{t.tag}") or "").strip() or None}
                     for t in report.find("current").find(grup)]
    return res


def calcula(ara=None):
    ara = ara or H.ara()
    try:
        with open(CACHE, encoding="utf-8") as f:
            desat = json.load(f)
        if ara - H.llegeix(desat["hora"]) < dt.timedelta(hours=CACHE_H):
            return desat["pollen"]
    except (OSError, ValueError, KeyError):
        pass
    res = llegeix(get(API.format("ca")), get(API.format("es")))
    if os.path.isdir(os.path.dirname(CACHE)):
        with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"hora": H.clau(ara), "pollen": res}, f, ensure_ascii=False)
        os.replace(CACHE + ".tmp", CACHE)
    return res


if __name__ == "__main__":
    print(json.dumps(calcula(), ensure_ascii=False, indent=1))
