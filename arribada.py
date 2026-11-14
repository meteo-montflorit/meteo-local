#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""¿Llega la lluvia a la hora que dice el radar? (ADR 0022)

El radar llevado hacia delante (nowcast.arribada) da la hora en que la
lluvia llegaría a casa, y la página la enseña cuando faltan FINS_MIN minutos
o menos. Aquí se mide, con la lluvia del barrio cada 5 minutos (la misma
verdad que el final de la lluvia, fi_pluja.pluja_5min, ADR 0102), cuánto se
adelanta o se retrasa esa hora, y se corrige si hace falta.

Un caso es una pasada sin lluvia en la que el radar daba la llegada entre
DE_MIN y FINS_MIN minutos después (radar-fonts-*.jsonl, con el radar que
usaba la página) y empezó a llover a MARGE_MIN minutos o menos de esa hora;
su error, los minutos entre el comienzo real y el previsto (positivo: llegó
más tarde). Los casos de un mismo comienzo de lluvia se parecen: van juntos.

Aprende sola, como el final de la lluvia: cada día prueba los RETARDS y,
para no elegir y medir con los mismos comienzos, a cada uno le aplica el
retraso que menos se equivoca en los demás. Si eso se equivoca menos que el
retraso en uso en el 95 % de los remuestreos por comienzos (remostreig, ADR
0105), con MIN_INICIS comienzos o más, lo propone, se lo dice a Juanjo y se
aplica al día siguiente; el archivo «atura» lo para. Se guarda en
aprenentatge/arribada.json; la propuesta, en arribada-proposat.json.

El 14-11-2026, con 12 comienzos, el error mediano era de 0 minutos: no se
corrige nada. Los 18 minutos de retraso que daba el registro de los avisos
(pluja_arriba.py) salían de mirar la lluvia solo en cada pasada y de los
avisos con el radar ya encima, que no dan hora.

Uso:
  python3 arribada.py resum     lo medido con lo que hay ahora
