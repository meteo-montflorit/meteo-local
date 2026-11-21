# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de las situaciones de peligro de la página de casa (sin red ni Telegram)."""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import riscos as RS  # noqa: E402

AHORA = dt.datetime(2026, 10, 6, 12, 10).astimezone()


def hores(cambios=None, n=24):
    """n horas tranquilas desde las 12; cambios = {índice: {campo: valor}}."""
    res = []
    for i in range(n):
        ini = dt.datetime(2026, 10, 6, 12) + dt.timedelta(hours=i)
        f = {"hora": ini.strftime("%Y-%m-%dT%H:%M"),
             "fins": (ini + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
             "temperatura": 18, "pluja_mm": 0.0, "ratxa": 20, "neu": 0}
        f.update((cambios or {}).get(i, {}))
        res.append(f)
    return res


def salida(h=None, casa=None):
    d = {"hores": h if h is not None else hores(),
         "ara_casa": casa or {"pluja_30min": 0, "pluja_3h": 0, "plou": False, "temperatura": 18}}
    d["riscos"] = RS.detecta(d, AHORA)
    return d


class Deteccio(unittest.TestCase):
    def test_tranquil(self):
        self.assertEqual(salida()["riscos"], [])

    def test_ratxa_amb_tram_i_nivell(self):
        # Llindars de Meteocat (16-10-2026): més de 72 km/h, groc; més de 108, taronja.
        r = salida(hores({3: {"ratxa": 75}, 5: {"ratxa": 110}}))["riscos"]
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["tipus"], r[0]["nivell"], r[0]["valor"]), ("ratxa", "taronja", 110))
        self.assertEqual(salida(hores({3: {"ratxa": 72}}))["riscos"], [])     # cal passar-lo
        self.assertIn("avui de 15 a 18 h", r[0]["text"])

    def test_el_tram_de_vent_no_es_talla_a_la_finestra(self):
        # 21-11-2026: «ratxes de fins a 81 km/h, demà de 9 a 10 h» amb 79 km/h
        # de 10 a 11 h també per sobre del llindar: les 24 hores de la finestra
        # tallaven el tram (finestra de 24 h i el tram acabava a la 25a).
        h = hores({22: {"ratxa": 81}, 23: {"ratxa": 90}, 24: {"ratxa": 79}, 25: {"ratxa": 20}}, n=30)
        r = RS.detecta({"hores": h, "ara_casa": {"pluja_30min": 0, "pluja_3h": 0, "temperatura": 18}}, AHORA)
        self.assertEqual((r[0]["tipus"], r[0]["valor"]), ("ratxa", 90))
        self.assertEqual(r[0]["fins"], RS.H.clau(dt.datetime(2026, 10, 7, 13).astimezone()))   # fi de la 25a hora
        # Un tram que comença després de la finestra no és d'aquest avís.
        h = hores({26: {"ratxa": 120}}, n=30)
        self.assertEqual(RS.detecta({"hores": h, "ara_casa": {"temperatura": 18}}, AHORA), [])

    def test_pluja_prevista_amb_la_probabilitat(self):
        # Inventari del 18-10-2026: «Pluja intensa prevista: 65 mm» amb
        # «Sense pluja prevista» al resum. Les hores per sota del 20 % no hi
        # compten; si cap arriba al 50 %, es diu la probabilitat.
        fort = {i: {"pluja_mm": 25} for i in range(3, 6)}
        self.assertEqual(salida(hores({i: {**v, "probabilitat": 0.1} for i, v in fort.items()}))["riscos"], [])
        r = salida(hores({i: {**v, "probabilitat": 0.3} for i, v in fort.items()}))["riscos"]
        self.assertEqual(r[0]["tipus"], "pluja_3h")
        self.assertTrue(r[0]["text"].endswith("(probabilitat fins al 30 %)."))
        r = salida(hores({i: {**v, "probabilitat": 0.8} for i, v in fort.items()}))["riscos"]
        self.assertNotIn("probabilitat", r[0]["text"])

    def test_neu_amb_decimal(self):
        r = salida(hores({3: {"neu": 0.3}}))["riscos"]
        self.assertIn("0,3 cm", r[0]["text"])
        self.assertEqual(salida(hores({3: {"neu": 0.02}}))["riscos"], [])

    def test_pluja_24h_sense_cap_tram_fort(self):
        h = hores({i: {"pluja_mm": 6} for i in range(4, 22)})
        r = salida(h)["riscos"]
        self.assertEqual([x["tipus"] for x in r], ["pluja_24h"])
        self.assertEqual(r[0]["valor"], 108)

    def test_pluja_3h(self):
        r = salida(hores({4: {"pluja_mm": 25}, 5: {"pluja_mm": 30}, 6: {"pluja_mm": 10}}))["riscos"]
        self.assertEqual([(x["tipus"], x["nivell"], x["valor"]) for x in r], [("pluja_3h", "groc", 65)])
        self.assertIn("avui de 16 a 19 h", r[0]["text"])

    def test_mesura_ara_i_previsio_son_claus_diferents(self):
        r = salida(hores({0: {"pluja_mm": 65}}), casa={"pluja_30min": 42, "plou": True, "temperatura": 15})["riscos"]
        self.assertEqual({x["clau"]: x["nivell"] for x in r}, {"ara:pluja_30min": "taronja", "previsio:pluja_3h": "groc"})
        self.assertEqual(r[0]["nivell"], "taronja")   # el pitjor primer

    def test_pluja_de_la_xarxa(self):
        # «pluja_30min» i «pluja_3h» ja són la mediana de la xarxa del barri
        # (casa.consens): compten encara que ara mateix no plogui, i el zero no fa res.
        self.assertEqual(len(salida(casa={"pluja_30min": 25, "plou": False, "temperatura": 15})["riscos"]), 1)
        self.assertEqual(len(salida(casa={"pluja_3h": 61, "temperatura": 15})["riscos"]), 1)
        self.assertEqual(salida(casa={"pluja_30min": 0, "plou": True, "temperatura": 15})["riscos"], [])
        self.assertEqual(salida(casa={"pluja_30min": None, "temperatura": 15})["riscos"], [])
        self.assertEqual(salida(casa=None)["riscos"], [])     # sense estació, només la previsió

    def test_fred_i_neu(self):
        # Cerdanyola: fred intens per sota de −1,6 °C i molt intens per sota de
        # −3,6; neu, qualsevol gruix per sota de 300 m.
        h = hores({i: {"temperatura": -2, "neu": 0.5} for i in range(14, 20)})
        tipus = {x["tipus"]: x["nivell"] for x in salida(h)["riscos"]}
        self.assertEqual(tipus, {"fred": "groc", "neu_24h": "groc"})
        self.assertEqual(salida(hores({14: {"temperatura": -4}}))["riscos"][0]["nivell"], "taronja")
        self.assertEqual(salida(hores({14: {"temperatura": -1.6}}))["riscos"], [])
        r = salida(casa={"temperatura": 37.0})["riscos"]
        self.assertEqual((r[0]["tipus"], r[0]["nivell"], r[0]["text"]), ("calor", "groc", "Ara fa calor intensa: 37 °C."))

    def test_nomes_les_24_primeres_hores(self):
        # La taula pot arribar a 45 hores per donar demà sencer (ADR 0041); el risc, no.
        self.assertEqual(salida(hores({26: {"ratxa": 115}}, n=30))["riscos"], [])

    def test_sense_previsio(self):
        self.assertEqual(salida(h=[])["riscos"], [])


