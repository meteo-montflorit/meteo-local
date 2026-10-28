#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Los avisos públicos para el bot y el canal de Telegram (ADR 0034).

Tras cada cálculo (en el NAS o en la reserva de IONOS), mira los datos de casa
y decide qué avisos tocan para los vecinos, con su propio estado: el de los
avisos de Juanjo es otro. Los deja en avisos.json, que se sube a IONOS con
montflorit.json; allí el bot (bot/bot.py) los reparte a quien los haya elegido
y publica en el canal los importantes. Cada aviso lleva un identificador:
el bot no manda dos veces el mismo.

Tipos:
- pluja: llueve en Montflorit en unos 15 minutos, según el radar (la lógica
  de pluja_arriba.py, ADR 0022), un aviso por episodio de lluvia.
- perill: lo medido o previsto llega a los umbrales de aviso de AEMET (la de
  riscos.py, ADR 0018), al aparecer o subir de nivel; y, desde el 08-10-2026,
  un incendio forestal en curso que interesa al barrio (Bombers; desde el
  16-10-2026, en Collserola o a 2 km o menos) al empezar y al dejar de constar (entorn.py, ADR 0046 y 0071).
- riera: riesgo de desbordamiento de la riera de Sant Cugat (la de riera.py,
  ADR 0027), atención y peligro, siempre con el aviso de que es orientativo.
- perill, también, desde el 09-10-2026: los avisos oficiales nuevos (ADR 0055).
  Desde la 3.87.0 (ADR 0092), los de Meteocat para el Vallès Occidental, por
  fenómeno: el primero, si sube de nivel, un fenómeno nuevo, horas nuevas y el
  final; desde la 3.88.0 (ADR 0093), los de AEMET para el Prelitoral de
  Barcelona, de cualquier tipo, para lo que Meteocat no cubre. Un plan de Protección Civil al pasar a alerta o a emergencia
  y cuando sale de ellas. La prealerta no avisa (ADR 0051).

- llum, desde el 11-10-2026: un corte de luz de e-distribución en el barrio
  (llum.py, ADR 0072), al aparecer y al dejar de constar, con la calle
  probable, que es una estimación. Sin nivel: 🔌. No es peligro: no va a
  «Perill».

Cada aviso de peligro y de la riera es parte de un episodio (episodi): el
historial, con su comienzo y su final, va en avisos.json para la página
«Perill» de la web (ADR 0071). Desde la 3.194.0 no se borra nada: lo acabado
hace más de ARXIU_DIES días pasa a un archivo por año (avisos-AAAA.json), al
lado del estado y del avisos.json que se publica (ADR 0124).

Los trenes y el tráfico no avisan desde el 09-10-2026: se consultan en «Si
surts» y con /trens y /transit del bot (ADR 0053).

Uso: python3 avisos_bot.py CASA.json AVISOS.json [ANTERIOR]
     ANTERIOR: el avisos.json publicado (ruta o https), para unir su historial.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata
import urllib.request

import config as C
import hora as H
import nowcast as N
import pluja_arriba as PA
import revisor as RV
import smp as SMP
import riera as RI
import riscos as RS

ESTAT = os.path.join(os.path.dirname(os.environ.get("REGISTRE_DIR", "/estat/registre")), "bot-avisos.json")
CONSERVA_H = 24          # avisos que se guardan en avisos.json
# Lo acabado hace más de ARXIU_DIES días sale de avisos.json, que cada página
# de la web descarga, y pasa al archivo de su año, que solo lee «Perill» (ADR
# 0124; hasta la 3.193, un año y se borraba: HISTORIAL_DIES = 366). Más que los
# 30 días de «Últims 30 dies» de «Perill».
ARXIU_DIES = 35
# Más información de cada tipo de aviso, si su texto no lleva ya un enlace
# (ADR 0071).
BOMBERS = {"ca": "https://interior.gencat.cat/ca/arees_dactuacio/bombers/actuacions-de-bombers/",
           "es": "https://interior.gencat.cat/es/arees_dactuacio/bombers/actuacions-de-bombers/"}
PROTECCIO_CIVIL = {"ca": "https://interior.gencat.cat/ca/arees_dactuacio/proteccio_civil/",
                   "es": "https://interior.gencat.cat/es/arees_dactuacio/proteccio_civil/"}
AEMET = {"ca": "https://www.aemet.es/ca/eltiempo/prediccion/avisos?w=hoy&k=cat",
         "es": "https://www.aemet.es/es/eltiempo/prediccion/avisos?w=hoy&k=cat"}
METEOCAT = {"ca": "https://www.meteo.cat/prediccio/general", "es": "https://www.meteo.cat/prediccio/general"}
# El mapa de talls d'e-distribució centrat al barri (el mateix que /llum).
MAPA_LLUM = ("https://dpa-portalgis.enel.com/portal/apps/instant/basic/index.html"
             "?appid=21f5d825ceeb48dba6ef6ee97f840168&center=2.133,41.481&level=15&locale={}")
# Un tall d'una o dues cases no s'anuncia a tothom: es veu a «Llum» (ADR 0072).
LLUM_AVIS_CLIENTS_MIN = 3
# Los avisos que calcula la web, a su explicación con palabras corrientes en
# «Com funciona», en la lengua de quien lo lee; la metodología técnica se
# enlaza desde allí (Juanjo, 12-10-2026; ADR 0076).
ENLLAC_RIERA = {"ca": "https://meteo-montflorit.github.io/com-funciona.html#riera",
                "es": "https://meteo-montflorit.github.io/es/com-funciona.html#riera"}
ENLLAC_PROPI = {"ca": "https://meteo-montflorit.github.io/com-funciona.html#temps-extrem",
                "es": "https://meteo-montflorit.github.io/es/com-funciona.html#temps-extrem"}
WEB = "https://meteo-montflorit.github.io/"
# Corto: se lee en plena alerta; lo demás, en la explicación de «Com funciona»
# (Juanjo, 12-10-2026: «el texto de la alerta en sí ahora veo que es
# demasiado, condénsalo también»; ADR 0076).
ORIENTATIU = {
    "ca": "Avís en proves, orientatiu i no oficial.",
    "es": "Aviso en pruebas, orientativo y no oficial.",
}
NIVELLS_ES = {"groc": "amarillo", "taronja": "naranja", "vermell": "rojo"}
RISCOS_ES = {
    "pluja_30min": (None, "Ahora llueve con mucha intensidad: {v} mm en la última media hora."),
    "pluja_3h": ("Lluvia intensa prevista: {v} mm en 3 horas, {q}.",
                 "Ha llovido mucho: {v} mm en las últimas 3 horas."),
    "pluja_24h": ("Mucha lluvia prevista: {v} mm en 24 horas, {q}.", None),
    "ratxa": ("Viento fuerte previsto: rachas de hasta {v} km/h, {q}.", None),
    "calor": ("Calor intenso previsto: hasta {v} °C, {q}.", "Ahora hace calor intenso: {v} °C."),
    "fred": ("Frío intenso previsto: hasta {v} °C, {q}.", "Ahora hace frío intenso: {v} °C."),
    "neu_24h": ("Nieve prevista: {v} cm en las próximas 24 horas.", None),
}


def coma(x):
    return f"{x:.0f}" if x >= 10 else f"{x:.1f}".replace(".", ",")


# --- Textos ------------------------------------------------------------------

# Cada aviso empieza por lo que pasa, en negrita (HTML de Telegram), y lo explica
# en palabras llanas para quien no conoce la web (Juanjo, 07-10-2026).
# Delante, el nivel con un círculo de color, la misma escala que el bot
# (bot/bot.py, CERCLE): se ve la gravedad antes de leer, también en la
# notificación del móvil (Juanjo, 10-10-2026; ADR 0065). El final, en verde.
# Lo que no tiene nivel lleva su propio símbolo, no un círculo: el incendio,
# 🔥 (Juanjo, 11-10-2026: «dejar los círculos para este tipo de niveles»; ADR 0071).
CERCLE = {"groc": "🟡", "taronja": "🟠", "vermell": "🔴", "atencio": "🟠", "perill": "🔴", "incendi": "🔥",
          "alerta": "🟠", "emergència": "🔴", "fi": "🟢", "llum": "🔌", "pluja": "🌧️", "nul": "⚪", "mig": "🟡", "alt": "🟠", "maxim": "🔴"}


def negreta(text, nivell=None):
    cercle = CERCLE.get(nivell)
    return (f"{cercle} " if cercle else "") + f"<b>{html.escape(text, quote=False)}</b>"


def text_pluja(salida, ahora):
    r = salida["radar"]
    falta = round(PA.falta_min(salida, ahora))
    mm = r.get("arriba_mm_h")
    forca = {"ca": "", "es": ""}
    if mm is not None:
        # Les franges de l'AEMET, com el requadre del radar (N.nom_intensitat).
        segura = mm < N.FRANGES_MMH[1]
        forca = {"ca": f" {'Serà' if segura else 'Pot ser'} {N.nom_intensitat(mm, 'ca')}.",
                 "es": f" {'Será' if segura else 'Puede ser'} {N.nom_intensitat(mm, 'es')}."}
    if falta <= 2:
        ca = (negreta("Temps a Montflorit: pluja imminent", "pluja") + "\nEl radar ja veu pluja a sobre del barri: pot "
              "començar en qualsevol moment." + forca["ca"])
        es = (negreta("Temps a Montflorit: lluvia inminente", "pluja") + "\nEl radar ya ve lluvia encima del barrio: puede "
              "empezar en cualquier momento." + forca["es"])
    else:
        hora = H.local(r["arriba"]).strftime("%H:%M")
        ca = negreta(f"Temps a Montflorit: pluja d'aquí a uns {falta} minuts", "pluja") + (
            f"\nSegons el radar, començarà a ploure a Montflorit cap a les {hora}.") + forca["ca"]
        es = negreta(f"Temps a Montflorit: lluvia dentro de unos {falta} minutos", "pluja") + (
            f"\nSegún el radar, empezará a llover en Montflorit hacia las {hora}.") + forca["es"]
    return amb_radar(ca, es, r)


def amb_radar(ca, es, r):
    """El radar en directe, el mateix que ha donat l'avís (Juanjo, 08-10-2026):
    a Telegram, un enllaç a l'última línia; a la notificació, que no admet
    enllaços al text, en tocar-la (bot/push.py llegeix «url» i «push»)."""
    font = "rainviewer" if r.get("imatge") == "rainviewer" else "meteocat"
    url = C.RADAR_EN_DIRECTE[font]
    nom = {"rainviewer": "RainViewer", "meteocat": "Meteocat"}[font]
    enllac = f'<a href="{html.escape(url)}">{nom}</a>'
    return {"ca": f"{ca}\nRadar en directe: {enllac}", "es": f"{es}\nRadar en directo: {enllac}", "url": url,
            "push": {"ca": f"{ca} Toca per veure el radar.", "es": f"{es} Toca para ver el radar."}}


def quan_es(r, ahora):
    ini, fin, ahora = H.local(r["des_de"]), H.local(r["fins"]), H.local(ahora)
    dia = ("hoy" if ini.date() == ahora.date() else
           "mañana" if ini.date() == ahora.date() + dt.timedelta(days=1) else ini.strftime("%d/%m"))
    return f"{dia} de {ini.hour} a {fin.hour} h"


