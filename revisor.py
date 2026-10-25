#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El revisor de coherencia de Temps a Montflorit (ADR 0101).

Juanjo, 18-10-2026, tras varios días de contradicciones que nadie veía (la
ficha de Meteocat con las horas del día anterior, «Pluja a sobre» sin que
lloviera, una cuenta atrás de lluvia junto a «sense pluja»): «no debería
comprobar la coherencia de todo lo que se anuncia en la web? … la ia debe
estar atenta a ellas, también cuando se mandan las previsiones, alertas».

Dos capas, en el NAS, después de cada publicación:

- **Reglas fijas** (`regles`), en cada pasada y sin IA: lo que ya sabemos que
  no puede pasar. Una que falla despierta también al revisor.
- **El revisor con IA** (Claude, `C.REVISOR_MODEL`, con el Claude Code y el
  token del contenedor), solo cuando hace falta (`toca`): ha salido un aviso
  hacia los vecinos, ha cambiado lo que concluye la web (llueve o no, el modo
  vigilancia, los avisos y sus niveles) o es la hora de los resúmenes del
  día. Lee las páginas ya dibujadas (Chromium sin pantalla), como las lee un
  vecino, el resumen del bot y los avisos enviados, junto con lo medido y lo
  oficial, y dice qué se contradice.

Qué puede hacer con lo que encuentra (Juanjo, 18-10-2026, «me parece bien»):

- **Corregir solo**, sin preguntar, lo que solo quita información falsa o
  caducada: líneas de una ficha de «Perill» o de un aviso ya enviado
  (`treu_linies`). Lo comprueba el código, no la IA: el texto nuevo tiene que
  ser el de antes con líneas de menos. El bot edita también los mensajes de
  Telegram de las últimas 48 horas (bot.corregeix).
- **Preguntar a Juanjo**, con botones (Aplicar / Dejar), lo demás: cambiar un
  texto, cerrar una ficha. Nunca inventa un aviso ni envía nada a los vecinos.
- **Avisar siempre** a Juanjo de lo que ha hecho, con el texto de antes y el de
  después y un botón para deshacerlo, y de lo que solo se arregla en el código.

Uso:
  python3 revisor.py revisa CASA.json AVISOS.json   después de cada publicación (reloj.sh)
  python3 revisor.py respostes                      los botones de Juanjo (cada minuto)
  python3 revisor.py prova CASA.json AVISOS.json    revisa ya, sin aplicar ni avisar (imprime)
  python3 revisor.py estat                          las últimas revisiones
