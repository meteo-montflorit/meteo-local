# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del radar llevado hacia delante (sin red)."""
import datetime as dt
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
import nowcast as N  # noqa: E402
import prevision as P  # noqa: E402

T0 = dt.datetime(2026, 10, 6, 12, 0).astimezone()


def camp(centre, radi=15, mmh=10.0):
    """Un chubasco redondo de mmh en el mosaico."""
    yy, xx = np.mgrid[:N.MIDA, :N.MIDA]
    return np.where((yy - centre[0]) ** 2 + (xx - centre[1]) ** 2 <= radi ** 2, mmh, 0.0)


class MapaIPropera(unittest.TestCase):
    # El requadre del radar (17-10-2026): la pluja més propera i el tros del mapa, de la mateixa imatge.
    def test_propera_i_mapa(self):
        camp = np.zeros((N.MIDA, N.MIDA))
        fila, col, km = 384.3, 384.6, 0.9
        self.assertIsNone(N.propera(camp, fila, col, km))
        self.assertIsNone(N.mapa(camp, fila, col, km))
        camp[374, 384] = 1.0          # feble, uns 9 km al nord
        camp[384, 395] = 45.0         # forta, uns 9,4 km a l'est
        p = N.propera(camp, fila, col, km)
        self.assertEqual((p["rumb"], p["classe"]), ("al nord", 1))
        self.assertAlmostEqual(p["km"], 9.3, delta=0.2)
        # Les franges de Meteocat en mm/h (el doble de les de 30 minuts).
        self.assertEqual([int(N.classe(x)) for x in (0.4, 0.5, 5.9, 6, 39.9, 40, 80)], [0, 1, 1, 2, 2, 3, 4])
        m = N.mapa(camp, fila, col, km)
        self.assertEqual(len(m["classes"]), m["n"] ** 2)
        n0 = (m["n"] - 1) // 2
        f0, c0 = 384 - n0, 385 - n0        # on comença el tros
        self.assertEqual(m["classes"][(374 - f0) * m["n"] + (384 - c0)], "1")
        self.assertEqual(m["classes"][(384 - f0) * m["n"] + (395 - c0)], "3")
        self.assertAlmostEqual(m["fila"], fila - f0)
        # Més lluny de PROPERA_MAX_KM, no es diu.
        lluny = np.zeros((N.MIDA, N.MIDA))
        lluny[384, 384 + 70] = 5
        self.assertIsNone(N.propera(lluny, fila, col, km))

    def test_el_mapa_porta_els_ecos_febles(self):
        # 18-10-2026: si el requadre parla de plugim, el mapa l'ha de poder pintar.
        camp = np.zeros((N.MIDA, N.MIDA))
        fila, col, km = 384.3, 384.6, 0.9
        camp[383, 384] = 0.2          # plugim, a sobre de casa
        camp[384, 395] = 0.05         # soroll: no
        m = N.mapa(camp, fila, col, km)
        self.assertIsNotNone(m)       # abans, sense pluja que compta, no hi havia mapa
        self.assertEqual(set(m["classes"]), {"0"})
        n0 = (m["n"] - 1) // 2
        f0, c0 = 384 - n0, 385 - n0
        self.assertEqual(m["febles"][(383 - f0) * m["n"] + (384 - c0)], "1")
        self.assertEqual(m["febles"].count("1"), 1)
        camp[383, 384] = 1.0          # ja és pluja que compta: cap eco feble
        self.assertNotIn("febles", N.mapa(camp, fila, col, km))

    def test_creixement(self):
        # 17-10-2026: la tempesta es formava cada cop més a prop, sense moure's cap aquí.
        fila, col, km = 384.3, 384.6, 0.9
        T1 = dt.datetime(2026, 10, 17, 19, 10).astimezone()
        hores = [T1 - dt.timedelta(minutes=10 * k) for k in range(6, -1, -1)]

        def pluja(radi):
            return camp((374, 384), radi, 5.0) if radi else np.zeros((N.MIDA, N.MIDA))
        r = {"rainviewer": {"hores": hores, "mm_h": [pluja(2)] * 4 + [pluja(3), pluja(4), pluja(6)]}}
        c = N.creixement(r, fila, col, km)
        self.assertEqual((c["minuts"], c["creix"]), (30, True))
        self.assertGreaterEqual(c["km2"] - c["km2_abans"], N.CREIX_GUANY_KM2)
        # La part del cercle de 15 km (uns 707 km²), en %.
        self.assertAlmostEqual(c["pct"], 100 * c["km2"] / 707, delta=1)
        self.assertAlmostEqual(c["km_moderada"], 3.9, delta=0.5)
        # El doble de poca pluja no és res: de 10 a 20 km², no es diu (Juanjo, 17-10-2026).
        r["rainviewer"]["mm_h"] = [pluja(2)] * 4 + [pluja(2), pluja(2), pluja(3)]
        c = N.creixement(r, fila, col, km)
        self.assertGreaterEqual(c["km2"], 2 * c["km2_abans"])
        self.assertFalse(c["creix"])
        # Sense pluja abans.
        r["rainviewer"]["mm_h"] = [pluja(0)] * 6 + [pluja(5)]
        c = N.creixement(r, fila, col, km)
        self.assertEqual((c["km2_abans"], c["pct_abans"], c["creix"]), (0, 0, True))
        # Sense la imatge de fa mitja hora, res.
        self.assertIsNone(N.creixement({"rainviewer": {"hores": hores[-2:], "mm_h": [pluja(2)] * 2}}, fila, col, km))

    def test_forta(self):
        # 17-10-2026: amb trons i una tempesta a 10 km, el requadre només deia
        # «la més propera, feble».
        fila, col, km = 384.3, 384.6, 0.9
        camp = np.zeros((N.MIDA, N.MIDA))
        camp[380, 384] = 1.0          # feble, uns 4 km al nord
        self.assertIsNone(N.forta(camp, fila, col, km))
        camp[384, 395] = 20.0         # moderada però intensa (15 mm/h o més), uns 9,4 km a l'est: es diu
        f = N.forta(camp, fila, col, km)
        self.assertEqual((f["rumb"], f["classe"]), ("a l'est", 2))
        camp[373, 384] = 45.0         # forta, uns 10 km al nord: mana la més intensa
        f = N.forta(camp, fila, col, km)
        self.assertEqual((f["rumb"], f["classe"]), ("al nord", 3))
        self.assertAlmostEqual(f["km"], 10.2, delta=0.3)
        # Més lluny de FORTA_KM, no.
        lluny = np.zeros((N.MIDA, N.MIDA))
        lluny[384, 384 + 20] = 60
        self.assertIsNone(N.forta(lluny, fila, col, km))


