#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""¿A qué hora para la lluvia que está cayendo? (ADR 0049)

El radar llevado hacia delante (nowcast.py) da, cada 5 minutos y hasta 2
horas, dos series para casa: la probabilidad de lluvia (prob, la fracción con
lluvia de un círculo que crece con el tiempo) y el borde de atrás (vora, la
de un círculo fijo de 2 km en el punto de donde vendrá; desde la 3.223.0).
El final previsto es el primer momento, desde la pasada, en que la serie de
la regla baja de un umbral durante unos minutos seguidos; si no lo hace en
el horizonte, «no s'acaba en 2 hores». La página lo enseña «en entrenament»
con prob; vora se apunta en paralelo y solo pasa a la página si gana
(MIN_EPISODIS_VORA).

El final real no es la última gota: la llovizna de cola (CUA_MM o menos en
total hasta el final del episodio) ya no cuenta (Juanjo, 14-11-2026: de 55
finales «demasiado pronto», en 15 lo que seguía cayendo era medio milímetro o
menos).

Aprende sola: cada día prueba las VARIANTS con lo registrado. Para no
elegir y medir con los mismos episodios (con pocos y nueve combinaciones, la
elegida podía ganar por azar; auditoría del 09-10-2026), el error que cuenta
es el de «elegir la mejor»: para cada episodio, la variante que menos se
equivoca en los demás, juzgada solo en ese (error_validat). Si ese error es
al menos un 5 % menor que el de la regla en uso (con MIN_EPISODIS_CANVI
episodios o más), se propone la mejor con todos los episodios, se dice a
Juanjo y se aplica al día siguiente, como el aprendizaje de la lluvia
(aprenentatge.py); el archivo «atura» lo para. Se guarda en
aprenentatge/fi-pluja.json; la propuesta, en fi-pluja-proposat.json.

Aquí se compara con la lluvia del barrio cada 5 minutos (ADR 0102): la de
la estación de casa (estacio-casa-5min.csv) y la de las vecinas
(veines-5min.csv, registre.py), con la regla única de
aprenentatge.pluja_observada: llueve si lo marca casa o dos vecinas que
cuentan; seco si casa y las vecinas que confirman marcan cero; si no, no se
sabe y el tramo no cuenta. Hasta la 3.142.0 solo contaba el pluviómetro de
casa, que a veces no marca la lluvia débil (ADR 0017) y daba finales antes
de tiempo. Episodios con lluvia separados por menos de BUIT_MIN minutos; su
final, el último tramo con lluvia. Se juzgan
las pasadas registradas mientras llovía (radar-fonts-*.jsonl, con el radar
que usaba la página). El día en que hay MIN_EPISODIS episodios, el NAS manda
el resultado a Juanjo una vez, para decidir si se muestra.

Uso:
  python3 fi_pluja.py resum     el resultado con lo que hay ahora
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import subprocess
import sys

import hora as H
import remostreig as R

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
APRENENTATGE = os.environ.get("APRENENTATGE_DIR", "/estat/aprenentatge")
AVIS = os.path.join(APRENENTATGE, "avis-fi-pluja")
AVIS_VORA = os.path.join(APRENENTATGE, "avis-fi-pluja-vora")
REGLA = os.path.join(APRENENTATGE, "fi-pluja.json")
PROPOSAT = os.path.join(APRENENTATGE, "fi-pluja-proposat.json")
ATURA = os.path.join(APRENENTATGE, "atura")
PER_DEFECTE = {"metode": "prob", "llindar": 0.2, "passos": 3}       # 20 %, 15 minutos
METODES = ("prob", "vora")
VARIANTS = ([{"metode": "prob", "llindar": l, "passos": p} for l in (0.1, 0.2, 0.3) for p in (2, 3, 4)]
            + [{"metode": "vora", "llindar": l, "passos": p} for l in (0.3, 0.5, 0.7) for p in (3, 4, 6)])
