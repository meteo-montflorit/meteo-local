#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Situaciones de peligro en casa según lo que mide y prevé la propia página
(ADR 0018).

Se comparan las estaciones (ahora) y la previsión de la página de casa (24
horas) con los umbrales bajo y alto de los avisos de peligro de Meteocat para
Cerdanyola (config.RISC_LLINDARS; hasta el 16-10-2026, los de AEMET): lluvia
en 30 minutos (medida), en 3 horas y en 24 horas (prevista), rachas de
viento, calor, frío y nieve. Los dos umbrales dan el nivel amarillo y el
naranja; el rojo de Meteocat también depende de la probabilidad, que la web
no tiene para estos fenómenos. Los avisos de AEMET y los planes de Protección Civil no cuentan
aquí: ya salen en la página, y Juanjo solo quiere el aviso cuando la previsión
propia ve el peligro.

Hay aviso cuando aparece un riesgo o sube de nivel, y una vez cuando ya no
queda ninguno (un riesgo se da por acabado tras RISC_FI_H horas sin verlo,
para que el vaivén de los modelos no repita mensajes). Lo reciben los
suscriptores del bot, el canal y las notificaciones (avisos_bot.py, con la
misma detección). Hasta el 08-10-2026 el NAS lo mandaba además a Juanjo por
Telegram; ahora «avisa» solo lo apunta en el registro del NAS.

Uso:
  python3 riscos.py avisa CASA.json   compara con lo ya visto y, si toca, lo dice
  python3 riscos.py estat             lo que se tiene por activo
