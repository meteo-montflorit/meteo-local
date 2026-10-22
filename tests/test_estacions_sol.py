# SPDX-License-Identifier: AGPL-3.0-or-later
"""El sol directe al termòmetre de casa amb el registre (sol_estacio.py, ADR 0081):
la correcció de cada passada, el repàs de l'historial i l'ús des de la línia d'ordres."""
import contextlib
import csv
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import config as C  # noqa: E402
import ecowitt as E  # noqa: E402
import sol_estacio as SE  # noqa: E402

ARA = dt.datetime(2026, 10, 15, 9, 0).astimezone()


def escriu_hores(ruta, valors):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fins", "temperatura"])
        w.writeheader()
        for c, v in valors.items():
            w.writerow({"fins": c, "temperatura": "" if v is None else v})


class AmbRegistre(unittest.TestCase):
    """Un registre temporal: casa 1 °C més freda que les veïnes les últimes 30 hores."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.reg = os.path.join(self.dir.name, "registre")
        os.makedirs(self.reg)
        for nom, valor in (("DIR", self.reg), ("EPISODIS", os.path.join(self.reg, "sol-estacio.csv")),
                           ("ESTAT", os.path.join(self.dir.name, "sol-estacio.json"))):
            p = mock.patch.object(SE, nom, valor)
            p.start()
            self.addCleanup(p.stop)
        casa, veina = {}, {}
        for h in range(0, 31):
            c = (ARA - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")
            casa[c], veina[c] = 10.0, 11.0
        escriu_hores(os.path.join(self.reg, "estacio-casa.csv"), casa)
        for e in C.VEINES:
            escriu_hores(os.path.join(self.reg, f"veina-{e}.csv"), veina)

    def estat(self):
        with open(SE.ESTAT, encoding="utf-8") as f:
            return json.load(f)


class Corregeix(AmbRegistre):
    def lectures(self, valors):
        return [{"t": ARA - dt.timedelta(minutes=5 * (len(valors) - i)), "temperatura": v} for i, v in enumerate(valors)]

    def veines(self, t=11.0, fa_min=5):
        hora = (ARA - dt.timedelta(minutes=fa_min)).isoformat()
        return [{"hora": hora, "temperatura": t} for _ in range(3)]

    def test_sense_registre_o_sense_dades_no_toca_res(self):
        self.assertIsNone(SE.corregeix(None, [], [], ARA))
        self.assertEqual(SE.corregeix({}, [], [], ARA), {})
        with mock.patch.object(SE, "DIR", os.path.join(self.dir.name, "no-hi-es")):
            ara_casa = {"hora": ARA.isoformat(), "temperatura": 15.0, "solar": 200}
            self.assertIs(SE.corregeix(ara_casa, self.lectures([9.0, 12.0]), self.veines(), ARA), ara_casa)
        self.assertFalse(os.path.exists(SE.ESTAT))

    def test_el_salt_es_corregeix_amb_la_humitat_i_s_apunta(self):
        rosada = SE.rosada(14.0, 60)
        ara_casa = {"hora": ARA.isoformat(), "temperatura": 14.0, "humitat": 60, "rosada": rosada, "solar": 150}
        res = SE.corregeix(ara_casa, self.lectures([10.0, 10.2, 11.5, 13.0]), self.veines(), ARA)
        # Esperada: mediana de les veïnes (11) + diferència habitual (−1) = 10.
        self.assertEqual(res["temperatura"], 10.0)
        self.assertEqual(res["temperatura_estacio"], 14.0)
        self.assertTrue(res["sol_directe"])
        # La rosada no canvia: a 10 °C la humitat de veritat és més alta que la mesurada.
        self.assertEqual(res["humitat_estacio"], 60)
        self.assertEqual(res["humitat"], round(SE.humitat(rosada, 10.0)))
        self.assertGreater(res["humitat"], 75)
        # L'original no es modifica.
        self.assertEqual(ara_casa["temperatura"], 14.0)
        self.assertEqual(self.estat()["inici"], ARA.isoformat(timespec="minutes"))
        self.assertEqual(SE.episodis(), [(ARA, ARA)])

    def test_sense_rosada_la_humitat_no_es_toca(self):
        ara_casa = {"hora": ARA.isoformat(), "temperatura": 14.0, "humitat": 60, "solar": 150}
        res = SE.corregeix(ara_casa, self.lectures([10.0, 13.0]), self.veines(), ARA)
        self.assertTrue(res["sol_directe"])
        self.assertEqual(res["humitat"], 60)
        self.assertNotIn("humitat_estacio", res)

    def test_l_episodi_acaba_i_ho_diu(self):
        inici = (ARA - dt.timedelta(minutes=30)).isoformat(timespec="minutes")
        with open(SE.ESTAT, "w", encoding="utf-8") as f:
            json.dump({"inici": inici, "exces_max": 3.0}, f)
        ara_casa = {"hora": ARA.isoformat(), "temperatura": 10.2, "solar": 300}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            res = SE.corregeix(ara_casa, self.lectures([13.0, 12.0, 11.0]), self.veines(), ARA)
        self.assertIs(res, ara_casa)
        self.assertNotIn("sol_directe", res)
        self.assertIn("acabat", err.getvalue())
        self.assertIsNone(self.estat())

    def test_l_episodi_segueix_i_allarga_el_registre(self):
        inici = ARA - dt.timedelta(minutes=30)
        SE.apunta(inici, inici, 2.0)
        with open(SE.ESTAT, "w", encoding="utf-8") as f:
            json.dump({"inici": inici.isoformat(timespec="minutes"), "exces_max": 2.0}, f)
        ara_casa = {"hora": ARA.isoformat(), "temperatura": 13.5, "solar": 300}
        res = SE.corregeix(ara_casa, self.lectures([13.5, 13.5]), self.veines(), ARA)
        self.assertTrue(res["sol_directe"])
        self.assertEqual(self.estat()["exces_max"], 3.5)
        self.assertEqual(SE.episodis(), [(inici, ARA)])

    def test_les_veines_velles_no_compten(self):
        ara_casa = {"hora": ARA.isoformat(), "temperatura": 14.0, "solar": 150}
        res = SE.corregeix(ara_casa, self.lectures([10.0, 13.0]), self.veines(fa_min=45), ARA)
        self.assertNotIn("sol_directe", res)
        self.assertIsNone(self.estat())

    def test_un_estat_espatllat_es_com_si_no_n_hi_hagues(self):
        with open(SE.ESTAT, "w", encoding="utf-8") as f:
            f.write("{no és json")
        ara_casa = {"hora": ARA.isoformat(), "temperatura": 10.0, "solar": 150}
        res = SE.corregeix(ara_casa, self.lectures([10.0, 10.0]), self.veines(), ARA)
        self.assertNotIn("sol_directe", res)
        self.assertIsNone(self.estat())

    def test_la_lectura_d_ara_ja_hi_es_i_no_es_duplica(self):
        # Si l'última fila ja és la d'ara, no s'hi afegeix: el salt es mira igual.
        files = self.lectures([10.0, 11.0]) + [{"t": ARA, "temperatura": 13.0}]
        ara_casa = {"hora": ARA.isoformat(), "temperatura": 13.0, "solar": 150}
        res = SE.corregeix(ara_casa, files, self.veines(), ARA)
        self.assertTrue(res["sol_directe"])
        self.assertEqual(res["temperatura"], 10.0)


class Esperades(AmbRegistre):
    def test_llegeix_el_registre_si_no_li_donen_les_hores(self):
        c = (ARA - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        t = dt.datetime.fromisoformat(c).astimezone()
        SE.apunta(t - dt.timedelta(minutes=10), t + dt.timedelta(minutes=10), 3.0)
        res = SE.amb_esperades({c: 16.0, "2026-10-15T10:00": 12.0}, ARA)
        self.assertEqual(res, {c: 10.0, "2026-10-15T10:00": 12.0})

    def test_sense_episodis_torna_una_copia(self):
        temps = {"2026-10-15T08:00": 9.0}
        res = SE.amb_esperades(temps, ARA, eps=[])
        self.assertEqual(res, temps)
        self.assertIsNot(res, temps)

    def test_llegeix_hores_amb_valors_buits_i_sense_fitxer(self):
        ruta = os.path.join(self.reg, "x.csv")
        escriu_hores(ruta, {"2026-10-15T08:00": None, "2026-10-15T09:00": "no"})
        self.assertEqual(SE._llegeix_hores(ruta), {"2026-10-15T08:00": None, "2026-10-15T09:00": None})
        self.assertEqual(SE._llegeix_hores(os.path.join(self.reg, "cap.csv")), {})


class Omple(AmbRegistre):
    def historial(self, valors, solar=200):
        inici = ARA - dt.timedelta(minutes=5 * len(valors))
        return [{"t": inici + dt.timedelta(minutes=5 * i), "temperatura": v, "solar": solar}
                for i, v in enumerate(valors)]

    def test_troba_l_episodi_i_l_apunta(self):
        # Les veïnes són a 11 a les hores registrades: l'esperada és 10.
        valors = [10.0] * 6 + [11.0, 12.5, 13.5, 13.0, 12.0, 10.1, 10.0, None]
        crides = []

        def historial(a, b, cicle):
            crides.append((a, b, cicle))
            return self.historial(valors)
        out = io.StringIO()
        with mock.patch.object(E, "historial", historial), contextlib.redirect_stdout(out):
            trobats = SE.omple(dies=2, ara=ARA)
        self.assertEqual(crides, [(ARA - dt.timedelta(days=2), ARA, "5min")])
        self.assertEqual(len(trobats), 1)
        a, b, exces = trobats[0]
        # Comença amb el salt (12,5, +2,5) i dura mentre és 0,7 °C o més per sobre.
        self.assertEqual(a, ARA - dt.timedelta(minutes=5 * (len(valors) - 7)))
        self.assertEqual(b, ARA - dt.timedelta(minutes=5 * (len(valors) - 10)))
        self.assertEqual(exces, 3.5)
        self.assertEqual(SE.episodis(), [(a, b)])
        self.assertIn("Diferència habitual: -1.0 °C. Episodis: 1", out.getvalue())

    def test_de_nit_no_hi_ha_episodis(self):
        valors = [10.0] * 6 + [11.0, 12.5, 13.5]
        out = io.StringIO()
        with mock.patch.object(E, "historial", lambda a, b, c: self.historial(valors, solar=0)), \
                contextlib.redirect_stdout(out):
            self.assertEqual(SE.omple(ara=ARA), [])
        self.assertEqual(SE.episodis(), [])
        self.assertIn("Episodis: 0", out.getvalue())

    def test_sense_diferencia_habitual_no_demana_l_historial(self):
        os.remove(os.path.join(self.reg, "estacio-casa.csv"))
        out = io.StringIO()
        with mock.patch.object(E, "historial", side_effect=AssertionError("no s'havia de cridar")), \
                contextlib.redirect_stdout(out):
            self.assertEqual(SE.omple(ara=ARA), [])
        self.assertIn("Encara no hi ha prou hores", out.getvalue())


class LiniaOrdres(unittest.TestCase):
    def executa(self, args, registre):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["sol_estacio.py", *args]), \
                mock.patch.dict(os.environ, {"REGISTRE_DIR": registre}), contextlib.redirect_stdout(out):
            runpy.run_path(os.path.join(ARREL, "sol_estacio.py"), run_name="__main__")
        return out.getvalue()

    def test_episodis_i_omple_i_l_us(self):
        with tempfile.TemporaryDirectory() as d:
            t = dt.datetime(2026, 10, 9, 8, 40).astimezone()
            SE.apunta(t, t + dt.timedelta(minutes=35), 3.0, os.path.join(d, "sol-estacio.csv"))
            self.assertEqual(self.executa(["episodis"], d).strip(), "09/10 08:40–09:15")
            # Sense registre de casa, «omple» només avisa.
            self.assertIn("Encara no hi ha prou hores", self.executa(["omple", "3"], d))
            with self.assertRaises(SystemExit) as cm:
                self.executa(["res"], d)
            self.assertIn("Uso:", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()