"""
import datetime as dt
import fcntl
import functools
import hashlib
import html.parser
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import config as C
import hora as H

ARREL = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.dirname(os.environ.get("REGISTRE_DIR", "/estat/registre"))
ESTAT = os.path.join(DIR, "revisor.json")
CORRECCIONS = os.path.join(DIR, "correccions.json")
REGISTRE = os.path.join(os.environ.get("REGISTRE_DIR", "/estat/registre"), "revisor.jsonl")
INSTRUCCIONS = os.path.join(ARREL, "revisor-instruccions.md")
CONFIG_BOT = os.path.expanduser("~/.config/avisar-juanjo/config.json")
# Una corrección aplicada: el reloj publica en el minuto siguiente (reloj.sh).
PUBLICA_ARA = os.path.join(DIR, "publica-ara")

# Las páginas que se leen, en catalán: las que dicen algo del tiempo de ahora.
PAGINES = ("index.html", "sortir.html", "perill.html")
DIES = ("dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge")


def ara():
    # L'hora de Madrid, sigui quina sigui la del sistema (ADR 0128).
    return H.local(H.ara())


def llegeix(ruta, defecte):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecte


def desa(ruta, dades):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dades, f, ensure_ascii=False, indent=1)
    os.replace(ruta + ".tmp", ruta)


def empremta(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


# --- Lo que concluye la web ----------------------------------------------------------

def conclusions(casa, avisos):
    """Lo que la web da por hecho ahora, para saber si ha cambiado: si llueve
    (el estado único de la lluvia, ADR 0101), el modo vigilancia, los avisos
    oficiales y propios con su nivel, las fichas abiertas de «Perill»."""
    pluja = casa.get("pluja_ara") or {}
    return {
        "pluja": pluja.get("estat"),
        "mode": (casa.get("modo") or {}).get("aviso") if isinstance(casa.get("modo"), dict) else casa.get("modo"),
        "smp": sorted((f.get("fenomen"), f.get("nivell")) for f in ((casa.get("smp") or {}).get("fenomens") or [])),
        "aemet": sorted((a.get("tipo"), a.get("nivel")) for a in casa.get("avisos") or [] if not a.get("cobert")),
        "plans": sorted((p.get("pla"), p.get("fase")) for p in casa.get("plans") or []),
        "riscos": sorted((r.get("clau"), r.get("nivell")) for r in casa.get("riscos") or []),
        "riera": [r.get("nivell") for r in casa.get("perill_riera") or []],
        "incendis": sorted(i.get("id") for i in ((casa.get("entorn") or {}).get("incendis") or [])),
        "fitxes": sorted((e["clau"], e.get("nivell")) for e in avisos.get("historial") or [] if not e.get("fi")),
    }


# --- Reglas fijas ---------------------------------------------------------------------

FRANJA = re.compile(r"\b(" + "|".join(DIES) + r") (\d{1,2}) de (\d{1,2}) a (\d{1,2}) h")


def franja_passada(text, moment):
    """Las franjas «dissabte 17 de 19 a 22 h» de un texto que ya han acabado."""
    res = []
    for m in FRANJA.finditer(text):
        dia, fi = int(m.group(2)), int(m.group(4))
        # El día del mes, en los 7 días de antes o de después de hoy.
        for delta in range(-7, 8):
            d = H.dia_local(moment) + dt.timedelta(days=delta)
            if d.day == dia and DIES[d.weekday()] == m.group(1):
                # Hores de rellotge de Madrid (ADR 0128).
                final = H.de_rellotge(d, fi)
                if final <= moment:
                    res.append(m.group(0))
                break
    return res


def regles(casa, avisos, moment, textos=None):
    """Lo que ya sabemos que no puede pasar. Cada problema: {regla, on, que}."""
    problemes = []
    # 1. Ninguna ficha abierta habla de horas que ya han pasado (18-10-2026).
    for e in avisos.get("historial") or []:
        if e.get("fi"):
            continue
        for linia in (e.get("ca") or "").split("\n")[1:]:
            passades = franja_passada(linia, moment)
            if passades:
                problemes.append({"regla": "franja_passada", "on": f"fitxa {e['clau']}",
                                  "que": f"parla d'hores ja passades ({', '.join(passades)}): «{netja(linia)}»"})
        # 2. «Observat ara» solo mientras Meteocat da la observación.
        if "Observat ara" in (e.get("ca") or "") and e["clau"].startswith("meteocat:"):
            obs = [a for a in ((casa.get("smp") or {}).get("avisos") or []) if a.get("tipus") != "previsio"
                   and not franja_passada(" ".join(f"{DIES[dt.date.fromisoformat(d).weekday()]} "
                                                   f"{dt.date.fromisoformat(d).day} de {i} a {f} h"
                                                   for d, fr in a["dies"].items() for i, f in fr), moment)]
            if not obs:
                problemes.append({"regla": "observat_ara", "on": f"fitxa {e['clau']}",
                                  "que": "diu «Observat ara» però Meteocat ja no dona cap avís d'observació vigent"})
    # 3. La lluvia: un solo estado para toda la web (ADR 0101).
    pluja = casa.get("pluja_ara") or {}
    hores = casa.get("hores") or []
    if pluja.get("estat") in ("plou", "radar_sobre") and hores:
        h0 = hores[0]
        if not h0.get("plou_ara") and pluja.get("estat") == "plou":
            problemes.append({"regla": "pluja_hora", "on": "previsió per hores",
                              "que": "a la xarxa del barri plou, però l'hora en curs no diu «Plou ara»"})
    # 4. Lo que leen los vecinos: llueve y no llueve a la vez.
    for pag, text in (textos or {}).items():
        t = text.lower()
        if "no plou" in t and ("pluja a sobre" in t and "segons el radar" not in t):
            problemes.append({"regla": "plou_i_no_plou", "on": pag,
                              "que": "diu «No plou» i «Pluja a sobre» alhora, sense dir que és el radar"})
    return problemes


def netja(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


# --- Las páginas, como las ve un vecino ---------------------------------------------

class Text(html.parser.HTMLParser):
    """El texto visible de una página: sin scripts, estilos ni iconos, con un
    salto de línea en cada bloque."""
    BLOCS = {"p", "div", "li", "h1", "h2", "h3", "h4", "section", "article", "tr", "summary", "details",
             "header", "footer", "nav", "br", "table", "ul", "ol", "dt", "dd"}
    FORA = {"script", "style", "svg", "noscript", "template", "head"}

    def __init__(self):
        super().__init__()
        self.trossos, self.fora = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.FORA:
            self.fora += 1
        if tag in self.BLOCS:
            self.trossos.append("\n")
        # La barra d'avís de la taula per hores: si fa una sola fila no hi cap
        # el text i queda buida, però el botó el porta sencer (19-10-2026: el
        # revisor creia que la fila 6–7 no tenia avís).
        a = dict(attrs)
        if tag == "button" and "boto-franja" in (a.get("class") or "") and not self.fora:
            self.trossos.append(f" {a.get('aria-label') or ''} ")

    def handle_endtag(self, tag):
        if tag in self.FORA and self.fora:
            self.fora -= 1
        if tag in self.BLOCS:
            self.trossos.append("\n")

    def handle_data(self, data):
        if not self.fora:
            self.trossos.append(data)

    def text(self):
        linies = (re.sub(r"\s+", " ", l).strip() for l in "".join(self.trossos).split("\n"))
        return "\n".join(l for l in linies if l)


def text_visible(dom):
    p = Text()
    p.feed(dom)
    return p.text()


def chromium():
    for ordre in (os.environ.get("CHROMIUM"), "chromium", "chromium-browser", "google-chrome"):
        if ordre and shutil.which(ordre):
            return shutil.which(ordre)
    return None


class Silenci(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def pagines(casa_json, avisos_json, navegador=None):
    """{pàgina: text} de la web generada con estos datos, en un servidor local
    de un momento: se genera la web (montflorit.py), se le ponen los datos y
    Chromium la dibuja con su JavaScript, como en el móvil de un vecino."""
    import montflorit
    navegador = navegador or chromium()
    if not navegador:
        return {}
    res = {}
    with tempfile.TemporaryDirectory() as tmp:
        web = os.path.join(tmp, "web")
        montflorit.construeix(web)
        subprocess.run([sys.executable, os.path.join(ARREL, "montflorit.py"), "dades", casa_json,
                        os.path.join(web, "montflorit.json"), avisos_json], check=True, capture_output=True)
        shutil.copy(avisos_json, os.path.join(web, "avisos.json"))
        # Los datos, los de al lado y no los de IONOS: los que se revisan.
        comu = os.path.join(web, "comu.js")
        with open(comu, encoding="utf-8") as f:
            codi = f.read()
        with open(comu, "w", encoding="utf-8") as f:
            f.write(re.sub(r"const DADES_URL = '[^']*';", "const DADES_URL = './';", codi))
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Silenci, directory=web))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            for pag in PAGINES:
                try:
                    r = subprocess.run([navegador, "--headless", "--no-sandbox", "--disable-gpu", "--no-first-run",
                                        "--disable-extensions", f"--user-data-dir={tmp}/perfil",
                                        "--virtual-time-budget=20000", "--dump-dom",
                                        f"http://127.0.0.1:{srv.server_address[1]}/{pag}"],
                                       capture_output=True, text=True, timeout=120)
                    res[pag] = text_visible(r.stdout)
                except subprocess.TimeoutExpired:
                    res[pag] = ""
        finally:
            srv.shutdown()
    return res


# --- Cuándo despertar al revisor ------------------------------------------------------

def nous_missatges(avisos, estat):
    """Los avisos hacia los vecinos que han salido desde la última revisión."""
    # Per moment: avisos.json porta l'hora de Madrid, amb el desfasament de
    # cada moment, i com a text s'ordenaria malament el dia del canvi (ADR 0128).
    darrer = estat.get("darrer_missatge")
    return [a for a in avisos.get("avisos") or [] if a.get("hora") and (not darrer or H.utc(a["hora"]) > H.utc(darrer))]


def toca(estat, casa, avisos, moment, problemes_regles):
    """El motivo para despertar al revisor, o None."""
    if nous_missatges(avisos, estat):
        return "avís enviat"
    for hora in C.REVISOR_HORES:
        clau = f"{moment.date().isoformat()} {hora}"
        if moment.strftime("%H:%M") >= hora and clau not in (estat.get("diaris") or []) \
                and moment.strftime("%H:%M") < f"{int(hora[:2]) + 1:02d}{hora[2:]}":
            return f"resum {hora}"
    darrera = estat.get("darrera")
    espera = darrera and moment - H.llegeix(darrera) < dt.timedelta(minutes=C.REVISOR_MIN_MIN)
    noves = [p for p in problemes_regles if empremta(p) not in (estat.get("regles_vistes") or {})]
    if noves and not espera:
        return "regla"
    if empremta(conclusions(casa, avisos)) != estat.get("conclusions") and not espera:
        return "canvi"
    return None


# --- La pregunta a Claude ------------------------------------------------------------

def context(casa, avisos, textos, moment, motiu, problemes_regles, resum=None, informats=None):
    """Todo lo que el revisor necesita, en un solo texto: lo que dice la web, lo
    que se ha enviado y los datos de los que sale."""
    hores = [{k: h.get(k) for k in ("hora", "temperatura", "probabilitat", "pluja_mm", "plou_ara", "segons_radar",
                                    "segons_estacio", "cel", "vent", "ratxa")}
             for h in (casa.get("hores") or [])[:12]]
    dades = {
        "ara": moment.isoformat(timespec="minutes"),
        "mesurat_ara": casa.get("ara_casa"),
        "pluja_ara": casa.get("pluja_ara"),
        "radar": casa.get("radar"),
        "modo": casa.get("modo"),
        "hores": hores,
        "meteocat": (casa.get("smp") or {}).get("avisos"),
        "aemet": casa.get("avisos"),
        "proteccio_civil": casa.get("plans"),
        "riera": casa.get("perill_riera"),
        "entorn": casa.get("entorn"),
        "riscos_propis": casa.get("riscos"),
    }
    # Les obertes, amb la mateixa regla que «Perill» (perill.js, finalDe): una
    # de l'AEMET que ha passat la seva hora final ja s'ha acabat, sense
    # missatge de final (revisor, 21-10-2026: les creia obertes).
    fitxes = [{k: e.get(k) for k in ("clau", "inici", "nivell", "ca", "fi", "fins")}
              for e in avisos.get("historial") or []
              if not e.get("fi") and not (e.get("fins") and H.llegeix(e["fins"]) <= moment)]
    enviats = [{k: a.get(k) for k in ("id", "hora", "ca")} for a in (avisos.get("avisos") or [])[-6:]]
    trossos = [f"Motiu de la revisió: {motiu}.", "",
               "## Ja informats a Juanjo (no els repeteixis si no han canviat)",
               json.dumps(informats or [], ensure_ascii=False), "",
               "## Regles fixes que ja han fallat", json.dumps(problemes_regles, ensure_ascii=False), "",
               # Amb l'hora de Madrid, com les pàgines i les fitxes: per dins és
               # en UTC (ADR 0128) i la IA veuria desfasaments que no hi són.
               "## Dades (mesurades, radar, previsió i avisos oficials)",
               json.dumps(H.publica(dades), ensure_ascii=False), "",
               "## Fitxes obertes de «Perill» (id: clau + inici)", json.dumps(fitxes, ensure_ascii=False), "",
               "## Últims avisos enviats als veïns", json.dumps(enviats, ensure_ascii=False), ""]
    if resum:
        trossos += ["## Resum del dia que envia el bot", resum, ""]
    for pag, text in textos.items():
        trossos += [f"## Pàgina {pag}, tal com la veu un veí", text[:12000], ""]
    return "\n".join(trossos)


def demana(text, model=None):
    """Claude, una sola respuesta y sin herramientas. Devuelve
    ({problemes}, {cost, durada})."""
    with open(INSTRUCCIONS, encoding="utf-8") as f:
        instruccions = f.read()
    t0 = time.monotonic()
    r = subprocess.run(["claude", "-p", "--model", model or C.REVISOR_MODEL, "--output-format", "json",
                        "--max-turns", "1", "--allowedTools", ""],
                       input=f"{instruccions}\n\n---\n\n{text}", capture_output=True, text=True, timeout=600)
    sortida = json.loads(r.stdout)
    resposta = sortida.get("result") or ""
    m = re.search(r"\{.*\}", resposta, re.S)
    res = json.loads(m.group(0)) if m else {"problemes": []}
    return res, {"cost_usd": sortida.get("total_cost_usd"), "segons": int(time.monotonic() - t0),
                 "tokens": (sortida.get("usage") or {}).get("input_tokens")}


# --- Las correcciones -----------------------------------------------------------------

def clau_fitxa(clau, inici):
    """La clau d'una fitxa a correccions.json: amb el començament en UTC, igual
    si ve del que s'ha publicat (hora de Madrid) que de l'historial intern
    (ADR 0128)."""
    return f"{clau}|{H.clau(inici)}"


def fitxa_normal(fitxa):
    """La clau «clau|inici» d'una correcció, amb el començament en UTC."""
    clau, _, inici = (fitxa or "").rpartition("|")
    try:
        return clau_fitxa(clau, inici)
    except ValueError:
        return fitxa


