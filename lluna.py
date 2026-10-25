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
# Les fases d'abans (perquè «Ara» les digui fins a 24 hores després) i les
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


# El recorregut per a la gràfica de «Consultes»: cada PAS_MIN minuts, de 12
# hores abans a 12 després del moment més alt més proper (Juanjo, 25-10-2026:
# «un grafico similar al del sol para la luna del dia»). Centrat en el més alt
# i no en el dia, perquè la Lluna surt cada dia uns 50 minuts més tard i el dia
# de rellotge la tallaria pel mig de la nit.
PAS_MIN = 10


def posicio(t):
    """(alçada, azimut) de la Lluna, en graus, amb la refracció."""
    tm = temps(t)
    eq = A.Equator(A.Body.Moon, tm, OBSERVADOR, True, True)
    h = A.Horizon(tm, OBSERVADOR, eq.ra, eq.dec, A.Refraction.Normal)
    return h.altitude, h.azimuth


def recorregut(ara):
    """{inici, pas, alt: [graus…], culminacio: {hora, alt}, sortida, posta,
    sortida_az, posta_az}. L'arc que interessa: si ara és sobre l'horitzó, el
    d'ara; si no, el següent (a migdia, la d'aquest vespre i no la de la nit
    passada). La sortida i la posta, les de dins de les 24 hores (None si no
    n'hi ha)."""
    if posicio(ara)[0] > 0:
        abans = moment(A.SearchHourAngle(A.Body.Moon, OBSERVADOR, 0, temps(ara - dt.timedelta(hours=12.42))).time)
        despres = moment(A.SearchHourAngle(A.Body.Moon, OBSERVADOR, 0, temps(abans + dt.timedelta(hours=1))).time)
        mig = min((abans, despres), key=lambda t: abs(t - ara))
    else:
        mig = moment(A.SearchHourAngle(A.Body.Moon, OBSERVADOR, 0, temps(ara)).time)
    ini, fi = mig - dt.timedelta(hours=12), mig + dt.timedelta(hours=12)
    n = int((fi - ini).total_seconds() // (PAS_MIN * 60))
    res = {"inici": local(ini), "pas": PAS_MIN,
           "alt": [round(posicio(ini + dt.timedelta(minutes=PAS_MIN * i))[0], 1) for i in range(n + 1)],
           "culminacio": {"hora": local(mig), "alt": round(posicio(mig)[0], 1)}}
    for clau, sentit in (("sortida", A.Direction.Rise), ("posta", A.Direction.Set)):
        t = A.SearchRiseSet(A.Body.Moon, OBSERVADOR, sentit, temps(ini), 1.0)
        dins = t is not None and moment(t) <= fi
        res[clau] = local(moment(t)) if dins else None
        res[clau + "_az"] = round(posicio(moment(t))[1]) if dins else None
    return res


def calcula(ara=None):
    """La Lluna per a «Consultes», «Ara» i la gràfica: l'angle de la fase
    (0 nova, 90 quart creixent, 180 plena, 270 quart minvant), la part
    il·luminada en %, les fases principals, la sortida i la posta d'avui i
    de demà i el recorregut per a la gràfica."""
    ara = (ara or dt.datetime.now(UTC)).astimezone(UTC)
    t = temps(ara)
    avui = ara.astimezone(ZONA).date()
    return {"hora": local(ara), "angle": round(A.MoonPhase(t), 1),
            "il_luminacio": round(A.Illumination(A.Body.Moon, t).phase_fraction * 100),
            "fases": fases(ara), "avui": sortida_posta(avui), "dema": sortida_posta(avui + dt.timedelta(days=1)),
            "recorregut": recorregut(ara)}


if __name__ == "__main__":
    print(json.dumps(calcula(), ensure_ascii=False, indent=1))
