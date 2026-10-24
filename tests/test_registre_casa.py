# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del registro de la página de casa (sin red)."""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import registre as R  # noqa: E402
import casa  # noqa: E402


TZ = dt.timezone(dt.timedelta(hours=2))


def lectura(hhmm, pluja, dia=5):
    h, m = map(int, hhmm.split(":"))
    return {"t": dt.datetime(2026, 10, dia, h, m, tzinfo=TZ), "pluja_avui": pluja}


class Registre(unittest.TestCase):
    def test_rehaz_la_pluja_de_casa(self):
        # El 06-10-2026 la hora de 20 a 21 quedó con 1,3 mm en lugar de 3,5 (ADR 0017).
        import tempfile
        from unittest import mock
        tz = dt.timezone(dt.timedelta(hours=2))
        with tempfile.TemporaryDirectory() as d:
            vell = R.ESTACIO_CASA
            R.ESTACIO_CASA = os.path.join(d, "estacio-casa.csv")
            try:
                with open(R.ESTACIO_CASA, "w") as f:
                    f.write("fins,pluja_mm,temperatura,humitat,rosada,pressio,solar\n"
                            "2026-10-06T21:00,1.3,20.1,99,19.9,1015,0\n2026-10-06T22:00,5.6,19.8,99,19.6,1014.7,0\n")
                lectura = lambda h, m, p: {"t": dt.datetime(2026, 10, 6, h, m, tzinfo=tz), "pluja_avui": p}
                historial = [lectura(20, 0, 0.0), lectura(20, 30, 1.0), lectura(21, 0, 3.5), lectura(22, 0, 9.1)]
                with mock.patch.object(R.E, "historial", return_value=historial):
                    self.assertEqual(R.rehaz_pluja_casa(dt.datetime(2026, 10, 8, 20, 0, tzinfo=tz)), 1)
                with open(R.ESTACIO_CASA) as f:
                    filas = f.read().splitlines()
                self.assertEqual(filas[1], "2026-10-06T21:00,3.5,20.1,99,19.9,1015,0")
                self.assertEqual(filas[2], "2026-10-06T22:00,5.6,19.8,99,19.6,1014.7,0")
                self.assertEqual(len([n for n in os.listdir(d) if ".bak-pluja-" in n]), 1)
            finally:
                R.ESTACIO_CASA = vell

    def test_avisos_y_plan_de_la_hora(self):
        # Lo oficial de cada hora, para que el modelo aprenda cuánto pesa (ADR 0047).
        avisos = [{"zona": casa.C.ZONA_AVISOS, "nivel": "groc", "tipo": "pluja",
                   "inicio": "2026-10-08T10:00:00+02:00", "fin": "2026-10-08T23:59:59+02:00"},
                  {"zona": casa.C.ZONA_AVISOS, "nivel": "groc", "tipo": "vent",
                   "inicio": "2026-10-08T06:00:00+02:00", "fin": "2026-10-08T09:00:00+02:00"}]
        plans = [{"pla": "INUNCAT", "fase": "emergència"}, {"pla": "INFOCAT", "fase": "alerta"}]
        tz = dt.timezone(dt.timedelta(hours=2))
        def senyals(h, avisos=avisos, plans=plans):
            fin = dt.datetime(2026, 10, 8, h, tzinfo=tz)
            return casa.senyals_avis(fin - dt.timedelta(hours=1), fin, avisos, plans)
        vell = casa.SMP_ACTUAL
        try:
            casa.SMP_ACTUAL = None
            self.assertEqual(senyals(11), {"avis_pluja": 1.0, "pla_inuncat": 1.0,
                                           "avis_meteocat": None, "avis_meteocat_alt": None})
            self.assertEqual(senyals(8)["avis_pluja"], 0.0)   # el de vent no compta
            self.assertEqual(senyals(11, plans=[{"pla": "INUNCAT", "fase": "prealerta"}])["pla_inuncat"], 0.0)
            # Si no s'han pogut llegir, no se sap: res de zeros.
            self.assertEqual(senyals(11, None, None), {"avis_pluja": None, "pla_inuncat": None,
                                                       "avis_meteocat": None, "avis_meteocat_alt": None})
            # Meteocat (ADR 0097): pluja o temps violent a la comarca, i si és de perill alt (grau 3 o més).
            casa.SMP_ACTUAL = {"avisos": [
                {"meteor": "Intensitat de pluja en 3 hores", "perill": 2, "dies": {"2026-10-08": [(12, 24)]}},
                {"meteor": "Intensitat de pluja en 30 minuts", "perill": 4, "dies": {"2026-10-08": [(18, 24)]}},
                {"meteor": "Ratxa màxima de vent", "perill": 4, "dies": {"2026-10-08": [(0, 24)]}}]}
            self.assertEqual([senyals(h)["avis_meteocat"] for h in (11, 13, 19)], [0.0, 1.0, 1.0])
            self.assertEqual([senyals(h)["avis_meteocat_alt"] for h in (11, 13, 19)], [0.0, 0.0, 1.0])
        finally:
            casa.SMP_ACTUAL = vell

    def test_riscos_de_la_hora(self):
        # ADR 0124: el registre desa els riscos propis que la gràfica pinta a
        # cada hora, com riscosHora de grafica.js: els previstos, si la franja
        # la toca; els d'ara, només a l'hora en curs.
        ara = dt.datetime(2026, 10, 19, 13, 20, tzinfo=TZ)
        riscos = [{"tipus": "ratxa", "nivell": "groc", "origen": "previsio",
                   "des_de": "2026-10-19T17:00+02:00", "fins": "2026-10-19T18:00+02:00"},
                  {"tipus": "pluja_30min", "nivell": "taronja", "origen": "mesura", "des_de": None, "fins": None}]
        hora = lambda h: (dt.datetime(2026, 10, 19, h, tzinfo=TZ), dt.datetime(2026, 10, 19, h + 1, tzinfo=TZ))  # noqa: E731
        self.assertEqual(casa.riscos_hora(*hora(17), riscos, ara), [{"tipus": "ratxa", "nivell": "groc"}])
        self.assertEqual(casa.riscos_hora(*hora(13), riscos, ara), [{"tipus": "pluja_30min", "nivell": "taronja"}])
        self.assertEqual(casa.riscos_hora(*hora(15), riscos, ara), [])
        self.assertEqual(casa.riscos_hora(*hora(15), None, ara), [])

    def test_cinc_minuts_de_casa(self):
        # Trams complets de 5 minuts; el que passa per mitjanit, amb l'acumulat que torna a zero.
        filas = [lectura("23:50", 5.0, dia=4), lectura("23:55", 5.4, dia=4), lectura("00:00", 5.6),
                 lectura("00:05", 0.2), lectura("00:10", 0.2), lectura("00:12", 0.4)]
        cincs = R.cincs_casa(filas)
        self.assertEqual(sorted(cincs), [lectura("23:55", 0, dia=4)["t"], lectura("00:00", 0)["t"],
                                         lectura("00:05", 0)["t"], lectura("00:10", 0)["t"]])
        self.assertAlmostEqual(cincs[lectura("00:00", 0)["t"]], 0.2)
        self.assertAlmostEqual(cincs[lectura("00:05", 0)["t"]], 0.2)   # 5,6 → 0,2: nou dia
        self.assertAlmostEqual(cincs[lectura("00:10", 0)["t"]], 0.0)
        # El de 00:10 a 00:15 no és complet (l'última lectura és de les 00:12).
        self.assertNotIn(lectura("00:15", 0)["t"], cincs)
        self.assertEqual(R.cincs_casa([]), {})

    def test_hores_de_meteocat(self):
        # Mitges hores en UTC (prevision.taula_meteocat): només les hores amb les dues.
        utc = lambda h, m: dt.datetime(2026, 10, 5, h, m, tzinfo=dt.timezone.utc)
        h = R.hores_meteocat([(utc(5, 30), 0.3), (utc(6, 0), 0.4), (utc(6, 30), 0.0), (utc(7, 0), 1.0)])
        # 6:00 i 6:30 UTC són l'hora de 8 a 9 local; la de 7 a 8 i la de 9 a 10 estan a mitges.
        self.assertEqual(list(h), [dt.datetime(2026, 10, 5, 9, 0, tzinfo=TZ)])
        self.assertAlmostEqual(h[dt.datetime(2026, 10, 5, 9, 0, tzinfo=TZ)], 0.4)
        self.assertEqual(R.hores_meteocat([]), {})

    def test_hores_d_una_veina_amb_el_vent(self):
        # Lectures cada 5 minuts d'una veïna (wunderground.files): la pluja de
        # l'hora per diferències i el vent de la lectura més a prop de l'hora.
        def v(hhmm, tot, vent):
            return {**lectura(hhmm, tot), "temperatura": 17.5, "humitat": 90.0, "rosada": 16.5, "pressio": 1010.0,
                    "vent": vent, "ratxa": vent * 2}
        filas = [v("06:00", 0.0, 1), v("06:30", 0.4, 3), v("07:00", 1.0, 5), v("07:30", 1.0, 2), v("08:00", 1.6, 4)]
        h = R.hores_veina(filas)
        set_, vuit = (dt.datetime(2026, 10, 5, x, 0, tzinfo=TZ) for x in (7, 8))
        self.assertEqual(list(h), [set_, vuit])
        self.assertAlmostEqual(h[set_]["pluja_mm"], 1.0)
        self.assertEqual((h[set_]["vent"], h[set_]["ratxa"], h[vuit]["vent"]), (5, 10, 4))
        self.assertNotIn("solar", h[set_])
        with tempfile.TemporaryDirectory() as d:
            vell = R.DIR
            R.DIR = d
            try:
                ara = dt.datetime(2026, 10, 6, 0, 10, tzinfo=TZ)
                self.assertTrue(R.falta_ahir_veina("ICERDA6", ara))       # sense registre
                R.apunta_veina("ICERDA6", h)
                with open(os.path.join(d, "veina-ICERDA6.csv")) as f:
                    linies = f.read().splitlines()
                self.assertEqual(linies[0], "fins,pluja_mm,temperatura,humitat,rosada,pressio,vent,ratxa")
                self.assertEqual(linies[1], "2026-10-05T07:00,1.0,17.5,90.0,16.5,1010.0,5,10")
                self.assertTrue(R.falta_ahir_veina("ICERDA6", ara))       # falta la de 23 a 24
                R.apunta_veina("ICERDA6", {dt.datetime(2026, 10, 6, 0, 0, tzinfo=TZ): {"pluja_mm": 0.0, "temperatura": 15.0}})
                self.assertFalse(R.falta_ahir_veina("ICERDA6", ara))
            finally:
                R.DIR = vell

    def test_apunta_meteocat_i_cinc_minuts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            vell = R.DIR, R.ESTACIO_CASA_5MIN
            R.DIR, R.ESTACIO_CASA_5MIN = d, os.path.join(d, "estacio-casa-5min.csv")
            try:
                R.apunta_meteocat("XV", {dt.datetime(2026, 10, 5, 9, 0, tzinfo=TZ): 0.4})
                R.apunta_meteocat("XV", {dt.datetime(2026, 10, 5, 10, 0, tzinfo=TZ): 1.2,
                                         dt.datetime(2026, 10, 5, 9, 0, tzinfo=TZ): 0.5})
                with open(os.path.join(d, "meteocat-XV.csv")) as f:
                    self.assertEqual(f.read().splitlines(),
                                     ["fins,pluja_mm", "2026-10-05T09:00,0.5", "2026-10-05T10:00,1.2"])
                R.apunta_casa_5min({lectura("00:05", 0)["t"]: 0.24})
                with open(R.ESTACIO_CASA_5MIN) as f:
                    self.assertEqual(f.read().splitlines(), ["fins,pluja_mm", "2026-10-05T00:05,0.2"])
            finally:
                R.DIR, R.ESTACIO_CASA_5MIN = vell


