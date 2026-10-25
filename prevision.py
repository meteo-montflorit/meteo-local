#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Recogida de datos del tiempo en el barrio, para casa.py y la riera.

Junta los avisos de AEMET, los planes de Protección Civil, la lluvia y el
viento de las estaciones y el radar (con la lluvia llevada hacia delante,
nowcast.py), y decide cuándo toca el modo aviso. Los textos salen en catalán
porque son los que lee la web.

Uso:
  python3 prevision.py               resumen legible de lo que recoge
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import config as C
import hora as H
import nowcast as N
import moviment_registre as MR
import ecowitt

UA = {"User-Agent": "meteo-local/" + C.VERSION}
DIR = os.path.dirname(os.path.abspath(__file__))
TZ = "Europe/Madrid"
ZONA = ZoneInfo(TZ)
# Ara, en UTC (ADR 0128): les hores i els dies de la gent, amb H.local.
AHORA = H.ara()


def clau_hora(t):
    """La clau d'una hora (ADR 0128): en UTC, «AAAA-MM-DDTHH:MMZ», en tot el
    programa i els registres. Fins a la 3.201.0 era l'hora de Madrid sense
    zona, amb el desfasament només a l'hora que es repeteix a l'octubre: es
    llegeix igual (H.llegeix)."""
    return H.clau(t)


def hora_universal(t):
    """Una clau d'hora del programa (de qualsevol època) o un datetime, en UTC."""
    return H.utc(t)


def hora_solar(t):
    """La hora (0-23) para lo que depende del sol (ADR 0090): la del tiempo
    universal, que no cambia con el reloj. En Montflorit el sol pasa por el
    punto más alto hacia las 12 de esta hora todo el año; con la hora oficial,
    a las 13 en invierno y a las 14 en verano. Lo que depende de las personas
    (las horas de salir, los textos) va en hora local."""
    return hora_universal(t).hour


def ordre_hora(clau):
    """Per ordenar claus pel moment real, també les d'abans de la migració."""
    return H.utc(clau).timestamp()


def horas_locales(resposta):
    """Passa a claus en UTC (clau_hora) les hores d'una resposta d'Open-Meteo,
    al mateix lloc. Open-Meteo posa a tota la sèrie el desfasament del moment
    de la consulta (utc_offset_seconds), no el de cada hora: el 13-10-2026, el
    25-10 a les 22 h d'hivern sortia com «T23:00» (GMT+2). Les dates soles
    (daily) es queden com són."""
    desfase = dt.timezone(dt.timedelta(seconds=resposta.get("utc_offset_seconds") or 0))
    local = lambda t: clau_hora(dt.datetime.fromisoformat(t).replace(tzinfo=desfase)) if t and len(t) > 10 else t
    for bloc in ("hourly", "daily", "minutely_15"):
        b = resposta.get(bloc)
        if not b:
            continue
        for camp in ("time", "sunrise", "sunset"):
            if camp in b:
                b[camp] = [local(t) for t in b[camp]]
    return resposta


