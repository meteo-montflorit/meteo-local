# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lo que pasa alrededor de Montflorit y condiciona salir (ADR 0046):

- incendios forestales en curso de la capa pública de actuaciones urgentes de
  Bombers de la Generalitat (ArcGIS), solo los que interesan al barrio (ADR
  0071): dentro del Parc Natural de Collserola (el límite oficial de la capa
  del Consorci, sin sus enclaves), a COLLSEROLA_RADI_KM o menos (desde el
  28-10-2026), y en cualquier sitio a ENTORN_RADI_KM o menos (desde el
  16-10-2026);
- el nivel del Pla Alfa de Cerdanyola hoy y mañana, y los cierres de espacios
  naturales que tocan Collserola, de las capas públicas de Agents Rurals
  (ArcGIS).

Las restricciones de acceso a Collserola por la peste porcina se leían de los
avisos de la web del parque; se quitaron el mismo día, por frágiles (dependían
de cómo y cuándo los redactaran: ADR 0046).

Las dos fuentes de ArcGIS son las que usan los visores oficiales, no conjuntos
de datos documentados: si una falla, su parte queda en None y se dice.

    python3 entorn.py        lo que hay ahora, en JSON
"""
import datetime as dt
import json
import math
import os
import tempfile
import time
import urllib.parse
import urllib.request

import config as C
import hora as H

ARCGIS = "https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services"
BOMBERS = ARCGIS + "/ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW/FeatureServer/0"
# El visor público de Bombers (ArcGIS Experience Builder): acepta en la
# dirección el centro y la escala de sus dos mapas, el del ordenador
# (widget_1) y el del móvil (widget_67). Si un día cambian, abre Cataluña
# entera, como antes (28-10-2026, ADR 0071).
VISOR = "https://experience.arcgis.com/experience/f6172fd2d6974bc0a8c51e3a6bc2a735/"
# Escala del nivel 0 de los mapas de teselas de ArcGIS (Web Mercator).
ESCALA_Z0 = 591657527.591555
# El límite del Parc Natural de la Serra de Collserola, del Consorci del parque.
COLLSEROLA = ("https://services7.arcgis.com/z50OW9s1n52Z8H2C/arcgis/rest/services/"
              "L%C3%ADmit_Parc_de_Collserola/FeatureServer/0")
ALFA_MUNICIPAL = {"avui": ARCGIS + "/Pla_Alfa_Municipal_Avui_FL_2_view/FeatureServer/0",
                  "dema": ARCGIS + "/pla_alfa_municipal_dema_FL_VW/FeatureServer/5"}
ALFA_TANCAMENTS = {"avui": ARCGIS + "/tancaments_pla_alfa_avui_VW/FeatureServer/2",
                   "dema": ARCGIS + "/tancaments_pla_alfa_dema_VW/FeatureServer/2"}
UA = {"User-Agent": "Temps a Montflorit (https://meteo-montflorit.github.io/)"}

def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    return 6371 * math.hypot((lo2 - lo1) * math.cos((la1 + la2) / 2), la2 - la1)


def hora_iso(ms):
    return H.clau(dt.datetime.fromtimestamp(ms / 1000, H.UTC)) if ms else None


# El contorno exterior del parque, sin los agujeros de su límite oficial (Les
# Planes, Can Cerdà, Vallvidrera…: 77 enclaves urbanos): un incendio que
# empieza en uno de ellos puede llegar a Montflorit a través del parque
# (Juanjo, 16-10-2026: «todo lo que quede dentro del recinto debe marcarse»).
# Se baja de la capa del Consorci y se guarda CONTORN_DIES días; sin él, la
# consulta a la capa, con los agujeros.
CONTORN = os.path.join(tempfile.gettempdir(), "meteo-collserola-contorn.json")
CONTORN_DIES = 7


def contorn():
    """Los anillos exteriores del parque, [[(lon, lat), …], …], o None."""
    try:
        if time.time() - os.path.getmtime(CONTORN) < CONTORN_DIES * 86400:
            with open(CONTORN) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    try:
        d = get(COLLSEROLA + "/query", {"where": "1=1", "outSR": 4326, "f": "geojson"})
        anells = [f["geometry"]["coordinates"][0] for f in d["features"] if f["geometry"]["type"] == "Polygon"]
        anells += [pol[0] for f in d["features"] if f["geometry"]["type"] == "MultiPolygon"
                   for pol in f["geometry"]["coordinates"]]
        if not anells:
            raise ValueError("sense polígons")
        with open(CONTORN + ".tmp", "w") as f:
            json.dump(anells, f)
        os.replace(CONTORN + ".tmp", CONTORN)
        return anells
    except Exception:
        try:
            with open(CONTORN) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None


def dins_anells(y, x, anells, marge_km):
    """Si el punto (lat y, lon x) cae dentro de algún anillo o a marge_km o
    menos de su borde (en plano local, que a estas distancias basta)."""
    kx, ky = 111.32 * math.cos(math.radians(y)), 110.57
    for anell in anells:
        dins = False
        for (x1, y1), (x2, y2) in zip(anell, anell[1:] + anell[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                dins = not dins
            # Distancia del punto al segmento.
            ax, ay, bx, by = (x1 - x) * kx, (y1 - y) * ky, (x2 - x) * kx, (y2 - y) * ky
            dx, dy = bx - ax, by - ay
            t = 0 if dx == dy == 0 else max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
            if math.hypot(ax + t * dx, ay + t * dy) <= marge_km:
                return True
        if dins:
            return True
    return False


def dins_collserola(y, x):
    """Si el punto cae dentro del parque, sin sus enclaves, con
    COLLSEROLA_MARGE_KM de margen: la posición de una actuación es aproximada."""
    anells = contorn()
    if anells:
        return dins_anells(y, x, anells, C.COLLSEROLA_MARGE_KM)
    d = get(COLLSEROLA + "/query", {
        "geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "distance": C.COLLSEROLA_MARGE_KM,
        "units": "esriSRUnit_Kilometer", "returnCountOnly": "true", "f": "json"})
    if "error" in d:
        raise RuntimeError(d["error"].get("message"))
    return d.get("count", 0) > 0


def mapa(lat, lon):
    """El visor de Bombers con el incendio y Montflorit a la vista en el móvil
    (unos 390 × 600 píxeles de mapa), con margen: centrado entre los dos y en
    el nivel de zoom que pide la distancia (Juanjo, 28-10-2026: «el mapa
    siempre hay que hacer zoom»). El visor redondea la escala a sus niveles
    (la de 1:100.000 la mostró a 1:72.224): se le pide ya uno, el más cercano
    en que caben los dos, y como mucho INCENDI_MAPA_ZOOM_MAX."""
    y, x = (lat + C.CASA[0]) / 2, (lon + C.CASA[1]) / 2
    dx = abs(lon - C.CASA[1]) * 111320 * math.cos(math.radians(y))
    dy = abs(lat - C.CASA[0]) * 111320
    # Metros por píxel de pantalla a escala 1: 0,0254 m / 96.
    cal = max(dx / 390, dy / 600) * 1.3 / (0.0254 / 96)
    zoom = min(C.INCENDI_MAPA_ZOOM_MAX, math.floor(math.log2(ESCALA_Z0 / cal)) if cal else C.INCENDI_MAPA_ZOOM_MAX)
    vista = f"center:{x:.4f}%2C{y:.4f}%2C4326,scale:{ESCALA_Z0 / 2 ** zoom:.3f}"
    return f"{VISOR}#widget_1={vista}&widget_67={vista}"


def interessa(municipi, dist, collserola):
    """Si un incendio interesa al barrio: en Collserola, a COLLSEROLA_RADI_KM
    o menos (Juanjo, 28-10-2026: «limita los avisos a 5 km en collserola»);
    en cualquier sitio, a ENTORN_RADI_KM o menos (16-10-2026: «bájalo a 2 km
    esté donde esté y luego los del parque»). El municipio ya no cuenta; se queda en la firma porque lo da
    Bombers y la página lo muestra."""
    if dist is None:
        return False
    return dist <= C.ENTORN_RADI_KM or (bool(collserola) and dist <= C.COLLSEROLA_RADI_KM)


def incendis(dades=None, collserola=None, fora=None, parats=None, ara=None, alies=None):
    """Incendios de vegetación forestal en curso que interesan al barrio
    (interessa), del más cercano al más lejano. En «fora», si se pasa, los
    identificadores de los que siguen en curso pero quedan fuera de la zona:
    salir de ella no es acabar (16-10-2026, ADR 0071). En «parats», los que
    Bombers deja abiertos sin ningún vehículo ni cambio desde hace
    INCENDI_PARAT_H horas, con la hora del último cambio: se dan por apagados
    (25-10-2026, ADR 0071). Cada incendio se identifica por el número de la
    actuación; en «alies», el GlobalID de cada fila con ese número, el
    identificador de antes (28-10-2026, ADR 0071)."""
    ara = ara or H.ara()
    xmin, ymin, xmax, ymax = C.INCENDIS_CAIXA
    d = dades or get(BOMBERS + "/query", {
        "where": "TAL_COD_ALARMA1='IV'", "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
        "outSR": 4326,
        "outFields": "GlobalID,OBJECTID,TAL_DESC_ALARMA2,MUNICIPI_SIG,ACT_DAT_INICI,ACT_DAT_FI,ACT_DAT_ACTUAL,"
                     "ACT_NUM_VEH,COM_FASE",
        "returnGeometry": "true", "f": "json"})
    if "error" in d:
        raise RuntimeError(d["error"].get("message"))
    collserola = collserola or dins_collserola
    # La capa repite filas de una misma actuación: mismo OBJECTID (el número
    # de Bombers), misma posición y mismas horas; solo cambian ESRI_OID y
    # GlobalID. El 28-10-2026, uno de Sant Cugat salió dos veces y los vecinos
    # recibieron dos avisos iguales; ese día, 5 de las 7 actuaciones de la
    # capa estaban repetidas. Y la que queda al dejar de repetirse puede ser
    # cualquiera: el incendio es el número de la actuación, no la fila.
    actuacions = {}
    for f in d.get("features", []):
        a = f["attributes"]
        iid = str(a.get("OBJECTID") or a["GlobalID"])
        actuacions.setdefault(iid, []).append(f)
        if alies is not None and a.get("GlobalID") and a["GlobalID"] != iid:
            alies[a["GlobalID"]] = iid
    res = []
    for iid, grup in actuacions.items():
        f = grup[0]
        a, g = f["attributes"], f.get("geometry") or {}
        # Solo los forestales: los de solares urbanos son muchos y no limitan salir.
        if "forestal" not in (a.get("TAL_DESC_ALARMA2") or "").lower() or a.get("ACT_DAT_FI"):
            continue
        if "x" not in g:
            continue
        dist = km(C.CASA, (g["y"], g["x"]))
        municipi = a.get("MUNICIPI_SIG")
        al_parc = collserola(g["y"], g["x"])
        if not interessa(municipi, dist, al_parc):
            if fora is not None:
                fora.append(iid)
            continue
        # Uno de Montcada se quedó abierto el 24-10-2026 con 0 vehículos y sin
        # ningún cambio desde que se dio de alta; los de antes duraron una hora
        # como mucho. Si Bombers vuelve a tocarlo, reaparece.
        canvi = a.get("ACT_DAT_ACTUAL") or a.get("ACT_DAT_INICI")
        if a.get("ACT_NUM_VEH") == 0 and canvi and \
                ara - dt.datetime.fromtimestamp(canvi / 1000, H.UTC) > dt.timedelta(hours=C.INCENDI_PARAT_H):
            if parats is not None:
                parats[iid] = hora_iso(canvi)
            continue
        res.append({"id": iid, "municipi": municipi, "km": round(dist, 1), "mapa": mapa(g["y"], g["x"]),
                    "collserola": al_parc, "inici": hora_iso(a.get("ACT_DAT_INICI")),
                    "vehicles": a.get("ACT_NUM_VEH"), "fase": a.get("COM_FASE")})
    return sorted(res, key=lambda i: i["km"])


def actualitzada(url, ara, hores):
    """Si la capa se ha editado en las últimas `hores`: fuera de campaña, la
    del Pla Alfa municipal se queda con el último valor y no vale."""
    edit = ((get(url, {"f": "json"}).get("editingInfo") or {}).get("lastEditDate"))
    return bool(edit) and ara - dt.datetime.fromtimestamp(edit / 1000, H.UTC) <= dt.timedelta(hours=hores)


def pla_alfa(ara):
    """Nivel del Pla Alfa de Cerdanyola hoy y mañana (None si la capa no está
    al día) y los cierres de espacios naturales que tocan Collserola."""
    res = {}
    for dia, url in ALFA_MUNICIPAL.items():
        nivell = None
        if actualitzada(url, ara, C.ALFA_ACTUAL_H):
            d = get(url + "/query", {"where": f"CODIMUNI='{C.ALFA_MUNICIPI}'", "outFields": "PERIL_M",
                                     "returnGeometry": "false", "f": "json"})
            files = d.get("features") or []
            nivell = files[0]["attributes"]["PERIL_M"] if files else None
        # La escala es 0-4; el 5 es «sin nivel» (gris claro en el mapa oficial).
        res[dia] = nivell if nivell in (0, 1, 2, 3, 4) else None
    tancaments = []
    for dia, url in ALFA_TANCAMENTS.items():
        d = get(url + "/query", {"where": "1=1", "outFields": "Espai_prot", "returnGeometry": "false", "f": "json"})
        for f in d.get("features") or []:
            nom = f["attributes"].get("Espai_prot") or ""
            if "collserola" in nom.lower():
                tancaments.append({"dia": dia, "espai": nom})
    res["tancaments"] = tancaments
    return res


def calcula(ara=None):
    """Para casa.json y los datos públicos. Cada parte, None si su fuente falla."""
    ara = ara or H.ara()
    res = {"hora": H.clau(ara), "errors": []}
    fora, parats, alies = [], {}, {}
    for clau, funcio in (("incendis", lambda: incendis(fora=fora, parats=parats, ara=ara, alies=alies)), ("pla_alfa", lambda: pla_alfa(ara))):
        try:
            res[clau] = funcio()
        except Exception as ex:
            res[clau] = None
            res["errors"].append(f"{clau}: {ex}")
    res["incendis_fora"] = None if res["incendis"] is None else fora
    res["incendis_parats"] = None if res["incendis"] is None else parats
    res["incendis_alies"] = None if res["incendis"] is None else alies
    return res


if __name__ == "__main__":
    print(json.dumps(calcula(), ensure_ascii=False, indent=1))
