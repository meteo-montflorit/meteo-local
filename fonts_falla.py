#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Les fonts que fallen, des de quan, i què se'n fa si dura (ADR 0031).

Juanjo, 25-10-2026: «y que pasa si se cae un servicio un dia completo?». Fins
a la 3.204.0, la web deia a cada actualització que no havia arribat i ningú no
se n'assabentava: la S2 va estar dos dies «sense dades» (FGC havia canviat el
fitxer). Ara, a cada passada del NAS (casa.py):

- s'apunta des de quan falla cada font (FITXER, a /estat) i es publica a les
  dades (`fonts_falla`), perquè la web digui «Des de les 12:00 no arriben…»;
- si dura LLINDAR_H hores i l'error és de la xarxa o del servidor (no respon,
  un 500), se li diu una vegada a Juanjo, i una altra quan torna;
- si sembla del programa (la font ha canviat de format: un error en llegir
  el que arriba), es demana al reparador (reparador.py, ADR 0113) que un agent
  ho arregli; si no ho aconsegueix, el reparador avisa Juanjo.

Les que ja tenen el seu avís a Juanjo no es vigilen aquí: Meteocat (smp.py)
i les estacions (estacions.py).

  python3 fonts_falla.py estat
"""
import datetime as dt
import json
import os
import re
import sys

import hora as H

ESTAT_DIR = os.environ.get("ESTAT_DIR", "/estat")
FITXER = os.path.join(ESTAT_DIR, "fonts-falla.json")
LLINDAR_H = 3
# Ja tenen el seu avís a Juanjo.
APART = {"smp", "estació", "estació de casa", "estacions veïnes"}
# Un error de la xarxa o del servidor: no és cosa del programa.
XARXA = re.compile(r"HTTP Error|URLError|urlopen error|timed out|Timeout|timeout|Connection|Temporary failure|"
                   r"Name or service|Network is unreachable|SSL|RemoteDisconnected|IncompleteRead|"
                   r"Service Unavailable|Bad Gateway|Gateway|Too Many Requests|refused|reset by peer", re.I)
# Quina font és i què deixa de sortir, per al missatge a Juanjo (com els textos
# de la web, comu.js TEXT_FONT_FALLA).
QUE = {
    "previsió": ("la previsió dels models (Open-Meteo)", "La web no té previsió hora a hora."),
    "ensemble": ("les 40 variants del model alemany (Open-Meteo)", "La probabilitat de pluja és menys afinada."),
    "vent": ("el vent de Meteocat a Sant Cugat", "No surt el vent mesurat."),
    "radar": ("el radar", "No es pot dir si s'acosta pluja."),
    "final de la pluja": ("el càlcul del final de la pluja", "No es diu quan pararà."),
    "avisos": ("els avisos de l'AEMET (Meteoalarm)", "Només surten els de Meteocat."),
    "plans": ("els plans de Protecció Civil", "Si n'hi hagués un d'activat, no sortiria."),
    "entorn: incendis": ("els incendis dels Bombers", "Si n'hi hagués un a prop, no sortiria."),
    "entorn: pla_alfa": ("el Pla Alfa de Protecció Civil", "No surt el risc d'incendi forestal."),
    "trens": ("l'estat dels trens", "No es diu si hi ha incidències."),
    "trànsit": ("l'estat del trànsit", "No es diu si hi ha incidències a prop."),
    "índex UV": ("l'índex UV", "No surt la protecció solar."),
}


def nom(f):
    return QUE.get(f, (f"la font «{f}»", ""))[0]


def font(error):
    """La font d'un error de casa.json: «avisos», «entorn: incendis»…"""
    parts = error.split(":")
    return ":".join(parts[:2]) if parts[0] == "entorn" and len(parts) > 2 else parts[0]


def es_de_xarxa(error):
    return bool(XARXA.search(error))


def _llegeix(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def text_falla(f, s):
    efecte = QUE.get(f, ("", ""))[1]
    return (f"Temps a Montflorit: falla una font des del {H.local(s['des_de']):%d/%m a les %H:%M}, {nom(f)}. "
            f"{efecte} L'error: {s['error'][:300]}").replace("  ", " ")


def vigila(errors, ahora, envia=None, ruta=None):
    """Apunta des de quan falla cada font i avisa o demana el reparador si dura.
    Torna {font: des_de} de les que fallen ara, per a les dades."""
    ruta = ruta or FITXER
    estat = _llegeix(ruta)
    ara_fallen = {}
    for e in errors or []:
        ara_fallen.setdefault(font(e), e)
    missatges = []
    for f in [f for f in estat if f not in ara_fallen]:
        s = estat.pop(f)
        if s.get("avisat"):
            missatges.append(f"Temps a Montflorit: torna a funcionar una font, {nom(f)}.")
    for f, e in ara_fallen.items():
        s = estat.setdefault(f, {"des_de": H.clau(ahora), "avisat": False})
        s["error"] = e
        if f in APART or s["avisat"] or s.get("reparar"):
            continue
        if ahora - H.llegeix(s["des_de"]) < dt.timedelta(hours=LLINDAR_H):
            continue
        if es_de_xarxa(e):
            s["avisat"] = True
            missatges.append(text_falla(f, s) + " Sembla de la font, no del programa: si dura, caldrà decidir.")
        else:
            # El reparador ho recull (reparador.comprova) i, si no ho arregla, avisa.
            s["reparar"] = True
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(estat, fh, ensure_ascii=False)
    os.replace(ruta + ".tmp", ruta)
    if missatges:
        if envia is None:
            import avis_privat
            envia = avis_privat.envia
        for m in missatges:
            envia(m)
    return {f: estat[f]["des_de"] for f in ara_fallen}


if __name__ == "__main__":
    if sys.argv[1:] == ["estat"]:
        print(json.dumps(_llegeix(FITXER), ensure_ascii=False, indent=1))
    else:
        print(__doc__)
