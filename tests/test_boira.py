# SPDX-License-Identifier: AGPL-3.0-or-later
"""La boira de l'hora en curs i la vigilància d'ICON (nuvols.py, boira.py; ADR 0100)."""
import datetime as dt
import os
import sys
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import boira as B  # noqa: E402
import nuvols as NV  # noqa: E402

ARA = dt.datetime(2026, 10, 17, 8, 40).astimezone()


class Boira(unittest.TestCase):
    def test_el_metar_de_la_boira(self):
        self.assertTrue(NV.te_boira("METAR LELL 170630Z VRB02KT 0150 R31/0375N FG VV002 16/15 Q1019"))
        self.assertTrue(NV.te_boira("METAR LELL 170430Z AUTO 28002KT 4000 BR BCFG BKN001 16/15 Q1019"))
        # La boirina no és boira, ni la «FG» d'un altre mot.
        self.assertFalse(NV.te_boira("METAR LELL 170400Z 29002KT 4000 BR BKN001 16/15 Q1019"))
        self.assertFalse(NV.te_boira(None))

    def test_nomes_si_es_recent(self):
        obs = [{"t": ARA - dt.timedelta(minutes=10), "brut": "METAR LELL 170630Z 0150 FG VV002"}]
        self.assertTrue(NV.boira_ara(obs, ARA))
        self.assertFalse(NV.boira_ara(obs, ARA + dt.timedelta(hours=1)))
        self.assertFalse(NV.boira_ara([], ARA))

    def test_observada_amb_la_casa_saturada(self):
        self.assertTrue(B.observada("FG VV002", 99))
        self.assertFalse(B.observada("FG VV002", 85))
        self.assertFalse(B.observada("BR", 100))


class Confirmacio(unittest.TestCase):
    """La pregunta a Juanjo quan casa és saturada i la seva resposta (ADR 0100)."""

    def setUp(self):
        import json
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        B.PREGUNTES = os.path.join(self.dir.name, "p.csv")
        B.CONFIRMACIONS = os.path.join(self.dir.name, "c.csv")
        B.CONFIG_BOT = os.path.join(self.dir.name, "bot.json")
        json.dump({"token": "x", "chat_id": 7}, open(B.CONFIG_BOT, "w"))
        self.casa = os.path.join(self.dir.name, "casa.json")
        self.crides = []

        self.dada = "boira:si"

        def telegram(metode, **p):
            self.crides.append((metode, p))
            if metode == "sendMessage":
                return {"message_id": 41}, {"chat_id": 7}
            if metode == "getUpdates":
                return [{"callback_query": {"id": "q", "data": self.dada, "from": {"id": 7},
                                            "message": {"message_id": 41}}}], {"chat_id": 7}
            return True, {"chat_id": 7}
        B.telegram = telegram
        self.nv = NV.llegeix
        NV.llegeix = lambda get: []
        self.addCleanup(setattr, NV, "llegeix", self.nv)

    def casa_amb(self, hum, plou=False):
        import json
        json.dump({"ara_casa": {"humitat_estacio": hum, "plou": plou}}, open(self.casa, "w"))

    def test_pregunta_una_vegada_i_apunta_la_resposta(self):
        self.casa_amb(99)
        self.assertEqual(B.pregunta(ARA, self.casa), 41)
        self.assertIsNone(B.pregunta(ARA + dt.timedelta(hours=1), self.casa))     # no fins d'aquí a 6 h
        self.assertEqual(B.respostes(ARA), 1)
        self.assertEqual(B.respostes(ARA), 0)                                     # una sola vegada
        # El missatge diu el que s'ha apuntat abans de respondre el toc.
        metodes = [m for m, _ in self.crides]
        self.assertLess(metodes.index("editMessageReplyMarkup"), metodes.index("answerCallbackQuery"))
        self.assertIn("answerCallbackQuery", [m for m, _ in self.crides])

    def botons(self):
        return [[b["text"] for b in fila] for fila in
                [p for m, p in self.crides if m == "editMessageReplyMarkup"][-1]["reply_markup"]["inline_keyboard"]]

    def test_a_temps_val_per_a_la_resposta(self):
        import confirmacio as CF
        self.casa_amb(99)
        B.pregunta(ARA, self.casa)
        B.respostes(ARA + dt.timedelta(minutes=20))
        fila = CF.files(B.CONFIRMACIONS)[0]
        self.assertEqual(fila["val_per"], "resposta")
        self.assertEqual(self.botons(), [["Apuntado a las 09:00: Sí, hay niebla"]])

    def test_tard_pregunta_per_a_quina_hora_val(self):
        # 28-10-2026: pregunta a les 7:01, resposta a les 8:16, «no había niebla a las 7».
        import confirmacio as CF
        self.casa_amb(99)
        B.pregunta(ARA, self.casa)
        tard = ARA + dt.timedelta(minutes=75)
        self.assertEqual(B.respostes(tard), 1)
        fila = CF.files(B.CONFIRMACIONS)[0]
        self.assertEqual(fila["val_per"], "")
        self.assertEqual(CF.val_per(fila), "resposta")                            # mentre no tria
        self.assertEqual(self.botons(), [["Apuntado: Sí, hay niebla"],
                                          ["Vale para las 08:40", "Vale para las 09:55"]])
        self.dada = "boira:val:pregunta"
        self.assertEqual(B.respostes(tard + dt.timedelta(seconds=15)), 1)
        fila = CF.files(B.CONFIRMACIONS)[0]
        self.assertEqual(fila["val_per"], "pregunta")
        self.assertEqual(fila["resposta"], "si")
        self.assertEqual(self.botons(), [["Apuntado a las 08:40: Sí, hay niebla"]])
        self.assertEqual(B.respostes(tard + dt.timedelta(seconds=30)), 0)        # una sola vegada
        self.assertEqual(len(CF.files(B.CONFIRMACIONS)), 1)

    def test_el_fitxer_d_abans_guanya_la_columna(self):
        import csv
        import confirmacio as CF
        camps = ["missatge", "pregunta", "resposta", "resposta_t", "humitat", "sabadell",
                 "pregunta_humitat", "pregunta_sabadell"]
        with open(B.CONFIRMACIONS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, camps)
            w.writeheader()
            w.writerow({"missatge": 9, "pregunta": "2026-10-27T06:01Z", "resposta": "no",
                        "resposta_t": "2026-10-27T06:02Z", "humitat": 99, "sabadell": 0,
                        "pregunta_humitat": 99, "pregunta_sabadell": 0})
        CF.al_dia(B.CONFIRMACIONS, ["humitat", "sabadell"])
        fila = CF.files(B.CONFIRMACIONS)[0]
        self.assertEqual((fila["val_per"], fila["humitat"], fila["pregunta_humitat"]), ("", "99", "99"))
        self.assertEqual(CF.val_per(fila), "resposta")

    def test_no_pregunta_si_no_toca(self):
        self.casa_amb(90)
        self.assertIsNone(B.pregunta(ARA, self.casa))
        self.casa_amb(99, plou=True)
        self.assertIsNone(B.pregunta(ARA, self.casa))
        self.casa_amb(99)
        self.assertIsNone(B.pregunta(ARA.replace(hour=3), self.casa))              # de nit no
