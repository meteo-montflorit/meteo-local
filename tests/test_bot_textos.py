# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de los textos del bot de Telegram en los casos límite (bot/bot.py,
ADR 0034, 0053, 0054, 0072 y 0101): sin datos, datos viejos, la presión, el
radar y la madrugada. Sin red."""
import datetime as dt
import os
import sys
import unittest
import unittest.mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
sys.path.insert(0, os.path.join(ARREL, "bot"))
import bot as B  # noqa: E402

ARA = dt.datetime(2026, 10, 7, 7, 0).astimezone()


def hores(inici, n=24, pluja=()):
    """n files horàries des d'«inici»; les hores de «pluja» (hora local) amb el 80 %."""
    res = []
    for i in range(n):
        h = (inici + dt.timedelta(hours=i)).replace(minute=0, tzinfo=None)
        res.append({"hora": h.isoformat(timespec="minutes"),
                    "fins": (h + dt.timedelta(hours=1)).isoformat(timespec="minutes"),
                    "temperatura": 15, "probabilitat": 0.8 if h.hour in pluja else 0.0, "pluja_mm": 0})
    return res


def ara_casa(**extra):
    return {"generat": ARA.isoformat(), "ara_casa": {"temperatura": 16.2, "plou": False, "hora": ARA.isoformat(), **extra}}


class AraAlBot(unittest.TestCase):
    def test_sense_temperatura_nomes_l_ajuda(self):
        # Sense la mesura no hi ha res a dir del temps d'ara: l'ajuda, no un «0 °C».
        self.assertEqual(B.text_ara_bot({"generat": ARA.isoformat(), "ara_casa": {}}, "es", ARA), B.T["es"]["ajuda"])

    def test_la_pressio_estable_pujant_i_baixant_rapid(self):
        estable = B.text_ara_bot(ara_casa(pressio=1015.4, pressio_3h=0.5), "ca", ARA)
        self.assertTrue(estable.endswith("💧 pressió 1015 hPa, estable."))
        self.assertIn("presión 1015 hPa, subiendo rápido.", B.text_ara_bot(ara_casa(pressio=1015.4, pressio_3h=4), "es", ARA))
        self.assertIn("pressió 1015 hPa, baixant ràpid.", B.text_ara_bot(ara_casa(pressio=1015.4, pressio_3h=-4), "ca", ARA))
        # Per sota de 3,6 hPa en 3 hores, sense «ràpid».
        self.assertTrue(B.text_ara_bot(ara_casa(pressio=1015.4, pressio_3h=2), "ca", ARA).endswith("pujant."))

    def test_la_pluja_que_arriba_segons_el_radar(self):
        d = ara_casa()
        d["radar"] = {"hora": ARA.isoformat(), "imatge": "meteocat",
                      "arriba": (ARA + dt.timedelta(minutes=30)).isoformat()}
        text = B.text_ara_bot(d, "ca", ARA)
        # Només la primera línia del radar, amb la icona de la pluja.
        self.assertIn("\n🌧️ Arribaria pluja a Montflorit cap a les 07:30.\n", text + "\n")
        self.assertNotIn("Radar de Meteocat", text)


class RadarAlBot(unittest.TestCase):
    def radar(self, **r):
        return {"generat": ARA.isoformat(), "ara_casa": {"temperatura": 15, "plou": False},
                "radar": {"hora": ARA.isoformat(), "imatge": "meteocat", **r}}

    def test_arriba_i_possible(self):
        arriba = B.text_radar_bot(self.radar(arriba=(ARA + dt.timedelta(minutes=30)).isoformat()), "es", ARA)
        self.assertTrue(arriba.startswith("Llegaría lluvia a Montflorit hacia las 07:30.\n"))
        self.assertTrue(arriba.endswith("En directo: " + B.RADAR_EN_DIRECTE["meteocat"]))
        possible = B.text_radar_bot(self.radar(possible=(ARA + dt.timedelta(minutes=40)).isoformat()), "ca", ARA)
        self.assertTrue(possible.startswith("Pot arribar pluja a Montflorit cap a les 07:40."))

    def test_a_sobre_nomes_segons_el_radar_i_sense_fi(self):
        # ADR 0101: si cap estació no la mesura, es diu que només la veu el radar.
        text = B.text_radar_bot(self.radar(arriba=(ARA + dt.timedelta(minutes=2)).isoformat(), sense_fi=True), "ca", ARA)
        self.assertTrue(text.startswith("Pluja a sobre de Montflorit segons el radar; cap estació del barri no en mesura. "
                                        "No s'acaba en 2 hores (en entrenament: pot fallar)."))

    def test_sense_radar_o_dades_velles(self):
        self.assertEqual(B.text_radar_bot({"generat": ARA.isoformat()}, "es", ARA), "Ahora no hay datos del radar.")
        vell = {"generat": (ARA - dt.timedelta(hours=3)).isoformat(), "radar": {"hora": ARA.isoformat()}}
        self.assertEqual(B.text_radar_bot(vell, "ca", ARA), B.T["ca"]["velles_ara"].format("04:00"))