def objectiu(avisos, c):
    """El texto al que se refiere una corrección: una ficha (clau + inici) o un
    aviso enviado (id)."""
    if c.get("fitxa"):
        return next((e for e in avisos.get("historial") or []
                     if clau_fitxa(e["clau"], e["inici"]) == fitxa_normal(c["fitxa"]) and not e.get("fi")), None)
    if c.get("avis"):
        return next((a for a in avisos.get("avisos") or [] if a["id"] == c["avis"]), None)
    return None


def treu(text, linies):
    files = text.split("\n")
    return "\n".join(l for n, l in enumerate(files) if n not in linies)


def valida(avisos, c):
    """Una corrección automática solo quita líneas: ni la primera (el título),
    ni todas las del cuerpo, y con el mismo número de líneas en los dos
    idiomas. Devuelve (ca, es) o None."""
    e = objectiu(avisos, c)
    linies = set(c.get("linies") or [])
    if not e or not linies or c.get("tipus") != "treu_linies":
        return None
    ca, es = e.get("ca") or "", e.get("es") or ""
    n = len(ca.split("\n"))
    if len(es.split("\n")) != n or 0 in linies or any(not 0 < l < n for l in linies) or len(linies) >= n - 1:
        return None
    return treu(ca, linies), treu(es, linies)


