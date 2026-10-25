#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Riesgo de desbordamiento de la riera de Sant Cugat en Montflorit (ADR 0027).

La riera nace en Collserola, cruza Sant Cugat y pasa por Montflorit. Su
cuenca es pequeña (unos 50 km²) y responde enseguida: las tres veces
conocidas se desbordó justo al acabar las 3 horas más lluviosas, con 53 mm en
esas 3 horas en la estación de Meteocat de Sant Cugat (29-04-2024) y con 67
(29-09-2026 y 04-10-2026). Por eso se mira:

- **Lo medido**: la lluvia semihoraria de Sant Cugat en la página de meteo.cat
  (va unos 30 minutos por detrás). La del Observatori Fabra, en la cresta de
  Collserola, junto a Les Planes, donde nace la riera, y la de Montflorit, en
  la parte baja, se guardan y se dicen en el aviso, pero no deciden.
- **Lo que viene**: la lluvia que el radar ve y lleva hacia delante sobre el
  centro de la cuenca (nowcast.py, ADR 0019), que cubre también la media hora
  que la estación va por detrás.
- **El índice**: la lluvia de 3 horas más alta que se alcanzará en la hora
  siguiente, juntando las dos: lo medido en las últimas 3 horas, en las
  últimas 2,5 más la media hora prevista o en las últimas 2 más la hora
  prevista. La de 6 horas, del mismo momento: el nivel se decide con las
  dos lluvias de cada momento, no con dos máximos de momentos distintos
  (auditoría del 09-10-2026).

Con RIERA_ATENCIO_MM en 3 horas hay aviso (a los suscriptores, al canal y en
las notificaciones, avisos_bot.py; hasta el 08-10-2026, también a Juanjo
aparte), y con RIERA_PERILL_MM en
3 horas y RIERA_PERILL_6H_MM en 6, otra vez: el 13-09-2025 cayeron 52 mm en
3 horas sobre suelo seco, sin más lluvia antes, y no se desbordó. Una sola vez
cada nivel por episodio. Un episodio empieza con RIERA_REGISTRE_MM
y acaba tras RIERA_FI_H horas por debajo; al acabar se apunta en el registro
(riera.csv) con sus máximos, para ajustar los umbrales con lo que pase.

Uso:
  python3 riera.py ara                  el índice ahora (con red)
  python3 riera.py avisa CASA.json      mira los datos y apunta el episodio
  python3 riera.py estat                el episodio en curso
  python3 riera.py resum                los episodios apuntados
  python3 riera.py previsio             la previsió de crescuda de les properes hores (amb xarxa)
  python3 riera.py previsio-resum       les previsions apuntades i el que va caure
