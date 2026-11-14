#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Aviso unos minutos antes de que empiece a llover en casa (ADR 0022).

Desde el 08-10-2026 ya no se manda a Juanjo por Telegram: le llega el aviso
público de lluvia como notificación del navegador (ADR 0048), que sale de la
misma cuenta (avisos_bot.py usa compara). Aquí queda el registro de cada
episodio, para saber cuánto acierta.

Sale del radar llevado hacia delante (nowcast.py, ADR 0019), que la página de
casa ya calcula en cada pasada: cuándo llegaría a casa la lluvia que hay
ahora. Tras publicar la página, el NAS mira cuánto falta. Si faltan
AVIS_PLUJA_MIN minutos más una pasada o menos (config.py) y aún no llueve en
casa, avisa.

Para no repetir, los avisos van por episodios: uno empieza cuando el radar
anuncia la lluvia o cuando empieza a llover, y acaba tras AVIS_PLUJA_REPOS_MIN
minutos sin lluvia medida ni anunciada. En un episodio hay un aviso como
mucho. Al acabar se apunta en el registro qué pasó (avisos-pluja.csv): si se
avisó, para cuándo y cuándo empezó a llover de verdad, para saber cuánto
acierta y ajustarlo.

Uso:
  python3 pluja_arriba.py avisa CASA.json   mira los datos y apunta el episodio
  python3 pluja_arriba.py estat             el episodio en curso
  python3 pluja_arriba.py resum             aciertos y fallos del registro
