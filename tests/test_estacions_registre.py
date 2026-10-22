# SPDX-License-Identifier: AGPL-3.0-or-later
"""El registre del NAS (registre.py, ADR 0006, 0012 i 0017): la línia per hora
de casa, les temperatures per comparar amb ahir, l'ompliment amb l'historial
d'Ecowitt i el que no s'ha d'apuntar."""
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
import ecowitt as E  # noqa: E402
import registre as R  # noqa: E402
import sol_estacio as SE  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=2))


def hora(h, dia=15, m=0):
    return dt.datetime(2026, 10, dia, h, m, tzinfo=TZ)


class AmbRegistre(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.reg = os.path.join(self.dir.name, "registre")
        valors = {"DIR": self.reg, "ESTACIO_CASA": os.path.join(self.reg, "estacio-casa.csv"),
                  "ESTACIO_CASA_5MIN": os.path.join(self.reg, "estacio-casa-5min.csv"),
                  "VEINES_5MIN": os.path.join(self.reg, "veines-5min.csv"),
                  "CASA_DARRERA": os.path.join(self.reg, "casa-darrera")}
        for nom, valor in valors.items():
            p = mock.patch.object(R, nom, valor)
            p.start()
            self.addCleanup(p.stop)
        # Sense episodis de sol directe al termòmetre.
        p = mock.patch.object(SE, "EPISODIS", os.path.join(self.reg, "sol-estacio.csv"))
        p.start()
        self.addCleanup(p.stop)

    def files_casa(self):
        with open(R.ESTACIO_CASA, encoding="utf-8") as f:
            return list(csv.DictReader(f))


class HiHaRegistre(AmbRegistre):
    def test_nomes_si_hi_ha_la_carpeta_de_l_estat(self):
        # El registre viu dins /estat: n'hi ha prou que existeixi la carpeta mare.
        self.assertTrue(R.hay_registro())
        with mock.patch.object(R, "DIR", os.path.join(self.dir.name, "no-hi-es", "registre")):
            self.assertFalse(R.hay_registro())


class ResNoEsApunta(AmbRegistre):
    def test_sense_dades_no_es_crea_cap_fitxer(self):
        R.apunta_casa_5min({})
        R.apunta_meteocat("XV", {})
        R.apunta_veines_5min({"ALTRA": {hora(9): 1.0}})
        R.apunta_veina("ICERDA6", {hora(9): {"pluja_mm": None, "temperatura": None, "humitat": 80}})
        R.apunta_estacio_casa({hora(9): {"humitat": 80, "pressio": 1012}})
        self.assertFalse(os.path.exists(self.reg))

    def test_l_hora_de_la_veina_sense_vent_es_guarda_igual(self):
        filas = [{"t": hora(8, m=0), "pluja_avui": 0.0, "temperatura": 15.0, "vent": None},
                 {"t": hora(8, m=30), "pluja_avui": 0.2, "temperatura": 15.5, "vent": None},
                 {"t": hora(9, m=0), "pluja_avui": 0.4, "temperatura": 16.0, "vent": None}]
        h = R.hores_veina(filas)
        self.assertEqual(list(h), [hora(9)])
        self.assertEqual((h[hora(9)]["vent"], h[hora(9)]["ratxa"]), (None, None))
        self.assertAlmostEqual(h[hora(9)]["pluja_mm"], 0.4)


class Temperatures(AmbRegistre):
    def test_del_registre_i_de_la_passada(self):
        os.makedirs(self.reg)
        with open(R.ESTACIO_CASA, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=R.CAMPOS_ESTACIO_CASA)
            w.writeheader()
            w.writerow({"fins": "2026-10-12T09:00", "temperatura": "11.0"})   # fa més de 72 hores
            w.writerow({"fins": "2026-10-14T10:00", "temperatura": "13.04"})
            w.writerow({"fins": "2026-10-14T11:00", "temperatura": ""})
            w.writerow({"fins": "2026-10-15T09:00", "temperatura": "14.0"})
        recents = {hora(9): {"temperatura": 14.46}, hora(10): {"temperatura": 15.0},
                   hora(11): {"temperatura": None}, hora(9, dia=11): {"temperatura": 9.0}}
        res = R.temperatures_casa(hora(10, m=20), recents=recents)
        # Les lectures d'aquesta passada manen sobre el registre; ordenades per hora.
        self.assertEqual(res, {"2026-10-14T10:00": 13.0, "2026-10-15T09:00": 14.5, "2026-10-15T10:00": 15.0})
        self.assertEqual(list(res), sorted(res))

    def test_sense_registre_nomes_la_passada(self):
        self.assertEqual(R.temperatures_casa(hora(10), hores=2, recents={hora(9): {"temperatura": 12.0}}),
                         {"2026-10-15T09:00": 12.0})
        self.assertEqual(R.temperatures_casa(hora(10)), {})

    def test_num(self):
        self.assertEqual(R._num("12.34"), 12.3)
        self.assertIsNone(R._num(""))
        self.assertIsNone(R._num(None))
        self.assertIsNone(R._num("(s/d)"))


class Completa(AmbRegistre):
    def setUp(self):
        super().setUp()
        self.demanat = []

        def historial(desde, fins, cicle):
            self.demanat.append((desde, fins, cicle))
            return ["lectures"]

        def hores(filas):
            self.assertEqual(filas, ["lectures"])
            return {hora(9): {"temperatura": 14.0, "pluja_mm": 0.0}, hora(10): {"temperatura": None, "pluja_mm": None}}
        for nom, valor in (("historial", historial), ("hores", hores), ("disponible", lambda: True)):
            p = mock.patch.object(E, nom, valor)
            p.start()
            self.addCleanup(p.stop)

    def completa(self, ara):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            R.completa_estacio_casa(ara)
        return out.getvalue()

    def test_sense_claus_no_fa_res(self):
        with mock.patch.object(E, "disponible", lambda: False):
            self.assertIn("Sin claves de Ecowitt", self.completa(hora(11)))
        self.assertEqual(self.demanat, [])

    def test_sense_registre_dos_dies(self):
        ara = hora(11)
        text = self.completa(ara)
        self.assertEqual(self.demanat, [(ara - dt.timedelta(days=2), ara, "5min")])
        self.assertIn("Estació de casa completada des de 2026-10-13T11:00+02:00", text)
        # L'hora buida no es guarda.
        self.assertEqual([(r["fins"], r["temperatura"]) for r in self.files_casa()], [("2026-10-15T09:00", "14.0")])

    def test_des_de_la_darrera_hora_amb_temperatura(self):
        os.makedirs(self.reg)
        with open(R.ESTACIO_CASA, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=R.CAMPOS_ESTACIO_CASA)
            w.writeheader()
            w.writerow({"fins": "2026-10-10T07:00", "temperatura": "12.0", "pluja_mm": "0.0"})
            w.writerow({"fins": "2026-10-10T08:00", "temperatura": "", "pluja_mm": "0.0"})
        ara = hora(11)
        self.completa(ara)
        # Dues hores abans de la darrera amb temperatura, per tancar la pluja d'aquella hora.
        self.assertEqual(self.demanat[0][0], dt.datetime.fromisoformat("2026-10-10T05:00").astimezone())
        self.assertEqual([r["fins"] for r in self.files_casa()],
                         ["2026-10-10T07:00", "2026-10-10T08:00", "2026-10-15T09:00"])

    def test_com_a_molt_89_dies(self):
        os.makedirs(self.reg)
        with open(R.ESTACIO_CASA, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=R.CAMPOS_ESTACIO_CASA)
            w.writeheader()
            w.writerow({"fins": "2026-01-10T07:00", "temperatura": "2.0"})
        ara = hora(11)
        self.completa(ara)
        self.assertEqual(self.demanat[0][0], ara - dt.timedelta(days=R.ESTACIO_CASA_DIES_MAX))

    def test_rehaz_sense_registre(self):
        self.assertEqual(R.rehaz_pluja_casa(hora(11)), 0)
        self.assertEqual(self.demanat, [])


class LiniaDeCasa(AmbRegistre):
    def linies(self, mes="2026-10"):
        with open(os.path.join(self.reg, f"casa-{mes}.jsonl"), encoding="utf-8") as f:
            return [json.loads(x) for x in f]

    def test_una_linia_per_hora_de_rellotge(self):
        R.apunta_casa(hora(9, m=5), [{"h": 1}], {"temperatura": 14}, sant_cugat=0.2, veines={"ICERDA6": 0.0})
        R.apunta_casa(hora(9, m=35), [{"h": 2}])          # la mateixa hora: no
        R.apunta_casa(hora(10, m=5), [{"h": 3}])
        ls = self.linies()
        self.assertEqual([x["hores"] for x in ls], [[{"h": 1}], [{"h": 3}]])
        self.assertEqual(ls[0], {"emes": "2026-10-15T09:05+02:00", "ara_casa": {"temperatura": 14},
                                 "hores": [{"h": 1}], "sant_cugat": 0.2, "veines": {"ICERDA6": 0.0}})
        with open(R.CASA_DARRERA) as f:
            self.assertEqual(f.read(), "2026-10-15T10")

    def test_el_canvi_de_mes_va_a_un_altre_fitxer(self):
        R.apunta_casa(dt.datetime(2026, 10, 31, 23, 5, tzinfo=dt.timezone.utc), [])
        R.apunta_casa(dt.datetime(2026, 11, 1, 0, 5, tzinfo=dt.timezone.utc), [])
        self.assertEqual(len(self.linies("2026-10")), 1)
        self.assertEqual(len(self.linies("2026-11")), 1)


class LiniaOrdres(unittest.TestCase):
    def executa(self, args, d):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["registre.py", *args]), \
                mock.patch.dict(os.environ, {"REGISTRE_DIR": d}), \
                mock.patch.object(E, "disponible", lambda: False), contextlib.redirect_stdout(out):
            runpy.run_path(os.path.join(ARREL, "registre.py"), run_name="__main__")
        return out.getvalue()

    def test_ordres(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Sin claves de Ecowitt", self.executa(["estacio"], d))
            self.assertIn("Horas con la lluvia corregida: 0", self.executa(["rehaz-pluja-casa"], d))
            self.assertIn("python3 registre.py estacio", self.executa([], d))
            self.assertEqual(os.listdir(d), [])


if __name__ == "__main__":
    unittest.main()
