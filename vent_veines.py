#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El viento de ahora con las estaciones vecinas de Weather Underground
(ADR 0064).

Las vecinas están a menos de un kilómetro y dan una lectura cada 5 minutos,
pero sus anemómetros no están a 10 m ni en campo abierto, como los de
Meteocat: marcan menos viento, y alguno casi siempre cero. Por eso no se
promedian tal cual. Cada día se aprende, con lo registrado por medias horas:

- de cada vecina, el factor que la lleva al viento de Sant Cugat (mínimos
  cuadrados por el origen) y lo bien que lo sigue (correlación);
- solo cuentan las que lo siguen (correlación de 0,6 o más y casi ningún cero
  cuando en Sant Cugat sopla);
- la estimación es la media de esas vecinas, cada una multiplicada por su
  factor y con un peso inverso a su error.

Se comprueba dejando fuera cada día: el error de la estimación contra Sant
Cugat se compara con el de Sabadell (otra estación oficial a 5 km) y con el
de la media hora anterior de Sant Cugat (lo que la página enseña ahora, que
llega con retraso). Cuando hay bastantes medias horas con viento de verdad,
avisa una vez a Juanjo con las cifras: la página solo pasa a usar la
estimación si él lo decide (config.VENT_VEINES_ACTIU).

Uso:
  python3 vent_veines.py omple    rellena el registro con los últimos 7 días
  python3 vent_veines.py apren    ajusta, comprueba y avisa si toca
  python3 vent_veines.py estat    lo aprendido y sus cifras
