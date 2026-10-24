#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El cel tapat sobre el barri segons el satèl·lit, en observació (ADR 0126).

Fins ara el cel tapat observat és el de l'aeroport de Sabadell (nuvols.py): el
METAR automàtic, a uns 8 km, que no veu els núvols alts. Juanjo, 24-10-2026:
«no hay una forma mejor de medirlo? las imágenes de satélite no se pueden
usar?». La màscara de núvols de Meteosat (EUMETSAT, servidor de mapes
EUMETView, capa msg_fes:clm, oberta i sense clau) diu cada 15 minuts, amb una
mitja hora de retard, si cada píxel (uns 4-5 km aquí) és núvol o serè. La part
dels píxels amb núvol en un requadre al voltant del barri (CAIXA) és el cel
tapat segons el satèl·lit.

Del 13 al 24-10-2026, contra Sabadell, coincidien en «tapat o no» 55 vegades
de 86: el satèl·lit veu núvols alts que el METAR no veu, i de nit se li
escapen els baixos. Per saber quin s'acosta més al que es veu des del barri,
primer s'observa (regla de les fonts noves) i es pregunta a Juanjo:

- `apunta`: cada passada, els quarts d'hora que falten (des de les últimes
  RECUPERA_H hores), a registre/nuvols-satellit.csv. No es fa servir enlloc.
