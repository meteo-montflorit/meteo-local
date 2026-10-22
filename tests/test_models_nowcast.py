# SPDX-License-Identifier: AGPL-3.0-or-later
"""Més proves del radar llevat endavant (nowcast.py, ADR 0019, 0023 i 0026):
les teselles dels dos radars, la càrrega quan una font falla i el resum per
a casa i la conca. Sense xarxa: les teselles són PNG fets aquí."""
import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import config as C  # noqa: E402
import nowcast as N  # noqa: E402

T0 = dt.datetime(2026, 10, 6, 12, 0).astimezone()


def png(rgba):
    """Una tesela de 256x256 d'un sol color RGBA."""
    b = io.BytesIO()
    Image.new("RGBA", (256, 256), rgba).save(b, format="PNG")
    return b.getvalue()


def hex_rgba(text):
    text = text.lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in range(0, 8, 2))


class SenseCache(unittest.TestCase):
    """Sense carpeta de caché (fora del NAS), les teselles sempre de la xarxa."""

    def setUp(self):
        p = mock.patch.object(N, "CACHE", "/no/existeix/radar-cache")
        p.start()
        self.addCleanup(p.stop)


class Rainviewer(SenseCache):
    def test_fotogrames_i_colors(self):
        color, dbz = next((c, d) for c, d in N.taula_dbz().items() if d == 30)
        demanades = []
        meta = ('{"host": "https://tilecache.rainviewer.com", "radar": {"past": ['
                + ",".join(f'{{"time": {int(T0.timestamp()) + 600 * k}, "path": "/v2/radar/{k}"}}' for k in range(9))
                + "]}}")

        def get(url, binari=False):
            demanades.append(url)
            return meta if url.endswith("weather-maps.json") else png(hex_rgba(color))
        rv = N.rainviewer(get, 64, 47, fotogrames=2)
        self.assertEqual(rv["hores"], [T0 + dt.timedelta(minutes=70), T0 + dt.timedelta(minutes=80)])
        self.assertEqual(len(rv["mm_h"]), 2)
        self.assertEqual(rv["mm_h"][0].shape, (N.MIDA, N.MIDA))
        # 30 dBZ amb Marshall-Palmer: uns 2,7 mm/h a tot el mosaic.
        self.assertAlmostEqual(float(rv["mm_h"][1][400, 400]), float(N.mm_h(np.array(30.0))), places=6)
        self.assertAlmostEqual(float(N.mm_h(np.array(30.0))), 2.73, places=2)
        # 3x3 teselles per fotograma, al voltant de la del centre.
        teselles = [u for u in demanades if u.endswith(".png")]
        self.assertEqual(len(teselles), 18)
        self.assertIn("https://tilecache.rainviewer.com/v2/radar/8/256/7/63/46/2/0_0.png", teselles)

    def test_color_desconegut_o_transparent_no_es_pluja(self):
        claus, valors = N.llegenda((int(k[1:], 16), v) for k, v in N.taula_dbz().items())
        for rgba in ((1, 2, 3, 255), (0, 0, 0, 0)):
            camp = N.mosaic(lambda url, binari, rgba=rgba: png(rgba), lambda x, y: f"u/{x}/{y}", 64, 47, claus, valors)
            self.assertEqual(float(camp.max()), 0.0)