class Conversions(unittest.TestCase):
    def test_marshall_palmer(self):
        self.assertAlmostEqual(float(N.mm_h(np.array(23.0))), 1.0, delta=0.1)   # 23 dBZ ≈ 1 mm/h
        self.assertAlmostEqual(float(N.mm_h(np.array(44.0))), 20.5, delta=1.5)
        self.assertEqual(float(N.mm_h(np.array(-32.0))), 0.0)

    def test_llegenda_meteocat_i_rainviewer(self):
        claus, valors = N.llegenda((int(c + "ff", 16), d + 1.5) for d, c in N.LLEGENDA_METEOCAT)
        rgba = np.array([[[0x00, 0xff, 0x00, 0xff], [0, 0, 0, 0], [1, 2, 3, 0xff]]], dtype=np.uint64)
        r = N.a_mm_h(rgba, claus, valors)
        self.assertAlmostEqual(float(r[0, 0]), float(N.mm_h(np.array(25.5))), places=3)
        self.assertEqual(float(r[0, 1]), 0.0)
        self.assertEqual(float(r[0, 2]), 0.0)          # color fuera de la leyenda
        self.assertGreater(len(N.taula_dbz()), 70)


class Moviment(unittest.TestCase):
    def test_desplacament_d_un_xubasc(self):
        a, b = camp((380, 370)), camp((372, 384))
        d = N.desplacament(a, b)
        self.assertAlmostEqual(d[0], -8, delta=0.6)
        self.assertAlmostEqual(d[1], 14, delta=0.6)

    def test_sense_pluja(self):
        self.assertIsNone(N.desplacament(np.zeros((N.MIDA, N.MIDA)), np.zeros((N.MIDA, N.MIDA))))

    def test_moviment_de_la_pluja_de_prop(self):
        # Cerca de casa, lluvia que va al este; lejos, una masa mayor que
        # va al sur. Manda la de cerca (ADR 0023).
        r = {"tx": 64, "ty": 47, "km_px": N.km_px(41.52)}
        f, c = (int(x) for x in N.pixel(*C.CASA, 64, 47))
        a = np.maximum(camp((f + 10, c - 20), radi=12), camp((f - 150, c - 150), radi=40))
        b = np.maximum(camp((f + 10, c + 7), radi=12), camp((f - 120, c - 150), radi=40))
        self.assertEqual(N.desplacament_local(a, b, r, 54), (0.0, 27.0))
        adv = {"base": T0 - dt.timedelta(minutes=20),
               "previsions": [(T0 - dt.timedelta(minutes=14), a), (T0 + dt.timedelta(minutes=40), b)]}
        v, origen = N.moviment({**r, "meteocat": {"adveccio": adv}}, T0)
        self.assertEqual(origen, "meteocat")
        self.assertAlmostEqual(v[0], 0.0, delta=0.01)
        self.assertAlmostEqual(v[1], 0.5, delta=0.01)

    def test_poca_pluja_a_prop_es_mesura_tot_el_quadre(self):
        r = {"tx": 64, "ty": 47, "km_px": N.km_px(41.52)}
        f, c = (int(x) for x in N.pixel(*C.CASA, 64, 47))
        # Solo lluvia a más de 100 km: cerca no hay nada que medir.
        a, b = camp((f - 120, c - 120), radi=30), camp((f - 120, c - 93), radi=30)
        self.assertIsNone(N.desplacament_local(a, b, r, 54))
        adv = {"base": T0 - dt.timedelta(minutes=20),
               "previsions": [(T0 - dt.timedelta(minutes=14), a), (T0 + dt.timedelta(minutes=40), b)]}
        v, _ = N.moviment({**r, "meteocat": {"adveccio": adv}}, T0)
        self.assertAlmostEqual(v[1], 0.5, delta=0.03)
        # Lluvia tan rápida que se sale de la búsqueda (más de 60 km): tampoco.
        self.assertIsNone(N.desplacament_local(camp((f, c - 40), radi=12), camp((f, c + 35), radi=12), r, 54))
        # Dos manchas que no se parecen: tampoco.
        self.assertIsNone(N.desplacament_local(camp((f, c), radi=6), camp((f, c), radi=40), r, 54))

    def test_rumb(self):
        self.assertEqual(N.rumb((-1, 0)), "al nord")
        self.assertEqual(N.rumb((0, 1)), "a l'est")
        self.assertEqual(N.rumb((1, -1)), "al sud-oest")
        self.assertAlmostEqual(N.graus((-1, 1)), 45)

    def test_rainviewer_nomes_si_els_parells_coincideixen(self):
        hores = [T0 - dt.timedelta(minutes=10 * k) for k in range(6, -1, -1)]
        bo = {"hores": hores, "mm_h": [camp((380, 360 + 2 * k)) for k in range(7)]}
        r = {"km_px": 0.92, "rainviewer": bo}
        v, origen = N.moviment(r, T0)
        self.assertEqual(origen, "rainviewer")
        self.assertAlmostEqual(v[1], 0.2, delta=0.03)          # 2 píxeles cada 10 minutos
        salts = [camp((380, 360 + (40 if k % 2 else 0))) for k in range(7)]
        self.assertIsNone(N.moviment({"km_px": 0.92, "rainviewer": {"hores": hores, "mm_h": salts}}, T0))

    def test_adveccio_de_meteocat_mana(self):
        adv = {"base": T0 - dt.timedelta(minutes=20),
               "previsions": [(T0 - dt.timedelta(minutes=14), camp((380, 360))),
                              (T0 + dt.timedelta(minutes=40), camp((380, 387)))]}
        v, origen = N.moviment({"km_px": 0.92, "meteocat": {"adveccio": adv}}, T0)
        self.assertEqual(origen, "meteocat")
        self.assertAlmostEqual(v[1], 0.5, delta=0.03)
        # Una advección de hace más de una hora no vale.
        self.assertIsNone(N.moviment({"km_px": 0.92, "meteocat": {"adveccio": adv}},
                                     T0 + dt.timedelta(minutes=50)))


