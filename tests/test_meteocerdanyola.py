# SPDX-License-Identifier: AGPL-3.0-or-later
"""Les estacions de MeteoCerdanyola (ADR 0130)."""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as C  # noqa: E402
import meteocerdanyola as MCE  # noqa: E402

UTC = dt.timezone.utc
ARA = dt.datetime(2026, 11, 22, 9, 30, tzinfo=UTC)


def fila(t, prec=0.0, vel=0.0, temp=12.5):
    return {"ts": int(t.timestamp() * 1000), "dt_local": "", "TEMP": temp, "HUM": 80, "VEL": vel,
            "BAR": 1012.0, "PREC": prec, "PINT": 0, "DEWPOINT": 9.1, "AGV": 0}


def serie(minuts=60, prec=lambda i: 0.0, vel=lambda i: 6.4, fins=ARA):
    return [fila(fins - dt.timedelta(minutes=minuts - 1 - i), prec(i), vel(i)) for i in range(minuts)]


def lector(per_slug):
    def llegeix(url):
        slug = url.split("slug=")[1]
        return json.dumps({"ok": True, "rows": per_slug[slug]})
    return llegeix


class Files(unittest.TestCase):
    def test_forma_de_les_veines(self):
        f = MCE.files([fila(ARA, prec=1.2, vel=8.0)])[0]
        self.assertEqual(f["t"], ARA)
        self.assertEqual((f["pluja_avui"], f["vent"], f["temperatura"], f["rosada"]), (1.2, 8.0, 12.5, 9.1))
        # La pressió no està reduïda com la de casa, i la ratxa no la publica.
        self.assertIsNone(f["pressio"])
        self.assertIsNone(f["ratxa"])

    def test_sense_temperatura_si_no_es_del_barri(self):
        f = MCE.files([fila(ARA)], temperatura=False)[0]
        self.assertEqual((f["temperatura"], f["humitat"], f["rosada"]), (None, None, None))
        self.assertEqual(f["vent"], 0.0)

    def test_ordenades(self):
        fs = MCE.files([fila(ARA), fila(ARA - dt.timedelta(minutes=1))])
        self.assertLess(fs[0]["t"], fs[1]["t"])


class Veines(unittest.TestCase):
    def llegeix(self, prec):
        return MCE.veines_ara(ARA, lector({"cerdanyola_montflorit": serie(prec=prec),
                                           "cerdanyola_centre": serie(vel=lambda i: 20.0)}))

    def test_les_dues(self):
        veines, errors = self.llegeix(lambda i: 0.0)
        self.assertEqual(errors, [])
        self.assertEqual([v["estacio"] for v in veines], MCE.estacions())
        centre = next(v for v in veines if v["estacio"] == "MC_CENTRE")
        self.assertIsNone(centre["temperatura"])
        self.assertFalse(centre["compta"])

    def test_una_bolcada_sola_no_plou(self):
        # 0,2 mm en 15 minuts: rosada (ADR 0130).
        veines, _ = self.llegeix(lambda i: 0.2 if i >= 55 else 0.0)
        mf = next(v for v in veines if v["estacio"] == "MC_MONTFLORIT")
        self.assertEqual(mf["pluja_15min"], 0.2)
        self.assertFalse(mf["plou"])

    def test_dues_bolcades_plou(self):
        veines, _ = self.llegeix(lambda i: 0.0 if i < 50 else (0.2 if i < 55 else 0.4))
        mf = next(v for v in veines if v["estacio"] == "MC_MONTFLORIT")
        self.assertEqual(mf["pluja_15min"], 0.4)
        self.assertTrue(mf["plou"])
        self.assertTrue(mf["compta"])

    def test_una_que_falla_no_atura_l_altra(self):
        def llegeix(url):
            if "centre" in url:
                raise OSError("sense connexió")
            return json.dumps({"ok": True, "rows": serie()})
        veines, errors = MCE.veines_ara(ARA, llegeix)
        self.assertEqual([v["estacio"] for v in veines], ["MC_MONTFLORIT"])
        self.assertEqual(len(errors), 1)
        self.assertIn("MC_CENTRE", errors[0])


class Vent(unittest.TestCase):
    def veina(self, files):
        return [{"estacio": C.VENT_ARA, "files": MCE.files(files, temperatura=False)}]

    def test_mitjana_sense_ratxa(self):
        v = MCE.vent_ara(self.veina(serie(vel=lambda i: 30.0 if i == 50 else 10.0)), ARA)
        self.assertEqual(v["estacio"], "Cerdanyola Centre")
        # La ratxa no la publica, i el minut més alt no la substitueix.
        self.assertIsNone(v["ratxa"])
        # Els últims 30 minuts: 31 lectures (de 9:00 a 9:30), una de 30 km/h.
        self.assertAlmostEqual(v["mitja"], round((30 * 10 + 30) / 31, 1))

    def test_sense_lectures_recents_mana_sant_cugat(self):
        vella = serie(fins=ARA - dt.timedelta(minutes=15))
        self.assertIsNone(MCE.vent_ara(self.veina(vella), ARA))

    def test_amb_poques_lectures_mana_sant_cugat(self):
        self.assertIsNone(MCE.vent_ara(self.veina(serie(minuts=10)), ARA))

    def test_sense_l_estacio(self):
        self.assertIsNone(MCE.vent_ara([], ARA))


if __name__ == "__main__":
    unittest.main()
