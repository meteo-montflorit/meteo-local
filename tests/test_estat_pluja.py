# SPDX-License-Identifier: AGPL-3.0-or-later
"""L'estat únic de la pluja d'ara i la taula d'hores que hi ha d'estar d'acord (casa.py, ADR 0101)."""
import datetime as dt
import os
import sys
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import casa  # noqa: E402
import config as C  # noqa: E402

ARA = dt.datetime(2026, 10, 17, 8, 40).astimezone()


def iso(minuts):
    return (ARA + dt.timedelta(minutes=minuts)).isoformat()


def hores(*probabilitats):
    """Tres hores de la taula a partir de les 8, en hora local sense zona, com a la previsió."""
    inici = ARA.replace(minute=0, tzinfo=None)
    return [{"hora": (inici + dt.timedelta(hours=n)).isoformat(), "fins": (inici + dt.timedelta(hours=n + 1)).isoformat(),
             "probabilitat": p} for n, p in enumerate(probabilitats)]


class EstatPluja(unittest.TestCase):
    def test_mana_el_mesurat_despres_el_radar(self):
        radar = {"arriba": iso(2), "possible": iso(-10), "fi": iso(60)}
        self.assertEqual(casa.estat_pluja(radar, True, ARA)["estat"], "plou")
        self.assertEqual(casa.estat_pluja(radar, True, ARA)["font"], "estacions")
        # El radar la posa a sobre: arriba d'aquí a 5 minuts o menys, o ja ha passat.
        self.assertEqual(casa.estat_pluja(radar, False, ARA)["estat"], "radar_sobre")
        self.assertEqual(casa.estat_pluja({"arriba": iso(-20)}, False, ARA)["estat"], "radar_sobre")
        self.assertEqual(casa.estat_pluja({"arriba": iso(30)}, False, ARA)["estat"], "arriba")
        self.assertEqual(casa.estat_pluja({"possible": iso(30)}, False, ARA)["estat"], "possible")
        res = casa.estat_pluja(None, False, ARA)
        self.assertEqual((res["estat"], res["font"]), ("no", None))
        # Les hores del radar es conserven tal com venen, perquè tothom digui el mateix.
        self.assertEqual(casa.estat_pluja(radar, False, ARA)["fi"], radar["fi"])


class AjustaHores(unittest.TestCase):
    def test_el_radar_a_sobre_puja_l_hora_en_curs(self):
        h = casa.ajusta_hores(hores(0.1, 0.1, 0.1), {"estat": "radar_sobre"}, ARA)
        self.assertEqual([f["probabilitat"] for f in h], [0.5, 0.1, 0.1])
        self.assertTrue(h[0]["segons_radar"])

    def test_la_que_arriba_puja_la_seva_hora_i_mai_baixa(self):
        h = casa.ajusta_hores(hores(0.1, 0.7, 0.1), {"estat": "arriba", "arriba": iso(30)}, ARA)
        # Arriba a les 9:10: és la segona hora, que ja deia més i no es toca.
        self.assertEqual([f["probabilitat"] for f in h], [0.1, 0.7, 0.1])
        self.assertNotIn("segons_radar", h[1])
        h = casa.ajusta_hores(hores(0.0, 0.0, 0.0), {"estat": "possible", "possible": iso(90)}, ARA)
        self.assertEqual([f["probabilitat"] for f in h], [0.0, 0.0, C.PROB_ATENCION])

    def test_la_que_ja_es_mesura_no_es_diu_segons_el_radar(self):
        h = hores(0.1, 0.1, 0.1)
        h[0]["segons_estacio"] = True
        casa.ajusta_hores(h, {"estat": "radar_sobre"}, ARA)
        self.assertEqual(h[0]["probabilitat"], 0.5)
        self.assertFalse(h[0]["segons_radar"])

    def test_sense_pluja_o_sense_hores_no_canvia_res(self):
        h = hores(0.1, 0.1, 0.1)
        self.assertEqual(casa.ajusta_hores(h, {"estat": "no"}, ARA), hores(0.1, 0.1, 0.1))
        self.assertEqual(casa.ajusta_hores(h, None, ARA), hores(0.1, 0.1, 0.1))
        self.assertEqual(casa.ajusta_hores([], {"estat": "radar_sobre"}, ARA), [])


if __name__ == "__main__":
    unittest.main()
