# SPDX-License-Identifier: AGPL-3.0-or-later
"""La Lluna a Montflorit (ADR 0127): la fase d'ara, les quatre fases
principals d'abans i de després i la sortida i la posta d'avui, amb Astronomy
Engine de Don Cross (tercers/astronomy.py, llicència MIT).

Es calcula en temps universal i les hores surten en hora local amb el seu
desfasament («…T21:12+01:00»): el canvi d'hora no les mou (Juanjo,
25-10-2026: «internamente siempre utc y al mostrar datos los adaptas al
horario actual»)."""
import datetime as dt
import json
from zoneinfo import ZoneInfo

import config as C
from tercers import astronomy as A

ZONA = ZoneInfo("Europe/Madrid")
UTC = dt.timezone.utc
# Les coordenades arrodonides i l'alçada de config.
OBSERVADOR = A.Observer(C.CASA[0], C.CASA[1], C.ALTITUD_CASA_M)
FASES = ("nova", "quart_creixent", "plena", "quart_minvant")
# Les fases d'abans (perquè «Ara» les digui fins a 12 hores després) i les
# del mes que ve.
ABANS_DIES, DESPRES_DIES = 2, 32


def temps(t):
    t = t.astimezone(UTC)
    return A.Time.Make(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)


def moment(tm):
    return tm.Utc().replace(tzinfo=UTC)


def local(t):
    return t.astimezone(ZONA).isoformat(timespec="minutes")


def fases(ara):
    """Les fases principals de ABANS_DIES dies abans a DESPRES_DIES després."""
    res = []
    q = A.SearchMoonQuarter(temps(ara - dt.timedelta(days=ABANS_DIES)))
    while moment(q.time) < ara + dt.timedelta(days=DESPRES_DIES):
        res.append({"fase": FASES[q.quarter], "hora": local(moment(q.time))})
        q = A.NextMoonQuarter(q)
    return res


def sortida_posta(dia):
    """La sortida i la posta de la Lluna el dia local `dia`; None si aquell
    dia no n'hi ha (passa un cop al mes amb cadascuna)."""
    ini = dt.datetime.combine(dia, dt.time(), tzinfo=ZONA).astimezone(UTC)
    fi = dt.datetime.combine(dia + dt.timedelta(days=1), dt.time(), tzinfo=ZONA).astimezone(UTC)
    res = {}
    for clau, sentit in (("sortida", A.Direction.Rise), ("posta", A.Direction.Set)):
        t = A.SearchRiseSet(A.Body.Moon, OBSERVADOR, sentit, temps(ini), (fi - ini).total_seconds() / 86400)
        res[clau] = local(moment(t)) if t is not None and moment(t) < fi else None
    return res


def calcula(ara=None):
    """La Lluna per a «Consultes», «Ara» i la gràfica: l'angle de la fase
    (0 nova, 90 quart creixent, 180 plena, 270 quart minvant), la part
    il·luminada en %, les fases principals i la sortida i la posta d'avui i
    de demà."""
    ara = (ara or dt.datetime.now(UTC)).astimezone(UTC)
    t = temps(ara)
    avui = ara.astimezone(ZONA).date()
    return {"hora": local(ara), "angle": round(A.MoonPhase(t), 1),
            "il_luminacio": round(A.Illumination(A.Body.Moon, t).phase_fraction * 100),
            "fases": fases(ara), "avui": sortida_posta(avui), "dema": sortida_posta(avui + dt.timedelta(days=1))}


if __name__ == "__main__":
    print(json.dumps(calcula(), ensure_ascii=False, indent=1))