"""
import csv
import datetime as dt
import json
import math
import os
import sys

import config as C
import hora as H
import nowcast as N

DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
ESTADO = os.path.join(os.path.dirname(DIR), "riera.json")
REGISTRO = os.path.join(DIR, "riera.csv")
CAMPOS = ["inici", "fi", "hora_max", "index_max", "mm_3h_max", "mm_6h_max", "capcalera_3h_max",
          "avis_atencio", "avis_perill", "desbordament"]
MITJA_HORA = dt.timedelta(minutes=30)
# Con la estación más atrasada que esto, lo medido ya no sirve para avisar.
RETARD_MAX = dt.timedelta(hours=2)


def files(codi, ahora, hores, lector):
    """Lluvia semihoraria de la estación que cubre las últimas hores: la de
    hoy y, si hace falta, la de ayer (días UTC)."""
    import prevision as P
    hoy = ahora.astimezone(dt.timezone.utc).date()
    dies = [hoy]
    if (ahora - dt.timedelta(hours=hores + 1)).astimezone(dt.timezone.utc).date() < hoy:
        dies.insert(0, hoy - dt.timedelta(days=1))
    res = []
    for dia in dies:
        res += P.taula_meteocat(codi, dia, lector)
    return res


def acumulat(filas, fins, hores):
    """mm de las medias horas que caen enteras entre fins - hores y fins."""
    desde = fins - dt.timedelta(hours=hores)
    return round(sum(mm for t, mm in filas if t >= desde and t + MITJA_HORA <= fins), 1)


# Medias horas que pueden faltar en una ventana sin que el cálculo se dé por
# incompleto: una en 3 horas (5 de 6) y dos en 6 (10 de 12). Una media hora
# ausente cuenta como cero y rebaja el índice: con más huecos no se puede
# decir que el riesgo haya bajado (auditoría del 07-10-2026, ADR 0038).
FORATS_MAX = {3: 1, 6: 2}


def cobertura(filas, fins, hores):
    """Medias horas presentes entre fins - hores y fins, de las hores * 2 que
    debería haber."""
    desde = fins - dt.timedelta(hours=hores)
    return sum(1 for t, _ in filas if t >= desde and t + MITJA_HORA <= fins)


def incomplet(filas, fins):
    """True si a alguna de las dos ventanas (3 y 6 horas) le faltan más
    medias horas de las admitidas."""
    return any(hores * 2 - cobertura(filas, fins, hores) > forats for hores, forats in FORATS_MAX.items())


def previst(nc, desde, minuts):
    """mm que el radar da sobre la cuenca entre desde (el final de lo medido)
    y desde + minuts. La imagen del radar suele ser más nueva que la última
    media hora de la estación: el hueco entre las dos se cuenta con la lluvia
    que ve la imagen."""
    passos = ((nc or {}).get("llocs") or {}).get("conca")
    if not minuts or not passos:
        return 0.0
    fin = desde + dt.timedelta(minutes=minuts)
    t0 = H.llegeix(nc["hora"])
    mm = 0.0
    if t0 > desde:
        mm += passos[0]["mm_h"] * (min(t0, fin) - desde).total_seconds() / 3600
    tram = N.en_tram(nc, "conca", max(desde, t0), fin) if fin > t0 else None
    return round(mm + (tram["mm"] if tram else 0.0), 1)


def nivell(index, index_6h):
    """Peligro con la lluvia de 3 y de 6 horas; atención y registro, con la
    de 3."""
    if index >= C.RIERA_PERILL_MM and index_6h >= C.RIERA_PERILL_6H_MM:
        return "perill"
    for nom, llindar in (("atencio", C.RIERA_ATENCIO_MM), ("registre", C.RIERA_REGISTRE_MM)):
        if index >= llindar:
            return nom
    return None


def horitzo(fins, ahora):
    """Minutos desde el final de lo medido hasta una hora después de ahora,
    en medias horas enteras hacia arriba. La estación llega con retraso (unos
    30 minutos; se admiten hasta 2 horas): la «hora siguiente» se cuenta
    desde ahora, no desde la última medida (auditoría del 08-10-2026)."""
    return int(math.ceil(((ahora - fins).total_seconds() / 60 + 60) / 30) * 30)


NIVELLS = (None, "registre", "atencio", "perill")


def nivell_amb_radar(filas, fins, nc, ahora):
    """El nivel más alto que se alcanza de aquí a una hora, con la lluvia de
    3 y de 6 horas del mismo momento: (nivell, mm de 3 h, mm de 6 h, dentro
    de cuántos minutos desde ahora). Hasta la auditoría del 09-10-2026 el
    máximo de 3 horas y el de 6 se tomaban por separado, de momentos
    distintos, y podían dar peligro sin que ningún momento cumpliera las dos
    condiciones: 50 mm de un chaparrón sobre suelo seco ahora (el caso del
    13-09-2025, que no se desbordó) y 60 en 6 horas una hora después, con
    10 mm más. Del nivel alcanzado, el momento con más lluvia de 3 horas."""
    millor = None
    for minuts in range(0, horitzo(fins, ahora) + 1, 30):
        radar = previst(nc, fins, minuts)
        mm3 = round(acumulat(filas, fins, max(C.RIERA_HORES - minuts / 60, 0)) + radar, 1)
        mm6 = round(acumulat(filas, fins, max(6 - minuts / 60, 0)) + radar, 1)
        d_aqui = max(0, int(minuts - (ahora - fins).total_seconds() / 60))
        n = nivell(mm3, mm6)
        clau = (NIVELLS.index(n), mm3, d_aqui)
        if millor is None or clau > millor[0]:
            millor = (clau, n, mm3, mm6, d_aqui)
    return millor[1:]


# --- Les estacions particulars de Sant Cugat (Weather Underground) ---------------
# Un dada cada 5 minuts i gairebé sense retard, al centre i a la part alta de
# la conca (C.RIERA_VEINES; Juanjo, 18-10-2026). La seva mediana fa el mateix
# índex que Meteocat (el mesurat més el que porta el radar) i l'avís pren el
# nivell més alt dels dos: només pot avançar o pujar un avís, mai treure'l.
# Només es consulten quan plou o el radar en veu sobre la conca, o hi ha un
# episodi obert, amb un tope diari (C.RIERA_VEINES_MAX_DIA); el dia d'ahir
# (per a les finestres que passen la mitjanit) es guarda i es baixa un cop.
ESTAT_DIR = os.path.dirname(DIR)
COMPTADOR_WU = os.path.join(ESTAT_DIR, "riera-wu.json")
CACHE_WU = os.path.join(ESTAT_DIR, "riera-wu-ahir")
REGISTRE_WU = os.path.join(DIR, "riera-veines.csv")
CAMPS_WU = ["t", "xv_3h", "xv_index", "xv_nivell", "n", "veines_3h", "veines_6h", "veines_index",
            "veines_nivell", "font"]


class Consulta:
    """Les consultes a Weather Underground, comptades: amb el tope del dia
    gastat, no se'n fa cap més fins l'endemà."""
    def __init__(self, ahora, consulta=None):
        import wunderground as W
        self.W, self.fer = W, consulta or W._consulta
        self.dia = H.dia_local(ahora).isoformat()
        try:
            with open(COMPTADOR_WU, encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            c = {}
        self.n = c.get("n", 0) if c.get("dia") == self.dia else 0

    def __call__(self, ruta, params):
        if self.n >= C.RIERA_VEINES_MAX_DIA:
            raise RuntimeError("tope diari de consultes de la riera")
        self.n += 1
        try:
            with open(COMPTADOR_WU, "w", encoding="utf-8") as f:
                json.dump({"dia": self.dia, "n": self.n}, f)
        except OSError:
            pass
        return self.fer(ruta, params)


def increments(lectures):
    """La pluja de cada lectura a partir de l'acumulada del dia, que torna a
    zero quan l'estació canvia de dia."""
    res, abans = [], None
    for x in lectures:
        v = x.get("pluja_avui") or 0
        res.append((x["t"], v if abans is None or v < abans else v - abans))
        abans = v
    return res


