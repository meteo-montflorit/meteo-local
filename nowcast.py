#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La lluvia del radar llevada hacia delante, hasta 2 horas (ADR 0019).

En las primeras horas, la lluvia que ya existe y cómo se mueve dicen más que
los modelos: el 05-10-2026 los modelos daban 0,3 mm por hora mientras caían
más de 20. Aquí:

1. **La imagen**: la última del radar de Meteocat (composición de la XRAD
   corregida, cada 6 minutos; el radar de Vallirana está a unos 20 km de
   casa). Si la de RainViewer (composición de AEMET, cada 10 minutos) es
   bastante más nueva, la de RainViewer: Meteocat publica cada imagen unos
   15 minutos tarde. Cuánto más nueva lo decide la comparación diaria de las
   dos (MARGES y radar_fonts.py, ADR 0026). Los
   colores se pasan a dBZ con la leyenda de cada uno y a mm/h con la
   relación de Marshall-Palmer, Z = 200 R^1,6.
2. **El movimiento**: el de la advección de Meteocat, que lo calcula con las
   tres últimas imágenes y extrapola una hora; aquí se mide lo que desplaza
   su primera imagen prevista hasta la última, en la lluvia que hay a 60 km
   o menos de casa (ADR 0023): la que puede llegar es esa, y la de más
   lejos puede moverse de otra manera. Si cerca hay poca lluvia, en un cuadro
   de unos 300 km. Si no hay advección, el de RainViewer (pares de imágenes
   separados 30 minutos), solo si los pares coinciden.
3. **Hacia delante**: para cada lugar y cada 5 minutos, la lluvia de ahora en
   el punto de donde vendrá y en un círculo alrededor que crece con el tiempo
   (3 km más 0,08 km por minuto): cada píxel del círculo es un caso posible.
   De ahí salen la lluvia esperada (la media) y la probabilidad (la fracción
   de casos con lluvia).

La lluvia que nace o muere en ese tiempo no se ve: por eso solo 2 horas.

