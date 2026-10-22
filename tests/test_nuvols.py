# SPDX-License-Identifier: AGPL-3.0-or-later
"""El cielo: la mezcla de modelos, lo observado en Sabadell y cómo se
eligen los pesos con lo que acierta cada modelo (ADR 0088). Sin red."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import casa  # noqa: E402
import config as C  # noqa: E402
import nuvols as NV  # noqa: E402
import registre as R  # noqa: E402
import numpy as np  # noqa: E402


def metar(hora_utc, capes, brut=None):
    return {"reportTime": f"2026-10-13T{hora_utc}:00.000Z",
            "clouds": [{"cover": c, "base": 3000} for c in capes],
            "rawOb": brut or "METAR LELL " + " ".join(f"{c}030" for c in capes)}


class Metar(unittest.TestCase):
    def test_la_capa_que_mes_tapa(self):
        # 13-10-2026, 15:00 h: «FEW020 BKN030 BKN040», entre 5 y 7 octavos.
        self.assertEqual(NV.percentatge(metar("13:00", ["FEW", "BKN", "BKN"])), (75, True))
        self.assertEqual(NV.percentatge(metar("13:00", ["FEW"])), (19, True))
        self.assertEqual(NV.percentatge(metar("13:00", ["SCT"])), (44, True))
        self.assertEqual(NV.percentatge(metar("13:00", ["OVC"])), (100, True))

    def test_sense_capes_i_boira(self):
        self.assertEqual(NV.percentatge(metar("13:00", [], "METAR LELL 131300Z 09005KT CAVOK 20/10 Q1020")),
                         (0, False))
        self.assertEqual(NV.percentatge(metar("13:00", [], "METAR LELL 131300Z AUTO 00000KT 9999 NCD 20/10 Q1020")),
                         (0, False))
        self.assertEqual(NV.percentatge(metar("13:00", [], "METAR LELL 131300Z 00000KT 0100 FG VV001 10/10 Q1020")),
                         (100, True))
        self.assertEqual(NV.percentatge(metar("13:00", [], "METAR LELL 131300Z 00000KT 9999 10/10 Q1020")),
                         (None, False))

    def test_llegeix_i_hores(self):
        dades = [metar("14:30", ["BKN"]), metar("13:30", ["SCT"]), metar("14:00", ["OVC"])]
        obs = NV.llegeix(lambda url: json.dumps(dades))
        self.assertEqual([o["nuvols"] for o in obs], [44, 100, 75])       # ordenadas
        h = {fin.strftime("%H:%M"): pct for fin, (pct, _, _) in NV.hores(obs).items()}
        # La hora que acaba a las 16 h (locales) junta las 15:30 y las 16:00.
        self.assertEqual(h, {"16:00": 72, "17:00": 75})

    def test_reintenta_un_504(self):
        crides = []

        def get(url):
            crides.append(url)
            if len(crides) == 1:
                raise OSError("HTTP Error 504")
            return json.dumps([metar("14:00", ["SCT"])])
        self.assertEqual(NV.llegeix(get)[0]["nuvols"], 44)

    def test_ara(self):
        obs = NV.llegeix(lambda url: json.dumps([metar("14:30", ["BKN"])]))
        t = obs[0]["t"]
        self.assertEqual(NV.ara(obs, t + dt.timedelta(minutes=40)), 75)
        self.assertIsNone(NV.ara(obs, t + dt.timedelta(minutes=50)))     # vieja
        cavok = NV.llegeix(lambda url: json.dumps([metar("14:30", [], "METAR LELL CAVOK")]))
        self.assertEqual(NV.ara(cavok, t), 0)   # sin nubes bajas; las altas, de los modelos
        sense = NV.llegeix(lambda url: json.dumps([metar("14:30", [], "METAR LELL 9999 10/10")]))
        self.assertIsNone(NV.ara(sense, t))     # no dice nada de las nubes
        self.assertIsNone(NV.ara([], t))

    def test_cel_ara_amb_els_nuvols_de_sobre(self):
        # 22-10-2026 a las 18 h: Sabadell, «FEW035» todo el día, y nubes altas
        # que el METAR no da. Los modelos: AROME 87 % (bajas 0), ICON-EU 100
        # (22), ECMWF 70 (0), GFS 100 (0). Sale «cobert», no «serè».
        h = {"cloud_cover_meteofrance_seamless": [87], "cloud_cover_low_meteofrance_seamless": [0],
             "cloud_cover_icon_eu": [100], "cloud_cover_low_icon_eu": [22],
             "cloud_cover_ecmwf_ifs": [70], "cloud_cover_low_ecmwf_ifs": [0],
             "cloud_cover_gfs_seamless": [100], "cloud_cover_low_gfs_seamless": [0]}
        with mock.patch.object(NV, "PESOS", "/no/existeix.json"):
            self.assertEqual(NV.cel_ara(19, h, 0), 89)
            # Si las bajas observadas tapan más, mandan ellas.
            self.assertEqual(NV.cel_ara(75, h, 0), 89)
            self.assertEqual(NV.cel_ara(100, h, 0), 100)
            # Sin las bajas de los modelos no se sabe qué hay encima: lo observado.
            self.assertEqual(NV.cel_ara(19, {"cloud_cover_icon_eu": [100]}, 0), 19)

    def test_per_sobre(self):
        self.assertEqual(NV.per_sobre(100, 0), 100)
        self.assertEqual(NV.per_sobre(60, 60), 0)
        self.assertAlmostEqual(NV.per_sobre(80, 50), 60)
        self.assertIsNone(NV.per_sobre(100, 100))       # las bajas lo tapan todo
        self.assertIsNone(NV.per_sobre(None, 0))


class Mescla(unittest.TestCase):
    def test_mitjana_ponderada_amb_els_que_hi_son(self):
        p = {"arome": 0.25, "icon_eu": 0.25, "ecmwf": 0.25, "gfs": 0.25}
        # 13-10-2026 a las 17 h: AROME 14, ECMWF 17, ICON 89, GFS 100.
        self.assertEqual(NV.mescla({"arome": 14, "icon_eu": 89, "ecmwf": 17, "gfs": 100}, p), 55)
        self.assertEqual(NV.mescla({"arome": 14, "icon_eu": 89, "ecmwf": None, "gfs": None}, p), 52)
        self.assertIsNone(NV.mescla({"arome": None, "icon_eu": None, "ecmwf": None, "gfs": None}, p))
        # Si los que tienen peso no tienen dato, la media de los que sí.
        self.assertEqual(NV.mescla({"arome": 10, "icon_eu": None, "ecmwf": None, "gfs": 30},
                                   {"arome": 0, "icon_eu": 1, "ecmwf": 0, "gfs": 0}), 20)

    def test_pesos_per_defecte(self):
        with mock.patch.object(NV, "PESOS", "/no/existeix.json"):
            self.assertEqual(NV.pesos(), {m: 0.25 for m in NV.MODELS})

    def test_la_taula_fa_servir_la_mescla_i_el_que_es_veu_ara(self):
        desde = dt.datetime(2026, 10, 13, 16, 43).astimezone()
        h = {"time": [f"2026-10-13T{x:02d}:00" for x in range(24)]}
        for m in C.MODELOS_FINOS:
            h[f"precipitation_{m}"] = [0.0] * 24
        h["cloud_cover_meteofrance_seamless"] = [14] * 24
        h["cloud_cover_icon_eu"] = [89] * 24
        h["cloud_cover_ecmwf_ifs"] = [17] * 24
        h["cloud_cover_gfs_seamless"] = [100] * 24
        with mock.patch.object(NV, "PESOS", "/no/existeix.json"):
            sense = casa.previsio(desde, h, {}, [])
            amb = casa.previsio(desde, h, {}, [], nuvols_ara=75)
        self.assertEqual([f["nuvols"] for f in sense[:2]], [55, 55])
        self.assertEqual([f["nuvols"] for f in amb[:2]], [75, 55])      # solo la hora en curso
        # Lo que daba cada modelo va al registro, para aprender.
        d = casa.variables_hora(desde, h, {}, 17, {})
        self.assertEqual((d["nuvols_arome"], d["nuvols_icon_eu"], d["nuvols_ecmwf"], d["nuvols_gfs"]),
                         (14, 89, 17, 100))


class Ajust(unittest.TestCase):
    def test_recupera_els_pesos(self):
        rng = np.random.default_rng(1)
        x = rng.uniform(0, 100, (2000, 4))
        y = x @ np.array([0.1, 0.0, 0.6, 0.3]) + rng.normal(0, 5, 2000)
        w = NV.ajusta(x, y)
        np.testing.assert_allclose(w, [0.1, 0.0, 0.6, 0.3], atol=0.02)
        self.assertAlmostEqual(w.sum(), 1)

    def test_pesos_positius_que_sumen_1(self):
        # Sin restricciones, el mejor sería 2·x0 − x1: aquí no puede haber
        # pesos negativos ni que pasen de 1.
        rng = np.random.default_rng(2)
        x = rng.uniform(0, 100, (500, 4))
        w = NV.ajusta(x, 2 * x[:, 0] - x[:, 1])
        self.assertTrue((w >= 0).all())
        self.assertAlmostEqual(w.sum(), 1)
        self.assertEqual(int(np.argmax(w)), 0)

    def test_exacte_contra_la_reixa(self):
        # Ningún peso de una rejilla fina se equivoca menos que el ajuste.
        rng = np.random.default_rng(3)
        x = rng.uniform(0, 100, (300, 4))
        y = np.clip(x @ np.array([0.35, 0.25, 0.4, 0]) + rng.normal(0, 20, 300), 0, 100)
        sse = lambda w: float(np.sum((x @ np.array(w) - y) ** 2))  # noqa: E731
        millor = sse(NV.ajusta(x, y))
        n = 20
        for a in range(n + 1):
            for b in range(n + 1 - a):
                for c in range(n + 1 - a - b):
                    self.assertGreaterEqual(sse([a / n, b / n, c / n, (n - a - b - c) / n]) + 1e-6, millor)


class Aprenentatge(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.object(NV, "DIR", self.dir), mock.patch.object(R, "DIR", self.dir),
                        mock.patch.object(NV, "APRENENTATGE", self.dir),
                        mock.patch.object(NV, "PESOS", os.path.join(self.dir, "nuvols-pesos.json")),
                        mock.patch.object(NV, "OBSERVATS", os.path.join(self.dir, "nuvols-sabadell.csv"))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def registra(self, dies, observat, previst, capes=1):
        """Horas observadas y lo que daba cada modelo para ellas."""
        inici = dt.datetime(2026, 9, 14)
        with open(NV.OBSERVATS, "w", encoding="utf-8") as f:
            f.write("fins,nuvols,capes,metars\n")
            for k in range(dies * 24):
                f.write(f"{(inici + dt.timedelta(hours=k)):%Y-%m-%dT%H:%M},{observat},{capes},x\n")
        with open(os.path.join(self.dir, "casa-2026-09.jsonl"), "w", encoding="utf-8") as f:
            for k in range(dies * 24):
                fins = f"{(inici + dt.timedelta(hours=k)):%Y-%m-%dT%H:%M}"
                f.write(json.dumps({"hores": [dict(fins=fins, **previst)]}) + "\n")

    def test_amb_poques_hores_no_canvia(self):
        self.registra(5, 80, {"nuvols_arome": 0, "nuvols_icon_eu": 80, "nuvols_ecmwf": 0, "nuvols_gfs": 0})
        estat = NV.verifica(dt.date(2026, 10, 13), avisa=False)
        self.assertEqual(estat["pesos"], NV.per_defecte())
        self.assertEqual(estat["comparacio"]["hores"], 120)

    def test_amb_un_mes_tria_el_que_encerta(self):
        self.registra(29, 80, {"nuvols_arome": 0, "nuvols_icon_eu": 80, "nuvols_ecmwf": 0, "nuvols_gfs": 0})
        estat = NV.verifica(dt.date(2026, 10, 13), avisa=False)
        self.assertEqual(estat["pesos"], {"arome": 0.0, "icon_eu": 1.0, "ecmwf": 0.0, "gfs": 0.0})
        self.assertEqual(estat["comparacio"]["error_icon_eu"], 0.0)
        # Y se usa al día siguiente.
        self.assertEqual(NV.pesos()["icon_eu"], 1.0)

    def test_sense_capes_compten_els_nuvols_baixos(self):
        # CAVOK: no hay nubes bajas, pero puede haber altas. GFS da el cielo
        # tapado de nubes altas (no se le cuenta como fallo); AROME da nubes
        # bajas que no hay.
        self.registra(29, 0, {"nuvols_arome": 60, "nuvols_icon_eu": 60, "nuvols_ecmwf": 60, "nuvols_gfs": 100,
                              "nuvols_baixos_arome": 60, "nuvols_baixos_icon_eu": 0,
                              "nuvols_baixos_ecmwf": 0, "nuvols_baixos_gfs": 0}, capes=0)
        c = NV.verifica(dt.date(2026, 10, 13), avisa=False)["comparacio"]
        self.assertEqual((c["error_arome"], c["error_gfs"]), (60.0, 0.0))

    def test_sense_millora_clara_no_canvia(self):
        # Cada modelo acierta unos días y falla otros, al azar: la mezcla
        # ajustada no gana de forma segura a la de todos iguales.
        inici = dt.datetime(2026, 9, 14)
        rng = np.random.default_rng(4)
        with open(NV.OBSERVATS, "w", encoding="utf-8") as fo, \
                open(os.path.join(self.dir, "casa-2026-09.jsonl"), "w", encoding="utf-8") as fp:
            fo.write("fins,nuvols,capes,metars\n")
            for k in range(29 * 24):
                fins = f"{(inici + dt.timedelta(hours=k)):%Y-%m-%dT%H:%M}"
                o = float(rng.uniform(0, 100))
                fo.write(f"{fins},{o},1,x\n")
                prev = {f"nuvols_{m}": float(np.clip(o + rng.normal(0, 30), 0, 100)) for m in NV.MODELS}
                fp.write(json.dumps({"hores": [dict(fins=fins, **prev)]}) + "\n")
        estat = NV.verifica(dt.date(2026, 10, 13), avisa=False)
        self.assertLess(estat["comparacio"]["seguretat"], NV.SEGURETAT)
        self.assertEqual(estat["pesos"], NV.per_defecte())

    def test_atura(self):
        self.registra(29, 80, {"nuvols_arome": 0, "nuvols_icon_eu": 80, "nuvols_ecmwf": 0, "nuvols_gfs": 0})
        open(os.path.join(self.dir, "atura"), "w").close()
        self.assertEqual(NV.verifica(dt.date(2026, 10, 13), avisa=False)["pesos"], NV.per_defecte())

    def test_avisa_si_no_arriben_observacions(self):
        self.registra(1, 50, {})
        self.assertIsNotNone(NV.sense_observacions(dt.datetime(2026, 10, 13, 9).astimezone()))
        self.assertIsNone(NV.sense_observacions(dt.datetime(2026, 9, 15, 9).astimezone()))

    def test_apunta_les_hores_tancades(self):
        obs = NV.llegeix(lambda url: json.dumps([metar("13:30", ["SCT"]), metar("14:00", ["OVC"]),
                                                 metar("14:30", ["BKN"])]))
        NV.apunta(obs, dt.datetime(2026, 10, 13, 16, 40).astimezone())
        with open(NV.OBSERVATS, encoding="utf-8") as f:
            linies = f.read().splitlines()
        self.assertEqual(linies[0], "fins,nuvols,capes,metars")
        self.assertEqual([l.split(",")[:3] for l in linies[1:]], [["2026-10-13T16:00", "72", "1"]])


if __name__ == "__main__":
    unittest.main()
