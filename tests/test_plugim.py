# SPDX-License-Identifier: AGPL-3.0-or-later
"""El plugim que només veu el radar i la confirmació de Juanjo (casa.plugim_radar,
plugim.py; ADR 0019)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import casa  # noqa: E402
import config as C  # noqa: E402
import plugim as PG  # noqa: E402

ARA = dt.datetime(2026, 10, 18, 18, 45).astimezone()


def a_prop(n_mc, n_rv, mm=0.25, km=1.5):
    px = lambda n: [[km, 90, mm]] * n  # noqa: E731
    return {"meteocat": {"px": px(n_mc)}, "rainviewer": {"px": px(n_rv)}}


class Plugim(unittest.TestCase):
    def test_els_dos_radars_amb_ecos_febles_estesos(self):
        # El cas del 18-10-2026 a les 18:45: 31 i 27 píxels febles a 3 km o menys.
        self.assertEqual(casa.plugim_radar(a_prop(31, 27)), {"meteocat": 31, "rainviewer": 27, "si": True})
        # Un sol radar, o pocs píxels (els ecos solts del 10-10-2026), no.
        self.assertFalse(casa.plugim_radar(a_prop(31, 3))["si"])
        self.assertFalse(casa.plugim_radar(a_prop(2, 27))["si"])
        # Lluny de casa o pluja que ja compta, no són plugim a sobre.
        self.assertFalse(casa.plugim_radar(a_prop(31, 27, km=C.PLUGIM_KM + 1))["si"])
        self.assertFalse(casa.plugim_radar(a_prop(31, 27, mm=0.6))["si"])
        self.assertIsNone(casa.plugim_radar({"rainviewer": {"px": []}}))

    def test_l_estat_de_la_pluja(self):
        si = {"plugim": {"si": True}}
        self.assertEqual(casa.estat_pluja(si, False, ARA)["plugim"], True)
        self.assertEqual(casa.estat_pluja(si, False, ARA)["estat"], "no")
        # Si plou a les estacions, mana el que es mesura.
        self.assertNotIn("plugim", casa.estat_pluja(si, True, ARA))
        self.assertNotIn("plugim", casa.estat_pluja({"plugim": {"si": False}}, False, ARA))


class Confirmacio(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        vells = {k: getattr(PG, k) for k in ("PREGUNTES", "CONFIRMACIONS", "CONFIG_BOT", "CASA_JSON", "telegram")}
        self.addCleanup(lambda: [setattr(PG, k, v) for k, v in vells.items()])
        PG.PREGUNTES = os.path.join(self.dir.name, "p.csv")
        PG.CONFIRMACIONS = os.path.join(self.dir.name, "c.csv")
        PG.CONFIG_BOT = os.path.join(self.dir.name, "bot.json")
        json.dump({"token": "x", "chat_id": 7}, open(PG.CONFIG_BOT, "w"))
        self.casa = os.path.join(self.dir.name, "casa.json")
        PG.CASA_JSON = self.casa
        self.crides = []

        def telegram(metode, **p):
            self.crides.append((metode, p))
            if metode == "sendMessage":
                return {"message_id": 52}, {"chat_id": 7}
            if metode == "getUpdates":
                return [{"callback_query": {"id": "q", "data": "boira:si", "from": {"id": 7},
                                            "message": {"message_id": 41}}},
                        {"callback_query": {"id": "r", "data": "plugim:si", "from": {"id": 7},
                                            "message": {"message_id": 52}}}], {"chat_id": 7}
            return True, {"chat_id": 7}
        PG.telegram = telegram

    def casa_amb(self, plugim, mc=31, rv=27):
        with open(self.casa, "w") as f:
            json.dump({"pluja_ara": {"estat": "no", **({"plugim": True} if plugim else {})},
                       "radar": {"plugim": {"meteocat": mc, "rainviewer": rv, "si": plugim}}}, f)

    def test_pregunta_i_apunta_la_resposta(self):
        self.casa_amb(True)
        self.assertEqual(PG.pregunta(ARA, self.casa), 52)
        text = self.crides[0][1]["text"]
        self.assertIn("Meteocat, 31 puntos; RainViewer, 27", text)
        self.assertTrue(text.startswith("⚙️ Temps a Montflorit · "))
        self.assertIsNone(PG.pregunta(ARA + dt.timedelta(hours=1), self.casa))   # no fins d'aquí a 3 h
        # Només la resposta del plugim, no la de la boira. Respon més tard: val
        # per a aquell moment, amb les dades d'aleshores (Juanjo, 18-10-2026).
        self.casa_amb(False, 5, 30)
        tard = ARA + dt.timedelta(minutes=40)
        self.assertEqual(PG.respostes(tard), 1)
        self.assertEqual(PG.respostes(tard), 0)
        fila = __import__("confirmacio").files(PG.CONFIRMACIONS)[0]
        self.assertEqual((fila["resposta"], fila["resposta_t"], fila["meteocat"], fila["plugim"]),
                         ("si", __import__("hora").clau(tard), "5", "0"))
        self.assertEqual((fila["pregunta"], fila["pregunta_meteocat"], fila["pregunta_plugim"]),
                         (__import__("hora").clau(ARA), "31", "1"))
        edit = [p for m, p in self.crides if m == "editMessageReplyMarkup"][0]
        self.assertEqual(edit["reply_markup"]["inline_keyboard"][0][0]["text"], "Apuntado a las 19:25: Sí, llueve")

    def test_les_respostes_d_abans_passen_a_les_dades_de_la_pregunta(self):
        import confirmacio as CF
        with open(PG.CONFIRMACIONS, "w") as f:
            f.write("missatge,pregunta,resposta,meteocat,rainviewer\n431,2026-10-18T19:16+02:00,nose,17,32\n")
        CF.al_dia(PG.CONFIRMACIONS, PG.CAMPS)
        fila = CF.files(PG.CONFIRMACIONS)[0]
        self.assertEqual((fila["resposta"], fila["meteocat"], fila["pregunta_meteocat"], fila["pregunta_rainviewer"]),
                         ("nose", "", "17", "32"))
        CF.al_dia(PG.CONFIRMACIONS, PG.CAMPS)
        self.assertEqual(len(CF.files(PG.CONFIRMACIONS)), 1)

    def test_les_preguntes_d_abans_no_es_desquadren(self):
        import confirmacio as CF
        with open(PG.PREGUNTES, "w") as f:
            f.write("t,missatge,meteocat,rainviewer\n2026-10-18T13:16+02:00,431,17,32\n")
        self.casa_amb(True)
        PG.pregunta(ARA, self.casa)
        files = CF.files(PG.PREGUNTES)
        self.assertEqual([(x["missatge"], x["meteocat"], x["plugim"]) for x in files],
                         [("431", "17", ""), ("52", "31", "1")])

    def test_no_pregunta_si_no_toca(self):
        self.casa_amb(False)
        self.assertIsNone(PG.pregunta(ARA, self.casa))
        self.casa_amb(True)
        self.assertIsNone(PG.pregunta(ARA.replace(hour=3), self.casa))           # de nit no


if __name__ == "__main__":
    unittest.main()
