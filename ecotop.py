#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""¿Anuncia el ecotop de AEMET las tormentas antes que lo que ya usa la web?
Dos semanas de registro antes de decidir si se usa (ADR 0108; Juanjo,
19-10-2026: «aemet también tiene radar, merece la pena incorporarlo a la
web?» y «sí, localiza el ecotop y regístralo un par de semanas»).

La imagen del radar de AEMET ya llega a la web a través de RainViewer, que en
España la toma de AEMET OpenData (ADR 0026). Lo que no llega es el ecotop: la
altura máxima de los ecos de 12 dBZ o más, en km, que separa una tormenta (las
nubes suben a 8-10 km o más) de la lluvia de un frente (4-6 km). AEMET lo
publica del radar de Gelida, a unos 22 km de casa, cada 10 minutos, en la
descarga georreferenciada de su visor (GeoTIFF en EPSG:4326, colores RGBA por
clases de 1 km y la escala en los metadatos). El paquete trae los quince
radares y solo las tres últimas imágenes de cada producto (37 MB), así que se
baja cada CADA_MIN minutos como mucho y solo si hay lluvia a la vista.

- `apunta casa.json` (en cada pasada del NAS, desde publica.sh): si el radar
  ve lluvia a 60 km o menos, llueve, o la previsión da un 20 % o más en las
  próximas 6 horas, baja el paquete y, por cada imagen nueva del ecotop de
  Gelida, apunta una fila en registre/ecotop.csv: la hora de los datos, cuándo
  los publicó AEMET y cuándo se bajaron; el ecotop más alto sobre casa (1 km)
  y a 5, 15, 30 y 60 km; la superficie a 30 km o menos con 8 y 10 km o más, y
  la distancia y el rumbo de los más cercanos de 8 y 10 km. Guarda además el
  trozo de 60 km alrededor de casa (registre/ecotop/, PNG en grises con la
  clase en km) para poder medirlo de otra manera después.
- `estat`: cuántas imágenes hay, la última y el retraso de publicación.

La comparación con lo que pasó (la lluvia del barrio cada 5 minutos,
veines-5min.csv, y los avisos de intensidad de Meteocat) se hace al acabar el
registro, el 02-11-2026.

  python3 ecotop.py apunta /estat/casa.json | estat
