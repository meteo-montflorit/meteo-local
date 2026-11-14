# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del aviso de antes de llover en casa (sin red ni Telegram)."""
import csv
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nowcast as N  # noqa: E402
import pluja_arriba as PA  # noqa: E402

T0 = dt.datetime(2026, 10, 6, 17, 3).astimezone()


def a(minuts):
    return T0 + dt.timedelta(minutes=minuts)


def salida(ahora, arriba=None, plou=False, mm_h=2.0):
    """Datos de casa en una pasada: la llegada que da el radar (minutos desde
    T0) y si llueve en casa."""
    radar = {"hora": (ahora - dt.timedelta(minutes=15)).isoformat(timespec="minutes"),
             "imatge": "meteocat", "arriba": None, "arriba_mm_h": None}
    if arriba is not None:
        radar.update(arriba=a(arriba).isoformat(timespec="minutes"), arriba_mm_h=mm_h)
    return {"generat": ahora.isoformat(timespec="minutes"), "radar": radar,
            "ara_casa": {"intensitat": 1.2 if plou else 0, "plou": plou},
            "pluja_ara": {"estat": "plou" if plou else "no"}}


class Avis(unittest.TestCase):
    def passades(self, casos, mm_h=2.0):
        """Pasadas seguidas: (minuto, llegada, llueve[, mm/h]) -> textos y filas."""
        estat, textos, files = {"episodi": None}, [], []
        for minut, arriba, plou, *mm in casos:
            text, fila = PA.compara(estat, salida(a(minut), arriba, plou, *(mm or [mm_h])), a(minut))
            textos.append(text)
            if fila:
                files.append(fila)
        return textos, files, estat

    def test_avisa_entre_15_i_21_minuts_abans(self):
        # La lluvia llegaría a las 17:33. A falta de 30 y 24 minutos, nada;
        # a falta de 18, el aviso, y ya no se repite.
        textos, _, _ = self.passades([(0, 30, False), (6, 30, False), (12, 30, False),
                                      (18, 30, False), (24, 30, False)])
        self.assertEqual([bool(t) for t in textos], [False, False, True, False, False])
        self.assertIn("d'aquí a uns 18 minuts, cap a les 17:33", textos[2])
        self.assertIn("Seria feble", textos[2])
        self.assertIn("Radar de Meteocat de les 17:00", textos[2])

    def test_encert_i_registre(self):
        # Avisa a las 17:21, empieza a llover a las 17:33, para, y una hora
        # después de la última lluvia el episodio se apunta como acierto.
        textos, files, estat = self.passades(
            [(18, 30, False), (24, 30, False), (30, 30, True), (36, None, True), (42, None, False),
             (90, None, False), (97, None, False)])
        self.assertEqual(sum(bool(t) for t in textos), 1)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["resultat"], "encert")
        self.assertEqual((files[0]["minuts_previstos"], files[0]["minuts_reals"]), (12, 12))
        self.assertIsNone(estat["episodi"])

    def test_avis_sense_pluja_i_nou_episodi(self):
        # El radar la anuncia y no llega: fallo apuntado. Más de una hora
        # después, otra que se acerca vuelve a avisar.
        textos, files, _ = self.passades([(18, 30, False), (24, 30, False), (30, None, False),
                                          (86, None, False), (92, 104, False)])
        self.assertEqual([bool(t) for t in textos], [True, False, False, False, True])
        self.assertEqual(files[0]["resultat"], "avís sense pluja")

    def test_dins_del_mateix_episodi_no_repeteix(self):
        # Chubascos seguidos con menos de una hora entre ellos: un solo aviso.
        textos, files, _ = self.passades([(18, 30, False), (30, None, True), (60, 72, False),
                                          (66, 72, False), (72, None, True)])
        self.assertEqual(sum(bool(t) for t in textos), 1)
        self.assertEqual(files, [])

    def test_la_pluja_feble_no_avisa_pero_s_apunta(self):
        # 14-11-2026 (ADR 0022): de 21 avisos, 14 sense pluja, gairebé tots d'ecos
        # febles. Amb menys d'1,5 mm/h no s'avisa; el registre l'apunta com a callat,
        # amb el que hauria passat, per comprovar el llindar.
        textos, files, _ = self.passades([(18, 30, False), (24, 30, False), (30, None, False),
                                          (86, None, False), (92, None, False)], mm_h=0.7)
        self.assertEqual(sum(bool(t) for t in textos), 0)
        self.assertEqual((files[0]["resultat"], files[0]["callat"], files[0]["mm_h"]), ("avís sense pluja", "sí", 0.7))
        # Si abans de ploure deixa de ser feble, s'avisa llavors, un sol cop.
        textos, files, _ = self.passades([(18, 30, False, 0.7), (24, 36, False, 3.0), (30, 36, False, 3.0),
                                          (36, None, True), (100, None, False), (106, None, False)])
        self.assertEqual([bool(t) for t in textos], [False, True, False, False, False, False])
        self.assertEqual((files[0]["resultat"], files[0]["callat"], files[0]["mm_h"]), ("encert", "", 3.0))
        # Just al llindar s'avisa; sense la dada, també.
        self.assertTrue(self.passades([(18, 30, False, 1.5)])[0][0])
        self.assertTrue(self.passades([(18, 30, False, None)])[0][0])
        # Un cop ha plogut, la pluja feble que torna dins de l'episodi no reobre res.
        textos, _, estat = self.passades([(18, 30, False, 0.7), (24, None, True), (40, 50, False, 5.0)])
        self.assertEqual(sum(bool(t) for t in textos), 0)
        self.assertTrue(estat["episodi"]["avis"]["callat"])

    def test_pluja_sense_avis(self):
        # Empieza a llover sin que el radar la anunciara: no se manda nada
        # (ya llueve) y se apunta como lluvia sin aviso.
        textos, files, _ = self.passades([(0, None, False), (6, None, True), (12, None, False),
                                          (70, None, False), (78, None, False)])
        self.assertEqual(sum(bool(t) for t in textos), 0)
        self.assertEqual(files[0]["resultat"], "pluja sense avís")

    def test_pluja_a_sobre_segons_el_radar(self):
        # El radar ya la ve encima y las estaciones aún no marcan.
        textos, _, _ = self.passades([(0, -5, False)])
        self.assertIn("pot començar en qualsevol moment", textos[0])

    def test_intensitat(self):
        textos, _, _ = self.passades([(18, 30, False)])
        self.assertIn("Seria feble", textos[0])
        text, _ = PA.compara({"episodi": None}, salida(a(18), 30, mm_h=6.0), a(18))
        self.assertIn("Seria moderada", text)       # franges de Meteocat, com el radar
        text, _ = PA.compara({"episodi": None}, salida(a(18), 30, mm_h=45.0), a(18))
        self.assertIn("Seria forta", text)

    def test_plou_segons_la_web_no_nomes_casa(self):
        # La pluja d'ara és l'estat únic de la web (ADR 0101 i 0102): una veïna
        # que compta amb pluja i casa a zero és «plou». Una sortida vella, casa.
        s = salida(a(0), plou=False)
        s["pluja_ara"]["estat"] = "plou"
        self.assertTrue(PA.plou(s))
        s["pluja_ara"]["estat"] = "radar_sobre"
        self.assertFalse(PA.plou(s))
        del s["pluja_ara"]
        self.assertFalse(PA.plou(s))
        s["ara_casa"]["plou"] = True
        self.assertTrue(PA.plou(s))

    def test_sense_radar_no_falla(self):
        d = salida(T0)
        d["radar"] = None
        self.assertEqual(PA.compara({"episodi": None}, d, T0), (None, None))