def aplica(correccio, ca, es, avisos, moment, motiu):
    """La guarda en correccions.json; avisos_bot.py la aplica en cada pasada
    mientras el texto corregido no cambie por sí solo."""
    cs = llegeix(CORRECCIONS, {"fitxes": {}, "avisos": {}})
    e = objectiu(avisos, correccio)
    entrada = {"original": empremta(e.get("ca")), "ca": ca, "es": es, "abans_ca": e.get("ca"), "abans_es": e.get("es"),
               "hora": H.clau(moment), "motiu": motiu}
    if correccio.get("fitxa"):
        cs["fitxes"][fitxa_normal(correccio["fitxa"])] = entrada
    else:
        cs["avisos"][correccio["avis"]] = entrada
    desa(CORRECCIONS, cs)
    open(PUBLICA_ARA, "w").close()
    return entrada


def desfes(clau):
    cs = llegeix(CORRECCIONS, {"fitxes": {}, "avisos": {}})
    for grup, k in (("fitxes", fitxa_normal(clau)), ("fitxes", clau), ("avisos", clau)):
        cs.get(grup, {}).pop(k, None)
    desa(CORRECCIONS, cs)


def aplica_correccions(sortida, correccions=None, ara_=None):
    """Lo que hace avisos_bot.py al escribir avisos.json: cada corrección, sobre
    su ficha o su aviso si el texto sigue siendo el que se corrigió; si ha
    cambiado por sí solo, la corrección ya no vale y se borra. Los avisos
    corregidos van también a «correccions», para que el bot edite los
    mensajes ya enviados."""
    cs = correccions if correccions is not None else llegeix(CORRECCIONS, None)
    if not cs:
        return sortida
    vius = {"fitxes": {}, "avisos": {}}
    # Les claus d'abans de la 3.201.0 portaven el començament amb desfasament.
    fitxes = {fitxa_normal(k): v for k, v in cs.get("fitxes", {}).items()}
    for e in sortida.get("historial") or []:
        clau = clau_fitxa(e["clau"], e["inici"])
        c = fitxes.get(clau)
        if c and empremta(e.get("ca")) in (c["original"], empremta(c["ca"])):
            if c.get("tanca"):
                e.update(fi=c["hora"], fi_ca=c.get("fi_ca") or "Ja no és vigent.",
                         fi_es=c.get("fi_es") or "Ya no está vigente.", corregit=c["hora"])
            else:
                e.update(ca=c["ca"], es=c["es"], corregit=c["hora"])
            vius["fitxes"][clau] = c
    llista = []
    for a in sortida.get("avisos") or []:
        c = cs.get("avisos", {}).get(a["id"])
        if c and empremta(a.get("ca")) in (c["original"], empremta(c["ca"])):
            a.update(ca=c["ca"], es=c["es"], corregit=c["hora"])
            vius["avisos"][a["id"]] = c
            llista.append({"id": a["id"], "hora": c["hora"], "ca": c["ca"], "es": c["es"]})
    sortida["correccions"] = llista
    if correccions is None and vius != cs:
        desa(CORRECCIONS, vius)
    return sortida


