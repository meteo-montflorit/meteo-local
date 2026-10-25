#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Las previsiones oficiales para Cerdanyola, apuntadas para compararlas con
la de la web (ADR 0110; Juanjo, 20-10-2026: «una comparación en cómo lo
predice el propio meteocat para cerdanyola» y «también estaría bien la
comparación con la prediccion de aemet para cerdanyola»).

Ni Meteocat ni AEMET guardan sus previsiones pasadas: la comparación empieza
el día que se empiezan a apuntar. En cada pasada del NAS (publica.sh):

- Meteocat, la previsión municipal por horas de Cerdanyola
  (`/pronostic/v1/municipalHoraria/082665`, 72 horas): temperatura y lluvia
  en mm por hora, sin probabilidad. Cada METEOCAT_CADA_MIN minutos y como
  mucho METEOCAT_MES consultas al mes: el plan es de 1.500 consultas al mes
  para todo lo de predicción, y la reserva de los avisos (smp.py, ADR 0109)
  puede necesitar una cada 30 minutos. Si la reserva se ha usado en las
  últimas RESERVA_H horas, no se consulta: los avisos van primero.
- AEMET, la predicción horaria del municipio 08266 (dos peticiones: la que da
  la dirección de los datos y los datos): temperatura y lluvia en mm por
  hora, y la probabilidad de lluvia por tramos de 6 horas. Cada
  AEMET_CADA_MIN minutos. Lleva la hora en que se elaboró.

Una línea por consulta en registre/previsio-oficial-AAAA-MM.jsonl:
{"font", "llegit", "elaborat", "t": {hora: °C}, "mm": {hora: mm}, "p6":
{inicio: [fin, %]}}, con las horas como en todo el programa (hora local,
prevision.clau_hora). Si no ha cambiado nada desde la anterior de la misma
fuente, solo {"font", "llegit", "repetit": true}: así se sabe qué previsión
estaba vigente en cada momento sin repetirla entera.

La temperatura es la de la hora en punto; la lluvia de una hora se apunta con
la hora en que acaba el periodo que dice cada fuente, tal como la dan (la
lectura que hace historial.py, y lo que falta comprobar, en el ADR 0110).

  python3 previsio_oficial.py apunta | estat
