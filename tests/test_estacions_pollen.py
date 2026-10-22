# SPDX-License-Identifier: AGPL-3.0-or-later
"""El polen de Bellaterra: la consulta i la còpia de 3 hores (pollen.py, ADR 0054)."""
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
import pollen as PO  # noqa: E402

DADES = os.path.join(ARREL, "tests", "dades")
ARA = dt.datetime(2026, 10, 15, 12, 0).astimezone()


def xml(idioma):
    with open(os.path.join(DADES, f"pollen-bellaterra-{idioma}.xml"), "rb") as f:
        return f.read()


def get_fals(crides):
    def get(url):
        crides.append(url)
        return xml("ca" if "/ca/" in url else "es")
    return get


class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Pollen(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        p = mock.patch.object(PO, "CACHE", os.path.join(self.dir.name, "pollen.json"))
        p.start()
        self.addCleanup(p.stop)

    def test_get_envia_l_agent_i_el_temps_maxim(self):
        vist = {}

        def urlopen(req, timeout):
            vist.update(url=req.full_url, ua=req.get_header("User-agent"), timeout=timeout)
            return Resposta(b"<xml/>")
        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(PO.get("https://exemple.cat/x"), b"<xml/>")
        self.assertEqual(vist["url"], "https://exemple.cat/x")
        self.assertIn("Temps a Montflorit", vist["ua"])
        self.assertEqual(vist["timeout"], 30)

    def test_demana_els_dos_idiomes_i_ho_desa(self):
        crides = []
        with mock.patch.object(PO, "get", get_fals(crides)):
            res = PO.calcula(ARA)
        self.assertEqual(crides, [PO.API.format("ca"), PO.API.format("es")])
        self.assertTrue(res["pollens"])
        with open(PO.CACHE, encoding="utf-8") as f:
            desat = json.load(f)
        self.assertEqual(desat["hora"], ARA.isoformat(timespec="minutes"))
        self.assertEqual(desat["pollen"], res)
        self.assertFalse(os.path.exists(PO.CACHE + ".tmp"))

    def test_la_copia_recent_estalvia_la_consulta(self):
        with open(PO.CACHE, "w", encoding="utf-8") as f:
            json.dump({"hora": (ARA - dt.timedelta(hours=2, minutes=59)).isoformat(), "pollen": {"desat": 1}}, f)
        with mock.patch.object(PO, "get", side_effect=AssertionError("no s'havia de consultar")):
            self.assertEqual(PO.calcula(ARA), {"desat": 1})

    def test_la_copia_vella_o_espatllada_es_torna_a_demanar(self):
        for contingut in (json.dumps({"hora": (ARA - dt.timedelta(hours=3)).isoformat(), "pollen": {"desat": 1}}),
                          "{no és json", json.dumps({"pollen": {}})):
            with self.subTest(contingut=contingut):
                with open(PO.CACHE, "w", encoding="utf-8") as f:
                    f.write(contingut)
                crides = []
                with mock.patch.object(PO, "get", get_fals(crides)):
                    res = PO.calcula(ARA)
                self.assertEqual(len(crides), 2)
                self.assertIn("pollens", res)

    def test_sense_carpeta_d_estat_no_desa_res(self):
        with mock.patch.object(PO, "CACHE", os.path.join(self.dir.name, "no-hi-es", "pollen.json")), \
                mock.patch.object(PO, "get", get_fals([])):
            self.assertIn("espores", PO.calcula(ARA))
        self.assertEqual(os.listdir(self.dir.name), [])

    def test_la_font_que_falla_no_es_amaga(self):
        # Si el PIA no respon, l'error puja: no es torna una setmana sense polen.
        with mock.patch.object(PO, "get", side_effect=OSError("caigut")):
            with self.assertRaises(OSError):
                PO.calcula(ARA)

    def test_des_de_la_linia_d_ordres_escriu_el_json(self):
        def urlopen(req, timeout):
            return Resposta(xml("ca" if "/ca/" in req.full_url else "es"))
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"POLLEN_DIR": self.dir.name}), \
                mock.patch("urllib.request.urlopen", urlopen), contextlib.redirect_stdout(out):
            runpy.run_path(os.path.join(ARREL, "pollen.py"), run_name="__main__")
        res = json.loads(out.getvalue())
        self.assertIn("pollens", res)
        self.assertTrue(os.path.exists(os.path.join(self.dir.name, "pollen.json")))


if __name__ == "__main__":
    unittest.main()