def serie_veina(estacio, ahora, consulta):
    """[(t, mm)] de les últimes 6 hores o més d'una estació."""
    W = consulta.W
    avui = W.files(consulta("observations/all/1day", {"stationId": estacio}))
    if avui and avui[0]["t"] > ahora - dt.timedelta(hours=6):
        ahir = (H.dia_local(ahora) - dt.timedelta(days=1)).strftime("%Y%m%d")
        ruta = os.path.join(CACHE_WU, f"{estacio}-{ahir}.json")
        try:
            with open(ruta, encoding="utf-8") as f:
                obs = json.load(f)
        except (OSError, ValueError):
            obs = consulta("history/all", {"stationId": estacio, "date": ahir})
            try:
                os.makedirs(CACHE_WU, exist_ok=True)
                for vell in os.listdir(CACHE_WU):
                    if not vell.endswith(f"-{ahir}.json"):
                        os.remove(os.path.join(CACHE_WU, vell))
                with open(ruta, "w", encoding="utf-8") as f:
                    json.dump(obs, f)
            except OSError:
                pass
        avui = W.files(obs) + avui
    return increments(avui)


def calcula_veines(ahora, nc, consulta):
    """La mediana de les estacions amb dada recent, amb el mateix índex que
    Meteocat. None si n'hi ha menys de C.RIERA_VEINES_MIN."""
    import statistics
    series = {}
    for e in C.RIERA_VEINES:
        try:
            s = serie_veina(e, ahora, consulta)
        except Exception:
            continue
        if s and ahora - s[-1][0] <= dt.timedelta(minutes=C.RIERA_VEINES_FRESCA_MIN):
            series[e] = s
    if len(series) < C.RIERA_VEINES_MIN:
        return None
    fins = min(s[-1][0] for s in series.values())
    med = lambda h: round(statistics.median(  # noqa: E731
        sum(d for t, d in s if fins - dt.timedelta(hours=h) < t <= fins) for s in series.values()), 1)
    millor = None
    for minuts in (0, 30, 60):
        radar = previst(nc, fins, minuts)
        mm3 = round(med(max(C.RIERA_HORES - minuts / 60, 0)) + radar, 1)
        mm6 = round(med(max(6 - minuts / 60, 0)) + radar, 1)
        n = nivell(mm3, mm6)
        clau = (NIVELLS.index(n), mm3, minuts)
        if millor is None or clau > millor[0]:
            millor = (clau, n, mm3, mm6, minuts)
    return {"n": len(series), "estacions": sorted(series), "fins": H.clau(fins),
            "mm_3h": med(C.RIERA_HORES), "mm_6h": med(6), "nivell": millor[1], "index": millor[2],
            "index_6h": millor[3], "index_d_aqui_a_min": millor[4]}


def cal_veines(res, nc, ahora, pluja_barri=None):
    """Si cal mirar les estacions: plou a Meteocat, el radar en veu sobre la
    conca en l'hora que ve, plou de manera moderada o més al barri o hi ha un
    episodi obert. pluja_barri: la pluja de la darrera mitja hora de la xarxa
    del barri (casa.consens, la mediana); des d'1 mm, 2 mm/h, el primer graó
    de l'escala d'intensitat de la web: amb plugim la riera no puja (Juanjo,
    18-10-2026: «que llueva, pero de forma importante»). Cobreix la pluja que
    el radar encara no veu sobre la conca mentre Meteocat no s'ha actualitzat.
    Sense dades recents de Meteocat, sempre: les estacions el substitueixen
    encara que no plogui, perquè sense ell no se sap què ha plogut a la conca
    (Juanjo, 21-10-2026: «si el resto de estaciones de sant cugat sí que
    funcionan, por qué no la reemplazan?»)."""
    if res is None:
        return True
    if (res.get("mm_3h") or 0) >= 1:
        return True
    if nc and previst(nc, ahora, 60) >= 1:
        return True
    if (pluja_barri or 0) >= C.RIERA_VEINES_BARRI_MM:
        return True
    return bool(llegeix_estat().get("episodi"))


