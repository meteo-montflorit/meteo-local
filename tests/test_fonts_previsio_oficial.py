# SPDX-License-Identifier: AGPL-3.0-or-later
"""Les previsions oficials per a Cerdanyola (previsio_oficial.py, ADR 0110):
claus, consultes, respostes estranyes, la reserva dels avisos, el registre i
l'estat, sense xarxa."""
import contextlib
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import time
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import previsio_oficial as O  # noqa: E402
import prevision as P  # noqa: E402

ARA = dt.datetime(2026, 10, 20, 9, 4, tzinfo=P.ZONA)
AEMET = [{"elaborado": "2026-10-20T06:13:22", "prediccion": {"dia": [{
    "fecha": "2026-10-20T00:00:00",
    "temperatura": [{"value": "14", "periodo": "07"}, {"value": "", "periodo": "08"}],
    "precipitacion": [{"value": "-", "periodo": "07"}],
    "probPrecipitacion": [{"value": "30", "periodo": "02"}, {"value": None, "periodo": "0208"},
                          {"value": "10", "periodo": "0814"}]}]}}]


class Clau(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        os.makedirs(os.path.join(self.home.name, ".config", "meteo-local"))

    def test_l_entorn_primer(self):
        with mock.patch.dict(os.environ, {"HOME": self.home.name, "AEMET_API_KEY": "entorn"}, clear=True):
            self.assertEqual(O.clau("aemet", "AEMET_API_KEY"), "entorn")

    def test_del_fitxer_i_sense_fitxer(self):
        with open(os.path.join(self.home.name, ".config", "meteo-local", "aemet.env"), "w") as f:
            f.write("ALTRA=x\nAEMET_API_KEY=\nAEMET_API_KEY=eyJ=a\n")
        with mock.patch.dict(os.environ, {"HOME": self.home.name}, clear=True):
            self.assertEqual(O.clau("aemet", "AEMET_API_KEY"), "eyJ=a")
            self.assertIsNone(O.clau("meteocat", "METEOCAT_API_KEY"))     # no hi ha meteocat.env
            self.assertIsNone(O.clau("aemet", "NO_HI_ES"))


class Baixa(unittest.TestCase):
    def test_capcaleres_i_codificacio(self):
        vist = {}

        def urlopen(req, timeout):
            vist["req"] = req
            return io.BytesIO("Cerdanyola del Vallès".encode("iso-8859-15"))
        with mock.patch.object(O.urllib.request, "urlopen", urlopen):
            self.assertEqual(O.baixa("https://x", {"api_key": "k"}, "iso-8859-15"), "Cerdanyola del Vallès")
        self.assertEqual(vist["req"].get_header("Api_key"), "k")
        self.assertEqual(vist["req"].get_header("User-agent"), "meteo-local")


class Llegeix(unittest.TestCase):
    def test_meteocat_salta_valors_dolents_i_sense_temperatures_falla(self):
        d = {"dies": [{"variables": {"temp": [{"valor": "n/d", "data": "2026-10-20T00:00Z"},
                                              {"valor": "12", "data": None},
                                              {"valor": "13", "data": "2026-10-20T01:00Z"}],
                                     "precipitacio": None}}, {}]}
        r = O.llegeix_meteocat(json.dumps(d))
        self.assertEqual(r, {"t": {"2026-10-20T03:00": 13.0}, "mm": {}})
        with self.assertRaisesRegex(ValueError, "Meteocat no torna temperatures"):
            O.llegeix_meteocat(json.dumps({"dies": []}))

    def test_aemet_salta_valors_dolents(self):
        r = O.llegeix_aemet(json.dumps(AEMET))
        self.assertEqual(r["t"], {"2026-10-20T07:00": 14.0})
        self.assertEqual(r["mm"], {})                      # «-» no és 0
        self.assertEqual(r["p6"], {"2026-10-20T08:00": ["2026-10-20T14:00", 10.0]})

    def test_aemet_sense_temperatures_i_sense_elaborat(self):
        with self.assertRaisesRegex(ValueError, "AEMET no torna temperatures"):
            O.llegeix_aemet(json.dumps({"prediccion": {"dia": []}}))
        d = {"prediccion": {"dia": [{"fecha": "2026-10-20", "temperatura": [{"value": "9", "periodo": "24"}]}]}}
        r = O.llegeix_aemet(json.dumps(d))
        self.assertIsNone(r["elaborat"])
        self.assertEqual(r["t"], {"2026-10-21T00:00": 9.0})       # la 24 és la mitjanit de l'endemà


class Consulta(unittest.TestCase):
    def test_meteocat_amb_la_clau_a_la_capcalera(self):
        crides = []

        def get(url, capcaleres):
            crides.append((url, capcaleres))
            return json.dumps({"dies": [{"variables": {"temp": {"valors": [{"valor": "10", "data": "2026-10-20T08:00Z"}]}}}]})
        self.assertEqual(O.consulta_meteocat("k", get)["t"], {"2026-10-20T10:00": 10.0})
        self.assertEqual(crides, [(O.URL_METEOCAT, {"X-Api-Key": "k"})])

    def test_aemet_en_dues_passes(self):
        crides = []

        def get(url, capcaleres, codificacio="utf-8"):
            crides.append((url, capcaleres, codificacio))
            if url == O.URL_AEMET:
                return json.dumps({"estado": 200, "datos": "https://opendata.aemet.es/dades/1"})
            return json.dumps(AEMET)
        self.assertEqual(O.consulta_aemet("k", get)["elaborat"], "2026-10-20T06:13")
        self.assertEqual(crides, [(O.URL_AEMET, {"api_key": "k"}, "utf-8"),
                                  ("https://opendata.aemet.es/dades/1", None, "iso-8859-15")])

    def test_aemet_sense_dades_es_error(self):
        get = lambda url, capcaleres: json.dumps({"estado": 401, "descripcion": "API key invalido"})  # noqa: E731
        with self.assertRaisesRegex(ValueError, "AEMET: API key invalido"):
            O.consulta_aemet("k", get)
        with self.assertRaisesRegex(ValueError, "AEMET: sense dades"):
            O.consulta_aemet("k", lambda url, capcaleres: "{}")


class Reserva(unittest.TestCase):
    def test_la_reserva_dels_avisos_va_primer(self):
        with tempfile.TemporaryDirectory() as d:
            cache = os.path.join(d, "smp-api.json")
            self.assertFalse(O.reserva_en_us(ARA, cache))         # sense fitxer
            open(cache, "w").close()
            ara = dt.datetime.now(P.ZONA)
            self.assertTrue(O.reserva_en_us(ara, cache))
            vell = time.time() - O.RESERVA_H * 3600 - 60
            os.utime(cache, (vell, vell))
            self.assertFalse(O.reserva_en_us(ara, cache))


class RegistreIEstat(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        for nom, valor in (("REGISTRE", self.dir.name), ("ESTAT", os.path.join(self.dir.name, "estat.json"))):
            p = mock.patch.object(O, nom, valor)
            p.start()
            self.addCleanup(p.stop)

    def escriu(self, mes, linies):
        with open(os.path.join(self.dir.name, f"previsio-oficial-{mes}.jsonl"), "w", encoding="utf-8") as f:
            f.write("\n".join(linies) + "\n")

    def test_linies_trencades_i_repetides_sense_anterior(self):
        self.escriu("2026-10", ['{"font":"aemet","llegit":"2026-10-20T09:00+02:00","repetit":true}',
                                '{trencada',
                                '{"font":"aemet","llegit":"2026-10-20T08:00+02:00","t":{"x":1}}',
                                '{"font":"aemet","llegit":"2026-10-20T10:00+02:00","repetit":true}'])
        r = O.registre()
        # La repetida del principi no té res a repetir; l'ordre és el de l'hora.
        self.assertEqual([x[0].hour for x in r["aemet"]], [8, 10])
        self.assertEqual(r["aemet"][0][1], {"t": {"x": 1}, "mm": {}, "p6": {}})

    def test_ordenat_entre_mesos(self):
        self.escriu("2026-11", ['{"font":"meteocat","llegit":"2026-11-01T00:30+01:00","t":{"a":2}}'])
        self.escriu("2026-10", ['{"font":"meteocat","llegit":"2026-10-31T21:00+01:00","t":{"a":1}}'])
        self.assertEqual([d["t"]["a"] for _, d in O.registre()["meteocat"]], [1, 2])

    def test_estat(self):
        crides = {"n": 0}

        def aemet():
            crides["n"] += 1
            if crides["n"] == 3:
                raise TimeoutError()
            return {"elaborat": None, "t": {"h": crides["n"]}, "mm": {}, "p6": {}}
        consultes = {"meteocat": lambda: {"t": {"h": 1}, "mm": {}}, "aemet": aemet}
        O.apunta(ARA, consultes, lambda _: False)
        O.apunta(ARA + dt.timedelta(hours=1), consultes, lambda _: False)
        fet = O.apunta(ARA + dt.timedelta(hours=2), consultes, lambda _: False)
        self.assertEqual(fet, {"aemet": "error"})
        sortida = io.StringIO()
        with contextlib.redirect_stdout(sortida):
            O.estat()
        meteocat, aemet_ = sortida.getvalue().splitlines()
        self.assertEqual(meteocat, "meteocat: 1 consultes, 1 amb previsió nova; la primera, 20-10 09:04; "
                                   "l'última, 20-10 09:04; aquest mes, 1 de 260")
        # Un error sense text diu el tipus.
        self.assertEqual(aemet_, "aemet: 2 consultes, 2 amb previsió nova; la primera, 20-10 09:04; "
                                 "l'última, 20-10 10:04; error: 2026-10-20T11:04+02:00 TimeoutError")

    def test_estat_buit(self):
        sortida = io.StringIO()
        with contextlib.redirect_stdout(sortida):
            O.estat()
        self.assertEqual(sortida.getvalue().splitlines(), ["meteocat: 0 consultes, 0 amb previsió nova",
                                                           "aemet: 0 consultes, 0 amb previsió nova"])

    def test_estat_trencat_es_buit(self):
        with open(O.ESTAT, "w") as f:
            f.write("no és json")
        self.assertEqual(O._llegeix_estat(), {})


class Ordres(unittest.TestCase):
    def executa(self, *args, env=None):
        sortida = io.StringIO()
        with mock.patch.object(sys, "argv", ["previsio_oficial.py", *args]), \
                mock.patch.dict(os.environ, env or {}), contextlib.redirect_stdout(sortida):
            runpy.run_path(os.path.join(ARREL, "previsio_oficial.py"), run_name="__main__")
        return sortida.getvalue()

    def test_ordre_desconeguda(self):
        for args in ((), ("res",), ("apunta", "estat")):
            with self.assertRaises(SystemExit) as cm:
                self.executa(*args)
            self.assertIn("python3 previsio_oficial.py apunta | estat", str(cm.exception))

    def test_apunta_i_estat_sense_xarxa(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"REGISTRE_DIR": d, "CACHE_WEB": d, "HOME": d, "METEOCAT_API_KEY": "", "AEMET_API_KEY": ""}
            with mock.patch("urllib.request.urlopen", side_effect=OSError("sense xarxa")):
                s = self.executa("apunta", env=env)
            self.assertEqual(json.loads(s), {"meteocat": "error", "aemet": "error"})
            s = self.executa("estat", env=env)
            self.assertIn("aquest mes, 1 de 260", s)
            self.assertIn("error: ", s)
            self.assertIn("sense xarxa", s)


if __name__ == "__main__":
    unittest.main()