- `pregunta`: de dia, si el satèl·lit i Sabadell discrepen de debò (un per
  sota de SERE i l'altre per sobre de TAPAT), un missatge amb botons a Juanjo
  (confirmacio.py, com la boira i el plugim), com a molt MAX_DIA al dia i
  separats CADA_H hores.
- `respostes`: les seves respostes, a registre/cel-confirmacions.csv.
- `resum`: com van.

  python3 nuvols_satellit.py apunta | pregunta | respostes | resum
"""
import datetime as dt
import fcntl
import io
import json
import os
import sys
import urllib.request

import config as C
import confirmacio as CF
import prevision as P

REGISTRE = os.environ.get("REGISTRE_DIR", "/estat/registre")
OBSERVATS = os.path.join(REGISTRE, "nuvols-satellit.csv")
SABADELL = os.path.join(REGISTRE, "nuvols-sabadell.csv")
PREGUNTES = os.path.join(REGISTRE, "cel-preguntes.csv")
CONFIRMACIONS = os.path.join(REGISTRE, "cel-confirmacions.csv")
CONFIG_BOT = CF.CONFIG_BOT
CAMPS_OBSERVATS = ["t", "nuvols", "pixels"]

URL = "https://view.eumetsat.int/geoserver/ows"
CAPA = "msg_fes:clm"
ESTIL = "msg_clm"
# El requadre: uns 18 km de nord a sud i 17 d'est a oest, amb el barri al mig;
# arriba a uns 3 km del mar per l'est. Una imatge de MIDA × MIDA punts.
CAIXA = (0.08, 0.10)
MIDA = 24
# Quan EUMETSAT el publica: uns 30 minuts després del quart d'hora.
RETARD_MIN = 35
RECUPERA_H = 3
# Discrepància de debò: un ho veu serè (menys del 30 %) i l'altre tapat (més del 70 %).
SERE, TAPAT = 30, 70
HORES_PREGUNTA = range(9, 20)
CADA_H = 4
MAX_DIA = 2
# Les observacions de cada font, com a molt així de velles per comparar-les.
VIGENT_MIN = 75
RESPOSTES = {"sere": "Despejado", "alts": "Solo nubes altas y finas", "alguns": "Algunas nubes",
             "tapat": "Cubierto", "nose": "No lo sé"}
CAMPS = ["satellit", "sabadell"]


def quart(t):
    """El quart d'hora en què comença t (temps universal)."""
    t = t.astimezone(dt.timezone.utc)
    return t.replace(minute=t.minute - t.minute % 15, second=0, microsecond=0)


def baixa(t, obre=urllib.request.urlopen):
    """La imatge de la màscara al voltant del barri a l'hora t: PNG."""
    lat, lon = C.CASA
    dlat, dlon = CAIXA
    # L'estil, fixat: els colors (blanc, núvol) no canvien si el servidor en
    # canvia el de per defecte. El WCS del mateix servidor, que donaria els
    # valors i no un dibuix, no ofereix la màscara (24-10-2026).
    url = (f"{URL}?service=WMS&version=1.3.0&request=GetMap&layers={CAPA}&styles={ESTIL}&crs=EPSG:4326"
           f"&bbox={lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon}&width={MIDA}&height={MIDA}"
           f"&format=image/png&transparent=true&time={t.strftime('%Y-%m-%dT%H:%M:00Z')}")
    with obre(url, timeout=60) as r:
        if not r.headers.get("Content-Type", "").startswith("image/png"):
            raise ValueError("EUMETView no ha tornat cap imatge")
        # Si aquell quart d'hora no hi és, el servidor dona el més proper i ho
        # diu en una capçalera: seria apuntar una imatge amb una altra hora.
        if "Nearest value used" in (r.headers.get("Warning") or ""):
            raise ValueError("EUMETView no té aquell quart d'hora")
        return r.read()


def percentatge(png):
    """(% de píxels amb núvol, píxels amb dada): el blanc és núvol; la resta,
    opaca, serè (sobre terra o sobre aigua); el transparent, sense dada.
    (None, 0) si no n'hi ha prou."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    nuvol = valids = 0
    for r, g, b, a in im.getdata():
        if a < 128:
            continue
        valids += 1
        nuvol += (r, g, b) == (255, 255, 255)
    if valids < MIDA * MIDA // 2:
        return None, valids
    return round(100 * nuvol / valids), valids


def files(ruta):
    return CF.files(ruta)


def apunta(ara=None, obre=urllib.request.urlopen):
    """Els quarts d'hora publicats que encara no són al registre, de les últimes
    RECUPERA_H hores. Si EUMETView falla, es prova a la passada següent."""
    ara = ara or dt.datetime.now(dt.timezone.utc)
    fets = {f["t"] for f in files(OBSERVATS)}
    darrer = quart(ara - dt.timedelta(minutes=RETARD_MIN))
    t, nous = darrer - dt.timedelta(hours=RECUPERA_H), 0
    while t <= darrer:
        clau = t.strftime("%Y-%m-%dT%H:%MZ")
        if clau not in fets:
            try:
                pct, n = percentatge(baixa(t, obre))
            except Exception:
                t += dt.timedelta(minutes=15)
                continue
            if pct is not None:
                CF.afegeix(OBSERVATS, CAMPS_OBSERVATS, {"t": clau, "nuvols": pct, "pixels": n})
                nous += 1
        t += dt.timedelta(minutes=15)
    return nous


def ultim(ruta, camp_t, ara, camp="nuvols"):
    """El valor de l'última observació de VIGENT_MIN minuts com a molt, o None."""
    fs = files(ruta)
    if not fs:
        return None
    f = fs[-1]
    t = dt.datetime.fromisoformat(f[camp_t].replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=P.ZONA)
    if ara - t > dt.timedelta(minutes=VIGENT_MIN) or f.get(camp) in (None, ""):
        return None
    return float(f[camp])


def estat(ara=None):
    ara = ara or dt.datetime.now(P.ZONA)
    return {"satellit": ultim(OBSERVATS, "t", ara), "sabadell": ultim(SABADELL, "fins", ara)}


def discrepen(sat, sab):
    return sat is not None and sab is not None and min(sat, sab) < SERE and max(sat, sab) > TAPAT


def telegram(metode, **params):
    return CF.telegram(metode, CONFIG_BOT, **params)


def pregunta(ara=None):
    """Amb un cadenat, com la boira: dues passades alhora no envien la mateixa
    pregunta dues vegades."""
    os.makedirs(os.path.dirname(PREGUNTES) or ".", exist_ok=True)
    with open(PREGUNTES + ".lock", "w") as cadenat:
        fcntl.flock(cadenat, fcntl.LOCK_EX)
        return _pregunta(ara or dt.datetime.now(P.ZONA))


def _pregunta(ara):
    if ara.hour not in HORES_PREGUNTA:
        return None
    e = estat(ara)
    if not discrepen(e["satellit"], e["sabadell"]):
        return None
    fetes = [dt.datetime.fromisoformat(f["t"]) for f in files(PREGUNTES)]
    if fetes and ara - fetes[-1] < dt.timedelta(hours=CADA_H):
        return None
    if sum(f.date() == ara.date() for f in fetes) >= MAX_DIA:
        return None
    sat, sab = round(e["satellit"]), round(e["sabadell"])
    text = ("¿Cómo está el cielo sobre Montflorit ahora? El satélite lo ve "
            f"{'cubierto' if sat > TAPAT else 'despejado'} ({sat} %) y el aeropuerto de Sabadell, "
            f"{'cubierto' if sab > TAPAT else 'despejado'} ({sab} %). Con tu respuesta se decide cuál "
            "de los dos se acerca más a lo que se ve desde el barrio.")
    claus = list(RESPOSTES)
    files_botons = [claus[0:2], claus[2:4], claus[4:]]
    teclat = {"inline_keyboard": [[{"text": RESPOSTES[k], "callback_data": f"cel:{k}"} for k in fila]
                                  for fila in files_botons]}
    with open(CONFIG_BOT, encoding="utf-8") as f:
        xat = json.load(f)["chat_id"]
    r, cfg = telegram("sendMessage", chat_id=xat, text=CF.capcalera(text), reply_markup=teclat)
    CF.afegeix(PREGUNTES, ["t", "missatge"] + CAMPS,
               {"t": ara.isoformat(timespec="minutes"), "missatge": r["message_id"], "satellit": sat, "sabadell": sab})
    return r["message_id"]


def respostes(ara=None):
    """Les respostes als botons, una vegada cadascuna, amb les dades del moment
    en què es respon."""
    return CF.respostes("cel", PREGUNTES, CONFIRMACIONS, RESPOSTES, CAMPS, telegram,
                        ara or dt.datetime.now(P.ZONA), estat)


def resum():
    obs, conf = files(OBSERVATS), files(CONFIRMACIONS)
    per = {k: sum(r["resposta"] == k for r in conf) for k in RESPOSTES}
    print(f"Satèl·lit: {len(obs)} quarts d'hora apuntats"
          + (f", des de {obs[0]['t']}" if obs else "") + f". Preguntes: {len(files(PREGUNTES))}, "
          f"respostes: {len(conf)} ({', '.join(f'{RESPOSTES[k]} {n}' for k, n in per.items() if n)}).")
    return {"observats": len(obs), "preguntes": len(files(PREGUNTES)), "respostes": len(conf), **per}


if __name__ == "__main__":
    ordres = {"apunta": apunta, "pregunta": pregunta, "respostes": respostes, "resum": resum}
    if len(sys.argv) != 2 or sys.argv[1] not in ordres:
        sys.exit(__doc__)
    ordres[sys.argv[1]]()
