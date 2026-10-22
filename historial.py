#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El historial de la gráfica y el acierto de la previsión (ADR 0099; Juanjo,
17-10-2026: «que se pueda ir hacia atrás sin límite» y «algún índice o
indicador de lo buena que es la predicción… con el tiempo debería mejorar»).

Para cada día, hora a hora, lo medido en Montflorit y lo que decía la web de
1 a 24 horas antes (Juanjo, 17-10-2026: «si elijo 1h, me salga la gráfica
con lo que se predijo 1h antes de cada hora y con el error, lo mismo con
2h, etc, hasta 24»):

- Lo medido: la temperatura de la estación de casa (estacio-casa.csv), la
  media de las lecturas del principio y del final de la hora, que es lo que
  la previsión anuncia para el tramo (casa.py: la media de las dos horas en
  punto; desde la 3.141.0, antes se comparaba con la lectura del final), y
  la lluvia de la hora como la cuenta el aprendizaje (aprenentatge.observada:
  casa, las vecinas que cuentan y, para las horas secas, Meteocat). Si no se
  sabe si llovió, None. Las horas con sol directo sobre el termómetro
  (sol_estacio.py, ADR 0081) llevan `sol` y no cuentan para el acierto de la
  temperatura, como en el aprendizaje.
- Lo previsto: lo que mostraba la web (`mostrat` de casa-AAAA-MM.jsonl, que
  apunta cada hora la previsión publicada) en la publicación de unas N horas
  antes del comienzo de la hora (entre N h y media antes y N h y media menos
  media hora), para N de 1 a 23 (cada publicación cubre 24 horas, contando la que ya ha
  empezado): `prev` = {"N": [temperatura, probabilidad, mm]} (los mm, desde la
  3.137.0: Juanjo, 18-10-2026, «quiero incluir los mm de lluvia predichos»).

El acierto, para cada antelación, sobre las horas con las dos cosas:
- Temperatura: el error medio absoluto (°C).
- Lluvia: por franjas de probabilidad anunciada (menos del 20 %, del 20 al
  50, del 50 al 70 y del 70 o más), cuántas horas hubo, en cuántas llovió y
  qué probabilidad decía de media (`franges`, desde la 3.141.0): si la
  probabilidad es buena, la fracción de horas con lluvia se parece a lo que
  decía. Es la comprobación de calibración de una probabilidad, contada en
  casos. Se conservan `plou` y `sec` (50 % o más; menos del 20 %) de los
  archivos anteriores. Y los milímetros: la lluvia esperada (la probabilidad
  de cada hora por sus milímetros, que son «si llueve»; desde la 3.143.0,
  ADR 0103) y la medida, sumadas en las horas que tienen las dos. Sumar los
  milímetros tal cual daba el doble de lo que caía (archivo 2024-2026).
Los últimos 30 días, los 30 anteriores (para ver si mejora) y por meses,
para cada antelación.

Archivos para la web (los sube publica.sh a IONOS):
  historial.json              los días que hay y el acierto
  historial-AAAA-MM-DD.json   cada día, hora a hora

  python3 historial.py fes CARPETA [DIES]   escribe el índice y los días (DIES: solo los últimos)
