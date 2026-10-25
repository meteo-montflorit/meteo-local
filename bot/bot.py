#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El bot de Telegram de Temps a Montflorit (@TempsMontfloritBot, ADR 0034).

Vive en el hosting de IONOS, no en el NAS: un corte de luz en casa durante una
tormenta no lo para. El cron lo arranca cada minuto y, durante unos 50
segundos, espera mensajes de Telegram (contesta en uno o dos segundos) y
reparte:

- los avisos que el NAS (o la reserva) deja en avisos.json (avisos_bot.py), a
  quien los haya elegido, y los de riera y peligro también al canal
  @TempsMontflorit (solo en catalán);
- el resumen del día, a la hora que elija cada uno, y al canal a las 7.

Cada persona elige en un menú con botones qué avisos quiere (riera, peligro,
lluvia en unos minutos, trenes), la hora del resumen y el idioma. Solo se
guarda su identificador de Telegram y lo que elige; /baixa lo borra. Sin
dependencias: solo la biblioteca estándar.

Uso: bot.py           una vuelta (lo que hace el cron, cada minuto)
     bot.py estat     suscriptores y avisos repartidos
     bot.py informe   el recuento, a Juanjo por Telegram (el cron, los lunes)
"""
import datetime as dt
import fcntl
import html
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

# La hora local de Montflorit, pase lo que pase con la del hosting.
os.environ.setdefault("TZ", "Europe/Madrid")
time.tzset()

BASE = os.environ.get("BOT_DIR", os.path.expanduser("~/.temps-bot"))
DADES = os.environ.get("BOT_DADES", os.path.expanduser("~/app/meteo-local"))
REPO = os.environ.get("BOT_REPO", os.path.expanduser("~/.meteo-reserva/repo"))
SUBS = os.path.join(BASE, "subscriptors.json")
ESTAT = os.path.join(BASE, "estat.json")
CANAL = os.environ.get("BOT_CANAL", "@TempsMontflorit")
WEB = "https://meteo-montflorit.github.io/"
DURADA_S = 50
# Els trens i el trànsit no són avisos: es consulten amb /trens i /transit
# (Juanjo, 09-10-2026: «el que le interese lo mira en el menú»; ADR 0053).
# Els talls de llum del barri, des de l'11-10-2026 (ADR 0072): al bot i a la
# web, si es trien, i al canal.
TIPUS = ("riera", "perill", "pluja", "llum")
PER_DEFECTE = ["riera", "perill"]
CANAL_TIPUS = ("riera", "perill", "llum")
# Al matí se'n tria una hora; la de la nit, la de demà, es pot afegir a part
# (Juanjo, 09-10-2026: «elegir 1h por la mañana y la de la noche si se
# quiere»). A les 21 h i no a les 20 h: a les 21 ja hi ha entrat sempre la
# passada de les 17 h d'AROME i ICON-EU, que arriba cap a les 19:45 (ADR 0053).
HORES_RESUM = ("6", "7", "8")
HORA_NIT = "21"
# El canal, la del matí a les 7 i la de demà a les 21 (ADR 0055).
CANAL_RESUMS = ("7", "21")
# Un aviso que llega tarde ya no sirve: lluvia en 15 minutos, como mucho 20.
VIGENCIA_MIN = {"pluja": 20, "perill": 180, "riera": 180, "llum": 180}
DADES_VELLES_H = 2

T = {
    "ca": {
        "benvinguda": ("<b>Bot Temps a Montflorit</b>\nT'enviaré, només a tu, els avisos del temps a Montflorit "
                       "(Cerdanyola del Vallès) que triïs a continuació. Els calcula un programa amb dades públiques: "
                       "són orientatius, no oficials. Segueix sempre les indicacions de Protecció Civil i de "
                       "l'Ajuntament.\n" + WEB),
        "inici": "Per començar, t'he activat els avisos de la riera i de perill.",
        "menu": ("Toca el que vulguis rebre. ✓ vol dir que sí; si el tornes a tocar, es treu.\n"
                 "La previsió del dia arriba al matí, a l'hora que triïs, i, si vols, la de demà a les 21 h.\n\n"
                 "Si també ets al canal (@TempsMontflorit), no et repetiré el que ja t'arriba per allà: els avisos "
                 "de la riera, de perill i de talls de llum i la previsió de les 7 h i de les 21 h.\n\n"
                 "Només es desa el teu identificador de Telegram i el que triïs aquí. Amb /baixa s'esborra tot."),
        "riera": "Desbordament de la riera de Sant Cugat (en proves)", "perill": "Situacions de perill",
        "pluja": "Pluja a punt de començar (15 min abans)",
        "llum": "Talls de llum al barri",
        "resum": "Previsió del dia, al matí, a les:", "no": "Cap", "h": "{} h",
        "nit": "A les 21 h, la previsió de demà",
        "baixa": "Fet: s'han esborrat les teves dades i ja no rebràs res. Amb /start pots tornar-hi.",
        "ajuda": ("/avisos tria què reps · /avui la previsió d'avui · /dema la de demà · /ara el temps ara · "
                  "/radar el radar ara · /sol el sol · /aire la qualitat de l'aire · /pollen el pol·len · /trens els trens · /busos els busos · "
                  "/transit el trànsit · /llum els talls de llum · /avisos_actius els avisos oficials · "
                  "/baixa deixa de rebre'n i esborra les teves dades"),
        "velles": "Les dades de Temps a Montflorit no s'actualitzen des de les {}: ara no puc donar la previsió.",
        "velles_ara": "Les dades de Temps a Montflorit no s'actualitzen des de les {}: ara no puc dir el temps que fa.",
        "sense_previsio": "Ara no hi ha previsió disponible: les dades de les {} no en porten.",
        "mesura": " (mesura de les {})",
        "sense_trens": "Els avisos de trens ja no s'envien automàticament. Pots consultar l'estat dels trens quan vulguis amb /trens.",
    },
    "es": {
        "benvinguda": ("<b>Bot Temps a Montflorit</b>\nTe enviaré, solo a ti, los avisos del tiempo en Montflorit "
                       "(Cerdanyola del Vallès) que elijas a continuación. Los calcula un programa con datos públicos: "
                       "son orientativos, no oficiales. Sigue siempre las indicaciones de Protección Civil y del "
                       "Ayuntamiento.\n" + WEB),
        "inici": "Para empezar, te he activado los avisos de la riera y de peligro.",
        "menu": ("Toca lo que quieras recibir. ✓ quiere decir que sí; si lo vuelves a tocar, se quita.\n"
                 "La previsión del día llega por la mañana, a la hora que elijas, y, si quieres, la de mañana a las 21 h.\n\n"
                 "Si también estás en el canal (@TempsMontflorit), no te repetiré lo que ya te llega por allí, en "
                 "catalán: los avisos de la riera, de peligro y de cortes de luz y la previsión de las 7 h y de las 21 h.\n\n"
                 "Solo se guarda tu identificador de Telegram y lo que elijas aquí. Con /baixa se borra todo."),
        "riera": "Desbordamiento de la riera de Sant Cugat (en pruebas)", "perill": "Situaciones de peligro",
        "pluja": "Lluvia a punto de empezar (15 min antes)",
        "llum": "Cortes de luz en el barrio",
        "resum": "Previsión del día, por la mañana, a las:", "no": "Ninguna", "h": "{} h",
        "nit": "A las 21 h, la previsión de mañana",
        "baixa": "Hecho: se han borrado tus datos y ya no recibirás nada. Con /start puedes volver.",
        "ajuda": ("/avisos elige qué recibes · /avui la previsión de hoy · /dema la de mañana · /ara el tiempo ahora · "
                  "/radar el radar ahora · /sol el sol · /aire la calidad del aire · /pollen el polen · /trens los trenes · /busos los autobuses · "
                  "/transit el tráfico · /llum los cortes de luz · /avisos_actius los avisos oficiales · "
                  "/baixa deja de recibir y borra tus datos"),
        "velles": "Los datos de Temps a Montflorit no se actualizan desde las {}: ahora no puedo dar la previsión.",
        "velles_ara": "Los datos de Temps a Montflorit no se actualizan desde las {}: ahora no puedo decir el tiempo que hace.",
        "sense_previsio": "Ahora no hay previsión disponible: los datos de las {} no la traen.",
        "mesura": " (medida de las {})",
        "sense_trens": "Los avisos de trenes ya no se envían automáticamente. Puedes consultar el estado de los trenes cuando quieras con /trens.",
    },
}


def ara():
    # L'hora de Madrid, sigui quina sigui la del sistema (ADR 0128).
    return dt.datetime.now(ZONA)


def llegeix(ruta, defecte):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecte


def desa(ruta, dades):
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dades, f, ensure_ascii=False)
    os.replace(ruta + ".tmp", ruta)


# Lo que falla queda apuntado (errors.log, junto al estado), sin
# identificadores de nadie: solo el aviso, cuántos chats y el motivo. Hasta la
# auditoría del 07-10-2026 los fallos de Telegram se silenciaban y un aviso
# podía caducar sin dejar rastro (ADR 0038).
REGISTRE_MAX = 500_000


def registra(text):
    ruta = os.path.join(BASE, "errors.log")
    try:
        os.makedirs(BASE, exist_ok=True)
        if os.path.exists(ruta) and os.path.getsize(ruta) > REGISTRE_MAX:
            os.replace(ruta, ruta + ".1")
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{ara():%F %T}  {text}\n")
    except OSError:
        pass


# --- Telegram ------------------------------------------------------------------

class Api:
    def __init__(self, token):
        self.url = f"https://api.telegram.org/bot{token}/"

    def __call__(self, metode, temps=30, **params):
        dades = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                        for k, v in params.items() if v is not None}).encode()
        try:
            with urllib.request.urlopen(self.url + metode, dades, timeout=temps) as r:
                return json.load(r).get("result")
        except urllib.error.HTTPError as ex:
            resposta = json.load(ex)
            if ex.code == 403:          # la persona ha bloqueado el bot
                raise Bloquejat() from ex
            raise RuntimeError(f"{metode}: {resposta.get('description')}") from ex


class Bloquejat(Exception):
    pass


# Las unidades no se separan de su número al partir la línea.
UNITATS = re.compile(r"(\d) (°C|mm|km/h|cm)\b")
# La última línea acaba en un enlace (la web, «Més informació…», la ficha).
ENLLAC_FINAL = re.compile(r"(<a\s[^>]*>.*</a>|https?://\S+)\s*$")


def text_telegram(text):
    """El texto tal como sale a Telegram: las unidades pegadas a su número y
    una línea en blanco antes del enlace final, en todos los mensajes
    (Juanjo, 18-10-2026: «en telegram deja una linea siempre antes del
    enlace final»)."""
    linies = UNITATS.sub("\\1\u00a0\\2", text).rstrip().split("\n")
    if len(linies) > 1 and ENLLAC_FINAL.search(linies[-1]) and linies[-2].strip():
        linies.insert(-1, "")
    return "\n".join(linies)


def envia(api, chat, text, teclat=None, html=False):
    return api("sendMessage", chat_id=chat, text=text_telegram(text), disable_web_page_preview=True,
               parse_mode="HTML" if html else None,
               reply_markup={"inline_keyboard": teclat} if teclat else None)


# --- La gràfica del resum, com a imatge (ADR 0098) ---------------------------------
# El NAS la dibuixa a cada publicació (grafica_imatge.py) i la puja aquí amb
# les dades: la d'avui (d'ara a mitjanit) i la de demà (de la nit d'avui al
# final de demà), en català i en castellà. Telegram la baixa de la carpeta
# pública; després es reaprofita el seu file_id. Només si és recent: si no, el
# resum surt només amb text, com abans.
URL_DADES = "https://bilateria.org/app/meteo-local/"
IMATGE_MAX_MIN = 45
PEU_MAX = 1024          # el text que admet Telegram sota una foto
FOTOS = {}


def es_resum_de_dema(moment, dema=False, avui=False):
    """El mateix criteri que resum(): /dema, o el programat des de HORA_DEMA."""
    return dema or (moment.hour >= HORA_DEMA and not avui)


def imatge_resum(idioma, moment, dema=False, avui=False, dades=None):
    nom = f"grafica-{'dema' if es_resum_de_dema(moment, dema, avui) else 'avui'}-{'es' if idioma == 'es' else 'ca'}.png"
    try:
        mt = os.path.getmtime(os.path.join(dades or DADES, nom))
    except OSError:
        return None
    if moment.timestamp() - mt > IMATGE_MAX_MIN * 60:
        return None
    return f"{URL_DADES}{nom}?v={int(mt)}"


def envia_resum(api, chat, text, imatge=None):
    """El resum amb la seva gràfica a dalt (Juanjo, 17-10-2026). Si el text no
    cap sota la foto, la foto i després el text; si la foto no entra, només el
    text."""
    if imatge:
        peu = text_telegram(text)
        pla = html.unescape(re.sub(r"<[^>]+>", "", peu))
        cap = len(pla.encode("utf-16-le")) // 2 <= PEU_MAX
        try:
            r = api("sendPhoto", chat_id=chat, photo=FOTOS.get(imatge, imatge),
                    caption=peu if cap else None, parse_mode="HTML" if cap else None)
        except Bloquejat:
            raise
        except Exception as ex:
            registra(f"la gràfica del resum no ha entrat: {ex}")
        else:
            if isinstance(r, dict) and r.get("photo"):
                FOTOS[imatge] = r["photo"][-1]["file_id"]
            if cap:
                return r
    return envia(api, chat, text, html=True)


# --- Menú ----------------------------------------------------------------------

def teclat(sub):
    t = T[sub["idioma"]]
    # Una sola marca: ✓ vol dir sí o triat; sense marca, no (Juanjo, 07-10-2026).
    marca = lambda si: "✓ " if si else ""
    files = [[{"text": marca(x in sub["avisos"]) + t[x], "callback_data": f"t:{x}"}] for x in TIPUS]
    files.append([{"text": t["resum"], "callback_data": "-"}])
    files.append([{"text": marca(sub.get("resum") == h) + t["h"].format(h), "callback_data": f"r:{h}"}
                  for h in HORES_RESUM] + [{"text": marca(not sub.get("resum")) + t["no"], "callback_data": "r:no"}])
    files.append([{"text": marca(sub.get("nit")) + t["nit"], "callback_data": "n:"}])
    files.append([{"text": marca(sub["idioma"] == i) + n, "callback_data": f"i:{i}"}
                  for i, n in (("ca", "Català"), ("es", "Castellano"))])
    return files


def nou_subscriptor(usuari):
    idioma = "es" if (usuari.get("language_code") or "").startswith("es") else "ca"
    return {"idioma": idioma, "avisos": list(PER_DEFECTE), "resum": None,
            "alta": ara().isoformat(timespec="minutes")}


def canvia(sub, dada):
    """Aplica un botón del menú. Devuelve True si cambia algo."""
    tipus, _, valor = dada.partition(":")
    if tipus == "t" and valor in TIPUS:
        sub["avisos"] = [x for x in TIPUS if (x in sub["avisos"]) != (x == valor)]
    elif tipus == "r" and (valor in HORES_RESUM or valor == "no"):
        sub["resum"] = None if valor == "no" else valor
    elif tipus == "n":
        sub["nit"] = not sub.get("nit")
    elif tipus == "i" and valor in T:
        sub["idioma"] = valor
    else:
        return False
    return True


# --- Resumen y tiempo ahora -------------------------------------------------------

def graus(t):
    # Redondeo como Math.round de la web (round() de Python lleva 18,5 a 18).
    return f"{math.floor(t + 0.5)} °C".replace("-", "−")


def _instant(iso):
    """El moment d'una hora de les dades, en UTC; sense zona, la de Madrid."""
    t = dt.datetime.fromisoformat(iso)
    return (t if t.tzinfo else t.replace(tzinfo=ZONA)).astimezone(dt.timezone.utc)


def _seguides(files):
    """[(inici, fi, files)] de les files seguides, unides pel moment i no per
    l'hora de rellotge: la nit del canvi d'hora d'octubre, de 2 a 3 dues
    vegades, no parteix la franja (ADR 0128). Inici i fi, al rellotge de Madrid
    i sense zona, com hora_local."""
    res = []
    for f in files:
        ini = _instant(f["hora"])
        fi = _instant(f["fins"]) if f.get("fins") else ini + dt.timedelta(hours=1)
        if res and res[-1][1] == ini:
            res[-1] = (res[-1][0], fi, res[-1][2] + [f])
        else:
            res.append((ini, fi, [f]))
    return [(a.astimezone(ZONA).replace(tzinfo=None), b.astimezone(ZONA).replace(tzinfo=None), fs)
            for a, b, fs in res]


def franges(hores):
    """[(inici, fi, prob)] de les hores seguides amb risc de pluja."""
    # Como en la web: decide la probabilidad; sin ella, los milímetros.
    def plou(f):
        p = f.get("probabilitat")
        return (p >= 0.2) if p is not None else (f.get("pluja_mm") or 0) >= 0.2
    return [(a, b, max(f.get("probabilitat") or 0 for f in fs)) for a, b, fs in _seguides(filter(plou, hores))]


