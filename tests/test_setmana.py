# SPDX-License-Identifier: AGPL-3.0-or-later
"""La previsión de la semana (ADR 0122): la corrección con la estación y los días."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setmana as S  # noqa: E402

AVUI = dt.date(2026, 10, 23)


def hores(dies, valor):
    """Una serie por horas de Open-Meteo: los días dados, valor(dia, hora)."""
    temps, vals = [], []
    for d in dies:
        for h in range(24):
            temps.append(f"{d}T{h:02d}:00")
            vals.append(valor(d, h))
    return temps, vals


class Correccio(unittest.TestCase):
    def test_l_error_mitja_de_cada_antelacio(self):
        # La estación marca 2 °C más de máxima y 1 menos de mínima que ECMWF a 3 días vista.
        dies = [(AVUI - dt.timedelta(days=i)).isoformat() for i in range(1, 31)]
        temps, prev = hores(dies, lambda d, h: 20.0 if h == 15 else 10.0)
        mesurada = {f"{d}T{h:02d}:00": (22.0 if h == 15 else 9.0) for d in dies for h in range(24)}
        anteriors = {"time": temps, "temperature_2m_previous_day3": prev}
        self.assertEqual(S.correccio(AVUI, mesurada, anteriors), {3: [2.0, -1.0]})

    def test_sense_prou_dies_no_corregeix(self):
        dies = [(AVUI - dt.timedelta(days=i)).isoformat() for i in range(1, S.MIN_DIES)]
        temps, prev = hores(dies, lambda d, h: 15.0)
        mesurada = {f"{d}T{h:02d}:00": 16.0 for d in dies for h in range(24)}
        self.assertEqual(S.correccio(AVUI, mesurada, {"time": temps, "temperature_2m_previous_day2": prev}), {})

    def test_els_dies_amb_poques_hores_mesurades_no_compten(self):
        mesurada = {f"2026-10-20T{h:02d}:00": 15.0 for h in range(S.MIN_HORES - 1)}
        self.assertEqual(S.dies_mesurats(mesurada), {})


class Dies(unittest.TestCase):
    def test_la_setmana(self):
        dies = [(AVUI + dt.timedelta(days=i)).isoformat() for i in range(S.DIES)]
        temps, t = hores(dies, lambda d, h: 20.0 if h == 15 else 12.0)
        _, n = hores(dies, lambda d, h: 80 if 7 <= h < 21 else 0)
        _, c = hores(dies, lambda d, h: 95 if d == dies[3] and h == 18 else 3)
        model = {"time": temps, "temperature_2m": t, "cloud_cover": n, "weather_code": c}
        # Quatre membres: el dia 2, en dos plou 1 mm; en els altres, gens.
        ens = {"time": temps}
        for m in range(4):
            ens[f"precipitation_member{m:02d}"] = hores(dies, lambda d, h, m=m: 1.0 if d == dies[2] and h == 12 and m < 2 else 0.0)[1]
        res = S.dies(AVUI, model, ens, {1: [1.0, -1.0], 2: [0.5, -0.5]})
        self.assertEqual([d["dia"] for d in res], dies)
        # Avui, amb la correcció d'un dia vista; el tercer dia, sense correcció per a aquesta antelació.
        self.assertEqual((res[0]["max"], res[0]["min"], res[0]["corregit"]), (21.0, 11.0, True))
        self.assertEqual((res[2]["max"], res[2]["min"]), (20.5, 11.5))
        self.assertEqual((res[3]["max"], res[3]["corregit"]), (20.0, False))
        self.assertEqual(res[1]["nuvols"], 80)
        self.assertEqual((res[2]["probabilitat"], res[2]["pluja_mm"]), (0.5, 0.5))
        # Si plou, la dels membres que plouen: 1 mm, no la mitjana de 0,5.
        self.assertEqual((res[2]["pluja_si_plou"], res[2]["pluja_fins"]), (1.0, 1.0))
        self.assertEqual(res[1]["probabilitat"], 0.0)
        self.assertNotIn("pluja_si_plou", res[1])
        self.assertEqual(res[3]["codi"], 95)

    def test_si_plou_la_mediana_i_fins_on_pot_arribar(self):
        dies = [(AVUI + dt.timedelta(days=i)).isoformat() for i in range(S.DIES)]
        temps, t = hores(dies, lambda d, h: 15.0)
        model = {"time": temps, "temperature_2m": t}
        # Deu membres: set secs i, el dia 1, tres amb 1, 2 i 9 mm.
        ens = {"time": temps}
        for m, mm in enumerate([0, 0, 0, 0, 0, 0, 0, 1.0, 2.0, 9.0]):
            ens[f"precipitation_member{m:02d}"] = hores(dies, lambda d, h, mm=mm: mm if d == dies[1] and h == 12 else 0.0)[1]
        d = S.dies(AVUI, model, ens, {})[1]
        self.assertEqual((d["probabilitat"], d["pluja_mm"], d["pluja_si_plou"]), (0.3, 1.2, 2.0))
        self.assertEqual(d["pluja_fins"], 7.6)          # el percentil 90 dels que plouen

    def test_la_part_alta(self):
        # ADR 0123: la mateixa compta amb la diferència de la part alta de cada hora i la mateixa correcció.
        dies = [AVUI.isoformat()]
        temps, t = hores(dies, lambda d, h: 20.0 if h == 15 else 10.0)
        taula = {h: 2.0 for h in range(24)}
        res = S.dies(AVUI, {"time": temps, "temperature_2m": t}, {"time": []}, {1: [1.0, -1.0]}, taula)
        self.assertEqual((res[0]["max_alta"], res[0]["min_alta"]), (23.0, 11.0))
        self.assertEqual((res[0]["max"], res[0]["min"]), (21.0, 9.0))

    def test_els_dies_incomplets_no_surten(self):
        dies = [AVUI.isoformat()]
        temps, t = hores(dies, lambda d, h: 15.0)
        model = {"time": temps[:12], "temperature_2m": t[:12]}
        self.assertEqual(S.dies(AVUI, model, {"time": []}, {}), [])

    def test_sense_ensemble_no_hi_ha_pluja(self):
        dies = [AVUI.isoformat()]
        temps, t = hores(dies, lambda d, h: 15.0)
        res = S.dies(AVUI, {"time": temps, "temperature_2m": t}, {"time": []}, {})
        self.assertNotIn("probabilitat", res[0])


if __name__ == "__main__":
    unittest.main()
