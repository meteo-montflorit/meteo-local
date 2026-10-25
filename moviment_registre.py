#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""¿Acierta el movimiento del radar? Un mes de registro antes de decidir si
hay que revisarlo (ADR 0019; Juanjo, 17-10-2026: «el calculo de la velocidad
y direccion de la lluvia es correcto o habria que revisarlo?» y «monta el
registro del movimiento»).

El movimiento (nowcast.moviment) solo se comprobó con una tarde, la del
06-10-2026 (ADR 0023), y no se guardaba. En cada pasada del NAS, sin pedir
nada más a nadie (las imágenes son las que ya se han bajado):

- `apunta(r, nc)` (desde prevision.radar): guarda el trozo de 60 km alrededor de
  casa de la última imagen de cada radar (Meteocat y RainViewer), con el
  movimiento que se ha usado, en /estat/moviment (se borran a las 3 horas).
  Después, para cada trozo de hace unos 30 y 60 minutos del mismo radar, lleva
  su lluvia hacia delante con el movimiento de entonces y la compara con la
  de ahora, en el círculo de 50 km: el índice de acierto (CSI, aciertos entre
  aciertos, fallos y falsas alarmas) del movimiento y el de dejarla quieta.
  Una fila por comparación en registre/moviment.csv.
- `apunta_creixement(c)` (también desde prevision.radar): cuánta lluvia hay a
  15 km o menos de casa en la última imagen de RainViewer y en la de 30
  minutos antes, y a qué distancia está la moderada, una fila por imagen en
  registre/creixement.csv. Para comprobar con la lluvia medida en casa si la
  lluvia que crece alrededor anuncia la de casa (Juanjo, 17-10-2026: «no se
  trata solo de la direccion de la lluvia sino de hacia donde crece»).
- `resum`: el CSI medio del movimiento y de dejarla quieta, por antelación y
  por de dónde sale el movimiento, en cuántos casos gana cada uno y, para las
  horas con movimiento, cuánto se aparta del viento a 700 hPa (unos 3.000 m,
  el que arrastra los chubascos) de Open-Meteo.

  python3 moviment_registre.py resum
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import sys

import config as C
import hora as H
import nowcast as N

REGISTRE = os.environ.get("REGISTRE_DIR", "/estat/registre")
FITXER = os.path.join(REGISTRE, "moviment.csv")
FITXER_CREIX = os.path.join(REGISTRE, "creixement.csv")
CAMPS_CREIX = ["emes", "minuts", "km2", "km2_abans", "km_moderada", "km_moderada_abans", "km2_meteocat", "creix"]
TROSSOS = os.path.join(os.path.dirname(REGISTRE), "moviment")
CAMPS = ["emes", "radar", "antelacio_min", "font_moviment", "kmh", "graus",
         "csi_moviment", "csi_quieta", "px_vista", "px_prevista", "px_quieta"]
RADI_KM = 60          # el trozo que se guarda
AVALUA_KM = 50        # donde se compara: margen para lo que entra de fuera
ANTELACIONS = (30, 60)
MARGE_MIN = 8         # la imagen de hace 30 min puede ser de hace 22 a 38
GUARDA_H = 3
PX_MIN = 20           # con menos lluvia, vista y prevista, no se compara


def tros(camp, fila, col, n):
    """El trozo de 2n+1 píxeles centrado en casa, en décimas de mm/h."""
    import numpy as np
    f0, c0 = int(round(fila)), int(round(col))
    t = camp[f0 - n:f0 + n + 1, c0 - n:c0 + n + 1]
    return np.clip(np.round(t * 10), 0, 255).astype(np.uint8)


def desplaca(a, df, dc):
    """a desplazada df filas y dc columnas, con ceros en lo que entra."""
    import numpy as np
    b = np.zeros_like(a)
    n = a.shape[0]
    if abs(df) >= n or abs(dc) >= n:
        return b
    b[max(df, 0):n + min(df, 0), max(dc, 0):n + min(dc, 0)] = a[max(-df, 0):n + min(-df, 0), max(-dc, 0):n + min(-dc, 0)]
    return b


def csi(prevista, vista):
    encerts = (prevista & vista).sum()
    total = (prevista | vista).sum()
    return None if total == 0 else round(float(encerts / total), 3)


