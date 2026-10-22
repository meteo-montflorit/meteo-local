# SPDX-License-Identifier: AGPL-3.0-or-later
"""La qualitat de l'aire (aire.py, ADR 0054): les mesures de la XVPCA, la
correcció guardada un dia, el que queda d'avui i el que passa si la xarxa de
la Generalitat falla, sense xarxa."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import aire as A  # noqa: E402

ARA = dt.datetime(2026, 10, 9, 10, 20).astimezone()


def hores_dia(dia="2026-10-09"):
    return [f"{dia}T{h:02d}:00" for h in range(24)]


class Index(unittest.TestCase):
    def test_sense_concentracio_no_hi_ha_index(self):
        self.assertIsNone(A.index_de("ozone", None))
        self.assertIsNone(A.categoria(None))

    def test_trams_i_mes_enlla_de_100(self):
        self.assertEqual(A.index_de("pm2_5", 5), 20)
        self.assertEqual(A.index_de("pm2_5", 140), 100)
        # Per sobre de l'últim tram es continua amb el pendent de l'últim.
        self.assertEqual(A.index_de("pm2_5", 190), 120)
        self.assertEqual(A.categoria(20), "bona")
        self.assertEqual(A.categoria(21), "raonablement_bona")
        self.assertEqual(A.categoria(100), "molt_desfavorable")
        self.assertEqual(A.categoria(101), "extremadament_desfavorable")

    def test_estacions_a_prop(self):
        self.assertLess(A.km(A.C.CASA, A.ESTACIONS["Montcada i Reixac"]), 5)
        self.assertEqual(A.km(A.C.CASA, A.C.CASA), 0)


class Xarxa(unittest.TestCase):
    def test_get_json_amb_parametres(self):
        vist = {}

        def urlopen(req, timeout):
            vist["url"], vist["timeout"] = req.full_url, timeout
            return io.BytesIO(b'[1, 2]')
        with mock.patch.object(A.urllib.request, "urlopen", urlopen):
            self.assertEqual(A.get_json("https://x/y", {"a": "b c"}), [1, 2])
        self.assertEqual(vist["url"], "https://x/y?a=b+c")
        self.assertEqual(vist["timeout"], 40)

    def test_model_demana_cams_i_passa_a_hora_local(self):
        resposta = {"utc_offset_seconds": 7200, "hourly": {"time": ["2026-10-09T10:00"], "ozone": [50]}}
        with mock.patch.object(A, "get_json", return_value=resposta) as g:
            r = A.model(ARA, 30)
        url, p = g.call_args[0]
        self.assertEqual(url, A.API)
        self.assertEqual(p["domains"], "cams_europe")
        self.assertEqual(p["past_days"], 30)
        self.assertEqual(p["hourly"].split(","), list(A.CONTAMINANTS))
        self.assertEqual(r["hourly"]["time"], ["2026-10-09T10:00"])

    def test_mesures_xvpca_filtra_estacions_i_contaminants(self):
        with mock.patch.object(A, "get_json", return_value=[]) as g:
            A.mesures_xvpca("2026-09-08")
        url, p = g.call_args[0]
        self.assertEqual(url, A.XVPCA)
        self.assertIn("data >= '2026-09-08T00:00:00.000'", p["$where"])
        self.assertIn("'Montcada i Reixac'", p["$where"])
        self.assertIn("'PM2.5'", p["$where"])


class PerHora(unittest.TestCase):
    def test_hora_del_final_del_periode(self):
        files = [{"data": "2026-10-08T00:00:00.000", "nom_estacio": "Barberà del Vallès", "contaminant": "NO2",
                  "h01": "12", "h02": "", "h04": "7.5", "h24": "3"},
                 {"data": "2026-10-08T00:00:00.000", "nom_estacio": "Barberà del Vallès", "contaminant": "CO",
                  "h01": "0.3"}]
        r = A.per_hora(files)
        self.assertEqual(r, {("Barberà del Vallès", "nitrogen_dioxide", "2026-10-08T01:00"): 12.0,
                             ("Barberà del Vallès", "nitrogen_dioxide", "2026-10-08T04:00"): 7.5,
                             # La h24 és la mitjanit de l'endemà.
                             ("Barberà del Vallès", "nitrogen_dioxide", "2026-10-09T00:00"): 3.0})


class ValidaFactor(unittest.TestCase):
    def test_un_sol_dia_no_es_pot_validar(self):
        self.assertEqual(A.valida_factor([("2026-10-01T01:00", 10, 20), ("2026-10-01T02:00", 10, 20)]),
                         (None, None, None))

    def test_hores_sense_model_no_compten(self):
        temps = [f"2026-10-{d:02d}T{h:02d}:00" for d in (1, 2, 3, 4) for h in range(24)]
        model = {"time": temps, "nitrogen_dioxide": [None] * 24 + [20.0] * 72}
        mesures = {(e, "nitrogen_dioxide", t): 10.0 for t in temps
                   for e in ("Barberà del Vallès", "Sant Cugat del Vallès")}
        r = A.factors(model, mesures)
        self.assertEqual(r["nitrogen_dioxide"]["hores"], 72)
        self.assertEqual(r["nitrogen_dioxide"]["factor"], 0.5)


class Correccio(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        p = mock.patch.object(A, "CACHE", os.path.join(self.dir.name, "aire-correccio.json"))
        p.start()
        self.addCleanup(p.stop)

    def calcula(self, ara=ARA):
        with mock.patch.object(A, "mesures_xvpca", return_value=[]) as mx, \
                mock.patch.object(A, "model", return_value={"hourly": {"time": []}}) as mo, \
                mock.patch.object(A, "factors", return_value=({"ozone": {"factor": 0.8}}, {"pm10": {}})):
            r = A.correccio(ara)
        return r, mx, mo

    def test_calcula_i_guarda(self):
        r, mx, mo = self.calcula()
        self.assertEqual(r, {"dia": "2026-10-09", "hora": ARA.isoformat(timespec="minutes"),
                             "factors": {"ozone": {"factor": 0.8}}, "descartats": {"pm10": {}}})
        self.assertEqual(mx.call_args[0][0], "2026-09-08")       # 31 dies enrere
        self.assertEqual(mo.call_args[0][1], A.DIES_CORRECCIO)
        with open(A.CACHE, encoding="utf-8") as f:
            self.assertEqual(json.load(f), r)

    def test_el_mateix_dia_i_recent_no_es_torna_a_calcular(self):
        self.calcula()
        with mock.patch.object(A, "mesures_xvpca", side_effect=AssertionError("no")):
            r = A.correccio(ARA + dt.timedelta(hours=2))
        self.assertEqual(r["factors"], {"ozone": {"factor": 0.8}})

    def test_passades_tres_hores_o_un_altre_dia_es_recalcula(self):
        self.calcula()
        _, mx, _ = self.calcula(ARA + dt.timedelta(hours=3))
        mx.assert_called_once()
        _, mx, _ = self.calcula(ARA + dt.timedelta(days=1))
        mx.assert_called_once()

    def test_fitxer_espatllat_es_recalcula(self):
        with open(A.CACHE, "w") as f:
            json.dump({"dia": "2026-10-09"}, f)      # sense «hora»: KeyError
        _, mx, _ = self.calcula()
        mx.assert_called_once()

    def test_sense_carpeta_no_es_guarda(self):
        with mock.patch.object(A, "CACHE", os.path.join(self.dir.name, "no", "hi", "es.json")):
            r, _, _ = self.calcula()
            self.assertFalse(os.path.exists(A.CACHE))
        self.assertEqual(r["dia"], "2026-10-09")


class Llegeix(unittest.TestCase):
    def dades(self):
        t = hores_dia() + ["2026-10-10T00:00"]
        n = len(t)
        no2 = [20.0] * n
        no2[15] = 80.0          # el pitjor, a les 15
        return {"hourly": {"time": t, "nitrogen_dioxide": no2, "ozone": [50.0] * n,
                           "pm10": [None] * n, "pm2_5": None}}

    def test_el_que_queda_d_avui(self):
        r = A.llegeix(self.dades(), ARA)
        self.assertEqual(r["hora"], "2026-10-09T10:00")
        self.assertEqual([x["hora"] for x in r["hores"]][-1], "2026-10-09T23:00")   # demà no
        self.assertEqual(len(r["hores"]), 14)
        self.assertEqual(r["contaminants"], {"nitrogen_dioxide": 33, "ozone": 17})
        self.assertEqual(r["contaminant"], "nitrogen_dioxide")
        self.assertEqual(r["categoria"], "raonablement_bona")
        self.assertEqual(r["pitjor"], {"hora": "2026-10-09T15:00", "index": 70, "categoria": "desfavorable"})
        self.assertFalse(r["corregit"])
        self.assertEqual(r["factors"], {})

    def test_amb_factors_es_corregeix(self):
        corr = {"factors": {"nitrogen_dioxide": {"factor": 0.25}}}
        r = A.llegeix(self.dades(), ARA, corr)
        self.assertTrue(r["corregit"])
        self.assertEqual(r["contaminants"]["nitrogen_dioxide"], 10)
        self.assertEqual(r["contaminant"], "ozone")
        self.assertEqual(r["factors"], corr["factors"])

    def test_sense_hores_d_avui_es_none(self):
        self.assertIsNone(A.llegeix(self.dades(), ARA + dt.timedelta(days=2)))


class Calcula(unittest.TestCase):
    def test_si_la_xarxa_de_la_generalitat_falla_es_el_model_tal_qual(self):
        d = {"hourly": {"time": hores_dia(), "ozone": [50.0] * 24}}
        with mock.patch.object(A, "correccio", side_effect=OSError("caiguda")), \
                mock.patch.object(A, "model", return_value=d):
            r = A.calcula(ARA)
        self.assertFalse(r["corregit"])
        self.assertEqual(r["index"], 17)

    def test_amb_correccio_i_l_hora_d_ara(self):
        avui = dt.date.today().isoformat()
        d = {"hourly": {"time": hores_dia(avui), "ozone": [50.0] * 24}}
        with mock.patch.object(A, "correccio", return_value={"factors": {"ozone": {"factor": 2}}}), \
                mock.patch.object(A, "model", return_value=d):
            r = A.calcula()
        self.assertTrue(r["corregit"])


if __name__ == "__main__":
    unittest.main()
