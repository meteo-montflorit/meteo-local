#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El modelo del archivo con los avisos oficiales como señales (ADR 0097).

El 16-10-2026 la página daba un 14 % de lluvia para el sábado por la tarde
con un aviso de peligro alto de Meteocat por intensidad de lluvia: la
probabilidad sale solo de los modelos y los avisos se muestran aparte. El
aviso no se impone a ojo (ADR 0062 y 0008: un aviso que no se cumple da
consejos erróneos), sino que su peso sale de lo que llovió de verdad.

Como pluja_casa_ecmwf.py (ADR 0086): regresión logística con las previsiones
archivadas en casa y la lluvia medida en Sabadell y Sant Cugat, cada estación
una muestra. A los rasgos del modelo con ECMWF se añaden:

- avis_aemet: aviso de AEMET por lluvia o tormentas en el Prelitoral de
  Barcelona que cubre la hora;
- avis_meteocat y avis_meteocat_alt (si están sus CSV): aviso de Meteocat
  por lluvia o tiempo violento en el Vallès Occidental, y si es de peligro
  alto o más (grado 3 o más).

Solo cuentan los avisos emitidos antes de la previsión: una hora antes del
tramo a corto plazo y un día antes en la de un día vista. Si no, el modelo
aprendería con avisos que todavía no existían (los de observación, por
ejemplo, salen cuando ya llueve).

Se valida contra el modelo sin avisos con las mismas muestras, en grupos de
semanas, por antelación, y con remuestreos por días (bootstrap): se adopta
solo si se equivoca menos en al menos el 95 % de ellos a corto plazo y un
día antes, y si la fiabilidad no empeora: el desvío medio entre lo dado y
lo que llovió, ponderado por horas, no pasa del del modelo sin avisos. Escribe pluja_casa_avisos.json, con «adoptat»: la
página lo usa solo si es true y la pasada tiene los avisos
(aprenentatge.prob_pluja).