def calcula(ahora, nc, lector=None, consulta=None, pluja_barri=None):
    """Estado de la riera ahora, para casa.json. Con Meteocat y, si hace falta,
    las estaciones particulares de Sant Cugat (calcula_veines): manda el nivel
    más alto. None si no hay datos recientes de ninguna de las dos."""
    res = calcula_meteocat(ahora, nc, lector)
    veines = None
    if consulta is None and lector is None:
        import wunderground as W
        consulta = Consulta(ahora) if W.lectura_disponible() else None
    elif consulta is not None and not isinstance(consulta, Consulta):
        consulta = Consulta(ahora, consulta)
    if consulta is not None and cal_veines(res, nc, ahora, pluja_barri):
        try:
            veines = calcula_veines(ahora, nc, consulta)
        except Exception:
            veines = None
    if res is None and veines is None:
        return None
    if res is None:
        # Sense Meteocat, les estacions soles (casa.py ho diu als errors).
        res = {"estacio": None, "sense_meteocat": True, "fins": veines["fins"], "mm_3h": veines["mm_3h"],
               "mm_6h": veines["mm_6h"], "mm_1h": None, "incomplet": False,
               "radar_1h": previst(nc, H.llegeix(veines["fins"]), 60) if nc else None,
               "capcalera": None, "nivell": None, "index": 0.0, "index_6h": 0.0, "index_d_aqui_a_min": 0}
    res["veines"] = veines
    res["font"] = "meteocat"
    if veines and (NIVELLS.index(veines["nivell"]), veines["index"]) > (NIVELLS.index(res["nivell"]), res["index"]):
        res.update({k: veines[k] for k in ("nivell", "index", "index_6h", "index_d_aqui_a_min")}, font="veines")
    elif res.get("sense_meteocat"):
        res["font"] = "veines"
    return res


def darrera_meteocat(ahora, lector=None):
    """Hasta cuándo tiene lluvia la estación de Meteocat de la riera, para
    decir en la página desde cuándo falta (ISO, o None si no hay nada en las
    últimas horas)."""
    filas = files(C.RIERA_ESTACIO, ahora, 6, lector)
    return H.clau(filas[-1][0] + MITJA_HORA) if filas else None


def calcula_meteocat(ahora, nc, lector=None):
    """La riera amb l'estació de Meteocat de Sant Cugat. None si no dona
    dades recents."""
    filas = files(C.RIERA_ESTACIO, ahora, 6, lector)
    if not filas:
        return None
    fins = filas[-1][0] + MITJA_HORA
    if ahora - fins > RETARD_MAX:
        return None
    h = C.RIERA_HORES
    res = {"estacio": C.ESTACIONES.get(C.RIERA_ESTACIO, C.RIERA_ESTACIO),
           "fins": H.clau(fins),
           "mm_3h": acumulat(filas, fins, h), "mm_6h": acumulat(filas, fins, 6),
           "mm_1h": acumulat(filas, fins, 1),     # per al registre de l'aprenentatge (ADR 0042)
           "incomplet": incomplet(filas, fins),
           "radar_1h": previst(nc, fins, (ahora - fins).total_seconds() / 60 + 60) if nc else None,
           "capcalera": None}
    res["nivell"], res["index"], res["index_6h"], res["index_d_aqui_a_min"] = nivell_amb_radar(filas, fins, nc, ahora)
    try:
        codi, nom = C.RIERA_CAPCALERA
        cap = files(codi, ahora, 6, lector)
        if cap:
            fc = cap[-1][0] + MITJA_HORA
            res["capcalera"] = {"estacio": nom, "fins": H.clau(fc),
                                "mm_3h": acumulat(cap, fc, h), "mm_6h": acumulat(cap, fc, 6)}
    except Exception:
        pass
    return res


def coma(x):
    return f"{x:.0f}" if x >= 10 else f"{x:.1f}".replace(".", ",")


def missatge(riera, nom):
    v = riera.get("veines") if riera.get("font") == "veines" else None
    if v:
        # Ha decidit la mediana de les estacions particulars (calcula).
        riera = {**riera, "mm_3h": v["mm_3h"], "mm_6h": v["mm_6h"], "fins": v["fins"]}
    hora = H.local(riera["fins"]).strftime("%H:%M")
    if nom == "perill":
        cap = ("Riera de Sant Cugat, perill de desbordament a Montflorit: a Sant Cugat han caigut "
               f"{coma(riera['mm_3h'])} mm en 3 hores i {coma(riera['mm_6h'])} en 6 (fins a les {hora})")
    else:
        cap = ("Riera de Sant Cugat, atenció: a Sant Cugat han caigut "
               f"{coma(riera['mm_3h'])} mm en 3 hores (fins a les {hora})")
    radar = riera.get("radar_1h")
    if radar and radar >= 1:
        cap += f" i el radar en preveu uns {coma(radar)} més a la conca des de llavors fins d'aquí a una hora"
    cap += "."
    altres = []
    if riera.get("capcalera"):
        altres.append(f"al Fabra (Collserola), {coma(riera['capcalera']['mm_3h'])} mm")
    if altres:
        cap += " En 3 hores, " + " i ".join(altres) + "."
    if nom == "perill":
        cap += (" Els desbordaments del 2024 i el 2026 van arribar amb 53 a 67 mm en 3 hores i més de 65 "
                "en 6, en acabar la pluja més forta.")
    else:
        cap += (f" S'ha desbordat amb {C.RIERA_PERILL_MM} mm o més en 3 hores i "
                f"{C.RIERA_PERILL_6H_MM} en 6.")
    if riera.get("incomplet"):
        cap += " A l'estació li falten mesures: la pluja real pot ser més alta."
    if v:
        cap += f" (Mediana de {v['n']} estacions particulars de Sant Cugat.)"
    return cap