QUE_CA = {"pluja_30min": "pluja intensa", "pluja_3h": "pluja intensa", "pluja_24h": "molta pluja",
          "ratxa": "vent fort", "calor": "calor intensa", "fred": "fred intens", "neu_24h": "neu"}
QUE_ES = {"pluja_30min": "lluvia intensa", "pluja_3h": "lluvia intensa", "pluja_24h": "mucha lluvia",
          "ratxa": "viento fuerte", "calor": "calor intenso", "fred": "frío intenso", "neu_24h": "nieve"}


def linia_risc_es(r, ahora):
    """El text d'un risc en castellà (el català ja ve fet a les dades)."""
    previst, mesura = RISCOS_ES[r["tipus"]]
    plantilla = previst if r["origen"] == "previsio" else mesura
    if not plantilla:
        return r["text"]
    text = plantilla.format(v=RS.num(r["valor"], r["tipus"]), q=quan_es(r, ahora) if r.get("des_de") else "")
    return text[:-1] + f" (probabilidad hasta el {r['prob']} %)." if r.get("prob") else text


CANVI = {"ca": ("Ha pujat", "Ha baixat", "des de l'avís de les {h}, que deia {v} {u}."),
         "es": ("Ha subido", "Ha bajado", "desde el aviso de las {h}, que decía {v} {u}.")}


def linia_canvi(r, avisat, idioma):
    """En la ficha abierta, si la cifra ya no es la del aviso enviado, que lo
    diga: el aviso de las 13:09 decía 77 km/h y la ficha, que enlaza, 89, sin
    explicarlo (revisor, 20-10-2026). No se manda otro mensaje: solo una subida
    de nivel lo merece (ADR 0092)."""
    a = (avisat or {}).get(r["clau"])
    if not a or RS.num(a["valor"], r["tipus"]) == RS.num(r["valor"], r["tipus"]):
        return []
    puja, baixa, resta = CANVI[idioma]
    h = H.local(a["hora"]).strftime("%H:%M")
    return [f"{puja if r['valor'] > a['valor'] else baixa} " +
            resta.format(h=h, v=RS.num(a["valor"], r["tipus"]), u=RS.UNITATS[r["tipus"]])]


def text_perill(nous, ahora, avisat=None):
    pitjor = max(nous, key=lambda r: RS.NIVELLS.index(r["nivell"]))["nivell"]
    tipus = list(dict.fromkeys(r["tipus"] for r in nous))
    # Qui avisa, primer (Juanjo, 17-10-2026: un avís de Meteocat es va llegir com
    # si fos de l'aplicació); el nivell ja el diu el cercle.
    ca = [negreta("Temps a Montflorit: avís de perill per " + " i ".join(dict.fromkeys(QUE_CA[t] for t in tipus))
                  + " al barri", pitjor)]
    # Cada risc, amb d'on surt i quant s'hi pot confiar (riscos.font): abans,
    # «Calculat per aquesta aplicació» d'unes ratxes que només preveia AROME
    # (Juanjo, 19-10-2026).
    font = lambda r, l: [html.escape(r["font"][l], quote=False)] if r.get("font") else []  # noqa: E731
    for r in nous:
        ca += [html.escape(r["text"], quote=False)] + linia_canvi(r, avisat, "ca") + font(r, "ca")
    ca.append("Avís no oficial.")
    es = [negreta("Temps a Montflorit: aviso de peligro por " + " y ".join(dict.fromkeys(QUE_ES[t] for t in tipus))
                  + " en el barrio", pitjor)]
    for r in nous:
        es += [html.escape(linia_risc_es(r, ahora), quote=False)] + linia_canvi(r, avisat, "es") + font(r, "es")
    es.append("Aviso no oficial.")
    return {"ca": "\n".join(ca), "es": "\n".join(es)}, pitjor


OFICIALS = {"ca": {"meteocat": "Meteocat", "aemet": "l'AEMET", "pc": "Protecció Civil"},
            "es": {"meteocat": "Meteocat", "aemet": "la AEMET", "pc": "Protección Civil"}}


def oficials_actius(salida, ahora):
    """Quins organismes tenen ara un avís de perill per al barri, per no dir
    «cap situació de perill» mentre n'hi ha d'oficials (revisor, 19-10-2026)."""
    res = []
    if SMP.pendents(((salida.get("smp") or {}).get("avisos")) or [], ahora):
        res.append("meteocat")
    if any(a.get("zona", C.ZONA_AVISOS) == C.ZONA_AVISOS and a.get("nivel") in RS.NIVELLS and not a.get("cobert")
           and H.llegeix(a["fin"]) > ahora for a in salida.get("avisos") or []):
        res.append("aemet")
    if any(p.get("fase") in ("alerta", "emergència") for p in salida.get("plans") or []):
        res.append("pc")
    return res


def i_llista(noms, idioma):
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + (" i " if idioma == "ca" else " y ") + noms[-1]


def text_perill_fi(tipus, des_de, oficials=()):
    """S'acaba l'avís propi: què ha passat, des de quan, i si continuen els
    oficials. Deia «ja no hi ha cap situació de perill al barri» amb INUNCAT,
    Meteocat i AEMET oberts, i «Fa 3 hores» quan la fitxa encara deia «avui de
    17 a 18 h» (revisor, 19-10-2026): les 3 hores es comptaven des que la
    previsió el va deixar de veure (15:21), no des del final de la franja."""
    que_ca = " i ".join(dict.fromkeys(QUE_CA[t] for t in tipus)) or "cap perill"
    que_es = " y ".join(dict.fromkeys(QUE_ES[t] for t in tipus)) or "ningún peligro"
    h = H.local(des_de).strftime("%H:%M")
    ca = (negreta(f"Temps a Montflorit: s'acaba l'avís per {que_ca} al barri", "fi") +
          f"\nNo se'n mesura ni se'n preveu des de les {h}. Si hi torna, hi haurà un avís nou.")
    es = (negreta(f"Temps a Montflorit: termina el aviso por {que_es} en el barrio", "fi") +
          f"\nNo se mide ni se prevé desde las {h}. Si vuelve, habrá un aviso nuevo.")
    if oficials:
        ca += f"\nContinuen els avisos oficials de {i_llista([OFICIALS['ca'][o] for o in oficials], 'ca')}."
        es += f"\nSiguen los avisos oficiales de {i_llista([OFICIALS['es'][o] for o in oficials], 'es')}."
    return {"ca": ca, "es": es}


def text_riera(riera, nivell):
    """Primer què cal fer; després, la pluja de Sant Cugat i si el radar en veu
    venir més (ADR 0076). El detall, a la fitxa i a «Com funciona»."""
    # La pluja de la font que ha decidit: Meteocat o, si dona més, la mediana de
    # les estacions particulars de Sant Cugat, i es diu (ADR 0027, 18-10-2026).
    v = riera.get("veines") if riera.get("font") == "veines" else None
    hora = H.local((v or riera)["fins"]).strftime("%H:%M")
    mm3 = coma((v or riera)["mm_3h"])
    qui_ca = f"segons {v['n']} estacions particulars, a les {hora}" if v else f"a les {hora}"
    qui_es = f"según {v['n']} estaciones particulares, a las {hora}" if v else f"a las {hora}"
    radar = riera.get("radar_1h")
    mes_ca = " i el radar en veu venir més" if radar and radar >= 1 else ""
    mes_es = " y el radar ve venir más" if radar and radar >= 1 else ""
    if nivell == "perill":
        ca = (negreta("Temps a Montflorit: perill de desbordament de la riera de Sant Cugat", nivell) +
              f"\nNo t'acostis a la riera.\n{mm3} mm en 3 hores a Sant Cugat ({qui_ca}){mes_ca}: "
              "amb aquesta pluja ja s'ha desbordat altres vegades.")
        es = (negreta("Temps a Montflorit: peligro de desbordamiento de la riera de Sant Cugat", nivell) +
              f"\nNo te acerques a la riera.\n{mm3} mm en 3 horas en Sant Cugat ({qui_es}){mes_es}: "
              "con esta lluvia ya se ha desbordado otras veces.")
    else:
        ca = (negreta("Temps a Montflorit: possible desbordament de la riera de Sant Cugat", nivell) +
              f"\nNo t'acostis a la riera.\n{mm3} mm en 3 hores a Sant Cugat ({qui_ca}){mes_ca}: "
              "si continua plovent fort, es pot desbordar.")
        es = (negreta("Temps a Montflorit: posible desbordamiento de la riera de Sant Cugat", nivell) +
              f"\nNo te acerques a la riera.\n{mm3} mm en 3 horas en Sant Cugat ({qui_es}){mes_es}: "
              "si sigue lloviendo fuerte, se puede desbordar.")
    if riera.get("incomplet"):
        ca += " A l'estació li falten mesures: pot haver plogut més."
        es += " A la estación le faltan medidas: puede haber llovido más."
    return {"ca": f"{ca}\n{ORIENTATIU['ca']}", "es": f"{es}\n{ORIENTATIU['es']}"}


def text_riera_fi(riera, episodi):
    """Final d'un episodi amb avís (Juanjo, 08-10-2026): un sol missatge, i
    només després de RIERA_FI_H hores per sota del registre. Curt (ADR 0076)."""
    h = C.RIERA_FI_H
    perill = bool(episodi["avisos"].get("perill"))
    ca = (negreta("Temps a Montflorit: " + ("ha passat el perill de desbordament" if perill else "ja no hi ha risc de desbordament")
                  + " de la riera de Sant Cugat", "fi")
          + f"\nFa {h} hores que no plou fort a Sant Cugat. Si hi torna, tornarà l'avís.")
    es = (negreta("Temps a Montflorit: " + ("ha pasado el peligro de desbordamiento" if perill else "ya no hay riesgo de desbordamiento")
                  + " de la riera de Sant Cugat", "fi")
          + f"\nLleva {h} horas sin llover fuerte en Sant Cugat. Si vuelve, volverá el aviso.")
    return {"ca": ca, "es": es}


# --- Incendios cerca (ADR 0046) ---------------------------------------------------
# Van con los de peligro («Situacions de perill»): son datos oficiales de
# Bombers, y se dice de dónde salen.

def hhmm(iso):
    return H.local(iso).strftime("%H:%M") if iso else "?"


def lloc_incendi(i, idioma):
    """Dónde es, para quien no conoce la web (ADR 0066 y 0071): dentro del
    parque de Collserola o el municipio, y siempre a qué distancia de
    Montflorit (Juanjo, 11-10-2026: «tiene que poner la distancia a
    Montflorit, siempre»)."""
    m = i.get("municipi") or "?"
    ca = idioma == "ca"
    if i.get("collserola"):
        on = f"dins del Parc de Collserola ({m})" if ca else f"dentro del Parque de Collserola ({m})"
    else:
        on = f"a {m}" if ca else f"en {m}"
    if i.get("km") is not None:
        on += f", a {coma(i['km'])} km de Montflorit"
    return on


def enllac_bombers(idioma):
    text = "Mapa d'actuacions de Bombers" if idioma == "ca" else "Mapa de actuaciones de Bombers"
    return f'<a href="{BOMBERS[idioma]}">{text}</a>'