Uso: python3 nowcast.py    resumen para casa y la cuenca de la riera
"""
import csv
import datetime as dt
import io
import json
import math
import os

import config as C
import hora as H

Z = 7
MIDA = 768                  # mosaico de 3x3 teselas de 256 píxeles
FINESTRA = 320              # cuadro para el movimiento (unos 300 km)
RADI_MOV_KM = 60            # el movimiento se mide primero en la lluvia de cerca
COINCIDENCIA_MIN = 0.3      # coincidencia mínima para fiarse del movimiento de cerca
PAS_MIN = 5
HORITZO_MIN = 120
RADI_KM = (3.0, 0.08)       # radio del círculo: 3 km + 0,08 km por minuto
PLOU_MMH = 0.5              # unos 18 dBZ: lluvia que llega al suelo
FEBLE_MMH = 0.08            # unos 6 dBZ: por debajo, ruido; hasta PLOU_MMH, eco débil (plugim)
VEL_MAX_KMH = 120           # más rápido es un error del cálculo
DESACORD_KMH = 20           # pares de RainViewer que difieren más: sin movimiento
# Cuántos minutos más nueva ha de ser la imagen de RainViewer para usarla en
# lugar de la de Meteocat, según qué fuente acierta más (ADR 0026). Las horas
# de las dos son pares: 16 equivale a «más de 15», la regla de antes.
# Con RainViewer como preferida, su imagen siempre que no sea más vieja que la
# de Meteocat (hasta el 17-10-2026, solo si era 10 minutos más nueva: con
# imágenes cada 10 y cada 6 minutos, la web saltaba de un radar a otro en
# cada pasada y enseñaba la de Meteocat con 15 minutos; ADR 0026).
MARGES = {"rainviewer": 0, "meteocat": 16}
FONT_PER_DEFECTE = "rainviewer"
FONT_PREFERIDA = os.path.join(os.environ.get("APRENENTATGE_DIR", "/estat/aprenentatge"), "radar-font.json")
ADVECCIO_MAX_MIN = 60       # advección más vieja: no se usa su movimiento
METEOCAT = "https://static-m.meteo.cat/tiles"
# Leyenda del radar de Meteocat (script de meteo.cat): cada color, una franja
# de 3 dBZ que empieza en el valor indicado; se toma su centro.
LLEGENDA_METEOCAT = [(9, "8000ff"), (12, "4000ff"), (15, "0000ff"), (18, "00ffff"),
                     (21, "00ff80"), (24, "00ff00"), (27, "3fff00"), (30, "7fff00"),
                     (33, "bfff00"), (36, "ffff00"), (39, "ffab00"), (42, "ff8100"),
                     (45, "ff5700"), (48, "ff2d00"), (51, "ff0000"), (54, "ff003f"),
                     (57, "ff007f"), (60, "ff00bf"), (63, "ff00ff"), (66, "f0f0f0")]
COLORS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibracio",
                      "rainviewer_colors.csv")


def taula_dbz():
    """Color RGBA (esquema 2, Universal Blue) → dBZ, solo la lluvia."""
    res = {}
    with open(COLORS, encoding="utf-8") as f:
        files = list(csv.reader(f))[1:]
    vistos = set()
    for fila in files:
        dbz = int(fila[0])
        if dbz in vistos:           # la segunda tanda de la tabla es la nieve
            break
        vistos.add(dbz)
        res.setdefault(fila[3].lower(), dbz)
    return res


def mm_h(dbz):
    """Marshall-Palmer: Z = 200 R^1,6."""
    import numpy as np
    return np.where(dbz > 0, (10 ** (dbz / 10) / 200) ** (1 / 1.6), 0.0)


def geometria(lat, lon):
    n = 2 ** Z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)


def pixel(lat, lon, tx, ty):
    """Fila y columna del lugar en el mosaico centrado en la tesela (tx, ty)."""
    n = 2 ** Z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return (y - ty + 1) * 256, (x - tx + 1) * 256


def km_px(lat):
    return 360 / 2 ** Z / 256 * 111.32 * math.cos(math.radians(lat))


def a_mm_h(rgba, claus, valors):
    """Píxeles RGBA → mm/h con una leyenda (claus: RGBA en entero, ordenadas)."""
    import numpy as np
    codi = (rgba[..., 0] << 24) | (rgba[..., 1] << 16) | (rgba[..., 2] << 8) | rgba[..., 3]
    i = np.clip(np.searchsorted(claus, codi), 0, len(claus) - 1)
    dbz = np.where((claus[i] == codi) & (rgba[..., 3] > 0), valors[i], -32.0)
    return mm_h(dbz)


def llegenda(parelles):
    import numpy as np
    parelles = list(parelles)
    claus = np.array([k for k, _ in parelles], dtype=np.uint64)
    valors = np.array([v for _, v in parelles], dtype=float)
    o = np.argsort(claus)
    return claus[o], valors[o]


CACHE = os.environ.get("RADAR_CACHE", "/estat/radar-cache")
CACHE_HORES = 3


def tesela(get, url):
    """Una tesela, de la caché si ya se bajó: cada imagen de los dos radares
    tiene su propia dirección y no cambia, así que solo se bajan las nuevas.
    Sin carpeta de caché (fuera del NAS), siempre de la red."""
    import hashlib
    if not os.path.isdir(os.path.dirname(CACHE)):
        return get(url, True)
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".png")
    try:
        with open(ruta, "rb") as f:
            return f.read()
    except OSError:
        dades = get(url, True)
        with open(ruta + ".tmp", "wb") as f:
            f.write(dades)
        os.replace(ruta + ".tmp", ruta)
        return dades


def neteja_cache():
    """Borra las teselas de más de CACHE_HORES horas."""
    import time
    if not os.path.isdir(CACHE):
        return
    limit = time.time() - CACHE_HORES * 3600
    for nom in os.listdir(CACHE):
        ruta = os.path.join(CACHE, nom)
        try:
            if os.path.getmtime(ruta) < limit:
                os.remove(ruta)
        except OSError:
            pass


def mosaic(get, url, tx, ty, claus, valors):
    """3x3 teselas alrededor de (tx, ty); url(x, y) da la dirección."""
    import numpy as np
    from PIL import Image
    rgba = np.zeros((MIDA, MIDA, 4), dtype=np.uint64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            im = Image.open(io.BytesIO(tesela(get, url(tx + dx, ty + dy)))).convert("RGBA")
            rgba[(dy + 1) * 256:(dy + 2) * 256, (dx + 1) * 256:(dx + 2) * 256] = np.array(im, dtype=np.uint64)
    return a_mm_h(rgba, claus, valors)


def rainviewer(get, tx, ty, fotogrames=7):
    """Los últimos fotogramas de RainViewer (por defecto, la última hora)."""
    meta = json.loads(get("https://api.rainviewer.com/public/weather-maps.json"))
    claus, valors = llegenda((int(k[1:], 16), v) for k, v in taula_dbz().items())
    past = meta["radar"]["past"][-fotogrames:]
    return {"hores": [dt.datetime.fromtimestamp(f["time"], H.UTC) for f in past],
            "mm_h": [mosaic(get, lambda x, y, f=f: f"{meta['host']}{f['path']}/256/{Z}/{x}/{y}/2/0_0.png",
                            tx, ty, claus, valors) for f in past]}


PAUSA_MIN = 60     # si Meteocat rechaza las peticiones, se deja de pedir


def fitxer_pausa():
    return os.path.join(os.path.dirname(CACHE), "meteocat-pausa")


def en_pausa(ara=None):
    """Hora hasta la que Meteocat está en pausa, o None."""
    try:
        with open(fitxer_pausa(), encoding="utf-8") as f:
            fins = H.llegeix(f.read().strip())
    except (OSError, ValueError):
        return None
    return fins if fins > (ara or H.ara()) else None


def posa_pausa(ara=None):
    """Una hora sin pedir nada a Meteocat (solo en el NAS, con /estat)."""
    if not os.path.isdir(os.path.dirname(CACHE)):
        return None
    fins = (ara or H.ara()) + dt.timedelta(minutes=PAUSA_MIN)
    with open(fitxer_pausa(), "w", encoding="utf-8") as f:
        f.write(fins.isoformat(timespec="minutes"))
    return fins


def es_rebuig(ex):
    """Un rechazo (403 o 429), no una caída: se respeta con una pausa."""
    import urllib.error
    return isinstance(ex, urllib.error.HTTPError) and ex.code in (403, 429)


def meteocat(get, tx, ty, get_pagina=None):
    """La última imagen del radar de Meteocat y las dos de su advección (la
    primera y la última prevista), con sus horas. Las teselas siguen el
    esquema TMS (la y, contada desde el sur). La página, con get_pagina si se
    da (para reutilizarla entre las lecturas de una misma pasada)."""
    import re
    pagina = (get_pagina or get)("https://www.meteo.cat/observacions/radar")
    if isinstance(pagina, bytes):
        pagina = pagina.decode("utf-8", "ignore")
    radar = re.search(r"dataDarreraRadar:\s*'(\d\d)/(\d\d)/(\d{4}) (\d\d):(\d\d)Z'", pagina)
    adv = re.search(r"dataDarreraAdveccio:\s*'([^']+)'", pagina)
    claus, valors = llegenda((int(c + "ff", 16), d + 1.5) for d, c in LLEGENDA_METEOCAT)
    tms = lambda y: 2 ** Z - 1 - y
    res = {}
    if radar:
        mes, dia, any_, h, m = radar.groups()
        t = dt.datetime(int(any_), int(mes), int(dia), int(h), int(m), tzinfo=dt.timezone.utc)
        res["hora"] = t
        res["mm_h"] = mosaic(get, lambda x, y: f"{METEOCAT}/radar/{t:%Y/%m/%d/%H/%M}/{Z:02d}/000/000/{x:03d}/000/000/{tms(y):03d}.png",
                             tx, ty, claus, valors)
    if adv:
        b = H.llegeix(adv.group(1)).astimezone(dt.timezone.utc)
        prev = []
        for minuts in (6, 60):
            t = b + dt.timedelta(minutes=minuts)
            url = (lambda x, y, t=t: f"{METEOCAT}/adveccio/{b:%Y/%m/%d}/{t:%Y/%m/%d}/{b:%H/%M}/{t:%H/%M}/"
                   f"{Z:02d}/000/000/{x:03d}/000/000/{tms(y):03d}.png")
            prev.append((t, mosaic(get, url, tx, ty, claus, valors)))
        res["adveccio"] = {"base": b, "previsions": prev}
    return res


def carrega(get, get_pagina=None):
    """Todo lo que hace falta: las imágenes de los dos radares, si están. Si
    Meteocat falla, la misma pasada sigue con RainViewer; si lo que hace es
    rechazar las peticiones, se deja en pausa una hora. El mosaico se centra
    en casa."""
    lat, lon = C.CASA
    tx, ty = geometria(lat, lon)
    r = {"tx": tx, "ty": ty, "km_px": km_px(lat), "errors": []}
    neteja_cache()
    try:
        r["rainviewer"] = rainviewer(get, tx, ty)
    except Exception as ex:
        r["errors"].append(f"RainViewer: {ex}")
    pausa = en_pausa()
    if pausa:
        r["errors"].append(f"Meteocat: en pausa fins a les {H.local(pausa):%H:%M}")
    else:
        try:
            r["meteocat"] = meteocat(get, tx, ty, get_pagina)
        except Exception as ex:
            r["errors"].append(f"Meteocat: {ex}")
            if es_rebuig(ex):
                fins = posa_pausa()
                if fins:
                    r["errors"].append(f"Meteocat: en pausa fins a les {H.local(fins):%H:%M}")
    return r


def desplacament(a, b):
    """Desplazamiento (filas, columnas) de a a b con la correlación de fase,
    en el cuadro central. None si casi no hay lluvia."""
    import numpy as np
    m = (MIDA - FINESTRA) // 2
    fa = np.log1p(a[m:m + FINESTRA, m:m + FINESTRA])
    fb = np.log1p(b[m:m + FINESTRA, m:m + FINESTRA])
    if (fa > np.log1p(PLOU_MMH)).sum() < 50 or (fb > np.log1p(PLOU_MMH)).sum() < 50:
        return None
    finestra = np.outer(np.hanning(FINESTRA), np.hanning(FINESTRA))
    A = np.fft.fft2((fa - fa.mean()) * finestra)
    B = np.fft.fft2((fb - fb.mean()) * finestra)
    r = B * np.conj(A)
    r /= np.abs(r) + 1e-9
    c = np.fft.ifft2(r).real
    i, j = np.unravel_index(np.argmax(c), c.shape)
    di = i if i < FINESTRA // 2 else i - FINESTRA
    dj = j if j < FINESTRA // 2 else j - FINESTRA
    # Ajuste subpíxel con una parábola en cada eje.
    def fi(v0, v1, v2):
        d = v0 - 2 * v1 + v2
        return 0.0 if d == 0 else 0.5 * (v0 - v2) / d
    di += fi(c[(i - 1) % FINESTRA, j], c[i, j], c[(i + 1) % FINESTRA, j])
    dj += fi(c[i, (j - 1) % FINESTRA], c[i, j], c[i, (j + 1) % FINESTRA])
    return float(di), float(dj)


def desplacament_local(a, b, r, minuts):
    """Desplazamiento (filas, columnas) de a a b de la lluvia que hay a
    RADI_MOV_KM o menos de casa: la traslación con la que más coinciden
    las dos manchas de lluvia (lo que comparten entre lo que ocupan las dos).
    None si cerca hay poca lluvia en alguna de las dos imágenes, si no
    coinciden lo bastante, si la lluvia va tan deprisa que se sale de la
    búsqueda o si no se sabe dónde está casa."""
    import numpy as np
    if "tx" not in r:
        return None
    fila, col = pixel(C.CASA[0], C.CASA[1], r["tx"], r["ty"])
    f, c = int(round(fila)), int(round(col))
    radi = int(RADI_MOV_KM / r["km_px"]) + 1
    # Solo saltos de hasta RADI_MOV_KM: más lejos ya se compararía con otra
    # lluvia, y una tormenta lejana puede parecerse más que la de cerca.
    salt = min(int(VEL_MAX_KMH / 60 * minuts / r["km_px"]), radi,
               f - radi, c - radi, MIDA - f - radi, MIDA - c - radi)
    if salt < 1:
        return None
    yy, xx = np.mgrid[-radi:radi, -radi:radi]
    zona = yy ** 2 + xx ** 2 < radi ** 2
    pa = a >= PLOU_MMH
    pb = (b >= PLOU_MMH)[f - radi:f + radi, c - radi:c + radi][zona]
    if pb.sum() < 50 or pa[f - radi:f + radi, c - radi:c + radi][zona].sum() < 50:
        return None
    millor = (-1.0, 0, 0)
    # Primero de 3 en 3 píxeles; luego, píxel a píxel alrededor del mejor.
    for pas, marge in ((3, salt), (1, 3)):
        _, f0, c0 = millor
        for df in range(max(-salt, f0 - marge), min(salt, f0 + marge) + 1, pas):
            for dc in range(max(-salt, c0 - marge), min(salt, c0 + marge) + 1, pas):
                if df * df + dc * dc > salt * salt:
                    continue
                p = pa[f - radi - df:f + radi - df, c - radi - dc:c + radi - dc][zona]
                coincidencia = (p & pb).sum() / max(1, (p | pb).sum())
                if coincidencia > millor[0]:
                    millor = (coincidencia, df, dc)
    # En el borde de la búsqueda no es un máximo: es que no lo ha encontrado.
    if millor[0] < COINCIDENCIA_MIN or math.hypot(millor[1], millor[2]) >= salt - 1:
        return None
    return float(millor[1]), float(millor[2])


def moviment(r, ara=None):
    """Velocidad (filas y columnas por minuto) y de dónde sale: la advección
    de Meteocat si es reciente (medida en la lluvia de cerca de casa y,
    si hay poca, en todo el cuadro); si no, RainViewer si sus pares
    coinciden. None si no hay forma fiable de saberlo."""
    import numpy as np
    ara = ara or H.ara()
    adv = (r.get("meteocat") or {}).get("adveccio")
    if adv and ara - adv["base"] <= dt.timedelta(minutes=ADVECCIO_MAX_MIN):
        (t0, a), (t1, b) = adv["previsions"]
        minuts = (t1 - t0).total_seconds() / 60
        d = desplacament_local(a, b, r, minuts) or desplacament(a, b)
        if d is not None:
            v = (d[0] / minuts, d[1] / minuts)
            if math.hypot(*v) * r["km_px"] * 60 <= VEL_MAX_KMH:
                return v, "meteocat"
    rv = r.get("rainviewer")
    if not rv:
        return None
    vs = []
    for k in range(3, len(rv["mm_h"])):
        d = desplacament(rv["mm_h"][k - 3], rv["mm_h"][k])
        if d is not None:
            minuts = (rv["hores"][k] - rv["hores"][k - 3]).total_seconds() / 60
            vs.append((d[0] / minuts, d[1] / minuts))
    if len(vs) < 2:
        return None
    vs = np.array(vs)
    v = np.median(vs, axis=0)
    dispersio = np.max(np.hypot(*(vs - v).T)) * r["km_px"] * 60
    if dispersio > DESACORD_KMH or math.hypot(*v) * r["km_px"] * 60 > VEL_MAX_KMH:
        return None
    return (float(v[0]), float(v[1])), "rainviewer"


def font_preferida():
    """La fuente que ha acertado más según la comparación diaria (ADR 0026);
    sin comparación, FONT_PER_DEFECTE."""
    try:
        with open(FONT_PREFERIDA, encoding="utf-8") as f:
            font = json.load(f).get("preferida")
    except (OSError, ValueError):
        font = None
    return font if font in MARGES else FONT_PER_DEFECTE


def imatge(r, preferida=None):
    """La imagen de la que se parte: la de Meteocat, salvo que la de
    RainViewer sea MARGES[preferida] minutos más nueva o más (con 0, la de
    RainViewer siempre que no sea más vieja). Devuelve
    (hora, mm/h, origen)."""
    mc, rv = r.get("meteocat") or {}, r.get("rainviewer")
    t_rv = rv["hores"][-1] if rv else None
    marge = dt.timedelta(minutes=MARGES[preferida or font_preferida()])
    if "mm_h" in mc and (t_rv is None or t_rv - mc["hora"] < marge):
        return mc["hora"], mc["mm_h"], "meteocat"
    if rv:
        return t_rv, rv["mm_h"][-1], "rainviewer"
    return None


def serie(r, ara, v, lat, lon):
    """Cada PAS_MIN minutos, de ahora a HORITZO_MIN: la lluvia esperada (mm/h,
    la media del círculo) y la probabilidad de lluvia (fracción del círculo
    con PLOU_MMH o más), para el lugar."""
    import numpy as np
    fila, col = pixel(lat, lon, r["tx"], r["ty"])
    yy, xx = np.mgrid[:MIDA, :MIDA]
    res = []
    for t in range(0, HORITZO_MIN + 1, PAS_MIN):
        f0, c0 = fila - v[0] * t, col - v[1] * t
        radi = (RADI_KM[0] + RADI_KM[1] * t) / r["km_px"]
        dins = (yy - f0) ** 2 + (xx - c0) ** 2 <= radi ** 2
        if not dins.any():
            break
        valors = ara[dins]
        res.append({"min": t, "mm_h": round(float(valors.mean()), 2),
                    "prob": round(float((valors >= PLOU_MMH).mean()), 2)})
    return res


def resum(r, ahora=None):
    """Lo que se guarda en los datos: de dónde salen la imagen y el
    movimiento y la serie de casa y de la cuenca de la riera de Sant Cugat
    (ADR 0027). None si no hay ninguna imagen."""
    im = imatge(r)
    if im is None:
        return None
    hora, camp, origen = im
    mov = moviment(r, ahora)
    res = {"hora": H.clau(hora), "imatge": origen,
           "moviment": mov and mov[1], "velocitat_kmh": None, "cap_a": None, "graus": None,
           "llocs": {}}
    v = mov[0] if mov else (0.0, 0.0)   # sin movimiento: la lluvia de ahora, quieta
    if mov:
        res["velocitat_kmh"] = round(math.hypot(*v) * r["km_px"] * 60)
        res["cap_a"] = rumb(v)
        res["graus"] = round(graus(v))      # para la flecha del mapa
        res["v"] = [round(v[0], 4), round(v[1], 4)]   # filas y columnas por minuto (moviment_registre)
    for nom, (lat, lon) in (("casa", C.CASA), ("conca", C.CONCA_RIERA)):
        res["llocs"][nom] = serie(r, camp, v, lat, lon)
    res["fonts"] = fonts(r, v)
    return res


def fonts(r, v):
    """Lo que daría en casa cada fuente con su última imagen y el mismo
    movimiento, para compararlas (radar_fonts.py, ADR 0026): la hora de la
    imagen y la probabilidad de cada PAS_MIN minutos desde ella."""
    res = {}
    mc, rv = r.get("meteocat") or {}, r.get("rainviewer")
    for nom, hora, camp in (("meteocat", mc.get("hora"), mc.get("mm_h")),
                            ("rainviewer", rv and rv["hores"][-1], rv and rv["mm_h"][-1])):
        if camp is not None:
            res[nom] = {"hora": H.clau(hora),
                        "prob": [p["prob"] for p in serie(r, camp, v, *C.CASA)]}
    return res


# Con la preposición, como se dice: «cap al nord», «cap a l'est».
RUMBS = ["al nord", "al nord-est", "a l'est", "al sud-est", "al sud", "al sud-oest", "a l'oest", "al nord-oest"]


def graus(v):
    """Hacia dónde va, en grados (0 = norte, 90 = este; las filas crecen
    hacia el sur)."""
    return math.degrees(math.atan2(v[1], -v[0])) % 360


def rumb(v):
    """Hacia dónde va, con ocho rumbos."""
    return RUMBS[int((graus(v) + 22.5) // 45) % 8]


# --- El mapa i la pluja més propera del requadre del radar (Juanjo,
# 17-10-2026: «distancia de la lluvia, un mapa donde se vea montflorit y la
# lluvia… que no sea un simple aviso de lluvia cerca»). De la mateixa imatge
# que el «quan arriba», perquè diguin el mateix. ---
MAPA_KM = 30                # el mapa, de 30 km al voltant de casa
PROPERA_MAX_KM = 60         # més lluny, no es diu
FORTA_KM = 15               # la pluja forta o més, fins aquí (forta())
FORTA_CLASSE = 3            # forta
CREIX_KM = 15               # creixement(): la pluja d'aquí al voltant
CREIX_MIN = 30              # comparada amb la de fa 30 minuts, del mateix radar
CREIX_MARGE_MIN = 5
CREIX_GUANY_KM2 = 50        # perquè es digui: 50 km² més que fa 30 minuts
# (unes 7 parts de cada 100 del cercle); el doble de 10 km² no és res i el
# doble de 216 és molt (Juanjo, 17-10-2026: «no es lo mismo el doble de 10km²
# que de 216»; fins a la 3.131.0, el doble i 20 km²).
# Les franges d'intensitat de l'AEMET (mm/h): feble, moderada, forta, molt
# forta i torrencial; per sota de PLOU_MMH, sense pluja.
FRANGES_MMH = (2, 15, 30, 60)
INTENSITATS = {"ca": ("feble", "moderada", "forta", "molt forta", "torrencial"),
               "es": ("débil", "moderada", "fuerte", "muy fuerte", "torrencial")}


def nom_intensitat(mm_h, idioma="ca"):
    """La paraula de les franges de l'AEMET per a una intensitat en mm/h: la
    mateixa per al requadre del radar i per a l'avís de pluja (abans l'avís
    deia «forta» des de 4 mm/h i el radar, des de 15; inventari del 18-10-2026)."""
    return INTENSITATS[idioma][sum(mm_h >= l for l in FRANGES_MMH)]


def classe(mm):
    """0 sense pluja; 1 feble … 5 torrencial."""
    import numpy as np
    return np.digitize(mm, [PLOU_MMH, *FRANGES_MMH])


def mapa(camp, fila, col, km_px, radi_km=MAPA_KM):
    """El tros de la imatge al voltant de casa, en classes d'intensitat, una
    xifra per píxel (fila a fila, de nord a sud): uns 4 KB. I, a «febles», els
    ecos per sota de la pluja que compta (de FEBLE_MMH a PLOU_MMH), un 1 per
    píxel, perquè la web pinti el plugim quan en parla (Juanjo, 18-10-2026:
    «si habla de llovizna el miniradar tiene que mostrarla»). None si no hi
    ha res."""
    n = int(math.ceil(radi_km / km_px))
    f0, c0 = int(round(fila)), int(round(col))
    tall = camp[f0 - n:f0 + n + 1, c0 - n:c0 + n + 1]
    tros = classe(tall)
    febles = (tall >= FEBLE_MMH) & (tall < PLOU_MMH)
    if not tros.any() and not febles.any():
        return None
    res = {"km_px": round(km_px, 4), "n": 2 * n + 1, "fila": round(fila - (f0 - n), 2),
           "col": round(col - (c0 - n), 2), "classes": "".join(str(int(x)) for x in tros.ravel())}
    if febles.any():
        res["febles"] = "".join("1" if x else "0" for x in febles.ravel())
    return res


def propera(camp, fila, col, km_px, max_km=PROPERA_MAX_KM):
    """La pluja més propera a casa: a quants km, cap a on i quina intensitat
    hi té el radar. None si no n'hi ha a max_km o menys."""
    import numpy as np
    yy, xx = np.ogrid[:camp.shape[0], :camp.shape[1]]
    dist = np.hypot((yy - fila) * km_px, (xx - col) * km_px)
    pluja = camp >= PLOU_MMH
    if not pluja.any():
        return None
    d = np.where(pluja, dist, np.inf)
    f, c = np.unravel_index(np.argmin(d), d.shape)
    if d[f, c] > max_km:
        return None
    angle = math.degrees(math.atan2(c - col, -(f - fila))) % 360
    return {"km": round(float(d[f, c]), 1), "rumb": RUMBS[int((angle + 22.5) // 45) % 8],
            "mm_h": round(float(camp[f, c]), 1), "classe": int(classe(camp[f, c]))}


def forta(camp, fila, col, km_px, max_km=FORTA_KM):
    """La pluja més intensa, si és forta o més, a max_km o menys de casa: a
    quants km i cap a on hi ha el punt més proper amb aquesta intensitat.
    None si no n'hi ha. Perquè el requadre no digui només «la més propera,
    feble» amb una tempesta a 10 km (Juanjo, 17-10-2026: «esta tronando… y
    el radar decía que no había nada»)."""
    import numpy as np
    yy, xx = np.ogrid[:camp.shape[0], :camp.shape[1]]
    dist = np.hypot((yy - fila) * km_px, (xx - col) * km_px)
    cl = np.where(dist <= max_km, classe(camp), 0)
    maxim = int(cl.max())
    if maxim < FORTA_CLASSE:
        return None
    d = np.where(cl == maxim, dist, np.inf)
    f, c = np.unravel_index(np.argmin(d), d.shape)
    angle = math.degrees(math.atan2(c - col, -(f - fila))) % 360
    return {"km": round(float(d[f, c]), 1), "rumb": RUMBS[int((angle + 22.5) // 45) % 8], "classe": maxim}


def creixement(r, fila, col, km_px):
    """Si la pluja creix al voltant de casa: els km² amb pluja (PLOU_MMH o
    més) a CREIX_KM o menys a la darrera imatge de RainViewer i a la de fa
    CREIX_MIN minuts, que porta la mateixa lectura, i la distància de la pluja
    moderada o més a totes dues. El moviment només desplaça la imatge; el
    17-10-2026 la tempesta no s'acostava sinó que es formava cada cop més a
    prop (Juanjo: «no se trata solo de la direccion de la lluvia sino de hacia
    donde crece»). «creix» diu si el requadre ho ha de dir; si ajuda a
    preveure la pluja a casa, ho dirà el registre (moviment_registre.py).
    None sense les dues imatges."""
    import numpy as np
    rv = r.get("rainviewer")
    if not rv or len(rv["mm_h"]) < 2:
        return None
    t1 = rv["hores"][-1]
    j = min(range(len(rv["hores"]) - 1), key=lambda i: abs((t1 - rv["hores"][i]).total_seconds() / 60 - CREIX_MIN))
    minuts = round((t1 - rv["hores"][j]).total_seconds() / 60)
    if abs(minuts - CREIX_MIN) > CREIX_MARGE_MIN:
        return None
    yy, xx = np.ogrid[:MIDA, :MIDA]
    dist = np.hypot((yy - fila) * km_px, (xx - col) * km_px)
    a_prop = dist <= CREIX_KM

    def km2(camp):
        return round(float(((camp >= PLOU_MMH) & a_prop).sum() * km_px ** 2))

    def km_moderada(camp):
        m = camp >= FRANGES_MMH[0]
        return round(float(dist[m].min()), 1) if m.any() else None

    ara, abans = km2(rv["mm_h"][-1]), km2(rv["mm_h"][j])
    cercle = float(a_prop.sum() * km_px ** 2)
    mc = (r.get("meteocat") or {}).get("mm_h")
    return {"radar": "rainviewer", "hora": H.clau(t1), "minuts": minuts,
            "km2": ara, "km2_abans": abans,
            # La part del cercle amb pluja, en %: el que es diu a la pàgina.
            "pct": round(100 * ara / cercle), "pct_abans": round(100 * abans / cercle),
            "km_moderada": km_moderada(rv["mm_h"][-1]), "km_moderada_abans": km_moderada(rv["mm_h"][j]),
            "km2_meteocat": None if mc is None else km2(mc),
            "creix": ara - abans >= CREIX_GUANY_KM2}


def en_tram(nc, lloc, ini, fin, minim_min=0):
    """Lluvia esperada (mm) y probabilidad de lluvia entre ini y fin según la
    serie del lugar, o None si el tramo queda fuera del horizonte o cubre
    menos de minim_min minutos."""
    if not nc or lloc not in (nc.get("llocs") or {}):
        return None
    t0 = H.llegeix(nc["hora"])
    passos = [p for p in nc["llocs"][lloc]
              if ini <= t0 + dt.timedelta(minutes=p["min"]) < fin]
    if not passos or len(passos) * PAS_MIN < minim_min:
        return None
    mm = sum(p["mm_h"] for p in passos) * PAS_MIN / 60
    return {"mm": round(mm, 1), "prob": max(p["prob"] for p in passos), "minuts": len(passos) * PAS_MIN}


def arribada(nc, lloc="casa", prob=0.5):
    """Primer momento en que la probabilidad de lluvia llega a prob en el
    lugar (por defecto, la mitad del círculo), o None."""
    if not nc or lloc not in (nc.get("llocs") or {}):
        return None
    t0 = H.llegeix(nc["hora"])
    for p in nc["llocs"][lloc]:
        if p["prob"] >= prob:
            return t0 + dt.timedelta(minutes=p["min"])
    return None


def intensitat_arribada(nc, lloc="casa", prob=0.5, minuts=30):
    """Lluvia esperada más alta (mm/h) en los minutos siguientes a la llegada,
    o None si no llega."""
    passos = (nc or {}).get("llocs", {}).get(lloc) or []
    inici = next((p["min"] for p in passos if p["prob"] >= prob), None)
    if inici is None:
        return None
    return max(p["mm_h"] for p in passos if inici <= p["min"] <= inici + minuts)


if __name__ == "__main__":
    import prevision as P
    r = carrega(P.get)
    print("Errors:", r["errors"])
    nc = resum(r)
    print("Imatge:", nc["imatge"], nc["hora"], "· moviment:", nc["moviment"], nc["velocitat_kmh"], "km/h cap", nc["cap_a"])
    for lloc, s in nc["llocs"].items():
        print(lloc, " ".join(f"{p['min']}:{p['mm_h']}/{p['prob']}" for p in s[::3]))
    print("Arriba a casa:", arribada(nc))
