#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Una sola regla per decidir si un mètode nou substitueix el que hi ha (ADR
0105): el nou guanya si s'equivoca menys en almenys SEGURETAT dels
REMOSTREJOS remostrejos per blocs (bootstrap), no per un marge fix del 5 %.

Els blocs són dies o episodis, perquè les hores d'un mateix dia o d'un
mateix episodi de pluja s'assemblen i no són casos independents: remostrejar
hora a hora faria creure que hi ha més dades de les que hi ha. La fan servir
la probabilitat de pluja i la temperatura (aprenentatge.py), el radar
(radar_fonts.py), el final de la pluja (fi_pluja.py), l'aire (aire.py), el
cel (nuvols.py) i la variant de l'arxiu amb avisos
(calibracio/pluja_casa_avisos.py); i «Com encerta» (historial.py, ADR 0110),
per comparar la web amb la climatologia, amb Meteocat i AEMET i amb ella
mateixa setmanes enrere (seguretat_periodes). Juanjo, 14-10-2026: «para ser coherentes y
evitar problemas en el futuro no habría que hacerlo todo…?».
"""
import numpy as np

REMOSTREJOS = 2000       # remostrejos per blocs
SEGURETAT = 0.95         # proporció de remostrejos en què el nou ha de guanyar
MIN_DIES_ENTRENAMENT = 7     # dies anteriors, com a mínim, per avaluar un dia (ADR 0106)
EPISODI_BUIT_H = 6           # hores seques que separen dos episodis de pluja


def seguretat(errors_nou, errors_actual, blocs, llavor=0):
    """Proporció de remostrejos per blocs (amb reposició) en què la suma
    d'errors del nou és menor que la de l'actual, amb els mateixos casos.
    errors_*: l'error de cada cas (quadràtic, absolut, minuts…); blocs: el
    dia o l'episodi de cada cas. None amb menys de dos blocs."""
    e_nou, e_actual = np.asarray(errors_nou, dtype=float), np.asarray(errors_actual, dtype=float)
    unics, idx = np.unique(np.asarray(blocs), return_inverse=True)
    if len(unics) < 2 or len(e_nou) != len(e_actual) or len(e_nou) != len(idx):
        return None
    per_bloc_nou = np.bincount(idx, e_nou, len(unics))
    per_bloc_actual = np.bincount(idx, e_actual, len(unics))
    tria = np.random.default_rng(llavor).integers(0, len(unics), (REMOSTREJOS, len(unics)))
    return round(float(np.mean(per_bloc_nou[tria].sum(axis=1) < per_bloc_actual[tria].sum(axis=1))), 3)


def seguretat_periodes(sumes_abans, casos_abans, sumes_ara, casos_ara, llavor=0):
    """Si un mètode s'equivoca menys ara que abans (ADR 0110): proporció de
    remostrejos per blocs, cada període pel seu compte perquè no tenen els
    mateixos casos, en què l'error mitjà per cas del període recent és menor
    que el de l'anterior. sumes_* i casos_*: la suma d'errors i els casos de
    cada bloc (dia). None amb menys de dos blocs amb casos en algun dels dos."""
    def mitjanes(sumes, casos, rng):
        s, n = np.asarray(sumes, dtype=float), np.asarray(casos, dtype=float)
        tria = rng.integers(0, len(s), (REMOSTREJOS, len(s)))
        total = n[tria].sum(axis=1)
        return np.where(total > 0, s[tria].sum(axis=1) / np.maximum(total, 1), np.nan)
    if min(sum(1 for n in casos_abans if n), sum(1 for n in casos_ara if n)) < 2:
        return None
    rng = np.random.default_rng(llavor)
    abans, ara = mitjanes(sumes_abans, casos_abans, rng), mitjanes(sumes_ara, casos_ara, rng)
    valids = ~(np.isnan(abans) | np.isnan(ara))
    return round(float(np.mean(ara[valids] < abans[valids])), 3) if valids.any() else None


def guanya(s):
    """Si amb aquesta seguretat el nou substitueix l'actual."""
    return s is not None and s >= SEGURETAT


# --- La validació: avanç temporal (ADR 0106) -----------------------------------------

def episodis(moments, plou, buit_h=EPISODI_BUIT_H):
    """L'episodi de pluja de cada cas (1, 2, …; 0 si no plou): les hores
    observades amb pluja separades per buit_h hores seques o menys formen un
    episodi. moments: l'hora observada de cada cas (ISO); plou: si hi va
    ploure."""
    import datetime as dt
    import hora as H
    # Per moment de debò i amb zona (ADR 0128): la nit del canvi d'hora, una
    # clau amb desfasament i una sense feien caure l'aprenentatge.
    hores = sorted({m for m, p in zip(moments, plou) if p}, key=H.utc)
    de, k, anterior = {}, 0, None
    for h in hores:
        t = H.utc(h)
        if anterior is None or t - anterior > dt.timedelta(hours=buit_h):
            k += 1
        de[h], anterior = k, t
    return np.array([de.get(m, 0) for m in moments])


def avanc(dies, episodi=None, min_dies=MIN_DIES_ENTRENAMENT):
    """Validació amb avanç temporal: per cada dia, (entrenament, avaluació)
    com a màscares. S'entrena amb els dies anteriors (min_dies com a mínim) i
    s'avalua el dia, com farà el programa, que es reajusta cada dia i
    s'aplica als següents; la validació creuada per setmanes entrenava amb
    setmanes posteriors a l'avaluada. Un episodi de pluja que creua la
    mitjanit s'aparta de l'entrenament del dia que avalua la seva part
    final: si no, el model ja l'hauria vist. dies: el dia de l'hora
    observada de cada cas; episodi: el d'episodis(), opcional."""
    dies = np.asarray(dies)
    for d in sorted(set(dies)):
        ent, aval = dies < d, dies == d
        if len(set(dies[ent])) < min_dies:
            continue
        if episodi is not None:
            del_dia = set(np.asarray(episodi)[aval]) - {0}
            if del_dia:
                ent = ent & ~np.isin(episodi, list(del_dia))
        yield ent, aval
