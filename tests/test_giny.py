# SPDX-License-Identifier: AGPL-3.0-or-later
"""El giny d'Android (giny.js, ADR 0131): diu el mateix que la targeta d'«Ara»,
en català i en castellà, i porta el que l'app necessita per pintar-lo."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ARREL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADES = os.path.join(ARREL, "tests", "dades", "montflorit-giny.json")
NODE = shutil.which("node")
# Les dades són del 24-11-2026 a les 9:00 (hora de Madrid).
ARA = "2026-11-24T09:05:00+01:00"


def giny(ara=ARA, dades=None):
    with tempfile.TemporaryDirectory() as tmp:
        entrada = DADES
        if dades is not None:
            entrada = os.path.join(tmp, "m.json")
            with open(entrada, "w", encoding="utf-8") as f:
                json.dump(dades, f)
        sortida = os.path.join(tmp, "giny.json")
        subprocess.run([NODE, os.path.join(ARREL, "giny.js"), entrada, sortida], check=True,
                       env={**os.environ, "TZ": "UTC", "GINY_ARA": ara})
        with open(sortida, encoding="utf-8") as f:
            return json.load(f)


@unittest.skipUnless(NODE, "cal Node")
class Giny(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = giny()

    def test_la_targeta_en_catala(self):
        ca = self.g["ca"]
        self.assertEqual(ca["titol"], "Temps a Montflorit (Cerdanyola)")
        self.assertEqual(ca["frase"], "Aquest matí, fred i després fresc, i cobert; aquesta tarda, fresc i cobert.")
        self.assertEqual(ca["temperatura"], "7 °C")
        self.assertEqual(ca["dia"], {"quan": "Avui:", "max": "màx. 15°", "min": "mín. 5°",
                                     "compara": "semblant a ahir"})
        self.assertEqual(ca["lluna"], {"text": "Lluna plena: 15:54", "angle": 180})
        self.assertEqual(ca["cel"], {"fons": "cobert", "dibuix": "overcast", "moment": "dia"})

    def test_la_linia_de_la_pluja_porta_el_compte_a_part(self):
        linia = self.g["ca"]["linia"]
        self.assertTrue(self.g["ca"]["linia_pluja"])
        self.assertEqual(linia[0], "Possible pluja ")
        self.assertEqual(linia[1], {"compte": "2026-11-24T19:00+01:00", "hores": True})
        self.assertEqual(linia[2], ", cap a les 19 h (22 %).")

    def test_la_gota_diu_la_pluja_en_curt(self):
        # La primera hora de pluja prevista i la probabilitat, com la línia de sota la frase.
        self.assertEqual(self.g["ca"]["gota"], "19\u00a0h · 22\u00a0%")
        self.assertEqual(self.g["es"]["gota"], "19\u00a0h · 22\u00a0%")

    def test_si_plou_la_gota_ho_diu(self):
        with open(DADES, encoding="utf-8") as f:
            d = json.load(f)
        d["ara_casa"]["plou"] = True
        g = giny(dades=d)
        self.assertEqual(g["ca"]["gota"], "Plou")
        self.assertEqual(g["es"]["gota"], "Llueve")

    def test_sense_pluja_no_hi_ha_gota(self):
        with open(DADES, encoding="utf-8") as f:
            d = json.load(f)
        for h in d["hores"]:
            h["probabilitat"] = 0
            h["pluja_mm"] = 0
        self.assertIsNone(giny(dades=d)["ca"]["gota"])

    def test_en_castella(self):
        es = self.g["es"]
        self.assertEqual(es["titol"], "Tiempo en Montflorit (Cerdanyola)")
        self.assertTrue(es["frase"].startswith("Esta mañana, frío"))
        self.assertEqual(es["dia"]["quan"], "Hoy:")
        self.assertEqual(es["linia"][0], "Posible lluvia ")
        self.assertEqual(es["lluna"]["text"], "Luna llena: 15:54")

    def test_els_textos_del_compte_enrere(self):
        for idioma in ("ca", "es"):
            textos = self.g[idioma]["textos"]
            self.assertEqual(set(textos), {"menys_hora", "una_hora", "hores", "ara", "un_minut", "minuts", "h_min", "h"})
            self.assertIn("{0}", textos["hores"])
            self.assertIn("{1}", textos["h_min"])
            self.assertNotIn("undefined", json.dumps(textos))
        self.assertEqual(self.g["es"]["textos"]["hores"], "dentro de unas {0} horas")

    def test_de_nit_el_fons_i_el_dibuix_de_nit(self):
        g = giny("2026-11-24T21:30:00+01:00")
        self.assertEqual(g["ca"]["cel"]["moment"], "nit")
        self.assertTrue(g["ca"]["cel"]["fons"].startswith("nit"))

    def test_sense_dades_d_ara_no_hi_ha_targeta(self):
        with open(DADES, encoding="utf-8") as f:
            d = json.load(f)
        d.pop("ara_casa")
        g = giny(dades=d)
        self.assertIsNone(g["ca"])
        self.assertIsNone(g["es"])

    def test_cada_cel_i_dibuix_te_el_seu_recurs_a_l_app(self):
        # GinyProvider busca «giny_fons_<cel>» i «giny_cel_<dibuix>» pel nom.
        res = os.path.join(ARREL, "android", "giny", "main", "res", "drawable-nodpi")
        with open(os.path.join(ARREL, "web", "casa.js"), encoding="utf-8") as f:
            casa = f.read()
        bloc = casa.split("const FONS_NIT", 1)[1].split("function celPortada", 1)[0]
        cels = set(re.findall(r":\s*'([a-z]+)'", bloc.split("const DIBUIX_CEL", 1)[0])) | {"sere", "poc", "nuvol", "cobert", "boira", "pluja", "tempesta"}
        dibuixos = set(re.findall(r"'([a-z-]+)'", bloc.split("const DIBUIX_CEL", 1)[1])) | {"sunrise", "sunset"}
        for cel in cels:
            self.assertTrue(os.path.exists(os.path.join(res, f"giny_fons_{cel}.webp")), cel)
        for dibuix in dibuixos - {"dia", "nit"}:
            self.assertTrue(os.path.exists(os.path.join(res, f"giny_cel_{dibuix.replace('-', '_')}.webp")), dibuix)


if __name__ == "__main__":
    unittest.main()