def leer_calibracion():
    """Lo que sale de la calibración con datos reales (calibracio/): la
    persistencia de la lluvia que usa casa.py."""
    try:
        with open(os.path.join(DIR, "calibracio", "calibracio.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


CALIBRACION_COMPLETA = leer_calibracion()


def get(url, binario=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = r.read()
    return datos if binario else datos.decode("utf-8", "replace")


# Open-Meteo respon a estones «503 Service Unavailable» uns segons, i la
# pasada es quedava amb la previsió anterior i l'avís a la pàgina, unes
# quantes vegades al dia (Juanjo, 17-10-2026: «se podría evitar de algun
# modo? reintentando o algo así»). Ara es torna a provar, i cada reintent
# queda al registre del contenidor per poder-ne mesurar l'efecte.
ESPERES_REINTENT = (5, 15)      # segons abans del segon i del tercer intent


def transitori(ex):
    """Un error que pot passar sol: el servidor saturat (5xx), massa
    peticions (429), la connexió que cau o triga massa."""
    if isinstance(ex, urllib.error.HTTPError):
        return ex.code >= 500 or ex.code == 429
    return isinstance(ex, (urllib.error.URLError, TimeoutError, ConnectionError))


def get_reintenta(url, esperes=ESPERES_REINTENT, dorm=time.sleep):
    """get() que torna a provar els errors transitoris, esperant `esperes`."""
    for espera in (*esperes, None):
        try:
            return get(url)
        except Exception as ex:
            if espera is None or not transitori(ex):
                raise
            print(f"Open-Meteo: {ex}; es torna a provar d'aquí a {espera} s", file=sys.stderr)
            dorm(espera)


CACHE_WEB = os.environ.get("CACHE_WEB", "/estat/cache-web")


def get_recent(url, segons=120):
    """get() que reutiliza la respuesta si tiene menos de segons: las
    distintas lecturas de una misma pasada (la lluvia, el viento, la riera)
    leen cada página una sola vez (ADR 0020). Fuera del NAS, sin /estat,
    siempre de la red."""
    import hashlib
    import time
    if not os.path.isdir(os.path.dirname(CACHE_WEB)):
        return get(url)
    os.makedirs(CACHE_WEB, exist_ok=True)
    ruta = os.path.join(CACHE_WEB, hashlib.sha1(url.encode()).hexdigest())
    try:
        if time.time() - os.path.getmtime(ruta) < segons:
            with open(ruta, encoding="utf-8") as f:
                return f.read()
    except OSError:
        pass
    datos = get(url)
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        f.write(datos)
    os.replace(ruta + ".tmp", ruta)
    return datos


# --- Estaciones -----------------------------------------------------------------

PORTAL = "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json"


def files_meteocat(codi, dia_utc=None, lector=None):
    """Filas semihorarias de un día (por defecto, hoy) en la página de
    meteo.cat: lista de (inicio de la media hora en UTC, {columna: texto}).
    La tabla va en hora UTC y el día también es el de UTC. Las columnas se
    llaman como en la cabecera: «PPTmm», «VVM (10 m)km/h», «VVX (10 m)km/h»…
    La misma página la leen la lluvia, el viento y la riera: se guarda dos
    minutos."""
    url = f"https://www.meteo.cat/observacions/xema/dades?codi={codi}"
    if dia_utc:
        url += f"&dia={dia_utc.isoformat()}T00:00Z"
    s = (lector or get_recent)(url)
    t = re.search(r"<table[^>]*tblperiode.*?</table>", s, re.S)
    cab, res = None, []
    dia_utc = dia_utc or AHORA.astimezone(H.UTC).date()
    for f in re.findall(r"<tr.*?</tr>", t.group(0), re.S) if t else []:
        celdas = [html.unescape(re.sub("<[^>]+>", "", c)).strip()
                  for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", f, re.S)]
        if celdas and celdas[0].startswith("Període"):
            cab = celdas
        elif cab and len(celdas) > 1:
            fila = dict(zip(cab, celdas))
            ini = fila[cab[0]].split("-")[0].strip()
            res.append((dt.datetime.combine(dia_utc, dt.time.fromisoformat(ini), dt.timezone.utc), fila))
    return res


def _columna(fila, prefix):
    """El valor numérico de la columna que empieza por prefix, o None si
    falta o es «(s/d)»."""
    for k, v in fila.items():
        if k.startswith(prefix):
            try:
                return float(v)
            except ValueError:
                return None
    return None


def taula_meteocat(codi, dia_utc=None, lector=None):
    """Lluvia semihoraria de un día: lista de (inicio de la media hora en
    UTC, mm), sin las medias horas sin dato."""
    res = []
    for ini, fila in files_meteocat(codi, dia_utc, lector):
        mm = _columna(fila, "PPT")
        if mm is not None:
            res.append((ini, mm))
    return res


def vent_meteocat(codi, lector=None):
    """El viento de la última media hora con dato en una estación de
    Meteocat: media y racha en km/h y hasta cuándo vale (ADR 0037)."""
    for ini, fila in reversed(files_meteocat(codi, lector=lector)):
        mitja, ratxa = _columna(fila, "VVM"), _columna(fila, "VVX")
        if mitja is not None:
            nom = C.ESTACIONES.get(codi, codi)
            return {"estacio": nom.split(" (")[0], "mitja": mitja, "ratxa": ratxa,
                    "fins": H.iso_local(ini + dt.timedelta(minutes=30))}
    return None


def observaciones_web(codi, nom):
    """Lluvia de hoy según la página de meteo.cat."""
    filas = taula_meteocat(codi)
    if not filas:
        return None
    hasta = filas[-1][0] + dt.timedelta(minutes=30)
    return {"estacion": nom, "font": "meteo.cat",
            "mm_hoy": round(sum(mm for _, mm in filas), 1),
            "mm_ultima_media_hora": filas[-1][1],
            "hasta": H.iso_local(hasta, segons=True)}


def observaciones_portal(codi, nom):
    """Lo mismo desde el portal de datos abiertos de la Generalitat. Va
    aproximadamente una hora por detrás, pero es una API estable. Cada lectura
    marca el inicio de su media hora, en UTC (comprobado con la tabla de
    meteo.cat del 04-10-2026)."""
    inicio = AHORA.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT00:00:00")
    q = urllib.parse.urlencode({
        "$where": f"codi_estacio='{codi}' AND codi_variable='35' AND data_lectura>='{inicio}'",
        "$order": "data_lectura", "$limit": 100})
    filas = json.loads(get(f"{PORTAL}?{q}"))
    if not filas:
        return None
    ultima = dt.datetime.fromisoformat(filas[-1]["data_lectura"]).replace(tzinfo=dt.timezone.utc)
    return {"estacion": nom, "font": "portal de dades obertes",
            "mm_hoy": round(sum(float(f["valor_lectura"]) for f in filas), 1),
            "mm_ultima_media_hora": float(filas[-1]["valor_lectura"]),
            "hasta": H.iso_local(ultima + dt.timedelta(minutes=30), segons=True)}


def resumen_minutal(filas, nom, font):
    """Lluvia de la última media hora a partir de filas minuto a minuto con el
    acumulado del día (PREC, se pone a cero a medianoche) y la intensidad
    (PINT, mm/h)."""
    filas = [f for f in filas if f.get("PREC") is not None]
    if not filas:
        return None
    ultima = H.llegeix(filas[-1]["dt_local"])
    desde = ultima - dt.timedelta(minutes=30)
    recientes = [f for f in filas if H.llegeix(f["dt_local"]) >= desde]
    mm = 0.0
    for antes, despues in zip(recientes, recientes[1:]):
        salto = despues["PREC"] - antes["PREC"]
        mm += despues["PREC"] if salto < 0 else salto
    return {"estacion": nom, "font": font,
            "mm_hoy": round(filas[-1]["PREC"], 1),
            "mm_ultima_media_hora": round(mm, 1),
            "intensitat": filas[-1].get("PINT"),
            "hasta": H.iso_local(ultima, segons=True)}


def observaciones():
    """La estación de casa, si marca lluvia (su cero no es fiable, ADR 0017),
    y después las de Meteocat: su web, que va más al día, o si falla el
    portal de la Generalitat."""
    res = []
    # La estación de casa, solo si marca lluvia: su cero no es fiable (ADR 0017).
    try:
        dato = ecowitt.observacio(ecowitt.resum_ara(), C.ESTACIO_CASA) if ecowitt.disponible() else None
    except Exception:
        dato = None
    if dato:
        res.append(dato)
    for codi, nom in C.ESTACIONES.items():
        dato = None
        for fuente in (observaciones_web, observaciones_portal):
            try:
                dato = fuente(codi, nom)
            except Exception:
                dato = None
            if dato:
                break
        if dato:
            res.append(dato)
    return res


# --- Radar ----------------------------------------------------------------------

def radar():
    """Lluvia apreciable más cercana a casa, si crece, y la lluvia llevada
    hacia delante hasta 2 horas (nowcast.py, ADR 0019): imagen de Meteocat
    o, si se ha quedado atrás, de RainViewer."""
    import math
    import numpy as np
    r = N.carrega(get, get_pagina=get_recent)
    im = N.imatge(r)
    if im is None:
        raise RuntimeError("; ".join(r["errors"]) or "sense imatges de radar")
    hora, ara, origen = im
    fila, col = N.pixel(C.CASA[0], C.CASA[1], r["tx"], r["ty"])
    yy, xx = np.ogrid[:N.MIDA, :N.MIDA]
    dist = np.hypot((yy - fila) * r["km_px"], (xx - col) * r["km_px"])
    cerca = dist <= 50
    lluvia = ara >= RADAR_APRECIABLE_MMH
    # La distancia que pone la página en modo aviso, con la misma lluvia que
    # la página enseña como «pluja» (nowcast.propera, PLOU_MMH): con la
    # apreciable (unos 6 dBZ, casi siempre llovizna que no llega al suelo),
    # el 20-10-2026 la página se actualizaba cada 6 minutos por ecos de 0,1
    # mm/h a 14,6 km y decía que la lluvia más cercana estaba a 36 km (Juanjo:
    # «por qué se actualiza cada 6 minutos si no hay ningun aviso?»).
    pluja = ara >= N.PLOU_MMH
    res = {"hora": H.iso_local(hora, segons=True), "imatge": origen,
           "km_lluvia": round(float(dist[pluja].min()), 1) if pluja.any() else None,
           "km2_50km_ahora": round(float((lluvia & cerca).sum() * r["km_px"] ** 2)),
           "km2_50km_antes": None, "nowcast": N.resum(r), "a_prop": {},
           "mapa": N.mapa(ara, fila, col, r["km_px"]), "propera": N.propera(ara, fila, col, r["km_px"]),
           "forta": N.forta(ara, fila, col, r["km_px"]),
           "creixement": N.creixement(r, fila, col, r["km_px"])}
    # El registro del movimiento, para comprobar en un mes si acierta (moviment_registre.py).
    for apunta, arg in ((MR.apunta, (r, res["nowcast"])), (MR.apunta_creixement, (res["creixement"],))):
        try:
            apunta(*arg)
        except Exception as ex:
            print(f"moviment_registre: {ex}", file=sys.stderr)
    # Los píxeles con lluvia a RADAR_AVISO_KM o menos en cada radar, para
    # seguir los ecos sueltos que encienden el modo aviso sin lluvia (registre.py).
    mc, rv = r.get("meteocat") or {}, r.get("rainviewer")
    for nom, t, mm in (("meteocat", mc.get("hora"), mc.get("mm_h")),
                       ("rainviewer", rv and rv["hores"][-1], rv and rv["mm_h"][-1])):
        if mm is None:
            continue
        px = []
        for f, c in zip(*np.nonzero((mm >= RADAR_APRECIABLE_MMH) & (dist <= C.RADAR_AVISO_KM))):
            dy, dx = (f - fila) * r["km_px"], (c - col) * r["km_px"]
            px.append([round(float(dist[f, c]), 1), round((math.degrees(math.atan2(dx, -dy)) + 360) % 360),
                       round(float(mm[f, c]), 2)])
        res["a_prop"][nom] = {"hora": H.iso_local(t), "px": sorted(px)[:PX_A_PROP]}
    # Si crece: la misma comparación de siempre, con RainViewer (una hora antes).
    rv = r.get("rainviewer")
    if rv and len(rv["mm_h"]) >= 7:
        res["km2_50km_antes"] = round(float(((rv["mm_h"][0] >= RADAR_APRECIABLE_MMH) & cerca).sum() * r["km_px"] ** 2))
        res["km2_50km_ahora"] = round(float(((rv["mm_h"][-1] >= RADAR_APRECIABLE_MMH) & cerca).sum() * r["km_px"] ** 2))
    return res


# Lluvia apreciable en el radar: unos 6 dBZ, el umbral que se usaba con la
# opacidad de RainViewer (por debajo, llovizna o ruido).
RADAR_APRECIABLE_MMH = N.FEBLE_MMH
PX_A_PROP = 40       # píxeles cercanos que se apuntan, como mucho (los más cercanos)


# --- Avisos y planes ------------------------------------------------------------

def descripcion_aviso(url):
    """El texto de un aviso de AEMET, tal como lo publica (en castellano; la
    versión inglesa de la ficha repite el mismo texto). Cada ficha tiene su
    dirección: si el aviso cambia, cambia la dirección, así que se puede
    guardar horas. None si no hay texto."""
    s = get_recent(url, segons=6 * 3600)
    textos = {}
    for info in re.findall(r"<info>.*?</info>", s, re.S):
        idioma = re.search(r"<language>(.*?)<", info)
        texto = re.search(r"<description>(.*?)</description>", info, re.S)
        if texto and texto.group(1).strip():
            textos[idioma.group(1) if idioma else ""] = html.unescape(" ".join(texto.group(1).split()))
    return textos.get("es-ES") or next(iter(textos.values()), None)


# Els tipus d'avís de Meteoalarm («Moderate wind warning»): el primer que
# encaixa. Un de desconegut surt igualment, com «altres».
TIPUS_METEOALARM = (("thunderstorm", "tempestes"), ("flood", "inundacions"), ("rain", "pluja"), ("wind", "vent"),
                    ("high-temperature", "calor"), ("low-temperature", "fred"), ("snow", "neu"), ("fog", "boira"),
                    ("forest-fire", "incendis"), ("coastal", "costaners"), ("avalanche", "allaus"), ("dust", "pols"))


def tipus_aemet(evento):
    e = evento.lower()
    return next((t for clau, t in TIPUS_METEOALARM if clau in e), "altres")


def avisos():
    """Avisos de AEMET, del feed de Meteoalarm: todos los tipos desde la 3.88.0."""
    s = get("https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-spain")
    res = []
    for ent in re.findall(r"<entry>.*?</entry>", s, re.S):
        def campo(c, ent=ent):
            m = re.search(rf"<cap:{c}>(.*?)<", ent)
            return m.group(1) if m else ""
        zona, evento = campo("areaDesc"), campo("event")
        if zona not in (C.ZONA_AVISOS, C.ZONA_CERCANA):
            continue
        # Tots els tipus, no només pluja i tempestes (fins a la 3.87.0; ADR 0093).
        tipo = tipus_aemet(evento)
        nivel = {"Moderate": "groc", "Severe": "taronja", "Extreme": "vermell"}.get(
            evento.split()[0], evento)
        aviso = {"zona": zona, "tipo": tipo, "nivel": nivel,
                 "inicio": H.iso_local(campo("onset"), segons=True),
                 "fin": H.iso_local(campo("expires"), segons=True)}
        # El texto del aviso («Pueden ir acompañadas de granizo…») está en su
        # ficha, no en el resumen (ADR 0033).
        ficha = re.search(r'href="(https://feeds\.meteoalarm\.org/api/v1/warnings/[^"]+)"', ent)
        if ficha and zona == C.ZONA_AVISOS and H.llegeix(aviso["fin"]) > AHORA:
            try:
                aviso["descripcio"] = descripcion_aviso(ficha.group(1))
            except Exception:
                pass
        res.append(aviso)
    # El feed repite entradas idénticas.
    unicos = {tuple(sorted(a.items())) for a in res}
    return sorted((dict(t) for t in unicos), key=lambda a: (H.utc(a["inicio"]), a["zona"], a["tipo"]))


PLANES_PC_URL = "https://analisi.transparenciacatalunya.cat/resource/wj9c-j6vf.json"


def afecta_la_zona(descripcion):
    """Un plan afecta salvo que su descripción nombre solo otras zonas."""
    d = descripcion or ""
    if any(z in d for z in C.ZONAS_PROPIAS_PC):
        return True
    return not any(z in d for z in C.ZONAS_AJENAS_PC)


ORDRE_FASES = {"prealerta": 0, "alerta": 1, "emergència": 2}


def nom_pla(p):
    """El nombre que ve el lector de un plan que interesa, o None. Del PROCICAT
    solo interesan algunos riesgos, y el de cada registro lo dice su icono."""
    acronimo = p.get("plaacronim", "")
    if acronimo in C.PLANES_PC:
        return C.PLANES_PC[acronimo]
    if acronimo == "PROCICAT":
        icona = urllib.parse.unquote((p.get("plaicona") or {}).get("url") or "")
        m = re.search(r"ico_PROCICAT_([^/]+)\.png$", icona, re.I)
        return C.PROCICAT_PC.get(m.group(1).upper()) if m else None
    return None


def planes_proteccion_civil():
    """Planes de Protección Civil que dependen del tiempo, activados o en
    prealerta (datos abiertos de la Generalitat, actualizados en tiempo real),
    uno por plan y riesgo, con la fase más alta. La prealerta no activa el plan
    pero se muestra (ADR 0051)."""
    res = {}
    for p in json.loads(get(PLANES_PC_URL)):
        nom = nom_pla(p)
        fase = (p.get("plafase") or "").lower()
        if (nom is None or fase not in ORDRE_FASES or (p.get("plaactivat") != "SI" and fase != "prealerta")
                or not afecta_la_zona(p.get("descripcio"))):
            continue
        clau = (p["plaacronim"], nom)
        if clau in res and ORDRE_FASES[res[clau]["fase"]] >= ORDRE_FASES[fase]:
            continue
        res[clau] = {"pla": p["plaacronim"], "nom": nom, "fase": fase,
                     "des_de": p.get("fasedatahora"),
                     "descripcio": (p.get("descripcio") or "").strip(" -"),
                     "comunicat": (p.get("comunicatpdf") or {}).get("url")}
    return list(res.values())


# Un plan abierto sin motivo meteorológico a la vista no se muestra (Juanjo,
# 10-10-2026: «el plan no está abierto por motivos meteorológicos sino de
# recuperación… confunde mucho»; ADR 0062). Se muestra si está en
# emergencia, si su último comunicado tiene menos de PLA_COMUNICAT_H horas o
# si hay aviso de AEMET o de Meteocat de su fenómeno en la zona (desde la 3.88.0;
# antes, solo AEMET por lluvia o tormentas), vigente o para las próximas
# PLA_AVIS_H horas. Si no se han podido leer los avisos, se muestra.
PLA_COMUNICAT_H = 24
PLA_AVIS_H = 24


def data_fase(text):
    """«08/10/2026 17:14» (hora local) de los datos de Protección Civil."""
    try:
        return dt.datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=ZONA)
    except (TypeError, ValueError):
        return None


# El fenómeno de cada plan, por su nombre (ADR 0093): un plan de viento se
# mantiene con un aviso de viento, no con uno de lluvia. Un plan sin fenómeno
# meteorológico (contaminación) se muestra siempre.
MOTIU_PLA = (("inundacions", {"pluja", "tempestes", "inundacions"}), ("vent", {"vent"}), ("neu", {"neu", "fred"}),
             ("calor", {"calor"}), ("fred", {"fred", "neu"}))


CODI_PLA = {"INUNCAT": "inundacions", "VENTCAT": "vent", "NEUCAT": "neu"}


def motiu_pla(p):
    nom = f"{(p.get('nom') or '').lower()} {CODI_PLA.get(p.get('pla'), '')}"
    return next((m for clau, m in MOTIU_PLA if clau in nom), None)


def pla_per_temps(p, avisos_, ahora=None, smp=None):
    """Si el plan tiene motivo meteorológico a la vista: un aviso de AEMET o de
    Meteocat (smp, ADR 0093) de su fenómeno en la zona, vigente o para las
    próximas PLA_AVIS_H horas."""
    import smp as SMP
    ahora = ahora or AHORA
    if p.get("fase") == "emergència":
        return True
    t = data_fase(p.get("des_de"))
    if t is None or ahora - t < dt.timedelta(hours=PLA_COMUNICAT_H):
        return True
    motiu = motiu_pla(p)
    if motiu is None or (avisos_ is None and smp is None):
        return True
    limit = ahora + dt.timedelta(hours=PLA_AVIS_H)
    if any(a.get("zona", C.ZONA_AVISOS) == C.ZONA_AVISOS and a.get("tipo") in motiu
           and dt.datetime.fromisoformat(a["inicio"]) <= limit and dt.datetime.fromisoformat(a["fin"]) > ahora
           for a in avisos_ or []):
        return True
    hores = set()
    h = H.utc(ahora).replace(minute=0, second=0, microsecond=0)
    while h < limit:
        hores.add(SMP.clau_hora(h))
        h += dt.timedelta(hours=1)
    return any(SMP.fenomen(m["meteor"]) in motiu and hores & SMP.hores_avis(m)
               for m in (smp or {}).get("avisos") or [])


# --- Horario y modo aviso -------------------------------------------------------

def motivos_modo_aviso(avisos_, planes, obs, radar_, smp=None):
    """Por qué conviene actualizar cada 6 minutos (lista vacía si no): aviso
    de Meteocat o de AEMET vigente, plan de Protección Civil en alerta o
    emergencia, lluvia en las estaciones o lluvia en el radar a menos de
    RADAR_AVISO_KM de casa (o que llegará a casa en la próxima hora). El de
    Meteocat cuenta aunque AEMET no tenga ninguno (Juanjo, 16-10-2026)."""
    import smp as SMP
    res = []
    if any(SMP.clau_hora(AHORA) in SMP.hores_avis(m)
           for m in (smp or {}).get("avisos") or []):
        res.append("avís del Meteocat")
    if any(a["zona"] == C.ZONA_AVISOS
           and dt.datetime.fromisoformat(a["inicio"]) <= AHORA < dt.datetime.fromisoformat(a["fin"])
           for a in avisos_ or []):
        res.append("avís de l'AEMET")
    if any(p["fase"] in ("alerta", "emergència") for p in planes or []):
        res.append("pla de Protecció Civil")
    if any((o.get("mm_ultima_media_hora") or 0) > 0 or (o.get("intensitat") or 0) > 0 for o in obs or []):
        res.append("pluja a les estacions")
    nc = (radar_ or {}).get("nowcast")
    propera = nc and N.en_tram(nc, "casa", AHORA, AHORA + dt.timedelta(hours=1))
    if (radar_ and radar_.get("km_lluvia") is not None and radar_["km_lluvia"] <= C.RADAR_AVISO_KM
            or propera and propera["prob"] >= C.PROB_ATENCION):
        res.append("pluja al radar")
    return res


def horario(trams, cada_min, motivos_aviso, km_pluja=None):
    """El horario que muestra la página y que sigue el reloj del NAS. Con los
    dos ritmos y la distancia del radar, para que la web explique los dos
    modos en cualquiera de ellos (ADR 0010), y, en modo aviso, a qué
    distancia está la lluvia del radar (km_pluja), para decir el motivo de
    ahora («Ara cada 6 minuts: …»)."""
    explica = {"normal_min": cada_min, "avis_min": C.MODO_AVISO_INTERVALO_MIN, "radar_km": C.RADAR_AVISO_KM}
    if motivos_aviso and km_pluja is not None:
        explica["km_pluja"] = km_pluja
    if motivos_aviso:
        return {"trams": trams, "cada_min": C.MODO_AVISO_INTERVALO_MIN,
                "desfase_min": C.MODO_AVISO_DESFASE_MIN, "mode_avis": motivos_aviso, **explica}
    return {"trams": trams, "cada_min": cada_min, "desfase_min": 0, "mode_avis": [], **explica}


if __name__ == "__main__":
    d, errores = {}, []
    for clave, funcion in (("avisos", avisos), ("plans", planes_proteccion_civil),
                           ("estacions", observaciones), ("radar", radar)):
        try:
            d[clave] = funcion()
        except Exception as ex:
            errores.append(f"{clave}: {ex}")
    print(f"Recollit {H.iso_local(AHORA)}")
    for error in errores:
        print("  fallo:", error)
    for a in d.get("avisos") or []:
        print(f"Avís {a['nivel']} per {a['tipo']} a {a['zona']}: {a['inicio'][11:16]}-{a['fin'][11:16]}")
    for p in d.get("plans") or []:
        print(f"Pla {p['pla']} en fase d'{p['fase']}")
    for o in d.get("estacions") or []:
        print(f"{o['estacion']}: {o['mm_ultima_media_hora']} mm en mitja hora, {o['mm_hoy']} mm avui ({o['font']})")
    r = d.get("radar")
    if r:
        nc = r["nowcast"] or {}
        print(f"Radar ({r['imatge']}, {r['hora'][11:16]}): pluja a {r['km_lluvia']} km de casa; "
              f"moviment cap {nc.get('cap_a')} a {nc.get('velocitat_kmh')} km/h")
    import smp as SMP
    try:
        smp = SMP.llegeix(get, AHORA)
    except Exception as ex:
        smp = None
        print("  fallo: smp:", ex)
    motius = motivos_modo_aviso(d.get("avisos"), d.get("plans"), d.get("estacions"), r, smp)
    print("Mode avís:", ", ".join(motius) if motius else "no")
    sys.exit(1 if errores and not d else 0)
