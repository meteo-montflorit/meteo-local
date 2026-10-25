#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El cielo de cada hora: las nubes de varios modelos, comprobadas con lo
que observa el aeropuerto de Sabadell (ADR 0088).

Hasta la 3.80 el cielo era el de un solo modelo, AROME, cuyas nubes saltan de
una hora a otra (el 13-10-2026 dio «serè» con más de la mitad del cielo
tapado). Ahora es la media ponderada de cuatro modelos (MODELS), y en la hora
en curso manda lo observado en las nubes bajas, las que da el aeropuerto; las
de encima siguen siendo las de los modelos (cel_ara).

La observación es el METAR del aeropuerto de Sabadell (LELL, a unos 7 km),
cada media hora, día y noche, leído del servicio público de la NOAA
(aviationweather.gov): cuánto cielo tapa cada capa, en octavos. El cielo
tapado es el de la capa que más tapa. Si no da capas (CAVOK, NSC, NCD y
parecidos) solo se sabe que no hay nubes bajas: por encima de 1.500 m puede
haberlas. Por eso, al comparar, las horas con capas se comparan con todas las
nubes del modelo, y las horas sin capas, solo con sus nubes bajas, que
tendrían que ser cero.

En cada pasada se apunta lo observado por horas (nuvols-sabadell.csv); lo
que daba cada modelo ya va en el registro de la previsión (casa-AAAA-MM.jsonl,
campos nuvols_<modelo> y nuvols_baixos_<modelo>). Cada día, con los últimos
DIES días, se ajustan los pesos con la combinación de previsiones de Granger
y Ramanathan (mínimos cuadrados con los pesos positivos y sumando 1), se
comprueban en semanas que no han visto (validación cruzada) y, si se
equivocan menos que los de ahora en al menos el 95 % de los remuestreos por
días (bootstrap), sustituyen a los de ahora y se avisa (ADR 0088).

Uso:
  python3 nuvols.py verifica   compara y, si toca, cambia los pesos
  python3 nuvols.py estat      los pesos y la última comparación
"""
import csv
import datetime as dt
import glob
import itertools
import json
import os
import subprocess
import sys

import numpy as np

import hora as H
import remostreig as R

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
APRENENTATGE = os.environ.get("APRENENTATGE_DIR", "/estat/aprenentatge")
PESOS = os.path.join(APRENENTATGE, "nuvols-pesos.json")
OBSERVATS = os.path.join(DIR, "nuvols-sabadell.csv")
CAMPS_OBSERVATS = ["fins", "nuvols", "capes", "metars"]

# Los modelos de Open-Meteo que se mezclan, con el nombre corto del registro.
MODELS = {"arome": "meteofrance_seamless", "icon_eu": "icon_eu",
          "ecmwf": "ecmwf_ifs", "gfs": "gfs_seamless"}
NOMS = {"arome": "AROME", "icon_eu": "ICON-EU", "ecmwf": "ECMWF", "gfs": "GFS"}
# Los dos que no trae la petición principal de casa.py.
MODELS_APART = ("ecmwf_ifs", "gfs_seamless")

AEROPORT = "LELL"
URL_METAR = f"https://aviationweather.gov/api/data/metar?ids={AEROPORT}&hours=3&format=json"
# Octavos de cada cantidad, en el punto medio de su intervalo, y en %.
OCTAUS = {"FEW": 1.5, "SCT": 3.5, "BKN": 6, "OVC": 8, "OVX": 8, "VV": 8}
SENSE_CAPES = ("CAVOK", "NSC", "NCD", "SKC", "CLR")
# Una observación de más de estos minutos ya no vale para la hora en curso.
ARA_MAX_MIN = 45

DIES = 30
MIN_HORES = 300          # horas observadas con los cuatro modelos, como mínimo
MIN_DIES = 14            # en días distintos
REMOSTREJOS, SEGURETAT = R.REMOSTREJOS, R.SEGURETAT     # la regla común (ADR 0105)


def percentatge(metar):
    """(% de cielo tapado, si hay capas) de un METAR de aviationweather.gov
    (formato json); (None, False) si no dice nada de las nubes."""
    capes = [OCTAUS[c["cover"]] for c in metar.get("clouds") or [] if c.get("cover") in OCTAUS]
    if capes:
        return round(max(capes) / 8 * 100), True
    brut = metar.get("rawOb") or ""
    if " VV" in brut:
        return 100, True
    if any(f" {c}" in brut for c in SENSE_CAPES) or (metar.get("clouds") and metar["clouds"][0].get("cover") in SENSE_CAPES):
        return 0, False
    return None, False


def llegeix(get):
    """Los METAR de las últimas 3 horas, del más antiguo al más nuevo:
    [{"t", "nuvols", "capes", "brut"}]."""
    try:
        dades = get(URL_METAR)
    except Exception:
        dades = get(URL_METAR)      # a veces da un 504 suelto
    res = []
    for m in json.loads(dades):
        pct, capes = percentatge(m)
        t = H.utc(m["reportTime"])
        res.append({"t": t, "nuvols": pct, "capes": capes, "brut": m.get("rawOb")})
    return sorted(res, key=lambda o: o["t"])


def hores(obs):
    """{fin: (media del % de la hora, si algún METAR ve capas, METAR)} de las
    horas con observación: la hora que acaba en fin junta los METAR de después
    de fin - 1 h hasta fin (los de y media y en punto)."""
    per_hora = {}
    for o in obs:
        if o["nuvols"] is None:
            continue
        t = o["t"]
        fin = t.replace(minute=0, second=0, microsecond=0)
        if t != fin:
            fin += dt.timedelta(hours=1)
        per_hora.setdefault(fin, []).append(o)
    return {fin: (round(sum(o["nuvols"] for o in os_) / len(os_)), any(o["capes"] for o in os_),
                  [o["brut"] for o in os_])
            for fin, os_ in per_hora.items()}


def ara(obs, ahora):
    """Las nubes bajas que se ven ahora: el % de la última observación si es
    reciente, también el 0 % si no ve capas (CAVOK y parecidos). El METAR solo
    da las nubes que importan a los aviones, no las altas: las de encima las
    ponen los modelos (cel_ara)."""
    if not obs:
        return None
    o = obs[-1]
    if o["nuvols"] is None or ahora - o["t"] > dt.timedelta(minutes=ARA_MAX_MIN):
        return None
    return o["nuvols"]


# La boira al METAR: FG (visibilitat de menys d'1 km) i les seves variants
# (bancs, parcial, baixa, gelant). La boirina (BR) no és boira.
BOIRA_METAR = ("FG", "BCFG", "PRFG", "MIFG", "FZFG")


def te_boira(brut):
    return any(tros in BOIRA_METAR for tros in (brut or "").split())


def boira_ara(obs, ahora):
    """Si l'última observació de Sabadell, recent, diu boira (ADR 0100)."""
    if not obs:
        return False
    o = obs[-1]
    return ahora - o["t"] <= dt.timedelta(minutes=ARA_MAX_MIN) and te_boira(o["brut"])


