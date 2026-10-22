# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proves de casa.recoger(), la passada sencera de la pàgina de casa, sense
xarxa ni registre.

L'arnès (Fonts) falseja totes les fonts que llegeix recoger(): l'estació de
casa (Ecowitt), les veïnes de Weather Underground, Open-Meteo (models,
ensemble, UV i sol, per un sol encaminador d'adreces), els avisos de l'AEMET,
els plans de Protecció Civil, el Meteocat (SMP), el radar, la riera, el METAR
de Sabadell, els trens, el trànsit, la llum, l'aire, el pol·len i l'entorn.
Cada font té un valor per defecte (un dia sec, sense avisos, amb totes les
fonts que responen) i cada prova en canvia només el que mira:

    s = Fonts(avisos=RuntimeError("503")).executa()

- un valor qualsevol: la font el retorna (una còpia, perquè recoger() el
  pot modificar);
- una excepció: la font falla amb ella;
- una funció: es crida amb els mateixos arguments que la font de veritat.

Amb registre=True, recoger() es comporta com al NAS (R.hay_registro) i totes
les funcions que hi escriuen són MagicMock (Fonts.mocks), per mirar què s'hi
apunta sense tocar el disc. Tots els canvis als mòduls es desfan en sortir
(mock.patch.object), també casa.SMP_ACTUAL.
"""
import contextlib
import copy
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import aire as AI  # noqa: E402
import aprenentatge as A  # noqa: E402
import casa  # noqa: E402
import config as C  # noqa: E402
import ecowitt as E  # noqa: E402
import entorn as EN  # noqa: E402
import estacions as ES  # noqa: E402
import fi_pluja as FP  # noqa: E402
import llum as LL  # noqa: E402
import nuvols as NV  # noqa: E402
import part_alta as PA  # noqa: E402
import pollen as PO  # noqa: E402
import prevision as P  # noqa: E402
import radar_fonts as RF  # noqa: E402
import registre as R  # noqa: E402
import riera as RI  # noqa: E402
import riscos as RS  # noqa: E402
import smp as SMP  # noqa: E402
import sol_estacio as SE  # noqa: E402
import transit as TT  # noqa: E402
import trens as TR  # noqa: E402
import vent_veines as VV  # noqa: E402
import wunderground as WU  # noqa: E402

# Un dimarts de tardor a mig matí, en horari d'estiu (+02:00).
AHORA = dt.datetime(2026, 10, 20, 10, 37).astimezone()
OFFSET = 7200

# La persistència de la pluja (calibracio.json), fixa perquè les proves no
# depenguin de la calibració del moment.
PERSISTENCIA = {"1.0": {"1": {"probabilitat": 0.8, "mediana_mm": 1.1},
                        "2": {"probabilitat": 0.6, "mediana_mm": 0.3},
                        "3": {"probabilitat": 0.45, "mediana_mm": 0.1},
                        "4": {"probabilitat": 0.4, "mediana_mm": 0.0}}}


def hores_open_meteo(desde, n=72):
    """Les hores que dona Open-Meteo, en hora local sense desfase."""
    ini = dt.datetime.fromisoformat(desde)
    return [(ini + dt.timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M") for k in range(n)]


class OpenMeteoFals:
    """Fa de P.get i P.get_reintenta: contesta cada consulta segons el que
    demana (principal, ensemble, ecmwf, núvols d'un model, vent de 15 minuts,
    UV o sol). pluja: {«AAAA-MM-DDTHH:MM»: mm} dels models fins a l'hora que
    acaba aquí. fallen: les consultes que fallen. ensemble: la fracció de
    membres amb pluja a totes les hores."""

    def __init__(self, pluja=None, fallen=(), ensemble=0.0, temperatura=16.0, humitat=80.0,
                 pressio=1015.0, uv=3.0):
        self.pluja, self.fallen, self.ensemble = pluja or {}, set(fallen), ensemble
        self.temperatura, self.humitat, self.pressio, self.uv = temperatura, humitat, pressio, uv
        self.consultes = []

    def tipus(self, url):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        model = q.get("models", [""])[0]
        if "ensemble-api" in url:
            return "ensemble", q
        if "minutely_15" in q:
            return "vent15", q
        if "daily" in q:
            return "sol", q
        if q.get("hourly") == ["uv_index"]:
            return "uv", q
        if model == C.MODEL_ECMWF and q.get("hourly") == ["precipitation"]:
            return "ecmwf", q
        if model in NV.MODELS_APART:
            return "nuvols", q
        return "principal", q

    def __call__(self, url, *args, **kwargs):
        tipus, q = self.tipus(url)
        self.consultes.append(tipus)
        if tipus in self.fallen:
            raise RuntimeError(f"Open-Meteo {tipus}: 503")
        temps = hores_open_meteo(q["start_date"][0] + "T00:00")
        n = len(temps)
        if tipus == "principal":
            h = {"time": temps}
            for camp, v in (("temperature_2m", self.temperatura), ("relative_humidity_2m", self.humitat),
                            ("weather_code", 3), ("cloud_cover", 60), ("cloud_cover_low", 20),
                            ("wind_speed_10m", 10.0), ("wind_gusts_10m", 25.0), ("shortwave_radiation", 200),
                            ("snowfall", 0.0), ("pressure_msl", self.pressio)):
                h[f"{camp}_meteofrance_seamless"] = [v] * n
            h["precipitation_meteofrance_seamless"] = [0.0] * n
            for m in C.MODELOS_FINOS:
                h[f"precipitation_{m}"] = [self.pluja.get(t, 0.0) for t in temps]
                h[f"wind_gusts_10m_{m}"] = [30.0] * n
            h["cloud_cover_icon_eu"] = [40] * n
            return json.dumps({"utc_offset_seconds": OFFSET, "hourly": h})
        if tipus == "ensemble":
            membres = 10
            plujosos = round(self.ensemble * membres)
            h = {"time": temps}
            for k in range(membres):
                h[f"precipitation_member{k:02d}"] = [1.0 if k < plujosos else 0.0] * n
            return json.dumps({"utc_offset_seconds": OFFSET, "hourly": h})
        if tipus == "ecmwf":
            return json.dumps({"utc_offset_seconds": OFFSET, "hourly": {"time": temps, "precipitation": [0.0] * n}})
        if tipus == "nuvols":
            return json.dumps({"utc_offset_seconds": OFFSET,
                               "hourly": {"time": temps, "cloud_cover": [80] * n, "cloud_cover_low": [10] * n}})
        if tipus == "vent15":
            t15 = [(dt.datetime.fromisoformat(temps[0]) + dt.timedelta(minutes=15 * k)).strftime("%Y-%m-%dT%H:%M")
                   for k in range(n * 4)]
            return json.dumps({"minutely_15": {"time": t15, "wind_speed_10m": [12.0] * len(t15)}})
        if tipus == "uv":
            return json.dumps({"utc_offset_seconds": OFFSET, "hourly": {"time": temps, "uv_index": [self.uv] * n}})
        dies = [q["start_date"][0], q["end_date"][0]]
        return json.dumps({"utc_offset_seconds": OFFSET, "daily": {
            "time": dies, "sunrise": [f"{d}T08:05" for d in dies], "sunset": [f"{d}T18:55" for d in dies],
            "uv_index_max": [4.0, 3.5]}})


def lectures_casa(fins, pluja_ultima_hora=0.0, desde_h=3.75):
    """Lectures de l'estació de casa cada 5 minuts (ecowitt.resum_ara), amb la
    pluja de la darrera hora repartida igual."""
    res, t = [], fins - dt.timedelta(hours=desde_h)
    total = 2.0
    while t <= fins:
        if fins - t < dt.timedelta(hours=1):
            total += pluja_ultima_hora / 12
        res.append({"t": t, "pluja_avui": round(total, 2), "temperatura": 15.0, "humitat": 85.0,
                    "rosada": 12.5, "pressio": 1016.5, "solar": 50.0})
        t += dt.timedelta(minutes=5)
    return res


def estacio(plou=False, minuts=2, humitat=85.0, pluja_1h=None, pluja_3h=None, temperatura=15.0):
    """El que retorna ecowitt.resum_ara(): la lectura d'ara i les files."""
    hora = AHORA - dt.timedelta(minutes=minuts)
    p1 = (1.2 if plou else 0.0) if pluja_1h is None else pluja_1h
    return {"hora": hora.isoformat(timespec="minutes"), "temperatura": temperatura, "humitat": humitat,
            "rosada": 12.5, "pressio": 1016.5, "pluja_avui": 2.0 + p1, "intensitat": 4.0 if plou else 0.0,
            "pluja_15min": 0.3 if plou else 0.0, "pluja_30min": 0.6 if plou else 0.0, "pluja_1h": p1,
            "pluja_3h": p1 if pluja_3h is None else pluja_3h, "pressio_3h": -0.5, "plou": plou,
            "files": lectures_casa(hora, p1)}


def veina(estacio_id, plou=False, compta=True, temperatura=15.5, minuts=3, pluja_15min=None):
    """Una veïna de Weather Underground (wunderground.veina_ara)."""
    hora = AHORA - dt.timedelta(minutes=minuts)
    p15 = (0.3 if plou else 0.0) if pluja_15min is None else pluja_15min
    return {"estacio": estacio_id, "nom": estacio_id, "hora": hora.isoformat(timespec="minutes"),
            "temperatura": temperatura, "humitat": 82.0, "rosada": 12.0, "pressio": 1014.0,
            "pluja_15min": p15, "pluja_30min": p15 * 2, "pluja_1h": p15 * 3, "pluja_3h": p15 * 3,
            "pluja_avui": p15 * 3, "plou": plou, "compta": compta, "intensitat": 3.0 if plou else 0.0,
            "files": [{"t": hora - dt.timedelta(minutes=5 * k), "pluja_avui": 0.0, "temperatura": temperatura,
                       "vent": 5.0} for k in range(3, -1, -1)]}


def radar(minuts_arribada=None, prob=0.9, mm_h=4.0, retard_min=7, plugim_px=0, km=None):
    """El que retorna P.radar(): el nowcast de casa (cada 5 minuts, dues
    hores), amb pluja des de minuts_arribada (None: sense pluja), i els ecos
    febles a sobre del barri de cada radar (plugim_px píxels a 1 km)."""
    hora = (AHORA - dt.timedelta(minutes=retard_min)).replace(second=0, microsecond=0)
    passos = [{"min": m, "mm_h": mm_h if minuts_arribada is not None and m >= minuts_arribada else 0.0,
               "prob": prob if minuts_arribada is not None and m >= minuts_arribada else 0.0}
              for m in range(0, 120, 5)]
    nc = {"hora": hora.isoformat(timespec="minutes"), "imatge": "meteocat", "moviment": True,
          "velocitat_kmh": 30, "cap_a": "NE", "graus": 45, "llocs": {"casa": passos}}
    px = [(1.0, 0, 0.3)] * plugim_px
    return {"nowcast": nc, "imatge": "meteocat", "hora": nc["hora"],
            "km_lluvia": km if km is not None else (0.0 if minuts_arribada == 0 else None),
            "a_prop": {"meteocat": {"px": px}, "rainviewer": {"px": px}},
            "mapa": {"url": "mapa.png"}, "propera": None, "forta": None, "creixement": None}


def avis_aemet(tipo="pluja", nivel="groc", hores=(9, 15), zona=C.ZONA_AVISOS):
    ini, fi = (AHORA.replace(hour=h, minute=0, second=0, microsecond=0) for h in hores)
    return {"zona": zona, "tipo": tipo, "nivel": nivel,
            "inicio": ini.isoformat(), "fin": fi.isoformat()}


def entorn_buit(*_args, **_kw):
    return {"incendis": [], "errors": []}


class Fonts:
    """Totes les fonts de recoger() falsejades (vegeu el docstring del mòdul).
    Els noms dels paràmetres són els de la font; els valors per defecte, un
    dia sec i tranquil."""

    PER_DEFECTE = {
        "ecowitt": True,                      # E.disponible
        "estacio": lambda: estacio(),         # E.resum_ara
        "wu_puja": True,                      # WU.disponible (pujar l'estació)
        "wu_lectura": True,                   # WU.lectura_disponible
        "veines": lambda *_a: ([veina("ICERDA6"), veina("ICERDA18", temperatura=17.0),
                                veina("ICERDA28", temperatura=16.0)], []),
        "wu_caduca": 100,                     # WU.dies_fins_caducitat
        "vent": {"estacio": "XV", "mitja": 8.0, "ratxa": 20.0},
        "vent_veines": None,
        "avisos": [],
        "plans": [],
        "smp": {"avisos": []},
        "llindars": {"plugim": {"pluja": 0.2, "risc": 0.3}},
        "radar": lambda: radar(),
        "fi_radar": None,
        "riera": {"mm_1h": 0.0, "fins": AHORA.isoformat(timespec="minutes"), "nivell": "normal"},
        "riera_fins": "2026-10-20T08:00+02:00",
        "riera_previsio": {"pics": []},
        "metars": [],
        "trens": {"r": []},
        "transit": {"incidencies": []},
        "llum": {"talls": []},
        "aire": {"ica": 1},
        "pollen": {"nivells": []},
        "entorn": entorn_buit,
        "riscos": [],
        "part_alta": {h: 1.0 for h in range(24)},  # PA.per_hores (amb registre)
        "part_alta_inicial": {h: 1.0 for h in range(24)},  # PA.inicial (sense)
        "temperatures": {"2026-10-19T10:00": 14.0},
    }

    def __init__(self, open_meteo=None, registre=False, **canvis):
        desconeguts = set(canvis) - set(self.PER_DEFECTE)
        if desconeguts:
            raise TypeError(f"fonts desconegudes: {desconeguts}")
        self.valors = {**self.PER_DEFECTE, **canvis}
        self.open_meteo = open_meteo or OpenMeteoFals()
        self.registre = registre
        self.mocks = {}
        self.stderr = ""

    @staticmethod
    def font(valor):
        """La funció falsa d'una font (vegeu el docstring del mòdul)."""
        if isinstance(valor, BaseException):
            def falla(*_a, **_kw):
                raise valor
            return falla
        if callable(valor):
            return valor
        return lambda *_a, **_kw: copy.deepcopy(valor)

    def pegats(self):
        v, f = self.valors, self.font
        pegats = [
            (E, "disponible", f(v["ecowitt"])), (E, "resum_ara", f(v["estacio"])),
            (R, "hay_registro", f(self.registre)), (R, "temperatures_casa", f(v["temperatures"])),
            (WU, "disponible", f(v["wu_puja"])), (WU, "lectura_disponible", f(v["wu_lectura"])),
            (WU, "veines_ara", f(v["veines"])), (WU, "dies_fins_caducitat", f(v["wu_caduca"])),
            (PA, "per_hores", f(v["part_alta"])), (PA, "inicial", f(v["part_alta_inicial"])),
            (PA, "ajust_nit", f(None)),
            (P, "vent_meteocat", f(v["vent"])), (VV, "ara", f(v["vent_veines"])),
            (P, "avisos", f(v["avisos"])), (P, "planes_proteccion_civil", f(v["plans"])),
            (SMP, "llegeix", f(v["smp"])), (A, "llindars_sortir", f(v["llindars"])),
            (P, "radar", f(v["radar"])), (FP, "fi_radar", f(v["fi_radar"])),
            (RI, "calcula", f(v["riera"])), (RI, "darrera_meteocat", f(v["riera_fins"])),
            (RI, "previsio", f(v["riera_previsio"])), (NV, "llegeix", f(v["metars"])),
            (NV, "pesos", NV.per_defecte),
            (A, "carrega", f({"pluja": None, "temperatura": None, "humitat": None})),
            (TR, "calcula", f(v["trens"])), (TT, "calcula", f(v["transit"])),
            (LL, "calcula", f(v["llum"])), (AI, "calcula", f(v["aire"])),
            (PO, "calcula", f(v["pollen"])), (EN, "calcula", f(v["entorn"])),
            (P, "get", self.open_meteo), (P, "get_reintenta", self.open_meteo),
            (P, "CALIBRACION_COMPLETA", {"persistencia": PERSISTENCIA}),
            (P, "AHORA", AHORA), (casa, "SMP_ACTUAL", None),
        ]
        # El que s'apunta al registre (i el que hi va a parar), per mirar-ho.
        for modul, nom in ((RS, "detecta"), (SE, "corregeix"), (SE, "amb_esperades"), (ES, "vigila"),
                           (WU, "puja"), (WU, "hores_ahir"), (PA, "apunta_nit"),
                           (R, "apunta_estacio_casa"), (R, "apunta_casa_5min"), (R, "cincs_casa"),
                           (R, "apunta_veines_5min"), (R, "apunta_casa"), (R, "apunta_radar_a_prop"),
                           (R, "apunta_meteocat"), (R, "hores_meteocat"), (RI, "files"),
                           (R, "falta_ahir_veina"), (R, "apunta_veina"), (R, "hores_veina"),
                           (VV, "mitges_hores_veina"), (VV, "mitges_hores_meteocat"), (P, "files_meteocat"),
                           (VV, "apunta"), (NV, "apunta"), (RF, "apunta")):
            m = mock.MagicMock(name=f"{modul.__name__}.{nom}")
            self.mocks[f"{modul.__name__}.{nom}"] = m
            pegats.append((modul, nom, m))
        m = self.mocks
        m["riscos.detecta"].return_value = copy.deepcopy(v["riscos"])
        m["sol_estacio.corregeix"].side_effect = lambda ara, *_a: {**ara, "corregida": True}
        m["sol_estacio.amb_esperades"].side_effect = lambda t, *_a: t
        m["wunderground.hores_ahir"].return_value = []
        m["registre.falta_ahir_veina"].return_value = False
        m["registre.cincs_casa"].return_value = []
        return pegats

    def executa(self, anterior=None):
        """Fa una passada de recoger() amb les fonts falses i retorna el que
        sortiria a casa.json. El que escriu a stderr queda a self.stderr."""
        err = io.StringIO()
        with contextlib.ExitStack() as pila:
            for modul, nom, valor in self.pegats():
                pila.enter_context(mock.patch.object(modul, nom, valor))
            pila.enter_context(contextlib.redirect_stderr(err))
            salida = casa.recoger(anterior)
            self.smp_actual = casa.SMP_ACTUAL
        self.stderr = err.getvalue()
        return salida


class Estructura(unittest.TestCase):
    def test_passada_sense_errors_te_totes_les_claus(self):
        fonts = Fonts()
        s = fonts.executa()
        self.assertEqual(s["errors"], [])
        self.assertEqual(s["versio"], C.VERSION)
        self.assertEqual(s["generat"], "2026-10-20T10:37+02:00")
        for clau in ("ara_casa", "temperatura_mesurada", "veines", "plou_ara", "vent", "vent_veines", "smp",
                     "plans_ocults", "avisos", "plans", "sortir_llindars", "radar", "riera", "riera_previsio",
                     "horari", "aprenentatge", "hores", "models", "pluja_ara", "trens", "transit", "llum",
                     "sol", "aire", "pollen", "entorn", "riscos"):
            self.assertIn(clau, s, clau)
        # Sense registre (la reserva d'IONOS) no es compara amb ahir.
        self.assertIsNone(s["temperatura_mesurada"])
        # «files» no surt a la pàgina: ni de casa ni de les veïnes.
        self.assertNotIn("files", s["ara_casa"])
        self.assertTrue(all("files" not in v for v in s["veines"]))
        self.assertEqual([v["estacio"] for v in s["veines"]], ["ICERDA6", "ICERDA18", "ICERDA28"])
        self.assertEqual(s["ara_casa"]["temperatura"], 15.0)
        # La part alta: la mediana de les de dalt menys la de casa.
        self.assertEqual(s["ara_casa"]["dif_alta"], 1.5)
        # El que diuen els riscos parteix de la sortida ja muntada.
        fonts.mocks["riscos.detecta"].assert_called_once()
        self.assertIs(fonts.mocks["riscos.detecta"].call_args[0][0], s)

    def test_les_hores_de_la_taula(self):
        s = Fonts().executa()
        hores = s["hores"]
        # De la hora en curs (10 a 11) fins a les 21 h de demà: 35 trams.
        self.assertEqual((hores[0]["hora"], hores[0]["fins"]), ("2026-10-20T10:00", "2026-10-20T11:00"))
        self.assertEqual(hores[-1]["fins"], "2026-10-21T21:00")
        self.assertEqual(len(hores), 35)
        f = hores[0]
        self.assertFalse(f["plou_ara"])
        self.assertEqual(f["pluja_mm"], 0.0)
        self.assertEqual(f["probabilitat"], 0.0)      # l'ensemble: cap membre plou
        self.assertEqual(f["temperatura"], 16.0)
        self.assertEqual(f["vent"], 12.0)               # la mitjana dels 15 minuts
        self.assertEqual(f["ratxa"], 30.0)              # la del model fi, no la combinada
        # La pressió, portada a l'estació de casa (+1,5 hPa sobre AROME).
        self.assertEqual(f["pressio"], 1016.5)
        # Els núvols de quatre models: AROME 60, ICON-EU 40, ECMWF i GFS 80.
        self.assertEqual(f["nuvols"], 65)
        self.assertEqual(f["uv"], 3.0)
        self.assertIn("dif_alta", f)
        # Les darreres 3 hores, amb l'estació: no plou i els models tampoc.
        self.assertEqual(s["models"], {"hores": 3, "mesurada_mm": 0.0, "prevista_mm": 0.0, "no_encerten": False})
        self.assertEqual(s["sol"][0], {"dia": "2026-10-20", "sortida": "2026-10-20T08:05",
                                       "posta": "2026-10-20T18:55", "uv_max": 4.0})
        self.assertEqual(s["aprenentatge"], {"pluja": None, "temperatura": None, "humitat": None})

    def test_horari_normal_i_mode_avis(self):
        s = Fonts().executa()
        self.assertEqual(s["horari"]["mode_avis"], [])
        self.assertEqual(s["horari"]["cada_min"], C.INTERVALO_CASA_MIN)
        s = Fonts(avisos=[avis_aemet()]).executa()
        self.assertIn("avís de l'AEMET", s["horari"]["mode_avis"])
        self.assertEqual(s["horari"]["cada_min"], C.MODO_AVISO_INTERVALO_MIN)
        self.assertEqual(s["horari"]["trams"], [C.HORARIO_CASA_AVISO])
        # I la taula el pinta a les hores que cobreix, i no després.
        self.assertEqual(s["hores"][0]["avisos"], [{"nivell": "groc", "tipus": ["pluja"]}])
        self.assertEqual(s["hores"][6]["avisos"], [])

    def test_avisos_d_altres_zones_o_acabats_no_hi_son(self):
        avisos = [avis_aemet(zona="Litoral sud de Barcelona"), avis_aemet(hores=(6, 10)),
                  avis_aemet("vent", hores=(12, 18))]
        s = Fonts(avisos=avisos).executa()
        self.assertEqual([a["tipo"] for a in s["avisos"]], ["vent"])

    def test_plans_sense_motiu_meteorologic_van_a_part(self):
        plans = [{"pla": "INUNCAT", "fase": "alerta", "motiu": True},
                 {"pla": "NEUCAT", "fase": "prealerta", "motiu": False}]
        with mock.patch.object(P, "pla_per_temps", lambda p, *_a: p["motiu"]):
            s = Fonts(plans=plans).executa()
        self.assertEqual([p["pla"] for p in s["plans"]], ["INUNCAT"])
        self.assertEqual([p["pla"] for p in s["plans_ocults"]], ["NEUCAT"])
        self.assertIn("pla de Protecció Civil", s["horari"]["mode_avis"])

    def test_meteocat_es_desa_per_a_la_taula_i_es_desfa(self):
        smp = {"avisos": []}
        fonts = Fonts(smp=smp)
        fonts.executa()
        # Durant la passada, la taula llegeix l'SMP d'aquesta passada…
        self.assertEqual(fonts.smp_actual, smp)
        # …i l'arnès el deixa com estava.
        self.assertIsNone(casa.SMP_ACTUAL)

    def test_el_vent_de_les_veines_nomes_si_s_activa(self):
        vv = {"estacio": "estacions veïnes", "mitja": 6.0, "ratxa": 15.0}
        s = Fonts(vent_veines=vv).executa()
        self.assertEqual(s["vent"]["estacio"], "XV")
        self.assertEqual(s["vent_veines"], vv)
        with mock.patch.object(C, "VENT_VEINES_ACTIU", True):
            s = Fonts(vent_veines=vv).executa()
        self.assertEqual(s["vent"], vv)

    def test_el_radar_a_la_pagina(self):
        fonts = Fonts(radar=radar(40, prob=0.9, mm_h=6.0), fi_radar={"fi": "2026-10-20T12:30+02:00"})
        s = fonts.executa()
        r = s["radar"]
        self.assertEqual(r["graus"], 45)
        self.assertEqual(r["mapa"], {"url": "mapa.png"})
        # Arriba als 40 minuts de la imatge (10:30): les 11:10, amb 6 mm/h.
        self.assertEqual(r["arriba"], "2026-10-20T11:10+02:00")
        self.assertEqual(r["possible"], "2026-10-20T11:10+02:00")
        self.assertEqual(r["arriba_mm_h"], 6.0)
        self.assertEqual(r["fi"], "2026-10-20T12:30+02:00")
        self.assertEqual(r["plugim"], {"meteocat": 0, "rainviewer": 0, "si": False})


class FontsQueFallen(unittest.TestCase):
    """Una font que falla queda apuntada a «errors» i no es converteix en
    «no plou» ni en «sense avisos»."""

    def test_sense_avisos_de_l_aemet_no_es_cap_avis(self):
        fonts = Fonts(avisos=RuntimeError("AEMET 503"), registre=True)
        s = fonts.executa()
        self.assertIsNone(s["avisos"])
        self.assertIn("avisos: AEMET 503", s["errors"])
        # Al registre, «avís de pluja» queda per saber (None), no a 0.
        files = fonts.mocks["registre.apunta_casa"].call_args[0][1]
        self.assertTrue(all(f["avis_pluja"] is None for f in files))
        # Amb la lectura bona i sense avisos, sí que és un 0.
        fonts = Fonts(registre=True)
        fonts.executa()
        files = fonts.mocks["registre.apunta_casa"].call_args[0][1]
        self.assertTrue(all(f["avis_pluja"] == 0.0 and f["pla_inuncat"] == 0.0 for f in files))

    def test_sense_plans_ni_meteocat(self):
        fonts = Fonts(plans=RuntimeError("timeout"), smp=ValueError("XML"), registre=True)
        s = fonts.executa()
        self.assertIsNone(s["plans"])
        self.assertIsNone(s["plans_ocults"])
        self.assertIsNone(s["smp"])
        self.assertIn("plans: timeout", s["errors"])
        self.assertIn("smp: XML", s["errors"])
        files = fonts.mocks["registre.apunta_casa"].call_args[0][1]
        self.assertTrue(all(f["pla_inuncat"] is None and f["avis_meteocat"] is None for f in files))

    def test_sense_meteocat_l_aemet_surt_sencer(self):
        # Sense lectura del Meteocat, l'avís de l'AEMET no queda amagat (ADR 0093).
        s = Fonts(avisos=[avis_aemet()], smp=RuntimeError("SMP")).executa()
        self.assertNotIn("cobert", s["avisos"][0])
        self.assertEqual(s["hores"][0]["avisos"], [{"nivell": "groc", "tipus": ["pluja"]}])

    def test_estacio_de_casa_aturada_fa_servir_les_veines(self):
        s = Fonts(estacio=lambda: estacio(minuts=45)).executa()
        self.assertIn("estació de casa: l'última lectura és de les 09:52", s["errors"])
        ara = s["ara_casa"]
        self.assertEqual(ara["font"], "veines")
        # La temperatura és la d'ICERDA6, la de vora la riera.
        self.assertEqual(ara["temperatura"], 15.5)
        self.assertIsNone(ara["pressio"])
        self.assertIsNone(s["models"])     # sense estació no es comprova res

    def test_estacio_aturada_i_una_veina_mullada_vol_dir_que_plou(self):
        veines = lambda *_a: ([veina("ICERDA6", plou=True), veina("ICERDA28")], [])  # noqa: E731
        s = Fonts(estacio=lambda: estacio(minuts=45), veines=veines).executa()
        self.assertTrue(s["plou_ara"])
        self.assertTrue(s["ara_casa"]["plou"])
        self.assertEqual(s["pluja_ara"]["estat"], "plou")
        self.assertTrue(s["hores"][0]["plou_ara"])

    def test_sense_claus_d_ecowitt_no_es_cap_error(self):
        s = Fonts(ecowitt=False).executa()
        self.assertEqual(s["errors"], [])
        self.assertEqual(s["ara_casa"]["font"], "veines")

    def test_cap_veina_llegida_es_diu(self):
        fonts = Fonts(veines=lambda *_a: ([], ["ICERDA6: 401", "ICERDA18: 401"]))
        s = fonts.executa()
        # «Plou ara» compta amb les veïnes: si no se'n llegeix cap, la pàgina ho diu.
        self.assertIn("estacions veïnes: ICERDA6: 401", s["errors"])
        self.assertIn("No he podido leer la estación vecina ICERDA18: 401", fonts.stderr)
        self.assertEqual(s["veines"], [])

    def test_una_veina_que_falla_nomes_s_apunta(self):
        fonts = Fonts(veines=lambda *_a: ([veina("ICERDA6")], ["ICERDA18: 500"]))
        s = fonts.executa()
        self.assertEqual(s["errors"], [])
        self.assertIn("No he podido leer la estación vecina ICERDA18: 500", fonts.stderr)

    def test_clau_de_weather_underground_a_punt_de_caducar(self):
        fonts = Fonts(wu_caduca=5)
        fonts.executa()
        self.assertIn("caduca d'aquí a 5 dies", fonts.stderr)

    def test_sense_radar_la_pluja_mesurada_mana(self):
        s = Fonts(radar=RuntimeError("radar 404"), estacio=lambda: estacio(plou=True)).executa()
        self.assertIn("radar: radar 404", s["errors"])
        self.assertIsNone(s["radar"])
        self.assertEqual(s["pluja_ara"]["estat"], "plou")
        self.assertEqual(s["pluja_ara"]["font"], "estacions")

    def test_riera_sense_dades_de_sant_cugat(self):
        s = Fonts(riera=None).executa()
        self.assertIn("riera: Sant Cugat (Meteocat) sense dades recents", s["errors"])
        self.assertEqual(s["riera_meteocat_fins"], "2026-10-20T08:00+02:00")
        s = Fonts(riera={"sense_meteocat": True}, riera_fins=OSError("disc")).executa()
        self.assertIn("riera: Sant Cugat (Meteocat) sense dades recents", s["errors"])
        self.assertIsNone(s["riera_meteocat_fins"])
        s = Fonts(riera={"mm_1h": 0.0, "fins": "x", "incomplet": True}).executa()
        self.assertIn("riera: a Sant Cugat (Meteocat) li falten mitges hores de pluja", s["errors"])
        s = Fonts(riera=RuntimeError("csv")).executa()
        self.assertIsNone(s["riera"])
        self.assertIn("riera: csv", s["errors"])

    def test_cada_font_secundaria_que_falla(self):
        casos = {"vent": ("vent", "vent: "), "trens": ("trens", "trens: "), "transit": ("transit", "trànsit: "),
                 "llum": ("llum", "llum: "), "aire": ("aire", "aire: "), "pollen": ("pollen", "pol·len: "),
                 "riera_previsio": ("riera_previsio", "riera, previsió: ")}
        for font, (clau, prefix) in casos.items():
            with self.subTest(font=font):
                s = Fonts(**{font: RuntimeError("caiguda")}).executa()
                self.assertIsNone(s[clau])
                self.assertIn(prefix + "caiguda", s["errors"])
                # La previsió segueix.
                self.assertTrue(s["hores"])

    def test_sol_uv_i_llindars_que_fallen(self):
        s = Fonts(open_meteo=OpenMeteoFals(fallen={"sol", "uv"}), llindars=OSError("json")).executa()
        self.assertIsNone(s["sol"])
        self.assertIn("sol: Open-Meteo sol: 503", s["errors"])
        self.assertIn("índex UV: Open-Meteo uv: 503", s["errors"])
        self.assertIn("llindars: json", s["errors"])
        self.assertNotIn("sortir_llindars", s)
        self.assertNotIn("uv", s["hores"][0])

    def test_final_de_la_pluja_que_falla(self):
        s = Fonts(radar=radar(0), fi_radar=RuntimeError("fi")).executa()
        self.assertIn("final de la pluja: fi", s["errors"])
        self.assertEqual(s["radar"]["arriba"], "2026-10-20T10:30+02:00")

    def test_els_errors_de_l_entorn_hi_van_amb_el_prefix(self):
        s = Fonts(entorn=lambda *_a: {"incendis": [], "errors": ["Pla Alfa: 500"]}).executa()
        self.assertIn("entorn: Pla Alfa: 500", s["errors"])
        self.assertNotIn("errors", s["entorn"])

    def test_metar_que_falla_no_es_cap_error_de_la_pagina(self):
        fonts = Fonts(metars=RuntimeError("504"))
        s = fonts.executa()
        self.assertEqual(s["errors"], [])
        self.assertIn("METAR de Sabadell", fonts.stderr)
        self.assertEqual(s["hores"][0]["nuvols"], 65)    # el dels models

    def test_ecmwf_nuvols_i_vent_15_minuts_que_fallen(self):
        om = OpenMeteoFals(fallen={"ecmwf", "nuvols", "vent15"})
        fonts = Fonts(open_meteo=om)
        s = fonts.executa()
        self.assertEqual(s["errors"], [])
        # Sense ECMWF ni GFS, AROME i ICON-EU; sense els 15 minuts, el de l'hora.
        self.assertEqual(s["hores"][0]["nuvols"], 50)
        self.assertEqual(s["hores"][0]["vent"], 10.0)
        self.assertIn("No he pogut llegir ECMWF", fonts.stderr)
        self.assertIn("No he pogut llegir el vent cada 15 minuts", fonts.stderr)


class PrevisioAnterior(unittest.TestCase):
    """Si Open-Meteo falla, la darrera previsió bona (ADR 0016)."""

    def anterior(self, generat, fins):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        ruta = os.path.join(carpeta.name, "casa.json")
        hora = lambda t: (dt.datetime.fromisoformat(t) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")  # noqa: E731
        hores = [{"hora": hora(t), "fins": t, "temperatura": 15.0, "pluja_mm": 0.0, "probabilitat": 0.05,
                  "plou_ara": False, "segons_estacio": False, "avisos": [], "nuvols": 30}
                 for t in fins]
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"generat": generat, "hores": hores, "aprenentatge": {"pluja": "arxiu"}}, f)
        return ruta

    def test_es_fa_servir_l_anterior_amb_la_pluja_i_el_radar_d_ara(self):
        ruta = self.anterior("2026-10-20T09:15+02:00",
                             ["2026-10-20T10:00", "2026-10-20T11:00", "2026-10-20T12:00", "2026-10-20T13:00"])
        fonts = Fonts(open_meteo=OpenMeteoFals(fallen={"principal"}), radar=radar(40), registre=True)
        s = fonts.executa(ruta)
        self.assertIn("previsió: Open-Meteo principal: 503", s["errors"])
        self.assertIsNone(s["models"])
        self.assertEqual(s["previsio_de"], "2026-10-20T09:15+02:00")
        self.assertEqual(s["aprenentatge"], {"pluja": "arxiu"})
        self.assertEqual([f["fins"] for f in s["hores"]],
                         ["2026-10-20T11:00", "2026-10-20T12:00", "2026-10-20T13:00"])
        # El radar la veu arribar a les 11:10: aquella hora no pot dir «sense pluja».
        self.assertEqual(s["pluja_ara"]["estat"], "arriba")
        self.assertEqual(s["hores"][0]["probabilitat"], 0.05)
        self.assertEqual(s["hores"][1]["probabilitat"], 0.5)
        self.assertTrue(s["hores"][1]["segons_radar"])
        # L'UV d'ara, també a les hores velles.
        self.assertEqual(s["hores"][0]["uv"], 3.0)
        # Al registre no s'apunta una previsió que no és d'aquesta passada.
        fonts.mocks["registre.apunta_casa"].assert_not_called()
        fonts.mocks["registre.apunta_estacio_casa"].assert_called_once()

    def test_sense_anterior_recent_no_hi_ha_taula(self):
        ruta = self.anterior("2026-10-20T03:00+02:00", ["2026-10-20T11:00"])
        s = Fonts(open_meteo=OpenMeteoFals(fallen={"principal"})).executa(ruta)
        self.assertIsNone(s["hores"])
        self.assertNotIn("previsio_de", s)
        self.assertTrue(any(e.startswith("previsió: ") for e in s["errors"]))
        # Sense hores, l'UV no és cap error.
        self.assertFalse(any(e.startswith("índex UV") for e in s["errors"]))
        s = Fonts(open_meteo=OpenMeteoFals(fallen={"principal"})).executa(None)
        self.assertIsNone(s["hores"])