MIN_EPISODIS_CANVI = 3
# El borde de atrás entra en la comparación con este número de episodios con
# vora apuntado, y entonces todas las variantes se miden con las mismas
# pasadas (las que lo tienen).
MIN_EPISODIS_VORA = 10
CUA_MM = 0.5            # llovizna de cola: lo que cae después ya no es «llover»
# Cuánto tiene que mejorar la regla elegida lo decide la regla común
# (remostreig: gana en el 95 % de los remuestreos por episodios; ADR 0105).
# Hasta la 3.144.0, un 5 % menos de error (MILLORA = 0.95).
PAS_MIN = 5
BUIT_MIN = 30           # una pausa más corta no acaba el episodio
MIN_EPISODIS = 5
ENCERT_MIN = 15         # acierto: a 15 minutos o menos del final real


def _llegeix(nom):
    ruta = os.path.join(DIR, nom)
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pluja_5min():
    """{fin del tramo: mm} del barrio: la regla única (aprenentatge.pluja_observada,
    ADR 0102) con la estación de casa y las vecinas de cada tramo de 5
    minutos; None si no se sabe (una sola vecina con lluvia y casa a cero,
    o casa a cero sin vecina que lo confirme)."""
    import aprenentatge as A
    # Les claus, en UTC també les d'abans de la migració (ADR 0128).
    casa = {H.clau(r["fins"]): r for r in _llegeix("estacio-casa-5min.csv")}
    veines = {H.clau(r["fins"]): r for r in _llegeix("veines-5min.csv")}
    res = {}
    for fins in set(casa) | set(veines):
        v = {k: {"pluja_mm": x} for k, x in veines.get(fins, {}).items() if k != "fins" and x not in ("", None)}
        res[H.utc(fins)] = A.pluja_observada(casa.get(fins), (), v, llindar=0.1)
    return res


def episodis(pluja):
    """[[inicio, final]] con los tramos con lluvia; una pausa de menos de
    BUIT_MIN minutos no corta el episodio. El último, si aún podría seguir
    (sin BUIT_MIN minutos registrados después), no cuenta. Un tramo del que
    no se sabe (None) ni corta ni alarga. El final, sin la llovizna de cola
    (final_real)."""
    res = []
    for t in sorted(t for t, mm in pluja.items() if mm):
        if res and t - res[-1][1] <= dt.timedelta(minutes=BUIT_MIN):
            res[-1][1] = t
        else:
            res.append([t - dt.timedelta(minutes=PAS_MIN), t])
    if res and (not pluja or max(pluja) - res[-1][1] < dt.timedelta(minutes=BUIT_MIN)):
        res.pop()
    return [[ini, final_real(pluja, ini, fi)] for ini, fi in res]


def final_real(pluja, ini, fi):
    """El último tramo del episodio después del cual cae CUA_MM o menos: lo
    que queda es llovizna de cola y ya no cuenta como lluvia."""
    trams = sorted((t, mm) for t, mm in pluja.items() if mm and ini < t <= fi)
    cua = sum(mm for _, mm in trams)
    for t, mm in trams:
        cua -= mm
        if cua <= CUA_MM + 1e-9:
            return t
    return fi


def regla():
    """La regla en uso; las de antes de la 3.223.0 no dicen el método: prob."""
    try:
        with open(REGLA, encoding="utf-8") as f:
            r = json.load(f)
        return {"metode": r.get("metode", "prob") if r.get("metode") in METODES else "prob",
                "llindar": r["llindar"], "passos": r["passos"]}
    except (OSError, ValueError, KeyError):
        return dict(PER_DEFECTE)


def nom_regla(r):
    """«menys del 30 % durant 10 minuts», con el método si es el borde de atrás."""
    t = f"menys del {round(r['llindar'] * 100)} % durant {r['passos'] * PAS_MIN} minuts"
    return t + " a la vora de darrere de la pluja" if r.get("metode") == "vora" else t


def fi_previst(t0, prob, des_de, r=None):
    """Primer momento desde des_de en que la probabilidad baja del umbral
    durante los pasos seguidos de la regla r; None si no pasa en el horizonte."""
    r = r or regla()
    for k in range(len(prob)):
        tk = t0 + dt.timedelta(minutes=PAS_MIN * k)
        tram = prob[k:k + r["passos"]]
        if tk >= des_de and len(tram) == r["passos"] and all(p < r["llindar"] for p in tram):
            return tk
    return None


