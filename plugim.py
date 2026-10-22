#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""¿Encerta el radar el plugim? La confirmació de Juanjo (ADR 0019).

El 18-10-2026 començava a plovisquejar a casa i la web deia «El radar no veu
pluja que vingui cap aquí»: els dos radars veien ecos febles a sobre del
barri, per sota de la pluja que compta (nowcast.PLOU_MMH), i el pluviòmetre no
recull el plugim. Des de llavors, si els dos radars veuen ecos febles estesos
a sobre del barri (casa.plugim_radar) i cap estació no mesura pluja, la web
diu «plugim segons el radar» i, de dia, es pregunta a Juanjo per Telegram si
plou a casa, amb botons, com a molt una vegada cada CADA_H hores. Les seves
respostes, a registre/plugim-confirmacions.csv, diran si aquest senyal
encerta prou per fer-lo servir també a la previsió (ADR 0019; es mira amb els
ecos de prop de casa a partir del 07-11-2026). Com la boira (ADR 0100), amb
confirmacio.py.

  python3 plugim.py pregunta | respostes | resum
"""
import datetime as dt
import fcntl
import json
import os
import sys

import confirmacio as CF
import prevision as P

REGISTRE = os.environ.get("REGISTRE_DIR", "/estat/registre")
PREGUNTES = os.path.join(REGISTRE, "plugim-preguntes.csv")
CONFIRMACIONS = os.path.join(REGISTRE, "plugim-confirmacions.csv")
CONFIG_BOT = CF.CONFIG_BOT
CASA_JSON = "/estat/casa.json"
HORES_PREGUNTA = range(7, 23)
CADA_H = 3
RESPOSTES = {"si": "Sí, llueve", "no": "No llueve", "nose": "No lo sé"}
# Els píxels febles de cada radar, si la web deia plugim i si alguna estació
# mesurava pluja: en preguntar i en respondre.
CAMPS = ["meteocat", "rainviewer", "plugim", "plou"]


def estat(casa_json=None):
    """El que diuen ara les dades (l'última passada, de fa 6 minuts com a
    molt en mode avís), amb les columnes de CAMPS."""
    with open(casa_json or CASA_JSON, encoding="utf-8") as f:
        casa = json.load(f)
    px = (casa.get("radar") or {}).get("plugim") or {}
    return {"meteocat": px.get("meteocat"), "rainviewer": px.get("rainviewer"),
            "plugim": int(bool((casa.get("pluja_ara") or {}).get("plugim"))),
            "plou": int(bool((casa.get("ara_casa") or {}).get("plou")))}


def telegram(metode, **params):
    return CF.telegram(metode, CONFIG_BOT, **params)


def pregunta(ara=None, casa_json=CASA_JSON):
    """Si la web diu plugim segons el radar, de dia, i no s'ha preguntat en les
    últimes CADA_H hores: el missatge amb els botons. Amb un cadenat, com la
    boira: dues passades alhora no envien la mateixa pregunta dues vegades."""
    os.makedirs(os.path.dirname(PREGUNTES) or ".", exist_ok=True)
    with open(PREGUNTES + ".lock", "w") as cadenat:
        fcntl.flock(cadenat, fcntl.LOCK_EX)
        return _pregunta(ara, casa_json)


def _pregunta(ara, casa_json):
    ara = ara or dt.datetime.now(P.ZONA)
    if ara.hour not in HORES_PREGUNTA:
        return None
    with open(casa_json, encoding="utf-8") as f:
        casa = json.load(f)
    if not (casa.get("pluja_ara") or {}).get("plugim"):
        return None
    ultima = CF.files(PREGUNTES)[-1:]
    if ultima and ara - dt.datetime.fromisoformat(ultima[0]["t"]) < dt.timedelta(hours=CADA_H):
        return None
    px = estat(casa_json)
    text = ("¿Llueve en casa ahora? Los dos radares ven lluvia muy débil encima del barrio "
            f"(Meteocat, {px.get('meteocat')} puntos; RainViewer, {px.get('rainviewer')}, a 3 km o menos) "
            "y ninguna estación la mide. Con tu respuesta se comprueba si el radar acierta la llovizna.")
    teclat = {"inline_keyboard": [[{"text": t, "callback_data": f"plugim:{k}"} for k, t in RESPOSTES.items()]]}
    with open(CONFIG_BOT, encoding="utf-8") as f:
        chat_id = json.load(f)["chat_id"]
    r, cfg = telegram("sendMessage", chat_id=chat_id, text=CF.capcalera(text), reply_markup=teclat)
    CF.afegeix(PREGUNTES, ["t", "missatge"] + CAMPS,
               {"t": ara.isoformat(timespec="minutes"), "missatge": r["message_id"], **{k: px.get(k) for k in CAMPS}})
    return r["message_id"]


def respostes(ara=None):
    """Les respostes als botons, una vegada cadascuna, a plugim-confirmacions.csv,
    amb les dades del moment en què es respon."""
    return CF.respostes("plugim", PREGUNTES, CONFIRMACIONS, RESPOSTES, CAMPS, telegram,
                        ara or dt.datetime.now(P.ZONA), estat)


def resum():
    conf = CF.files(CONFIRMACIONS)
    si = sum(r["resposta"] == "si" for r in conf)
    no = sum(r["resposta"] == "no" for r in conf)
    print(f"Plugim segons el radar: {len(CF.files(PREGUNTES))} preguntes, {len(conf)} respostes "
          f"(plovia {si}, no plovia {no}).")
    return {"preguntes": len(CF.files(PREGUNTES)), "respostes": len(conf), "si": si, "no": no}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("pregunta", "respostes", "resum"):
        sys.exit(__doc__)
    {"pregunta": pregunta, "respostes": respostes, "resum": resum}[sys.argv[1]]()
