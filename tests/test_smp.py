# SPDX-License-Identifier: AGPL-3.0-or-later
"""Los avisos de peligro de Meteocat de la comarca, junto a los planes (ADR 0067), sin red."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
sys.path.insert(0, os.path.join(ARREL, "bot"))
import avisos_bot as AB  # noqa: E402
import config as C  # noqa: E402
import bot as B  # noqa: E402
import smp  # noqa: E402

AHORA = dt.datetime(2026, 10, 10, 19, 0).astimezone()
MATI = AHORA.replace(hour=11)   # abans de l'avís de 12 a 18 h


def afectacio(comarca, perill, dia="2026-10-10T00:00Z"):
    return {"dia": dia, "llindar": "Intensitat > 20 mm / 30 minuts", "auxiliar": False, "perill": perill,
            "idComarca": comarca, "nivell": 1}


# Com l'exemple de /smp/episodis-oberts de la documentació de l'API de Meteocat.
EPISODIS = [{
    "estat": {"nom": "Obert", "data": None}, "meteor": {"nom": "Intensitat de pluja"},
    "avisos": [{
        "tipus": "Avís", "dataEmisio": "2026-10-10T08:09Z", "dataInici": "2026-10-10T12:00Z",
        "dataFi": "2026-10-11T05:59Z", "estat": "Vigent",
        "evolucions": [
            {"dia": "2026-10-10T00:00Z", "llindar1": "Intensitat > 20 mm / 30 minuts", "periodes": [
                {"nom": "00-06", "afectacions": None}, {"nom": "06-12", "afectacions": None},
                {"nom": "12-18", "afectacions": [afectacio(40, 3), afectacio(41, 2)]},
                {"nom": "18-00", "afectacions": [afectacio(40, 2)]}]},
            {"dia": "2026-10-11T00:00Z", "llindar1": "Intensitat > 20 mm / 30 minuts", "periodes": [
                {"nom": "00-06", "afectacions": [afectacio(40, 1, "2026-10-11T00:00Z")]}]}]},
        {"tipus": "Preavís", "estat": "Vigent", "evolucions": [{"dia": "2026-10-12T00:00Z", "periodes": [
            {"nom": "00-06", "afectacions": [afectacio(40, 5, "2026-10-12T00:00Z")]}]}]}]},
    {"estat": {"nom": "Obert"}, "meteor": {"nom": "Acumulació de pluja"}, "avisos": [{
        "tipus": "Avís", "estat": "Vigent", "dataEmisio": "2026-10-10T08:09Z",
        "evolucions": [{"dia": "2026-10-10T00:00Z", "periodes": [
            {"nom": "12-18", "afectacions": [afectacio(31, 4)]}]}]}]},
]


def pagina(episodis):
    return ("<script>\n            Meteocat.avisosSMP({\n                dom: 'mapaAvisos',\n"
            "                prediccions: [{\"general\":{}}],\n"
            "                episodisPreavisos: [{\"avisos\": [{\"tipus\": \"Preavís\"}]}],\n"
            f"                avisos: {json.dumps(episodis)},\n                cataleg: []\n            }});\n</script>")


class Smp(unittest.TestCase):
    def test_llegeix_els_avisos_de_la_pagina(self):
        self.assertEqual(smp.episodis(pagina(EPISODIS)), EPISODIS)
        self.assertEqual(smp.episodis(pagina([])), [])
        with self.assertRaises(ValueError):
            smp.episodis("<html>sense avisos</html>")

    def test_nomes_els_vigents_de_la_comarca(self):
        a = smp.de_la_comarca(EPISODIS, 40)
        # El preavís i l'avís d'una altra comarca no hi són; les franges seguides, juntes.
        # Cada nivell amb les seves hores: el grau 3 de dissabte no s'estén als
        # graus 1 i 2 (17-10-2026: deia «perill molt alt» per a un dilluns en groc).
        self.assertEqual(len(a), 2)
        self.assertEqual(a[0]["meteor"], "Intensitat de pluja")
        # Les franges són hores UTC (dataInici 12:00Z, la franja 12-18): en
        # hora de Madrid d'estiu, dues més (ADR 0128).
        self.assertEqual((a[0]["perill"], a[0]["dies"]), (3, {"2026-10-10": [(14, 20)]}))
        self.assertEqual((a[1]["perill"], a[1]["dies"]), (2, {"2026-10-10": [(20, 24)], "2026-10-11": [(0, 8)]}))
        self.assertEqual(smp.de_la_comarca(EPISODIS, 99), [])

    def test_les_franges_son_hores_utc(self):
        # L'avís real de l'acumulació del 19-10-2026: dataInici 06:00Z i dataFi
        # 05:59Z del 20, franges 06-12, 12-18 i 18-00 del 19 i 00-06 del 20.
        def af(dia):
            return [afectacio(40.0, 2.0, dia)]
        ep = {"id": None, "estat": {"nom": "Obert", "data": None}, "meteor": {"idMeteor": None, "nom": "Acumulació de pluja"},
              "avisos": [{"tipus": "Avís", "estat": "Vigent", "dataEmisio": "2026-10-19T08:46Z",
                          "dataInici": "2026-10-19T06:00Z", "dataFi": "2026-10-20T05:59Z", "evolucions": [
                              {"dia": "2026-10-19T00:00Z", "llindar1": "Acumulada > 100 mm /24 hores", "periodes": [
                                  {"nom": "00-06", "afectacions": None}, {"nom": "06-12", "afectacions": af("2026-10-19T00:00Z")},
                                  {"nom": "12-18", "afectacions": af("2026-10-19T00:00Z")},
                                  {"nom": "18-00", "afectacions": af("2026-10-19T00:00Z")}]},
                              {"dia": "2026-10-20T00:00Z", "llindar1": "Acumulada > 100 mm /24 hores", "periodes": [
                                  {"nom": "00-06", "afectacions": af("2026-10-20T00:00Z")}]}]}]}
        a = smp.de_la_comarca(smp.episodis(pagina([[ep]])))
        # De les 8 h del 19 a les 8 h del 20, en hora d'estiu: el mateix que dataInici i dataFi.
        self.assertEqual(a[0]["dies"], {"2026-10-19": [(8, 24)], "2026-10-20": [(0, 8)]})

    def test_grau_com_el_mapa_de_meteocat(self):
        self.assertEqual([smp.nivell(p) for p in range(1, 7)], ["mig", "mig", "alt", "alt", "maxim", "maxim"])

    def test_textos(self):
        r = smp.llegeix(lambda url: pagina(EPISODIS), MATI)
        l = r["linies"][0]
        self.assertEqual(l["nivell"], "alt")
        hora = smp.hora_local("2026-10-10T08:09Z")
        self.assertEqual(l["ca"], "Meteocat: avís de perill alt per «Intensitat de pluja» al Vallès Occidental, "
                                  f"dissabte 10 de 14 a 20 h (Intensitat > 20 mm / 30 minuts; emès a les {hora}).")
        self.assertTrue(l["es"].startswith("Meteocat: aviso de peligro alto por «Intensitat de pluja» en el Vallès "
                                           "Occidental, sábado 10 de 14 a 20 h"))
        self.assertTrue(r["linies"][1]["ca"].startswith("Meteocat: avís de perill moderat per «Intensitat de pluja» al "
                                                        "Vallès Occidental, dissabte 10 de 20 a 24 h i diumenge 11 de 0 a 8 h"))
        # El resum per fenomen, igual: cada nivell amb les seves hores, sense repetir-ne.
        self.assertEqual([(f["nivell"], f["dies"]) for f in smp.per_fenomen(r["avisos"])],
                         [("alt", {"2026-10-10": [[14, 20]]}),
                          ("mig", {"2026-10-10": [[20, 24]], "2026-10-11": [[0, 8]]})])
        # Les hores passades no surten al resum: a les 19 h, de 14 a 19 h ja no.
        tarda = smp.llegeix(lambda url: pagina(EPISODIS), AHORA)
        self.assertEqual([(f["nivell"], f["dies"]) for f in tarda["fenomens"]],
                         [("alt", {"2026-10-10": [[19, 20]]}),
                          ("mig", {"2026-10-10": [[20, 24]], "2026-10-11": [[0, 8]]})])
        # Ni a les línies (18-10-2026: Meteocat manté al vigent les franges
        # passades, i la fitxa deia les del dia abans); els avisos, sencers.
        self.assertEqual([l["nivell"] for l in tarda["linies"]], ["alt", "mig"])
        self.assertIn("dissabte 10 de 19 a 20 h", tarda["linies"][0]["ca"])
        self.assertIn("dissabte 10 de 20 a 24 h i diumenge 11 de 0 a 8 h", tarda["linies"][1]["ca"])
        self.assertEqual(len(tarda["avisos"]), 2)
        cap = smp.llegeix(lambda url: pagina([]), AHORA)["linies"]
        self.assertEqual(cap, [{"nivell": "nul",
                                "ca": "Meteocat no té cap avís de perill per al Vallès Occidental (dades de les 19:00).",
                                "es": "Meteocat no tiene ningún aviso de peligro para el Vallès Occidental "
                                      "(datos de las 19:00)."}])

    def test_a_part_del_pla(self):
        s = smp.llegeix(lambda url: pagina(EPISODIS), MATI)
        pla = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "alerta"}
        d = {"generat": AHORA.isoformat(), "plans": [pla], "smp": s}
        r = B.text_avisos_actius(d, "ca", AHORA)
        # Meteocat, en el seu bloc, separat de Protecció Civil (Juanjo, 17-10-2026).
        self.assertIn("🟠 Pla d'inundacions (INUNCAT) en fase d'alerta.\n\n", r)
        self.assertIn("🟠 Meteocat: avís de perill alt", r)
        self.assertLess(r.index("Pla d'inundacions"), r.index("Meteocat: avís"))
        # L'avís del pla nou no porta els de Meteocat, que tenen el seu.
        self.assertNotIn("Meteocat", AB.text_pla(pla)["ca"])
        self.assertNotIn("Meteocat", AB.text_pla(pla)["es"])
        self.assertNotIn("Meteocat", B.text_avisos_actius({**d, "smp": None}, "ca", AHORA))

    def test_sense_pla_surt_sol(self):
        # ADR 0071: sense pla, als avisos actius amb el nom de Meteocat; el
        # «no hi ha cap avís», no.
        s = smp.llegeix(lambda url: pagina(EPISODIS), MATI)
        r = B.text_avisos_actius({"generat": AHORA.isoformat(), "plans": [], "smp": s}, "ca", AHORA)
        self.assertIn("<b>Meteocat</b>\n🟠 Meteocat: avís de perill alt", r)
        buit = smp.llegeix(lambda url: pagina([]), AHORA)
        self.assertNotIn("Meteocat", B.text_avisos_actius({"generat": AHORA.isoformat(), "smp": buit}, "ca", AHORA))

    def test_la_llista_agrupada_de_meteo_cat(self):
        # El 16-10-2026 la pàgina portava els episodis en dos blocs repetits
        # ([[…], […]]) i la lectura fallava: ara s'aplana i cada un va una vegada.
        self.assertEqual(smp.episodis(pagina([EPISODIS, EPISODIS])), EPISODIS)
        self.assertEqual(len(smp.de_la_comarca(smp.episodis(pagina([EPISODIS, EPISODIS])), 40)), 2)
        with self.assertRaises(ValueError):
            smp.episodis(pagina([["no és un episodi"]]))

    def test_avisos_d_observacio_i_temps_violent(self):
        # «Avís Vigilància» i «… per Temps Violent»: hora d'inici i de fi i les
        # comarques a l'avís mateix (script.min.js de meteo.cat).
        obs = [{"meteor": {"nom": "Intensitat de pluja"}, "avisos": [{
                    "tipus": "Avís Vigilància", "estat": "Vigent", "dataEmisio": "2026-10-17T13:10Z",
                    "dataInici": "2026-10-17T13:20Z", "dataFi": "2026-10-17T15:00Z",
                    "afectacions": [afectacio(40, 3), afectacio(41, 4)]}]},
               {"meteor": {"nom": "Temps violent"}, "avisos": [{
                    "tipus": "Avís Vigilància per Temps Violent", "estat": "Vigent", "dataEmisio": "2026-10-17T13:30Z",
                    "dataInici": "2026-10-17T13:30Z", "dataFi": "2026-10-17T14:30Z",
                    "afectacions": [afectacio(41, 5)]}]}]
        a = smp.de_la_comarca(obs, 40)
        self.assertEqual(len(a), 1)                                  # el de temps violent és d'una altra comarca
        self.assertEqual((a[0]["tipus"], a[0]["perill"]), ("observacio", 3))
        inici = dt.datetime.fromisoformat("2026-10-17T13:20+00:00").astimezone()
        self.assertEqual(a[0]["dies"], {inici.date().isoformat(): [(inici.hour, inici.hour + 2)]})
        self.assertTrue(smp.textos(a, "15:30")[0]["ca"].startswith(
            "Meteocat: avís d'observació de perill alt per «Intensitat de pluja» al Vallès Occidental"))
        self.assertEqual(smp.de_la_comarca(obs, 41)[1]["tipus"], "temps_violent")

    def test_la_pagina_real_del_16_d_octubre(self):
        # Retallada de la pàgina real: dos blocs repetits, cada avís amb la
        # versió «Ampliat» (l'anterior) i la «Vigent».
        def av(estat, emissio, perill):
            return {"tipus": "Avís", "estat": estat, "dataEmisio": emissio, "evolucions": [{
                "dia": "2026-10-17T00:00Z", "llindar1": "Intensitat > 20 mm / 30 minuts", "periodes": [
                    {"nom": "06-12", "afectacions": None},
                    {"nom": "12-18", "afectacions": [afectacio(40.0, perill, "2026-10-17T00:00Z")]},
                    {"nom": "18-00", "afectacions": [afectacio(40.0, perill, "2026-10-17T00:00Z")]}]}]}
        ep = {"id": None, "estat": {"nom": "Obert", "data": None},
              "meteor": {"idMeteor": None, "nom": "Intensitat de pluja en 30 minuts"},
              "avisos": [av("Ampliat", "2026-10-15T07:28Z", 2.0), av("Vigent", "2026-10-15T16:20Z", 3.0)]}
        a = smp.de_la_comarca(smp.episodis(pagina([[ep], [ep]])))
        # De 12 a 24 h UTC: de 14 a 2 h de Madrid, en estiu.
        self.assertEqual([(x["perill"], x["dies"]) for x in a],
                         [(3, {"2026-10-17": [(14, 24)], "2026-10-18": [(0, 2)]})])

    def test_meteocat_avisa_per_fenomen(self):
        # ADR 0092: el primer, si puja de nivell, un fenomen nou i hores noves;
        # no una nova emissió igual, una baixada ni un avís menor del mateix fenomen.
        estat = {}

        def passa(avisos, minuts):
            s = {"avisos": avisos, "linies": []}
            return [a for a in AB.decideix(estat, {"smp": s}, AHORA + dt.timedelta(minutes=minuts))
                    if a["tipus"] == "perill"]

        def av(meteor, perill, dies, tipus="previsio"):
            return {"meteor": meteor, "tipus": tipus, "llindar": "Intensitat > 20 mm / 30 minuts",
                    "perill": perill, "emissio": "2026-10-16T16:20Z", "dies": dies}
        dissabte = {"2026-10-17": [(12, 24)]}
        p30 = av("Intensitat de pluja en 30 minuts", 3, dissabte)
        p3h = av("Intensitat de pluja en 3 hores", 2, dissabte)
        self.assertEqual(passa([], 0), [])                                   # la primera vegada, s'apunta
        nous = passa([p30, p3h], 6)
        self.assertEqual(len(nous), 1)                                       # els dos de pluja, un sol avís
        self.assertEqual(nous[0]["ca"].splitlines()[0],
                         "🟠 <b>Meteocat: avís de perill alt per pluja al Vallès Occidental</b>")
        self.assertIn("\n🟠 Perill alt per «Intensitat de pluja en 30 minuts»: dissabte 17 de 12 a 24 h "
                      "(Intensitat > 20 mm / 30 minuts).", nous[0]["ca"])
        self.assertIn("\n🟡 Perill moderat per «Intensitat de pluja en 3 hores»", nous[0]["ca"])
        self.assertEqual(nous[0]["nivell"], "alt")
        episodi = nous[0]["episodi"]
        self.assertEqual(passa([dict(p30, emissio="2026-10-17T07:00Z"), p3h], 12), [])   # nova emissió igual
        self.assertEqual(passa([dict(p30, perill=4), p3h], 18), [])           # 4 és «alt», com el 3
        self.assertEqual(passa([dict(p30, perill=2), p3h], 24), [])           # baixa: res
        puja = passa([dict(p30, perill=5), p3h], 30)
        self.assertEqual(puja[0]["ca"].splitlines()[0],
                         "🔴 <b>Meteocat: actualització, puja a perill molt alt per pluja al Vallès Occidental</b>")
        self.assertEqual(puja[0]["episodi"], episodi)                         # la mateixa fitxa a «Perill»
        amplia = passa([dict(p30, perill=5, dies={**dissabte, "2026-10-18": [(0, 6)]})], 36)
        self.assertIn("Meteocat: actualització, amplia l'avís de perill molt alt per pluja", amplia[0]["ca"])
        vent = passa([dict(p30, perill=5, dies={**dissabte, "2026-10-18": [(0, 6)]}),
                      av("Ratxa màxima de vent", 1, dissabte)], 42)
        self.assertIn("Meteocat: actualització, avisa també de perill moderat per vent", vent[0]["ca"])
        self.assertEqual(vent[0]["nivell"], "maxim")                          # el color, el pitjor dels vigents
        obs = passa([dict(p30, perill=5, dies={**dissabte, "2026-10-18": [(0, 6)]}), av("Ratxa màxima de vent", 1, dissabte),
                     av("Intensitat de pluja", 3, {"2026-10-17": [(15, 17)]}, "observacio")], 48)
        self.assertIn("Meteocat: s'observa perill alt per pluja al Vallès Occidental", obs[0]["ca"])
        self.assertIn("Observat ara, perill alt per «Intensitat de pluja»", obs[0]["ca"])
        # Si no hi ha lectura, res; quan ja no en queda cap (passada la mitja hora), el final.
        self.assertEqual(AB.decideix(estat, {"smp": None}, AHORA + dt.timedelta(minutes=54)), [])
        self.assertEqual(passa([], 60), [])
        fi = passa([], 90)
        self.assertEqual(fi[0]["ca"], "🟢 <b>Meteocat: ja no hi ha cap avís de perill per al Vallès Occidental</b>")
        self.assertEqual((fi[0]["nivell"], fi[0]["episodi"]), ("fi", episodi))
        self.assertEqual(passa([], 96), [])
        # Un de nou després, un episodi nou.
        torna = passa([p3h], 102)
        self.assertTrue(torna[0]["ca"].startswith("🟡 <b>Meteocat: avís de perill moderat per pluja"))
        self.assertNotEqual(torna[0]["episodi"], episodi)

    def test_la_fitxa_diu_el_que_queda(self):
        # 18-10-2026: Meteocat mantenia al vigent les franges del dissabte, i la
        # fitxa de «Perill» deia «Observat ara» i el dissabte el diumenge
        # (Juanjo: «no está una parte ya pasada?»). Ara, sense enviar res, la
        # fitxa diu el que queda, i l'episodi s'acaba quan no en queda cap.
        estat = {}

        def av(meteor, perill, dies, tipus="previsio"):
            return {"meteor": meteor, "tipus": tipus, "llindar": None, "perill": perill,
                    "emissio": "2026-10-17T16:20Z", "dies": dies}
        avisos = [av("Intensitat de pluja en 30 minuts", 5, {"2026-10-17": [(18, 24)]}),
                  av("Intensitat de pluja en 30 minuts", 1, {"2026-10-19": [(12, 24)]}),
                  av("Temps violent", 3, {"2026-10-17": [(19, 22)]}, "temps_violent")]

        def passa(avisos, ara):
            nous = [a for a in AB.decideix(estat, {"smp": {"avisos": avisos}}, ara) if a["tipus"] == "perill"]
            AB.historial(estat, nous, ara)
            return nous
        dissabte = dt.datetime(2026, 10, 17, 17, 0).astimezone()
        passa([], dissabte)
        self.assertEqual(len(passa(avisos[:2], dissabte + dt.timedelta(minutes=5))), 1)
        obs = passa(avisos, dissabte.replace(hour=19, minute=13))
        self.assertIn("Observat ara", obs[0]["ca"])
        fitxa = lambda: next(e for e in estat["historial"] if e["clau"] == obs[0]["episodi"])  # noqa: E731
        self.assertEqual(fitxa()["ca"], obs[0]["ca"])
        # El mateix a les 19:20: la fitxa es queda el text de l'avís.
        self.assertEqual(passa(avisos, dissabte.replace(hour=19, minute=20)), [])
        self.assertEqual(fitxa()["ca"], obs[0]["ca"])
        # Diumenge: cap missatge, i la fitxa, en groc, només amb el dilluns.
        self.assertEqual(passa(avisos, dt.datetime(2026, 10, 18, 6, 0).astimezone()), [])
        self.assertEqual(fitxa()["ca"],
                         "🟡 <b>Meteocat: avís de perill moderat per pluja al Vallès Occidental</b>\n"
                         "🟡 Perill moderat per «Intensitat de pluja en 30 minuts»: dilluns 19 de 12 a 24 h.\n"
                         "És un avís oficial: segueix les indicacions de Protecció Civil.")
        self.assertTrue(fitxa()["es"].startswith("🟡 <b>Meteocat: aviso de peligro moderado por lluvia"))
        # I diu quan comença el que queda: la fitxa en surt «Previst» (ADR 0101).
        import hora as HR
        self.assertEqual(HR.utc(fitxa()["comenca"]), dt.datetime(2026, 10, 19, 12).astimezone())
        self.assertNotIn("fi", fitxa())
        # Passat el dilluns, el final, encara que Meteocat no l'hagi retirat.
        self.assertEqual(passa(avisos, dt.datetime(2026, 10, 19, 23, 55).astimezone()), [])
        dimarts = dt.datetime(2026, 10, 20, 0, 5).astimezone()
        self.assertEqual(passa(avisos, dimarts), [])
        fi = passa(avisos, dimarts + dt.timedelta(minutes=C.SMP_FI_MIN))
        self.assertEqual(fi[0]["ca"], "🟢 <b>Meteocat: ja no hi ha cap avís de perill per al Vallès Occidental</b>")
        self.assertIn("fi", fitxa())

    def test_franja_de_l_aemet_amb_el_dia(self):
        # 18-10-2026: les fitxes deien «Des de demà…» d'avisos de dies abans.
        ara = dt.datetime(2026, 10, 18, 0, 15).astimezone()
        self.assertEqual(AB.franja("2026-10-19T16:00:00+02:00", "2026-10-19T23:59:59+02:00", ara, "ca"),
                         "Des del dilluns 19 a les 16 h fins a mitjanit.")
        self.assertEqual(AB.franja("2026-10-19T16:00:00+02:00", "2026-10-20T03:59:59+02:00", ara, "es"),
                         "Desde el lunes 19 a las 16 h hasta el martes 20 a las 4 h.")
        self.assertEqual(AB.franja("2026-10-18T00:00:00+02:00", "2026-10-18T03:59:59+02:00", ara, "ca"),
                         "Diumenge 18, de les 0 h a les 4 h.")

    def test_l_estat_d_abans_avisa_el_que_hi_ha(self):
        # Fins a la 3.86.3 l'estat era {clau: grau} i, com que la lectura fallava,
        # buit: el que hi ha ara s'avisa una vegada.
        estat = {"oficials": {"aemet": {}, "plans": {}, "smp": {}}}
        s = smp.llegeix(lambda url: pagina(EPISODIS), AHORA)
        self.assertEqual(len(AB.decideix(estat, {"smp": s}, AHORA)), 1)
        self.assertEqual(AB.decideix(estat, {"smp": s}, AHORA + dt.timedelta(minutes=6)), [])

    def test_l_aemet_per_al_que_meteocat_no_cobreix(self):
        # ADR 0093: per fenomen i hores, mana Meteocat; l'AEMET avisa del que
        # Meteocat no cobreix (Juanjo, 16-10-2026: «si meteocat no tiene aviso
        # y aemet sí, debe salir aemet»). Les tempestes, sempre de l'AEMET.
        pluja = {"zona": "Prelitoral de Barcelona", "tipo": "pluja", "nivel": "groc",
                 "inicio": "2026-10-17T12:00:00+02:00", "fin": "2026-10-17T23:59:59+02:00"}
        tempestes = dict(pluja, tipo="tempestes")
        mc = {"meteor": "Intensitat de pluja en 30 minuts", "tipus": "previsio", "llindar": None, "perill": 3,
              "emissio": "2026-10-16T16:20Z", "dies": {"2026-10-17": [(12, 24)]}}
        amb = {"avisos": [mc], "linies": []}
        self.assertTrue(smp.cobreix([mc], pluja))
        self.assertFalse(smp.cobreix([mc], tempestes))
        self.assertFalse(smp.cobreix([mc], dict(pluja, inicio="2026-10-18T12:00:00+02:00",
                                                 fin="2026-10-18T23:59:59+02:00")))      # un altre dia
        self.assertFalse(smp.cobreix([dict(mc, meteor="Ratxa màxima de vent")], pluja))   # un altre fenomen
        estat = {}

        def perill(sal, m):
            sal = {**sal, "avisos": [dict(a) for a in sal["avisos"]]}
            smp.marca_coberts(sal["avisos"], sal["smp"])
            return [a for a in AB.decideix(estat, sal, AHORA + dt.timedelta(minutes=m)) if a["tipus"] == "perill"]
        self.assertEqual(perill({"avisos": [], "smp": amb}, 0), [])                     # s'apunta
        nous = perill({"avisos": [pluja, tempestes], "smp": amb}, 6)
        self.assertEqual([a["id"].split(":")[2] for a in nous], ["tempestes"])          # la pluja la cobreix Meteocat
        self.assertEqual(estat["aemet_coberts"], ["aemet:pluja:2026-10-17T12:00:00+02:00"])
        # Si Meteocat la deixa de cobrir (o no es pot llegir), surt la de l'AEMET.
        nous = perill({"avisos": [pluja, tempestes], "smp": None}, 12)
        self.assertEqual([a["id"].split(":")[2] for a in nous], ["pluja"])
        self.assertEqual(perill({"avisos": [pluja, tempestes], "smp": None}, 18), [])

    def test_l_aemet_surt_a_les_hores_que_meteocat_no_cobreix(self):
        # 19-10-2026: el groc de pluja de l'AEMET del 20, de 4 a 6:59, no sortia a la
        # franja de les 6 a les 7 perquè Meteocat avisava fins a les 6: n'hi havia prou
        # amb una hora coberta per amagar-lo sencer. Ara surt a les que no cobreix.
        aemet = {"zona": "Prelitoral de Barcelona", "tipo": "pluja", "nivel": "groc",
                 "inicio": "2026-10-20T04:00:00+02:00", "fin": "2026-10-20T06:59:59+02:00"}
        mc = {"meteor": "Acumulació de pluja", "tipus": "previsio", "llindar": None, "perill": 3,
              "emissio": "2026-10-19T16:20Z", "dies": {"2026-10-20": [(0, 6)]}}
        avisos = [dict(aemet)]
        smp.marca_coberts(avisos, {"avisos": [mc]})
        a = avisos[0]
        self.assertNotIn("cobert", a)
        self.assertEqual((a["inicio_visible"], a.get("fin_visible")), ("2026-10-20T06:00:00+02:00", None))
        self.assertFalse(smp.cobreix([mc], aemet))
        self.assertEqual(smp.visible(a)["inicio"], "2026-10-20T06:00:00+02:00")
        # A la taula per hores (casa.avisos_del_tramo, el que es mostra): a les 6, sí; a les 5, no.
        import casa
        tram = lambda h: casa.avisos_del_tramo(dt.datetime.fromisoformat(f"2026-10-20T{h:02d}:00+02:00"),
                                               dt.datetime.fromisoformat(f"2026-10-20T{h + 1:02d}:00+02:00"), avisos, tots=False)
        self.assertEqual(tram(6), [{"nivell": "groc", "tipus": ["pluja"]}])
        self.assertEqual(tram(5), [])
        # Al resum del bot, també, amb l'hora de les 6.
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot"))
        import bot as B
        ara = dt.datetime(2026, 10, 20, 3, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        text = B.text_avisos_aemet({"avisos": avisos}, "ca", ara.date(), ara)
        self.assertEqual(text, ["🟡 AEMET: avís groc per pluja al Vallès de 06:00 a 07:00."])
        # Cobert del tot (Meteocat fins a les 7), no surt enlloc; sense lectura de Meteocat, sencer.
        avisos = [dict(aemet)]
        smp.marca_coberts(avisos, {"avisos": [dict(mc, dies={"2026-10-20": [(0, 7)]})]})
        self.assertEqual(avisos[0].get("cobert"), "meteocat")
        avisos = [dict(aemet)]
        smp.marca_coberts(avisos, None)
        self.assertEqual(smp.visible(avisos[0]), aemet)

    def test_la_fitxa_de_l_aemet_es_tanca_si_la_cobreix_meteocat(self):
        estat = {"aemet_coberts": ["aemet:pluja:x"]}
        h = AB.historial(estat, [{"id": "perill:aemet:pluja:x:groc", "tipus": "perill", "nivell": "groc",
                                  "hora": AHORA.isoformat(timespec="minutes"), "ca": "a", "es": "a",
                                  "episodi": "aemet:pluja:x"}], AHORA)
        self.assertEqual(h[0]["fi_ca"], "Meteocat en té avís per al Vallès Occidental: ara es mostra el seu.")
        # Amb la fitxa de Meteocat que la substitueix, perquè «Perill» no la doni per acabada.
        mc = {"id": "perill:meteocat:x", "tipus": "perill", "nivell": "alt", "hora": AHORA.isoformat(timespec="minutes"),
              "ca": "b", "es": "b", "episodi": "meteocat:x"}
        estat["oficials"] = {"smp": {"episodi": "meteocat:x"}}
        h = AB.historial(estat, [mc], AHORA)
        self.assertEqual(h[0]["substituit_per"], {"clau": "meteocat:x", "inici": AHORA.isoformat(timespec="minutes")})

    def test_la_fitxa_de_l_aemet_segueix_l_aemet(self):
        # 17-10-2026: l'AEMET va juntar els avisos de demà de 0 a 4 h en el d'avui, allargat fins a les 4 h.
        hora = AHORA.isoformat(timespec="minutes")
        fitxa = lambda k, fins: {"clau": k, "tipus": "perill", "inici": hora, "nivell": "groc", "ca": "x", "es": "x",
                                 "fins": fins}
        avui_t, dema_t = "aemet:tempestes:2026-10-17T12:00:00+02:00", "aemet:tempestes:2026-10-18T00:00:00+02:00"
        dema_p, altra = "aemet:pluja:2026-10-18T00:00:00+02:00", "aemet:neu:2026-10-18T00:00:00+02:00"
        fi = "2026-10-18T03:59:59+02:00"
        estat = {"historial": [fitxa(avui_t, "2026-10-17T23:59:59+02:00"), fitxa(dema_t, fi), fitxa(dema_p, fi), fitxa(altra, fi)],
                 "aemet_vigents": {avui_t: {"fin": fi, "cobert": False},
                                   "aemet:pluja:2026-10-17T12:00:00+02:00": {"fin": fi, "cobert": True}}}
        h = {e["clau"]: e for e in AB.historial(estat, [], AHORA)}
        self.assertEqual(h[avui_t]["fins"], fi)                        # allargat
        self.assertEqual(h[avui_t]["allargat_de"], "2026-10-17T23:59:59+02:00")   # la fitxa ho diu
        self.assertNotIn("allargat_de", h[dema_t])
        self.assertNotIn("fi", h[avui_t])
        self.assertEqual(h[dema_t]["fi_ca"], AB.INCLOS["ca"])          # dins del d'avui
        self.assertEqual(h[dema_t]["substituit_per"], {"clau": avui_t, "inici": hora})
        self.assertEqual(h[dema_p]["fi_ca"], AB.SUBSTITUIT["ca"])      # dins d'un que cobreix Meteocat
        self.assertEqual(h[altra]["fi_ca"], AB.RETIRAT["ca"])          # retirat
        # Sense lectura de l'AEMET, no es toca res.
        estat = {"historial": [fitxa(dema_t, fi)], "aemet_vigents": None}
        self.assertNotIn("fi", AB.historial(estat, [], AHORA)[0])

    def test_la_fitxa_de_l_aemet_allargada_diu_el_final_nou(self):
        # 19-10-2026: «Dimarts 20, de les 6 h a les 7 h» i, a sota, «L'AEMET l'ha allargat fins a
        # dt. 20/10, 08:59»; la portada deia de 6 a 9 (revisor). La línia passa a dir el final nou.
        k = "aemet:pluja:2026-10-20T04:00:00+02:00"
        ca = "🟡 <b>AEMET: avís groc per pluja al Vallès</b>\nDimarts 20, de les 6 h a les 7 h.\n«20 mm.»"
        es = "🟡 <b>AEMET: aviso amarillo por lluvia en el Vallès</b>\nMartes 20, de las 6 h a las 7 h.\n«20 mm.»"
        fitxa = {"clau": k, "tipus": "perill", "inici": "2026-10-19T10:30+02:00", "nivell": "groc", "ca": ca, "es": es,
                 "fins": "2026-10-20T06:59:59+02:00", "comenca": "2026-10-20T06:00:00+02:00"}
        estat = {"historial": [fitxa], "aemet_vigents": {k: {"fin": "2026-10-20T08:59:59+02:00", "cobert": False}}}
        e = AB.historial(estat, [], AHORA)[0]
        self.assertEqual(e["ca"].split("\n")[1], "Dimarts 20, de les 6 h a les 9 h.")
        self.assertEqual(e["es"].split("\n")[1], "Martes 20, de las 6 h a las 9 h.")
        self.assertEqual((e["allargat_de"], e["franja_fins"]), ("2026-10-20T06:59:59+02:00", "2026-10-20T08:59:59+02:00"))
        # Si l'allarga una altra vegada, també; i la fitxa que ja estava allargada abans d'aquesta
        # versió (sense franja_fins) es corregeix a la passada següent.
        estat["aemet_vigents"][k]["fin"] = "2026-10-20T11:59:59+02:00"
        e = AB.historial(estat, [], AHORA)[0]
        self.assertEqual(e["ca"].split("\n")[1], "Dimarts 20, de les 6 h a les 12 h.")
        vella = dict(fitxa, fins="2026-10-20T08:59:59+02:00", allargat_de="2026-10-20T06:59:59+02:00")
        e = AB.historial({"historial": [vella], "aemet_vigents": {k: {"fin": vella["fins"], "cobert": False}}}, [], AHORA)[0]
        self.assertEqual(e["ca"].split("\n")[1], "Dimarts 20, de les 6 h a les 9 h.")
        # Sense la línia (la va treure el revisor), no es toca.
        sense = dict(fitxa, ca="🟡 <b>AEMET</b>\nÉs un avís oficial.", es="🟡 <b>AEMET</b>\nEs un aviso oficial.")
        e = AB.historial({"historial": [sense], "aemet_vigents": {k: {"fin": vella["fins"], "cobert": False}}}, [], AHORA)[0]
        self.assertEqual(e["ca"], sense["ca"])
        self.assertNotIn("franja_fins", e)

    def test_avis_a_juanjo_en_el_moment(self):
        # Si la passada no ha pogut llegir Meteocat, una vegada; i quan torna.
        from unittest import mock
        with tempfile.TemporaryDirectory() as dir:
            casa, sortida = os.path.join(dir, "casa.json"), os.path.join(dir, "avisos.json")
            marca = os.path.join(dir, "aprenentatge", "smp-falla")

            def passa(salida):
                with open(casa, "w", encoding="utf-8") as f:
                    json.dump(salida, f)
                with mock.patch.object(AB, "ESTAT", os.path.join(dir, "estat.json")), \
                        mock.patch.object(AB, "MARCA_SMP", marca), \
                        mock.patch("avis_privat.envia") as envia:
                    AB.actualitza(casa, sortida, ahora=AHORA)
                return [c.args[0] for c in envia.call_args_list]
            falla = passa({"smp": None, "errors": ["smp: 'list' object has no attribute 'get'"]})
            self.assertEqual(len(falla), 1)
            self.assertIn("no es poden llegir els avisos de perill de Meteocat ('list' object", falla[0])
            self.assertIn("els veïns reben els avisos de l'AEMET", falla[0])
            self.assertEqual(passa({"smp": None, "errors": []}), [])
            # La pàgina continua caiguda, però els avisos arriben de l'API.
            api = passa({"smp": {"avisos": [], "linies": [], "falla_pagina": "x"}})
            self.assertEqual(len(api), 1)
            self.assertIn("es llegeixen de l'API", api[0])
            self.assertEqual(passa({"smp": {"avisos": [], "linies": []}}),
                             ["Temps a Montflorit: els avisos de perill de Meteocat es tornen a llegir."])
            self.assertEqual(passa({"smp": {"avisos": [], "linies": []}}), [])
            self.assertEqual(passa({}), [])                                    # sense la clau, res

    def test_prova_diaria(self):
        with tempfile.TemporaryDirectory() as dir:
            marca = os.path.join(dir, "smp-falla")
            self.assertIsNotNone(smp.comprova(lambda url: "<html></html>", marca, avisa=False, api=None))
            self.assertTrue(os.path.exists(marca))
            self.assertIsNone(smp.comprova(lambda url: pagina([]), marca, avisa=False, api=None))
            self.assertFalse(os.path.exists(marca))
            # Una forma que no se sap llegir també és una fallada (el 16-10-2026
            # la prova diària només mirava que hi hagués la llista).
            self.assertIsNotNone(smp.comprova(lambda url: pagina([[{"avisos": [{"estat": "Vigent", "evolucions": [
                {"periodes": [{"nom": "x", "afectacions": [afectacio(40, 3)]}]}]}]}]]), marca, avisa=False, api=None))
            # Amb la pàgina caiguda i l'API bé, la marca diu «api».
            os.remove(marca)
            self.assertIsNotNone(smp.comprova(lambda url: "<html></html>", marca, avisa=False, api=lambda ara: EPISODIS))
            with open(marca, encoding="utf-8") as f:
                self.assertEqual(f.read(), "api")

    def test_reserva_de_l_api(self):
        # Si la pàgina falla, els mateixos episodis de l'API (ADR 0109).
        s = smp.llegeix(lambda url: "<html></html>", MATI, api=lambda ara: EPISODIS)
        self.assertEqual(s["avisos"], smp.llegeix(lambda url: pagina(EPISODIS), MATI, api=None)["avisos"])
        self.assertIn("no porta els avisos", s["falla_pagina"])
        self.assertNotIn("falla_pagina", smp.llegeix(lambda url: pagina(EPISODIS), MATI, api=None))

        def cau(ara):
            raise ValueError("HTTP Error 429")
        with self.assertRaises(ValueError) as e:
            smp.llegeix(lambda url: "<html></html>", MATI, api=cau)
        self.assertIn("no porta els avisos", str(e.exception))
        self.assertIn("API: HTTP Error 429", str(e.exception))

    def test_l_api_com_a_molt_cada_mitja_hora(self):
        with tempfile.TemporaryDirectory() as dir:
            cache = os.path.join(dir, "smp-api.json")
            urls = []

            def baixa(url, clau):
                urls.append((url, clau))
                return json.dumps(EPISODIS)
            self.assertEqual(smp.episodis_api(MATI, "k", baixa, cache), EPISODIS)
            self.assertEqual(urls, [("https://api.meteo.cat/pronostic/v2/smp/episodis-oberts?data=2026-10-10Z", "k")])
            smp.episodis_api(MATI + dt.timedelta(minutes=29), "k", baixa, cache)
            self.assertEqual(len(urls), 1)
            smp.episodis_api(MATI + dt.timedelta(minutes=30), "k", baixa, cache)
            self.assertEqual(len(urls), 2)
            # Una resposta que no és la llista no es desa.
            with self.assertRaises(ValueError):
                smp.episodis_api(MATI + dt.timedelta(hours=2), "k", lambda url, clau: '{"message": "x"}', cache)
            # Sense clau: ni la de l'entorn ni la de ~/.config de la màquina on es prova
            # (al NAS hi és i la prova fallava; ho va trobar el reparador, ADR 0113).
            with mock.patch.object(smp, "clau_api", return_value=None), self.assertRaises(ValueError):
                smp.episodis_api(MATI + dt.timedelta(hours=2), "", baixa, os.path.join(dir, "buida.json"))

    def test_marca_amb_l_api(self):
        with tempfile.TemporaryDirectory() as dir:
            marca = os.path.join(dir, "smp-falla")
            api = smp.marca_falla(marca, "x", avisa=False, reserva=True)
            self.assertIn("es llegeixen de l'API, cada 30 minuts", api)
            self.assertIsNone(smp.marca_falla(marca, "x", avisa=False, reserva=True))
            cap = smp.marca_falla(marca, "x; API: y", avisa=False)
            self.assertIn("els veïns reben els avisos de l'AEMET", cap)
            self.assertIsNone(smp.marca_falla(marca, "x", avisa=False))
            self.assertIn("API", smp.marca_falla(marca, "x", avisa=False, reserva=True))
            self.assertIn("es tornen a llegir", smp.marca_falla(marca, None, avisa=False))
            self.assertFalse(os.path.exists(marca))
            # Una marca buida (d'abans de l'API) és «cap».
            open(marca, "w").close()
            self.assertIsNone(smp.marca_falla(marca, "x", avisa=False))


if __name__ == "__main__":
    unittest.main()
