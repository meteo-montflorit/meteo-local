# SPDX-License-Identifier: AGPL-3.0-or-later
"""L'API d'Ecowitt de l'estació de casa (ecowitt.py, ADR 0017), sense xarxa ni claus reals."""
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
import ecowitt as E  # noqa: E402

CLAUS = {"ECOWITT_APPLICATION_KEY": "app", "ECOWITT_API_KEY": "api", "ECOWITT_MAC": "AA:BB"}
ARA = dt.datetime(2026, 10, 17, 8, 40).astimezone()


def resposta(cos):
    """El que torna urlopen: un context amb el cos JSON."""
    r = mock.MagicMock()
    r.__enter__.return_value = io.BytesIO(json.dumps(cos).encode())
    return r


class Claus(unittest.TestCase):
    def test_de_l_entorn_o_del_fitxer(self):
        with mock.patch.dict(os.environ, CLAUS):
            self.assertEqual(E.claves(), CLAUS)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True):
            ruta = os.path.join(tmp, "ecowitt.env")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write("ECOWITT_APPLICATION_KEY=app\nECOWITT_API_KEY=api\nALTRA=x\nECOWITT_MAC=AA:BB\n")
            with mock.patch.object(E.os.path, "expanduser", return_value=ruta):
                self.assertEqual(E.claves(), CLAUS)
                self.assertTrue(E.disponible())

    def test_una_clau_que_falta_vol_dir_sense_estacio(self):
        with mock.patch.dict(os.environ, {"ECOWITT_API_KEY": "api"}, clear=True), \
                mock.patch.object(E.os.path, "expanduser", return_value="/no/hi/es"):
            self.assertIsNone(E.claves())
            with self.assertRaisesRegex(RuntimeError, "sense claus"):
                E.consulta("real_time")


class Consulta(unittest.TestCase):
    def test_unitats_fixes_i_error_de_l_api(self):
        with mock.patch.dict(os.environ, CLAUS), \
                mock.patch.object(E.urllib.request, "urlopen", return_value=resposta({"code": 0, "data": {"ok": 1}})) as obre:
            self.assertEqual(E.consulta("real_time", call_back="outdoor"), {"ok": 1})
        url = obre.call_args[0][0].full_url
        # Les unitats van sempre fixades: °C, hPa, mm i W/m².
        for clau, valor in E.UNIDADES.items():
            self.assertIn(f"{clau}={valor}", url)
        self.assertIn("mac=AA%3ABB", url)
        with mock.patch.dict(os.environ, CLAUS), \
                mock.patch.object(E.urllib.request, "urlopen", return_value=resposta({"code": -1, "msg": "too frequent"})):
            with self.assertRaisesRegex(RuntimeError, "Ecowitt: too frequent"):
                E.consulta("history")


class Lectures(unittest.TestCase):
    def test_ara_amb_la_pressio_reduida_al_nivell_del_mar(self):
        t = int(ARA.timestamp())
        d = {"outdoor": {"temperature": {"time": str(t), "value": "18.5"}, "humidity": {"value": "97"},
                         "dew_point": {"value": "18.0"}},
             "pressure": {"absolute": {"value": "1000.0"}},
             "solar_and_uvi": {"solar": {"value": "12"}, "uvi": {"value": "0"}},
             "rainfall": {"rain_rate": {"value": "0.0"}, "1_hour": {"value": "0.2"}, "daily": {"value": "1.4"}}}
        with mock.patch.object(E, "consulta", return_value=d):
            a = E.ara()
        self.assertEqual(dt.datetime.fromisoformat(a["hora"]), ARA)
        self.assertEqual((a["temperatura"], a["humitat"], a["pluja_avui"]), (18.5, 97, 1.4))
        self.assertEqual(a["pressio"], E.pressio_mar(1000.0, 18.5))
        self.assertGreater(a["pressio"], 1000.0)
        self.assertIsNone(E._valor(d, "outdoor", "no_hi_es"))

    def test_historial_per_trams_amb_reintents(self):
        inici = ARA - dt.timedelta(days=2, hours=1)
        crides, esperes = [], []

        def consulta(ordre, **params):
            crides.append(params["start_date"])
            if len(crides) == 1:
                raise RuntimeError("Ecowitt: operation too frequent")
            t = str(int(ARA.timestamp()))
            # Totes les respostes porten la mateixa lectura: només se'n queda una.
            return {"outdoor": {"temperature": {"list": {t: "18"}}}}

        with mock.patch.object(E, "consulta", side_effect=consulta), \
                mock.patch.object(E.time, "sleep", side_effect=esperes.append):
            files = E.historial(inici, ARA, "5min")
        # Tres dies de calendari en trams d'un dia, més el reintent del primer.
        self.assertEqual(len(crides), 4)
        self.assertEqual(crides[0], crides[1])
        self.assertIn(30, esperes)
        self.assertEqual(files, [{"t": ARA, "temperatura": 18.0}])

    def test_un_error_que_no_es_de_limit_no_es_reintenta(self):
        with mock.patch.object(E, "consulta", side_effect=RuntimeError("Ecowitt: invalid mac")) as consulta, \
                mock.patch.object(E.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "invalid mac"):
                E.historial(ARA - dt.timedelta(hours=1), ARA)
        self.assertEqual(consulta.call_count, 1)

    def test_resum_ara_plou_nomes_si_marca_pluja_recent(self):
        abans = [{"t": ARA - dt.timedelta(minutes=m), "pluja_avui": 1.0, "pressio": 1012.0} for m in (185, 60, 20)]
        a = {"hora": ARA.isoformat(), "temperatura": 18, "pluja_avui": 1.4, "pressio": 1013.5, "intensitat": 1.2}
        with mock.patch.object(E, "ara", return_value=dict(a)), mock.patch.object(E, "historial", return_value=list(abans)):
            r = E.resum_ara(ARA)
        self.assertTrue(r["plou"])
        self.assertEqual((r["pluja_15min"], r["pluja_1h"]), (0.4, 0.4))
        self.assertEqual(r["pressio_3h"], 1.5)
        self.assertEqual(E.observacio(r, "Casa")["mm_ultima_media_hora"], 0.4)
        # Sense pluja nova, el zero no s'afirma: no hi ha observació.
        with mock.patch.object(E, "ara", return_value={**a, "pluja_avui": 1.0}), \
                mock.patch.object(E, "historial", return_value=list(abans)):
            r = E.resum_ara(ARA)
        self.assertFalse(r["plou"])
        self.assertIsNone(E.observacio(r, "Casa"))
        self.assertIsNone(E.observacio(None, "Casa"))

    def test_csv_d_anada_i_tornada(self):
        files = [{"t": ARA, "temperatura": 18.5, "humitat": 97.0, "rosada": None, "pressio": 1013.2,
                  "solar": 0.0, "intensitat": 0.0, "pluja_avui": 1.4}]
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "casa.csv")
            E.guarda_csv(files, ruta)
            self.assertEqual(E.lee_csv(ruta), files)


if __name__ == "__main__":
    unittest.main()
