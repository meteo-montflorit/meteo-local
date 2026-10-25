#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Registro en el NAS de lo medido, para aprender con datos (ADR 0006 y 0012).

Lo ejecuta el reloj del NAS, sin IA:

  python3 registre.py estacio             rellena las horas que falten de la
                                          estación de casa con su historial
  python3 registre.py rehaz-pluja-casa    vuelve a calcular su lluvia por horas
                                          con el historial (ADR 0017)

Además, casa.py apunta en cada pasada lo que mide la estación de casa hora a
hora (estacio-casa.csv, ADR 0017) y cada 5 minutos (estacio-casa-5min.csv,
ADR 0049), la lluvia por horas de las estaciones de Meteocat de Sabadell y
Sant Cugat (meteocat-XF.csv y meteocat-XV.csv, ADR 0058), lo que miden por
horas las estaciones vecinas de Weather Underground (veina-<id>.csv, ADR
0060), los ecos del radar a 15 km o menos (radar-a-prop-AAAA-MM.jsonl) y, una vez por hora, lo que daban los modelos para las 24 horas
siguientes (casa-AAAA-MM.jsonl), para aprender de los fallos (ADR 0012).

Los datos van a REGISTRE_DIR (en el NAS, /estat/registre), no al repositorio.
"""
import csv
import datetime as dt
import json
import os
import sys

import config as C
import ecowitt as E
import hora as H
import prevision as P

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")


# --- Los ecos del radar cerca de casa --------------------------------------------

def apunta_radar_a_prop(ahora, radar, motius, obs):
    """Una línea por pasada en radar-a-prop-AAAA-MM.jsonl: los píxeles con
    lluvia a 15 km o menos de cada radar (distancia, rumbo y mm/h), si el modo
    aviso se encendió y por qué, y qué estaciones medían lluvia. Para decidir
    si los ecos sueltos de Meteocat cerca de casa son lluvia o no (seguimiento
    pedido por Juanjo el 10-10-2026; ADR 0019)."""
    linia = {"t": H.clau(ahora), "triada": radar.get("imatge"),
             "km": radar.get("km_lluvia"), "mode_avis": motius,
             "pluja_mesurada": [o["estacion"] for o in obs or []
                                if (o.get("mm_ultima_media_hora") or 0) > 0 or (o.get("intensitat") or 0) > 0],
             "radars": radar.get("a_prop") or {}}
    with open(os.path.join(DIR, f"radar-a-prop-{H.local(ahora):%Y-%m}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(H.interna(linia), ensure_ascii=False) + "\n")


# --- Página de casa: previsiones y lo que pasó -----------------------------------

CASA_DARRERA = os.path.join(DIR, "casa-darrera")


def hay_registro():
    """El registro vive en el NAS (/estat); en un ordenador no se apunta nada."""
    return os.path.isdir(os.path.dirname(DIR))


ESTACIO_CASA = os.path.join(DIR, "estacio-casa.csv")
CAMPOS_ESTACIO_CASA = ["fins", "pluja_mm", "temperatura", "humitat", "rosada", "pressio", "solar"]
# La lluvia de casa cada 5 minutos, el paso del radar: para comprobar a qué
# hora para la lluvia que se ve encima (fi_pluja.py, ADR 0049). Ecowitt solo
# guarda 90 días; aquí se van quedando.
ESTACIO_CASA_5MIN = os.path.join(DIR, "estacio-casa-5min.csv")
CAMPOS_5MIN = ["fins", "pluja_mm"]
# La lluvia por horas de las estaciones de Meteocat (meteocat-<codi>.csv):
# cuando casa marca cero, una hora solo cuenta como seca si ellas tampoco
# recogieron nada (aprenentatge.py, ADR 0058).
CAMPOS_METEOCAT = ["fins", "pluja_mm"]


def llegeix_per_hores(ruta):
    """Les files d'un CSV per hores ({«fins»: fila}), amb «fins» en UTC (ADR
    0128): les d'abans de la 3.201.0, en hora de Madrid, es passen a UTC en
    llegir-les, i el fitxer queda migrat la primera vegada que es desa."""
    with open(ruta, encoding="utf-8") as f:
        return {P.clau_hora(r["fins"]): {**r, "fins": P.clau_hora(r["fins"])} for r in csv.DictReader(f)}


def _desa_per_hores(ruta, campos, nuevas):
    """Añade o sustituye filas ({«fins» en UTC: valores}) en un CSV ordenado."""
    if not nuevas:
        return
    os.makedirs(DIR, exist_ok=True)
    guardadas = {}
    if os.path.exists(ruta):
        guardadas = llegeix_per_hores(ruta)
    guardadas.update(nuevas)
    with open(ruta + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(guardadas[k] for k in sorted(guardadas, key=P.ordre_hora))
    os.replace(ruta + ".tmp", ruta)


def cincs_casa(filas):
    """La lluvia de cada tramo completo de 5 minutos ({fin: mm}) de las
    lecturas de la estación de casa («t» y «pluja_avui», acumulada del día,
    que vuelve a cero a medianoche)."""
    filas = sorted((f for f in filas if f.get("pluja_avui") is not None), key=lambda f: f["t"])
    if not filas:
        return {}
    res = {}
    for antes, despues in zip(filas, filas[1:]):
        t = despues["t"]
        # El tramo que acaba en «fin» va de fin - 5 min (sin incluir) a fin.
        base = t.replace(minute=t.minute - t.minute % 5, second=0, microsecond=0)
        fin = base if t == base else base + dt.timedelta(minutes=5)
        salto = despues["pluja_avui"] - antes["pluja_avui"]
        res[fin] = res.get(fin, 0.0) + (despues["pluja_avui"] if salto < 0 else salto)
    primera, ultima = filas[0]["t"], filas[-1]["t"]
    return {fin: mm for fin, mm in res.items() if fin <= ultima and fin - dt.timedelta(minutes=5) >= primera}


def apunta_casa_5min(cincs):
    _desa_per_hores(ESTACIO_CASA_5MIN, CAMPOS_5MIN,
                    {P.clau_hora(fin): {"fins": P.clau_hora(fin), "pluja_mm": round(mm, 1)}
                     for fin, mm in cincs.items()})


# La lluvia de las vecinas cada 5 minutos (veines-5min.csv, ADR 0102): una
# columna por estación, para que el final de la lluvia (fi_pluja.py) se
# juzgue con la misma regla que la hora (aprenentatge.pluja_observada) y no
# solo con el pluviómetro de casa.
VEINES_5MIN = os.path.join(DIR, "veines-5min.csv")


def campos_veines_5min():
    return ["fins"] + list(C.VEINES)


def apunta_veines_5min(cincs):
    """{estacio: {fin: mm}} (cincs_casa con las lecturas de cada vecina). Una
    estación que falta en esta pasada conserva lo que tuviera apuntado."""
    files = {}
    for estacio, tram in cincs.items():
        if estacio not in C.VEINES:
            continue
        for fin, mm in tram.items():
            files.setdefault(P.clau_hora(fin), {})[estacio] = round(mm, 1)
    if not files:
        return
    os.makedirs(DIR, exist_ok=True)
    campos = campos_veines_5min()
    guardadas = {}
    if os.path.exists(VEINES_5MIN):
        guardadas = {k: {c: r.get(c, "") for c in campos} for k, r in llegeix_per_hores(VEINES_5MIN).items()}
    for clave, valors in files.items():
        fila = guardadas.setdefault(clave, {c: "" for c in campos})
        fila["fins"] = clave
        fila.update(valors)
    with open(VEINES_5MIN + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(guardadas[k] for k in sorted(guardadas, key=P.ordre_hora))
    os.replace(VEINES_5MIN + ".tmp", VEINES_5MIN)


def hores_meteocat(filas):
    """Horas completas ({fin local: mm}) de las medias horas de una estación
    de Meteocat ((inicio en UTC, mm), prevision.taula_meteocat): solo las
    horas con sus dos medias horas."""
    per_hora = {}
    for ini, mm in filas:
        fin = H.utc(ini + dt.timedelta(minutes=30))
        fin = fin.replace(minute=0, second=0, microsecond=0) + (dt.timedelta(hours=1) if fin.minute else dt.timedelta())
        h = per_hora.setdefault(fin, [0.0, 0])
        h[0] += mm
        h[1] += 1
    return {fin: round(mm, 1) for fin, (mm, n) in per_hora.items() if n == 2}


def apunta_meteocat(codi, hores):
    _desa_per_hores(os.path.join(DIR, f"meteocat-{codi}.csv"), CAMPOS_METEOCAT,
                    {P.clau_hora(fin): {"fins": P.clau_hora(fin), "pluja_mm": mm}
                     for fin, mm in hores.items()})


# Lo que miden por horas las estaciones vecinas de Weather Underground
# (veina-<id>.csv, ADR 0060): la lluvia de la hora y las lecturas más
# cercanas a la hora en punto, como en estacio-casa.csv. La presión es la
# que publica cada estación (no todas la reducen al nivel del mar).
CAMPOS_VEINA = ["fins", "pluja_mm", "temperatura", "humitat", "rosada", "pressio", "vent", "ratxa"]


def hores_veina(filas):
    """Horas completas ({fin: valores}) de las lecturas de una vecina
    (wunderground.files), con la lluvia de la hora y el viento."""
    hores = E.hores(filas)
    vent = {}
    for f in filas:
        if f.get("vent") is None:
            continue
        marca = (f["t"] + dt.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
        dist = abs((f["t"] - marca).total_seconds())
        if dist <= 300 and dist < vent.get(marca, (999, None))[0]:
            vent[marca] = (dist, f)
    for fin, h in hores.items():
        h.pop("solar", None)
        f = vent.get(fin, (None, {}))[1]
        h["vent"], h["ratxa"] = f.get("vent"), f.get("ratxa")
    return hores


def apunta_veina(estacio, hores):
    nuevas = {}
    for fin, h in hores.items():
        if h.get("pluja_mm") is None and h.get("temperatura") is None:
            continue
        clave = P.clau_hora(fin)
        nuevas[clave] = {"fins": clave, **{k: h.get(k) for k in CAMPOS_VEINA[1:]}}
    _desa_per_hores(os.path.join(DIR, f"veina-{estacio}.csv"), CAMPOS_VEINA, nuevas)


def falta_ahir_veina(estacio, ahora):
    """Si al registro de una vecina le falta la última hora de ayer (las
    lecturas de hoy no la cierran): se pide el historial de ayer una vez."""
    ruta = os.path.join(DIR, f"veina-{estacio}.csv")
    mitjanit = H.clau(H.mitjanit(H.dia_local(ahora)))
    if not os.path.exists(ruta):
        return True
    with open(ruta, encoding="utf-8") as f:
        return not any(r["fins"] == mitjanit for r in csv.DictReader(f))
def temperatures_casa(ahora, hores=72, recents=None):
    """La temperatura medida en casa a cada hora en punto de las últimas
    horas ({"AAAA-MM-DDTHH:MM" local: °C}), del registro y de las lecturas
    de esta pasada (recents, ecowitt.hores): para comparar la previsión con
    lo de ayer (ADR 0061)."""
    desde = H.utc(ahora) - dt.timedelta(hours=hores)
    res = {}
    if os.path.exists(ESTACIO_CASA):
        with open(ESTACIO_CASA, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if H.utc(r["fins"]) >= desde and _num(r["temperatura"]) is not None:
                    res[P.clau_hora(r["fins"])] = _num(r["temperatura"])
    for fin, h in (recents or {}).items():
        clau = P.clau_hora(fin)
        if H.utc(fin) >= desde and h.get("temperatura") is not None:
            res[clau] = round(h["temperatura"], 1)
    # Las horas con sol directo sobre el termómetro, con la temperatura
    # esperada según las vecinas (ADR 0081).
    import sol_estacio
    return dict(sorted(sol_estacio.amb_esperades(res, ahora).items(), key=lambda kv: P.ordre_hora(kv[0])))


# Cuánto se rellena hacia atrás como mucho: Ecowitt guarda 90 días cada 5 minutos.
ESTACIO_CASA_DIES_MAX = 89


def apunta_setmana(ahora, dies):
    """La previsión de la semana tal como se publica, una línea cada vez que
    se calcula (como mucho cada hora, setmana.CADA_MIN), en
    setmana-AAAA-MM.jsonl: para comprobar con lo que pasó la probabilidad de
    lluvia, que sale del ensemble sin calibrar (ADR 0122)."""
    with open(os.path.join(DIR, f"setmana-{H.local(ahora):%Y-%m}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": H.clau(ahora), "dies": dies}, ensure_ascii=False) + "\n")


def apunta_estacio_casa(nuevas):
    """Horas completas de la estación de casa ({fin: valores}, ecowitt.hores)."""
    nuevas = {fin: h for fin, h in nuevas.items() if h.get("temperatura") is not None
              or h.get("pluja_mm") is not None}
    if not nuevas:
        return
    os.makedirs(DIR, exist_ok=True)
    guardadas = {}
    if os.path.exists(ESTACIO_CASA):
        guardadas = llegeix_per_hores(ESTACIO_CASA)
    for fin, h in nuevas.items():
        clave = P.clau_hora(fin)
        guardadas[clave] = {"fins": clave, **{k: h.get(k) for k in CAMPOS_ESTACIO_CASA[1:]}}
    with open(ESTACIO_CASA + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_ESTACIO_CASA)
        w.writeheader()
        w.writerows(guardadas[k] for k in sorted(guardadas, key=P.ordre_hora))
    os.replace(ESTACIO_CASA + ".tmp", ESTACIO_CASA)


def completa_estacio_casa(ahora=None):
    """Rellena con el historial de Ecowitt las horas que falten desde la
    última guardada (o desde el inicio del registro de casa), por si el NAS
    ha estado apagado. Una consulta por día que falte."""
    if not E.disponible():
        print("Sin claves de Ecowitt: no se rellena la estación de casa.")
        return
    ahora = ahora or P.AHORA
    desde = ahora - dt.timedelta(days=ESTACIO_CASA_DIES_MAX)
    if os.path.exists(ESTACIO_CASA):
        with open(ESTACIO_CASA, encoding="utf-8") as f:
            horas = [r["fins"] for r in csv.DictReader(f) if r["temperatura"]]
        if horas:
            desde = max(desde, H.utc(horas[-1]) - dt.timedelta(hours=2))
    else:
        desde = max(desde, ahora - dt.timedelta(days=2))
    apunta_estacio_casa(E.hores(E.historial(desde, ahora, "5min")))
    print("Estació de casa completada des de", desde.isoformat(timespec="minutes"))


def rehaz_pluja_casa(ahora=None):
    """Vuelve a calcular la lluvia de cada hora de estacio-casa.csv con el
    historial de Ecowitt (5 minutos, los últimos ESTACIO_CASA_DIES_MAX días).
    Hasta la 3.27.5 se guardaba la de la primera hora cortada de cada pasada
    encima de la buena (ADR 0017). Deja una copia del archivo de antes y solo
    cambia la lluvia."""
    ahora = ahora or P.AHORA
    if not os.path.exists(ESTACIO_CASA):
        return 0
    filas = sorted(llegeix_per_hores(ESTACIO_CASA).values(), key=lambda r: r["fins"])
    desde = max(ahora - dt.timedelta(days=ESTACIO_CASA_DIES_MAX),
                H.utc(filas[0]["fins"]) - dt.timedelta(hours=1))
    buenas = {P.clau_hora(fin): h["pluja_mm"]
              for fin, h in E.hores(E.historial(desde, ahora, "5min")).items() if h["pluja_mm"] is not None}
    canvis = 0
    for r in filas:
        if r["fins"] in buenas and _num(r["pluja_mm"]) != buenas[r["fins"]]:
            r["pluja_mm"] = buenas[r["fins"]]
            canvis += 1
    if canvis:
        copia = f"{ESTACIO_CASA}.bak-pluja-{ahora:%Y%m%d%H%M}"
        os.replace(ESTACIO_CASA, copia)
        with open(ESTACIO_CASA + ".tmp", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_ESTACIO_CASA)
            w.writeheader()
            w.writerows(filas)
        os.replace(ESTACIO_CASA + ".tmp", ESTACIO_CASA)
    return canvis


def _num(x):
    try:
        return round(float(x), 1)
    except (TypeError, ValueError):
        return None


def apunta_casa(emes, hores, ara_casa=None, sant_cugat=None, veines=None):
    """Una línea por hora de reloj: la primera pasada de cada hora. sant_cugat:
    la lluvia de la última hora en la estación de Meteocat de Sant Cugat, por
    si lo que llueve cerca ayuda a prever (ADR 0042); veines: la de cada
    estación vecina ({id: mm}), desde el 10-10-2026 (ADR 0070)."""
    # L'hora en UTC: la nit d'octubre, les dues hores de 2 a 3 són dues (fins
    # a la 3.200.0 la segona no s'apuntava; ADR 0128).
    hora = H.clau(emes)[:13]
    if os.path.exists(CASA_DARRERA):
        with open(CASA_DARRERA) as f:
            if f.read().strip() == hora:
                return
    os.makedirs(DIR, exist_ok=True)
    linea = {"emes": H.clau(emes), "ara_casa": ara_casa, "hores": hores,
             "sant_cugat": sant_cugat, "veines": veines}
    with open(os.path.join(DIR, f"casa-{H.local(emes):%Y-%m}.jsonl"), "a", encoding="utf-8") as f:
        # Les hores, totes en UTC (ADR 0128).
        f.write(json.dumps(H.interna(linea), ensure_ascii=False) + "\n")
    with open(CASA_DARRERA, "w") as f:
        f.write(hora)


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "estacio":
        completa_estacio_casa()
    elif orden == "rehaz-pluja-casa":
        print("Horas con la lluvia corregida:", rehaz_pluja_casa())
    else:
        print(__doc__)
