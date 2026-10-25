# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de la estación de casa (ADR 0017), sin red."""
import datetime as dt
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import casa  # noqa: E402
import ecowitt as E  # noqa: E402
import registre as R  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=2))


def lectura(hhmm, pluja, temp=18.0, pressio=1010.0, dia="2026-10-05"):
    return {"t": dt.datetime.fromisoformat(f"{dia}T{hhmm}").replace(tzinfo=TZ), "pluja_avui": pluja,
            "temperatura": temp, "humitat": 90.0, "rosada": temp - 1, "pressio": pressio, "solar": 0.0}


class Ecowitt(unittest.TestCase):
    def test_hores_lluvia_y_lecturas(self):
        filas = [lectura("06:00", 0.0), lectura("06:30", 0.4), lectura("07:00", 1.0, 17.5),
                 lectura("07:30", 1.0), lectura("08:00", 1.6, 17.0)]
        h = E.hores(filas)
        siete, ocho = (dt.datetime(2026, 10, 5, x, 0, tzinfo=TZ) for x in (7, 8))
        self.assertEqual(list(h), [siete, ocho])
        self.assertAlmostEqual(h[siete]["pluja_mm"], 1.0)
        self.assertEqual(h[siete]["temperatura"], 17.5)
        self.assertAlmostEqual(h[ocho]["pluja_mm"], 0.6)
        # La primera hora, cortada, no cuenta: guardada encima de la buena,
        # apuntaba la lluvia de unos minutos (06-10-2026, ADR 0017).
        tallades = [lectura("20:55", 2.2), lectura("21:00", 3.5), lectura("21:30", 8.3), lectura("22:00", 8.9)]
        h = E.hores(tallades)
        self.assertEqual(list(h), [dt.datetime(2026, 10, 5, 22, 0, tzinfo=TZ)])
        self.assertAlmostEqual(h[dt.datetime(2026, 10, 5, 22, 0, tzinfo=TZ)]["pluja_mm"], 5.4)

    def test_medianoche_y_presion(self):
        filas = [lectura("23:30", 5.0, dia="2026-10-04"), lectura("00:00", 5.2, dia="2026-10-05"),
                 lectura("00:05", 0.1, dia="2026-10-05")]
        ini = dt.datetime(2026, 10, 4, 23, 0, tzinfo=TZ)
        self.assertAlmostEqual(E.pluja_entre(filas, ini, ini + dt.timedelta(hours=2)), 0.3)
        p = [lectura("09:00", 0, pressio=1012.0), lectura("12:00", 0, pressio=1009.5)]
        self.assertEqual(E.tendencia_pressio(p, p[1]["t"]), -2.5)

    def test_solo_cuenta_si_marca_lluvia(self):
        seco = {"plou": False, "hora": "2026-10-05T07:00+02:00"}
        self.assertIsNone(E.observacio(seco, "Casa"))
        mojado = {"plou": True, "hora": "2026-10-05T07:00+02:00", "pluja_avui": 3.0,
                  "pluja_30min": 1.2, "intensitat": 4.0}
        self.assertEqual(E.observacio(mojado, "Casa")["mm_ultima_media_hora"], 1.2)

    def test_plou_ara_amb_les_veines(self):
        # Plou si casa marca o si ho fa una veïna que compta (ADR 0060); la que no compta, no.
        sec = {"plou": False}
        compta, no_compta = {"plou": True, "compta": True}, {"plou": True, "compta": False}
        self.assertFalse(casa.llueve_ahora_en(sec, []))
        self.assertFalse(casa.llueve_ahora_en(sec, [no_compta]))
        self.assertTrue(casa.llueve_ahora_en(sec, [no_compta, compta]))
        self.assertTrue(casa.llueve_ahora_en({"plou": True}, None))
        self.assertFalse(casa.llueve_ahora_en(None, None))

    def test_consens_de_la_xarxa(self):
        # Juanjo, 13-10-2026: la lluvia y la humedad, por consenso de la red del barrio.
        def veina(est, pluja_1h, plou=False, rosada=15, intensitat=None, compta=True):
            files = [lectura("00:05", 3.0, dia="2026-10-13"), lectura("05:00", 3.0, dia="2026-10-13"),
                     lectura("06:00", 3.0 + pluja_1h, dia="2026-10-13")]
            # Como wunderground.veina_ara: la de hoy, de las mismas lecturas (el total de WU, aparte).
            return {"estacio": est, "hora": files[-1]["t"].isoformat(timespec="minutes"), "files": files,
                    "pluja_1h": pluja_1h, "pluja_avui": pluja_1h, "pluja_avui_wu": 99.0, "plou": plou,
                    "compta": compta, "rosada": rosada, "intensitat": intensitat}
        casa_ = {"pluja_1h": 0.0, "pluja_avui": 0.0, "plou": False, "intensitat": 0.0,
                 "temperatura": 18.0, "humitat": 70, "rosada": 12.0}
        veines = [veina("A", 4.0, True, 15, 6.0), veina("B", 2.0, True, 15, 2.0), veina("C", 3.0, False, 16),
                  veina("D", 9.0, True, 15, 20.0, compta=False)]
        r = casa.consens(dict(casa_), casa_, veines)
        # La mediana de casa (0, su cero no es fiable) y de las tres que cuentan (2, 3, 4).
        self.assertEqual(r["pluja_1h"], 2.5)
        self.assertEqual(r["pluja_1h_estacio"], 0.0)
        # Hoy, la mediana de las mismas cifras de cada estación (el total de 99 de WU no cuenta).
        self.assertEqual(r["pluja_avui"], 2.5)
        # Llueve, con la intensidad mediana de las que la marcan y cuentan (A y B).
        self.assertTrue(r["plou"])
        self.assertEqual(r["intensitat"], 4.0)
        # La humedad, con el rocío mediano de todas (12, 15, 15, 16, 15 → 15) y la temperatura de casa.
        self.assertEqual(r["rosada"], 15)
        self.assertEqual(r["humitat"], round(casa.SE.humitat(15, 18.0)))
        self.assertEqual(r["temperatura"], 18.0)
        # Sin vecinas, todo como lo mide casa.
        self.assertEqual(casa.consens(dict(casa_), casa_, []), casa_)
        # La persistencia de las primeras horas, con la misma lluvia.
        self.assertEqual(casa.consens_pluja(casa_, veines)["pluja_1h"], 2.5)
        self.assertEqual(casa.consens_pluja(None, veines[:1])["pluja_1h"], 4.0)

    def test_rosada_no_supera_la_temperatura(self):
        # Revisor, 19-10-2026: rocío 16 con 15,2 °C (vecinas en grados enteros, casa en la zona fría).
        casa_ = {"temperatura": 15.2, "humitat": 99, "rosada": 15.0}
        veines = [{"estacio": e, "rosada": 16, "compta": True} for e in ("A", "B", "C")]
        r = casa.consens(dict(casa_), casa_, veines)
        self.assertEqual(r["rosada"], 15.2)
        self.assertEqual(r["humitat"], 100)
        self.assertEqual(r["humitat_estacio"], 99)

    def test_la_de_15_minuts_tambe_per_consens(self):
        # Revisor, 18-10-2026: 0,3 mm en 15 minuts (només casa) i 0 a l'última hora (mediana).
        casa_ = {"pluja_15min": 0.3, "pluja_30min": 0.3, "pluja_1h": 0.3, "pluja_3h": 0.8, "pluja_avui": 4.0,
                 "plou": True, "intensitat": 1.8, "temperatura": 16.0}
        seca = {"compta": True, "pluja_15min": 0.0, "pluja_30min": 0.0, "pluja_1h": 0.0, "pluja_3h": 0.8,
                "plou": False}
        r = casa.consens(dict(casa_), casa_, [dict(seca), dict(seca)])
        self.assertLessEqual(r["pluja_15min"], r["pluja_30min"])
        self.assertLessEqual(r["pluja_30min"], r["pluja_1h"])
        self.assertEqual(r["pluja_15min_estacio"], 0.3)

    def test_sin_claves_no_esta_disponible(self):
        with mock.patch.dict(os.environ, {"HOME": tempfile.mkdtemp()}, clear=True):
            self.assertFalse(E.disponible())