def plou_ara(dades):
    """Llueve ahora según los datos: en casa o en una vecina que cuenta
    (casa.py; los datos de antes de la 3.46.0 solo tienen la de casa)."""
    if "plou_ara" in dades:
        return bool(dades["plou_ara"])
    return bool((dades.get("ara_casa") or {}).get("plou"))


# --- Icones (Juanjo, 10-10-2026: «que sirvan para leer y entender mejor los
# mensajes, no poner por poner»; ADR 0065) ------------------------------------------
# Telegram només mostra emojis. N'hi ha on diuen el que el text no diu (el cel
# d'ara) o on deixen veure d'una ullada el que s'hauria de llegir línia a línia
# (la pluja, només quan n'hi ha, i els nivells, amb una sola escala de colors).
# Res de temes: cada línia ja comença pel seu rètol.
#
# Els mateixos textos van a «Consultes» de la web (montflorit.py), que hi posa
# les seves icones de Lucide amb colors (ADR 0063) en lloc dels emojis: amb
# ICONES = "web", cada icona surt com una marca, «⟦i-cloud-moon⟧» o «⟦alt⟧»,
# amb la icona exacta, i web/consultes.js la dibuixa.
ICONES = "emoji"
NIVELLS_EMOJI = {"nul": "⚪", "baix": "🟢", "mig": "🟡", "alt": "🟠", "maxim": "🔴", "extrem": "🟣"}


def marca(clau, emoji=None):
    if ICONES == "web":
        return f"⟦{clau}⟧"
    return emoji or NIVELLS_EMOJI.get(clau) or EMOJI_CEL[clau]


class Escala(dict):
    """De cada valor, el seu nivell; en llegir-lo, la marca (emoji o web)."""
    def __getitem__(self, clau):
        return marca(dict.__getitem__(self, clau))

    def get(self, clau, defecte=None):
        return self[clau] if clau in self else defecte


CERCLE = Escala({n: n for n in NIVELLS_EMOJI})
# Els nivells d'avís (AEMET i els propis) en la mateixa escala; el mateix a avisos_bot.py.
CERCLE_AVIS = Escala(groc="mig", taronja="alt", vermell="maxim")
CERCLE_FASE = Escala({"prealerta": "mig", "alerta": "alt", "emergència": "maxim"})

# El cel, amb la mateixa regla que web/casa.js (plujaHora, cel i celNuvols):
# les proves comparen les dues. Les icones de Lucide de la web, en emojis.
PROB_PLUJA = 0.5
PROB_POSSIBLE = 0.2
INTENSITAT_PLUJA = (6, 40, 80)
CASA_COORD = (41.5, 2.1)       # com web/comu.js
ZONA = ZoneInfo("Europe/Madrid")


def hora_local(iso):
    """L'hora d'una fila de la previsió, al rellotge de Madrid i sense zona.
    L'hora que es repeteix a l'octubre arriba amb el desfase
    («…T02:00+01:00», prevision.clau_hora): sense, es podria comparar amb
    les altres i ordenar-les."""
    t = dt.datetime.fromisoformat(iso)
    return t.astimezone(ZONA).replace(tzinfo=None) if t.tzinfo else t


def altura_sol(t):
    """Altura del sol en graus, com alturaSol de web/comu.js."""
    rad = math.pi / 180
    dies = t.timestamp() / 86400 + 2440587.5 - 2451545
    l = (280.46 + 0.9856474 * dies) % 360
    g = ((357.528 + 0.9856003 * dies) % 360) * rad
    lam = (l + 1.915 * math.sin(g) + 0.02 * math.sin(2 * g)) * rad
    eps = (23.439 - 0.0000004 * dies) * rad
    dec = math.asin(math.sin(eps) * math.sin(lam))
    ar = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = (18.697374558 + 24.06570982441908 * dies) % 24
    angle = (gmst * 15 + CASA_COORD[1]) * rad - ar
    lat = CASA_COORD[0] * rad
    return math.asin(math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(angle)) / rad


def pluja_hora(f):
    p = f.get("probabilitat")
    if f.get("plou_ara") or (((f.get("pluja_mm") or 0) >= 0.2) if p is None else p >= PROB_PLUJA):
        return "pluja"
    return "possible" if p is not None and p >= PROB_POSSIBLE else None


def es_neu(c):
    return c is not None and (71 <= c <= 77 or c in (85, 86))


def es_nit(f):
    """De nit, a mitja hora de l'hora (com la web)."""
    t = dt.datetime.fromisoformat(f["hora"])
    t = t if t.tzinfo else t.replace(tzinfo=ZONA)
    return altura_sol(t + dt.timedelta(minutes=30)) < 0


def icona_cel(f):
    """La icona de Lucide que la web posa a l'hora f (cel de web/casa.js)."""
    nit = es_nit(f)
    pluja = pluja_hora(f)
    codi = f.get("codi")
    tempesta = codi is not None and codi >= 95
    if pluja == "pluja":
        if tempesta:
            return "i-cloud-hail" if codi in (96, 99) else "i-cloud-lightning"
        if es_neu(codi):
            return "i-cloud-snow"
        if codi in (56, 57, 66, 67):
            return "i-cloud-rain"
        mm = f.get("pluja_mm") or 0
        if mm >= INTENSITAT_PLUJA[1]:
            return "i-cloud-rain-wind"
        if mm >= INTENSITAT_PLUJA[0]:
            return "i-cloud-rain"
        return "i-cloud-drizzle"
    if pluja == "possible":
        if es_neu(codi):
            return "i-cloud-snow"
        return "i-cloud-moon-rain" if nit else "i-cloud-sun-rain"
    if codi in (45, 48):
        return "i-cloud-fog"
    if f.get("nuvols") is None:
        return None
    n = max(f["nuvols"], 50) if (f.get("pluja_mm") or 0) >= 0.2 else f["nuvols"]
    if n < 20:
        return "i-moon-cel" if nit else "i-sun"
    if n < 45:
        return "i-cloud-moon" if nit else "i-cloud-sun"
    return "i-cloud" if n < 70 else "i-cloudy"


# Mig ennuvolat: de dia, el sol rere el núvol, que és com tothom el coneix; de
# nit no hi ha emoji de lluna amb núvol, i amb pocs núvols es queda la lluna.
EMOJI_CEL = {"i-sun": "☀️", "i-moon-cel": "🌙", "i-cloud-sun": "🌤️", "i-cloud-moon": "🌙", "i-cloud": "⛅",
             "i-cloudy": "☁️", "i-cloud-fog": "🌫️", "i-cloud-sun-rain": "🌦️", "i-cloud-moon-rain": "🌧️",
             "i-cloud-drizzle": "🌧️", "i-cloud-rain": "🌧️", "i-cloud-rain-wind": "🌧️", "i-cloud-snow": "🌨️",
             "i-cloud-lightning": "⛈️", "i-cloud-hail": "⛈️", "i-umbrella": "☔"}
# De menys a més: la icona de la línia de la pluja és la de l'hora pitjor.
ORDRE_PLUJA = ("i-cloud-moon-rain", "i-cloud-sun-rain", "i-cloud-drizzle", "i-cloud-rain", "i-cloud-rain-wind",
               "i-cloud-snow", "i-cloud-lightning", "i-cloud-hail")


def emoji_cel(f):
    i = icona_cel(f)
    if not i:
        return None
    return marca(i, "☁️" if i == "i-cloud" and es_nit(f) else None)


def emoji_pluja(tram):
    """La de l'hora amb la pluja pitjor; cap si no se n'espera."""
    ids = [i for i in (icona_cel(f) for f in tram if pluja_hora(f)) if i in ORDRE_PLUJA]
    return marca(max(ids, key=ORDRE_PLUJA.index)) if ids else None


def amb_icona(icona, text):
    return f"{icona} {text}" if icona and text else text


def hora_ara(dades, moment):
    # Pel moment, no per l'hora de rellotge: la primera de 2 a 3 d'octubre
    # acaba a les 2 i no es trobava mai (ADR 0128).
    ara_u = moment.astimezone(dt.timezone.utc)
    for f in dades.get("hores") or []:
        if _instant(f["hora"]) <= ara_u < _instant(f["fins"]):
            return f
    return None


def text_ara(dades, idioma, lloc="", moment=None):
    """Como la web: la temperatura y la lluvia de la estación particular del
    barrio («plou» si ha recogido lluvia en los últimos minutos, o si lo ha
    hecho una vecina de Weather Underground que cuenta; ADR 0058 y 0060)."""
    c = dades.get("ara_casa") or {}
    t = c.get("temperatura")
    if t is None:
        return None
    plou = plou_ara(dades)
    # El cel de l'hora, el de la taula de la web; si plou, el paraigua, com allà.
    f = hora_ara(dades, moment or ara())
    # Si no plou, el cel sense pluja: «no plou» amb un núvol de pluja es
    # contradeia (inventari del 18-10-2026).
    icona = marca("i-umbrella") if plou else (f and (marca("i-cloud") if icona_cel(f) in ORDRE_PLUJA
                                                     else emoji_cel(f)))
    # Plugim que només veu el radar, com a la web (Juanjo, 18-10-2026; ADR 0019).
    plugim = not plou and (dades.get("pluja_ara") or {}).get("plugim")
    if idioma == "es":
        que = "llueve" if plou else "llovizna según el radar" if plugim else "no llueve"
        return amb_icona(icona, f"Ahora mismo{lloc and ' en ' + lloc}: {graus(t)}, {que}.")
    que = "plou" if plou else "plugim segons el radar" if plugim else "no plou"
    return amb_icona(icona, f"Ara mateix{lloc and ' a ' + lloc}: {graus(t)}, {que}.")


def text_pluja_prevista(dades, idioma, moment):
    """La primera hora de les 24 que venen amb pluja segons la previsió (del
    20 %, com «possible pluja»): «Pluja prevista d'aquí a unes 6 hores, cap a
    les 20 h (73 %).». La previsió és per hores: sense minuts."""
    # Les hores que falten, pel moment (el dia del canvi d'hora, el rellotge
    # en diria una de més o de menys); l'hora que es diu, la de Madrid.
    ara_u = moment.astimezone(dt.timezone.utc)
    for f in dades.get("hores") or []:
        ini_u = _instant(f["hora"])
        if not (ara_u < ini_u <= ara_u + dt.timedelta(hours=24)) or not pluja_hora(f):
            continue
        ini = hora_local(f["hora"])
        h = round((ini_u - ara_u).total_seconds() / 3600)
        p = f.get("probabilitat")
        pct = f" ({math.floor(p * 100 + 0.5)} %)" if p is not None else ""
        segura = p is None or p >= 0.5
        if idioma == "es":
            quan = "dentro de menos de una hora" if h < 1 else "dentro de una hora" if h == 1 else f"dentro de unas {h} horas"
            return f"{'Lluvia prevista' if segura else 'Posible lluvia'} {quan}, hacia las {ini.hour} h{pct}."
        quan = "d'aquí a menys d'una hora" if h < 1 else "d'aquí a una hora" if h == 1 else f"d'aquí a unes {h} hores"
        return f"{'Pluja prevista' if segura else 'Possible pluja'} {quan}, cap a les {ini.hour} h{pct}."
    return None


def text_ara_bot(dades, idioma, moment):
    """La respuesta a /ara: como text_ara, pero con el mismo límite de edad
    que el resumen, también para la propia medida, y diciendo de qué hora es
    (auditoría del 07-10-2026)."""
    t = T[idioma]
    generat = dades.get("generat") and dt.datetime.fromisoformat(dades["generat"])
    if not generat or moment - generat > dt.timedelta(hours=DADES_VELLES_H):
        return t["velles_ara"].format(generat.strftime("%H:%M") if generat else "?")
    hora = (dades.get("ara_casa") or {}).get("hora")
    mesura = hora and dt.datetime.fromisoformat(hora)
    if mesura and moment - mesura > dt.timedelta(hours=DADES_VELLES_H):
        return t["velles_ara"].format(mesura.strftime("%H:%M"))
    text = text_ara(dades, idioma, "", moment)
    if not text:
        return t["ajuda"]
    # Com la targeta «Ara» de la web, en el mateix ordre (Juanjo, 17-10-2026:
    # «en el de /ara da muy poca información»), i l'hora de la mesura a la
    # capçalera, no enganxada al final.
    es = idioma == "es"
    c = dades.get("ara_casa") or {}
    cap = "<b>Ahora en Montflorit</b>" if es else "<b>Ara a Montflorit</b>"
    linies = [cap + (t["mesura"].format(mesura.strftime("%H:%M")) if mesura else ""),
              text.replace("Ahora mismo: ", "").replace("Ara mateix: ", "")]
    alta = c.get("dif_alta")
    if alta is not None and abs(alta) >= 0.5:
        r = int(math.copysign(math.floor(abs(alta) + 0.5), alta))
        linies.append(f"En la parte alta, {abs(r)} °C {'más' if r > 0 else 'menos'}." if es
                      else f"A la part alta, {abs(r)} °C {'més' if r > 0 else 'menys'}.")
    r = dades.get("radar") or {}
    if r.get("arriba") or r.get("possible") or (plou_ara(dades) and r.get("fi")):
        linies.append(amb_icona("🌧️", text_radar_bot(dades, idioma, moment).split("\n")[0]))
    elif not plou_ara(dades):
        # Si el radar no la veu, quan la dona la previsió (Juanjo, 17-10-2026).
        prevista = text_pluja_prevista(dades, idioma, moment)
        if prevista:
            linies.append(amb_icona("🌧️", prevista))
    if c.get("pluja_avui") is not None:
        mm = f"{c['pluja_avui']:.1f}".replace(".", ",").replace(",0", "")
        linies.append(amb_icona("🌧️", f"Lluvia de hoy: {mm} mm." if es else f"Pluja d'avui: {mm} mm."))
    v = dades.get("vent") or {}
    if v.get("mitja") is not None:
        ratxa = (f", rachas de {round(v['ratxa'])} km/h" if es else f", ratxes de {round(v['ratxa'])} km/h") \
            if v.get("ratxa") is not None else ""
        linies.append(amb_icona("💨", f"{'Viento' if es else 'Vent'}: {round(v['mitja'])} km/h{ratxa}."))
    altres = []
    if c.get("humitat") is not None:
        altres.append(f"{'Humedad' if es else 'Humitat'} {round(c['humitat'])} %")
    if c.get("pressio") is not None:
        p = f"{'presión' if es else 'pressió'} {round(c['pressio'])} hPa"
        d = c.get("pressio_3h")
        if d is not None:
            if abs(d) < 1:
                p += ", estable"
            else:
                p += (", subiendo" if d > 0 else ", bajando") if es else (", pujant" if d > 0 else ", baixant")
                if abs(d) >= 3.6:
                    p += " rápido" if es else " ràpid"
        altres.append(p)
    if altres:
        linies.append(amb_icona("💧", " · ".join(altres) + "."))
    # Els avisos, només si n'hi ha: quants i on es miren, amb el color del primer.
    perills = linies_perill_dia(dades, idioma, moment.date(), moment)
    if perills:
        marca_ = perills[0].split(" ", 1)[0]
        n = len(perills)
        quants = (f"{n} avisos activos" if n > 1 else "1 aviso activo") if es else \
            (f"{n} avisos actius" if n > 1 else "1 avís actiu")
        linies.append(f"{marca_} {quants}: /avisos_actius")
    return "\n".join(linies)


DIES = {"ca": ("dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"),
        "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")}
# A partir de esta hora, la previsión es para el día siguiente.
HORA_DEMA = 18


def text_franges(pluges, idioma):
    """«pluja de 7 a 10 h (probabilitat fins al 95 %); possible pluja de 18 a 19 h
    (fins al 25 %)», en minúscula. Les paraules, les de la columna «Cel» de la
    web: «pluja» des del 50 %, «possible pluja» des del 20 % (Juanjo,
    12-10-2026: deia «possible» amb un 95 %)."""
    es = idioma == "es"
    parts = []
    for n, (a, b, p) in enumerate(pluges):
        nom = ("lluvia" if es else "pluja") if p >= 0.5 else ("posible lluvia" if es else "possible pluja")
        prob = ((f"probabilidad hasta el {math.floor(p * 100 + 0.5)} %" if es else f"probabilitat fins al {math.floor(p * 100 + 0.5)} %") if not n
                else (f"hasta el {math.floor(p * 100 + 0.5)} %" if es else f"fins al {math.floor(p * 100 + 0.5)} %"))
        parts.append(f"{nom} de {a.hour} a {b.hour} h ({prob})")
    return "; ".join(parts)


