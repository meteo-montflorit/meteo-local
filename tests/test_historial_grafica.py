# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del historial de la gráfica y del acierto de la previsión (historial.py, ADR 0099).
El otro test_historial.py es el de la página «Perill».""" 
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import historial as H  # noqa: E402


class Historial(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        reg = self.dir.name
        dia = "2026-10-16"
        with open(os.path.join(reg, "estacio-casa.csv"), "w", encoding="utf-8") as f:
            f.write("fins,pluja_mm,temperatura,humitat,rosada,pressio,solar\n")
            for h in range(1, 25):
                fins = f"{dia}T{h:02d}:00" if h < 24 else "2026-10-17T00:00"
                f.write(f"{fins},{1.0 if h in (20, 21) else 0.0},{15 + h % 10},90,12,1015,0\n")
        # Meteocat sec a totes les hores: el zero de casa val (aprenentatge.pluja_observada).
        import config as C
        for codi in C.ESTACIONES:
            with open(os.path.join(reg, f"meteocat-{codi}.csv"), "w", encoding="utf-8") as f:
                f.write("fins,pluja_mm\n" + "".join(
                    f"{(f'{dia}T{h:02d}:00' if h < 24 else '2026-10-17T00:00')},0.0\n" for h in range(1, 25)))
        # La previsió de les 7 i una altra de les 6 (no és la que compta).
        def emissio(emes, delta):
            hores = []
            for h in range(8, 25):
                fins = f"{dia}T{h:02d}:00" if h < 24 else "2026-10-17T00:00"
                hores.append({"fins": fins, "mostrat": {"temperatura": 15 + h % 10 + delta,
                                                         "probabilitat": 0.8 if h in (20, 21, 22) else 0.05,
                                                         "pluja_mm": 1.0}})
            return json.dumps({"emes": emes, "hores": hores})
        with open(os.path.join(reg, "casa-2026-10.jsonl"), "w", encoding="utf-8") as f:
            f.write(emissio(f"{dia}T06:03+02:00", 5) + "\n" + emissio(f"{dia}T07:03+02:00", 1) + "\n")
        # Sol directe sobre el termòmetre de 12:10 a 13:20 (ADR 0081): toca les hores
        # en punt de les 13 (i, per tant, els trams de 12 a 13 i de 13 a 14).
        with open(os.path.join(reg, "sol-estacio.csv"), "w", encoding="utf-8") as f:
            f.write(f"inici,fi,exces_max\n{dia}T12:10+02:00,{dia}T13:20+02:00,3.1\n")
        self.dies = H.tots(dt.date(2026, 10, 17), reg)

    def test_mesurat_i_previsions_per_antelacio(self):
        d = next(x for x in self.dies if x["dia"] == "2026-10-16")
        self.assertEqual(len(d["hores"]), 24)
        f = d["hores"][9]                                  # de 9 a 10
        # La temperatura del tram és la mitjana de les lectures de les 9 (24 °C) i
        # de les 10 (15 °C), que és el que anuncia la previsió (auditoria del
        # 18-10-2026: abans es comparava amb la lectura del final).
        self.assertEqual((f["hora"], f["temperatura"]), ("2026-10-16T09:00", 19.5))
        self.assertIsNone(d["hores"][0]["temperatura"])     # de 0 a 1: sense lectura de les 0
        # Les hores tocades pel sol porten la marca; les altres, no.
        self.assertTrue(d["hores"][12].get("sol") and d["hores"][13].get("sol"))
        self.assertFalse(d["hores"][11].get("sol") or d["hores"][14].get("sol"))
        # La de les 7:03, 2 h abans (16 °C); la de les 6:03, 3 h abans (20 °C).
        self.assertEqual(f["prev"]["2"][0], 16.0)
        self.assertEqual(f["prev"]["3"][0], 20.0)
        self.assertNotIn("prev", d["hores"][3])            # cap publicació abans de les 3

    def test_humitat_pressio_vent_i_nuvols(self):
        # ADR 0124 (formato 6): lo demás que se mide, para el historial de la
        # gráfica. La humedad y la presión, la media del principio y del final
        # de la hora; el viento de Sant Cugat, la media de las dos medias horas
        # y la racha mayor; el cielo tapado de Sabadell; lo que falta, no va.
        reg = self.dir.name
        dia = "2026-10-16"
        with open(os.path.join(reg, "vent-mitges-hores.csv"), "w", encoding="utf-8") as f:
            f.write("fins,XV,XV_ratxa,XF,XF_ratxa\n")
            f.write(f"{dia}T09:30,6.0,15.0,3,8\n{dia}T10:00,9.0,21.0,4,9\n{dia}T11:00,5.0,12.0,2,6\n")
        with open(os.path.join(reg, "nuvols-sabadell.csv"), "w", encoding="utf-8") as f:
            f.write(f"fins,nuvols,capes,metars\n{dia}T10:00,75,2,METAR\n")
        d = next(x for x in H.tots(dt.date(2026, 10, 17), reg) if x["dia"] == dia)
        f = d["hores"][9]                                  # de 9 a 10
        self.assertEqual((f["humitat"], f["pressio"]), (90, 1015.0))
        self.assertEqual((f["vent"], f["ratxa"], f["nuvols"]), (8, 21, 75))
        g = d["hores"][10]                                 # de 10 a 11: falta la media hora de les 10:30
        self.assertNotIn("vent", g)
        self.assertNotIn("ratxa", g)
        self.assertNotIn("nuvols", g)

    def test_les_alertes_de_cada_hora(self):
        # ADR 0124: a l'historial, les alertes de cada hora en el format de la
        # gràfica. El que pintava la gràfica (mostrat), si es va desar; si no,
        # l'AEMET de l'historial de «Perill» i Meteocat de la seva marca. I
        # sempre els plans, la prealerta, els incendis i la riera.
        reg = self.dir.name
        dia = "2026-10-16"
        with open(os.path.join(reg, "casa-2026-10.jsonl"), "w", encoding="utf-8") as f:
            hores = [{"fins": f"{dia}T{h:02d}:00", "avis_meteocat": 1.0 if h == 10 else 0.0, "avis_meteocat_alt": 0.0,
                      "mostrat": {"temperatura": 15, "probabilitat": 0, "pluja_mm": 0}} for h in range(9, 12)]
            hores.append({"fins": f"{dia}T13:00", "mostrat": {"temperatura": 15, "probabilitat": 0, "pluja_mm": 0,
                          "avisos": [{"nivell": "taronja", "tipus": ["pluja"], "font": "meteocat"}],
                          "riscos": [{"tipus": "ratxa", "nivell": "groc"}]}})
            f.write(json.dumps({"emes": f"{dia}T07:03+02:00", "hores": hores}) + "\n")
        avisos = os.path.join(reg, "avisos.json")
        with open(avisos, "w", encoding="utf-8") as f:
            json.dump({"historial": [
                {"clau": "aemet:tempestes:2026-10-16T08:00:00+02:00", "inici": "2026-10-15T20:00+02:00", "nivell": "groc",
                 "comenca": "2026-10-16T08:00:00+02:00", "fins": "2026-10-16T09:59:59+02:00"},
                {"clau": "pla:INUNCAT", "inici": "2026-10-16T09:30+02:00", "nivell": "pc", "ca": "🟠 <b>en fase d'alerta</b>",
                 "fi": "2026-10-16T11:10+02:00"},
                {"clau": "prealerta:INUNCAT", "inici": "2026-10-16T07:10+02:00", "nivell": "prealerta",
                 "fi": "2026-10-16T09:30+02:00"}]}, f)
        d = next(x for x in H.tots(dt.date(2026, 10, 17), reg, avisos=avisos) if x["dia"] == dia)
        h = {f["hora"][11:13]: f for f in d["hores"]}
        aemet = {"font": "aemet", "nivell": "groc", "tipus": ["tempestes"]}
        pre = {"font": "pc", "nivell": "groc", "tipus": ["INUNCAT"], "fase": "prealerta"}
        alerta = {"font": "pc", "nivell": "taronja", "tipus": ["INUNCAT"], "fase": "alerta"}
        # Sense mostrat.avisos: l'AEMET de «Perill» i Meteocat de la marca (la
        # de la fila que acaba a les 10, la de 9 a 10).
        self.assertEqual(h["08"]["avisos"], [aemet, pre])
        self.assertEqual(h["09"]["avisos"], [aemet, {"font": "meteocat", "nivell": "groc", "tipus": ["pluja"]}, alerta, pre])
        self.assertEqual(h["10"]["avisos"], [alerta])
        self.assertEqual(h["11"]["avisos"], [alerta])                # sense publicació: només «Perill»
        self.assertNotIn("avisos", h["13"])
        self.assertEqual(h["12"]["avisos"], [{"nivell": "taronja", "tipus": ["pluja"], "font": "meteocat"}])
        self.assertEqual(h["12"]["riscos_hora"], [{"tipus": "ratxa", "nivell": "groc"}])
        # Sense l'historial de «Perill», res d'ell.
        d = next(x for x in H.tots(dt.date(2026, 10, 17), reg) if x["dia"] == dia)
        self.assertNotIn("avisos", d["hores"][8])

    def test_encert_per_antelacio(self):
        e = next(x for x in self.dies if x["dia"] == "2026-10-16")["encert"]
        # Amb 1 h: el tram de 6 a 7 (mitjana 21,5 °C) amb la de les 6:03 (27 °C: 5,5
        # d'error) i el de 7 a 8 (22,5) amb la de les 7:03 (24: 1,5). Cada publicació
        # dona una hora per antelació.
        # El biaix (3.165.0, ADR 0110): +5,5 i +1,5, de mitjana +3,5 (diu més calor de la que fa).
        self.assertEqual(e["1"]["temperatura"], {"error": 3.5, "hores": 2, "biaix": 3.5})
        # Els mm esperats (probabilitat 0,05 per 1 mm, dues hores; ADR 0103) i els
        # mesurats, a les mateixes hores (18-10-2026).
        self.assertEqual(e["1"]["mm"], {"previst": 0.1, "mesurat": 0.0, "hores": 2})
        f = next(x for x in self.dies if x["dia"] == "2026-10-16")["hores"][9]
        self.assertEqual(f["prev"]["2"][2], 1.0)
        self.assertEqual(e["2"]["temperatura"]["hores"], 2)
        i = H.index(self.dies, dt.date(2026, 10, 17))
        self.assertEqual(i["encert"]["2"]["darrers"]["temperatura"]["hores"], 2)
        self.assertEqual(i["encert"]["2"]["darrers"]["mm"]["hores"], 2)
        self.assertEqual(list(i["encert"]["2"]["mesos"]), ["2026-10"])
        self.assertIn("2026-10-17", i["dies"])
        self.assertEqual(sorted(map(int, i["encert"])), list(range(1, 24)))

    def test_el_format_nou_es_refa_per_tandes(self):
        # 18-10-2026: tots els dies de cop eren 22 arxius i IONOS en vol 12 com a
        # molt. Cada passada, els 2 de sempre i 3 dels vells, fins que hi són tots.
        with tempfile.TemporaryDirectory() as reg, tempfile.TemporaryDirectory() as sortida:
            for f in os.listdir(self.dir.name):
                shutil.copy(os.path.join(self.dir.name, f), reg)
            avui = dt.date(2026, 10, 17)
            tandes = []
            while True:
                noms = H.fes(sortida, 2, avui, reg)
                tandes.append([n for n in noms if n != "historial.json"])
                if open(os.path.join(reg, "historial-format")).read() == str(H.FORMAT):
                    break
            dies = (avui - H.PRIMER_DIA).days + 1
            self.assertTrue(all(len(t) <= 5 for t in tandes))
            self.assertEqual(len({n for t in tandes for n in t}), dies)
            self.assertEqual(H.fes(sortida, 2, avui, reg), ["historial.json", "historial-2026-10-16.json",
                                                            "historial-2026-10-17.json"])

    def test_el_dia_del_canvi_d_hora_te_25_hores(self):
        self.assertEqual(len(H.hores_del_dia(dt.date(2026, 10, 25))), 25)
        self.assertEqual(len(H.hores_del_dia(dt.date(2027, 3, 28))), 23)

    def test_el_sol_no_compta_per_a_la_temperatura(self):
        # Amb 6 h d'antelació, la de les 6:03 dona el tram de 12 a 13 i la de les
        # 7:03 el de 13 a 14, tots dos tocats pel sol: cap compta. Amb 5 h, el d'11
        # a 12 sí i el de 12 a 13 no; amb 4 h, els dos.
        e = next(x for x in self.dies if x["dia"] == "2026-10-16")["encert"]
        self.assertEqual(e["6"]["temperatura"]["hores"], 0)
        self.assertEqual(e["5"]["temperatura"]["hores"], 1)
        self.assertEqual(e["4"]["temperatura"]["hores"], 2)

    def test_la_pluja_per_franges(self):
        # Per a cada franja de probabilitat anunciada: hores, en quantes va ploure
        # i la suma del que deia (auditoria del 18-10-2026: de 11 hores amb 70 % o
        # més, va ploure en 6). Es conserven «plou» i «sec» dels fitxers d'abans.
        def fila(p, mm):
            return {"temperatura": None, "pluja_mm": mm, "prev": {"1": [None, p, None]}}
        files = [fila(0.05, 0), fila(0.1, 0.5), fila(0.2, 0), fila(0.3, 0), fila(0.5, 1.0), fila(0.9, 1.0),
                 fila(0.7, 0), fila(0.95, 0.2), fila(None, 1.0), fila(0.5, None)]
        e = H.encert(files, 1)
        self.assertEqual(e["pluja"]["franges"], {"0": [2, 1, 0.15], "20": [2, 0, 0.5], "50": [1, 1, 0.5],
                                                 "70": [3, 2, 2.55]})
        self.assertEqual(e["pluja"]["plou"], [3, 4])
        self.assertEqual(e["pluja"]["sec"], [1, 2])
        self.assertEqual(H.franja(0.199), 0)
        self.assertEqual(H.franja(0.7), 70)
        s = H.suma([e, e])
        self.assertEqual(s["pluja"]["franges"]["70"], [6, 4, 5.1])
        # Un dia guardat sense franges (format 2) se suma igual.
        vell = {"temperatura": {"error": None, "hores": 0}, "pluja": {"plou": [0, 0], "sec": [0, 0]},
                "mm": {"previst": 0, "mesurat": 0, "hores": 0}}
        self.assertEqual(H.suma([e, vell])["pluja"]["franges"]["0"], [2, 1, 0.15])
        i = H.index(self.dies, dt.date(2026, 10, 17))
        self.assertEqual(i["franges"], [0, 20, 50, 70])

    def test_brier_i_climatologia(self):
        # 3.165.0, ADR 0110: el Brier sumat i, de la climatologia c, Σ(c − o)².
        def fila(p, mm):
            return {"temperatura": None, "pluja_mm": mm, "prev": {"1": [None, p, None]}}
        e = H.encert([fila(0.9, 1.0), fila(0.1, 0), fila(0.5, 0), fila(0.0, 0)], 1)
        self.assertEqual(e["pluja"]["brier"], [4, 1, 0.27])
        r = H.resum_pluja(e["pluja"]["brier"], 0.25)
        # Dir sempre 25 %: 0,5625 + 3 × 0,0625 = 0,75, 0,1875 per hora.
        self.assertEqual((r["brier"], r["clima"]), (0.0675, 0.1875))
        self.assertEqual(r["millora_clima"], 0.64)
        self.assertIsNone(H.resum_pluja([0, 0, 0.0], 0.1)["brier"])

    def test_index_amb_setmanes_i_sense_prou_per_dir_si_millora(self):
        i = H.index(self.dies, dt.date(2026, 10, 17))
        e = i["encert"]["1"]
        self.assertEqual([s["des_de"] for s in e["setmanes"]], ["2026-10-12"])
        self.assertTrue(e["setmanes"][0]["en_curs"])
        self.assertEqual(e["millora"], {"setmanes": 0, "cal": 2 * H.SETMANES_COMPARA})
        self.assertEqual(e["oficial"], {})

    def test_millora_compara_les_ultimes_setmanes_amb_les_anteriors(self):
        # Vuit setmanes completes: abans s'equivoca 2 °C cada hora; ara, entre 1 i 1,2 °C.
        ini = dt.date(2026, 8, 24)
        dies = []
        for k in range(56):
            d = ini + dt.timedelta(days=k)
            err = 2.0 if k < 28 else 1.0 + 0.1 * (k % 3)
            dies.append((d.isoformat(), {"temperatura": {"error": err, "hores": 20},
                                         "pluja": {"brier": [20, 2, 1.0]}}))
        m = H.millora(dies, dt.date(2026, 10, 19))
        self.assertEqual(m["setmanes"], 8)
        self.assertEqual(m["temperatura"]["abans"], 2.0)
        self.assertGreaterEqual(m["temperatura"]["seguretat"], 0.95)
        self.assertEqual(m["pluja"]["seguretat"], 0.0)       # igual: mai és menor

    def test_comparacio_amb_la_previsio_oficial_del_mateix_moment(self):
        # Una previsió oficial llegida a les 7:20: es compara amb la de la web de
        # les 7:03 (a menys de 35 minuts). De 9 a 10, 2 h d'antelació; l'oficial
        # diu 18 i 20 °C a les 9 i a les 10 (19 de mitjana) i la mesura és 19,5.
        oficial = {"t": {f"2026-10-16T{h:02d}:00": (18.0 if h == 9 else 20.0) for h in range(8, 24)},
                   "mm": {f"2026-10-16T{h:02d}:00": 0.0 for h in range(8, 24)}}
        s = dt.datetime(2026, 10, 16, 7, 20, tzinfo=H.P.ZONA)
        emes = H.emissions(self.dir.name)
        comp = H.comparacio(self.dies, emes, {"aemet": [(s, oficial)]})
        dia = comp["aemet"][2]["2026-10-16"]
        self.assertEqual(dia[0], 1)                  # de 9 a 10, l'única hora amb 2 h
        self.assertEqual(round(dia[2], 2), 0.5)      # |19 − 19,5|
        self.assertEqual(round(dia[1], 2), 3.5)      # la de les 7:03: 16 − 19,5
        # La pluja, amb 12 h: de 19 a 20 plou (1 mm a les 20); l'oficial diu que no.
        d12 = comp["aemet"][12]["2026-10-16"]
        self.assertEqual((d12[5], d12[6]), (1, 1))
        self.assertEqual(round(d12[8], 2), 1.0)
        self.assertEqual(round(d12[7], 2), 0.04)     # la web deia 80 %
        # Sense cap publicació a prop (llegida a les 4:00), res.
        self.assertEqual(H.comparacio(self.dies, emes, {"aemet": [(s - dt.timedelta(hours=3, minutes=20), oficial)]}),
                         {"meteocat": {}, "aemet": {}})
        r = H.resum_comparacio(comp["aemet"][2])
        self.assertEqual((r["temperatura"]["web"], r["temperatura"]["oficial"]), (3.5, 0.5))
        self.assertIsNone(r["temperatura"]["seguretat"])   # un sol dia: no hi ha seguretat

    def test_aprenentatge_i_canvis_amb_data(self):
        # ADR 0110: el que la pàgina explica de l'aprenentatge i els canvis que la
        # web ha fet sola, amb la data (Juanjo, 20-10-2026: «las mejoras que hay dia a dia»).
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "historial.csv"), "w", encoding="utf-8") as f:
                f.write("dia,pluja,temperatura,mostres_pluja,hores_pluja,error_pluja,error_pluja_arxiu,dies_temperatura,"
                        "error_temp,error_temp_model\n2026-10-18,arxiu,arxiu,10,12,0.08,0.04,13,0.96,0.94\n"
                        "2026-10-19,local,arxiu,10,31,0.03,0.04,14,1.11,1.07\n")
            with open(os.path.join(d, "radar-font.json"), "w") as f:
                json.dump({"preferida": "rainviewer", "des_de": "2026-10-07", "comparacio": {
                    "seguretat_rainviewer": 0.977, "parelles": 900, "amb_pluja": 40, "brier_meteocat": 0.031,
                    "brier_rainviewer": 0.022}}, f)
            with open(os.path.join(d, "nuvols-pesos.json"), "w") as f:
                json.dump({"pesos": {"arome": 0.5, "gfs": 0.5}, "comparacio": {
                    "dies": 7, "error_actual": 20.5, "error_arome": 22.0, "error_gfs": 25.1}}, f)
            with open(os.path.join(d, "fi-pluja.json"), "w") as f:
                json.dump({"llindar": 0.3, "des_de": "2026-10-19"}, f)
            # La humedad (ADR 0114), en su archivo: el cambio al barrio, también.
            with open(os.path.join(d, "historial-humitat.csv"), "w", encoding="utf-8") as f:
                f.write("dia,humitat,dies,mostres,error_rosada,error_rosada_abans,seguretat,error_humitat,"
                        "error_humitat_abans\n2026-10-17,arxiu,13,900,0.9,1.0,0.8,4.1,4.4\n"
                        "2026-10-18,barri,14,980,0.8,1.0,0.97,3.8,4.4\n")
            a = H.aprenentatge(d)
        self.assertEqual(a["dies"][-1]["error_pluja_vigent"], 0.04)
        self.assertEqual(a["radar"]["seguretat"], 0.977)
        # L'error de cada radar i de cada model del cel, per dibuixar-lo (Juanjo, 20-10-2026).
        self.assertEqual((a["radar"]["error"], a["radar"]["casos"], a["radar"]["amb_pluja"]),
                         ({"meteocat": 0.031, "rainviewer": 0.022}, 900, 40))
        self.assertEqual((a["cel"]["error"], a["cel"]["error_actual"]), ({"arome": 22.0, "gfs": 25.1}, 20.5))
        self.assertEqual([(c["dia"], c["que"]) for c in a["canvis"]],
                         [("2026-10-19", "pluja"), ("2026-10-19", "fi_pluja"), ("2026-10-18", "humitat"),
                          ("2026-10-07", "radar")])
        self.assertEqual(a["minims"], {"hores_pluja": 30, "dies_temperatura": 14, "dies_humitat": 14})
        self.assertEqual(a["humitat"]["dies"][-1], {"dia": "2026-10-18", "humitat": "barri", "dies": 14.0,
                                                    "error": 3.8, "error_vigent": 4.4})
        # El año de casa, del repositorio.
        self.assertTrue(a["humitat"]["arxiu"]["adoptat"])
