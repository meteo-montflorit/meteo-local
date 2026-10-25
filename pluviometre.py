#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""¿Marca bien el pluviómetro de casa? Vigilancia de una sola vez (ADR 0017).

Tras limpiar el pluviómetro, compara su lluvia con la de referencia: la de
Montflorit según las vecinas fiables (la mediana, con dos al menos; ADR 0070)
o, si no las hay, lo que recogieron a la vez las estaciones de Meteocat de
Sabadell y Sant Cugat (la menor de las dos, ADR 0058), en cada episodio de lluvia (horas
seguidas con lluvia, con dos horas secas como mucho entre medias). Lo que
importa es la lluvia débil, la que no marcaba: un episodio débil (de
EPISODIO_DEBIL_MM en la referencia) cuenta como detectado si casa marca algo
en él o en la hora de antes o de después.

Cuando hay bastantes episodios débiles, avisa a Juanjo por Telegram con el
resultado y borra su archivo: no vuelve a avisar. Si en DIAS_MAX no ha llovido
lo bastante, avisa con lo que haya. El reloj del NAS la ejecuta cada hora
mientras exista el archivo.

Uso:
  python3 pluviometre.py inicia [DESDE]   empieza a vigilar (por defecto, ya)
  python3 pluviometre.py vigila           comprueba y, si hay resultado, avisa
  python3 pluviometre.py estat            cómo va, sin avisar
