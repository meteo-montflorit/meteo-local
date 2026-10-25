# SPDX-License-Identifier: AGPL-3.0-or-later
"""casa.py ante fuentes congeladas o caídas (revisión del 07-10-2026), sin red."""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import casa  # noqa: E402
import prevision as P  # noqa: E402

AHORA = dt.datetime(2026, 10, 7, 18, 30).astimezone()



class Fonts(unittest.TestCase):
    def setUp(self):
        self.ahora, self.get_recent, self.get = P.AHORA, P.get_recent, P.get
        P.AHORA = AHORA

    def tearDown(self):
        P.AHORA, P.get_recent, P.get = self.ahora, self.get_recent, self.get

    def test_sense_ensemble_la_previsio_segueix(self):
        def get(url):
            if "ensemble" in url:
                raise RuntimeError("502")
            return json.dumps({"hourly": {"time": []}})
        P.get = get
        errors = []
        h, e = casa.modelos(AHORA, errors)
        self.assertEqual((h, e), ({"time": []}, {}))
        self.assertTrue(errors and errors[0].startswith("ensemble: "))
        with self.assertRaises(RuntimeError):
            casa.modelos(AHORA)        # sense llista d'errors, com abans: falla

    def test_open_meteo_es_torna_a_provar(self):
        # 17-10-2026: Open-Meteo respon 503 uns segons; es torna a provar dues vegades, només si és transitori.
        import io
        import urllib.error
        error = lambda codi: urllib.error.HTTPError("u", codi, "x", {}, io.BytesIO())
        respostes, esperes = [error(503), error(503), "ok"], []

        def get(url):
            r = respostes.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        P.get = get
        self.assertEqual(P.get_reintenta("u", dorm=esperes.append), "ok")
        self.assertEqual(esperes, [5, 15])
        respostes[:] = [error(503)] * 3
        with self.assertRaises(urllib.error.HTTPError):
            P.get_reintenta("u", dorm=esperes.append)          # al tercer, prou
        respostes[:], esperes[:] = [error(400), "ok"], []
        with self.assertRaises(urllib.error.HTTPError):
            P.get_reintenta("u", dorm=esperes.append)          # un error de la consulta no es reintenta
        self.assertEqual(esperes, [])


if __name__ == "__main__":
    unittest.main()


class VentHora(unittest.TestCase):
    """El vent de cada fila, la mitjana de l'hora (19-10-2026): abans, el d'un
    instant, i en una hora de tempesta sortia «3 (37)»."""

    def test_mitjana_de_la_hora(self):
        import casa
        # Les claus, en UTC com les dona prevision.horas_locales (ADR 0128).
        h = {"time": ["2026-10-19T15:00Z", "2026-10-19T16:00Z"],
             "wind_speed_10m_meteofrance_seamless": [12.7, 3.3],
             "vent_15min": {"2026-10-19T15:00Z": 12.7, "2026-10-19T15:15Z": 12.1, "2026-10-19T15:30Z": 7.1,
                            "2026-10-19T15:45Z": 1.1, "2026-10-19T16:00Z": 3.3}}
        # Pels trapezis: (12,7/2 + 12,1 + 7,1 + 1,1 + 3,3/2) / 4 = 7,1, no el 3,3 de les 18 h.
        self.assertEqual(casa.vent_hora(h, 1), 7.1)
        # Sense els de 15 minuts, la mitjana del principi i el final.
        self.assertEqual(casa.vent_hora({**h, "vent_15min": {}}, 1), 8.0)
        # I sense el principi, el de l'hora.
        self.assertEqual(casa.vent_hora({**h, "vent_15min": {}}, 0), 12.7)


class RatxaHora(unittest.TestCase):
    def test_la_del_model_que_en_preveu_mes(self):
        # 19-10-2026, 13:43: la combinada de Météo-France, 66 km/h; AROME HD, 92,5, i AROME, 89,3.
        h = {"wind_gusts_10m_meteofrance_seamless": [65.9], "wind_gusts_10m_meteofrance_arome_france_hd": [92.5],
             "wind_gusts_10m_meteofrance_arome_france": [89.3], "wind_gusts_10m_icon_eu": [11.5]}
        self.assertEqual(casa.ratxa_modelos(h, 0), 92.5)
        # Sense cap model fi, la combinada.
        self.assertEqual(casa.ratxa_modelos({"wind_gusts_10m_meteofrance_seamless": [65.9]}, 0), 65.9)