def apunta(r, nc, ara=None):
    """Guarda las imágenes de ahora y compara con ellas las de hace 30 y 60
    minutos; nc es nowcast.resum(r), con el movimiento que se ha usado. Solo
    en el NAS (si existe la carpeta del registro)."""
    import numpy as np
    if not os.path.isdir(REGISTRE):
        return 0
    ara = ara or H.ara()
    os.makedirs(TROSSOS, exist_ok=True)
    fila, col = N.pixel(C.CASA[0], C.CASA[1], r["tx"], r["ty"])
    k = r["km_px"]
    n = int(math.ceil(RADI_KM / k))
    v = (nc or {}).get("v")
    font = (nc or {}).get("moviment") or "cap"
    imatges = []
    mc, rv = r.get("meteocat") or {}, r.get("rainviewer")
    if "mm_h" in mc:
        imatges.append(("meteocat", mc["hora"], mc["mm_h"]))
    if rv:
        imatges.append(("rainviewer", rv["hores"][-1], rv["mm_h"][-1]))
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    zona = np.hypot(yy, xx) * k <= AVALUA_KM
    files = []
    for radar, hora, camp in imatges:
        # El nom, amb l'hora en UTC: la nit d'octubre, les dues imatges de les
        # 2:30 tenien el mateix nom (ADR 0128).
        ruta = os.path.join(TROSSOS, f"{radar}-{H.utc(hora):%Y%m%d%H%M}Z.npz")
        ara_t = tros(camp, fila, col, n)
        if not os.path.exists(ruta):
            np.savez_compressed(ruta, mm=ara_t, km_px=k, hora=H.clau(hora),
                                v=np.array(v if v else (np.nan, np.nan)), font=font if v else "cap")
        vista = (ara_t >= N.PLOU_MMH * 10) & zona
        for antelacio in ANTELACIONS:
            for vell in glob.glob(os.path.join(TROSSOS, f"{radar}-*.npz")):
                d = np.load(vell)
                hora_v = H.llegeix(str(d["hora"]))
                minuts = (hora - hora_v).total_seconds() / 60
                if abs(minuts - antelacio) > MARGE_MIN or ja_avaluat(radar, hora_v, antelacio):
                    continue
                antiga = d["mm"] >= N.PLOU_MMH * 10
                vv = d["v"]
                if np.isnan(vv).any():
                    prevista = antiga
                    kmh = graus = None
                else:
                    prevista = desplaca(antiga, int(round(vv[0] * minuts)), int(round(vv[1] * minuts)))
                    kmh, graus = round(math.hypot(*vv) * k * 60, 1), round(N.graus(vv))
                prevista, quieta = prevista & zona, antiga & zona
                if vista.sum() < PX_MIN and prevista.sum() < PX_MIN and quieta.sum() < PX_MIN:
                    continue
                files.append({"emes": H.clau(hora_v), "radar": radar,
                              "antelacio_min": antelacio, "font_moviment": str(d["font"]), "kmh": kmh,
                              "graus": graus, "csi_moviment": csi(prevista, vista), "csi_quieta": csi(quieta, vista),
                              "px_vista": int(vista.sum()), "px_prevista": int(prevista.sum()),
                              "px_quieta": int(quieta.sum())})
    if files:
        nou = not os.path.exists(FITXER)
        with open(FITXER, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, CAMPS)
            if nou:
                w.writeheader()
            w.writerows(files)
    neteja(ara)
    return len(files)


def apunta_creixement(c):
    """Una fila per imatge de RainViewer (la mateixa imatge en diverses
    passades, una sola vegada). Només al NAS."""
    if not c or not os.path.isdir(REGISTRE):
        return 0
    nou = not os.path.exists(FITXER_CREIX)
    if not nou:
        with open(FITXER_CREIX, encoding="utf-8") as f:
            darrera = f.readlines()[-1]
        if darrera.startswith(c["hora"] + ","):
            return 0
    with open(FITXER_CREIX, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, CAMPS_CREIX, extrasaction="ignore")
        if nou:
            w.writeheader()
        w.writerow({**c, "emes": c["hora"], "creix": int(bool(c["creix"]))})
    return 1


_avaluats = None


