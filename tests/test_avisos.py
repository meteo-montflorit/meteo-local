# SPDX-License-Identifier: AGPL-3.0-or-later
"""Texto de los avisos de AEMET (ADR 0033), sin red."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prevision as P  # noqa: E402

FICHA = """<alert><info><language>es-ES</language><event>Aviso de tormentas</event>
<description>Pueden ir acompañadas de granizo,
 en general inferior a 2 cm.</description><instruction>Esté atento.</instruction></info>
<info><language>en-GB</language><description>Pueden ir acompañadas de granizo, en general inferior a 2 cm.
</description><instruction>Be aware.</instruction></info></alert>"""


class Descripcio(unittest.TestCase):
    def setUp(self):
        self.original = P.get_recent

    def tearDown(self):
        P.get_recent = self.original

    def test_text_en_castella_tal_qual(self):
        P.get_recent = lambda url, segons=120: FICHA
        self.assertEqual(P.descripcion_aviso("https://x"), "Pueden ir acompañadas de granizo, en general inferior a 2 cm.")

    def test_sense_text(self):
        P.get_recent = lambda url, segons=120: "<alert><info><language>es-ES</language></info></alert>"
        self.assertIsNone(P.descripcion_aviso("https://x"))


if __name__ == "__main__":
    unittest.main()


def registre(acronim, fase, activat="SI", icona=None, descripcio="Episodi", comunicat=None):
    return {"plaacronim": acronim, "planom": acronim, "plafase": fase, "plaactivat": activat,
            "plaicona": {"url": icona or f"https://documents.dadesobertes.gencat.cat/cecat/docs/ico_{acronim}.png"},
            "fasedatahora": "09/10/2026 08:00", "descripcio": descripcio,
            "comunicatpdf": {"url": comunicat} if comunicat else None}


class PlansProteccioCivil(unittest.TestCase):
    """Prealerta i plans del PROCICAT (ADR 0051), sense xarxa."""
    def setUp(self):
        self.original = P.get

    def tearDown(self):
        P.get = self.original

    def plans(self, registres):
        P.get = lambda url, *a, **k: __import__("json").dumps(registres)
        return {(p["pla"], p["nom"]): p["fase"] for p in P.planes_proteccion_civil()}

    def test_la_prealerta_surt_encara_que_el_pla_no_estigui_activat(self):
        self.assertEqual(self.plans([registre("VENTCAT", "PREALERTA", "NO")]), {("VENTCAT", "de vent"): "prealerta"})
        # Un pla no activat que no és en prealerta, no.
        self.assertEqual(self.plans([registre("VENTCAT", "ALERTA", "NO")]), {})

    def test_procicat_nomes_els_riscos_del_temps_i_de_l_aire(self):
        base = "https://documents.dadesobertes.gencat.cat/cecat/docs/"
        r = self.plans([registre("PROCICAT", "ALERTA", icona=base + "ico_PROCICAT_ONADA_CALOR.png"),
                        registre("PROCICAT", "PREALERTA", "NO", icona=base + "ico_PROCICAT_CONTAMINACI%C3%93.png"),
                        registre("PROCICAT", "ALERTA", icona=base + "ico_PROCICAT_PANDEMIA.png"),
                        registre("PROCICAT", "ALERTA", icona=base + "ico_PROCICAT_FERROCARRIL.png"),
                        registre("PROCICAT", "ALERTA"),
                        registre("INFOCAT", "ALERTA"), registre("TRANSCAT", "EMERGÈNCIA")])
        self.assertEqual(r, {("PROCICAT", "per onada de calor"): "alerta",
                             ("PROCICAT", "per contaminació"): "prealerta"})

    def test_un_pla_sense_motiu_meteorologic_no_es_mostra(self):
        # ADR 0062: l'INUNCAT del 10-10-2026, en alerta des del comunicat del 8 a les 17:14,
        # sense cap avís de l'AEMET: no es mostra. Amb comunicat recent, emergència o avís, sí.
        import datetime as dt
        ara = dt.datetime(2026, 10, 10, 8, 0).astimezone()
        pla = {"pla": "INUNCAT", "fase": "alerta", "des_de": "08/10/2026 17:14"}
        avis = {"zona": "Prelitoral de Barcelona", "tipo": "pluja", "nivel": "groc",
                "inicio": "2026-10-11T03:00:00+02:00", "fin": "2026-10-11T12:00:00+02:00"}
        self.assertFalse(P.pla_per_temps(pla, [], ara))
        self.assertTrue(P.pla_per_temps(dict(pla, des_de="10/10/2026 07:30"), [], ara))      # comunicat de fa poc
        self.assertTrue(P.pla_per_temps(dict(pla, fase="emergència"), [], ara))
        self.assertTrue(P.pla_per_temps(pla, [avis], ara))                                  # avís per a demà a les 3 h
        self.assertFalse(P.pla_per_temps(pla, [dict(avis, inicio="2026-10-11T10:00:00+02:00")], ara))  # més enllà de 24 h
        self.assertFalse(P.pla_per_temps(pla, [dict(avis, tipo="vent")], ara))
        self.assertFalse(P.pla_per_temps(pla, [dict(avis, zona="Litoral de Barcelona")], ara))
        self.assertTrue(P.pla_per_temps(pla, None, ara))                                    # sense avisos llegits: es mostra
        self.assertTrue(P.pla_per_temps(dict(pla, des_de=None), [], ara))

    def test_un_pla_d_altres_comarques_no_es_mostra(self):
        # L'INUNCAT del 02-11-2026 a les 12:07: Meteocat avisava de pluja intensa
        # al Barcelonès, el Garraf, el Tarragonès… i no al Vallès Occidental. No es
        # mostra, encara que el comunicat sigui de fa poc i l'AEMET avisi al Vallès.
        import datetime as dt
        ara = dt.datetime(2026, 11, 2, 12, 33).astimezone()
        pla = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "alerta", "des_de": "02/11/2026 12:07"}
        aemet = [{"zona": "Prelitoral de Barcelona", "tipo": "pluja", "nivel": "groc",
                  "inicio": "2026-11-02T22:00:00+01:00", "fin": "2026-11-03T03:59:59+01:00"}]
        fora = {"avisos": [], "fenomens_catalunya": ["pluja"]}
        self.assertFalse(P.pla_per_temps(pla, aemet, ara, fora))
        self.assertTrue(P.pla_per_temps(dict(pla, fase="emergència"), aemet, ara, fora))
        # Amb avís de Meteocat de pluja al Vallès, sí.
        al_valles = dict(fora, avisos=[{"meteor": "Intensitat de pluja en 30 minuts", "tipus": "previsio",
                                        "perill": 1, "dies": {"2026-11-02": [(23, 24)]}}])
        self.assertTrue(P.pla_per_temps(pla, aemet, ara, al_valles))
        # Meteocat sense avisos de pluja enlloc (o d'un altre fenomen): la regla d'abans.
        self.assertTrue(P.pla_per_temps(pla, aemet, ara, {"avisos": [], "fenomens_catalunya": ["vent"]}))
        self.assertTrue(P.pla_per_temps(pla, aemet, ara, {"avisos": [], "fenomens_catalunya": []}))
        # Sense lectura de Meteocat o amb dades d'abans de la 3.208.0: es mostra.
        self.assertTrue(P.pla_per_temps(pla, aemet, ara, None))
        self.assertTrue(P.pla_per_temps(pla, aemet, ara, {"avisos": []}))
        # Un pla de vent amb avisos de pluja a fora: no és d'altres comarques.
        self.assertTrue(P.pla_per_temps(dict(pla, pla="VENTCAT", nom="de vent"), aemet, ara, fora))

    def test_un_pla_d_altres_comarques_ho_continua_sent(self):
        # 14-11-2026: l'INUNCAT en alerta per la pluja intensa al Montsià va sortir a
        # la portada quan Meteocat va treure l'avís d'allà. Mentre no canvia de fase
        # (clau_pla), continua sent d'aquelles comarques; si Meteocat avisa al Vallès, surt.
        import datetime as dt
        ara = dt.datetime(2026, 11, 14, 20, 9).astimezone()
        pla = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "alerta", "des_de": "14/11/2026 16:33"}
        fora = {"avisos": [], "fenomens_catalunya": ["pluja"]}
        res = {"avisos": [], "fenomens_catalunya": []}
        self.assertTrue(P.de_altres_comarques(pla, fora))
        abans = {P.clau_pla(pla)}
        self.assertTrue(P.pla_per_temps(pla, [], ara, res))                          # sense memòria, sortia
        self.assertFalse(P.pla_per_temps(pla, [], ara, res, abans))
        self.assertFalse(P.pla_per_temps(pla, [], ara, None, abans))                 # sense lectura, igual
        al_valles = dict(res, avisos=[{"meteor": "Intensitat de pluja en 30 minuts", "tipus": "previsio",
                                       "perill": 1, "dies": {"2026-11-14": [(20, 24)]}}])
        self.assertTrue(P.pla_per_temps(pla, [], ara, al_valles, abans))
        # En una altra fase és una activació nova: la regla de sempre.
        self.assertTrue(P.pla_per_temps(dict(pla, fase="emergència"), [], ara, res, abans))
        self.assertTrue(P.pla_per_temps(dict(pla, des_de="14/11/2026 19:00"), [], ara, res, abans))

    def test_un_pla_repetit_es_queda_amb_la_fase_mes_alta(self):
        r = self.plans([registre("INUNCAT", "PREALERTA", "NO"), registre("INUNCAT", "EMERGÈNCIA"),
                        registre("INUNCAT", "ALERTA")])
        self.assertEqual(r, {("INUNCAT", "d'inundacions"): "emergència"})

    def test_fora_de_zona_no(self):
        self.assertEqual(self.plans([registre("NEUCAT", "PREALERTA", "NO", descripcio="Neu al Pirineu")]), {})