class EstatDeLaPluja(unittest.TestCase):
    """L'estat únic de la pluja d'ara (ADR 0101): mana el mesurat, després el
    radar i després el model, i la taula hi està d'acord."""

    def test_estacio_mana_sobre_el_radar(self):
        s = Fonts(estacio=lambda: estacio(plou=True), radar=radar(15)).executa()
        p = s["pluja_ara"]
        self.assertEqual((p["estat"], p["font"]), ("plou", "estacions"))
        self.assertEqual(p["arriba"], "2026-10-20T10:45+02:00")    # es conserva
        self.assertTrue(p["mesurada"])
        self.assertTrue(s["plou_ara"])
        f = s["hores"][0]
        self.assertTrue(f["plou_ara"])
        self.assertEqual(f["probabilitat"], 1.0)
        self.assertTrue(f["segons_estacio"])
        self.assertFalse(f["segons_radar"])
        # La següent, la del radar.
        self.assertEqual(s["hores"][1]["probabilitat"], 0.9)
        self.assertTrue(s["hores"][1]["segons_radar"])

    def test_persistencia_de_la_pluja_mesurada(self):
        # 1,2 mm l'última hora a casa (sense veïnes que la rebaixin): les
        # primeres hores, amb la persistència real de la pluja.
        s = Fonts(estacio=lambda: estacio(plou=True), wu_lectura=False).executa()
        h = s["hores"]
        self.assertEqual([f["probabilitat"] for f in h[:5]], [1.0, 0.6, 0.45, 0.4, 0.0])
        self.assertEqual([f["pluja_mm"] for f in h[:5]], [1.1, 0.3, 0.1, 0.0, 0.0])
        self.assertEqual([f["segons_estacio"] for f in h[:5]], [True, True, True, True, False])
        self.assertFalse(any(f["segons_radar"] for f in h[:5]))

    def test_radar_a_sobre_sense_estacio_mullada(self):
        s = Fonts(radar=radar(0, prob=0.6)).executa()
        p = s["pluja_ara"]
        self.assertEqual((p["estat"], p["font"]), ("radar_sobre", "radar"))
        self.assertFalse(s["plou_ara"])
        f = s["hores"][0]
        self.assertFalse(f["plou_ara"])
        self.assertGreaterEqual(f["probabilitat"], 0.5)
        self.assertTrue(f["segons_radar"])
        # Casa i les veïnes marquen zero: el mesurat diu que no.
        self.assertFalse(p["mesurada"])

    def test_radar_que_la_veu_venir(self):
        s = Fonts(radar=radar(40)).executa()
        self.assertEqual(s["pluja_ara"]["estat"], "arriba")
        self.assertEqual(s["hores"][0]["probabilitat"], 0.0)
        self.assertEqual(s["hores"][1]["probabilitat"], 0.9)
        self.assertTrue(s["hores"][1]["segons_radar"])
        s = Fonts(radar=radar(40, prob=0.3)).executa()
        self.assertEqual(s["pluja_ara"]["estat"], "possible")
        self.assertEqual(s["pluja_ara"]["possible"], "2026-10-20T11:10+02:00")
        self.assertIsNone(s["pluja_ara"]["arriba"])

    def test_plugim_que_nomes_veuen_els_radars(self):
        s = Fonts(radar=radar(plugim_px=C.PLUGIM_PX)).executa()
        p = s["pluja_ara"]
        self.assertEqual(p["estat"], "no")
        self.assertTrue(p["plugim"])
        self.assertEqual(p["font"], "radar")
        # El pluviòmetre no recull el plugim: no se sap si plou.
        self.assertIsNone(p["mesurada"])

    def test_veina_que_no_compta_no_fa_ploure(self):
        veines = lambda *_a: ([veina("ICERDA48", plou=True, compta=False), veina("ICERDA6")], [])  # noqa: E731
        s = Fonts(veines=veines).executa()
        self.assertFalse(s["plou_ara"])
        self.assertEqual(s["pluja_ara"]["estat"], "no")
        self.assertIsNone(s["pluja_ara"]["font"])
        self.assertFalse(s["hores"][0]["plou_ara"])

    def test_models_que_no_l_encerten(self):
        # 6 mm a l'estació en 3 hores i els models sense res: la pàgina ho diu.
        # (Sense veïnes: amb elles, el mesurat és la mediana del barri.)
        s = Fonts(estacio=lambda: estacio(pluja_1h=2.0, pluja_3h=6.0), wu_lectura=False).executa()
        self.assertTrue(s["models"]["no_encerten"])
        self.assertEqual(s["models"]["mesurada_mm"], 6.0)
        pluja = {"2026-10-20T08:00": 2.0, "2026-10-20T09:00": 1.0}
        s = Fonts(estacio=lambda: estacio(pluja_1h=2.0, pluja_3h=6.0), wu_lectura=False,
                  open_meteo=OpenMeteoFals(pluja=pluja)).executa()
        self.assertEqual(s["models"]["prevista_mm"], 3.0)
        self.assertFalse(s["models"]["no_encerten"])