class Avis(unittest.TestCase):
    def setUp(self):
        self.estat = {"actius": {}}

    def pas(self, s, minuts):
        return RS.compara(self.estat, s, AHORA + dt.timedelta(minutes=minuts))

    def test_avisa_un_cop_puja_i_acaba(self):
        groc = salida(hores({3: {"ratxa": 75}}))
        self.assertIn("risc groc", self.pas(groc, 0))
        self.assertIsNone(self.pas(groc, 30))                                  # ja avisat
        self.assertIn("risc taronja", self.pas(salida(hores({3: {"ratxa": 112}})), 60))
        self.assertIsNone(self.pas(groc, 90))                                  # baixa: no avisa
        self.assertIsNone(self.pas(salida(), 120))                             # encara no fa 3 h
        self.assertIn("ja no", self.pas(salida(), 90 + 180))
        self.assertEqual(self.estat["actius"], {})
        self.assertIsNone(self.pas(salida(), 300))

    def test_sense_previsio_no_dona_per_acabat(self):
        self.pas(salida(hores({3: {"ratxa": 75}})), 0)
        self.assertIsNone(self.pas(salida(h=[]), 600))
        self.assertIn("previsio:ratxa", self.estat["actius"])

    def test_desa_i_llegeix(self):
        RS.ESTADO = os.path.join(tempfile.mkdtemp(), "riscos.json")
        ruta = os.path.join(os.path.dirname(RS.ESTADO), "casa.json")
        import json
        with open(ruta, "w") as f:
            json.dump(salida(hores({3: {"ratxa": 75}})), f)
        self.assertIn("risc groc", RS.avisa(ruta, AHORA))
        self.assertIsNone(RS.avisa(ruta, AHORA))



