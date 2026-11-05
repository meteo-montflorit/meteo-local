# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del horario de actualización y del modo aviso (sin red)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
import prevision as P  # noqa: E402
import que_toca as Q  # noqa: E402


def datos(horari):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"generat": dt.datetime.now().isoformat(), "horari": horari}, f)
    f.close()
    return f.name


class QueToca(unittest.TestCase):
    # Solo la página del tiempo: el trayecto se retiró (ADR 0030).
    def test_horario_normal(self):
        c = datos(P.horario([C.HORARIO_CASA], C.INTERVALO_CASA_MIN, []))
        self.assertEqual(Q.que_toca("06:30", c), "casa")
        self.assertEqual(Q.que_toca("10:00", c), "casa")
        self.assertEqual(Q.que_toca("10:10", c), "")

    def test_modo_aviso_al_ritme_del_radar(self):
        # Cada 6 minutos, 3 después de cada imagen de Meteocat (ADR 0020).
        self.assertEqual((C.MODO_AVISO_INTERVALO_MIN, C.MODO_AVISO_DESFASE_MIN), (6, 3))
        c = datos(P.horario([C.HORARIO_CASA_AVISO], C.INTERVALO_CASA_MIN, ["pluja al radar"]))
        self.assertEqual(Q.que_toca("10:21", c), "casa")
        self.assertEqual(Q.que_toca("23:57", c), "casa")
        self.assertEqual(Q.que_toca("10:00", c), "")
        self.assertEqual(Q.que_toca("10:20", c), "")

    def test_distancia_solo_si_es_el_motivo(self):
        # Con la lluvia más lejos de RADAR_AVISO_KM, el modo aviso viene de la
        # que el radar prevé en casa: sin distancia (revisor, 05-11-2026).
        cerca = P.horario([C.HORARIO_CASA_AVISO], C.INTERVALO_CASA_MIN, ["pluja al radar"], 12.6)
        lejos = P.horario([C.HORARIO_CASA_AVISO], C.INTERVALO_CASA_MIN, ["pluja al radar"], 15.4)
        self.assertEqual(cerca["km_pluja"], 12.6)
        self.assertNotIn("km_pluja", lejos)

    def test_sin_datos_de_hoy_usa_el_horario_normal(self):
        self.assertEqual(Q.que_toca("13:00", "/no/existe"), "casa")


class ModoAviso(unittest.TestCase):
    def test_sin_nada_no_hay_modo_aviso(self):
        self.assertEqual(P.motivos_modo_aviso([], [], [], {"km_lluvia": None}), [])

    def test_plan_en_emergencia(self):
        self.assertIn("pla de Protecció Civil",
                      P.motivos_modo_aviso([], [{"fase": "emergència"}], [], None))

    def test_lluvia_cerca_en_el_radar(self):
        self.assertEqual(P.motivos_modo_aviso([], [], [], {"km_lluvia": 8}), ["pluja al radar"])
        self.assertEqual(P.motivos_modo_aviso([], [], [], {"km_lluvia": 40}), [])

    def test_aviso_de_meteocat_sin_aemet(self):
        # Juanjo, 16-10-2026: el de Meteocat cuenta aunque AEMET no tenga ninguno.
        ara = P.AHORA.astimezone()
        ahora = {"avisos": [{"meteor": "Pluja", "dies": {ara.date().isoformat(): [(ara.hour, ara.hour + 1)]}}]}
        despues = {"avisos": [{"meteor": "Pluja", "dies": {"2099-01-01": [(0, 6)]}}]}
        self.assertEqual(P.motivos_modo_aviso([], [], [], None, ahora), ["avís del Meteocat"])
        self.assertEqual(P.motivos_modo_aviso([], [], [], None, despues), [])
        self.assertEqual(P.motivos_modo_aviso([], [], [], None, None), [])


if __name__ == "__main__":
    unittest.main()
