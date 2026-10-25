# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de la vigilancia del pluviómetro de casa (sin red ni Telegram)."""
import datetime as dt
import os
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pluviometre as V  # noqa: E402

# Amb zona (ADR 0128): els registres sense zona són hora de Madrid.
T0 = dt.datetime(2026, 10, 6, 9, 0, tzinfo=ZoneInfo("Europe/Madrid"))


def h(n):
    return T0 + dt.timedelta(hours=n)


class Vigilancia(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        V.DIR = os.path.join(d, "registre")
        V.ESTADO, V.CASA = os.path.join(d, "vigila.json"), os.path.join(V.DIR, "c.csv")
        # Sense veïnes, les dues de Meteocat: compta la menor de les dues en cada hora.
        V.REFERENCIA = [os.path.join(V.DIR, "xf.csv"), os.path.join(V.DIR, "xv.csv")]
        V.METEOCAT_REF, V.VEINES_REF = list(V.REFERENCIA), []
        os.makedirs(V.DIR)

    def escribe(self, mont, casa, horas=200):
        for ruta, datos in ((V.REFERENCIA[0], mont), (V.REFERENCIA[1], mont), (V.CASA, casa)):
            with open(ruta, "w") as f:
                f.write("fins,pluja_mm\n")
                for n in range(horas):
                    f.write(f"{h(n).strftime('%Y-%m-%dT%H:%M')},{datos.get(n, 0.0)}\n")

    def tres_lluvias(self, en_casa):
        mont = {10: 0.4, 11: 0.4, 40: 1.0, 70: 0.3, 71: 0.5, 100: 12.0}
        casa = {11: 0.3, 40: 0.8, 72: 0.5, 100: 11.0} if en_casa else {100: 11.0}
        self.escribe(mont, casa)

    def test_funciona_avisa_una_vez_y_se_borra(self):
        self.tres_lluvias(en_casa=True)
        V.inicia(T0.isoformat())
        self.assertEqual(V.vigila(h(150), avisa=False), "funciona")
        self.assertFalse(os.path.exists(V.ESTADO))
        self.assertIsNone(V.vigila(h(151), avisa=False))

    def test_sigue_fallando(self):
        self.tres_lluvias(en_casa=False)
        V.inicia(T0.isoformat())
        self.assertEqual(V.vigila(h(150), avisa=False), "falla")

    def test_espera_hasta_tener_bastantes(self):
        self.tres_lluvias(en_casa=True)
        V.inicia(T0.isoformat())
        self.assertIsNone(V.vigila(h(60), avisa=False))     # solo dos lluvias débiles
        self.assertTrue(os.path.exists(V.ESTADO))

    def test_cuenta_desde_la_limpieza(self):
        # A las 9 h llueve débil y casa no marca; a las 12 h, la limpieza mueve
        # el cubo sin lluvia: desde ahí, todo bien.
        mont = {1: 1.0, 20: 1.0, 40: 1.0, 60: 1.0}
        casa = {3: 0.3, 20: 0.8, 40: 1.0, 60: 0.8}
        self.escribe(mont, casa)
        r = V.evalua(V.referencia(), V.lee(V.CASA), T0, h(150))
        self.assertEqual(r["neteja"], V.H.clau(h(3)))
        self.assertEqual((len(r["debils"]), r["detectats"]), (3, 3))
        self.assertIn("limpieza", V.mensaje(r, "funciona"))

    def test_la_referencia_es_la_menor_de_les_dues(self):
        # Pluja només a Sabadell: no és de tota la zona i no compta com a episodi.
        self.escribe({10: 1.0}, {}, horas=30)
        with open(V.REFERENCIA[1], "w") as f:
            f.write("fins,pluja_mm\n" + "".join(f"{h(n).strftime('%Y-%m-%dT%H:%M')},0.0\n" for n in range(30)))
        self.assertEqual(V.referencia()[h(10)], 0.0)
        self.assertEqual(V.evalua(V.referencia(), V.lee(V.CASA), T0, h(29))["debils"], [])

    def test_montflorit_primer(self):
        # ADR 0070: amb dues veïnes o més, mana la seva mediana, encara que a
        # Sabadell i a Sant Cugat no plogui (o hi plogui i aquí no).
        V.VEINES_REF = [os.path.join(V.DIR, f"v{k}.csv") for k in range(3)]
        self.escribe({10: 1.0}, {}, horas=30)
        for k, mm in enumerate((0.6, 0.8, 0.0)):
            with open(V.VEINES_REF[k], "w") as f:
                f.write("fins,pluja_mm\n" + "".join(
                    f"{h(n).strftime('%Y-%m-%dT%H:%M')},{mm if n == 20 else 0.0}\n" for n in range(30)))
        ref = V.referencia()
        self.assertEqual(ref[h(20)], 0.6)          # plou a Montflorit, no a Meteocat
        self.assertEqual(ref[h(10)], 0.0)          # plou a Meteocat, no a Montflorit

    def test_sin_lluvia_en_el_plazo(self):
        self.escribe({}, {}, horas=10)
        V.inicia(T0.isoformat())
        self.assertEqual(V.vigila(h(24 * (V.DIAS_MAX + 1)), avisa=False), "sin datos")


if __name__ == "__main__":
    unittest.main()
