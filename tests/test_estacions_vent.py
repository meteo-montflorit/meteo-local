# SPDX-License-Identifier: AGPL-3.0-or-later
"""El vent de les estacions veïnes (vent_veines.py, ADR 0064): les mitges hores
de Meteocat, l'ompliment del registre, l'avís a Juanjo i la línia d'ordres."""
import contextlib
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import config as C  # noqa: E402
import registre as R  # noqa: E402
import vent_veines as VV  # noqa: E402
import wunderground as WU  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=2))


def hora(hhmm, dia=10):
    h, m = map(int, hhmm.split(":"))
    return dt.datetime(2026, 10, dia, h, m, tzinfo=TZ)


def sintetic(dies=4):
    """Sant Cugat bufa de 2 a 20 km/h; el Puig n'és la meitat (±0,2) i
    Sabadell 3 km/h més: l'estimació amb el Puig encerta més."""
    files = []
    inici = dt.datetime(2026, 10, 1, 0, 0)
    for k in range(dies * 48):
        fin = inici + dt.timedelta(minutes=30 * (k + 1))
        xv = 2.0 + (k * 7) % 19
        files.append({"fins": fin.strftime("%Y-%m-%dT%H:%M"), "XV": xv, "XV_ratxa": xv * 2,
                      "XF": xv + 3, "XF_ratxa": xv * 2 + 3, "ICERDA18": xv / 2 + (0.2 if k % 2 else -0.2), "ICERDA18_ratxa": xv})
    return files


def escriu_registre(ruta, files):
    VV.apunta({e: {dt.datetime.fromisoformat(f["fins"]).astimezone(): (f[e], f[f"{e}_ratxa"]) for f in files}
               for e in ("XV", "XF", "ICERDA18")}, ruta)


class MitgesHores(unittest.TestCase):
    def test_les_lectures_sense_vent_no_compten(self):
        files = [{"t": hora("10:05") + dt.timedelta(minutes=5 * k), "vent": v, "ratxa": None}
                 for k, v in enumerate([2.0, None, 4.0, None, 6.0, None])]
        # Només tres lectures amb vent: la mitja hora no és completa.
        self.assertEqual(VV.mitges_hores_veina(files), {})
        files[1]["vent"] = 8.0
        self.assertEqual(VV.mitges_hores_veina(files), {hora("10:30"): (5.0, None)})

    def test_meteocat_mitja_hora_acabada(self):
        ini = dt.datetime(2026, 10, 10, 8, 0, tzinfo=dt.timezone.utc)
        files = [(ini, {"VVM10 (km/h)": "12.6", "VVX10 (km/h)": "30.2"}),
                 (ini + dt.timedelta(minutes=30), {"VVM10 (km/h)": "(s/d)", "VVX10 (km/h)": "20"}),
                 (ini + dt.timedelta(minutes=60), {"VVM10 (km/h)": "7", "VVX10 (km/h)": "(s/d)"})]
        res = VV.mitges_hores_meteocat(files)
        self.assertEqual(res, {hora("10:30"): (12.6, 30.2), hora("11:30"): (7.0, None)})
        self.assertTrue(all(k.tzinfo is not None for k in res))


class Omple(unittest.TestCase):
    def test_set_dies_de_veines_i_el_portal(self):
        ara = hora("12:00")
        consultes, portal = [], []

        def consulta(ruta, params, lector):
            consultes.append((params["stationId"], params["date"]))
            if params["stationId"] == "ICERDA6":
                raise RuntimeError("la clau de lectura no val")
            if params["date"] != "20261010":
                return []
            return [{"obsTimeUtc": f"2026-10-10T08:{m:02d}:00Z", "metric": {"windspeedAvg": 4.0, "windgustHigh": 9.0}}
                    for m in range(5, 31, 5)]

        def portal_fals(codi, desde):
            portal.append((codi, desde))
            return {hora("10:30"): (10.0, 20.0)}
        apuntat = {}
        err = io.StringIO()
        with mock.patch.object(WU, "_consulta", consulta), mock.patch.object(VV, "portal", portal_fals), \
                mock.patch.object(VV, "apunta", apuntat.update), contextlib.redirect_stderr(err):
            res = VV.omple(dies=2, ara=ara)
        # Tres dies per veïna (del més antic al d'avui) i, de Meteocat, des d'un dia més enrere.
        self.assertEqual([d for e, d in consultes if e == "ICERDA18"], ["20261008", "20261009", "20261010"])
        self.assertEqual(portal, [("XV", ara - dt.timedelta(days=3)), ("XF", ara - dt.timedelta(days=3))])
        # La veïna que falla no atura les altres: queda buida i es diu.
        self.assertEqual(res, {"ICERDA6": 0, "ICERDA18": 1, "ICERDA28": 1, "ICERDA48": 1, "XV": 1, "XF": 1})
        self.assertIn("ICERDA6 20261008: la clau de lectura no val", err.getvalue())
        self.assertEqual(apuntat["ICERDA18"], {hora("10:30"): (4.0, 9.0)})