def text_paraigua(hores, idioma, nit=None):
    """«Paraigua de 18 a 0 h.», a continuació de la roba per anar a peu, amb
    les mateixes hores que la línia de la pluja (des del 20 %, el «si surts,
    porta paraigua» de la web). Sense pluja, res (Juanjo, 17-10-2026: «si hoy
    va a llover, por qué no recomienda paraguas?»). La de demà, amb la nit
    davant i sense hores («Paraigua aquesta nit i de 6 a 15 h.»): les hores de
    la nit ja són a la seva línia, i «de 18 a 15 h» no s'entenia."""
    trams = [f"de {a.hour} a {b.hour} h" for a, b, _ in franges(hores)]
    if nit and franges(nit):
        trams.insert(0, "esta noche" if idioma == "es" else "aquesta nit")
    if not trams:
        return None
    i = " y " if idioma == "es" else " i "
    hores_txt = trams[0] if len(trams) == 1 else ", ".join(trams[:-1]) + i + trams[-1]
    return ("Paraguas " if idioma == "es" else "Paraigua ") + hores_txt + "."


# Els avisos oficials per pluja de les hores (els que pinta la taula), com
# avisPluja de web/sortir.js.
TIPUS_AVIS_PLUJA = {"pluja", "tempestes", "temps_violent"}


def hores_avis_pluja(files):
    """[(inici, fi)] de les hores seguides amb avís oficial per pluja."""
    return [(a, b) for a, b, _ in _seguides(
        f for f in files if any(set(a.get("tipus") or []) & TIPUS_AVIS_PLUJA for a in f.get("avisos") or []))]


def text_pluja(tram, idioma, icona=True, avis=None):
    """Sense pluja, sense icona: la línia destaca només quan n'hi ha (ADR 0065).
    Si la previsió no en dona però hi ha avís oficial per pluja (avis: les
    hores on mirar-lo, per defecte el tram), es diu (revisor, 19-10-2026:
    «Sense pluja prevista» per a demà amb avisos de Meteocat i AEMET de 0 a 9 h)."""
    pluges = franges(tram)
    if not pluges:
        es = idioma == "es"
        trams = [f"de {a.hour} a {b.hour} h" for a, b in hores_avis_pluja(tram if avis is None else avis)]
        if trams:
            quan = (" y " if es else " i ").join(trams)
            return (f"La previsión no da lluvia, pero hay aviso oficial por lluvia {quan}." if es
                    else f"La previsió no dona pluja, però hi ha avís oficial per pluja {quan}.")
        return "Sin lluvia prevista." if es else "Sense pluja prevista."
    text = text_franges(pluges, idioma)
    return amb_icona(emoji_pluja(tram) if icona else None, text[0].upper() + text[1:] + ".")


# Cuántos grados más o menos que el día anterior (Juanjo, 10-10-2026: «la
# mayoría de predicciones de otros servicios lo llevan y es muy útil»; ADR
# 0061): lo previsto, con las mismas horas del día antes, medidas en casa o,
# si aún no han pasado, previstas. La máxima de día y la mínima de noche, y la
# cifra solo desde COMPARA_MIN grados: la previsión se equivoca en torno a uno.
# Lo mismo en web/casa.js, que las pruebas comparan.
COMPARA_MIN = 2


def _rellotge(clau):
    """La clau en hora de rellotge de Madrid, sense zona: «2026-10-25T07:00»
    (les dades porten el desfasament, ADR 0128)."""
    return hora_local(clau).strftime("%Y-%m-%dT%H:%M")


