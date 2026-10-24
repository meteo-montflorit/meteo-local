#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Aprendizaje de la página de casa con lo que pasó de verdad (ADR 0012).

Dos regresiones, sin IA, ajustadas con numpy:

- Lluvia: regresión logística. Da la probabilidad de que caigan 0,2 mm o
  más en una hora a partir de la lluvia de los tres modelos finos (cuánta, si
  cada uno da alguna y cuántos coinciden), la antelación, la hora y el día
  del año (ADR 0021) y, con datos propios, la fracción del ensemble y la
  lluvia que medía la estación de casa al hacer la previsión.
- Temperatura: regresión lineal (ridge) del error del modelo en la estación
  de casa según la propia temperatura, las nubes, la humedad, la radiación,
  la hora, el día del año, la antelación y el error que tenía el modelo al
  prever (ADR 0017). La temperatura corregida es la del modelo menos ese error.
- Humedad: la misma regresión para el punto de rocío del modelo, contra el
  rocío medido en el barrio (la mediana de casa y las vecinas, como el
  recuadro «Ara»), con el error que tenía al prever (ADR 0114). La humedad de
  cada hora sale de ese rocío y de la temperatura corregida.

Mientras no hay bastantes datos propios, la lluvia usa el modelo ajustado con
el archivo de 2024-2026 (calibracio/pluja_casa.json) y la temperatura, la
corrección ajustada con el último año de la estación de casa
(calibracio/temperatura_casa.json). Cada día, a la hora de la verificación, el reloj del
NAS ejecuta «diari»: vuelve a ajustar con todo lo registrado, lo compara con
lo que se usa ahora en semanas que no ha visto y, si mejora, lo propone. Un
cambio de método se avisa por Telegram y se aplica al día siguiente, salvo que
exista el archivo «atura»; un nuevo ajuste del mismo método se aplica directamente.

Uso:
  python3 aprenentatge.py diari     ajusta, compara y propone o aplica
  python3 aprenentatge.py estat     qué se usa ahora y con qué resultados
  python3 aprenentatge.py sortir    cómo van las reglas de cada medio de «Si surts» (también «moto»)
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import subprocess
import sys

import numpy as np

import config as C
import prevision as P
import remostreig as R
import sol_estacio

AQUI = os.path.dirname(os.path.abspath(__file__))
ARXIU = os.path.join(AQUI, "calibracio", "pluja_casa.json")
ARXIU_ECMWF = os.path.join(AQUI, "calibracio", "pluja_casa_ecmwf.json")
ARXIU_AVISOS = os.path.join(AQUI, "calibracio", "pluja_casa_avisos.json")
ARXIU_TEMPERATURA = os.path.join(AQUI, "calibracio", "temperatura_casa.json")
ARXIU_HUMITAT = os.path.join(AQUI, "calibracio", "humitat_casa.json")
REGISTRE = os.environ.get("REGISTRE_DIR", "/estat/registre")
DIR = os.environ.get("APRENENTATGE_DIR", "/estat/aprenentatge")
MODEL = os.path.join(DIR, "model.json")
PROPOSAT = os.path.join(DIR, "proposat.json")
ATURA = os.path.join(DIR, "atura")
HISTORIAL = os.path.join(DIR, "historial.csv")
HISTORIAL_HUMITAT = os.path.join(DIR, "historial-humitat.csv")

# Cuándo hay bastantes datos propios para que un método pueda sustituir al
# que se usa. Cuánto tiene que mejorar lo decide la regla común (remostreig:
# gana en el 95 % de los remuestreos por días; ADR 0105). Hasta la 3.144.0,
# un 5 % menos de error (MILLORA_MINIMA).
MIN_HORES_PLUJA = 30        # horas con lluvia medida en casa
MIN_DIES_TEMPERATURA = 14
MIN_DIES_HUMITAT = 14
SETMANES_VALIDACIO = 4      # grupos de semanas de la validación cruzada del archivo (calibracio/)
PERSISTENCIA_H = 4          # horas en que cuenta lo medido al prever (lluvia, sequedad)
# Cuánto dura el error de temperatura que tenía el modelo al prever: una
# parte se pierde en unas horas, otra en un día (ADR 0017).
ERROR_TEMP_H = (3, 24)

# Un modelo «da lluvia» desde su décima de milímetro: que ponga algo ya dice
# mucho más de lo que pesa su cantidad (ADR 0021).
MM_MODEL_PLOU = 0.1
RASGOS_ARXIU = ["constant", "arome_hd", "arome", "icon_eu", "antelacio",
                "hora_sin", "hora_cos", "dia_sin", "dia_cos",
                "plou_arome_hd", "plou_arome", "plou_icon_eu", "dos_models", "tres_models",
                "arome_hd_antelacio", "arome_antelacio", "icon_eu_antelacio",
                "algun_antelacio", "tres_antelacio"]
# ECMWF IFS a 9 km como un modelo más (ADR 0086): su lluvia, si la da, la
# antelación, si la dan los cuatro y si solo la da él. El modelo del archivo
# con ECMWF (pluja_casa_ecmwf.json) se usa si la pasada lo tiene; si no, el
# de siempre.
RASGOS_ECMWF = ["ecmwf", "plou_ecmwf", "ecmwf_antelacio", "quatre_models", "nomes_ecmwf"]
RASGOS_ARXIU_ECMWF = RASGOS_ARXIU + RASGOS_ECMWF
RASGOS_PROPIS = RASGOS_ARXIU + ["ensemble", "persistencia", "sequedat"]
# El del archivo con ECMWF y los avisos oficiales de cada hora (ADR 0097):
# solo se usa si su ajuste lo ha adoptado (pluja_casa_avisos.py).
RASGOS_ARXIU_ECMWF_AVISOS = RASGOS_ARXIU_ECMWF + ["avis_aemet"]
RASGOS_ARXIU_ECMWF_AVISOS_METEOCAT = RASGOS_ARXIU_ECMWF_AVISOS + ["avis_meteocat", "avis_meteocat_alt"]
# Con la lluvia de la última hora en Sant Cugat (Meteocat, a 4,6 km, en la
# cuenca de la riera): se ajusta aparte y solo gana si acierta más (ADR 0042).
RASGOS_PROPIS_XV = RASGOS_PROPIS + ["sant_cugat"]
# Con la lluvia de la última hora en las vecinas de Montflorit (Weather
# Underground, a menos de 1 km): la mediana de las que cuentan para «plou
# ara». Igual que la de Sant Cugat, aparte y solo si acierta más (ADR 0070).
RASGOS_PROPIS_VEINES = RASGOS_PROPIS + ["veines"]
AVIS_XV = os.path.join(DIR, "avis-sant-cugat")
# Con lo oficial de cada hora: aviso de AEMET por lluvia o tormentas y el
# INUNCAT en alerta o emergencia. Se registran desde el 08-10-2026; la variante
# se ajusta aparte y solo gana si acierta más (ADR 0047).
RASGOS_PROPIS_AVIS = RASGOS_PROPIS + ["avis_aemet", "pla_inuncat"]
# Sin la estación de casa (si falla al prever), la temperatura se corrige con
# los mismos rasgos menos el error al prever.
RASGOS_TEMPERATURA_SENSE_ESTACIO = ["constant", "temperatura", "nuvols", "humitat", "hora_sin",
                                    "hora_cos", "antelacio", "dia_sin", "dia_cos", "radiacio"]
RASGOS_TEMPERATURA = RASGOS_TEMPERATURA_SENSE_ESTACIO + ["error_ara_3h", "error_ara_24h"]
# El punto de rocío (ADR 0114): los mismos rasgos, con el rocío del modelo, y
# el error que tenía al prever con los mismos plazos que la temperatura.
RASGOS_ROSADA_SENSE_ESTACIO = ["constant", "rosada"] + RASGOS_TEMPERATURA_SENSE_ESTACIO[1:]
RASGOS_ROSADA = RASGOS_ROSADA_SENSE_ESTACIO + ["error_rosada_ara_3h", "error_rosada_ara_24h"]


# --- Rasgos ------------------------------------------------------------------------