def missatge_fi(riera, ep):
    """El final d'un episodi amb avís: 3 hores sense pluja forta a Sant Cugat
    ni al radar."""
    que = "ha passat el perill de desbordament" if ep["avisos"].get("perill") else "ja no hi ha risc de desbordament"
    return (f"Riera de Sant Cugat: {que}. A Sant Cugat fa {C.RIERA_FI_H} hores que no plou amb força "
            f"({coma(riera['mm_3h'])} mm en les últimes 3 hores) i el radar no hi veu pluja forta. "
            "Si torna a ploure fort, tornarà l'avís.")


def fila_registro(ep):
    fila = dict.fromkeys(CAMPOS, "")
    fila.update({k: ep.get(k, "") for k in ("inici", "hora_max", "index_max", "mm_3h_max",
                                             "mm_6h_max", "capcalera_3h_max")})
    fila["fi"] = ep["vist"]
    fila["avis_atencio"] = ep["avisos"].get("atencio") or ""
    fila["avis_perill"] = ep["avisos"].get("perill") or ""
    return fila


def compara(estat, riera, ahora):
    """Pone al día el episodio y devuelve (mensaje o None, fila del registro
    del episodio que acaba o None)."""
    ep = estat.get("episodi")
    if not riera:
        return None, None
    ara = H.clau(ahora)
    senyal = riera["index"] >= C.RIERA_REGISTRE_MM
    text = fila = None
    # Con huecos en la estación, lo medido puede quedarse corto: el episodio
    # no se cierra hasta tener las medias horas que faltan.
    if ep and not senyal and not riera.get("incomplet") \
            and ahora - H.llegeix(ep["vist"]) >= dt.timedelta(hours=C.RIERA_FI_H):
        # Si es va avisar, es diu que ha passat (Juanjo, 08-10-2026): un sol
        # missatge per episodi, i només després de 3 hores de calma, perquè
        # no es converteixi en una successió d'avís i contraavís.
        if ep["avisos"]:
            text = missatge_fi(riera, ep)
        fila, ep = fila_registro(ep), None
    if senyal:
        if not ep:
            ep = {"inici": ara, "avisos": {}, "index_max": 0, "mm_3h_max": 0, "mm_6h_max": 0,
                  "capcalera_3h_max": 0, "hora_max": ara}
        ep["vist"] = ara
        if riera["index"] > ep["index_max"]:
            ep["index_max"], ep["hora_max"] = riera["index"], ara
        ep["mm_3h_max"] = max(ep["mm_3h_max"], riera["mm_3h"])
        ep["mm_6h_max"] = max(ep["mm_6h_max"], riera["mm_6h"])
        if riera.get("capcalera"):
            ep["capcalera_3h_max"] = max(ep["capcalera_3h_max"], riera["capcalera"]["mm_3h"])
        nom = nivell(riera["index"], riera.get("index_6h", riera["mm_6h"]))
        if nom in ("perill", "atencio") and not ep["avisos"].get(nom):
            text = missatge(riera, nom)
            ep["avisos"][nom] = ara
            ep["avisos"].setdefault("atencio", ara)
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
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nou:
            w.writeheader()
        w.writerow(fila)


def apunta_veines(riera, ahora):
    """Les dues fonts, cada vegada que s'han mirat les estacions, per comparar
    en el registre (riera-veines.csv) i ajustar els llindars."""
    v = (riera or {}).get("veines")
    if not v:
        return
    fila = {"t": H.clau(ahora),
            "xv_3h": "" if riera.get("sense_meteocat") else riera.get("mm_3h"),
            "xv_index": "", "xv_nivell": "", "n": v["n"], "veines_3h": v["mm_3h"], "veines_6h": v["mm_6h"],
            "veines_index": v["index"], "veines_nivell": v["nivell"] or "", "font": riera.get("font")}
    if riera.get("font") == "meteocat" and not riera.get("sense_meteocat"):
        fila.update(xv_index=riera["index"], xv_nivell=riera["nivell"] or "")
    try:
        nou = not os.path.exists(REGISTRE_WU)
        os.makedirs(DIR, exist_ok=True)
        with open(REGISTRE_WU, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPS_WU)
            if nou:
                w.writeheader()
            w.writerow(fila)
    except OSError:
        pass


def avisa(ruta, ahora=None):
    ahora = ahora or H.ara()
    # Las respuestas de Juanjo a la pregunta del desbordamiento, cada minuto,
    # para que el mensaje diga enseguida que se han apuntado.
    try:
        respostes(ahora)
    except Exception as ex:
        print("Respostes del desbordament:", ex, file=sys.stderr)
    with open(ruta, encoding="utf-8") as f:
        salida = json.load(f)
    # Con datos viejos (la pasada ha fallado), no se avisa.
    if ahora - H.llegeix(salida["generat"]) > dt.timedelta(minutes=C.INTERVALO_CASA_MIN):
        return None
    estat = llegeix_estat()
    apunta_veines(salida.get("riera"), ahora)
    text, fila = compara(estat, salida.get("riera"), ahora)
    desa_estat(estat)
    if fila:
        apunta(fila)
        try:
            pregunta_desbordament(fila, ahora)
        except Exception as ex:
            print("Pregunta del desbordament:", ex, file=sys.stderr)
    if text:
        print(text)         # al registro del NAS; ya no se manda a Juanjo (ADR 0027)
    return text


