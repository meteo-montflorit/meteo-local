#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Vigila que respondan las estaciones del barrio (ADR 0087).

Juanjo, 13-10-2026: «hay que prever qué hace el programa si fallan las
estaciones, las de la parte baja o las de la parte alta, incluso si el
servicio completo deja de funcionar. Aparte de avisarme para tomar
decisiones, la web debe seguir funcionando». Lo que hace la web en cada caso
está en casa.py (ara_sense_casa, consens) y part_alta.py; aquí solo se mira
en cada pasada del NAS qué falla y, si dura, se le dice una vez a Juanjo
(avis_privat, con reintento), y otra cuando vuelve:

- la estación de casa, a los LLINDAR_MIN["casa"] minutos;
- la parte alta (menos de part_alta.ALTES_MIN de sus vecinas), a la hora;
- Weather Underground entero (ninguna vecina), a la hora; mientras dura, no
  se avisa de cada vecina ni de la parte alta;
- una vecina sola, al día.

Solo se vigila lo que se puede leer: sin claves de Ecowitt o de Weather
Underground (la reserva de IONOS no las tiene), no hay nada que vigilar, no un
fallo. Hasta la 3.83.1 la prueba diaria de la reserva lo tomaba por un fallo y
avisaba a Juanjo cada día.
"""
import datetime as dt
import json
import os

import config as C
import hora as H
import part_alta as PA

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
ESTAT = os.path.join(os.path.dirname(DIR), "estacions-falla.json")
LLINDAR_MIN = {"casa": 30, "alta": 60, "xarxa": 60}
LLINDAR_VEINA_MIN = 24 * 60

FALLA = {
    "casa": ("Temps a Montflorit: l'estació de casa no respon des de les {h}. «Ara» surt de les estacions "
             "veïnes (la temperatura, d'ICERDA6, vora la riera, o de la part alta menys la diferència habitual) "
             "i la previsió es corregeix sense l'estació. Mira l'estació o l'API d'Ecowitt."),
    "alta": ("Temps a Montflorit: les estacions de la part alta (" + ", ".join(PA.ALTES) + ") no responen des "
             "de les {h}. «Ara» no diu quant més fa a la part alta i la previsió fa servir la diferència habitual."),
    "xarxa": ("Temps a Montflorit: no es pot llegir cap estació veïna de Weather Underground des de les {h}. "
              "La pluja i la humitat surten només de l'estació de casa i no es diu la diferència amb la part "
              "alta. Si dura, mira la clau de lectura (caduca el " + C.WU_CLAU_CADUCA + ") i Weather Underground."),
}
VEINA = ("Temps a Montflorit: l'estació veïna {e} ({nom}) no publica des del {d}. La web segueix amb les "
         "altres; si no torna, caldrà decidir si se substitueix.")
TORNA = {"casa": "l'estació de casa", "alta": "les estacions de la part alta", "xarxa": "Weather Underground"}


def _llegeix(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def vigila(casa_ok, veines_ok, ahora, envia=None, ruta=None):
    """casa_ok: si se ha leído la estación de casa; veines_ok: las vecinas
    leídas. None en cualquiera de los dos: no hay claves para leerla y no se
    vigila. Devuelve los mensajes enviados."""
    if envia is None:
        import avis_privat
        envia = avis_privat.envia
    ruta = ruta or ESTAT
    falles = {}
    if casa_ok is not None:
        falles["casa"] = not casa_ok
    if veines_ok is not None:
        veines_ok = set(veines_ok)
        falles.update({"xarxa": not veines_ok, "alta": len(veines_ok & set(PA.ALTES)) < PA.ALTES_MIN})
        falles.update({e: e not in veines_ok for e in C.VEINES})
    estat, missatges = _llegeix(ruta), []
    # Lo que ya no se vigila se olvida, sin avisar de que vuelve.
    for clau in [c for c in estat if c not in falles]:
        estat.pop(clau)
    for clau, falla in falles.items():
        s = estat.get(clau)
        if not falla:
            if s and s.get("avisat"):
                qui = TORNA.get(clau, f"l'estació veïna {clau}")
                missatges.append(f"Temps a Montflorit: {qui} torna a respondre.")
            estat.pop(clau, None)
            continue
        if not s:
            estat[clau] = s = {"des_de": H.clau(ahora), "avisat": False}
        if s["avisat"]:
            continue
        # Sin Weather Underground, ni la parte alta ni cada vecina: ya lo dice «xarxa».
        if clau != "xarxa" and clau != "casa" and falles.get("xarxa"):
            continue
        des_de = H.llegeix(s["des_de"])
        llindar = LLINDAR_MIN.get(clau, LLINDAR_VEINA_MIN)
        if ahora - des_de < dt.timedelta(minutes=llindar):
            continue
        s["avisat"] = True
        if clau in FALLA:
            missatges.append(FALLA[clau].format(h=f"{H.local(des_de):%H:%M}"))
        else:
            missatges.append(VEINA.format(e=clau, nom=C.VEINES[clau]["nom"], d=f"{des_de:%d/%m %H:%M}"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estat, f)
    os.replace(ruta + ".tmp", ruta)
    for m in missatges:
        envia(m)
    return missatges