class Cache(unittest.TestCase):
    def test_nomes_baixa_un_cop_i_neteja(self):
        import tempfile, time
        base = tempfile.mkdtemp()
        N.CACHE = os.path.join(base, "radar-cache")
        baixades = []
        get = lambda url, binari: baixades.append(url) or b"png"
        self.assertEqual(N.tesela(get, "https://x/1.png"), b"png")
        self.assertEqual(N.tesela(get, "https://x/1.png"), b"png")
        self.assertEqual(baixades, ["https://x/1.png"])
        vell = os.path.join(N.CACHE, os.listdir(N.CACHE)[0])
        os.utime(vell, (time.time() - 4 * 3600,) * 2)
        N.neteja_cache()
        self.assertEqual(os.listdir(N.CACHE), [])

    def test_sense_carpeta_no_desa(self):
        N.CACHE = "/no/existeix/radar-cache"
        self.assertEqual(N.tesela(lambda u, b: b"x", "https://x/2.png"), b"x")


class Pausa(unittest.TestCase):
    def setUp(self):
        import tempfile
        N.CACHE = os.path.join(tempfile.mkdtemp(), "radar-cache")
        self.rv = N.rainviewer
        N.rainviewer = lambda get, tx, ty: {"hores": [T0], "mm_h": [camp((380, 380))]}

    def tearDown(self):
        N.rainviewer = self.rv

    def carrega(self, error):
        demanades = []

        def get(url, binari=False):
            demanades.append(url)
            raise error
        r = N.carrega(get)
        return r, demanades

    def test_rebuig_posa_pausa_i_no_torna_a_demanar(self):
        import urllib.error
        rebuig = urllib.error.HTTPError("https://www.meteo.cat/", 429, "Too Many Requests", {}, None)
        r, demanades = self.carrega(rebuig)
        self.assertEqual(len(demanades), 1)
        self.assertIsNotNone(N.en_pausa())
        self.assertEqual(N.imatge(r)[2], "rainviewer")      # la mateixa passada, amb RainViewer
        r, demanades = self.carrega(rebuig)
        self.assertEqual(demanades, [])                      # en pausa: ni s'intenta
        self.assertIn("en pausa", " ".join(r["errors"]))
        self.assertIsNone(N.en_pausa(dt.datetime.now().astimezone() + dt.timedelta(minutes=61)))

    def test_caiguda_no_posa_pausa(self):
        r, demanades = self.carrega(TimeoutError("timed out"))
        self.assertIsNone(N.en_pausa())
        self.assertEqual(N.imatge(r)[2], "rainviewer")