def text_incendi(i, acabat=False, parat=None):
    """La distancia va en el título, que es lo que se ve en la notificación y
    en la ficha plegada de «Perill»; el texto ya no la repite. «parat», la hora
    del último cambio de uno que Bombers deja abierto sin vehículos."""
    lloc = i.get("municipi") or "?"
    parc_ca = ", dins del Parc Natural de Collserola" if i.get("collserola") else ""
    parc_es = ", dentro del Parque Natural de Collserola" if i.get("collserola") else ""
    if acabat:
        dist = f", a {coma(i['km'])} km de Montflorit" if i.get("km") is not None else ""
        on_ca = (f"al Parc de Collserola ({lloc})" if i.get("collserola") else f"a {lloc}") + dist
        on_es = (f"en el Parque de Collserola ({lloc})" if i.get("collserola") else f"en {lloc}") + dist
        if parat:
            return {"ca": negreta(f"Bombers: incendi {on_ca}: probablement ja s'ha apagat", "fi")
                          + "\nBombers de la Generalitat el mantenen obert, però sense cap vehicle i sense cap "
                          f"actualització des de les {hhmm(parat)}.",
                    "es": negreta(f"Bombers: incendio {on_es}: probablemente ya se ha apagado", "fi")
                          + "\nBombers de la Generalitat lo mantienen abierto, pero sin ningún vehículo y sin ninguna "
                          f"actualización desde las {hhmm(parat)}."}
        return {"ca": negreta(f"Bombers: incendi {on_ca}: ja no consta com a actiu", "fi")
                      + "\nBombers de la Generalitat ja no el tenen entre les actuacions en curs.",
                "es": negreta(f"Bombers: incendio {on_es}: ya no consta como activo", "fi")
                      + "\nBombers de la Generalitat ya no lo tienen entre las actuaciones en curso."}
    return {"ca": negreta(f"Bombers: incendi forestal {lloc_incendi(i, 'ca')}", "incendi")
                  + f"\nBombers de la Generalitat treballen en un incendi de vegetació forestal a {lloc}{parc_ca}, "
                  f"des de les {hhmm(i.get('inici'))}. Segueix les indicacions de Bombers i de Protecció Civil."
                  + "\n" + enllac_bombers("ca"),
            "es": negreta(f"Bombers: incendio forestal {lloc_incendi(i, 'es')}", "incendi")
                  + f"\nBombers de la Generalitat trabajan en un incendio de vegetación forestal en {lloc}{parc_es}, "
                  f"desde las {hhmm(i.get('inici'))}. Sigue las indicaciones de Bombers y de Protección Civil."
                  + "\n" + enllac_bombers("es")}


# --- Cortes de luz (ADR 0072) ----------------------------------------------------

def on_llum(t, idioma):
    """«Carrer de Sant Jeroni o Carrer de Casanovas (carrers probables)», o
    «al barri» si no hay calle cerca."""
    es = idioma == "es"
    c = t.get("carrers") or []
    if not c:
        return "en el barrio" if es else "al barri"
    cap = (("calle probable" if es else "carrer probable") if len(c) == 1
           else ("calles probables" if es else "carrers probables"))
    return f"{' o '.join(c)} ({cap})"


def text_llum(t, ahora, acabat=False):
    nota = {"ca": "Els carrers són una estimació a partir del punt aproximat del mapa: e-distribució no diu quins "
                  "carrers queden sense llum.",
            "es": "Las calles son una estimación a partir del punto aproximado del mapa: e-distribución no dice qué "
                  "calles se quedan sin luz."}
    if acabat:
        return {"ca": negreta(f"e-distribució: tall de llum a Montflorit, {on_llum(t, 'ca')}: ja no consta", "fi")
                      + "\ne-distribució ja no el té entre els talls en curs.",
                "es": negreta(f"e-distribución: corte de luz en Montflorit, {on_llum(t, 'es')}: ya no consta", "fi")
                      + "\ne-distribución ya no lo tiene entre los cortes en curso."}
    n = t.get("clients")
    res = {}
    for idioma in ("ca", "es"):
        es = idioma == "es"
        que = (("Trabajos programados" if es else "Treballs programats") if t.get("programat")
               else ("Avería" if es else "Avaria"))
        qui = "" if n is None else (f": {n} clientes sin luz" if es else f": {n} clients sense llum") if n != 1 \
            else (": 1 cliente sin luz" if es else ": 1 client sense llum")
        quan = ""
        if t.get("fins"):
            h = H.local(t["fins"]).strftime("%H:%M")
            quan = f"; previsto hasta las {h}" if es else f"; previst fins a les {h}"
        mapa = ("Mapa de e-distribución" if es else "Mapa d'e-distribució")
        res[idioma] = (negreta(f"e-distribución: corte de luz en Montflorit, {on_llum(t, idioma)}", "llum")
                       + f"\n{que} de e-distribución{qui}{quan}." if es else
                       negreta(f"e-distribució: tall de llum a Montflorit, {on_llum(t, idioma)}", "llum")
                       + f"\n{que} d'e-distribució{qui}{quan}.")
        res[idioma] += f"\n<i>{nota[idioma]}</i>\n" + f'<a href="{html.escape(MAPA_LLUM.format(idioma))}">{mapa}</a>'
    return res


# --- Avisos oficiales nuevos (ADR 0055) -------------------------------------------
# Van con los de peligro: llegan al canal y a quien tiene «Situacions de perill».

FASES_PLA = ("prealerta", "alerta", "emergència")
DIES = {"ca": ("dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"),
        "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")}
# Els tipus de l'AEMET (prevision.TIPUS_METEOALARM), en cada idioma.
TIPUS_AEMET = {"ca": {"pluja": "pluja", "tempestes": "tempestes", "inundacions": "inundacions", "vent": "vent",
                      "calor": "calor", "fred": "fred", "neu": "neu", "boira": "boira", "incendis": "risc d'incendis",
                      "costaners": "fenòmens costaners", "allaus": "allaus", "pols": "pols", "altres": "altres fenòmens"},
               "es": {"pluja": "lluvia", "tempestes": "tormentas", "inundacions": "inundaciones", "vent": "viento",
                      "calor": "calor", "fred": "frío", "neu": "nieve", "boira": "niebla", "incendis": "riesgo de incendios",
                      "costaners": "fenómenos costeros", "allaus": "aludes", "pols": "polvo", "altres": "otros fenómenos"}}
NOM_PLA_ES = {"d'inundacions": "de inundaciones", "de vent": "de viento", "de neu": "de nieve",
              "per onada de calor": "por ola de calor", "per onada de fred": "por ola de frío",
              "per contaminació": "por contaminación", "per vent": "por viento"}
SENTIT_FASE = {
    "ca": {"alerta": "El pla està activat: es preveu un risc important a curt termini, o hi ha afectacions que no són greus.",
           "emergència": "El pla està activat per un risc greu per a la població: segueix les indicacions de Protecció Civil."},
    "es": {"alerta": "El plan está activado: se prevé un riesgo importante a corto plazo, o hay afectaciones que no son graves.",
           "emergència": "El plan está activado por un riesgo grave para la población: sigue las indicaciones de Protección Civil."}}


def moment(iso, ahora):
    """(dia, hora) d'un instant; les 23:59:59 compten com la mitjanit següent."""
    # En hora de Madrid (ZoneInfo, ADR 0128): amb el desfasament d'ara, un text
    # escrit abans del canvi d'hora sobre una hora de després anava una hora
    # desplaçat.
    t = H.utc(iso)
    if t.second == 59:
        t += dt.timedelta(seconds=1)
    t = H.local(t)
    return t, (t.date() - H.dia_local(ahora)).days


def nom_dia(t, idioma):
    """«dilluns 19»: el dia de la setmana i del mes, no «avui» ni «demà». El text
    es queda a la fitxa de «Perill» i es rellegeix altres dies: el 18-10-2026
    hi deia «Des de demà…» d'avisos del 16 i del 17 (revisor, ADR 0101)."""
    return f"{DIES[idioma][t.weekday()]} {t.day}"


def franja(inici, fi, ahora, idioma):
    """«Des del dissabte 17 a les 15 h fins a mitjanit.», «Desde el lunes 19 a
    las 6 h hasta el martes 20 a las 3 h.», «Dilluns 19, de les 0 h a les 4 h.»"""
    es = idioma == "es"
    t0, d0 = moment(inici, ahora)
    t1, d1 = moment(fi, ahora)
    dia0 = nom_dia(t0, idioma)
    if d1 == d0:                                     # el mateix dia
        return (f"{dia0.capitalize()}, de las {t0.hour} h a las {t1.hour} h." if es
                else f"{dia0.capitalize()}, de les {t0.hour} h a les {t1.hour} h.")
    if t1.hour == 0 and t1.minute == 0 and d1 == d0 + 1:
        fins = "hasta medianoche" if es else "fins a mitjanit"
    else:
        fins = (f"hasta el {nom_dia(t1, idioma)} a las {t1.hour} h" if es
                else f"fins al {nom_dia(t1, idioma)} a les {t1.hour} h")
    if es:
        return f"Desde el {dia0} a las {t0.hour} h {fins}."
    return f"Des del {dia0} a les {t0.hour} h {fins}."


def text_aemet(a, ahora):
    """Un aviso de AEMET: nivel, de qué, de cuándo a cuándo y su texto (en
    castellano, como lo publica AEMET: ADR 0033)."""
    nivell = a["nivel"]
    desc = f"\n«{html.escape(a['descripcio'], quote=False)}»" if a.get("descripcio") else ""
    ca = (negreta(f"AEMET: avís {nivell} per {TIPUS_AEMET['ca'].get(a['tipo'], a['tipo'])} al Vallès", nivell)
          + "\n" + franja(a["inicio"], a["fin"], ahora, "ca") + desc
          + "\nÉs un avís oficial: segueix les indicacions de Protecció Civil.")
    es = (negreta(f"AEMET: aviso {NIVELLS_ES.get(nivell, nivell)} por {TIPUS_AEMET['es'].get(a['tipo'], a['tipo'])} "
                  f"en el Vallès", nivell)
          + "\n" + franja(a["inicio"], a["fin"], ahora, "es") + desc
          + "\nEs un aviso oficial: sigue las indicaciones de Protección Civil.")
    return {"ca": ca, "es": es}


# --- Meteocat avisa; AEMET, de reserva (ADR 0092) -----------------------------
# Meteocat es el servicio de aquí: avisa por comarca y es la referencia de
# Protecció Civil de Catalunya. Sus avisos se agrupan por fenómeno (la lluvia
# en 30 minutos y en 3 horas son la misma lluvia) y se notifica el primero,
# una subida de nivel, un fenómeno nuevo, unas horas que el aviso no cubría y
# el final, cuando ya no queda ninguno. Una nueva emisión sin cambios, una
# bajada o un aviso menor del mismo fenómeno no avisan: se ven en «Perill»
# (Juanjo, 16-10-2026: «lo que no quiero son avisos repetidos que molesten a
# la gente» y «en situación de peligro no podemos dar un aviso al día»).

RANG_SMP = {"mig": 1, "alt": 2, "maxim": 3}


def fenomen(a):
    """El fenómeno de un aviso de Meteocat; los de observación van aparte: dicen
    que ya está pasando, y eso es una novedad aunque el nivel no suba."""
    f = SMP.fenomen(a["meteor"])
    return f if a.get("tipus", "previsio") == "previsio" else f"obs:{f}"


