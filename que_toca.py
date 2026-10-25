#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Si toca actualizar en este minuto, según el horario que muestra la página.

El reloj del NAS lo pregunta cada minuto. Lee el horario de los últimos datos
publicados (en modo aviso, cada 6 minutos con desfase; si no, el normal de
config.py), de modo que lo que dice la página y lo que se hace son lo mismo.
Desde el 07-10-2026 solo hay la página del tiempo (ADR 0030).

Uso: python3 que_toca.py HH:MM [CASA.json]
Escribe «casa» si toca, o nada.
"""
import datetime as dt
import json
import sys

import config as C
import hora as H


def leer_horario(ruta, por_defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        # Solo vale el horario de hoy: el modo aviso de ayer no cuenta.
        if H.dia_local(datos["generat"]) == H.dia_local(H.ara()):
            return datos["horari"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return por_defecto


def horas(horari):
    res = set()
    desfase = horari.get("desfase_min", 0)
    for ini, fin in horari["trams"]:
        t = dt.datetime.strptime(ini, "%H:%M") + dt.timedelta(minutes=desfase)
        f = dt.datetime.strptime(fin, "%H:%M") + dt.timedelta(minutes=desfase)
        while t <= f:
            res.add(t.strftime("%H:%M"))
            t += dt.timedelta(minutes=horari["cada_min"])
    return res


def que_toca(hhmm, casa="/estat/casa.json"):
    hogar = leer_horario(casa, {"trams": [C.HORARIO_CASA], "cada_min": C.INTERVALO_CASA_MIN})
    return "casa" if hhmm in horas(hogar) else ""


if __name__ == "__main__":
    print(que_toca(*sys.argv[1:3]))
