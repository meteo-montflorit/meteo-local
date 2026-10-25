# SPDX-License-Identifier: AGPL-3.0-or-later
import datetime as dt
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ecotop as E  # noqa: E402

ARA = dt.datetime(2026, 10, 19, 16, 45, tzinfo=E.ZONA)


def paquet(classes, nom="down_GLD261019142000.TOP.12DBZ_240.tif", mtime=None):
    """Un paquete como el de AEMET: un GeoTIFF RGBA con la escala de colores y
    casa en el centro, a 0,005° por píxel."""
    rgba = np.zeros(classes.shape + (4,), np.uint8)
    for k, col in E.ESCALA.items():
        rgba[classes == k] = (*col, 255)
    lat, lon = E.C.CASA
    ny, nx = classes.shape
    im = Image.fromarray(rgba, "RGBA")
    b = io.BytesIO()
    im.save(b, "TIFF", tiffinfo={33922: (0.0, 0.0, 0.0, lon - (nx // 2) * 0.005, lat + (ny // 2) * 0.005, 0.0),
                                 33550: (0.005, 0.005, 0.0)})
    t = io.BytesIO()
    with tarfile.open(fileobj=t, mode="w:gz") as tar:
        info = tarfile.TarInfo(nom)
        info.size = len(b.getvalue())
        info.mtime = mtime or dt.datetime(2026, 10, 19, 16, 30, tzinfo=E.ZONA).timestamp()
        tar.addfile(info, io.BytesIO(b.getvalue()))
        altre = tarfile.TarInfo("down_MAD261019142000.TOP.12DBZ_240.tif")
        altre.size = 0
        tar.addfile(altre, io.BytesIO(b""))
    return t.getvalue()


class Ecotop(unittest.TestCase):
    def test_cal_amb_pluja_a_la_vista(self):
        sec = {"radar": {"propera": None}, "pluja_ara": {"estat": "no"},
               "hores": [{"hora": "2026-10-19T18:00:00+02:00", "probabilitat": 0.05}]}
        self.assertFalse(E.cal(sec, ARA))
        self.assertTrue(E.cal({**sec, "radar": {"propera": {"km": 40}}}, ARA))
        self.assertTrue(E.cal({**sec, "pluja_ara": {"estat": "plou"}}, ARA))
        self.assertTrue(E.cal({**sec, "hores": [{"hora": "2026-10-19T21:00:00+02:00", "probabilitat": 0.3}]}, ARA))
        # Les hores de casa.json, sense zona (com les escriu casa.py).
        self.assertFalse(E.cal({**sec, "hores": [{"hora": "2026-10-19T18:00", "probabilitat": 0.05}]}, ARA))
        self.assertTrue(E.cal({**sec, "hores": [{"hora": "2026-10-19T21:00", "probabilitat": 0.3}]}, ARA))
        # Més enllà de 6 hores, no.
        self.assertFalse(E.cal({**sec, "hores": [{"hora": "2026-10-20T03:00:00+02:00", "probabilitat": 0.9}]}, ARA))

    def test_classifica_amb_els_colors_de_l_escala(self):
        # El GeoTIFF va amb JPEG: un groc una mica desviat és 8 km; sense alfa, res.
        rgba = np.array([[[250, 252, 6, 255], [130, 10, 110, 255], [255, 255, 0, 0], [128, 128, 128, 255]]], np.uint8)
        self.assertEqual(E.classifica(rgba).tolist(), [[8, 20, 0, E.DESCONEGUT]])

    def test_mesura(self):
        c = np.zeros((101, 101), np.uint8)
        c[50, 50] = 3                      # sobre casa
        c[50, 60] = 8                      # 10 píxels a l'est
        c[10, 50] = 12                     # 40 píxels al nord
        r = E.mesura(c, 50, 50, 1.0, 1.0)
        self.assertEqual((r["max_casa"], r["max_5"], r["max_15"], r["max_30"], r["max_60"]), (3, 3, 8, 8, 12))
        self.assertEqual((r["km_8"], r["graus_8"]), (10.0, 90))
        self.assertEqual((r["km_10"], r["graus_10"]), (40.0, 0))
        self.assertEqual((r["km2_8_30"], r["km2_10_30"]), (1.0, 0.0))

    def test_apunta_un_cop_i_espera(self):
        c = np.zeros((301, 301), np.uint8)
        c[150, 150:160] = 10
        with tempfile.TemporaryDirectory() as d:
            E.REGISTRE, E.FITXER = d, os.path.join(d, "ecotop.csv")
            E.TROSSOS, E.BAIXADA = os.path.join(d, "ecotop"), os.path.join(d, "ecotop", "darrera-baixada")
            casa = os.path.join(d, "casa.json")
            with open(casa, "w") as f:
                json.dump({"radar": {"propera": {"km": 5}}}, f)
            p = paquet(c)
            self.assertEqual(E.apunta(casa, ARA, lambda: p), 1)
            # Abans de CADA_MIN no es torna a baixar; després, la mateixa imatge no es repeteix.
            self.assertEqual(E.apunta(casa, ARA + dt.timedelta(minutes=10), lambda: 1 / 0), 0)
            self.assertEqual(E.apunta(casa, ARA + dt.timedelta(minutes=30), lambda: p), 0)
            with open(E.FITXER) as f:
                files = f.read().splitlines()
            self.assertEqual(len(files), 2)
            # En UTC (ADR 0128): les 16:20 de Madrid són les 14:20Z.
            self.assertTrue(files[1].startswith("2026-10-19T14:20Z,2026-10-19T14:30Z,2026-10-19T14:45Z,10,"))
            self.assertTrue(os.path.exists(os.path.join(E.TROSSOS, "GLD-202610191420Z.png")))


if __name__ == "__main__":
    unittest.main()