def nom_fenomen(f, idioma):
    f = f.removeprefix("obs:")
    return SMP.NOM_FENOMEN[idioma].get(f, f)


hores_smp = SMP.hores_avis


def fins_smp(avisos):
    """Hasta cuándo valen: el final de la última franja, en hora local."""
    def fi(a):
        dia = max(a["dies"])
        return H.de_rellotge(dia, a["dies"][dia][-1][1])
    return H.clau(max(fi(a) for a in avisos))


def linia_smp(a, idioma):
    """«🟠 «Intensitat de pluja en 30 minuts»: perill alt, dissabte 17 de 12 a 24 h
    (Intensitat > 20 mm / 30 minuts).» El meteoro y el umbral, como los publica
    Meteocat (ADR 0067)."""
    n = SMP.nivell(a["perill"])
    obs = a.get("tipus", "previsio") != "previsio"
    # Primer què és i després el nom oficial, entre cometes: «Intensitat de
    # pluja en 30 minuts» al començament es llegia com «plourà d'aquí a 30
    # minuts» (Juanjo, 17-10-2026).
    if idioma == "es":
        tipus = "Observado ahora, peligro" if obs else "Peligro"
        per = "por"
    else:
        tipus = "Observat ara, perill" if obs else "Perill"
        per = "per"
    llindar = f" ({a['llindar']})" if a.get("llindar") else ""
    return f"{CERCLE.get(n, '')} {tipus} {SMP.GRAU[idioma][n]} {per} «{a['meteor']}»: {SMP.quan(a['dies'], idioma)}{llindar}."


def text_meteocat(canvi, f, avisos):
    """El aviso de Meteocat para la comarca: en la primera línea, qué pasa (el
    primero, «Actualització: …» si ya se había avisado); debajo, todos los
    avisos vigentes, para que la ficha de «Perill» los tenga todos."""
    nom = C.SMP_COMARCA_NOM
    n = SMP.nivell(max(a["perill"] for a in avisos if fenomen(a) == f))
    fca, fes = nom_fenomen(f, "ca"), nom_fenomen(f, "es")
    gca, ges = SMP.GRAU["ca"][n], SMP.GRAU["es"][n]
    if f.startswith("obs:"):
        ca = f"Meteocat: s'observa perill {gca} per {fca} al {nom}"
        es = f"Meteocat: se observa peligro {ges} por {fes} en el {nom}"
    elif canvi in ("nou", "vigent"):
        ca = f"Meteocat: avís de perill {gca} per {fca} al {nom}"
        es = f"Meteocat: aviso de peligro {ges} por {fes} en el {nom}"
    elif canvi == "puja":
        ca = f"Meteocat: actualització, puja a perill {gca} per {fca} al {nom}"
        es = f"Meteocat: actualización, sube a peligro {ges} por {fes} en el {nom}"
    elif canvi == "fenomen":
        ca = f"Meteocat: actualització, avisa també de perill {gca} per {fca} al {nom}"
        es = f"Meteocat: actualización, avisa también de peligro {ges} por {fes} en el {nom}"
    else:
        ca = f"Meteocat: actualització, amplia l'avís de perill {gca} per {fca} al {nom}"
        es = f"Meteocat: actualización, amplía el aviso de peligro {ges} por {fes} en el {nom}"
    ordre = sorted(avisos, key=lambda a: (fenomen(a) != f, -a["perill"]))
    return {"ca": negreta(ca, n) + "".join("\n" + linia_smp(a, "ca") for a in ordre)
                  + "\nÉs un avís oficial: segueix les indicacions de Protecció Civil.",
            "es": negreta(es, n) + "".join("\n" + linia_smp(a, "es") for a in ordre)
                  + "\nEs un aviso oficial: sigue las indicaciones de Protección Civil."}


def comenca_smp(avisos):
    """Quan comença el primer dels que queden, en hora local."""
    # Hores de rellotge: fins a la 3.200.0 se sumaven a la mitjanit amb el
    # desfasament d'ara, i el dia del canvi d'hora l'inici sortia una hora abans
    # o després (inventari del 25-10-2026, ADR 0128).
    def ini(a):
        dia = min(a["dies"])
        return H.de_rellotge(dia, a["dies"][dia][0][0])
    return H.clau(min(ini(a) for a in avisos)) if avisos else None


def principal_smp(avisos):
    """El fenomen del títol de la fitxa quan no hi ha res de nou: el que
    s'observa ara, si n'hi ha cap; si no, el de més perill."""
    return fenomen(max(avisos, key=lambda a: (a.get("tipus", "previsio") != "previsio", a["perill"])))


def text_meteocat_fi():
    nom = C.SMP_COMARCA_NOM
    return {"ca": negreta(f"Meteocat: ja no hi ha cap avís de perill per al {nom}", "fi"),
            "es": negreta(f"Meteocat: ya no hay ningún aviso de peligro para el {nom}", "fi")}


PRIORITAT = ("nou", "obs", "puja", "fenomen", "amplia")


def decideix_smp(abans, avisos, ahora):
    """Compara los avisos de Meteocat de esta pasada con lo ya avisado.
    abans: {"episodi", "fenomens": {f: {"rang", "hores", "vist"}}} o None.
    Devuelve (estado nuevo, [(canvi, fenomen)], acabat). Un fenómeno que deja
    de constar se da por acabado a los SMP_FI_MIN minutos, para que el relevo
    entre dos emisiones no avise dos veces."""
    hora = H.clau(ahora)
    e = {"episodi": (abans or {}).get("episodi"), "fenomens": dict((abans or {}).get("fenomens") or {})}
    nou_episodi = not e["fenomens"]
    canvis = []
    per_f = {}
    for a in avisos:
        per_f.setdefault(fenomen(a), []).append(a)
    for f, llista in per_f.items():
        rang_ara = max(RANG_SMP[SMP.nivell(a["perill"])] for a in llista)
        hores = set().union(*(hores_smp(a) for a in llista))
        vell = e["fenomens"].get(f)
        if vell is None:
            canvi = "nou" if nou_episodi else "obs" if f.startswith("obs:") else "fenomen"
            canvis.append((canvi, f))
            vell = {"rang": rang_ara, "hores": []}
        elif rang_ara > vell["rang"]:
            canvis.append(("puja", f))
        elif not hores <= set(vell["hores"]):
            canvis.append(("amplia", f))
        e["fenomens"][f] = {"rang": max(rang_ara, vell["rang"]), "hores": sorted(hores | set(vell["hores"])),
                            "vist": hora}
    for f, v in list(e["fenomens"].items()):
        if f not in per_f and ahora - H.llegeix(v["vist"]) >= dt.timedelta(minutes=C.SMP_FI_MIN):
            del e["fenomens"][f]
    acabat = bool(abans and abans.get("fenomens")) and not e["fenomens"]
    if nou_episodi and canvis:
        e["episodi"] = f"meteocat:{hora}"
    canvis.sort(key=lambda c: PRIORITAT.index(c[0]))
    return e, canvis, acabat


def text_pla(p, acabat=False):
    """L'avís d'un pla de Protecció Civil, sense els de Meteocat, que són d'un
    altre organisme i tenen el seu (Juanjo, 17-10-2026: «separalos de
    proteccion civil porque son avisos aparte»)."""
    nom_ca, nom_es = p["nom"], NOM_PLA_ES.get(p["nom"], p["nom"])
    if acabat:
        return {"ca": negreta(f"Protecció Civil: el pla {nom_ca} ({p['pla']}) ja no està en alerta", "fi")
                      + "\nJa no consta en alerta ni en emergència.",
                "es": negreta(f"Protección Civil: el plan {nom_es} ({p['pla']}) ya no está en alerta", "fi")
                      + "\nYa no consta en alerta ni en emergencia."}
    de = "d'" if p["fase"][:1] in "aeiouàèéíòóú" else "de "
    fase_es = {"emergència": "emergencia"}.get(p["fase"], p["fase"])
    enllac_ca = f"\n<a href=\"{html.escape(p['comunicat'])}\">Comunicat (PDF)</a>" if p.get("comunicat") else ""
    enllac_es = enllac_ca.replace("Comunicat (PDF)", "Comunicado (PDF)")
    return {"ca": negreta(f"Protecció Civil: pla {nom_ca} ({p['pla']}) en fase {de}{p['fase']}", p["fase"])
                  + "\n" + SENTIT_FASE["ca"][p["fase"]] + enllac_ca,
            "es": negreta(f"Protección Civil: plan {nom_es} ({p['pla']}) en fase de {fase_es}", p["fase"])
                  + "\n" + SENTIT_FASE["es"][p["fase"]] + enllac_es}


def text_comunicat(p):
    """Un comunicado nuevo de Protección Civil para un plan que ya estaba en
    alerta o emergencia (Juanjo, 15-10-2026: «cuando cambie»; ADR 0091). Breve,
    porque el plan ya se avisó: «yo hablaría de actualización, texto breve»."""
    nom_ca, nom_es = p["nom"], NOM_PLA_ES.get(p["nom"], p["nom"])
    url = html.escape(p["comunicat"])
    ca = negreta(f"Protecció Civil: actualització del pla {nom_ca} ({p['pla']})", p["fase"])
    es = negreta(f"Protección Civil: actualización del plan {nom_es} ({p['pla']})", p["fase"])
    # La notificació de l'app i de la web no admet enllaços al text: en tocar-la
    # obre el comunicat, com el radar a l'avís de pluja (bot/push.py).
    return {"ca": f"{ca}\n<a href=\"{url}\">Comunicat (PDF)</a>",
            "es": f"{es}\n<a href=\"{url}\">Comunicado (PDF)</a>",
            "url": p["comunicat"],
            "push": {"ca": f"{ca}\nToca per veure el comunicat.", "es": f"{es}\nToca para ver el comunicado."}}


# --- Decidir -----------------------------------------------------------------

def aemet_per_clau(avisos):
    """Un aviso de AEMET por clave (tipo:inicio). AEMET puede publicar dos del
    mismo tipo que empiezan a la vez (19-10-2026: lluvia de 40 mm en 1 h hasta
    las 23:59, que cubría Meteocat, y de 80 mm en 12 h hasta las 8:59, visible
    de 6 a 9): ganaba el último de la lista, cuyo orden cambia de una pasada a
    otra, y la ficha del de 80 mm se cerró como «Substituït per l'avís de
    Meteocat» (revisor, ADR 0101). Se queda el que Meteocat no cubre, luego el
    de más nivel y luego el que acaba más tarde."""
    res = {}
    pes = lambda a: (not a.get("cobert"), RS.NIVELLS.index(a["nivel"]), a["fin"])  # noqa: E731
    for a in avisos:
        k = f"{a['tipo']}:{a['inicio']}"
        if k not in res or pes(a) > pes(res[k]):
            res[k] = a
    return res