def rasgos(d, noms):
    """Vector de rasgos de una hora. d lleva lo que se guarda en el registro:
    la lluvia de cada modelo (pluja_<modelo>), «fins» (hora local en que acaba
    el tramo), antelacio_h, prob_ens, temperature_2m… y lo que medía la
    estación al prever: pluja_1h_emes, error_temp_ara (temperatura del modelo
    menos la medida) y deficit_rosada_ara (temperatura menos punto de rocío).
    La hora y el día del año, los del sol (tiempo universal, ADR 0090): con la
    del reloj, el mes siguiente a cada cambio de hora iban desplazados."""
    fin = P.hora_universal(d["fins"])
    h = 2 * math.pi * fin.hour / 24
    dia = 2 * math.pi * fin.timetuple().tm_yday / 365.25
    pluja = {m: d.get(f"pluja_{m}") for m in C.MODELOS_FINOS}
    antelacio = max(d.get("antelacio_h", 0), 0)
    corto = d.get("antelacio_h", 99) <= PERSISTENCIA_H
    error_ara, deficit = d.get("error_temp_ara"), d.get("deficit_rosada_ara")
    error_rosada = d.get("error_rosada_ara")
    valors = {
        "constant": 1.0,
        "arome_hd": pluja["meteofrance_arome_france_hd"],
        "arome": pluja["meteofrance_arome_france"],
        "icon_eu": pluja["icon_eu"],
        # El archivo solo tiene el corto plazo (0) y la previsión de un día
        # antes (1): la antelación va en días, hasta 1.
        "antelacio": min(max(d.get("antelacio_h", 0), 0) / 24, 1.0),
        "hora_sin": math.sin(h), "hora_cos": math.cos(h),
        "dia_sin": math.sin(dia), "dia_cos": math.cos(dia),
        "ensemble": d.get("prob_ens"),
        "persistencia": math.log1p(d.get("pluja_1h_emes") or 0) if corto else 0.0,
        # Aire seco al prever, menos lluvia en las horas siguientes.
        "sequedat": (0.0 if not corto else None if deficit is None else min(max(deficit, 0), 15) / 10),
        # Lo que llovía en Sant Cugat al prever, como la persistencia; sin dato, no hay vector.
        "sant_cugat": (0.0 if not corto else None if d.get("pluja_1h_xv") is None else math.log1p(d["pluja_1h_xv"])),
        "veines": (0.0 if not corto else None if d.get("pluja_1h_veines") is None
                   else math.log1p(d["pluja_1h_veines"])),
        # Lo oficial de la hora (0 o 1); sin dato, no hay vector.
        "avis_aemet": d.get("avis_pluja"),
        "pla_inuncat": d.get("pla_inuncat"),
        "avis_meteocat": d.get("avis_meteocat"),
        "avis_meteocat_alt": d.get("avis_meteocat_alt"),
        "temperatura": d.get("temperature_2m"),
        "nuvols": None if d.get("cloud_cover") is None else d["cloud_cover"] / 100,
        "vent": None if d.get("wind_speed_10m") is None else d["wind_speed_10m"] / 10,
        "humitat": None if d.get("relative_humidity_2m") is None else d["relative_humidity_2m"] / 100,
        "radiacio": None if d.get("shortwave_radiation") is None else d["shortwave_radiation"] / 1000,
        "error_ara_3h": None if error_ara is None else error_ara * math.exp(-antelacio / ERROR_TEMP_H[0]),
        "error_ara_24h": None if error_ara is None else error_ara * math.exp(-antelacio / ERROR_TEMP_H[1]),
        "rosada": rosada_model(d),
        "error_rosada_ara_3h": None if error_rosada is None else error_rosada * math.exp(-antelacio / ERROR_TEMP_H[0]),
        "error_rosada_ara_24h": None if error_rosada is None else error_rosada * math.exp(-antelacio / ERROR_TEMP_H[1]),
    }
    # Si un modelo da lluvia, cuántos coinciden y cuánto vale todo eso según
    # la antelación: la lluvia prevista para dentro de un día se cumple menos.
    mm = [valors[m] for m in ("arome_hd", "arome", "icon_eu")]
    if None not in mm:
        plou = [float(v >= MM_MODEL_PLOU - 1e-9) for v in mm]
        ant = valors["antelacio"]
        for m, v, p in zip(("arome_hd", "arome", "icon_eu"), mm, plou):
            valors[m] = math.log1p(max(v, 0))
            valors[f"plou_{m}"] = p
            valors[f"{m}_antelacio"] = valors[m] * ant
        valors["dos_models"] = float(sum(plou) >= 2)
        valors["tres_models"] = float(sum(plou) == 3)
        valors["algun_antelacio"] = float(sum(plou) >= 1) * ant
        valors["tres_antelacio"] = valors["tres_models"] * ant
        ec = d.get(f"pluja_{C.MODEL_ECMWF}")
        if ec is not None:
            p_ec = float(ec >= MM_MODEL_PLOU - 1e-9)
            valors["ecmwf"] = math.log1p(max(ec, 0))
            valors["plou_ecmwf"] = p_ec
            valors["ecmwf_antelacio"] = valors["ecmwf"] * ant
            valors["quatre_models"] = float(p_ec and sum(plou) == 3)
            valors["nomes_ecmwf"] = float(p_ec and sum(plou) == 0)
    x = [valors.get(n) for n in noms]
    return None if any(v is None for v in x) else x


# --- Regresiones ---------------------------------------------------------------------

def ajustar(x, y, l2=1.0, iteraciones=50):
    """Regresión logística por Newton-Raphson con regularización L2 (sin
    penalizar la constante)."""
    w = np.zeros(x.shape[1])
    pen = np.full(x.shape[1], l2)
    pen[0] = 0
    for _ in range(iteraciones):
        p = 1 / (1 + np.exp(-x @ w))
        g = x.T @ (p - y) + pen * w
        h = x.T @ (x * (p * (1 - p))[:, None]) + np.diag(pen)
        paso = np.linalg.solve(h, g)
        w -= paso
        if np.abs(paso).max() < 1e-8:
            break
    return w


def predecir(w, x):
    return 1 / (1 + np.exp(-x @ w))


def ajustar_ridge(x, y, l2=1.0):
    """Regresión lineal con regularización L2 (sin penalizar la constante)."""
    pen = np.full(x.shape[1], l2)
    pen[0] = 0
    return np.linalg.solve(x.T @ x + np.diag(pen), x.T @ y)


# --- Modelo en uso --------------------------------------------------------------------

def modelo_arxiu():
    with open(ARXIU, encoding="utf-8") as f:
        return json.load(f)


