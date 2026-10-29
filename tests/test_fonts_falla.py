# SPDX-License-Identifier: AGPL-3.0-or-later
"""Les fonts que fallen, des de quan i què se'n fa si dura (fonts_falla.py, ADR 0031)."""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fonts_falla as FF  # noqa: E402

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 25, 11, 0, tzinfo=UTC)


class FontsFalla(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.dir.name, "fonts-falla.json")
        self.enviats = []

    def tearDown(self):
        self.dir.cleanup()

    def passa(self, errors, hores):
        return FF.vigila(errors, T0 + dt.timedelta(hours=hores), envia=self.enviats.append, ruta=self.ruta)

    def test_des_de_quan_i_un_avis_si_dura_i_es_de_la_xarxa(self):
        e = ["avisos: HTTP Error 500: Internal Server Error"]
        self.assertEqual(self.passa(e, 0), {"avisos": "2026-10-25T11:00Z"})
        self.assertEqual(self.passa(e, 2.9), {"avisos": "2026-10-25T11:00Z"})        # des de la primera
        self.assertEqual(self.enviats, [])
        self.passa(e, 3)
        self.assertEqual(len(self.enviats), 1)
        self.assertIn("els avisos de l'AEMET (Meteoalarm)", self.enviats[0])
        self.assertIn("des del 25/10 a les 12:00", self.enviats[0])                  # hora de Madrid
        self.passa(e, 5)
        self.assertEqual(len(self.enviats), 1)                                       # una sola vegada
        self.assertEqual(self.passa([], 6), {})
        self.assertEqual(self.enviats[-1], "Temps a Montflorit: torna a funcionar una font, els avisos de l'AEMET (Meteoalarm).")

    def test_si_sembla_del_programa_ho_fa_el_reparador(self):
        e = ["trens: tipus de camp desconegut: 4"]
        self.passa(e, 0)
        self.passa(e, 3)
        self.assertEqual(self.enviats, [])
        self.assertTrue(FF._llegeix(self.ruta)["trens"]["reparar"])

    def test_les_que_ja_tenen_el_seu_avis_no(self):
        e = ["smp: x", "estació de casa: 500", "estacions veïnes: 500"]
        self.passa(e, 0)
        self.assertEqual(set(self.passa(e, 4)), {"smp", "estació de casa", "estacions veïnes"})
        self.assertEqual(self.enviats, [])

    def test_la_font_de_cada_error(self):
        self.assertEqual(FF.font("entorn: incendis: HTTP Error 503"), "entorn: incendis")
        self.assertEqual(FF.font("final de la pluja: x"), "final de la pluja")
        self.assertTrue(FF.es_de_xarxa("<urlopen error _ssl.c:975: The handshake operation timed out>"))
        self.assertFalse(FF.es_de_xarxa("tipus de camp desconegut: 4"))

    def test_una_font_que_respon_sense_dades_no_va_al_reparador(self):
        # 29-10-2026: la XV de Sant Cugat aturada no és un canvi de format.
        e = ["riera: Sant Cugat (Meteocat) sense dades recents"]
        self.passa(e, 0)
        self.passa(e, 4)
        self.assertEqual(len(self.enviats), 1)
        self.assertIn("estacions particulars", self.enviats[0])
        self.assertIn("Sembla de la font", self.enviats[0])


if __name__ == "__main__":
    unittest.main()