# --- Telegram, a Juanjo --------------------------------------------------------------

def telegram(metode, **params):
    import boira
    return boira.telegram(metode, **params)


def chat_juanjo():
    return llegeix(CONFIG_BOT, {}).get("chat_id")


def envia(text, **params):
    """A Juanjo, con la cabecera de los demás mensajes de IA del bot (la de
    avisar-juanjo): quién escribe, cuándo y de qué. Juanjo, 19-10-2026: «el
    revisor no se identifica al escribirme como hacen el resto de mensajes de IA»."""
    cap = f"🤖 <b>Claude</b> · {ara():%Y-%m-%d %H:%M} · <b>Temps a Montflorit, revisor</b>"
    return telegram("sendMessage", chat_id=chat_juanjo(), text=f"{cap}\n\n{html.escape(text[:3800])}",
                    parse_mode="HTML", **params)


def missatge(p, accio, abans=None, despres=None):
    """El mensaje de un problema: dónde, qué, por qué; y lo hecho o propuesto,
    con el texto de antes y el de después (Juanjo, 18-10-2026: «sí, añádelo»)."""
    t = [p.get("on", ""), "", p.get("que", "")]
    if p.get("per_que"):
        t += ["", p["per_que"]]
    tros = lambda x: netja(x)[:1500]  # noqa: E731
    if accio == "corregit":
        t += ["", "Corregido en la web y en Telegram.", "", "Antes:", tros(abans), "", "Ahora:", tros(despres)]
    elif accio == "proposta":
        t += ["", "Ahora dice:", tros(abans), "", "Propuesta:", tros(despres)]
    elif accio == "codi":
        t += ["", "No se puede corregir desde aquí: hay que arreglarlo en el código (queda apuntado)."]
    return "\n".join(t)[:4000]


