# SPDX-License-Identifier: AGPL-3.0-or-later
"""El revisor de coherencia (revisor.py, ADR 0101): les propostes amb botons,
les respostes de Juanjo, la pregunta a Claude i les pàgines dibuixades, sense
xarxa, sense IA i sense Chromium."""
import contextlib
import datetime as dt
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import revisor as RV  # noqa: E402

ARA = dt.datetime(2026, 10, 18, 7, 0).astimezone()
CA = "🟡 <b>Meteocat: perill moderat per pluja</b>\nLínia u.\nLínia dos.\nÉs un avís oficial."
ES = "🟡 <b>Meteocat: peligro moderado por lluvia</b>\nLínea uno.\nLínea dos.\nEs un aviso oficial."
FITXA = "meteocat:2026-10-18T05:00+02:00|2026-10-18T05:00+02:00"


def avisos():
    return {"avisos": [{"id": "pluja:1", "tipus": "pluja", "hora": "2026-10-18T05:10+02:00", "ca": CA, "es": ES}],
            "historial": [{"clau": "meteocat:2026-10-18T05:00+02:00", "inici": "2026-10-18T05:00+02:00",
                           "tipus": "perill", "nivell": "moderat", "ca": CA, "es": ES}]}


class Regles(unittest.TestCase):
    def test_una_fitxa_tancada_no_es_revisa(self):
        a = {"historial": [{"clau": "meteocat:x", "inici": "i", "fi": "2026-10-18T06:00+02:00",
                            "ca": "Títol\n🟠 Observat ara: dissabte 17 de 19 a 22 h"}]}
        self.assertEqual(RV.regles({}, a, ARA), [])

    def test_plou_a_la_xarxa_pero_no_a_l_hora_en_curs(self):
        casa = {"pluja_ara": {"estat": "plou"}, "hores": [{"plou_ara": False}]}
        self.assertEqual([p["regla"] for p in RV.regles(casa, {}, ARA)], ["pluja_hora"])
        # Si l'hora ho diu, o només és el radar, no hi ha contradicció.
        casa["hores"][0]["plou_ara"] = True
        self.assertEqual(RV.regles(casa, {}, ARA), [])
        self.assertEqual(RV.regles({"pluja_ara": {"estat": "radar_sobre"}, "hores": [{}]}, {}, ARA), [])
        # Sense hores no es pot comparar.
        self.assertEqual(RV.regles({"pluja_ara": {"estat": "plou"}, "hores": []}, {}, ARA), [])

    def test_l_observacio_vigent_de_meteocat_manté_l_observat_ara(self):
        a = {"historial": [{"clau": "meteocat:1", "inici": "i", "ca": "Títol\n🟠 Observat ara, perill alt"}]}
        vigent = {"smp": {"avisos": [{"tipus": "observacio", "dies": {"2026-10-18": [[6, 12]]}}]}}
        self.assertEqual(RV.regles(vigent, a, ARA), [])
        passada = {"smp": {"avisos": [{"tipus": "observacio", "dies": {"2026-10-18": [[0, 6]]}},
                                      {"tipus": "previsio", "dies": {"2026-10-18": [[6, 12]]}}]}}
        self.assertEqual([p["regla"] for p in RV.regles(passada, a, ARA)], ["observat_ara"])

    def test_el_boto_de_la_franja_porta_el_text_de_l_avis(self):
        dom = ('<body><div><button class="boto-franja x" aria-label="Avís groc de pluja"></button></div>'
               '<svg><button class="boto-franja" aria-label="amagat"></button></svg></body>')
        self.assertEqual(RV.text_visible(dom), "Avís groc de pluja")

    def test_netja(self):
        self.assertEqual(RV.netja("  <b>Hola</b> <i>món</i> "), "Hola món")
        self.assertEqual(RV.netja(None), "")


