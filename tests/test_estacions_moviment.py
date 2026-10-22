# SPDX-License-Identifier: AGPL-3.0-or-later
"""El registre del moviment del radar (moviment_registre.py, ADR 0019): RainViewer
sense moviment, el que ja s'havia avaluat, la neteja dels trossos i el resum
amb el vent a 700 hPa."""
import contextlib
import csv
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import config as C  # noqa: E402
import moviment_registre as MR  # noqa: E402
import nowcast as N  # noqa: E402

T0 = dt.datetime(2026, 10, 17, 16, 0).astimezone()


def xafec(fila, col, radi=8):
    yy, xx = np.mgrid[:N.MIDA, :N.MIDA]
    return np.where((yy - fila) ** 2 + (xx - col) ** 2 <= radi ** 2, 5.0, 0.0)


class AmbRegistre(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        reg = os.path.join(self.dir.name, "registre")
        os.makedirs(reg)
        valors = {"REGISTRE": reg, "FITXER": os.path.join(reg, "moviment.csv"),
                  "FITXER_CREIX": os.path.join(reg, "creixement.csv"),
                  "TROSSOS": os.path.join(self.dir.name, "moviment"), "_avaluats": None}
        for nom, valor in valors.items():
            p = mock.patch.object(MR, nom, valor)
            p.start()
            self.addCleanup(p.stop)

    def files(self):
        with open(MR.FITXER, encoding="utf-8") as f:
            return list(csv.DictReader(f))


class Calculs(unittest.TestCase):
    def test_desplaca_amb_zeros_i_massa_lluny(self):
        a = np.arange(9).reshape(3, 3)
        self.assertEqual(MR.desplaca(a, 1, 0).tolist(), [[0, 0, 0], [0, 1, 2], [3, 4, 5]])
        self.assertEqual(MR.desplaca(a, 0, -1).tolist(), [[1, 2, 0], [4, 5, 0], [7, 8, 0]])
        self.assertFalse(MR.desplaca(a, 3, 0).any())
        self.assertFalse(MR.desplaca(a, 0, -5).any())

    def test_csi(self):
        p = np.array([True, True, False, False])
        v = np.array([True, False, True, False])
        self.assertEqual(MR.csi(p, v), 0.333)
        # Sense pluja ni vista ni prevista, no hi ha índex (no és un encert).
        self.assertIsNone(MR.csi(np.zeros(4, bool), np.zeros(4, bool)))


class Apunta(AmbRegistre):
    def radar(self, hora, camp):
        tx, ty = N.geometria(*C.CASA)
        return {"tx": tx, "ty": ty, "km_px": N.km_px(C.CASA[0]),
                "rainviewer": {"hores": [hora - dt.timedelta(minutes=10), hora], "mm_h": [None, camp]}}

    def casa(self):
        tx, ty = N.geometria(*C.CASA)
        return N.pixel(C.CASA[0], C.CASA[1], tx, ty)

    def test_rainviewer_sense_moviment_es_compara_quieta(self):
        fila, col = self.casa()
        camp = xafec(fila + 5, col)
        for minuts in (0, 30):
            hora = T0 + dt.timedelta(minutes=minuts)
            n = MR.apunta(self.radar(hora, camp), None, ara=hora)
        self.assertEqual(n, 1)
        x = self.files()[0]
        self.assertEqual((x["radar"], x["antelacio_min"], x["font_moviment"]), ("rainviewer", "30", "cap"))
        # Sense moviment, la prevista és la quieta: el mateix índex i cap velocitat.
        self.assertEqual((x["kmh"], x["graus"]), ("", ""))
        self.assertEqual(x["csi_moviment"], x["csi_quieta"])
        self.assertEqual(float(x["csi_quieta"]), 1.0)
        self.assertEqual(x["px_prevista"], x["px_quieta"])
        self.assertEqual(len(os.listdir(MR.TROSSOS)), 2)

    def test_sense_pluja_no_es_compara(self):
        buit = np.zeros((N.MIDA, N.MIDA))
        for minuts in (0, 30):
            hora = T0 + dt.timedelta(minutes=minuts)
            self.assertEqual(MR.apunta(self.radar(hora, buit), {"v": [0.1, 0.1], "moviment": "x"}, ara=hora), 0)
        self.assertFalse(os.path.exists(MR.FITXER))

    def test_fora_del_marge_no_es_compara(self):
        fila, col = self.casa()
        camp = xafec(fila, col)
        for minuts in (0, 45):
            hora = T0 + dt.timedelta(minutes=minuts)
            self.assertEqual(MR.apunta(self.radar(hora, camp), None, ara=hora), 0)

    def test_sense_hora_fa_servir_la_d_ara(self):
        fila, col = self.casa()
        ara = dt.datetime.now().astimezone()
        self.assertEqual(MR.apunta(self.radar(ara, xafec(fila, col)), None), 0)
        self.assertEqual(len(os.listdir(MR.TROSSOS)), 1)


class JaAvaluat(AmbRegistre):
    def test_llegeix_les_files_que_ja_hi_ha(self):
        with open(MR.FITXER, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, MR.CAMPS)
            w.writeheader()
            w.writerow({"emes": T0.isoformat(timespec="minutes"), "radar": "meteocat", "antelacio_min": 30})
        self.assertTrue(MR.ja_avaluat("meteocat", T0, 30))
        self.assertFalse(MR.ja_avaluat("meteocat", T0, 60))
        self.assertTrue(MR.ja_avaluat("meteocat", T0, 60))
        self.assertFalse(MR.ja_avaluat("rainviewer", T0, 30))


class Neteja(AmbRegistre):
    def test_esborra_els_trossos_de_mes_de_tres_hores(self):
        os.makedirs(MR.TROSSOS)
        vell, nou = (os.path.join(MR.TROSSOS, n) for n in ("vell.npz", "nou.npz"))
        for ruta in (vell, nou):
            open(ruta, "wb").close()
        ara = time.time()
        os.utime(vell, (ara - 3 * 3600 - 60,) * 2)
        os.utime(nou, (ara - 3 * 3600 + 60,) * 2)
        MR.neteja(dt.datetime.fromtimestamp(ara).astimezone())
        self.assertEqual(os.listdir(MR.TROSSOS), ["nou.npz"])


def respon_vent(hores, crides=None):
    def get(url):
        if crides is not None:
            crides.append(url)
        return json.dumps({"hourly": {"time": [h for h, _, _ in hores],
                                      "wind_speed_700hPa": [s for _, s, _ in hores],
                                      "wind_direction_700hPa": [d for _, _, d in hores]}})
    return get


class Vent700(unittest.TestCase):
    def test_demana_els_dies_i_treu_les_hores_buides(self):
        crides = []
        res = MR.vent_700({"2026-10-18", "2026-10-17"}, respon_vent(
            [("2026-10-17T16:00", 40, 270), ("2026-10-17T17:00", None, 270), ("2026-10-17T18:00", 30, None)], crides))
        self.assertEqual(res, {"2026-10-17T16": (40, 270)})
        self.assertIn("start_date=2026-10-17&end_date=2026-10-18", crides[0])
        self.assertIn(f"latitude={C.CASA[0]}", crides[0])
        self.assertIn("wind_speed_700hPa", crides[0])


class Resum(AmbRegistre):
    FILES = [
        ("2026-10-17T16:00+02:00", "30", "meteocat", "20", "90", "0.8", "0.4"),
        ("2026-10-17T17:00+02:00", "30", "meteocat", "30", "100", "0.5", "0.6"),
        ("2026-10-17T18:00+02:00", "30", "meteocat", "10", "45", "0.3", "0.3"),
        ("2026-10-18T09:00+02:00", "60", "cap", "", "", "0.2", "0.2"),
        ("2026-10-19T09:00+02:00", "60", "cap", "", "", "", "0.2"),
    ]

    def escriu(self, files):
        with open(MR.FITXER, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, MR.CAMPS)
            w.writeheader()
            for emes, ant, font, kmh, graus, m, q in files:
                w.writerow({"emes": emes, "radar": "meteocat", "antelacio_min": ant, "font_moviment": font,
                            "kmh": kmh, "graus": graus, "csi_moviment": m, "csi_quieta": q})

    def resum(self, get):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            MR.resum(get)
        return out.getvalue()

    def test_sense_registre(self):
        self.assertIn("Encara no hi ha cap comparació", self.resum(None))

    def test_sense_csi_no_hi_ha_res_a_comparar(self):
        self.escriu([self.FILES[-1]])
        self.assertIn("Cap comparació amb pluja.", self.resum(None))

    def test_mitjanes_i_vent(self):
        self.escriu(self.FILES)
        get = respon_vent([("2026-10-17T16:00", 40, 270), ("2026-10-17T17:00", 60, 290),
                           ("2026-10-17T18:00", 3, 0)])
        text = self.resum(get)
        # La fila sense CSI del moviment no compta (ni el seu dia).
        self.assertIn("4 comparacions, 2 dies amb pluja a prop (2026-10-17 a 2026-10-18).", text)
        self.assertIn("30 min, totes         3 casos · moviment 0.533 · quieta 0.433 · guanya el moviment 1, perd 1",
                      text)
        self.assertIn("60 min, cap           1 casos · moviment 0.200 · quieta 0.200 · guanya el moviment 0, perd 0",
                      text)
        # Vent de 270° (de l'oest) porta la pluja cap als 90°: 0° de diferència; el de 290°, 10°.
        # Amb vent de menys de 5 km/h no es compara.
        self.assertIn("(2 casos amb vent de 5 km/h o més): diferència de direcció mediana 10°", text)
        self.assertIn("velocitat del radar / vent, mediana 0.50.", text)

    def test_si_el_vent_falla_ho_diu(self):
        self.escriu(self.FILES)

        def get(url):
            raise OSError("Open-Meteo no respon")
        self.assertIn("Sense el vent a 700 hPa: Open-Meteo no respon", self.resum(get))

    def test_sense_moviment_no_demana_el_vent(self):
        self.escriu(self.FILES[3:])
        text = self.resum(mock.Mock(side_effect=AssertionError("no s'havia de demanar")))
        self.assertIn("60 min, totes", text)
        self.assertNotIn("700 hPa", text)

    def test_vent_massa_fluix_no_dona_resultat(self):
        self.escriu(self.FILES[2:3])
        text = self.resum(respon_vent([("2026-10-17T18:00", 3, 0)]))
        self.assertNotIn("Contra el vent", text)


class LiniaOrdres(unittest.TestCase):
    def executa(self, args, registre):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["moviment_registre.py", *args]), \
                mock.patch.dict(os.environ, {"REGISTRE_DIR": registre}), contextlib.redirect_stdout(out):
            runpy.run_path(os.path.join(ARREL, "moviment_registre.py"), run_name="__main__")
        return out.getvalue()

    def test_resum_i_ajuda(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Encara no hi ha cap comparació", self.executa(["resum"], d))
            self.assertIn("python3 moviment_registre.py resum", self.executa([], d))


if __name__ == "__main__":
    unittest.main()