def botons(n, accio):
    if accio == "corregit":
        return {"inline_keyboard": [[{"text": "Deshacer", "callback_data": f"rev:{n}:desfes"}]]}
    if accio == "proposta":
        return {"inline_keyboard": [[{"text": "Aplicar", "callback_data": f"rev:{n}:aplica"},
                                     {"text": "Dejar", "callback_data": f"rev:{n}:deixa"}]]}
    return None


# --- La revisión -----------------------------------------------------------------------

def revisa(casa_json, avisos_json, moment=None, prova=False, demana_=None, pagines_=None):
    moment = moment or ara()
    casa = llegeix(casa_json, {})
    avisos = llegeix(avisos_json, {})
    estat = llegeix(ESTAT, {})
    textos = None
    problemes_regles = regles(casa, avisos, moment)
    motiu = "prova" if prova else toca(estat, casa, avisos, moment, problemes_regles)
    if not motiu:
        return None
    textos = (pagines_ or pagines)(casa_json, avisos_json)
    problemes_regles += regles(casa, avisos, moment, textos)[len(problemes_regles):]
    resum = None
    if motiu.startswith("resum") or prova:
        try:
            sys.path.insert(0, os.path.join(ARREL, "bot"))
            import bot as B
            resum = B.resum(llegeix_publiques(casa_json, avisos_json), "ca", moment, avui=moment.hour < 12)
        except Exception as ex:
            resum = f"(no s'ha pogut generar el resum: {ex})"
    informats = [v for v in (estat.get("informats") or []) if H.llegeix(v["hora"]) > moment - dt.timedelta(days=2)]
    resposta, cost = (demana_ or demana)(context(casa, avisos, textos, moment, motiu, problemes_regles, resum,
                                                 [{k: v[k] for k in ("on", "que")} for v in informats]))
    problemes = resposta.get("problemes") or []
    # Las reglas fijas que la IA no haya recogido van igualmente.
    for p in problemes_regles:
        if not any(p["que"][:40] in (q.get("que") or "") for q in problemes):
            problemes.append({"on": p["on"], "que": p["que"], "gravetat": "mitjana", "regla": p["regla"]})
    fets = []
    if not prova:
        preguntes = estat.setdefault("preguntes", {})
        resum_juanjo = []
        for p in problemes:
            c = p.get("correccio")
            accio, abans, despres = "codi", None, None
            if c and c.get("tipus") == "treu_linies" and (nous := valida(avisos, c)):
                entrada = aplica(c, *nous, avisos, moment, motiu)
                accio, abans, despres = "corregit", entrada["abans_ca"], entrada["ca"]
            elif c and (e := objectiu(avisos, c)) and (c.get("ca") or c.get("tipus") == "tanca_fitxa"):
                c = {**c, "original_empremta": empremta(e.get("ca")), "abans_ca": e.get("ca")}
                accio, abans = "proposta", e.get("ca")
                despres = (f"Se cierra la ficha: {c.get('fi_es') or c.get('fi_ca') or ''}"
                           if c.get("tipus") == "tanca_fitxa" else c.get("ca"))
            fets.append({"accio": accio, **p})
            # Lo que se corrige o se propone, un mensaje con su botón; lo
            # demás, grave o medio, en un solo mensaje; lo leve, al registro.
            if accio in ("corregit", "proposta"):
                n = str(max([int(k) for k in preguntes] + [0]) + 1)
                try:
                    r, _ = envia(missatge(p, accio, abans, despres), reply_markup=botons(n, accio))
                    preguntes[n] = {"missatge": r["message_id"], "accio": accio, "correccio": c,
                                    "t": H.clau(moment)}
                except Exception as ex:
                    fets.append({"error_telegram": str(ex)})
            elif p.get("gravetat") in ("alta", "mitjana"):
                resum_juanjo.append(p)
        lleus = sum(1 for x in fets if x.get("accio") == "codi" and x.get("gravetat") not in ("alta", "mitjana"))
        if resum_juanjo:
            text = [f"Revisión ({motiu}): {len(resum_juanjo)} incoherencia(s) que hay que arreglar en el código."]
            for p in resum_juanjo:
                text += ["", f"{'Grave' if p.get('gravetat') == 'alta' else 'Media'}. {p.get('on', '')}: "
                             f"{p.get('que', '')}"]
            if lleus:
                text += ["", f"Y {lleus} leve(s), en el registro."]
            try:
                envia("\n".join(text))
            except Exception as ex:
                fets.append({"error_telegram": str(ex)})
        estat["informats"] = (estat.get("informats") or []) + [
            {"on": p.get("on"), "que": p.get("que"), "hora": H.clau(moment)} for p in problemes]
        # Lo que se recuerda: dos días.
        limit = moment - dt.timedelta(days=2)
        estat["informats"] = [v for v in estat["informats"] if H.llegeix(v["hora"]) > limit]
        estat["preguntes"] = {k: v for k, v in preguntes.items() if H.llegeix(v["t"]) > limit}
        estat["regles_vistes"] = {empremta(p): H.clau(moment) for p in problemes_regles}
        estat["conclusions"] = empremta(conclusions(casa, avisos))
        estat["darrera"] = H.clau(moment)
        if hores := [a["hora"] for a in avisos.get("avisos") or [] if a.get("hora")]:
            estat["darrer_missatge"] = H.clau(max(hores, key=H.utc))
        if motiu.startswith("resum"):
            estat["diaris"] = (estat.get("diaris") or [])[-10:] + [f"{moment.date().isoformat()} {motiu[6:]}"]
        desa(ESTAT, estat)
        os.makedirs(os.path.dirname(REGISTRE), exist_ok=True)
        with open(REGISTRE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"hora": H.clau(moment), "motiu": motiu, **cost,
                                "problemes": problemes, "fets": [x.get("accio") for x in fets]},
                               ensure_ascii=False) + "\n")
    return {"motiu": motiu, "problemes": problemes, "cost": cost, "textos": textos}