class Casa(unittest.TestCase):
    def test_llueve_ahora_solo_si_casa_marca(self):
        # Només el pluviòmetre de casa, i només el sí (ADR 0017 i 0058).
        self.assertFalse(casa.llueve_ahora_en({"plou": False, "intensitat": 0.8}))
        self.assertTrue(casa.llueve_ahora_en({"plou": True}))
        self.assertFalse(casa.llueve_ahora_en(None))

    def test_error_del_modelo_al_prever(self):
        h = {"time": ["2026-10-05T08:00Z", "2026-10-05T09:00Z"],   # les 10 i les 11, en UTC (ADR 0128)
             "temperature_2m_meteofrance_seamless": [18.0, 20.0]}
        est = {"hora": "2026-10-05T10:30+02:00", "temperatura": 17.0, "rosada": 15.5, "pluja_1h": 0.4}
        d = casa.al_prever(None, h, est)
        self.assertEqual(d["error_temp_ara"], 2.0)      # 19,0 del modelo a las 10:30 - 17,0
        self.assertEqual(d["deficit_rosada_ara"], 1.5)
        self.assertEqual(d["pluja_1h_emes"], 0.4)       # la lluvia de la última hora en casa
        self.assertIsNone(casa.al_prever(None, h, None)["error_temp_ara"])
        self.assertIsNone(casa.al_prever(None, h, None)["pluja_1h_emes"])