class AlNas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.abans = (PA.DIR, PA.ESTADO, PA.REGISTRO)
        PA.DIR = os.path.join(self.tmp.name, "registre")
        PA.ESTADO = os.path.join(self.tmp.name, "avis-pluja.json")
        PA.REGISTRO = os.path.join(PA.DIR, "avisos-pluja.csv")
        self.addCleanup(lambda: setattr(PA, "DIR", self.abans[0]))
        self.addCleanup(lambda: setattr(PA, "ESTADO", self.abans[1]))
        self.addCleanup(lambda: setattr(PA, "REGISTRO", self.abans[2]))

    def passada(self, minut, arriba=None, plou=False, generat=None):
        ruta = os.path.join(self.tmp.name, "casa.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(salida(a(generat if generat is not None else minut), arriba, plou), f)
        return PA.avisa(ruta, a(minut))

    def test_estat_registre_i_resum(self):
        self.assertTrue(self.passada(18, 30))
        self.assertIsNone(self.passada(24, 30))
        self.assertIsNone(self.passada(30, plou=True))
        self.assertIsNone(self.passada(95))
        self.assertIsNone(PA.llegeix_estat()["episodi"])
        self.assertIn("Episodis: 1. Encerts: 1.", PA.resum())
        self.assertIn("12 minuts després", PA.resum())

    def test_el_registre_d_abans_guanya_la_columna_callat(self):
        # Un registre d'abans de la 3.224.0, sense «callat»: es reescriu amb la
        # capçalera d'ara i el resum compta a part els callats.
        os.makedirs(PA.DIR)
        with open(PA.REGISTRO, "w", encoding="utf-8") as f:
            f.write("inici,avisat,arribada_prevista,minuts_previstos,imatge,mm_h,pluja_mesurada,minuts_reals,resultat\n"
                    "2026-11-09T14:22Z,2026-11-09T14:22Z,2026-11-09T14:40Z,18,2026-11-09T14:20Z,2.14,"
                    "2026-11-09T14:58Z,36,encert\n")
        fila = dict.fromkeys(PA.CAMPOS, "")
        fila.update(inici="2026-11-14T12:10Z", avisat="2026-11-14T12:10Z", resultat="avís sense pluja", callat="sí")
        PA.apunta(fila)
        with open(PA.REGISTRO, encoding="utf-8") as f:
            files = list(csv.DictReader(f))
        self.assertEqual([list(x) for x in files], [PA.CAMPOS] * 2)
        self.assertEqual([(x["resultat"], x["callat"]) for x in files], [("encert", ""), ("avís sense pluja", "sí")])
        self.assertIn("Episodis: 1. Encerts: 1.", PA.resum())
        self.assertIn("Avisos callats per pluja feble (menys de 1.5 mm/h): 1; haurien encertat 0", PA.resum())

    def test_dades_velles_no_avisen(self):
        # La pasada ha fallado y los datos son de hace media hora.
        self.assertIsNone(self.passada(40, arriba=30, generat=10))
        self.assertIsNone(PA.llegeix_estat()["episodi"])


class Intensitat(unittest.TestCase):
    def test_intensitat_arribada(self):
        nc = {"llocs": {"casa": [{"min": 0, "mm_h": 0.0, "prob": 0.0}, {"min": 25, "mm_h": 0.4, "prob": 0.6},
                                 {"min": 40, "mm_h": 2.5, "prob": 0.9}, {"min": 70, "mm_h": 9.0, "prob": 1.0}]}}
        self.assertEqual(N.intensitat_arribada(nc), 2.5)
        self.assertIsNone(N.intensitat_arribada({"llocs": {"casa": [{"min": 0, "mm_h": 0, "prob": 0.1}]}}))
        self.assertIsNone(N.intensitat_arribada(None))


if __name__ == "__main__":
    unittest.main()
