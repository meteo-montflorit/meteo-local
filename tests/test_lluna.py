# SPDX-License-Identifier: AGPL-3.0-or-later
"""La Lluna (lluna.py, ADR 0127), sense xarxa."""
import datetime as dt
import os
import sys
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lluna as LU  # noqa: E402

ZONA = ZoneInfo("Europe/Madrid")


class Lluna(unittest.TestCase):
    def test_la_lluna_plena_del_26_d_octubre(self):
        # Moongiant i Star Walk: 26-10-2026, a les 4:11-4:12 UTC.
        r = LU.calcula(dt.datetime(2026, 10, 25, 20, 0, tzinfo=ZONA))
        plena = next(f for f in r["fases"] if f["fase"] == "plena")
        t = dt.datetime.fromisoformat(plena["hora"]).astimezone(dt.timezone.utc)
        self.assertEqual((t.date(), t.hour), (dt.date(2026, 10, 26), 4))
        self.assertIn(t.minute, (11, 12, 13))
        self.assertEqual(plena["hora"][-6:], "+01:00")       # amb el desfasament, ja a l'hora d'hivern
        self.assertGreater(r["il_luminacio"], 95)
        self.assertTrue(170 < r["angle"] < 180)

    def test_les_fases_d_abans_i_les_que_venen_per_ordre(self):
        r = LU.calcula(dt.datetime(2026, 10, 27, 12, 0, tzinfo=ZONA))
        hores = [dt.datetime.fromisoformat(f["hora"]) for f in r["fases"]]
        self.assertEqual(hores, sorted(hores))
        self.assertEqual(r["fases"][0]["fase"], "plena")    # la d'ahir, perquè «Ara» la digui fins 12 h després
        self.assertGreaterEqual(len(r["fases"]), 4)

    def test_el_canvi_d_hora_no_mou_res(self):
        # El mateix instant, demanat amb un desfasament o amb un altre.
        a = LU.calcula(dt.datetime(2026, 10, 25, 1, 0, tzinfo=dt.timezone.utc))
        b = LU.calcula(dt.datetime(2026, 10, 25, 3, 0, tzinfo=dt.timezone(dt.timedelta(hours=2))))
        self.assertEqual(a["fases"], b["fases"])

    def test_sortida_i_posta_del_dia_local(self):
        r = LU.sortida_posta(dt.date(2026, 10, 25))
        for clau in ("sortida", "posta"):
            self.assertEqual(r[clau][:10], "2026-10-25")
        # Un cop al mes no surt (o no es pon) en tot el dia: llavors, None.
        buits = [d for d in range(30) if None in LU.sortida_posta(dt.date(2026, 11, 1) + dt.timedelta(days=d)).values()]
        self.assertTrue(1 <= len(buits) <= 3)


if __name__ == "__main__":
    unittest.main()