# --- ¿Se desbordó? La confirmación de Juanjo ------------------------------------
# Auditoría del 18-10-2026: el registro tiene la columna «desbordament» y nadie
# la rellenaba, así que no se puede saber si el aviso acierta. Al cerrarse un
# episodio con aviso (atención o peligro), el bot de los agentes le pregunta a
# Juanjo con botones, como con la niebla (confirmacio.py); su respuesta va a
# riera-confirmacions.csv y a la columna del episodio en riera.csv.
PREGUNTES = os.path.join(DIR, "riera-preguntes.csv")
CONFIRMACIONS = os.path.join(DIR, "riera-confirmacions.csv")
CAMPS_PREGUNTA = ["inici", "fi", "index_max", "nivell"]
RESPOSTES = {"si": "Sí, se ha desbordado", "no": "No se ha desbordado", "nose": "No lo sé"}


def telegram(metode, **params):
    import confirmacio as CF
    return CF.telegram(metode, CF.CONFIG_BOT, **params)


def _config_bot():
    import confirmacio as CF
    return CF.CONFIG_BOT


def pregunta_desbordament(fila, ara=None):
    """La pregunta por Telegram al cerrarse un episodio con aviso. Solo donde
    está el bot de los agentes (el NAS; la reserva de IONOS no lo tiene).
    Devuelve el identificador del mensaje o None."""
    import confirmacio as CF
    if not (fila.get("avis_atencio") or fila.get("avis_perill")) or not os.path.exists(_config_bot()):
        return None
    ara = ara or H.ara()
    nivell = "perill" if fila.get("avis_perill") else "atencio"
    inici, fi = (H.local(fila[k]) for k in ("inici", "fi"))
    avis = H.local(fila["avis_perill"] or fila["avis_atencio"])
    text = (f"Riera de Sant Cugat: ¿se ha desbordado en Montflorit en este episodio? "
            f"Lluvia desde el {inici:%d-%m} a las {inici:%H:%M} hasta las {fi:%H:%M} del {fi:%d-%m}; "
            f"aviso de {'peligro' if nivell == 'perill' else 'atención'} a las {avis:%H:%M}; "
            f"como mucho, {coma(float(fila['index_max']))} mm en 3 horas. "
            "Con tu respuesta se comprueba si el aviso acierta.")
    teclat = {"inline_keyboard": [[{"text": t, "callback_data": f"riera:{k}"} for k, t in RESPOSTES.items()]]}
    with open(_config_bot(), encoding="utf-8") as f:
        chat = json.load(f)["chat_id"]
    r, _ = telegram("sendMessage", chat_id=chat, text=CF.capcalera(text), reply_markup=teclat)
    CF.afegeix(PREGUNTES, ["t", "missatge"] + CAMPS_PREGUNTA,
               {"t": H.clau(ara), "missatge": r["message_id"], "inici": fila["inici"],
                "fi": fila["fi"], "index_max": fila["index_max"], "nivell": nivell})
    return r["message_id"]


def respostes(ara=None):
    """Las respuestas a los botones, una vez cada una, en riera-confirmacions.csv,
    y la columna «desbordament» del episodio en riera.csv («si» o «no»)."""
    import confirmacio as CF
    if not os.path.exists(PREGUNTES):
        return 0
    n = CF.respostes("riera", PREGUNTES, CONFIRMACIONS, RESPOSTES, CAMPS_PREGUNTA, telegram,
                     ara or H.ara())
    if n:
        omple_desbordament()
    return n


def omple_desbordament():
    """Pasa las respuestas («si» o «no») a la columna del episodio en riera.csv."""
    import confirmacio as CF
    resp = {r["pregunta_inici"]: r["resposta"] for r in CF.files(CONFIRMACIONS) if r["resposta"] in ("si", "no")}
    if not resp or not os.path.exists(REGISTRO):
        return 0
    with open(REGISTRO, encoding="utf-8") as f:
        files_ = list(csv.DictReader(f))
    n = 0
    for fila in files_:
        if fila["inici"] in resp and fila.get("desbordament") != resp[fila["inici"]]:
            fila["desbordament"] = resp[fila["inici"]]
            n += 1
    if n:
        with open(REGISTRO + ".tmp", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            w.writerows({c: fila.get(c, "") for c in CAMPOS} for fila in files_)
        os.replace(REGISTRO + ".tmp", REGISTRO)
    return n


# --- La previsió de crescuda (ADR 0107) ------------------------------------------------
# El que els models preveuen a la conca per a les properes hores, per a la
# pàgina «Riera»: una previsió, no un avís (Juanjo, 19-10-2026: «no podemos
# dar falsos positivos que provoquen alarma… dejando muy claro que es una
# previsión y que la situación puede cambiar en cualquier momento»). Amb
# l'arxiu 2024-2026, el màxim dels models amb 20 mm o més en 3 hores va
# sortir 27 dies, 4 amb 35 mm reals; dels tres desbordaments en va veure
# venir un (el 04-10-2026), un a mitges (29-04-2024, 30 mm) i cap senyal del
# 29-09-2026 (14 mm previstos, 66 caiguts).

ESTAT_PREVISIO = os.path.join(ESTAT_DIR, "riera-previsio.json")
REGISTRE_PREVISIO = os.path.join(DIR, "riera-previsio.csv")
CAMPS_PREVISIO = ["t", "nivell", "mm_3h_max", "mm_3h_mitjana", "finestra_ini", "finestra_fi", "mm_6h_max",
                  "mm_6h_mitjana", "model_max", "xv_24h"]
URL_PREVISIO = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation"
                "&models={models}&forecast_days=2&timezone=GMT")


