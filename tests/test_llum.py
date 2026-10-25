# SPDX-License-Identifier: AGPL-3.0-or-later
"""Talls de llum a prop (llum.py, ADR 0072), la consulta del bot i la prova diària (sense xarxa)."""
import datetime as dt
import os
import sys
import tempfile
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
sys.path.insert(0, os.path.join(ARREL, "bot"))
import bot as B  # noqa: E402
import llum as LL  # noqa: E402

ARA = dt.datetime(2026, 10, 11, 7, 30).astimezone()


def tall(tipus, clients, y, x, inici="10/10/2026 23:12", fins="11/10/2026 08:15",
         nota="No hay información adicional en estos momentos."):
    return {"attributes": {"service_type": tipus, "service_des_ca": None, "service_des_es": "Avería BT",
                           "des_cause_ca": None, "des_cause_es": "Avería", "affected_client": clients,
                           "interruption_date": inici, "reposition_date": fins, "note": nota,
                           "update_time": "11/10/2026 07:00", "municipality": "Cerdanyola del Vallès"},
            "geometry": {"x": x, "y": y}}


class Llum(unittest.TestCase):
    def test_nomes_els_del_barri(self):
        # ADR 0072: dins dels límits de Montflorit o a 150 m o menys; els altres, no.
        d = {"features": [tall("LV", 3, 41.4850, 2.1340),      # l'altre costat de la riera, dins
                          tall("MV", 45, 41.4800, 2.1330),     # Collserola, dins
                          tall("MV", 7, 41.4835, 2.1300),      # vora el límit
                          tall("MV", 9, 41.4895, 2.1330),      # Cerdanyola, fora
                          tall("MV", 2, 41.4719, 2.0801),      # Sant Cugat, fora
                          {"attributes": {}, "geometry": {}}]}
        r = LL.calcula(ARA, d)
        self.assertEqual(sorted(t["clients"] for t in r["talls"]), [3, 7, 45])
        self.assertEqual({t["clients"]: t["on"] for t in r["talls"]}, {3: "dins", 45: "dins", 7: "vora"})
        self.assertTrue(next(t for t in r["talls"] if t["clients"] == 3)["programat"])
        self.assertEqual(next(t for t in r["talls"] if t["clients"] == 45)["inici"], "2026-10-10T21:12Z")  # 23:12 de Madrid

    def test_text_del_bot(self):
        d = {"features": [tall("MV", 45, 41.4800, 2.1330,
                               nota="Su suministro está afectado por una incidencia,  un equipo revisa la zona."),
                          tall("LV", 1, 41.4835, 2.1300, inici="11/10/2026 07:00", fins="11/10/2026 12:00")]}
        dades = {"generat": ARA.isoformat(), "llum": LL.calcula(ARA, d)}
        ca = B.text_llum_bot(dades, "ca", ARA)
        self.assertIn("<b>Talls de llum a Montflorit</b>", ca)
        self.assertIn("<b>Avaria</b> (al barri; carrers probables: Carrer de Catalunya o Carrer de Montflorit): "
                      "45 clients sense llum des del 10/10 a les 23:12; previst fins a "
                      "les 08:15. «Su suministro está afectado por una incidencia, un equipo revisa la zona.»", ca)
        # La nota que no diu res, fora; un sol client, en singular.
        self.assertIn("<b>Treballs programats</b> (al límit del barri; carrers probables: Carrer de Sant Isidre o "
                      "Carrer de Sant Cugat): 1 client sense llum des de les 07:00; previst fins a les 12:00.\n", ca)
        self.assertIn("Els carrers són una estimació", ca)
        self.assertIn("center=2.133,41.481&amp;level=15&amp;locale=ca", ca)
        self.assertIn('Talls programats per carrer: <a href="https://wtp-pro.endesa.com/#/wtp">cercador d\'Endesa</a> '
                      '(Cerdanyola només hi surt quan en té)', ca)
        es = B.text_llum_bot({"generat": ARA.isoformat(), "llum": {"hora": ARA.isoformat(), "talls": []}}, "es", ARA)
        self.assertIn("Ningún corte de luz en Montflorit.", es)
        self.assertNotIn("estimación", es)
        self.assertIn("locale=es", es)
        self.assertIn("Ara no hi ha dades", B.text_llum_bot({"generat": ARA.isoformat(), "llum": None}, "ca", ARA))

    def test_carrer_probable(self):
        # ADR 0072: el més proper i, si n'hi ha un altre a 40 m més o menys, també; cap si és lluny.
        vies = {"A": [[(41.0, 2.0), (41.0, 2.01)]], "B": [[(41.0003, 2.0), (41.0003, 2.01)]],
                "C": [[(41.003, 2.0), (41.003, 2.01)]]}
        self.assertEqual(LL.carrers_probables((41.0001, 2.005), vies), ["A", "B"])   # 11 i 22 m
        self.assertEqual(LL.carrers_probables((41.0029, 2.005), vies), ["C"])        # 11 m; B a 289 m
        self.assertEqual(LL.carrers_probables((41.02, 2.005), vies), [])
        # Amb els carrers de veritat: Sant Jeroni i Santa Margarida, a l'altre costat de la riera.
        self.assertEqual(set(LL.carrers_probables((41.4843, 2.1335))), {"Carrer de Santa Margarida", "Carrer de Sant Jeroni"})

    def test_avis_quan_apareix_i_quan_s_acaba(self):
        import avisos_bot as AB
        tall = {"id": "D1:11/10/2026 07:00", "on": "dins", "carrers": ["Carrer de Sant Jeroni"], "programat": False,
                "clients": 45, "fins": "2026-10-11T09:00+02:00"}
        petit = {**tall, "id": "D2:x", "clients": 1}
        estat = {}
        passa = lambda talls, m=0: [a for a in AB.decideix(estat, {"llum": {"talls": talls}}, ARA + dt.timedelta(minutes=m))
                                    if a["tipus"] == "llum"]
        self.assertEqual(passa([]), [])                       # la primera vegada, només s'apunta
        nous = passa([tall, petit], 6)
        self.assertEqual(len(nous), 1)                        # el d'un client no s'anuncia
        self.assertTrue(nous[0]["ca"].startswith("🔌 <b>e-distribució: tall de llum a Montflorit, Carrer de Sant Jeroni (carrer probable)</b>"))
        self.assertIn("Els carrers són una estimació", nous[0]["ca"])
        self.assertIn("&amp;level=15", nous[0]["ca"])
        self.assertNotIn("episodi", nous[0])                  # no va a «Perill»
        self.assertEqual(passa([tall], 12), [])
        self.assertEqual(AB.decideix(estat, {"llum": None}, ARA), [])   # e-distribució no respon: res
        fi = passa([], 18)
        self.assertTrue(fi[0]["ca"].startswith("🟢 <b>e-distribució: tall de llum a Montflorit, Carrer de Sant Jeroni (carrer probable): ja no consta</b>"))

    def test_prova_diaria(self):
        bona = lambda url, p: ({"fields": [{"name": n} for n in LL.CAMPS_NECESSARIS]} if p == {"f": "json"}
                               else {"count": 3})
        canviada = lambda url, p: {"fields": [{"name": "affected_client"}]}
        self.assertIsNone(LL.prova(bona))
        self.assertIn("falten camps", LL.prova(canviada))
        with tempfile.TemporaryDirectory() as dir:
            marca = os.path.join(dir, "llum-falla")
            self.assertIsNotNone(LL.comprova(marca, avisa=False, get_json=canviada))
            self.assertTrue(os.path.exists(marca))
            self.assertIsNone(LL.comprova(marca, avisa=False, get_json=bona))
            self.assertFalse(os.path.exists(marca))


if __name__ == "__main__":
    unittest.main()