class Toca(unittest.TestCase):
    def test_una_regla_nova_desperta_i_una_de_vista_no(self):
        p = {"regla": "plou_i_no_plou", "on": "index.html", "que": "x"}
        estat = {"darrer_missatge": "2026-10-18T05:10+02:00", "conclusions": RV.empremta(RV.conclusions({}, {})),
                 "darrera": (ARA - dt.timedelta(hours=1)).isoformat()}
        self.assertEqual(RV.toca(estat, {}, {}, ARA, [p]), "regla")
        estat["regles_vistes"] = {RV.empremta(p): "2026-10-18T06:00+02:00"}
        self.assertIsNone(RV.toca(estat, {}, {}, ARA, [p]))
        # Dins de la mitja hora d'espera, una regla nova espera.
        estat = {**estat, "regles_vistes": {}, "darrera": (ARA - dt.timedelta(minutes=5)).isoformat()}
        self.assertIsNone(RV.toca(estat, {}, {}, ARA, [p]))

    def test_el_resum_del_dia_una_sola_vegada(self):
        estat = {"diaris": ["2026-10-18 05:50"], "conclusions": RV.empremta(RV.conclusions({}, {}))}
        self.assertIsNone(RV.toca(estat, {}, {}, ARA.replace(hour=6, minute=10), []))
        # Passada l'hora de marge, ja no.
        self.assertIsNone(RV.toca({"conclusions": estat["conclusions"]}, {}, {}, ARA.replace(hour=7, minute=0), []))

    def test_conclusions(self):
        casa = {"pluja_ara": {"estat": "plou"}, "modo": {"aviso": "vigilancia"},
                "smp": {"fenomens": [{"fenomen": "pluja", "nivell": 2}]},
                "avisos": [{"tipo": "lluvia", "nivel": "amarillo"}, {"tipo": "viento", "nivel": "amarillo",
                                                                      "cobert": True}],
                "plans": [{"pla": "INUNCAT", "fase": "alerta"}], "riscos": [{"clau": "riera", "nivell": "alt"}],
                "perill_riera": [{"nivell": "alt"}], "entorn": {"incendis": [{"id": 3}]}}
        c = RV.conclusions(casa, avisos())
        self.assertEqual(c["mode"], "vigilancia")
        self.assertEqual(c["aemet"], [("lluvia", "amarillo")])      # el cobert per Meteocat no compta
        self.assertEqual(c["fitxes"], [("meteocat:2026-10-18T05:00+02:00", "moderat")])
        self.assertEqual(RV.conclusions({"modo": "normal"}, {})["mode"], "normal")


class Missatges(unittest.TestCase):
    def test_codi_amb_el_per_que(self):
        t = RV.missatge({"on": "portada", "que": "plou i no plou", "per_que": "dos llindars"}, "codi")
        self.assertEqual(t.split("\n")[:5], ["portada", "", "plou i no plou", "", "dos llindars"])
        self.assertIn("hay que arreglarlo en el código", t)

    def test_proposta_sense_html(self):
        t = RV.missatge({"on": "o", "que": "q"}, "proposta", CA, "<b>Nou</b>")
        self.assertIn("Ahora dice:\n🟡 Meteocat: perill moderat per pluja", t)
        self.assertTrue(t.endswith("Propuesta:\nNou"))

    def test_botons(self):
        self.assertEqual([b["callback_data"] for b in RV.botons("7", "proposta")["inline_keyboard"][0]],
                         ["rev:7:aplica", "rev:7:deixa"])
        self.assertEqual(RV.botons("7", "corregit")["inline_keyboard"][0][0]["callback_data"], "rev:7:desfes")
        self.assertIsNone(RV.botons("7", "codi"))

    def test_objectiu_sense_fitxa_ni_avis(self):
        self.assertIsNone(RV.objectiu(avisos(), {"tipus": "treu_linies", "linies": [1]}))
        self.assertIsNone(RV.valida(avisos(), {"tipus": "treu_linies", "fitxa": FITXA, "linies": []}))

    def test_telegram_i_el_xat_de_juanjo(self):
        import boira
        with mock.patch.object(boira, "telegram", return_value=("ok", {})) as t:
            self.assertEqual(RV.telegram("getMe", a=1), ("ok", {}))
        t.assert_called_once_with("getMe", a=1)
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "c.json")
            with mock.patch.object(RV, "CONFIG_BOT", cfg):
                self.assertIsNone(RV.chat_juanjo())
                with open(cfg, "w") as f:
                    json.dump({"chat_id": 42}, f)
                self.assertEqual(RV.chat_juanjo(), 42)