if __name__ == "__main__":
    unittest.main()


class VeinesCincMinuts(unittest.TestCase):
    def test_apunta_les_veines_sense_perdre_les_que_falten(self):
        # Una columna per veïna (ADR 0102); una passada en què falta una estació
        # conserva el que tenia apuntat.
        with tempfile.TemporaryDirectory() as d:
            vell = R.VEINES_5MIN
            R.VEINES_5MIN = os.path.join(d, "veines-5min.csv")
            try:
                fin = dt.datetime(2026, 10, 5, 20, 10, tzinfo=TZ)
                R.apunta_veines_5min({"ICERDA6": {fin: 0.2}, "ICERDA18": {fin: 0.0}, "ALTRA": {fin: 9}})
                R.apunta_veines_5min({"ICERDA6": {fin: 0.3, fin + dt.timedelta(minutes=5): 0.1}})
                import csv
                with open(R.VEINES_5MIN, encoding="utf-8") as f:
                    files = list(csv.DictReader(f))
                self.assertEqual(files[0]["fins"], "2026-10-05T20:10")
                self.assertEqual((files[0]["ICERDA6"], files[0]["ICERDA18"], files[0]["ICERDA28"]), ("0.3", "0.0", ""))
                self.assertEqual((files[1]["ICERDA6"], files[1]["ICERDA18"]), ("0.1", ""))
                self.assertNotIn("ALTRA", files[0])
            finally:
                R.VEINES_5MIN = vell

