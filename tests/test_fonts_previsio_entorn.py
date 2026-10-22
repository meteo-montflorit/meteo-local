# SPDX-License-Identifier: AGPL-3.0-or-later
"""El contorn de Collserola, la consulta a Bombers i el càlcul d'entorn.py
quan una font falla (ADR 0046 i 0071), sense xarxa."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import entorn as EN  # noqa: E402

ARA = dt.datetime(2026, 10, 8, 13, 0).astimezone()
QUADRAT = [[2.0, 41.0], [2.1, 41.0], [2.1, 41.1], [2.0, 41.1]]


def feature(desc, y, x, fi=None, gid="g1", municipi="Cerdanyola del Vallès"):
    return {"attributes": {"GlobalID": gid, "TAL_DESC_ALARMA2": desc, "MUNICIPI_SIG": municipi,
                           "ACT_DAT_INICI": int(ARA.timestamp() * 1000), "ACT_DAT_FI": fi,
                           "ACT_NUM_VEH": 2, "COM_FASE": "Actiu"}, "geometry": {"x": x, "y": y}}


class Get(unittest.TestCase):
    def test_afegeix_els_parametres_i_la_capcalera(self):
        vist = {}

        def urlopen(req, timeout):
            vist["url"], vist["ua"], vist["timeout"] = req.full_url, req.get_header("User-agent"), timeout
            return io.BytesIO(b'{"ok": 1}')
        with mock.patch.object(EN.urllib.request, "urlopen", urlopen):
            self.assertEqual(EN.get("https://x/q", {"f": "json", "where": "1=1"}), {"ok": 1})
            self.assertIn("?f=json&where=1%3D1", vist["url"])
            self.assertIn("Montflorit", vist["ua"])
            self.assertEqual(vist["timeout"], 30)
            EN.get("https://x/q")
            self.assertEqual(vist["url"], "https://x/q")

    def test_hora_iso(self):
        self.assertIsNone(EN.hora_iso(None))
        self.assertIsNone(EN.hora_iso(0))
        self.assertEqual(EN.hora_iso(int(ARA.timestamp() * 1000)), ARA.isoformat(timespec="minutes"))


class Contorn(unittest.TestCase):
    """El contorn exterior del parc es guarda CONTORN_DIES dies; sense xarxa,
    es fa servir el vell; sense res, None."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        p = mock.patch.object(EN, "CONTORN", os.path.join(self.dir.name, "contorn.json"))
        p.start()
        self.addCleanup(p.stop)

    def test_baixa_poligons_i_multipoligons_i_els_guarda(self):
        d = {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [QUADRAT, [[2.05, 41.05]]]}},
            {"geometry": {"type": "MultiPolygon", "coordinates": [[[[3, 4], [5, 6]]], [[[7, 8], [9, 10]]]]}},
            {"geometry": {"type": "Point", "coordinates": [1, 2]}}]}
        with mock.patch.object(EN, "get", return_value=d) as get:
            anells = EN.contorn()
        # Només l'anell exterior de cada polígon: els forats (enclavaments) no.
        self.assertEqual(anells, [QUADRAT, [[3, 4], [5, 6]], [[7, 8], [9, 10]]])
        self.assertEqual(get.call_args[0][1]["f"], "geojson")
        with open(EN.CONTORN) as f:
            self.assertEqual(json.load(f), anells)
        self.assertFalse(os.path.exists(EN.CONTORN + ".tmp"))
        # La segona vegada surt del fitxer, sense tornar a baixar-lo.
        with mock.patch.object(EN, "get", side_effect=AssertionError("no hauria de baixar")):
            self.assertEqual(EN.contorn(), anells)

    def test_un_fitxer_vell_es_torna_a_baixar(self):
        with open(EN.CONTORN, "w") as f:
            json.dump([[[0, 0], [1, 1]]], f)
        vell = time.time() - (EN.CONTORN_DIES + 1) * 86400
        os.utime(EN.CONTORN, (vell, vell))
        d = {"features": [{"geometry": {"type": "Polygon", "coordinates": [QUADRAT]}}]}
        with mock.patch.object(EN, "get", return_value=d):
            self.assertEqual(EN.contorn(), [QUADRAT])

    def test_si_la_capa_falla_val_el_vell(self):
        with open(EN.CONTORN, "w") as f:
            json.dump([QUADRAT], f)
        vell = time.time() - (EN.CONTORN_DIES + 1) * 86400
        os.utime(EN.CONTORN, (vell, vell))
        with mock.patch.object(EN, "get", side_effect=OSError("sense xarxa")):
            self.assertEqual(EN.contorn(), [QUADRAT])

    def test_capa_sense_poligons_i_sense_fitxer_es_none(self):
        with mock.patch.object(EN, "get", return_value={"features": []}):
            self.assertIsNone(EN.contorn())
        self.assertFalse(os.path.exists(EN.CONTORN))

    def test_fitxer_espatllat_es_torna_a_baixar(self):
        with open(EN.CONTORN, "w") as f:
            f.write("{no és json")
        with mock.patch.object(EN, "get", side_effect=OSError("sense xarxa")):
            self.assertIsNone(EN.contorn())