class SenseDades(unittest.TestCase):
    """Cada consulta diu que no hi ha dades o que són velles: mai un «tot bé» sense saber-ho."""

    def test_dades_velles_a_totes_les_consultes(self):
        vell = {"generat": (ARA - dt.timedelta(hours=3)).isoformat()}
        for funcio in (B.text_transit_bot, B.text_llum_bot, B.text_sol_bot, B.text_aire_bot, B.text_avisos_actius,
                       B.text_trens_bot, B.text_radar_bot):
            with self.subTest(funcio=funcio.__name__):
                self.assertEqual(funcio(vell, "ca", ARA), B.T["ca"]["velles_ara"].format("04:00"))
        # Sense hora de generació, «?».
        self.assertEqual(B.text_sol_bot({}, "es", ARA), B.T["es"]["velles_ara"].format("?"))

    def test_sense_la_dada_concreta(self):
        d = {"generat": ARA.isoformat()}
        self.assertEqual(B.text_transit_bot(d, "es", ARA), "Ahora no hay datos del tráfico.")
        self.assertEqual(B.text_sol_bot(d, "ca", ARA), "Ara no hi ha dades del sol.")
        self.assertEqual(B.text_aire_bot(d, "es", ARA), "Ahora no hay datos de la calidad del aire.")
        self.assertEqual(B.text_aire_bot({**d, "aire": {"index": None}}, "ca", ARA),
                         "Ara no hi ha dades de la qualitat de l'aire.")
        self.assertEqual(B.text_pollen_bot(d, "ca", ARA), "Ara no hi ha dades del pol·len.")
        # Un sol d'un altre dia no és el d'avui.
        self.assertEqual(B.text_sol_bot({**d, "sol": [{"dia": "2026-10-01", "sortida": "x", "posta": "y"}]}, "es", ARA),
                         "Ahora no hay datos del sol.")


class Trens(unittest.TestCase):
    def test_resum_dels_trens(self):
        linia = lambda estat: {"linia": "R4", "estat": estat}
        self.assertIsNone(B.text_trens_resum({}, "ca"))
        # De nit, tot fora d'horari: no es diu res.
        self.assertIsNone(B.text_trens_resum({"trens": {"linies": [linia("fora_horari")]}}, "ca"))
        self.assertTrue(B.text_trens_resum({"trens": {"linies": [linia("circula"), linia("fora_horari")]}}, "es")
                        .endswith("Trenes de Cerdanyola sin incidencias."))
        self.assertIn("R4 amb retard", B.text_trens_resum({"trens": {"linies": [linia("retard")]}}, "ca"))

    def test_circula_pero_no_s_ha_vist_cap_tren(self):
        d = {"generat": ARA.isoformat(),
             "trens": {"linies": [{"linia": "S2", "estacio": "Bellaterra", "estat": "circula", "no_vist": True}]}}
        text = B.text_trens_bot(d, "es", ARA)
        # El cercle ambre, no el verd: diu que circula, però no se n'ha vist cap.
        self.assertIn(B.CERCLE["mig"] + " <b>S2</b> (Bellaterra): sin incidencias (dice que circula, pero", text)
        self.assertEqual(B.cercle_tren({"estat": "circula"}), B.CERCLE["baix"])
        self.assertEqual(B.cercle_tren({"estat": "desconegut"}), B.CERCLE["nul"])


