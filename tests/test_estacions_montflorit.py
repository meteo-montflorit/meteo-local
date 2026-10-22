# SPDX-License-Identifier: AGPL-3.0-or-later
"""La web pública (montflorit.py, ADR 0024): els avisos de la riera a les dades
públiques (ADR 0093), els talls de llum sense distància (ADR 0077), les
consultes que fallen i els errors quan una peça deixa d'encaixar."""
import contextlib
import io
import json
import os
import re
import runpy
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import montflorit as M  # noqa: E402


class Errors(unittest.TestCase):
    def test_treu_ha_de_trobar_un_sol_tros(self):
        self.assertEqual(M.treu("a<x>b", re.compile("<x>"), "p"), "ab")
        with self.assertRaisesRegex(ValueError, "p: no trobo el que s'havia de treure"):
            M.treu("ab", re.compile("<x>"), "p")
        with self.assertRaises(ValueError):
            M.treu("<x><x>", re.compile("<x>"), "p")

    def test_menu_sense_nav(self):
        with self.assertRaisesRegex(ValueError, "no trobo el menú de pàgines"):
            M.menu("<body><p>res</p></body>", "index.html", "x.html")

    def test_service_worker_sense_llista_de_peces(self):
        with self.assertRaisesRegex(ValueError, "sw.js: no trobo la llista de peces"):
            M.service_worker("const MAGATZEM = 'meteo-local';\nconst ALTRES = [];")
        t = M.service_worker("const MAGATZEM = 'meteo-local';\nconst PECES = ['a.html'];")
        self.assertIn("'meteo-montflorit'", t)
        self.assertIn("'fiabilitat.html'", t)

    def test_falta_una_peca_del_service_worker(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(M, "PECES", [*M.PECES, "no-hi-es.html"]):
            with self.assertRaisesRegex(ValueError, r"falten peces: \['no-hi-es.html'\]"):
                M.construeix(d)


class Riera(unittest.TestCase):
    def test_nomes_els_avisos_oberts_de_la_riera(self):
        avisos = {"historial": [
            {"clau": "riera:1", "nivell": "perill", "ca": "🔴 <b>Perill</b> de desbordament &amp; més\nDetall",
             "es": "🔴 <b>Peligro</b> de desbordamiento\nDetalle"},
            {"clau": "riera:2", "nivell": "atencio", "ca": "⚠️ «Atenció» a la riera"},
            {"clau": "riera:3", "nivell": "perill", "ca": "Ja passat", "fi": "2026-10-15T10:00"},
            {"clau": "riera:4", "nivell": "info", "ca": "Només informació"},
            {"clau": "smp:5", "nivell": "perill", "ca": "Pluja intensa"},
        ]}
        self.assertEqual(M.perill_riera(avisos), [
            {"nivell": "maxim", "ca": "Perill de desbordament & més", "es": "Peligro de desbordamiento"},
            # Sense text en castellà, el català; les cometes d'obrir es conserven.
            {"nivell": "alt", "ca": "«Atenció» a la riera", "es": "«Atenció» a la riera"},
        ])
        self.assertEqual(M.perill_riera(None), [])
        self.assertEqual(M.perill_riera({"historial": None}), [])

    def test_a_les_dades_publiques(self):
        casa = {"versio": "1", "sortides": [1]}
        self.assertEqual(M.dades_publiques(casa, {"historial": []}), {"versio": "1", "perill_riera": []})
        self.assertNotIn("perill_riera", M.dades_publiques(casa))


class Dades(unittest.TestCase):
    def test_els_talls_de_llum_sense_distancia(self):
        casa = {"llum": {"actualitzat": "x", "talls": [{"carrer": "A", "km": 0.3}, {"carrer": "B", "km": 1.2}]}}
        res = M.dades_publiques(casa)
        self.assertEqual(res["llum"], {"actualitzat": "x", "talls": [{"carrer": "A"}, {"carrer": "B"}]})
        # L'original es manté (casa.json el fa servir el bot amb la distància).
        self.assertEqual(casa["llum"]["talls"][0]["km"], 0.3)
        self.assertEqual(M.dades_publiques({"llum": {"talls": None}})["llum"]["talls"], [])

    def test_les_consultes_que_fallen_no_aturen_la_publicacio(self):
        with mock.patch.object(M, "consultes", side_effect=KeyError("hores")):
            res = M.dades_publiques({"generat": "2026-10-15T10:00+02:00", "errors": ["abans"]})
        self.assertNotIn("consultes", res)
        self.assertEqual(res["errors"], ["abans", "consultes: 'hores'"])


class LiniaOrdres(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.casa = os.path.join(self.dir.name, "casa.json")
        self.sortida = os.path.join(self.dir.name, "montflorit.json")
        with open(self.casa, "w", encoding="utf-8") as f:
            json.dump({"versio": "3", "sortides": [{"mitja": "cotxe"}], "lloc": "Montflorit · Cerdanyola"}, f)

    def executa(self, *args):
        with mock.patch.object(sys, "argv", ["montflorit.py", *args]), contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(os.path.join(ARREL, "montflorit.py"), run_name="__main__")
        with open(self.sortida, encoding="utf-8") as f:
            return f.read()

    def test_dades_sense_i_amb_avisos(self):
        text = self.executa("dades", self.casa, self.sortida)
        self.assertEqual(json.loads(text), {"versio": "3", "lloc": "Montflorit · Cerdanyola"})
        # Compacte i amb els accents tal qual.
        self.assertNotIn(" ", text.replace("Montflorit · Cerdanyola", ""))
        avisos = os.path.join(self.dir.name, "avisos.json")
        with open(avisos, "w", encoding="utf-8") as f:
            json.dump({"historial": [{"clau": "riera:1", "nivell": "perill", "ca": "Perill"}]}, f)
        self.assertEqual(json.loads(self.executa("dades", self.casa, self.sortida, avisos))["perill_riera"],
                         [{"nivell": "maxim", "ca": "Perill", "es": "Perill"}])

    def test_uns_avisos_illegibles_no_aturen_les_dades(self):
        for contingut in ("{trencat", None):
            avisos = os.path.join(self.dir.name, "avisos.json")
            if contingut is None:
                os.remove(avisos)
            else:
                with open(avisos, "w", encoding="utf-8") as f:
                    f.write(contingut)
            with self.subTest(contingut=contingut):
                res = json.loads(self.executa("dades", self.casa, self.sortida, avisos))
                self.assertNotIn("perill_riera", res)
                self.assertNotIn("sortides", res)

    def test_sense_ordre_explica_l_us(self):
        with mock.patch.object(sys, "argv", ["montflorit.py", "dades"]), self.assertRaises(SystemExit) as cm:
            runpy.run_path(os.path.join(ARREL, "montflorit.py"), run_name="__main__")
        self.assertIn("python3 montflorit.py dades", cm.exception.code)


if __name__ == "__main__":
    unittest.main()