def apunta(obs, ahora):
    """Las horas ya cerradas, en nuvols-sabadell.csv."""
    from registre import _desa_per_hores
    import prevision as P
    nuevas = {}
    for fin, (pct, capes, brut) in hores(obs).items():
        if fin <= ahora:
            clau = P.clau_hora(fin)
            nuevas[clau] = {"fins": clau, "nuvols": pct, "capes": int(capes),
                            "metars": " | ".join(b or "" for b in brut)}
    _desa_per_hores(OBSERVATS, CAMPS_OBSERVATS, nuevas)


# --- La mezcla -------------------------------------------------------------------

def per_defecte():
    return {m: round(1 / len(MODELS), 4) for m in MODELS}


def pesos():
    """Los pesos de la última comparación; sin ella, todos iguales."""
    try:
        with open(PESOS, encoding="utf-8") as f:
            p = json.load(f).get("pesos")
        if p and set(p) == set(MODELS):
            return p
    except (OSError, ValueError):
        pass
    return per_defecte()


def mescla(valors, p=None):
    """La media ponderada de los modelos que tienen dato ({nom: %}); None si
    no hay ninguno."""
    p = p or pesos()
    hi = [(p[m], v) for m, v in valors.items() if v is not None and p.get(m, 0) > 0]
    total = sum(w for w, _ in hi)
    if not total:
        hi = [(1, v) for v in valors.values() if v is not None]
        total = len(hi)
    return round(sum(w * v for w, v in hi) / total) if total else None


def valors_hora(h, i, camp="cloud_cover"):
    """Las nubes de cada modelo para la hora i de la respuesta de Open-Meteo
    (camp: cloud_cover, todas; cloud_cover_low, las bajas)."""
    return {nom: (h.get(f"{camp}_{model}") or [None] * (i + 1))[i] for nom, model in MODELS.items()}