class Fitxers(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        for k, v in (("CORRECCIONS", "correccions.json"), ("PUBLICA_ARA", "publica-ara"),
                     ("REGISTRE", "registre/revisor.jsonl")):
            p = mock.patch.object(RV, k, os.path.join(self.dir.name, v))
            p.start()
            self.addCleanup(p.stop)

    def test_desfes_treu_la_correccio_de_qualsevol_grup(self):
        RV.desa(RV.CORRECCIONS, {"fitxes": {FITXA: {"ca": "x"}}, "avisos": {"pluja:1": {"ca": "y"}}})
        RV.desfes(FITXA)
        RV.desfes("pluja:1")
        RV.desfes("no-hi-és")
        self.assertEqual(RV.llegeix(RV.CORRECCIONS, None), {"fitxes": {}, "avisos": {}})

    def test_sense_correccions_no_es_toca_res(self):
        a = avisos()
        self.assertIs(RV.aplica_correccions(a), a)
        self.assertNotIn("correccions", a)
        self.assertFalse(os.path.exists(RV.CORRECCIONS))

    def test_tancar_una_fitxa(self):
        cs = {"fitxes": {FITXA: {"original": RV.empremta(CA), "ca": CA, "es": ES, "tanca": True,
                                 "hora": "2026-10-18T07:00+02:00"}}, "avisos": {}}
        e = RV.aplica_correccions(avisos(), correccions=cs)["historial"][0]
        self.assertEqual(e["fi"], "2026-10-18T07:00+02:00")
        self.assertEqual((e["fi_ca"], e["fi_es"]), ("Ja no és vigent.", "Ya no está vigente."))
        self.assertEqual(e["ca"], CA)
        # Amb les correccions donades, no es desa res.
        self.assertFalse(os.path.exists(RV.CORRECCIONS))

    def test_mostra_estat(self):
        sortida = io.StringIO()
        with contextlib.redirect_stdout(sortida):
            RV.mostra_estat()
        self.assertEqual(sortida.getvalue(), "")
        os.makedirs(os.path.dirname(RV.REGISTRE))
        with open(RV.REGISTRE, "w") as f:
            for i in range(25):
                f.write(json.dumps({"hora": f"h{i}", "motiu": "canvi", "problemes": [1] * (i % 3),
                                    "segons": 40, "cost_usd": 0.2}) + "\n")
            f.write("\n")
        with contextlib.redirect_stdout(sortida):
            RV.mostra_estat()
        linies = sortida.getvalue().splitlines()
        self.assertEqual(len(linies), 20)                 # les 20 últimes
        self.assertTrue(linies[0].startswith("h5  canvi"))
        self.assertIn("2 problema(es)  40 s  0.2 $", linies[-2])        # h23


class Demana(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        instr = os.path.join(self.dir.name, "instr.md")
        with open(instr, "w") as f:
            f.write("INSTRUCCIONS")
        p = mock.patch.object(RV, "INSTRUCCIONS", instr)
        p.start()
        self.addCleanup(p.stop)

    def crida(self, result):
        sortida = {"result": result, "total_cost_usd": 0.12, "usage": {"input_tokens": 900}}
        r = subprocess.CompletedProcess([], 0, stdout=json.dumps(sortida), stderr="")
        with mock.patch.object(RV.subprocess, "run", return_value=r) as run:
            return RV.demana("CONTEXT"), run

    def test_una_sola_resposta_sense_eines(self):
        (res, cost), run = self.crida('Aquí va:\n{"problemes": [{"on": "portada"}]}\nFi.')
        self.assertEqual(res, {"problemes": [{"on": "portada"}]})
        self.assertEqual((cost["cost_usd"], cost["tokens"]), (0.12, 900))
        ordre = run.call_args[0][0]
        self.assertEqual(ordre[ordre.index("--model") + 1], RV.C.REVISOR_MODEL)
        self.assertEqual(ordre[ordre.index("--max-turns") + 1], "1")
        self.assertEqual(ordre[ordre.index("--allowedTools") + 1], "")
        self.assertEqual(run.call_args[1]["input"], "INSTRUCCIONS\n\n---\n\nCONTEXT")

    def test_sense_json_no_hi_ha_problemes(self):
        (res, _), _ = self.crida("Tot quadra.")
        self.assertEqual(res, {"problemes": []})
        (res, _), _ = self.crida(None)
        self.assertEqual(res, {"problemes": []})


class Pagines(unittest.TestCase):
    def test_sense_chromium_no_hi_ha_pagines(self):
        with mock.patch.object(RV, "chromium", return_value=None):
            self.assertEqual(RV.pagines("casa.json", "avisos.json"), {})

    def test_chromium(self):
        with mock.patch.dict(os.environ, {"CHROMIUM": "el-meu-chrome"}), \
                mock.patch.object(RV.shutil, "which", lambda o: f"/bin/{o}" if o == "el-meu-chrome" else None):
            self.assertEqual(RV.chromium(), "/bin/el-meu-chrome")
        with mock.patch.dict(os.environ, {"CHROMIUM": ""}), \
                mock.patch.object(RV.shutil, "which", lambda o: f"/usr/bin/{o}" if o == "chromium-browser" else None):
            self.assertEqual(RV.chromium(), "/usr/bin/chromium-browser")
        with mock.patch.object(RV.shutil, "which", return_value=None):
            self.assertIsNone(RV.chromium())

    def test_silenci_no_escriu_res(self):
        sortida = io.StringIO()
        with contextlib.redirect_stderr(sortida):
            self.assertIsNone(RV.Silenci.log_message(object(), "%s", "GET /"))
        self.assertEqual(sortida.getvalue(), "")

    def test_la_web_es_dibuixa_amb_les_dades_del_costat(self):
        import montflorit
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        avisos_json = os.path.join(d.name, "avisos.json")
        with open(avisos_json, "w") as f:
            json.dump(avisos(), f)
        comu = {}

        def construeix(web):
            os.makedirs(web)
            with open(os.path.join(web, "comu.js"), "w") as f:
                f.write("const DADES_URL = 'https://bilateria.org/app/meteo-local/';\nX();\n")
            comu["ruta"] = os.path.join(web, "comu.js")

        crides = []

        def run(ordre, **kw):
            crides.append(ordre)
            if ordre[0] == sys.executable:
                return subprocess.CompletedProcess(ordre, 0, "", "")
            if ordre[-1].endswith("/sortir.html"):
                raise subprocess.TimeoutExpired(ordre, 120)
            # El DOM ja ha llegit les dades del costat, no les d'IONOS.
            with open(comu["ruta"]) as f:
                comu["final"] = f.read()
            return subprocess.CompletedProcess(ordre, 0, "<html><body><p>No plou</p></body></html>", "")

        srv = mock.Mock(server_address=("127.0.0.1", 4321))
        with mock.patch.object(montflorit, "construeix", construeix), \
                mock.patch.object(RV.subprocess, "run", run), \
                mock.patch.object(RV.http.server, "ThreadingHTTPServer", return_value=srv):
            res = RV.pagines("casa.json", avisos_json, navegador="chrome")
        self.assertEqual(res, {"index.html": "No plou", "sortir.html": "", "perill.html": "No plou"})
        self.assertIn("const DADES_URL = './';", comu["final"])
        self.assertEqual(crides[0][2:4], ["dades", "casa.json"])
        self.assertEqual([c[-1] for c in crides[1:]],
                         [f"http://127.0.0.1:4321/{p}" for p in RV.PAGINES])
        self.assertTrue(all("--headless" in c for c in crides[1:]))
        srv.shutdown.assert_called_once()


class Revisio(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        d = self.dir.name
        for k, v in (("ESTAT", "revisor.json"), ("CORRECCIONS", "correccions.json"),
                     ("REGISTRE", "registre/revisor.jsonl"), ("PUBLICA_ARA", "publica-ara")):
            p = mock.patch.object(RV, k, os.path.join(d, v))
            p.start()
            self.addCleanup(p.stop)
        self.enviats = []
        self.updates = []
        self.falla = set()
        for p in (mock.patch.object(RV, "telegram", side_effect=self.telegram),
                  mock.patch.object(RV, "chat_juanjo", return_value="1"),
                  mock.patch.object(RV, "ara", return_value=ARA),
                  mock.patch.object(sys, "path", sys.path[:])):
            p.start()
            self.addCleanup(p.stop)
        self.casa = os.path.join(d, "casa.json")
        self.avisos = os.path.join(d, "avisos.json")
        with open(self.casa, "w") as f:
            json.dump({"hores": []}, f)
        with open(self.avisos, "w") as f:
            json.dump(avisos(), f)

    def telegram(self, metode, **p):
        self.enviats.append((metode, p))
        if metode in self.falla:
            raise OSError("sense xarxa")
        if metode == "getUpdates":
            return self.updates, {"chat_id": 1}
        return {"message_id": 100 + len(self.enviats)}, {"chat_id": "1"}

    def revisa(self, moment, problemes, **kw):
        demana = mock.Mock(return_value=({"problemes": problemes}, {"cost_usd": 0.3, "segons": 40}))
        r = RV.revisa(self.casa, self.avisos, moment, demana_=demana, pagines_=lambda c, a: {}, **kw)
        return r, demana

    def boto(self, dada, de=1):
        return {"callback_query": {"id": f"q{len(self.updates)}", "data": dada, "from": {"id": de}}}

    def test_proposta_de_tancar_una_fitxa_i_juanjo_l_aplica(self):
        p = {"gravetat": "alta", "on": "Perill", "que": "la fitxa ja no és vigent",
             "correccio": {"tipus": "tanca_fitxa", "fitxa": FITXA, "fi_es": "Ya no hay peligro."}}
        r, _ = self.revisa(ARA, [p])
        self.assertEqual(r["motiu"], "avís enviat")
        metode, msg = self.enviats[-1]
        self.assertEqual(metode, "sendMessage")
        self.assertIn("Propuesta:\nSe cierra la ficha: Ya no hay peligro.", msg["text"])
        self.assertEqual([b["text"] for b in msg["reply_markup"]["inline_keyboard"][0]], ["Aplicar", "Dejar"])
        # No s'ha corregit res sol.
        self.assertFalse(os.path.exists(RV.CORRECCIONS))
        estat = RV.llegeix(RV.ESTAT, {})
        self.assertEqual(estat["preguntes"]["1"]["accio"], "proposta")
        self.assertEqual(estat["preguntes"]["1"]["correccio"]["original_empremta"], RV.empremta(CA))
        # Un altre usuari, una altra pregunta o un altre bot no compten.
        self.updates = [self.boto("rev:1:aplica", de=99), self.boto("boira:si"), self.boto("rev:9:aplica"),
                        {"message": {}}, self.boto("rev:1:aplica")]
        self.assertEqual(RV.respostes(ARA), 1)
        self.assertTrue(os.path.exists(RV.PUBLICA_ARA))
        cs = RV.llegeix(RV.CORRECCIONS, {})
        self.assertTrue(cs["fitxes"][FITXA]["tanca"])
        self.assertEqual(cs["fitxes"][FITXA]["motiu"], "aprovat per Juanjo")
        editats = [p for m, p in self.enviats if m == "editMessageReplyMarkup"]
        self.assertEqual(editats[0]["reply_markup"]["inline_keyboard"][0][0]["text"], "Aplicado")
        self.assertEqual(editats[0]["message_id"], estat["preguntes"]["1"]["missatge"])
        # La web la tanca a la passada següent.
        e = RV.aplica_correccions(avisos())["historial"][0]
        self.assertEqual(e["fi_es"], "Ya no hay peligro.")
        self.assertEqual(e["fi"], "2026-10-18T07:00+02:00")
        # Ja contestada: no torna a comptar ni a preguntar a Telegram.
        n = len(self.enviats)
        self.assertEqual(RV.respostes(ARA), 0)
        self.assertEqual(len(self.enviats), n)

    def test_proposta_de_text_nou_i_juanjo_la_deixa(self):
        p = {"gravetat": "mitjana", "on": "avís enviat", "que": "diu dues coses",
             "correccio": {"tipus": "substitueix_text", "avis": "pluja:1", "ca": "Text nou."}}
        self.revisa(ARA, [p])
        self.assertIn("Propuesta:\nText nou.", self.enviats[-1][1]["text"])
        self.updates = [self.boto("rev:1:deixa")]
        self.assertEqual(RV.respostes(ARA), 1)
        self.assertFalse(os.path.exists(RV.CORRECCIONS))
        self.assertEqual(RV.llegeix(RV.ESTAT, {})["preguntes"]["1"]["resposta"], "deixa")

    def test_aplicar_un_text_nou_d_un_avis(self):
        p = {"gravetat": "mitjana", "on": "avís", "que": "q",
             "correccio": {"tipus": "substitueix_text", "avis": "pluja:1", "ca": "Text nou."}}
        self.revisa(ARA, [p])
        self.updates = [self.boto("rev:1:aplica")]
        RV.respostes(ARA)
        c = RV.llegeix(RV.CORRECCIONS, {})["avisos"]["pluja:1"]
        # Sense text en castellà, es posa el català (no es deixa el vell).
        self.assertEqual((c["ca"], c["es"], c["tanca"]), ("Text nou.", "Text nou.", False))
        sortida = RV.aplica_correccions(avisos())
        self.assertEqual(sortida["correccions"][0]["ca"], "Text nou.")

    def test_desfer_una_correccio_automatica(self):
        p = {"gravetat": "alta", "on": "fitxa", "que": "línia caducada",
             "correccio": {"tipus": "treu_linies", "fitxa": FITXA, "linies": [2]}}
        self.revisa(ARA, [p])
        self.assertIn(FITXA, RV.llegeix(RV.CORRECCIONS, {})["fitxes"])
        self.updates = [self.boto("rev:1:desfes")]
        # Que Telegram falli en editar el botó no impedeix desfer.
        self.falla = {"editMessageReplyMarkup"}
        self.assertEqual(RV.respostes(ARA), 1)
        self.assertEqual(RV.llegeix(RV.CORRECCIONS, {})["fitxes"], {})
        self.assertEqual(RV.llegeix(RV.ESTAT, {})["preguntes"]["1"]["resposta"], "desfes")

    def test_sense_preguntes_pendents_no_es_consulta_telegram(self):
        self.assertEqual(RV.respostes(ARA), 0)
        self.assertEqual(self.enviats, [])

    def test_si_telegram_falla_queda_al_registre(self):
        self.falla = {"sendMessage"}
        ps = [{"gravetat": "alta", "on": "fitxa", "que": "x",
               "correccio": {"tipus": "treu_linies", "fitxa": FITXA, "linies": [2]}},
              {"gravetat": "alta", "on": "portada", "que": "plou i no plou"}]
        r, _ = self.revisa(ARA, ps)
        self.assertEqual(len(r["problemes"]), 2)
        with open(RV.REGISTRE) as f:
            registre = [json.loads(linia) for linia in f]
        self.assertEqual(registre[-1]["fets"], ["corregit", None, "codi", None])
        # La correcció s'ha aplicat igualment i l'estat s'ha desat.
        self.assertIn(FITXA, RV.llegeix(RV.CORRECCIONS, {})["fitxes"])
        self.assertEqual(RV.llegeix(RV.ESTAT, {})["darrera"], "2026-10-18T07:00+02:00")

    def test_una_correccio_no_valida_va_com_a_codi(self):
        p = {"gravetat": "baixa", "on": "fitxa", "que": "x",
             "correccio": {"tipus": "treu_linies", "fitxa": FITXA, "linies": [0]}}
        r, _ = self.revisa(ARA, [p])
        self.assertEqual(self.enviats, [])                    # lleu: només al registre
        self.assertFalse(os.path.exists(RV.CORRECCIONS))
        with open(RV.REGISTRE) as f:
            self.assertEqual(json.loads(f.readline())["fets"], ["codi"])

    def test_la_regla_fixa_que_la_ia_no_recull_hi_va_igualment(self):
        with open(self.casa, "w") as f:
            json.dump({"pluja_ara": {"estat": "plou"}, "hores": [{"plou_ara": False}]}, f)
        r, demana = self.revisa(ARA, [])
        self.assertEqual([(p["regla"], p["gravetat"]) for p in r["problemes"]], [("pluja_hora", "mitjana")])
        self.assertIn("pluja_hora", demana.call_args[0][0])
        # La IA ja l'ha dit amb les seves paraules: no es repeteix.
        regla = RV.regles({"pluja_ara": {"estat": "plou"}, "hores": [{"plou_ara": False}]}, {}, ARA)[0]
        r, _ = self.revisa(ARA + dt.timedelta(hours=1), [{"on": "hores", "que": "Diu: " + regla["que"],
                                                          "gravetat": "alta"}], prova=True)
        self.assertEqual(len(r["problemes"]), 1)

    def test_el_resum_del_dia_va_al_context(self):
        bot = types.ModuleType("bot")
        bot.resum = mock.Mock(return_value="RESUM DEL BOT")
        with open(self.avisos, "w") as f:
            json.dump({"avisos": [], "historial": []}, f)
        moment = ARA.replace(hour=5, minute=55)
        with mock.patch.dict(sys.modules, {"bot": bot}), \
                mock.patch.object(RV, "llegeix_publiques", return_value={"dades": 1}):
            r, demana = self.revisa(moment, [])
        self.assertEqual(r["motiu"], "resum 05:50")
        self.assertIn("## Resum del dia que envia el bot\nRESUM DEL BOT", demana.call_args[0][0])
        self.assertEqual(bot.resum.call_args[0][:2], ({"dades": 1}, "ca"))
        self.assertTrue(bot.resum.call_args[1]["avui"])
        self.assertEqual(RV.llegeix(RV.ESTAT, {})["diaris"], ["2026-10-18 05:50"])
        # Si el resum falla, el revisor continua i ho diu.
        bot.resum.side_effect = RuntimeError("sense dades")
        with mock.patch.dict(sys.modules, {"bot": bot}), \
                mock.patch.object(RV, "llegeix_publiques", return_value={}):
            r, demana = self.revisa(moment, [], prova=True)
        self.assertIn("(no s'ha pogut generar el resum: sense dades)", demana.call_args[0][0])
        self.assertEqual(r["motiu"], "prova")

    def test_la_prova_no_envia_ni_desa_res(self):
        r, _ = self.revisa(ARA, [{"gravetat": "alta", "on": "x", "que": "y"}], prova=True)
        self.assertEqual(r["motiu"], "prova")
        self.assertEqual(self.enviats, [])
        self.assertFalse(os.path.exists(RV.ESTAT))
        self.assertFalse(os.path.exists(RV.REGISTRE))

    def test_llegeix_publiques(self):
        def run(ordre, **kw):
            with open(ordre[4], "w") as f:
                json.dump({"generat": ordre[3]}, f)
        with mock.patch.object(RV.subprocess, "run", run):
            self.assertEqual(RV.llegeix_publiques("casa.json", "avisos.json"), {"generat": "casa.json"})


class Ordres(unittest.TestCase):
    """La línia d'ordres, tal com la fa servir el NAS."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        d = self.dir.name
        p = mock.patch.dict(os.environ, {"REGISTRE_DIR": os.path.join(d, "registre")})
        p.start()
        self.addCleanup(p.stop)
        self.casa = os.path.join(d, "casa.json")
        self.avisos = os.path.join(d, "avisos.json")
        for ruta in (self.casa, self.avisos):
            with open(ruta, "w") as f:
                json.dump({}, f)

    def executa(self, *args, claude=None, flock=None):
        sortida = io.StringIO()
        resposta = json.dumps({"result": claude or '{"problemes": []}', "total_cost_usd": 0.1})
        run = mock.Mock(return_value=subprocess.CompletedProcess([], 0, stdout=resposta, stderr=""))
        with mock.patch.object(sys, "argv", ["revisor.py", *args]), mock.patch("subprocess.run", run), \
                mock.patch("shutil.which", return_value=None), mock.patch("fcntl.flock", flock or mock.Mock()), \
                mock.patch.object(sys, "path", sys.path[:]), contextlib.redirect_stdout(sortida):
            runpy.run_path(os.path.join(ARREL, "revisor.py"), run_name="__main__")
        return sortida.getvalue(), run

    def test_revisa(self):
        # A l'hora dels resums el motiu seria un altre: el bot, fals.
        bot = types.ModuleType("bot")
        bot.resum = mock.Mock(return_value="R")
        with mock.patch.dict(sys.modules, {"bot": bot}):
            text, run = self.executa("revisa", self.casa, self.avisos)
        self.assertRegex(text, r"^(canvi|resum \d\d:\d\d): 0 problema\(es\)\n$")
        self.assertEqual(run.call_args[0][0][0], "claude")
        self.assertTrue(os.path.exists(os.path.join(self.dir.name, "revisor.json")))

    def test_prova(self):
        bot = types.ModuleType("bot")
        bot.resum = mock.Mock(return_value="R")
        with mock.patch.dict(sys.modules, {"bot": bot}):
            text, _ = self.executa("prova", self.casa, self.avisos)
        self.assertEqual(json.loads(text)["motiu"], "prova")
        self.assertFalse(os.path.exists(os.path.join(self.dir.name, "revisor.json")))

    def test_si_l_anterior_no_ha_acabat_no_fa_res(self):
        with self.assertRaises(SystemExit) as e:
            self.executa("revisa", self.casa, self.avisos, flock=mock.Mock(side_effect=BlockingIOError))
        self.assertEqual(e.exception.code, 0)

    def test_respostes_estat_i_ajuda(self):
        self.assertEqual(self.executa("respostes")[0], "")
        self.assertEqual(self.executa("estat")[0], "")
        with self.assertRaises(SystemExit) as e:
            self.executa("res")
        self.assertIn("revisor de coherencia", e.exception.code)


if __name__ == "__main__":
    unittest.main()