"""
import csv
import datetime as dt
import glob
import json
import os
import sys

import aprenentatge as A
import config as C
import previsio_oficial as O
import prevision as P
import remostreig as R
import sol_estacio as SE

REGISTRE = A.REGISTRE
PRIMER_DIA = dt.date(2026, 10, 4)       # el primero con la estación de casa en el registro
# Cada publicació porta les 24 hores següents, comptant la que ja ha començat:
# com a molt, 23 hores abans del començament d'una hora.
ANTELACIONS = range(1, 24)
PROB_PLOU = 0.5                          # «plourà», como en la web (PROB_PLUJA)
PROB_SEC = 0.2                           # «no plourà», por debajo de «possible pluja»
# Las franjas de probabilidad anunciada, por su límite inferior (en %): menos
# del 20, del 20 al 50, del 50 al 70 y del 70 o más. Las de la web (20 %,
# «possible pluja»; 50 %, «plourà») y una más arriba, para ver si la
# probabilidad alta se cumple (18-10-2026: de 11 horas con 70 % o más, llovió
# en 6, con un 89 % de media anunciado).
FRANGES = (0, 20, 50, 70)
DIES_FINESTRA = 30
MIN_HORES_TEMP = 48                      # para dar el error de la temperatura
MIN_CASOS_PLUJA = 20                     # para dar el acierto de la lluvia (en cada sentido)
# El formato de los días: si cambia, se rehacen todos, no solo los últimos
# (3.137.0: los mm previstos; 3.141.0: la temperatura del tramo, el sol y las
# franjas; 3.143.0: los mm esperados), y lo apunta en el registro. Por tandas: IONOS
# acepta como mucho 12 archivos por envío (reserva/rep-dades.sh, ADR 0057), y
# todos de golpe se rechazaron (18-10-2026, 22 archivos). Con los 2 días de
# siempre, el índice, los datos y las 4 imágenes, caben 3 más por pasada.
FORMAT = 5
REFER_PER_PASSADA = 3
# Si mejora con el tiempo (ADR 0110; Juanjo, 20-10-2026: «dado que la pagina
# aprende, estaria bien una comparación semana a semana»): por semanas de
# lunes a domingo, y la conclusión, las últimas SETMANES_COMPARA semanas
# completas contra las SETMANES_COMPARA anteriores, con el remuestreo por
# días (remostreig.seguretat_periodes).
SETMANES_COMPARA = 4
# Frente a Meteocat y AEMET (previsio_oficial.py): cada previsión oficial se
# compara con la que publicaba la web en el mismo momento (la publicación más
# cercana, a PARELLA_MIN minutos como mucho), en las mismas horas.
PARELLA_MIN = 35
FONTS_OFICIALS = ("meteocat", "aemet")


def hores_del_dia(dia):
    """Las horas de un día local (23 o 25 el día del cambio de hora): [(hora, fins)]."""
    ini = dt.datetime.combine(dia, dt.time()).replace(tzinfo=P.ZONA)
    fi = dt.datetime.combine(dia + dt.timedelta(days=1), dt.time()).replace(tzinfo=P.ZONA)
    res, t = [], ini.astimezone(dt.timezone.utc)
    while t < fi.astimezone(dt.timezone.utc):
        res.append((P.clau_hora(t), P.clau_hora(t + dt.timedelta(hours=1))))
        t += dt.timedelta(hours=1)
    return res


def emissions(registre=None):
    """Las previsiones apuntadas, {emes: {fins: mostrat}}, de casa-*.jsonl."""
    res = {}
    for ruta in sorted(glob.glob(os.path.join(registre or REGISTRE, "casa-*.jsonl"))):
        with open(ruta, encoding="utf-8") as f:
            for linia in f:
                try:
                    e = json.loads(linia)
                except ValueError:
                    continue
                hores = {h["fins"]: h["mostrat"] for h in e.get("hores") or [] if h.get("mostrat")}
                if hores:
                    res[e["emes"]] = hores
    return res


def per_hora(emes):
    """{fins: {N: mostrat}}: para cada hora, lo que decía la publicación de
    unas N horas antes de que empezara (la más reciente de las que caen entre
    N h y media y N h menos media hora antes)."""
    res = {}
    for k in sorted(emes):
        t = dt.datetime.fromisoformat(k)
        for fins, m in emes[k].items():
            ini = dt.datetime.fromisoformat(fins).replace(tzinfo=t.tzinfo) - dt.timedelta(hours=1)
            n = round((ini - t).total_seconds() / 3600)
            if n in ANTELACIONS:
                res.setdefault(fins, {})[n] = m
    return res


def temperatura_tram(casa, hora, fins):
    """La temperatura medida del tramo: la media de las lecturas del
    principio y del final, como la que anuncia la previsión (casa.py); None
    si falta alguna."""
    t0 = A._num((casa.get(hora) or {}).get("temperatura"))
    t1 = A._num((casa.get(fins) or {}).get("temperatura"))
    return None if t0 is None or t1 is None else round((t0 + t1) / 2, 1)


def un_dia(dia, casa, meteocat, veines, previstes, sol=()):
    """El día, para la web: {dia, hores: [...], encert: {N: …}}. sol: las
    horas en punto con sol directo sobre el termómetro (sol_estacio.hores_tocades)."""
    files = []
    for hora, fins in hores_del_dia(dia):
        t = temperatura_tram(casa, hora, fins)
        mm = A.observada(casa, meteocat, veines, fins)
        f = {"hora": hora, "fins": fins, "mesura": True,
             "temperatura": t,
             "pluja_mm": None if mm is None else round(mm, 1)}
        if hora in sol or fins in sol:
            f["sol"] = True
        p = previstes.get(fins)
        if p:
            f["prev"] = {str(n): [m.get("temperatura"), m.get("probabilitat"), m.get("pluja_mm")]
                         for n, m in sorted(p.items())}
        files.append(f)
    return {"dia": dia.isoformat(), "hores": files,
            "encert": {str(n): encert(files, n) for n in ANTELACIONS}}


def _prev(f, n):
    """(temperatura, probabilidad, mm) que decía la web n horas antes."""
    v = (f.get("prev") or {}).get(str(n))
    return (v[0], v[1], v[2] if len(v) > 2 else None) if v else (None, None, None)


def franja(p):
    """La franja (su límite inferior, en %) en que cae una probabilidad."""
    return max(f for f in FRANGES if p * 100 >= f - 1e-9)


def encert(files, n):
    """El acierto con n horas de antelación: {temperatura: {error, hores},
    pluja: {plou: [sí, de], sec: [sí, de], franges: {"20": [hores, plogudes,
    suma de la probabilidad]}}, mm: {previst, mesurat, hores}}. Sin las horas
    con sol sobre el termómetro para la temperatura."""
    signes = [_prev(f, n)[0] - f["temperatura"] for f in files
              if f["temperatura"] is not None and _prev(f, n)[0] is not None and not f.get("sol")]
    errors = [abs(e) for e in signes]
    plou, sec = [0, 0], [0, 0]
    franges = {str(k): [0, 0, 0.0] for k in FRANGES}
    brier = [0, 0, 0.0]
    for f in files:
        p = _prev(f, n)[1]
        if p is None or f["pluja_mm"] is None:
            continue
        mullat = f["pluja_mm"] >= C.UMBRAL_MM
        brier = [brier[0] + 1, brier[1] + mullat, round(brier[2] + (p - mullat) ** 2, 4)]
        if p >= PROB_PLOU:
            plou = [plou[0] + mullat, plou[1] + 1]
        elif p < PROB_SEC:
            sec = [sec[0] + (not mullat), sec[1] + 1]
        fr = franges[str(franja(p))]
        fr[0] += 1
        fr[1] += mullat
        fr[2] = round(fr[2] + p, 3)
    # Los mm esperados: probabilidad por mm (1 si ya llovía, que la web da como 100 %).
    mm = [((_prev(f, n)[1] if _prev(f, n)[1] is not None else 1.0) * _prev(f, n)[2], f["pluja_mm"])
          for f in files if _prev(f, n)[2] is not None and f["pluja_mm"] is not None]
    return {"temperatura": {"error": round(sum(errors) / len(errors), 2) if errors else None, "hores": len(errors),
                            "biaix": round(sum(signes) / len(signes), 2) if signes else None},
            "pluja": {"plou": plou, "sec": sec, "franges": franges, "brier": brier},
            "mm": {"previst": round(sum(p for p, _ in mm), 1), "mesurat": round(sum(m for _, m in mm), 1),
                   "hores": len(mm)}}


def suma(encerts):
    """El acierto de varios días juntos."""
    hores = sum(e["temperatura"]["hores"] for e in encerts)
    err = sum((e["temperatura"]["error"] or 0) * e["temperatura"]["hores"] for e in encerts)
    signe = sum((e["temperatura"].get("biaix") or 0) * e["temperatura"]["hores"] for e in encerts)
    brier = [0, 0, 0.0]
    for e in encerts:
        b = e["pluja"].get("brier") or [0, 0, 0.0]
        brier = [brier[0] + b[0], brier[1] + b[1], round(brier[2] + b[2], 4)]
    plou = [sum(e["pluja"]["plou"][i] for e in encerts) for i in (0, 1)]
    sec = [sum(e["pluja"]["sec"][i] for e in encerts) for i in (0, 1)]
    franges = {}
    for e in encerts:
        for k, (h, pl, sp) in (e["pluja"].get("franges") or {}).items():
            fr = franges.setdefault(k, [0, 0, 0.0])
            fr[0] += h
            fr[1] += pl
            fr[2] = round(fr[2] + sp, 3)
    mms = [e["mm"] for e in encerts if e.get("mm")]
    return {"temperatura": {"error": round(err / hores, 2) if hores else None, "hores": hores,
                            "biaix": round(signe / hores, 2) if hores else None},
            "pluja": {"plou": plou, "sec": sec, "franges": franges, "brier": brier},
            "mm": {"previst": round(sum(m["previst"] for m in mms), 1), "mesurat": round(sum(m["mesurat"] for m in mms), 1),
                   "hores": sum(m["hores"] for m in mms)}}


# --- La lluvia con el error de Brier, por semanas y frente a las previsiones
# oficiales (ADR 0110) ---------------------------------------------------------

def _brier_clima(b, clima):
    """El error de Brier sumado de decir siempre la climatología: b = [horas,
    con lluvia, …]. Con o = 0 o 1, (c − o)² = c² − 2co + o."""
    return b[0] * clima * clima - 2 * clima * b[1] + b[1]


def resum_pluja(b, clima):
    """El error de Brier medio y cuánto mejora a decir siempre la frecuencia
    de lluvia habitual (clima): 1 − Brier / Brier de la climatología."""
    n, plogudes, suma_b = b
    if not n:
        return {"hores": 0, "plogudes": 0, "brier": None, "clima": None, "millora_clima": None}
    ref = _brier_clima(b, clima) / n
    return {"hores": n, "plogudes": plogudes, "brier": round(suma_b / n, 4), "clima": round(ref, 4),
            "millora_clima": round(1 - (suma_b / n) / ref, 3) if ref > 0 else None}


def dilluns(d):
    return d - dt.timedelta(days=d.weekday())


def _emissio_propera(temps, valors, t):
    """La publicación de la web más cercana a t, a PARELLA_MIN minutos como mucho."""
    import bisect
    i = bisect.bisect_left(temps, t)
    millor = None
    for j in (i - 1, i):
        if 0 <= j < len(temps) and abs((temps[j] - t).total_seconds()) <= PARELLA_MIN * 60:
            if millor is None or abs((temps[j] - t).total_seconds()) < abs((temps[millor] - t).total_seconds()):
                millor = j
    return valors[millor] if millor is not None else None


def comparacio(dies, emes, oficials):
    """Las previsiones oficiales contra la de la web publicada en el mismo
    momento: {font: {N: {dia: [horas temp, Σ|web|, Σ|oficial|, Σ web, Σ oficial,
    horas lluvia, con lluvia, Brier web, Brier oficial]}}}. La temperatura
    oficial de la hora es la media de la de su principio y su final (como la
    de la web y la medida); la lluvia, «plou» si da UMBRAL_MM o más en la hora
    que acaba al final del tramo, y su Brier es el de una previsión de sí o no.
    Sin las horas con sol sobre el termómetro para la temperatura."""
    obs = {f["fins"]: (d["dia"], f) for d in dies for f in d["hores"]}
    ordenades = sorted((dt.datetime.fromisoformat(k), v) for k, v in emes.items())
    temps, valors = [t for t, _ in ordenades], [v for _, v in ordenades]
    res = {}
    for font in FONTS_OFICIALS:
        per_n = res.setdefault(font, {})
        for s, prev in oficials.get(font) or []:
            web = _emissio_propera(temps, valors, s)
            if not web:
                continue
            for fins, m in web.items():
                if fins not in obs:
                    continue
                dia, f = obs[fins]
                ini = dt.datetime.fromisoformat(f["hora"])
                ini = ini if ini.tzinfo else ini.replace(tzinfo=P.ZONA)
                n = round((ini - s).total_seconds() / 3600)
                if n not in ANTELACIONS:
                    continue
                acc = per_n.setdefault(n, {}).setdefault(dia, [0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0, 0.0])
                t0, t1 = prev["t"].get(f["hora"]), prev["t"].get(fins)
                tw = m.get("temperatura")
                if None not in (t0, t1, tw, f["temperatura"]) and not f.get("sol"):
                    to = (t0 + t1) / 2
                    acc[0] += 1
                    acc[1] += abs(tw - f["temperatura"])
                    acc[2] += abs(to - f["temperatura"])
                    acc[3] += tw - f["temperatura"]
                    acc[4] += to - f["temperatura"]
                pw, mo = m.get("probabilitat"), prev["mm"].get(fins)
                if None not in (pw, mo, f["pluja_mm"]):
                    o = f["pluja_mm"] >= C.UMBRAL_MM
                    acc[5] += 1
                    acc[6] += o
                    acc[7] += (pw - o) ** 2
                    acc[8] += ((mo >= C.UMBRAL_MM) - o) ** 2
    return res


def resum_comparacio(per_dia):
    """La comparación de unos días: {temperatura: {hores, web, oficial,
    web_biaix, oficial_biaix, seguretat}, pluja: {hores, plogudes, web,
    oficial, seguretat}}. seguretat: en qué parte de los remuestreos por días
    se equivoca menos la web (remostreig.seguretat); con un 95 % o más la
    web acierta más, con un 5 % o menos acierta más la oficial."""
    dies = sorted(per_dia)
    v = [per_dia[d] for d in dies]
    nt, npl = sum(x[0] for x in v), sum(x[5] for x in v)
    temp = {"hores": nt}
    if nt:
        temp.update({"web": round(sum(x[1] for x in v) / nt, 2), "oficial": round(sum(x[2] for x in v) / nt, 2),
                     "web_biaix": round(sum(x[3] for x in v) / nt, 2),
                     "oficial_biaix": round(sum(x[4] for x in v) / nt, 2),
                     "seguretat": R.seguretat([x[1] for x in v], [x[2] for x in v], dies)})
    pluja = {"hores": npl, "plogudes": sum(x[6] for x in v)}
    if npl:
        pluja.update({"web": round(sum(x[7] for x in v) / npl, 4), "oficial": round(sum(x[8] for x in v) / npl, 4),
                      "seguretat": R.seguretat([x[7] for x in v], [x[8] for x in v], dies)})
    return {"temperatura": temp, "pluja": pluja}


def millora(dies_encert, avui):
    """Las últimas SETMANES_COMPARA semanas completas contra las anteriores:
    {setmanes, temperatura: {abans, ara, seguretat}, pluja: {…}}, con el
    error medio por hora de cada periodo (°C; Brier) y en qué parte de los
    remuestreos por días es menor el de ahora. Sin bastantes semanas, solo
    las que hay."""
    fi = dilluns(avui)                      # la semana en curso no cuenta
    complets = [(d, e) for d, e in dies_encert if dt.date.fromisoformat(d) < fi
                and (e["temperatura"]["hores"] or (e["pluja"].get("brier") or [0])[0])]
    setmanes = len({dilluns(dt.date.fromisoformat(d)) for d, _ in complets})
    res = {"setmanes": setmanes, "cal": 2 * SETMANES_COMPARA}
    if setmanes < 2 * SETMANES_COMPARA:
        return res
    tall = fi - dt.timedelta(weeks=SETMANES_COMPARA)
    ini = tall - dt.timedelta(weeks=SETMANES_COMPARA)
    abans = [e for d, e in complets if ini <= dt.date.fromisoformat(d) < tall]
    ara = [e for d, e in complets if tall <= dt.date.fromisoformat(d) < fi]

    def compara(sumes, casos):
        sa, na = [sumes(e) for e in abans], [casos(e) for e in abans]
        sb, nb = [sumes(e) for e in ara], [casos(e) for e in ara]
        if not sum(na) or not sum(nb):
            return None
        return {"abans": round(sum(sa) / sum(na), 4), "ara": round(sum(sb) / sum(nb), 4),
                "seguretat": R.seguretat_periodes(sa, na, sb, nb)}
    res["temperatura"] = compara(lambda e: (e["temperatura"]["error"] or 0) * e["temperatura"]["hores"],
                                 lambda e: e["temperatura"]["hores"])
    res["pluja"] = compara(lambda e: (e["pluja"].get("brier") or [0, 0, 0])[2],
                           lambda e: (e["pluja"].get("brier") or [0, 0, 0])[0])
    return res


# --- Cómo aprende la web (ADR 0110; Juanjo, 20-10-2026: «no veo nada sobre
# como aprende la web») -------------------------------------------------------

def _json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def aprenentatge(dir_=None):
    """Lo que la página cuenta del aprendizaje, de lo que deja cada día en el
    NAS: la probabilidad de lluvia y la temperatura (aprenentatge.py,
    historial.csv: el método vigente, el candidato propio con su error y el
    del vigente en las mismas horas, y lo que le falta para poder decidir), el
    radar (radar_fonts.py) y el cielo (nuvols.py)."""
    dir_ = dir_ or A.DIR
    num = lambda x: float(x) if x not in (None, "") else None
    dies = []
    try:
        with open(os.path.join(dir_, "historial.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                dies.append({"dia": r["dia"], "pluja": r.get("pluja") or None, "temperatura": r.get("temperatura") or None,
                             "hores_pluja": num(r.get("hores_pluja")), "error_pluja": num(r.get("error_pluja")),
                             "error_pluja_vigent": num(r.get("error_pluja_arxiu")),
                             "dies_temperatura": num(r.get("dies_temperatura")), "error_temp": num(r.get("error_temp")),
                             "error_temp_vigent": num(r.get("error_temp_model"))})
    except OSError:
        pass
    res = {"dies": dies, "minims": {"hores_pluja": A.MIN_HORES_PLUJA, "dies_temperatura": A.MIN_DIES_TEMPERATURA,
                                     "dies_humitat": A.MIN_DIES_HUMITAT}}
    res["humitat"] = humitat(dir_)
    radar = _json(os.path.join(dir_, "radar-font.json"))
    if radar and radar.get("preferida"):
        c = radar.get("comparacio") or {}
        # L'error de cada radar i amb quants casos, per dibuixar-los a la
        # pàgina (Juanjo, 20-10-2026: «por qué no pones los datos de quien
        # acierta y se equivoca más?»).
        res["radar"] = {"preferida": radar["preferida"], "des_de": radar.get("des_de"), "dia": radar.get("dia"),
                        "dies_pluja": c.get("dies_pluja"), "seguretat": c.get(f"seguretat_{radar['preferida']}"),
                        "casos": c.get("parelles"), "amb_pluja": c.get("amb_pluja"),
                        "error": {n: c[f"brier_{n}"] for n in ("meteocat", "rainviewer") if c.get(f"brier_{n}") is not None}}
    cel = _json(os.path.join(dir_, "nuvols-pesos.json"))
    if cel and cel.get("pesos"):
        c = cel.get("comparacio") or {}
        # I l'error de cada model i de la mitjana que fa servir, en punts de cel tapat.
        res["cel"] = {"pesos": cel["pesos"], "dia": cel.get("dia"), "dies": c.get("dies"),
                      "error": {m: c[f"error_{m}"] for m in cel["pesos"] if c.get(f"error_{m}") is not None},
                      "error_actual": c.get("error_actual")}
    res["canvis"] = canvis(dies, dir_)
    return res


def humitat(dir_=None):
    """La corrección del rocío (ADR 0114): cómo salió con el año de casa
    (calibracio/humitat_casa.json) y, día a día, la que aprende el NAS con el
    barrio (historial-humitat.csv), en puntos de humedad. None sin ninguna."""
    num = lambda x: float(x) if x not in (None, "") else None
    dies = []
    try:
        with open(os.path.join(dir_ or A.DIR, "historial-humitat.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                dies.append({"dia": r["dia"], "humitat": r.get("humitat") or None, "dies": num(r.get("dies")),
                             "error": num(r.get("error_humitat")), "error_vigent": num(r.get("error_humitat_abans"))})
    except OSError:
        pass
    arxiu = _json(A.ARXIU_HUMITAT)
    v = (arxiu or {}).get("validacio") or {}
    resum = arxiu and {"des_de": arxiu.get("des_de"), "fins": arxiu.get("fins"), "adoptat": arxiu.get("adoptat"),
                       "dies": v.get("dies_avaluats"), "seguretat": v.get("seguretat"),
                       "error": v.get("humitat_error_corregit"), "error_model": v.get("humitat_error_model")}
    return {"dies": dies, "arxiu": resum} if dies or resum else None


def canvis(dies, dir_=None):
    """Lo que la web ha cambiado sola, con la fecha (Juanjo, 20-10-2026: «en
    como aprende quiero q aparezcan las mejoras que hay dia a dia»): el
    método de la lluvia y de la temperatura (historial.csv) y, desde cuándo,
    el radar que usa (radar-font.json) y la regla del final de la lluvia
    (fi-pluja.json): de esos dos solo se guarda la vigente. Las pasadas de
    radar-fonts-*.jsonl no sirven: cambian de radar cuando uno falla.
    [{dia, que, a}], del más reciente al más antiguo."""
    res = []
    hum = (humitat(dir_) or {}).get("dies", [])
    for que, llista in (("pluja", dies), ("temperatura", dies), ("humitat", hum)):
        abans = None
        for d in llista:
            if d.get(que) and abans and d[que] != abans:
                res.append({"dia": d["dia"], "que": que, "a": d[que]})
            abans = d.get(que) or abans
    radar = _json(os.path.join(dir_ or A.DIR, "radar-font.json"))
    if radar and radar.get("des_de") and radar.get("preferida"):
        res.append({"dia": radar["des_de"], "que": "radar", "a": radar["preferida"]})
    fi = _json(os.path.join(dir_ or A.DIR, "fi-pluja.json"))
    if fi and fi.get("des_de"):
        res.append({"dia": fi["des_de"], "que": "fi_pluja", "a": None})
    return sorted(res, key=lambda c: c["dia"], reverse=True)


def tots(avui=None, registre=None, emes=None):
    """Todos los días del registro, del primero a hoy."""
    avui = avui or dt.date.today()
    if registre:
        A.REGISTRE = registre
    casa = A._llegeix("estacio-casa.csv")
    meteocat, veines = A._meteocat(), A._veines()
    previstes = per_hora(emes if emes is not None else emissions(registre))
    # Las horas con sol directo sobre el termómetro (ADR 0081), del registro.
    sol = SE.hores_tocades(list(casa), SE.episodis(os.path.join(registre or A.REGISTRE, "sol-estacio.csv")))
    dies, d = [], PRIMER_DIA
    while d <= avui:
        dies.append(un_dia(d, casa, meteocat, veines, previstes, sol))
        d += dt.timedelta(days=1)
    return dies


def index(dies, avui, comp=None):
    """historial.json: los días que hay y el acierto de los últimos 30 días,
    de los 30 anteriores y de cada mes, con los mínimos para darlo. Hoy
    también, con sus horas ya pasadas (las que faltan no tienen medida): así
    cuadra con la gráfica (Juanjo, 18-10-2026: «entre ayer y hoy ha habido
    más»). `periode`: desde qué día cuenta la ventana y cuántos días son.
    Desde la 3.165.0 (ADR 0110), para cada antelación: la lluvia con el error
    de Brier frente a la climatología de todo el registro (`pluja`), el acierto
    por semanas (`setmanes`), si mejora (`millora`) y, con comp
    (comparacio()), frente a Meteocat y AEMET (`oficial`)."""
    complets = [d for d in dies if d["dia"] <= avui.isoformat()]
    fi = avui + dt.timedelta(days=1)
    des_de = max(PRIMER_DIA, fi - dt.timedelta(days=DIES_FINESTRA))
    comp = comp or {}

    def per_antelacio(n):
        finestra = lambda ini, fi_: [d["encert"][str(n)] for d in complets
                                     if ini.isoformat() <= d["dia"] < fi_.isoformat()]
        mesos = {}
        for d in complets:
            mesos.setdefault(d["dia"][:7], []).append(d["encert"][str(n)])
        # La climatología: la parte de las horas con lluvia en todo el registro.
        total = suma([d["encert"][str(n)] for d in complets])["pluja"]["brier"]
        clima = total[1] / total[0] if total[0] else 0
        darrers = [(d["dia"], d["encert"][str(n)]) for d in complets
                   if (fi - dt.timedelta(days=DIES_FINESTRA)).isoformat() <= d["dia"] < fi.isoformat()]
        pluja = resum_pluja(suma([e for _, e in darrers])["pluja"]["brier"], clima)
        pluja["seguretat_clima"] = (R.seguretat([(e["pluja"].get("brier") or [0, 0, 0])[2] for _, e in darrers],
                                                [_brier_clima(e["pluja"].get("brier") or [0, 0, 0], clima)
                                                 for _, e in darrers], [d for d, _ in darrers])
                                    if pluja["hores"] else None)
        per_setmana = {}
        for d in complets:
            per_setmana.setdefault(dilluns(dt.date.fromisoformat(d["dia"])), []).append(d)
        setmanes = []
        for dl, ds in sorted(per_setmana.items()):
            e = suma([d["encert"][str(n)] for d in ds])
            fila = {"des_de": dl.isoformat(), "dies": len(ds), "en_curs": dl == dilluns(avui),
                    "temperatura": e["temperatura"], "pluja": resum_pluja(e["pluja"]["brier"], clima)}
            dies_s = {d["dia"] for d in ds}
            oficials = {font: resum_comparacio({k: v for k, v in (comp.get(font) or {}).get(n, {}).items()
                                                if k in dies_s}) for font in FONTS_OFICIALS}
            fila["oficial"] = {f: r for f, r in oficials.items() if r["temperatura"]["hores"] or r["pluja"]["hores"]}
            if e["temperatura"]["hores"] or e["pluja"]["brier"][0]:
                setmanes.append(fila)
        oficial = {}
        for font in FONTS_OFICIALS:
            dies_f = {k: v for k, v in (comp.get(font) or {}).get(n, {}).items()
                      if (fi - dt.timedelta(days=DIES_FINESTRA)).isoformat() <= k < fi.isoformat()}
            r = resum_comparacio(dies_f)
            if r["temperatura"]["hores"] or r["pluja"]["hores"]:
                oficial[font] = {**r, "des_de": min(dies_f)}
        return {"darrers": suma([e for _, e in darrers]),
                "anteriors": suma(finestra(fi - dt.timedelta(days=2 * DIES_FINESTRA),
                                           fi - dt.timedelta(days=DIES_FINESTRA))),
                "mesos": {m: suma(e) for m, e in sorted(mesos.items())},
                "pluja": pluja, "setmanes": setmanes,
                "millora": millora([(d["dia"], d["encert"][str(n)]) for d in complets], avui),
                "oficial": oficial}
    return {"generat": dt.datetime.now(P.ZONA).isoformat(timespec="minutes"),
            "dies": [d["dia"] for d in dies],
            "minims": {"temperatura_hores": MIN_HORES_TEMP, "pluja_casos": MIN_CASOS_PLUJA},
            "franges": list(FRANGES),
            "periode": {"des_de": des_de.isoformat(), "dies": (fi - des_de).days},
            "encert": {str(n): per_antelacio(n) for n in ANTELACIONS}}


def fes(carpeta, ultims=None, avui=None, registre=None):
    """Escribe historial.json y los días (todos o los `ultims`). Devuelve los nombres."""
    avui = avui or dt.date.today()
    emes = emissions(registre)
    dies = tots(avui, registre, emes)
    comp = comparacio(dies, emes, O.registre(registre or A.REGISTRE))
    os.makedirs(carpeta, exist_ok=True)
    noms = ["historial.json"]
    def escriu(nom, dades):
        with open(os.path.join(carpeta, nom), "w", encoding="utf-8") as f:
            json.dump(dades, f, ensure_ascii=False, separators=(",", ":"))
    i = index(dies, avui, comp)
    i["aprenentatge"] = aprenentatge()
    escriu("historial.json", i)
    # La marca: el formato, si ya están todos; si no, {"format", "seguent"}, el
    # primer día que falta rehacer.
    marca = os.path.join(registre or A.REGISTRE, "historial-format")
    try:
        with open(marca) as f:
            text = f.read().strip()
    except OSError:
        text = ""
    triats = dies[-ultims:] if ultims else dies
    pendent = None
    if ultims and text != str(FORMAT):
        try:
            m = json.loads(text)
            seguent = m["seguent"] if m.get("format") == FORMAT else PRIMER_DIA.isoformat()
        except (ValueError, TypeError, KeyError, AttributeError):
            seguent = PRIMER_DIA.isoformat()
        vells = [d for d in dies[:-ultims] if d["dia"] >= seguent]
        triats = vells[:REFER_PER_PASSADA] + triats
        pendent = vells[REFER_PER_PASSADA]["dia"] if len(vells) > REFER_PER_PASSADA else None
    for d in triats:
        nom = f"historial-{d['dia']}.json"
        escriu(nom, d)
        noms.append(nom)
    if ultims and text != str(FORMAT):
        try:
            with open(marca, "w") as f:
                f.write(json.dumps({"format": FORMAT, "seguent": pendent}) if pendent else str(FORMAT))
        except OSError:
            pass
    return noms


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4) or sys.argv[1] != "fes":
        sys.exit(__doc__)
    print(" ".join(fes(sys.argv[2], int(sys.argv[3]) if len(sys.argv) == 4 else None)))