class Trams(unittest.TestCase):
    def test_dos_trams_separats_no_s_ajunten(self):
        # Ratxes avui de 15 a 16 h i demà de 3 a 4 h: el tram és el del pitjor
        # valor, no «avui de 15 a 4 h».
        r = salida(hores({3: {"ratxa": 75}, 15: {"ratxa": 80}}))["riscos"]
        self.assertEqual(len(r), 1)
        self.assertIn("demà de 3 a 4 h", r[0]["text"])
        r = salida(hores({3: {"ratxa": 80}, 15: {"ratxa": 75}}))["riscos"]
        self.assertIn("avui de 15 a 16 h", r[0]["text"])

if __name__ == "__main__":
    unittest.main()


class FontTest(unittest.TestCase):
    # Juanjo, 19-10-2026: «hay que indicar el origen de la alerta y a ser posible la validez
    # que tiene» i «dado que viene de un modelo no debe decir que la ha calculado nuestra web».
    def test_el_llindar_amb_la_xifra_que_es_mostra(self):
        # Revisor, 18-11-2026: 72,4 km/h passava el llindar de 72 i la fitxa
        # deia «de més de 72 km/h: AROME HD, fins a 72».
        self.assertIsNone(RS.nivell("ratxa", 72.4))
        self.assertEqual(RS.nivell("ratxa", 72.5), "groc")
        self.assertIsNone(RS.nivell("calor", 36.84))
        self.assertEqual(RS.nivell("calor", 36.85), "groc")
        self.assertIsNone(RS.nivell("fred", -1.64))
        self.assertEqual(RS.nivell("fred", -1.65), "groc")

    def test_ratxa_amb_els_models_que_hi_arriben(self):
        f = RS.font("ratxa", "previsio", {"meteofrance_arome_france_hd": 92.5, "meteofrance_arome_france": 36.0,
                                          "icon_eu": 11.5})
        self.assertIn("Origen: el model que en preveu més, AROME HD.", f["ca"])
        self.assertIn("només 1 també preveu ratxes de més de 72 km/h: AROME HD, fins a 93 km/h; AROME, només 36 km/h, "
                      "i ICON-EU, només 12 km/h. Previsió poc segura.", f["ca"])
        self.assertIn("solo 1 también prevé rachas de más de 72 km/h", f["es"])
        # El cas del 19-10-2026 a les 13:33, amb el text que va aprovar Juanjo.
        dos = RS.font("ratxa", "previsio", {"meteofrance_arome_france_hd": 92.5, "meteofrance_arome_france": 89,
                                            "icon_eu": 11.5})
        self.assertIn("Dels 3 models que es consulten, 2 també preveuen ratxes de més de 72 km/h: AROME HD, fins a "
                      "93 km/h, i AROME, fins a 89 km/h; ICON-EU, només 12 km/h. Una ratxa", dos["ca"])
        tots = RS.font("ratxa", "previsio", {"meteofrance_arome_france_hd": 80, "icon_eu": 75})
        self.assertIn("Els 2 models que es consulten també preveuen ratxes de més de 72 km/h: AROME HD, fins a 80 km/h, "
                      "i ICON-EU, fins a 75 km/h.", tots["ca"])

    def test_cada_risc_porta_font(self):
        for tipus, origen in (("pluja_30min", "ara"), ("pluja_3h", "ara"), ("pluja_3h", "previsio"),
                              ("pluja_24h", "previsio"), ("calor", "ara"), ("fred", "previsio"),
                              ("neu_24h", "previsio"), ("ratxa", "previsio")):
            f = RS.font(tipus, origen)
            self.assertTrue(f and f["ca"] and f["es"], (tipus, origen))
            self.assertNotIn("aquesta", f["ca"])

    def test_el_risc_de_ratxa_porta_els_models_del_tram(self):
        h = hores({3: {"ratxa": 75, "ratxes_models": {"icon_eu": 20, "meteofrance_arome_france_hd": 90}}})
        r = salida(h)["riscos"][0]
        self.assertIn("ICON-EU, només 20 km/h", r["font"]["ca"])

    def test_les_meitats_cap_amunt_com_la_web(self):
        # Revisor, 19-10-2026: la ratxa de 92,5 km/h, «92» a l'avís i «93» a la taula.
        self.assertEqual(RS.num(92.5, "ratxa"), "93")
        self.assertEqual(RS.num(36.85, "calor"), "36,9")
        self.assertIn("fins a 93 km/h", RS.risc("ratxa", "previsio", 92.5, AHORA, AHORA, AHORA)["text"])