def decideix(estat, salida, ahora):
    """Pone al día el estado y devuelve los avisos nuevos:
    [{id, tipus, nivell, ca, es, hora}]."""
    nous = []
    hora = H.clau(ahora)

    def afegeix(tipus, clau, text, nivell=None, episodi=None, enllac=None, fins=None, nomes_avis=False, comenca=None):
        # episodi: de qué suceso es parte, para el historial (ADR 0071); enllac,
        # más información si el texto no la enlaza; fins, cuándo acaba un
        # aviso que no tiene mensaje de final (los de AEMET); nomes_avis, que
        # lleva a la ficha del episodio sin cambiarla (el comunicado nuevo).
        # comenca: quan comença el que s'avisa, si és més tard (ADR 0101): la
        # fitxa diu «Previst» i no «Actiu ara» mentre no ha començat.
        extra = {k: v for k, v in (("episodi", episodi), ("enllac", enllac), ("fins", fins),
                                   ("nomes_avis", nomes_avis), ("comenca", comenca)) if v}
        nous.append({"id": f"{tipus}:{clau}", "tipus": tipus, "nivell": nivell, "hora": hora, **text, **extra})

    # Lluvia en unos minutos: la lógica del aviso de Juanjo, con estado propio.
    try:
        avis, _ = PA.compara(estat.setdefault("pluja", {"episodi": None}), salida, ahora)
        if avis:
            afegeix("pluja", estat["pluja"]["episodi"]["inici"], text_pluja(salida, ahora))
    except Exception:
        pass
    # Peligro: al aparecer o subir de nivel.
    actius = estat.setdefault("perill", {})
    nous_perill = []
    for r in salida.get("riscos") or []:
        abans = actius.get(r["clau"])
        if not abans or RS.NIVELLS.index(r["nivell"]) > RS.NIVELLS.index(abans["nivell"]):
            nous_perill.append(r)
            actius[r["clau"]] = {"nivell": r["nivell"]}
        actius[r["clau"]]["vist"] = hora
    # Sin previsión o sin estación no se ha podido mirar: el riesgo no caduca,
    # para no repetirlo al canal cuando vuelvan los datos.
    # Fins a la 3.136.0 mirava «ara», que casa.py no escriu (és «ara_casa»): no
    # se'n tancava cap i el final no s'avisava mai (inventari del 18-10-2026).
    sense = not salida.get("hores") or not salida.get("ara_casa")
    acabats = []
    for clau, a in list(actius.items()):
        vist = ahora - H.llegeix(a["vist"])
        if not sense and vist >= dt.timedelta(hours=C.RISC_FI_H):
            # Els que fa dies que no es veuen (els que s'havien quedat oberts
            # per aquest error) es tanquen sense avisar: el final arribaria tard.
            if vist < dt.timedelta(hours=C.RISC_FI_H + 1):
                acabats.append((clau, a["vist"]))
            del actius[clau]
    # El que hi ha ara, per tenir al dia la fitxa oberta de «Perill» (historial).
    riscos_ara = salida.get("riscos") or []
    if nous_perill:
        # Les xifres de l'últim avís enviat, per dir a la fitxa si han canviat.
        estat["perill_avisat"] = {**(estat.get("perill_avisat") or {}),
                                  **{r["clau"]: {"valor": r["valor"], "hora": hora} for r in riscos_ara}}
    estat["perill_text"] = text_perill(riscos_ara, ahora, estat.get("perill_avisat"))[0] if riscos_ara else None
    # Amb dades i cap risc: la fitxa oberta espera RISC_FI_H hores a tancar-se,
    # però ja no és activa (historial, «en_pausa»).
    estat["perill_buit"] = not riscos_ara and not sense
    if nous_perill:
        estat["perill_tipus"] = list(dict.fromkeys((estat.get("perill_tipus") or []) + [r["tipus"] for r in nous_perill]))
        text, pitjor = text_perill(nous_perill, ahora)
        afegeix("perill", hora + ":" + ",".join(r["clau"] for r in nous_perill), text, pitjor,
                episodi="propi", enllac=ENLLAC_PROPI)
    elif acabats and not actius:
        # Quan ja no en queda cap, es diu (abans, només a Juanjo).
        tipus = estat.pop("perill_tipus", None) or [c.split(":", 1)[1] for c, _ in acabats]
        afegeix("perill", hora + ":fi", text_perill_fi(tipus, max((v for _, v in acabats), key=H.utc), oficials_actius(salida, ahora)),
                "fi", episodi="propi")
    if not actius:
        estat.pop("perill_tipus", None)
        estat.pop("perill_avisat", None)
    # Incendios forestales cerca (ADR 0046). La primera vez solo se apunta lo
    # que hay: lo que ya estaba no es una novedad.
    entorn = salida.get("entorn") or {}
    e = estat.get("entorn")
    # Uno que sigue en curso pero sale de la zona (porque cambia la zona o la
    # posición que da Bombers) no ha acabado: no se dice «ja no consta», se
    # aparta (fora) y su ficha de «Perill» lo explica; si vuelve, no es nuevo.
    # El 16-10-2026, al bajar a 2 km, uno de Cerdanyola a 2,6 km se anunció
    # como acabado sin estarlo (ADR 0071).
    if entorn.get("incendis") is not None:
        ara_ids = {i["id"]: i for i in entorn["incendis"]}
        fora = set(entorn.get("incendis_fora") or [])
        parats = entorn.get("incendis_parats") or {}
        apartats = set((e or {}).get("fora") or [])
        abans = dict((e or {}).get("incendis") or {})
        # Una fila repetida de Bombers es el mismo incendio con otro
        # identificador: ni es nuevo ni, al apartarla, se ha acabado
        # (28-10-2026, ADR 0071).
        duplicats = {**((e or {}).get("duplicats") or {}), **(entorn.get("incendis_duplicats") or {})}
        if e is not None:
            for i in entorn["incendis"]:
                coneguts = {i["id"]} | {d for d, q in duplicats.items() if q == i["id"]}
                if not coneguts & (set(e["incendis"]) | apartats):
                    afegeix("perill", f"incendi:{i['id']}", text_incendi(i), "incendi", episodi=f"incendi:{i['id']}")
            for iid, i in e["incendis"].items():
                if iid not in ara_ids and iid not in fora and iid not in duplicats:
                    afegeix("perill", f"incendi:{iid}:fi", text_incendi(i, acabat=True, parat=parats.get(iid)), "fi",
                            episodi=f"incendi:{iid}")
        estat.setdefault("entorn", {"incendis": {}})["incendis"] = ara_ids
        estat["entorn"]["fora"] = sorted((apartats | set(abans)) & fora)
        estat["entorn"]["en_curs_fora"] = sorted(fora)
        # Se guardan por si el historial publicado o la reserva devuelven la
        # ficha repetida; los de hace mucho ya no hacen falta.
        estat["entorn"]["duplicats"] = dict(list(duplicats.items())[-50:])
    # Cortes de luz del barrio (ADR 0072): al aparecer y al dejar de constar. La
    # primera vez solo se apunta lo que hay; si e-distribución no responde
    # (None), no se toca el estado.
    llum = salida.get("llum")
    if llum is not None:
        ara_talls = {t["id"]: t for t in llum.get("talls") or []
                     if (t.get("clients") or 0) >= LLUM_AVIS_CLIENTS_MIN}
        abans = estat.get("llum")
        if abans is not None:
            for k, t in ara_talls.items():
                if k not in abans:
                    afegeix("llum", k, text_llum(t, ahora), "llum")
            for k, t in abans.items():
                if k not in ara_talls:
                    afegeix("llum", f"{k}:fi", text_llum(t, ahora, acabat=True), "fi")
        estat["llum"] = ara_talls
    # Avisos oficiales nuevos (ADR 0055). La primera vez solo se apunta lo que
    # hay; si una fuente ha fallado (None), no se toca: no es que se acabe.
    of = estat.get("oficials")
    nou_of = {"aemet": dict((of or {}).get("aemet") or {}), "plans": dict((of or {}).get("plans") or {})}
    if of is not None and "smp" in of:
        nou_of["smp"] = dict(of["smp"])
    if salida.get("avisos") is not None:
        aemet = aemet_per_clau(a for a in salida["avisos"]
                               if a.get("zona", C.ZONA_AVISOS) == C.ZONA_AVISOS and a["nivel"] in RS.NIVELLS)
        # Avisan los que Meteocat no cubre (ADR 0093): un fenómeno o unas horas
        # sin aviso de Meteocat, o todos si no se ha podido leer. Uno cubierto
        # no se apunta: si deja de estarlo, se avisa.
        if of is not None:
            for k, a in aemet.items():
                if a.get("cobert"):
                    continue
                abans = of["aemet"].get(k)
                if abans is None or RS.NIVELLS.index(a["nivel"]) > RS.NIVELLS.index(abans):
                    # Amb les hores que no cobreix Meteocat; la clau, la de l'avís sencer.
                    v = SMP.visible(a)
                    afegeix("perill", f"aemet:{k}:{a['nivel']}", text_aemet(v, ahora), a["nivel"],
                            episodi=f"aemet:{k}", enllac=AEMET, fins=v.get("fin"), comenca=v.get("inicio"))
        anterior_aemet = (of or {}).get("aemet") or {}
        nou_of["aemet"] = {k: (anterior_aemet.get(k) if a.get("cobert") else a["nivel"]) for k, a in aemet.items()}
        nou_of["aemet"] = {k: v for k, v in nou_of["aemet"].items() if v}
        estat["aemet_coberts"] = [f"aemet:{k}" for k, a in aemet.items() if a.get("cobert")]
        # Els vigents ara, amb el final, per tancar les fitxes dels que l'AEMET
        # ja no publica i allargar les dels que allarga (historial).
        # Amb quan comença la part que no cobreix Meteocat, que s'avança si
        # Meteocat retira el seu (revisor, 20-10-2026: «Previst · Comença a les
        # 6 h» a les 5:40 amb l'avís de Meteocat ja retirat).
        estat["aemet_vigents"] = {f"aemet:{k}": {"fin": a["fin"], "cobert": bool(a.get("cobert")),
                                                 "comenca": SMP.visible(a)["inicio"]}
                                  for k, a in aemet.items()}
    else:
        estat["aemet_vigents"] = None
    # Los avisos de peligro de Meteocat para la comarca (ADR 0092). La primera
    # vez, solo se apuntan; un estado de antes de la 3.87.0 ({clave: grado},
    # sin «fenomens») se toma como vacío: lo vigente se avisa una vez.
    if salida.get("smp") is not None:
        # Només el que queda: Meteocat manté a l'avís vigent les franges ja
        # passades (18-10-2026), i l'episodi s'acaba quan no en queda cap.
        avisos_smp = SMP.pendents(salida["smp"].get("avisos") or [], ahora)
        abans = (of or {}).get("smp")
        abans = abans if isinstance(abans, dict) and "fenomens" in abans else None
        e_smp, canvis, acabat = decideix_smp(abans, avisos_smp, ahora)
        # Si Meteocat ja no en mostra cap, la fitxa espera SMP_FI_MIN minuts a
        # tancar-se (el relleu entre emissions), però ja no és activa: «Perill»
        # la donava per activa i la portada ja no la llistava (revisor, 20-10-2026).
        vistos = [v["vist"] for v in e_smp["fenomens"].values()]
        darrer = max(vistos, key=H.utc, default=None)
        if darrer and H.llegeix(darrer) < ahora.replace(second=0, microsecond=0):
            e_smp["pausa"] = darrer
        if of is not None and "smp" in of:
            if canvis:
                canvi, f = canvis[0]
                rang_max = max(a["perill"] for a in avisos_smp)
                afegeix("perill", f"meteocat:{hora}:{canvi}:{f}", text_meteocat(canvi, f, avisos_smp),
                        SMP.nivell(rang_max), episodi=e_smp["episodi"], enllac=METEOCAT, fins=fins_smp(avisos_smp),
                        comenca=comenca_smp(avisos_smp))
            elif acabat:
                afegeix("perill", f"meteocat:{hora}:fi", text_meteocat_fi(), "fi", episodi=abans["episodi"])
            elif avisos_smp and e_smp["episodi"]:
                # Sense res de nou, la fitxa de «Perill» diu el que queda ara,
                # sense enviar cap missatge (historial).
                e_smp["text"] = {**text_meteocat("vigent", principal_smp(avisos_smp), avisos_smp),
                                 "comenca": comenca_smp(avisos_smp)}
        nou_of["smp"] = e_smp
    elif of is not None and "smp" in of:
        nou_of["smp"] = of["smp"]
    if salida.get("plans") is not None:
        actius = ("alerta", "emergència")
        plans = {p["pla"]: p for p in salida["plans"] if p.get("fase") in actius}
        # Los ocultos por no tener motivo meteorológico (ADR 0062) siguen
        # activos: ocultarlos no es un final, y si vuelven a mostrarse en la
        # misma fase no son nuevos. Al desactivarse uno oculto no se avisa:
        # ya no se estaba mostrando.
        ocults = {p["pla"]: p for p in salida.get("plans_ocults") or [] if p.get("fase") in actius}
        if of is not None:
            for k, p in plans.items():
                abans = (of["plans"].get(k) or {}).get("fase")
                if abans is None or FASES_PLA.index(p["fase"]) > FASES_PLA.index(abans):
                    afegeix("perill", f"pla:{k}:{p['fase']}:{hora}", text_pla(p), "pc",
                            episodi=f"pla:{k}", enllac=None if p.get("comunicat") else PROTECCIO_CIVIL)
                elif p.get("comunicat") and p["comunicat"] != (of["plans"].get(k) or {}).get("comunicat", p["comunicat"]):
                    # Un comunicado distinto del último avisado, también el
                    # primero si la alerta salió sin él (ADR 0091). Un estado
                    # de antes de esto, sin la clave, lo da por avisado.
                    afegeix("perill", f"pla:{k}:comunicat:{hora}", text_comunicat(p), "pc",
                            episodi=f"pla:{k}", nomes_avis=True)
            for k, p in of["plans"].items():
                if k not in plans and k not in ocults and not p.get("ocult"):
                    afegeix("perill", f"pla:{k}:fi:{hora}", text_pla({**p, "pla": k}, acabat=True), "fi",
                            episodi=f"pla:{k}")
        # El último comunicado avisado; si la fuente no lo trae en una pasada,
        # se queda el de antes, para no volver a avisar del mismo.
        nou_of["plans"] = {k: {"fase": p["fase"], "nom": p["nom"], **({"ocult": True} if k in ocults else {}),
                               "comunicat": p.get("comunicat") or ((of or {}).get("plans", {}).get(k) or {}).get("comunicat")}
                           for k, p in {**ocults, **plans}.items()}
    estat["oficials"] = nou_of
    # Riera: atención y peligro, una vez cada nivel por episodio.
    riera = salida.get("riera")
    if riera:
        e = estat.setdefault("riera", {"episodi": None})
        episodi_abans = e.get("episodi")
        abans = set((episodi_abans or {}).get("avisos", {}))
        RI.compara(e, riera, ahora)
        despres = (e.get("episodi") or {}).get("avisos", {})
        for nivell in ("perill", "atencio"):
            if nivell in despres and nivell not in abans:
                afegeix("riera", f"{e['episodi']['inici']}:{nivell}", text_riera(riera, nivell), nivell,
                        episodi=f"riera:{e['episodi']['inici']}", enllac=ENLLAC_RIERA)
                break
        # L'episodi s'ha tancat (3 hores de calma) després d'un avís: es diu que ha passat.
        if episodi_abans and not e.get("episodi") and abans:
            afegeix("riera", f"{episodi_abans['inici']}:fi", text_riera_fi(riera, episodi_abans), "fi",
                    episodi=f"riera:{episodi_abans['inici']}")
    # Los avisos de trenes y de cortes ya no existen (ADR 0053): fuera su estado.
    estat.pop("trens", None)
    estat.pop("talls", None)
    return nous


