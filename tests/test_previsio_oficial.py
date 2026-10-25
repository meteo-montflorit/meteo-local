# SPDX-License-Identifier: AGPL-3.0-or-later
"""Las previsiones oficiales para Cerdanyola, apuntadas (previsio_oficial.py, ADR 0110)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import previsio_oficial as O  # noqa: E402
import prevision as P  # noqa: E402

METEOCAT = json.dumps({"codiMunicipi": "082665", "dies": [{"data": "2026-10-20Z", "variables": {
    "temp": {"unitat": "°C", "valors": [{"valor": "16.0", "data": "2026-10-20T00:00Z"},
                                         {"valor": "15.5", "data": "2026-10-20T01:00Z"}]},
    "precipitacio": {"unitat": "mm", "valor": [{"valor": "-0.0", "data": "2026-10-20T00:00Z"},
                                                {"valor": "1.2", "data": "2026-10-20T01:00Z"}]}}}]})
AEMET = json.dumps([{"elaborado": "2026-10-20T06:13:22", "prediccion": {"dia": [{
    "fecha": "2026-10-20T00:00:00",
    "temperatura": [{"value": "14", "periodo": "07"}, {"value": "16", "periodo": "09"}],
    "precipitacion": [{"value": "Ip", "periodo": "07"}, {"value": "0.4", "periodo": "09"}],
    "probPrecipitacion": [{"value": "30", "periodo": "0208"}, {"value": "0", "periodo": "2002"}]}]}}])
ARA = dt.datetime(2026, 10, 20, 9, 4, tzinfo=P.ZONA)


class Llegeix(unittest.TestCase):
    def test_meteocat_en_hora_local_i_sense_menys_zero(self):
        d = O.llegeix_meteocat(METEOCAT)
        self.assertEqual(d["t"], {"2026-10-20T00:00Z": 16.0, "2026-10-20T01:00Z": 15.5})
        self.assertEqual(d["mm"]["2026-10-20T00:00Z"], 0.0)
        self.assertEqual(str(d["mm"]["2026-10-20T00:00Z"]), "0.0")

    def test_aemet_amb_inapreciable_i_trams_que_passen_de_mitjanit(self):
        d = O.llegeix_aemet(AEMET)
        self.assertEqual(d["elaborat"], "2026-10-20T04:13Z")       # les 6:13 de Madrid, en UTC (ADR 0128)
        self.assertEqual(d["t"][O.P.clau_hora("2026-10-20T09:00")], 16.0)
        self.assertEqual(d["mm"][O.P.clau_hora("2026-10-20T07:00")], 0.0)
        self.assertEqual(d["p6"][O.P.clau_hora("2026-10-20T02:00")], [O.P.clau_hora("2026-10-20T08:00"), 30.0])
        self.assertEqual(d["p6"][O.P.clau_hora("2026-10-20T20:00")], [O.P.clau_hora("2026-10-21T02:00"), 0.0])


class Apunta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.vells = O.REGISTRE, O.ESTAT
        O.REGISTRE = self.dir.name
        O.ESTAT = os.path.join(self.dir.name, "estat.json")
        self.crides = []
        self.consultes = {"meteocat": lambda: self.crida("meteocat", O.llegeix_meteocat(METEOCAT)),
                          "aemet": lambda: self.crida("aemet", O.llegeix_aemet(AEMET))}

    def tearDown(self):
        O.REGISTRE, O.ESTAT = self.vells
        self.dir.cleanup()

    def crida(self, font, dades):
        self.crides.append(font)
        return dades

    def test_cada_font_al_seu_ritme_i_les_repetides_curtes(self):
        self.assertEqual(O.apunta(ARA, self.consultes, lambda _: False), {"meteocat": "nova", "aemet": "nova"})
        self.assertEqual(O.apunta(ARA + dt.timedelta(minutes=30), self.consultes, lambda _: False), {})
        self.assertEqual(O.apunta(ARA + dt.timedelta(hours=1), self.consultes, lambda _: False), {"aemet": "repetida"})
        r = O.registre(self.dir.name)
        self.assertEqual(len(r["aemet"]), 2)
        self.assertIs(r["aemet"][1][1], r["aemet"][0][1])
        self.assertEqual(self.crides, ["meteocat", "aemet", "aemet"])

    def test_meteocat_cedeix_a_la_reserva_dels_avisos_i_te_sostre(self):
        self.assertEqual(O.apunta(ARA, self.consultes, lambda _: True)["meteocat"], "saltada")
        estat = {"meteocat": {"mes": "2026-10", "consultes": O.METEOCAT_MES}}
        with open(O.ESTAT, "w") as f:
            json.dump(estat, f)
        self.assertEqual(O.apunta(ARA, self.consultes, lambda _: False)["meteocat"], "saltada")
        self.assertNotIn("meteocat", self.crides)

    def test_un_error_no_para_l_altra_font(self):
        consultes = {**self.consultes, "meteocat": lambda: 1 / 0}
        fet = O.apunta(ARA, consultes, lambda _: False)
        self.assertEqual(fet, {"meteocat": "error", "aemet": "nova"})


if __name__ == "__main__":
    unittest.main()
