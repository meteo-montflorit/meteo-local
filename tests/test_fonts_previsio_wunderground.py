# SPDX-License-Identifier: AGPL-3.0-or-later
"""Weather Underground (wunderground.py, ADR 0059 i 0060): les claus del
fitxer, els reintents de la pujada, els errors de la API de lectura i les
ordres, sense xarxa."""
import contextlib
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import ecowitt as E  # noqa: E402
import wunderground as W  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=2))
CASA = {"hora": "2026-10-09T22:40+02:00", "temperatura": 12.5}


def error_http(codi):
    return urllib.error.HTTPError("https://x", codi, "error", {}, None)


def resposta(text):
    return io.BytesIO(text.encode("utf-8"))


class Claus(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        os.makedirs(os.path.join(self.home.name, ".config", "meteo-local"))
        self.env = os.path.join(self.home.name, ".config", "meteo-local", "wunderground.env")

    def test_del_fitxer_quan_no_son_a_l_entorn(self):
        with open(self.env, "w", encoding="utf-8") as f:
            f.write("WU_STATION_ID=IPROVA1\nWU_STATION_KEY=a=b\nWU_API_KEY=lectura\nALTRA=x\n")
        with mock.patch.dict(os.environ, {"HOME": self.home.name}, clear=True):
            self.assertEqual(W.claves(), {"WU_STATION_ID": "IPROVA1", "WU_STATION_KEY": "a=b"})
            self.assertEqual(W.clau_lectura(), "lectura")
            self.assertTrue(W.disponible())
            self.assertTrue(W.lectura_disponible())

    def test_l_entorn_mana_sobre_el_fitxer(self):
        with open(self.env, "w", encoding="utf-8") as f:
            f.write("WU_STATION_ID=FITXER\nWU_STATION_KEY=fitxer\n")
        with mock.patch.dict(os.environ, {"HOME": self.home.name, "WU_STATION_ID": "ENTORN"}, clear=True):
            self.assertEqual(W.claves(), {"WU_STATION_ID": "ENTORN", "WU_STATION_KEY": "fitxer"})

    def test_mig_fitxer_no_val(self):
        with open(self.env, "w", encoding="utf-8") as f:
            f.write("WU_STATION_ID=IPROVA1\n")
        with mock.patch.dict(os.environ, {"HOME": self.home.name}, clear=True):
            self.assertIsNone(W.claves())


class Puja(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"WU_STATION_ID": "IPROVA1", "WU_STATION_KEY": "clau"})
        p.start()
        self.addCleanup(p.stop)
        s = mock.patch.object(W.time, "sleep")
        self.sleep = s.start()
        self.addCleanup(s.stop)

    def test_success(self):
        with mock.patch.object(W.urllib.request, "urlopen", return_value=resposta("success\n")) as u:
            self.assertEqual(W.puja(CASA), "success")
        req = u.call_args[0][0]
        self.assertIn("ID=IPROVA1", req.full_url)
        self.assertEqual(req.get_header("User-agent"), W.PROGRAMA)
        self.sleep.assert_not_called()

    def test_un_unauthorized_passatger_es_torna_a_provar(self):
        with mock.patch.object(W.urllib.request, "urlopen",
                               side_effect=[error_http(401), error_http(401), resposta("success")]) as u:
            self.assertEqual(W.puja(CASA), "success")
        self.assertEqual(u.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)
        self.sleep.assert_called_with(W.PAUSA_S)

    def test_tres_unauthorized_fallen(self):
        with mock.patch.object(W.urllib.request, "urlopen", side_effect=[error_http(401)] * 3) as u:
            with self.assertRaises(urllib.error.HTTPError):
                W.puja(CASA)
        self.assertEqual(u.call_count, W.INTENTS)

    def test_un_altre_error_no_es_torna_a_provar(self):
        with mock.patch.object(W.urllib.request, "urlopen", side_effect=error_http(500)) as u:
            with self.assertRaises(urllib.error.HTTPError):
                W.puja(CASA)
        self.assertEqual(u.call_count, 1)
        self.sleep.assert_not_called()

    def test_una_resposta_que_no_es_success_es_error(self):
        with mock.patch.object(W.urllib.request, "urlopen", return_value=resposta("INVALIDPASSWORDID" + "x" * 200)):
            with self.assertRaisesRegex(RuntimeError, "Weather Underground: INVALIDPASSWORDID") as cm:
                W.puja(CASA)
        self.assertLessEqual(len(str(cm.exception)), len("Weather Underground: ") + 80)

    def test_sense_hora_es_la_d_ara(self):
        ara = dt.datetime(2026, 10, 9, 22, 0, tzinfo=TZ)
        self.assertEqual(W.parametres({}, ara)["dateutc"], "2026-10-09 20:00:00")
        self.assertIn("dateutc", W.parametres({}))


