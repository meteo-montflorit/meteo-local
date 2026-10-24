# SPDX-License-Identifier: AGPL-3.0-or-later
"""El cel tapat segons el satèl·lit, en observació, i la pregunta a Juanjo
quan discrepa de Sabadell (nuvols_satellit.py, ADR 0126). Sense xarxa."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import confirmacio as CF  # noqa: E402
import nuvols_satellit as S  # noqa: E402
import prevision as P  # noqa: E402

ARA = dt.datetime(2026, 10, 24, 12, 40, tzinfo=P.ZONA)


def png(nuvol, sere, buit=0):
    """Una imatge de la màscara: tants punts blancs (núvol), verds (serè) i transparents."""
    from PIL import Image
    im = Image.new("RGBA", (S.MIDA, S.MIDA), (0, 0, 0, 0))
    punts = [(255, 255, 255, 255)] * nuvol + [(0, 192, 0, 255)] * sere + [(0, 0, 0, 0)] * buit
    punts += [(0, 0, 0, 0)] * (S.MIDA * S.MIDA - len(punts))
    im.putdata(punts)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


class Resposta:
    def __init__(self, cos, tipus="image/png", avis=None):
        self.cos, self.headers = cos, {"Content-Type": tipus, **({"Warning": avis} if avis else {})}

    def read(self):
        return self.cos

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Satellit(unittest.TestCase):
    def test_el_percentatge_dels_pixels_amb_nuvol(self):
        n = S.MIDA * S.MIDA
        self.assertEqual(S.percentatge(png(n // 4, n - n // 4)), (25, n))
        # El transparent no compta; amb menys de la meitat amb dada, res.
        self.assertEqual(S.percentatge(png(n // 2, n // 4, n // 4)), (67, n - n // 4))
        self.assertEqual(S.percentatge(png(10, 10))[0], None)

    def test_discrepen_de_debo(self):
        self.assertTrue(S.discrepen(100, 0))
        self.assertTrue(S.discrepen(19, 87))
        self.assertFalse(S.discrepen(50, 100))
        self.assertFalse(S.discrepen(None, 100))

    def test_apunta_els_quarts_que_falten(self):
        with tempfile.TemporaryDirectory() as d:
            vell = S.OBSERVATS
            self.addCleanup(setattr, S, "OBSERVATS", vell)
            S.OBSERVATS = os.path.join(d, "s.csv")
            ara = dt.datetime(2026, 10, 24, 6, 20, tzinfo=dt.timezone.utc)
            demanats = []

            def obre(url, timeout):
                t = url.split("time=")[1]
                demanats.append(t)
                if t.startswith("2026-10-24T05:30"):
                    return Resposta(png(S.MIDA * S.MIDA, 0), avis="99 Nearest value used: time=...")
                if t.startswith("2026-10-24T05:15"):
                    return Resposta(b"<xml/>", "text/xml")
                return Resposta(png(S.MIDA * S.MIDA, 0))
            # Fins al quart publicat (05:45), des de 3 hores abans: 13 quarts;
            # el que el servidor no té (05:30, li'n donaria un altre) i l'error, no.
            self.assertEqual(S.apunta(ara, obre), 11)
            self.assertEqual(len(demanats), 13)
            fets = [f["t"] for f in CF.files(S.OBSERVATS)]
            self.assertNotIn("2026-10-24T05:30Z", fets)
            self.assertEqual(fets[-1], "2026-10-24T05:45Z")
            # A la passada següent, només els que faltaven.
            demanats.clear()
            self.assertEqual(S.apunta(ara, obre), 0)
            self.assertEqual(len(demanats), 2)


class Pregunta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        noms = ("OBSERVATS", "SABADELL", "PREGUNTES", "CONFIRMACIONS", "CONFIG_BOT", "telegram")
        vells = {k: getattr(S, k) for k in noms}
        self.addCleanup(lambda: [setattr(S, k, v) for k, v in vells.items()])
        for k, nom in zip(noms[:4], ("s.csv", "sab.csv", "p.csv", "c.csv")):
            setattr(S, k, os.path.join(self.dir.name, nom))
        S.CONFIG_BOT = os.path.join(self.dir.name, "bot.json")
        json.dump({"token": "x", "chat_id": 7}, open(S.CONFIG_BOT, "w"))
        self.crides = []

        def telegram(metode, **p):
            self.crides.append((metode, p))
            if metode == "sendMessage":
                return {"message_id": 60}, {"chat_id": 7}
            if metode == "getUpdates":
                return [{"callback_query": {"id": "q", "data": "cel:alts", "from": {"id": 7},
                                            "message": {"message_id": 60}}}], {"chat_id": 7}
            return True, {"chat_id": 7}
        S.telegram = telegram

    def observa(self, sat, sab, ara=ARA):
        CF.afegeix(S.OBSERVATS, S.CAMPS_OBSERVATS,
                   {"t": (ara - dt.timedelta(minutes=40)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                    "nuvols": sat, "pixels": 576})
        CF.afegeix(S.SABADELL, ["fins", "nuvols", "capes", "metars"],
                   {"fins": ara.replace(minute=0).strftime("%Y-%m-%dT%H:%M"), "nuvols": sab, "capes": 0, "metars": ""})

    def test_pregunta_quan_discrepen_i_apunta_la_resposta(self):
        self.observa(100, 0)
        self.assertEqual(S.pregunta(ARA), 60)
        text = self.crides[0][1]["text"]
        self.assertIn("El satélite lo ve cubierto (100 %) y el aeropuerto de Sabadell, despejado (0 %)", text)
        botons = self.crides[0][1]["reply_markup"]["inline_keyboard"]
        self.assertEqual([[b["callback_data"] for b in f] for f in botons],
                         [["cel:sere", "cel:alts"], ["cel:alguns", "cel:tapat"], ["cel:nose"]])
        self.assertIsNone(S.pregunta(ARA + dt.timedelta(hours=1)))     # no fins d'aquí a 4 h
        self.assertEqual(S.respostes(ARA + dt.timedelta(minutes=10)), 1)
        fila = CF.files(S.CONFIRMACIONS)[0]
        self.assertEqual((fila["resposta"], fila["pregunta_satellit"], fila["pregunta_sabadell"]), ("alts", "100", "0"))

    def test_no_pregunta_si_no_toca(self):
        self.observa(100, 75)
        self.assertIsNone(S.pregunta(ARA))                                 # no discrepen
        self.observa(100, 0, ARA.replace(hour=21))
        self.assertIsNone(S.pregunta(ARA.replace(hour=21)))                # de nit, no
        self.observa(100, 0, ARA + dt.timedelta(hours=3))
        self.assertIsNone(S.pregunta(ARA + dt.timedelta(hours=5)))         # observacions velles
        # Com a molt MAX_DIA al dia.
        for h in (9, 13, 17):
            t = ARA.replace(hour=h, minute=50)
            self.observa(0, 100, t)
            S.pregunta(t)
        self.assertEqual(len(CF.files(S.PREGUNTES)), S.MAX_DIA)


if __name__ == "__main__":
    unittest.main()