def fi_radar(nc, ahora, arriba=None):
    """Para la página: {fi: hora o None, sense_fi: si no se ve el final en el
    horizonte}, desde ahora o desde que llegue la lluvia. None sin radar."""
    serie = ((nc or {}).get("llocs") or {}).get("casa")
    if not serie:
        return None
    t0 = H.llegeix(nc["hora"])
    des_de = max(ahora, H.llegeix(arriba)) if arriba else ahora
    r = regla()
    # Un nowcast sin vora (de antes de la 3.223.0), con prob.
    clau = r["metode"] if all(r["metode"] in p for p in serie) else "prob"
    fi = fi_previst(t0, [p[clau] for p in serie], des_de, r)
    return {"fi": fi and H.clau(fi), "sense_fi": fi is None}


def passades():
    res = []
    for ruta in sorted(glob.glob(os.path.join(DIR, "radar-fonts-*.jsonl"))):
        with open(ruta, encoding="utf-8") as f:
            res += [json.loads(l) for l in f if l.strip()]
    return res


def compara(pluja, regs, r=None):
    """Para cada pasada durante un episodio: el final real, el previsto con
    la regla r (o None) y el horizonte del radar. Las pasadas sin la serie
    del método de r (vora, antes de la 3.223.0) no cuentan."""
    r = r or regla()
    clau = r.get("metode", "prob")
    eps = episodis(pluja)
    res = []
    for reg in regs:
        t = H.llegeix(reg["t"])
        ep = next((e for e in eps if e[0] <= t <= e[1]), None)
        f = (reg.get("fonts") or {}).get(reg.get("triada"))
        if not ep or not f or not f.get(clau):
            continue
        t0 = H.llegeix(f["hora"])
        res.append({"t": t, "episodi": ep[0], "real": ep[1], "previst": fi_previst(t0, f[clau], t, r),
                    "horitzo": t0 + dt.timedelta(minutes=PAS_MIN * (len(f[clau]) - 1))})
    return res, len(eps)


def amb_vora(reg):
    f = (reg.get("fonts") or {}).get(reg.get("triada")) or {}
    return bool(f.get("vora"))


def candidats(pluja, regs):
    """Las variantes que se comparan y con qué pasadas: el borde de atrás,
    con MIN_EPISODIS_VORA episodios con vora apuntado, y entonces todas con
    esas pasadas; si no, solo las de prob, con todas."""
    comuns = [g for g in regs if amb_vora(g)]
    n = len({e[0] for e in episodis(pluja) for g in comuns if e[0] <= H.llegeix(g["t"]) <= e[1]})
    if n >= MIN_EPISODIS_VORA or regla()["metode"] == "vora":
        return VARIANTS, comuns
    return [v for v in VARIANTS if v["metode"] == "prob"], regs


def resultat(casos, n_episodis):
    """Las cifras para decidir."""
    amb = [c for c in casos if c["previst"]]
    errors = [(c["previst"] - c["real"]).total_seconds() / 60 for c in amb]
    sense = [c for c in casos if not c["previst"]]
    return {"episodis": n_episodis, "passades": len(casos), "amb_final": len(amb),
            "encerts": sum(abs(e) <= ENCERT_MIN for e in errors),
            "massa_aviat": sum(e < -ENCERT_MIN for e in errors), "massa_tard": sum(e > ENCERT_MIN for e in errors),
            "error_mitja": round(sum(abs(e) for e in errors) / len(errors)) if errors else None,
            "sense_final": len(sense), "sense_final_be": sum(c["real"] > c["horitzo"] for c in sense)}


def errors_casos(casos):
    """Error en minutos de cada caso: con hora de final, la distancia al final
    real; sin ella, nada si de verdad acababa más allá del radar y, si no,
    lo que faltaba hasta el horizonte."""
    return [abs((c["previst"] - c["real"]).total_seconds()) / 60 if c["previst"]
            else max(0.0, (c["horitzo"] - c["real"]).total_seconds() / 60) for c in casos]


def error(casos):
    """Error medio en minutos de una regla."""
    return sum(errors_casos(casos)) / len(casos) if casos else None