# --- Historial (ADR 0071) -----------------------------------------------------
# Los avisos de peligro y de la riera agrupados por suceso: una entrada con
# su comienzo y, si ya ha acabado, su final. Para la página «Perill».

RANG = {"🟡": 1, "🟠": 2, "🔴": 3}


def rang(nivell):
    return RANG.get(CERCLE.get(nivell), 0)


def fusiona(propi, altre):
    """El historial propio con el último publicado (anterior): el NAS y la
    reserva de IONOS llevan estados distintos, y el que vuelve a publicar no
    puede borrar lo que el otro vio mientras tanto. Un suceso es el mismo si
    coinciden clave y comienzo; si uno de los dos ya lo da por acabado, vale ese."""
    res = [dict(e) for e in propi]
    for e in altre or []:
        igual = next((x for x in res if x["clau"] == e["clau"] and H.clau(x["inici"]) == H.clau(e["inici"])), None)
        if igual is None:
            res.append(dict(e))
        elif e.get("fi") and not igual.get("fi"):
            igual.update({k: e[k] for k in ("fi", "fi_ca", "fi_es", "substituit_per", "fora_zona") if k in e})
    # Per moment, no com a text: al registre hi ha hores d'abans amb el
    # desfasament i les noves en UTC (ADR 0128).
    return sorted(res, key=lambda e: H.utc(e["inici"]))


FORA_ZONA = {"ca": "Segons Bombers continua actiu, però és fora de la zona que vigila aquesta aplicació "
                   "(el parc de Collserola i fins a 2 km del barri).",
             "es": "Según Bombers sigue activo, pero está fuera de la zona que vigila esta aplicación "
                   "(el parque de Collserola y hasta 2 km del barrio)."}
SUBSTITUIT = {"ca": "Meteocat en té avís per al Vallès Occidental: ara es mostra el seu.",
              "es": "Meteocat tiene aviso para el Vallès Occidental: ahora se muestra el suyo."}
INCLOS = {"ca": "L'AEMET l'ha inclòs en un altre avís seu, que continua actiu.",
          "es": "La AEMET lo ha incluido en otro aviso suyo, que sigue activo."}
RETIRAT = {"ca": "L'AEMET l'ha retirat abans d'hora.",
           "es": "La AEMET lo ha retirado antes de tiempo."}


def aemet_que_inclou(clau, vigents, ahora):
    """El aviso vigente de AEMET del mismo fenómeno que abarca lo que queda de
    uno que ya no publica: «aemet:tempestes:2026-10-18T00:00…» dentro de
    «aemet:tempestes:2026-10-17T12:00…» con final a las 04:00. Lo que queda
    empieza ahora si ya había empezado: el 19-10-2026 a las 19:27 AEMET cambió
    el de 16 h a 8:59 por uno de 19 h a 8:59, y como empezaba más tarde que el
    viejo, la ficha se cerró con «L'AEMET l'ha retirat» (revisor, ADR 0101)."""
    _, tipus, inici = clau.split(":", 2)
    des_de = max(H.llegeix(inici), ahora)
    for k, v in vigents.items():
        _, t, i = k.split(":", 2)
        if t == tipus and k != clau and H.llegeix(i) <= des_de <= H.llegeix(v["fin"]):
            return k
    return None


def posa_fins(e, fins):
    """El final nuevo de una ficha. Si AEMET la alarga, se guarda el que tenía
    al publicarse (`allargat_de`): su texto dice ese final y la ficha tiene que
    decir que lo ha alargado (revisor, 18-10-2026: «fins a mitjanit» con final
    a las 03:59; ADR 0101)."""
    vell = e.get("fins")
    if not fins or fins == vell:
        return
    if vell and e["clau"].startswith("aemet:") and H.llegeix(fins) > H.llegeix(vell):
        e.setdefault("allargat_de", vell)
    e["fins"] = fins


def refa_franja(e):
    """La línea de cuándo dura, con el final que AEMET ha alargado: «de les 6 h
    a les 7 h» pasa a «de les 6 h a les 9 h», en lugar de dejarla y decir
    debajo hasta cuándo va (revisor, 19-10-2026: la ficha decía las dos cosas
    y la portada, de 6 a 9). `franja_fins` es el final que dice ahora la línea;
    con él la web sabe que ya no hace falta repetir la hora. Si la línea no
    está (la quitó el revisor o es de un texto antiguo, con «demà»), no se toca."""
    fins_text = e.get("franja_fins") or e.get("allargat_de")
    if not fins_text or not e.get("fins") or fins_text == e["fins"]:
        return
    ini = e.get("comenca") or e["clau"].split(":", 2)[2]
    t = H.llegeix(e["fins"])
    canviat = False
    for idioma in ("ca", "es"):
        abans, ara = franja(ini, fins_text, t, idioma), franja(ini, e["fins"], t, idioma)
        linies = e[idioma].split("\n")
        if abans in linies:
            linies[linies.index(abans)] = ara
            e[idioma] = "\n".join(linies)
            canviat = True
    if canviat:
        e["franja_fins"] = e["fins"]


def tanca_aemet(h, vigents, ahora):
    """Las fichas de AEMET al día con lo que publica AEMET ahora (Juanjo,
    17-10-2026: «Perill» enseñaba como activos dos avisos que AEMET ya había
    juntado en otro). Si alarga uno, su ficha también; si uno desaparece antes
    de acabar, la ficha se cierra diciendo si está dentro de otro (con el
    enlace a su ficha, o a la de Meteocat si lo cubre Meteocat) o si se ha
    retirado. Sin lectura de AEMET (None), no se toca nada."""
    if vigents is None:
        return
    ara = H.clau(ahora)
    for e in h:
        if not e["clau"].startswith("aemet:") or e.get("fi"):
            continue
        v = vigents.get(e["clau"])
        if v:
            posa_fins(e, v["fin"])
            refa_franja(e)
            if v.get("comenca") and e.get("comenca") and \
                    H.llegeix(v["comenca"]) < H.llegeix(e["comenca"]):
                e["comenca"] = v["comenca"]
            continue
        if e.get("fins") and H.llegeix(e["fins"]) <= ahora:
            continue        # ja ha acabat a la seva hora
        k = aemet_que_inclou(e["clau"], vigents, ahora)
        if k and vigents[k]["cobert"]:
            # El substituït_per de Meteocat el posa el pas de sota.
            e.update(fi=ara, fi_ca=SUBSTITUIT["ca"], fi_es=SUBSTITUIT["es"])
        elif k:
            e.update(fi=ara, fi_ca=INCLOS["ca"], fi_es=INCLOS["es"])
            altra = next((x for x in h if x["clau"] == k and not x.get("fi")), None)
            if altra:
                e["substituit_per"] = {"clau": altra["clau"], "inici": altra["inici"]}
        else:
            e.update(fi=ara, fi_ca=RETIRAT["ca"], fi_es=RETIRAT["es"])