def ja_avaluat(radar, hora, antelacio):
    """Si ya hay fila para esta imagen y antelación (una pasada que se repite
    con la misma imagen no la vuelve a contar)."""
    global _avaluats
    if _avaluats is None:
        _avaluats = set()
        if os.path.exists(FITXER):
            with open(FITXER, encoding="utf-8") as f:
                _avaluats = {(x["radar"], H.clau(x["emes"]), int(x["antelacio_min"])) for x in csv.DictReader(f)}
    clau = (radar, H.clau(hora), antelacio)
    if clau in _avaluats:
        return True
    _avaluats.add(clau)
    return False


def neteja(ara):
    for ruta in glob.glob(os.path.join(TROSSOS, "*.npz")):
        if os.path.getmtime(ruta) < ara.timestamp() - GUARDA_H * 3600:
            os.remove(ruta)


def vent_700(dies, get):
    """El viento a 700 hPa en casa, hora a hora, de Open-Meteo (previsión
    histórica): {«AAAA-MM-DDTHH» en UTC: (km/h, grados de donde viene)}. En
    UTC (timezone=GMT): con la hora de Madrid, Open-Meteo ponía a toda la serie
    el desfase del día de la consulta, y los casos de la otra mitad del año
    salían una hora desplazados (ADR 0128). Un día más a cada lado, porque los
    días de dies son de UTC."""
    lat, lon = C.CASA
    url = ("https://historical-forecast-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&hourly=wind_speed_700hPa,wind_direction_700hPa&start_date={ini}&end_date={fi}&timezone=GMT")
    ini = (dt.date.fromisoformat(min(dies)) - dt.timedelta(days=1)).isoformat()
    fi = (dt.date.fromisoformat(max(dies)) + dt.timedelta(days=1)).isoformat()
    h = json.loads(get(url.format(lat=lat, lon=lon, ini=ini, fi=fi)))["hourly"]
    return {t[:13]: (s, d) for t, s, d in zip(h["time"], h["wind_speed_700hPa"], h["wind_direction_700hPa"])
            if s is not None and d is not None}


def resum(get=None):
    if not os.path.exists(FITXER):
        print("Encara no hi ha cap comparació.")
        return
    with open(FITXER, encoding="utf-8") as f:
        files = [x for x in csv.DictReader(f) if x["csi_moviment"] and x["csi_quieta"]]
    dies = sorted({x["emes"][:10] for x in files})
    print(f"{len(files)} comparacions, {len(dies)} dies amb pluja a prop ({dies[0]} a {dies[-1]})." if files
          else "Cap comparació amb pluja.")
    grups = {}
    for x in files:
        for clau in ((x["antelacio_min"], "totes"), (x["antelacio_min"], x["font_moviment"])):
            grups.setdefault(clau, []).append(x)
    print("\nCSI mitjà (1 = encert perfecte) del moviment i de deixar-la quieta:")
    for (ant, font), g in sorted(grups.items()):
        m = sum(float(x["csi_moviment"]) for x in g) / len(g)
        q = sum(float(x["csi_quieta"]) for x in g) / len(g)
        guanya = sum(float(x["csi_moviment"]) > float(x["csi_quieta"]) for x in g)
        perd = sum(float(x["csi_moviment"]) < float(x["csi_quieta"]) for x in g)
        print(f"  {ant} min, {font:<10} {len(g):4d} casos · moviment {m:.3f} · quieta {q:.3f}"
              f" · guanya el moviment {guanya}, perd {perd}")
    amb = [x for x in files if x["graus"]]
    if not amb:
        return
    try:
        import prevision as P
        vent = vent_700({H.clau(x["emes"])[:10] for x in amb}, get or P.get)
    except Exception as ex:
        print(f"\nSense el vent a 700 hPa: {ex}")
        return
    difs, rati = [], []
    for x in amb:
        w = vent.get(H.clau(x["emes"])[:13])
        if not w or w[0] < 5:
            continue
        cap = (w[1] + 180) % 360
        difs.append(abs((float(x["graus"]) - cap + 180) % 360 - 180))
        rati.append(float(x["kmh"]) / w[0])
    if difs:
        difs.sort()
        rati.sort()
        print(f"\nContra el vent a 700 hPa ({len(difs)} casos amb vent de 5 km/h o més): diferència de direcció"
              f" mediana {difs[len(difs) // 2]:.0f}° (el 90 % per sota de {difs[int(len(difs) * 0.9)]:.0f}°);"
              f" velocitat del radar / vent, mediana {rati[len(rati) // 2]:.2f}.")


if __name__ == "__main__":
    if sys.argv[1:] == ["resum"]:
        resum()
    else:
        print(__doc__)