class Registre(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def test_llegeix_desde_i_sense_fitxer(self):
        ruta = os.path.join(self.dir.name, "r", "vent.csv")
        self.assertEqual(VV.llegeix(ruta), [])
        escriu_registre(ruta, sintetic(1)[:4])
        files = VV.llegeix(ruta, desde="2026-10-01T01:30")
        self.assertEqual([f["fins"] for f in files], ["2026-10-01T01:30", "2026-10-01T02:00"])
        self.assertAlmostEqual(files[0]["ICERDA18"], files[0]["XV"] / 2 - 0.2)
        self.assertIsNone(files[0]["ICERDA6"])

    def test_apren_avisa_juanjo_encara_que_falli_el_portal(self):
        reg, dir_ = os.path.join(self.dir.name, "reg"), os.path.join(self.dir.name, "apren")
        escriu_registre(os.path.join(reg, os.path.basename(VV.CSV)), sintetic())
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(VV, "portal", side_effect=OSError("portal caigut")), \
                mock.patch.object(VV.subprocess, "run") as run, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            model = VV.apren(dt.datetime(2026, 10, 5, 12).astimezone(), registre=reg, directori=dir_)
        self.assertIn("No he pogut llegir Meteocat al portal: portal caigut", err.getvalue())
        self.assertTrue(model["mitja"]["veines"]["ICERDA18"]["compta"])
        self.assertLess(model["mitja"]["validacio"]["estimacio"], 1.0)
        self.assertEqual(model["mitja"]["validacio"]["sabadell"], 3.0)
        args = run.call_args.args[0]
        self.assertEqual(args[:2], ["avisar-juanjo", "--de"])
        self.assertIn("L'estimació encerta tant o més", args[-1])
        self.assertIn("al Puig de la Guàrdia", args[-1])
        self.assertEqual(run.call_args.kwargs, {"check": False})
        self.assertIn(args[-1], out.getvalue())
        # Desat a la carpeta d'aprenentatge, amb la marca de l'avís.
        self.assertEqual(sorted(os.listdir(dir_)), ["avis-vent-veines", "vent-veines.json"])

    def test_avis_quan_l_estimacio_es_pitjor(self):
        model = {"mitja": {"veines": {"ICERDA18": {"compta": False}},
                           "validacio": {"ventoses": 20, "mitges_hores": 100, "estimacio": 3.0,
                                         "sabadell": 2.0, "abans": 2.5}}}
        text = VV.avis(model, os.path.join(self.dir.name, "cap-marca"))
        self.assertIn("(cap) 3,0 km/h", text)
        self.assertIn("millor seguir amb Sant Cugat", text)
        model["mitja"]["validacio"]["ventoses"] = VV.MIN_VENTOSES - 1
        self.assertIsNone(VV.avis(model, os.path.join(self.dir.name, "cap-marca")))


class Model(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        p = mock.patch.object(VV, "MODEL", os.path.join(self.dir.name, "vent-veines.json"))
        p.start()
        self.addCleanup(p.stop)

    def sortida(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            VV.estat()
        return out.getvalue()

    def test_carrega_i_estat(self):
        self.assertIsNone(VV.carrega())
        self.assertIn("Encara no s'ha après res.", self.sortida())
        with open(VV.MODEL, "w", encoding="utf-8") as f:
            f.write("{a mitges")
        self.assertIsNone(VV.carrega())
        info = {"parelles": 150, "factor": 2.0, "compta": True}
        model = {"dia": "2026-10-05", **{v: {"veines": {"ICERDA18": info}, "validacio": {"ventoses": 30}}
                                         for v in VV.VARIABLES}}
        with open(VV.MODEL, "w", encoding="utf-8") as f:
            json.dump(model, f)
        self.assertEqual(VV.carrega(), model)
        text = self.sortida()
        self.assertIn("Après el 2026-10-05", text)
        self.assertIn("ratxa:", text)
        self.assertIn(f"ICERDA18  {C.VEINES['ICERDA18']['nom']}", text)
        # Sense model guardat, l'estimació d'ara no s'inventa res.
        os.remove(VV.MODEL)
        self.assertIsNone(VV.ara([{"estacio": "ICERDA18", "files": []}]))


class LiniaOrdres(unittest.TestCase):
    def executa(self, args, d):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["vent_veines.py", *args]), \
                mock.patch.dict(os.environ, {"APRENENTATGE_DIR": d}), mock.patch.object(R, "DIR", d), \
                mock.patch.object(WU, "_consulta", lambda ruta, params, lector: []), \
                mock.patch("urllib.request.urlopen", lambda url, timeout: io.BytesIO(b"[]")), \
                contextlib.redirect_stdout(out):
            runpy.run_path(os.path.join(ARREL, "vent_veines.py"), run_name="__main__")
        return out.getvalue()

    def test_ordres(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Encara no s'ha après res.", self.executa(["estat"], d))
            # Sense registre, «apren» no aprèn res.
            self.assertIn("Encara no s'ha après res.", self.executa(["apren", "--sense-avis"], d))
            self.assertIn("'XV': 0", self.executa(["omple"], d))
            self.assertFalse(os.path.exists(os.path.join(d, "vent-mitges-hores.csv")))
            self.assertIn("python3 vent_veines.py apren", self.executa([], d))


if __name__ == "__main__":
    unittest.main()