class Consulta(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"WU_API_KEY": "lectura"})
        p.start()
        self.addCleanup(p.stop)

    def test_get_sense_lector_llegeix_la_url(self):
        with mock.patch.object(W.urllib.request, "urlopen", return_value=resposta('{"observations": [1]}')) as u:
            self.assertEqual(W._consulta("observations/all/1day", {"stationId": "ICERDA6"}), [1])
        url = u.call_args[0][0].full_url
        self.assertTrue(url.startswith(W.URL_API + "/observations/all/1day?stationId=ICERDA6"))
        self.assertIn("units=m", url)
        self.assertIn("apiKey=lectura", url)

    def test_204_es_llista_buida(self):
        def lector(url):
            raise error_http(204)
        self.assertEqual(W._consulta("x", {}, lector), [])

    def test_clau_caducada_es_diu(self):
        for codi in (401, 403):
            def lector(url, codi=codi):
                raise error_http(codi)
            with self.assertRaisesRegex(RuntimeError, f"no val \\(HTTP {codi}\\): caduca el {W.C.WU_CLAU_CADUCA}"):
                W._consulta("x", {}, lector)

    def test_altres_errors_http_passen(self):
        def lector(url):
            raise error_http(500)
        with self.assertRaises(urllib.error.HTTPError):
            W._consulta("x", {}, lector)

    def test_sense_observacions(self):
        self.assertEqual(W._consulta("x", {}, lambda u: "  \n"), [])
        self.assertEqual(W._consulta("x", {}, lambda u: '{"observations": null}'), [])

    def test_hores_d_ahir(self):
        urls = []
        o = {"obsTimeUtc": "2026-10-09T21:55:00Z", "metric": {"precipTotal": 1.2, "pressureMin": 1010.0}}

        def lector(url):
            urls.append(url)
            return json.dumps({"observations": [o]})
        r = W.hores_ahir("ICERDA6", dt.datetime(2026, 10, 10, 0, 5, tzinfo=TZ), lector)
        self.assertIn("history/all?stationId=ICERDA6&date=20261009", urls[0])
        self.assertEqual(r[0]["pluja_avui"], 1.2)
        self.assertEqual(r[0]["pressio"], 1010.0)       # amb una sola pressió, aquesta
        self.assertIsNone(r[0]["temperatura"])


class Observacio(unittest.TestCase):
    def test_nomes_si_plou_i_compta(self):
        self.assertIsNone(W.observacio(None))
        self.assertIsNone(W.observacio({"plou": True, "compta": False}))
        self.assertIsNone(W.observacio({"plou": False, "compta": True}))

    def test_sense_lectures_la_mitja_hora_es_la_dels_15_minuts(self):
        v = {"estacio": "ICERDA6", "plou": True, "compta": True, "pluja_avui": 3.0, "pluja_15min": 0.4,
             "intensitat": 1.2, "hora": "2026-10-10T06:20+02:00", "files": []}
        o = W.observacio(v)
        self.assertEqual(o["mm_ultima_media_hora"], 0.4)
        self.assertEqual((o["estacion"], o["mm_hoy"], o["hasta"]), ("ICERDA6", 3.0, v["hora"]))
        self.assertFalse(W.plou_a_les_veines(None))
        self.assertTrue(W.plou_a_les_veines([v]))


class Ordres(unittest.TestCase):
    """python3 wunderground.py puja|mostra|veines."""

    def executa(self, *args):
        sortida = io.StringIO()
        with mock.patch.object(sys, "argv", ["wunderground.py", *args]), contextlib.redirect_stdout(sortida):
            runpy.run_path(os.path.join(ARREL, "wunderground.py"), run_name="__main__")
        return sortida.getvalue()

    def test_sense_ordre_l_ajuda(self):
        self.assertIn("python3 wunderground.py puja", self.executa())

    def test_sense_claus_d_ecowitt(self):
        with mock.patch.object(E, "disponible", return_value=False):
            with self.assertRaises(SystemExit) as cm:
                self.executa("mostra")
        self.assertEqual(str(cm.exception), "sense claus d'Ecowitt")

    def test_mostra_i_puja_sense_claus_de_weather_underground(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        with mock.patch.object(E, "disponible", return_value=True), \
                mock.patch.object(E, "resum_ara", return_value=CASA), \
                mock.patch.dict(os.environ, {"HOME": home.name}, clear=True), \
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("sense xarxa")):
            s = self.executa("mostra")
            self.assertIn("'tempf': 54.5", s)
            self.assertNotIn("no es puja", s)
            self.assertIn("sense claus de Weather Underground: no es puja", self.executa("puja"))

    def test_veines(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        with mock.patch.dict(os.environ, {"HOME": home.name}, clear=True):
            with self.assertRaises(SystemExit) as cm:
                self.executa("veines")
            self.assertIn("sense clau de lectura", str(cm.exception))
        ara = dt.datetime.now(dt.timezone.utc)
        obs = [{"obsTimeUtc": (ara - dt.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ"), "humidityAvg": 90,
                "metric": {"tempAvg": 12.0, "precipTotal": 0.0, "pressureMax": 1015.0, "windspeedAvg": 3}}
               for m in (10, 5)]

        def urlopen(req, timeout):
            if "ICERDA18" in req.full_url:
                raise error_http(500)
            return resposta(json.dumps({"observations": obs}))
        with mock.patch.dict(os.environ, {"WU_API_KEY": "lectura"}), mock.patch("urllib.request.urlopen", urlopen):
            s = self.executa("veines")
        self.assertIn("ICERDA6 a 1 km a l'est", s)
        self.assertIn("no plou", s)
        self.assertIn("(no compta)", s)            # ICERDA48
        self.assertIn("fallo: ICERDA18", s)
        self.assertIn("La clau de lectura caduca d'aquí a", s)


if __name__ == "__main__":
    unittest.main()
