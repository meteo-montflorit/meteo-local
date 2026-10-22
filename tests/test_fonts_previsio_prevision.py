# SPDX-License-Identifier: AGPL-3.0-or-later
"""La recollida de prevision.py: la memòria de pàgines (ADR 0020), les
estacions de Meteocat amb les seves dues fonts, el radar quan falla, els
avisos del feed de Meteoalarm i el resum per consola, sense xarxa."""
import ast
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import numpy as np  # noqa: E402

import config as C  # noqa: E402
import ecowitt  # noqa: E402
import moviment_registre as MR  # noqa: E402
import nowcast as N  # noqa: E402
import prevision as P  # noqa: E402
import smp as SMP  # noqa: E402

ARA = dt.datetime(2026, 10, 10, 12, 0).astimezone()
UTC = dt.timezone.utc


class Calibracio(unittest.TestCase):
    def test_sense_fitxer_o_trencat_es_buida(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(P, "DIR", d):
            self.assertEqual(P.leer_calibracion(), {})
            os.makedirs(os.path.join(d, "calibracio"))
            with open(os.path.join(d, "calibracio", "calibracio.json"), "w") as f:
                f.write("{trencat")
            self.assertEqual(P.leer_calibracion(), {})
            with open(os.path.join(d, "calibracio", "calibracio.json"), "w") as f:
                json.dump({"persistencia": 0.7}, f)
            self.assertEqual(P.leer_calibracion(), {"persistencia": 0.7})


class GetRecent(unittest.TestCase):
    """Cada pàgina es llegeix una sola vegada per passada (ADR 0020)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.crides = []

    def get(self, url):
        self.crides.append(url)
        return f"pàgina {len(self.crides)}"

    def test_fora_del_nas_sempre_de_la_xarxa(self):
        with mock.patch.object(P, "CACHE_WEB", os.path.join(self.dir.name, "no", "cache")), \
                mock.patch.object(P, "get", self.get):
            self.assertEqual(P.get_recent("https://a"), "pàgina 1")
            self.assertEqual(P.get_recent("https://a"), "pàgina 2")
        self.assertFalse(os.path.exists(os.path.join(self.dir.name, "no")))

    def test_es_reaprofita_mentre_es_recent(self):
        cache = os.path.join(self.dir.name, "cache-web")
        with mock.patch.object(P, "CACHE_WEB", cache), mock.patch.object(P, "get", self.get):
            self.assertEqual(P.get_recent("https://a"), "pàgina 1")
            self.assertEqual(P.get_recent("https://a"), "pàgina 1")      # de la memòria
            self.assertEqual(P.get_recent("https://b"), "pàgina 2")      # una altra adreça
            self.assertEqual(len(os.listdir(cache)), 2)
            self.assertFalse([f for f in os.listdir(cache) if f.endswith(".tmp")])
            # Passat el temps, es torna a baixar.
            for f in os.listdir(cache):
                vell = time.time() - 200
                os.utime(os.path.join(cache, f), (vell, vell))
            self.assertEqual(P.get_recent("https://a"), "pàgina 3")
            self.assertEqual(P.get_recent("https://a", segons=0), "pàgina 4")
        self.assertEqual(self.crides, ["https://a", "https://b", "https://a", "https://a"])


TAULA = """<table class="tblperiode"><tr><th>Període<br>TU</th><th>PPT<br>mm</th><th>VVM (10 m)<br>km/h</th></tr>
<tr><td>10:00 - 10:30</td><td>0.2</td><td>7.2</td></tr>
<tr><td>10:30 - 11:00</td><td>(s/d)</td><td>(s/d)</td></tr>
<tr><td>11:00 - 11:30</td><td>1.4</td><td>9.0</td></tr></table>"""


class Estacions(unittest.TestCase):
    def test_columna_que_no_hi_es(self):
        self.assertIsNone(P._columna({"PPTmm": "0.1"}, "VVX"))
        self.assertIsNone(P._columna({"PPTmm": "(s/d)"}, "PPT"))
        self.assertEqual(P._columna({"PPTmm": "0.1"}, "PPT"), 0.1)

    def test_vent_sense_ratxa(self):
        v = P.vent_meteocat("XF", lector=lambda url: TAULA)
        self.assertEqual(v["estacio"], "Sabadell")
        self.assertEqual((v["mitja"], v["ratxa"]), (9.0, None))
        self.assertIsNone(P.vent_meteocat("XF", lector=lambda url: "<html>sense taula</html>"))

    def test_observacions_de_la_web(self):
        dia = dt.date(2026, 10, 10)
        files = [(dt.datetime(2026, 10, 10, 10, 0, tzinfo=UTC), 0.2), (dt.datetime(2026, 10, 10, 11, 0, tzinfo=UTC), 1.4)]
        with mock.patch.object(P, "taula_meteocat", return_value=files) as t:
            r = P.observaciones_web("XF", "Sabadell")
        t.assert_called_once_with("XF")
        self.assertEqual(r["font"], "meteo.cat")
        self.assertEqual((r["mm_hoy"], r["mm_ultima_media_hora"]), (1.6, 1.4))
        # Fins al final de l'última mitja hora, en hora local.
        self.assertEqual(dt.datetime.fromisoformat(r["hasta"]), dt.datetime(2026, 10, 10, 11, 30, tzinfo=UTC))
        with mock.patch.object(P, "taula_meteocat", return_value=[]):
            self.assertIsNone(P.observaciones_web("XF", "Sabadell"))
        # Amb la taula de veritat: les mitges hores sense dada no compten.
        with mock.patch.object(P, "get_recent", return_value=TAULA):
            self.assertEqual([mm for _, mm in P.taula_meteocat("XF", dia)], [0.2, 1.4])

    def test_observacions_del_portal(self):
        urls = []
        files = [{"data_lectura": "2026-10-10T08:00:00.000", "valor_lectura": "0.4"},
                 {"data_lectura": "2026-10-10T08:30:00.000", "valor_lectura": "1.1"}]

        def get(url):
            urls.append(url)
            return json.dumps(files)
        with mock.patch.object(P, "AHORA", ARA), mock.patch.object(P, "get", get):
            r = P.observaciones_portal("XV", "Sant Cugat")
        self.assertIn("codi_estacio%3D%27XV%27", urls[0])
        self.assertIn("2026-10-10T00%3A00%3A00", urls[0])
        self.assertEqual(r["font"], "portal de dades obertes")
        self.assertEqual((r["mm_hoy"], r["mm_ultima_media_hora"]), (1.5, 1.1))
        self.assertEqual(dt.datetime.fromisoformat(r["hasta"]), dt.datetime(2026, 10, 10, 9, 0, tzinfo=UTC))
        with mock.patch.object(P, "AHORA", ARA), mock.patch.object(P, "get", return_value="[]"):
            self.assertIsNone(P.observaciones_portal("XV", "Sant Cugat"))


class Observacions(unittest.TestCase):
    def test_casa_nomes_si_plou_i_una_font_de_reserva(self):
        def web(codi, nom):
            if codi == "XF":
                raise OSError("meteo.cat caigut")
            return None

        def portal(codi, nom):
            if codi == "XV":
                raise ValueError("JSON")
            return {"estacion": nom, "font": "portal"}
        casa = {"estacion": "Casa", "mm_ultima_media_hora": 0.3}
        with mock.patch.object(ecowitt, "disponible", return_value=True), \
                mock.patch.object(ecowitt, "resum_ara", return_value={}), \
                mock.patch.object(ecowitt, "observacio", return_value=casa) as obs, \
                mock.patch.object(P, "observaciones_web", web), mock.patch.object(P, "observaciones_portal", portal):
            r = P.observaciones()
        obs.assert_called_once_with({}, C.ESTACIO_CASA)
        # XF: la web falla i val el portal; XV: les dues fallen i no hi surt (no és «0 mm»).
        self.assertEqual(r, [casa, {"estacion": "Sabadell (Parc Agrari)", "font": "portal"}])

    def test_si_ecowitt_falla_continuen_les_altres(self):
        web = lambda codi, nom: {"estacion": nom, "font": "meteo.cat"}  # noqa: E731
        with mock.patch.object(ecowitt, "disponible", return_value=True), \
                mock.patch.object(ecowitt, "resum_ara", side_effect=OSError("Ecowitt")), \
                mock.patch.object(P, "observaciones_web", web), \
                mock.patch.object(P, "observaciones_portal", side_effect=AssertionError("no cal")):
            r = P.observaciones()
        self.assertEqual([o["estacion"] for o in r], list(C.ESTACIONES.values()))
        with mock.patch.object(ecowitt, "disponible", return_value=False), \
                mock.patch.object(ecowitt, "resum_ara", side_effect=AssertionError("no cal")), \
                mock.patch.object(P, "observaciones_web", web):
            self.assertEqual(len(P.observaciones()), len(C.ESTACIONES))


class Radar(unittest.TestCase):
    def setUp(self):
        for nom in ("apunta", "apunta_creixement"):
            p = mock.patch.object(MR, nom, return_value=0)
            p.start()
            self.addCleanup(p.stop)
        lat, lon = C.CASA
        self.tx, self.ty = N.geometria(lat, lon)
        self.fila, self.col = (int(v) for v in N.pixel(lat, lon, self.tx, self.ty))
        self.kmpx = N.km_px(lat)
        self.hora = dt.datetime(2026, 10, 10, 11, 24).astimezone()

    def r(self, **extra):
        return {"tx": self.tx, "ty": self.ty, "km_px": self.kmpx, "errors": [], **extra}

    def test_sense_imatges_es_error_no_sense_pluja(self):
        with mock.patch.object(N, "carrega", return_value=self.r(errors=["RainViewer: 503", "Meteocat: 403"])):
            with self.assertRaisesRegex(RuntimeError, "RainViewer: 503; Meteocat: 403"):
                P.radar()
        with mock.patch.object(N, "carrega", return_value=self.r()):
            with self.assertRaisesRegex(RuntimeError, "sense imatges de radar"):
                P.radar()

    def test_rainviewer_sol_amb_una_hora_de_imatges(self):
        abans = np.zeros((N.MIDA, N.MIDA))
        ara = np.zeros((N.MIDA, N.MIDA))
        n = round(10 / self.kmpx)
        abans[self.fila - n:self.fila + n, self.col - n:self.col + n] = 2.0     # una hora abans, pluja a casa
        ara[self.fila - 2:self.fila + 2, self.col + 3 * n:self.col + 3 * n + 4] = 2.0   # ara, poca i lluny
        hores = [self.hora + dt.timedelta(minutes=10 * i) for i in range(7)]
        rv = {"hores": hores, "mm_h": [abans] + [np.zeros_like(ara)] * 5 + [ara]}
        with mock.patch.object(N, "carrega", return_value=self.r(rainviewer=rv)), \
                mock.patch.object(N, "resum", return_value=None):
            res = P.radar()
        self.assertEqual(res["imatge"], "rainviewer")
        self.assertEqual(list(res["a_prop"]), ["rainviewer"])        # Meteocat sense imatge: no hi és
        self.assertGreater(res["km2_50km_antes"], res["km2_50km_ahora"])
        self.assertGreater(res["km2_50km_ahora"], 0)
        self.assertAlmostEqual(res["km_lluvia"], 30, delta=2)

    def test_el_registre_del_moviment_no_atura_el_radar(self):
        mc = np.zeros((N.MIDA, N.MIDA))
        mc[self.fila, self.col] = 1.0
        r = self.r(meteocat={"hora": self.hora, "mm_h": mc})
        err = io.StringIO()
        with mock.patch.object(N, "carrega", return_value=r), mock.patch.object(N, "resum", return_value=None), \
                mock.patch.object(N, "font_preferida", return_value="meteocat"), \
                mock.patch.object(MR, "apunta", side_effect=OSError("disc ple")), \
                contextlib.redirect_stderr(err):
            res = P.radar()
        self.assertLess(res["km_lluvia"], 1)                  # el píxel de casa
        self.assertIsNone(res["km2_50km_antes"])
        self.assertIn("moviment_registre: disc ple", err.getvalue())
        [(km, _, mm)] = res["a_prop"]["meteocat"]["px"]
        self.assertEqual((km, mm), (res["km_lluvia"], 1.0))


def entrada(zona, evento, onset, expires, ficha=None):
    enllac = f'<link href="https://feeds.meteoalarm.org/api/v1/warnings/{ficha}"/>' if ficha else ""
    return (f"<entry>{enllac}<cap:areaDesc>{zona}</cap:areaDesc><cap:event>{evento}</cap:event>"
            f"<cap:onset>{onset}</cap:onset><cap:expires>{expires}</cap:expires></entry>")


class Avisos(unittest.TestCase):
    def test_tipus(self):
        self.assertEqual(P.tipus_aemet("Moderate thunderstorm warning"), "tempestes")
        self.assertEqual(P.tipus_aemet("Severe rain-flood warning"), "inundacions")
        self.assertEqual(P.tipus_aemet("Moderate high-temperature warning"), "calor")
        self.assertEqual(P.tipus_aemet("Moderate wind warning"), "vent")
        self.assertEqual(P.tipus_aemet("Moderate tsunami warning"), "altres")

    def test_del_feed_nomes_la_zona_sense_repetits_i_amb_el_text(self):
        z, prop = C.ZONA_AVISOS, C.ZONA_CERCANA
        feed = "<feed>" + "".join([
            entrada(z, "Moderate rain warning", "2026-10-10T14:00:00+02:00", "2026-10-10T23:59:00+02:00", "a"),
            entrada(z, "Moderate rain warning", "2026-10-10T14:00:00+02:00", "2026-10-10T23:59:00+02:00", "a"),
            entrada(prop, "Severe coastal event warning", "2026-10-10T10:00:00+02:00",
                    "2026-10-10T20:00:00+02:00", "b"),
            entrada(z, "Extreme wind warning", "2026-10-09T08:00:00+02:00", "2026-10-09T20:00:00+02:00", "c"),
            entrada(z, "Moderate snow warning", "2026-10-10T08:00:00+02:00", "2026-10-11T08:00:00+02:00", "d"),
            entrada(z, "Unknown fog warning", "2026-10-10T06:00:00+02:00", "2026-10-10T18:00:00+02:00"),
            entrada("Pirineu de Lleida", "Severe snow warning", "2026-10-10T00:00:00+02:00",
                    "2026-10-11T00:00:00+02:00", "e")]) + "</feed>"
        fitxes = []

        def descripcio(url):
            fitxes.append(url[-1])
            if url.endswith("d"):
                raise OSError("fitxa caiguda")
            return "Pueden ir acompañadas de granizo."
        with mock.patch.object(P, "AHORA", ARA), mock.patch.object(P, "get", return_value=feed), \
                mock.patch.object(P, "descripcion_aviso", descripcio):
            r = P.avisos()
        self.assertEqual([(a["tipo"], a["nivel"]) for a in r],
                         [("vent", "vermell"), ("boira", "Unknown fog warning"), ("neu", "groc"),
                          ("costaners", "taronja"), ("pluja", "groc")])
        # El text només dels de la zona que no han acabat; si la fitxa falla, l'avís hi és igual.
        self.assertEqual(sorted(fitxes), ["a", "a", "d"])
        pluja = r[-1]
        self.assertEqual(pluja["descripcio"], "Pueden ir acompañadas de granizo.")
        self.assertNotIn("descripcio", r[2])
        self.assertNotIn("descripcio", r[3])
        self.assertEqual(dt.datetime.fromisoformat(pluja["inicio"]),
                         dt.datetime(2026, 10, 10, 12, 0, tzinfo=UTC))


class Horari(unittest.TestCase):
    def test_en_mode_avis_diu_a_quina_distancia_es_la_pluja(self):
        h = P.horario([["00:00", "23:45"]], 15, ["pluja al radar"], km_pluja=8.4)
        self.assertEqual(h["cada_min"], C.MODO_AVISO_INTERVALO_MIN)
        self.assertEqual(h["desfase_min"], C.MODO_AVISO_DESFASE_MIN)
        self.assertEqual(h["km_pluja"], 8.4)
        self.assertEqual(h["normal_min"], 15)
        # Fora del mode avís, la distància no hi va encara que n'hi hagi.
        h = P.horario([["00:00", "23:45"]], 15, [], km_pluja=8.4)
        self.assertNotIn("km_pluja", h)
        self.assertEqual((h["cada_min"], h["desfase_min"], h["mode_avis"]), (15, 0, []))


def executa_resum(**fonts):
    """El bloc «__main__» de prevision.py amb les fonts substituïdes: la
    sortida i el codi de sortida."""
    with open(P.__file__, encoding="utf-8") as f:
        arbre = ast.parse(f.read())
    bloc = [n for n in arbre.body if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)]
    codi = compile(ast.Module(body=bloc, type_ignores=[]), P.__file__, "exec")
    espai = {**vars(P), **fonts, "__name__": "__main__"}
    sortida = io.StringIO()
    with contextlib.redirect_stdout(sortida), mock.patch.object(P, "AHORA", ARA):
        espai["AHORA"] = ARA
        try:
            exec(codi, espai)
            codi_sortida = None
        except SystemExit as ex:
            codi_sortida = ex.code
    return sortida.getvalue(), codi_sortida


def falla(missatge):
    def f():
        raise RuntimeError(missatge)
    return f


class Resum(unittest.TestCase):
    def test_tot_falla(self):
        with mock.patch.object(SMP, "llegeix", side_effect=OSError("smp caigut")):
            s, codi = executa_resum(avisos=falla("feed"), planes_proteccion_civil=falla("plans"),
                                    observaciones=falla("estacions"), radar=falla("radar"))
        self.assertEqual(codi, 1)
        for text in ("fallo: avisos: feed", "fallo: plans: plans", "fallo: estacions: estacions",
                     "fallo: radar: radar", "fallo: smp: smp caigut", "Mode avís: no"):
            self.assertIn(text, s)

    def test_amb_dades(self):
        avisos = [{"zona": C.ZONA_AVISOS, "tipo": "pluja", "nivel": "groc",
                   "inicio": "2026-10-10T11:00:00+02:00", "fin": "2026-10-10T18:00:00+02:00"}]
        plans = [{"pla": "INUNCAT", "fase": "alerta"}]
        obs = [{"estacion": "Sabadell", "mm_ultima_media_hora": 0.4, "mm_hoy": 3.1, "font": "meteo.cat"}]
        radar = {"imatge": "meteocat", "hora": "2026-10-10T11:54:00+02:00", "km_lluvia": 3.2,
                 "nowcast": {"cap_a": "NE", "velocitat_kmh": 25}}
        with mock.patch.object(SMP, "llegeix", return_value={"avisos": []}):
            s, codi = executa_resum(avisos=lambda: avisos, planes_proteccion_civil=lambda: plans,
                                    observaciones=lambda: obs, radar=lambda: radar)
        self.assertEqual(codi, 0)
        self.assertIn("Recollit 2026-10-10T12:00", s)
        self.assertIn(f"Avís groc per pluja a {C.ZONA_AVISOS}: 11:00-18:00", s)
        self.assertIn("Pla INUNCAT en fase d'alerta", s)
        self.assertIn("Sabadell: 0.4 mm en mitja hora, 3.1 mm avui (meteo.cat)", s)
        self.assertIn("Radar (meteocat, 11:54): pluja a 3.2 km de casa; moviment cap NE a 25 km/h", s)
        self.assertIn("Mode avís: avís de l'AEMET, pla de Protecció Civil, pluja a les estacions, pluja al radar", s)
        self.assertNotIn("fallo", s)

    def test_una_font_que_falla_no_fa_fallar_el_resum(self):
        radar = {"imatge": "rainviewer", "hora": "2026-10-10T11:50:00+02:00", "km_lluvia": None, "nowcast": None}
        with mock.patch.object(SMP, "llegeix", return_value=None):
            s, codi = executa_resum(avisos=falla("feed"), planes_proteccion_civil=lambda: [],
                                    observaciones=lambda: [], radar=lambda: radar)
        self.assertEqual(codi, 0)
        self.assertIn("fallo: avisos: feed", s)
        self.assertIn("moviment cap None a None km/h", s)


if __name__ == "__main__":
    unittest.main()