def cos_avis(text):
    """Les línies d'un avís sense el títol."""
    return text.split("\n")[1:]


def historial(estat, nous, ahora, anterior=None):
    h = estat["historial"] = fusiona(estat.get("historial") or [], anterior)
    for a in nous:
        ep = a.get("episodi")
        if not ep:
            continue
        obert = next((e for e in reversed(h) if e["clau"] == ep and not e.get("fi")), None)
        if a.get("nomes_avis"):
            # El comunicat nou d'un pla no canvia la fitxa, però «actualitzat»
            # diu l'hora del missatge, la mateixa que al mòbil: deia la del PDF
            # (12:08) amb el missatge enviat a les 12:15 (revisor, 19-10-2026).
            if obert:
                obert["darrer"] = a["hora"]
            continue
        if a.get("nivell") == "fi":
            for e in h:
                if e["clau"] == ep and not e.get("fi"):
                    e.update(fi=a["hora"], fi_ca=a["ca"], fi_es=a["es"])
            continue
        if obert:
            # Sube de nivel o cambia: se queda el texto nuevo y el peor nivel.
            if rang(a.get("nivell")) >= rang(obert.get("nivell")):
                obert["nivell"] = a.get("nivell")
            obert.update(ca=a["ca"], es=a["es"], darrer=a["hora"], escrit=a["hora"],
                         **{k: a[k] for k in ("enllac", "comenca") if a.get(k)})
            obert.pop("franja_fins", None)      # el text nou diu el seu final
            posa_fins(obert, a.get("fins"))
        else:
            h.append({"clau": ep, "tipus": a["tipus"], "inici": a["hora"], "nivell": a.get("nivell"),
                      "ca": a["ca"], "es": a["es"], "escrit": a["hora"], **{k: a[k] for k in ("enllac", "fins", "comenca") if a.get(k)}})
    # Un aviso de AEMET que ahora cubre Meteocat ya no se muestra en ningún
    # sitio (ADR 0093): su ficha se cierra diciéndolo, con la de Meteocat que
    # la sustituye, para que «Perill» no la dé por acabada (Juanjo, 16-10-2026:
    # «¿este aviso se ha retirado?»). Las cerradas antes de la 3.88.1 la toman
    # en la pasada siguiente.
    tanca_aemet(h, estat.get("aemet_vigents"), ahora)
    # Les fitxes de l'AEMET obertes abans de la 3.136.0 no duien quan comencen:
    # és a la clau (aemet:tipus:inici).
    for e in h:
        if e["clau"].startswith("aemet:") and not e.get("fi") and not e.get("comenca"):
            e["comenca"] = e["clau"].split(":", 2)[2]
    smp_estat = (estat.get("oficials") or {}).get("smp") or {}
    smp = smp_estat.get("episodi")
    mc = next((x for x in reversed(h) if smp and x["clau"] == smp), None)
    # La fitxa oberta de Meteocat, amb el que queda: les franges que passen en
    # surten, i «Observat ara» quan ja no s'observa (18-10-2026). Si les
    # línies són les mateixes, es queda el text de l'últim avís.
    ara_smp = smp_estat.get("text")
    if mc and ara_smp and not mc.get("fi") and set(cos_avis(mc["ca"])) != set(cos_avis(ara_smp["ca"])):
        mc.update(ca=ara_smp["ca"], es=ara_smp["es"], escrit=H.clau(ahora))
    if mc and ara_smp and not mc.get("fi") and ara_smp.get("comenca"):
        mc["comenca"] = ara_smp["comenca"]
    if mc and not mc.get("fi") and smp_estat.get("pausa"):
        mc.setdefault("en_pausa", smp_estat["pausa"])
    elif mc:
        mc.pop("en_pausa", None)
    # La fitxa oberta del temps extrem d'aquesta web, igual: els riscos d'ara,
    # cadascun amb d'on surt i quant s'hi pot confiar, que canvia d'una passada
    # a l'altra (riscos.font). Sense «darrer»: no és un avís nou (Juanjo,
    # 19-10-2026: la fitxa de les 13:09 deia «Calculat per aquesta aplicació»
    # d'unes ratxes que només preveia un model).
    propi = next((x for x in reversed(h) if x["clau"] == "propi" and not x.get("fi")), None)
    ara_propi = estat.get("perill_text")
    if propi and ara_propi and cos_avis(propi["ca"]) != cos_avis(ara_propi["ca"]):
        propi.update(ca=ara_propi["ca"], es=ara_propi["es"], escrit=H.clau(ahora))
    # Si la previsió ja no veu cap risc, la fitxa no es tanca fins passades
    # RISC_FI_H hores (que el vaivé dels models no repeteixi missatges), però
    # mentrestant diu «Ja no es preveu» i no compta com a activa: «Perill» la
    # donava per activa i la portada ja no la llistava (revisor, 19-10-2026).
    if propi and ara_propi:
        propi.pop("en_pausa", None)
    elif propi and estat.get("perill_buit"):
        propi.setdefault("en_pausa", H.clau(ahora))
    for e in h:
        if e["clau"] in (estat.get("aemet_coberts") or []) and not e.get("fi"):
            e.update(fi=H.clau(ahora), fi_ca=SUBSTITUIT["ca"], fi_es=SUBSTITUIT["es"])
        if mc and e.get("fi_ca") == SUBSTITUIT["ca"] and not e.get("substituit_per"):
            e["substituit_per"] = {"clau": mc["clau"], "inici": mc["inici"]}
    # Un incendio que sigue en curso pero ha salido de la zona: su ficha se
    # cierra diciéndolo, sin darlo por apagado.
    # Las que se cerraron con «ja no consta» estando en curso (16-10-2026)
    # se corrigen igual.
    # La ficha de una fila repetida de Bombers (28-10-2026): fuera si ya está
    # la del mismo incendio; si no, pasa a ser la suya.
    duplicats = (estat.get("entorn") or {}).get("duplicats") or {}
    for e in list(h):
        iid = e["clau"][8:] if e["clau"].startswith("incendi:") else None
        if iid in duplicats:
            if any(x["clau"] == f"incendi:{duplicats[iid]}" for x in h):
                h.remove(e)
            else:
                e["clau"] = f"incendi:{duplicats[iid]}"
    en_curs_fora = set((estat.get("entorn") or {}).get("en_curs_fora") or [])
    for e in h:
        if e["clau"].startswith("incendi:") and e["clau"][8:] in en_curs_fora and (
                not e.get("fi") or "ja no consta" in (e.get("fi_ca") or "")):
            e.update(fi=e.get("fi") or H.clau(ahora), fi_ca=FORA_ZONA["ca"], fi_es=FORA_ZONA["es"],
                     fora_zona=True)
    # Un plan que ya no se muestra (desactivado sin aviso, u oculto por no
    # tener motivo meteorológico: ADR 0062) ya no está activo en la página.
    plans = (estat.get("oficials") or {}).get("plans")
    if plans is not None:
        visibles = {k for k, p in plans.items() if not p.get("ocult")}
        for e in h:
            if e["clau"].startswith("pla:") and not e.get("fi") and e["clau"][4:] not in visibles:
                e["fi"] = H.clau(ahora)
    estat["historial"] = h
    return h


def final(e, ahora):
    """Cuándo acabó un episodio: su final o, en los de AEMET, que no tienen
    mensaje de final, el fin de su validez si ya ha pasado; None si sigue."""
    if e.get("fi"):
        return H.llegeix(e["fi"])
    if e.get("fins") and H.llegeix(e["fins"]) <= ahora:
        return H.llegeix(e["fins"])
    return None


def parteix(hist, ahora):
    """(recents, vells): lo que sigue o acabó hace ARXIU_DIES días o menos, y
    lo que va a los archivos por año."""
    limit = ahora - dt.timedelta(days=ARXIU_DIES)
    recents, vells = [], []
    for e in hist:
        fi = final(e, ahora)
        (vells if fi and fi < limit else recents).append(e)
    return recents, vells


def nom_arxiu(any_):
    return f"avisos-{any_}.json"


def llegeix_arxiu(font):
    """El historial de un archivo por año (ruta o dirección); [] si no está."""
    try:
        if font.startswith("https://"):
            with urllib.request.urlopen(font, timeout=20) as r:
                return H.interna(json.load(r).get("historial") or [])
        with open(font, encoding="utf-8") as f:
            # Publicat, amb l'hora de Madrid: per dins, en UTC (ADR 0128).
            return H.interna(json.load(f).get("historial") or [])
    except (OSError, ValueError):
        return []


def arxiva(vells, dir_estat, dir_sortida, anterior=None):
    """Los episodios viejos, cada uno al archivo del año en que empezó: el
    propio (en la carpeta del estado), unido con el publicado (al lado de
    `anterior`, el avisos.json publicado: el NAS y la reserva llevan cada uno
    el suyo) y con los nuevos, como `fusiona`. Se escribe en las dos carpetas
    y devuelve los nombres escritos en la de salida."""
    per_any = {}
    for e in vells:
        # L'any de Madrid: amb la clau en UTC, el que comença l'1 de gener entre
        # les 0 i la 1 aniria a l'arxiu de l'any anterior (ADR 0128).
        per_any.setdefault(str(H.local(e["inici"]).year), []).append(e)
    def publicat(nom):
        if not anterior:
            return []
        if anterior.startswith("https://"):
            return llegeix_arxiu(anterior.rsplit("/", 1)[0] + "/" + nom)
        return llegeix_arxiu(os.path.join(os.path.dirname(anterior), nom))
    noms = []
    for any_, nous in sorted(per_any.items()):
        nom = nom_arxiu(any_)
        tots = fusiona(fusiona(llegeix_arxiu(os.path.join(dir_estat, nom)), publicat(nom)), nous)
        for carpeta in dict.fromkeys((dir_estat, dir_sortida)):
            ruta = os.path.join(carpeta, nom)
            with open(ruta + ".tmp", "w", encoding="utf-8") as f:
                arxiu = {"any": int(any_), "historial": tots}
                # El que es publica, amb les hores en hora de Madrid (ADR 0128).
                json.dump(H.publica(arxiu) if carpeta == dir_sortida else arxiu, f, ensure_ascii=False)
            os.replace(ruta + ".tmp", ruta)
        noms.append(nom)
    return noms


SENTIT_PREALERTA = {"ca": "Es preveia un risc a mitjà termini. El pla no estava activat: només calia estar-ne pendent.",
                    "es": "Se preveía un riesgo a medio plazo. El plan no estaba activado: solo había que estar pendiente."}


def data_fase(text):
    """«24/10/2026 01:10», hora de Madrid, de los datos de Protección Civil;
    None si no se entiende. La zona, explícita, para no depender del reloj
    del equipo que lo ejecuta (el NAS o la reserva de IONOS)."""
    from zoneinfo import ZoneInfo
    try:
        return dt.datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Madrid"))
    except (TypeError, ValueError):
        return None


