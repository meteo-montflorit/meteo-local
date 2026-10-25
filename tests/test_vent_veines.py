# SPDX-License-Identifier: AGPL-3.0-or-later
"""El viento de ahora estimado con las estaciones vecinas (vent_veines.py,
ADR 0064), sin red."""
import datetime as dt
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vent_veines as VV  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=2))


def t(hhmm, dia=10):
    h, m = map(int, hhmm.split(":"))
    return dt.datetime(2026, 10, dia, h, m, tzinfo=TZ)


def lectures(inici, n, vent, ratxa=None, pas=5):
    return [{"t": inici + dt.timedelta(minutes=pas * k), "vent": vent, "ratxa": ratxa if ratxa is not None else vent + 3}
            for k in range(n)]


def sintetic(dies=4, seed=1):
    """Medias horas en que Sant Cugat es el doble del Puig, la del nordeste
    la mitad con ruido, y la de la riera casi siempre cero."""
    rnd = random.Random(seed)
    files = []
    inici = dt.datetime(2026, 10, 1, 0, 0)
    for k in range(dies * 48):
        fin = inici + dt.timedelta(minutes=30 * (k + 1))
        xv = 2 + 18 * rnd.random()
        files.append({"fins": fin.strftime("%Y-%m-%dT%H:%M"),
                      "XV": xv, "XV_ratxa": xv * 1.8, "XF": xv + rnd.uniform(-3, 3), "XF_ratxa": xv * 1.8,
                      "ICERDA18": xv / 2 + rnd.uniform(-0.3, 0.3), "ICERDA18_ratxa": xv * 0.9,
                      "ICERDA48": xv / 2.5 + rnd.uniform(-1, 1), "ICERDA48_ratxa": xv * 0.7,
                      "ICERDA6": 0.0, "ICERDA6_ratxa": 0.0,
                      "ICERDA28": None, "ICERDA28_ratxa": None})
    return files


class MitgesHores(unittest.TestCase):
    def test_veina_completa_i_incompleta(self):
        # De 14:00 a 14:30, sis lectures (la de les 14:00 és de la mitja hora anterior);
        # de 14:30 a 15:00, només tres: no compta.
        fs = lectures(t("14:05"), 6, 4.0, 9.0) + lectures(t("14:35"), 3, 8.0)
        fs[2]["vent"], fs[3]["ratxa"] = 7.0, 15.0
        m = VV.mitges_hores_veina(fs)
        self.assertEqual(list(m), [t("14:30")])
        self.assertEqual(m[t("14:30")], (4.5, 15.0))

    def test_apunta_no_esborra_les_altres_columnes(self):
        ruta = os.path.join(tempfile.mkdtemp(), "vent.csv")
        VV.apunta({"ICERDA18": {t("14:30"): (4.5, 15.0)}}, ruta)
        VV.apunta({"XV": {t("14:30"): (10.0, 20.0), t("15:00"): (11.0, 22.0)}}, ruta)
        files = VV.llegeix(ruta)
        self.assertEqual(len(files), 2)
        self.assertEqual((files[0]["ICERDA18"], files[0]["XV"], files[0]["XV_ratxa"]), (4.5, 10.0, 20.0))
        self.assertIsNone(files[1]["ICERDA18"])

    def test_portal_en_km_h_i_hora_local(self):
        dades = [{"data_lectura": "2026-10-10T12:00:00.000", "codi_variable": "30", "valor_lectura": "2.5"},
                 {"data_lectura": "2026-10-10T12:00:00.000", "codi_variable": "50", "valor_lectura": "5.0"}]
        m = VV.portal("XV", t("00:00"), lector=lambda url: dades)
        fin = dt.datetime(2026, 10, 10, 12, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(m[fin], (9.0, 18.0))


class Aprendre(unittest.TestCase):
    def test_tria_les_veines_que_segueixen_sant_cugat(self):
        a = VV.ajusta(sintetic())
        self.assertTrue(a["ICERDA18"]["compta"])
        self.assertAlmostEqual(a["ICERDA18"]["factor"], 2.0, delta=0.1)
        self.assertTrue(a["ICERDA48"]["compta"])
        # La de la riera sempre a zero i la que no té dades no compten.
        self.assertFalse(a["ICERDA6"]["compta"])
        self.assertFalse(a["ICERDA28"]["compta"])
        # Pesa més la que s'equivoca menys.
        mitja, usades = VV.estima(a, {"ICERDA18": 5.0, "ICERDA48": 4.0, "ICERDA6": 0.0})
        self.assertEqual(usades, ["ICERDA18", "ICERDA48"])
        self.assertAlmostEqual(mitja, 10.0, delta=0.5)
        self.assertEqual(VV.estima(a, {"ICERDA6": 3.0}), (None, []))

    def test_poques_dades_no_compten(self):
        a = VV.ajusta(sintetic(dies=1))
        self.assertFalse(any(i["compta"] for i in a.values()))

    def test_validacio_i_avis_una_sola_vegada(self):
        files = sintetic()
        v = VV.valida(files)
        self.assertLess(v["estimacio"], v["sabadell"])
        self.assertGreater(v["ventoses"], VV.MIN_VENTOSES)
        reg, dir_ = tempfile.mkdtemp(), tempfile.mkdtemp()
        # Sense registre, no fa res (ni llegeix la xarxa).
        self.assertIsNone(VV.apren(avisa=False, registre=reg, directori=dir_))
        ruta = os.path.join(reg, os.path.basename(VV.CSV))
        VV.apunta({e: {dt.datetime.fromisoformat(f["fins"]).astimezone(): (f[e], f[f"{e}_ratxa"])
                       for f in files if f[e] is not None}
                   for e in ("XV", "XF", "ICERDA18", "ICERDA48", "ICERDA6")}, ruta)
        portal = VV.portal
        VV.portal = lambda codi, desde, lector=None: {}
        try:
            ara = dt.datetime(2026, 10, 6, 12).astimezone()
            model = VV.apren(ara, avisa=False, registre=reg, directori=dir_)
            self.assertTrue(model["mitja"]["veines"]["ICERDA18"]["compta"])
            self.assertTrue(os.path.exists(os.path.join(dir_, "avis-vent-veines")))
            self.assertIsNone(VV.avis(model, os.path.join(dir_, "avis-vent-veines")))
        finally:
            VV.portal = portal


class Ara(unittest.TestCase):
    def setUp(self):
        a = VV.ajusta(sintetic())
        self.model = {"mitja": {"veines": a}, "ratxa": {"veines": VV.ajusta(sintetic(), "ratxa")}}

    def test_estima_amb_la_darrera_mitja_hora(self):
        veines = [{"estacio": "ICERDA18", "files": lectures(t("13:40"), 6, 1.0) + lectures(t("14:10"), 6, 5.0)},
                  {"estacio": "ICERDA6", "files": lectures(t("14:10"), 6, 0.0)}]
        v = VV.ara(veines, self.model, ahora=t("14:36"))
        self.assertEqual((v["font"], v["estacions"]), ("veines", ["ICERDA18"]))
        self.assertAlmostEqual(v["mitja"], 10.0, delta=0.5)
        self.assertEqual(v["fins"], VV.H.clau(t("14:35")))

    def test_sense_lectures_recents_ni_model(self):
        veines = [{"estacio": "ICERDA18", "files": lectures(t("12:00"), 6, 5.0)}]
        self.assertIsNone(VV.ara(veines, self.model, ahora=t("14:36")))
        self.assertIsNone(VV.ara(veines, {}, ahora=t("12:30")))


if __name__ == "__main__":
    unittest.main()
