# SPDX-License-Identifier: AGPL-3.0-or-later
"""El revisor de coherencia (revisor.py, ADR 0101), sin red ni IA."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import revisor as RV  # noqa: E402

ARA = dt.datetime(2026, 10, 18, 7, 0).astimezone()
OBS = ("🟠 <b>Meteocat: s'observa perill alt per temps violent al Vallès Occidental</b>\n"
       "🟠 Observat ara, perill alt per «Temps violent»: dissabte 17 de 19 a 22 h (Pedra).\n"
       "🟡 Perill moderat per «Intensitat de pluja en 30 minuts»: dilluns 19 de 12 a 24 h.\n"
       "És un avís oficial: segueix les indicacions de Protecció Civil.")
OBS_ES = OBS.replace("Perill", "Peligro")


def avisos():
    return {"avisos": [{"id": "perill:1", "tipus": "perill", "hora": "2026-10-17T19:13+02:00", "ca": OBS, "es": OBS_ES}],
            "historial": [{"clau": "meteocat:2026-10-16T07:55+02:00", "inici": "2026-10-16T07:55+02:00",
                           "tipus": "perill", "nivell": "alt", "ca": OBS, "es": OBS_ES}]}


FITXA = "meteocat:2026-10-16T07:55+02:00|2026-10-16T07:55+02:00"


class Regles(unittest.TestCase):
    def test_franja_passada(self):
        self.assertEqual(RV.franja_passada("dissabte 17 de 19 a 22 h", ARA), ["dissabte 17 de 19 a 22 h"])
        self.assertEqual(RV.franja_passada("dilluns 19 de 12 a 24 h", ARA), [])
        self.assertEqual(RV.franja_passada("diumenge 18 de 0 a 7 h", ARA), ["diumenge 18 de 0 a 7 h"])

    def test_el_cas_del_18_d_octubre(self):
        # La fitxa amb el dissabte i «Observat ara» el diumenge (Juanjo: «no está
        # una parte ya pasada?»): les dues regles ho veuen.
        p = RV.regles({"smp": {"avisos": []}}, avisos(), ARA)
        self.assertEqual(sorted(x["regla"] for x in p), ["franja_passada", "observat_ara"])

    def test_plou_i_no_plou(self):
        p = RV.regles({}, {}, ARA, {"index.html": "No plou\nPluja a sobre"})
        self.assertEqual([x["regla"] for x in p], ["plou_i_no_plou"])
        self.assertEqual(RV.regles({}, {}, ARA, {"index.html": "No plou\nPluja a sobre segons el radar"}), [])

    def test_text_visible(self):
        dom = ("<html><head><title>x</title></head><body><script>var a=1</script><p>Plou</p>"
               "<div><svg><text>icona</text></svg>Pluja a sobre</div></body></html>")
        self.assertEqual(RV.text_visible(dom), "Plou\nPluja a sobre")


class Context(unittest.TestCase):
    def test_les_fitxes_de_l_aemet_acabades_per_l_hora_no_son_obertes(self):
        # Revisor, 21-10-2026 05:53: creia obertes quatre fitxes de l'AEMET amb el
        # «fins» passat; «Perill» les dona per acabades (perill.js, finalDe).
        moment = dt.datetime.fromisoformat("2026-10-21T05:53+02:00")
        avisos = {"historial": [
            {"clau": "aemet:pluja:2026-10-20T00:00", "inici": "2026-10-19T20:00+02:00", "ca": "a",
             "fins": "2026-10-20T08:59:59+02:00"},
            {"clau": "aemet:vent:2026-10-21T00:00", "inici": "2026-10-20T20:00+02:00", "ca": "b",
             "fins": "2026-10-21T12:00+02:00"},
            {"clau": "propi", "inici": "2026-10-20T20:00+02:00", "ca": "c"},
            {"clau": "smp:1", "inici": "2026-10-19T20:00+02:00", "ca": "d", "fi": "2026-10-20T10:00+02:00"}]}
        text = RV.context({}, avisos, {}, moment, "prova", [])
        self.assertNotIn("aemet:pluja:2026-10-20T00:00", text)
        self.assertIn("aemet:vent:2026-10-21T00:00", text)
        self.assertIn('"propi"', text)
        self.assertNotIn("smp:1", text)


class Correccions(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.p = [mock.patch.object(RV, "CORRECCIONS", os.path.join(self.dir.name, "correccions.json")),
                  mock.patch.object(RV, "PUBLICA_ARA", os.path.join(self.dir.name, "publica-ara"))]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.dir.cleanup()

    def test_nomes_es_treuen_linies(self):
        a = avisos()
        ca, es = RV.valida(a, {"tipus": "treu_linies", "fitxa": FITXA, "linies": [1]})
        self.assertNotIn("Observat ara", ca)
        self.assertIn("dilluns 19", ca)
        self.assertNotIn("Observat ara", es)
        # Ni el títol, ni tot el cos, ni un altre tipus, ni una fitxa que no hi és.
        for c in ({"tipus": "treu_linies", "fitxa": FITXA, "linies": [0]},
                  {"tipus": "treu_linies", "fitxa": FITXA, "linies": [1, 2, 3]},
                  {"tipus": "substitueix_text", "fitxa": FITXA, "linies": [1]},
                  {"tipus": "treu_linies", "fitxa": "cap|cap", "linies": [1]}):
            self.assertIsNone(RV.valida(a, c), c)

    def test_s_aplica_mentre_el_text_no_canvia(self):
        a = avisos()
        c = {"tipus": "treu_linies", "fitxa": FITXA, "linies": [1]}
        RV.aplica(c, *RV.valida(a, c), a, ARA, "prova")
        self.assertTrue(os.path.exists(RV.PUBLICA_ARA))
        sortida = RV.aplica_correccions(avisos())
        self.assertNotIn("Observat ara", sortida["historial"][0]["ca"])
        self.assertEqual(sortida["correccions"], [])
        # El text de la fitxa canvia sol: la correcció ja no hi és.
        nou = avisos()
        nou["historial"][0]["ca"] = "🟡 <b>Una altra cosa</b>\nRes."
        self.assertEqual(RV.aplica_correccions(nou)["historial"][0]["ca"], "🟡 <b>Una altra cosa</b>\nRes.")
        self.assertEqual(RV.llegeix(RV.CORRECCIONS, None)["fitxes"], {})

    def test_l_avis_enviat_va_al_bot(self):
        a = avisos()
        c = {"tipus": "treu_linies", "avis": "perill:1", "linies": [1]}
        RV.aplica(c, *RV.valida(a, c), a, ARA, "prova")
        sortida = RV.aplica_correccions(avisos())
        self.assertEqual([x["id"] for x in sortida["correccions"]], ["perill:1"])
        self.assertNotIn("Observat ara", sortida["avisos"][0]["ca"])


class Revisio(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = self.dir.name
        self.p = [mock.patch.object(RV, k, os.path.join(d, v)) for k, v in
                  (("ESTAT", "revisor.json"), ("CORRECCIONS", "correccions.json"), ("REGISTRE", "revisor.jsonl"),
                   ("PUBLICA_ARA", "publica-ara"))]
        self.enviats = []
        self.p.append(mock.patch.object(RV, "telegram", side_effect=self.telegram))
        self.p.append(mock.patch.object(RV, "chat_juanjo", return_value="1"))
        for x in self.p:
            x.start()
        self.casa = os.path.join(d, "casa.json")
        self.avisos = os.path.join(d, "avisos.json")
        with open(self.casa, "w") as f:
            json.dump({"smp": {"avisos": []}, "hores": []}, f)
        with open(self.avisos, "w") as f:
            json.dump(avisos(), f)

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.dir.cleanup()

    def telegram(self, metode, **p):
        self.enviats.append((metode, p))
        return {"message_id": len(self.enviats)}, {"chat_id": "1"}

    def revisa(self, moment, resposta):
        demana = mock.Mock(return_value=({"problemes": resposta}, {"cost_usd": 0.3, "segons": 40}))
        r = RV.revisa(self.casa, self.avisos, moment, demana_=demana, pagines_=lambda c, a, llista=None: {"index.html": "No plou"})
        return r, demana

    def test_corregeix_avisa_i_no_es_repeteix(self):
        problema = {"gravetat": "alta", "on": "fitxa Meteocat", "que": "diu «Observat ara» del dissabte",
                    "correccio": {"tipus": "treu_linies", "fitxa": FITXA, "linies": [1]}}
        r, demana = self.revisa(ARA, [problema])
        self.assertEqual(r["motiu"], "avís enviat")
        # Corregit sol, amb el botó de desfer.
        botons = [p["reply_markup"] for m, p in self.enviats if p.get("reply_markup")]
        self.assertEqual(botons[0]["inline_keyboard"][0][0]["text"], "Deshacer")
        # Amb el text d'abans i el de després, sense l'HTML de Telegram.
        text = next(p["text"] for m, p in self.enviats if p.get("reply_markup"))
        antes, ahora = text.split("\nAntes:\n")[1].split("\n\nAhora:\n")
        self.assertIn("Observat ara", antes)
        self.assertNotIn("Observat ara", ahora)
        self.assertIn("dilluns 19", ahora)
        # Con la cabecera de los mensajes de IA, y el texto escapado debajo.
        cap, cos = text.split("\n\n", 1)
        self.assertIn("🤖 <b>Claude</b>", cap)
        self.assertIn("revisor", cap)
        self.assertNotIn("<b>", cos)
        # La clau, amb el començament en UTC (ADR 0128): la mateixa que fa
        # aplica_correccions sobre l'historial intern.
        self.assertIn(RV.fitxa_normal(FITXA), RV.llegeix(RV.CORRECCIONS, {})["fitxes"])
        self.assertEqual(RV.fitxa_normal(FITXA), "meteocat:2026-10-16T07:55+02:00|2026-10-16T05:55Z")
        # A la següent pasada, sense res de nou, no es desperta.
        self.assertIsNone(self.revisa(ARA + dt.timedelta(minutes=6), [problema])[0])
        # Despertat més tard, el que ja s'ha dit va al context perquè no ho repeteixi.
        self.revisa(ARA.replace(hour=20, minute=50), [])
        context = demana.call_args[0][0] if demana.called else ""
        self.assertIsInstance(context, str)

    def test_greu_sense_correccio_en_un_sol_missatge(self):
        ps = [{"gravetat": "alta", "on": "portada", "que": "plou i no plou"},
              {"gravetat": "mitjana", "on": "Si surts", "que": "bé amb pluja"},
              {"gravetat": "baixa", "on": "taula", "que": "un detall"}]
        self.revisa(ARA, ps)
        textos = [p["text"] for m, p in self.enviats if m == "sendMessage"]
        self.assertEqual(len(textos), 1)
        self.assertIn("4 incoherencia(s)", textos[0])     # amb les dues regles fixes de la fitxa
        self.assertIn("Y 1 leve(s)", textos[0])

    def test_pagines_de_cada_revisio(self):
        # Juanjo, 26-10-2026: «no debería repasarlas todas?». Les del temps
        # d'ara, sempre; «Fiabilitat», amb el resum de la nit; les fixes i
        # config.py, a la mateixa revisió si hi ha una versió nova.
        demanades = []

        def pagines(c, a, llista=None):
            demanades.append(list(llista))
            return {p: "No plou" for p in llista}
        demana = mock.Mock(return_value=({"problemes": []}, {"cost_usd": 0.3, "segons": 40}))

        def revisa(moment):
            return RV.revisa(self.casa, self.avisos, moment, demana_=demana, pagines_=pagines)
        revisa(ARA)
        self.assertEqual(demanades[-1], list(RV.PAGINES))
        self.assertIn("riera.html", demanades[-1])
        self.assertNotIn("config.py", demana.call_args[0][0])
        nit = ARA.replace(hour=20, minute=55)
        self.assertEqual(revisa(nit)["motiu"], "resum 20:50")
        self.assertEqual(demanades[-1], list(RV.PAGINES + RV.PAGINES_DIA + RV.PAGINES_FIXES))
        self.assertIn("## config.py", demana.call_args[0][0])
        self.assertEqual(RV.llegeix(RV.ESTAT, {})["fixes"], RV.C.VERSION)
        # L'endemà, amb la mateixa versió, només «Fiabilitat».
        revisa(nit + dt.timedelta(days=1))
        self.assertEqual(demanades[-1], list(RV.PAGINES + RV.PAGINES_DIA))
        self.assertNotIn("## config.py", demana.call_args[0][0])
        # El matí, sense cap de les dues.
        revisa(ARA.replace(hour=5, minute=55) + dt.timedelta(days=2))
        self.assertEqual(demanades[-1], list(RV.PAGINES))

    def test_toca(self):
        estat = {"darrer_missatge": "2026-10-17T19:13+02:00", "conclusions": RV.empremta(RV.conclusions({}, {})),
                 "darrera": ARA.isoformat()}
        self.assertIsNone(RV.toca(estat, {}, {}, ARA + dt.timedelta(minutes=5), []))
        self.assertEqual(RV.toca(estat, {}, {}, ARA.replace(hour=5, minute=55), []), "resum 05:50")
        self.assertEqual(RV.toca(estat, {"pluja_ara": {"estat": "plou"}}, {}, ARA + dt.timedelta(minutes=40), []),
                         "canvi")
        # Un canvi dins dels 30 minuts espera; un avís enviat, no.
        self.assertIsNone(RV.toca(estat, {"pluja_ara": {"estat": "plou"}}, {}, ARA + dt.timedelta(minutes=10), []))
        self.assertEqual(RV.toca(estat, {}, {"avisos": [{"hora": "2026-10-18T07:05+02:00"}]},
                                 ARA + dt.timedelta(minutes=10), []), "avís enviat")


class ClauFitxa(unittest.TestCase):
    def test_la_correccio_del_publicat_s_aplica_a_l_historial_intern(self):
        # El revisor llegeix avisos.json (hora de Madrid) i avisos_bot aplica
        # la correcció abans de publicar, amb l'historial en UTC (ADR 0128).
        e = {"clau": "pla:INUNCAT", "inici": "2026-10-25T09:00Z", "ca": "a\nb", "es": "a\nb"}
        cs = {"fitxes": {"pla:INUNCAT|2026-10-25T10:00+01:00": {"original": RV.empremta("a\nb"), "ca": "a",
                                                               "es": "a", "hora": "2026-10-25T09:30Z"}}}
        sortida = RV.aplica_correccions({"historial": [e]}, cs)
        self.assertEqual(sortida["historial"][0]["ca"], "a")


if __name__ == "__main__":
    unittest.main()