class Registre(unittest.TestCase):
    def test_apunta_y_sobrescribe_horas(self):
        R.ESTACIO_CASA = os.path.join(tempfile.mkdtemp(), "estacio-casa.csv")
        R.DIR = os.path.dirname(R.ESTACIO_CASA)
        siete = dt.datetime(2026, 10, 5, 7, 0, tzinfo=TZ)
        R.apunta_estacio_casa({siete: {"pluja_mm": 0.0, "temperatura": 17.0}})
        R.apunta_estacio_casa({siete: {"pluja_mm": 0.4, "temperatura": 17.2},
                               siete + dt.timedelta(hours=1): {"pluja_mm": None, "temperatura": None}})
        with open(R.ESTACIO_CASA) as f:
            lineas = f.read().splitlines()
        self.assertEqual(lineas[0], ",".join(R.CAMPOS_ESTACIO_CASA))
        self.assertEqual(len(lineas), 2)                 # la hora vacía no se guarda
        self.assertTrue(lineas[1].startswith("2026-10-05T05:00Z,0.4,17.2"))



class PressioNivellMar(unittest.TestCase):
    def test_reduccio(self):
        # 07-10-2026, 18:30: la estación marcaba 1002,1 hPa a 23 °C; Open-Meteo
        # daba 1010,2 al nivel del mar y el METAR de Sabadell, QNH 1011.
        self.assertEqual(E.pressio_mar(1002.1, 23.0, 70), 1010.2)
        self.assertEqual(E.pressio_mar(1002.1, 23.0), 1010.2)      # config.ALTITUD_CASA_M
        self.assertEqual(E.pressio_mar(1002.1, None, 70), 1010.4)  # sin temperatura, 15 °C
        self.assertIsNone(E.pressio_mar(None, 20.0))
        self.assertEqual(E.pressio_mar(1000.0, 20.0, 0), 1000.0)

if __name__ == "__main__":
    unittest.main()
