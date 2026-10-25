# SPDX-License-Identifier: AGPL-3.0-or-later
"""La humedad de cada hora de la gráfica: el punto de rocío corregido con la
temperatura de la página (casa.humitat_hora, aprenentatge.rosada; ADR 0114)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aprenentatge as A  # noqa: E402
import casa  # noqa: E402
import sol_estacio as SE  # noqa: E402

SENSE = {"humitat": None}       # sin corrección: el rocío del modelo


def hora(t, hr, **mes):
    return {"fins": "2026-10-21T12:00", "antelacio_h": 3, "temperature_2m": t, "relative_humidity_2m": hr,
            "cloud_cover": 50, "shortwave_radiation": 300, **mes}


class Rosada(unittest.TestCase):
    def test_es_la_inversa_de_humitat(self):
        for t, hr in ((15, 60), (9, 98), (25, 30), (-3, 80)):
            self.assertAlmostEqual(SE.humitat(SE.rosada(t, hr), t), hr, places=6)

    def test_sense_correccio_es_la_del_model(self):
        self.assertAlmostEqual(A.rosada(SENSE, hora(15, 60)), SE.rosada(15, 60))
        self.assertIsNone(A.rosada(SENSE, hora(15, None)))

    def test_correccio(self):
        # Una corrección que solo lleva la constante: el modelo, 1,3 °C más seco.
        noms = A.RASGOS_ROSADA_SENSE_ESTACIO
        model = {"humitat": {"rasgos_sense_estacio": noms, "w_sense_estacio": [-1.3] + [0] * (len(noms) - 1)}}
        self.assertAlmostEqual(A.rosada(model, hora(15, 60)), SE.rosada(15, 60) + 1.3)

    def test_amb_l_error_al_prever(self):
        # Con el error de ahora, los pesos completos; sin él, los que no lo necesitan.
        model = {"humitat": {"rasgos": A.RASGOS_ROSADA, "w": [0] * (len(A.RASGOS_ROSADA) - 2) + [1, 0],
                             "rasgos_sense_estacio": A.RASGOS_ROSADA_SENSE_ESTACIO,
                             "w_sense_estacio": [0] * len(A.RASGOS_ROSADA_SENSE_ESTACIO)}}
        amb = A.rosada(model, hora(15, 60, error_rosada_ara=-2.0))
        self.assertGreater(amb, SE.rosada(15, 60))
        self.assertAlmostEqual(A.rosada(model, hora(15, 60)), SE.rosada(15, 60))

    def test_l_arxiu_es_adopta(self):
        # El del año de casa ganó con seguridad: la web lo usa.
        self.assertIsNotNone(A.modelo_arxiu_humitat())
        self.assertIsNotNone(A.carrega()["humitat"])


class HumitatHora(unittest.TestCase):
    def test_amb_la_temperatura_de_la_pagina(self):
        # AROME da 15 °C y 60 %; la página, corregida, 13 °C: el mismo rocío
        # con menos temperatura es más humedad.
        d = hora(15, 60)
        self.assertEqual(casa.humitat_hora(SENSE, d, d, 15), 60)
        self.assertGreater(casa.humitat_hora(SENSE, d, d, 13), 60)

    def test_mitjana_del_rosada_del_tram(self):
        a, b = hora(10, 90), hora(12, 70)
        r = (SE.rosada(10, 90) + SE.rosada(12, 70)) / 2
        self.assertEqual(casa.humitat_hora(SENSE, b, a, 11), round(SE.humitat(r, 11)))

    def test_no_passa_del_100(self):
        d = hora(12, 95)
        self.assertEqual(casa.humitat_hora(SENSE, d, d, 9), 100)

    def test_sense_dades(self):
        self.assertIsNone(casa.humitat_hora(SENSE, hora(10, None), None, 10))
        self.assertIsNone(casa.humitat_hora(SENSE, hora(10, 80), None, None))
        # La primera hora, solo con la suya.
        self.assertEqual(casa.humitat_hora(SENSE, hora(10, 80), None, 10), 80)


class AlPrever(unittest.TestCase):
    def test_error_del_rosada_amb_la_mediana_del_barri(self):
        h = {"time": ["2026-10-21T03:00Z", "2026-10-21T04:00Z"],   # les 5 i les 6 de Madrid (ADR 0128)
             "temperature_2m_meteofrance_seamless": [9.0, 9.0],
             "relative_humidity_2m_meteofrance_seamless": [80, 80]}
        casa_ = {"hora": "2026-10-21T05:30+02:00", "temperatura": 9.1, "rosada": 8.4}
        veines = [{"estacio": "A", "rosada": 8.0}, {"estacio": "B", "rosada": 7.9}, {"estacio": "C", "rosada": None}]
        d = casa.al_prever(None, h, casa_, None, veines)
        self.assertAlmostEqual(d["error_rosada_ara"], round(SE.rosada(9.0, 80) - 8.0, 2))

    def test_sense_mesura(self):
        h = {"time": ["2026-10-21T03:00Z", "2026-10-21T04:00Z"],   # les 5 i les 6 de Madrid (ADR 0128)
             "temperature_2m_meteofrance_seamless": [9.0, 9.0],
             "relative_humidity_2m_meteofrance_seamless": [80, 80]}
        self.assertIsNone(casa.al_prever(None, h, None, None, [])["error_rosada_ara"])


class AprenentatgeDiari(unittest.TestCase):
    def test_rosada_observada_es_la_mediana_del_barri(self):
        casa_ = {"2026-10-21T05:00": {"rosada": "8.4"}}
        veines = {"A": {"2026-10-21T05:00": {"rosada": "8.0"}}, "B": {"2026-10-21T05:00": {"rosada": ""}},
                  "C": {"2026-10-21T05:00": {"rosada": "7.8"}}, "D": {}}
        self.assertAlmostEqual(A.rosada_observada(casa_, veines, "2026-10-21T05:00"), 8.0)
        self.assertIsNone(A.rosada_observada({}, {}, "2026-10-21T05:00"))

    def test_els_numeros_no_es_desen(self):
        self.assertNotIn("_vh", A.per_desar({"pluja": None, "humitat": None, "_vh": {"dies": 3}}))


if __name__ == "__main__":
    unittest.main()