Necesita descarrega.py, ecmwf_descarrega.py, avisos_descarrega.py (AEMET) y,
para Meteocat, sus CSV en calibracio/dades/smp_csv/ (avisos_descarrega.py).
Uso: python3 calibracio/pluja_casa_avisos.py
"""
import bisect
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aprenentatge as A  # noqa: E402
import remostreig as R  # noqa: E402
import config as C  # noqa: E402
import smp as SMP  # noqa: E402
from calibracio.analitza import leer_obs, leer_prev  # noqa: E402
from calibracio.avisos_descarrega import (COBERTURA_METEOCAT_CSV, DIR_METEOCAT_CSV,  # noqa: E402
                                          SORTIDA_AEMET, meteocat_csv)
from calibracio.ecmwf_prova import leer_ecmwf  # noqa: E402
from calibracio.pluja_casa import creuada, fiabilitat  # noqa: E402

LOCAL = ZoneInfo("Europe/Madrid")
UTC = dt.timezone.utc
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pluja_casa_avisos.json")
REMOSTREJOS, SEGURETAT = R.REMOSTREJOS, R.SEGURETAT     # la regla común (ADR 0105)
# Los fenómenos de AEMET que cuentan, como en la página (casa.senyals_avis):
# lluvia y tormentas, con su código de Meteoalerta.
FENOMENS_AEMET = ("PR", "TO")
# El primer día descargado del archivo de AEMET (avisos_descarrega.py).
PRIMER_AVIS = dt.datetime(2023, 12, 25, tzinfo=dt.timezone.utc)


def hora(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


# --- AEMET: el estado de los avisos en cada momento ------------------------------------

def avisos_aemet():
    """Los avisos de lluvia o tormentas del archivo, cada uno con el tramo de
    tiempo en que era el vigente: [(emès, substituït, inici, fi)]. Un aviso
    deja de valer cuando sale un mensaje que lo cita en «references»
    (actualización, cancelación o nivel verde); los verdes y las
    cancelaciones no cuentan como aviso."""
    with open(SORTIDA_AEMET, encoding="utf-8") as f:
        crus = [a for a in json.load(f)
                if a["fenomen"].split(";")[0] in FENOMENS_AEMET and a["inici"] and a["fi"]]
    substituit = {}
    for a in crus:
        # «sender,identifier,sent sender,identifier,sent»
        for r in a["referencies"].split():
            parts = r.split(",")
            if len(parts) >= 3:
                t = hora(a["emes"])
                substituit[parts[1]] = min(substituit.get(parts[1], t), t)
    fi_temps = dt.datetime.max.replace(tzinfo=UTC)
    return sorted((hora(a["emes"]), substituit.get(a["id"], fi_temps), hora(a["inici"]), hora(a["fi"]))
                  for a in crus
                  if a["tipus_missatge"] != "Cancel" and a["nivell"].lower() not in ("verde", ""))


def senyal_aemet(avisos, inici, fi, tall):
    """1 si a la hora «tall» había un aviso vigente (emitido y todavía no
    sustituido) que cubre [inici, fi)."""
    return float(any(e <= tall < sub and a < fi and b > inici for e, sub, a, b in avisos))


# --- Meteocat ----------------------------------------------------------------------------

def avisos_meteocat():
    """Los avisos de los CSV del Meteocat, indexados por la hora que cubren:
    {"emissions": {grup: [emissió]}, "per_hora": {clau_hora: [(grup,
    emissió, avís)]}}, o {} si no están (avisos_descarrega.meteocat_csv)."""
    if not os.path.isdir(DIR_METEOCAT_CSV):
        return {}
    grups = meteocat_csv()
    res = {"emissions": {g: [hora(e) for e, _ in v] for g, v in grups.items()}, "per_hora": {}}
    for g, v in grups.items():
        for e, avisos in v:
            for a in avisos:
                for h in SMP.hores_avis(a):
                    res["per_hora"].setdefault(h, []).append((g, hora(e), a))
    return res


def senyal_meteocat(meteocat, inici, tall):
    """(avís, avís alt) de Meteocat por lluvia o tiempo violento que cubre la
    hora que empieza en «inici», según la última actualización de cada aviso
    emitida antes de «tall»; None fuera de lo que cubren los CSV."""
    cob0, cob1 = COBERTURA_METEOCAT_CSV
    if tall < cob0 or inici >= cob1:
        return None
    vigents = []
    for g, e, a in meteocat["per_hora"].get(SMP.clau_hora(inici), []):
        ems = meteocat["emissions"][g]
        i = bisect.bisect_right(ems, tall)
        if i and ems[i - 1] == e:
            vigents.append(a)
    graus = SMP.graus_pluja(inici, {"avisos": vigents})
    return float(bool(graus)), float(max(graus, default=0) >= 3)


# --- Muestras y validación -----------------------------------------------------------------

def muestras(amb_meteocat):
    obs, prev, ec = leer_obs(), leer_prev(), leer_ecmwf()
    aemet, meteocat = avisos_aemet(), avisos_meteocat() if amb_meteocat else {}
    primer = PRIMER_AVIS
    noms = A.RASGOS_ARXIU_ECMWF_AVISOS_METEOCAT if amb_meteocat else A.RASGOS_ARXIU_ECMWF_AVISOS
    res = []
    for t, puntos in sorted(prev.items()):
        p, e = puntos.get("casa"), ec.get(t)
        if not p or not e:
            continue
        inici = t - dt.timedelta(hours=1)
        fins = t.astimezone(LOCAL).strftime("%Y-%m-%dT%H:%M")
        for plazo, horas in (("", 0), ("_previous_day1", 24)):
            tall = inici - dt.timedelta(hours=1 if horas == 0 else horas)
            if tall < primer:
                continue
            d = {"fins": fins, "antelacio_h": horas,
                 f"pluja_{C.MODEL_ECMWF}": e.get(f"precipitation{plazo}_{C.MODEL_ECMWF}"),
                 "avis_pluja": senyal_aemet(aemet, inici, t, tall)}
            d.update({f"pluja_{m}": p.get(f"precipitation{plazo}_{m}") for m in C.MODELOS_FINOS})
            if amb_meteocat:
                s = senyal_meteocat(meteocat, inici, tall)
                if s is None:
                    continue
                d["avis_meteocat"], d["avis_meteocat_alt"] = s
            x = A.rasgos(d, noms)
            if x is None:
                continue
            for serie in obs.values():
                a, b = serie.get(t - dt.timedelta(minutes=60)), serie.get(t - dt.timedelta(minutes=30))
                if a is not None and b is not None:
                    res.append((t, horas, x, float(a + b >= C.UMBRAL_MM)))
    return noms, res


def seguretat(p_nou, p_base, y, dies, rng):
    """Proporción de remuestreos por días en que el nuevo se equivoca menos
    (la regla común, remostreig; rng, por compatibilidad con las cifras
    guardadas: la semilla 97)."""
    return R.seguretat((p_nou - y) ** 2, (p_base - y) ** 2, dies, llavor=97)


def desviacio(f):
    """El desvío medio entre lo dado y lo que llovió, ponderado por horas
    (error de calibración esperado)."""
    n = sum(t["hores"] for t in f)
    return round(sum(t["hores"] * abs(t["donada"] - t["va_ploure"]) for t in f) / n, 4)


def main():
    amb_meteocat = bool(avisos_meteocat())
    noms, ms = muestras(amb_meteocat)
    t = np.array([m[0] for m in ms])
    horas = np.array([m[1] for m in ms])
    x = np.array([m[2] for m in ms])
    base = [noms.index(n) for n in A.RASGOS_ARXIU_ECMWF]
    y = np.array([m[3] for m in ms])
    dies = np.array([ti.astimezone(LOCAL).date().toordinal() for ti in t])
    grup = np.array([(ti.isocalendar()[0] * 53 + ti.isocalendar()[1]) % A.SETMANES_VALIDACIO for ti in t])
    p_nou, p_base = creuada(x, y, grup), creuada(x[:, base], y, grup)
    rng = np.random.default_rng(97)

    def brier(p, s):
        return round(float(np.mean((p[s] - y[s]) ** 2)), 5)

    validacio = {"metode": f"validació creuada en {A.SETMANES_VALIDACIO} grups de setmanes, "
                           f"les mateixes mostres amb avisos i sense; {REMOSTREJOS} remostrejos per dies"}
    adoptat = True
    for nom, h in (("curt_termini", 0), ("un_dia_abans", 24)):
        s = horas == h
        b0, b1 = brier(p_base, s), brier(p_nou, s)
        with_avis = s & (x[:, noms.index("avis_aemet")] > 0)
        v = {"des_de": t[s].min().astimezone(LOCAL).date().isoformat(),
             "mostres": int(s.sum()), "hores_pluja": int(y[s].sum()),
             "mostres_amb_avis_aemet": int(with_avis.sum()),
             "va_ploure_amb_avis_aemet": round(float(y[with_avis].mean()), 3) if with_avis.any() else None,
             "error_sense_avisos": b0, "error": b1, "millora_pct": round(100 * (b0 - b1) / b0, 1),
             "seguretat": round(seguretat(p_nou[s], p_base[s], y[s], dies[s], rng), 3),
             "fiabilitat": fiabilitat(p_nou[s], y[s])}
        v["desviacio"] = desviacio(v["fiabilitat"])
        v["desviacio_sense_avisos"] = desviacio(fiabilitat(p_base[s], y[s]))
        if amb_meteocat:
            mc = s & (x[:, noms.index("avis_meteocat")] > 0)
            v["mostres_amb_avis_meteocat"] = int(mc.sum())
            v["va_ploure_amb_avis_meteocat"] = round(float(y[mc].mean()), 3) if mc.any() else None
        v["per_grup_pct"] = [round(100 * (brier(p_base, s & (grup == g)) - brier(p_nou, s & (grup == g)))
                                   / brier(p_base, s & (grup == g)), 1) for g in sorted(set(grup))]
        adoptat = bool(adoptat and v["seguretat"] >= SEGURETAT and v["desviacio"] <= v["desviacio_sense_avisos"])
        validacio[nom] = v
    resultado = {
        "origen": "arxiu", "ecmwf": True, "avisos": True, "meteocat": amb_meteocat, "adoptat": adoptat,
        "des_de": t.min().astimezone(LOCAL).date().isoformat(),
        "fins": t.max().astimezone(LOCAL).date().isoformat(),
        "rasgos": noms, "w": [round(v, 5) for v in A.ajustar(x, y).tolist()],
        "mostres": int(len(y)), "hores_pluja": int(y.sum()),
        "validacio": validacio,
    }
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)
    for nom in ("curt_termini", "un_dia_abans"):
        v = validacio[nom]
        print(f"{nom} (des del {v['des_de']}): {v['mostres']} mostres, {v['hores_pluja']} amb pluja; "
              f"amb avís de l'AEMET {v['mostres_amb_avis_aemet']} (va ploure el {v['va_ploure_amb_avis_aemet']}). "
              f"Error sense avisos {v['error_sense_avisos']}, amb avisos {v['error']} ({v['millora_pct']:+} %), "
              f"guanya en el {100 * v['seguretat']:.1f} % dels remostrejos; per grups {v['per_grup_pct']}")
        if amb_meteocat:
            print(f"  amb avís de Meteocat {v['mostres_amb_avis_meteocat']} (va ploure el {v['va_ploure_amb_avis_meteocat']})")
        print(f"  desviació {v['desviacio']} (sense avisos {v['desviacio_sense_avisos']}); fiabilitat", " ".join(f"{100 * f['donada']:.0f}→{100 * f['va_ploure']:.0f} ({f['hores']})"
                                       for f in v["fiabilitat"]))
    print("Pesos dels avisos:", {n: w for n, w in zip(noms, resultado["w"]) if n.startswith("avis")})
    print("Adoptat:", adoptat)


if __name__ == "__main__":
    main()
