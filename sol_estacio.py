#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El sol directo sobre el termómetro de la estación de casa (ADR 0081).

Los días soleados, a primera hora (y, según la época, también por la tarde),
un rayo de sol llega al termómetro: en media hora sube de 3 a 5 °C y luego
baja, mientras las estaciones vecinas suben poco a poco (el 09-10-2026, de
9,2 °C a las 8:30 a 14,7 a las 9:05; las vecinas, 10,5 a las 9). El sensor
de radiación no lo ve (marca lo mismo que más tarde, sin pico), y la hora
cambia con la estación del año: por eso no se mira la hora ni la radiación,
sino el salto de la propia estación comparado con las vecinas.

- **Diferencia habitual**: la mediana de (casa − mediana de las vecinas) en
  las horas en punto de los últimos DIES_OFSET días, sin las horas con sol
  directo. La estación de casa está en una zona más fría del barrio (Juanjo,
  12-10-2026: «quiero que siga siendo así»): esa diferencia se conserva.
- **Empieza** un episodio, de día (radiación > 0), si la estación ha subido
  SALT_MIN °C o más en los últimos SALT_MIN_MINUTS minutos y está EXCES_INICI
  °C o más por encima de lo esperado (vecinas + diferencia habitual).
- **Sigue** mientras esté EXCES_SEGUIR °C por encima, de día y como mucho
  DURADA_MAX_H horas.
- Mientras dura, la temperatura de «Ara» es la esperada, con la marca
  `sol_directe`; la medida queda en `temperatura_estacio`. La humedad relativa
  también se corrige: el sol la baja al calentar el sensor, pero el punto de
  rocío (el agua que hay en el aire) no cambia, y con él y la temperatura
  esperada sale la humedad de verdad (Juanjo: «si lo ves conveniente aplica lo
  mismo al resto de mediciones»). La presión y la lluvia no las toca el sol.
- Cada episodio se apunta en el registro (sol-estacio.csv). Para comparar con
  ayer (registre.temperatures_casa), sus horas llevan la temperatura esperada,
  la misma cuenta que «Ara» (Juanjo, 13-10-2026: «no es que no haya datos,
  solo no hay datos de mi estación»); para aprender la corrección de la
  temperatura (aprenentatge.mostres), no cuentan.

Uso:
  python3 sol_estacio.py omple [DIES]   repasa el historial cada 5 minutos y apunta los episodios
  python3 sol_estacio.py episodis       los episodios apuntados
