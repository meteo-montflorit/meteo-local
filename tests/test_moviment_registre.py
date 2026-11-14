# SPDX-License-Identifier: AGPL-3.0-or-later
"""El registro del movimiento del radar (17-10-2026): compara la lluvia llevada
hacia delante con la de después, y la de dejarla quieta."""
import csv
import datetime as dt
import importlib
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config as C  # noqa: E402
import nowcast as N  # noqa: E402


def xafec(fila, col, radi=8):
    yy, xx = np.mgrid[:N.MIDA, :N.MIDA]
    return np.where((yy - fila) ** 2 + (xx - col) ** 2 <= radi ** 2, 5.0, 0.0)


class Registre(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.environ["REGISTRE_DIR"] = os.path.join(self.dir.name, "registre")
        os.makedirs(os.environ["REGISTRE_DIR"])
        import moviment_registre
        self.MR = importlib.reload(moviment_registre)

    def tearDown(self):
        del os.environ["REGISTRE_DIR"]
        self.dir.cleanup()

    def test_el_moviment_encerta_i_quieta_no(self):
        tx, ty = N.geometria(*C.CASA)
        km = N.km_px(C.CASA[0])
        fila, col = N.pixel(C.CASA[0], C.CASA[1], tx, ty)
        t0 = dt.datetime(2026, 10, 17, 16, 0, tzinfo=dt.timezone.utc)
        v = [0.0, 0.4]              # cap a l'est, 0,4 columnes per minut (uns 22 km/h)
        nc = {"v": v, "moviment": "meteocat"}
        for minuts in (0, 30):
            r = {"tx": tx, "ty": ty, "km_px": km,
                 "meteocat": {"hora": t0 + dt.timedelta(minutes=minuts),
                              "mm_h": xafec(fila + 5, col - 20 + v[1] * minuts)}}
            self.MR.apunta(r, nc, ara=t0 + dt.timedelta(minutes=minuts))
        with open(self.MR.FITXER, encoding="utf-8") as f:
            files = list(csv.DictReader(f))
        self.assertEqual(len(files), 1)
        x = files[0]
        self.assertEqual((x["radar"], x["antelacio_min"], x["font_moviment"]), ("meteocat", "30", "meteocat"))
        self.assertEqual(float(x["csi_moviment"]), 1.0)
        self.assertLess(float(x["csi_quieta"]), 0.3)
        self.assertEqual(x["graus"], "90")
        # La mateixa imatge en una altra passada no es torna a comptar.
        self.MR.apunta(r, nc, ara=t0 + dt.timedelta(minutes=35))
        with open(self.MR.FITXER, encoding="utf-8") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)

    def test_els_trossos_amb_pluja_a_prop_es_guarden(self):
        # ADR 0049 (14-11-2026): passades les hores, el tros amb pluja a prop de casa
        # va a l'arxiu del mes; el sec s'esborra.
        tx, ty = N.geometria(*C.CASA)
        km = N.km_px(C.CASA[0])
        fila, col = N.pixel(C.CASA[0], C.CASA[1], tx, ty)
        t0 = dt.datetime(2026, 11, 14, 16, 0, tzinfo=dt.timezone.utc)
        for radar, camp in (("meteocat", xafec(fila, col + 10)), ("rainviewer", np.zeros((N.MIDA, N.MIDA)))):
            r = {"tx": tx, "ty": ty, "km_px": km, radar: ({"hora": t0, "mm_h": camp} if radar == "meteocat"
                                                           else {"hores": [t0], "mm_h": [camp]})}
            self.MR.apunta(r, {"v": [0.0, 0.4], "moviment": "meteocat"}, ara=t0)
        self.assertEqual(len(os.listdir(self.MR.TROSSOS)), 2)
        for nom in os.listdir(self.MR.TROSSOS):
            os.utime(os.path.join(self.MR.TROSSOS, nom), (t0.timestamp() - 4 * 3600,) * 2)
        self.MR.neteja(t0)
        self.assertEqual(os.listdir(self.MR.TROSSOS), [])
        self.assertEqual(os.listdir(os.path.join(self.MR.ARXIU, "2026-11")), ["meteocat-202611141600Z.npz"])

    def test_fora_del_nas_no_fa_res(self):
        os.rmdir(os.environ["REGISTRE_DIR"])
        self.assertEqual(self.MR.apunta({}, None), 0)


if __name__ == "__main__":
    unittest.main()


class Creixement(unittest.TestCase):
    def test_una_fila_per_imatge(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["REGISTRE_DIR"] = d
            import moviment_registre
            MR = importlib.reload(moviment_registre)
            c = {"hora": "2026-10-17T19:10+02:00", "minuts": 30, "km2": 118, "km2_abans": 42, "km_moderada": 7.0,
                 "km_moderada_abans": 8.4, "km2_meteocat": 94, "pct": 17, "pct_abans": 6, "creix": True}
            self.assertEqual(MR.apunta_creixement(c), 1)
            self.assertEqual(MR.apunta_creixement(c), 0)          # la mateixa imatge, una vegada
            self.assertEqual(MR.apunta_creixement({**c, "hora": "2026-10-17T19:20+02:00"}), 1)
            with open(MR.FITXER_CREIX) as f:
                files = list(csv.DictReader(f))
            self.assertEqual([(x["emes"], x["km2"], x["creix"]) for x in files],
                             [("2026-10-17T19:10+02:00", "118", "1"), ("2026-10-17T19:20+02:00", "118", "1")])
            self.assertEqual(MR.apunta_creixement(None), 0)