class Llum(unittest.TestCase):
    def test_quan_i_carrers(self):
        self.assertEqual(B.carrers_llum([], "ca"), "")
        self.assertEqual(B.carrers_llum(["Carrer A"], "es"), "; calle probable: Carrer A")
        self.assertEqual(B.carrers_llum(["A", "B"], "ca"), "; carrers probables: A o B")
        ahir = "2026-10-06T23:12:00+02:00"
        self.assertEqual(B.quan_llum(ahir, "ca", ARA), "el 06/10 a les 23:12")
        self.assertEqual(B.quan_llum(ahir, "es", ARA), "el 06/10 a las 23:12")
        self.assertEqual(B.quan_llum(ahir, "es", ARA, des_de=True), "desde el 06/10 a las 23:12")
        self.assertEqual(B.quan_llum("2026-10-07T05:30:00+02:00", "ca", ARA, des_de=True), "des de les 05:30")


class AvisosActius(unittest.TestCase):
    def test_el_pla_porta_el_comunicat(self):
        d = {"generat": ARA.isoformat(),
             "plans": [{"pla": "INUNCAT", "nom": "d'inundacions", "fase": "alerta", "comunicat": "https://x/c.pdf"}]}
        text = B.text_avisos_actius(d, "es", ARA)
        self.assertIn("Plan de inundaciones (INUNCAT) en fase de alerta. "
                      '<a href="https://x/c.pdf">Comunicado (PDF)</a>', text)

    def test_els_riscos_en_castella_si_avisos_bot_falla(self):
        # Si no es pot carregar avisos_bot (la còpia del repositori trencada), el
        # text de les dades: millor en català que cap avís.
        risc = {"nivell": "groc", "text": "Ratxes de 75 km/h."}
        with unittest.mock.patch.dict(sys.modules, {"avisos_bot": None}), \
                unittest.mock.patch.object(sys, "path", list(sys.path)):
            self.assertEqual(B.linies_riscos([risc], "es", ARA), [B.CERCLE_AVIS["groc"] + " Ratxes de 75 km/h."])


class Resum(unittest.TestCase):
    def test_avui_de_vespre_amb_pluja_de_matinada(self):
        # /avui a les 19 h: la nit fins a les 6 també, «De matinada», i el
        # paraigua en compta les hores.
        moment = ARA.replace(hour=19)
        d = {"generat": moment.isoformat(), "ara_casa": {"temperatura": 14, "plou": False},
             "hores": hores(moment, pluja=(2, 3))}
        text = B.resum(d, "ca", moment, avui=True)
        self.assertTrue(text.startswith("<b>Avui, dimecres, a Montflorit</b>"))
        self.assertIn("De matinada: pluja de 2 a 4 h (probabilitat fins al 80 %).", text)
        self.assertIn("Paraigua de 2 a 4 h.", text)
        es = B.resum(d, "es", moment, avui=True)
        self.assertIn("De madrugada: lluvia de 2 a 4 h", es)

    def test_hores_dels_avisos_de_meteocat(self):
        # Avui, si ja ha començat, «fins a»; si no, de quina a quina.
        self.assertEqual(B.hores_dia([[5, 12], [18, 24]], ARA.date(), ARA, "ca"), "fins a les 12:00 i de 18:00 a 00:00")
        self.assertEqual(B.hores_dia([[5, 12]], ARA.date(), ARA, "es"), "hasta las 12:00")
        self.assertEqual(B.hores_dia([[5, 12]], ARA.date() + dt.timedelta(days=1), ARA, "es"), "de 05:00 a 12:00")

    def test_temperatura_sense_dades(self):
        self.assertIsNone(B.compara_resum({}, []))
        self.assertEqual(B.text_alta([{"temperatura": None}], "ca"), "")
        self.assertIsNone(B.text_temperatura([{"temperatura": None}], "ca", "Temperatura"))
        # Amb la d'ara, encara que la previsió no en porti.
        self.assertEqual(B.text_temperatura([], "ca", "Ara", ara=16.4), "Ara: 16 °C.")


if __name__ == "__main__":
    unittest.main()
