# SPDX-License-Identifier: AGPL-3.0-or-later
"""Si la lluvia llega a la hora que dice el radar, y el retraso que se
aprende (arribada.py, ADR 0022)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import arribada as A  # noqa: E402

TZ = dt.timezone.utc


def t(hhmm, dia=1):
    h, m = map(int, hhmm.split(":"))
    return dt.datetime(2026, 11, dia, h, m, tzinfo=TZ)


def passada(hora, arriba_min, dia=1):
    """Una pasada a esa hora en que el radar da la llegada (la mitad del
    círculo con lluvia) arriba_min minutos después."""
    prob = [0.0] * (arriba_min // 5) + [1.0] * (25 - arriba_min // 5)
    return {"t": t(hora, dia).isoformat(), "triada": "meteocat",
            "fonts": {"meteocat": {"hora": t(hora, dia).isoformat(), "prob": prob}}}


class Arribada(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        abans = (A.APRENENTATGE, A.REGLA, A.PROPOSAT, A.ATURA)
        A.APRENENTATGE = self.tmp.name
        A.REGLA, A.PROPOSAT, A.ATURA = (os.path.join(self.tmp.name, n) for n in
                                        ("arribada.json", "arribada-proposat.json", "atura"))
        self.addCleanup(lambda: [setattr(A, k, v) for k, v in zip(("APRENENTATGE", "REGLA", "PROPOSAT", "ATURA"), abans)])

    def dies(self, retard, n=12):
        """n días: el radar dice a las 10:00 que llega a las 10:20 y empieza
        a llover retard minutos después de esa hora."""
        pluja, regs = {}, []
        for dia in range(1, n + 1):
            ini = t("10:20", dia) + dt.timedelta(minutes=retard)
            for k in range(1, 5):
                pluja[ini + dt.timedelta(minutes=5 * k)] = 1.0
            pluja[t("12:00", dia)] = 0.0
            regs.append(passada("10:00", 20, dia))
        return pluja, regs

    def test_casos(self):
        pluja, regs = self.dies(10, 1)
        self.assertEqual(A.casos(pluja, regs), [("2026-11-01T10:30Z", 10.0)])
        # Ja plovia, el radar ja la dona a sobre, la dona a més de mitja hora o no
        # plou a 45 minuts de l'hora dita: no compten.
        self.assertEqual(A.casos(pluja, [passada("10:40", 10)]), [])
        self.assertEqual(A.casos(pluja, [passada("10:25", 5)]), [])
        self.assertEqual(A.casos(pluja, [passada("09:30", 35)]), [])
        self.assertEqual(A.casos(pluja, [passada("09:00", 20)]), [])
        self.assertEqual(A.casos({}, regs), [])

    def test_sense_retard_no_proposa_res(self):
        # El 14-11-2026: l'hora del radar, encertada de mediana; no es toca.
        pluja, regs = self.dies(0)
        self.assertIsNone(A.aprèn(pluja, regs, avisa=False, avui="2026-11-14"))
        self.assertEqual(A.retard(), 0)
        ara = t("10:00")
        self.assertEqual(A.corregeix(t("10:20"), ara), t("10:20"))
        self.assertIsNone(A.corregeix(None, ara))

    def test_apren_el_retard_i_l_aplica_l_endema(self):
        pluja, regs = self.dies(15)
        self.assertIsNone(A.aprèn(*self.dies(15, 9), avisa=False, avui="2026-11-14"))    # pocs inicis
        text = A.aprèn(pluja, regs, avisa=False, avui="2026-11-14")
        self.assertIn("15 minuts més tard que l'hora del radar", text)
        self.assertEqual(A.retard(), 0)                                                  # avui encara no
        self.assertIsNone(A.aprèn(pluja, regs, avisa=False, avui="2026-11-14"))          # ja proposada
        self.assertIsNone(A.aplica_proposta("2026-11-14"))
        self.assertIn("aplicada", A.aplica_proposta("2026-11-15"))
        self.assertEqual(A.retard(), 15)
        with open(A.REGLA, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["des_de"], "2026-11-15")
        self.assertIsNone(A.aprèn(pluja, regs, avisa=False, avui="2026-11-15"))          # ja és la millor
        # L'hora, corregida; si el radar ja la dona a sobre, tal qual.
        ara = t("10:00")
        self.assertEqual(A.corregeix(t("10:20"), ara), t("10:35"))
        self.assertEqual(A.corregeix(t("10:03"), ara), t("10:03"))
        self.assertEqual(A.corregeix(t("09:50"), ara), t("09:50"))
        # «atura» ho para.
        os.remove(A.REGLA)
        open(A.ATURA, "w").close()
        self.assertIsNone(A.aprèn(pluja, regs, avisa=False, avui="2026-11-15"))


if __name__ == "__main__":
    unittest.main()