"""
import datetime as dt
import glob
import hashlib
import json
import os
import sys
import urllib.request

import hora as H
import prevision as P

REGISTRE = os.environ.get("REGISTRE_DIR", "/estat/registre")
ESTAT = os.path.join(REGISTRE, "previsio-oficial-estat.json")
MUNICIPI_METEOCAT = "082665"     # Cerdanyola del Vallès (config.ALFA_MUNICIPI)
MUNICIPI_AEMET = "08266"
URL_METEOCAT = f"https://api.meteo.cat/pronostic/v1/municipalHoraria/{MUNICIPI_METEOCAT}"
URL_AEMET = f"https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/horaria/{MUNICIPI_AEMET}"
METEOCAT_CADA_MIN = 180          # 8 al día, unas 250 al mes
METEOCAT_MES = 260
AEMET_CADA_MIN = 60
RESERVA_H = 2
CACHE_SMP = os.path.join(os.environ.get("CACHE_WEB", "/estat/cache-web"), "smp-api.json")


def clau(nom, variable):
    """La clave de la API: la variable de entorno o ~/.config/meteo-local/<nom>.env."""
    if os.environ.get(variable):
        return os.environ[variable]
    try:
        with open(os.path.expanduser(f"~/.config/meteo-local/{nom}.env"), encoding="utf-8") as f:
            for linia in f:
                k, _, v = linia.strip().partition("=")
                if k == variable and v:
                    return v
    except OSError:
        pass
    return None


def baixa(url, capcaleres=None, codificacio="utf-8"):
    req = urllib.request.Request(url, headers={"User-Agent": "meteo-local", **(capcaleres or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode(codificacio)


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return 0.0 if x == 0 else x          # el «-0.0» de Meteocat


def llegeix_meteocat(text):
    """{"t", "mm"} de la respuesta de Meteocat (horas en UTC, «…Z»). Cada
    variable es {"unitat", "valors": [...]}; la lluvia, {"unitat", "valor": [...]}."""
    d = json.loads(text)
    t, mm = {}, {}
    valors = lambda x: (x.get("valors") or x.get("valor") or []) if isinstance(x, dict) else (x or [])
    for dia in d.get("dies") or []:
        v = dia.get("variables") or {}
        for desti, llista in ((t, valors(v.get("temp"))), (mm, valors(v.get("precipitacio")))):
            for x in llista:
                valor = _num(x.get("valor"))
                if valor is None or not x.get("data"):
                    continue
                hora = H.llegeix(x["data"].replace("Z", "+00:00"))
                desti[P.clau_hora(hora)] = valor
    if not t:
        raise ValueError("Meteocat no torna temperatures")
    return {"t": t, "mm": mm}


def _hora_aemet(dia, hh):
    """La hora local de AEMET: el día de «fecha» y la hora «HH» (24 es la medianoche siguiente)."""
    base = dt.datetime.combine(dia, dt.time()) + dt.timedelta(hours=int(hh))
    return P.clau_hora(base.replace(tzinfo=P.ZONA))


def llegeix_aemet(text):
    """{"elaborat", "t", "mm", "p6"} de los datos de AEMET (hora local). La
    lluvia «Ip» (inapreciable) cuenta como 0."""
    d = json.loads(text)
    d = d[0] if isinstance(d, list) else d
    t, mm, p6 = {}, {}, {}
    for dia in (d.get("prediccion") or {}).get("dia") or []:
        data = dt.date.fromisoformat(dia["fecha"][:10])
        for x in dia.get("temperatura") or []:
            v = _num(x.get("value"))
            if v is not None:
                t[_hora_aemet(data, x["periodo"])] = v
        for x in dia.get("precipitacion") or []:
            v = 0.0 if x.get("value") == "Ip" else _num(x.get("value"))
            if v is not None:
                mm[_hora_aemet(data, x["periodo"])] = v
        for x in dia.get("probPrecipitacion") or []:
            v, per = _num(x.get("value")), x.get("periodo") or ""
            if v is None or len(per) != 4:
                continue
            ini, fi = int(per[:2]), int(per[2:])
            p6[_hora_aemet(data, ini)] = [_hora_aemet(data, fi + (24 if fi <= ini else 0)), v]
    if not t:
        raise ValueError("AEMET no torna temperatures")
    elaborat = d.get("elaborado")
    if elaborat:
        # Sense zona, però en UTC: llegida com a hora de Madrid, la diferència
        # amb l'hora de baixada saltava just una hora amb el canvi d'hora (de
        # 127 min com a mínim a 75); com a UTC queda entre 7 i 71 min tot l'any
        # (registre d'octubre de 2026, ADR 0128).
        quan = dt.datetime.fromisoformat(elaborat)
        elaborat = P.clau_hora(quan if quan.tzinfo else quan.replace(tzinfo=H.UTC))
    return {"elaborat": elaborat, "t": t, "mm": mm, "p6": p6}


def consulta_meteocat(clau_api, get=baixa):
    return llegeix_meteocat(get(URL_METEOCAT, {"X-Api-Key": clau_api}))


def consulta_aemet(clau_api, get=baixa):
    meta = json.loads(get(URL_AEMET, {"api_key": clau_api}))
    if not meta.get("datos"):
        raise ValueError(f"AEMET: {meta.get('descripcion') or 'sense dades'}")
    return llegeix_aemet(get(meta["datos"], None, "iso-8859-15"))


def _llegeix_estat():
    try:
        with open(ESTAT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _desa_estat(estat):
    os.makedirs(REGISTRE, exist_ok=True)
    with open(ESTAT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estat, f)
    os.replace(ESTAT + ".tmp", ESTAT)


def reserva_en_us(ara, cache=CACHE_SMP):
    """Si la reserva de los avisos (smp.py) ha consultado la API hace poco."""
    try:
        return ara.timestamp() - os.path.getmtime(cache) < RESERVA_H * 3600
    except OSError:
        return False


def toca(estat, font, ara, cada_min):
    ultima = (estat.get(font) or {}).get("llegit")
    return not ultima or ara - H.llegeix(ultima) >= dt.timedelta(minutes=cada_min) - dt.timedelta(seconds=90)


def apunta(ara=None, consultes=None, reserva=reserva_en_us):
    """Consulta las fuentes que toca y las apunta. Devuelve lo hecho, por fuente."""
    ara = ara or H.ara()
    consultes = consultes or {"meteocat": lambda: consulta_meteocat(clau("meteocat", "METEOCAT_API_KEY")),
                              "aemet": lambda: consulta_aemet(clau("aemet", "AEMET_API_KEY"))}
    estat = _llegeix_estat()
    mes = H.local(ara).strftime("%Y-%m")
    fet = {}
    for font, cada in (("meteocat", METEOCAT_CADA_MIN), ("aemet", AEMET_CADA_MIN)):
        e = estat.setdefault(font, {})
        if not toca(estat, font, ara, cada):
            continue
        if font == "meteocat":
            if e.get("mes") != mes:
                e["mes"], e["consultes"] = mes, 0
            if e["consultes"] >= METEOCAT_MES or reserva(ara):
                fet[font] = "saltada"
                continue
            e["consultes"] += 1
        e["llegit"] = H.clau(ara)
        try:
            dades = consultes[font]()
        except Exception as ex:          # que una fuente no pare la otra ni la publicación
            e["error"] = f"{H.iso_local(ara)} {str(ex)[:200] or type(ex).__name__}"
            fet[font] = "error"
            continue
        e.pop("error", None)
        empremta = hashlib.sha1(json.dumps(dades, sort_keys=True).encode()).hexdigest()
        if empremta == e.get("empremta"):
            linia = {"font": font, "llegit": e["llegit"], "repetit": True}
            fet[font] = "repetida"
        else:
            linia = {"font": font, "llegit": e["llegit"], "elaborat": dades.get("elaborat"), **dades}
            e["empremta"] = empremta
            fet[font] = "nova"
        os.makedirs(REGISTRE, exist_ok=True)
        with open(os.path.join(REGISTRE, f"previsio-oficial-{mes}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(linia, ensure_ascii=False, separators=(",", ":")) + "\n")
    _desa_estat(estat)
    return fet


def registre(carpeta=None):
    """Las consultas apuntadas, por fuente: [(llegit, {"t", "mm", "p6"})], en
    orden; las repetidas llevan las de la anterior."""
    res = {}
    for ruta in sorted(glob.glob(os.path.join(carpeta or REGISTRE, "previsio-oficial-*.jsonl"))):
        with open(ruta, encoding="utf-8") as f:
            for linia in f:
                try:
                    e = json.loads(linia)
                except ValueError:
                    continue
                llista = res.setdefault(e.get("font"), [])
                if e.get("repetit"):
                    if llista:
                        llista.append((H.llegeix(e["llegit"]), llista[-1][1]))
                    continue
                # Les claus, en UTC també les d'abans de la migració (ADR 0128).
                hores = lambda d: {H.clau(k): v for k, v in (d or {}).items()}  # noqa: E731
                llista.append((H.llegeix(e["llegit"]),
                               {"t": hores(e.get("t")), "mm": hores(e.get("mm")),
                                "p6": {H.clau(k): [H.clau(v[0]), v[1]] for k, v in (e.get("p6") or {}).items()}}))
    for llista in res.values():
        llista.sort(key=lambda x: x[0])
    return res


def estat():
    e = _llegeix_estat()
    r = registre()
    for font in ("meteocat", "aemet"):
        llista = r.get(font) or []
        canvis = sum(1 for i, (_, d) in enumerate(llista) if i == 0 or d is not llista[i - 1][1])
        linia = f"{font}: {len(llista)} consultes, {canvis} amb previsió nova"
        if llista:
            linia += f"; la primera, {H.local(llista[0][0]):%d-%m %H:%M}; l'última, {H.local(llista[-1][0]):%d-%m %H:%M}"
        if font == "meteocat" and e.get(font, {}).get("mes"):
            linia += f"; aquest mes, {e[font].get('consultes', 0)} de {METEOCAT_MES}"
        if (e.get(font) or {}).get("error"):
            linia += f"; error: {e[font]['error']}"
        print(linia)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("apunta", "estat"):
        sys.exit(__doc__)
    if sys.argv[1] == "apunta":
        print(json.dumps(apunta(), ensure_ascii=False))
    else:
        estat()
