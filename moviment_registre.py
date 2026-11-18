#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""¿Acierta el movimiento del radar? Un mes de registro antes de decidir si
había que revisarlo (ADR 0019; Juanjo, 17-10-2026: «el calculo de la velocidad
y direccion de la lluvia es correcto o habria que revisarlo?» y «monta el
registro del movimiento»).

Decidido el 18-11-2026 (ADR 0019): el movimiento es correcto y se deja como
está, así que la comparación se retiró. Lo que sigue en cada pasada del NAS,
sin pedir nada más a nadie (las imágenes son las que ya se han bajado):

- `apunta(r, nc)` (desde prevision.radar): guarda el trozo de 60 km alrededor de
  casa de la última imagen de cada radar (Meteocat y RainViewer), con el
  movimiento que se ha usado, en /estat/moviment; a las 3 horas se borra, o
  va al archivo si tiene lluvia cerca (ADR 0049). Del 17-10 al 18-11-2026,
  además, comparaba la lluvia de hace 30 y 60 minutos llevada hacia delante
  con la que veía después el mismo radar, y con dejarla quieta, en
  registre/moviment.csv, que se conserva.
- `apunta_creixement(c)` (también desde prevision.radar): cuánta lluvia hay a
  15 km o menos de casa en la última imagen de RainViewer y en la de 30
  minutos antes, y a qué distancia está la moderada, una fila por imagen en
  registre/creixement.csv. Para comprobar con la lluvia medida en casa si la
  lluvia que crece alrededor anuncia la de casa (Juanjo, 17-10-2026: «no se
  trata solo de la direccion de la lluvia sino de hacia donde crece»). Con el
  primer mes no bastaba (ADR 0019): sigue hasta la revisión de primavera.
- `resum`: con el registro del mes, el CSI medio del movimiento y de dejarla
  quieta, por antelación y por de dónde sale el movimiento, en cuántos casos
  gana cada uno y cuánto se aparta del viento a 700 hPa (unos 3.000 m, el que
  arrastra los chubascos) de Open-Meteo.

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
ARXIU = os.path.join(REGISTRE, "radar-retalls")   # los trozos con lluvia cerca, sin borrar
ARXIU_KM = 30
RADI_KM = 60          # el trozo que se guarda
GUARDA_H = 3


def tros(camp, fila, col, n):
    """El trozo de 2n+1 píxeles centrado en casa, en décimas de mm/h."""
    import numpy as np
    f0, c0 = int(round(fila)), int(round(col))
    t = camp[f0 - n:f0 + n + 1, c0 - n:c0 + n + 1]
    return np.clip(np.round(t * 10), 0, 255).astype(np.uint8)


def apunta(r, nc, ara=None):
    """Guarda las imágenes de ahora, con el movimiento que se ha usado (nc es
    nowcast.resum(r)), y archiva o borra las de hace más de GUARDA_H horas.
    Solo en el NAS (si existe la carpeta del registro)."""
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
    noves = 0
    for radar, hora, camp in imatges:
        # El nom, amb l'hora en UTC: la nit d'octubre, les dues imatges de les
        # 2:30 tenien el mateix nom (ADR 0128).
        ruta = os.path.join(TROSSOS, f"{radar}-{H.utc(hora):%Y%m%d%H%M}Z.npz")
        if not os.path.exists(ruta):
            np.savez_compressed(ruta, mm=tros(camp, fila, col, n), km_px=k, hora=H.clau(hora),
                                v=np.array(v if v else (np.nan, np.nan)), font=font if v else "cap")
            noves += 1
    neteja(ara)
    return noves


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


def neteja(ara):
    """Los trozos de más de GUARDA_H horas se borran, salvo los que tienen
    lluvia a ARXIU_KM o menos de casa: van al archivo (ARXIU, una carpeta por
    mes), para probar con lo ya pasado otras formas de calcular el final de la
    lluvia (fi_pluja.py, ADR 0049). Unos 5 kB cada uno."""
    import numpy as np
    for ruta in glob.glob(os.path.join(TROSSOS, "*.npz")):
        if os.path.getmtime(ruta) < ara.timestamp() - GUARDA_H * 3600:
            try:
                d = np.load(ruta)
                n = d["mm"].shape[0] // 2
                yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
                plou = ((d["mm"] >= N.PLOU_MMH * 10) & (np.hypot(yy, xx) * float(d["km_px"]) <= ARXIU_KM)).any()
                mes = H.utc(H.llegeix(str(d["hora"]))).strftime("%Y-%m")
            except Exception:
                plou = False
            if plou:
                desti = os.path.join(ARXIU, mes)
                os.makedirs(desti, exist_ok=True)
                os.replace(ruta, os.path.join(desti, os.path.basename(ruta)))
            else:
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