def _suma(valors, i, n):
    tros = [v for v in valors[max(0, i - n + 1):i + 1] if v is not None]
    return round(sum(tros), 1) if tros else None


def previsio_models(hores, per_model, ahora, horitzo_h=None, llindar=None):
    """La previsió de crescuda amb les sèries horàries de cada model a la
    conca ({model: [mm per hora]}; hores: ISO, l'hora en què comença cada
    mm): per a cada model, la seva pluja de 3 hores més alta en les properes
    horitzo_h hores; mana el model que més en dona («si un model ho veu»), amb
    la seva finestra, i s'hi afegeix la mitjana dels models en aquesta
    finestra. El mateix en 6 hores, i el nivell «possible» des de llindar mm
    en 3 hores."""
    horitzo_h = horitzo_h or C.RIERA_PREVISIO_HORES
    llindar = llindar or C.RIERA_PREVISIO_MM
    fi = ahora + dt.timedelta(hours=horitzo_h)
    dins = [i for i, h in enumerate(hores) if ahora - dt.timedelta(hours=1) < H.llegeix(h) <= fi]
    series = {m: s for m, s in per_model.items() if any(i < len(s) and s[i] is not None for i in dins)}
    if not dins or not series:
        return None
    mitjana = []
    for i in range(len(hores)):
        vals = [s[i] for s in series.values() if i < len(s) and s[i] is not None]
        mitjana.append(round(sum(vals) / len(vals), 2) if vals else None)
    res = {"generat": H.clau(ahora), "horitzo_h": horitzo_h, "models": list(series),
           "hores": [{"hora": hores[i], "max": max([s[i] for s in series.values() if i < len(s) and s[i] is not None] or [None]),
                      "mitjana": mitjana[i]} for i in dins]}
    for n, nom in ((3, "3h"), (6, "6h")):
        millor_model, millor_i, millor_mm = None, dins[0], -1.0
        for m, s in series.items():
            for i in dins:
                v = _suma(s, i, n)
                if v is not None and v > millor_mm:
                    millor_model, millor_i, millor_mm = m, i, v
        ini = H.llegeix(hores[max(0, millor_i - n + 1)])
        res[f"mm_{nom}_max"] = max(millor_mm, 0.0)
        res[f"mm_{nom}_mitjana"] = _suma(mitjana, millor_i, n) or 0.0
        res[f"finestra_{nom}"] = {"ini": H.clau(ini), "fi": H.clau(H.llegeix(hores[millor_i]) + dt.timedelta(hours=1))}
        if n == 3:
            res["per_model"] = {m: (_suma(s, millor_i, 3) or 0.0) for m, s in series.items()}
            res["model_max"] = millor_model
    res["nivell"] = "possible" if res["mm_3h_max"] >= llindar else None
    res["llindar_mm"] = llindar
    return res


def previsio(ahora, get=None, lector=None):
    """La previsió de crescuda per a casa.json: els quatre models a la conca
    (CONCA_RIERA), la pluja de les últimes 24 hores a Sant Cugat (el sòl
    mullat distingeix els casos, docs/estadistica.md 12.3) i des de quan
    dura el «possible» (ESTAT_PREVISIO), perquè la pestanya el senyali com a
    nou. S'apunta cada passada al registre per mesurar-la."""
    import prevision as P
    get = get or P.get_reintenta
    models = C.MODELOS_FINOS + [C.MODEL_ECMWF]
    d = json.loads(get(URL_PREVISIO.format(lat=C.CONCA_RIERA[0], lon=C.CONCA_RIERA[1], models=",".join(models))))
    h = d["hourly"]
    per_model = {m: h.get(f"precipitation_{m}") or [] for m in models}
    hores = h["time"]
    # Les hores d'Open-Meteo, en UTC (timezone=GMT): claus «…Z» (ADR 0128).
    # Fins a la 3.200.0 es demanaven en hora de Madrid i s'hi posava el
    # desfasament d'ara, que ja no valia passat un canvi d'hora.
    hores_tz = [t + "Z" for t in hores]
    res = previsio_models(hores_tz, per_model, ahora)
    if res is None:
        return None
    try:
        filas = files(C.RIERA_ESTACIO, ahora, 24, lector)
        fins = filas[-1][0] + MITJA_HORA if filas else None
        res["xv_24h"] = acumulat(filas, fins, 24) if fins else None
        res["xv_fins"] = H.clau(fins) if fins else None
    except Exception:
        res["xv_24h"], res["xv_fins"] = None, None
    estat = {}
    try:
        with open(ESTAT_PREVISIO, encoding="utf-8") as f:
            estat = json.load(f)
    except (OSError, ValueError):
        pass
    if res["nivell"]:
        res["inici"] = estat.get("inici") if estat.get("inici") else res["generat"]
        estat = {"inici": res["inici"], "darrer": res["generat"], "mm_3h_max": res["mm_3h_max"]}
    else:
        estat = {}
    try:
        os.makedirs(ESTAT_DIR, exist_ok=True)
        with open(ESTAT_PREVISIO + ".tmp", "w", encoding="utf-8") as f:
            json.dump(estat, f)
        os.replace(ESTAT_PREVISIO + ".tmp", ESTAT_PREVISIO)
    except OSError:
        pass
    apunta_previsio(res)
    return res


