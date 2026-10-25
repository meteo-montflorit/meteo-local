# SPDX-License-Identifier: AGPL-3.0-or-later
"""La hora del programa (ADR 0128): per dins, sempre en temps universal; la
local, només a la frontera (el que es mostra, el que s'escriu a la gent i
les regles que depenen de les persones: les hores de sortir, la roba, el
resum de demà). El canvi d'hora no pot desplaçar cap resultat (Juanjo,
25-10-2026: «internamente siempre utc y al mostrar datos los adaptas al
horario actual»).

- Un moment és un `datetime` amb zona; «ara» és en UTC (`ara`).
- Les claus que es desen (registres, estat, dades) són text en UTC amb «Z»,
  «AAAA-MM-DDTHH:MMZ» (`clau`): totes amb el mateix format, s'ordenen i es
  comparen bé com a text, també la nit que l'hora es repeteix.
- Es llegeix qualsevol forma que hi hagi hagut (`llegeix`): «…Z», amb
  desfasament («…+01:00») i sense (l'hora de Madrid d'abans de la 3.201.0).
- Per a la gent, l'hora de Madrid (`local`), i a les dades públiques, amb el
  desfasament explícit (`iso_local`), que no és mai ambigu."""
import datetime as dt
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
ZONA = ZoneInfo("Europe/Madrid")


def ara():
    """Ara, en UTC."""
    return dt.datetime.now(UTC)


def llegeix(t):
    """Un moment amb zona a partir d'un text (o d'un datetime) en qualsevol de
    les formes del programa. Sense zona, és l'hora de Madrid (els registres
    d'abans de la migració); la primera de l'hora repetida d'octubre, que
    llavors ja portava el desfasament."""
    if t is None:
        return None
    if isinstance(t, str):
        t = dt.datetime.fromisoformat(t.replace("Z", "+00:00") if t.endswith("Z") else t)
    if t.tzinfo is None:
        # En UTC i no amb ZoneInfo: Python resta dues hores amb la mateixa
        # ZoneInfo com a hores de rellotge, i la nit del canvi s'equivoca d'una.
        t = t.replace(tzinfo=ZONA).astimezone(UTC)
    return t


def utc(t):
    """El moment en UTC."""
    return llegeix(t).astimezone(UTC)


def clau(t):
    """La clau d'un moment, en UTC: «AAAA-MM-DDTHH:MMZ»."""
    return utc(t).strftime("%Y-%m-%dT%H:%MZ")


def local(t):
    """El moment en hora de Madrid, per llegir-ne l'hora, el dia o el text. No
    per calcular: Python resta i suma dues hores de Madrid com a hores de
    rellotge (el dia del canvi, s'equivoca d'una); els càlculs, en UTC."""
    return llegeix(t).astimezone(ZONA)


def iso_local(t, segons=False):
    """Per a les dades públiques: l'hora de Madrid amb el desfasament,
    «2026-10-25T07:14+01:00»."""
    return local(t).isoformat(timespec="seconds" if segons else "minutes")


def mitjanit(dia):
    """L'inici del dia local `dia` (date), com a moment en UTC."""
    return dt.datetime.combine(dia, dt.time(), tzinfo=ZONA).astimezone(UTC)


def de_rellotge(dia, hores):
    """El moment de les `hores` de rellotge de Madrid del dia `dia` (date o
    «AAAA-MM-DD»): les franges dels avisos, «de 0 a 24 h», són de rellotge;
    24 és la mitjanit següent. Per sumar-hi temps, en UTC."""
    dia = dt.date.fromisoformat(dia) if isinstance(dia, str) else dia
    t = dt.datetime.combine(dia, dt.time()) + dt.timedelta(hours=hores)
    return t.replace(tzinfo=ZONA).astimezone(UTC)


def dia_local(t):
    """El dia (date) de Madrid d'un moment."""
    return local(t).date()


def hora_local(t):
    """L'hora (0-23) de Madrid d'un moment: per a les regles de les persones."""
    return local(t).hour


def suma(t, **quant):
    """Suma temps de debò (en UTC): sumar hores a una hora de Madrid amb
    ZoneInfo suma hores de rellotge i, el dia del canvi, s'equivoca d'una."""
    return utc(t) + dt.timedelta(**quant)


# Una clau interna: una hora en UTC amb «Z» (amb segons o sense).
_CLAU = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")


def publica(dades):
    """Les dades com es publiquen (la frontera, ADR 0128): cada hora interna
    «…Z», valor o clau d'un diccionari, en hora de Madrid amb el desfasament;
    la resta, tal com és. Així la web, el bot i qui llegeixi les dades veuen
    l'hora d'aquí, sense ambigüitat, i per dins tot és en UTC."""
    if isinstance(dades, dict):
        return {(_local_clau(k) if isinstance(k, str) else k): publica(v) for k, v in dades.items()}
    if isinstance(dades, list):
        return [publica(v) for v in dades]
    if isinstance(dades, str):
        return _local_clau(dades)
    return dades


def _local_clau(text):
    if _CLAU.match(text):
        return iso_local(text, segons=len(text) > 17)
    return text
