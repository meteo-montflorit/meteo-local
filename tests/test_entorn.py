# SPDX-License-Identifier: AGPL-3.0-or-later
"""Incendios cerca y Pla Alfa (entorn.py, ADR 0046), y sus avisos (sin red)."""
import datetime as dt
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import avisos_bot as AB  # noqa: E402
import entorn as EN  # noqa: E402

ARA = dt.datetime(2026, 10, 8, 13, 0).astimezone()


def feature(desc, municipi, y, x, fi=None, gid="g1"):
    return {"attributes": {"GlobalID": gid, "TAL_DESC_ALARMA2": desc, "MUNICIPI_SIG": municipi,
                           "ACT_DAT_INICI": int(ARA.timestamp() * 1000), "ACT_DAT_FI": fi,
                           "ACT_NUM_VEH": 4, "COM_FASE": None}, "geometry": {"x": x, "y": y}}


class Fonts(unittest.TestCase):
    def test_incendis_forestals_en_curs(self):
        d = {"features": [feature("Incendi vegetació forestal", "Sant Cugat del Vallès", 41.47, 2.09, gid="a"),
                          feature("Incendi vegetació urbana", "Cerdanyola del Vallès", 41.49, 2.14, gid="b"),
                          feature("Incendi vegetació forestal", "Ripollet", 41.50, 2.16, fi=1, gid="c")]}
        r = EN.incendis(d, collserola=lambda y, x: True)
        self.assertEqual([i["id"] for i in r], ["a"])      # ni l'urbà ni l'acabat
        self.assertEqual(r[0]["municipi"], "Sant Cugat del Vallès")
        self.assertAlmostEqual(r[0]["km"], 3.9, delta=0.3)
        self.assertTrue(r[0]["collserola"])

    def test_obert_sense_vehicles_ni_canvis_es_dona_per_apagat(self):
        # 25-10-2026: un de Montcada va quedar obert amb 0 vehicles i sense cap
        # canvi des de les 17:15 del dia abans (ADR 0071).
        def foc(gid, vehicles, hores):
            f = feature("Incendi vegetació forestal", "Sant Cugat del Vallès", 41.47, 2.09, gid=gid)
            f["attributes"].update(ACT_NUM_VEH=vehicles,
                                   ACT_DAT_ACTUAL=int((ARA - dt.timedelta(hours=hores)).timestamp() * 1000))
            return f
        d = {"features": [foc("parat", 0, 4), foc("nou", 0, 1), foc("amb-vehicles", 3, 12)]}
        parats = {}
        r = EN.incendis(d, collserola=lambda y, x: True, parats=parats, ara=ARA)
        self.assertEqual(sorted(i["id"] for i in r), ["amb-vehicles", "nou"])
        self.assertEqual(parats, {"parat": (ARA - dt.timedelta(hours=4)).isoformat(timespec="minutes")})

    def test_nomes_els_que_interessen_al_barri(self):
        # ADR 0071 (Juanjo, 16-10-2026): Collserola a qualsevol distància i,
        # fora del parc, a 2 km o menys, sigui quin sigui el municipi.
        parc = {(41.40, 2.02), (41.46, 2.10)}                     # Molins i Sant Cugat, dins del parc
        f = "Incendi vegetació forestal"
        d = {"features": [feature(f, "Ripollet", 41.490, 2.148, gid="ripollet"),            # 1,4 km, sense parc
                          feature(f, "Badia del Vallès", 41.505, 2.115, gid="badia"),
                          feature(f, "Montcada i Reixac", 41.483, 2.165, gid="montcada"),  # 2,5 km, fora del parc
                          feature(f, "Montcada i Reixac", 41.483, 2.180, gid="montcada-lluny"),  # 3,8 km
                          feature(f, "Molins de Rei", 41.40, 2.02, gid="molins"),          # 13 km
                          feature(f, "Sant Cugat del Vallès", 41.46, 2.10, gid="stcugat"),
                          feature(f, "Cerdanyola del Vallès", 41.50, 2.14, gid="cerdanyola")]}   # 2,04 km, fora del parc
        r = EN.incendis(d, collserola=lambda y, x: (y, x) in parc)
        self.assertEqual(sorted(i["id"] for i in r), ["molins", "ripollet", "stcugat"])
        self.assertEqual(r[-1]["id"], "molins")                  # del més a prop al més lluny

    def test_el_parc_sense_forats(self):
        # Juanjo, 16-10-2026: els enclavaments (les Planes, Can Cerdà…) també compten.
        anell = [[2.0, 41.0], [2.1, 41.0], [2.1, 41.1], [2.0, 41.1]]
        self.assertTrue(EN.dins_anells(41.05, 2.05, [anell], 0.2))      # al mig, on hi hauria un forat
        self.assertTrue(EN.dins_anells(41.05, 2.1015, [anell], 0.2))    # a uns 130 m del límit
        self.assertFalse(EN.dins_anells(41.05, 2.11, [anell], 0.2))     # a 840 m
        self.assertFalse(EN.dins_anells(41.2, 2.05, [anell], 0.2))

    def test_interessa(self):
        self.assertTrue(EN.interessa("Montcada i Reixac", 2.0, False))
        self.assertFalse(EN.interessa("Montcada i Reixac", 2.1, False))
        self.assertTrue(EN.interessa("Molins de Rei", 14, True))
        self.assertTrue(EN.interessa("Ripollet", 1.5, False))
        self.assertFalse(EN.interessa("Cerdanyola del Vallès", 7, False))
        self.assertTrue(EN.interessa("Cerdanyola del Vallès", 1.9, False))

    def test_pla_alfa_el_5_no_es_cap_nivell(self):
        respostes = {"avui": 4, "dema": 5}
        def get(url, params=None):
            if params == {"f": "json"}:
                return {"editingInfo": {"lastEditDate": int(ARA.timestamp() * 1000)}}
            if "Espai_prot" in str(params):
                return {"features": [{"attributes": {"Espai_prot": "Parc Natural de la Serra de Collserola"}}]}
            dia = "avui" if "Avui" in url else "dema"
            return {"features": [{"attributes": {"PERIL_M": respostes[dia]}}]}
        with mock.patch.object(EN, "get", get):
            r = EN.pla_alfa(ARA)
        self.assertEqual((r["avui"], r["dema"]), (4, None))
        self.assertEqual(len(r["tancaments"]), 2)

    def test_pla_alfa_capa_vella_no_val(self):
        vell = int((ARA - dt.timedelta(days=50)).timestamp() * 1000)
        def get(url, params=None):
            return {"editingInfo": {"lastEditDate": vell}} if params == {"f": "json"} else {"features": []}
        with mock.patch.object(EN, "get", get):
            self.assertEqual(EN.pla_alfa(ARA), {"avui": None, "dema": None, "tancaments": []})