def _dia_abans(clau):
    return (hora_local(clau) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")


def compara_temp(dades, files, nit=False):
    """Grados de diferencia (redondeados) entre lo previsto en «files» y las
    mismas horas del día antes; None si falta algún dato."""
    mesurada = {_rellotge(k): v for k, v in (dades.get("temperatura_mesurada") or {}).items()}
    if not mesurada or not files:
        return None
    previstes = {_rellotge(f["hora"]): f for f in dades.get("hores") or []}
    abans, ara = [], []
    for f in files:
        a, b = mesurada.get(_dia_abans(f["hora"])), mesurada.get(_dia_abans(f["fins"]))
        v = (a + b) / 2 if a is not None and b is not None else (previstes.get(_dia_abans(f["hora"])) or {}).get("temperatura")
        if v is None or f.get("temperatura") is None:
            return None
        abans.append(v)
        ara.append(f["temperatura"])
    # Se restan las cifras ya redondeadas, las que se leen en las cabeceras
    # (revisor, 19-10-2026: 15–18 frente a 14–19 decía «2° més»).
    r = lambda x: math.floor(x + 0.5)
    return (r(min(ara)) - r(min(abans))) if nit else (r(max(ara)) - r(max(abans)))


# Les hores de dia de les capçaleres (Matí i Tarda, TRAMS de web/casa.js).
TRAM_DIA = (7, 21)


def compara_resum(dades, files):
    """La comparació d'un resum que travessa trams, amb el criteri de les
    capçaleres (revisor, 19-10-2026: «2 graus més que ahir» amb Tarda i Nit
    «semblant», per una màxima que queia passades les 21 h): si queden hores
    de dia, la màxima d'aquestes hores; si no, la mínima de la nit fins a les 7."""
    dia = [f for f in files if TRAM_DIA[0] <= hora_local(f["hora"]).hour < TRAM_DIA[1]]
    if dia:
        return compara_temp(dades, dia)
    if not files:
        return None
    ini = hora_local(files[0]["hora"])
    fi = (ini if ini.hour < TRAM_DIA[0] else ini + dt.timedelta(days=1)).replace(hour=TRAM_DIA[0], minute=0)
    return compara_temp(dades, [f for f in dades.get("hores") or [] if ini <= hora_local(f["hora"]) < fi], nit=True)


def text_comparacio(n, idioma, respecte):
    """«, 3 graus més que ahir», «, semblant a la d'avui»… (respecte: «ahir» o «avui»)."""
    if n is None:
        return ""
    if idioma == "es":
        dia = {"ahir": "ayer", "avui": "hoy"}[respecte]
        if abs(n) < COMPARA_MIN:
            return f", parecida a la de {dia}"
        return f", {abs(n)} grados {'más' if n > 0 else 'menos'} que {dia}"
    if abs(n) < COMPARA_MIN:
        return ", semblant a la d'ahir" if respecte == "ahir" else ", semblant a la d'avui"
    return f", {abs(n)} graus {'més' if n > 0 else 'menys'} que {respecte}"


def text_alta(tram, idioma):
    """« (fins a 26 °C a la part alta)»: la màxima a la part alta del barri,
    si es separa un grau o més (arrodonit) de la de vora la riera (ADR 0087;
    Juanjo, 13-10-2026: «0.9 yo lo consideraría como 1»)."""
    files = [f for f in tram if f.get("temperatura") is not None]
    if not files:
        return ""
    alta = max(f["temperatura"] + (f.get("dif_alta") or 0) for f in files)
    maxima = max(f["temperatura"] for f in files)
    # La xifra de dalt és la màxima arrodonida més la diferència arrodonida,
    # com «18 °C» i «+2» a les files dels trams (arrodoneixAlta, grafica.js):
    # arrodonir la suma donava «fins a 21 °C» amb 18,2 i 2,4, i a les files es
    # llegia 20 (revisor, 20-10-2026). Si la diferència arrodonida és zero,
    # «entre 11 °C i 16 °C (fins a 16 °C…)» repetiria la xifra (Juanjo,
    # 20-10-2026: «el 2º 16 sobra»).
    d = alta - maxima
    r = int(math.copysign(math.floor(abs(d) + 0.5), d))
    if r == 0:
        return ""
    xifra = graus(math.floor(maxima + 0.5) + r)
    return f" (hasta {xifra} en la parte alta)" if idioma == "es" else f" (fins a {xifra} a la part alta)"


def text_temperatura(tram, idioma, quan, comparacio=None, respecte="ahir", ara=None):
    # Amb la d'ara, la mesurada: la de les hores és prevista, i «entre 12 i
    # 17 °C» amb 17,5 °C a «Ara» es contradeia (inventari del 18-10-2026).
    temps = [f["temperatura"] for f in tram if f.get("temperatura") is not None] + ([ara] if ara is not None else [])
    i = " y " if idioma == "es" else " i "
    if not temps:
        return None
    alta = text_alta(tram, idioma)
    # Si la mínima i la màxima coincideixen, una xifra: «16 °C», no «entre 16 °C i 16 °C» (ADR 0074).
    if graus(min(temps)) == graus(max(temps)):
        return f"{quan}: {graus(min(temps))}{alta}{text_comparacio(comparacio, idioma, respecte)}."
    return f"{quan}: entre {graus(min(temps))}{i}{graus(max(temps))}{alta}{text_comparacio(comparacio, idioma, respecte)}."


# La ropa para ir a pie, con los mismos tramos que «Si surts» (web/sortir.js,
# ADR 0029): temperatura que se nota con el viento previsto, redondeada. Las
# pruebas comprueban que las dos tablas dicen lo mismo.
ROBA = ((0, "Abric, gorro, bufanda i guants", "Abrigo, gorro, bufanda y guantes"),
        (5, "Abric, bufanda i guants", "Abrigo, bufanda y guantes"),
        (10, "Abric", "Abrigo"),
        (14, "Jaqueta", "Chaqueta"),
        (17, "Jaqueta lleugera o jersei", "Chaqueta ligera o jersey"),
        (20, "Màniga llarga o jersei fi", "Manga larga o jersey fino"),
        (24, "Màniga curta o màniga llarga fina", "Manga corta o manga larga fina"),
        (None, "Màniga curta", "Manga corta"))
# Las horas en que se sale de casa: de 7 a 21 h.
HORES_ROBA = range(7, 22)


def es_nota(t, kmh):
    """Índice de Environment Canada: solo con 10 °C o menos y viento."""
    if t > 10 or kmh < 5:
        return t
    v = kmh ** 0.16
    return 13.12 + 0.6215 * t - 11.37 * v + 0.3965 * t * v


# La frase de la targeta «Ara» de la web (casa.fraseCelAra, ADR 0118), per als
# resums d'avui i de demà: com es nota cada tram i el cel (Juanjo, 23-10-2026:
# «cuando envias las alertas de hoy, podrías poner el texto que pones de si
# hará fresco… solo el de hoy. Y cuando envias el de mañana, también»). El
# mateix compte que la web, a la riera, com la resta del resum.
TRAMS_FRASE = ((7, 14, "Matí"), (14, 21, "Tarda"), (21, 7, "Nit"))
SENSACIO = ((-1, "fred intens"), (5, "molt fred"), (11, "fred"), (17, "fresc"), (25, "agradable"),
            (32, "calor"), (math.inf, "molta calor"))
PARAULA_SENSACIO = {
    "ca": {"fred intens": "amb fred intens", "molt fred": "amb molt de fred", "fred": "fred", "fresc": "fresc",
           "agradable": "temperatura agradable", "calor": "amb calor", "molta calor": "amb molta calor"},
    "es": {"fred intens": "con frío intenso", "molt fred": "con mucho frío", "fred": "frío", "fresc": "fresco",
           "agradable": "temperatura agradable", "calor": "con calor", "molta calor": "con mucho calor"},
}
CEL_FRASE = {"ca": ("serè", "poc ennuvolat", "mig ennuvolat", "molt ennuvolat", "cobert", "boira"),
             "es": ("despejado", "poco nuboso", "nuboso", "muy nuboso", "cubierto", "niebla")}
QUAN_FRASE = {"ca": {"Matí": "Aquest matí", "Tarda": "Aquesta tarda", "Nit": "Aquesta nit"},
              "es": {"Matí": "Esta mañana", "Tarda": "Esta tarde", "Nit": "Esta noche"}}
# Al resum de demà el títol ja diu que és demà.
QUAN_FRASE_DEMA = {"ca": {"Matí": "Al matí", "Tarda": "A la tarda", "Nit": "A la nit"},
                   "es": {"Matí": "Por la mañana", "Tarda": "Por la tarde", "Nit": "Por la noche"}}


def tram_frase(f):
    """(dia, nom) del tram de l'hora, com casa.tramDe: la nit de matinada és del dia abans."""
    t = hora_local(f["hora"])
    nom = next(n for a, b, n in TRAMS_FRASE if (a <= t.hour < b if a < b else (t.hour >= a or t.hour < b)))
    dia = t.date() - dt.timedelta(days=1) if nom == "Nit" and t.hour < 7 else t.date()
    return dia, nom


def cel_frase(files, idioma):
    """El cel del tram en paraules (casa.celTram): boira si n'hi ha la major
    part de les hores; si no, la mitjana dels núvols (com a icona_cel)."""
    if sum(1 for f in files if f.get("codi") in (45, 48)) * 2 > len(files):
        return CEL_FRASE[idioma][5]
    n = [max(f["nuvols"], 50) if (f.get("pluja_mm") or 0) >= 0.2 else f["nuvols"] for f in files if f.get("nuvols") is not None]
    if not n:
        return None
    m = sum(n) / len(n)
    return CEL_FRASE[idioma][0 if m < 20 else 1 if m < 45 else 2 if m < 70 else 3 if m < 85 else 4]


def sensacio_tram(files, nom):
    """Com es nota el tram (casa.sensacioTram): la temperatura que es nota,
    arrodonida; la màxima a la tarda i la mínima a la nit i al matí, i al
    matí, si després escalfa fins a un altre nivell, «inici>després»."""
    notes = [es_nota(f["temperatura"], f.get("vent") or 0) for f in files if f.get("temperatura") is not None]
    if not notes:
        return None
    nivell = lambda v: next(n for fins, n in SENSACIO if math.floor(v + 0.5) <= fins)
    if nom == "Tarda":
        return nivell(max(notes))
    inici = nivell(min(notes))
    if nom != "Matí":
        return inici
    despres = nivell(max(notes[notes.index(min(notes)):]))
    return inici if despres == inici else f"{inici}>{despres}"


def text_sensacio(s, idioma, encara=False):
    inici, _, despres = s.partition(">")
    p = PARAULA_SENSACIO[idioma]
    primera = (("todavía " if idioma == "es" else "encara ") + p[inici]) if encara else p[inici]
    if not despres:
        return primera
    segona = "agradable" if despres == "agradable" else p[despres]
    return f"{primera} {'y después' if idioma == 'es' else 'i després'} {segona}"


def frase_cel(hores, idioma, dia, dema=False):
    """La frase per als trams del dia (per a avui, els que queden, també la
    nit; per a demà, els de demà): «Aquest matí, fresc i després agradable,
    i molt ennuvolat; aquesta tarda, temperatura agradable i poc ennuvolat.»
    Els trams seguits amb el mateix cel i la mateixa sensació, junts; «encara»
    si la sensació continua. None sense dades."""
    i_ = "y" if idioma == "es" else "i"
    grups = []
    for f in hores:
        d, nom = tram_frase(f)
        if (d == dia) if dema else (d <= dia):
            if not grups or grups[-1][0] != (d, nom):
                grups.append([(d, nom), []])
            grups[-1][1].append(f)
    # El tram en curs, si només li queda una hora, ja no és el que ve (casa.tramsFrase).
    if len(grups) > 1 and len(grups[0][1]) <= 1:
        grups = grups[1:]
    quan = (QUAN_FRASE_DEMA if dema else QUAN_FRASE)[idioma]
    parts = [[quan[nom], cel_frase(fs, idioma), sensacio_tram(fs, nom)] for (_, nom), fs in grups]
    parts = [p for p in parts if p[1]]
    if not parts:
        return None
    junts = []
    for p in parts:
        if junts and junts[-1][1:] == p[1:]:
            junts[-1][0] += f" {i_} {p[0][0].lower()}{p[0][1:]}"
        else:
            junts.append(list(p))
    amb = lambda cel, s, encara: cel if not s else (
        f"{text_sensacio(s, idioma, encara)}, {i_} {cel}" if ">" in s else f"{text_sensacio(s, idioma, encara)} {i_} {cel}")
    trossos = []
    for n, (q, cel, s) in enumerate(junts):
        encara = bool(n and s and s.split(">")[0] == junts[n - 1][2])
        trossos.append(f"{q if not n else q[0].lower() + q[1:]}, {amb(cel, s, encara)}")
    return "; ".join(trossos) + "."


def peca(s, idioma):
    for fins, ca, es in ROBA:
        if fins is None or s <= fins:
            return es if idioma == "es" else ca


def text_roba(tram, idioma):
    """La ropa para todo el día: si el momento más frío y el más caluroso
    piden prendas distintas, las dos, por orden de hora."""
    hores = []
    for f in tram:
        h = hora_local(f["hora"])
        if f.get("temperatura") is not None and h.hour in HORES_ROBA:
            # Redondeo como Math.round de la web (round() de Python lleva 14,5 a 14).
            s = math.floor(es_nota(f["temperatura"], f.get("vent") or 0) + 0.5)
            hores.append((h, f["temperatura"], s))
    if not hores:
        return None
    fred, calor = min(hores, key=lambda x: x[2]), max(hores, key=lambda x: x[2])
    cap = "Ropa para ir a pie: " if idioma == "es" else "Roba per anar a peu: "
    if peca(fred[2], idioma) == peca(calor[2], idioma):
        return cap + peca(fred[2], idioma).lower() + "."

    # Primer l'hora i la temperatura i després la peça: amb la peça davant,
    # «màniga curta» quedava rere «(10 °C);» i semblava que hi anés (Juanjo,
    # 10-10-2026: «manga corta para 10º?»).
    def moment(x):
        h, t, s = x
        nota = (f", se notan como {graus(s)}" if idioma == "es" else f", es noten com {graus(s)}") \
            if s < math.floor(t + 0.5) else ""
        a = "a las" if idioma == "es" else "a les"
        return f"{a} {h.hour} h ({graus(t)}{nota}), {peca(s, idioma).lower()}"
    return cap + "; ".join(moment(x) for x in sorted((fred, calor))) + "."


def text_avisos_aemet(dades, idioma, dia, moment):
    """Los avisos de AEMET de un día: hoy, «fins a les 20:00»; mañana, «de 10:00 a 20:00»."""
    # Els que toquen el dia (també els que van començar abans: auditoria del 08-10-2026).
    inici_dia = dt.datetime.combine(dia, dt.time.min, tzinfo=moment.tzinfo)
    # Sense els que cobreix Meteocat: llavors surt el seu (ADR 0093).
    # I dels que cobreix en part, només les hores que no cobreix (smp.visible;
    # el bot viu a IONOS sense els mòduls del projecte).
    visibles = [{**a, "inicio": a.get("inicio_visible") or a["inicio"], "fin": a.get("fin_visible") or a["fin"]}
                for a in dades.get("avisos") or [] if not a.get("cobert")]
    avisos = [a for a in visibles if dt.datetime.fromisoformat(a["fin"]) > max(moment, inici_dia)
              and dt.datetime.fromisoformat(a["inicio"]) < inici_dia + dt.timedelta(days=1)]
    res = []
    for nivell in ("vermell", "taronja", "groc"):
        dels = [a for a in avisos if a["nivel"] == nivell]
        if not dels:
            continue
        tipus = sorted({a["tipo"] for a in dels})
        inici = min(dt.datetime.fromisoformat(a["inicio"]) for a in dels)
        ini = inici.strftime("%H:%M")
        # Avui, «fins a les…» només si ja ha començat; si comença més tard, de quina a quina.
        ja = dia == moment.date() and inici <= moment
        fi = (max(dt.datetime.fromisoformat(a["fin"]) for a in dels) + dt.timedelta(seconds=1)).strftime("%H:%M")
        if idioma == "es":
            nom = {"vermell": "rojo", "taronja": "naranja", "groc": "amarillo"}[nivell]
            que = " y ".join(TIPUS_AEMET_ES.get(x, x) for x in tipus)
            quan = f"hasta las {fi}" if ja else f"de {ini} a {fi}"
            res.append(f"{CERCLE_AVIS[nivell]} AEMET: aviso {nom} por {que} en el Vallès {quan}.")
        else:
            quan = f"fins a les {fi}" if ja else f"de {ini} a {fi}"
            que = " i ".join(TIPUS_AEMET_CA.get(x, x) for x in tipus)
            res.append(f"{CERCLE_AVIS[nivell]} AEMET: avís {nivell} per {que} al Vallès {quan}.")
    return res


# Els tipus de l'AEMET (prevision.TIPUS_METEOALARM; els mateixos noms que
# avisos_bot.TIPUS_AEMET: el bot no carrega els mòduls del repositori).
TIPUS_AEMET_CA = {"incendis": "risc d'incendis", "costaners": "fenòmens costaners", "altres": "altres fenòmens"}
TIPUS_AEMET_ES = {"pluja": "lluvia", "tempestes": "tormentas", "inundacions": "inundaciones", "vent": "viento",
                  "calor": "calor", "fred": "frío", "neu": "nieve", "boira": "niebla", "incendis": "riesgo de incendios",
                  "costaners": "fenómenos costeros", "allaus": "aludes", "pols": "polvo", "altres": "otros fenómenos"}

# --- Totes les alertes de perill, juntes (ADR 0093) -------------------------------
# Cada lloc que diu les alertes (/avisos_actius, el resum del dia al bot i a
# «Consultes», la portada, «Si surts» i «Perill») les ha de dir totes. Els
# tipus són aquests, en aquest ordre; tests/test_perills.py comprova que cada
# lloc en diu un de cada i que tot avís de perill de avisos_bot.py en té un.
TIPUS_PERILL = ("pla", "meteocat", "aemet", "riera", "incendi", "alfa", "propi")


def hores_dia(franges, dia, moment, idioma):
    """[[12, 24]] → «de 12:00 a 00:00»; avui, si ja ha començat, «fins a les 00:00»."""
    es = idioma == "es"
    parts = []
    for a, b in franges:
        fi = f"{b % 24:02d}:00"
        if dia == moment.date() and a <= moment.hour:
            parts.append(f"hasta las {fi}" if es else f"fins a les {fi}")
        else:
            parts.append(f"de {a:02d}:00 a {fi}")
    return (" y " if es else " i ").join(parts)


def linies_perill_dia(dades, idioma, dia, moment):
    """Totes les alertes de perill d'un dia, una línia cadascuna, per al resum
    (Juanjo, 16-10-2026: «las alertas de peligro deben ir siempre juntas»).
    Les que no tenen hora (els plans) surten avui i demà; les que diuen el que
    passa ara (riera, incendis), només avui."""
    es = idioma == "es"
    avui = dia == moment.date()
    res = []
    for p in dades.get("plans") or []:
        if es:
            frase = (f"Protección Civil: plan {PLA_ES.get(p['nom'], p['nom'])} ({p['pla']}) en fase de "
                     f"{FASE_ES.get(p['fase'], p['fase'])}.")
        else:
            de = "d'" if p["fase"][:1] in "aeiouàèéíòóú" else "de "
            frase = f"Protecció Civil: pla {p['nom']} ({p['pla']}) en fase {de}{p['fase']}."
        res.append(amb_icona(CERCLE_FASE.get(p["fase"]), html.escape(frase, quote=False)))
    for f in (dades.get("smp") or {}).get("fenomens") or []:
        franges = f["dies"].get(dia.isoformat())
        if franges:
            res.append(amb_icona(CERCLE.get(f["nivell"]),
                                 html.escape(f"{f[idioma]} {hores_dia(franges, dia, moment, idioma)}.", quote=False)))
    res += [html.escape(x, quote=False) for x in text_avisos_aemet(dades, idioma, dia, moment)]
    if avui:
        res += [amb_icona(CERCLE.get(r.get("nivell")), html.escape(r[idioma].rstrip(".") + ".", quote=False))
                for r in dades.get("perill_riera") or []]
        for _, linies in blocs_entorn({**(dades.get("entorn") or {}), "pla_alfa": None}, idioma):
            res += [l for l in linies if not l.startswith("<a ")]
    alfa = (dades.get("entorn") or {}).get("pla_alfa") or {}
    n = alfa.get("avui" if avui else "dema") if dia in (moment.date(), moment.date() + dt.timedelta(days=1)) else None
    if n is not None and n >= ALFA_NIVELL_MOSTRAR:
        quan = ("hoy" if es else "avui") if avui else ("mañana" if es else "demà")
        res.append(amb_icona(CERCLE["maxim"] if n >= 4 else CERCLE["alt"],
                             html.escape(("Plan Alfa: " if es else "Pla Alfa: ")
                                         + ALFA[idioma].format(n=n, quan=quan)[0].lower() + ALFA[idioma].format(n=n, quan=quan)[1:],
                                         quote=False)))
    riscos = [r for r in dades.get("riscos") or []
              if (r.get("origen") != "previsio" and avui)
              or (r.get("des_de") and dt.datetime.fromisoformat(r["des_de"]).date() <= dia
                  <= dt.datetime.fromisoformat(r["fins"]).date())]
    propis = linies_riscos(riscos, idioma, moment)
    if propis:
        # Qui avisa, primer, com als avisos (Juanjo, 17-10-2026).
        nota = " (no oficial)" if es else " (no oficial)"
        for x in propis:
            icona, _, text = x.partition(" ") if x[:1] and not x[:1].isalnum() else ("", "", x)
            text = "Temps a Montflorit: " + text[:1].lower() + text[1:]
            text = text[:-1] + nota + "." if text.endswith(".") else text + nota
            res.append(amb_icona(icona, text))
    return res


def resum(dades, idioma, moment, dema=False, avui=False, telegram=False):
    """La previsión en pocas líneas, con los datos públicos: hasta las 18 h,
    el tiempo ahora y el resto del día; desde las 18 h, la de mañana. Con la
    ropa para ir a pie (text_roba)."""
    t = T[idioma]
    if not dades.get("generat"):
        return t["velles"].format("?")
    generat = dt.datetime.fromisoformat(dades["generat"])
    if moment - generat > dt.timedelta(hours=DADES_VELLES_H):
        return t["velles"].format(generat.strftime("%H:%M"))
    ara_n = moment.replace(tzinfo=None)
    hores = [f for f in dades.get("hores") or [] if hora_local(f["fins"]) > ara_n]
    hora = lambda f: hora_local(f["hora"])
    # /resum demana sempre la d'avui, /dema la de demà; el resum programat
    # canvia a demà a partir de HORA_DEMA (Juanjo, 08-10-2026).
    if dema or (moment.hour >= HORA_DEMA and not avui):
        dema = (moment + dt.timedelta(days=1)).date()
        # La nit comença a les HORA_DEMA d'avui, també si es demana /dema al matí.
        vespre = dt.datetime.combine(moment.date(), dt.time(HORA_DEMA))
        nit = [f for f in hores if vespre <= hora(f) < dt.datetime.combine(dema, dt.time(6))]
        dia = [f for f in hores if hora(f).date() == dema and hora(f).hour >= 6]
        nom_dia = DIES[idioma][dema.weekday()]
        if not dia:     # sense hores de demà, no hi ha previsió, i es diu (auditoria del 08-10-2026)
            return t["sense_previsio"].format(generat.strftime("%H:%M")) + "\n" + WEB
        # Les dades arriben fins a les 21 h de demà (ADR 0041): demà, el matí i
        # la tarda, és sencer. Si no hi arriben (dades d'abans), es diu fins on.
        fi = dt.datetime.fromisoformat(dia[-1]["fins"]).hour if dia else 0
        fins = (f" (hasta las {fi} h)" if idioma == "es" else f" (fins a les {fi} h)") if 0 < fi < 21 else ""
        linies = [(f"<b>Previsión para mañana, {nom_dia}, en Montflorit</b>" if idioma == "es"
                   else f"<b>Previsió per a demà, {nom_dia}, a Montflorit</b>") + fins]
        linies.append(frase_cel(dia, idioma, dema, dema=True))
        if franges(nit):    # la noche, solo si se espera lluvia
            linies.append(amb_icona(emoji_pluja(nit), ("Esta noche: " if idioma == "es" else "Aquesta nit: ")
                                    + text_franges(franges(nit), idioma) + "."))
        linies.append(text_temperatura(dia, idioma, "Temperatura", compara_resum(dades, dia), "avui"))
        linies.append(text_pluja(dia, idioma, avis=[f for f in nit + dia if hora(f).date() == dema]))
        roba = text_roba(dia, idioma)
        paraigua = text_paraigua(dia, idioma, nit)
        linies += linies_perill_dia(dades, idioma, dema, moment)
    else:
        fi_dia = ara_n.replace(hour=23, minute=59)
        tram = [f for f in hores if hora(f) < fi_dia]
        nom_dia = DIES[idioma][moment.weekday()]
        if not tram:    # sense hores d'avui, no hi ha previsió, i es diu (auditoria del 08-10-2026)
            return "\n".join(x for x in (text_ara(dades, idioma, moment=moment), t["sense_previsio"].format(generat.strftime("%H:%M")), WEB) if x)
        linies = [f"<b>Hoy, {nom_dia}, en Montflorit</b>" if idioma == "es"
                  else f"<b>Avui, {nom_dia}, a Montflorit</b>",
                  text_ara(dades, idioma, moment=moment),
                  frase_cel(hores, idioma, moment.date()),
                  text_temperatura(tram, idioma, "Temperatura de aquí a medianoche" if idioma == "es"
                                   else "Temperatura d'aquí a mitjanit", compara_resum(dades, tram), "ahir",
                                   (dades.get("ara_casa") or {}).get("temperatura")),
                  text_pluja(tram, idioma)]
        roba = text_roba(tram, idioma)
        paraigua = text_paraigua(tram, idioma)
        # De vespre, si ha de ploure abans de les 6, també la nit.
        if avui and moment.hour >= HORA_DEMA:
            fi_nit = dt.datetime.combine(moment.date() + dt.timedelta(days=1), dt.time(6))
            nit = [f for f in hores if fi_dia <= hora(f) < fi_nit]
            # «De matinada», de 0 a 6 h: el vespre ja és a la línia de la pluja, i
            # «Aquesta nit» del resum de demà va de les 18 a les 6 h (inventari
            # del 18-10-2026: la mateixa pluja amb dues franges).
            if franges(nit):
                linies.append(amb_icona(emoji_pluja(nit), ("De madrugada: " if idioma == "es" else "De matinada: ")
                                        + text_franges(franges(nit), idioma) + "."))
                paraigua = text_paraigua(tram + nit, idioma)
        linies += linies_perill_dia(dades, idioma, moment.date(), moment)
        linies.append(text_trens_resum(dades, idioma))
    # La ropa, al final y aparte (Juanjo, 08-10-2026: «muy desordenado»), y
    # detrás, el paraguas.
    roba = " ".join(x for x in (roba, paraigua) if x) or None
    text = "\n".join(x for x in linies if x)
    return text + (f"\n\n{roba}" if roba else "") + "\n" + (peu_telegram(generat, idioma) if telegram else WEB)


def peu_telegram(generat, idioma):
    """A Telegram el missatge queda al xat i es llegeix hores després: de quan
    són les dades (les de la imatge) i on hi ha la d'ara (Juanjo, 17-10-2026:
    «para obtener la previsión actualizada en cada momento hay que visitar
    url»). Les notificacions obren la web en tocar-les i «Consultes» ja hi és."""
    if idioma == "es":
        return f"Previsión de las {generat:%H:%M}. La de cada momento, en {WEB}"
    return f"Previsió de les {generat:%H:%M}. La de cada moment, a {WEB}"


def text_trens_resum(dades, idioma):
    linies = ((dades.get("trens") or {}).get("linies")) or []
    if not linies:
        return None
    no = {"ca": {"sense_trens": "sense trens", "bus": "per carretera", "incidencies": "amb incidències",
                 "retard": "amb retard", "sense_dades": "sense dades"},
          "es": {"sense_trens": "sin trenes", "bus": "por carretera", "incidencies": "con incidencias",
                 "retard": "con retraso", "sense_dades": "sin datos"}}[idioma]
    # Sense dades de cap línia (Renfe i FGC caiguts), no es pot dir que vagin bé.
    if all(l["estat"] == "sense_dades" for l in linies):
        return ("Trenes de Cerdanyola: ahora mismo no hay datos de Renfe ni de FGC." if idioma == "es"
                else "Trens de Cerdanyola: ara mateix no hi ha dades de Renfe ni d'FGC.")
    mal = [f"{cercle_tren(l)} {l['linia']} {no[l['estat']]}" for l in linies if l["estat"] in no]
    if not mal:
        return None if all(l["estat"] == "fora_horari" for l in linies) else \
            (f"{CERCLE['baix']} Trenes de Cerdanyola sin incidencias." if idioma == "es"
             else f"{CERCLE['baix']} Trens de Cerdanyola sense incidències.")
    return ("Trenes de Cerdanyola: " if idioma == "es" else "Trens de Cerdanyola: ") + ", ".join(mal) + "."


# --- Órdenes de consulta (Juanjo, 08-10-2026) ---------------------------------------
# /trens, /radar y /avisos_actius: lo mismo que la web, con el mismo límite de
# edad de los datos que /ara.

def dades_velles(dades, idioma, moment):
    generat = dades.get("generat") and dt.datetime.fromisoformat(dades["generat"])
    if not generat or moment - generat > dt.timedelta(hours=DADES_VELLES_H):
        return T[idioma]["velles_ara"].format(generat.strftime("%H:%M") if generat else "?")
    return None


ESTAT_TREN = {"ca": {"circula": "sense incidències", "incidencies": "amb incidències", "retard": "amb retard",
                     "bus": "servei per carretera",
                     "sense_trens": "sense trens", "fora_horari": "fora d'horari", "sense_dades": "sense dades"},
              "es": {"circula": "sin incidencias", "incidencies": "con incidencias", "retard": "con retraso",
                     "bus": "servicio por carretera",
                     "sense_trens": "sin trenes", "fora_horari": "fuera de horario", "sense_dades": "sin datos"}}


# Verd, circula; ambre, amb incidències, o diu que circula però no s'hi ha vist
# cap tren; vermell, sense trens (també per carretera); blanc, sense dades o
# fora d'horari: no se'n sap res.
CERCLE_TREN = Escala(circula="baix", incidencies="alt", retard="alt", bus="maxim", sense_trens="maxim", fora_horari="nul",
                     sense_dades="nul")


def cercle_tren(l):
    if l["estat"] == "circula" and l.get("no_vist"):
        return CERCLE["mig"]
    return CERCLE_TREN.get(l["estat"], CERCLE["nul"])


def text_trens_bot(dades, idioma, moment):
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    linies = ((dades.get("trens") or {}).get("linies")) or []
    if not linies:
        return "Ahora no hay datos de los trenes." if idioma == "es" else "Ara no hi ha dades dels trens."
    # Cada línia una sola vegada, amb el seu avís més nou al costat, en
    # l'idioma original de l'operador (Juanjo, 07-10-2026 i 08-10-2026).
    files = []
    for l in linies:
        fila = f"{cercle_tren(l)} <b>{html.escape(l['linia'])}</b> ({html.escape(l.get('estacio', ''))}): {ESTAT_TREN[idioma].get(l['estat'], l['estat'])}"
        if l.get("no_vist"):
            fila += (" (dice que circula, pero en la última hora no se ha visto ningún tren cerca de la estación)"
                     if idioma == "es" else
                     " (diu que circula, però a l'última hora no s'ha vist cap tren a prop de l'estació)")
        if l.get("avisos"):
            a = l["avisos"][0]
            fila += f". «{html.escape(a.get(idioma) or a.get('ca') or a.get('es') or '')}»"
        files.append(fila)
    cap = "Trenes de Cerdanyola" if idioma == "es" else "Trens de Cerdanyola"
    return f"<b>{cap}</b>\n" + "\n".join(files)


# --- Busos (ADR 0120) -----------------------------------------------------------------
# Com «Consultes › Busos» de la web (web/comu.js, blocBusos): cada línia amb les
# seves incidències i, de cada sentit, les parades del barri amb les dues
# hores de pas següents de les 2 hores vinents o, si no n'hi ha, la propera.
# Els avisos de l'AMB, tal com els publica, en català o en castellà.

def _hora_bus(h):
    return f"{h.hour}:{h.minute:02d}"


def _dia_bus(d, idioma):
    return f"{DIES[idioma][d.weekday()]} {d.day}"


def hores_parada(hores, des, idioma):
    # Pel moment (ADR 0128); per mostrar, en hora de Madrid sense zona, com des.
    des_u = _instant(des.isoformat())
    futures = [(u, hora_local(x)) for x in hores if (u := _instant(x)) >= des_u]
    properes = [h for u, h in futures if u <= des_u + dt.timedelta(hours=2)][:2]
    futures = [h for _, h in futures]
    if properes:
        return (" y " if idioma == "es" else " i ").join(_hora_bus(h) for h in properes)
    if not futures:
        return "—"
    d = futures[0]
    if d.date() == des.date():
        return _hora_bus(d)
    return f"{_dia_bus(d, idioma)} a las {_hora_bus(d)}" if idioma == "es" else f"{_dia_bus(d, idioma)} a les {_hora_bus(d)}"


def linia_incidencia_bus(inc, des, idioma):
    es = idioma == "es"
    titol = (inc.get("titol") or {}).get(idioma) or (inc.get("titol") or {}).get("ca") or ""
    url = (inc.get("url") or {}).get(idioma) or (inc.get("url") or {}).get("ca")
    text = enllac(url, titol) if url else html.escape(titol, quote=False)
    inici = inc.get("inici") and hora_local(inc["inici"])
    fi = inc.get("fi") and hora_local(inc["fi"])
    if inici and inici > des:
        quan = (f", a partir de las {_hora_bus(inici)}" if es else f", a partir de les {_hora_bus(inici)}") \
            if inici.date() == des.date() else \
            (f", a partir del {_dia_bus(inici, idioma)} a las {_hora_bus(inici)}" if es
             else f", a partir del {_dia_bus(inici, idioma)} a les {_hora_bus(inici)}")
    elif fi:
        quan = (f", hasta las {_hora_bus(fi)}" if es else f", fins a les {_hora_bus(fi)}") if fi.date() == des.date() \
            else (f", hasta el {_dia_bus(fi, idioma)}" if es else f", fins al {_dia_bus(fi, idioma)}")
    else:
        quan = ""
    return f"⚠️ {text}{quan}."


def text_busos_bot(dades, idioma, moment):
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    es = idioma == "es"
    busos = dades.get("busos") or {}
    if not busos.get("linies"):
        return "Ahora no hay datos de los autobuses." if es else "Ara no hi ha dades dels busos."
    des = moment.astimezone(ZONA).replace(tzinfo=None)
    blocs = ["<b>Autobuses de Montflorit</b>" if es else "<b>Busos de Montflorit</b>"]
    for l in busos["linies"]:
        files = [f"<b>{html.escape(l['linia'])}</b> {html.escape(l.get('nom', ''))}"]
        for inc in busos.get("incidencies") or []:
            fi = inc.get("fi") and hora_local(inc["fi"])
            if l["linia"] in inc.get("linies", []) and not (fi and fi < des):
                files.append(linia_incidencia_bus(inc, des, idioma))
        for s in l.get("sentits") or []:
            files.append(("→ Hacia " if es else "→ Cap a ") + html.escape(s["cap_a"]))
            files += [f"• {html.escape(p['parada'])}: {hores_parada(p['hores'], des, idioma)}" for p in s["parades"]]
        if l.get("horari"):
            files.append(enllac(l["horari"], "Horario completo (PDF)" if es else "Horari complet (PDF)"))
        blocs.append("\n".join(files))
    if busos.get("temps_real_de"):
        h = hora_local(busos["temps_real_de"]).strftime("%H:%M")
        peu = (f"<i>Hora de llegada estimada, con datos del AMB de las {h}.</i>" if es
               else f"<i>Hora d'arribada estimada, amb dades de l'AMB de les {h}.</i>")
    else:
        peu = ("<i>Horas del horario del AMB: ahora no llegan las del tiempo real.</i>" if es
               else "<i>Hores de l'horari de l'AMB: ara no arriben les del temps real.</i>")
    return "\n\n".join(blocs + [peu])


TRANSIT = "https://transit.gencat.cat/{}/informacio-viaria/estat-transit/"


def distancia(km):
    """Com a la web: en metres (de 50 en 50) per sota d'1 km; si no, en km amb un decimal."""
    # Arrodonit com Math.round de la web (la meitat, cap amunt), perquè surti igual.
    if km < 1:
        return f"{max(50, math.floor(km * 20 + 0.5) * 50)}\u00a0m"
    x = math.floor(km * 10 + 0.5) / 10
    return f"{x:g}".replace(".", ",") + "\u00a0km"


def text_transit_bot(dades, idioma, moment):
    """Les incidències de trànsit a prop, com a la fitxa del cotxe de «Si surts»
    (ADR 0052 i 0053). Els textos del Servei Català de Trànsit, en català."""
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    es = idioma == "es"
    transit = dades.get("transit")
    if not transit:
        return "Ahora no hay datos del tráfico." if es else "Ara no hi ha dades del trànsit."
    cap = "Tráfico a menos de 5\u00a0km de Montflorit" if es else "Trànsit a menys de 5\u00a0km de Montflorit"
    files = []
    for i in transit.get("incidencies") or []:
        lloc = ", ".join(x for x in (i.get("municipi"), i.get("km") is not None and f"a {distancia(i['km'])}") if x)
        lloc = f" ({lloc})" if lloc else ""
        causa = i.get("causa") if i.get("causa") != "Circulació" else None
        if causa and i.get("tipus") == "obres":
            causa = ("Obras: " if es else "Obres: ") + causa
        # Sense hora per incidència: la de la font és la de l'última actualització
        # (Juanjo, 09-10-2026). La de la consulta va al peu.
        detall = ", ".join(x for x in (causa, i.get("sentit"), i.get("pk") and f"km {i['pk']}") if x)
        files.append(f"<b>{html.escape(i.get('carretera') or '?')}</b>{html.escape(lloc)}: "
                     + html.escape(f"{i.get('descripcio') or ''}. {detall}." if detall else f"{i.get('descripcio') or ''}.",
                                   quote=False))
    if not files:
        files = ["Ninguna incidencia a menos de 5\u00a0km de Montflorit." if es
                 else "Cap incidència a menys de 5\u00a0km de Montflorit."]
    h = hora_local(transit["hora"]).strftime("%H:%M") if transit.get("hora") else "?"
    return (f"<b>{cap}</b>\n" + "\n".join(files) + "\n"
            + enllac(TRANSIT.format("es" if es else "ca"), f"Servei Català de Trànsit, {h}"))


# --- Llum (ADR 0072) ---------------------------------------------------------------

# El mapa de talls d'e-distribució (l'aplicació d'ArcGIS que hi ha dins la seva
# pàgina d'avaries), centrat a Montflorit i en l'idioma de qui el mira (Juanjo,
# 11-10-2026: «si es posible centrado en montflorit»).
MAPA_LLUM = ("https://dpa-portalgis.enel.com/portal/apps/instant/basic/index.html"
             "?appid=21f5d825ceeb48dba6ef6ee97f840168&center=2.133,41.481&level=15&locale={}")
CERCADOR_TALLS = "https://wtp-pro.endesa.com/#/wtp"
# La nota d'e-distribució que no diu res, fora (Juanjo: «informacion vacía»).
NOTA_BUIDA = ("no hay información adicional",)


# Els carrers no els dona e-distribució: s'estimen amb el punt aproximat
# (llum.carrers_probables) i es diu (Juanjo, 11-10-2026: «avisando que el
# servicio no ofrece este dato y es una estimación»).
NOTA_CARRERS = {
    "ca": "<i>Els carrers són una estimació a partir del punt aproximat del mapa: e-distribució no diu quins carrers queden sense llum.</i>",
    "es": "<i>Las calles son una estimación a partir del punto aproximado del mapa: e-distribución no dice qué calles se quedan sin luz.</i>",
}


def carrers_llum(carrers, idioma):
    """«; carrer probable: Carrer de Sant Jeroni» o «; carrers probables: … o …»."""
    if not carrers:
        return ""
    es = idioma == "es"
    cap = (("calle probable" if es else "carrer probable") if len(carrers) == 1
           else ("calles probables" if es else "carrers probables"))
    return f"; {cap}: " + " o ".join(carrers)


def quan_llum(iso, idioma, moment, des_de=False):
    """«les 23:12», o «el 10/10 a les 23:12» si no és avui; amb des_de, «des de
    les 23:12» o «des del 10/10 a les 23:12»."""
    t = dt.datetime.fromisoformat(iso).astimezone(ZONA)
    h = t.strftime("%H:%M")
    es = idioma == "es"
    if t.date() == moment.astimezone(ZONA).date():
        res = f"las {h}" if es else f"les {h}"
        return (("desde " if es else "des de ") + res) if des_de else res
    d = t.strftime("%d/%m")
    if des_de:
        return f"desde el {d} a las {h}" if es else f"des del {d} a les {h}"
    return f"el {d} a las {h}" if es else f"el {d} a les {h}"


def text_llum_bot(dades, idioma, moment):
    """Els talls de llum del barri (llum.py, ADR 0072): dins dels límits de
    Montflorit o tocant-hi, sense el carrer, que e-distribució no publica; els
    programats, carrer per carrer, al cercador d'Endesa, enllaçat. La nota, com
    la publica e-distribució."""
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    es = idioma == "es"
    llum = dades.get("llum")
    if not llum:
        return "Ahora no hay datos de los cortes de luz." if es else "Ara no hi ha dades dels talls de llum."
    cap = "Cortes de luz en Montflorit" if es else "Talls de llum a Montflorit"
    files = []
    for t in llum.get("talls") or []:
        que = (("Trabajos programados" if es else "Treballs programats") if t.get("programat")
               else ("Avería" if es else "Avaria"))
        lloc = (("en el barrio" if es else "al barri") if t.get("on") != "vora"
                else ("en el límite del barrio" if es else "al límit del barri"))
        lloc += carrers_llum(t.get("carrers"), idioma)
        n = t.get("clients")
        qui = ((f"{n} clientes" if n != 1 else "1 cliente") if es else (f"{n} clients" if n != 1 else "1 client")) \
            if n is not None else ("Clientes" if es else "Clients")
        frase = f"{qui} sin luz" if es else f"{qui} sense llum"
        if t.get("inici"):
            frase += " " + quan_llum(t["inici"], idioma, moment, des_de=True)
        if t.get("fins"):
            frase += (f"; previsto hasta {quan_llum(t['fins'], idioma, moment)}" if es
                      else f"; previst fins a {quan_llum(t['fins'], idioma, moment)}")
        fila = f"<b>{html.escape(que)}</b> ({html.escape(lloc)}): {html.escape(frase, quote=False)}."
        nota = " ".join((t.get("nota") or "").split())
        if nota and not any(b in nota.lower() for b in NOTA_BUIDA):
            fila += f" «{html.escape(nota, quote=False)}»"
        files.append(fila)
    if files:
        files.append(NOTA_CARRERS["es" if es else "ca"])
    else:
        files = ["Ningún corte de luz en Montflorit." if es else "Cap tall de llum a Montflorit."]
    h = hora_local(llum["hora"]).strftime("%H:%M") if llum.get("hora") else "?"
    return (f"<b>{cap}</b>\n" + "\n".join(files) + "\n"
            + enllac(MAPA_LLUM.format("es" if es else "ca"), ("Mapa de e-distribución" if es else "Mapa d'e-distribució") + f", {h}")
            # El cercador només llista els municipis amb talls programats els 7 dies
            # següents: sense cap, Cerdanyola no hi surt (comprovat l'11-10-2026).
            + "\n" + ("Cortes programados por calle: " if es else "Talls programats per carrer: ")
            + enllac(CERCADOR_TALLS, "buscador de Endesa" if es else "cercador d'Endesa")
            + (" (Cerdanyola solo aparece cuando tiene alguno)" if es else " (Cerdanyola només hi surt quan en té)"))


# --- Sol, aire i pol·len (ADR 0054) -------------------------------------------------

def hm(iso):
    return hora_local(iso).strftime("%H:%M")


UV_NIVELLS = ((2, "baix", "bajo"), (5, "moderat", "moderado"), (7, "alt", "alto"), (10, "molt alt", "muy alto"),
              (99, "extrem", "extremo"))
CERCLE_UV = Escala({"baix": "baix", "moderat": "mig", "alt": "alt", "molt alt": "maxim", "extrem": "extrem"})


def text_sol_bot(dades, idioma, moment):
    """La sortida i la posta del sol i l'índex UV màxim, avui i demà. Els
    consells, els de «Si surts» (UV de 3 o més)."""
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    es = idioma == "es"
    dies = {d["dia"]: d for d in dades.get("sol") or []}
    avui, dema = moment.date().isoformat(), (moment + dt.timedelta(days=1)).date().isoformat()
    if avui not in dies:
        return "Ahora no hay datos del sol." if es else "Ara no hi ha dades del sol."
    d = dies[avui]
    llum = dt.datetime.fromisoformat(d["posta"]) - dt.datetime.fromisoformat(d["sortida"])
    h, m = divmod(round(llum.total_seconds() / 60), 60)
    linies = [f"<b>{'El sol hoy en Montflorit' if es else 'El sol avui a Montflorit'}</b>",
              (f"Sale a las {hm(d['sortida'])} y se pone a las {hm(d['posta'])}: {h} h {m} min de luz." if es else
               f"Surt a les {hm(d['sortida'])} i es pon a les {hm(d['posta'])}: {h} h {m} min de llum.")]
    if d.get("uv_max") is not None:
        uv = round(d["uv_max"])
        ca = next(ca for lim, ca, es_ in UV_NIVELLS if uv <= lim)
        nom = next(n for lim, ca_, es_ in UV_NIVELLS if uv <= lim for n in [(es_ if es else ca_)])
        linia = CERCLE_UV[ca] + (f" Índice UV máximo: {uv} ({nom})." if es else f" Índex UV màxim: {uv} ({nom}).")
        if uv >= 3:
            linia += (" A las horas centrales, protector solar, gorra y gafas de sol." if es
                      else " A les hores centrals, protector solar, gorra i ulleres de sol.")
        linies.append(linia)
    if dema in dies:
        dm = dies[dema]
        linies.append(f"Mañana sale a las {hm(dm['sortida'])} y se pone a las {hm(dm['posta'])}." if es
                      else f"Demà surt a les {hm(dm['sortida'])} i es pon a les {hm(dm['posta'])}.")
    return "\n".join(linies)


AIRE_NOMS = {"ca": {"bona": "bona", "raonablement_bona": "raonablement bona", "regular": "regular",
                    "desfavorable": "desfavorable", "molt_desfavorable": "molt desfavorable",
                    "extremadament_desfavorable": "extremadament desfavorable",
                    "pm2_5": "les partícules fines (PM2,5)", "pm10": "les partícules (PM10)",
                    "nitrogen_dioxide": "el diòxid de nitrogen (NO₂)", "ozone": "l'ozó (O₃)",
                    "sulphur_dioxide": "el diòxid de sofre (SO₂)"},
             "es": {"bona": "buena", "raonablement_bona": "razonablemente buena", "regular": "regular",
                    "desfavorable": "desfavorable", "molt_desfavorable": "muy desfavorable",
                    "extremadament_desfavorable": "extremadamente desfavorable",
                    "pm2_5": "las partículas finas (PM2,5)", "pm10": "las partículas (PM10)",
                    "nitrogen_dioxide": "el dióxido de nitrógeno (NO₂)", "ozone": "el ozono (O₃)",
                    "sulphur_dioxide": "el dióxido de azufre (SO₂)"}}
CERCLE_AIRE = Escala(bona="baix", raonablement_bona="baix", regular="mig", desfavorable="alt",
                     molt_desfavorable="maxim", extremadament_desfavorable="extrem")
MAPA_AIRE = "https://mediambient.gencat.cat/{}/05_ambits_dactuacio/atmosfera/qualitat_de_laire/vols-saber-que-respires/"


def text_aire_bot(dades, idioma, moment):
    """L'índex europeu de qualitat de l'aire del model CAMS, corregit amb les
    estacions (aire.py): ara, el pitjor moment del que queda d'avui i que és una
    estimació d'una zona. Les mesures de les estacions no es mostren: per als
    veïns són soroll (Juanjo, 09-10-2026)."""
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    es = idioma == "es"
    a = dades.get("aire")
    if not a or a.get("index") is None:
        return "Ahora no hay datos de la calidad del aire." if es else "Ara no hi ha dades de la qualitat de l'aire."
    n = AIRE_NOMS[idioma]
    linies = [f"<b>{'Calidad del aire en Montflorit' if es else 'Qualitat de l’aire a Montflorit'}</b>",
              amb_icona(CERCLE_AIRE.get(a["categoria"]),
                        f"Ahora: {n[a['categoria']]} (índice europeo {a['index']})." if es
                        else f"Ara: {n[a['categoria']]} (índex europeu {a['index']}).")]
    if a.get("contaminant") and a["categoria"] != "bona":
        plural = a["contaminant"] in ("pm2_5", "pm10")
        verb = ("son" if plural else "es") if es else ("són" if plural else "és")
        linies[-1] += (f" Lo que más pesa {verb} {n[a['contaminant']]}." if es else f" El que més pesa {verb} {n[a['contaminant']]}.")
    p = a.get("pitjor")
    if p and p["index"] > a["index"] and p["categoria"] != a["categoria"]:
        linies.append(amb_icona(CERCLE_AIRE.get(p["categoria"]),
                                f"Lo peor de hoy: {n[p['categoria']]} hacia las {hm(p['hora'])}." if es
                                else f"El pitjor d'avui: {n[p['categoria']]} cap a les {hm(p['hora'])}."))
    linies.append("<i>" + html.escape(nota_aire(a, idioma), quote=False) + "</i>")
    linies.append(enllac(MAPA_AIRE.format("es" if es else "ca"),
                         "Medidas de las estaciones (Generalitat)" if es else "Mesures de les estacions (Generalitat)"))
    return "\n".join(linies)


CURT_AIRE = {"ca": {"nitrogen_dioxide": "NO₂", "ozone": "ozó", "pm10": "PM10", "pm2_5": "PM2,5", "sulphur_dioxide": "SO₂"},
             "es": {"nitrogen_dioxide": "NO₂", "ozone": "ozono", "pm10": "PM10", "pm2_5": "PM2,5", "sulphur_dioxide": "SO₂"}}
ORDRE_AIRE = ("nitrogen_dioxide", "ozone", "pm10", "pm2_5", "sulphur_dioxide")


def nota_aire(a, idioma):
    """Que és una estimació d'una zona i què s'ha corregit amb les mesures
    (Juanjo, 09-10-2026: «¿realmente es la de Montflorit?»)."""
    es = idioma == "es"
    nota = ("Estimación del modelo europeo CAMS para una zona de unos 10 km alrededor de Bellaterra, no medida en "
            "Montflorit" if es else "Estimació del model europeu CAMS per a una zona d'uns 10 km al voltant de "
            "Bellaterra, no mesurada a Montflorit")
    corregits = [CURT_AIRE[idioma][c] for c in ORDRE_AIRE if c in (a.get("factors") or {})]
    if corregits:
        llista = (" y " if es else " i ").join([", ".join(corregits[:-1]), corregits[-1]] if len(corregits) > 1
                                                else corregits)
        nota += (f"; {llista}, corregidos con las medidas de las estaciones de los últimos 30 días." if es else
                 f"; {llista}, corregits amb les mesures de les estacions dels últims 30 dies.")
    else:
        nota += "."
    return nota


NIVELL_POLLEN = {"ca": ("nul", "baix", "mig", "alt", "màxim"), "es": ("nulo", "bajo", "medio", "alto", "máximo")}
# Els colors de les barres de la web (estil.css, .nivell-N).
CERCLE_POLLEN = Escala(enumerate(("nul", "baix", "mig", "alt", "maxim")))
TENDENCIA = {"ca": {"A": "en augment", "D": "en descens", "!": "situació excepcional"},
             "es": {"A": "en aumento", "D": "en descenso", "!": "situación excepcional"}}


def text_pollen_bot(dades, idioma, moment):
    """El pol·len i les espores de la setmana a Bellaterra (pollen.py): de cada
    nivell, de més a menys, els tipus que hi són, amb la tendència si no és
    estable; dels que no n'hi ha, només els que van en augment."""
    es = idioma == "es"
    p = dades.get("pollen")
    if not p:
        return "Ahora no hay datos del polen." if es else "Ara no hi ha dades del pol·len."
    nivell, tend = NIVELL_POLLEN[idioma], TENDENCIA[idioma]
    ini, fi = dt.date.fromisoformat(p["inici"]), dt.date.fromisoformat(p["fi"])
    setmana = (f"semana del {ini.day}/{ini.month} al {fi.day}/{fi.month}" if es
               else f"setmana del {ini.day}/{ini.month} al {fi.day}/{fi.month}")
    linies = [f"<b>{'Polen en Bellaterra' if es else 'Pol·len a Bellaterra'}</b> ({setmana}, "
              + (f"a {str(p['km']).replace('.', ',')} km)" if p.get("km") is not None else "")]
    if fi < moment.date():
        linies.append("<i>" + ("Son los datos de la última semana publicada." if es
                               else "Són les dades de l'última setmana publicada.") + "</i>")

    def grup(tipus, titol):
        files = []
        for n in range(4, 0, -1):
            noms = [t["nom"][idioma] + (f" ({tend[t['tendencia']]})" if t.get("tendencia") in tend else "")
                    for t in tipus if t["nivell"] == n]
            if noms:
                files.append(f"{CERCLE_POLLEN[n]} {nivell[n].capitalize()}: {', '.join(noms)}.")
        # Els que són a zero, també: a qui hi és al·lèrgic també li serveix
        # (Juanjo, 09-10-2026). Si van en augment, a part.
        pugen = [t["nom"][idioma] for t in tipus if t["nivell"] == 0 and t.get("tendencia") in ("A", "!")]
        nuls = [t["nom"][idioma] for t in tipus if t["nivell"] == 0 and t["nom"][idioma] not in pugen]
        if nuls:
            files.append(CERCLE_POLLEN[0] + " " + (f"{nivell[0].capitalize()}: {', '.join(nuls)}." if files or pugen
                                                   else ("Nulo en todos." if es else "Nul en tots.")))
        if pugen:
            files.append((f"Empiezan a subir: {', '.join(pugen)}." if es else f"Comencen a pujar: {', '.join(pugen)}."))
        return [f"<b>{titol}</b>"] + [html.escape(f, quote=False) for f in files]

    linies += grup(p.get("pollens") or [], "Polen" if es else "Pol·len")
    linies += grup(p.get("espores") or [], "Esporas de hongos" if es else "Espores de fongs")
    url = (p.get("url") or {}).get(idioma) or (p.get("url") or {}).get("ca") or "https://aerobiologia.cat/"
    linies.append(enllac(url, "Punt d’Informació Aerobiològica (UAB)") + " · CC BY-NC-SA 4.0")
    return "\n".join(linies)


DIRECCIO_ES = {"al nord": "el norte", "al nord-est": "el nordeste", "a l'est": "el este", "al sud-est": "el sudeste",
               "al sud": "el sur", "al sud-oest": "el sudoeste", "a l'oest": "el oeste", "al nord-oest": "el noroeste"}
RADAR_EN_DIRECTE = {"rainviewer": "https://www.rainviewer.com/map.html?loc=41.482,2.135,9&layer=radar",
                    "meteocat": "https://www.meteo.cat/observacions/radar"}


def text_radar_bot(dades, idioma, moment):
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    r = dades.get("radar")
    if not r:
        return "Ahora no hay datos del radar." if idioma == "es" else "Ara no hi ha dades del radar."
    h = lambda t: hora_local(t).strftime("%H:%M")
    es = idioma == "es"
    # El que es mesura mana, com a la web: si ja plou, «pluja a sobre», amb
    # l'hora en què pararia si el radar la veu (ADR 0049).
    plou = plou_ara(dades)
    # Sumant en UTC: amb la zona de Madrid, Python suma hores de rellotge.
    ara_u = moment.astimezone(dt.timezone.utc)
    aviat = r.get("arriba") and dt.datetime.fromisoformat(r["arriba"]) <= ara_u + dt.timedelta(minutes=5)
    # L'estat únic de la pluja (ADR 0101), com a la web: si només la veu el
    # radar, es diu.
    estat = (dades.get("pluja_ara") or {}).get("estat")
    nomes_radar = estat == "radar_sobre" or (estat is None and aviat and not plou)
    veu = aviat or (r.get("possible") and dt.datetime.fromisoformat(r["possible"]) <= ara_u + dt.timedelta(minutes=5))
    if plou and not veu and estat != "radar_sobre":
        # La mesuren les estacions i el radar no la veu a sobre (el plugim,
        # sovint), com a la web (Juanjo, 18-10-2026).
        que = ("Lluvia encima de Montflorit según las estaciones del barrio; el radar no la ve." if es
               else "Pluja a sobre de Montflorit segons les estacions del barri; el radar no la veu.")
    elif (plou and (r.get("arriba") or r.get("possible"))) or aviat or estat == "radar_sobre":
        que = "Lluvia encima de Montflorit." if es else "Pluja a sobre de Montflorit."
        if nomes_radar:
            que = ("Lluvia encima de Montflorit según el radar; ninguna estación del barrio la mide." if es
                   else "Pluja a sobre de Montflorit segons el radar; cap estació del barri no en mesura.")
        if r.get("fi"):
            que += (f" Pararía hacia las {h(r['fi'])} (en entrenamiento: puede fallar)." if es
                    else f" Pararia cap a les {h(r['fi'])} (en entrenament: pot fallar).")
        elif r.get("sense_fi"):
            que += (" No acaba en 2 horas (en entrenamiento: puede fallar)." if es
                    else " No s'acaba en 2 hores (en entrenament: pot fallar).")
    elif estat == "no" and (dades.get("pluja_ara") or {}).get("plugim"):
        # Ecos febles estesos a sobre als dos radars, com a la web (18-10-2026).
        que = ("El radar ve lluvia muy débil encima de Montflorit (llovizna), que las estaciones no miden." if es
               else "El radar veu pluja molt feble a sobre de Montflorit (plugim), que les estacions no mesuren.")
    elif r.get("arriba"):
        que = (f"Llegaría lluvia a Montflorit hacia las {h(r['arriba'])}." if idioma == "es" else f"Arribaria pluja a Montflorit cap a les {h(r['arriba'])}.")
    elif r.get("possible"):
        que = (f"Puede llegar lluvia a Montflorit hacia las {h(r['possible'])}." if idioma == "es" else f"Pot arribar pluja a Montflorit cap a les {h(r['possible'])}.")
    elif (r.get("forta") or {}).get("km", 0) >= 1:
        # Pluja forta o més a 15 km o menys, com a la web (17-10-2026).
        f = r["forta"]
        cap = ("al " + DIRECCIO_ES.get(f["rumb"], f["rumb"]).removeprefix("el ")) if es else f["rumb"]
        nom = INTENSITAT_RADAR[idioma][f["classe"]]
        que = (f"Lluvia {nom} a {round(f['km'])}\u00a0km {cap}, que de momento no viene hacia Montflorit." if es
               else f"Pluja {nom} a {round(f['km'])}\u00a0km {cap}, que de moment no ve cap a Montflorit.")
    else:
        # Només el que veu: la pluja que encara no s'ha format no hi surt
        # (Juanjo, 17-10-2026: «son mensajes contrarios» amb la previsió).
        que = ("El radar no ve lluvia que venga hacia Montflorit." if idioma == "es"
               else "El radar no veu pluja que vingui cap a Montflorit.")
    # Si la pluja creix al voltant, com a la web (17-10-2026): només si no
    # plou ni arriba.
    c = r.get("creixement") or {}
    if c.get("creix") and c.get("pct") is not None and not plou and not r.get("arriba") and not r.get("possible"):
        abans = (f"el {max(c['pct_abans'], 1)}\u00a0%" if c.get("km2_abans") else ("nada" if es else "gens"))
        que += (f"\nLa lluvia se está formando cerca: ya ocupa el {c['pct']}\u00a0% del terreno a 15\u00a0km o menos; "
                f"hace media hora, {abans}." if es
                else f"\nLa pluja s'està formant a prop: ja ocupa el {c['pct']}\u00a0% del terreny a 15\u00a0km o menys; "
                f"fa mitja hora, {abans}.")
    # La pluja més propera, si no és a sobre, com a la web (17-10-2026), i si
    # no és la mateixa que la forta que ja s'ha dit.
    # Amb plugim a sobre, tampoc (Juanjo, 18-10-2026: confonia).
    plugim = (dades.get("pluja_ara") or {}).get("plugim")
    p = None if que.startswith(("Pluja a sobre", "Lluvia encima")) or plugim else r.get("propera")
    f = r.get("forta")
    if f and p and round(p.get("km", 0)) == round(f["km"]) and p.get("rumb") == f["rumb"]:
        p = None
    if p and p.get("km", 0) >= 1:
        noms = INTENSITAT_RADAR[idioma]
        cap = ("al " + DIRECCIO_ES.get(p["rumb"], p["rumb"]).removeprefix("el ")) if es else p["rumb"]
        que += (f"\nLa más cercana, a {round(p['km'])}\u00a0km {cap} ({noms[p.get('classe') or 1]})." if es
                else f"\nLa més propera, a {round(p['km'])}\u00a0km {cap} ({noms[p.get('classe') or 1]}).")
    font = "RainViewer" if r.get("imatge") == "rainviewer" else "Meteocat"
    mov = ""
    # Sense moviment (menys d'1 km/h), no es diu cap on va.
    if r.get("cap_a") and (r.get("velocitat_kmh") or 0) >= 1:
        mov = (f" · va hacia {DIRECCIO_ES.get(r['cap_a'], r['cap_a'])} a {r['velocitat_kmh']}\u00a0km/h" if idioma == "es"
               else f" · va cap {r['cap_a']} a {r['velocitat_kmh']}\u00a0km/h")
    detall = (f"Radar de {font} de las {h(r['hora'])}{mov}." if idioma == "es" else f"Radar de {font} de les {h(r['hora'])}{mov}.")
    enllac = RADAR_EN_DIRECTE["rainviewer" if font == "RainViewer" else "meteocat"]
    vist = "En directo" if idioma == "es" else "En directe"
    return f"{que}\n{detall}\n{vist}: {enllac}"


# Les franges d'intensitat de l'AEMET, com nowcast.FRANGES_MMH (la 0, sense pluja).
INTENSITAT_RADAR = {"ca": [None, "feble", "moderada", "forta", "molt forta", "torrencial"],
                    "es": [None, "débil", "moderada", "fuerte", "muy fuerte", "torrencial"]}
FASE_ES = {"prealerta": "prealerta", "alerta": "alerta", "emergència": "emergencia"}
PLA_ES = {"d'inundacions": "de inundaciones", "de vent": "de viento", "de neu": "de nieve",
          "per onada de calor": "por ola de calor", "per onada de fred": "por ola de frío",
          "per contaminació": "por contaminación", "per vent": "por viento"}


def linies_smp(smp, idioma):
    """Les línies de Meteocat (smp.py), amb el cercle del seu nivell."""
    return [amb_icona(CERCLE.get(l.get("nivell")), html.escape(l.get(idioma) or l.get("ca") or "", quote=False))
            for l in (smp or {}).get("linies") or []]


def enllac(url, text):
    return f'<a href="{html.escape(url)}">{html.escape(text, quote=False)}</a>'


def text_avisos_actius(dades, idioma, moment):
    """Cada font en un bloc, amb el nom en negreta i els enllaços curts, separats
    per una línia en blanc (Juanjo, 08-10-2026: «sale todo muy seguido»)."""
    vell = dades_velles(dades, idioma, moment)
    if vell:
        return vell
    es = idioma == "es"
    blocs = []                     # (títol, [línies en HTML])
    for p in dades.get("plans") or []:
        if es:
            frase = (f"Plan {PLA_ES.get(p['nom'], p['nom'])} ({p['pla']}) en fase de "
                     f"{FASE_ES.get(p['fase'], p['fase'])}.")
        else:
            # «d'alerta», «d'emergència», però «de prealerta», com a la web.
            de = "d'" if p["fase"][:1] in "aeiouàèéíòóú" else "de "
            frase = f"Pla {p['nom']} ({p['pla']}) en fase {de}{p['fase']}."
        linia = amb_icona(CERCLE_FASE.get(p["fase"]), html.escape(frase, quote=False))
        if p.get("comunicat"):
            linia += " " + enllac(p["comunicat"], "Comunicado (PDF)" if es else "Comunicat (PDF)")
        blocs.append(("Protección Civil" if es else "Protecció Civil", [linia]))
    # Els avisos de Meteocat, en el seu bloc, també amb un pla: són d'un altre
    # organisme (Juanjo, 17-10-2026: «separalos de proteccion civil porque son
    # avisos aparte»; ADR 0071).
    if dades.get("smp"):
        smp = {"linies": [l for l in dades["smp"].get("linies") or [] if l.get("nivell") != "nul"]}
        if smp["linies"]:
            blocs.append(("Meteocat", linies_smp(smp, idioma)))
    avui, dema = moment.date(), (moment + dt.timedelta(days=1)).date()
    aemet = text_avisos_aemet(dades, idioma, avui, moment)
    aemet += [x for x in text_avisos_aemet(dades, idioma, dema, moment) if x not in aemet]
    if aemet:
        # «Avís groc de l'AEMET per pluja…» → «Avís groc per pluja…»: l'AEMET ja és el títol.
        net = [x.replace(" de l'AEMET", "").replace(" de la AEMET", "") for x in aemet]
        blocs.append(("AEMET", [html.escape(x, quote=False) for x in net]))
    # La riera, si hi ha avís obert (ADR 0093: faltava aquí).
    riera = [amb_icona(CERCLE.get(r.get("nivell")), html.escape(r[idioma], quote=False))
             for r in dades.get("perill_riera") or []]
    if riera:
        blocs.append(("Riera de Sant Cugat", riera))
    # Incendis a prop i Pla Alfa des del nivell 3 (ADR 0046).
    blocs += blocs_entorn(dades.get("entorn") or {}, idioma)
    # El temps excepcional que calcula la pàgina amb els llindars de Meteocat (des
    # del 16-10-2026; abans deia «de l'AEMET», inventari del 18-10-2026)
    # (el mateix de l'avís «perill», ADR 0018), dit que no és oficial.
    propis = linies_riscos(dades.get("riscos") or [], idioma, moment)
    if propis:
        blocs.append(("Tiempo excepcional en Montflorit" if es else "Temps excepcional a Montflorit",
                      [("<i>Lo calcula Temps a Montflorit con los umbrales de Meteocat: no es oficial.</i>" if es else
                        "<i>Ho calcula Temps a Montflorit amb els llindars de Meteocat: no és oficial.</i>")]
                      + [html.escape(x, quote=False) for x in propis]))
    if not blocs:
        # Amb un pla amagat per falta de motiu meteorològic (ADR 0062), el pla
        # continua activat: no es pot dir que no n'hi ha cap.
        if dades.get("plans_ocults"):
            return ("No hay avisos de la AEMET ni se prevé tiempo excepcional." if es else
                    "No hi ha avisos de l'AEMET ni es preveu temps excepcional.")
        return ("No hay avisos de la AEMET ni planes de Protección Civil activos, ni se prevé tiempo excepcional."
                if es else
                "No hi ha avisos de l'AEMET ni plans de Protecció Civil activats, ni es preveu temps excepcional.")
    # Sense títol: l'ordre ja diu què és (Juanjo, 08-10-2026).
    return "\n\n".join(f"<b>{t}</b>\n" + "\n".join(ls) for t, ls in blocs) + "\n"


# Des del nivell 3 el Pla Alfa restringeix l'accés (config.ALFA_NIVELL_MOSTRAR;
# el bot no carrega config).
ALFA_NIVELL_MOSTRAR = 3
ALFA = {"ca": "Nivell {n} {quan} a Cerdanyola: accés restringit als espais forestals.",
        "es": "Nivel {n} {quan} en Cerdanyola: acceso restringido a los espacios forestales."}
BOMBERS = "https://interior.gencat.cat/ca/arees_dactuacio/bombers/actuacions-de-bombers/"
PLA_ALFA = "https://interior.gencat.cat/ca/arees_dactuacio/agents-rurals/pla-alfa/"


def blocs_entorn(entorn, idioma):
    es = idioma == "es"
    blocs = []
    focs = []
    for i in entorn.get("incendis") or []:
        h = hora_local(i["inici"]).strftime("%H:%M") if i.get("inici") else "?"
        dist = f", a {str(i['km']).replace('.', ',')} km de Montflorit" if i.get("km") is not None else ""
        # Dins del parc, dit clarament (Juanjo, 11-10-2026; ADR 0071).
        lloc = ((f"dentro del Parque de Collserola ({i['municipi']})" if es else
                 f"dins del Parc de Collserola ({i['municipi']})") if i.get("collserola") else
                (f"en {i['municipi']}" if es else f"a {i['municipi']}"))
        focs.append(amb_icona("🔥", html.escape(f"Bombers: incendio forestal {lloc}{dist}, desde las {h}." if es
                                                else f"Bombers: incendi forestal {lloc}{dist}, des de les {h}.", quote=False)))
    if focs:
        blocs.append(("Bombers", focs + [enllac(BOMBERS, "Mapa")]))
    alfa = entorn.get("pla_alfa") or {}
    nivells = []
    for dia in ("avui", "dema"):
        n = alfa.get(dia)
        if n is not None and n >= ALFA_NIVELL_MOSTRAR:
            quan = {"avui": ("hoy" if es else "avui"), "dema": ("mañana" if es else "demà")}[dia]
            nivells.append(amb_icona(CERCLE["maxim"] if n >= 4 else CERCLE["alt"],
                                     html.escape(ALFA[idioma].format(n=n, quan=quan), quote=False)))
    nivells += [html.escape(f"Cerrado: {t['espai']}." if es else f"Tancat: {t['espai']}.", quote=False)
                for t in alfa.get("tancaments") or []]
    if nivells:
        blocs.append(("Plan Alfa" if es else "Pla Alfa", nivells + [enllac(PLA_ALFA, "Mapa")]))
    return blocs


def linies_riscos(riscos, idioma, moment):
    """Una línia per risc, en l'idioma de qui pregunta. Els textos en castellà
    són els de l'avís (avisos_bot.py); si no es pot carregar, el català de les dades."""
    if idioma == "es":
        try:
            sys.path.insert(0, REPO)
            import avisos_bot as AB
            return [amb_icona(CERCLE_AVIS.get(r.get("nivell")), AB.linia_risc_es(r, moment)) for r in riscos]
        except Exception:
            pass
    return [amb_icona(CERCLE_AVIS.get(r.get("nivell")), r.get("text", "")) for r in riscos]


# --- Mensajes recibidos -------------------------------------------------------------

# --- Comptador anònim de les ordres (Juanjo, 08-10-2026) --------------------------
# Quantes vegades es fa servir cada ordre cada dia, sense saber qui: no es desa
# cap identificador ni cap text. Les ordres de Juanjo no compten. Una ordre que
# no existeix compta com «altres», sense guardar què s'ha escrit.

COMPTADOR = os.path.join(BASE, "comptador.json")
ORDRES = ("/start", "/avisos", "/menu", "/avui", "/resum", "/dema", "/ara", "/radar", "/sol", "/aire", "/pollen", "/trens", "/busos",
          "/transit", "/llum", "/avisos_actius", "/baixa")
COMPTADOR_DIES = 400


def chat_juanjo():
    propi = llegeix(os.environ.get("AVISAR_CONFIG", os.path.expanduser("~/.vigilancia-nas/config.json")), {})
    return str(propi.get("chat_id") or "")


def compta(ordre, chat, dia=None):
    if chat == chat_juanjo():
        return
    clau = ordre if ordre in ORDRES else "altres"
    dia = dia or ara().date().isoformat()
    c = llegeix(COMPTADOR, {})
    c.setdefault(dia, {})
    c[dia][clau] = c[dia].get(clau, 0) + 1
    for vell in sorted(c)[:-COMPTADOR_DIES]:
        del c[vell]
    desa(COMPTADOR, c)


def text_estadistiques(dies=(7, 30), avui=None):
    """Els usos de cada ordre en els últims dies, de més a menys."""
    c = llegeix(COMPTADOR, {})
    avui = avui or ara().date()
    linies = ["Usos del bot (sense comptar-te a tu; no es desa qui):"]
    for n in dies:
        des_de = (avui - dt.timedelta(days=n - 1)).isoformat()
        total = {}
        for dia, ordres in c.items():
            if dia >= des_de:
                for o, k in ordres.items():
                    total[o] = total.get(o, 0) + k
        detall = ", ".join(f"{o} {k}" for o, k in sorted(total.items(), key=lambda x: -x[1])) or "cap"
        linies.append(f"Últims {n} dies: {sum(total.values())} ({detall})")
    return "\n".join(linies)


def avisa_juanjo(text):
    """A Juanjo, con su bot de avisos (el del vigía de IONOS). Sin nombres de
    nadie: el bot promete guardar solo el identificador."""
    propi = llegeix(os.environ.get("AVISAR_CONFIG", os.path.expanduser("~/.vigilancia-nas/config.json")), {})
    if propi.get("token") and propi.get("chat_id"):
        try:
            Api(propi["token"])("sendMessage", chat_id=propi["chat_id"], text=text)
        except Exception as ex:
            registra(f"no se ha podido avisar a Juanjo: {ex}")


# --- Altes i baixes (ADR 0084) ---
# Juanjo vol saber quanta gent s'apunta i se'n va (12-10-2026), només els
# totals: del bot i dels avisos de la web, quantes altes, baixes, bloquejos i
# adreces mortes hi ha cada dia, sense res de qui («me interesa el total»).
MOVIMENTS_DIES = 400


def moviment(canal, tipus, dia=None):
    """Apunta un moviment: canal «bot» o «web»; tipus «alta», «baixa»,
    «bloqueig» (bot) o «morta» (web). Només el dia: res més."""
    ruta = os.path.join(BASE, "moviments.json")
    dia = dia or ara().date().isoformat()
    with open(os.path.join(BASE, "moviments.lock"), "a") as cadenat:
        fcntl.flock(cadenat, fcntl.LOCK_EX)
        m = llegeix(ruta, [])
        m.append({"dia": dia, "canal": canal, "tipus": tipus})
        limit = (dt.date.fromisoformat(dia) - dt.timedelta(days=MOVIMENTS_DIES)).isoformat()
        desa(ruta, [x for x in m if x["dia"] >= limit])


def treu(subs, estat, chat, tipus):
    """Fora del bot: amb /baixa («baixa») o perquè l'ha bloquejat («bloqueig»)."""
    if subs.pop(chat, None) is not None:
        try:
            moviment("bot", tipus)
        except Exception as ex:               # el control no pot aturar el bot
            registra(f"moviments: {ex}")
    esborra(estat, chat)


def alta(subs, chat, usuari):
    """El suscriptor de este chat; si es nuevo, se le da de alta y se avisa a
    Juanjo con el número total."""
    if chat not in subs:
        subs[chat] = nou_subscriptor(usuari)
        try:
            moviment("bot", "alta")
        except Exception as ex:
            registra(f"moviments: {ex}")
        avisa_juanjo(f"Temps a Montflorit: alta nova al bot (ja en són {len(subs)}).")
    return subs[chat]


def esborra(estat, chat):
    """La baja borra el chat de todo el estado: la fecha del último resumen y
    los avisos pendientes de entregarle (auditoría del 07-10-2026)."""
    if estat is None:
        return
    estat.get("resums", {}).pop(chat, None)
    for p in estat.get("pendents", {}).values():
        p["chats"] = [c for c in p["chats"] if c != chat]


def neteja(subs, estat):
    """Quita del estado los restos de chats que ya no están suscritos."""
    resums = estat.get("resums") or {}
    for chat in [c for c in resums if c not in subs]:
        del resums[chat]
    for p in (estat.get("pendents") or {}).values():
        p["chats"] = [c for c in p["chats"] if c in subs]


def migra(api, subs, estat):
    """Canvis del 09-10-2026 (ADR 0053), sense que ningú hagi de fer res: la
    previsió de les 20 h passa a les 21 h, i a qui tenia els avisos de trens
    se li diu una sola vegada que ja no arriben i que hi ha /trens. Si el
    missatge no entra, es torna a provar a la volta següent."""
    for chat, sub in list(subs.items()):
        # La del vespre ja no és una hora de la llista: va a part (ADR 0055).
        if sub.get("resum") in ("20", "21"):
            sub["resum"], sub["nit"] = None, True
        if "trens" in sub.get("avisos", []):
            try:
                envia(api, chat, T[sub["idioma"]]["sense_trens"])
            except Bloquejat:
                treu(subs, estat, chat, "bloqueig")
                continue
            except Exception as ex:
                registra(f"l'avís de la fi dels avisos de trens no ha entrat: {ex}")
                continue
            sub["avisos"] = [x for x in sub["avisos"] if x in TIPUS]


def canvi_canal(api, cm):
    """Juanjo quiere saber cuándo entra y sale alguien del canal (08-10-2026).
    Telegram lo cuenta al bot porque es administrador del canal. Desde el
    11-10-2026, sin el nombre: solo el total (Juanjo: «quita el nombre»; la
    página «Privacitat» dice que la web solo cuenta el total, ADR 0073)."""
    if cm.get("chat", {}).get("username", "").lower() != CANAL.lstrip("@").lower():
        return
    dins = lambda m: m.get("status") in DINS_CANAL or bool(m.get("status") == "restricted" and m.get("is_member"))
    abans, despres = cm.get("old_chat_member") or {}, cm.get("new_chat_member") or {}
    if dins(abans) == dins(despres):
        return
    try:
        total = f" Ja en són {api('getChatMemberCount', chat_id=CANAL)}."
    except Exception:
        total = ""
    que = "alta nova al canal" if dins(despres) else "baixa del canal"
    avisa_juanjo(f"Temps a Montflorit: {que}.{total}")


CONSULTES = ("/dema", "/trens", "/busos", "/transit", "/llum", "/radar", "/sol", "/aire", "/pollen", "/avisos_actius")


def atén(api, subs, update, estat=None):
    if "chat_member" in update:
        canvi_canal(api, update["chat_member"])
        return
    if "callback_query" in update:
        q = update["callback_query"]
        chat = str(q["message"]["chat"]["id"])
        sub = alta(subs, chat, q.get("from", {}))
        if canvia(sub, q.get("data", "")):
            api("editMessageText", chat_id=chat, message_id=q["message"]["message_id"],
                text=T[sub["idioma"]]["menu"], reply_markup={"inline_keyboard": teclat(sub)})
        api("answerCallbackQuery", callback_query_id=q["id"])
        return
    m = update.get("message") or {}
    if m.get("chat", {}).get("type") != "private" or "text" not in m:
        return
    chat = str(m["chat"]["id"])
    ordre = m["text"].split()[0].split("@")[0].lower()
    # Només Juanjo, i no surt al menú: les estadístiques del comptador anònim.
    if ordre == "/estadistiques" and chat == chat_juanjo():
        envia(api, chat, text_estadistiques())
        return
    if ordre.startswith("/"):
        try:
            compta(ordre, chat)
        except Exception as ex:              # el comptador no pot aturar el bot
            registra(f"comptador: {ex}")
    if ordre == "/baixa":
        idioma = (subs.get(chat) or nou_subscriptor(m.get("from", {})))["idioma"]
        treu(subs, estat, chat, "baixa")
        envia(api, chat, T[idioma]["baixa"])
        return
    nou = chat not in subs
    if nou and ordre not in ("/start", "/avisos", "/menu", "/avui", "/resum", "/ara") + CONSULTES:
        # Quien escribe cualquier cosa sin haber empezado solo recibe la ayuda.
        envia(api, chat, T[nou_subscriptor(m.get("from", {}))["idioma"]]["ajuda"])
        return
    sub = alta(subs, chat, m.get("from", {}))
    t = T[sub["idioma"]]
    if ordre == "/start":
        envia(api, chat, t["benvinguda"], html=True)
        # A quien llega de nuevo se le dice qué se le ha marcado ya (Juanjo, 07-10-2026).
        envia(api, chat, (t["inici"] + " " if nou else "") + t["menu"], teclat(sub))
    elif ordre in ("/avisos", "/menu"):
        envia(api, chat, t["menu"], teclat(sub))
    # /avui des del 17-10-2026 (Juanjo: «sería más lógico poner /avui»); /resum
    # continua funcionant per a qui ja el fa servir, però ja no s'anuncia.
    elif ordre in ("/avui", "/resum"):
        moment = ara()
        envia_resum(api, chat, resum(llegeix(os.path.join(DADES, "montflorit.json"), {}), sub["idioma"], moment, avui=True, telegram=True),
                    imatge_resum(sub["idioma"], moment, avui=True))
    elif ordre == "/ara":
        dades = llegeix(os.path.join(DADES, "montflorit.json"), {})
        envia(api, chat, text_ara_bot(dades, sub["idioma"], ara()) + "\n" + WEB, html=True)
    elif ordre == "/dema":
        moment = ara()
        envia_resum(api, chat, resum(llegeix(os.path.join(DADES, "montflorit.json"), {}), sub["idioma"], moment, dema=True, telegram=True),
                    imatge_resum(sub["idioma"], moment, dema=True))
    elif ordre in CONSULTES:
        dades = llegeix(os.path.join(DADES, "montflorit.json"), {})
        funcio = {"/trens": text_trens_bot, "/busos": text_busos_bot, "/transit": text_transit_bot, "/llum": text_llum_bot,
                  "/radar": text_radar_bot,
                  "/sol": text_sol_bot, "/aire": text_aire_bot, "/pollen": text_pollen_bot,
                  "/avisos_actius": text_avisos_actius}[ordre]
        envia(api, chat, funcio(dades, sub["idioma"], ara()) + "\n" + WEB, html=True)
    else:
        envia(api, chat, t["ajuda"])


# --- Repartir ----------------------------------------------------------------------

def a_repartir(avisos, enviats, moment):
    """Los avisos aún no repartidos y vigentes."""
    res = []
    for a in avisos:
        if a["id"] in enviats:
            continue
        edat = (moment - dt.datetime.fromisoformat(a["hora"])).total_seconds() / 60
        if edat <= VIGENCIA_MIN.get(a["tipus"], 60):
            res.append(a)
    return res


# Quien sigue el canal no recibe por el bot lo que el canal ya le da: avisos de
# riera y peligro y la previsión de las 7 (Juanjo, 07-10-2026). El bot, como
# administrador del canal, puede preguntar quién está; ante la duda o si el
# canal no lo ha recibido, se manda: mejor un aviso repetido que uno perdido.
# El canal va solo en catalán, y aun así no se repite a nadie: quien está en
# el canal ya lo recibe allí (Juanjo, 08-10-2026). El menú del bot lo explica.
DINS_CANAL = ("creator", "administrator", "member")


def al_canal(api, chat, memoria):
    if chat not in memoria:
        try:
            r = api("getChatMember", chat_id=CANAL, user_id=chat) or {}
            memoria[chat] = r.get("status") in DINS_CANAL or bool(r.get("status") == "restricted" and r.get("is_member"))
        except Exception:
            memoria[chat] = False
    return memoria[chat]


def apunta_missatge(estat, clau, chat, idioma, resultat):
    """On ha anat cada avís, per poder-lo corregir (corregeix). Només el
    xat, el número del missatge i l'idioma, i es treu amb l'avís, als 3 dies."""
    if isinstance(resultat, dict) and resultat.get("message_id"):
        estat.setdefault("missatges", {}).setdefault(clau, []).append([chat, resultat["message_id"], idioma])


# Les correccions del revisor (revisor.py, ADR 0101): el NAS les deixa a
# avisos.json i el bot edita els missatges que ja havia enviat, al canal i a
# cada xat. Telegram només deixa editar-los durant 48 hores; els avisos al
# navegador no es poden corregir un cop arribats.
EDITA_MAX_H = 47


def corregeix(api, estat, moment):
    correccions = llegeix(os.path.join(DADES, "avisos.json"), {}).get("correccions") or []
    fetes = estat.setdefault("corregits", {})
    for c in correccions:
        clau, hora = c.get("id"), c.get("hora")
        if not clau or fetes.get(clau) == hora:
            continue
        fetes[clau] = hora
        enviat = (estat.get("enviats") or {}).get(clau)
        if not enviat or moment - dt.datetime.fromisoformat(enviat) > dt.timedelta(hours=EDITA_MAX_H):
            continue
        # Si encara s'està repartint, la resta ja rep el text corregit.
        if clau in estat.get("pendents", {}):
            estat["pendents"][clau]["avis"].update({k: c[k] for k in ("ca", "es") if c.get(k)})
        for chat, missatge, idioma in (estat.get("missatges") or {}).get(clau, []):
            try:
                api("editMessageText", chat_id=chat, message_id=missatge, parse_mode="HTML",
                    text=text_telegram(c.get(idioma) or c["ca"]), disable_web_page_preview=True)
            except Exception as ex:
                registra(f"correcció de {clau} a {chat}: {ex}")
            time.sleep(0.05)
    for k in [k for k in fetes if k not in (estat.get("enviats") or {})]:
        del fetes[k]


def reparteix(api, subs, estat, moment):
    """Reparte los avisos nuevos y vuelve a intentar, cada minuto mientras el
    aviso esté vigente, lo que Telegram no aceptó (el canal o algún chat):
    un fallo pasajero no puede perder un aviso de riera o de peligro (ADR
    0034). Si el canal falla, los suscriptores lo reciben igualmente por el
    bot; cuando el canal lo acepte, quien está en él lo verá repetido."""
    enviats = estat.setdefault("enviats", {})
    pendents = estat.setdefault("pendents", {})     # id: {"avis", "canal", "chats"}
    memoria = {}        # quién está en el canal, preguntado una vez por pasada
    avisos = llegeix(os.path.join(DADES, "avisos.json"), {}).get("avisos", [])
    for a in a_repartir(avisos, enviats, moment):
        enviats[a["id"]] = moment.isoformat(timespec="minutes")
        pendents[a["id"]] = {"avis": a, "canal": a["tipus"] in CANAL_TIPUS,
                             "chats": [c for c, s in subs.items() if a["tipus"] in s["avisos"]]}
    for clau, p in list(pendents.items()):
        a = p["avis"]
        if not a_repartir([a], {}, moment):
            # Ya no está vigente: se deja estar, pero con rastro, y si era de
            # riera o de peligro, Juanjo se entera (auditoría del 07-10-2026).
            if p["canal"] or p["chats"]:
                on = (["el canal"] if p["canal"] else []) + ([f"{len(p['chats'])} chat(s)"] if p["chats"] else [])
                registra(f"aviso {clau} caducado sin entregar a {' y '.join(on)}")
                if a["tipus"] in CANAL_TIPUS:
                    avisa_juanjo(f"Temps a Montflorit: el aviso {clau} ha caducado sin llegar a {' y '.join(on)}. "
                                 "Telegram lo ha rechazado durante toda su vigencia: mira errors.log del bot.")
            del pendents[clau]
            continue
        if p["canal"]:
            try:
                apunta_missatge(estat, clau, CANAL, "ca", envia(api, CANAL, a["ca"], html=True))
                p["canal"] = False
            except Exception as ex:
                registra(f"aviso {clau}: el canal no lo acepta: {ex}")
        al_canal_ok = a["tipus"] in CANAL_TIPUS and not p["canal"]
        queden, motius = [], []
        for chat in p["chats"]:
            sub = subs.get(chat)
            # Quien ha quitado la categoría mientras se reintentaba ya no lo
            # recibe (auditoría del 09-10-2026).
            if not sub or a["tipus"] not in sub["avisos"] or (al_canal_ok and al_canal(api, chat, memoria)):
                continue
            try:
                apunta_missatge(estat, clau, chat, sub["idioma"], envia(api, chat, a[sub["idioma"]], html=True))
            except Bloquejat:
                treu(subs, estat, chat, "bloqueig")
            except Exception as ex:
                queden.append(chat)
                motius.append(str(ex))
            time.sleep(0.05)
        p["chats"] = queden
        if queden:
            registra(f"aviso {clau}: {len(queden)} chat(s) sin entregar: {'; '.join(sorted(set(motius)))}")
        if not p["canal"] and not queden:
            del pendents[clau]
    # Lo repartido hace más de 3 días ya no hace falta recordarlo.
    limit = moment - dt.timedelta(days=3)
    for k in [k for k, v in enviats.items() if dt.datetime.fromisoformat(v) < limit]:
        del enviats[k]
    for k in [k for k in estat.get("missatges", {}) if k not in enviats]:
        del estat["missatges"][k]
    # El resumen diario: primero el del canal, a las 7 y a las 21 (la de mañana);
    # luego el de cada uno, a su hora, salvo a quien ya le ha llegado por el
    # canal. Se apunta como hecho solo cuando Telegram lo acepta: si falla, se
    # reintenta al minuto siguiente mientras dure esa hora.
    hora, avui = str(moment.hour), moment.date().isoformat()
    dades = None
    canal = estat.setdefault("canal_resums", {})
    if "canal_resum" in estat:                       # estat d'abans del 09-10-2026
        canal.setdefault("7", estat.pop("canal_resum"))
    if hora in CANAL_RESUMS and canal.get(hora) != avui:
        dades = llegeix(os.path.join(DADES, "montflorit.json"), {})
        try:
            # El canal, solo en catalán (Juanjo, 08-10-2026).
            envia_resum(api, CANAL, resum(dades, "ca", moment, telegram=True), imatge_resum("ca", moment))
            canal[hora] = avui
        except Exception as ex:
            registra(f"el resumen del canal de las {hora} h no ha entrado: {ex}")
    canal_resum_ok = hora in CANAL_RESUMS and canal.get(hora) == avui
    resums = estat.setdefault("resums", {})
    for chat, sub in list(subs.items()):
        fets = fets_resum(resums.get(chat), sub)
        toca = sub.get("resum") == hora or (hora == HORA_NIT and sub.get("nit"))
        if toca and fets.get(hora) != avui:
            if canal_resum_ok and al_canal(api, chat, memoria):
                resums[chat] = {**fets, hora: avui}
                continue
            dades = dades or llegeix(os.path.join(DADES, "montflorit.json"), {})
            try:
                envia_resum(api, chat, resum(dades, sub["idioma"], moment, telegram=True), imatge_resum(sub["idioma"], moment))
                resums[chat] = {**fets, hora: avui}
            except Bloquejat:
                treu(subs, estat, chat, "bloqueig")
            except Exception as ex:
                registra(f"un resumen de las {hora} h no ha entrado: {ex}")


def fets_resum(fet, sub):
    """Les previsions ja enviades avui a un subscriptor, per hora. Abans del
    09-10-2026 era una sola data: la de la seva hora (ADR 0055)."""
    if isinstance(fet, dict):
        return fet
    return {sub.get("resum"): fet} if fet and sub.get("resum") else {}


def actualitza_repo(estat):
    """Pone al día la copia del repositorio, como mucho una vez por hora, y
    solo hasta el último commit con las pruebas de GitHub en verde
    (desplegament.py, ADR 0038); mientras se espera a unas pruebas, cada
    vuelta. Si la copia es tan vieja que no trae desplegament.py, git pull."""
    pendent = estat.get("desplegament", {}).get("proves_pendents")
    if not pendent and time.time() - estat.get("pull", 0) < 3600:
        return
    estat["pull"] = time.time()
    try:
        sys.path.insert(0, REPO)
        import desplegament
        desplegament.actualitza(REPO, estat.setdefault("desplegament", {}), registra)
    except ImportError:
        subprocess.run(["git", "-C", REPO, "pull", "-q", "--ff-only"], check=False, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as ex:
        registra(f"no se ha podido poner al día el repositorio: {ex}")


def volta():
    os.makedirs(BASE, exist_ok=True)
    cadenat = open(os.path.join(BASE, "bot.lock"), "w")
    try:
        fcntl.flock(cadenat, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return          # la vuelta anterior aún no ha acabado
    api = Api(llegeix(os.path.join(BASE, "config.json"), {})["token"])
    subs = llegeix(SUBS, {})
    estat = llegeix(ESTAT, {})
    neteja(subs, estat)
    migra(api, subs, estat)
    actualitza_repo(estat)
    fi = time.time() + DURADA_S
    while True:
        reparteix(api, subs, estat, ara())
        corregeix(api, estat, ara())
        desa(SUBS, subs)
        desa(ESTAT, estat)
        queda = int(fi - time.time())
        if queda < 3:
            break
        try:
            updates = api("getUpdates", temps=queda + 10, offset=estat.get("offset"),
                          timeout=min(queda, 25), allowed_updates=["message", "callback_query", "chat_member"]) or []
        except Exception as ex:
            registra(f"getUpdates: {ex}")
            time.sleep(5)
            continue
        for u in updates:
            estat["offset"] = u["update_id"] + 1
            try:
                atén(api, subs, u, estat)
            except Exception as ex:
                registra(f"al atender un mensaje: {ex}")
        desa(SUBS, subs)
        desa(ESTAT, estat)


def mostra_estat():
    subs = llegeix(SUBS, {})
    estat = llegeix(ESTAT, {})
    print(f"Subscriptors: {len(subs)}")
    for x in TIPUS:
        print(f"  {x}: {sum(x in s['avisos'] for s in subs.values())}")
    print(f"  resum: {sum(bool(s.get('resum')) for s in subs.values())}")
    print(f"Avisos repartits (3 dies): {len(estat.get('enviats', {}))}")
    print(text_estadistiques())
    pendents = estat.get("pendents") or {}
    if pendents:
        print(f"Pendents d'entregar: {', '.join(pendents)}")
    try:
        with open(os.path.join(BASE, "errors.log"), encoding="utf-8") as f:
            darrers = f.readlines()[-5:]
        print("Últims errors:\n" + "".join(darrers), end="")
    except OSError:
        pass


def text_push():
    """Los avisos en el navegador (bot/push.py, ADR 0048), en el recuento."""
    push = llegeix(os.path.join(BASE, "push.json"), {})
    n = lambda x: sum(x in s.get("avisos", []) for s in push.values())
    return (f"Avisos en el navegador: {len(push)} dispositivos (riera {n('riera')}, peligro {n('perill')}, "
            f"lluvia {n('pluja')}, previsión diaria "
            f"{sum(bool(s.get('resum')) for s in push.values())}).\n")


def text_moviments(fins=None):
    """Cuántas altas y bajas en los siete días antes de «fins» (ADR 0084)."""
    fins = fins or ara().date()
    des_de = (fins - dt.timedelta(days=7)).isoformat()
    setmana = [m for m in llegeix(os.path.join(BASE, "moviments.json"), []) if des_de <= m["dia"] < fins.isoformat()]
    n = lambda canal, tipus: sum(m["canal"] == canal and m["tipus"] == tipus for m in setmana)
    q = lambda k, una, moltes: f"{k} {una if k == 1 else moltes}"
    return (f"Últimos 7 días: avisos de la web, {q(n('web', 'alta'), 'alta', 'altas')}, "
            f"{q(n('web', 'baixa'), 'baja', 'bajas')} y {q(n('web', 'morta'), 'dirección muerta', 'direcciones muertas')}; "
            f"bot, {q(n('bot', 'alta'), 'alta', 'altas')}, {q(n('bot', 'baixa'), 'baja', 'bajas')} y "
            f"{q(n('bot', 'bloqueig'), 'bloqueo', 'bloqueos')}.\n")


def informe():
    """Los lunes, a Juanjo, con su bot de avisos (el del vigía de IONOS):
    cuántos suscriptores hay y qué eligen, y cuántos miembros tiene el canal."""
    subs = llegeix(SUBS, {})
    n = lambda x: sum(x in s["avisos"] for s in subs.values())
    try:
        canal = Api(llegeix(os.path.join(BASE, "config.json"), {})["token"])("getChatMemberCount", chat_id=CANAL)
    except Exception:
        canal = "?"
    text = (f"Temps a Montflorit: {len(subs)} suscriptores en el bot (riera {n('riera')}, peligro {n('perill')}, "
            f"lluvia {n('pluja')}, previsión diaria "
            f"{sum(bool(s.get('resum')) for s in subs.values())}) y {canal} miembros en el canal.\n"
            + text_push()
            + text_moviments()
            + text_estadistiques(dies=(7,)))
    propi = llegeix(os.environ.get("AVISAR_CONFIG", os.path.expanduser("~/.vigilancia-nas/config.json")), {})
    if propi.get("token") and propi.get("chat_id"):
        Api(propi["token"])("sendMessage", chat_id=propi["chat_id"], text=text)
    print(text)


if __name__ == "__main__":
    {"estat": mostra_estat, "informe": informe}.get(sys.argv[1] if sys.argv[1:] else "", volta)()