class Meteocat(SenseCache):
    PAGINA = ("var x = {dataDarreraRadar: '10/06/2026 09:54Z', "
              "dataDarreraAdveccio: '2026-10-06T09:48:00Z'};")

    def test_imatge_i_adveccio(self):
        demanades = []

        def get(url, binari=False):
            demanades.append(url)
            if url.endswith("/radar"):
                return self.PAGINA.encode()           # la pàgina pot arribar en bytes
            return png((0, 255, 255, 255))            # 18 dBZ a la llegenda de Meteocat
        r = N.meteocat(get, 64, 47)
        self.assertEqual(r["hora"], dt.datetime(2026, 10, 6, 9, 54, tzinfo=dt.timezone.utc))
        # El centre de la franja de 18 dBZ: 19,5.
        self.assertAlmostEqual(float(r["mm_h"][10, 10]), float(N.mm_h(np.array(19.5))), places=6)
        adv = r["adveccio"]
        self.assertEqual(adv["base"], dt.datetime(2026, 10, 6, 9, 48, tzinfo=dt.timezone.utc))
        self.assertEqual([t for t, _ in adv["previsions"]],
                         [dt.datetime(2026, 10, 6, 9, 54, tzinfo=dt.timezone.utc),
                          dt.datetime(2026, 10, 6, 10, 48, tzinfo=dt.timezone.utc)])
        # Les teselles en TMS: la y, des del sud (127 - 47 = 80).
        self.assertIn(f"{N.METEOCAT}/radar/2026/10/06/09/54/07/000/000/064/000/000/080.png", demanades)
        self.assertIn(f"{N.METEOCAT}/adveccio/2026/10/06/2026/10/06/09/48/10/48/07/000/000/063/000/000/079.png",
                      demanades)
        self.assertEqual(len(demanades), 1 + 9 * 3)

    def test_pagina_reutilitzada_i_sense_dates(self):
        teselles = []
        r = N.meteocat(lambda url, binari=False: teselles.append(url), 64, 47, get_pagina=lambda url: "res")
        self.assertEqual((r, teselles), ({}, []))


class Carrega(SenseCache):
    def test_rainviewer_caigut_no_atura_meteocat(self):
        with mock.patch.object(N, "rainviewer", side_effect=OSError("RainViewer caigut")), \
                mock.patch.object(N, "meteocat", return_value={"hora": T0}), \
                mock.patch.object(N, "en_pausa", return_value=None):
            r = N.carrega(lambda url, binari=False: b"")
        self.assertEqual(r["errors"], ["RainViewer: RainViewer caigut"])
        self.assertNotIn("rainviewer", r)
        self.assertEqual(r["meteocat"], {"hora": T0})
        self.assertEqual((r["tx"], r["ty"]), N.geometria(*C.CASA))

    def test_rebuig_fora_del_nas_no_posa_pausa(self):
        import urllib.error
        rebuig = urllib.error.HTTPError("https://www.meteo.cat/", 403, "Forbidden", {}, None)
        self.assertIsNone(N.posa_pausa())
        with mock.patch.object(N, "rainviewer", return_value=None), \
                mock.patch.object(N, "meteocat", side_effect=rebuig), \
                mock.patch.object(N, "en_pausa", return_value=None):
            r = N.carrega(lambda url, binari=False: b"")
        self.assertEqual(len(r["errors"]), 1)
        self.assertTrue(r["errors"][0].startswith("Meteocat: HTTP Error 403"))

    def test_neteja_no_falla_si_un_fitxer_desapareix(self):
        with tempfile.TemporaryDirectory() as d:
            cache = os.path.join(d, "radar-cache")
            os.makedirs(cache)
            with open(os.path.join(cache, "a.png"), "wb") as f:
                f.write(b"x")
            with mock.patch.object(N, "CACHE", cache), \
                    mock.patch.object(N.os.path, "getmtime", side_effect=FileNotFoundError("ja no hi és")):
                N.neteja_cache()
            self.assertEqual(os.listdir(cache), ["a.png"])


def camp(centre, radi=15, mmh=10.0):
    yy, xx = np.mgrid[:N.MIDA, :N.MIDA]
    return np.where((yy - centre[0]) ** 2 + (xx - centre[1]) ** 2 <= radi ** 2, mmh, 0.0)


