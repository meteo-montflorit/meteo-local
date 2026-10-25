# SPDX-License-Identifier: AGPL-3.0-or-later
"""El historial de avisos de peligro para la página «Perill» (avisos_bot.py, ADR 0071)."""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import avisos_bot as AB  # noqa: E402
import hora as HR  # noqa: E402


def hm(t):
    """L'hora de Madrid d'un moment desat (en UTC des de l'ADR 0128)."""
    return HR.local(t).strftime("%H:%M")

ARA = dt.datetime(2026, 10, 11, 12, 0).astimezone()


def avis(minuts, episodi, nivell, text="t", **extra):
    hora = (ARA + dt.timedelta(minutes=minuts)).isoformat(timespec="minutes")
    return {"id": f"perill:{episodi}:{minuts}", "tipus": "perill", "nivell": nivell, "hora": hora,
            "ca": text, "es": text, "episodi": episodi, **extra}


class Historial(unittest.TestCase):
    def test_comencament_i_final_en_una_sola_entrada(self):
        estat = {}
        AB.historial(estat, [avis(0, "incendi:x", "incendi", "🔥 foc")], ARA)
        h = AB.historial(estat, [avis(60, "incendi:x", "fi", "🟢 acabat")], ARA)
        self.assertEqual(len(h), 1)
        self.assertEqual((hm(h[0]["inici"]), hm(h[0]["fi"])), ("12:00", "13:00"))
        self.assertEqual((h[0]["ca"], h[0]["fi_ca"]), ("🔥 foc", "🟢 acabat"))

    def test_si_puja_de_nivell_es_queda_el_pitjor_i_el_text_nou(self):
        estat = {}
        AB.historial(estat, [avis(0, "riera:a", "atencio", "atenció")], ARA)
        AB.historial(estat, [avis(30, "riera:a", "perill", "perill")], ARA)
        h = AB.historial(estat, [avis(60, "riera:a", "groc", "després")], ARA)
        self.assertEqual(len(h), 1)
        self.assertEqual((h[0]["nivell"], h[0]["ca"]), ("perill", "després"))

    def test_sense_risc_la_fitxa_espera_en_pausa(self):
        # Revisor, 19-10-2026: «Perill» donava per activa una fitxa que la portada ja no llistava.
        estat = {}
        AB.historial(estat, [avis(0, "propi", "groc", "🟡 títol\nVent fort.")], ARA)
        estat.update(perill_text=None, perill_buit=True)
        h = AB.historial(estat, [], ARA + dt.timedelta(minutes=30))
        self.assertEqual(hm(h[0]["en_pausa"]), "12:30")
        # Sense dades no es decideix res; si el risc torna, deixa d'estar en pausa.
        estat.update(perill_buit=False)
        self.assertIn("en_pausa", AB.historial(estat, [], ARA + dt.timedelta(minutes=45))[0])
        estat.update(perill_text={"ca": "🟡 títol\nVent fort.", "es": "x"})
        self.assertNotIn("en_pausa", AB.historial(estat, [], ARA + dt.timedelta(minutes=60))[0])

    def test_la_fitxa_de_meteocat_retirat_espera_en_pausa(self):
        # Revisor, 20-10-2026: Meteocat va retirar l'avís de 5 a 6 h i «Perill» el donava per actiu
        # durant la mitja hora de relleu, quan la portada ja no el llistava.
        ep = "meteocat:2026-10-16T07:55+02:00"
        estat = {"oficials": {"smp": {"episodi": ep, "fenomens": {}, "pausa": "2026-10-11T12:30+02:00"}}}
        AB.historial(estat, [avis(0, ep, "groc", "🟡 Meteocat\nPluja.")], ARA)
        h = AB.historial(estat, [], ARA + dt.timedelta(minutes=40))
        self.assertEqual(h[0]["en_pausa"], "2026-10-11T12:30+02:00")
        estat["oficials"]["smp"].pop("pausa")
        self.assertNotIn("en_pausa", AB.historial(estat, [], ARA + dt.timedelta(minutes=45))[0])

    def test_l_aemet_avanca_l_inici_si_meteocat_ja_no_el_cobreix(self):
        # Revisor, 20-10-2026: «Previst · Comença a les 6 h» a les 5:40, amb Meteocat ja retirat.
        k = "aemet:pluja:2026-10-20T00:00:00+02:00"
        e = {"clau": k, "inici": "2026-10-19T19:27+02:00", "comenca": "2026-10-20T06:00:00+02:00",
             "fins": "2026-10-20T08:59:59+02:00", "ca": "x", "es": "x"}
        ara = dt.datetime.fromisoformat("2026-10-20T05:40:00+02:00")
        AB.tanca_aemet([e], {k: {"fin": "2026-10-20T08:59:59+02:00", "cobert": False,
                                 "comenca": "2026-10-20T00:00:00+02:00"}}, ara)
        self.assertEqual(e["comenca"], "2026-10-20T00:00:00+02:00")
        self.assertNotIn("fi", e)

    def test_el_comunicat_nou_posa_l_hora_del_missatge(self):
        # Revisor, 19-10-2026: «actualitzat avui 12:08» (el PDF) amb el missatge enviat a les 12:15.
        estat = {}
        AB.historial(estat, [avis(0, "pla:INUNCAT", "pc", "pla")], ARA)
        h = AB.historial(estat, [avis(15, "pla:INUNCAT", "pc", "comunicat", nomes_avis=True)], ARA)
        self.assertEqual((h[0]["ca"], h[0]["darrer"][11:16]), ("pla", "12:15"))

    def test_la_fitxa_del_temps_extrem_amb_els_riscos_d_ara(self):
        # 19-10-2026: la fitxa oberta diu d'on surt cada risc ara (riscos.font), sense marcar-se nova.
        estat = {}
        AB.historial(estat, [avis(0, "propi", "groc", "🟡 títol\nVent fort previst.\nCalculat per aquesta aplicació, no oficial.")], ARA)
        estat["perill_text"] = {"ca": "🟡 títol\nVent fort previst.\nOrigen: Météo-France.\nAvís no oficial.", "es": "x"}
        h = AB.historial(estat, [], ARA + dt.timedelta(minutes=15))
        self.assertIn("Origen: Météo-France.", h[0]["ca"])
        self.assertNotIn("darrer", h[0])
        # Però sí quan es va escriure el text, per al dia d'«avui» quan es rellegeix (20-10-2026).
        self.assertEqual(HR.utc(h[0]["escrit"]), ARA + dt.timedelta(minutes=15))
        # Sense riscos ara (falta la previsió), es queda com estava.
        estat["perill_text"] = None
        self.assertIn("Origen: Météo-France.", AB.historial(estat, [], ARA + dt.timedelta(minutes=30))[0]["ca"])

    def test_un_episodi_nou_despres_d_un_d_acabat(self):
        estat = {}
        AB.historial(estat, [avis(0, "propi", "groc"), avis(10, "propi", "fi")], ARA)
        h = AB.historial(estat, [avis(600, "propi", "taronja")], ARA)
        self.assertEqual(len(h), 2)
        self.assertFalse(h[1].get("fi"))

    def test_sense_episodi_no_hi_va(self):
        estat = {}
        pluja = {"id": "pluja:x", "tipus": "pluja", "nivell": None, "hora": ARA.isoformat(), "ca": "p", "es": "p"}
        self.assertEqual(AB.historial(estat, [pluja], ARA), [])

    def test_un_pla_que_ja_no_es_mostra_acaba(self):
        estat = {"oficials": {"plans": {"INUNCAT": {"fase": "alerta", "nom": "d'inundacions"}}}}
        AB.historial(estat, [avis(0, "pla:INUNCAT", "pc")], ARA)
        self.assertFalse(estat["historial"][0].get("fi"))
        estat["oficials"]["plans"]["INUNCAT"]["ocult"] = True
        h = AB.historial(estat, [], ARA + dt.timedelta(hours=2))
        self.assertEqual(hm(h[0]["fi"]), "14:00")

    def test_el_pla_porta_el_comunicat_mes_recent(self):
        # L'INUNCAT del 15-10-2026: alerta a les 19:09 sense comunicat; el PDF surt
        # a les 19:43 i la fitxa l'ha de portar; si n'hi ha un de nou, el nou, i
        # quan acaba es queda amb l'últim.
        estat = {}
        pdf = "https://documents.dadesobertes.gencat.cat/cecat/docs/I-1.pdf"
        text = "🟠 <b>Pla</b>\nActivat." + '\n<a href="' + pdf + '">Comunicat (PDF)</a>'
        h = AB.comunicats(AB.historial(estat, [avis(0, "pla:INUNCAT", "pc", "🟠 <b>Pla</b>",
                                                    enllac=AB.PROTECCIO_CIVIL)], ARA), [])
        self.assertNotIn("comunicat", h[0])
        h = AB.comunicats(h, [{"pla": "INUNCAT", "fase": "alerta", "comunicat": pdf}])
        self.assertEqual(h[0]["comunicat"], pdf)
        h = AB.comunicats(h, [{"pla": "INUNCAT", "fase": "alerta", "comunicat": pdf.replace("1", "2")}])
        self.assertTrue(h[0]["comunicat"].endswith("I-2.pdf"))
        h[0]["fi"] = ARA.isoformat()
        h = AB.comunicats(h, [{"pla": "INUNCAT", "fase": "alerta", "comunicat": pdf.replace("1", "3")}])
        self.assertTrue(h[0]["comunicat"].endswith("I-2.pdf"))
        # Si el text ja portava el comunicat, el perd: només un enllaç.
        h = AB.comunicats(AB.historial({}, [avis(0, "pla:INUNFOC", "pc", text)], ARA),
                          [{"pla": "INUNFOC", "fase": "alerta", "comunicat": pdf}])
        self.assertEqual(h[0]["ca"], "🟠 <b>Pla</b>\nActivat.")

    def test_el_comunicat_nou_porta_a_la_fitxa_sense_canviar_la(self):
        estat = {}
        AB.historial(estat, [avis(0, "pla:INUNCAT", "pc", "alerta")], ARA)
        nou = avis(30, "pla:INUNCAT", "pc", "comunicat nou", nomes_avis=True)
        h = AB.historial(estat, [nou], ARA)
        # El text no canvia; «actualitzat» diu l'hora del missatge (revisor, 19-10-2026).
        self.assertEqual((len(h), h[0]["ca"], h[0].get("darrer")[11:16]), (1, "alerta", "12:30"))
        self.assertEqual(AB.pagina(nou, h), "perill.html#" + AB.id_fitxa("pla:INUNCAT", h[0]["inici"]))

    def test_no_es_perd_res_i_el_vell_va_a_l_arxiu_del_seu_any(self):
        # ADR 0124: fins a la 3.193 es guardava un any i es borrava. Ara, el que
        # va acabar fa més d'ARXIU_DIES dies passa a avisos-AAAA.json (el de
        # l'any en què va començar), unit amb el publicat, i el que segueix no.
        import tempfile
        estat = {}
        AB.historial(estat, [avis(0, "aemet:pluja:x", "groc", fins=ARA.isoformat()),
                             avis(0, "incendi:y", "incendi")], ARA)
        h = AB.historial(estat, [], ARA + dt.timedelta(days=400))
        self.assertEqual(len(h), 2)                        # ja no es borra
        recents, vells = AB.parteix(h, ARA + dt.timedelta(days=AB.ARXIU_DIES + 1))
        self.assertEqual(([e["clau"] for e in recents], [e["clau"] for e in vells]), (["incendi:y"], ["aemet:pluja:x"]))
        self.assertEqual(AB.parteix(h, ARA + dt.timedelta(days=AB.ARXIU_DIES - 1))[1], [])
        with tempfile.TemporaryDirectory() as estat_dir, tempfile.TemporaryDirectory() as sortida:
            publicat = os.path.join(sortida, "avisos.json")
            altre = {"clau": "incendi:z", "tipus": "perill", "inici": "2026-01-02T10:00+01:00", "fi": "2026-01-02T11:00+01:00"}
            with open(os.path.join(sortida, "avisos-2026.json"), "w", encoding="utf-8") as f:
                json.dump({"any": 2026, "historial": [altre]}, f)
            self.assertEqual(AB.arxiva(vells, estat_dir, sortida, publicat), ["avisos-2026.json"])
            for carpeta in (estat_dir, sortida):
                with open(os.path.join(carpeta, "avisos-2026.json"), encoding="utf-8") as f:
                    self.assertEqual([e["clau"] for e in json.load(f)["historial"]], ["incendi:z", "aemet:pluja:x"])
            # Una altra vegada el mateix: no es repeteix.
            AB.arxiva(vells, estat_dir, sortida, publicat)
            with open(os.path.join(estat_dir, "avisos-2026.json"), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)["historial"]), 2)

    def test_s_uneix_amb_el_publicat_per_l_altre_servidor(self):
        # El NAS torna després que la reserva hagi vist un incendi i el seu final.
        reserva = AB.historial({}, [avis(0, "incendi:r", "incendi"), avis(30, "incendi:r", "fi")], ARA)
        estat = {}
        AB.historial(estat, [avis(-600, "propi", "groc")], ARA)
        h = AB.historial(estat, [], ARA + dt.timedelta(hours=1), reserva)
        self.assertEqual([e["clau"] for e in h], ["propi", "incendi:r"])
        self.assertEqual(hm(h[1]["fi"]), "12:30")
        # Si l'altre ja l'ha tancat, val el final.
        obert = AB.historial({}, [avis(0, "riera:a", "atencio")], ARA)
        tancat = AB.historial({}, [avis(0, "riera:a", "atencio"), avis(60, "riera:a", "fi")], ARA)
        self.assertEqual(hm(AB.fusiona(obert, tancat)[0]["fi"]), "13:00")

    def test_un_avis_nou_continua_l_episodi_obert_de_l_altre(self):
        reserva = AB.historial({}, [avis(0, "incendi:x", "incendi", "primer")], ARA)
        h = AB.historial({}, [avis(15, "incendi:x", "incendi", "repetit")], ARA, reserva)
        self.assertEqual(len(h), 1)
        h = AB.historial({"historial": h}, [avis(60, "incendi:x", "fi")], ARA)
        self.assertTrue(all(e.get("fi") for e in h))

    def test_cada_avis_porta_l_enllac_a_la_seva_pagina(self):
        # ADR 0072: perill i riera, a la seva fitxa de «Perill»; llum, a «Llum»; pluja, a «El temps».
        estat = {}
        foc = avis(0, "incendi:x", "incendi", "🔥 foc")
        hist = AB.historial(estat, [foc], ARA)
        AB.amb_enllac(foc, hist)
        self.assertEqual(foc["pagina"], "perill.html#" + AB.id_fitxa("incendi:x", hist[0]["inici"]))
        self.assertTrue(foc["ca"].endswith('perill.html#a-incendi-x-2026-10-11t12-00-02-00">'
                                           'Més informació a Temps a Montflorit</a>'))
        self.assertIn('https://meteo-montflorit.github.io/es/perill.html#a-incendi-x-', foc["es"])
        self.assertEqual(hist[0]["ca"], "🔥 foc")                 # l'historial, sense l'enllaç
        # El final va a la mateixa fitxa.
        fi = avis(30, "incendi:x", "fi", "🟢 acabat")
        AB.amb_enllac(fi, AB.historial(estat, [fi], ARA))
        self.assertEqual(fi["pagina"], foc["pagina"])
        llum = {"tipus": "llum", "ca": "t", "es": "t"}
        self.assertEqual(AB.amb_enllac(llum, [])["pagina"], "consultes.html#llum")
        pluja = {"tipus": "pluja", "ca": "t", "es": "t"}
        self.assertIn('href="https://meteo-montflorit.github.io/es/"', AB.amb_enllac(pluja, [])["es"])

    def test_el_mateix_id_que_la_pagina(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("cal Node")
        casos = [("meteocat:Intensitat de pluja:2026-10-11", "2026-10-11T09:00+02:00"),
                 ("riera:2026-10-11T08:00", "2026-10-11T08:15+02:00"), ("pla:INUNCAT", "2026-10-11T09:00+02:00")]
        # idFitxa, a comu.js des de la 3.66.0: la fa servir també la portada (ADR 0076).
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "comu.js"),
                  encoding="utf-8") as f:
            js = f.read()
        funcio = "function idFitxa" + js.split("function idFitxa", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
        codi = funcio + "console.log(JSON.stringify(" + json.dumps([{"clau": c, "inici": i} for c, i in casos]) \
            + ".map(idFitxa)));"
        r = json.loads(subprocess.run(["node", "-e", codi], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(r, [AB.id_fitxa(c, i) for c, i in casos])
        # Amb l'hora interna, en UTC (ADR 0128), l'enllaç és el mateix que fa la
        # web amb l'hora publicada: el de l'avís porta a la seva fitxa.
        self.assertEqual(AB.id_fitxa("pla:INUNCAT", "2026-10-11T07:00Z"), r[2])


    def test_la_prealerta_queda_a_l_historial_quan_acaba(self):
        # ADR 0124 (24-10-2026): una prealerta de matinada que va desaparèixer
        # sense deixar rastre. Mentre dura no hi ha fitxa (la d'«Ara» surt de
        # plans_prealerta); en acabar, una de tancada amb el començament oficial.
        estat = {}
        pdf = "https://documents.dadesobertes.gencat.cat/cecat/docs/P-1.pdf"
        pre = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "prealerta", "des_de": "23/10/2026 22:10",
               "descripcio": "Pluges intenses", "comunicat": pdf}
        h = AB.prealertes(estat, {"plans": [pre]}, [], ARA)
        self.assertEqual(h, [])
        # Sense dades de Protecció Civil, res no canvia.
        self.assertEqual(AB.prealertes(estat, {"plans": None}, [], ARA), [])
        h = AB.prealertes(estat, {"plans": []}, [], ARA + dt.timedelta(hours=1))
        self.assertEqual(len(h), 1)
        e = h[0]
        self.assertEqual((e["clau"], HR.utc(e["inici"]), hm(e["fi"])),
                         ("prealerta:INUNCAT", HR.utc("2026-10-23T22:10+02:00"), "13:00"))
        self.assertEqual(e["nivell"], "prealerta")
        self.assertEqual(e["comunicat"], pdf)
        self.assertTrue(e["ca"].startswith("🟡 <b>Protecció Civil: pla d'inundacions (INUNCAT) en fase de prealerta</b>"))
        self.assertIn("Motiu, segons Protecció Civil: Pluges intenses.", e["ca"])
        self.assertIn("Motivo, según Protecció Civil: Pluges intenses.", e["es"])
        self.assertTrue(e["fi_ca"].endswith("Ja no consta en prealerta."))
        # Una altra passada sense el pla: no es repeteix.
        self.assertEqual(len(AB.prealertes(estat, {"plans": []}, h, ARA + dt.timedelta(hours=2))), 1)
        # Si passa a alerta, ho diu.
        estat = {}
        AB.prealertes(estat, {"plans": [pre]}, [], ARA)
        h = AB.prealertes(estat, {"plans": [dict(pre, fase="alerta")]}, [], ARA)
        self.assertTrue(h[0]["fi_ca"].endswith("Ha passat a fase d'alerta."))
        self.assertTrue(h[0]["fi_es"].endswith("Ha pasado a fase de alerta."))
        # Una que només ha estat oculta (sense motiu meteorològic, ADR 0062) no s'apunta.
        estat = {}
        AB.prealertes(estat, {"plans": [], "plans_ocults": [pre]}, [], ARA)
        self.assertEqual(AB.prealertes(estat, {"plans": []}, [], ARA), [])

    def test_els_plans_en_prealerta_van_a_avisos_json(self):
        # «Perill» els ensenya a «Ara»: no avisen i no tenen fitxa a l'historial (ADR 0091).
        import tempfile
        from unittest import mock
        prealerta = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "prealerta", "des_de": "15/10/2026 10:33",
                     "descripcio": "Avís-Intensitat de pluja", "comunicat": "https://example.org/c.pdf", "altre": 1}
        alerta = {"pla": "VENTCAT", "nom": "de vent", "fase": "alerta", "des_de": "15/10/2026 10:00"}
        with tempfile.TemporaryDirectory() as d:
            casa, sortida = os.path.join(d, "casa.json"), os.path.join(d, "avisos.json")
            with open(casa, "w", encoding="utf-8") as f:
                json.dump({"plans": [prealerta, alerta]}, f)
            with mock.patch.object(AB, "ESTAT", os.path.join(d, "estat.json")):
                AB.actualitza(casa, sortida, ahora=ARA)
            with open(sortida, encoding="utf-8") as f:
                plans = json.load(f)["plans_prealerta"]
        self.assertEqual(plans, [{k: v for k, v in prealerta.items() if k != "altre"}])

    def test_la_portada_porta_a_la_fitxa_del_pla(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("cal Node")
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "comu.js"),
                  encoding="utf-8") as f:
            js = f.read()
        funcions = "".join("function " + nom + js.split("function " + nom, 1)[1].split("\n}\n", 1)[0] + "\n}\n"
                           for nom in ("idFitxa", "idPla", "fitxaDelPla"))
        historial = [{"clau": "pla:VENTCAT", "inici": "2026-10-15T10:00+02:00"}]
        codi = ("let HISTORIAL_PERILL = " + json.dumps(historial) + ";\n" + funcions
                + "console.log(JSON.stringify([fitxaDelPla({pla: 'INUNCAT', fase: 'prealerta'}),"
                  " fitxaDelPla({pla: 'VENTCAT', fase: 'alerta'}), fitxaDelPla({pla: 'NEUCAT', fase: 'alerta'})]));")
        r = json.loads(subprocess.run(["node", "-e", codi], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(r, ["pla-inuncat", AB.id_fitxa("pla:VENTCAT", "2026-10-15T10:00+02:00"), "pla-neucat"])


if __name__ == "__main__":
    unittest.main()