class Boira(unittest.TestCase):
    def metar(self, brut, minuts=10):
        return [{"t": AHORA - dt.timedelta(minutes=minuts), "nuvols": 100, "capes": True, "brut": brut}]

    def test_boira_a_sabadell_i_casa_saturada(self):
        s = Fonts(metars=self.metar("LELL 200820Z 00000KT 0200 FG VV001"),
                  estacio=lambda: estacio(humitat=99.0)).executa()
        f = s["hores"][0]
        self.assertEqual(f["codi"], 45)
        self.assertTrue(f["boira_observada"])
        # El cel d'ara és el que veu l'aeroport.
        self.assertEqual(f["nuvols"], 100)
        self.assertEqual(s["hores"][1]["codi"], 3)

    def test_sense_casa_saturada_no_hi_ha_boira(self):
        s = Fonts(metars=self.metar("LELL 200820Z 00000KT 0200 FG VV001"),
                  estacio=lambda: estacio(humitat=90.0)).executa()
        self.assertEqual(s["hores"][0]["codi"], 3)
        self.assertNotIn("boira_observada", s["hores"][0])

    def test_error_de_la_boira(self):
        with mock.patch.object(NV, "boira_ara", side_effect=RuntimeError("metar")):
            s = Fonts().executa()
        self.assertIn("boira: metar", s["errors"])