"""
import bisect
import datetime as dt
import json
import os
import statistics
import subprocess
import sys

import hora as H
import remostreig as R

APRENENTATGE = os.environ.get("APRENENTATGE_DIR", "/estat/aprenentatge")
REGLA = os.path.join(APRENENTATGE, "arribada.json")
PROPOSAT = os.path.join(APRENENTATGE, "arribada-proposat.json")
ATURA = os.path.join(APRENENTATGE, "atura")
RETARDS = (-10, -5, 0, 5, 10, 15, 20)     # minutos que se suman a la hora del radar
PROB = 0.5              # la llegada: la mitad del círculo con lluvia (nowcast.arribada)
DE_MIN, FINS_MIN = 5, 30    # antelaciones con hora en la página (más cerca, «a sobre»; más lejos, sin hora)
MARGE_MIN = 45          # el comienzo real, a esto o menos de la hora prevista
SEC_MIN = 20            # sin lluvia medida en estos minutos: aún no llueve
MIN_INICIS = 10
PAS = dt.timedelta(minutes=5)


def retard():
    """Los minutos que se suman a la hora del radar; 0 sin regla."""
    try:
        with open(REGLA, encoding="utf-8") as f:
            r = json.load(f)["retard_min"]
        return r if r in RETARDS else 0
    except (OSError, ValueError, KeyError):
        return 0


def corregeix(t, ahora):
    """La hora de llegada t con el retraso aprendido. Si el radar ya la da
    encima (a DE_MIN minutos o menos), tal cual: eso no es una hora, es
    «pluja a sobre»."""
    r = retard()
    if not t or not r or t - ahora <= dt.timedelta(minutes=DE_MIN):
        return t
    return max(t + dt.timedelta(minutes=r), ahora + dt.timedelta(minutes=DE_MIN + 1))


def casos(pluja, regs):
    """[(comienzo real, error en minutos)] de cada pasada que cuenta."""
    plou = sorted(t for t, mm in pluja.items() if mm)        # final de cada tramo con lluvia
    res = []
    for reg in regs:
        t = H.llegeix(reg["t"])
        f = (reg.get("fonts") or {}).get(reg.get("triada"))
        if not f:
            continue
        i = bisect.bisect_right(plou, t - dt.timedelta(minutes=SEC_MIN))
        if i < len(plou) and plou[i] <= t + PAS:
            continue                                          # ya llovía
        t0 = H.llegeix(f["hora"])
        previst = next((t0 + PAS * k for k, p in enumerate(f["prob"]) if p >= PROB), None)
        if previst is None or not DE_MIN < (previst - t).total_seconds() / 60 <= FINS_MIN:
            continue
        if i == len(plou):
            continue
        real = plou[i] - PAS
        error = (real - previst).total_seconds() / 60
        if abs(error) <= MARGE_MIN:
            res.append((H.clau(real), error))
    return res


def error(cs, r):
    """Error medio en minutos con el retraso r."""
    return sum(abs(e - r) for _, e in cs) / len(cs) if cs else None


def validats(cs, actual):
    """Por caso, (comienzo, error con el retraso elegido sin ese comienzo,
    error con el retraso en uso)."""
    res = []
    for inici in sorted({i for i, _ in cs}):
        fora = [c for c in cs if c[0] != inici]
        if not fora:
            continue
        r = min(RETARDS, key=lambda r: (error(fora, r), abs(r)))
        res += [(inici, abs(e - r), abs(e - actual)) for i, e in cs if i == inici]
    return res


def llegeix_proposta():
    try:
        with open(PROPOSAT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def aplica_proposta(avui=None):
    """Una propuesta de un día anterior que nadie ha parado pasa a ser la
    regla. Devuelve qué ha hecho."""
    avui = avui or H.dia_local(H.ara()).isoformat()
    p = llegeix_proposta()
    if not p:
        return None
    if os.path.exists(ATURA):
        os.remove(PROPOSAT)
        return "Arribada de la pluja: proposta aturada, no s'aplica."
    if p["dia"] >= avui:
        return None
    with open(REGLA + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"retard_min": p["retard_min"], "error_min": p["error_min"], "inicis": p["inicis"],
                   "des_de": avui}, f)
    os.replace(REGLA + ".tmp", REGLA)
    os.remove(PROPOSAT)
    return f"Arribada de la pluja: aplicada la proposta d'ahir, {text_retard(p['retard_min'])}."


def text_retard(r):
    return ("l'hora del radar, tal qual" if not r
            else f"{abs(r)} minuts {'més tard' if r > 0 else 'abans'} que l'hora del radar")


def aprèn(pluja, regs, avisa=True, avui=None):
    """Propone el retraso que menos se equivoca si gana al que hay en
    comienzos que no han servido para elegirlo."""
    avui = avui or H.dia_local(H.ara()).isoformat()
    cs = casos(pluja, regs)
    inicis = len({i for i, _ in cs})
    if inicis < MIN_INICIS or os.path.exists(ATURA):
        return None
    actual = retard()
    millor = min(RETARDS, key=lambda r: (error(cs, r), abs(r)))
    v = validats(cs, actual)
    seguretat = R.seguretat([n for _, n, _ in v], [a for _, _, a in v], [i for i, _, _ in v])
    if millor == actual or not R.guanya(seguretat):
        return None
    p = llegeix_proposta()
    if p and p["retard_min"] == millor:
        return None             # ya propuesta: se aplicará mañana
    err_validat = sum(n for _, n, _ in v) / len(v)
    os.makedirs(APRENENTATGE, exist_ok=True)
    with open(PROPOSAT + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"retard_min": millor, "error_min": round(err_validat, 1), "error_abans": round(error(cs, actual), 1),
                   "seguretat": seguretat, "inicis": inicis, "dia": avui}, f)
    os.replace(PROPOSAT + ".tmp", PROPOSAT)
    t = (f"Temps a Montflorit, arribada de la pluja segons el radar: proposta de dir-la {text_retard(millor)} "
         f"(ara, {text_retard(actual)}). Error mitjà en inicis de pluja no usats per triar-ho: {err_validat:.0f} "
         f"minuts, amb el d'ara {error(cs, actual):.0f} ({inicis} inicis; guanya en el {round(100 * seguretat)} % "
         "dels remostrejos per inicis). S'aplicarà demà; per aturar-ho, demana-ho a Claude abans.")
    if avisa:
        subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", t], check=False)
    return t


def verifica(avisa=True, avui=None):
    """Cada día (aprenentatge.py diari): aplica la propuesta de ayer y
    propone la de hoy si la hay. Devuelve lo que ha hecho, en texto."""
    import fi_pluja as F
    fets = [aplica_proposta(avui), aprèn(F.pluja_5min(), F.passades(), avisa, avui)]
    return "\n".join(f for f in fets if f) or None


def resum():
    import fi_pluja as F
    cs = casos(F.pluja_5min(), F.passades())
    if not cs:
        return "Arribada de la pluja: encara cap passada amb l'hora a la vista i pluja després."
    per_inici = {}
    for i, e in cs:
        per_inici.setdefault(i, []).append(e)
    medianes = sorted(round(statistics.median(v)) for v in per_inici.values())
    actual = retard()
    return (f"Arribada de la pluja segons el radar, quan en donava l'hora (de {DE_MIN} a {FINS_MIN} minuts vista): "
            f"{len(cs)} passades de {len(per_inici)} inicis de pluja. Retard (real menys previst): mediana "
            f"{statistics.median(e for _, e in cs):.0f} minuts; per inici, {medianes}. A {15} minuts o menys de "
            f"l'hora dita, {sum(abs(e - actual) <= 15 for _, e in cs)}. Ara es diu {text_retard(actual)}; error mitjà "
            f"{error(cs, actual):.0f} minuts (decideix amb {MIN_INICIS} inicis).")


if __name__ == "__main__":
    if sys.argv[1:] == ["resum"]:
        print(resum())
    else:
        print(__doc__)
