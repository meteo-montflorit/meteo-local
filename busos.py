#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Els busos urbans del barri (CV1, CV4 i CV5 de l'AMB), per a «Consultes» i
«Si surts» (ADR 0120).

Per a cada línia i sentit, les parades del barri amb les hores de pas
previstes: les de l'horari oficial (GTFS de l'AMB) corregides amb el temps
real (GTFS-RT), que el mostreig de calibracio/mostreig_busos.py va trobar de
fiar (del 15 al 21-10-2026, tots els viatges de la CV1 al temps real abans de
sortir i, 5-15 minuts abans de passar pel barri, un error típic d'un minut).
I les incidències que publica l'AMB per a aquestes línies, en català i en
castellà, tal com les publica.

L'horari oficial és un ZIP de 8,5 MB que l'AMB renova cada nit: es baixa un
cop al dia i se'n desa només el que cal (BUSOS_DIR/busos-horari.json). El
temps real i els avisos es llegeixen a cada passada, sense IA.

Ús:
  python3 busos.py          les línies ara (amb xarxa)
"""
import csv
import datetime as dt
import html
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict
from zoneinfo import ZoneInfo

import config as C
from trens import camps

ZONA = ZoneInfo("Europe/Madrid")

TEMPS_REAL = "https://www.ambmobilitat.cat/transit/trips-updates/trips.bin"
AVISOS = "https://www.ambmobilitat.cat/transit/alerts/alerts.bin"
HORARI = "https://www.ambmobilitat.cat/OpenData/google_transit.zip"
UA = {"User-Agent": "meteo-local/" + C.VERSION}
CAU = os.path.join(os.environ.get("BUSOS_DIR", os.environ.get("ESTAT_DIR", "/estat")), "busos-horari.json")
# Si l'AMB no deixa baixar l'horari, el desat serveix uns dies: hi ha els
# viatges dels DIES_HORARI dies següents.
DIES_HORARI = 4
# Les hores que es mostren de cada parada, com a molt.
HORES_PARADA = 12

BANDERES = "Pl. de les Banderes"
# Línia de l'AMB → [(cap a, [(parada, nom), …])], en l'ordre en què hi passa
# el bus: només les parades del barri o a tocar.
LINIES = {
    "508": [("Flor de Maig", [("201243", BANDERES), ("201464", "Av. Flor de Maig - Sant Jeroni"),
                              ("201463", "Av. Flor de Maig - Pl. Olivé")]),
            ("Canaletes", [("200075", "Canaletes - Av. Flor de Maig"), ("201465", "Av. Flor de Maig - Sant Jeroni"),
                           ("201455", BANDERES)])],
    "511": [("Can Cerdà", [("201506", "Santa Rosa - Pl. Salut"), ("201464", "Av. Flor de Maig - Sant Jeroni"),
                           ("200075", "Canaletes - Av. Flor de Maig")]),
            ("La Farigola", [("200075", "Canaletes - Av. Flor de Maig"), ("201465", "Av. Flor de Maig - Sant Jeroni"),
                             ("201503", "Santa Rosa - Av. Flor de Maig")])],
    "512": [("FGC Bellaterra", [("201243", BANDERES)])],
}


def baixa(url, segons=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=segons) as r:
        return r.read()


def temps_real(feed):
    """(hora de la capçalera, {viatge: {parada: hora}}) de les línies del barri."""
    capcalera, res = 0, {}
    for num, v in camps(feed):
        if num == 1:  # FeedHeader
            capcalera = dict(camps(v)).get(3, 0)
        elif num == 2:  # FeedEntity → TripUpdate
            tu = dict(camps(v)).get(3)
            if tu is None:
                continue
            camps_tu = camps(tu)
            trip = dict(camps(dict(camps_tu).get(1, b"")))
            viatge = trip.get(1, b"").decode()
            if viatge.split(".")[0] not in LINIES:
                continue
            parades = {}
            for n, stu in camps_tu:
                if n != 2:
                    continue
                c = dict(camps(stu))
                hora = next((h for h in (dict(camps(c[k])).get(2) for k in (2, 3) if k in c) if h), None)  # arrival, departure
                parada = c.get(4, b"").decode()
                if parada and hora:
                    parades[parada] = hora
            res[viatge] = parades
    return capcalera, res


def horari(zip_bytes, dies):
    """El que cal de l'horari oficial per als dies donats: les línies i, de cada
    viatge que hi circula, el sentit i l'hora de pas per cada parada."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    llegir = lambda nom: csv.DictReader(io.TextIOWrapper(z.open(nom), "utf-8-sig"))  # noqa: E731
    rutes = {r["route_id"]: {"linia": r["route_short_name"], "nom": r["route_long_name"].replace("-", " – "),
                             "mapa": r.get("map_url", "").strip(), "horari": r.get("timetable_url", "").strip()}
             for r in llegir("routes.txt") if r["route_id"] in LINIES}
    viatges = {r["trip_id"]: (r["service_id"], r["trip_headsign"]) for r in llegir("trips.txt") if r["route_id"] in LINIES}
    serveis = {s for s, _ in viatges.values()}
    calendari = {r["service_id"]: r for r in llegir("calendar.txt") if r["service_id"] in serveis}
    excepcions = defaultdict(dict)
    for r in llegir("calendar_dates.txt"):
        if r["service_id"] in serveis:
            excepcions[r["service_id"]][r["date"]] = r["exception_type"]
    pas = defaultdict(dict)
    for r in llegir("stop_times.txt"):
        if r["trip_id"] in viatges:
            h, m, s = map(int, r["arrival_time"].split(":"))
            pas[r["trip_id"]][r["stop_id"]] = h * 3600 + m * 60 + s
    noms_dia = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    passos = []
    for dia in dies:
        clau = f"{dia:%Y%m%d}"
        # Les hores del GTFS es compten des de les 12 del migdia menys 12 hores,
        # no des de la mitjanit: el dia del canvi d'hora (25 o 23 hores) no són
        # el mateix moment, i comptant des de la mitjanit tots els busos sense
        # temps real sortien una hora abans o després tot el dia, no només els
        # de matinada (inventari del 25-10-2026, el mateix dia del canvi).
        mitjanit = dt.datetime.combine(dia, dt.time(12), tzinfo=ZONA).timestamp() - 12 * 3600
        for viatge, (servei, cap_a) in viatges.items():
            c = calendari.get(servei)
            actiu = bool(c) and c["start_date"] <= clau <= c["end_date"] and c[noms_dia[dia.weekday()]] == "1"
            exc = excepcions[servei].get(clau)
            if (actiu or exc == "1") and exc != "2" and pas[viatge]:
                passos.append({"v": viatge, "cap_a": cap_a, "p": {p: mitjanit + s for p, s in pas[viatge].items()}})
    return {"rutes": rutes, "viatges": passos}


def horari_desat(avui):
    """L'horari d'avui en endavant: el desat si és d'avui; si no, es baixa i
    es desa. Si no es pot baixar, el desat, si encara arriba a avui."""
    desat = None
    try:
        with open(CAU, encoding="utf-8") as f:
            desat = json.load(f)
        if desat.get("dia") == avui.isoformat():
            return desat
    except (OSError, ValueError):
        pass
    try:
        nou = horari(baixa(HORARI, 120), [avui + dt.timedelta(days=n) for n in range(DIES_HORARI)])
        nou["dia"] = avui.isoformat()
        try:
            os.makedirs(os.path.dirname(CAU), exist_ok=True)
            with open(CAU + ".tmp", "w", encoding="utf-8") as f:
                json.dump(nou, f, separators=(",", ":"))
            os.replace(CAU + ".tmp", CAU)
        except OSError:
            pass
        return nou
    except Exception:
        if desat and (avui - dt.date.fromisoformat(desat["dia"])).days < DIES_HORARI:
            return desat
        raise


def hora_iso(t):
    return dt.datetime.fromtimestamp(t).isoformat(timespec="minutes")


def linies(hor, real, ara):
    """Cada línia amb els seus sentits i, de cada parada, les hores de pas
    d'ara en endavant (com a molt HORES_PARADA, en els 3 dies següents)."""
    res = []
    for ruta, sentits in LINIES.items():
        r = hor["rutes"].get(ruta)
        if not r:
            continue
        linia = {**r, "sentits": []}
        for desti, parades in sentits:
            files = []
            for parada, nom in parades:
                hores = set()
                for v in hor["viatges"]:
                    if not v["v"].startswith(ruta + ".") or v["cap_a"] != desti or parada not in v["p"]:
                        continue
                    h = v["p"][parada]
                    rt = real.get(v["v"], {})
                    if parada in rt:
                        h = rt[parada]
                    elif rt:
                        # El temps real no sempre porta totes les parades: el
                        # retard, el de la parada més propera que porta.
                        prop = min((q for q in rt if q in v["p"]), key=lambda q: abs(v["p"][q] - h), default=None)
                        if prop:
                            h += rt[prop] - v["p"][prop]
                    if ara - 60 <= h <= ara + 3 * 86400:
                        hores.add(h)
                files.append({"parada": nom, "hores": [hora_iso(h) for h in sorted(hores)[:HORES_PARADA]]})
            linia["sentits"].append({"cap_a": desti, "parades": files})
        res.append(linia)
    return res


def _text(al, camp):
    """El TranslatedString del camp d'un avís: {idioma: text}."""
    return {dict(camps(t)).get(2, b"").decode(): html.unescape(dict(camps(t)).get(1, b"").decode()).strip()
            for k, v in al if k == camp for c, t in camps(v) if c == 1}


def incidencies(feed, rutes, ara):
    """Els avisos de l'AMB (GTFS-RT) per a les línies del barri, vigents o
    futurs. Les hores del període hi són en hora local escrita com si fos UTC
    (el 22-10-2026, «dijous a les 8:00» arribava com a 08:00Z)."""
    local = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)  # noqa: E731
    ara_local = dt.datetime.fromtimestamp(ara)
    noms = {k: r["linia"] for k, r in rutes.items()}
    res = []
    for num, e in camps(feed):
        if num != 2:
            continue
        for n, a in camps(e):
            if n != 5:  # Alert
                continue
            al = camps(a)
            afectades = sorted({noms.get(dict(camps(v)).get(2, b"").decode()) for k, v in al if k == 5} - {None})
            if not afectades:
                continue

            periodes = [dict(camps(v)) for k, v in al if k == 1]
            inici = min((p[1] for p in periodes if 1 in p), default=None)
            fi = max((p[2] for p in periodes if 2 in p), default=None)
            if fi and local(fi) < ara_local:
                continue
            res.append({"linies": afectades, "titol": _text(al, 10), "url": _text(al, 8),
                        "inici": inici and local(inici).isoformat(timespec="minutes"),
                        "fi": fi and local(fi).isoformat(timespec="minutes")})
    return res


def calcula(ahora=None):
    """{temps_real_de, incidencies, linies}. Sense temps real, les hores de
    l'horari (temps_real_de buit); sense avisos, la llista buida i l'error."""
    ara = (ahora or dt.datetime.now()).timestamp()
    hor = horari_desat(dt.date.fromtimestamp(ara))
    errors = []
    capcalera, real = 0, {}
    try:
        capcalera, real = temps_real(baixa(TEMPS_REAL))
    except Exception as ex:
        errors.append(f"temps real: {ex}")
    try:
        incs = incidencies(baixa(AVISOS), hor["rutes"], ara)
    except Exception as ex:
        incs = []
        errors.append(f"avisos: {ex}")
    res = {"temps_real_de": hora_iso(capcalera) if capcalera else None, "incidencies": incs,
           "linies": linies(hor, real, ara)}
    if errors:
        res["errors"] = errors
    return res


if __name__ == "__main__":
    inici = time.time()
    json.dump(calcula(), sys.stdout, ensure_ascii=False, indent=1)
    print(f"\n({time.time() - inici:.1f} s)", file=sys.stderr)
