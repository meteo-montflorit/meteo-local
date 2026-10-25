# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proves de l'estat dels trens (sense xarxa)."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
import trens as T  # noqa: E402

ARA = dt.datetime(2026, 10, 7, 7, 50).astimezone()
R7 = C.TRENS_ESTACIONS["R7"]


def camp(num, valor):
    """Un camp protobuf de longitud variable (o un enter)."""
    def varint(n):
        res = b""
        while True:
            b = n & 0x7F
            n >>= 7
            res += bytes([b | (0x80 if n else 0)])
            if not n:
                return res
    if isinstance(valor, int):
        return varint(num << 3) + varint(valor)
    if isinstance(valor, str):
        valor = valor.encode()
    return varint(num << 3 | 2) + varint(len(valor)) + valor


def traduccio(text, idioma):
    return camp(1, camp(1, text) + camp(2, idioma))


class Protobuf(unittest.TestCase):
    def test_avis_gtfs_rt(self):
        alerta = (camp(1, camp(1, 1791350000)) + camp(5, camp(2, "S2")) + camp(5, camp(2, "S1"))
                  + camp(11, traduccio("Obres a Bellaterra.", "ca") + traduccio("Obras en Bellaterra.", "es")))
        feed = camp(1, camp(1, "2.0")) + camp(2, camp(1, "a1") + camp(5, alerta))
        self.assertEqual(T.avisos_pb(feed), [{"rutes": ["S2", "S1"], "text": {
            "ca": "Obres a Bellaterra.", "es": "Obras en Bellaterra."}, "inici": T.iso(1791350000), "fi": None}])
        amb_fi = feed.replace(camp(1, camp(1, 1791350000)), camp(1, camp(1, 1791350000) + camp(2, 1791353600)))
        self.assertEqual(T.avisos_pb(amb_fi)[0]["fi"], T.iso(1791353600))
        self.assertEqual(T.iso(1791350000), "2026-10-07T05:13Z")       # en UTC (ADR 0128)
        self.assertIsNone(T.iso(None))

    def test_el_fitxer_d_fgc_amb_avisos_de_php_davant(self):
        # Des del 25-10-2026 el servidor de FGC hi posa davant els seus avisos de
        # PHP, i fins a la 3.202.0 la S2 sortia «sense dades» («tipus de camp
        # desconegut: 4»). El binari comença amb un salt de línia (camp 1).
        alerta = camp(5, camp(2, "S2")) + camp(11, traduccio("Obres a Bellaterra.", "ca"))
        feed = camp(1, camp(1, "1.0")) + camp(2, camp(1, "a1") + camp(5, alerta))
        php = (b"<br />\n<b>Warning</b>:  Undefined property: stdClass::$language in <b>/var/www/html/www/feed/"
               b"Alerts.php</b> on line <b>87</b><br />\n") * 3
        self.assertEqual(T.avisos_pb(T.sense_avisos_php(php + feed))[0]["rutes"], ["S2"])
        self.assertEqual(T.sense_avisos_php(feed), feed)

    def test_avisos_renfe_amb_inici(self):
        # Formato real de alerts.json (08-10-2026): activePeriod con start en segundos.
        dades = {"entity": [{"alert": {"activePeriod": [{"start": "1791354540"}],
                                       "informedEntity": [{"routeId": "51T0036R8"}],
                                       "descriptionText": {"translation": [
                                           {"text": "Circulació ferroviària a tot el recorregut.", "language": "es"},
                                           {"text": "Circulación ferroviaria en todo su recorrido.", "language": "es"}]}}},
                            {"alert": {"informedEntity": [{"routeId": "51T0036R8"}],
                                       "descriptionText": {"translation": [{"text": "Sense data.", "language": "es"}]}}}]}
        r = T.avisos_renfe(dades)
        self.assertEqual([a["linies"] for a in r], [{"R8"}, {"R8"}])
        self.assertEqual(r[0]["inici"], "2026-10-07T06:29Z")
        self.assertIsNone(r[0]["fi"])          # sense end: obert
        self.assertIsNone(r[1]["inici"])
        dades["entity"][0]["alert"]["activePeriod"][0]["end"] = "1791358140"
        self.assertEqual(T.avisos_renfe(dades)[0]["fi"], "2026-10-07T07:29Z")

    def test_un_avis_futur_o_acabat_no_decideix(self):
        # Auditoria del 08-10-2026: un avís de carretera per a demà posava «bus» avui.
        def avis(inici, fi):
            return {"linies": {"R8"}, "inici": inici, "fi": fi,
                    "text": {"ca": "Servei alternatiu per carretera.", "es": "Servicio alternativo por carretera."}}
        dema = (ARA + dt.timedelta(days=1)).isoformat(timespec="minutes")
        ahir = (ARA - dt.timedelta(days=1)).isoformat(timespec="minutes")
        fa_una_hora = (ARA - dt.timedelta(hours=1)).isoformat(timespec="minutes")
        mou = [{"linia": "R8", "lat": 0, "lon": 0}]
        self.assertEqual(T.estat_linia("R8", mou, None, [avis(dema, None)], ARA)["estat"], "incidencies")
        self.assertEqual(T.estat_linia("R8", mou, None, [avis(ahir, fa_una_hora)], ARA)["estat"], "incidencies")
        self.assertEqual(T.estat_linia("R8", mou, None, [avis(ahir, None)], ARA)["estat"], "bus")
        self.assertEqual(T.estat_linia("R8", mou, None, [avis(None, None)], ARA)["estat"], "bus")
        # L'avís futur es mostra igualment.
        self.assertEqual(len(T.estat_linia("R8", mou, None, [avis(dema, None)], ARA)["avisos"]), 1)

    def test_posicions_velles_no_serveixen(self):
        feed = {"header": {"timestamp": str(int((ARA - dt.timedelta(minutes=11)).timestamp()))},
                "entity": [{"vehicle": {"vehicle": {"label": "R8-1", "id": "1"}, "position": {"latitude": 41.5, "longitude": 2.1}}}]}
        with self.assertRaises(ValueError):
            T.trens_renfe(feed, ARA)
        feed["header"]["timestamp"] = str(int((ARA - dt.timedelta(minutes=2)).timestamp()))
        self.assertEqual([t["linia"] for t in T.trens_renfe(feed, ARA)], ["R8"])