def llegeix_publiques(casa_json, avisos_json):
    """Los datos como los lee el bot (montflorit.json), para su resumen."""
    with tempfile.TemporaryDirectory() as tmp:
        sortida = os.path.join(tmp, "montflorit.json")
        subprocess.run([sys.executable, os.path.join(ARREL, "montflorit.py"), "dades", casa_json, sortida, avisos_json],
                       check=True, capture_output=True)
        return llegeix(sortida, {})


def respostes(moment=None):
    """Los botones de Juanjo: Aplicar, Dejar, Deshacer. Como boira.py, sin
    marcar las respuestas como leídas (getUpdates sin offset)."""
    estat = llegeix(ESTAT, {})
    preguntes = estat.get("preguntes") or {}
    pendents = {n: p for n, p in preguntes.items() if not p.get("resposta")}
    if not pendents:
        return 0
    updates, cfg = telegram("getUpdates", allowed_updates=["callback_query"])
    fetes = 0
    for u in updates or []:
        q = u.get("callback_query") or {}
        dada = q.get("data") or ""
        if not dada.startswith("rev:") or str((q.get("from") or {}).get("id")) != str(cfg["chat_id"]):
            continue
        _, n, accio = dada.split(":", 2)
        p = pendents.get(n)
        if not p or p.get("resposta"):
            continue
        c = p.get("correccio") or {}
        clau = fitxa_normal(c["fitxa"]) if c.get("fitxa") else c.get("avis")
        text = {"aplica": "Aplicado", "deixa": "Dejado como estaba", "desfes": "Deshecho"}.get(accio, accio)
        if accio == "aplica" and clau:
            cs = llegeix(CORRECCIONS, {"fitxes": {}, "avisos": {}})
            grup = "fitxes" if c.get("fitxa") else "avisos"
            cs.setdefault(grup, {})[clau] = {
                "original": c.get("original_empremta"), "ca": c.get("ca") or c.get("abans_ca"),
                "es": c.get("es") or c.get("ca") or c.get("abans_ca"), "tanca": c.get("tipus") == "tanca_fitxa",
                "fi_ca": c.get("fi_ca"), "fi_es": c.get("fi_es"),
                "hora": H.clau(moment or ara()), "motiu": "aprovat per Juanjo"}
            desa(CORRECCIONS, cs)
        elif accio == "desfes" and clau:
            desfes(clau)
        p["resposta"] = accio
        fetes += 1
        try:
            telegram("editMessageReplyMarkup", chat_id=cfg["chat_id"], message_id=p["missatge"],
                     reply_markup={"inline_keyboard": [[{"text": text, "callback_data": "rev:fet"}]]})
            telegram("answerCallbackQuery", callback_query_id=q["id"], text=text)
        except Exception:
            pass
    if fetes:
        desa(ESTAT, estat)
        open(PUBLICA_ARA, "w").close()
    return fetes


def mostra_estat():
    try:
        with open(REGISTRE, encoding="utf-8") as f:
            files = [json.loads(l) for l in f if l.strip()][-20:]
    except OSError:
        files = []
    for r in files:
        print(f"{r['hora']}  {r['motiu']:<14} {len(r.get('problemes') or [])} problema(es)  "
              f"{r.get('segons')} s  {r.get('cost_usd')} $")


if __name__ == "__main__":
    ordre = sys.argv[1] if len(sys.argv) > 1 else ""
    if ordre in ("revisa", "prova") and len(sys.argv) == 4:
        with open(os.path.join(DIR, "revisor.lock"), "w") as cadenat:
            try:
                fcntl.flock(cadenat, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                sys.exit(0)        # la anterior aún no ha acabado
            r = revisa(sys.argv[2], sys.argv[3], prova=ordre == "prova")
        if r and ordre == "prova":
            print(json.dumps({k: r[k] for k in ("motiu", "problemes", "cost")}, ensure_ascii=False, indent=1))
        elif r:
            print(f"{r['motiu']}: {len(r['problemes'])} problema(es)")
    elif ordre == "respostes":
        respostes()
    elif ordre == "estat":
        mostra_estat()
    else:
        sys.exit(__doc__)