"""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
import json
import os
import sys

import config as C
import hora as H

NIVELLS = ("groc", "taronja", "vermell")
DIR = os.environ.get("REGISTRE_DIR", "/estat/registre")
ESTADO = os.path.join(os.path.dirname(DIR), "riscos.json")
WEB = "https://meteo-montflorit.github.io/"

UNITATS = {"pluja_30min": "mm", "pluja_3h": "mm", "pluja_24h": "mm", "ratxa": "km/h", "calor": "°C",
           "fred": "°C", "neu_24h": "cm"}


def nivell(tipus, valor):
    """Nivel que alcanza el valor (el umbral bajo de Meteocat, amarillo; el
    alto, naranja), o None. Hay que pasar el umbral, no basta con llegar."""
    if valor is None:
        return None
    res = None
    for n, llindar in zip(NIVELLS, C.RISC_LLINDARS[tipus]):
        if (valor < llindar) if tipus == "fred" else (valor > llindar):
            res = n
    return res


TEMPERATURES = ("calor", "fred")


def num(x, tipus=None):
    """Sin decimales; la temperatura, con uno si no es un grado entero, como
    los umbrales de Meteocat (36,8 °C)."""
    # La neu, també amb un decimal: «0 cm» d'una neu de 0,3 cm es contradeia
    # (inventari del 18-10-2026).
    # Les meitats, cap amunt, com la web (Math.round, toFixed): Python arrodoneix
    # a parell i la mateixa ratxa de 92,5 km/h sortia 92 a l'avís i 93 a la
    # taula (revisor, 19-10-2026).
    d = 1 if tipus in TEMPERATURES + ("neu_24h",) and abs(x - round(x)) >= 0.05 else 0
    t = str(Decimal(str(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
    return t.replace(".", ",").replace("-", "−")


def quan(ini, fin, ahora):
    """«avui de 15 a 18 h», «demà de 2 a 5 h»."""
    # En hora de Madrid, la de la gent (ADR 0128).
    ini, fin, ahora = H.local(ini), H.local(fin), H.local(ahora)
    dia = "avui" if ini.date() == ahora.date() else "demà" if ini.date() == ahora.date() + dt.timedelta(days=1) \
        else ini.strftime("%d/%m")
    return f"{dia} de {ini.hour} a {fin.hour} h"


TEXTOS = {
    "pluja_30min": (None, "Ara plou amb molta intensitat: {v} mm en l'última mitja hora."),
    "pluja_3h": ("Pluja intensa prevista: {v} mm en 3 hores, {q}.", "Ha plogut molt: {v} mm en les últimes 3 hores."),
    "pluja_24h": ("Molta pluja prevista: {v} mm en 24 hores, {q}.", None),
    "ratxa": ("Vent fort previst: ratxes de fins a {v} km/h, {q}.", None),
    "calor": ("Calor intensa prevista: fins a {v} °C, {q}.", "Ara fa calor intensa: {v} °C."),
    "fred": ("Fred intens previst: fins a {v} °C, {q}.", "Ara fa fred intens: {v} °C."),
    "neu_24h": ("Neu prevista: {v} cm en les pròximes 24 hores.", None),
}


def risc(tipus, origen, valor, ini=None, fin=None, ahora=None, ratxes=None):
    n = nivell(tipus, valor)
    if not n:
        return None
    previst, mesura = TEXTOS[tipus]
    plantilla = previst if origen == "previsio" else mesura
    text = plantilla.format(v=num(valor, tipus), q=quan(ini, fin, ahora) if ini else "")
    llindar = C.RISC_LLINDARS[tipus][NIVELLS.index(n)]
    return {"clau": f"{origen}:{tipus}", "tipus": tipus, "origen": origen, "nivell": n,
            "valor": round(valor, 1), "llindar": llindar, "unitat": UNITATS[tipus],
            "des_de": ini and H.clau(ini),
            "fins": fin and H.clau(fin), "text": text,
            "font": font(tipus, origen, ratxes)}


# D'on surt cada risc i quant s'hi pot confiar, a la línia de sota (Juanjo,
# 19-10-2026: «hay que indicar el origen de la alerta y a ser posible la
# validez que tiene» i «dado que viene de un modelo no debe decir que la ha
# calculado nuestra web»). Abans, el missatge deia «Calculat per aquesta
# aplicació» d'unes ratxes que només preveia AROME.
NOMS_MODELS = {"meteofrance_arome_france_hd": "AROME HD", "meteofrance_arome_france": "AROME",
               "icon_eu": "ICON-EU"}
MF = ("previsió de Météo-France per a Montflorit",
      "previsión de Météo-France para Montflorit")
FONTS = {
    ("ara", "pluja"): ("Mesurat: la mediana de les estacions del barri.",
                       "Medido: la mediana de las estaciones del barrio."),
    ("ara", "temp"): ("Mesurat: les estacions de la part baixa del barri.",
                      "Medido: las estaciones de la parte baja del barrio."),
    ("previsio", "pluja"): ("Origen: la pluja del model que en dona més (AROME HD, AROME o ICON-EU) i, les "
                            "primeres hores, el radar i les estacions del barri. Els mil·límetres diuen com seria "
                            "la pluja; si n'hi haurà, ho diu la probabilitat de la taula.",
                            "Origen: la lluvia del modelo que da más (AROME HD, AROME o ICON-EU) y, las primeras "
                            "horas, el radar y las estaciones del barrio. Los milímetros dicen cómo sería la "
                            "lluvia; si la habrá, lo dice la probabilidad de la tabla."),
    ("previsio", "temp"): (f"Origen: {MF[0]}, corregida amb el que ha mesurat una estació del barri vora la "
                           "riera. L'error mitjà és d'un grau.",
                           f"Origen: {MF[1]}, corregida con lo que ha medido una estación del barrio junto a "
                           "la riera. El error medio es de un grado."),
    ("previsio", "neu_24h"): (f"Origen: {MF[0]}.", f"Origen: {MF[1]}."),
}


def font(tipus, origen, ratxes=None):
    """{"ca", "es"}: d'on surt el risc i, si se sap, quant s'hi pot confiar.
    Les ratxes, amb quants dels models fins hi arriben (ratxes: {model: la
    més forta del tram})."""
    if tipus == "ratxa":
        # La xifra de l'avís és la del model que en preveu més (casa.ratxa_modelos,
        # com la pluja); darrere, quants models la veuen i fins a quant cadascun
        # (Juanjo, 19-10-2026: «que significa esta frase…?», davant de «2 hi
        # arriben (AROME HD, 92; AROME, 89; ICON-EU, 12 km/h)», i «hazlo»).
        vals = {NOMS_MODELS.get(m, m): v for m, v in (ratxes or {}).items() if v is not None}
        if vals:
            qui = max(vals, key=vals.get)
            ca = [f"Origen: el model que en preveu més, {qui}."]
            es = [f"Origen: el modelo que prevé más, {qui}."]
        else:
            ca = ["Origen: el model que en preveu més dels que es consulten (AROME HD, AROME i ICON-EU)."]
            es = ["Origen: el modelo que prevé más de los que se consultan (AROME HD, AROME e ICON-EU)."]
        if vals:
            llindar = num(C.RISC_LLINDARS["ratxa"][0])
            n, total = sum(1 for v in vals.values() if nivell("ratxa", v)), len(vals)
            dalt = [(m, v) for m, v in vals.items() if nivell("ratxa", v)]
            baix = [(m, v) for m, v in vals.items() if not nivell("ratxa", v)]

            def uneix(trossos, i):
                return trossos[0] if len(trossos) == 1 else "; ".join(trossos[:-1]) + f", {i} " + trossos[-1]

            # Els que hi arriben, units; darrere d'un punt i coma, els altres.
            def llista(i, fins, nomes):
                grups = [uneix([f"{m}, {paraula} {num(v)} km/h" for m, v in g], i)
                         for g, paraula in ((dalt, fins), (baix, nomes)) if g]
                return "; ".join(grups)

            l_ca, l_es = llista("i", "fins a", "només"), llista("y", "hasta", "solo")
            if n == total:
                ca.append(f"Els {total} models que es consulten també preveuen ratxes de més de {llindar} km/h: {l_ca}.")
                es.append(f"Los {total} modelos que se consultan también prevén rachas de más de {llindar} km/h: {l_es}.")
            elif n == 0:
                ca.append(f"Cap dels {total} models que es consulten no preveu ratxes de més de {llindar} km/h: "
                          f"{l_ca}. Previsió poc segura.")
                es.append(f"Ninguno de los {total} modelos que se consultan prevé rachas de más de {llindar} km/h: "
                          f"{l_es}. Previsión poco segura.")
            else:
                verb_ca, verb_es = ("preveu", "prevé") if n == 1 else ("preveuen", "prevén")
                nomes_ca, nomes_es = ("només ", "solo ") if 2 * n < total else ("", "")
                ca.append(f"Dels {total} models que es consulten, {nomes_ca}{n} també {verb_ca} ratxes de més de "
                          f"{llindar} km/h: {l_ca}." + (" Previsió poc segura." if 2 * n < total else ""))
                es.append(f"De los {total} modelos que se consultan, {nomes_es}{n} también {verb_es} rachas de más de "
                          f"{llindar} km/h: {l_es}." + (" Previsión poco segura." if 2 * n < total else ""))
        ca.append("Una ratxa prevista pot arribar abans, després o en un altre lloc, sobretot amb tempesta.")
        es.append("Una racha prevista puede llegar antes, después o en otro lugar, sobre todo con tormenta.")
        return {"ca": " ".join(ca), "es": " ".join(es)}
    clau = (origen if origen == "ara" else "previsio",
            "pluja" if tipus.startswith("pluja") else "temp" if tipus in TEMPERATURES else tipus)
    if clau not in FONTS:
        return None
    return dict(zip(("ca", "es"), FONTS[clau]))


TRAM_PAUSA_H = 2


def pitjor_tram(hores, tipus, valor_de):
    """De las horas que pasan el umbral amarillo, el peor valor y el tramo
    de horas seguidas que lo contiene."""
    dins = [(f, valor_de(f)) for f in hores if nivell(tipus, valor_de(f))]
    if not dins:
        return None
    cmp = min if tipus == "fred" else max
    valor = cmp(v for _, v in dins)
    # Tramos de horas seguidas (una pausa de hasta TRAM_PAUSA_H horas no los
    # separa): el que tiene el peor valor. Antes se unían la primera y la
    # última hora aunque hubiera media noche sin riesgo en medio («avui de
    # 15 a 4 h»).
    trams, tram = [], [dins[0]]
    for ant, act in zip(dins, dins[1:]):
        pausa = H.llegeix(act[0]["hora"]) - H.llegeix(ant[0]["fins"])
        if pausa <= dt.timedelta(hours=TRAM_PAUSA_H):
            tram.append(act)
        else:
            trams.append(tram)
            tram = [act]
    trams.append(tram)
    tram = next(t for t in trams if any(v == valor for _, v in t))
    ini = H.llegeix(tram[0][0]["hora"])
    fin = H.llegeix(tram[-1][0]["fins"])
    return valor, ini, fin


def de_la_previsio(hores, ahora):
    res = []
    if not hores:
        return res
    for tipus, valor_de in (("ratxa", lambda f: f.get("ratxa")),
                            ("calor", lambda f: f.get("temperatura")),
                            ("fred", lambda f: f.get("temperatura"))):
        t = pitjor_tram(hores, tipus, valor_de)
        if t:
            ratxes = None
            if tipus == "ratxa":
                # La més forta de cada model en les hores del tram.
                dins = [f for f in hores if t[1] <= H.llegeix(f["hora"]) < t[2]]
                ratxes = {}
                for f in dins:
                    for m, v in (f.get("ratxes_models") or {}).items():
                        if v is not None and (ratxes.get(m) is None or v > ratxes[m]):
                            ratxes[m] = v
                        ratxes.setdefault(m, None)
            res.append(risc(tipus, "previsio", t[0], t[1], t[2], ahora, ratxes))
    # La lluvia, en las horas seguidas que más acumulan: 3 y 24. La media
    # hora de Meteocat no se puede prever con modelos que dan horas enteras.
    # Només les hores en què la pàgina diu que pot ploure (probabilitat del
    # 20 % o més, C.PROB_ATENCION): els mil·límetres són el màxim dels models i
    # diuen com seria la pluja, no si n'hi haurà. Abans sortia «Pluja intensa
    # prevista» al costat de «Sense pluja prevista» (inventari del 18-10-2026).
    # Si cap d'aquestes hores arriba al 50 %, es diu la probabilitat.
    pot = lambda f: f.get("probabilitat") is None or f["probabilitat"] >= C.PROB_ATENCION  # noqa: E731
    for tipus, n in (("pluja_3h", 3), ("pluja_24h", 24)):
        millor = None
        for i in range(max(0, len(hores) - n + 1)):
            tram = hores[i:i + n]
            mm = sum(f.get("pluja_mm") or 0 for f in tram if pot(f))
            if millor is None or mm > millor[0]:
                millor = (mm, tram)
        if millor and nivell(tipus, millor[0]):
            tram = millor[1]
            r = risc(tipus, "previsio", millor[0], H.llegeix(tram[0]["hora"]),
                     H.llegeix(tram[-1]["fins"]), ahora)
            probs = [f["probabilitat"] for f in tram if pot(f) and f.get("probabilitat") is not None]
            if probs and max(probs) < 0.5:
                r["prob"] = round(max(probs) * 100)
                r["text"] = r["text"][:-1] + f" (probabilitat fins al {r['prob']} %)."
            res.append(r)
    # Arrodonida com es diu: per sota d'1 mm de neu, no n'hi ha.
    neu = round(sum(f.get("neu") or 0 for f in hores), 1)
    r = risc("neu_24h", "previsio", neu)
    if r:
        res.append(r)
    return res


def de_l_estacio(casa):
    """Lo que se mide ahora: la lluvia de la última media hora y de las tres
    últimas horas de la red del barrio (casa.consens: la mediana de casa y de
    las vecinas que cuentan), y la temperatura de casa. Ni el viento (el
    anemómetro no va bien) ni la lluvia de 24 horas, que las estaciones no dan
    en cada pasada: esos riesgos salen solo de la previsión."""
    res = []
    if not casa:
        return res
    for tipus in ("pluja_30min", "pluja_3h"):
        if casa.get(tipus):
            r = risc(tipus, "ara", casa[tipus])
            if r:
                res.append(r)
    if casa.get("temperatura") is not None:
        for tipus in ("calor", "fred"):
            r = risc(tipus, "ara", casa["temperatura"])
            if r:
                res.append(r)
    return res


HORES_RISC = 24     # la tabla puede llegar a 38 para dar mañana entero (ADR 0041); el riesgo, no


def detecta(salida, ahora):
    """Riesgos de ahora y de las próximas 24 horas, el peor nivel primero."""
    hores = (salida.get("hores") or [])[:HORES_RISC]
    res = de_l_estacio(salida.get("ara_casa")) + de_la_previsio(hores, ahora)
    return sorted(res, key=lambda r: -NIVELLS.index(r["nivell"]))


# --- Aviso por Telegram (solo en el NAS) ---------------------------------

def llegeix_estat():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"actius": {}}


def desa_estat(estat):
    with open(ESTADO + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estat, f, ensure_ascii=False, indent=1)
    os.replace(ESTADO + ".tmp", ESTADO)


def compara(estat, salida, ahora):
    """Pone al día el estado y devuelve el mensaje que toca, o None."""
    actius = estat.setdefault("actius", {})
    riscos = salida.get("riscos") or []
    # Si falta una fuente, lo suyo no se da por acabado.
    sense = set()
    if not salida.get("hores"):
        sense.add("previsio")
    if not salida.get("ara") and not salida.get("ara_casa"):
        sense.add("ara")
    nous = []
    for r in riscos:
        abans = actius.get(r["clau"])
        if not abans or NIVELLS.index(r["nivell"]) > NIVELLS.index(abans["nivell"]):
            nous.append(r)
            actius[r["clau"]] = {"nivell": r["nivell"]}
        actius[r["clau"]]["vist"] = H.clau(ahora)
    acabats = []
    for clau, a in list(actius.items()):
        if clau.split(":")[0] in sense:
            continue
        if ahora - H.llegeix(a["vist"]) >= dt.timedelta(hours=C.RISC_FI_H):
            acabats.append(clau)
            del actius[clau]
    if nous:
        pitjor = max(nous, key=lambda r: NIVELLS.index(r["nivell"]))["nivell"]
        linies = [f"Temps a casa: risc {pitjor}."]
        linies += [f"{r['text']} (llindar {r['nivell']} de Meteocat: {num(r['llindar'], r['tipus'])} {r['unitat']})"
                   for r in nous]
        linies.append(WEB)
        return "\n".join(linies)
    if acabats and not actius:
        return "Temps a casa: ja no es preveu ni es mesura cap situació de perill."
    return None


def avisa(ruta, ahora=None):
    ahora = ahora or H.ara()
    with open(ruta, encoding="utf-8") as f:
        salida = json.load(f)
    estat = llegeix_estat()
    text = compara(estat, salida, ahora)
    desa_estat(estat)
    if text:
        print(text)         # al registro del NAS; ya no se manda a Juanjo (ADR 0018)
    return text


if __name__ == "__main__":
    ordre = sys.argv[1] if len(sys.argv) > 1 else ""
    if ordre == "avisa" and len(sys.argv) > 2:
        avisa(sys.argv[2])
    elif ordre == "estat":
        print(json.dumps(llegeix_estat(), ensure_ascii=False, indent=1))
    else:
        print(__doc__)
        sys.exit(1)
