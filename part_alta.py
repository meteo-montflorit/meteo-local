#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La parte alta del barrio, más cálida que la riera (ADR 0087).

La estación de casa está junto a la riera (carrer Canaletes), en la zona más
fría del barrio, como ICERDA6; ICERDA18, ICERDA28 e ICERDA48 están en la
parte alta (config.VEINES, «alta»). Juanjo, 13-10-2026: las temperaturas son
las de la riera, y para el resto hay que sumar «1, 2... grados, dependiendo
del momento y del frío, porque a veces no habrá diferencias, pero otras sí».

- **Ahora** (`ara`): la mediana de las vecinas de arriba leídas en la última
  media hora menos la temperatura de «Ara». Es una medida.
- **Previsión** (`per_hores`): para cada hora del día, la mediana de (parte
  alta − casa) en los últimos DIES días del registro, sin las horas con sol
  directo sobre el termómetro (ADR 0081). Si una hora tiene menos de
  MIN_MOSTRES, la de partida, calculada con el verano y el otoño de 2026
  (calibracio/part_alta.json). Así sigue la época del año sola.

Las horas del día son las solares (`prevision.hora_solar`, ADR 0090), no las
del reloj: la diferencia la marcan el sol y el aire que se calienta, que no
cambian con la hora oficial. Con las del reloj, el mes siguiente a cada
cambio de hora (ADR 0089) se mezclaban dos horas de sol distintas.
"""
import datetime as dt
import json
import os
import statistics

import config as C
import hora as H
import prevision as P
import sol_estacio as SE

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
INICIAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibracio", "part_alta.json")
ALTES = [e for e, v in C.VEINES.items() if v.get("alta")]
DIES = 30
MIN_MOSTRES = 10
ALTES_MIN = 2           # vecinas de arriba con dato para dar la diferencia
FRESCA_MIN = 30
hora_solar = P.hora_solar


def mediana_alta(temperatures):
    ts = [t for t in temperatures if t is not None]
    return statistics.median(ts) if len(ts) >= ALTES_MIN else None


def ara(temperatura, veines, ahora):
    """Grados que tiene de más la parte alta ahora mismo (o None)."""
    if temperatura is None:
        return None
    fresques = [v.get("temperatura") for v in veines or [] if v.get("estacio") in ALTES and v.get("hora")
                and ahora - H.llegeix(v["hora"]) <= dt.timedelta(minutes=FRESCA_MIN)]
    m = mediana_alta(fresques)
    return None if m is None else round(m - temperatura, 1)


def mesurada(ahora, hores=72, veines_hores=None):
    """La temperatura medida en la parte alta a cada hora en punto de las
    últimas horas ({"AAAA-MM-DDTHH:MM" local: °C}): la mediana de las vecinas
    de arriba, con ALTES_MIN como mínimo. Para comparar con ayer cuando se
    mira la parte alta (ADR 0123), como temperatura_mesurada para la riera."""
    if veines_hores is None:
        veines_hores = {e: SE._llegeix_hores(os.path.join(DIR, f"veina-{e}.csv")) for e in ALTES}
    desde = H.clau(ahora - dt.timedelta(hours=hores))
    claus = sorted({c for h in veines_hores.values() for c in h if c >= desde}, key=P.ordre_hora)
    res = {c: mediana_alta([veines_hores.get(e, {}).get(c) for e in ALTES]) for c in claus}
    return {c: round(v, 1) for c, v in res.items() if v is not None}


def inicial():
    try:
        with open(INICIAL, encoding="utf-8") as f:
            return {int(h): v for h, v in json.load(f)["per_hora_utc"].items()}
    except (OSError, ValueError, KeyError):
        return {}


def per_hores(ahora, casa_hores=None, veines_hores=None, eps=None):
    """{hora del día en tiempo universal: grados que tiene de más la parte alta}."""
    if casa_hores is None:
        casa_hores = SE._llegeix_hores(os.path.join(DIR, "estacio-casa.csv"))
    if veines_hores is None:
        veines_hores = {e: SE._llegeix_hores(os.path.join(DIR, f"veina-{e}.csv")) for e in ALTES}
    desde = H.clau(ahora - dt.timedelta(days=DIES))
    claus = [c for c in casa_hores if c >= desde and casa_hores[c] is not None]
    fora = SE.hores_tocades(claus, eps)
    mostres = {}
    for c in claus:
        if c in fora:
            continue
        m = mediana_alta([veines_hores.get(e, {}).get(c) for e in ALTES])
        if m is not None:
            mostres.setdefault(hora_solar(c), []).append(m - casa_hores[c])
    res = inicial()
    for h, ds in mostres.items():
        if len(ds) >= MIN_MOSTRES:
            res[h] = round(statistics.median(ds), 1)
    return res


def ajust_nit():
    """Los coeficientes del ajuste de las noches (calibracio/part_alta.json,
    «ajust_nit»), o None."""
    try:
        with open(INICIAL, encoding="utf-8") as f:
            a = json.load(f)["ajust_nit"]
        return {"hores": set(a["hores_utc"]), "coef": a["coef"]}
    except (OSError, ValueError, KeyError):
        return None


def correccio_nit(f, ajust):
    """Lo que la noche de la fila suma a la mediana de 30 días (Juanjo,
    19-10-2026: «sí, adóptalo y vigílalo este invierno»). Con el cielo
    despejado y en calma, la inversión deja la riera unos 2 °C por debajo de
    la parte alta y la mediana, que mezcla todo tipo de noches, da 1-1,5; con
    nubes o viento el aire se mezcla y casi no cambia. Las nubes, el viento y
    la temperatura, los de la propia fila; sin alguno, 0."""
    n, v, t = f.get("nuvols"), f.get("vent"), f.get("temperatura")
    if not ajust or n is None or v is None or t is None:
        return 0.0
    c, calma = 1 - n / 100, max(0.0, 1 - v / 15)
    return sum(b * x for b, x in zip(ajust["coef"], (1, c, calma, c * calma, min(t, 15))))


def a_les_hores(hores, taula, ajust=None):
    """Pone a cada fila de la previsión «dif_alta»: la de su hora (la
    temperatura de la fila es la media de sus dos extremos) y, en los
    extremos de noche, con el ajuste de las nubes y el viento (ajust_nit);
    «dif_alta_base», sin él, para vigilarlo (registre_nit)."""
    for f in hores or []:
        extrems = [(taula.get(hora_solar(f[k])), hora_solar(f[k])) for k in ("hora", "fins")]
        base = [x for x, _ in extrems if x is not None]
        corr = correccio_nit(f, ajust)
        vals = [x + (corr if ajust and h in ajust["hores"] else 0) for x, h in extrems if x is not None]
        # «+ 0.0»: sense el «-0.0» que deixa round amb una correcció negativa.
        f["dif_alta"] = round(sum(vals) / len(vals), 1) + 0.0 if vals else None
        if ajust and any(h in ajust["hores"] for _, h in extrems):
            f["dif_alta_base"] = round(sum(base) / len(base), 1) if base else None
    return hores


# --- La vigilancia del ajuste de las noches, el invierno 2026-27 -----------
# Juanjo, 19-10-2026: «vigílalo este invierno». El análisis usó ICERDA6 como
# riera y ICON-EU; la web usa la estación de casa, las nubes de cuatro modelos
# y el viento de AROME. Para cada hora de noche se apunta lo que dio la web
# con el ajuste y sin él, la última previsión hecha 3 horas antes o más, y el
# resumen la compara con lo medido (casa y las vecinas de arriba).
REGISTRE_NIT = os.path.join(DIR, "part-alta-nit.csv")
CAMPS_NIT = ["hora", "fins", "emes", "dif_base", "dif_ajust", "nuvols", "vent", "temperatura"]
ANTELACIO_H = 3


def apunta_nit(hores, ahora, ruta=None):
    import csv
    ruta = ruta or REGISTRE_NIT
    files = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            files = {H.clau(r["hora"]): {**r, "hora": H.clau(r["hora"]), "fins": H.clau(r["fins"])}
                     for r in csv.DictReader(f)}
    except OSError:
        pass
    canvi = False
    for f in hores or []:
        if f.get("dif_alta_base") is None or f.get("dif_alta") is None:
            continue
        if H.utc(f["hora"]) - ahora < dt.timedelta(hours=ANTELACIO_H):
            continue
        files[f["hora"]] = {"hora": f["hora"], "fins": f["fins"], "emes": H.clau(ahora),
                            "dif_base": f["dif_alta_base"], "dif_ajust": f["dif_alta"], "nuvols": f.get("nuvols"),
                            "vent": f.get("vent"), "temperatura": f.get("temperatura")}
        canvi = True
    if not canvi:
        return
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".tmp", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPS_NIT)
        w.writeheader()
        w.writerows(files[k] for k in sorted(files))
    os.replace(ruta + ".tmp", ruta)


def resum_nit(ruta=None, casa_hores=None, veines_hores=None):
    """Error medio de la diferencia de la parte alta, con el ajuste y sin él,
    contra la medida (mediana de las vecinas de arriba − casa, media de los dos
    extremos de la fila), en todas las horas de noche y en las de helada junto
    a la riera (casa a 0 °C o menos)."""
    import csv
    ruta = ruta or REGISTRE_NIT
    if casa_hores is None:
        casa_hores = SE._llegeix_hores(os.path.join(DIR, "estacio-casa.csv"))
    if veines_hores is None:
        veines_hores = {e: SE._llegeix_hores(os.path.join(DIR, f"veina-{e}.csv")) for e in ALTES}
    # Totes les claus en UTC, vinguin d'on vinguin (ADR 0128).
    casa_hores = {H.clau(k): v for k, v in casa_hores.items()}
    veines_hores = {e: {H.clau(k): v for k, v in h.items()} for e, h in veines_hores.items()}

    def mesura(c):
        m = mediana_alta([veines_hores.get(e, {}).get(c) for e in ALTES])
        return None if m is None or casa_hores.get(c) is None else m - casa_hores[c]

    try:
        with open(ruta, encoding="utf-8") as f:
            # Les hores, en UTC com les de les estacions, si el registre fos
            # d'abans de la migració (ADR 0128).
            files = [{**f_, "hora": H.clau(f_["hora"]), "fins": H.clau(f_["fins"])} for f_ in csv.DictReader(f)]
    except OSError:
        return "Encara no hi ha registre de les nits."
    grups = {"totes": [], "gelada": []}
    for r in files:
        reals = [mesura(r[k]) for k in ("hora", "fins")]
        if None in reals:
            continue
        real = sum(reals) / 2
        e = (abs(float(r["dif_base"]) - real), abs(float(r["dif_ajust"]) - real))
        grups["totes"].append(e)
        if min(casa_hores[r["hora"]], casa_hores[r["fins"]]) <= 0:
            grups["gelada"].append(e)
    if not grups["totes"]:
        return f"{len(files)} hores de nit apuntades, encara sense mesura per comparar."
    linies = [f"Hores de nit apuntades: {len(files)} (des de {H.dia_local(files[0]['hora'])})."]
    for nom, text in (("totes", "Totes les hores de nit"), ("gelada", "Hores amb la riera a 0 °C o menys")):
        es = grups[nom]
        if es:
            base = sum(a for a, _ in es) / len(es)
            ajust = sum(b for _, b in es) / len(es)
            millor = sum(1 for a, b in es if b < a)
            linies.append(f"{text} ({len(es)}): error {base:.2f} °C sense l'ajust, {ajust:.2f} °C amb l'ajust; "
                          f"l'ajust s'apropa més en {millor} ({100 * millor / len(es):.0f} %).")
        else:
            linies.append(f"{text}: cap encara.")
    return "\n".join(linies)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["nit-resum"]:
        print(resum_nit())
    else:
        print("Ús: python3 part_alta.py nit-resum")

