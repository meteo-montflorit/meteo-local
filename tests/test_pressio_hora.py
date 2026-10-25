# SPDX-License-Identifier: AGPL-3.0-or-later
"""La presión de cada hora de la gráfica: la de AROME llevada a la estación de
casa con la diferencia del momento (casa.desviacio_pressio, casa.pressio_hora;
ADR 0116)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import casa  # noqa: E402

# Les 18, les 19 i les 20 de Madrid, com les dona prevision.horas_locales (ADR 0128).
H = {"time": ["2026-10-21T16:00Z", "2026-10-21T17:00Z", "2026-10-21T18:00Z"],
     "pressure_msl_meteofrance_seamless": [1019.0, 1020.0, 1022.0]}


class Pressio(unittest.TestCase):
    def test_desviacio_amb_el_model_d_ara(self):
        # A les 18:30 el model dona 1019,5; la de casa, 1021,0.
        casa_ = {"hora": "2026-10-21T18:30+02:00", "pressio": 1021.0}
        self.assertAlmostEqual(casa.desviacio_pressio(H, casa_), 1.5)

    def test_sense_lectura_de_casa_no_es_toca(self):
        self.assertEqual(casa.desviacio_pressio(H, None), 0.0)
        self.assertEqual(casa.desviacio_pressio(H, {"hora": "2026-10-21T18:30+02:00", "pressio": None}), 0.0)

    def test_una_lectura_dolenta_no_es_toca(self):
        casa_ = {"hora": "2026-10-21T18:30+02:00", "pressio": 1030.0}
        self.assertEqual(casa.desviacio_pressio(H, casa_), 0.0)

    def test_el_tram_es_la_mitjana_dels_extrems_mes_la_desviacio(self):
        self.assertEqual(casa.pressio_hora(H, 2, 1.5), 1022.5)
        # La primera hora de la resposta, sense principi: la de l'hora.
        self.assertEqual(casa.pressio_hora(H, 0, 0.0), 1019.0)
        self.assertIsNone(casa.pressio_hora({"time": H["time"]}, 1, 0.0))


if __name__ == "__main__":
    unittest.main()
