# SPDX-License-Identifier: AGPL-3.0-or-later
"""La subida de la estación de casa a Weather Underground (wunderground.py, ADR 0059), sin red."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wunderground as W  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=2))

CASA = {"hora": "2026-10-09T22:40+02:00", "temperatura": 12.5, "humitat": 89.0, "rosada": 10.7,
        "pressio": 1018.6, "solar": 0.0, "uv": 0.0, "intensitat": 0.0, "pluja_1h": 0.2, "pluja_avui": 2.54,
        "pluja_15min": 0.0, "plou": False, "files": []}


class Parametres(unittest.TestCase):
    def test_unitats_de_weather_underground(self):
        p = W.parametres(CASA)
        self.assertEqual(p["dateutc"], "2026-10-09 20:40:00")        # en UTC
        self.assertEqual(p["tempf"], 54.5)
        self.assertEqual(p["dewptf"], 51.3)
        self.assertEqual(p["humidity"], 89.0)
        self.assertEqual(p["baromin"], 30.079)                         # inHg, al nivell del mar
        self.assertEqual((p["rainin"], p["dailyrainin"]), (0.008, 0.1))  # polzades
        self.assertEqual((p["solarradiation"], p["UV"]), (0.0, 0.0))
        self.assertEqual(p["action"], "updateraw")
        self.assertNotIn("windspeedmph", p)                            # el vent no es puja (ADR 0017)

    def test_sense_dades_no_s_envien_camps_buits(self):
        p = W.parametres({"hora": CASA["hora"], "temperatura": 12.5})
        self.assertEqual(set(p), {"dateutc", "tempf", "softwaretype", "action"})


class Puja(unittest.TestCase):
    def test_sense_claus_no_puja(self):
        with mock.patch.dict(os.environ, {"HOME": tempfile.mkdtemp()}, clear=True):
            self.assertFalse(W.disponible())
            self.assertIsNone(W.puja(CASA))

    def test_amb_claus_envia_id_i_clau(self):
        urls = []
        with mock.patch.dict(os.environ, {"WU_STATION_ID": "IPROVA1", "WU_STATION_KEY": "clau"}):
            r = W.puja(CASA, lector=lambda u: urls.append(u) or "success")
        self.assertEqual(r, "success")
        self.assertIn("ID=IPROVA1&PASSWORD=clau&dateutc=2026-10-09+20%3A40%3A00&tempf=54.5", urls[0])
        self.assertTrue(urls[0].startswith(W.URL))


def obs(hhmm, tot, temp=12.0, vent=1, dia="2026-10-10"):
    """Una observación de la API (all/1day), en UTC."""
    return {"stationID": "ICERDA6", "obsTimeUtc": f"{dia}T{hhmm}{'' if ':' in hhmm[3:] else ':00'}Z", "humidityAvg": 90,
            "metric": {"tempAvg": temp, "dewptAvg": temp - 1, "pressureMax": 1018.2, "pressureMin": 1018.0,
                       "windspeedAvg": vent, "windgustHigh": vent * 2, "precipRate": 0.0, "precipTotal": tot}}


class Veines(unittest.TestCase):
    def test_lectures_amb_la_forma_de_les_d_ecowitt(self):
        f = W.files([obs("04:05", 0.5), obs("04:00", 0.0)])
        self.assertEqual([W.H.local(x["t"]).strftime("%H:%M") for x in f], ["06:00", "06:05"])   # ordenades, hora local
        self.assertEqual(f[1]["pluja_avui"], 0.5)
        self.assertEqual((f[1]["temperatura"], f[1]["humitat"], f[1]["rosada"]), (12.0, 90, 11.0))
        self.assertEqual((f[1]["pressio"], f[1]["vent"], f[1]["ratxa"]), (1018.1, 1, 2))
        self.assertEqual(W.files([]), [])

    def test_plou_si_ha_recollit_pluja_en_els_darrers_minuts(self):
        ara = dt.datetime(2026, 10, 10, 6, 22, tzinfo=TZ)
        # Llovió 1 mm de madrugada; la de hoy es lo que sube el total desde la medianoche local.
        seca = W.files([obs("22:00", 0.0, dia="2026-10-09"), obs("02:50", 1.0), obs("04:05", 1.0), obs("04:20", 1.0)])
        v = W.veina_ara("ICERDA6", seca, ara)
        self.assertFalse(v["plou"])
        self.assertEqual((v["estacio"], v["compta"], v["hora"]), ("ICERDA6", True, "2026-10-10T06:20+02:00"))
        self.assertEqual((v["pluja_15min"], v["pluja_1h"], v["pluja_avui"], v["pluja_avui_wu"]), (0.0, 0.0, 1.0, 1.0))
        # 0,3 mm entre les 06:05 i les 06:20: plou. La d'una hora abans no compta.
        moll = W.files([obs("03:50", 0.0), obs("04:05", 1.0), obs("04:20", 1.3)])
        v = W.veina_ara("ICERDA6", moll, ara)
        self.assertTrue(v["plou"])
        self.assertEqual((v["pluja_15min"], v["pluja_1h"]), (0.3, 1.3))
        # El dia de l'estació canvia (l'acumulat torna a zero): el que hi ha després compta.
        reinici = W.files([obs("03:50", 55.1), obs("04:05", 0.2), obs("04:20", 0.4)])
        self.assertEqual(W.veina_ara("ICERDA6", reinici, ara)["pluja_1h"], 0.4)

    def test_la_pluja_d_avui_compta_l_ultima_lectura_amb_segons(self):
        # 19-10-2026, 06:09: les lectures de WU porten segons (06:04:54) i la
        # d'avui, calculada fins a l'hora sense segons, perdia el salt de
        # l'última lectura: 0,1 mm d'avui amb 0,2 en l'última hora.
        ara = dt.datetime(2026, 10, 19, 6, 9, tzinfo=TZ)
        fs = W.files([obs("22:04:46", 0.0, dia="2026-10-18"), obs("03:54:46", 0.0, dia="2026-10-19"),
                      obs("03:59:58", 0.0, dia="2026-10-19"), obs("04:04:46", 0.25, dia="2026-10-19")])
        v = W.veina_ara("ICERDA18", fs, ara)
        self.assertEqual(v["hora"], "2026-10-19T06:04+02:00")
        self.assertEqual((v["pluja_15min"], v["pluja_1h"], v["pluja_avui"]), (0.2, 0.2, 0.2))
        self.assertGreaterEqual(v["pluja_avui"], v["pluja_1h"])

    def test_una_lectura_vella_no_val(self):
        ara = dt.datetime(2026, 10, 10, 6, 22, tzinfo=TZ)
        with self.assertRaises(RuntimeError):
            W.veina_ara("ICERDA6", W.files([obs("03:40", 0.0)]), ara)
        with self.assertRaises(RuntimeError):
            W.veina_ara("ICERDA6", [], ara)

    def test_qui_compta_i_observacio_per_al_mode_avis(self):
        ara = dt.datetime(2026, 10, 10, 6, 22, tzinfo=TZ)
        moll = W.files([obs("04:05", 1.0), obs("04:20", 1.3)])
        bona = W.veina_ara("ICERDA6", moll, ara)
        curta = W.veina_ara("ICERDA48", moll, ara)       # no compta per a «plou ara» (ADR 0060)
        self.assertTrue(bona["compta"] and not curta["compta"])
        self.assertTrue(W.plou_a_les_veines([curta, bona]))
        self.assertFalse(W.plou_a_les_veines([curta]))
        self.assertFalse(W.plou_a_les_veines(None))
        o = W.observacio(bona)
        self.assertEqual((o["estacion"], o["font"], o["mm_ultima_media_hora"]), ("ICERDA6", "Weather Underground", 0.3))
        self.assertIsNone(W.observacio(curta))

    def test_veines_ara_amb_una_que_falla(self):
        ara = dt.datetime(2026, 10, 10, 6, 22, tzinfo=TZ)

        def lector(url):
            if "ICERDA18" in url:
                raise RuntimeError("HTTP 500")
            if "ICERDA28" in url:
                return ""                                      # 204: sense dades
            return json.dumps({"observations": [obs("04:05", 0.0), obs("04:20", 0.0)]})
        with mock.patch.dict(os.environ, {"WU_API_KEY": "clau"}):
            veines, errors = W.veines_ara(ara, lector)
        self.assertEqual([v["estacio"] for v in veines], ["ICERDA6", "ICERDA48"])
        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0].startswith("ICERDA18: HTTP 500"))
        self.assertIn("sense lectures", errors[1])

    def test_sense_clau_no_es_llegeix(self):
        with mock.patch.dict(os.environ, {"HOME": tempfile.mkdtemp()}, clear=True):
            self.assertFalse(W.lectura_disponible())

    def test_dies_fins_que_caduca_la_clau(self):
        self.assertEqual(W.dies_fins_caducitat(dt.datetime(2027, 3, 20, 12, 0, tzinfo=TZ)), 21)


if __name__ == "__main__":
    unittest.main()