"""
import csv
import datetime as dt
import json
import os
import statistics
import sys

import config as C
import hora as H

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
EPISODIS = os.path.join(DIR, "sol-estacio.csv")
ESTAT = os.path.join(os.path.dirname(DIR), "sol-estacio.json")
CAMPS = ["inici", "fi", "exces_max"]

SALT_MIN = 1.5            # °C
SALT_MIN_MINUTS = 30
EXCES_INICI = 1.5         # °C por encima de lo esperado
EXCES_SEGUIR = 0.7
DURADA_MAX_H = 3
DIES_OFSET = 30
HORES_OFSET_MIN = 24      # sin tantas horas comparables, no se corrige
VEINES_MIN = 2            # vecinas con temperatura para comparar


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def episodis(ruta=None):
    ruta = ruta or EPISODIS
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return [(H.llegeix(r["inici"]), H.llegeix(r["fi"]))
                for r in csv.DictReader(f) if r.get("inici") and r.get("fi")]


def hores_tocades(claus, eps=None):
    """De las horas en punto («AAAA-MM-DDTHH:MM», hora local), las que caen
    dentro de un episodio de sol directo."""
    eps = episodis() if eps is None else eps
    res = set()
    for c in claus:
        t = H.utc(c)
        if any(a <= t <= b for a, b in eps):
            res.add(c)
    return res


def apunta(inici, fi, exces, ruta=None):
    """Un episodio, o lo alarga si ya estaba (mismo inicio)."""
    ruta = ruta or EPISODIS
    files = []
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            files = [r for r in csv.DictReader(f)]
    clau = H.clau(inici)
    files = [{**r, "inici": H.clau(r["inici"]), "fi": H.clau(r["fi"])} for r in files if H.clau(r["inici"]) != clau]
    files.append({"inici": clau, "fi": H.clau(fi), "exces_max": round(exces, 1)})
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPS)
        w.writeheader()
        w.writerows(sorted(files, key=lambda r: r["inici"]))
    os.replace(ruta + ".tmp", ruta)


def mediana_veines(temperatures):
    ts = [t for t in temperatures if t is not None]
    return statistics.median(ts) if len(ts) >= VEINES_MIN else None


def ofset(casa_hores, veines_hores, ara, eps=None):
    """La diferencia habitual casa − vecinas ({fins: °C} de casa; {estacio:
    {fins: °C}}), en las horas de los últimos DIES_OFSET días sin sol directo.
    None si no hay HORES_OFSET_MIN horas comparables."""
    desde = H.clau(ara - dt.timedelta(days=DIES_OFSET))
    claus = [c for c in casa_hores if c >= desde]
    fora = hores_tocades(claus, eps)
    difs = []
    for c in claus:
        if c in fora or casa_hores[c] is None:
            continue
        m = mediana_veines([v.get(c) for v in veines_hores.values()])
        if m is not None:
            difs.append(casa_hores[c] - m)
    return statistics.median(difs) if len(difs) >= HORES_OFSET_MIN else None


def amb_esperades(temperatures, ara, eps=None, casa_hores=None, veines_hores=None):
    """Las temperaturas de la estación por horas ({"AAAA-MM-DDTHH:MM": °C})
    con las horas de sol directo cambiadas por la esperada (mediana de las
    vecinas + diferencia habitual), como en «Ara». Si en esa hora no hay
    VEINES_MIN vecinas o no hay diferencia habitual, la hora se quita."""
    fora = hores_tocades(temperatures, eps)
    if not fora:
        return dict(temperatures)
    if casa_hores is None:
        casa_hores = _llegeix_hores(os.path.join(DIR, "estacio-casa.csv"))
    if veines_hores is None:
        veines_hores = {e: _llegeix_hores(os.path.join(DIR, f"veina-{e}.csv")) for e in C.VEINES}
    ofs = ofset(casa_hores, veines_hores, ara, eps)
    res = {}
    for c, v in temperatures.items():
        if c in fora:
            m = mediana_veines([vh.get(c) for vh in veines_hores.values()]) if ofs is not None else None
            if m is None:
                continue
            v = round(m + ofs, 1)
        res[c] = v
    return res


def avalua(lectures, veines_ara, ofs, estat, ara, solar):
    """Si ara hi ha sol directe. lectures: [(t, °C)] de la estación, cada 5
    minutos, de las últimas horas; veines_ara: °C de las vecinas ahora; estat:
    {inici, exces_max} del episodio en curso o None. Torna (nou_estat,
    esperada, exces)."""
    if ofs is None or not lectures:
        return None, None, None
    m = mediana_veines(veines_ara)
    if m is None:
        return None, None, None
    t_ara = lectures[-1][1]
    esperada = m + ofs
    exces = t_ara - esperada
    de_dia = solar is not None and solar > 0
    if estat:
        inici = H.llegeix(estat["inici"])
        if de_dia and exces >= EXCES_SEGUIR and ara - inici <= dt.timedelta(hours=DURADA_MAX_H):
            return {"inici": estat["inici"], "exces_max": max(estat.get("exces_max", 0), exces)}, esperada, exces
        return None, esperada, exces
    fa = [t for (h, t) in lectures if ara - h <= dt.timedelta(minutes=SALT_MIN_MINUTS) and t is not None]
    salt = t_ara - min(fa) if fa else 0
    if de_dia and salt >= SALT_MIN and exces >= EXCES_INICI:
        return {"inici": H.clau(ara), "exces_max": exces}, esperada, exces
    return None, esperada, exces


def humitat(rosada, temperatura):
    """Humedad relativa (%) con el punto de rocío y la temperatura (Magnus)."""
    import math
    e = lambda t: math.exp(17.625 * t / (243.04 + t))
    return max(0.0, min(100.0, 100 * e(rosada) / e(temperatura)))


def rosada(temperatura, humitat):
    """Punto de rocío (°C) con la temperatura y la humedad relativa (Magnus,
    la inversa de humitat)."""
    import math
    g = math.log(max(humitat, 1) / 100) + 17.625 * temperatura / (243.04 + temperatura)
    return 243.04 * g / (17.625 - g)


def _llegeix_hores(ruta, camp="temperatura"):
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        # Les claus, en UTC també les d'abans de la migració (ADR 0128).
        return {H.clau(r["fins"]): _num(r.get(camp)) for r in csv.DictReader(f)}


def corregeix(ara_casa, files, veines, ara):
    """En cada pasada (casa.recoger): si hay sol directo, cambia la temperatura
    de ara_casa por la esperada y lo marca; apunta el episodio. Solo en el NAS
    (con registro): sin él no hay diferencia habitual."""
    if not ara_casa or not os.path.isdir(DIR):
        return ara_casa
    casa_hores = _llegeix_hores(os.path.join(DIR, "estacio-casa.csv"))
    veines_hores = {e: _llegeix_hores(os.path.join(DIR, f"veina-{e}.csv")) for e in C.VEINES}
    ofs = ofset(casa_hores, veines_hores, ara)
    estat = None
    if os.path.exists(ESTAT):
        try:
            with open(ESTAT, encoding="utf-8") as f:
                estat = json.load(f) or None
        except (OSError, ValueError):
            estat = None
    lectures = [(f["t"], f["temperatura"]) for f in files or [] if f.get("temperatura") is not None]
    if ara_casa.get("temperatura") is not None and (not lectures or lectures[-1][0] < H.llegeix(ara_casa["hora"])):
        lectures.append((H.llegeix(ara_casa["hora"]), ara_casa["temperatura"]))
    fresques = [v.get("temperatura") for v in veines or []
                if v.get("hora") and ara - H.llegeix(v["hora"]) <= dt.timedelta(minutes=30)]
    nou, esperada, exces = avalua(lectures, fresques, ofs, estat, ara, ara_casa.get("solar"))
    if estat and not nou:
        print(f"Sol directe a l'estació: acabat (des de {estat['inici']}).", file=sys.stderr)
    if nou:
        apunta(H.llegeix(nou["inici"]), ara, nou["exces_max"])
        ara_casa = {**ara_casa, "temperatura_estacio": ara_casa["temperatura"],
                    "temperatura": round(esperada, 1), "sol_directe": True}
        if ara_casa.get("rosada") is not None and ara_casa.get("humitat") is not None:
            ara_casa.update(humitat_estacio=ara_casa["humitat"], humitat=round(humitat(ara_casa["rosada"], esperada)))
    with open(ESTAT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(nou, f)
    os.replace(ESTAT + ".tmp", ESTAT)
    return ara_casa


def omple(dies=10, ara=None):
    """Repasa el historial de la estación (cada 5 minutos, Ecowitt) con las
    vecinas por horas y apunta los episodios de los últimos días."""
    import ecowitt as E
    import prevision as P
    ara = ara or H.ara()
    casa_hores = _llegeix_hores(os.path.join(DIR, "estacio-casa.csv"))
    veines_hores = {e: _llegeix_hores(os.path.join(DIR, f"veina-{e}.csv")) for e in C.VEINES}
    ofs = ofset(casa_hores, veines_hores, ara, eps=[])
    if ofs is None:
        print("Encara no hi ha prou hores per saber la diferència habitual.")
        return []
    files = [f for f in E.historial(ara - dt.timedelta(days=dies), ara, "5min") if f.get("temperatura") is not None]
    trobats, estat, ultima = [], None, None
    for i, f in enumerate(files):
        t = f["t"]
        h = P.clau_hora((t + dt.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0))
        veines = [v.get(h) for v in veines_hores.values()]
        lectures = [(g["t"], g["temperatura"]) for g in files[max(0, i - 12):i + 1]]
        nou, _, _ = avalua(lectures, veines, ofs, estat, t, f.get("solar"))
        if nou and not estat:
            trobats.append([t, t, nou["exces_max"]])
        elif nou:
            trobats[-1][1] = t
            trobats[-1][2] = max(trobats[-1][2], nou["exces_max"])
        estat = nou
        ultima = t
    for a, b, e in trobats:
        apunta(a, b, e)
        print(f"{H.local(a):%d/%m %H:%M}–{H.local(b):%H:%M}: fins a {e:+.1f} °C sobre l'esperada")
    print(f"Diferència habitual: {ofs:+.1f} °C. Episodis: {len(trobats)} (fins a {H.local(ultima):%d/%m %H:%M}).")
    return trobats


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "omple":
        omple(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    elif len(sys.argv) == 2 and sys.argv[1] == "episodis":
        for a, b in episodis():
            print(f"{H.local(a):%d/%m %H:%M}–{H.local(b):%H:%M}")
    else:
        sys.exit(__doc__)