def apunta_previsio(res):
    try:
        os.makedirs(DIR, exist_ok=True)
        nou = not os.path.exists(REGISTRE_PREVISIO)
        with open(REGISTRE_PREVISIO, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPS_PREVISIO)
            if nou:
                w.writeheader()
            w.writerow({"t": res["generat"], "nivell": res["nivell"] or "", "mm_3h_max": res["mm_3h_max"],
                        "mm_3h_mitjana": res["mm_3h_mitjana"], "finestra_ini": res["finestra_3h"]["ini"],
                        "finestra_fi": res["finestra_3h"]["fi"], "mm_6h_max": res["mm_6h_max"],
                        "mm_6h_mitjana": res["mm_6h_mitjana"], "model_max": res.get("model_max") or "",
                        "xv_24h": "" if res.get("xv_24h") is None else res["xv_24h"]})
    except OSError:
        pass


def resum_previsio(registre_xv=None):
    """Per dies: el màxim previst en 3 hores (l'últim de cada dia abans de la
    finestra) i el que va caure a Sant Cugat (registre/meteocat-XV.csv), per
    decidir el llindar amb dades (ADR 0107)."""
    if not os.path.exists(REGISTRE_PREVISIO):
        return "Encara no hi ha cap previsió apuntada."
    with open(REGISTRE_PREVISIO, encoding="utf-8") as f:
        files_ = list(csv.DictReader(f))
    xv = {}
    ruta = registre_xv or os.path.join(DIR, f"meteocat-{C.RIERA_ESTACIO}.csv")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    xv[H.clau(r["fins"])[:13]] = float(r["pluja_mm"])
                except (KeyError, ValueError):
                    pass
    per_dia = {}
    for r in files_:
        d = H.dia_local(r["finestra_fi"]).isoformat()
        v = float(r["mm_3h_max"] or 0)
        if v >= per_dia.get(d, (0, None))[0]:
            per_dia[d] = (v, r["t"])
    linies = [f"{'dia':10} {'previst 3h':>10} {'real 3h':>8}  (XV, màxim del dia)"]
    hores = sorted(xv)
    for d in sorted(per_dia):
        del_dia = [h for h in hores if H.dia_local(h + ":00Z").isoformat() == d]
        real = max((sum(xv.get(h2, 0) for h2 in hores[max(0, hores.index(h) - 2):hores.index(h) + 1]) for h in del_dia),
                   default=None)
        linies.append(f"{d:10} {per_dia[d][0]:10.1f} {('%.1f' % real) if real is not None else '  —':>8}")
    n_poss = sum(1 for d, (v, _) in per_dia.items() if v >= C.RIERA_PREVISIO_MM)
    linies.append(f"Dies amb {C.RIERA_PREVISIO_MM} mm o més previstos: {n_poss} de {len(per_dia)}.")
    return "\n".join(linies)


def resum():
    if not os.path.exists(REGISTRO):
        return "Encara no hi ha cap episodi apuntat."
    with open(REGISTRO, encoding="utf-8") as f:
        files_ = list(csv.DictReader(f))
    return "\n".join(f"{f['inici']} · índex {f['index_max']} mm · 3 h {f['mm_3h_max']} · 6 h {f['mm_6h_max']}"
                     f" · Fabra {f['capcalera_3h_max']} · atenció {f['avis_atencio'] or '-'}"
                     f" · perill {f['avis_perill'] or '-'} · desbordament {f['desbordament'] or '?'}"
                     for f in files_)


if __name__ == "__main__":
    ordre = sys.argv[1] if len(sys.argv) > 1 else ""
    if ordre == "ara":
        import prevision as P
        try:
            nc = P.radar()["nowcast"]
        except Exception as ex:
            print("Sense radar:", ex, file=sys.stderr)
            nc = None
        print(json.dumps(calcula(P.AHORA, nc), ensure_ascii=False, indent=1))
    elif ordre == "avisa" and len(sys.argv) > 2:
        avisa(sys.argv[2])
    elif ordre == "estat":
        print(json.dumps(llegeix_estat(), ensure_ascii=False, indent=1))
    elif ordre == "resum":
        print(resum())
    elif ordre == "previsio":
        import prevision as P
        print(json.dumps(previsio(P.AHORA), ensure_ascii=False, indent=1))
    elif ordre == "previsio-resum":
        print(resum_previsio())
    elif ordre == "respostes":
        print(respostes())
    else:
        print(__doc__)
        sys.exit(1)