class Registre(unittest.TestCase):
    """Al NAS (R.hay_registro), la passada apunta el que ha mesurat i previst."""

    def test_el_que_s_apunta(self):
        metars = [{"t": AHORA - dt.timedelta(minutes=10), "nuvols": 50, "capes": True, "brut": "LELL"}]
        fonts = Fonts(registre=True, metars=metars)
        s = fonts.executa()
        m = fonts.mocks
        self.assertEqual(s["errors"], [])
        # Amb registre: la temperatura d'ahir i el sol directe corregit.
        self.assertEqual(s["temperatura_mesurada"], {"2026-10-19T10:00": 14.0})
        self.assertTrue(s["ara_casa"]["corregida"])
        m["wunderground.puja"].assert_called_once()
        m["estacions.vigila"].assert_called_once_with(True, ["ICERDA6", "ICERDA18", "ICERDA28"], AHORA)
        m["part_alta.apunta_nit"].assert_called_once()
        m["registre.apunta_estacio_casa"].assert_called_once()
        m["registre.apunta_casa_5min"].assert_called_once()
        self.assertEqual(set(m["registre.apunta_veines_5min"].call_args[0][0]), {"ICERDA6", "ICERDA18", "ICERDA28"})
        ahora, files, ara, riera, veines = m["registre.apunta_casa"].call_args[0]
        self.assertEqual(ahora, AHORA)
        self.assertEqual(len(files), casa.HORAS)
        self.assertEqual(files[0]["fins"], "2026-10-20T11:00")
        self.assertEqual(files[0]["mostrat"]["probabilitat"], 0.0)
        # Les pluges de les estacions van una vegada per línia, no a cada fila.
        self.assertNotIn("pluja_1h_emes", files[0])
        self.assertNotIn("pluja_1h_xv", files[0])
        self.assertIs(ara, s["ara_casa"])
        self.assertEqual(riera, {"pluja_1h": 0.0, "fins": s["riera"]["fins"]})
        self.assertEqual(veines, {"ICERDA6": 0.0, "ICERDA18": 0.0, "ICERDA28": 0.0})
        m["registre.apunta_radar_a_prop"].assert_called_once()
        self.assertEqual(m["registre.apunta_meteocat"].call_count, len(C.ESTACIONES))
        self.assertEqual(m["registre.apunta_veina"].call_count, 3)
        m["wunderground.hores_ahir"].assert_not_called()
        self.assertEqual(set(m["vent_veines.apunta"].call_args[0][0]), {"ICERDA6", "ICERDA18", "ICERDA28"} | set(VV.OFICIALS))
        m["nuvols.apunta"].assert_called_once_with(metars, AHORA)
        m["radar_fonts.apunta"].assert_called_once()

    def test_les_hores_d_ahir_d_una_veina(self):
        fonts = Fonts(registre=True)
        pegats = fonts.pegats
        def amb_ahir():
            res = pegats()
            fonts.mocks["registre.falta_ahir_veina"].return_value = True
            fonts.mocks["wunderground.hores_ahir"].return_value = [{"t": AHORA - dt.timedelta(days=1)}]
            return res
        fonts.pegats = amb_ahir
        fonts.executa()
        m = fonts.mocks
        self.assertEqual(m["wunderground.hores_ahir"].call_count, 3)
        files = m["registre.hores_veina"].call_args_list[0][0][0]
        self.assertEqual(files[0], {"t": AHORA - dt.timedelta(days=1)})

    def test_si_el_registre_falla_la_pagina_surt_igual(self):
        fonts = Fonts(registre=True, temperatures=RuntimeError("csv"), part_alta=RuntimeError("csv"),
                      veines=lambda *_a: ([veina("ICERDA6")], []),
                      metars=[{"t": AHORA, "nuvols": 50, "capes": True, "brut": "LELL"}])
        pegats = fonts.pegats
        def tot_falla():
            res = pegats()
            for nom, m in fonts.mocks.items():
                if nom not in ("riscos.detecta", "sol_estacio.amb_esperades", "registre.falta_ahir_veina",
                               "registre.cincs_casa", "wunderground.hores_ahir"):
                    m.side_effect = OSError(f"{nom}: disc ple")
            return res
        fonts.pegats = tot_falla
        s = fonts.executa()
        self.assertEqual(s["errors"], [])
        self.assertTrue(s["hores"])
        self.assertIsNone(s["temperatura_mesurada"])
        # El sol directe no s'ha pogut mirar: «Ara» queda com estava.
        self.assertNotIn("corregida", s["ara_casa"])
        for text in ("temperatura medida", "Weather Underground", "sol directe", "part alta",
                     "vigilar les estacions", "registre de les nits", "apuntar en el registro",
                     "ecos del radar", "estación vecina ICERDA6", "viento por medias horas", "nubes de Sabadell",
                     "los radares"):
            self.assertIn(text, fonts.stderr, text)


if __name__ == "__main__":
    unittest.main()
