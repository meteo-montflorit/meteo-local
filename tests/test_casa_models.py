# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proves de les consultes de casa.py a Open-Meteo (models, UV i sol), de
l'estació de casa, de la comprovació dels models, de la previsió anterior
(ADR 0016) i de l'ordre de línia, sense xarxa. Fan servir l'arnès de
test_casa_recoger (OpenMeteoFals i Fonts)."""
import contextlib
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import casa  # noqa: E402
import config as C  # noqa: E402
import ecowitt as E  # noqa: E402
import prevision as P  # noqa: E402
from test_casa_recoger import AHORA, Fonts, OpenMeteoFals, estacio, lectures_casa  # noqa: E402


class Models(unittest.TestCase):
    def consulta(self, om, errors=None):
        with mock.patch.object(P, "get_reintenta", om):
            return casa.modelos(AHORA, errors)

    def test_junta_ecmwf_els_nuvols_i_el_vent_de_15_minuts(self):
        om = OpenMeteoFals()
        h, e = self.consulta(om, [])
        self.assertEqual(sorted(om.consultes), sorted(["principal", "ensemble", "ecmwf", "nuvols", "nuvols", "vent15"]))
        self.assertEqual(len(h["time"]), 72)
        self.assertEqual(h["time"][0], "2026-10-20T00:00")
        # ECMWF, a part, per a la probabilitat (ADR 0086).
        self.assertEqual(h[f"precipitation_{C.MODEL_ECMWF}"], [0.0] * 72)
        # Els núvols de cada model apart (ADR 0088), totals i baixos.
        for m in ("ecmwf_ifs", "gfs_seamless"):
            self.assertEqual(h[f"cloud_cover_{m}"][0], 80)
            self.assertEqual(h[f"cloud_cover_low_{m}"][0], 10)
        self.assertEqual(h["vent_15min"]["2026-10-20T10:15"], 12.0)
        self.assertEqual(len([k for k in e if k.startswith("precipitation")]), 10)

    def test_series_amb_altres_hores_no_es_barregen(self):
        # Si ECMWF o un model de núvols tornen unes altres hores, no s'hi posen:
        # la sèrie quedaria desplaçada.
        om = OpenMeteoFals()
        original = om.__call__

        def desplacat(url, *a, **kw):
            res = json.loads(original(url, *a, **kw))
            if om.consultes[-1] in ("ecmwf", "nuvols"):
                res["hourly"]["time"] = res["hourly"]["time"][1:] + ["2026-10-23T00:00"]
            return json.dumps(res)
        with mock.patch.object(P, "get_reintenta", desplacat):
            h, _ = casa.modelos(AHORA, [])
        self.assertNotIn(f"precipitation_{C.MODEL_ECMWF}", h)
        self.assertNotIn("cloud_cover_gfs_seamless", h)

    def test_si_falla_el_principal_falla_tot(self):
        with self.assertRaises(RuntimeError):
            self.consulta(OpenMeteoFals(fallen={"principal"}), [])

    def test_uv_i_sol(self):
        om = OpenMeteoFals(uv=5.5)
        with mock.patch.object(P, "get", om):
            uv = casa.indice_uv(AHORA)
            sol = casa.sol(AHORA)
        self.assertEqual(uv["2026-10-20T13:00"], 5.5)
        self.assertEqual(len(uv), 72)
        # Avui i demà, amb el màxim de l'UV de cada dia.
        self.assertEqual([d["dia"] for d in sol], ["2026-10-20", "2026-10-21"])
        self.assertEqual(sol[1]["uv_max"], 3.5)
        self.assertEqual(sol[0]["posta"], "2026-10-20T18:55")

    def test_uv_sense_valors(self):
        om = OpenMeteoFals()
        original = om.__call__

        def amb_forats(url):
            res = json.loads(original(url))
            res["hourly"]["uv_index"] = [None] * len(res["hourly"]["time"])
            return json.dumps(res)
        with mock.patch.object(P, "get", amb_forats):
            self.assertEqual(casa.indice_uv(AHORA), {})


class EstacioCasa(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(P, "AHORA", AHORA)
        p.start()
        self.addCleanup(p.stop)

    def test_sense_claus_no_hi_ha_estacio(self):
        with mock.patch.object(E, "disponible", return_value=False), \
                mock.patch.object(E, "resum_ara", side_effect=AssertionError("no s'ha de llegir")):
            self.assertIsNone(casa.estacio_casa())

    def test_lectura_recent_i_lectura_congelada(self):
        with mock.patch.object(E, "disponible", return_value=True), \
                mock.patch.object(E, "resum_ara", return_value=estacio(minuts=30)):
            self.assertEqual(casa.estacio_casa()["temperatura"], 15.0)
        # Un feed congelat no pot dir que plou (o que no) durant hores.
        with mock.patch.object(E, "disponible", return_value=True), \
                mock.patch.object(E, "resum_ara", return_value=estacio(minuts=31)):
            with self.assertRaisesRegex(RuntimeError, "10:06"):
                casa.estacio_casa()


class ComprovacioModels(unittest.TestCase):
    def h(self, pluja):
        temps = [(AHORA.replace(hour=0, minute=0) + dt.timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M")
                 for k in range(24)]
        return {"time": temps, **{f"precipitation_{m}": [pluja.get(t, 0.0) for t in temps]
                                  for m in C.MODELOS_FINOS}}

    def test_sense_lectures_que_cobreixin_les_hores(self):
        self.assertIsNone(casa.comprobacion_modelos(AHORA, self.h({}), []))
        # Les lectures comencen a les 8: no cobreixen les 3 hores (de 7 a 10).
        curtes = lectures_casa(AHORA, 3.0, desde_h=2.5)
        self.assertIsNone(casa.comprobacion_modelos(AHORA, self.h({}), curtes))

    def test_mesurada_amb_l_estacio_i_amb_el_consens(self):
        files = lectures_casa(AHORA, 6.0)
        r = casa.comprobacion_modelos(AHORA, self.h({}), files)
        # De les 7 a les 10: només la darrera hora (de 9:37 a 10:00) ha plogut.
        self.assertEqual(r["mesurada_mm"], 2.0)
        self.assertEqual(r["prevista_mm"], 0.0)
        self.assertFalse(r["no_encerten"])       # menys de 3 mm
        # Amb el consens del barri (la mediana de «Ara»), el mesurat és aquest.
        r = casa.comprobacion_modelos(AHORA, self.h({}), files, consens_3h=8.0)
        self.assertEqual(r["mesurada_mm"], 8.0)
        self.assertTrue(r["no_encerten"])
        # Només compten les hores de dins (de 7 a 10, l'hora que acaba a les 8, 9 i 10).
        r = casa.comprobacion_modelos(AHORA, self.h({"2026-10-20T07:00": 9.0, "2026-10-20T10:00": 2.4}),
                                      files, consens_3h=8.0)
        self.assertEqual(r["prevista_mm"], 2.4)
        self.assertFalse(r["no_encerten"])       # 8 no passa de 3 × 2,4 + 1


class AuxiliarsDeLaPrevisio(unittest.TestCase):
    def test_temperatura_del_model_amb_forats(self):
        h = {"time": ["2026-10-20T10:00", "2026-10-20T11:00"], "temperature_2m_meteofrance_seamless": [14.0, None]}
        self.assertIsNone(casa.temperatura_model_ara(h, AHORA))
        h["temperature_2m_meteofrance_seamless"] = [14.0, 16.0]
        self.assertAlmostEqual(casa.temperatura_model_ara(h, AHORA), 14.0 + 2 * 37 / 60)

    def test_consens_sense_lectura(self):
        self.assertIsNone(casa.consens(None, None, []))

    def test_ensemble_sense_membres(self):
        self.assertEqual(casa.prob_ensemble({"time": ["x"]}), {})


class PrevisioAnteriorCasosLimit(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(P, "AHORA", AHORA)
        p.start()
        self.addCleanup(p.stop)

    def fila(self, fins):
        ini = (dt.datetime.fromisoformat(fins) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        return {"hora": ini, "fins": fins, "probabilitat": 0.1, "segons_estacio": False, "nuvols": 20}

    def test_des_d_una_adreca_i_amb_el_cel_d_ara(self):
        antes = {"generat": "2026-10-20T10:07+02:00", "hores": [self.fila("2026-10-20T11:00"),
                                                                 self.fila("2026-10-20T12:00")]}
        demanades = []

        def get(url):
            demanades.append(url)
            return json.dumps(antes)
        with mock.patch.object(P, "get", get):
            r = casa.previsio_anterior("https://exemple.org/casa.json", [], None, None, nuvols_ara=90)
        self.assertEqual(demanades, ["https://exemple.org/casa.json"])
        # El cel que es veu ara manda a la primera hora, no a les altres.
        self.assertEqual([f["nuvols"] for f in r["hores"]], [90, 20])
        self.assertIsNone(r["aprenentatge"])
        # La previsió anterior no es modifica.
        self.assertEqual(antes["hores"][0]["nuvols"], 20)

    def test_adreca_que_falla(self):
        with mock.patch.object(P, "get", side_effect=OSError("404")):
            self.assertIsNone(casa.previsio_anterior("https://exemple.org/casa.json", []))

    def test_sense_hores_sense_data_o_totes_passades(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "casa.json")
            for antes in ({"generat": "2026-10-20T10:07+02:00", "hores": []},
                          {"hores": [self.fila("2026-10-20T11:00")]},
                          {"generat": "2026-10-20T09:07+02:00", "hores": [self.fila("2026-10-20T10:00")]}):
                with self.subTest(antes=antes):
                    with open(ruta, "w", encoding="utf-8") as f:
                        json.dump(antes, f)
                    self.assertIsNone(casa.previsio_anterior(ruta, []))


class RecogerExtra(unittest.TestCase):
    def test_vent_de_les_veines_que_falla(self):
        fonts = Fonts(vent_veines=RuntimeError("model"))
        s = fonts.executa()
        # És una estimació per comparar: no és cap error de la pàgina.
        self.assertIsNone(s["vent_veines"])
        self.assertEqual(s["errors"], [])
        self.assertIn("viento con las vecinas: model", fonts.stderr)


class OrdreDeLinia(unittest.TestCase):
    def test_escriu_el_json_i_el_resum(self):
        """python3 casa.py --json fitxer: la passada sencera, desada en JSON."""
        fonts = Fonts()
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "casa.json")
            sortida = io.StringIO()
            with contextlib.ExitStack() as pila:
                for modul, nom, valor in fonts.pegats():
                    pila.enter_context(mock.patch.object(modul, nom, valor))
                pila.enter_context(mock.patch.object(sys, "argv", ["casa.py", "--json", ruta]))
                pila.enter_context(contextlib.redirect_stdout(sortida))
                pila.enter_context(contextlib.redirect_stderr(io.StringIO()))
                runpy.run_path(os.path.join(ARREL, "casa.py"), run_name="__main__")
            with open(ruta, encoding="utf-8") as f:
                desat = json.load(f)
        self.assertEqual(desat["generat"], "2026-10-20T10:37+02:00")
        self.assertEqual(desat["errors"], [])
        self.assertEqual(len(desat["hores"]), 35)
        text = sortida.getvalue()
        self.assertIn("Generado 2026-10-20T10:37+02:00", text)
        self.assertIn("10:00 16.0 °C 0.0 mm 0.0", text)


if __name__ == "__main__":
    unittest.main()
