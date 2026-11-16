# SPDX-License-Identifier: AGPL-3.0-or-later
"""El histórico de avisos que mandó el Meteocat en CSV (ADR 0097): las franjas
que Excel convirtió en fechas, los de tiempo violento sin franja y que solo
cuente la última actualización emitida antes de prever."""
import datetime as dt
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calibracio import avisos_descarrega as AD  # noqa: E402
from calibracio import pluja_casa_avisos as P  # noqa: E402

U = dt.timezone.utc
CAP = "Episodi;Meteor;Tipus;Data Emissió;Data Inici;Data Fi;Data Avís;Període;Perill;Comarca;Llindar;Comentari;Auxiliar"
FILES = [
    # Primera emisión: de 12 a 18 UTC («des-18»), grado 1.
    "10;Intensitat de pluja en 30 minuts;Avís;2025-10-01T08:00Z;2025-10-02T12:00Z;2025-10-02T17:59Z;"
    "2025-10-02T00:00Z;des-18;1;Vallès Occidental;> 20 mm;;False",
    # La actualización de las 20:00 la pasa a 06-12 («6-des») y grado 3.
    "10;Intensitat de pluja en 30 minuts;Avís;2025-10-01T20:00Z;2025-10-02T06:00Z;2025-10-02T11:59Z;"
    "2025-10-02T00:00Z;6-des;3;Vallès Occidental;> 40 mm;;False",
    # Tiempo violento, sin franja: de 05:24 a 07:24 UTC.
    "11;Temps violent;Avís temps violent;2025-10-03T05:25Z;2025-10-03T05:24Z;2025-10-03T07:24Z;"
    "2025-10-03T05:24Z;;3;Vallès Occidental;;;",
    # Viento: no cuenta para la lluvia.
    "12;Vent;Avís;2025-10-01T08:00Z;2025-10-02T12:00Z;2025-10-02T17:59Z;"
    "2025-10-02T00:00Z;des-18;1;Vallès Occidental;> 72 km/h;;False",
]


def t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=U)


class CsvMeteocat(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, "Avisos_VOcc_2025.csv"), "w", encoding="utf-8", newline="") as f:
            f.write("\r\n".join([CAP] + FILES) + "\r\n")
        grups = AD.meteocat_csv(self.dir)
        with mock.patch.object(P, "meteocat_csv", return_value=grups), \
                mock.patch.object(P, "DIR_METEOCAT_CSV", self.dir):
            self.m = P.avisos_meteocat()

    def senyal(self, inici, tall):
        return P.senyal_meteocat(self.m, t(inici), t(tall))

    def test_franja_que_excel_hizo_fecha(self):
        # Antes de la actualización vale la primera: 12-18 UTC, grado 1.
        self.assertEqual(self.senyal("2025-10-02T13:00", "2025-10-01T12:00"), (1.0, 0.0))
        self.assertEqual(self.senyal("2025-10-02T07:00", "2025-10-01T12:00"), (0.0, 0.0))

    def test_cuenta_la_ultima_actualizacion_emitida(self):
        # Después, la de 06-12 UTC y grado 3; la franja de la tarde ya no.
        self.assertEqual(self.senyal("2025-10-02T07:00", "2025-10-01T21:00"), (1.0, 1.0))
        self.assertEqual(self.senyal("2025-10-02T13:00", "2025-10-01T21:00"), (0.0, 0.0))

    def test_tiempo_violento_sin_franja_y_solo_ya_emitido(self):
        self.assertEqual(self.senyal("2025-10-03T06:00", "2025-10-03T05:30"), (1.0, 1.0))
        self.assertEqual(self.senyal("2025-10-03T06:00", "2025-10-03T05:00"), (0.0, 0.0))

    def test_fuera_de_lo_que_cubren(self):
        self.assertIsNone(self.senyal("2023-12-31T13:00", "2023-12-30T12:00"))
        self.assertIsNone(self.senyal("2026-11-20T13:00", "2026-11-19T12:00"))


if __name__ == "__main__":
    unittest.main()