class Endavant(unittest.TestCase):
    def setUp(self):
        self.r = {"tx": 64, "ty": 47, "km_px": N.km_px(41.52)}
        self.f, self.c = N.pixel(*C.CASA, 64, 47)

    def test_arriba_quan_toca(self):
        # Un chubasco a 30 píxeles al oeste de casa que va al este a 0,5 px/min:
        # llega en unos 60 minutos.
        ara = camp((self.f, self.c - 30), radi=8)
        s = N.serie(self.r, ara, (0.0, 0.5), *C.CASA)
        nc = {"hora": T0.isoformat(), "llocs": {"casa": s}}
        arriba = N.arribada(nc)
        self.assertTrue(T0 + dt.timedelta(minutes=45) <= arriba <= T0 + dt.timedelta(minutes=65))
        abans = N.en_tram(nc, "casa", T0, T0 + dt.timedelta(minutes=30))
        despres = N.en_tram(nc, "casa", T0 + dt.timedelta(minutes=50), T0 + dt.timedelta(minutes=70))
        self.assertEqual(abans["prob"], 0)
        self.assertGreater(despres["prob"], 0.5)
        self.assertGreater(despres["mm"], 1)
        self.assertIsNone(N.en_tram(nc, "casa", T0 + dt.timedelta(hours=3), T0 + dt.timedelta(hours=4)))

    def test_si_se_n_va_no_arriba(self):
        ara = camp((self.f, self.c - 30), radi=8)
        s = N.serie(self.r, ara, (0.0, -0.5), *C.CASA)
        self.assertIsNone(N.arribada({"hora": T0.isoformat(), "llocs": {"casa": s}}))


class ModeAvis(unittest.TestCase):
    def nc(self, prob, mm_h):
        passos = [{"min": m, "mm_h": mm_h, "prob": prob} for m in range(0, 125, 5)]
        return {"hora": P.AHORA.isoformat(), "cap_a": "a l'est", "velocitat_kmh": 30,
                "llocs": {"casa": passos}}

    def test_mode_avis(self):
        self.assertEqual(P.motivos_modo_aviso([], [], [], {"km_lluvia": None, "nowcast": self.nc(0.4, 1)}),
                         ["pluja al radar"])
        self.assertEqual(P.motivos_modo_aviso([], [], [], {"km_lluvia": None, "nowcast": self.nc(0.0, 0)}), [])


if __name__ == "__main__":
    unittest.main()