def errors_per_cas(pluja, regs, actual=None, variants=None):
    """El error honesto de «elegir la mejor variante»: para cada episodio, la
    variante que menos se equivoca en los demás, juzgada solo en ese
    (validación dejando un episodio fuera). Por caso, (episodio, error de la
    variante elegida, error de la regla actual), para compararlos por
    episodios (remostreig, ADR 0105). Hasta la auditoría del 09-10-2026 la
    variante se elegía y se medía con los mismos episodios."""
    variants = variants or [v for v in VARIANTS if v["metode"] == "prob"]
    per_variant = [compara(pluja, regs, v)[0] for v in variants]
    casos_actual = compara(pluja, regs, actual or regla())[0]
    res = []
    for ep in episodis(pluja):
        fora = [[c for c in casos if c["episodi"] != ep[0]] for casos in per_variant]
        if not fora[0]:
            continue
        k = min(range(len(variants)), key=lambda k: error(fora[k]))
        # Los mismos casos (pasadas) en el mismo orden con las dos reglas.
        triada = errors_casos([c for c in per_variant[k] if c["episodi"] == ep[0]])
        amb_actual = errors_casos([c for c in casos_actual if c["episodi"] == ep[0]])
        res += [(ep[0].isoformat(), e, a) for e, a in zip(triada, amb_actual)]
    return res


def error_validat(pluja, regs):
    """La media del error de elegir la mejor variante, por casos."""
    variants, regs = candidats(pluja, regs)
    errors = [e for _, e, _ in errors_per_cas(pluja, regs, variants=variants)]
    return sum(errors) / len(errors) if errors else None


def llegeix_proposta():
    try:
        with open(PROPOSAT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def aplica_proposta(avui=None):
    """Una propuesta de un día anterior que nadie ha parado pasa a ser la
    regla (como las del aprendizaje de la lluvia). Devuelve qué ha hecho."""
    avui = avui or H.dia_local(H.ara()).isoformat()
    p = llegeix_proposta()
    if not p:
        return None
    if os.path.exists(ATURA):
        os.remove(PROPOSAT)
        return "Final de la pluja: proposta aturada, no s'aplica."
    if p["dia"] >= avui:
        return None
    with open(REGLA + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"metode": p.get("metode", "prob"), "llindar": p["llindar"], "passos": p["passos"],
                   "error_min": p["error_min"], "episodis": p["episodis"], "des_de": avui}, f)
    os.replace(REGLA + ".tmp", REGLA)
    os.remove(PROPOSAT)
    return f"Final de la pluja: aplicada la proposta d'ahir, {nom_regla({'metode': 'prob', **p})}."


def aprèn(pluja, regs, avisa=True, avui=None):
    """Prueba las variantes y, si elegir la mejor se equivoca bastante menos
    que la regla en uso en episodios que no han servido para elegirla, la
    propone para el día siguiente."""
    avui = avui or H.dia_local(H.ara()).isoformat()
    eps = episodis(pluja)
    if len(eps) < MIN_EPISODIS_CANVI or os.path.exists(ATURA):
        return None
    actual = regla()
    variants, regs = candidats(pluja, regs)
    err_actual = error(compara(pluja, regs, actual)[0])
    millor = min(variants, key=lambda v: error(compara(pluja, regs, v)[0]) if compara(pluja, regs, v)[0] else math.inf)
    casos = errors_per_cas(pluja, regs, actual, variants)
    err_validat = sum(e for _, e, _ in casos) / len(casos) if casos else None
    # Gana si se equivoca menos en el 95 % de los remuestreos por episodios.
    seguretat = R.seguretat([e for _, e, _ in casos], [a for _, _, a in casos], [ep for ep, _, _ in casos])
    if millor == actual or err_actual is None or err_validat is None or not R.guanya(seguretat):
        return None
    p = llegeix_proposta()
    if p and (p.get("metode", "prob"), p["llindar"], p["passos"]) == (millor["metode"], millor["llindar"], millor["passos"]):
        return None            # ya propuesta: se aplicará mañana
    os.makedirs(APRENENTATGE, exist_ok=True)
    with open(PROPOSAT + ".tmp", "w", encoding="utf-8") as f:
        json.dump({**millor, "error_min": round(err_validat, 1), "error_abans": round(err_actual, 1),
                   "seguretat": seguretat, "episodis": len(eps), "dia": avui}, f)
    os.replace(PROPOSAT + ".tmp", PROPOSAT)
    t = (f"Temps a Montflorit, final de la pluja segons el radar: proposta de donar-la per acabada amb "
         f"{nom_regla(millor)} (ara, {nom_regla(actual)}). Error mitjà en episodis no usats per "
         f"triar-la: {err_validat:.0f} minuts, amb la regla actual {err_actual:.0f} ({len(eps)} episodis; "
         f"guanya en el {round(100 * seguretat)} % dels remostrejos per episodis). "
         "S'aplicarà demà; per aturar-ho, demana-ho a Claude abans.")
    if avisa:
        subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", t], check=False)
    return t