def per_sobre(total, baixos):
    """Lo que tapan las nubes de encima de las bajas en un modelo, con las
    capas solapadas al azar: total = 1 - (1 - bajas)(1 - de encima). None si
    falta un dato o las bajas lo tapan todo: entonces no se sabe."""
    if total is None or baixos is None or baixos >= 99:
        return None
    return max(0.0, min(100.0, 100 * (1 - (1 - total / 100) / (1 - baixos / 100))))


def cel_ara(baixos, h, i):
    """El cielo de la hora en curso: lo que tapan las nubes bajas observadas
    en Sabadell (ara) o lo que tapan las de encima según la mezcla de modelos,
    lo que sea más. Contra el satélite (96 días), se equivoca 19,7 puntos de
    cielo tapado, y el METAR solo, 24,1 (ADR 0088). Sin modelos, lo observado."""
    tot, baix = valors_hora(h, i), valors_hora(h, i, "cloud_cover_low")
    sobre = mescla({nom: per_sobre(tot[nom], baix[nom]) for nom in MODELS})
    return baixos if sobre is None else max(baixos, sobre)


# --- La comparación diaria ---------------------------------------------------------

def llegeix_observats():
    """{fins: (% observado, si había capas)}."""
    if not os.path.exists(OBSERVATS):
        return {}
    with open(OBSERVATS, encoding="utf-8") as f:
        return {r["fins"]: (float(r["nuvols"]), r.get("capes") == "1")
                for r in csv.DictReader(f) if r["nuvols"] not in ("", None)}


def parelles(avui):
    """(fins, {nom: % previsto}, % observado) de cada hora prevista en los
    últimos DIES días con los cuatro modelos y observación. En las horas sin
    capas, lo previsto son las nubes bajas, y lo observado, cero."""
    obs = llegeix_observats()
    des_de = (avui - dt.timedelta(days=DIES)).isoformat()
    res = []
    for ruta in sorted(glob.glob(os.path.join(DIR, "casa-*.jsonl"))):
        with open(ruta, encoding="utf-8") as f:
            for linia in f:
                if not linia.strip():
                    continue
                l = json.loads(linia)
                for hr in l.get("hores") or []:
                    fins = hr.get("fins")
                    if not fins or H.dia_local(fins).isoformat() < des_de or fins not in obs:
                        continue
                    pct, capes = obs[fins]
                    camp = "nuvols_" if capes else "nuvols_baixos_"
                    v = {nom: hr.get(f"{camp}{nom}") for nom in MODELS}
                    if all(x is not None for x in v.values()):
                        res.append((fins, v, pct if capes else 0.0))
    return res


def error(matriu, obs, p):
    """El error medio, en puntos de cielo tapado, de la mezcla p."""
    w = np.array([p[m] for m in MODELS])
    return float(np.mean(np.abs(matriu @ w - obs)))


def ajusta(x, y):
    """Los pesos de la combinación de previsiones de Granger y Ramanathan
    (1984): mínimos cuadrados con los pesos positivos y sumando 1,
    min ||x w - y||² con w >= 0 y sum(w) = 1. Solución exacta: el mínimo
    está en el interior de alguna cara del símplex; en cada cara (cada
    subconjunto de modelos) se resuelve el sistema de Lagrange con la suma
    igual a 1 y, de las soluciones con todos los pesos positivos, se queda la
    de menor error. Con cuatro modelos son 15 sistemas."""
    k = x.shape[1]
    millor = None
    for r in range(1, k + 1):
        for cara in itertools.combinations(range(k), r):
            xs = x[:, cara]
            a = np.zeros((r + 1, r + 1))
            a[:r, :r] = 2 * xs.T @ xs
            a[:r, r] = a[r, :r] = 1
            b = np.append(2 * xs.T @ y, 1)
            w = np.linalg.lstsq(a, b, rcond=None)[0][:r]
            if (w < -1e-9).any():
                continue
            tots = np.zeros(k)
            tots[list(cara)] = np.clip(w, 0, None)
            tots /= tots.sum()
            sse = float(np.sum((x @ tots - y) ** 2))
            if millor is None or sse < millor[0] - 1e-9:
                millor = (sse, tots)
    return millor[1]