class DinsCollserola(unittest.TestCase):
    def test_amb_el_contorn(self):
        with mock.patch.object(EN, "contorn", return_value=[QUADRAT]):
            self.assertTrue(EN.dins_collserola(41.05, 2.05))
            self.assertFalse(EN.dins_collserola(41.5, 2.05))

    def test_sense_contorn_pregunta_a_la_capa_amb_el_marge(self):
        crides = []

        def get(url, params):
            crides.append(params)
            return {"count": 1}
        with mock.patch.object(EN, "contorn", return_value=None), mock.patch.object(EN, "get", get):
            self.assertTrue(EN.dins_collserola(41.45, 2.1))
        self.assertEqual(crides[0]["geometry"], "2.1,41.45")
        self.assertEqual(crides[0]["distance"], EN.C.COLLSEROLA_MARGE_KM)
        with mock.patch.object(EN, "contorn", return_value=None), \
                mock.patch.object(EN, "get", return_value={"count": 0}):
            self.assertFalse(EN.dins_collserola(41.45, 2.1))
        with mock.patch.object(EN, "contorn", return_value=None), \
                mock.patch.object(EN, "get", return_value={}):
            self.assertFalse(EN.dins_collserola(41.45, 2.1))

    def test_un_error_de_la_capa_no_es_fora_del_parc(self):
        with mock.patch.object(EN, "contorn", return_value=None), \
                mock.patch.object(EN, "get", return_value={"error": {"message": "Token required"}}):
            with self.assertRaisesRegex(RuntimeError, "Token required"):
                EN.dins_collserola(41.45, 2.1)


class Incendis(unittest.TestCase):
    def test_un_error_de_bombers_no_es_cap_incendi(self):
        with self.assertRaisesRegex(RuntimeError, "caiguda"):
            EN.incendis({"error": {"message": "caiguda"}})

    def test_sense_geometria_es_salta_i_fora_es_apunta(self):
        f = "Incendi vegetació forestal"
        sense = feature(f, 0, 0, gid="sense")
        sense["geometry"] = None
        d = {"features": [sense, feature(f, 41.30, 2.40, gid="lluny"), feature(f, 41.483, 2.136, gid="aprop")]}
        fora = []
        r = EN.incendis(d, collserola=lambda y, x: False, fora=fora)
        self.assertEqual([i["id"] for i in r], ["aprop"])
        self.assertEqual(fora, ["lluny"])
        self.assertEqual(r[0]["vehicles"], 2)
        self.assertEqual(r[0]["fase"], "Actiu")
        # Sense «fora», els de fora de la zona tampoc hi surten.
        self.assertEqual([i["id"] for i in EN.incendis(d, collserola=lambda y, x: False)], ["aprop"])

    def test_ordenats_del_mes_proper_al_mes_llunya(self):
        f = "Incendi vegetació forestal"
        d = {"features": [feature(f, 41.40, 2.02, gid="molins"), feature(f, 41.483, 2.136, gid="aprop")]}
        r = EN.incendis(d, collserola=lambda y, x: True)
        self.assertEqual([i["id"] for i in r], ["aprop", "molins"])
        self.assertLess(r[0]["km"], r[1]["km"])

    def test_consulta_bombers_amb_la_caixa(self):
        with mock.patch.object(EN, "get", return_value={"features": []}) as get:
            self.assertEqual(EN.incendis(), [])
        p = get.call_args[0][1]
        self.assertEqual(p["geometry"], ",".join(str(v) for v in EN.C.INCENDIS_CAIXA))
        self.assertIn("IV", p["where"])


class Calcula(unittest.TestCase):
    def test_tot_be(self):
        with mock.patch.object(EN, "incendis", lambda fora: fora.append("x") or [{"id": "a"}]), \
                mock.patch.object(EN, "pla_alfa", lambda ara: {"avui": 2, "dema": 3, "tancaments": []}):
            r = EN.calcula(ARA)
        self.assertEqual(r["hora"], ARA.isoformat(timespec="minutes"))
        self.assertEqual(r["incendis"], [{"id": "a"}])
        self.assertEqual(r["incendis_fora"], ["x"])
        self.assertEqual(r["pla_alfa"]["dema"], 3)
        self.assertEqual(r["errors"], [])

    def test_una_font_que_falla_es_none_no_zero(self):
        def falla(fora):
            raise OSError("timeout")
        with mock.patch.object(EN, "incendis", falla), \
                mock.patch.object(EN, "pla_alfa", side_effect=RuntimeError("capa")):
            r = EN.calcula()
        # Si Bombers falla no es diu «cap incendi» ni «cap fora de la zona».
        self.assertIsNone(r["incendis"])
        self.assertIsNone(r["incendis_fora"])
        self.assertIsNone(r["pla_alfa"])
        self.assertEqual(r["errors"], ["incendis: timeout", "pla_alfa: capa"])


if __name__ == "__main__":
    unittest.main()