def text(r):
    return (f"Temps a Montflorit, final de la pluja segons el radar: ja hi ha {r['episodis']} episodis de pluja "
            f"amb dades cada 5 minuts ({r['passades']} passades mentre plovia). "
            f"Quan donava una hora de final ({r['amb_final']} vegades): {r['encerts']} a {ENCERT_MIN} minuts o menys, "
            f"{r['massa_aviat']} massa aviat i {r['massa_tard']} massa tard; error mitjà de {r['error_mitja']} minuts. "
            f"Quan deia que no s'acabava en 2 hores ({r['sense_final']}), ho encertava {r['sense_final_be']}. "
            "Es mostra a la pàgina «en entrenament»: digues a Claude si cal treure-ho o si ja no cal dir-ho (ADR 0049).")


def verifica(avisa=True, avui=None):
    """Cada día (aprenentatge.py diari): aplica la propuesta de ayer, propone
    la de hoy si la hay y, con MIN_EPISODIS episodios, manda el resultado a
    Juanjo, una sola vez. Devuelve lo que ha hecho, en texto."""
    pluja, regs = pluja_5min(), passades()
    fets = [aplica_proposta(avui), aprèn(pluja, regs, avisa, avui)]
    if not os.path.exists(AVIS):
        casos, n = compara(pluja, regs)
        if n >= MIN_EPISODIS:
            t = text(resultat(casos, n))
            if avisa:
                subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", t], check=False)
            os.makedirs(APRENENTATGE, exist_ok=True)
            open(AVIS, "w").close()
            fets.append(t)
    # Con MIN_EPISODIS_VORA episodios con el borde de atrás, cómo ha ido, una
    # vez: si gana, aprèn ya lo ha propuesto; si no, para decidir qué hacer.
    if not os.path.exists(AVIS_VORA):
        variants, _ = candidats(pluja, regs)
        if any(v["metode"] == "vora" for v in variants):
            t = "Temps a Montflorit, final de la pluja: " + text_vora(pluja, regs)
            if avisa:
                subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit", "--asunto", "meteo-local", t], check=False)
            os.makedirs(APRENENTATGE, exist_ok=True)
            open(AVIS_VORA, "w").close()
            fets.append(t)
    return "\n".join(f for f in fets if f) or None


def text_vora(pluja, regs):
    """Cómo va el borde de atrás, apuntado en paralelo: con las mismas
    pasadas, la regla en uso y la mejor variante de vora (elegida con esas
    mismas pasadas: orientativo; la comparación que decide es la de aprèn)."""
    comuns = [g for g in regs if amb_vora(g)]
    casos, _ = compara(pluja, comuns, regla())
    if not casos:
        return "Vora de darrere de la pluja (en paral·lel): encara cap passada mentre plovia."
    n = len({c["episodi"] for c in casos})
    millor = min((v for v in VARIANTS if v["metode"] == "vora"), key=lambda v: error(compara(pluja, comuns, v)[0]))
    rv = resultat(compara(pluja, comuns, millor)[0], n)
    ra = resultat(casos, n)
    return (f"Vora de darrere de la pluja (en paral·lel, {n} episodis i {ra['passades']} passades; decideix amb "
            f"{MIN_EPISODIS_VORA}): amb la regla d'ara, {ra['encerts']} encerts a {ENCERT_MIN} minuts i error "
            f"{error(casos):.0f} minuts; la millor vora ({nom_regla(millor)}), {rv['encerts']} encerts i error "
            f"{error(compara(pluja, comuns, millor)[0]):.0f}.")


if __name__ == "__main__":
    if sys.argv[1:] == ["resum"]:
        pluja, regs = pluja_5min(), passades()
        casos, n = compara(pluja, regs)
        print(text(resultat(casos, n)) if casos else f"Encara no hi ha cap passada mentre plovia ({n} episodis).")
        print(text_vora(pluja, regs))
    else:
        print(__doc__)
