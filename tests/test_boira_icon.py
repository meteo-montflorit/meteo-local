# SPDX-License-Identifier: AGPL-3.0-or-later
"""La vigilància de la boira d'ICON (boira.py, ADR 0100): què s'apunta i com es compta."""
import contextlib
import csv
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
import boira as B  # noqa: E402
import prevision as P  # noqa: E402

ARA = dt.datetime(2026, 10, 17, 8, 40, tzinfo=P.ZONA)


def icon(hores):
    """La resposta d'Open-Meteo amb ICON per a unes hores (codi, visibilitat)."""
    temps = [(ARA.replace(minute=0) + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h, _, _ in hores]
    return json.dumps({"hourly": {"time": temps, "weather_code": [c for _, c, _ in hores],
                                  "visibility": [v for _, _, v in hores]}})


def escriu(ruta, camps, files):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, camps)
        w.writeheader()
        w.writerows(files)


class Apunta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        fitxer = mock.patch.object(B, "FITXER", os.path.join(self.dir.name, "boira-icon.csv"))
        fitxer.start()
        self.addCleanup(fitxer.stop)

    def test_nomes_les_hores_que_venen_i_com_a_molt_un_cop_per_hora(self):
        resposta = icon([(0, 0, 24000), (1, 45, 720), (12, 3, 9000), (14, 3, 9000)])
        self.assertEqual(B.apunta(ARA, get=lambda url: resposta), 2)
        with open(B.FITXER, encoding="utf-8") as f:
            files = list(csv.DictReader(f))
        # L'hora en curs ja ha passat i la de 14 h queda fora de les 12 h.
        self.assertEqual([r["codi"] for r in files], ["45", "3"])
        self.assertEqual(files[0]["antelacio_h"], "0.33")
        # Una altra passada al cap de mitja hora no hi torna: no hi ha cap consulta.
        self.assertEqual(B.apunta(ARA + dt.timedelta(minutes=30), get=self.fail), 0)
        self.assertEqual(B.apunta(ARA + dt.timedelta(hours=1), get=lambda url: resposta), 1)


class Resum(unittest.TestCase):
    def test_encerts_fallades_i_falses_alarmes(self):
        hores = [f"2026-10-17T{h:02d}:00" for h in range(5, 10)]
        with tempfile.TemporaryDirectory() as tmp:
            escriu(os.path.join(tmp, "boira-icon.csv"), B.CAMPS, [
                # ICON diu boira a les 5 i a les 6, i no a les 7 ni a les 8; la de les 9 és massa d'avançada.
                {"emes": "x", "fins": hores[0], "antelacio_h": 2, "codi": 45, "visibilitat": 500},
                {"emes": "x", "fins": hores[1], "antelacio_h": 3, "codi": 48, "visibilitat": 500},
                {"emes": "x", "fins": hores[2], "antelacio_h": 1, "codi": 3, "visibilitat": 9000},
                {"emes": "x", "fins": hores[3], "antelacio_h": 4, "codi": 3, "visibilitat": 9000},
                {"emes": "x", "fins": hores[4], "antelacio_h": 9, "codi": 45, "visibilitat": 500}])
            escriu(os.path.join(tmp, "nuvols-sabadell.csv"), ["fins", "metars"], [
                {"fins": hores[0], "metars": "LELL 0150 FG VV002"}, {"fins": hores[1], "metars": "LELL 9999 FEW020"},
                {"fins": hores[2], "metars": "LELL 0150 FG VV002"}, {"fins": hores[3], "metars": "LELL 9999 FEW020"}])
            camps = ["fins", "humitat", "temperatura", "rosada", "pluja_mm"]
            escriu(os.path.join(tmp, "estacio-casa.csv"), camps, [
                {"fins": hores[0], "humitat": 99, "temperatura": 12, "rosada": 11.8, "pluja_mm": 0},
                {"fins": hores[1], "humitat": 99, "temperatura": 12, "rosada": 11.8, "pluja_mm": 0},
                {"fins": hores[2], "humitat": 99, "temperatura": 12, "rosada": 11.8, "pluja_mm": 0},
                {"fins": hores[3], "humitat": 80, "temperatura": 15, "rosada": 11, "pluja_mm": ""},
                {"fins": hores[4], "humitat": 99, "temperatura": 12, "rosada": 11.8, "pluja_mm": 0}])
            escriu(os.path.join(tmp, "c.csv"), ["t", "resposta"], [{"t": "x", "resposta": "si"}, {"t": "y", "resposta": "no"}])
            with mock.patch.object(B, "REGISTRE", tmp), mock.patch.object(B, "CONFIRMACIONS", os.path.join(tmp, "c.csv")), \
                    contextlib.redirect_stdout(io.StringIO()) as sortida:
                res = B.resum()
        self.assertEqual(res["Boira a Sabadell i casa saturada"],
                         {"encert": 1, "fallada": 1, "falsa_alarma": 1, "sense_boira": 1})
        self.assertEqual(res["Casa saturada i sense pluja (la riera)"],
                         {"encert": 2, "fallada": 1, "falsa_alarma": 0, "sense_boira": 1})
        self.assertIn("Detecció 50%", sortida.getvalue())
        self.assertIn("Confirmacions de Juanjo amb casa saturada: 2 (boira 1, sense boira 1).", sortida.getvalue())


class Pregunta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.casa = os.path.join(self.dir.name, "casa.json")
        for nom, valor in (("PREGUNTES", os.path.join(self.dir.name, "p.csv")),):
            p = mock.patch.object(B, nom, valor)
            p.start()
            self.addCleanup(p.stop)

    def casa_amb(self, **ara_casa):
        with open(self.casa, "w", encoding="utf-8") as f:
            json.dump({"ara_casa": ara_casa}, f)

    def test_de_nit_plovent_o_sense_saturar_no_es_pregunta(self):
        self.casa_amb(humitat=99, plou=False)
        self.assertIsNone(B._pregunta(ARA.replace(hour=3), self.casa))
        self.casa_amb(humitat=99, plou=True)
        self.assertIsNone(B._pregunta(ARA, self.casa))
        self.casa_amb(humitat=90)
        self.assertIsNone(B._pregunta(ARA, self.casa))
        self.casa_amb()
        self.assertIsNone(B._pregunta(ARA, self.casa))

    def test_sabadell_que_no_respon_no_impedeix_la_pregunta(self):
        self.casa_amb(humitat_estacio=99)
        bot = os.path.join(self.dir.name, "bot.json")
        with open(bot, "w", encoding="utf-8") as f:
            json.dump({"chat_id": 7}, f)
        enviat = []
        with mock.patch.object(B, "CONFIG_BOT", bot), mock.patch.object(B.NV, "llegeix", side_effect=TimeoutError), \
                mock.patch.object(B, "telegram", side_effect=lambda m, **p: (enviat.append(p) or {"message_id": 5}, {})):
            self.assertEqual(B._pregunta(ARA, self.casa), 5)
        self.assertNotIn("Sabadell", enviat[0]["text"])
        self.assertIn("99 %", enviat[0]["text"])

    def test_l_estat_de_quan_es_respon(self):
        self.casa_amb(humitat=97)
        with mock.patch.object(B.NV, "llegeix", side_effect=TimeoutError):
            self.assertEqual(B.estat(self.casa), {"humitat": 97, "sabadell": None})
        with mock.patch.object(B.NV, "llegeix", return_value=[]), mock.patch.object(B.NV, "boira_ara", return_value=True):
            self.assertEqual(B.estat(self.casa), {"humitat": 97, "sabadell": 1})


if __name__ == "__main__":
    unittest.main()