def prealertes(estat, salida, hist, ahora):
    """Las prealertas de Protección Civil, en el historial de «Perill» cuando
    acaban (ADR 0124; Juanjo, 24-10-2026, tras una prealerta de madrugada que
    desapareció sin dejar rastro: «ya no está y tampoco está en el historial
    de avisos, que ha pasado?»). Mientras duran, la ficha de «Ara» sale de
    `plans_prealerta` (ADR 0091) y no avisan (ADR 0051); al acabar, una ficha
    ya cerrada, con el comienzo oficial y el final: si ha pasado a alerta o
    emergencia, o si ya no consta. Las ocultas por no tener motivo
    meteorológico (ADR 0062) siguen en curso, pero solo se apuntan si llegaron
    a mostrarse. Sin datos de Protección Civil, no se toca nada."""
    plans = salida.get("plans")
    if plans is None:
        return hist
    ara = H.clau(ahora)
    visibles = {p["pla"]: p for p in plans if p.get("fase") == "prealerta"}
    ocults = {p["pla"]: p for p in salida.get("plans_ocults") or [] if p.get("fase") == "prealerta"}
    actius = {p["pla"]: p for p in plans + (salida.get("plans_ocults") or []) if p.get("fase") in ("alerta", "emergència")}
    abans = estat.get("prealertes") or {}
    nou = {}
    for k, p in {**ocults, **visibles}.items():
        vell = abans.get(k) or {}
        t = data_fase(p.get("des_de"))
        nou[k] = {"nom": p["nom"], "inici": vell.get("inici") or (H.clau(t) if t else ara),
                  "descripcio": p.get("descripcio") or vell.get("descripcio"),
                  "comunicat": p.get("comunicat") or vell.get("comunicat"),
                  "vista": vell.get("vista") or k in visibles}
    for k, v in abans.items():
        if k in nou or not v.get("vista"):
            continue
        nom_ca, nom_es = v["nom"], NOM_PLA_ES.get(v["nom"], v["nom"])
        motiu = f"\nMotiu, segons Protecció Civil: {html.escape(v['descripcio'], quote=False)}." if v.get("descripcio") else ""
        passa = actius.get(k)
        fase = (passa or {}).get("fase")
        de = "d'" if fase and fase[0] in "aeiouàèéíòóú" else "de "
        fase_es = {"emergència": "emergencia"}.get(fase, fase)
        e = {"clau": f"prealerta:{k}", "tipus": "perill", "inici": v["inici"], "nivell": "prealerta",
             "ca": negreta(f"Protecció Civil: pla {nom_ca} ({k}) en fase de prealerta", "mig")
                   + f"\n{SENTIT_PREALERTA['ca']}{motiu}\nLa prealerta no arriba com a avís.",
             "es": negreta(f"Protección Civil: plan {nom_es} ({k}) en fase de prealerta", "mig")
                   + f"\n{SENTIT_PREALERTA['es']}{motiu.replace('Motiu, segons', 'Motivo, según')}"
                   + "\nLa prealerta no llega como aviso.",
             "escrit": ara, "fi": ara,
             "fi_ca": negreta(f"Protecció Civil: el pla {nom_ca} ({k}) ja no està en prealerta", "fi")
                      + (f"\nHa passat a fase {de}{fase}." if passa else "\nJa no consta en prealerta."),
             "fi_es": negreta(f"Protección Civil: el plan {nom_es} ({k}) ya no está en prealerta", "fi")
                      + (f"\nHa pasado a fase de {fase_es}." if passa else "\nYa no consta en prealerta.")}
        if v.get("comunicat"):
            e["comunicat"] = v["comunicat"]
        else:
            e["enllac"] = PROTECCIO_CIVIL
        if not any(x["clau"] == e["clau"] and H.clau(x["inici"]) == H.clau(e["inici"]) for x in hist):
            hist.append(e)
    estat["prealertes"] = nou
    hist.sort(key=lambda e: H.utc(e["inici"]))
    return hist


# El enlace al comunicado que llevaba el texto del aviso, si ya había uno al
# empezar (text_pla).
ENLLAC_COMUNICAT = re.compile(r'\n<a href="[^"]*">Comunica(?:t|do) \(PDF\)</a>')


def comunicats(hist, plans):
    """El comunicado más reciente de cada plan activo, en su ficha de «Perill».
    Protección Civil puede publicarlo después de cambiar la fase (el INUNCAT
    del 15-10-2026 pasó a alerta a las 19:09 y el comunicado salió a las
    19:43), y lo actualiza mientras dura: la ficha lo toma en cada pasada y,
    al acabar, se queda con el último (Juanjo, 15-10-2026; ADR 0091). El texto
    pierde el enlace que llevaba, para que no haya dos."""
    actius = {p["pla"]: p.get("comunicat") for p in plans or [] if p.get("pla")}
    for e in hist:
        if e["clau"].startswith("pla:") and not e.get("fi") and actius.get(e["clau"][4:]):
            e["comunicat"] = actius[e["clau"][4:]]
            for idioma in ("ca", "es"):
                e[idioma] = ENLLAC_COMUNICAT.sub("", e[idioma])
    return hist


def anterior_publicat(font):
    """El historial del último avisos.json publicado: una ruta (la reserva, en
    IONOS) o una dirección (el NAS). [] si no se puede leer."""
    if not font:
        return []
    try:
        if font.startswith("https://"):
            with urllib.request.urlopen(font, timeout=20) as r:
                return H.interna(json.load(r).get("historial") or [])
        with open(font, encoding="utf-8") as f:
            # Publicat, amb l'hora de Madrid: per dins, en UTC (ADR 0128).
            return H.interna(json.load(f).get("historial") or [])
    except (OSError, ValueError):
        return []


# --- Enlace a la web (ADR 0072) -----------------------------------------------------
# Todo aviso que se puede elegir lleva un enlace a su información en la web
# (Juanjo, 11-10-2026: «todos los avisos que tengan una alerta configurable …
# deben tener un enlace, como ya has hecho con la pestaña peligros»): peligro y
# riera, a su ficha de «Perill»; los cortes de luz, a «Llum»; la lluvia, a «El
# temps». La misma página abre la notificación del navegador (bot/push.py).

def id_fitxa(clau, inici):
    """El id de la ficha en «Perill», el mismo que idFitxa de web/perill.js: amb
    l'hora com es publica, la de Madrid amb el desfasament (ADR 0128), que és la
    que veu la web; amb la interna, en UTC, l'enllaç no hi portaria."""
    t = unicodedata.normalize("NFD", f"{clau}-{H.publica(inici)}")
    t = "".join(c for c in t if not "\u0300" <= c <= "\u036f")
    return "a-" + re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9-]+", "-", t)).lower()


PAGINA = {"pluja": "./", "llum": "consultes.html#llum"}
MES_INFO = {"ca": "Més informació a Temps a Montflorit", "es": "Más información en Temps a Montflorit"}


def pagina(a, hist):
    """La página del aviso, relativa a la web (perill.html#a-…, consultes.html#llum…)."""
    ep = a.get("episodi")
    if ep:
        e = next((e for e in reversed(hist) if e["clau"] == ep), None)
        return f"perill.html#{id_fitxa(ep, e['inici'])}" if e else "perill.html"
    return PAGINA.get(a["tipus"], "./")


def amb_enllac(a, hist):
    """Pone a cada aviso nuevo su página y, al final del texto, el enlace."""
    a["pagina"] = pagina(a, hist)
    for idioma in ("ca", "es"):
        base = WEB if idioma == "ca" else WEB + "es/"
        url = base + ("" if a["pagina"] == "./" else a["pagina"])
        a[idioma] += f'\n<a href="{html.escape(url)}">{MES_INFO[idioma]}</a>'
    return a


MARCA_SMP = os.path.join(os.environ.get("APRENENTATGE_DIR", "/estat/aprenentatge"), "smp-falla")


def actualitza(casa_json, sortida, ahora=None, anterior=None, avisa=True):
    ahora = ahora or H.ara()
    with open(casa_json, encoding="utf-8") as f:
        salida = json.load(f)
    # Si no se ha podido leer Meteocat, a Juanjo en el momento, no al día
    # siguiente (ADR 0092): mientras tanto avisan los de AEMET.
    if "smp" in salida:
        error, reserva = None, False
        if salida["smp"] is None:
            error = next((e[5:] for e in salida.get("errors") or [] if e.startswith("smp: ")), "sense dades")
        elif salida["smp"].get("falla_pagina"):
            error, reserva = salida["smp"]["falla_pagina"], True
        try:
            SMP.marca_falla(MARCA_SMP, error, avisa, reserva)
        except OSError:
            pass
    try:
        with open(ESTAT, encoding="utf-8") as f:
            # Les hores d'abans de la 3.201.0, amb desfasament, en UTC com les
            # noves (ADR 0128): així es comparen i s'ordenen bé.
            estat = H.interna(json.load(f))
    except (OSError, ValueError):
        estat = {}
    nous = decideix(estat, salida, ahora)
    # Los avisos de las últimas CONSERVA_H horas: el bot reparte los que no ha
    # mandado aún.
    limit = ahora - dt.timedelta(hours=CONSERVA_H)
    llista = [a for a in estat.get("llista", []) if H.llegeix(a["hora"]) > limit] + nous
    estat["llista"] = llista
    hist = comunicats(historial(estat, nous, ahora, anterior_publicat(anterior)), salida.get("plans"))
    hist = prealertes(estat, salida, hist, ahora)
    # Lo acabado hace tiempo, al archivo de su año (ADR 0124): no se pierde y
    # avisos.json, que descarga cada página, no crece.
    hist, vells = parteix(hist, ahora)
    if vells:
        try:
            arxiva(vells, os.path.dirname(ESTAT), os.path.dirname(os.path.abspath(sortida)), anterior)
            estat["historial"] = hist
        except OSError:
            hist = sorted(hist + vells, key=lambda e: H.utc(e["inici"]))
    # El enlace va en el aviso, no en el historial: la ficha ya está en la web.
    for a in nous:
        amb_enllac(a, hist)
    with open(ESTAT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estat, f, ensure_ascii=False)
    os.replace(ESTAT + ".tmp", ESTAT)
    with open(sortida, "w", encoding="utf-8") as f:
        # El Pla Alfa de hoy y mañana, para «Ara» de «Perill», sin avisar ni
        # guardar historial: cambia cada día (ADR 0046 y 0071).
        alfa = (salida.get("entorn") or {}).get("pla_alfa")
        # Los planes en prealerta que muestra la web, también para «Ara»: no
        # avisan (ADR 0051) y no tienen ficha en el historial, y la portada
        # llevaba a una «Perill» vacía (Juanjo, 15-10-2026; ADR 0091).
        prealerta = [{k: p.get(k) for k in ("pla", "nom", "fase", "des_de", "descripcio", "comunicat")}
                     for p in salida.get("plans") or [] if p.get("fase") == "prealerta"]
        # Les correccions del revisor (ADR 0101), mentre el text sigui el corregit.
        json.dump(H.publica(RV.aplica_correccions({"generat": H.clau(ahora), "versio": C.VERSION,
                                         "avisos": llista, "historial": hist, "pla_alfa": alfa,
                                         "plans_prealerta": prealerta,
                                         # Per al punt ambre de la pestanya «Riera» (ADR 0107).
                                         "riera_previsio": salida.get("riera_previsio")})), f, ensure_ascii=False)
    return nous


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(1)
    for a in actualitza(sys.argv[1], sys.argv[2], anterior=sys.argv[3] if len(sys.argv) == 4 else None):
        print(a["id"], a["ca"].splitlines()[0])
