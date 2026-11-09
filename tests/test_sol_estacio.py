# SPDX-License-Identifier: AGPL-3.0-or-later
"""El sol directo sobre el termómetro de la estación de casa (ADR 0081)."""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sol_estacio as SE  # noqa: E402

T0 = dt.datetime(2026, 10, 9, 8, 30).astimezone()


def lectures(valors, inici=T0):
    return [(inici + dt.timedelta(minutes=5 * i), v) for i, v in enumerate(valors)]


class Sol(unittest.TestCase):
    def test_el_salt_del_9_d_octubre(self):
        # 8:30 9,2 °C → 8:50 13,0; vecinas 10,5 y la estación, 1 °C más fría de normal.
        l = lectures([9.2, 9.2, 9.9, 11.6, 13.0])
        ara = l[-1][0]
        estat, esperada, exces = SE.avalua(l, [10.5, 10.0, 11.0], -1.0, None, ara, 22)
        self.assertIsNotNone(estat)
        self.assertAlmostEqual(esperada, 9.5)
        self.assertAlmostEqual(exces, 3.5)
        # Sigue mientras esté por encima; acaba cuando vuelve a lo esperado.
        seg = ara + dt.timedelta(minutes=30)
        estat2, _, _ = SE.avalua(lectures([13.4], seg), [12.5, 12.0, 13.0], -1.0, estat, seg, 25)
        self.assertIsNotNone(estat2)
        fi = ara + dt.timedelta(minutes=80)
        self.assertIsNone(SE.avalua(lectures([13.1], fi), [14.0, 13.5, 14.5], -1.0, estat2, fi, 23)[0])

    def test_sense_salt_no_hi_ha_sol(self):
        # Por encima de las vecinas, pero subiendo poco a poco: no es el sol en el termómetro.
        l = lectures([12.0, 12.2, 12.4, 12.6, 12.8, 13.0, 13.2])
        self.assertIsNone(SE.avalua(l, [10.0, 10.5, 10.0], -1.0, None, l[-1][0], 200)[0])
        # Un salto de noche (sin radiación), tampoco.
        l = lectures([9.0, 9.0, 11.0, 12.0])
        self.assertIsNone(SE.avalua(l, [9.0, 9.5, 9.0], -1.0, None, l[-1][0], 0)[0])
        # Sin diferencia habitual o con menos de dos vecinas, no se decide.
        self.assertIsNone(SE.avalua(l, [9.0, 9.5], None, None, l[-1][0], 20)[0])
        self.assertIsNone(SE.avalua(l, [9.0], -1.0, None, l[-1][0], 20)[0])

    def test_diferencia_habitual_sense_les_hores_de_sol(self):
        ara = dt.datetime(2026, 10, 12, 12).astimezone()
        casa, veines = {}, {"A": {}, "B": {}}
        for h in range(30):
            c = (ara - dt.timedelta(hours=h + 1)).strftime("%Y-%m-%dT%H:%M")
            casa[c] = 10.0
            veines["A"][c] = veines["B"][c] = 11.0
        c9 = (ara - dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
        casa[c9] = 15.0
        eps = [(dt.datetime.fromisoformat(c9).astimezone(), dt.datetime.fromisoformat(c9).astimezone())]
        self.assertEqual(SE.ofset(casa, veines, ara, eps), -1.0)
        self.assertEqual(SE.hores_tocades(casa, eps), {c9})
        self.assertIsNone(SE.ofset({k: v for k, v in list(casa.items())[:10]}, veines, ara, eps))

    def test_diferencia_habitual_per_franges_d_hora_solar(self):
        # Del 10-10 al 09-11-2026 la casa estaba −0,4 °C de 6 a 9 h y −1,8 de
        # 12 a 15 h (hora solar, UTC): cada hora usa la de su franja.
        ara = dt.datetime(2026, 11, 9, 0, tzinfo=dt.timezone.utc)
        casa, veines = {}, {"A": {}, "B": {}}
        for h in range(24 * 12):
            t = ara - dt.timedelta(hours=h + 1)
            c = t.strftime("%Y-%m-%dT%H:%MZ")
            veines["A"][c] = veines["B"][c] = 10.0
            casa[c] = 10.0 + (-0.4 if 6 <= t.hour < 9 else -1.8 if 12 <= t.hour < 15 else -1.0)
        mati = dt.datetime(2026, 11, 9, 7, 30, tzinfo=dt.timezone.utc)
        migdia = dt.datetime(2026, 11, 9, 13, tzinfo=dt.timezone.utc)
        self.assertAlmostEqual(SE.ofset(casa, veines, ara, [], hora=mati), -0.4)
        self.assertAlmostEqual(SE.ofset(casa, veines, ara, [], hora=migdia), -1.8)
        self.assertAlmostEqual(SE.ofset(casa, veines, ara, [], hora="2026-11-09T22:00Z"), -1.0)
        self.assertAlmostEqual(SE.ofset(casa, veines, ara, []), -1.0)   # sin hora, la de todo el día
        self.assertEqual(SE.franja("2026-11-09T08:59Z"), 2)
        # Con la hora de Madrid (09:30 CET = 08:30 UTC), la misma franja.
        self.assertEqual(SE.franja(dt.datetime(2026, 11, 9, 9, 30, tzinfo=dt.timezone(dt.timedelta(hours=1)))), 2)
        # Una franja con menos de FRANJA_MIN horas usa la de todo el día.
        pocs = {c: v for c, v in casa.items() if not (6 <= SE.H.utc(c).hour < 9) or SE.H.utc(c).day == 8}
        self.assertEqual(len([c for c in pocs if 6 <= SE.H.utc(c).hour < 9]), 3)
        self.assertAlmostEqual(SE.ofset(pocs, veines, ara, [], hora=mati), -1.0)

    def test_les_hores_de_sol_amb_la_temperatura_esperada(self):
        # El 12-10-2026 faltaban las 9 y las 10 en la comparación con ayer:
        # ahora llevan la mediana de las vecinas más la diferencia habitual.
        ara = dt.datetime(2026, 10, 13, 6).astimezone()
        casa, veines = {}, {"A": {}, "B": {}, "C": {}}
        for h in range(40):
            c = (ara - dt.timedelta(hours=h + 1)).strftime("%Y-%m-%dT%H:%M")
            casa[c] = 12.0
            veines["A"][c] = veines["B"][c] = veines["C"][c] = 13.0
        c9, c10 = "2026-10-12T09:00", "2026-10-12T10:00"
        casa[c9], casa[c10] = 19.0, 18.0
        veines["A"][c9], veines["B"][c9], veines["C"][c9] = 14.0, 14.0, 15.0
        veines["A"][c10], veines["B"][c10] = 16.0, None
        veines["C"][c10] = None
        eps = [(dt.datetime(2026, 10, 12, 8, 40).astimezone(), dt.datetime(2026, 10, 12, 10, 5).astimezone())]
        res = SE.amb_esperades(casa, ara, eps, casa, veines)
        self.assertEqual(res[c9], 13.0)   # 14 − 1
        self.assertNotIn(c10, res)        # una sola vecina: no se estima
        self.assertEqual(len(res), len(casa) - 1)
        # Sin diferencia habitual (pocas horas), las horas de sol se quitan.
        pocas = {c9: 19.0, "2026-10-12T11:00": 18.0}
        self.assertEqual(SE.amb_esperades(pocas, ara, eps, pocas, veines), {"2026-10-12T11:00": 18.0})

    def test_humitat_amb_el_punt_de_rosada(self):
        # 98 % a 13 °C (rocío 12,7): con el sensor a 16,6, la estación diría ~80 %.
        self.assertAlmostEqual(SE.humitat(12.7, 13.0), 98, delta=1)
        self.assertLess(SE.humitat(12.7, 16.6), 82)

    def test_apunta_i_allarga_l_episodi(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "sol.csv")
            SE.apunta(T0, T0 + dt.timedelta(minutes=10), 2.0, ruta)
            SE.apunta(T0, T0 + dt.timedelta(minutes=40), 3.0, ruta)
            self.assertEqual(SE.episodis(ruta), [(T0, T0 + dt.timedelta(minutes=40))])


if __name__ == "__main__":
    unittest.main()
