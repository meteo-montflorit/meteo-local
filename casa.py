#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El tiempo en casa (Montflorit): lo que mide ahora la estación de casa y
la previsión hora a hora para las próximas 24 horas.

Los modelos pueden no ver un episodio (el 05-10-2026 daban 0,3 mm por hora
mientras caían más de 20 mm/h y había alerta de Protección Civil). Por eso:
- las primeras horas parten de la lluvia que mide la estación, con la
  persistencia real de la lluvia en Sabadell y Sant Cugat (calibracio.json);
- si los modelos se han quedado muy cortos en las últimas horas, se dice;
- cada hora lleva los avisos de AEMET y los planes de Protección Civil que la
  cubren.

La estación de casa (ecowitt.py, ADR 0017) da la temperatura de ahora y, con
lo que se equivoca el modelo en este momento, corrige la de las horas
siguientes. Su lluvia solo cuenta cuando marca lluvia.

Si Open-Meteo falla, se reutiliza la última previsión buena (--anterior), con
las horas que aún no han pasado y los avisos y la lluvia de ahora (ADR 0016).

Uso: python3 casa.py --json web/casa.json [--anterior casa.json|URL]
"""
import datetime as dt
import json
import statistics
import sys
import urllib.parse

import aire as AI
import aprenentatge as A
import config as C
import ecowitt as E
import entorn as EN
import estacions as ES
import fi_pluja as FP
import nowcast as N
import nuvols as NV
import part_alta as PA
import pollen as PO
import prevision as P
import radar_fonts as RF
import registre as R
import riera as RI
import riscos as RS
import smp as SMP
import vent_veines as VV
import llum as LL
import setmana as SM
import sol_estacio as SE
import transit as TT
import trens as TR
import busos as BU
import wunderground as WU

HORAS = 24
# La tabla llega como mínimo a 24 horas y hasta las 21 h de mañana, para que
# mañana salga entero (la mañana y la tarde), y acaba siempre con un tramo del
# día (matí 7–14, tarda 14–21, nit 21–7: web/casa.js, ADR 0041). «Mañana» es
# el día siguiente del calendario, también de madrugada: antes, de 0 a 7 h,
# era el del tramo en curso (la noche aún era de ayer) y «Demà» llegaba solo
# a las 7 h (Juanjo, 12-10-2026; ADR 0074). Entre 24 y 45 filas (a las 0 h,
# hasta las 21 h de mañana). AROME llega a unas 40-45 horas; más allá, la
# lluvia es la de los otros modelos y la probabilidad, la del ensemble. Los
# riesgos y el registro siguen con las 24 primeras.
FI_TRAMS = (7, 14, 21)
FI_DEMA = 21
HORAS_PERSISTENCIA = 4      # las que tiene la tabla de calibracio.json
# Una lectura de «ahora» con más de estos minutos no vale: un feed congelado
# no puede decir que llueve (o que no) durante horas.
ARA_MAX_MIN = 30
HORAS_COMPROBACION = 3      # últimas horas en que se comparan modelos y estación
# Entre la estación y AROME hay 1,3 hPa de media y como mucho 3,2 en 17 días:
# más de 5 es una lectura mala, y la presión se queda la del modelo.
DESVIACIO_PRESSIO_MAX = 5


def modelos(desde, errors=None):
    """Los modelos deterministas y, aparte, el ensemble: si solo falla el
    ensemble, la previsión sigue (la probabilidad sale del modelo aprendido
    sin él) y queda apuntado en errors."""
    dias = [desde.date().isoformat(), (desde + dt.timedelta(days=2)).date().isoformat()]
    q = urllib.parse.urlencode({
        "latitude": C.CASA[0], "longitude": C.CASA[1],
        "hourly": "temperature_2m,precipitation,weather_code,cloud_cover,cloud_cover_low,"
                  "wind_speed_10m,wind_gusts_10m,relative_humidity_2m,shortwave_radiation,snowfall,pressure_msl",
        "models": "meteofrance_seamless," + ",".join(C.MODELOS_FINOS),
        "timezone": P.TZ, "start_date": dias[0], "end_date": dias[1]})
    h = P.horas_locales(json.loads(P.get_reintenta(f"https://api.open-meteo.com/v1/forecast?{q}")))["hourly"]
    q = urllib.parse.urlencode({
        "latitude": C.CASA[0], "longitude": C.CASA[1], "hourly": "precipitation",
        "models": C.ENSEMBLE, "timezone": P.TZ, "start_date": dias[0], "end_date": dias[1]})
    try:
        e = P.horas_locales(json.loads(P.get_reintenta(f"https://ensemble-api.open-meteo.com/v1/ensemble?{q}")))["hourly"]
    except Exception as ex:
        if errors is None:
            raise
        errors.append(f"ensemble: {ex}")
        e = {}
    # ECMWF, para la probabilidad de lluvia (ADR 0086), aparte: si falla, la
    # probabilidad sale del modelo sin él y la página no lo dice.
    q = urllib.parse.urlencode({
        "latitude": C.CASA[0], "longitude": C.CASA[1], "hourly": "precipitation",
        "models": C.MODEL_ECMWF, "timezone": P.TZ, "start_date": dias[0], "end_date": dias[1]})
    try:
        ec = P.horas_locales(json.loads(P.get_reintenta(f"https://api.open-meteo.com/v1/forecast?{q}")))["hourly"]
        serie = ec.get("precipitation") or ec.get(f"precipitation_{C.MODEL_ECMWF}")
        if serie and ec.get("time") == h.get("time"):
            h[f"precipitation_{C.MODEL_ECMWF}"] = serie
    except Exception as ex:
        print("No he pogut llegir ECMWF:", ex, file=sys.stderr)
    # Las nubes de ECMWF y GFS, para mezclarlas con las de AROME e ICON-EU
    # (nuvols.py, ADR 0088). Una petición por modelo: si falla uno, el cielo
    # sale de los demás.
    for m in NV.MODELS_APART:
        q = urllib.parse.urlencode({
            "latitude": C.CASA[0], "longitude": C.CASA[1], "hourly": "cloud_cover,cloud_cover_low",
            "models": m, "timezone": P.TZ, "start_date": dias[0], "end_date": dias[1]})
        try:
            nv = P.horas_locales(json.loads(P.get_reintenta(f"https://api.open-meteo.com/v1/forecast?{q}")))["hourly"]
            if nv.get("time") == h.get("time"):
                for camp in ("cloud_cover", "cloud_cover_low"):
                    serie = nv.get(camp) or nv.get(f"{camp}_{m}")
                    if serie:
                        h[f"{camp}_{m}"] = serie
        except Exception as ex:
            print(f"No he pogut llegir els núvols de {m}:", ex, file=sys.stderr)
    # El vent cada 15 minuts, per a la mitjana de cada hora (vent_hora): el
    # vent horari és el d'un instant, el de l'hora en punt, i en una hora de
    # tempesta sortia «3 (37)» (revisor, 19-10-2026). Si falla, el de l'hora.
    q = urllib.parse.urlencode({
        "latitude": C.CASA[0], "longitude": C.CASA[1], "minutely_15": "wind_speed_10m",
        "models": "meteofrance_seamless", "timezone": P.TZ, "start_date": dias[0], "end_date": dias[1]})
    try:
        m15 = json.loads(P.get_reintenta(f"https://api.open-meteo.com/v1/forecast?{q}"))["minutely_15"]
        h["vent_15min"] = {t: v for t, v in zip(m15["time"], m15["wind_speed_10m"]) if v is not None}
    except Exception as ex:
        print("No he pogut llegir el vent cada 15 minuts:", ex, file=sys.stderr)
    return h, e


def humitat_hora(model, d, d_abans, temp):
    """La humedad relativa del tramo (%), para la gráfica (Juanjo, 21-10-2026:
    «haz el UV y la humedad»): el punto de rocío corregido (A.rosada, ADR
    0114; la media del principio y el final del tramo, como la temperatura)
    con la temperatura de la página, que también lo está. Con la humedad de
    AROME tal cual no cuadraría con esa temperatura, y AROME ve el aire más
    seco de lo que está (1,3 °C de rocío de media en un año). Sin datos, None."""
    if temp is None:
        return None
    rosades = [r for r in (A.rosada(model, x) for x in (d_abans, d) if x) if r is not None]
    if not rosades:
        return None
    # El rocío no pasa de la temperatura.
    return round(SE.humitat(min(sum(rosades) / len(rosades), temp), temp))


def desviacio_pressio(h, casa):
    """Lo que la estación de casa marca de más sobre la presión del modelo
    ahora (hPa), para llevar a ella toda la curva de la gráfica (Juanjo,
    21-10-2026: «Es facil añadir la presión?»). AROME da 1,3 hPa menos de
    media, casi siempre igual (17 días): con la diferencia del momento, el
    error baja de 1,2 a 0,5 hPa, también a 24 horas. Sin lectura de casa (las
    vecinas no tienen la presión calibrada), 0. Una diferencia de más de
    DESVIACIO_PRESSIO_MAX es una lectura mala: 0."""
    if not casa or casa.get("pressio") is None or not casa.get("hora"):
        return 0.0
    model = temperatura_model_ara(h, dt.datetime.fromisoformat(casa["hora"]), "pressure_msl")
    if model is None or abs(casa["pressio"] - model) > DESVIACIO_PRESSIO_MAX:
        return 0.0
    return casa["pressio"] - model


def pressio_hora(h, i, desviacio):
    """La presión del tramo que acaba a la hora i (hPa, al nivel del mar), la
    media del principio y el final como la temperatura, llevada a la estación
    de casa (desviacio_pressio). Sin datos, None."""
    serie = h.get("pressure_msl_meteofrance_seamless") or []
    v = [serie[j] for j in (i - 1, i) if 0 <= j < len(serie) and serie[j] is not None]
    return round(sum(v) / len(v) + desviacio, 1) if v else None


def vent_hora(h, i):
    """El vent mitjà del tram que acaba a l'hora i (km/h): la mitjana dels
    valors cada 15 minuts de la hora, pels trapezis (els dos extrems hi compten
    la meitat); sense, la mitjana del principi i el final, com la
    temperatura; i sense el principi, el de l'hora. Juanjo, 19-10-2026: «sí,
    hazlo» (la llegenda en diu «mitjana» i era un instant)."""
    hores = h.get("wind_speed_10m_meteofrance_seamless") or []
    fi = h["time"][i]
    m15 = h.get("vent_15min") or {}
    if m15:
        t = dt.datetime.fromisoformat(fi)
        punts = [m15.get((t - dt.timedelta(minutes=15 * k)).strftime("%Y-%m-%dT%H:%M")) for k in range(4, -1, -1)]
        if all(v is not None for v in punts):
            return round((punts[0] / 2 + sum(punts[1:4]) + punts[4] / 2) / 4, 1)
    ara = hores[i] if i < len(hores) else None
    abans = hores[i - 1] if 0 < i <= len(hores) else None
    if ara is not None and abans is not None:
        return round((ara + abans) / 2, 1)
    return ara


def indice_uv(desde):
    """Índice UV por hora ({"AAAA-MM-DDTHH:MM": valor}) para la página «Si
    surts» (ADR 0029). Solo lo da el modelo por defecto de Open-Meteo: va en
    una consulta aparte, y si falla la página sigue sin él."""
    dias = [desde.date().isoformat(), (desde + dt.timedelta(days=2)).date().isoformat()]
    q = urllib.parse.urlencode({"latitude": C.CASA[0], "longitude": C.CASA[1], "hourly": "uv_index",
                                "timezone": P.TZ, "start_date": dias[0], "end_date": dias[1]})
    h = P.horas_locales(json.loads(P.get(f"https://api.open-meteo.com/v1/forecast?{q}")))["hourly"]
    return {t: v for t, v in zip(h["time"], h["uv_index"]) if v is not None}


def sol(desde):
    """Salida y puesta del sol e índice UV máximo de hoy y mañana, para
    «Consultes» y /sol (ADR 0054). Del modelo por defecto de Open-Meteo."""
    q = urllib.parse.urlencode({"latitude": C.CASA[0], "longitude": C.CASA[1], "timezone": P.TZ,
                                "daily": "sunrise,sunset,uv_index_max", "start_date": desde.date().isoformat(),
                                "end_date": (desde + dt.timedelta(days=1)).date().isoformat()})
    d = P.horas_locales(json.loads(P.get(f"https://api.open-meteo.com/v1/forecast?{q}")))["daily"]
    return [{"dia": t, "sortida": s, "posta": p, "uv_max": uv}
            for t, s, p, uv in zip(d["time"], d["sunrise"], d["sunset"], d["uv_index_max"])]


def estacio_casa():
    """Lo que mide ahora la estación de casa (None sin claves o si falla)."""
    if not E.disponible():
        return None
    casa = E.resum_ara()
    hora = dt.datetime.fromisoformat(casa["hora"])
    if P.AHORA - hora > dt.timedelta(minutes=ARA_MAX_MIN):
        raise RuntimeError(f"l'última lectura és de les {hora:%H:%M}")
    return casa


def llueve_ahora_en(casa, veines=None):
    """Llueve ahora: el pluviómetro de casa ha recogido lluvia en los últimos
    PLOU_ARA_MIN minutos (config.py), o lo ha hecho alguna de las estaciones
    vecinas de Weather Underground que cuentan (config.VEINES, ADR 0060).
    Solo cuenta el sí (ADR 0017)."""
    return bool(casa and casa.get("plou")) or WU.plou_a_les_veines(veines)


def plugim_radar(a_prop):
    """Els ecos febles de cada radar a sobre del barri (per sota de
    nowcast.PLOU_MMH, a C.PLUGIM_KM o menys de casa) i si diuen plugim: tots
    dos radars amb C.PLUGIM_PX píxels o més. None sense els dos radars."""
    px = {nom: sum(1 for km, _, mm in (r or {}).get("px") or [] if km <= C.PLUGIM_KM and mm < N.PLOU_MMH)
          for nom, r in (a_prop or {}).items()}
    if not {"meteocat", "rainviewer"} <= px.keys():
        return None
    return {**px, "si": all(px[n] >= C.PLUGIM_PX for n in ("meteocat", "rainviewer"))}


def estat_pluja(radar, plou, ahora):
    """El estado único de la lluvia de ahora (ADR 0101), del que sale todo lo
    que la web y el bot dicen de ella. Cada bloque lo decidía con sus datos y
    se contradecían: «No plou», «Pluja a sobre» y una hora «sense pluja» a la
    vez (Juanjo, 18-10-2026). Manda lo medido, luego el radar, luego el modelo:
    - plou: alguna estación del barrio que cuenta ha medido lluvia en los
      últimos PLOU_ARA_MIN minutos;
    - radar_sobre: el radar la pone encima (llegada en 5 minutos o menos, o ya
      pasada: la imagen llega con retraso), pero ninguna estación la mide;
    - arriba / possible: el radar la ve venir (50 % / 20 %);
    - no: nada de lo anterior; con «plugim» si los dos radares ven ecos
      débiles extendidos sobre el barrio (plugim_radar), que el pluviómetro
      no recoge. No cambia la previsión ni los avisos: se dice y se pregunta
      a Juanjo para comprobarlo (plugim.py)."""
    r = radar or {}
    t = lambda k: dt.datetime.fromisoformat(r[k]) if r.get(k) else None  # noqa: E731
    arriba, possible = t("arriba"), t("possible")
    if plou:
        estat, font = "plou", "estacions"
    elif arriba and arriba <= ahora + dt.timedelta(minutes=5):
        estat, font = "radar_sobre", "radar"
    elif arriba:
        estat, font = "arriba", "radar"
    elif possible:
        estat, font = "possible", "radar"
    else:
        estat, font = "no", None
    res = {"estat": estat, "font": font, **{k: r.get(k) for k in ("arriba", "possible", "fi", "sense_fi")}}
    if estat == "no" and (r.get("plugim") or {}).get("si"):
        res.update(plugim=True, font="radar")
    return res


def ajusta_hores(hores, pluja, ahora):
    """Las horas de la tabla, de acuerdo con el estado de la lluvia: si el radar
    la pone encima, la hora en curso no puede decir «sense pluja»; si la ve
    llegar dentro de una hora, esa hora tampoco. Solo sube la probabilidad,
    como el radar en previsio(); hace falta también con la previsión anterior
    (previsio_anterior), que no lleva el radar."""
    if not hores or not pluja:
        return hores
    local = lambda iso: dt.datetime.fromisoformat(iso).astimezone().replace(tzinfo=None)  # noqa: E731
    marques = []
    if pluja["estat"] == "radar_sobre":
        marques.append((ahora.astimezone().replace(tzinfo=None), 0.5))
    elif pluja["estat"] in ("arriba", "possible") and pluja.get(pluja["estat"]):
        marques.append((local(pluja[pluja["estat"]]), 0.5 if pluja["estat"] == "arriba" else C.PROB_ATENCION))
    for t, p in marques:
        for f in hores[:3]:
            if dt.datetime.fromisoformat(f["hora"]) <= t < dt.datetime.fromisoformat(f["fins"]) \
                    and (f.get("probabilitat") or 0) < p:
                f["probabilitat"] = p
                f["segons_radar"] = not f.get("plou_ara") and not f.get("segons_estacio")
    return hores


def _mediana(valors):
    valors = [x for x in valors if x is not None]
    return round(statistics.median(valors), 1) if valors else None


def consens_pluja(casa, veines=None):
    """La lluvia de Montflorit por consenso de la red del barrio (Juanjo,
    13-10-2026: «que mi estación no sea la principal sino que los datos se
    hagan por consenso»): la mediana de la estación de casa y de las vecinas
    que cuentan para «plou ara», con las que se hayan podido leer, de la
    última hora y de hoy. Sin vecinas, la de casa."""
    estacions = ([casa] if casa else []) + [v for v in veines or [] if v.get("compta")]
    # También la de 15 minutos: si no, quedaba la de casa sola y podía ser
    # mayor que la de la última hora (revisor, 18-10-2026: 0,3 mm en 15
    # minutos y 0 en la hora). Con las mismas estaciones y cada una con sus
    # cifras de las mismas lecturas (wunderground.veina_ara), las medianas no
    # se cruzan: la de hoy no baja de la de la última hora si la hora es de hoy.
    return {c: _mediana([e.get(c) for e in estacions])
            for c in ("pluja_15min", "pluja_30min", "pluja_1h", "pluja_3h", "pluja_avui")}


def consens(ara_casa, casa, veines=None):
    """«Ara» con la lluvia y la humedad de la red del barrio, sin decir de qué
    estación sale cada dato (Juanjo: «debe hacerlo silenciosamente»). La temperatura
    sigue siendo la de casa (la zona fría del barrio, ADR 0081) y la presión
    también: la de las vecinas no está calibrada. La humedad sale del punto de
    rocío (el agua que hay en el aire, que es la misma en todo el barrio),
    mediana de casa y de todas las vecinas, con la temperatura de casa. Lo que
    marcaba la estación queda en «…_estacio»."""
    if not ara_casa:
        return ara_casa
    res = dict(ara_casa)
    pluja = consens_pluja(casa, veines)
    for camp in ("pluja_15min", "pluja_30min", "pluja_1h", "pluja_3h", "pluja_avui"):
        if pluja[camp] is not None and any(v.get("compta") for v in veines or []):
            res.setdefault(f"{camp}_estacio", ara_casa.get(camp))
            res[camp] = pluja[camp]
    # Llueve si llueve en casa o en una vecina que cuenta (llueve_ahora_en),
    # con la intensidad mediana de las que la marcan.
    mullades = [e for e in ([casa] if casa else []) + [v for v in veines or [] if v.get("compta")]
                if e.get("plou")]
    if mullades:
        res.setdefault("plou_estacio", ara_casa.get("plou"))
        res.setdefault("intensitat_estacio", ara_casa.get("intensitat"))
        res["plou"] = True
        res["intensitat"] = _mediana([e.get("intensitat") for e in mullades])
    rosada = _mediana([(casa or {}).get("rosada")] + [v.get("rosada") for v in veines or []])
    if rosada is not None and res.get("temperatura") is not None and veines:
        # El rocío no pasa de la temperatura: las vecinas lo dan en grados
        # enteros y casa está en la zona fría (revisor, 19-10-2026).
        rosada = min(rosada, res["temperatura"])
        res.setdefault("humitat_estacio", ara_casa.get("humitat"))
        res["rosada"] = rosada
        res["humitat"] = round(SE.humitat(rosada, res["temperatura"]))
    return res


def ara_sense_casa(veines, taula, ahora):
    """Si falla la estación de casa (ADR 0087): «Ara» con las vecinas leídas
    en la última media hora. La temperatura, la de ICERDA6, la otra estación
    junto a la riera, para que siga siendo la de la riera; sin ella, la de la
    parte alta menos su diferencia habitual a esa hora (part_alta). La lluvia
    y la humedad, por consenso de las vecinas (consens). Sin presión: la de
    las vecinas no está calibrada. Sin vecinas, None, como hasta ahora."""
    fresques = [v for v in veines or [] if v.get("hora")
                and ahora - dt.datetime.fromisoformat(v["hora"]) <= dt.timedelta(minutes=PA.FRESCA_MIN)]
    baixa = [v["temperatura"] for v in fresques
             if not C.VEINES.get(v["estacio"], {}).get("alta") and v.get("temperatura") is not None]
    if baixa:
        temperatura = _mediana(baixa)
    else:
        alta = PA.mediana_alta([v.get("temperatura") for v in fresques if v["estacio"] in PA.ALTES])
        dif = taula.get(PA.hora_solar(ahora))
        if alta is None or dif is None:
            return None
        temperatura = round(alta - dif, 1)
    res = {"hora": max(v["hora"] for v in fresques), "temperatura": temperatura, "pressio": None,
           "humitat": _mediana([v.get("humitat") for v in fresques]), "pluja_avui": 0.0, "pluja_1h": 0.0,
           "plou": False, "intensitat": 0.0, "font": "veines"}
    return consens(res, None, fresques)


def temperatura_model_ara(h, ahora, camp="temperature_2m"):
    """Temperatura del modelo en este momento, entre las dos horas en punto
    (o, con camp, otra variable, como la humedad)."""
    serie = h.get(f"{camp}_meteofrance_seamless") or []
    ini = ahora.replace(minute=0, second=0, microsecond=0)
    try:
        i = h["time"].index(P.clau_hora(ini))
        a, b = serie[i], serie[i + 1]
    except (ValueError, IndexError):
        return None
    if a is None or b is None:
        return None
    return a + (b - a) * (ahora - ini).total_seconds() / 3600


def pluja_veines_ara(veines):
    """{id: mm de la última hora} de las vecinas leídas en esta pasada."""
    return {v["estacio"]: v.get("pluja_1h") for v in veines or []}


def al_prever(desde, h, casa, riera=None, veines=None):
    """Lo que medían las estaciones al prever y usa el aprendizaje: la lluvia
    de la última hora en casa, lo que se equivocaba el modelo
    de temperatura en casa, lo seco que estaba el aire y la lluvia de la
    última hora en Sant Cugat (la misma que guarda el registro, ADR 0042;
    hasta la auditoría del 09-10-2026 la variante se entrenaba con ella pero
    al prever no llegaba, y las primeras horas caían al modelo del archivo).
    Sin dato reciente de Sant Cugat (riera None: más de 2 horas), None, y
    esa variante usa el archivo en las primeras horas; el error «riera: …»
    de la pasada lo deja apuntado."""
    d = {"pluja_1h_emes": casa.get("pluja_1h") if casa else None,
         "error_temp_ara": None, "deficit_rosada_ara": None,
         "pluja_1h_xv": (riera or {}).get("mm_1h"),
         # La de las vecinas de Montflorit, como la guarda el registro (ADR 0070).
         "pluja_1h_veines": A.pluja_veines(pluja_veines_ara(veines))}
    if casa and casa.get("temperatura") is not None:
        t_model = temperatura_model_ara(h, dt.datetime.fromisoformat(casa["hora"]))
        if t_model is not None:
            d["error_temp_ara"] = round(t_model - casa["temperatura"], 2)
        if casa.get("rosada") is not None:
            d["deficit_rosada_ara"] = round(casa["temperatura"] - casa["rosada"], 1)
    # El error del rocío del modelo contra el del barrio, la mediana de casa y
    # las vecinas, el mismo del recuadro «Ara» (ADR 0114).
    d["error_rosada_ara"] = None
    rosada = _mediana([(casa or {}).get("rosada")] + [v.get("rosada") for v in veines or []])
    hora = (casa or {}).get("hora") or next((v.get("hora") for v in veines or [] if v.get("hora")), None)
    if rosada is not None and hora:
        ahora = dt.datetime.fromisoformat(hora)
        t, hr = temperatura_model_ara(h, ahora), temperatura_model_ara(h, ahora, "relative_humidity_2m")
        if t is not None and hr is not None:
            d["error_rosada_ara"] = round(SE.rosada(t, hr) - rosada, 2)
    return d


def lluvia_modelos(h, i):
    """Lluvia de la hora i: la mayor de los modelos finos."""
    v = [h.get(f"precipitation_{m}", [None] * (i + 1))[i] for m in C.MODELOS_FINOS]
    v = [x for x in v if x is not None]
    return max(v) if v else (h.get("precipitation_meteofrance_seamless", [0] * (i + 1))[i] or 0.0)


def ratxa_modelos(h, i):
    """Ratxa de l'hora i: la més forta dels models fins, com la pluja
    (lluvia_modelos). La previsió combinada de Météo-France barreja els seus
    models i rebaixa els pics: el 19-10-2026 a les 13:43 donava 66 km/h de 17 a
    18 h amb AROME HD a 92 i AROME a 89, i l'avís de vent fort desapareixia
    (Juanjo: «hazlo»). Sense cap model fi, la combinada."""
    v = [h.get(f"wind_gusts_10m_{m}", [None] * (i + 1))[i] for m in C.MODELOS_FINOS]
    v = [x for x in v if x is not None]
    return max(v) if v else h.get("wind_gusts_10m_meteofrance_seamless", [None] * (i + 1))[i]


def persistencia(mm_ultima_hora, k):
    """Probabilidad y lluvia mediana k horas después de una hora con esa
    lluvia, según el histórico (None si no ha llovido)."""
    tabla = P.CALIBRACION_COMPLETA.get("persistencia", {})
    for clase in sorted(tabla, key=float, reverse=True):
        if mm_ultima_hora >= float(clase):
            return tabla[clase].get(str(k))
    return None


def avisos_del_tramo(ini, fin, avisos, tots=True):
    """Avisos de AEMET que cubren el tramo. Los planes de Protección Civil no
    tienen hora de fin: van en un aviso aparte, encima de la tabla. tots=False:
    sin los que cubre Meteocat (lo que se muestra, ADR 0093)."""
    res = {}
    for a in avisos or []:
        # Sense els que cobreix Meteocat, només les hores que no cobreix (smp.visible).
        v = a if tots else SMP.visible(a)
        a_ini, a_fin = (dt.datetime.fromisoformat(v[k]) for k in ("inicio", "fin"))
        if a["zona"] == C.ZONA_AVISOS and a_ini < fin and a_fin > ini and (tots or not a.get("cobert")):
            res.setdefault(a["nivel"], set()).add(a["tipo"])
    return [{"nivell": n, "tipus": sorted(t)} for n, t in res.items()]


# Los avisos de Meteocat de esta pasada, para la tabla (casa.py los lee antes
# de calcular las horas).
SMP_ACTUAL = None


def avisos_mostrats(ini, fin, avisos):
    """Lo que la tabla pinta en el tramo: los de Meteocat y los de AEMET que
    Meteocat no cubre (ADR 0093)."""
    return SMP.per_hora(ini, fin, SMP_ACTUAL) + avisos_del_tramo(ini, fin, avisos, tots=False)


def senyals_avis(ini, fin, avisos, planes):
    """Lo que dice lo oficial de la hora, para que el modelo aprenda cuánto
    pesa (ADR 0047 y 0097): si había aviso de AEMET por lluvia o tormentas, si
    el INUNCAT estaba en alerta o emergencia y si Meteocat avisaba por lluvia
    o tiempo violento en la comarca, y con peligro alto o más (grado 3 o
    más). None si no se pudieron leer."""
    tipus = {t for a in avisos_del_tramo(ini, fin, avisos) for t in a["tipus"]}
    res = {"avis_pluja": None if avisos is None else float(bool(tipus & {"pluja", "tempestes"})),
           "pla_inuncat": None if planes is None else float(any(
               p["pla"] == "INUNCAT" and p["fase"] in ("alerta", "emergència") for p in planes))}
    graus = SMP.graus_pluja(ini, SMP_ACTUAL)
    res["avis_meteocat"] = None if graus is None else float(bool(graus))
    res["avis_meteocat_alt"] = None if graus is None else float(max(graus, default=0) >= 3)
    return res


def prob_ensemble(e):
    """Fracción de miembros del ensemble con lluvia, por hora."""
    miembros = [k for k in e if k.startswith("precipitation")]
    if not miembros:
        return {}
    return {t: sum((e[k][i] or 0) >= C.UMBRAL_MM for k in miembros) / len(miembros)
            for i, t in enumerate(e["time"])}


def variables_hora(desde, h, prob, i, prever):
    """Lo que dan los modelos para la hora que acaba en h["time"][i] y lo que
    medían las estaciones al prever (al_prever): lo que usa el modelo
    aprendido y lo que se guarda en el registro."""
    t = h["time"][i]
    fin = dt.datetime.fromisoformat(t).astimezone()
    d = {"fins": t, "antelacio_h": round((fin - desde).total_seconds() / 3600, 2),
         "prob_ens": prob.get(t)}
    for m in C.MODELOS_FINOS + [C.MODEL_ECMWF]:
        d[f"pluja_{m}"] = (h.get(f"precipitation_{m}") or [None] * (i + 1))[i]
    for campo in ("temperature_2m", "relative_humidity_2m", "cloud_cover",
                  "wind_speed_10m", "wind_gusts_10m", "weather_code", "shortwave_radiation"):
        d[campo] = h.get(f"{campo}_meteofrance_seamless", [None] * (i + 1))[i]
    # Las nubes de cada modelo, todas y las bajas, para saber cuál acierta
    # más (ADR 0088).
    d.update({f"nuvols_{nom}": v for nom, v in NV.valors_hora(h, i).items()})
    d.update({f"nuvols_baixos_{nom}": v for nom, v in NV.valors_hora(h, i, "cloud_cover_low").items()})
    d.update(prever or {})
    return d


def previsio(desde, h, e, avisos, model=None, casa=None, nc=None, planes=None, riera=None, veines=None,
             nuvols_ara=None):
    """Una fila por tramo de una hora («de 10 a 11»), de la hora actual a 24
    horas después como mínimo, hasta las 21 h de mañana y acabando un tramo
    del día (FI_TRAMS). Open-Meteo da la lluvia acumulada en la hora anterior: el
    tramo de 10 a 11 se lee en la hora 11:00, y los demás valores también.
    nuvols_ara: las nubes bajas que observa ahora el aeropuerto de Sabadell
    (nuvols.ara), que mandan en la hora en curso; las de encima, de los
    modelos (nuvols.cel_ara, ADR 0088)."""
    prob = prob_ensemble(e)
    llueve_ahora = llueve_ahora_en(casa, veines)
    prever = al_prever(desde, h, casa, riera, veines)
    desviacio = desviacio_pressio(h, casa)
    # La persistencia, con la lluvia de la red del barrio (consens_pluja).
    ultima_hora = consens_pluja(casa, veines)["pluja_1h"] or 0.0

    def valor(campo, i):
        return h.get(f"{campo}_meteofrance_seamless", [None] * (i + 1))[i]

    primera = desde.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    fi_dema = (dt.datetime.combine(desde.date() + dt.timedelta(days=1), dt.time(FI_DEMA))).strftime("%Y-%m-%dT%H:%M")
    filas = []
    for i, t in enumerate(h["time"]):
        if t < primera.strftime("%Y-%m-%dT%H:%M"):
            continue
        if (len(filas) >= HORAS and filas[-1]["fins"] >= fi_dema
                and int(filas[-1]["fins"][11:13]) in FI_TRAMS):
            break
        fin = dt.datetime.fromisoformat(t).astimezone()
        ini = fin - dt.timedelta(hours=1)
        n = len(filas)
        d = variables_hora(desde, h, prob, i, prever)
        d.update(senyals_avis(ini, fin, avisos, planes))
        # Probabilidad aprendida con lo que llovió de verdad; sin modelo, la
        # fracción del ensemble.
        p = A.prob_pluja(model, d)
        if p is None:
            p = prob.get(t)
        mm = round(lluvia_modelos(h, i), 1)
        # La temperatura es la de un instante: la del tramo de 18 a 19, la media
        # de las 18 y las 19, las dos corregidas (la lluvia sí es la acumulada
        # hasta el final del tramo).
        temp = A.temperatura(model, d)
        d_antes = variables_hora(desde, h, prob, i - 1, prever) if i > 0 else None
        if d_antes:
            antes = A.temperatura(model, d_antes)
            if antes is not None and temp is not None:
                temp = (antes + temp) / 2
        humitat = humitat_hora(model, d, d_antes, temp)
        segun_estacion = False
        # Primeras horas: la persistencia de la lluvia que mide ahora la
        # estación, si da más que los modelos.
        dato = persistencia(ultima_hora, n + 1) if n < HORAS_PERSISTENCIA else None
        if dato:
            if p is None or dato["probabilitat"] > p:
                p, segun_estacion = dato["probabilitat"], True
            if dato["mediana_mm"] > mm:
                mm, segun_estacion = dato["mediana_mm"], True
        # Primeras dos horas: la lluvia del radar llevada hacia delante (ADR
        # 0019), si da más. No rebaja nada: la lluvia que aún no ha nacido no
        # se ve en el radar.
        segun_radar = False
        # La probabilidad vale aunque el radar cubra solo una parte de la hora
        # (si llueve en ese rato, llueve en la hora); los mm, solo si cubre
        # media hora o más. Los dos, solo si la probabilidad del radar llega a
        # PROB_ATENCION, la misma con la que el recuadro dice «Pot arribar
        # pluja»: con menos, la tabla marcaba «†» y el recuadro decía que no
        # venía lluvia (revisor, 18-10-2026: 0,2 mm con un 5 %).
        radar = N.en_tram(nc, "casa", max(ini, desde), fin)
        if radar and radar["prob"] >= C.PROB_ATENCION:
            if radar["prob"] > (p or 0):
                p, segun_radar = radar["prob"], True
            if radar["minuts"] >= 30 and radar["mm"] > mm and radar["mm"] >= C.UMBRAL_MM:
                mm, segun_radar = radar["mm"], True
        plou_ara = n == 0 and llueve_ahora
        if plou_ara:
            p, segun_estacion = 1.0, True
        filas.append({
            "hora": P.clau_hora(ini), "fins": t,
            "temperatura": None if temp is None else round(temp, 1),
            "pluja_mm": round(mm, 1), "probabilitat": round(p, 2) if p is not None else None,
            "plou_ara": plou_ara, "segons_estacio": segun_estacion,
            "segons_radar": segun_radar and not plou_ara and not segun_estacion,
            "radar": radar,
            "avisos": avisos_mostrats(ini, fin, avisos),
            "nuvols": (NV.cel_ara(nuvols_ara, h, i) if n == 0 and nuvols_ara is not None
                       else NV.mescla(NV.valors_hora(h, i))),
            "codi": valor("weather_code", i),
            "vent": vent_hora(h, i), "ratxa": ratxa_modelos(h, i),
            # La de cada model fi, perquè l'avís de vent fort digui quants la
            # veuen (Juanjo, 19-10-2026: «indicar el origen de la alerta y a
            # ser posible la validez que tiene»; riscos.font).
            "ratxes_models": {m: h.get(f"wind_gusts_10m_{m}", [None] * (i + 1))[i] for m in C.MODELOS_FINOS},
            "neu": valor("snowfall", i), "humitat": humitat, "pressio": pressio_hora(h, i, desviacio)})
    return filas


def filas_registro(desde, h, e, mostradas, casa=None, avisos=None, planes=None, riera=None, veines=None):
    """Todo lo que los modelos daban para cada hora de la tabla, junto a lo que
    mostró la página: lo que hace falta para aprender de los fallos (ADR 0012)."""
    prob = prob_ensemble(e)
    indice = {t: i for i, t in enumerate(h["time"])}
    prever = al_prever(desde, h, casa, riera, veines)
    filas = []
    for f in mostradas:
        d = variables_hora(desde, h, prob, indice[f["fins"]], prever)
        d.pop("pluja_1h_emes")      # ya va en «ara_casa», una vez por línea
        d.pop("pluja_1h_xv", None)  # ya va en «sant_cugat», una vez por línea
        d.pop("pluja_1h_veines", None)  # y las vecinas, en «veines»
        fin = dt.datetime.fromisoformat(f["fins"]).astimezone()
        d.update(senyals_avis(fin - dt.timedelta(hours=1), fin, avisos, planes))
        # «plou_ara», para saber qué veredicto dio «Si surts» (ADR 0047).
        d["mostrat"] = {"pluja_mm": f["pluja_mm"], "probabilitat": f["probabilitat"],
                        "temperatura": f["temperatura"], "segons_estacio": f["segons_estacio"],
                        "segons_radar": f.get("segons_radar", False), "plou_ara": f.get("plou_ara", False),
                        "ratxa": f.get("ratxa"), "nuvols": f.get("nuvols")}
        # Lo que daba el radar llevado hacia delante, para aprender (ADR 0019).
        d["radar_mm"] = (f.get("radar") or {}).get("mm")
        d["radar_prob"] = (f.get("radar") or {}).get("prob")
        filas.append(d)
    return filas


def previsio_anterior(origen, avisos, casa=None, veines=None, nuvols_ara=None):
    """Las horas que aún no han pasado de la última previsión buena, con los
    avisos, la lluvia y el cielo de ahora. None si no la hay o tiene más de
    CASA_PREVISION_ANTERIOR_MAX_H horas."""
    if not origen:
        return None
    try:
        if origen.startswith("http"):
            antes = json.loads(P.get(origen))
        else:
            with open(origen, encoding="utf-8") as f:
                antes = json.load(f)
    except Exception:
        return None
    de = antes.get("previsio_de") or antes.get("generat")
    if not antes.get("hores") or not de:
        return None
    if P.AHORA - dt.datetime.fromisoformat(de) > dt.timedelta(hours=C.CASA_PREVISION_ANTERIOR_MAX_H):
        return None
    ara_hora = P.AHORA.strftime("%Y-%m-%dT%H:%M")
    hores = [dict(f) for f in antes["hores"] if f["fins"] > ara_hora]
    if not hores:
        return None
    llueve_ahora = llueve_ahora_en(casa, veines)
    for n, f in enumerate(hores):
        fin = dt.datetime.fromisoformat(f["fins"]).astimezone()
        f["avisos"] = avisos_mostrats(fin - dt.timedelta(hours=1), fin, avisos)
        f["plou_ara"] = n == 0 and llueve_ahora
        if f["plou_ara"]:
            f["probabilitat"], f["segons_estacio"] = 1.0, True
        # Sin modelos, las nubes de encima son las de la previsión anterior.
        if n == 0 and nuvols_ara is not None:
            f["nuvols"] = max(nuvols_ara, f.get("nuvols") or 0)
    return {"hores": hores, "previsio_de": de, "aprenentatge": antes.get("aprenentatge")}


def comprobacion_modelos(desde, h, filas_estacion, consens_3h=None):
    """Lluvia medida en casa y prevista en las últimas horas completas. Si
    los modelos se han quedado muy cortos, la página lo dice. Solo si las
    lecturas de la estación (ecowitt.resum_ara) cubren esas horas. Lo medido,
    el de la red del barrio (consens_3h, la mediana que muestra «Ara»), si
    lo hay: con solo la estación de casa, la nota decía «12 mm a Montflorit»
    junto a «6 mm avui» (inventari del 18-10-2026)."""
    if not filas_estacion:
        return None
    fin = desde.replace(minute=0, second=0, microsecond=0)
    ini = fin - dt.timedelta(hours=HORAS_COMPROBACION)
    if filas_estacion[0]["t"] > ini or filas_estacion[-1]["t"] < fin:
        return None
    medida = E.pluja_entre(filas_estacion, ini, fin)
    if consens_3h is not None and HORAS_COMPROBACION == 3:
        medida = consens_3h
    prevista = 0.0
    for i, t in enumerate(h["time"]):
        tt = dt.datetime.fromisoformat(t).astimezone()
        if ini < tt <= fin:
            prevista += lluvia_modelos(h, i)
    fallan = medida >= 3 and medida > 3 * prevista + 1
    return {"hores": HORAS_COMPROBACION, "mesurada_mm": round(medida, 1),
            "prevista_mm": round(prevista, 1), "no_encerten": fallan}


def recoger(anterior=None):
    salida = {"versio": C.VERSION, "generat": P.AHORA.isoformat(timespec="minutes"),
              "errors": []}
    # La estación del barrio es la de casa, en «ara_casa» (ADR 0017 y 0058).
    casa = None
    try:
        casa = estacio_casa()
    except Exception as ex:
        salida["errors"].append(f"estació de casa: {ex}")
    salida["ara_casa"] = casa and {k: v for k, v in casa.items() if k != "files"}
    # La temperatura medida cada hora de las últimas 72, para decir cuántos
    # grados más o menos que ayer (ADR 0061). Solo en el NAS, que tiene el
    # registro; sin él (la reserva de IONOS), no se compara.
    salida["temperatura_mesurada"] = None
    if R.hay_registro():
        try:
            salida["temperatura_mesurada"] = R.temperatures_casa(
                P.AHORA, recents=E.hores(casa["files"]) if casa else None) or None
        except Exception as ex:
            print("No he podido leer la temperatura medida:", ex, file=sys.stderr)
    # La estación de casa, a Weather Underground (ADR 0059). Si falla, no es
    # cosa de la página: solo se apunta.
    if casa and WU.disponible():
        try:
            WU.puja(casa, P.AHORA)
        except Exception as ex:
            print("No he podido subir la estación a Weather Underground:", ex, file=sys.stderr)
    # Las estaciones vecinas de Weather Underground (ADR 0060): si falla una,
    # solo se apunta; si no se puede leer ninguna teniendo clave (caducada,
    # red caída), la página lo dice, porque «plou ara» cuenta con ellas.
    veines = []
    if WU.lectura_disponible():
        veines, fallos = WU.veines_ara(P.AHORA)
        for fallo in fallos:
            print("No he podido leer la estación vecina", fallo, file=sys.stderr)
        if fallos and not veines:
            salida["errors"].append(f"estacions veïnes: {fallos[0]}")
        dies = WU.dies_fins_caducitat(P.AHORA)
        if dies <= C.WU_AVIS_CADUCITAT_DIES:
            print(f"La clau de lectura de Weather Underground caduca d'aquí a {dies} dies "
                  f"({C.WU_CLAU_CADUCA}): cal regenerar-la (RESTAURAR.md).", file=sys.stderr)
    salida["veines"] = [{k: v for k, v in x.items() if k != "files"} for x in veines]
    # El sol directo sobre el termómetro de casa (ADR 0081): se corrige con las
    # vecinas y la diferencia habitual, también en las horas para comparar
    # (por si el episodio ha empezado en esta pasada).
    if salida["ara_casa"] and R.hay_registro():
        try:
            salida["ara_casa"] = SE.corregeix(salida["ara_casa"], casa.get("files") if casa else None, veines, P.AHORA)
            if salida["temperatura_mesurada"]:
                salida["temperatura_mesurada"] = SE.amb_esperades(salida["temperatura_mesurada"], P.AHORA) or None
        except Exception as ex:
            print("No he pogut mirar el sol directe a l'estació:", ex, file=sys.stderr)
    # La lluvia y la humedad de «Ara», por consenso de la red del barrio.
    salida["ara_casa"] = consens(salida["ara_casa"], casa, veines)
    # La parte alta (ADR 0087): la diferencia de cada hora, para la previsión
    # y, si falla la estación de casa, para «Ara»; y la de ahora, medida.
    try:
        taula_alta = PA.per_hores(P.AHORA) if R.hay_registro() else PA.inicial()
    except Exception as ex:
        print("No he pogut calcular la part alta:", ex, file=sys.stderr)
        taula_alta = PA.inicial()
    if not salida["ara_casa"] and veines:
        salida["ara_casa"] = ara_sense_casa(veines, taula_alta, P.AHORA)
    if salida["ara_casa"]:
        salida["ara_casa"]["dif_alta"] = PA.ara(salida["ara_casa"].get("temperatura"), veines, P.AHORA)
    # Lo medido cada hora en la parte alta, para comparar con ayer cuando se
    # mira esa zona (ADR 0123). Solo en el NAS, como el de la riera.
    salida["temperatura_mesurada_alta"] = None
    if R.hay_registro():
        try:
            salida["temperatura_mesurada_alta"] = PA.mesurada(P.AHORA) or None
        except Exception as ex:
            print("No he pogut llegir la temperatura de la part alta:", ex, file=sys.stderr)
    # En el NAS, si dura un fallo de las estaciones, se le dice a Juanjo.
    if R.hay_registro():
        try:
            ES.vigila(casa is not None if E.disponible() else None,
                      [v["estacio"] for v in veines] if WU.lectura_disponible() else None, P.AHORA)
        except Exception as ex:
            print("No he pogut vigilar les estacions:", ex, file=sys.stderr)
    # Si llueve ahora, en casa o en una vecina que cuenta: lo que miran el
    # bot, los avisos y la web (plou_ara de la primera hora de la tabla).
    salida["plou_ara"] = llueve_ahora_en(casa, veines)
    # El viento de ahora, de la estación de Meteocat más cercana (ADR 0037).
    try:
        salida["vent"] = P.vent_meteocat(C.VENT_ESTACIO)
    except Exception as ex:
        salida["vent"] = None
        salida["errors"].append(f"vent: {ex}")
    # El mismo viento estimado con las vecinas (ADR 0064): se calcula siempre
    # para compararlo y solo sustituye al de Sant Cugat si Juanjo lo decide.
    try:
        salida["vent_veines"] = VV.ara(veines, ahora=P.AHORA)
    except Exception as ex:
        salida["vent_veines"] = None
        print("No he podido estimar el viento con las vecinas:", ex, file=sys.stderr)
    if C.VENT_VEINES_ACTIU and salida["vent_veines"]:
        salida["vent"] = salida["vent_veines"]
    avisos = planes = None
    try:
        avisos = [a for a in P.avisos() if a["zona"] == C.ZONA_AVISOS
                  and dt.datetime.fromisoformat(a["fin"]) > P.AHORA]
    except Exception as ex:
        salida["errors"].append(f"avisos: {ex}")
    try:
        planes = P.planes_proteccion_civil()
    except Exception as ex:
        salida["errors"].append(f"plans: {ex}")
    # Si Meteocat tiene aviso de peligro para la comarca: junto a los planes,
    # que no dicen qué zona abarcan (ADR 0067), y, desde el 11-10-2026, en
    # cada pasada, para avisar como los de AEMET (ADR 0071). Si falla, no se
    # dice nada.
    salida["smp"] = None
    try:
        salida["smp"] = SMP.llegeix(P.get, P.AHORA)
    except Exception as ex:
        salida["errors"].append(f"smp: {ex}")
    # Per fenomen, mana Meteocat; l'AEMET, per al que no cobreix (ADR 0093).
    SMP.marca_coberts(avisos, salida["smp"])
    global SMP_ACTUAL
    SMP_ACTUAL = salida["smp"]
    # Los planes sin motivo meteorológico a la vista (la recuperación tras un
    # temporal) no se muestran ni ponen la página en modo aviso; van aparte,
    # para que los avisos del canal no anuncien un final que no ha habido
    # (ADR 0062).
    salida["plans_ocults"] = None
    if planes is not None:
        salida["plans_ocults"] = [p for p in planes if not P.pla_per_temps(p, avisos, P.AHORA, salida["smp"])]
        planes = [p for p in planes if P.pla_per_temps(p, avisos, P.AHORA, salida["smp"])]
    salida["avisos"], salida["plans"] = avisos, planes
    # Los umbrales de lluvia de «Si surts», los aprendidos (ADR 0069).
    try:
        salida["sortir_llindars"] = A.llindars_sortir()
    except Exception as ex:
        salida["errors"].append(f"llindars: {ex}")
    radar = None
    try:
        radar = P.radar()
    except Exception as ex:
        salida["errors"].append(f"radar: {ex}")
    obs = [o for o in [E.observacio(casa, C.ESTACIO_CASA)] + [WU.observacio(v) for v in veines] if o]
    motivos = P.motivos_modo_aviso(avisos, planes, obs, radar, salida["smp"])
    # En modo aviso, todo el día: hasta las 23:50, no solo hasta las 23:00.
    nc = (radar or {}).get("nowcast")
    # Els graus, per a la fletxa del mapa (17-10-2026).
    salida["radar"] = nc and {k: nc.get(k) for k in ("hora", "imatge", "moviment", "velocitat_kmh", "cap_a", "graus")}
    if nc:
        # Els ecos febles a sobre del barri, per dir plugim (estat_pluja).
        salida["radar"]["plugim"] = plugim_radar(radar.get("a_prop"))
        # Cuándo llegaría: probable (50 %) o, si no, posible (20 %).
        for clau, prob in (("arriba", 0.5), ("possible", C.PROB_ATENCION)):
            t = N.arribada(nc, "casa", prob)
            salida["radar"][clau] = t and t.isoformat(timespec="minutes")
        # Cómo sería al llegar, para el aviso de antes de llover (ADR 0022).
        salida["radar"]["arriba_mm_h"] = N.intensitat_arribada(nc, "casa")
        # El mapa i la pluja més propera, per al requadre del radar (17-10-2026).
        salida["radar"]["mapa"], salida["radar"]["propera"] = radar.get("mapa"), radar.get("propera")
        # La pluja forta o més a 15 km o menys, per al titular (17-10-2026).
        salida["radar"]["forta"] = radar.get("forta")
        # Si la pluja creix al voltant de casa (17-10-2026).
        salida["radar"]["creixement"] = radar.get("creixement")
        # A qué hora pararía, «en entrenament» en la página (fi_pluja.py, ADR 0049).
        try:
            salida["radar"].update(FP.fi_radar(nc, P.AHORA, salida["radar"]["arriba"]) or {})
        except Exception as ex:
            salida["errors"].append(f"final de la pluja: {ex}")
    # La riera de Sant Cugat: lo que ha llovido en la cuenca y lo que trae el
    # radar, para el aviso por Telegram (ADR 0027).
    try:
        salida["riera"] = RI.calcula(P.AHORA, nc, pluja_barri=(salida.get("ara_casa") or {}).get("pluja_30min"))
        if salida["riera"] is None or salida["riera"].get("sense_meteocat"):
            salida["errors"].append("riera: Sant Cugat (Meteocat) sense dades recents")
            # Desde cuándo, para que la página lo diga (21-10-2026).
            try:
                salida["riera_meteocat_fins"] = RI.darrera_meteocat(P.AHORA)
            except Exception:
                salida["riera_meteocat_fins"] = None
        elif salida["riera"].get("incomplet"):
            salida["errors"].append("riera: a Sant Cugat (Meteocat) li falten mitges hores de pluja")
    except Exception as ex:
        salida["riera"] = None
        salida["errors"].append(f"riera: {ex}")
    # La previsió de crescuda de les properes hores, per a la pàgina «Riera»
    # (ADR 0107): una previsió, no un avís.
    try:
        salida["riera_previsio"] = RI.previsio(P.AHORA)
    except Exception as ex:
        salida["riera_previsio"] = None
        salida["errors"].append(f"riera, previsió: {ex}")
    salida["horari"] = P.horario([C.HORARIO_CASA_AVISO if motivos else C.HORARIO_CASA],
                                 C.INTERVALO_CASA_MIN, motivos, (radar or {}).get("km_lluvia"))
    # Las nubes bajas que se ven ahora desde el aeropuerto de Sabadell (ADR
    # 0088). Si no se puede leer, el cielo de la hora en curso es el de los
    # modelos.
    metars = []
    try:
        metars = NV.llegeix(P.get)
    except Exception as ex:
        print("No he pogut llegir el METAR de Sabadell:", ex, file=sys.stderr)
    nuvols_ara = NV.ara(metars, P.AHORA)
    try:
        h, e = modelos(P.AHORA, salida["errors"])
        model = A.carrega()
        salida["aprenentatge"] = A.resum_pagina(model)
        salida["hores"] = previsio(P.AHORA, h, e, avisos, model, casa, nc, planes, salida.get("riera"), veines,
                                   nuvols_ara)
        PA.a_les_hores(salida["hores"], taula_alta, PA.ajust_nit())
        if R.hay_registro():
            try:
                PA.apunta_nit(salida["hores"], P.AHORA)
            except Exception as ex:
                # Només el registre: a la pàgina no li afecta.
                print(f"registre de les nits: {ex}", file=sys.stderr)
        salida["models"] = comprobacion_modelos(P.AHORA, h, (casa or {}).get("files", []),
                                                (salida.get("ara_casa") or {}).get("pluja_3h"))
    except Exception as ex:
        salida["hores"] = salida["models"] = None
        salida["errors"].append(f"previsió: {ex}")
        print("Sense previsió nova:", ex, file=sys.stderr)
        # Sin modelos: la última previsión buena, si es reciente, avisando.
        antes = previsio_anterior(anterior, avisos, casa, veines, nuvols_ara)
        if antes:
            salida.update(antes)
    # L'estat únic de la pluja (ADR 0101): el que diuen la portada, el radar,
    # la taula, «Si surts» i el bot, i les hores, d'acord amb ell.
    salida["pluja_ara"] = estat_pluja(salida.get("radar"), salida.get("plou_ara"), P.AHORA)
    ajusta_hores(salida.get("hores"), salida["pluja_ara"], P.AHORA)
    # Y la verdad medida de ahora, para comprobar el radar (ADR 0102): sí, no
    # o no se sabe (una sola vecina, sin vecinas que confirmen, o llovizna
    # que solo ve el radar).
    salida["pluja_ara"]["mesurada"] = A.plou_ara_barri(casa, veines, salida["pluja_ara"].get("plugim"))
    # La niebla de la hora en curso (ADR 0100): la que observa el aeropuerto
    # de Sabadell, si además la estación de casa está saturada. AROME, de
    # donde sale el tipo de tiempo de cada hora, no da niebla (17-10-2026).
    try:
        # La de l'estació de casa, vora la riera, no la del barri (17-10-2026: amb
        # boira, el barri donava el 96 % i casa el 99 %).
        ara_casa = salida.get("ara_casa") or {}
        humitat = ara_casa.get("humitat_estacio", ara_casa.get("humitat"))
        if salida["hores"] and NV.boira_ara(metars, P.AHORA) and humitat is not None and humitat >= C.HUMITAT_BOIRA:
            salida["hores"][0].update(codi=45, boira_observada=True)
    except Exception as ex:
        salida["errors"].append(f"boira: {ex}")
    # Para «Si surts» (ADR 0029): el índice UV de cada hora y si circulan los
    # trenes de cerca.
    try:
        uv = indice_uv(P.AHORA)
        for f in salida["hores"] or []:
            valors = [uv[t] for t in (f["hora"], f["fins"]) if t in uv]
            f["uv"] = round(max(valors), 1) if valors else None
    except Exception as ex:
        salida["errors"].append(f"índex UV: {ex}")
    try:
        salida["trens"] = TR.calcula(P.AHORA)
    except Exception as ex:
        salida["trens"] = None
        salida["errors"].append(f"trens: {ex}")
    # Los autobuses del barrio, para «Consultes» y «Si surts» (ADR 0120).
    try:
        salida["busos"] = BU.calcula(P.AHORA)
        salida["errors"] += [f"busos: {e}" for e in salida["busos"].pop("errors", [])]
    except Exception as ex:
        salida["busos"] = None
        salida["errors"].append(f"busos: {ex}")
    # Incidencias de tráfico de cerca, para el coche y la moto (ADR 0052).
    try:
        salida["transit"] = TT.calcula(P.AHORA)
    except Exception as ex:
        salida["transit"] = None
        salida["errors"].append(f"trànsit: {ex}")
    # Los cortes de luz de cerca, para «Consultes» y /llum (ADR 0072).
    try:
        salida["llum"] = LL.calcula(P.AHORA)
    except Exception as ex:
        salida["llum"] = None
        salida["errors"].append(f"llum: {ex}")
    # La previsión de la semana, debajo de la gráfica (ADR 0122). Si falla, la
    # de la pasada anterior: la página quita los días ya pasados.
    try:
        salida["setmana"] = SM.calcula(P.AHORA, taula_alta)
    except Exception as ex:
        salida["setmana"] = (anterior or {}).get("setmana")
        salida["errors"].append(f"setmana: {ex}")
    # El sol y la calidad del aire, para «Consultes», /sol y /aire (ADR 0054).
    for clau, funcio in (("sol", lambda: sol(P.AHORA)), ("aire", lambda: AI.calcula(P.AHORA))):
        try:
            salida[clau] = funcio()
        except Exception as ex:
            salida[clau] = None
            salida["errors"].append(f"{clau}: {ex}")
    # El polen de la semana en Bellaterra, para «Consultes» y /pollen (ADR 0054).
    try:
        salida["pollen"] = PO.calcula(P.AHORA)
    except Exception as ex:
        salida["pollen"] = None
        salida["errors"].append(f"pol·len: {ex}")
    # Incendios cerca, Pla Alfa y acceso a Collserola (ADR 0046).
    salida["entorn"] = EN.calcula(P.AHORA)
    salida["errors"] += [f"entorn: {e}" for e in salida["entorn"].pop("errors")]
    # Situaciones de peligro según lo medido y lo previsto (ADR 0018).
    salida["riscos"] = RS.detecta(salida, P.AHORA)
    # Registro para aprender (solo en el NAS, que tiene /estat): lo que medía
    # la estación de casa, por horas y cada 5 minutos, la lluvia por horas de
    # las estaciones de Meteocat, lo que medían las vecinas y, una vez por
    # hora, lo que daban los modelos.
    if R.hay_registro():
        try:
            if casa:
                R.apunta_estacio_casa(E.hores(casa["files"]))
                R.apunta_casa_5min(R.cincs_casa(casa["files"]))
            # Y las vecinas cada 5 minutos, para el final de la lluvia (ADR 0102).
            R.apunta_veines_5min({v["estacio"]: R.cincs_casa(v["files"]) for v in veines if v.get("files")})
            if salida["hores"] and not salida.get("previsio_de"):
                r = salida.get("riera")
                R.apunta_casa(P.AHORA, filas_registro(P.AHORA, h, e, salida["hores"][:HORAS], casa,
                                                      avisos, planes, salida.get("riera"), veines),
                              salida["ara_casa"], {"pluja_1h": r["mm_1h"], "fins": r["fins"]} if r else None,
                              pluja_veines_ara(veines) if veines else None)
        except Exception as ex:
            print("No he podido apuntar en el registro:", ex, file=sys.stderr)
        if radar:
            try:
                R.apunta_radar_a_prop(P.AHORA, radar, motivos, obs)
            except Exception as ex:
                print("No he podido apuntar los ecos del radar:", ex, file=sys.stderr)
        for codi in C.ESTACIONES:
            try:
                R.apunta_meteocat(codi, R.hores_meteocat(RI.files(codi, P.AHORA, 6, None)))
            except Exception as ex:
                print(f"No he podido apuntar la estación {codi} de Meteocat:", ex, file=sys.stderr)
        # Las vecinas por horas (ADR 0060): las de hoy en cada pasada y, una
        # vez al día, las de ayer, para cerrar la última hora del día.
        vent_mitges = {}
        for v in veines:
            try:
                files = v["files"]
                if R.falta_ahir_veina(v["estacio"], P.AHORA):
                    files = WU.hores_ahir(v["estacio"], P.AHORA) + files
                R.apunta_veina(v["estacio"], R.hores_veina(files))
                vent_mitges[v["estacio"]] = VV.mitges_hores_veina(files)
            except Exception as ex:
                print(f"No he podido apuntar la estación vecina {v['estacio']}:", ex, file=sys.stderr)
        # El viento por medias horas de las vecinas y de Meteocat, para
        # aprender a estimarlo con las vecinas (ADR 0064).
        for codi in VV.OFICIALS:
            try:
                vent_mitges[codi] = VV.mitges_hores_meteocat(P.files_meteocat(codi))
            except Exception as ex:
                print(f"No he podido leer el viento de {codi}:", ex, file=sys.stderr)
        try:
            VV.apunta(vent_mitges)
        except Exception as ex:
            print("No he podido apuntar el viento por medias horas:", ex, file=sys.stderr)
        # Las nubes observadas en Sabadell, para saber qué modelo acierta más
        # (ADR 0088).
        if metars:
            try:
                NV.apunta(metars, P.AHORA)
            except Exception as ex:
                print("No he podido apuntar las nubes de Sabadell:", ex, file=sys.stderr)
        # Lo que daba cada radar, para saber cuál acierta más (ADR 0026).
        try:
            RF.apunta(P.AHORA, nc, salida)
        except Exception as ex:
            print("No he podido apuntar los radares:", ex, file=sys.stderr)
    return salida


if __name__ == "__main__":
    datos = recoger(sys.argv[sys.argv.index("--anterior") + 1] if "--anterior" in sys.argv else None)
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
    print(f"Generado {datos['generat']}", datos["errors"] or "")
    print("Casa:", datos["ara_casa"])
    print("Modelos:", datos["models"])
    print("Planes:", datos["plans"])
    for f in (datos["hores"] or [])[:8]:
        print(f["hora"][11:16], f["temperatura"], "°C", f["pluja_mm"], "mm", f["probabilitat"],
              "estació" if f["segons_estacio"] else "", "PLOU ARA" if f["plou_ara"] else "",
              f["avisos"])