class Avisos(unittest.TestCase):
    def passada(self, estat, incendis, minuts=0):
        salida = {"entorn": {"incendis": incendis, "pla_alfa": {}}}
        return [a for a in AB.decideix(estat, salida, ARA + dt.timedelta(minutes=minuts)) if a["tipus"] == "perill"]

    def test_la_primera_vegada_nomes_s_apunta(self):
        estat = {}
        foc = [{"id": "x", "municipi": "Ripollet", "km": 2.0, "inici": ARA.isoformat()}]
        self.assertEqual(self.passada(estat, foc), [])
        self.assertEqual(self.passada(estat, foc, 15), [])

    def test_incendi_a_prop_i_quan_s_acaba(self):
        estat = {}
        self.passada(estat, [])
        foc = [{"id": "x", "municipi": "Sant Cugat del Vallès", "km": 3.2, "inici": ARA.isoformat(), "vehicles": 4}]
        nous = self.passada(estat, foc, 6)
        self.assertEqual(len(nous), 1)
        self.assertTrue(nous[0]["ca"].startswith("🔥 <b>Bombers: incendi forestal a Sant Cugat del Vallès, a 3,2 km de Montflorit</b>"))
        self.assertIn("Bombers: incendio forestal en Sant Cugat del Vallès, a 3,2 km de Montflorit", nous[0]["es"])
        self.assertIn('<a href="https://interior.gencat.cat/es/arees_dactuacio/bombers/', nous[0]["es"])
        self.assertEqual(nous[0]["episodi"], "incendi:x")
        self.assertEqual(self.passada(estat, foc, 12), [])          # una sola vegada
        fi = self.passada(estat, [], 18)
        self.assertIn("ja no consta com a actiu", fi[0]["ca"])
        self.assertTrue(fi[0]["ca"].startswith("🟢"))

    def test_parat_es_diu_que_probablement_s_ha_apagat(self):
        estat = {}
        foc = [{"id": "x", "municipi": "Montcada i Reixac", "km": 4.1, "collserola": True, "inici": ARA.isoformat(),
                "vehicles": 0}]
        self.passada(estat, [])
        self.assertEqual(len(self.passada(estat, foc, 6)), 1)
        salida = {"entorn": {"incendis": [], "incendis_parats": {"x": ARA.isoformat()}, "pla_alfa": {}}}
        fi = [a for a in AB.decideix(estat, salida, ARA + dt.timedelta(hours=4)) if a["tipus"] == "perill"]
        self.assertTrue(fi[0]["ca"].startswith(
            "🟢 <b>Bombers: incendi al Parc de Collserola (Montcada i Reixac), a 4,1 km de Montflorit: "
            "probablement ja s'ha apagat</b>"))
        self.assertIn("sense cap vehicle i sense cap actualització des de les 13:00", fi[0]["ca"])
        self.assertIn("probablemente ya se ha apagado", fi[0]["es"])

    def test_sortir_de_la_zona_no_es_acabar(self):
        # 16-10-2026: en baixar a 2 km, un incendi de Cerdanyola a 2,6 km es va
        # anunciar «ja no consta com a actiu» sense estar apagat (ADR 0071).
        def passada(incendis, fora, minuts):
            salida = {"entorn": {"incendis": incendis, "incendis_fora": fora, "pla_alfa": {}}}
            return [a for a in AB.decideix(estat, salida, ARA + dt.timedelta(minutes=minuts)) if a["tipus"] == "perill"]
        estat = {}
        passada([], [], 0)
        foc = [{"id": "x", "municipi": "Cerdanyola del Vallès", "km": 1.8, "inici": ARA.isoformat()}]
        self.assertEqual(len(passada(foc, [], 6)), 1)
        AB.historial(estat, [{"tipus": "perill", "episodi": "incendi:x", "nivell": "incendi", "hora": ARA.isoformat(),
                              "ca": "🔥", "es": "🔥"}], ARA)
        self.assertEqual(passada([], ["x"], 12), [])                 # en curs, fora de la zona: res
        self.assertEqual(estat["entorn"]["fora"], ["x"])
        h = AB.historial(estat, [], ARA + dt.timedelta(minutes=12))
        self.assertTrue(h[-1]["fi"] and h[-1]["fi_ca"].startswith("Segons Bombers continua actiu"))
        self.assertTrue(h[-1]["fora_zona"])
        self.assertEqual(passada(foc, [], 18), [])                   # torna a la zona: no és nou
        self.assertEqual(passada([], [], 24)[0]["nivell"], "fi")      # ara sí que s'acaba
        self.assertEqual(passada([], [], 30), [])

    def test_a_collserola_es_diu_on_es(self):
        foc = {"id": "y", "municipi": "Molins de Rei", "km": 13.4, "collserola": True, "inici": ARA.isoformat()}
        t = AB.text_incendi(foc)
        self.assertTrue(t["ca"].startswith("🔥 <b>Bombers: incendi forestal dins del Parc de Collserola (Molins de Rei), a 13 km de Montflorit</b>"))
        self.assertIn("a Molins de Rei, dins del Parc Natural de Collserola, des de", t["ca"])
        self.assertTrue(AB.text_incendi(foc, acabat=True)["es"].startswith(
            "🟢 <b>Bombers: incendio en el Parque de Collserola (Molins de Rei), a 13 km de Montflorit: ya no consta como activo</b>"))

    def test_si_una_font_falla_no_es_toca_l_estat(self):
        estat = {}
        foc = [{"id": "x", "municipi": "Cerdanyola del Vallès", "km": 1.0, "inici": ARA.isoformat()}]
        self.passada(estat, foc)
        self.assertEqual(self.passada(estat, None, 6), [])     # Bombers no respon: no «s'ha acabat»
        self.assertIn("x", estat["entorn"]["incendis"])


if __name__ == "__main__":
    unittest.main()
