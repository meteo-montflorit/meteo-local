# SPDX-License-Identifier: AGPL-3.0-or-later
"""La migració dels registres a UTC (migra_utc.py, ADR 0128), sense xarxa."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import migra_utc as M  # noqa: E402


class Migra(unittest.TestCase):
    def test_migra_una_vegada_amb_copia(self):
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "registre")
            os.makedirs(reg)
            with open(os.path.join(reg, "meteocat-XV.csv"), "w", encoding="utf-8") as f:
                f.write("fins,pluja_mm\n2026-10-25T03:00,0.4\n2026-10-25T02:00+02:00,0.2\n"
                        "2026-10-25T02:00+01:00,0.3\n2026-10-25T01:00,0.1\n")
            with open(os.path.join(reg, "casa-2026-10.jsonl"), "w", encoding="utf-8") as f:
                f.write(json.dumps({"emes": "2026-10-25T07:03+01:00", "dia": "2026-10-25", "text": "a les 2026-10-25T07:03",
                                    "hores": [{"fins": "2026-10-25T08:00"}], "per_hora": {"2026-10-25T09:00": 1}}) + "\n")
            fet = M.migra(reg)
            self.assertEqual(fet, {"meteocat-XV.csv": 4, "casa-2026-10.jsonl": 1})
            with open(os.path.join(reg, "meteocat-XV.csv"), encoding="utf-8") as f:
                self.assertEqual(f.read().split(), ["fins,pluja_mm", "2026-10-24T23:00Z,0.1", "2026-10-25T00:00Z,0.2",
                                                    "2026-10-25T01:00Z,0.3", "2026-10-25T02:00Z,0.4"])
            with open(os.path.join(reg, "casa-2026-10.jsonl"), encoding="utf-8") as f:
                l = json.loads(f.read())
            self.assertEqual((l["emes"], l["hores"][0]["fins"], list(l["per_hora"])),
                             ("2026-10-25T06:03Z", "2026-10-25T07:00Z", ["2026-10-25T08:00Z"]))
            # Les dates soles i els textos, tal com eren.
            self.assertEqual((l["dia"], l["text"]), ("2026-10-25", "a les 2026-10-25T07:03"))
            # La còpia d'abans, al costat, i la segona vegada no fa res.
            self.assertTrue(any(n.startswith("registre-abans-utc-") for n in os.listdir(d)))
            self.assertIsNone(M.migra(reg))

    def test_els_segons_es_conserven(self):
        self.assertEqual(M.valor("2026-10-18T03:59:59+02:00"), "2026-10-18T01:59:59Z")
        self.assertEqual(M.valor("2026-10-18T04:00:00+02:00"), "2026-10-18T02:00Z")
        self.assertEqual(M.valor("2026-10-18"), "2026-10-18")
        self.assertEqual(M.valor("2026-10-18T02:00Z"), "2026-10-18T02:00Z")


if __name__ == "__main__":
    unittest.main()