class Resum(unittest.TestCase):
    def setUp(self):
        self.tx, self.ty = N.geometria(*C.CASA)
        self.f, self.c = N.pixel(*C.CASA, self.tx, self.ty)
        self.r = {"tx": self.tx, "ty": self.ty, "km_px": N.km_px(C.CASA[0]), "errors": []}

    def test_sense_imatges(self):
        self.assertIsNone(N.imatge(self.r, "meteocat"))
        self.assertIsNone(N.resum(self.r, T0))
        self.assertIsNone(N.moviment(self.r, T0))

    def test_sense_moviment_la_pluja_queda_quieta(self):
        # Un xàfec a sobre de casa i cap manera de saber cap on va: la serie és la de ara, quieta.
        self.r["rainviewer"] = {"hores": [T0], "mm_h": [camp((self.f, self.c), radi=60)]}
        with mock.patch.object(N, "font_preferida", return_value="rainviewer"):
            nc = N.resum(self.r, T0)
        self.assertEqual((nc["imatge"], nc["moviment"], nc["velocitat_kmh"], nc["cap_a"]),
                         ("rainviewer", None, None, None))
        self.assertNotIn("v", nc)
        self.assertEqual(set(nc["llocs"]), {"casa", "conca"})
        casa = nc["llocs"]["casa"]
        self.assertEqual(len(casa), N.HORITZO_MIN // N.PAS_MIN + 1)
        self.assertTrue(all(p["prob"] == 1.0 and p["mm_h"] == 10.0 for p in casa[:5]))
        self.assertEqual(N.arribada(nc), T0)
        self.assertEqual(set(nc["fonts"]), {"rainviewer"})
        self.assertEqual(nc["fonts"]["rainviewer"]["prob"][0], 1.0)

    def test_amb_moviment_cap_a_l_est(self):
        self.r["rainviewer"] = {"hores": [T0], "mm_h": [camp((self.f, self.c - 40), radi=10)]}
        self.r["meteocat"] = {"hora": T0 - dt.timedelta(minutes=5), "mm_h": camp((self.f, self.c - 40), radi=10)}
        v = (0.0, 0.5)
        with mock.patch.object(N, "moviment", return_value=(v, "meteocat")), \
                mock.patch.object(N, "font_preferida", return_value="rainviewer"):
            nc = N.resum(self.r, T0)
        self.assertEqual((nc["moviment"], nc["cap_a"], nc["graus"], nc["v"]), ("meteocat", "a l'est", 90, [0.0, 0.5]))
        self.assertEqual(nc["velocitat_kmh"], round(0.5 * self.r["km_px"] * 60))
        self.assertEqual(nc["fonts"]["meteocat"]["hora"], (T0 - dt.timedelta(minutes=5)).isoformat(timespec="minutes"))
        # Ara no plou a casa; el xàfec arriba més tard.
        self.assertEqual(nc["llocs"]["casa"][0]["prob"], 0.0)
        self.assertGreater(N.arribada(nc), T0)

    def test_la_serie_s_atura_fora_del_mosaic(self):
        # A tota velocitat, el punt d'on ve la pluja surt del mosaic: no s'inventa res més enllà.
        s = N.serie(self.r, np.zeros((N.MIDA, N.MIDA)), (0.0, 20.0), *C.CASA)
        self.assertLess(len(s), N.HORITZO_MIN // N.PAS_MIN + 1)
        self.assertTrue(all(p["prob"] == 0.0 for p in s))

    def test_desplacament_local_sense_casa(self):
        self.assertIsNone(N.desplacament_local(camp((384, 384)), camp((384, 390)), {"km_px": 1.0}, 30))
        # Entre imatges massa properes en el temps, no es pot buscar cap salt.
        self.assertIsNone(N.desplacament_local(camp((self.f, self.c), 40), camp((self.f, self.c + 1), 40), self.r, 0.1))

    def test_sense_radar_no_hi_ha_arribada(self):
        self.assertIsNone(N.arribada(None))
        self.assertIsNone(N.arribada({"hora": T0.isoformat(), "llocs": {}}))
        self.assertIsNone(N.intensitat_arribada(None))
        self.assertIsNone(N.en_tram(None, "casa", T0, T0))


if __name__ == "__main__":
    unittest.main()