"""
import csv
import datetime as dt
import json
import os
import subprocess
import sys

import config as C
import hora as H

# Todo en UTC (ADR 0128): hasta la 3.200.0, hora local sin zona, y la noche
# del cambio de hora la hora repetida, con desfase, hacía caer la vigilancia.
def local(t=None):
    return H.utc(t or H.ara())


DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
ESTADO = os.path.join(os.path.dirname(DIR), "vigila-pluviometre.json")
# Montflorit primero (ADR 0070): las vecinas fiables de Weather Underground y,
# de respaldo, las estaciones de Meteocat de Sabadell y Sant Cugat.
VEINES_REF = [os.path.join(DIR, f"veina-{e}.csv") for e, v in C.VEINES.items() if v.get("sec")]
METEOCAT_REF = [os.path.join(DIR, f"meteocat-{codi}.csv") for codi in ("XF", "XV")]
REFERENCIA = VEINES_REF + METEOCAT_REF
CASA = os.path.join(DIR, "estacio-casa.csv")

UMBRAL_MM = 0.2                 # una hora con lluvia
EPISODIO_DEBIL_MM = (0.6, 4.0)  # al menos dos vuelcos del cubo (0,254 mm) y lluvia débil
HUECO_H = 2                     # horas secas que aún separan un mismo episodio
ESPERA_H = 2                    # horas desde el final antes de juzgar un episodio
MINIMO = 3                      # episodios débiles para dar un resultado
DIAS_MAX = 45


def lee(ruta):
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        res = {}
        for r in csv.DictReader(f):
            try:
                res[H.utc(r["fins"])] = float(r["pluja_mm"])
            except (TypeError, ValueError):
                pass
        return res


def referencia():
    """{hora: mm} de la lluvia en Montflorit: la mediana de las vecinas fiables
    en las horas que tienen al menos dos (ADR 0070); si no, la menor de
    Sabadell y Sant Cugat, en las horas que tienen las dos (ADR 0058)."""
    veines = [lee(r) for r in VEINES_REF]
    meteocat = [lee(r) for r in METEOCAT_REF]
    res = {}
    if meteocat:
        for t in set.intersection(*(set(s) for s in meteocat)):
            res[t] = min(s[t] for s in meteocat)
    for t in set().union(*(set(s) for s in veines)) if veines else ():
        vals = sorted(s[t] for s in veines if t in s)
        if len(vals) >= 2:
            n = len(vals)
            res[t] = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return res


def episodios(mont, desde, hasta):
    """Episodios de la referencia entre desde y hasta: listas de horas (fin)."""
    horas = sorted(t for t, mm in mont.items() if desde < t <= hasta and mm >= UMBRAL_MM)
    res = []
    for t in horas:
        if res and t - res[-1][-1] <= dt.timedelta(hours=HUECO_H + 1):
            res[-1].append(t)
        else:
            res.append([t])
    return res


def movimiento(mont, casa, desde):
    """Primera hora en que casa marca lluvia sin que llueva en la referencia
    (ni la hora antes ni la de después): mover el cubo al limpiar."""
    for t in sorted(casa):
        if t <= desde or casa[t] < UMBRAL_MM:
            continue
        cerca = [mont.get(t + dt.timedelta(hours=k)) for k in (-1, 0, 1)]
        if all(x is not None and x < UMBRAL_MM for x in cerca):
            return t
    return None


def evalua(mont, casa, desde, ahora):
    limpieza = movimiento(mont, casa, desde)
    inicio = max(desde, limpieza) if limpieza else desde
    debiles, otros = [], []
    for ep in episodios(mont, inicio, ahora - dt.timedelta(hours=ESPERA_H)):
        horas = [ep[0] - dt.timedelta(hours=1)] + ep + [ep[-1] + dt.timedelta(hours=1)]
        if any(t not in casa for t in ep):
            continue        # sin datos de casa en el episodio: no se juzga
        m = round(sum(mont[t] for t in ep), 1)
        c = round(sum(casa.get(t, 0.0) for t in horas), 1)
        fila = {"inici": H.clau(ep[0] - dt.timedelta(hours=1)),
                "fi": H.clau(ep[-1]), "referencia_mm": m, "casa_mm": c}
        (debiles if EPISODIO_DEBIL_MM[0] <= m < EPISODIO_DEBIL_MM[1] else otros).append(fila)
    detectados = sum(e["casa_mm"] >= UMBRAL_MM for e in debiles)
    return {"des_de": H.clau(inicio),
            "neteja": limpieza and H.clau(limpieza),
            "debils": debiles, "altres": otros, "detectats": detectados}


def veredicto(r, vencido):
    n, d = len(r["debils"]), r["detectats"]
    if n >= MINIMO and d == n:
        return "funciona"
    if n >= MINIMO and d <= n / 2:
        return "falla"
    if n >= 2 * MINIMO:
        return "funciona" if d / n >= 0.8 else "dudoso"
    return "sin datos" if vencido else None


def coma(x):
    return f"{x:.1f}".replace(".", ",")


def hm(iso):
    t = H.local(iso)
    return f"{t.day}/{t.month} {t.hour}h"


def mensaje(r, v):
    lineas = []
    if v == "funciona":
        lineas.append("El pluviómetro de casa ya marca la lluvia débil.")
    elif v == "falla":
        lineas.append("El pluviómetro de casa sigue sin marcar la lluvia débil.")
    elif v == "dudoso":
        lineas.append("El pluviómetro de casa marca la lluvia débil solo a veces.")
    else:
        lineas.append(f"En {DIAS_MAX} días no ha llovido lo bastante para comprobar el pluviómetro de casa.")
    if r["neteja"]:
        lineas.append(f"Cuento desde la limpieza, que se nota el {hm(r['neteja'])}.")
    if r["debils"]:
        lineas.append(f"Lluvias débiles: marcó {r['detectats']} de {len(r['debils'])}.")
        lineas += [f"- {hm(e['inici'])}: Meteocat {coma(e['referencia_mm'])} mm, casa {coma(e['casa_mm'])} mm"
                   for e in r["debils"]]
    if r["altres"]:
        m = sum(e["referencia_mm"] for e in r["altres"])
        c = sum(e["casa_mm"] for e in r["altres"])
        lineas.append(f"Lluvias más fuertes: Meteocat {coma(m)} mm, casa {coma(c)} mm.")
    if v == "funciona":
        lineas.append("Si quieres que la web vuelva a fiarse también de su cero, díselo a Claude.")
    elif v in ("falla", "dudoso"):
        lineas.append("Ecowitt recomienda entonces revisar el nivel y el cubo o pedir el recambio del pluviómetro.")
    return "\n".join(lineas)


def vigila(ahora=None, avisa=True):
    if not os.path.exists(ESTADO):
        return None
    with open(ESTADO, encoding="utf-8") as f:
        estado = json.load(f)
    ahora = local(ahora)
    desde = local(H.llegeix(estado["des_de"]))
    r = evalua(referencia(), lee(CASA), desde, ahora)
    v = veredicto(r, ahora - desde > dt.timedelta(days=DIAS_MAX))
    if not v:
        return None
    texto = mensaje(r, v)
    print(texto)
    if avisa:
        subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "pluviómetro de casa", texto], check=True)
    os.remove(ESTADO)
    return v


def inicia(desde=None):
    desde = H.utc(desde) if desde else H.ara()
    desde = desde.replace(second=0, microsecond=0)
    os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump({"des_de": H.clau(desde)}, f)
    print("Vigilando el pluviómetro desde", H.iso_local(desde))


def estat():
    if not os.path.exists(ESTADO):
        print("No se está vigilando.")
        return
    with open(ESTADO, encoding="utf-8") as f:
        desde = local(H.llegeix(json.load(f)["des_de"]))
    print(json.dumps(evalua(referencia(), lee(CASA), desde, local()),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "inicia":
        inicia(sys.argv[2] if len(sys.argv) > 2 else None)
    elif orden == "vigila":
        vigila()
    elif orden == "estat":
        estat()
    else:
        print(__doc__)
