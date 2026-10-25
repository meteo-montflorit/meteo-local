# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lo que pasa alrededor de Montflorit y condiciona salir (ADR 0046):

- incendios forestales en curso de la capa pública de actuaciones urgentes de
  Bombers de la Generalitat (ArcGIS), solo los que interesan al barrio (ADR
  0071): dentro del Parc Natural de Collserola, a cualquier distancia (el
  límite oficial de la capa del Consorci, sin sus enclaves), y fuera del parque, a
  ENTORN_RADI_KM o menos, en cualquier municipio (desde el 16-10-2026);
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


def interessa(municipi, dist, collserola):
    """Si un incendio interesa al barrio: en Collserola, a cualquier
    distancia; fuera, a ENTORN_RADI_KM o menos, en cualquier municipio
    (Juanjo, 16-10-2026: «bájalo a 2 km esté donde esté y luego los del
    parque»). El municipio ya no cuenta; se queda en la firma porque lo da
    Bombers y la página lo muestra."""
    return bool(collserola) or (dist is not None and dist <= C.ENTORN_RADI_KM)


def incendis(dades=None, collserola=None, fora=None, parats=None, ara=None):
    """Incendios de vegetación forestal en curso que interesan al barrio
    (interessa), del más cercano al más lejano. En «fora», si se pasa, los
    identificadores de los que siguen en curso pero quedan fuera de la zona:
    salir de ella no es acabar (16-10-2026, ADR 0071). En «parats», los que
    Bombers deja abiertos sin ningún vehículo ni cambio desde hace
    INCENDI_PARAT_H horas, con la hora del último cambio: se dan por apagados
    (25-10-2026, ADR 0071)."""
    ara = ara or H.ara()
    xmin, ymin, xmax, ymax = C.INCENDIS_CAIXA
    d = dades or get(BOMBERS + "/query", {
        "where": "TAL_COD_ALARMA1='IV'", "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
        "outSR": 4326,
        "outFields": "GlobalID,TAL_DESC_ALARMA2,MUNICIPI_SIG,ACT_DAT_INICI,ACT_DAT_FI,ACT_DAT_ACTUAL,ACT_NUM_VEH,COM_FASE",
        "returnGeometry": "true", "f": "json"})
    if "error" in d:
        raise RuntimeError(d["error"].get("message"))
    collserola = collserola or dins_collserola
    res = []
    for f in d.get("features", []):
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
                fora.append(a["GlobalID"])
            continue
        # Uno de Montcada se quedó abierto el 24-10-2026 con 0 vehículos y sin
        # ningún cambio desde que se dio de alta; los de antes duraron una hora
        # como mucho. Si Bombers vuelve a tocarlo, reaparece.
        canvi = a.get("ACT_DAT_ACTUAL") or a.get("ACT_DAT_INICI")
        if a.get("ACT_NUM_VEH") == 0 and canvi and \
                ara - dt.datetime.fromtimestamp(canvi / 1000, H.UTC) > dt.timedelta(hours=C.INCENDI_PARAT_H):
            if parats is not None:
                parats[a["GlobalID"]] = hora_iso(canvi)
            continue
        res.append({"id": a["GlobalID"], "municipi": municipi, "km": round(dist, 1),
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
    fora, parats = [], {}
    for clau, funcio in (("incendis", lambda: incendis(fora=fora, parats=parats, ara=ara)), ("pla_alfa", lambda: pla_alfa(ara))):
        try:
            res[clau] = funcio()
        except Exception as ex:
            res[clau] = None
            res["errors"].append(f"{clau}: {ex}")
    res["incendis_fora"] = None if res["incendis"] is None else fora
    res["incendis_parats"] = None if res["incendis"] is None else parats
    return res


if __name__ == "__main__":
    print(json.dumps(calcula(), ensure_ascii=False, indent=1))