"""
import csv
import datetime as dt
import json
import os
import sys

import config as C
import hora as H

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
ESTADO = os.path.join(os.path.dirname(DIR), "avis-pluja.json")
REGISTRO = os.path.join(DIR, "avisos-pluja.csv")
CAMPOS = ["inici", "avisat", "arribada_prevista", "minuts_previstos", "imatge", "mm_h",
          "pluja_mesurada", "minuts_reals", "resultat", "callat"]
FONTS = {"meteocat": "Meteocat", "rainviewer": "RainViewer"}


def plou(salida):
    """Llueve ahora en el barrio: lo que dice la web (`pluja_ara.estat`, el
    estado único de la lluvia, ADR 0101: casa o una vecina que cuenta han
    recogido lluvia en los últimos PLOU_ARA_MIN minutos). Hasta la 3.142.0,
    solo el pluviómetro de casa (ADR 0102); con una salida vieja, lo mismo."""
    if "pluja_ara" in salida:
        return (salida["pluja_ara"] or {}).get("estat") == "plou"
    casa = salida.get("ara_casa")
    return bool(casa and casa.get("plou"))


def falta_min(salida, ahora):
    """Minutos que faltan para que llegue la lluvia según el radar (negativo
    si ya tendría que estar encima), o None si no se acerca."""
    arriba = (salida.get("radar") or {}).get("arriba")
    if not arriba:
        return None
    return (H.llegeix(arriba) - ahora).total_seconds() / 60


def feble(salida):
    """La lluvia que llega es débil: menos de C.AVIS_PLUJA_MM_H_MIN mm/h. No
    se avisa (desde la 3.224.0): de los 21 avisos del 6-10 al 14-11-2026, 14
    no trajeron lluvia y 12 de esos eran de menos de 1,5 mm/h (ADR 0022). Se
    apunta igual (callat), para comprobar el umbral. Sin el dato, no lo es."""
    mm = (salida.get("radar") or {}).get("arriba_mm_h")
    return mm is not None and mm < C.AVIS_PLUJA_MM_H_MIN


def intensitat(mm_h):
    if mm_h is None:
        return ""
    import nowcast as N
    return f" Seria {N.nom_intensitat(mm_h)}."


def missatge(salida, ahora):
    r = salida["radar"]
    falta = round(falta_min(salida, ahora))
    font = FONTS.get(r.get("imatge"), "radar")
    imatge = H.local(r["hora"]).strftime("%H:%M")
    if falta <= 2:
        return (f"El radar ja veu pluja a sobre de casa: pot començar en qualsevol moment."
                f"{intensitat(r.get('arriba_mm_h'))} (Radar de {font} de les {imatge}.)")
    hora = H.local(r["arriba"]).strftime("%H:%M")
    return (f"Plourà a casa d'aquí a uns {falta} minuts, cap a les {hora}."
            f"{intensitat(r.get('arriba_mm_h'))} (Radar de {font} de les {imatge}.)")


def fila_registro(ep):
    """Lo que pasó en un episodio, para el registro."""
    avis, pluja = ep.get("avis"), ep.get("pluja")
    fila = dict.fromkeys(CAMPOS, "")
    fila["inici"], fila["pluja_mesurada"] = ep["inici"], pluja or ""
    if avis:
        enviat = H.llegeix(avis["enviat"])
        fila.update(avisat=avis["enviat"], arribada_prevista=avis["arribada"], imatge=avis["imatge"],
                    mm_h="" if avis.get("mm_h") is None else avis["mm_h"], callat="sí" if avis.get("callat") else "",
                    minuts_previstos=round((H.llegeix(avis["arribada"]) - enviat).total_seconds() / 60))
        reals = pluja and (H.llegeix(pluja) - enviat).total_seconds() / 60
        if pluja:
            fila["minuts_reals"] = round(reals)
        fila["resultat"] = ("encert" if pluja and reals <= C.AVIS_PLUJA_VERIFICA_MIN
                            else "avís sense pluja")
    else:
        fila["resultat"] = "pluja sense avís"
    return fila


def compara(estat, salida, ahora):
    """Pone al día el episodio y devuelve (mensaje o None, fila del registro
    del episodio que acaba o None)."""
    ara = H.clau(ahora)
    ep = estat.get("episodi")
    falta = falta_min(salida, ahora)
    mullat = plou(salida)
    limit = C.AVIS_PLUJA_MIN + C.MODO_AVISO_INTERVALO_MIN
    senyal = mullat or (falta is not None and falta <= limit)
    fila = text = None
    if ep and not senyal:
        vist = H.llegeix(ep["vist"])
        if ahora - vist >= dt.timedelta(minutes=C.AVIS_PLUJA_REPOS_MIN):
            fila = fila_registro(ep)
            ep = None
    if senyal:
        nou = not ep
        if nou:
            ep = {"inici": ara, "avis": None, "pluja": None}
        # El aviso, al empezar el episodio sin lluvia. Si la que llega es débil,
        # se apunta callado, sin mensaje; si antes de empezar a llover deja de
        # serlo, se avisa entonces.
        callat = (ep["avis"] or {}).get("callat")
        if not mullat and not ep["pluja"] and (nou or callat) and falta is not None and falta <= limit:
            r = salida["radar"]
            if not feble(salida):
                text = missatge(salida, ahora)
            if nou or text:
                ep["avis"] = {"enviat": ara, "arribada": r["arriba"], "imatge": r["hora"],
                              "mm_h": r.get("arriba_mm_h"), **({} if text else {"callat": True})}
        ep["vist"] = ara
        if mullat and not ep["pluja"]:
            ep["pluja"] = ara
    estat["episodi"] = ep
    return text, fila


# --- En el NAS -----------------------------------------------------------------

def llegeix_estat():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"episodi": None}


def desa_estat(estat):
    with open(ESTADO + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estat, f, ensure_ascii=False, indent=1)
    os.replace(ESTADO + ".tmp", ESTADO)


def apunta(fila):
    nou = not os.path.exists(REGISTRO)
    os.makedirs(DIR, exist_ok=True)
    if not nou:
        # Un registro de antes de la 3.224.0, sin la columna «callat»: se
        # reescribe con la cabecera de ahora.
        with open(REGISTRO, encoding="utf-8") as f:
            files = list(csv.DictReader(f))
        if files and list(files[0]) != CAMPOS:
            with open(REGISTRO + ".tmp", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
                w.writeheader()
                w.writerows({c: x.get(c) or "" for c in CAMPOS} for x in files)
            os.replace(REGISTRO + ".tmp", REGISTRO)
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nou:
            w.writeheader()
        w.writerow(fila)


def avisa(ruta, ahora=None):
    ahora = ahora or H.ara()
    with open(ruta, encoding="utf-8") as f:
        salida = json.load(f)
    # Con datos viejos (la pasada ha fallado), la llegada ya no vale.
    if ahora - H.llegeix(salida["generat"]) > dt.timedelta(minutes=C.INTERVALO_CASA_MIN):
        return None
    estat = llegeix_estat()
    text, fila = compara(estat, salida, ahora)
    desa_estat(estat)
    if fila:
        apunta(fila)
    if text:
        print(text)         # al registro del NAS; ya no se manda a Juanjo
    return text


def resum():
    """Cuánto acierta, con lo apuntado hasta ahora."""
    if not os.path.exists(REGISTRO):
        return "Encara no hi ha cap episodi apuntat."
    with open(REGISTRO, encoding="utf-8") as f:
        files = list(csv.DictReader(f))
    callats = [f for f in files if f.get("callat")]
    files = [f for f in files if not f.get("callat")]
    n = {r: sum(f["resultat"] == r for f in files) for r in ("encert", "avís sense pluja", "pluja sense avís")}
    linies = [f"Episodis: {len(files)}. Encerts: {n['encert']}. Avisos sense pluja: {n['avís sense pluja']}. "
              f"Pluja sense avís: {n['pluja sense avís']}."]
    if callats:
        # Els que no s'han enviat perquè la pluja que venia era feble: si
        # molts haurien encertat, el llindar és massa alt.
        be = sum(f["resultat"] == "encert" for f in callats)
        linies.append(f"Avisos callats per pluja feble (menys de {C.AVIS_PLUJA_MM_H_MIN:g} mm/h): {len(callats)}; "
                      f"haurien encertat {be} i {len(callats) - be} haurien estat sense pluja.")
    reals = [int(f["minuts_reals"]) for f in files if f["resultat"] == "encert"]
    if reals:
        linies.append(f"Als encerts, va començar a ploure entre {min(reals)} i {max(reals)} minuts després "
                      f"de l'avís (mitjana, {round(sum(reals) / len(reals))}).")
    return "\n".join(linies)


if __name__ == "__main__":
    ordre = sys.argv[1] if len(sys.argv) > 1 else ""
    if ordre == "avisa" and len(sys.argv) > 2:
        avisa(sys.argv[2])
    elif ordre == "estat":
        print(json.dumps(llegeix_estat(), ensure_ascii=False, indent=1))
    elif ordre == "resum":
        print(resum())
    else:
        print(__doc__)
        sys.exit(1)
