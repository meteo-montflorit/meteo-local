# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de la comprobación del final de la lluvia (fi_pluja.py, ADR 0049)
con la lluvia de casa cada 5 minutos (registre.py)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fi_pluja as F  # noqa: E402
import registre as R  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=2))


def t(hhmm, dia=6):
    h, m = map(int, hhmm.split(":"))
    return dt.datetime(2026, 10, dia, h, m, tzinfo=TZ)


class CincMinuts(unittest.TestCase):
    def test_trams_complets(self):
        fila = lambda hhmm, prec: {"t": t(hhmm), "pluja_avui": prec}
        filas = [fila("20:03", 1.0), fila("20:05", 1.2), fila("20:07", 1.6), fila("20:10", 2.0), fila("20:12", 2.2)]
        cincs = R.cincs_casa(filas)
        # El de 20:00 a 20:05 comença a les 20:03: no és complet; el de 20:10 a 20:15 tampoc.
        self.assertEqual(list(cincs), [t("20:10")])
        self.assertAlmostEqual(cincs[t("20:10")], 0.8)


class Final(unittest.TestCase):
    def test_pluja_del_barri_cada_5_minuts(self):
        # La veritat única (ADR 0102): casa o dues veïnes que compten; sec si casa
        # i les que confirmen marquen zero; si no, no se sap (None).
        with tempfile.TemporaryDirectory() as d:
            vell = F.DIR
            F.DIR = d
            try:
                with open(os.path.join(d, "estacio-casa-5min.csv"), "w", encoding="utf-8") as f:
                    f.write("fins,pluja_mm\n2026-10-06T20:05,0.0\n2026-10-06T20:10,0.0\n2026-10-06T20:15,0.0\n"
                            "2026-10-06T20:20,0.3\n2026-10-06T20:25,0.0\n")
                with open(os.path.join(d, "veines-5min.csv"), "w", encoding="utf-8") as f:
                    f.write("fins,ICERDA6,ICERDA18,ICERDA28,ICERDA48\n"
                            "2026-10-06T20:05,0.2,0.1,,0.0\n"      # dues veïnes que compten: plou
                            "2026-10-06T20:10,0.2,0.0,0.0,0.0\n"   # una sola: no se sap
                            "2026-10-06T20:15,0.0,0.0,0.0,0.0\n"   # totes a zero: sec
                            "2026-10-06T20:30,0.0,0.0,0.0,0.0\n")  # sense casa: no se sap
                p = F.pluja_5min()
                self.assertEqual(p[t("20:05")], 0.2)                 # la mediana alta de les dues
                self.assertIsNone(p[t("20:10")])
                self.assertEqual(p[t("20:15")], 0.0)
                self.assertEqual(p[t("20:20")], 0.3)                 # casa mana si marca pluja
                self.assertIsNone(p[t("20:25")])                     # casa a zero sense veïnes
                self.assertIsNone(p[t("20:30")])
                # Els None ni tallen ni allarguen els episodis.
                self.assertEqual(F.episodis({t("20:05"): 0.2, t("20:10"): None, t("20:15"): 0.2, t("21:00"): 0.0}),
                                 [[t("20:00"), t("20:15")]])
            finally:
                F.DIR = vell

    def test_episodis(self):
        pluja = {t("20:05"): 0.2, t("20:10"): 1.0, t("20:35"): 0.2, t("21:20"): 0.2}
        pluja.update({t("22:00"): 0.0})
        # Una pausa de 25 minuts no talla; la de 45, sí. L'últim té 40 minuts de calma després: compta.
        self.assertEqual(F.episodis(pluja), [[t("20:00"), t("20:35")], [t("21:15"), t("21:20")]])
        # Si la pluja pot continuar (no hi ha prou calma registrada després), l'últim no compta.
        self.assertEqual(F.episodis({t("20:05"): 0.2, t("20:15"): 0.0}), [])

    def test_fi_previst(self):
        prob = [1.0, 0.9, 0.5, 0.1, 0.1, 0.3, 0.1, 0.1, 0.1, 0.0]
        # Baixa del 20 % a les 20:15, però a les 20:25 torna a pujar: el final, a les 20:30.
        self.assertEqual(F.fi_previst(t("20:00"), prob, t("20:00")), t("20:30"))
        self.assertIsNone(F.fi_previst(t("20:00"), [1.0] * 25, t("20:00")))

    def test_resultat_i_avis_una_vegada(self):
        with tempfile.TemporaryDirectory() as d:
            F.DIR, F.APRENENTATGE, F.AVIS = d, d, os.path.join(d, "avis-fi-pluja")
            with open(os.path.join(d, "estacio-casa-5min.csv"), "w") as f:
                f.write("fins,pluja_mm\n" + "".join(f"2026-10-06T{h},{mm}\n" for h, mm in
                        (("20:05", 0.4), ("20:10", 1.0), ("20:15", 0.6), ("20:20", 0.0), ("21:00", 0.0))))
            linia = lambda hora, prob: json.dumps({"t": f"2026-10-06T{hora}+02:00", "triada": "meteocat",
                                                   "fonts": {"meteocat": {"hora": f"2026-10-06T{hora}+02:00",
                                                                          "prob": prob}}})
            with open(os.path.join(d, "radar-fonts-2026-10.jsonl"), "w") as f:
                f.write(linia("20:05", [1, 1, 1, 0, 0, 0]) + "\n" + linia("20:10", [1] * 25) + "\n")
            casos, n = F.compara(F.pluja_5min(), F.passades())
            r = F.resultat(casos, n)
            self.assertEqual((r["episodis"], r["passades"], r["amb_final"], r["encerts"], r["sense_final"]),
                             (1, 2, 1, 1, 1))
            F.MIN_EPISODIS = 2
            self.assertIsNone(F.verifica(avisa=False))
            F.MIN_EPISODIS = 1
            self.assertIn("1 episodis", F.verifica(avisa=False))
            self.assertIsNone(F.verifica(avisa=False))       # una sola vegada
            F.MIN_EPISODIS = 5


    def test_fi_radar_per_a_la_pagina(self):
        nc = {"hora": "2026-10-08T19:00+02:00",
              "llocs": {"casa": [{"min": 5 * k, "prob": p} for k, p in enumerate([1, 1, 0.9, 0.1, 0.1, 0.1, 0.0])]}}
        with tempfile.TemporaryDirectory() as d:
            F.REGLA = os.path.join(d, "fi-pluja.json")
            self.assertEqual(F.fi_radar(nc, t("19:00", 8)), {"fi": "2026-10-08T17:15Z", "sense_fi": False})
            # La pluja encara no ha arribat: el final es busca des que arriba.
            self.assertEqual(F.fi_radar(nc, t("18:40", 8), "2026-10-08T19:20+02:00")["fi"], "2026-10-08T17:20Z")
            self.assertTrue(F.fi_radar({**nc, "llocs": {"casa": [{"min": 0, "prob": 1}] * 4}}, t("19:00", 8))["sense_fi"])
            self.assertIsNone(F.fi_radar(None, t("19:00", 8)))

    def test_apren_la_variant_que_menys_s_equivoca(self):
        with tempfile.TemporaryDirectory() as d:
            F.APRENENTATGE, F.REGLA, F.ATURA = d, os.path.join(d, "fi-pluja.json"), os.path.join(d, "atura")
            # Tres episodis en què la probabilitat baixa al 25 % just quan para la pluja:
            # amb el 20 % no s'hi veu mai el final; amb el 30 %, sí.
            pluja, regs = {}, []
            for dia in (6, 7, 8):
                for m in (5, 10, 15, 20):
                    pluja[t(f"20:{m:02d}", dia)] = 0.4
                pluja[t("21:00", dia)] = 0.0
                for m in (0, 5):
                    regs.append({"t": t(f"20:{m:02d}", dia).isoformat(), "triada": "meteocat",
                                 "fonts": {"meteocat": {"hora": t("20:00", dia).isoformat(),
                                                        "prob": [1, 1, 1, 1, 0.25, 0.25, 0.25, 0.25, 0.25]}}})
            F.PROPOSAT = os.path.join(d, "fi-pluja-proposat.json")
            text = F.aprèn(pluja, regs, avisa=False, avui="2026-10-09")
            self.assertIn("menys del 30 %", text)
            self.assertIn("episodis no usats per triar-la", text)
            # Auditoria del 09-10-2026: es proposa i s'aplica l'endemà, no el mateix dia.
            self.assertEqual(F.regla()["llindar"], 0.2)
            self.assertIsNone(F.aprèn(pluja, regs, avisa=False, avui="2026-10-09"))    # ja proposada: no es repeteix
            self.assertIsNone(F.aplica_proposta("2026-10-09"))                          # avui encara no
            self.assertIn("aplicada", F.aplica_proposta("2026-10-10"))
            self.assertEqual(F.regla()["llindar"], 0.3)
            self.assertFalse(os.path.exists(F.PROPOSAT))
            self.assertIsNone(F.aprèn(pluja, regs, avisa=False))       # ja és la millor
            open(F.ATURA, "w").close()
            os.remove(F.REGLA)
            self.assertIsNone(F.aprèn(pluja, regs, avisa=False))       # aturat

    def test_l_error_validat_deixa_fora_cada_episodi(self):
        # Auditoria del 09-10-2026: la variant es triava i es mesurava amb els
        # mateixos episodis. Dos episodis en què guanya el 30 % i un en què el
        # 30 % s'equivoca molt: en triar amb els altres, aquell surt a l'error.
        pluja, regs = {}, []
        for dia, baixa in ((6, 0.25), (7, 0.25), (8, 0.25)):
            for m in (5, 10, 15, 20):
                pluja[t(f"20:{m:02d}", dia)] = 0.4
            pluja[t("21:00", dia)] = 0.0
            prob = [1, 1, 1, 1, baixa, baixa, baixa, baixa, baixa]
            if dia == 8:        # el radar s'equivoca: baixa del 30 % quan encara plou 15 minuts
                prob = [1, baixa, baixa, baixa, baixa, baixa, baixa, baixa, baixa]
            regs.append({"t": t("20:00", dia).isoformat(), "triada": "meteocat",
                         "fonts": {"meteocat": {"hora": t("20:00", dia).isoformat(), "prob": prob}}})
        millor = min(F.VARIANTS, key=lambda v: F.error(F.compara(pluja, regs, v)[0]))
        self.assertEqual(millor["llindar"], 0.3)
        # Amb tots: error 5 (0, 0 i 15 minuts). Deixant cada episodi fora, el
        # mateix: en triar amb els altres dos també surt el 30 %, i el tercer costa 15.
        self.assertAlmostEqual(F.error(F.compara(pluja, regs, millor)[0]), 5.0)
        self.assertAlmostEqual(F.error_validat(pluja, regs), 5.0)
        # Un sol episodi en què guanya una altra regla no val: en triar sense
        # ell surt el 30 %, i l'error validat és el del 30 % en aquell episodi.
        pluja2 = {k: v for k, v in pluja.items() if k.day != 8}
        regs2 = [r for r in regs if "-08T" not in r["t"]]
        self.assertAlmostEqual(F.error_validat(pluja2, regs2), 0.0)



if __name__ == "__main__":
    unittest.main()
