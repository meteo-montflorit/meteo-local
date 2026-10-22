# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de la imagen de la gráfica (grafica_imatge.py, ADR 0098), sin Chromium."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import grafica_imatge as G  # noqa: E402


class Credits(unittest.TestCase):
    def test_que_es_de_quan_i_que_mana_l_oficial(self):
        ca, avis = G.credits({"generat": "2026-10-17T07:21+02:00"}, "ca")
        self.assertEqual(ca, "Temps a Montflorit (Cerdanyola del Vallès) · previsió de dissabte 17 d’octubre, 07:21"
                             " · meteo-montflorit.github.io")
        self.assertIn("mana el seu", avis)
        self.assertIn("previsión del lunes 2 de noviembre, 07:00", G.credits({"generat": "2026-11-02T07:00+01:00"}, "es")[0])
        self.assertIn("de novembre", G.credits({"generat": "2026-11-02T07:00+01:00"}, "ca")[0])

    def test_la_pagina_porta_els_credits_i_les_icones(self):
        p = G.pagina({"generat": "2026-10-17T07:21+02:00", "hores": []}, "avui", "ca")
        self.assertIn("meteo-montflorit.github.io", p)
        self.assertIn('<symbol id="i-cloud"', p)
        # Sense el botó de la càmera, que a la imatge no fa res.
        self.assertIn("fig._botoImatge = false", p)


def captura(ruta, mida=(1064, 1800), contingut=None):
    """Una captura com la de Chromium: blanca, amb la gràfica a dalt si n'hi ha."""
    im = Image.new("RGB", mida, "white")
    if contingut:
        im.paste((20, 60, 200), contingut)
    im.save(ruta)


class Imatges(unittest.TestCase):
    def test_retalla_el_blanc_de_sota_amb_el_marge(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "g.png")
            captura(ruta, contingut=(40, 40, 1000, 600))
            self.assertTrue(G.retalla(ruta))
            with Image.open(ruta) as im:
                self.assertEqual(im.size, (1064, 600 + G.MARGE * G.ESCALA))
            # Una captura en blanc (la pàgina no s'ha dibuixat) no és una imatge.
            captura(ruta)
            self.assertFalse(G.retalla(ruta))

    def test_les_quatre_imatges_i_les_que_fallen(self):
        dades = {"generat": "2026-10-17T07:21+02:00", "hores": []}

        def chromium(ordre, **kw):
            png = next(a for a in ordre if a.startswith("--screenshot=")).split("=", 1)[1]
            if "avui-es" in png:
                raise subprocess.TimeoutExpired(ordre, G.TEMPS_S)
            # La de demà en català surt en blanc: no s'ha de publicar.
            captura(png, contingut=None if "dema-ca" in png else (40, 40, 1000, 600))

        with tempfile.TemporaryDirectory() as tmp:
            # Una imatge d'una passada anterior no pot quedar-se si ara falla.
            captura(os.path.join(tmp, G.nom("dema", "ca")), contingut=(0, 0, 10, 10))
            with mock.patch.object(G.subprocess, "run", side_effect=chromium):
                fetes = G.fes(dades, tmp, navegador="/usr/bin/chromium")
            self.assertEqual(fetes, [G.nom("avui", "ca"), G.nom("dema", "es")])
            self.assertEqual(sorted(os.listdir(tmp)), sorted(fetes))

    def test_sense_navegador_no_es_fa_cap_imatge(self):
        with mock.patch.object(G, "chromium", return_value=None), mock.patch.object(G.subprocess, "run") as run:
            self.assertEqual(G.fes({}, "/no/cal"), [])
        run.assert_not_called()
        with mock.patch.dict(os.environ, {"CHROMIUM": "el-meu-chromium"}), \
                mock.patch.object(G.shutil, "which", side_effect=lambda o: "/opt/" + o if o == "el-meu-chromium" else None):
            self.assertEqual(G.chromium(), "/opt/el-meu-chromium")
        with mock.patch.object(G.shutil, "which", return_value=None):
            self.assertIsNone(G.chromium())


if __name__ == "__main__":
    unittest.main()