def compara(ps, actual):
    """La mezcla ajustada frente a la de ahora, en semanas que no ha visto
    (validación cruzada), y con qué seguridad es mejor: la proporción de
    remuestreos por días en que se equivoca menos (bootstrap)."""
    hores_obs = {f for f, _, _ in ps}
    res = {"parelles": len(ps), "hores": len(hores_obs), "dies": len({f[:10] for f in hores_obs})}
    if not ps:
        return res
    matriu = np.array([[v[m] for m in MODELS] for _, v, _ in ps], dtype=float)
    obs = np.array([o for _, _, o in ps], dtype=float)
    res["error_actual"] = round(error(matriu, obs, actual), 1)
    for nom in MODELS:
        res[f"error_{nom}"] = round(error(matriu, obs, {m: float(m == nom) for m in MODELS}), 1)
    w = ajusta(matriu, obs)
    res["ajustats"] = {m: round(float(x), 3) for m, x in zip(MODELS, w)}
    # Avance temporal (ADR 0106): cada día se predice con los pesos
    # ajustados con los días anteriores.
    dies = np.array([f[:10] for f, _, _ in ps])
    pred = np.full(len(obs), np.nan)
    for ent, aval in R.avanc(dies):
        pred[aval] = matriu[aval] @ ajusta(matriu[ent], obs[ent])
    s = ~np.isnan(pred)
    if not s.any():
        return res
    pred_actual = matriu @ np.array([actual[m] for m in MODELS])
    res["dies_avaluats"] = len(set(dies[s]))
    res["error_ajustats"] = round(float(np.mean(np.abs(pred[s] - obs[s]))), 1)
    # El remuestreo, por días enteros: las horas de un mismo día se parecen
    # y no son casos independientes (la regla común, remostreig).
    res["seguretat"] = R.seguretat((pred[s] - obs[s]) ** 2, (pred_actual[s] - obs[s]) ** 2, dies[s])
    return res


def decideix(c, actual):
    """Los pesos que tocan: los ajustados con todo, si hay bastantes horas y
    se equivocan menos que los de ahora en las semanas que no han visto en
    al menos el 95 % de los remuestreos; si no, los de ahora."""
    if c["hores"] < MIN_HORES or c["dies"] < MIN_DIES or c.get("seguretat") is None:
        return actual
    return c["ajustats"] if c["seguretat"] >= SEGURETAT else actual


def sense_observacions(ahora):
    """Si hace más de un día que no se apunta ninguna hora de Sabadell: el
    cielo de la hora en curso vuelve a ser el de los modelos y la
    comparación se para. None si todo va bien."""
    obs = llegeix_observats()
    darrera = max(obs) if obs else None
    if darrera and ahora - H.llegeix(darrera) < dt.timedelta(days=1):
        return None
    return ("Temps a Montflorit, el cel: fa més d'un dia que no arriba l'observació de núvols de l'aeroport "
            f"de Sabadell (darrera hora: {darrera or 'cap'}). El cel de l'hora en curs és el dels models i "
            "no es pot comprovar quin encerta: mira nuvols.py i aviationweather.gov.")


def verifica(avui=None, avisa=True):
    avui = avui or H.dia_local(H.ara())
    if os.path.exists(OBSERVATS):
        avis = sense_observacions(H.ara())
        if avis:
            print(avis)
            if avisa:
                subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", avis], check=False)
    actual = pesos()
    c = compara(parelles(avui), actual)
    nous = decideix(c, actual)
    if nous != actual and os.path.exists(os.path.join(APRENENTATGE, "atura")):
        print("Canvi dels pesos dels núvols aturat (existeix «atura»).")
        nous = actual
    os.makedirs(APRENENTATGE, exist_ok=True)
    estat = {"pesos": nous, "dia": avui.isoformat(), "comparacio": c}
    with open(PESOS + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estat, f, ensure_ascii=False, indent=1)
    os.replace(PESOS + ".tmp", PESOS)
    if nous != actual:
        noms = ", ".join(f"{NOMS[m]} {round(w * 100)} %" for m, w in nous.items() if w)
        coma = lambda x: f"{x:.1f}".replace(".", ",")  # noqa: E731
        text = (f"Temps a Montflorit, el cel: ara la mescla de models és {noms}. En setmanes que no ha vist, "
                f"dels últims {DIES} dies, s'equivoca de mitjana en {coma(c['error_ajustats'])} punts de cel "
                f"tapat, contra {coma(c['error_actual'])} de l'anterior, i encerta més en el "
                f"{round(c['seguretat'] * 100)} % dels remostrejos ({c['hores']} hores observades a l'aeroport "
                f"de Sabadell en {c['dies']} dies).")
        print(text)
        if avisa:
            subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", text], check=False)
    else:
        print("Núvols: es queden els pesos.", json.dumps(c, ensure_ascii=False))
    return estat


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "verifica":
        verifica()
    elif orden == "estat":
        print(json.dumps(pesos(), ensure_ascii=False))
        print(json.dumps(compara(parelles(H.dia_local(H.ara())), pesos()), ensure_ascii=False))
    else:
        print(__doc__)