"""
import csv
import datetime as dt
import json
import math
import os
import subprocess
import sys
import urllib.parse
import urllib.request

import config as C
import hora as H
import registre as R

CSV = os.path.join(R.DIR, "vent-mitges-hores.csv")
DIR = os.environ.get("APRENENTATGE_DIR", "/estat/aprenentatge")
MODEL = os.path.join(DIR, "vent-veines.json")
AVIS = os.path.join(DIR, "avis-vent-veines")

REFERENCIA = "XV"              # Sant Cugat: la que enseña ahora la página
CONTRAST = "XF"                # Sabadell: la otra estación oficial
OFICIALS = (REFERENCIA, CONTRAST)
LECTURES_MIN = 4               # de 6 lecturas de 5 minutos en la media hora
MIN_PARELLES = 96              # dos días de medias horas por vecina
R_MIN = 0.6
ZEROS_MAX = 0.25               # medias horas a cero cuando en Sant Cugat sopla
SOPLA_KMH = 5
VENT_FORT_KMH = 15             # viento de verdad, para poder decidir
MIN_VENTOSES = 12              # seis horas de viento de verdad
DIES_APREN = 60
VARIABLES = ("mitja", "ratxa")
PORTAL = "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json"
PORTAL_VAR = {"30": "mitja", "50": "ratxa"}   # m/s, a 10 m


def camps():
    res = ["fins"]
    for e in OFICIALS + tuple(C.VEINES):
        res += [e, f"{e}_ratxa"]
    return res


def _fi_mitja_hora(t):
    """El final de la media hora en que cae t (t incluido en ese final)."""
    base = t.replace(minute=t.minute - t.minute % 30, second=0, microsecond=0)
    return base if t == base else base + dt.timedelta(minutes=30)


def mitges_hores_veina(files):
    """Medias horas completas de una vecina (wunderground.files): {fin local:
    (media de las lecturas de 5 minutos, racha más alta)}."""
    grups = {}
    for f in files:
        if f.get("vent") is None:
            continue
        grups.setdefault(_fi_mitja_hora(f["t"]), []).append(f)
    res = {}
    for fin, fs in grups.items():
        if len(fs) < LECTURES_MIN:
            continue
        ratxes = [f["ratxa"] for f in fs if f.get("ratxa") is not None]
        res[fin] = (round(sum(f["vent"] for f in fs) / len(fs), 1), max(ratxes) if ratxes else None)
    return res


def mitges_hores_meteocat(files):
    """Medias horas de una estación de Meteocat (prevision.files_meteocat):
    {fin local: (VVM, VVX)}."""
    import prevision as P
    res = {}
    for ini, fila in files:
        mitja = P._columna(fila, "VVM")
        if mitja is not None:
            res[H.utc(ini + dt.timedelta(minutes=30))] = (mitja, P._columna(fila, "VVX"))
    return res


def apunta(columnes, ruta=None):
    """Añade al registro {estación: {fin: (media, racha)}}, fila a fila, sin
    borrar lo que ya tenían las otras columnas."""
    import prevision as P
    ruta = ruta or CSV
    if not any(columnes.values()):
        return
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    files = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            files = {r["fins"]: r for r in csv.DictReader(f)}
    for est, valors in columnes.items():
        for fin, (mitja, ratxa) in valors.items():
            clau = P.clau_hora(fin)
            fila = files.setdefault(clau, {"fins": clau})
            fila[est], fila[f"{est}_ratxa"] = mitja, ratxa
    cs = camps()
    with open(ruta + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cs, extrasaction="ignore")
        w.writeheader()
        w.writerows({k: files[c].get(k) for k in cs} for c in sorted(files, key=P.ordre_hora))
    os.replace(ruta + ".tmp", ruta)


def portal(codi, desde, lector=None):
    """Medias horas de Meteocat desde el portal de datos abiertos de la
    Generalitat (va una hora por detrás; cada lectura marca el inicio de su
    media hora, en UTC): {fin local: (media, racha)} en km/h."""
    q = urllib.parse.urlencode({
        "$where": (f"codi_estacio='{codi}' AND codi_variable in('30','50') "
                   f"AND data_lectura >= '{desde.astimezone(dt.timezone.utc):%Y-%m-%dT%H:%M:%S}'"),
        "$limit": 50000})
    leer = lector or (lambda url: json.load(urllib.request.urlopen(url, timeout=60)))
    res = {}
    for r in leer(f"{PORTAL}?{q}"):
        ini = dt.datetime.fromisoformat(r["data_lectura"][:19]).replace(tzinfo=dt.timezone.utc)
        fin = H.utc(ini + dt.timedelta(minutes=30))
        v = res.setdefault(fin, {})
        v[PORTAL_VAR[r["codi_variable"]]] = round(float(r["valor_lectura"]) * 3.6, 1)
    return {fin: (v.get("mitja"), v.get("ratxa")) for fin, v in res.items() if v.get("mitja") is not None}


def omple(dies=7, ara=None):
    """Rellena el registro con lo que aún dan las fuentes: 7 días de las
    vecinas (Weather Underground no da más) y lo mismo de Meteocat."""
    import wunderground as WU
    ara = ara or H.ara()
    columnes = {}
    for est in C.VEINES:
        files = []
        for d in range(dies, -1, -1):
            dia = (H.dia_local(ara) - dt.timedelta(days=d)).strftime("%Y%m%d")
            try:
                files += WU.files(WU._consulta("history/all", {"stationId": est, "date": dia}, None))
            except Exception as ex:
                print(f"{est} {dia}: {ex}", file=sys.stderr)
        columnes[est] = mitges_hores_veina(files)
    for codi in OFICIALS:
        columnes[codi] = portal(codi, ara - dt.timedelta(days=dies + 1))
    apunta(columnes)
    return {k: len(v) for k, v in columnes.items()}


# --- Aprender -------------------------------------------------------------------------

def llegeix(ruta=None, desde=None):
    ruta = ruta or CSV
    if not os.path.exists(ruta):
        return []
    res = []
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            # En UTC, també les files d'abans de la migració (ADR 0128).
            fins = H.clau(r["fins"])
            if desde and fins < desde:
                continue
            fila = {"fins": fins}
            for k, v in r.items():
                if k != "fins":
                    fila[k] = float(v) if v not in (None, "") else None
            res.append(fila)
    return res


def _clau(est, var):
    return est if var == "mitja" else f"{est}_ratxa"


def _r(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0


def ajusta(files, var="mitja"):
    """De cada vecina: factor, correlación, ceros, error y si cuenta."""
    res = {}
    ref = _clau(REFERENCIA, var)
    for est in C.VEINES:
        k = _clau(est, var)
        ps = [(f[k], f[ref]) for f in files if f.get(k) is not None and f.get(ref) is not None]
        xs, ys = [p[0] for p in ps], [p[1] for p in ps]
        info = {"parelles": len(ps)}
        sxx = sum(x * x for x in xs)
        if len(ps) >= 2 and sxx > 0:
            factor = sum(x * y for x, y in ps) / sxx
            bufa = [x for x, y in ps if y >= SOPLA_KMH]
            info.update({
                "factor": round(factor, 3),
                "r": round(_r(xs, ys), 3),
                "zeros": round(sum(x < 0.5 for x in bufa) / len(bufa), 3) if bufa else None,
                "error_quadratic": round(sum((factor * x - y) ** 2 for x, y in ps) / len(ps), 3)})
        info["compta"] = bool(info["parelles"] >= MIN_PARELLES and info.get("r", 0) >= R_MIN
                              and info.get("zeros") is not None and info["zeros"] <= ZEROS_MAX
                              and info.get("error_quadratic"))
        res[est] = info
    return res


def estima(ajust, valors):
    """La estimación con las vecinas que cuentan y tienen lectura ahora
    (valors: {estación: km/h}). None si no hay ninguna."""
    num = den = 0.0
    usades = []
    for est, info in ajust.items():
        x = valors.get(est)
        if not info.get("compta") or x is None:
            continue
        w = 1 / max(info["error_quadratic"], 0.25)
        num += w * info["factor"] * x
        den += w
        usades.append(est)
    return (round(num / den, 1), usades) if den else (None, [])


def valida(files, var="mitja"):
    """Dejando fuera cada día: error medio absoluto contra Sant Cugat de la
    estimación, de Sabadell y de la media hora anterior de Sant Cugat, en las
    mismas medias horas."""
    import prevision as P
    ref, con = _clau(REFERENCIA, var), _clau(CONTRAST, var)
    per_fins = {H.clau(f["fins"]): f for f in files}
    dies = sorted({f["fins"][:10] for f in files})
    err = {"estimacio": [], "sabadell": [], "abans": []}
    ventoses = 0
    for dia in dies:
        ajust = ajusta([f for f in files if f["fins"][:10] != dia], var)
        for f in files:
            if f["fins"][:10] != dia or f.get(ref) is None or f.get(con) is None:
                continue
            est, _ = estima(ajust, {e: f.get(_clau(e, var)) for e in C.VEINES})
            abans = per_fins.get(P.clau_hora(H.utc(f["fins"])
                                             - dt.timedelta(minutes=30)), {}).get(ref)
            if est is None or abans is None:
                continue
            err["estimacio"].append(abs(est - f[ref]))
            err["sabadell"].append(abs(f[con] - f[ref]))
            err["abans"].append(abs(abans - f[ref]))
            ventoses += f[REFERENCIA] is not None and f[REFERENCIA] >= VENT_FORT_KMH
    n = len(err["estimacio"])
    return {"mitges_hores": n, "ventoses": ventoses,
            **{k: round(sum(v) / n, 2) if n else None for k, v in err.items()}}


def apren(ara=None, avisa=True, registre=None, directori=None):
    """Ajusta con los últimos DIES_APREN días (completando antes Meteocat con
    el portal), guarda lo aprendido y avisa una vez si ya se puede decidir.
    Sin registro todavía, no hace nada."""
    ara = ara or H.ara()
    ruta = os.path.join(registre, os.path.basename(CSV)) if registre else CSV
    directori = directori or DIR
    if not os.path.exists(ruta):
        return None
    try:
        apunta({c: portal(c, ara - dt.timedelta(days=3)) for c in OFICIALS}, ruta)
    except Exception as ex:
        print("No he pogut llegir Meteocat al portal:", ex, file=sys.stderr)
    files = llegeix(ruta, H.clau(ara - dt.timedelta(days=DIES_APREN)))
    model = {"dia": H.dia_local(ara).isoformat(),
             **{var: {"veines": ajusta(files, var), "validacio": valida(files, var)} for var in VARIABLES}}
    os.makedirs(directori, exist_ok=True)
    desti = os.path.join(directori, os.path.basename(MODEL))
    with open(desti + ".tmp", "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=1)
    os.replace(desti + ".tmp", desti)
    marca = os.path.join(directori, os.path.basename(AVIS))
    text = avis(model, marca)
    if text:
        print(text)
        open(marca, "w").close()
        if avisa:
            subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", text], check=False)
    return model


def avis(model, marca=None):
    """El texto para Juanjo, una sola vez, cuando la comprobación ya tiene
    MIN_VENTOSES medias horas de viento de verdad (Juanjo, 10-10-2026: «¿te
    acordarás de mirar los resultados para tomar una decisión?»)."""
    v = model["mitja"]["validacio"]
    if os.path.exists(marca or AVIS) or v["ventoses"] < MIN_VENTOSES or v["estimacio"] is None:
        return None
    compten = [C.VEINES[e]["nom"] for e, i in model["mitja"]["veines"].items() if i["compta"]]
    km = lambda x: f"{x:.1f}".replace(".", ",") + "\u00a0km/h"
    millor = v["estimacio"] <= min(v["sabadell"], v["abans"])
    return (f"Temps a casa, vent de les estacions veïnes: ja hi ha {v['ventoses']} mitges hores amb "
            f"{VENT_FORT_KMH}\u00a0km/h o més a Sant Cugat. Error mitjà contra Sant Cugat en dies no vistos "
            f"({v['mitges_hores']} mitges hores): estimació amb les veïnes ({'; '.join(compten) or 'cap'}) "
            f"{km(v['estimacio'])}, Sabadell {km(v['sabadell'])}, Sant Cugat de mitja hora abans {km(v['abans'])}. "
            + ("L'estimació encerta tant o més: decideix si la pàgina la fa servir."
               if millor else "L'estimació encerta menys: millor seguir amb Sant Cugat."))


def carrega():
    try:
        with open(MODEL, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# --- Ahora -----------------------------------------------------------------------------

def ara(veines, model=None, ahora=None):
    """El viento de ahora estimado con las vecinas (wunderground.veines_ara):
    la media de su última media hora, llevada a 10 m. None si no hay modelo
    o ninguna vecina que cuente tiene lecturas recientes."""
    model = model if model is not None else carrega()
    if not model:
        return None
    ahora = ahora or H.ara()
    darrera, valors = None, {"mitja": {}, "ratxa": {}}
    for v in veines:
        fs = [f for f in v.get("files") or [] if f.get("vent") is not None
              and dt.timedelta(0) <= ahora - f["t"] <= dt.timedelta(minutes=30)]
        if len(fs) < LECTURES_MIN:
            continue
        valors["mitja"][v["estacio"]] = sum(f["vent"] for f in fs) / len(fs)
        ratxes = [f["ratxa"] for f in fs if f.get("ratxa") is not None]
        if ratxes:
            valors["ratxa"][v["estacio"]] = max(ratxes)
        darrera = max(darrera or fs[-1]["t"], fs[-1]["t"])
    mitja, usades = estima(model["mitja"]["veines"], valors["mitja"])
    if mitja is None:
        return None
    ratxa, _ = estima(model["ratxa"]["veines"], valors["ratxa"])
    return {"estacio": "estacions veïnes", "font": "veines", "mitja": mitja, "ratxa": ratxa,
            "estacions": usades, "fins": H.clau(darrera)}


def estat():
    m = carrega()
    if not m:
        print("Encara no s'ha après res.")
        return
    print("Après el", m["dia"])
    for var in VARIABLES:
        print(f"\n{var}:", json.dumps(m[var]["validacio"], ensure_ascii=False))
        for e, i in m[var]["veines"].items():
            print(f"  {e:9} {C.VEINES[e]['nom']:28} {json.dumps(i, ensure_ascii=False)}")


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "omple":
        print(omple())
    elif orden == "apren":
        apren(avisa="--sense-avis" not in sys.argv)
        estat()
    elif orden == "estat":
        estat()
    else:
        print(__doc__)