class Idiomes(unittest.TestCase):
    def test_renfe_marca_els_dos_com_a_castella(self):
        r = T.idiomes(["Per causes alienes a Rodalies no es pot garantir la prestació del servei.\r\n",
                       "Por causas ajenas a Rodalies no se puede garantizar la prestación del servicio."])
        self.assertTrue(r["ca"].startswith("Per causes"))
        self.assertTrue(r["es"].startswith("Por causas"))

    def test_un_sol_idioma_es_queda_tal_qual(self):
        r = T.idiomes(["Servicio alternativo por carretera en todo su recorrido."])
        self.assertEqual(r["ca"], r["es"])

    def test_linia_renfe(self):
        self.assertEqual(T.linia_renfe("51T0037R7"), "R7")
        self.assertEqual(T.linia_renfe("51T0094R2N"), "R2N")
        self.assertIsNone(T.linia_renfe("10T0001C1"))


def tren(linia, lat, lon, aturat=False, ident="1"):
    return {"id": ident, "linia": linia, "lat": lat, "lon": lon, "aturat": aturat}


class Estat(unittest.TestCase):
    def test_aturat_a_l_estacio_no_circula(self):
        # 07-10-2026: dos trens de l'R7 «a l'estació», sense moure's.
        abans = {"hora": (ARA - dt.timedelta(minutes=15)).isoformat(), "posicions": {"1": R7}}
        self.assertEqual(T.es_mouen([tren("R7", *R7, aturat=True)], abans, ARA), [])
        # Sense passada anterior, l'aturat tampoc no compta.
        self.assertEqual(T.es_mouen([tren("R7", *R7, aturat=True)], None, ARA), [])

    def test_lluny_de_l_estacio_no_compta(self):
        # L'R4 pel tram sud (Martorell) no serveix a qui surt de Cerdanyola.
        self.assertEqual(T.es_mouen([tren("R4", 41.47, 1.93)], None, ARA), [])

    def test_es_mou(self):
        abans = {"hora": (ARA - dt.timedelta(minutes=15)).isoformat(), "posicions": {"1": (41.48, 2.12)}}
        self.assertEqual(len(T.es_mouen([tren("R7", *R7)], abans, ARA)), 1)

    def test_ha_passat_entre_dues_passades(self):
        # 13-10-2026: l'R8 (un tren per hora i sentit) era a Rubí Can
        # Vallhonrat (6,9 km) en una passada i a Santa Perpètua (6,8 km) a la
        # següent: no s'havia vist mai a menys de 6 km, però hi ha passat.
        rubi, santa_perpetua = (41.4752, 2.0371), (41.5262, 2.1863)
        abans = {"hora": (ARA - dt.timedelta(minutes=15)).isoformat(), "posicions": {"1": rubi}}
        self.assertEqual(len(T.es_mouen([tren("R8", *santa_perpetua)], abans, ARA)), 1)
        # De Martorell a Castellbisbal es mou, però lluny de Cerdanyola.
        abans["posicions"]["1"] = (41.4793, 1.9253)
        self.assertEqual(T.es_mouen([tren("R8", 41.4734, 1.9676)], abans, ARA), [])
        # Sense passada anterior, només compta el que és a prop.
        self.assertEqual(T.es_mouen([tren("R8", *santa_perpetua)], None, ARA), [])

    def test_circulacio_normalitzada(self):
        # 13-10-2026: l'R8 sortia «Sense trens» amb l'avís «Circulació normalitzada».
        ara = ARA.replace(day=13, hour=18, minute=45)
        normal = self.avis(["R8"], "Circulació normalitzada.", "Circulación normalizada.", "2026-10-13T16:47+02:00")
        normal["font"] = "rodalies"
        mou = [tren("R8", *C.TRENS_ESTACIONS["R8"])]
        self.assertEqual(T.estat_linia("R8", mou, None, [normal], ara)["estat"], "circula")
        r = T.estat_linia("R8", [], None, [normal], ara)
        self.assertEqual(r["estat"], "incidencies")
        self.assertTrue(r["no_vist"])

    def avis(self, linies, ca, es=None, inici=None):
        return {"linies": set(linies), "text": {"ca": ca, "es": es or ca}, "inici": inici}

    def test_estats(self):
        bus = self.avis(["R8"], "Servei alternatiu per carretera en tot el seu recorregut.")
        general = self.avis(["R4", "R7", "R8"], "No es pot garantir la prestació del servei.")
        mou = [tren("R7", *R7)]
        self.assertEqual(T.estat_linia("R8", [], None, [bus, general], ARA)["estat"], "bus")
        self.assertEqual(T.estat_linia("R7", mou, None, [general], ARA)["estat"], "incidencies")
        self.assertEqual(T.estat_linia("R7", mou, None, [], ARA)["estat"], "circula")
        self.assertEqual(T.estat_linia("R4", [], None, [general], ARA)["estat"], "sense_trens")
        nit = ARA.replace(hour=2)
        self.assertEqual(T.estat_linia("R4", [], None, [], nit)["estat"], "fora_horari")

    def test_avisos_de_la_web_de_rodalies(self):
        # ADR 0078: el 12-10-2026 la web de Rodalies deia «Servei ferroviari a tot el recorregut» per a
        # l'R4 (07:34) i el GTFS-RT de Renfe encara portava avisos del 6 i del 7.
        api = {"included": [{"date": "2026-10-12", "time": "07:34:00",
                             "title": {"ca": "Servei ferroviari a tot el recorregut."},
                             "description": {"ca": "Servei ferroviari a tot el recorregut.",
                                             "es": "Servicio ferroviario en todo su recorrido."},
                             "lines": [{"id": "R1"}, {"id": "R4"}, {"id": "R7"}]},
                            {"date": "2026-10-12", "time": "07:21:00", "description": {"ca": "Sense línies."}, "lines": []}]}
        a = T.avisos_rodalies(api)
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["linies"], {"R1", "R4", "R7"})
        self.assertEqual(a[0]["text"]["es"], "Servicio ferroviario en todo su recorrido.")
        self.assertEqual(a[0]["inici"], "2026-10-12T05:34Z")     # les 7:34 de Madrid
        self.assertIsNone(T.prova(lambda url: api))
        self.assertIn("llista", T.prova(lambda url: {"total": 0}))

    def test_avis_de_servei_normal_no_es_incidencia(self):
        # ADR 0078: «Servei ferroviari a tot el recorregut» diu que tot va bé.
        ara = ARA.replace(day=12, hour=8)
        normal = self.avis(["R1", "R4", "R7"], "Servei ferroviari a tot el recorregut.",
                           "Servicio ferroviario en todo su recorrido.", "2026-10-12T07:34+02:00")
        normal["font"] = "rodalies"
        mou = [tren("R4", *C.TRENS_ESTACIONS["R4"])]
        r = T.estat_linia("R4", mou, None, [normal], ara)
        self.assertEqual(r["estat"], "circula")
        self.assertEqual(r["avisos"][0]["ca"], "Servei ferroviari a tot el recorregut.")
        parcial = self.avis(["R4"], "Servei ferroviari entre Montcada i Cerdanyola.", inici="2026-10-12T07:40+02:00")
        self.assertEqual(T.estat_linia("R4", mou, None, [parcial], ara)["estat"], "incidencies")

    def test_incidencia_resolta_que_es_recupera_va_amb_retard(self):
        # Revisor, 19-10-2026: l'R4 sortia «amb incidències» amb un avís que diu que ja s'ha resolt.
        ara = ARA.replace(day=19, hour=8)
        rec = self.avis(["R4"], "Un cop resolta la incidència a la infraestructura a l'estació de Montcada Bifurcació, "
                        "els trens recuperen progressivament els seus horaris habituals de pas.", inici="2026-10-19T07:50+02:00")
        rec["font"] = "rodalies"
        mou = [tren("R4", *C.TRENS_ESTACIONS["R4"])]
        self.assertEqual(T.estat_linia("R4", mou, None, [rec], ara)["estat"], "retard")
        # Amb un altre avís obert, segueix «amb incidències».
        altre = self.avis(["R4"], "Servei ferroviari entre Montcada i Cerdanyola.", inici="2026-10-19T07:55+02:00")
        self.assertEqual(T.estat_linia("R4", mou, None, [rec, altre], ara)["estat"], "incidencies")

    def test_els_generals_de_rodalies_decideixen_i_els_de_renfe_no(self):
        ara = ARA.replace(day=12, hour=8)
        bus = self.avis(["R1", "R4", "R7"], "Servei alternatiu per carretera en tot el seu recorregut.",
                        inici="2026-10-12T07:30+02:00")
        self.assertEqual(T.estat_linia("R4", [], None, [bus], ara)["estat"], "sense_trens")      # de Renfe
        self.assertEqual(T.estat_linia("R4", [], None, [{**bus, "font": "rodalies"}], ara)["estat"], "bus")

    def test_si_rodalies_no_respon_es_fan_servir_els_de_renfe(self):
        errors = []
        orig_r, orig_f = T.avisos_rodalies, T.avisos_renfe
        try:
            T.avisos_rodalies = lambda dades=None: (_ for _ in ()).throw(OSError("caiguda"))
            T.avisos_renfe = lambda dades=None: ["de renfe"]
            self.assertEqual(T.avisos_rodalies_o_renfe(errors), ["de renfe"])
        finally:
            T.avisos_rodalies, T.avisos_renfe = orig_r, orig_f
        self.assertEqual(errors, ["avisos de Rodalies: caiguda"])

    def test_retard_de_la_s2(self):
        # ADR 0079: «amb retard» si, dels trens vistos a prop de l'estació en l'última mitja hora, van
        # tard com a mínim 2 i més que els puntuals; un sol tren no ho decideix.
        s2 = C.TRENS_ESTACIONS["S2"]
        t = lambda ident, en_hora, lat=s2[0]: {"id": ident, "linia": "S2", "lat": lat, "lon": s2[1], "en_hora": en_hora}
        r = T.puntualitat({}, [t("a", False)], ARA)
        self.assertEqual(T.amb_retard(r["S2"]), 0)                                  # un sol tren
        r = T.puntualitat(r, [t("b", False), t("c", True)], ARA + dt.timedelta(minutes=10))
        self.assertEqual(T.amb_retard(r["S2"]), 2)                                  # 2 tard, 1 puntual
        r = T.puntualitat(r, [t("d", True), t("e", True)], ARA + dt.timedelta(minutes=20))
        self.assertEqual(T.amb_retard(r["S2"]), 0)                                  # 2 tard, 3 puntuals
        # Passada la mitja hora, els vells marxen; els trens lluny de l'estació no compten.
        r = T.puntualitat(r, [t("f", False, lat=41.40)], ARA + dt.timedelta(minutes=45))
        self.assertNotIn("a", r.get("S2", {}))
        self.assertNotIn("f", r.get("S2", {}))

    def test_horari_de_cada_linia(self):
        # 08-10-2026, 05:39: «l'R7 no circula», però el primer tren és a les 06:40.
        general = self.avis(["R4", "R7", "R8"], "No es pot garantir la prestació del servei.")
        matinada = ARA.replace(hour=5, minute=39)
        self.assertEqual(T.estat_linia("R7", [], None, [general], matinada)["estat"], "fora_horari")
        self.assertEqual(T.estat_linia("R8", [], None, [], matinada)["estat"], "fora_horari")
        self.assertEqual(T.estat_linia("R4", [], None, [], matinada)["estat"], "fora_horari")   # 05:20 + 30 min
        self.assertEqual(T.estat_linia("R4", [], None, [], ARA.replace(hour=5, minute=50))["estat"], "sense_trens")
        self.assertEqual(T.estat_linia("S2", [], None, [], ARA.replace(hour=5, minute=45))["estat"], "sense_trens")
        # Mitja hora després del primer tren de l'R7 (06:35 a Cerdanyola), ja compta.
        self.assertEqual(T.estat_linia("R7", [], None, [], ARA.replace(hour=7, minute=4))["estat"], "fora_horari")
        self.assertEqual(T.estat_linia("R7", [], None, [], ARA.replace(hour=7, minute=5))["estat"], "sense_trens")
        # I després de l'últim (22:40), tampoc; l'R4 fins a mitjanit.
        self.assertEqual(T.estat_linia("R7", [], None, [], ARA.replace(hour=22, minute=50))["estat"], "fora_horari")
        self.assertEqual(T.estat_linia("R4", [], None, [], ARA.replace(hour=23, minute=50))["estat"], "sense_trens")
        # Una línia que es mou circula a qualsevol hora.
        self.assertEqual(T.estat_linia("R7", [tren("R7", *R7)], None, [], matinada)["estat"], "circula")

    def test_vist_fa_poc_circula(self):
        # Amb trens cada 30 minuts, en una passada pot no haver-n'hi cap a prop.
        fa_poc = (ARA - dt.timedelta(minutes=20)).isoformat()
        fa_molt = (ARA - dt.timedelta(minutes=C.TRENS_VIST_MIN + 5)).isoformat()
        self.assertEqual(T.estat_linia("R4", [], fa_poc, [], ARA)["estat"], "circula")
        self.assertEqual(T.estat_linia("R4", [], fa_molt, [], ARA)["estat"], "sense_trens")

    def test_l_avis_propi_va_primer(self):
        bus = self.avis(["R8"], "Servei alternatiu per carretera.")
        general = self.avis(["R4", "R8"], "No es pot garantir el servei.")
        r = T.estat_linia("R8", [], None, [general, bus, bus], ARA)
        self.assertEqual([a["ca"] for a in r["avisos"]], ["Servei alternatiu per carretera.",
                                                          "No es pot garantir el servei."])

    def test_l_avis_mes_recent_mana(self):
        # 07-10-2026, 20:21: l'R8 tenia un avís vell de servei per carretera i
        # un de nou de circulació ferroviària, i sortia «bus» (auditoria).
        vespre = ARA.replace(hour=20, minute=21)
        bus = self.avis(["R8"], "Servei alternatiu per carretera en tot el seu recorregut.", inici="2026-10-06T18:33+02:00")
        tren = self.avis(["R8"], "Circulació ferroviària a tot el recorregut.", inici="2026-10-07T09:49+02:00")
        general = self.avis(["R4", "R7", "R8"], "No es pot garantir la prestació del servei.", inici="2026-10-07T09:02+02:00")
        r = T.estat_linia("R8", [], None, [bus, general, tren], vespre)
        # Sense trens vistos, però l'avís oficial més nou diu que hi ha
        # circulació: mana ell, i es diu que no se n'ha vist cap (09-10-2026).
        self.assertEqual((r["estat"], r.get("no_vist")), ("incidencies", True))
        # De servei, només el més nou: el de carretera ja no val. Després, el general.
        self.assertEqual([a["ca"][:12] for a in r["avisos"]], ["Circulació f", "No es pot ga"])
        # Al revés (el de carretera és el nou), bus.
        bus["inici"], tren["inici"] = tren["inici"], bus["inici"]
        self.assertEqual(T.estat_linia("R8", [], None, [tren, general, bus], vespre)["estat"], "bus")
        # Un avís nou que no parla del servei (obres) no treu el bus.
        obres = self.avis(["R8"], "Obres a l'estació de Mollet.", inici="2026-10-07T12:00+02:00")
        self.assertEqual(T.estat_linia("R8", [], None, [tren, general, bus, obres], vespre)["estat"], "bus")
        # Sense dates, com abans: qualsevol avís propi de carretera.
        for a in (bus, tren, general):
            a["inici"] = None
        self.assertEqual(T.estat_linia("R8", [], None, [tren, bus], vespre)["estat"], "bus")

    def test_carretera_nomes_si_el_tram_passa_per_cerdanyola(self):
        # Revisor, 18-10-2026: l'R4 sortia «per carretera» per un bus entre Terrassa Nord i Manresa.
        ara = ARA.replace(day=18, hour=17)
        avis = self.avis(["R4"], "A causa d'incidències a la infraestructura entre Sants-P.Catalunya, i entre "
                         "Sants-El Clot, [...] els trens circulen amb demores de 30 minuts de mitjana. Servei "
                         "complementari per carretera entre Terrassa Nord-Manresa",
                         "Debido a incidencias en la infraestructura entre Sants-P. Catalunya, [...] los trenes "
                         "circulan con demoras de 30 minutos de media.Serv. complementari por carretera entre "
                         "Terrassa Nord-Manresa", inici="2026-10-18T14:33+02:00")
        avis["font"] = "rodalies"
        mou = [tren("R4", *C.TRENS_ESTACIONS["R4"])]
        self.assertEqual(T.estat_linia("R4", mou, None, [avis], ara)["estat"], "incidencies")
        self.assertFalse(T.carretera_passa("R8", "Servei per carretera entre Martorell i Rubí Can Vallhonrat."))
        # Si el tram passa per Cerdanyola, o hi acaba, sí; si no se sap on és, també.
        self.assertTrue(T.carretera_passa("R4", "Servei per carretera entre Montcada i Reixac-Manresa i Sabadell Nord."))
        self.assertTrue(T.carretera_passa("R4", "Servei per carretera entre Cerdanyola i Terrassa Est."))
        self.assertTrue(T.carretera_passa("R4", "Servei alternatiu per carretera en tot el seu recorregut."))
        self.assertTrue(T.carretera_passa("R7", "Servei per carretera entre Montcada i Reixac-Santa Maria i "
                                                "Cerdanyola-Universitat."))


if __name__ == "__main__":
    unittest.main()