"""
import csv
import datetime as dt
import io
import json
import math
import os
import re
import sys
import tarfile
import urllib.request

import numpy as np
from PIL import Image

import config as C
import hora as H

ZONA = H.ZONA

REGISTRE = os.environ.get("REGISTRE_DIR", "/estat/registre")
FITXER = os.path.join(REGISTRE, "ecotop.csv")
TROSSOS = os.path.join(REGISTRE, "ecotop")
BAIXADA = os.path.join(TROSSOS, "darrera-baixada")
URL = "https://www.aemet.es/es/api-eltiempo/radar/download/GLD"
RADAR = "GLD"                   # Barcelona - Gelida
PRODUCTE = "TOP.12DBZ_240"
CADA_MIN = 25                   # el paquete guarda 30 minutos (tres imágenes)
RADI_KM = 60
RADIS = (5, 15, 30, 60)
LLINDARS = (8, 10)              # km: por encima, casi siempre tormenta
PROB_MIN = 0.2
HORES_PREVISIO = 6
# La escala de AEMET (metadatos ESCALA): el límite inferior de cada clase, en km.
ESCALA = {20: (130, 10, 110), 16: (200, 0, 80), 14: (252, 0, 0), 12: (255, 107, 0),
          10: (255, 170, 0), 8: (255, 255, 0), 7: (0, 250, 0), 6: (150, 200, 0),
          5: (67, 131, 35), 4: (0, 255, 255), 3: (0, 190, 255), 2: (0, 130, 255), 1: (0, 0, 252)}
DIST2_MAX = 3000                # el GeoTIFF va con JPEG: los colores no son exactos
DESCONEGUT = 255
CAMPS = ["dades", "publicat", "baixat", "max_casa"] + [f"max_{r}" for r in RADIS] \
    + [f"km2_{l}_30" for l in LLINDARS] + [x for l in LLINDARS for x in (f"km_{l}", f"graus_{l}")] \
    + ["px_desconeguts"]


def cal(casa, ara):
    """Si hay lluvia a la vista: la del radar, la de ahora o la prevista."""
    if (casa.get("radar") or {}).get("propera") or (casa.get("pluja_ara") or {}).get("estat", "no") != "no":
        return True
    fins = ara + dt.timedelta(hours=HORES_PREVISIO)
    for h in casa.get("hores") or []:
        # Les hores de casa.json són claus en UTC (ADR 0128); H.llegeix entén
        # també les d'abans, locals i sense zona.
        t = H.llegeix(h["hora"])
        if ara - dt.timedelta(hours=1) < t <= fins and (h.get("probabilitat") or 0) >= PROB_MIN:
            return True
    return False


def classifica(rgba):
    """La clase (km) de cada píxel por el color más cercano de la escala; 0 sin
    eco y DESCONEGUT si ningún color se le parece."""
    pal = np.array(list(ESCALA.values()), dtype=np.int32)
    km = np.array(list(ESCALA), dtype=np.uint8)
    rgb = rgba[..., :3].astype(np.int32)
    d = ((rgb[..., None, :] - pal) ** 2).sum(-1)
    i = d.argmin(-1)
    out = np.where(d.min(-1) < DIST2_MAX, km[i], DESCONEGUT).astype(np.uint8)
    out[rgba[..., 3] <= 128] = 0
    return out


def mesura(classes, fila, col, km_x, km_y):
    """Lo que se apunta de un trozo de clases con casa en (fila, col)."""
    ny, nx = classes.shape
    dy = (np.arange(ny) - fila)[:, None] * km_y
    dx = (np.arange(nx) - col)[None, :] * km_x
    dist = np.hypot(dx, dy)
    valid = np.where(classes == DESCONEGUT, 0, classes)
    r = {"max_casa": int(valid[max(fila - 1, 0):fila + 2, max(col - 1, 0):col + 2].max())}
    for radi in RADIS:
        dins = valid[dist <= radi]
        r[f"max_{radi}"] = int(dins.max()) if dins.size else 0
    for l in LLINDARS:
        alt = valid >= l
        r[f"km2_{l}_30"] = round(float((alt & (dist <= 30)).sum() * km_x * km_y), 1)
        if alt.any():
            d = np.where(alt, dist, np.inf)
            j = np.unravel_index(d.argmin(), d.shape)
            r[f"km_{l}"] = round(float(d[j]), 1)
            # Rumbo desde casa, en grados desde el norte (las filas crecen hacia el sur).
            r[f"graus_{l}"] = round(math.degrees(math.atan2(dx[0, j[1]], -dy[j[0], 0])) % 360)
        else:
            r[f"km_{l}"] = r[f"graus_{l}"] = ""
    r["px_desconeguts"] = int((classes == DESCONEGUT).sum())
    return r


def tros(im):
    """El trozo de RADI_KM alrededor de casa en clases, con casa en el centro,
    y los km por píxel (en x y en y)."""
    lon0, lat0 = im.tag_v2[33922][3], im.tag_v2[33922][4]
    sx, sy = im.tag_v2[33550][0], im.tag_v2[33550][1]
    lat, lon = C.CASA
    km_y = sy * 111.32
    km_x = sx * 111.32 * math.cos(math.radians(lat))
    col, fila = round((lon - lon0) / sx), round((lat0 - lat) / sy)
    nx, ny = round(RADI_KM / km_x), round(RADI_KM / km_y)
    rgba = np.asarray(im.convert("RGBA").crop((col - nx, fila - ny, col + nx + 1, fila + ny + 1)))
    return classifica(rgba), ny, nx, km_x, km_y


def hora_dades(nom):
    """«down_GLD261019142000.TOP…» → las 14:20 UTC del 19-10-2026."""
    m = re.search(rf"down_{RADAR}(\d{{12}})\.", nom)
    return dt.datetime.strptime(m.group(1), "%y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)


def ja_apuntades():
    if not os.path.exists(FITXER):
        return set()
    with open(FITXER, encoding="utf-8") as f:
        return {H.clau(r["dades"]) for r in csv.DictReader(f)}


def apunta(casa_json, ara=None, baixa=None):
    ara = ara or H.ara()
    # La hora de la última bajada, aparte del CSV: una bajada sin imágenes
    # nuevas no deja fila y se repetiría en cada pasada.
    try:
        with open(BAIXADA, encoding="utf-8") as f:
            darrera = H.llegeix(f.read().strip())
        if ara - darrera < dt.timedelta(minutes=CADA_MIN):
            return 0
    except (OSError, ValueError):
        pass
    with open(casa_json, encoding="utf-8") as f:
        if not cal(json.load(f), ara):
            return 0
    dades = (baixa or baixa_paquet)()
    os.makedirs(TROSSOS, exist_ok=True)
    with open(BAIXADA, "w", encoding="utf-8") as f:
        f.write(H.clau(ara))
    vistes = ja_apuntades()
    files, mes_nova = [], None
    with tarfile.open(fileobj=io.BytesIO(dades), mode="r:gz") as tar:
        for m in tar.getmembers():
            if f"down_{RADAR}" not in m.name or PRODUCTE not in m.name:
                continue
            hora = hora_dades(m.name)
            mes_nova = max(mes_nova or hora, hora)
            clau = H.clau(hora)
            if clau in vistes:
                continue
            im = Image.open(io.BytesIO(tar.extractfile(m).read()))
            classes, fila, col, km_x, km_y = tros(im)
            Image.fromarray(classes, "L").save(os.path.join(TROSSOS, f"{RADAR}-{hora:%Y%m%d%H%M}Z.png"), optimize=True)
            publicat = H.clau(dt.datetime.fromtimestamp(m.mtime, dt.timezone.utc))
            files.append({"dades": clau, "publicat": publicat, "baixat": H.clau(ara),
                          **mesura(classes, fila, col, km_x, km_y)})
    files.sort(key=lambda r: r["dades"])
    nou = not os.path.exists(FITXER)
    with open(FITXER, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, CAMPS)
        if nou:
            w.writeheader()
        w.writerows(files)
    # Sin imagen de Gelida de la última hora, el radar está parado o AEMET ha
    # cambiado el paquete: que se vea en el registro del NAS.
    if mes_nova is None or ara - mes_nova > dt.timedelta(hours=1):
        print(f"{ara:%F %T}  l'ecotop de Gelida no té cap imatge de l'última hora "
              f"(la més nova: {mes_nova})", file=sys.stderr)
    return len(files)


def baixa_paquet():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Temps a Montflorit)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def estat():
    if not os.path.exists(FITXER):
        print("encara no hi ha cap imatge")
        return
    with open(FITXER, encoding="utf-8") as f:
        files = list(csv.DictReader(f))
    if not files:
        print("encara no hi ha cap imatge")
        return
    retard = [(H.utc(r["publicat"]) - H.utc(r["dades"])).total_seconds() / 60
              for r in files]
    altes = sum(1 for r in files if int(r["max_30"]) >= 8)
    print(f"{len(files)} imatges, de {files[0]['dades']} a {files[-1]['dades']}; "
          f"retard de publicació: mediana {sorted(retard)[len(retard) // 2]:.0f} min; "
          f"amb ecotop de 8 km o més a 30 km: {altes}")
    print(json.dumps(files[-1], ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "apunta":
        apunta(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "estat":
        estat()
    else:
        print(__doc__)
        sys.exit(1)