def modelo_arxiu_ecmwf():
    try:
        with open(ARXIU_ECMWF, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def modelo_arxiu_avisos():
    """El del archivo con los avisos, solo si su validación lo adoptó."""
    try:
        with open(ARXIU_AVISOS, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return None
    return m if m.get("adoptat") else None


def modelo_arxiu_temperatura():
    with open(ARXIU_TEMPERATURA, encoding="utf-8") as f:
        m = json.load(f)
    return {k: v for k, v in m.items() if k != "pluja"}


def modelo_arxiu_humitat():
    """La corrección del rocío ajustada con el año de la estación de casa
    (calibracio/humitat_casa.py), solo si ganó al modelo sin corregir."""
    with open(ARXIU_HUMITAT, encoding="utf-8") as f:
        m = json.load(f)
    return m if m.get("adoptat") else None


def carrega():
    """El modelo en uso: el aprendido en el NAS si lo hay; lo que falte, el
    del archivo (lluvia de 2024-2026, temperatura del último año en casa)."""
    model = {"pluja": None, "temperatura": None, "humitat": None}
    try:
        with open(MODEL, encoding="utf-8") as f:
            model.update(json.load(f))
    except (OSError, ValueError):
        pass
    for clave, carga in (("pluja", modelo_arxiu), ("temperatura", modelo_arxiu_temperatura),
                         ("humitat", modelo_arxiu_humitat)):
        if not model.get(clave):
            try:
                model[clave] = carga()
            except (OSError, ValueError):
                pass
    return model


def variants_arxiu():
    """Las variantes del archivo que la web usa antes que el de tres modelos,
    por orden: la de los avisos si está adoptada (ADR 0097) y la de ECMWF
    (ADR 0086). Leídas una vez cuando hay que predecir muchas horas."""
    return [m for m in (modelo_arxiu_avisos(), modelo_arxiu_ecmwf()) if m]


def prob_pluja(model, d, variants=None):
    """Probabilidad de lluvia. Con el modelo del archivo, el que lleva los
    avisos oficiales si está adoptado y la pasada los tiene (ADR 0097); si
    no, el que lleva ECMWF si la pasada lo tiene (ADR 0086). Si el modelo
    propio necesita la estación de casa y no hay dato, la del archivo."""
    m = (model or {}).get("pluja")
    if m and m.get("origen") == "arxiu":
        for me in variants_arxiu() if variants is None else variants:
            xe = rasgos(d, me["rasgos"])
            if xe is not None:
                return float(predecir(np.array(me["w"]), np.array(xe)))
    x = rasgos(d, m["rasgos"]) if m else None
    if x is None and m and m.get("origen") != "arxiu":
        m = modelo_arxiu()
        x = rasgos(d, m["rasgos"])
    return None if x is None else float(predecir(np.array(m["w"]), np.array(x)))


def temperatura(model, d):
    """Temperatura corregida; sin la estación al prever, con los pesos que no
    la necesitan; sin modelo, la del modelo meteorológico."""
    m = (model or {}).get("temperatura")
    if not m or d.get("temperature_2m") is None:
        return d.get("temperature_2m")
    for sufijo in ("", "_sense_estacio"):
        if m.get(f"rasgos{sufijo}"):
            x = rasgos(d, m[f"rasgos{sufijo}"])
            if x is not None:
                return d["temperature_2m"] - float(np.array(m[f"w{sufijo}"]) @ np.array(x))
    return d["temperature_2m"]


def rosada_model(d):
    """El punto de rocío del modelo (°C), con su temperatura y su humedad."""
    t, hr = d.get("temperature_2m"), d.get("relative_humidity_2m")
    return None if t is None or hr is None else sol_estacio.rosada(t, hr)


def rosada(model, d):
    """Punto de rocío corregido (ADR 0114); sin la estación al prever, con los
    pesos que no la necesitan; sin corrección adoptada, el del modelo."""
    r = rosada_model(d)
    m = (model or {}).get("humitat")
    if not m or r is None:
        return r
    for sufijo in ("", "_sense_estacio"):
        if m.get(f"rasgos{sufijo}"):
            x = rasgos(d, m[f"rasgos{sufijo}"])
            if x is not None:
                return r - float(np.array(m[f"w{sufijo}"]) @ np.array(x))
    return r


def resum_pagina(model):
    """Lo que dice la página sobre cómo se calcula."""
    p, t = (model or {}).get("pluja"), (model or {}).get("temperatura")
    h = (model or {}).get("humitat")
    return {"pluja": p and {"origen": p["origen"], "des_de": p["des_de"]},
            "temperatura": t and {"origen": t["origen"], "des_de": t["des_de"]},
            "humitat": h and {"origen": h["origen"], "des_de": h["des_de"]}}


# --- Datos propios ----------------------------------------------------------------------

def _llegeix(nom):
    ruta = os.path.join(REGISTRE, nom)
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return {r["fins"]: r for r in csv.DictReader(f)}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pluja_observada(casa, meteocat=(), veines=None, llindar=None):
    """mm de la hora en Montflorit, con lo de Montflorit primero (Juanjo,
    10-10-2026: «si está lloviendo en 2 estaciones de montflorit eso no puede
    ser una hora seca, a lo mejor sí lo es en sant cugat o sabadell»; ADR 0070).
    Es la única verdad de la lluvia del barrio (ADR 0102): la misma regla
    sirve para la hora (el aprendizaje y el historial), para los 5 minutos
    (el final de la lluvia, fi_pluja.py, con llindar más bajo) y, con los
    últimos minutos, para «ahora» (plou_ara_barri).
    - Llueve si la estación de casa lo marca, o si lo marcan al menos
      C.VEINES_PLUJA_MIN vecinas de las que cuentan para la lluvia (`plou`):
      el pluviómetro de casa a veces no recoge la lluvia débil (ADR 0017).
    - Seca si casa marca cero, ninguna vecina que cuenta ve lluvia y las que
      confirman horas secas (`sec`) están a cero, con una al menos.
    - Sin ninguna vecina que confirme, como antes: el cero de casa vale si
      tampoco recogieron nada las estaciones de Meteocat (meteocat).
    - Si solo una vecina ve lluvia y casa no, no se sabe.
    veines: {id: lo medido en la hora}; meteocat: lo de cada estación;
    llindar: desde cuántos mm cuenta como lluvia (C.UMBRAL_MM)."""
    llindar = C.UMBRAL_MM if llindar is None else llindar
    c = _num((casa or {}).get("pluja_mm"))
    v = {k: _num((x or {}).get("pluja_mm")) for k, x in (veines or {}).items()}
    plou = [x for k, x in v.items() if C.VEINES.get(k, {}).get("plou") and x is not None]
    mullen = [x for x in plou if x >= llindar]
    if c is not None and c >= llindar:
        return c
    if len(mullen) >= C.VEINES_PLUJA_MIN:
        return sorted(mullen)[len(mullen) // 2]
    if c is None or mullen:
        return None
    sec = [x for k, x in v.items() if C.VEINES.get(k, {}).get("sec") and x is not None]
    if sec:
        return 0.0 if all(x < llindar for x in sec) else None
    prop = [_num((m or {}).get("pluja_mm")) for m in meteocat]
    prop = [x for x in prop if x is not None]
    return 0.0 if prop and all(x < llindar for x in prop) else None


def pluja_dubtosa(veines=None, llindar=None):
    """Cuando pluja_observada no lo sabe porque solo una vecina de las que
    cuentan ve lluvia (y no llegan a C.VEINES_PLUJA_MIN): sus mm, para que el
    historial diga que quizá lloviznó y no solo «no se sabe» (Juanjo,
    24-10-2026: «por que pone que de 2 hores no se sap?»). None si ninguna
    vecina ve lluvia: entonces lo que falta son datos."""
    llindar = C.UMBRAL_MM if llindar is None else llindar
    mullen = [_num((x or {}).get("pluja_mm")) for k, x in (veines or {}).items() if C.VEINES.get(k, {}).get("plou")]
    mullen = [x for x in mullen if x is not None and x >= llindar]
    return max(mullen) if mullen else None


def plou_ara_barri(casa, veines, plugim=False):
    """Si llueve ahora en Montflorit, para comprobar lo que decía el radar
    (radar_fonts.py; ADR 0102): True, False o None si no se sabe. La regla de
    pluja_observada con la lluvia de los últimos C.PLOU_ARA_MIN minutos de
    casa (ecowitt.resum_ara) y de las vecinas (wunderground.veina_ara): llueve
    si lo marca casa o dos vecinas que cuentan; seco si casa marca cero y las
    vecinas que confirman también; si no, no se sabe. Un cero dudoso tampoco
    vale: con «plugim segons el radar» (los dos radares ven ecos débiles sobre
    el barrio y ninguna estación mide nada, casa.plugim_radar) la pasada no
    cuenta, porque el pluviómetro no recoge la llovizna."""
    if plugim:
        return None
    c = None if not casa or casa.get("plou") is None else {"pluja_mm": 1.0 if casa["plou"] else 0.0}
    v = {x["estacio"]: {"pluja_mm": x.get("pluja_15min")} for x in veines or [] if x.get("pluja_15min") is not None}
    mm = pluja_observada(c, (), v, llindar=0.1)
    return None if mm is None else mm > 0


def pluja_veines(veines):
    """La mediana de la lluvia de la última hora de las vecinas que cuentan
    para «plou ara» ({id: mm}); None sin ninguna (ADR 0070)."""
    vals = sorted(v for k, v in (veines or {}).items() if C.VEINES.get(k, {}).get("plou") and v is not None)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _meteocat():
    """Lo medido por horas en cada estación de Meteocat del registro: el
    respaldo para las horas secas cuando no hay vecinas (ADR 0058 y 0070)."""
    return [_llegeix(f"meteocat-{codi}.csv") for codi in C.ESTACIONES]


def _veines():
    """Lo medido por horas en cada vecina de Montflorit ({id: {fins: fila}}, ADR 0060)."""
    return {estacio: _llegeix(f"veina-{estacio}.csv") for estacio in C.VEINES}


def observada(casa, meteocat, veines, fins):
    """pluja_observada de la hora que acaba en fins, con los registros leídos."""
    return pluja_observada(casa.get(fins), [m.get(fins) for m in meteocat],
                           {k: v.get(fins) for k, v in veines.items()})


def dubtosa(veines, fins):
    """pluja_dubtosa de la hora que acaba en fins, con los registros leídos."""
    return pluja_dubtosa({k: v.get(fins) for k, v in veines.items()})


def mostres():
    """Una muestra por hora prevista y pasada de cada previsión registrada, con
    lo que pasó: la lluvia y la temperatura de casa (ADR 0017), con las
    estaciones de Meteocat y la vecina fiable para confirmar las horas secas
    (ADR 0058 y 0060)."""
    casa, meteocat, veines = _llegeix("estacio-casa.csv"), _meteocat(), _veines()
    # Sin la temperatura de las horas con sol directo sobre el termómetro (ADR 0081).
    amb_sol = sol_estacio.hores_tocades(casa)
    res = []
    for arxiu in sorted(glob.glob(os.path.join(REGISTRE, "casa-*.jsonl"))):
        with open(arxiu, encoding="utf-8") as f:
            for linea in map(json.loads, f):
                ara_casa = linea.get("ara_casa") or {}
                plujas = [x for x in (ara_casa.get("pluja_1h"),) if x is not None]
                for h in linea["hores"]:
                    obs_pluja = observada(casa, meteocat, veines, h["fins"])
                    obs_temp = None if h["fins"] in amb_sol else _num((casa.get(h["fins"]) or {}).get("temperatura"))
                    obs_rosada = rosada_observada(casa, veines, h["fins"])
                    if obs_pluja is None and obs_temp is None and obs_rosada is None:
                        continue
                    res.append({**h, "emes": linea["emes"], "pluja_1h_emes": max(plujas) if plujas else None,
                                "pluja_1h_xv": (linea.get("sant_cugat") or {}).get("pluja_1h"),
                                "pluja_1h_veines": pluja_veines(linea.get("veines")),
                                "obs_pluja": obs_pluja, "obs_temp": obs_temp, "obs_rosada": obs_rosada})
    return res


def rosada_observada(casa, veines, fins):
    """El rocío del barrio en la hora que acaba en fins: la mediana de casa y
    las vecinas, como el recuadro «Ara» (ADR 0114). El sol sobre el
    termómetro no lo toca: el rocío sale del agua del aire."""
    valors = [_num((r.get(fins) or {}).get("rosada")) for r in [casa, *veines.values()]]
    valors = sorted(v for v in valors if v is not None)
    if not valors:
        return None
    n = len(valors)
    return valors[n // 2] if n % 2 else (valors[n // 2 - 1] + valors[n // 2]) / 2


def valida_pluja(ms, arxiu, noms=RASGOS_PROPIS):
    """Error (Brier) del modelo propio (con los rasgos noms) con avance
    temporal (remostreig.avanc, ADR 0106: cada día se predice con el modelo
    ajustado con los días anteriores, y un episodio de lluvia que cruza la
    medianoche no entra en el ajuste del día que lo evalúa) y, con las mismas
    muestras evaluadas, del archivo tal como lo publica la web (prob_pluja:
    con los avisos o con ECMWF cuando la pasada los tiene; ADR 0104). Hasta
    la 3.145.1 la validación era cruzada en cuatro grupos de semanas, que
    podía ajustar con semanas posteriores a la evaluada; hasta la 3.143.0 el
    competidor eran los coeficientes de tres modelos solos (evaluación de los
    métodos del 18-10-2026). None sin días bastantes para evaluar ninguno."""
    ms = [m for m in ms if m["obs_pluja"] is not None and rasgos(m, noms) is not None]
    if not ms:
        return None
    x = np.array([rasgos(m, noms) for m in ms])
    y = np.array([m["obs_pluja"] >= C.UMBRAL_MM for m in ms], dtype=float)
    variants = variants_arxiu()
    p_abans = np.array([prob_pluja({"pluja": arxiu}, m, variants) for m in ms])
    fins = [m["fins"] for m in ms]
    dies = np.array([f[:10] for f in fins])
    p = np.full(len(y), np.nan)
    for ent, aval in R.avanc(dies, R.episodis(fins, y > 0)):
        p[aval] = y[ent].mean() if y[ent].sum() == 0 else predecir(ajustar(x[ent], y[ent]), x[aval])
    s = ~np.isnan(p)
    if not s.any():
        return None
    # Horas observadas distintas con lluvia: cada hora se prevé muchas veces y
    # no cuenta más por eso (auditoría del 08-10-2026).
    hores_pluja = len({f for f, plou in zip(fins, y) if plou})
    return {"mostres": len(y), "hores_pluja": hores_pluja, "rasgos": noms,
            "avaluades": int(s.sum()), "dies_avaluats": len(set(dies[s])),
            "hores_pluja_avaluades": len({f for f, plou, e in zip(fins, y, s) if plou and e}),
            "error": float(np.mean((p[s] - y[s]) ** 2)),
            "error_abans": float(np.mean((p_abans[s] - y[s]) ** 2)),
            # Con qué seguridad gana al que publica la web: remuestreos por
            # días de la hora observada (ADR 0105).
            "seguretat": R.seguretat((p[s] - y[s]) ** 2, (p_abans[s] - y[s]) ** 2, dies[s]),
            "_errors": ((p[s] - y[s]) ** 2).tolist(), "_dies": dies[s].tolist(),
            "w": ajustar(x, y).tolist() if y.sum() else None}


def sense_avaluar(ms, dies):
    """Els primers dies, abans que l'avanç temporal (remostreig.avanc) en
    pugui avaluar cap (calen MIN_DIES_ENTRENAMENT d'entrenament): els dies i
    les mostres que ja hi ha, sense error ni pesos. Fins a la 3.192.3 no en
    tornava res i «Fiabilitat» deia «en porta 0» de la humitat amb tres dies
    de dades (Juanjo, 23-10-2026: «por qué la humedad no tiene ningún día?»)."""
    return {"mostres": len(ms), "dies": dies, "avaluades": 0, "dies_avaluats": 0, "error": None,
            "error_abans": None, "seguretat": None, "error_humitat": None, "error_humitat_abans": None,
            "w": None, "w_sense_estacio": None}


def valida_temperatura(ms, arxiu_t):
    """Error medio absoluto con avance temporal (remostreig.avanc, ADR 0106):
    la corrección ajustada con el registro propio de los días anteriores
    frente a la del archivo (o, sin ella, la temperatura sin corregir), con
    las mismas horas evaluadas."""
    ms = [m for m in ms if m["obs_temp"] is not None and rasgos(m, RASGOS_TEMPERATURA) is not None]
    if not ms:
        return None
    x = np.array([rasgos(m, RASGOS_TEMPERATURA) for m in ms])
    modelo = np.array([m["temperature_2m"] for m in ms])
    obs = np.array([m["obs_temp"] for m in ms])
    error = modelo - obs
    dia = np.array([m["fins"][:10] for m in ms])
    pred = np.full(len(error), np.nan)
    for ent, aval in R.avanc(dia):             # avance temporal (ADR 0106)
        pred[aval] = x[aval] @ ajustar_ridge(x[ent], error[ent])
    s = ~np.isnan(pred)
    dies = len({m["emes"][:10] for m in ms})
    if not s.any():
        return sense_avaluar(ms, dies)
    abans = np.array([temperatura({"temperatura": arxiu_t}, m) for m in ms])
    xs = np.array([rasgos(m, RASGOS_TEMPERATURA_SENSE_ESTACIO) for m in ms])
    return {"mostres": len(ms), "dies": dies, "avaluades": int(s.sum()), "dies_avaluats": len(set(dia[s])),
            "error": float(np.mean(np.abs(error[s] - pred[s]))),
            "error_abans": float(np.mean(np.abs(abans[s] - obs[s]))),
            "seguretat": R.seguretat(np.abs(error[s] - pred[s]), np.abs(abans[s] - obs[s]), dia[s]),
            "w": ajustar_ridge(x, error).tolist(), "w_sense_estacio": ajustar_ridge(xs, error).tolist()}


def valida_humitat(ms, arxiu_h):
    """Como valida_temperatura, para el rocío (ADR 0114): la corrección
    ajustada con el registro propio de los días anteriores frente a la del
    archivo (o, sin ella, el rocío del modelo), con las mismas horas."""
    ms = [m for m in ms if m.get("obs_rosada") is not None and rasgos(m, RASGOS_ROSADA) is not None]
    if not ms:
        return None
    x = np.array([rasgos(m, RASGOS_ROSADA) for m in ms])
    obs = np.array([m["obs_rosada"] for m in ms])
    error = np.array([rosada_model(m) for m in ms]) - obs
    dia = np.array([m["fins"][:10] for m in ms])
    pred = np.full(len(error), np.nan)
    for ent, aval in R.avanc(dia):
        pred[aval] = x[aval] @ ajustar_ridge(x[ent], error[ent])
    s = ~np.isnan(pred)
    dies = len({m["emes"][:10] for m in ms})
    if not s.any():
        return sense_avaluar(ms, dies)
    abans = np.array([rosada({"humitat": arxiu_h}, m) for m in ms])
    xs = np.array([rasgos(m, RASGOS_ROSADA_SENSE_ESTACIO) for m in ms])
    # Y en puntos de humedad, lo que ve quien mira la gráfica («Fiabilitat»):
    # cada rocío con la temperatura medida en casa a esa hora.
    t = np.array([np.nan if m.get("obs_temp") is None else m["obs_temp"] for m in ms])
    ok = s & ~np.isnan(t)

    def hum(r):
        return np.array([sol_estacio.humitat(min(a, b), b) for a, b in zip(r[ok], t[ok])])
    h_obs = hum(obs)
    return {"mostres": len(ms), "dies": dies, "avaluades": int(s.sum()), "dies_avaluats": len(set(dia[s])),
            "error_humitat": float(np.mean(np.abs(hum(obs + error - pred) - h_obs))) if ok.any() else None,
            "error_humitat_abans": float(np.mean(np.abs(hum(abans) - h_obs))) if ok.any() else None,
            "error": float(np.mean(np.abs(error[s] - pred[s]))),
            "error_abans": float(np.mean(np.abs(abans[s] - obs[s]))),
            "seguretat": R.seguretat(np.abs(error[s] - pred[s]), np.abs(abans[s] - obs[s]), dia[s]),
            "w": ajustar_ridge(x, error).tolist(), "w_sense_estacio": ajustar_ridge(xs, error).tolist()}


def valida_variant(ms, arxiu, noms):
    """Una variante (Sant Cugat, los avisos), solo con las muestras que llevan
    su dato, y el modelo base ajustado y comprobado con esas mismas muestras
    (error_base): un error medido en horas distintas no se puede comparar.
    Hasta la auditoría del 09-10-2026 la variante se elegía por tener menos
    error que el base, aunque el suyo saliera de la mitad de las horas."""
    sub = [m for m in ms if m["obs_pluja"] is not None and rasgos(m, noms) is not None]
    v = valida_pluja(sub, arxiu, noms)
    if v:
        base = valida_pluja(sub, arxiu)
        v["error_base"] = base["error"] if base else None
        v["mostres_base"] = base["mostres"] if base else None
        v["seguretat_base"] = R.seguretat(v["_errors"], base["_errors"], v["_dies"]) if base else None
    return v


# --- Decisión diaria -------------------------------------------------------------------

def millora(v, clau="seguretat"):
    """Si el candidato gana con seguridad al que se usa: en al menos el 95 %
    de los remuestreos por días (remostreig, ADR 0105)."""
    return R.guanya(v.get(clau))


def candidat(ms, arxiu, arxiu_t, avui, arxiu_h=None):
    """El modelo que tocaría usar con los datos de hoy, y los números (los
    del rocío, en model["_vh"], que no se guarda)."""
    vp, vt = valida_pluja(ms, arxiu), valida_temperatura(ms, arxiu_t)
    vh = valida_humitat(ms, arxiu_h)
    # Las variantes con Sant Cugat y con los avisos, aparte: solo con las
    # muestras que llevan el dato, y el base con esas mismas (valida_variant).
    if vp:
        vp["xv"] = valida_variant(ms, arxiu, RASGOS_PROPIS_XV)
        vp["avis"] = valida_variant(ms, arxiu, RASGOS_PROPIS_AVIS)
        vp["veines"] = valida_variant(ms, arxiu, RASGOS_PROPIS_VEINES)
    model = {"pluja": arxiu, "temperatura": arxiu_t, "humitat": arxiu_h, "_vh": vh}

    def val(v):
        return bool(v and v["hores_pluja"] >= MIN_HORES_PLUJA and v["w"] and millora(v))
    # Una variante, solo si en sus mismas horas gana también al base con la
    # misma seguridad; entre varias, la que más lo mejora en proporción. Si
    # ninguna, el base, si gana al archivo.
    variants = [v for v in ((vp or {}).get("xv"), (vp or {}).get("avis"), (vp or {}).get("veines"))
                if val(v) and v.get("error_base") and millora(v, "seguretat_base")]
    v = max(variants, key=lambda v: 1 - v["error"] / v["error_base"]) if variants else vp if val(vp) else None
    if v:
        model["pluja"] = {"origen": "local", "des_de": ms[0]["emes"][:10], "fins": avui,
                          "rasgos": v["rasgos"], "w": v["w"], "error": v["error"],
                          "error_abans": v["error_abans"], "mostres": v["mostres"],
                          "error_base": v.get("error_base"), "seguretat": v.get("seguretat"),
                          "seguretat_base": v.get("seguretat_base")}
    if vt and vt["dies"] >= MIN_DIES_TEMPERATURA and millora(vt):
        model["temperatura"] = {"origen": "casa", "des_de": ms[0]["emes"][:10], "fins": avui,
                                "rasgos": RASGOS_TEMPERATURA, "w": vt["w"],
                                "rasgos_sense_estacio": RASGOS_TEMPERATURA_SENSE_ESTACIO,
                                "w_sense_estacio": vt["w_sense_estacio"], "error": vt["error"],
                                "error_abans": vt["error_abans"], "mostres": vt["mostres"],
                                "seguretat": vt.get("seguretat")}
    if vh and vh["dies"] >= MIN_DIES_HUMITAT and millora(vh):
        model["humitat"] = {"origen": "barri", "des_de": ms[0]["emes"][:10], "fins": avui,
                            "rasgos": RASGOS_ROSADA, "w": vh["w"],
                            "rasgos_sense_estacio": RASGOS_ROSADA_SENSE_ESTACIO,
                            "w_sense_estacio": vh["w_sense_estacio"], "error": vh["error"],
                            "error_abans": vh["error_abans"], "mostres": vh["mostres"],
                            "seguretat": vh.get("seguretat")}
    return model, vp, vt


def metode(model):
    p, t = model.get("pluja"), model.get("temperatura")
    return ((p or {}).get("origen"), (t or {}).get("origen"))


def metode_humitat(model):
    return ((model or {}).get("humitat") or {}).get("origen")


def explica(abans, nou, vp, vt):
    """Mensaje de Telegram: qué cambia y con qué números."""
    linies = ["Temps a casa: canvi de mètode d'aprenentatge, s'aplicarà demà."]
    if metode(abans)[0] != metode(nou)[0]:
        if nou["pluja"]["origen"] != "arxiu":
            p = nou["pluja"]
            amb_xv = (" i la pluja de Sant Cugat" if "sant_cugat" in p["rasgos"]
                      else " i la pluja de les estacions veïnes" if "veines" in p["rasgos"]
                      else " i els avisos oficials" if "avis_aemet" in p["rasgos"] else "")
            linies.append(f"Pluja: passa a aprendre de l'estació de casa{amb_xv} "
                          f"({p['mostres']} mostres). "
                          f"Error {p['error']:.4f} en setmanes no vistes, abans {p['error_abans']:.4f}"
                          + (f" (guanya en el {round(100 * p['seguretat'])} % dels remostrejos per dies)."
                             if p.get("seguretat") is not None else ".")
                          + (f" Sense aquest rasgo, a les mateixes hores: {p['error_base']:.4f}."
                             if p.get("error_base") else ""))
        else:
            linies.append("Pluja: torna al model de l'arxiu; el propi ja no millora.")
    if metode(abans)[1] != metode(nou)[1]:
        if nou["temperatura"] and nou["temperatura"]["origen"] != "arxiu":
            linies.append(f"Temperatura: es corregeix amb el registre propi ({vt['dies']} dies). "
                          f"Error mitjà {vt['error']:.2f} °C, amb la correcció de l'arxiu {vt['error_abans']:.2f} °C"
                          + (f" (guanya en el {round(100 * vt['seguretat'])} % dels remostrejos per dies)."
                             if vt.get("seguretat") is not None else "."))
        else:
            linies.append("Temperatura: torna a la correcció de l'arxiu; la del registre propi ja no millora.")
    if metode_humitat(abans) != metode_humitat(nou):
        vh = nou.get("_vh") or {}
        if metode_humitat(nou) == "barri":
            linies.append(f"Humitat: el rosada es corregeix amb el registre del barri ({vh['dies']} dies). "
                          f"Error mitjà {vh['error']:.2f} °C, abans {vh['error_abans']:.2f} °C"
                          + (f" (guanya en el {round(100 * vh['seguretat'])} % dels remostrejos per dies)."
                             if vh.get("seguretat") is not None else "."))
        else:
            linies.append("Humitat: torna a la correcció de l'arxiu; la del registre del barri ja no millora.")
    linies.append("Per aturar-ho, demana-ho a Claude abans de demà.")
    return "\n".join(linies)


def per_desar(model):
    """Lo que se guarda en el NAS: solo los modelos propios. Los del archivo
    se leen siempre del repositorio, para que un ajuste nuevo llegue solo."""
    return {k: (v if v and v.get("origen") != "arxiu" else None) for k, v in model.items() if not k.startswith("_")}


def guarda(ruta, dades):
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dades, f, ensure_ascii=False, indent=1)
    os.replace(ruta + ".tmp", ruta)


def apunta_historial(avui, model, vp, vt):
    nou = not os.path.exists(HISTORIAL)
    with open(HISTORIAL, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nou:
            w.writerow(["dia", "pluja", "temperatura", "mostres_pluja", "hores_pluja", "error_pluja",
                        "error_pluja_arxiu", "dies_temperatura", "error_temp", "error_temp_model",
                        "hores_pluja_sant_cugat", "error_pluja_sant_cugat",
                        "hores_pluja_avisos", "error_pluja_avisos"])
        xv, av = (vp or {}).get("xv"), (vp or {}).get("avis")
        r = lambda v, n: None if v is None else round(v, n)
        w.writerow([avui, *metode(model),
                    vp and vp["mostres"], vp and vp["hores_pluja"], vp and round(vp["error"], 5),
                    vp and round(vp["error_abans"], 5), vt and vt["dies"],
                    vt and r(vt["error"], 2), vt and r(vt["error_abans"], 2),
                    xv and xv["hores_pluja"], xv and round(xv["error"], 5),
                    av and av["hores_pluja"], av and round(av["error"], 5)])


def apunta_historial_humitat(avui, model):
    """El rocío, en un archivo aparte (ADR 0114): historial.csv ya tenía sus
    columnas cuando llegó."""
    vh = model.get("_vh")
    nou = not os.path.exists(HISTORIAL_HUMITAT)
    with open(HISTORIAL_HUMITAT, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nou:
            w.writerow(["dia", "humitat", "dies", "mostres", "error_rosada", "error_rosada_abans", "seguretat",
                        "error_humitat", "error_humitat_abans"])
        r = lambda v, n: None if v is None else round(v, n)
        w.writerow([avui, metode_humitat(model), vh and vh["dies"], vh and vh["mostres"],
                    vh and r(vh["error"], 3), vh and r(vh["error_abans"], 3), vh and vh.get("seguretat"),
                    vh and r(vh["error_humitat"], 2), vh and r(vh["error_humitat_abans"], 2)])


def diari(avui=None, avisa=True):
    avui = avui or dt.date.today().isoformat()
    os.makedirs(DIR, exist_ok=True)
    # Qué radar acierta más en casa (radar_fonts.py, ADR 0026).
    try:
        import radar_fonts
        radar_fonts.verifica(dt.date.fromisoformat(avui), avisa)
    except Exception as ex:
        print("No he pogut comparar els radars:", ex)
    # Qué mezcla de modelos acierta más el cielo, con lo observado en el
    # aeropuerto de Sabadell (nuvols.py, ADR 0088).
    try:
        import nuvols
        nuvols.verifica(dt.date.fromisoformat(avui), avisa)
    except Exception as ex:
        print("No he pogut comparar els núvols:", ex)
    # A qué hora para la lluvia, según el radar: con 5 episodios, el resultado
    # a Juanjo, una vez (ADR 0049).
    try:
        import fi_pluja
        text_fi = fi_pluja.verifica(avisa)
        if text_fi:
            print(text_fi)
    except Exception as ex:
        print("No he pogut comprovar el final de la pluja:", ex)
    # Que la página de Meteocat sigue trayendo sus avisos de peligro (ADR 0067).
    try:
        import prevision as P
        import smp
        smp.comprova(P.get, os.path.join(DIR, "smp-falla"), avisa)
    except Exception as ex:
        print("No he pogut comprovar els avisos de Meteocat:", ex)
    # El mapa de talls de llum d'e-distribució, que no és una API documentada (ADR 0072).
    try:
        import llum
        llum.comprova(os.path.join(DIR, "llum-falla"), avisa)
    except Exception as ex:
        print("No he pogut comprovar el mapa de talls de llum:", ex)
    # La API de avisos de Rodalies, que tampoco es un servicio documentado (ADR 0078).
    try:
        import trens
        trens.comprova(os.path.join(DIR, "rodalies-falla"), avisa)
    except Exception as ex:
        print("No he pogut comprovar l'API d'avisos de Rodalies:", ex)
    # Qué dijo «Si surts» de cada medio y qué pasó (ADR 0047 y 0068).
    try:
        print("Si surts: hores noves verificades:", verifica_sortir())
        text_sortir = avis_sortir(avisa)
        if text_sortir:
            print(text_sortir)
        text_llindars = aprén_sortir(avui, avisa)
        if text_llindars:
            print(text_llindars)
    except Exception as ex:
        print("No he pogut verificar Si surts:", ex)
    # El viento con las vecinas: factores, comprobación y, una vez, el
    # resultado a Juanjo para que decida (ADR 0064).
    try:
        import vent_veines
        vent_veines.apren(avisa=avisa, registre=REGISTRE, directori=DIR)
    except Exception as ex:
        print("No he pogut aprendre el vent de les veïnes:", ex)
    arxiu, arxiu_t = modelo_arxiu(), modelo_arxiu_temperatura()
    try:
        arxiu_h = modelo_arxiu_humitat()
    except (OSError, ValueError):
        arxiu_h = None
    en_us = carrega()
    # 1. Una propuesta de ayer que nadie ha parado: se aplica.
    if os.path.exists(PROPOSAT):
        with open(PROPOSAT, encoding="utf-8") as f:
            proposat = json.load(f)
        if os.path.exists(ATURA):
            print("Proposta aturada: no s'aplica.")
            os.remove(PROPOSAT)
        elif proposat["dia"] < avui:
            guarda(MODEL, per_desar(proposat["model"]))
            en_us = carrega()
            os.remove(PROPOSAT)
            print("Aplicada la proposta d'ahir:", metode(en_us))
    # 2. Lo que tocaría hoy.
    nou, vp, vt = candidat(mostres(), arxiu, arxiu_t, avui, arxiu_h)
    apunta_historial(avui, nou, vp, vt)
    apunta_historial_humitat(avui, nou)
    # Una sola vez: cuando haya bastante lluvia con el dato de Sant Cugat, el
    # resultado medido, para decidir si se pide la clave de AEMET (ADR 0042).
    text_xv = avis_sant_cugat(vp)
    if text_xv:
        print(text_xv)
        if avisa:
            subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", text_xv], check=False)
    if metode(nou) == metode(en_us) and metode_humitat(nou) == metode_humitat(en_us):
        # Mismo método, más datos: se pone al día sin avisar.
        if per_desar(nou) != per_desar(en_us) and not os.path.exists(ATURA):
            guarda(MODEL, per_desar(nou))
        print("Mateix mètode:", metode(nou), metode_humitat(nou))
        return
    if os.path.exists(ATURA):
        print("Canvi de mètode aturat (existeix «atura»).")
        return
    guarda(PROPOSAT, {"dia": avui, "model": per_desar(nou)})
    text = explica(en_us, nou, vp, vt)
    print(text)
    if avisa:
        subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", text], check=False)


def avis_sant_cugat(vp):
    """El día en que el registro tiene MIN_HORES_PLUJA horas de lluvia con la
    lluvia de Sant Cugat, una vez: si ese rasgo acierta más o no, con las
    cifras (Juanjo, 08-10-2026: «¿quién se acordará de mirarlo?»)."""
    xv = (vp or {}).get("xv")
    if not xv or xv["hores_pluja"] < MIN_HORES_PLUJA or xv.get("error_base") is None or os.path.exists(AVIS_XV):
        return None
    # Contra el base a las mismas horas, no contra el base de todas (auditoría del 09-10-2026).
    sense = xv["error_base"]
    ajuda = xv["error"] < sense
    text = (f"Temps a casa: el registre ja té {xv['hores_pluja']} hores de pluja amb la dada de Sant Cugat. "
            f"Error en setmanes no vistes, a les mateixes hores: amb la pluja de Sant Cugat {xv['error']:.4f}, "
            f"sense {sense:.4f} (model de l'arxiu {xv['error_abans']:.4f}). "
            + ("Ajuda: si vols, demana la clau d'OpenData de l'AEMET i afegim l'aeroport de Sabadell."
               if ajuda else "No ajuda: no val la pena afegir l'aeroport de Sabadell."))
    os.makedirs(DIR, exist_ok=True)
    open(AVIS_XV, "w").close()
    return text


# --- «Si surts»: el veredicto de cada medio y lo que pasó (ADR 0047 y 0068) -----------
# Hasta el 10-10-2026 solo se comprobaba la lluvia en moto (moto.csv). Juanjo,
# ese día: «si un medio como la moto falla, es de suponer que el resto también
# lo hará ya que se rigen por las mismas reglas, por eso es necesario no poner
# parches a un elemento sino buscar que todo funcione bien». Se comprueban
# todos los medios con sus tres reglas (lluvia, viento y frío), con lo que
# mostró la página y lo que pasó: sortir.csv guarda las entradas y lo medido,
# y el resumen juzga con las reglas de ahora (C.SORTIR_*, las de web/sortir.js,
# que las pruebas comparan ejecutando la página).

SORTIR = os.path.join(REGISTRE, "sortir.csv")
MOTO_VELL = os.path.join(REGISTRE, "moto.csv")       # el de antes del 10-10-2026, sustituido
CAMPS_SORTIR = ["fins", "termini", "emes", "antelacio_h", "probabilitat", "pluja_mm", "plou_ara", "avis",
                "ratxa", "temperatura", "pluja_obs", "ratxa_obs", "temperatura_obs", "pluja_3h"]
# Con qué antelación se juzga: al salir (la previsión de 1 a 3 horas antes) y
# la vuelta, decidida por la mañana (de 6 a 10 horas antes); de cada hora, la
# previsión más reciente dentro de ese margen.
TERMINIS_SORTIR = {"sortida": (1, 3), "tornada": (6, 10)}
# Solo las horas en que se circula: tramos que acaban de las 7 a las 22 h.
HORES_SORTIR = range(7, 23)
DIES_RESUM_SORTIR = 28          # resumen por Telegram, una vez
AVIS_SORTIR = os.path.join(DIR, "avis-sortir")
MITJANS_SORTIR = ("peu", "bici", "moto", "cotxe")     # el transporte público no depende del tiempo
NOM_MITJA = {"peu": "A peu", "bici": "Bici o patinet", "moto": "Moto", "cotxe": "Cotxe"}
ORDRE_NIVELLS = ("be", "compte", "no")
# La regla de lluvia de la moto de antes del 08-10-2026, para comparar: 50 % o
# 1 mm, «no»; 20 % o 0,2 mm, «compte»; un aviso de AEMET solo, «no».
ABANS_MOTO = (0.2, 0.5, 0.2, 1.0)


def _sobre(p, mm, prob, llindar_mm):
    return mm >= llindar_mm if p is None else p >= prob


def banda(h):
    """«curt» si la hora es de aquí a SORTIR_CURT_H horas o menos; si no, «llarg»."""
    return "curt" if (h.get("antelacio_h") or 0) <= C.SORTIR_CURT_H else "llarg"


def pluja_3h(hores, i):
    """La lluvia que mostraba la página en 3 horas seguidas alrededor de la
    hora i: de las ventanas que la contienen, la que más acumula, solo con las
    horas en que puede llover (20 % o más), como plujaTresHores de
    web/sortir.js y los peligros (riscos.py)."""
    pot = lambda f: f.get("probabilitat") is None or f["probabilitat"] >= C.PROB_ATENCION  # noqa: E731
    sumes = [sum((f.get("pluja_mm") or 0) for f in hores[a:a + 3] if pot(f))
             for a in range(max(0, i - 2), i + 1) if a + 3 <= len(hores)]
    return round(max(sumes), 1) if sumes else None


def nivell_pluja(mitja, h, llindars=None):
    """El nivel por lluvia de una hora, como avalua() de web/sortir.js. h:
    probabilitat, pluja_mm, plou_ara, avis (aviso de AEMET por lluvia) y
    antelacio_h; llindars: los de lluvia en uso (llindars_sortir)."""
    ll = (llindars or C.SORTIR_LLINDARS_PLUJA)[banda(h)]
    p, mm, plou, avis = h.get("probabilitat"), h.get("pluja_mm") or 0, bool(h.get("plou_ara")), bool(h.get("avis"))
    pluja = plou or _sobre(p, mm, ll["pluja"], C.SORTIR_MM_PLUJA)
    risc = plou or avis or _sobre(p, mm, ll["risc"], C.SORTIR_MM_RISC)
    if mitja in ("bici", "moto"):
        return "no" if pluja else "compte" if risc else "be"
    if mitja == "cotxe":
        # La lluvia en 3 horas (desde la 3.139.0, ADR 0039); la de la última
        # media hora solo cuenta al salir ahora, que el registro no juzga.
        mm3 = h.get("pluja_3h") or 0
        if mm3 > C.SORTIR_PLUJA_COTXE["3h"][1]:
            return "no"
        return "compte" if mm3 > C.SORTIR_PLUJA_COTXE["3h"][0] or pluja or avis else "be"
    if mitja == "peu":
        return "compte" if risc else "be"
    return "be"


def nivell_moto_abans(h):
    p, mm, plou, avis = h.get("probabilitat"), h.get("pluja_mm") or 0, h.get("plou_ara"), h.get("avis")
    risc, pluja, mm_risc, mm_pluja = ABANS_MOTO
    if plou or avis or (p or 0) >= pluja or mm >= mm_pluja:
        return "no"
    return "compte" if (p or 0) >= risc or mm >= mm_risc else "be"


def nivell_llindar(valor, llindars, baix=False):
    """«no», «compte» o «be» de un valor con (compte, no); baix: cuanto menos,
    peor (el frío)."""
    if valor is None:
        return None
    compte, no = llindars
    passa = (lambda l: l is not None and valor <= l) if baix else (lambda l: l is not None and valor >= l)
    return "no" if passa(no) else "compte" if passa(compte) else "be"


def nivells_sortir(mitja, h, llindars=None):
    """{pluja, vent, fred} de una hora para un medio (sin el tráfico)."""
    ll = C.SORTIR_LLINDARS[mitja]
    return {"pluja": nivell_pluja(mitja, h, llindars), "vent": nivell_llindar(h.get("ratxa"), ll["ratxa"]),
            "fred": nivell_llindar(h.get("temperatura"), ll["fred"], baix=True)}


def nivell_sortir(mitja, h, llindars=None):
    """El nivel de una hora: el peor de las tres reglas."""
    return max((n for n in nivells_sortir(mitja, h, llindars).values() if n), key=ORDRE_NIVELLS.index, default="be")


def ratxa_observada(vent, fins):
    """La racha máxima de la estación del viento (C.VENT_ESTACIO) en la hora que
    acaba en fins: las dos medias horas (vent-mitges-hores.csv)."""
    import prevision as P
    t = dt.datetime.fromisoformat(fins).astimezone()
    vals = [_num((vent.get(P.clau_hora(t - dt.timedelta(minutes=m))) or {}).get(f"{C.VENT_ESTACIO}_ratxa"))
            for m in (0, 30)]
    vals = [v for v in vals if v is not None]
    return max(vals) if len(vals) == 2 else None


def verifica_sortir(ahora=None):
    """Apunta en sortir.csv, de cada hora pasada que aún no esté, lo que mostró
    la página (al salir y la vuelta decidida por la mañana) y lo que se midió:
    lluvia, racha y temperatura. Devuelve cuántas horas ha añadido."""
    ahora = ahora or dt.datetime.now().astimezone()
    if os.path.exists(MOTO_VELL):                 # sustituido por sortir.csv (ADR 0068)
        os.remove(MOTO_VELL)
    fetes = set()
    if os.path.exists(SORTIR):
        with open(SORTIR, encoding="utf-8") as f:
            fetes = {(r["fins"], r["termini"]) for r in csv.DictReader(f)}
    casa, meteocat, vent = _llegeix("estacio-casa.csv"), _meteocat(), _llegeix("vent-mitges-hores.csv")
    veines = _veines()
    millor = {}
    for arxiu in sorted(glob.glob(os.path.join(REGISTRE, "casa-*.jsonl"))):
        with open(arxiu, encoding="utf-8") as f:
            for linea in map(json.loads, f):
                for idx, h in enumerate(linea["hores"]):
                    # Sin el aviso registrado (antes del 08-10-2026) no se sabe qué dijo.
                    if not h.get("mostrat") or h.get("avis_pluja") is None or int(h["fins"][11:13]) not in HORES_SORTIR:
                        continue
                    for termini, (a, b) in TERMINIS_SORTIR.items():
                        clau = (h["fins"], termini)
                        if a <= h["antelacio_h"] < b and (clau not in millor
                                                          or h["antelacio_h"] < millor[clau][1]["antelacio_h"]):
                            millor[clau] = (linea["emes"], h,
                                            pluja_3h([x.get("mostrat") or {} for x in linea["hores"]], idx))
    noves = []
    for (fins, termini), (emes, h, mm3) in sorted(millor.items()):
        if (fins, termini) in fetes or dt.datetime.fromisoformat(fins).astimezone() > ahora:
            continue
        obs = observada(casa, meteocat, veines, fins)
        ratxa_obs, temp_obs = ratxa_observada(vent, fins), _num((casa.get(fins) or {}).get("temperatura"))
        if obs is None and ratxa_obs is None and temp_obs is None:
            continue
        m = h["mostrat"]
        # La racha que mostró la página es la del modelo (casa.py); desde el
        # 10-10-2026 va también en «mostrat».
        ratxa = m.get("ratxa", h.get("wind_gusts_10m"))
        temp = m.get("temperatura", h.get("temperature_2m"))
        noves.append({"fins": fins, "termini": termini, "emes": emes, "antelacio_h": h["antelacio_h"],
                      "probabilitat": m.get("probabilitat"), "pluja_mm": m.get("pluja_mm"),
                      "plou_ara": int(bool(m.get("plou_ara"))), "avis": int(bool(h["avis_pluja"])),
                      "ratxa": ratxa, "temperatura": temp, "pluja_obs": obs, "ratxa_obs": ratxa_obs,
                      "temperatura_obs": temp_obs, "pluja_3h": mm3})
    if noves:
        os.makedirs(os.path.dirname(SORTIR), exist_ok=True)
        _al_dia_sortir()
        nou = not os.path.exists(SORTIR)
        with open(SORTIR, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPS_SORTIR)
            if nou:
                w.writeheader()
            w.writerows(noves)
    return len(noves)


def _al_dia_sortir():
    """Si sortir.csv tiene las columnas de antes (sin «pluja_3h», antes de la
    3.139.0), lo reescribe con las de ahora; las filas viejas quedan vacías."""
    if not os.path.exists(SORTIR):
        return
    with open(SORTIR, encoding="utf-8") as f:
        r = csv.DictReader(f)
        if r.fieldnames == CAMPS_SORTIR:
            return
        files = list(r)
    with open(SORTIR, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPS_SORTIR)
        w.writeheader()
        w.writerows({k: fila.get(k, "") for k in CAMPS_SORTIR} for fila in files)


def _hora_sortir(r):
    """Una fila de sortir.csv, con números."""
    n = {k: _num(r.get(k)) for k in ("probabilitat", "pluja_mm", "ratxa", "temperatura", "pluja_obs", "ratxa_obs",
                                     "temperatura_obs", "pluja_3h")}
    return {**n, "plou_ara": r.get("plou_ara") == "1", "avis": r.get("avis") == "1",
            "antelacio_h": _num(r.get("antelacio_h"))}


def resum_sortir():
    """Por medio, regla y antelación: cuántas horas dio cada nivel y en cuántas
    pasó (llovió, o la racha o el frío llegaron al umbral de «compte»). La
    moto, también con su regla de lluvia de antes. None si aún no hay nada."""
    if not os.path.exists(SORTIR):
        return None
    with open(SORTIR, encoding="utf-8") as f:
        files = list(csv.DictReader(f))
    if not files:
        return None
    dies = sorted({r["fins"][:10] for r in files})
    res = {"dies": len(dies), "des_de": dies[0], "fins": dies[-1], "mitjans": {}}
    llindars = llindars_sortir()
    for mitja in MITJANS_SORTIR:
        ll = C.SORTIR_LLINDARS[mitja]
        regles = {"pluja": (lambda h: h["pluja_obs"] is not None and h["pluja_obs"] >= C.UMBRAL_MM,
                            lambda h: h["pluja_obs"] is not None)}
        if ll["ratxa"][0] is not None or ll["ratxa"][1] is not None:
            regles["vent"] = (lambda h, ll=ll: nivell_llindar(h["ratxa_obs"], ll["ratxa"]) not in (None, "be"),
                              lambda h: h["ratxa_obs"] is not None)
        if ll["fred"][0] is not None or ll["fred"][1] is not None:
            regles["fred"] = (lambda h, ll=ll: nivell_llindar(h["temperatura_obs"], ll["fred"], baix=True) not in (None, "be"),
                              lambda h: h["temperatura_obs"] is not None)
        m = res["mitjans"][mitja] = {}
        for regla, (passa, mesurat) in regles.items():
            m[regla] = {}
            for termini in TERMINIS_SORTIR:
                hs = [_hora_sortir(r) for r in files if r["termini"] == termini]
                hs = [h for h in hs if mesurat(h)]
                nivell = (lambda h, regla=regla, mitja=mitja: nivells_sortir(mitja, h, llindars)[regla] or "be")
                m[regla][termini] = {n: [sum(1 for h in hs if nivell(h) == n), sum(1 for h in hs if nivell(h) == n and passa(h))]
                                     for n in ORDRE_NIVELLS}
                if mitja == "moto" and regla == "pluja":
                    m[regla][termini]["abans"] = {n: [sum(1 for h in hs if nivell_moto_abans(h) == n),
                                                      sum(1 for h in hs if nivell_moto_abans(h) == n and passa(h))]
                                                  for n in ORDRE_NIVELLS}
    return res


def text_resum_sortir(r):
    """El resumen para Juanjo: de cada medio y regla, al salir y la vuelta, las
    horas con cada nivel y en cuántas pasó."""
    noms_regla = {"pluja": "pluja", "vent": "ratxes", "fred": "fred"}
    passa = {"pluja": "va ploure", "vent": "van arribar al llindar", "fred": "va arribar al llindar"}
    noms_nivell = {"no": "«millor no»", "compte": "«compte»", "be": "«bé»"}
    linies = [f"Si surts, comprovació de tots els mitjans: {r['dies']} dies ({r['des_de']} a {r['fins']}), "
              "hores de 7 a 22 h. De cada nivell, les hores i en quantes va passar. "
              "Al sortir (previsió d'1 a 3 h abans) / tornada decidida al matí (de 6 a 10 h abans)."]
    pluja_total = 0
    for mitja, regles in r["mitjans"].items():
        for regla, t in regles.items():
            parts = []
            for n in ("no", "compte", "be"):
                s, v = t["sortida"][n], t["tornada"][n]
                if s[0] or v[0]:
                    parts.append(f"{noms_nivell[n]} {s[0]} h, {passa[regla]} en {s[1]} / {v[0]} h, en {v[1]}")
            if regla == "pluja":
                pluja_total = max(pluja_total, sum(t["sortida"][n][1] for n in ORDRE_NIVELLS))
            linia = f"{NOM_MITJA[mitja]}, {noms_regla[regla]}: " + ("; ".join(parts) or "cap hora mesurada") + "."
            if "abans" in t["sortida"]:
                a = t["sortida"]["abans"]
                linia += (f" Amb la regla d'abans del 08-10-2026, al sortir: «millor no» {a['no'][0]} h "
                          f"(va ploure en {a['no'][1]}), «bé» {a['be'][0]} h (en {a['be'][1]}).")
            linies.append(linia)
    if pluja_total < 5:
        linies.append("Encara hi ha massa poca pluja per jutjar-ho.")
    return "\n".join(linies)


# --- Los umbrales de lluvia de «Si surts», aprendidos (ADR 0069) -------------------
# Juanjo, 10-10-2026: cada nivel tiene que significar lo que dice. Con
# «millor no» tiene que llover al menos 2 de cada 3 veces; con «bé», como
# mucho 1 de cada 100. La probabilidad acierta más cerca de la hora, así que
# (y ninguna franja de 5 puntos con «bé», más de 1 de cada 10). La
# probabilidad acierta más cerca de la hora, así que
# hay dos juegos de umbrales: para dentro de SORTIR_CURT_H horas o menos
# («curt», se juzga con la previsión de 1 a 3 h antes) y para más tarde
# («llarg», con la de 6 a 10 h antes). «pluja»: el umbral más bajo cuyo
# resultado cumple el objetivo también con el margen de la muestra (cota de
# Wilson); «risc»: el más alto. Se proponen, se avisa y se aplican al día
# siguiente, como el resto del aprendizaje (ATURA los para).

LLINDARS_SORTIR = os.path.join(DIR, "llindars-sortir.json")
PROPOSTA_SORTIR = os.path.join(DIR, "llindars-sortir-proposta.json")
TERMINI_BANDA = {"sortida": "curt", "tornada": "llarg"}
GRAELLA_PLUJA = [round(0.25 + 0.05 * k, 2) for k in range(12)]          # 25 % a 80 %
GRAELLA_RISC = [round(0.05 * k, 2) for k in range(1, 5)]                 # 5, 10, 15 i 20 %


def wilson(exits, n, z=None):
    """(cota baja, cota alta) de una proporción."""
    z = C.SORTIR_Z if z is None else z
    if not n:
        return 0.0, 1.0
    f = exits / n
    centre = (f + z * z / (2 * n)) / (1 + z * z / n)
    marge = z * math.sqrt(f * (1 - f) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - marge, centre + marge


def apren_llindars(mostres):
    """mostres: [(probabilitat, plou)]. Los umbrales que cumplen los objetivos,
    o None si no hay bastante lluvia para decidir."""
    mostres = [(p, y) for p, y in mostres if p is not None]
    if sum(y for _, y in mostres) < C.SORTIR_MIN_PLUJA:
        return None
    res = {}
    for t in GRAELLA_PLUJA:
        dins = [y for p, y in mostres if p >= t]
        if len(dins) >= C.SORTIR_MIN_HORES and wilson(sum(dins), len(dins))[0] >= C.SORTIR_OBJECTIU_NO:
            res["pluja"] = t
            break
    # «Bé»: en conjunto, 1 de cada 100 con el margen; y ninguna franja de 5
    # puntos por debajo puede llover más de 1 de cada 10 veces, para que las
    # muchas horas secas no tapen las dudosas (la de justo debajo, con datos
    # suficientes para juzgarla).
    def franges_bones(t):
        a = 0.0
        while a < t - 1e-9:
            dins = [y for p, y in mostres if a <= p < min(a + 0.05, t)]
            if len(dins) >= C.SORTIR_MIN_HORES and sum(dins) / len(dins) > C.SORTIR_OBJECTIU_FRANJA:
                return False
            if a + 0.05 >= t - 1e-9 and len(dins) < C.SORTIR_MIN_HORES:
                return False
            a += 0.05
        return True
    for t in reversed(GRAELLA_RISC):
        dins = [y for p, y in mostres if p < t]
        if (len(dins) >= C.SORTIR_MIN_HORES and wilson(sum(dins), len(dins))[1] <= C.SORTIR_OBJECTIU_BE
                and franges_bones(t)):
            res["risc"] = t
            break
    return res or None


def llindars_sortir():
    """Los umbrales en uso: los aprendidos o, si no hay, los de partida."""
    ll = json.loads(json.dumps(C.SORTIR_LLINDARS_PLUJA))
    try:
        with open(LLINDARS_SORTIR, encoding="utf-8") as f:
            apresos = json.load(f)
        for banda, v in apresos.get("llindars", {}).items():
            ll.setdefault(banda, {}).update({k: v[k] for k in ("pluja", "risc") if k in v})
    except (OSError, ValueError):
        pass
    return ll


def mostres_sortir():
    """De sortir.csv, por banda: [(probabilitat, plou)] de las horas con lluvia medida."""
    res = {"curt": [], "llarg": []}
    if not os.path.exists(SORTIR):
        return res
    with open(SORTIR, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p, obs = _num(r.get("probabilitat")), _num(r.get("pluja_obs"))
            if p is not None and obs is not None:
                res[TERMINI_BANDA[r["termini"]]].append((p, obs >= C.UMBRAL_MM))
    return res


def aprén_sortir(avui, avisa=True):
    """1. Una propuesta de ayer, si nadie la ha parado, se aplica. 2. Con los
    datos de hoy, si los umbrales que cumplen los objetivos no son los de
    ahora, se propone para mañana y se avisa. Devuelve el texto del aviso."""
    text = None
    if os.path.exists(PROPOSTA_SORTIR):
        with open(PROPOSTA_SORTIR, encoding="utf-8") as f:
            proposta = json.load(f)
        os.remove(PROPOSTA_SORTIR)
        if proposta.get("dia", "") < avui and not os.path.exists(ATURA):
            guarda(LLINDARS_SORTIR, {"des_de": avui, "llindars": proposta["llindars"], "dades": proposta["dades"]})
    ara = llindars_sortir()
    nous, dades = {}, {}
    for banda, mostres in mostres_sortir().items():
        apres = apren_llindars(mostres)
        if apres:
            nous[banda] = {**ara[banda], **apres}
            dades[banda] = {"hores": len(mostres), "hores_pluja": sum(y for _, y in mostres)}
    canvis = {b: v for b, v in nous.items() if v != ara.get(b)}
    if canvis:
        guarda(PROPOSTA_SORTIR, {"dia": avui, "llindars": {**{b: ara[b] for b in ara}, **canvis}, "dades": dades})
        noms = {"curt": "per sortir d'aquí a 3 hores o menys", "llarg": "per a més tard"}
        linies = ["Si surts, llindars de pluja: canvi proposat, s'aplicarà demà (per aturar-ho, demana-ho a Claude)."]
        for b, v in canvis.items():
            a = ara[b]
            linies.append(f"{noms[b].capitalize()}: «millor no» des del {round(a['pluja'] * 100)} % al "
                          f"{round(v['pluja'] * 100)} %, «compte» des del {round(a['risc'] * 100)} % al "
                          f"{round(v['risc'] * 100)} % ({dades[b]['hores']} hores, {dades[b]['hores_pluja']} amb pluja).")
        text = "\n".join(linies)
        if avisa:
            subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", text], check=False)
    return text


def avis_sortir(avisa=True):
    """El resumen, una sola vez, cuando hay DIES_RESUM_SORTIR días."""
    r = resum_sortir()
    if not r or r["dies"] < DIES_RESUM_SORTIR or os.path.exists(AVIS_SORTIR):
        return None
    text = text_resum_sortir(r)
    if avisa:
        subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", text], check=False)
    os.makedirs(DIR, exist_ok=True)
    open(AVIS_SORTIR, "w").close()
    return text


def estat():
    model = carrega()
    print(json.dumps(resum_pagina(model), ensure_ascii=False))
    for ruta in (HISTORIAL, HISTORIAL_HUMITAT):
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                print("".join(f.readlines()[-5:]), end="")


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "diari":
        diari()
    elif orden == "estat":
        estat()
    elif orden in ("sortir", "moto"):
        r = resum_sortir()
        print(text_resum_sortir(r) if r else "Encara no hi ha cap hora verificada.")
    else:
        print(__doc__)
