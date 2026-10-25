# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del bot de Telegram y de sus avisos (ADR 0034), sin red."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
import unittest.mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
sys.path.insert(0, os.path.join(ARREL, "bot"))
import avisos_bot as AB  # noqa: E402
import bot as B  # noqa: E402
import smp as SMP  # noqa: E402

# Les proves no escriuen mai a ~/.temps-bot: el registre d'errors i el comptador
# van a una carpeta temporal.
_BASE = tempfile.TemporaryDirectory()
B.BASE = _BASE.name
B.COMPTADOR = os.path.join(_BASE.name, "comptador.json")

ARA = dt.datetime(2026, 10, 7, 7, 0).astimezone()


class Api:
    """Telegram de mentira: apunta lo que se envía."""
    def __init__(self, bloquejats=(), al_canal=(), canal_falla=False):
        self.enviats, self.bloquejats, self.al_canal = [], set(bloquejats), set(al_canal)
        self.canal_falla = canal_falla

    def __call__(self, metode, temps=30, **p):
        if metode == "getChatMemberCount":
            return 10
        if metode == "getChatMember":       # preguntar no envía nada
            return {"status": "member" if str(p["user_id"]) in self.al_canal else "left"}
        if metode == "sendMessage" and str(p["chat_id"]) in self.bloquejats:
            raise B.Bloquejat()
        if metode == "sendMessage" and p["chat_id"] == B.CANAL and self.canal_falla:
            raise RuntimeError("canal")
        self.enviats.append((metode, p))
        return {"message_id": len(self.enviats)} if metode == "sendMessage" else {}


def dades(generat=ARA):
    hores = []
    for i in range(24):
        h = (generat + dt.timedelta(hours=i)).replace(minute=0, tzinfo=None)
        hores.append({"hora": h.isoformat(timespec="minutes"), "fins": (h + dt.timedelta(hours=1)).isoformat(timespec="minutes"),
                      "temperatura": 15 + i % 10, "probabilitat": 0.4 if 12 <= h.hour < 15 else 0.0, "pluja_mm": 0})
    return {"generat": generat.isoformat(timespec="minutes"), "ara_casa": {"temperatura": 16.2, "intensitat": 0, "plou": False},
            "hores": hores, "trens": {"linies": [{"linia": "R4", "estat": "sense_trens"}, {"linia": "S2", "estat": "circula"}]},
            "avisos": [{"inicio": "2026-10-07T12:00:00+02:00", "fin": "2026-10-07T19:59:59+02:00", "nivel": "groc",
                        "tipo": "tempestes", "zona": "Prelitoral de Barcelona"}]}


class Menu(unittest.TestCase):
    def test_alta_per_defecte_i_idioma(self):
        self.assertEqual(B.nou_subscriptor({"language_code": "es"})["idioma"], "es")
        sub = B.nou_subscriptor({})
        self.assertEqual((sub["idioma"], sub["avisos"], sub["resum"]), ("ca", ["riera", "perill"], None))

    def test_botons(self):
        sub = B.nou_subscriptor({})
        self.assertTrue(B.canvia(sub, "t:pluja"))
        self.assertTrue(B.canvia(sub, "t:riera"))
        self.assertEqual(sub["avisos"], ["perill", "pluja"])
        self.assertTrue(B.canvia(sub, "r:7"))
        self.assertTrue(B.canvia(sub, "i:es"))
        self.assertFalse(B.canvia(sub, "-"))
        self.assertEqual((sub["resum"], sub["idioma"]), ("7", "es"))
        textos = [b["text"] for fila in B.teclat(sub) for b in fila]
        self.assertIn("✓ Lluvia a punto de empezar (15 min antes)", textos)
        self.assertIn("Desbordamiento de la riera de Sant Cugat (en pruebas)", textos)
        self.assertIn("✓ 7 h", textos)
        self.assertIn("A las 21 h, la previsión de mañana", textos)
        self.assertNotIn("21 h", [x.replace("✓ ", "") for x in textos])
        # Els trens ja no són un avís: es consulten amb /trens (ADR 0053).
        self.assertFalse(any("Tren" in t for t in textos))
        self.assertFalse(B.canvia(sub, "t:trens"))

    def test_start_i_baixa(self):
        api, subs = Api(), {}
        B.atén(api, subs, {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "/start"}})
        self.assertIn("5", subs)
        self.assertIn("orientatius, no oficials", api.enviats[0][1]["text"])
        self.assertIn("inline_keyboard", api.enviats[1][1]["reply_markup"])
        B.atén(api, subs, {"callback_query": {"id": "q", "data": "t:pluja", "from": {},
                                              "message": {"chat": {"id": 5}, "message_id": 9}}})
        self.assertIn("pluja", subs["5"]["avisos"])
        estat = {"resums": {"5": "2026-10-07", "6": "2026-10-07"},
                 "pendents": {"riera:1": {"avis": {}, "canal": False, "chats": ["5", "6"]}}}
        B.atén(api, subs, {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "/baixa"}}, estat)
        self.assertNotIn("5", subs)
        # La baja borra el chat de todo el estado (auditoría del 07-10-2026).
        self.assertEqual(estat["resums"], {"6": "2026-10-07"})
        self.assertEqual(estat["pendents"]["riera:1"]["chats"], ["6"])
        self.assertEqual(json.dumps(estat).count('"5"'), 0)

    def test_moviments_del_bot(self):
        # Altes, baixes i bloquejos, amb el dia i sense el xat (ADR 0084).
        ruta = os.path.join(B.BASE, "moviments.json")
        B.desa(ruta, [])
        api, subs = Api(bloquejats=["7"]), {}
        B.atén(api, subs, {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "/start"}})
        B.atén(api, subs, {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "/baixa"}}, {})
        B.atén(api, subs, {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "/baixa"}}, {})
        subs["7"] = {"idioma": "ca", "avisos": ["perill"], "resum": None, "nit": False}
        B.treu(subs, {}, "7", "bloqueig")
        self.assertEqual([m["tipus"] for m in B.llegeix(ruta, [])], ["alta", "baixa", "bloqueig"])   # la 2a baixa no compta
        self.assertNotIn('"5"', json.dumps(B.llegeix(ruta, [])))
        self.assertTrue(all(m["canal"] == "bot" and len(m["dia"]) == 10 for m in B.llegeix(ruta, [])))

    def test_moviments_a_l_informe(self):
        # El resum dels dilluns (bot.py informe) porta les altes i baixes de la setmana (ADR 0084).
        B.desa(os.path.join(B.BASE, "moviments.json"), [])
        for dia, canal, tipus in (("2026-10-05", "web", "alta"), ("2026-10-07", "web", "alta"),
                                  ("2026-10-08", "web", "morta"), ("2026-10-09", "bot", "alta"),
                                  ("2026-10-10", "bot", "bloqueig"), ("2026-10-12", "web", "alta"),
                                  ("2026-10-04", "web", "baixa")):
            B.moviment(canal, tipus, dia=dia)
        text = B.text_moviments(dt.date(2026, 10, 12))
        self.assertEqual(text, "Últimos 7 días: avisos de la web, 2 altas, 0 bajas y "
                               "1 dirección muerta; bot, 1 alta, 0 bajas y 1 bloqueo.\n")

    def test_neteja_de_restes(self):
        estat = {"resums": {"1": "d", "9": "d"}, "pendents": {"x": {"avis": {}, "canal": False, "chats": ["1", "9"]}}}
        B.neteja({"1": {}}, estat)
        self.assertEqual(estat, {"resums": {"1": "d"}, "pendents": {"x": {"avis": {}, "canal": False, "chats": ["1"]}}})

    def test_alta_avisa_a_juanjo_sense_nom(self):
        avisos, original = [], B.avisa_juanjo
        B.avisa_juanjo = avisos.append
        try:
            subs = {}
            for _ in range(2):
                B.atén(Api(), subs, {"message": {"chat": {"id": 7, "type": "private"},
                                                 "from": {"first_name": "Maria"}, "text": "/start"}})
        finally:
            B.avisa_juanjo = original
        self.assertEqual(avisos, ["Temps a Montflorit: alta nova al bot (ja en són 1)."])

    def test_altes_i_baixes_del_canal_avisen_a_juanjo(self):
        avisos, original = [], B.avisa_juanjo
        B.avisa_juanjo = avisos.append
        canal = {"id": -100, "type": "channel", "username": "TempsMontflorit"}
        usuari = {"id": 5, "first_name": "Quela", "username": "Glamurosa"}
        def canvi(chat, abans, despres):
            return {"chat_member": {"chat": chat, "old_chat_member": {"status": abans, "user": usuari},
                                    "new_chat_member": {"status": despres, "user": usuari}}}
        try:
            B.atén(Api(), {}, canvi(canal, "left", "member"))
            B.atén(Api(), {}, canvi(canal, "member", "left"))
            B.atén(Api(), {}, canvi(canal, "member", "kicked"))
            B.atén(Api(), {}, canvi(canal, "member", "administrator"))   # ja hi era
            B.atén(Api(), {}, canvi({"id": -200, "type": "channel", "username": "Altre"}, "left", "member"))
        finally:
            B.avisa_juanjo = original
        # Sense el nom (ADR 0073).
        self.assertEqual(avisos, ["Temps a Montflorit: alta nova al canal. Ja en són 10.",
                                  "Temps a Montflorit: baixa del canal. Ja en són 10.",
                                  "Temps a Montflorit: baixa del canal. Ja en són 10."])

    def test_grups_no(self):
        api, subs = Api(), {}
        B.atén(api, subs, {"message": {"chat": {"id": -9, "type": "group"}, "text": "/start"}})
        self.assertEqual((subs, api.enviats), ({}, []))


class TextTelegram(unittest.TestCase):
    # Juanjo, 18-10-2026: «en telegram deja una linea siempre antes del enlace final».
    def test_linia_en_blanc_abans_de_l_enllac_final(self):
        avis = AB.amb_enllac({"tipus": "pluja", "ca": "🟠 Meteocat: avís\nAcumulada > 100 mm.", "es": "x"}, [])
        self.assertIn("100\u00a0mm.\n\n<a href=", B.text_telegram(avis["ca"]))
        self.assertTrue(B.text_telegram("Hola\n" + B.WEB).endswith("Hola\n\n" + B.WEB))
        self.assertTrue(B.text_telegram("Previsió de les 10:00. La de cada moment, a " + B.WEB).startswith("Previsió"))

    def test_si_ja_hi_ha_linia_en_blanc_o_no_acaba_en_enllac_no_canvia(self):
        self.assertEqual(B.text_telegram("Hola\n\n" + B.WEB), "Hola\n\n" + B.WEB)
        self.assertEqual(B.text_telegram("Hola\nAdéu"), "Hola\nAdéu")
        self.assertEqual(B.text_telegram(B.WEB), B.WEB)

    def test_tots_els_enviaments_el_fan_servir(self):
        api = Api()
        B.envia(api, "1", "Hola\n" + B.WEB)
        self.assertTrue(api.enviats[-1][1]["text"].endswith("Hola\n\n" + B.WEB))


class Resum(unittest.TestCase):
    def test_resum(self):
        r = B.resum(dades(), "ca", ARA)
        self.assertIn("Ara mateix: 16 °C, no plou.", r)
        self.assertIn("Possible pluja de 12 a 15 h (probabilitat fins al 40 %).", r)
        # Encara no ha començat (de 12 a 20 h): de quina a quina, no «fins a les 20:00» (19-10-2026).
        self.assertIn("AEMET: avís groc per tempestes al Vallès de 12:00 a 20:00.", r)
        self.assertIn("Trens de Cerdanyola: 🔴 R4 sense trens.", r)
        self.assertIn("Posible lluvia de 12 a 15 h", B.resum(dades(), "es", ARA))

    def test_ara_amb_l_estacio_particular_i_fins_a_mitjanit(self):
        # La temperatura d'ara, de l'estació particular; la pluja, de qualsevol.
        d = dades()
        d["ara_casa"] = {"temperatura": 14.6, "plou": True}
        r = B.resum(d, "ca", ARA)
        self.assertIn("Ara mateix: 15 °C, plou.", r)
        self.assertIn("Temperatura d'aquí a mitjanit: entre ", r)
        self.assertIn("Temperatura de aquí a medianoche: entre ", B.resum(d, "es", ARA))

    def test_sense_hores_no_hi_ha_previsio(self):
        # Auditoria del 08-10-2026: amb hores: null deia «Sense pluja prevista».
        for moment in (ARA, ARA.replace(hour=20)):
            d = {"generat": moment.isoformat(), "hores": None, "errors": ["previsió: caiguda"]}
            r = B.resum(d, "ca", moment)
            self.assertIn(f"Ara no hi ha previsió disponible: les dades de les {moment:%H:%M} no en porten.", r)
            self.assertNotIn("Sense pluja", r)
            self.assertIn("Ahora no hay previsión disponible", B.resum(d, "es", moment))
        # Amb hores només d'avui, a les 20 h tampoc n'hi ha de demà.
        vespre = ARA.replace(hour=20)
        d = dades(vespre)
        d["hores"] = [f for f in d["hores"] if f["hora"][:10] == vespre.date().isoformat()]
        self.assertIn("no en porten", B.resum(d, "ca", vespre))

    def test_sense_pluja_pero_amb_avis_oficial(self):
        # Revisor, 19-10-2026: «Sense pluja prevista» per a demà amb avisos de Meteocat i AEMET de 0 a 9 h.
        def fila(h, avis=None):
            return {"hora": f"2026-10-20T{h:02d}:00", "fins": f"2026-10-20T{h + 1:02d}:00", "probabilitat": 0.0,
                    "avisos": [{"nivell": "groc", "tipus": avis}] if avis else []}
        files = [fila(h, ["pluja"] if h < 6 else ["pluja", "tempestes"] if h < 9 else None) for h in range(12)]
        self.assertEqual(B.text_pluja(files[6:], "ca", avis=files),
                         "La previsió no dona pluja, però hi ha avís oficial per pluja de 0 a 9 h.")
        self.assertEqual(B.text_pluja(files[6:], "es"), "La previsión no da lluvia, pero hay aviso oficial por lluvia de 6 a 9 h.")
        self.assertEqual(B.text_pluja([fila(10, ["vent"]), fila(11)], "ca"), "Sense pluja prevista.")

    def test_graus_mes_o_menys_que_el_dia_abans(self):
        # ADR 0061: la màxima prevista d'avui contra les mateixes hores mesurades ahir.
        def fila(dia, h, t):
            return {"hora": f"2026-10-{dia}T{h:02d}:00", "fins": f"2026-10-{dia}T{h + 1:02d}:00", "temperatura": t}
        avui = [fila(10, 14, 20.0), fila(10, 15, 23.4)]
        mes = {"2026-10-09T14:00": 19.0, "2026-10-09T15:00": 20.0, "2026-10-09T16:00": 21.0}
        d = {"temperatura_mesurada": mes, "hores": avui}
        self.assertEqual(B.compara_temp(d, avui), 2)                        # 23,4 contra 20,5: es lleu 23 i 21
        self.assertEqual(B.text_comparacio(3, "ca", "ahir"), ", 3 graus més que ahir")
        self.assertEqual(B.text_comparacio(-2, "es", "avui"), ", 2 grados menos que hoy")
        self.assertEqual(B.text_comparacio(1, "ca", "ahir"), ", semblant a la d'ahir")     # menys de 2 graus
        self.assertEqual(B.text_comparacio(-1, "es", "ahir"), ", parecida a la de ayer")
        self.assertEqual(B.text_comparacio(None, "ca", "ahir"), "")
        self.assertEqual(B.text_temperatura(avui, "ca", "Temperatura", 3), "Temperatura: entre 20 °C i 23 °C, 3 graus més que ahir.")
        # Si la mínima i la màxima coincideixen, una xifra (ADR 0074: sortia «entre 16 °C i 16 °C»).
        self.assertEqual(B.text_temperatura([fila(11, 5, 16.2), fila(11, 6, 15.8)], "es", "Temperatura"), "Temperatura: 16 °C.")
        # La part alta (ADR 0087): la màxima de dalt, si es separa un grau o més, arrodonit.
        alta = [dict(f, dif_alta=1.8) for f in avui]
        self.assertEqual(B.text_temperatura(alta, "ca", "Temperatura", 3),
                         "Temperatura: entre 20 °C i 23 °C (fins a 25 °C a la part alta), 3 graus més que ahir.")
        self.assertIn("(hasta 25 °C en la parte alta)", B.text_temperatura(alta, "es", "Temperatura"))
        self.assertEqual(B.text_temperatura([dict(f, dif_alta=0.4) for f in avui], "ca", "Temperatura"),
                         "Temperatura: entre 20 °C i 23 °C.")
        # La xifra de dalt, com a les files: 18,2 + 2,4 es llegeix «18 °C» i «+2»,
        # així que 20 °C, no els 21 de la suma arrodonida (revisor, 20-10-2026).
        tarda = [fila(20, 17, 18.2), fila(20, 18, 17.0)]
        tarda = [dict(tarda[0], dif_alta=2.4), dict(tarda[1], dif_alta=1.0)]
        self.assertIn("(fins a 20 °C a la part alta)", B.text_temperatura(tarda, "ca", "Temperatura"))
        # La xifra de dalt no repeteix mai la màxima: amb 15,6 i 0,8, la fila diu
        # «16 °C» i «+1», i el resum «fins a 17» (abans, «entre 11 i 16 (fins a 16)»).
        self.assertEqual(B.text_temperatura([fila(11, 5, 11.0), dict(fila(11, 15, 15.6), dif_alta=0.8)], "es", "Temperatura"),
                         "Temperatura: entre 11 °C y 16 °C (hasta 17 °C en la parte alta).")
        # La nit compara la mínima; si falta una hora del dia abans, no es diu res.
        self.assertEqual(B.compara_temp(d, avui, nit=True), 0)              # 20 contra 19,5: es llegeix 20 i 20
        self.assertIsNone(B.compara_temp({"temperatura_mesurada": {"2026-10-09T14:00": 19.0}, "hores": avui}, avui))
        self.assertIsNone(B.compara_temp({"hores": avui}, avui))            # sense estació (la reserva)
        # Demà contra avui: les hores que encara no han passat, previstes.
        dema = [fila(11, 15, 18.0)]
        d = {"temperatura_mesurada": mes, "hores": avui + dema}
        self.assertEqual(B.compara_temp(d, dema), -5)                      # 18 contra 23,4
        # Es resten les xifres arrodonides, les de les capçaleres (revisor, 19-10-2026:
        # 15–18 avui i 14–19 demà deia «2° més»); i 18,5 és 19, com Math.round de la web.
        avui2 = [fila(19, 15, 17.6)]
        dema2 = [fila(20, 15, 19.4)]
        self.assertEqual(B.compara_temp({"temperatura_mesurada": mes, "hores": avui2 + dema2}, dema2), 1)
        # El resum travessa trams i compara com les capçaleres (revisor, 19-10-2026: a les 19 h,
        # «2 graus més» per 17 °C a les 22 h, amb Tarda i Nit «semblant»): de dia, la màxima de les
        # hores de dia; de nit, la mínima fins a les 7.
        def fila_t(t, temp):
            return {"hora": t.strftime("%Y-%m-%dT%H:%M"), "temperatura": temp,
                    "fins": (t + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")}
        t0 = dt.datetime(2026, 10, 19, 19)
        temps = [15.4, 15.8, 17.0, 17.0, 16.2] + [15.0] * 7         # de 19 a 7 h
        files = [fila_t(t0 + dt.timedelta(hours=k), v) for k, v in enumerate(temps)]
        ahir = {(t0 - dt.timedelta(days=1, hours=-k)).strftime("%Y-%m-%dT%H:%M"): (15.0 if k < 5 else 14.0)
                for k in range(13)}
        d = {"temperatura_mesurada": ahir, "hores": files}
        self.assertEqual(B.compara_temp(d, files[:5]), 2)                   # el càlcul d'abans: 17 contra 15
        self.assertEqual(B.compara_resum(d, files[:5]), 1)                  # 19–21 h: 16 contra 15
        self.assertEqual(B.compara_resum(d, files[2:5]), 1)                 # de nit, la mínima fins a les 7: 15 contra 14
        self.assertEqual(B.graus(18.5), "19 °C")
        self.assertEqual(B.graus(-2.5), "−2 °C")

    def test_ara_nomes_amb_l_estacio_del_barri(self):
        # Des de la 3.44.0 l'única estació és la particular (ADR 0058): el que marca mana.
        self.assertEqual(B.text_ara({"ara_casa": {"temperatura": 20, "plou": False}}, "es"),
                         "Ahora mismo: 20 °C, no llueve.")
        self.assertEqual(B.text_ara({"ara_casa": {"temperatura": 20, "plou": True}}, "ca"),
                         "☔ Ara mateix: 20 °C, plou.")
        self.assertIsNone(B.text_ara({"ara_casa": None}, "ca"))
        # Des de la 3.46.0 les dades porten «plou_ara», que compta les veïnes (ADR 0060).
        self.assertEqual(B.text_ara({"ara_casa": {"temperatura": 20, "plou": False}, "plou_ara": True}, "ca"),
                         "☔ Ara mateix: 20 °C, plou.")
        # Dades d'abans de la 3.44.0, amb «ara» de l'estació retirada: no es fan servir.
        self.assertIsNone(B.text_ara({"ara": {"temperatura": 20, "intensitat": 0}, "ara_casa": None}, "ca"))

    def test_avis_aemet_que_ve_d_ahir(self):
        # Auditoria del 08-10-2026: un avís començat ahir i vigent avui no sortia.
        migdia = ARA.replace(hour=12)
        ahir, dema = (migdia - dt.timedelta(days=1)).date(), (migdia + dt.timedelta(days=1)).date()
        d = {"avisos": [{"inicio": f"{ahir}T23:00:00+02:00", "fin": f"{migdia.date()}T13:59:59+02:00",
                         "nivel": "taronja", "tipo": "pluja", "zona": "Prelitoral de Barcelona"}]}
        self.assertEqual(B.text_avisos_aemet(d, "es", migdia.date(), migdia),
                         ["🟠 AEMET: aviso naranja por lluvia en el Vallès hasta las 14:00."])
        self.assertEqual(B.text_avisos_aemet(d, "ca", dema, migdia), [])
        # I el de demà que comença avui a la nit també compta per a demà.
        d = {"avisos": [{"inicio": f"{migdia.date()}T22:00:00+02:00", "fin": f"{dema}T05:59:59+02:00",
                         "nivel": "groc", "tipo": "vent", "zona": "Prelitoral de Barcelona"}]}
        self.assertEqual(B.text_avisos_aemet(d, "ca", dema, migdia), ["🟡 AEMET: avís groc per vent al Vallès de 22:00 a 06:00."])

    def test_a_les_20_la_de_dema(self):
        vespre = ARA.replace(hour=20)
        d = dades(vespre)
        d["avisos"].append({"inicio": "2026-10-08T10:00:00+02:00", "fin": "2026-10-08T19:59:59+02:00",
                            "nivel": "groc", "tipo": "pluja", "zona": "Prelitoral de Barcelona"})
        r = B.resum(d, "ca", vespre)
        self.assertTrue(r.startswith("<b>Previsió per a demà, dijous, a Montflorit</b> (fins a les 20 h)"))
        self.assertIn("Temperatura: entre ", r)
        self.assertIn("Possible pluja de 12 a 15 h (probabilitat fins al 40 %).", r)
        self.assertIn("AEMET: avís groc per pluja al Vallès de 10:00 a 20:00.", r)
        self.assertNotIn("Ara mateix", r)
        self.assertNotIn("Trens", r)
        self.assertNotIn("Aquesta nit", r)
        self.assertTrue(B.resum(d, "es", vespre).startswith("<b>Previsión para mañana, jueves, en Montflorit</b> (hasta las 20 h)"))

    def test_dema_sencer_sense_fins_a_les(self):
        # Juanjo, 09-10-2026: les dades arriben a les 21 h de demà (ADR 0041); demà és sencer i no es diu «fins a les».
        vespre = ARA.replace(hour=20)
        d = dades(vespre)
        h = dt.datetime.fromisoformat(d["hores"][-1]["fins"])
        d["hores"].append({"hora": h.isoformat(timespec="minutes"), "fins": (h + dt.timedelta(hours=1)).isoformat(timespec="minutes"),
                           "temperatura": 15, "probabilitat": 0.0, "pluja_mm": 0})
        self.assertTrue(B.resum(d, "ca", vespre).startswith("<b>Previsió per a demà, dijous, a Montflorit</b>\n"))
        self.assertTrue(B.resum(d, "es", vespre).startswith("<b>Previsión para mañana, jueves, en Montflorit</b>\n"))

    def test_radar_quan_ja_plou(self):
        # El que es mesura mana: si ja plou i el radar en veu una mica, «pluja a sobre» i quan pararia.
        d = dades()
        d["radar"] = {"hora": ARA.isoformat(timespec="minutes"), "imatge": "rainviewer", "arriba": None,
                      "possible": ARA.isoformat(timespec="minutes"), "fi": (ARA + dt.timedelta(minutes=10)).isoformat(),
                      "sense_fi": False}
        d["ara_casa"].update(intensitat=0.8, plou=True)
        self.assertTrue(B.text_radar_bot(d, "ca", ARA).startswith(
            "Pluja a sobre de Montflorit. Pararia cap a les 07:10 (en entrenament: pot fallar)."))
        self.assertTrue(B.text_radar_bot(d, "es", ARA).startswith(
            "Lluvia encima de Montflorit. Pararía hacia las 07:10 (en entrenamiento: puede fallar)."))
        d["radar"].update(possible=None, fi=None)
        self.assertTrue(B.text_radar_bot(d, "ca", ARA).startswith(
            "Pluja a sobre de Montflorit segons les estacions del barri; el radar no la veu.\n"))
        self.assertTrue(B.text_radar_bot(d, "es", ARA).startswith(
            "Lluvia encima de Montflorit según las estaciones del barrio; el radar no la ve.\n"))
        d["ara_casa"].update(intensitat=0, plou=False)
        self.assertTrue(B.text_radar_bot(d, "ca", ARA).startswith("El radar no veu pluja que vingui cap a Montflorit."))
        # Plugim que només veu el radar, com a la web (18-10-2026).
        d["pluja_ara"] = {"estat": "no", "plugim": True}
        self.assertTrue(B.text_radar_bot(d, "ca", ARA).startswith(
            "El radar veu pluja molt feble a sobre de Montflorit (plugim), que les estacions no mesuren."))
        self.assertTrue(B.text_radar_bot(d, "es", ARA).startswith(
            "El radar ve lluvia muy débil encima de Montflorit (llovizna), que las estaciones no miden."))
        d["radar"]["propera"] = {"km": 4.2, "rumb": "nord-oest", "classe": 1}
        self.assertNotIn("La més propera", B.text_radar_bot(d, "ca", ARA))
        self.assertIn("plugim segons el radar.", B.text_ara(d, "ca"))
        self.assertIn("llovizna según el radar.", B.text_ara(d, "es"))

    def test_radar_pluja_propera_i_sense_moviment(self):
        # 17-10-2026: la pluja més propera, i sense «a 0 km/h».
        d = dades()
        d["radar"] = {"hora": ARA.isoformat(timespec="minutes"), "imatge": "meteocat", "arriba": None, "possible": None,
                      "cap_a": "al sud-oest", "velocitat_kmh": 0,
                      "propera": {"km": 6.4, "rumb": "al nord-oest", "mm_h": 3, "classe": 2}}
        self.assertIn("\nLa més propera, a 6\u00a0km al nord-oest (moderada).\n", B.text_radar_bot(d, "ca", ARA))
        self.assertIn("\nLa más cercana, a 6\u00a0km al noroeste (moderada).\n", B.text_radar_bot(d, "es", ARA))
        self.assertNotIn("km/h", B.text_radar_bot(d, "ca", ARA))
        d["radar"].update(velocitat_kmh=12, propera={"km": 0.4, "rumb": "al nord", "mm_h": 3, "classe": 2})
        self.assertIn("va cap al sud-oest a 12\u00a0km/h", B.text_radar_bot(d, "ca", ARA))
        self.assertNotIn("més propera", B.text_radar_bot(d, "ca", ARA))   # a sobre, no

    def test_radar_pluja_forta_a_prop(self):
        # 17-10-2026: amb trons, deia «El radar no veu pluja que vingui cap a Montflorit».
        d = dades()
        d["radar"] = {"hora": ARA.isoformat(timespec="minutes"), "imatge": "rainviewer", "arriba": None, "possible": None,
                      "forta": {"km": 10.2, "rumb": "al nord", "classe": 4},
                      "propera": {"km": 6.4, "rumb": "al nord-est", "mm_h": 0.6, "classe": 1}}
        ca = B.text_radar_bot(d, "ca", ARA)
        self.assertTrue(ca.startswith("Pluja molt forta a 10\u00a0km al nord, que de moment no ve cap a Montflorit.\n"
                                      "La més propera, a 6\u00a0km al nord-est (feble)."))
        self.assertTrue(B.text_radar_bot(d, "es", ARA).startswith(
            "Lluvia muy fuerte a 10\u00a0km al norte, que de momento no viene hacia Montflorit."))
        # La pluja que creix al voltant, com a la web.
        d["radar"]["creixement"] = {"creix": True, "km2": 216, "km2_abans": 113, "pct": 31, "pct_abans": 16}
        self.assertIn("\nLa pluja s'està formant a prop: ja ocupa el 31\u00a0% del terreny a 15\u00a0km o menys; "
                      "fa mitja hora, el 16\u00a0%.", B.text_radar_bot(d, "ca", ARA))
        self.assertIn("\nLa lluvia se está formando cerca: ya ocupa el 31\u00a0% del terreno a 15\u00a0km o menos; "
                      "hace media hora, el 16\u00a0%.", B.text_radar_bot(d, "es", ARA))
        # Si la més propera és la mateixa, no es repeteix.
        d["radar"]["propera"] = {"km": 10.4, "rumb": "al nord", "mm_h": 35, "classe": 4}
        self.assertNotIn("més propera", B.text_radar_bot(d, "ca", ARA))

    def test_pluja_aquesta_nit(self):
        # El 08-10-2026 deia «Esta noche: posible de 20 a 23 h»: hi faltava la pluja.
        vespre = ARA.replace(hour=20)
        d = dades(vespre)
        for f in d["hores"][:3]:
            f["probabilitat"] = 0.56
        self.assertIn("Aquesta nit: pluja de 20 a 23 h (probabilitat fins al 56 %).", B.resum(d, "ca", vespre))
        self.assertIn("Esta noche: lluvia de 20 a 23 h (probabilidad hasta el 56 %).", B.resum(d, "es", vespre))

    def test_roba_de_tot_el_dia(self):
        # Les dades de prova van de 15 °C (7 h) a 24 °C (16 h): dues peces, per ordre d'hora.
        self.assertIn("Roba per anar a peu: a les 7 h (15 °C), jaqueta lleugera o jersei; "
                      "a les 16 h (24 °C), màniga curta o màniga llarga fina.", B.resum(dades(), "ca", ARA))
        self.assertIn("Ropa para ir a pie: a las 7 h (15 °C), chaqueta ligera o jersey; "
                      "a las 16 h (24 °C), manga corta o manga larga fina.", B.resum(dades(), "es", ARA))

    def test_la_roba_al_final_i_apart(self):
        # Juanjo, 08-10-2026: la ropa, al final y separada del resto.
        for moment in (ARA, ARA.replace(hour=20)):
            for idioma in ("ca", "es"):
                linies = B.resum(dades(moment), idioma, moment).split("\n")
                self.assertEqual(linies[-1], B.WEB)
                self.assertTrue(linies[-2].startswith(("Roba per anar a peu", "Ropa para ir a pie")))
                self.assertEqual(linies[-3], "")
                self.assertNotIn("", linies[:-3])

    def test_roba_amb_vent_i_una_sola_peca(self):
        hora = lambda h, t, v=0: {"hora": f"2026-10-08T{h:02d}:00", "temperatura": t, "vent": v}
        # 8 °C amb 30 km/h es noten com 4 °C; fora de les 7-21 h no compta.
        self.assertEqual(B.text_roba([hora(5, -2), hora(9, 8, 30), hora(14, 9)], "ca"),
                         "Roba per anar a peu: a les 9 h (8 °C, es noten com 4 °C), abric, bufanda i guants; "
                         "a les 14 h (9 °C), abric.")
        self.assertEqual(B.text_roba([hora(9, 26), hora(14, 30)], "es"), "Ropa para ir a pie: manga corta.")
        self.assertIsNone(B.text_roba([hora(23, 12)], "ca"))

    def test_milimetres_sense_probabilitat_no_compten(self):
        d = dades()
        for f in d["hores"]:
            f.update(probabilitat=0.17, pluja_mm=0.4)
        self.assertIn("Sense pluja prevista.", B.resum(d, "ca", ARA))

    def test_dades_velles(self):
        r = B.resum(dades(ARA - dt.timedelta(hours=3)), "ca", ARA)
        self.assertIn("no s'actualitzen des de les", r)

    def test_ara_amb_el_mateix_limit_i_l_hora_de_la_mesura(self):
        # Auditoría del 07-10-2026: /ara contestaba con medidas de hace horas.
        d = dades()
        d["ara_casa"]["hora"] = (ARA - dt.timedelta(minutes=9)).isoformat(timespec="minutes")
        self.assertTrue(B.text_ara_bot(d, "ca", ARA).startswith("<b>Ara a Montflorit</b> (mesura de les 06:51)\n"))
        self.assertTrue(B.text_ara_bot(d, "es", ARA).startswith("<b>Ahora en Montflorit</b> (medida de las 06:51)\n"))
        self.assertIn("16 °C, no plou.", B.text_ara_bot(d, "ca", ARA))
        vell = dades(ARA - dt.timedelta(hours=3))
        self.assertIn("ara no puc dir el temps que fa", B.text_ara_bot(vell, "ca", ARA))
        self.assertIn("ahora no puedo decir el tiempo que hace", B.text_ara_bot(vell, "es", ARA))
        # Medida congelada con un generat reciente: tampoco.
        d["ara_casa"]["hora"] = (ARA - dt.timedelta(hours=5)).isoformat(timespec="minutes")
        self.assertIn("des de les 02:00", B.text_ara_bot(d, "ca", ARA))
        self.assertEqual(B.text_ara_bot({}, "ca", ARA), B.T["ca"]["velles_ara"].format("?"))


class Repartiment(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        B.DADES = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def escriu(self, avisos, dades_=None):
        with open(os.path.join(self.dir.name, "avisos.json"), "w") as f:
            json.dump({"avisos": avisos}, f)
        with open(os.path.join(self.dir.name, "montflorit.json"), "w") as f:
            json.dump(dades_ or dades(), f)

    def test_correccio_del_revisor(self):
        # ADR 0101: el revisor deixa la correcció a avisos.json i el bot edita
        # els missatges ja enviats, al canal i a cada xat, en el seu idioma;
        # una sola vegada, i no passades les 48 hores de Telegram.
        hora = ARA.isoformat(timespec="minutes")
        avis = {"id": "perill:1", "tipus": "perill", "hora": hora, "ca": "Mal ca", "es": "Mal es"}
        self.escriu([avis])
        subs = {"1": {"idioma": "ca", "avisos": ["perill"], "resum": None},
                "2": {"idioma": "es", "avisos": ["perill"], "resum": None}}
        api, estat = Api(), {}
        B.reparteix(api, subs, estat, ARA)
        self.assertEqual(len(estat["missatges"]["perill:1"]), 3)          # el canal i els dos xats
        with open(os.path.join(self.dir.name, "avisos.json"), "w") as f:
            json.dump({"avisos": [avis], "correccions": [{"id": "perill:1", "hora": hora, "ca": "Bé ca",
                                                          "es": "Bien es"}]}, f)
        api.enviats.clear()
        B.corregeix(api, estat, ARA + dt.timedelta(minutes=5))
        edits = sorted((p["chat_id"], p["text"]) for m, p in api.enviats if m == "editMessageText")
        self.assertEqual(edits, sorted([(B.CANAL, "Bé ca"), ("1", "Bé ca"), ("2", "Bien es")]))
        api.enviats.clear()
        B.corregeix(api, estat, ARA + dt.timedelta(minutes=6))
        self.assertEqual(api.enviats, [])                                  # una sola vegada
        estat["corregits"].clear()
        B.corregeix(api, estat, ARA + dt.timedelta(hours=48))
        self.assertEqual(api.enviats, [])                                  # massa tard per a Telegram

    def test_cadascu_el_que_tria_i_canal(self):
        hora = ARA.isoformat(timespec="minutes")
        self.escriu([{"id": "riera:1", "tipus": "riera", "hora": hora, "ca": "R ca", "es": "R es"},
                     {"id": "pluja:1", "tipus": "pluja", "hora": hora, "ca": "P ca", "es": "P es"}])
        subs = {"1": {"idioma": "ca", "avisos": ["riera"], "resum": None},
                "2": {"idioma": "es", "avisos": ["riera", "pluja"], "resum": None},
                "3": {"idioma": "ca", "avisos": ["pluja"], "resum": None}}
        api, estat = Api(bloquejats=["3"]), {}
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=30))   # la lluvia ya no vale
        enviats = [(p["chat_id"], p["text"]) for _, p in api.enviats]
        self.assertIn(("1", "R ca"), enviats)
        self.assertIn(("2", "R es"), enviats)
        self.assertIn((B.CANAL, "R ca"), enviats)            # el canal, solo en catalán
        self.assertNotIn(("2", "P es"), enviats)
        # Una sola vez.
        api.enviats.clear()
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=31))
        self.assertEqual(api.enviats, [])

    def test_bloquejat_es_dona_de_baixa(self):
        self.escriu([{"id": "pluja:1", "tipus": "pluja", "hora": ARA.isoformat(), "ca": "P", "es": "P"}])
        subs = {"3": {"idioma": "ca", "avisos": ["pluja"], "resum": None}}
        B.reparteix(Api(bloquejats=["3"]), subs, {}, ARA)
        self.assertEqual(subs, {})

    def test_resum_a_l_hora_i_canal(self):
        self.escriu([])
        subs = {"1": {"idioma": "ca", "avisos": [], "resum": "7"}, "2": {"idioma": "ca", "avisos": [], "resum": "8"}}
        api, estat = Api(), {}
        B.reparteix(api, subs, estat, ARA)
        destins = [p["chat_id"] for _, p in api.enviats]
        self.assertEqual(sorted(map(str, destins)), sorted(["1", B.CANAL]))
        canal = [p["text"] for _, p in api.enviats if p["chat_id"] == B.CANAL][0]
        self.assertEqual(canal.count(B.WEB), 1)
        self.assertTrue(canal.startswith("<b>Avui, "))
        self.assertNotIn("<b>Hoy, ", canal)              # el canal, solo en catalán
        api.enviats.clear()
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=20))
        self.assertEqual(api.enviats, [])


    def test_qui_es_al_canal_no_ho_rep_dos_cops(self):
        hora = ARA.isoformat(timespec="minutes")
        self.escriu([{"id": "riera:1", "tipus": "riera", "hora": hora, "ca": "R ca", "es": "R es"},
                     {"id": "pluja:1", "tipus": "pluja", "hora": hora, "ca": "P ca", "es": "P es"}])
        subs = {"1": {"idioma": "ca", "avisos": ["riera", "pluja"], "resum": "7"},
                "2": {"idioma": "ca", "avisos": ["riera"], "resum": "7"}}
        api = Api(al_canal=["1"])
        B.reparteix(api, subs, {}, ARA)
        enviats = [(str(p["chat_id"]), p["text"]) for _, p in api.enviats]
        self.assertNotIn(("1", "R ca"), enviats)       # la riera ja li arriba pel canal
        self.assertIn(("1", "P ca"), enviats)          # la pluja, el canal no la dona
        self.assertIn(("2", "R ca"), enviats)          # no és al canal
        destins = [d for d, _ in enviats]
        self.assertEqual(destins.count("1"), 1)        # sense la previsió de les 7
        self.assertEqual(destins.count("2"), 2)

    def test_qui_te_el_bot_en_castella_tampoc_ho_rep_dos_cops(self):
        # El canal va en catalán, pero tampoco se repite a quien lee en castellano (Juanjo, 08-10-2026).
        self.escriu([{"id": "riera:1", "tipus": "riera", "hora": ARA.isoformat(), "ca": "R ca", "es": "R es"},
                     {"id": "pluja:1", "tipus": "pluja", "hora": ARA.isoformat(), "ca": "P ca", "es": "P es"}])
        subs = {"1": {"idioma": "es", "avisos": ["riera", "pluja"], "resum": "7"}}
        api = Api(al_canal=["1"])
        B.reparteix(api, subs, {}, ARA)
        rebut = [p["text"] for _, p in api.enviats if str(p["chat_id"]) == "1"]
        self.assertEqual(rebut, ["P es"])      # la pluja sí; la riera i el resum, pel canal

    def test_si_el_canal_falla_el_bot_ho_envia(self):
        self.escriu([{"id": "riera:1", "tipus": "riera", "hora": ARA.isoformat(), "ca": "R ca", "es": "R es"}])
        subs = {"1": {"idioma": "ca", "avisos": ["riera"], "resum": "7"}}
        api = Api(al_canal=["1"], canal_falla=True)
        B.reparteix(api, subs, {}, ARA)
        self.assertEqual([(str(p["chat_id"]), p["text"][:4]) for _, p in api.enviats],
                         [("1", "R ca"), ("1", "<b>A")])

    def test_la_benvinguda_diu_que_ja_hi_ha_marcat(self):
        subs, api = {}, Api()
        missatge = {"message": {"chat": {"id": 9, "type": "private"}, "from": {"language_code": "ca"}, "text": "/start"}}
        B.atén(api, subs, missatge)
        self.assertTrue(api.enviats[-1][1]["text"].startswith("Per començar, t'he activat"))
        self.assertEqual(B.PER_DEFECTE, ["riera", "perill"])    # el que diu el text
        api.enviats.clear()
        B.atén(api, subs, missatge)                               # qui ja hi era: sense la frase
        self.assertTrue(api.enviats[-1][1]["text"].startswith("Toca el que vulguis"))

    def test_el_menu_explica_el_canal(self):
        for idioma in ("ca", "es"):
            self.assertIn("@TempsMontflorit)", B.T[idioma]["menu"])


class Consultes(unittest.TestCase):
    """/dema, /radar, /trens i /avisos_actius (Juanjo, 08-10-2026): només llegeixen,
    i la llista de subscriptors queda igual."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        B.DADES = self.dir.name
        d = dades()
        d["radar"] = {"hora": ARA.isoformat(timespec="minutes"), "imatge": "rainviewer", "cap_a": "a l'est",
                      "velocitat_kmh": 37, "arriba": None, "possible": None}
        d["plans"] = [{"pla": "INUNCAT", "nom": "d'inundacions", "fase": "emergència", "comunicat": None}]
        d["trens"] = {"linies": [{"linia": "R4", "estacio": "Cerdanyola del Vallès", "estat": "incidencies",
                                  "avisos": [{"ca": "Obres <a Montcada>.", "es": "Obras en Montcada."}]},
                                 {"linia": "S2", "estacio": "Bellaterra", "estat": "circula", "avisos": []}]}
        with open(os.path.join(self.dir.name, "montflorit.json"), "w") as f:
            json.dump(d, f)

    def tearDown(self):
        self.dir.cleanup()

    def ordre(self, text, subs, chat=7, idioma="ca"):
        api = Api()
        missatge = {"message": {"chat": {"id": chat, "type": "private"}, "from": {"language_code": idioma}, "text": text}}
        with unittest.mock.patch.object(B, "ara", return_value=ARA):
            B.atén(api, subs, missatge)
        return api.enviats[-1][1]["text"]

    def test_busos(self):
        """/busos (ADR 0120): com «Consultes › Busos» de la web."""
        subs = {"7": {"idioma": "ca", "avisos": [], "resum": None}}
        ara_n = ARA.astimezone(B.ZONA).replace(tzinfo=None)
        h = lambda minuts: (ara_n + dt.timedelta(minutes=minuts)).isoformat(timespec="minutes")  # noqa: E731
        d = json.load(open(os.path.join(self.dir.name, "montflorit.json")))
        d["busos"] = {"temps_real_de": h(-2), "incidencies": [
            {"linies": ["CV1"], "titol": {"ca": "Desviament <provisional>", "es": "Desvío"}, "url": {"ca": "https://amb/a"},
             "inici": h(-3000), "fi": (ara_n + dt.timedelta(days=1)).replace(hour=23, minute=59).isoformat(timespec="minutes")},
            {"linies": ["CV1"], "titol": {"ca": "Ja acabada"}, "url": {}, "inici": h(-300), "fi": h(-10)}],
            "linies": [{"linia": "CV1", "nom": "Canaletes – Flor de Maig", "horari": "https://amb/cv1.pdf", "sentits": [
                {"cap_a": "Flor de Maig", "parades": [{"parada": "Pl. de les Banderes", "hores": [h(-5), h(10), h(40), h(70)]}]},
                {"cap_a": "Canaletes", "parades": [{"parada": "Canaletes", "hores": [h(60 * 30)]}]}]}]}
        json.dump(d, open(os.path.join(self.dir.name, "montflorit.json"), "w"))
        t = self.ordre("/busos", subs)
        self.assertTrue(t.startswith("<b>Busos de Montflorit</b>\n\n<b>CV1</b> Canaletes – Flor de Maig\n"))
        # Les dues hores següents de les 2 hores vinents; la que ja ha passat, no.
        hm = lambda minuts: f"{(ara_n + dt.timedelta(minutes=minuts)).hour}:{(ara_n + dt.timedelta(minutes=minuts)).minute:02d}"  # noqa: E731
        self.assertIn(f"• Pl. de les Banderes: {hm(10)} i {hm(40)}\n", t)
        # Sense cap en 2 hores: la propera, amb el dia si no és avui.
        dema = ara_n + dt.timedelta(minutes=60 * 30)
        self.assertIn(f"• Canaletes: {B.DIES['ca'][dema.weekday()]} {dema.day} a les {hm(60 * 30)}", t)
        self.assertIn('⚠️ <a href="https://amb/a">Desviament &lt;provisional&gt;</a>, fins al ', t)
        self.assertNotIn("Ja acabada", t)
        self.assertIn("Horari complet (PDF)", t)
        self.assertIn(f"amb dades de l'AMB de les {(ara_n - dt.timedelta(minutes=2)):%H:%M}.", t)
        subs["7"]["idioma"] = "es"
        t = self.ordre("/busos", subs)
        self.assertIn(f"• Pl. de les Banderes: {hm(10)} y {hm(40)}\n", t)
        self.assertIn("→ Hacia Canaletes", t)
        # Sense dades dels busos.
        d["busos"] = None
        json.dump(d, open(os.path.join(self.dir.name, "montflorit.json"), "w"))
        self.assertIn("Ahora no hay datos de los autobuses.", self.ordre("/busos", subs))

    def test_les_consultes_no_toquen_ningu(self):
        subs = {"1": {"idioma": "ca", "avisos": ["riera"], "resum": "7", "alta": "x"},
                "7": {"idioma": "es", "avisos": ["perill", "pluja"], "resum": "20", "alta": "y"}}
        abans = json.dumps(subs, sort_keys=True)
        for o in ("/dema", "/radar", "/trens", "/busos", "/avisos_actius", "/ara", "/resum", "/ajuda", "/xyz"):
            self.ordre(o, subs, chat=7, idioma="es")
        self.assertEqual(json.dumps(subs, sort_keys=True), abans)

    def test_respostes(self):
        subs = {"7": {"idioma": "ca", "avisos": [], "resum": None}}
        self.assertIn("El radar no veu pluja que vingui cap a Montflorit.", self.ordre("/radar", subs))
        self.assertIn("https://www.rainviewer.com/map.html", self.ordre("/radar", subs))
        trens = self.ordre("/trens", subs)
        # Cada línia una sola vegada, amb el seu avís al costat i el text de l'operador escapat.
        self.assertIn("<b>R4</b> (Cerdanyola del Vallès): amb incidències. «Obres &lt;a Montcada&gt;.»", trens)
        self.assertEqual(trens.count("R4"), 1)
        self.assertIn("<b>S2</b> (Bellaterra): sense incidències\n", trens)
        self.assertIn("<b>Protecció Civil</b>\n🔴 Pla d'inundacions (INUNCAT) en fase d'emergència.", self.ordre("/avisos_actius", subs))
        self.assertTrue(self.ordre("/dema", subs).startswith("<b>Previsió per a demà"))
        # /resum, sempre la d'avui, també de vespre; el resum programat de les 20 h, la de demà.
        with unittest.mock.patch.object(B, "ara", return_value=ARA.replace(hour=20)):
            d = json.load(open(os.path.join(self.dir.name, "montflorit.json")))
            d["generat"] = ARA.replace(hour=20).isoformat()
            json.dump(d, open(os.path.join(self.dir.name, "montflorit.json"), "w"))
            api = Api()
            B.atén(api, subs, {"message": {"chat": {"id": 7, "type": "private"}, "from": {}, "text": "/resum"}})
        self.assertTrue(api.enviats[-1][1]["text"].startswith("<b>Avui, "))
        self.assertTrue(B.resum(d, "ca", ARA.replace(hour=20)).startswith("<b>Previsió per a demà"))
        subs["7"]["idioma"] = "es"
        self.assertIn("en fase de emergencia", self.ordre("/avisos_actius", subs))
        # El temps excepcional calculat també hi surt, dit que no és oficial.
        d = json.load(open(os.path.join(self.dir.name, "montflorit.json")))
        d["riscos"] = [{"tipus": "ratxa", "nivell": "groc", "origen": "mesura", "valor": 75, "llindar": 70,
                        "unitat": "km/h", "text": "Ara bufa vent molt fort: ratxes de 75 km/h."}]
        json.dump(d, open(os.path.join(self.dir.name, "montflorit.json"), "w"))
        r = self.ordre("/avisos_actius", subs)
        self.assertIn("<b>Tiempo excepcional en Montflorit</b>\n<i>Lo calcula Temps a Montflorit", r)
        subs["7"]["idioma"] = "ca"
        self.assertIn("Ara bufa vent molt fort: ratxes de 75\u00a0km/h.", self.ordre("/avisos_actius", subs))
        subs["7"]["idioma"] = "es"
        self.assertIn("va hacia el este", self.ordre("/radar", subs))

    def test_entorn_a_avisos_actius(self):
        # Incendis a prop i Pla Alfa des del 3 (ADR 0046).
        d = json.load(open(os.path.join(self.dir.name, "montflorit.json")))
        d["entorn"] = {"incendis": [{"id": "x", "municipi": "Sant Cugat del Vallès", "km": 3.2,
                                     "inici": ARA.isoformat()}],
                       "pla_alfa": {"avui": 4, "dema": 2, "tancaments": []}}
        json.dump(d, open(os.path.join(self.dir.name, "montflorit.json"), "w"))
        subs = {"7": {"idioma": "ca", "avisos": [], "resum": None}}
        r = self.ordre("/avisos_actius", subs)
        self.assertIn("<b>Bombers</b>\n🔥 Bombers: incendi forestal a Sant Cugat del Vallès, a 3,2 km de Montflorit", r)
        self.assertIn("<b>Pla Alfa</b>\n🔴 Nivell 4 avui a Cerdanyola", r)
        self.assertNotIn("nivell 2", r)
        self.assertNotIn("Avisos actius", r)             # sense títol: l'ordre ja diu què és
        self.assertNotIn("de l'AEMET per", r)          # l'AEMET ja és el títol del bloc
        self.assertIn("\n\n<b>", r)                     # un bloc per font
        subs["7"]["idioma"] = "es"
        self.assertIn("<b>Plan Alfa</b>\n🔴 Nivel 4 hoy en Cerdanyola", self.ordre("/avisos_actius", subs))

    def test_transit(self):
        # /transit: les incidències de la fitxa del cotxe, amb els textos del SCT (ADR 0053).
        d = json.load(open(os.path.join(self.dir.name, "montflorit.json")))
        d["transit"] = {"hora": ARA.isoformat(), "incidencies": [
            {"id": "t1", "tipus": "retencio", "nivell": 3, "carretera": "C-58", "municipi": "Barcelona",
             "sentit": "Sentit Sud cap a NUS TRINITAT", "causa": "Circulació", "descripcio": "Circulació amb retencions",
             "pk": "0-1,5", "km": 4.04},
            {"id": "t2", "tipus": "obres", "nivell": 2, "carretera": "BV-1414", "municipi": "Cerdanyola del Vallès",
             "sentit": "Sentit Sud cap a C-58", "causa": "Reasfaltat", "descripcio": "Calçada restringida",
             "pk": "4-0", "km": 0.73}]}
        json.dump(d, open(os.path.join(self.dir.name, "montflorit.json"), "w"))
        subs = {"7": {"idioma": "ca", "avisos": [], "resum": None}}
        r = self.ordre("/transit", subs)
        self.assertIn("<b>Trànsit a menys de 5\u00a0km de Montflorit</b>\n<b>C-58</b> (Barcelona, a 4\u00a0km): Circulació amb retencions. "
                      "Sentit Sud cap a NUS TRINITAT, km 0-1,5.", r)
        self.assertIn("<b>BV-1414</b> (Cerdanyola del Vallès, a 750\u00a0m): Calçada restringida. Obres: Reasfaltat, "
                      "Sentit Sud cap a C-58, km 4-0.", r)
        self.assertIn("Servei Català de Trànsit", r)
        subs["7"]["idioma"] = "es"
        r = self.ordre("/transit", subs)
        self.assertIn("<b>Tráfico a menos de 5\u00a0km de Montflorit</b>", r)
        self.assertIn("Obras: Reasfaltat", r)
        d["transit"]["incidencies"] = []
        json.dump(d, open(os.path.join(self.dir.name, "montflorit.json"), "w"))
        self.assertIn("Ninguna incidencia a menos de 5\u00a0km de Montflorit.", self.ordre("/transit", subs))
        # Ja no surten a /avisos_actius: no són una situació de perill.
        self.assertNotIn("Carreter", self.ordre("/avisos_actius", subs))

    def test_els_5_km_dels_textos_son_els_de_config(self):
        # Juanjo, 10-10-2026: cal dir de quina zona és el trànsit. Si canvia el radi, canvien els textos.
        import config as C
        self.assertEqual(C.TRANSIT_RADI_KM, 5)

    def test_distancia(self):
        self.assertEqual([B.distancia(x) for x in (0.01, 0.73, 0.98, 1.0, 4.04, 4.35, 4.96)],
                         ["50\u00a0m", "750\u00a0m", "1000\u00a0m", "1\u00a0km", "4\u00a0km", "4,4\u00a0km", "5\u00a0km"])

    def test_el_canal_a_les_7_i_a_les_21(self):
        api, estat = Api(), {"canal_resum": "2026-10-01"}          # estat d'abans
        B.reparteix(api, {}, estat, ARA.replace(hour=21, minute=0))
        self.assertEqual(estat["canal_resums"], {"7": "2026-10-01", "21": ARA.date().isoformat()})
        self.assertEqual([p["chat_id"] for m, p in api.enviats if m == "sendMessage"], [B.CANAL])

    def test_avisos_oficials_nous(self):
        # ADR 0055: AEMET en aparèixer o pujar de nivell; Protecció Civil en
        # passar a alerta o emergència i en sortir-ne. La primera vegada, només s'apunta.
        aemet = {"zona": "Prelitoral de Barcelona", "tipo": "pluja", "nivel": "groc",
                 "inicio": "2026-10-07T15:00:00+02:00", "fin": "2026-10-07T23:59:59+02:00"}
        pla = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "prealerta"}
        estat = {}
        perill = lambda sal, m: [a for a in AB.decideix(estat, sal, ARA + dt.timedelta(minutes=m)) if a["tipus"] == "perill"]
        self.assertEqual(perill({"avisos": [], "plans": [pla]}, 0), [])
        nous = perill({"avisos": [aemet], "plans": [pla]}, 6)
        self.assertEqual(nous[0]["ca"].splitlines()[0], "🟡 <b>AEMET: avís groc per pluja al Vallès</b>")
        self.assertEqual(perill({"avisos": [aemet], "plans": [pla]}, 12), [])          # una sola vegada
        nous = perill({"avisos": [dict(aemet, nivel="taronja")], "plans": [dict(pla, fase="alerta")]}, 18)
        self.assertEqual([a["nivell"] for a in nous], ["taronja", "pc"])
        self.assertIn("en fase d'alerta", nous[1]["ca"])
        self.assertEqual(perill({"avisos": None, "plans": None}, 24), [])              # font caiguda: res
        fi = perill({"avisos": [], "plans": [dict(pla, fase="prealerta")]}, 30)
        self.assertEqual(fi[0]["ca"].splitlines()[0], "🟢 <b>Protecció Civil: el pla d'inundacions (INUNCAT) ja no està en alerta</b>")

    def test_un_comunicat_nou_s_avisa_una_vegada(self):
        # L'INUNCAT del 15-10-2026: alerta a les 19:09 sense comunicat, el PDF a les
        # 19:43. Cada PDF diferent de l'últim avisat, un avís que porta a la fitxa
        # sense canviar-la; no si la font no el porta una pasada, ni en prealerta.
        pla = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "prealerta", "comunicat": None}
        pdf = "https://documents.dadesobertes.gencat.cat/cecat/docs/I-1.pdf"
        estat = {}
        perill = lambda p, m: [a for a in AB.decideix(estat, {"avisos": [], "plans": [p]}, ARA + dt.timedelta(minutes=m))
                               if a["tipus"] == "perill"]
        self.assertEqual(perill(pla, 0), [])
        self.assertEqual(perill(dict(pla, comunicat=pdf), 6), [])                       # prealerta: res
        alerta = dict(pla, fase="alerta")
        self.assertEqual(len(perill(alerta, 12)), 1)                                   # l'alerta
        nous = perill(dict(alerta, comunicat=pdf), 18)
        self.assertEqual(nous[0]["ca"].splitlines()[0],
                         "🟠 <b>Protecció Civil: actualització del pla d'inundacions (INUNCAT)</b>")
        self.assertIn(f'<a href="{pdf}">Comunicat (PDF)</a>', nous[0]["ca"])
        self.assertIn(f'<a href="{pdf}">Comunicado (PDF)</a>', nous[0]["es"])
        self.assertEqual(len(nous[0]["ca"].splitlines()), 2)                            # breu
        self.assertTrue(nous[0]["nomes_avis"])
        # A la notificació, en tocar-la, el PDF.
        self.assertEqual((nous[0]["url"], nous[0]["push"]["ca"].splitlines()[1]), (pdf, "Toca per veure el comunicat."))
        self.assertEqual(perill(dict(alerta, comunicat=pdf), 24), [])                  # el mateix: res
        self.assertEqual(perill(alerta, 30), [])                                       # sense: res
        self.assertEqual(perill(dict(alerta, comunicat=pdf), 36), [])                  # torna el mateix: res
        self.assertEqual(len(perill(dict(alerta, comunicat=pdf.replace("1", "2")), 42)), 1)
        # Un estat d'abans, sense la clau, el dona per avisat.
        del estat["oficials"]["plans"]["INUNCAT"]["comunicat"]
        self.assertEqual(perill(dict(alerta, comunicat=pdf.replace("1", "3")), 48), [])

    def test_un_pla_ocult_no_s_acaba_ni_torna_a_comencar(self):
        # ADR 0062: amagar-lo per falta de motiu meteorològic no és un final; si torna a
        # sortir en la mateixa fase no és nou; si es desactiva mentre és amagat, no es diu.
        pla = {"pla": "INUNCAT", "nom": "d'inundacions", "fase": "alerta"}
        estat = {}
        perill = lambda sal, m: [a for a in AB.decideix(estat, sal, ARA + dt.timedelta(minutes=m)) if a["tipus"] == "perill"]
        self.assertEqual(perill({"avisos": [], "plans": [pla], "plans_ocults": []}, 0), [])      # s'apunta
        self.assertEqual(perill({"avisos": [], "plans": [], "plans_ocults": [pla]}, 6), [])      # s'amaga: res
        self.assertEqual(perill({"avisos": [], "plans": [pla], "plans_ocults": []}, 12), [])     # torna: res
        self.assertEqual(perill({"avisos": [], "plans": [], "plans_ocults": [pla]}, 18), [])
        self.assertEqual(perill({"avisos": [], "plans": [], "plans_ocults": []}, 24), [])        # desactivat amagat
        # Un que puja de fase mentre era amagat sí que s'anuncia.
        self.assertEqual(perill({"avisos": [], "plans": [], "plans_ocults": [pla]}, 30), [])
        nous = perill({"avisos": [], "plans": [dict(pla, fase="emergència")], "plans_ocults": []}, 36)
        self.assertIn("emergència", nous[0]["ca"])
        # «/avisos_actius» no diu que no hi ha cap pla, perquè n'hi ha un d'activat.
        d = {"generat": ARA.isoformat(timespec="minutes"), "plans": [], "plans_ocults": [pla], "avisos": []}
        self.assertEqual(B.text_avisos_actius(d, "ca", ARA), "No hi ha avisos de l'AEMET ni es preveu temps excepcional.")

    def test_mati_i_nit(self):
        # Una hora al matí i, a part, la de demà a les 21 h (Juanjo, 09-10-2026).
        sub = B.nou_subscriptor({})
        self.assertTrue(B.canvia(sub, "r:8"))
        self.assertTrue(B.canvia(sub, "n:"))
        self.assertEqual((sub["resum"], sub["nit"]), ("8", True))
        self.assertTrue(B.canvia(sub, "n:"))
        self.assertFalse(sub["nit"])
        self.assertFalse(B.canvia(sub, "r:21"))         # el 21 ja no és una hora del matí
        api = Api()
        subs = {"1": {"idioma": "ca", "avisos": [], "resum": "8", "nit": True}}
        estat = {"canal_resums": {"7": ARA.date().isoformat(), "21": ARA.date().isoformat()}}
        for h in (8, 21):
            B.reparteix(api, subs, estat, ARA.replace(hour=h, minute=1))
        enviats = [p["chat_id"] for m, p in api.enviats if m == "sendMessage"]
        self.assertEqual(enviats.count("1"), 2)                 # matí i nit, el mateix dia
        self.assertEqual(set(estat["resums"]["1"]), {"8", "21"})

    def test_migracio_del_9_d_octubre(self):
        # ADR 0053: les 20 h passen a les 21 h, i a qui tenia els trens se li diu una sola vegada.
        api = Api()
        subs = {"1": {"idioma": "ca", "avisos": ["perill", "trens"], "resum": "20"},
                "2": {"idioma": "es", "avisos": ["riera"], "resum": "7"}}
        B.migra(api, subs, {})
        # La de la nit va a part: qui la tenia, la conserva (ADR 0055).
        self.assertEqual(subs["1"], {"idioma": "ca", "avisos": ["perill"], "resum": None, "nit": True})
        self.assertEqual(subs["2"]["resum"], "7")
        self.assertEqual([(m, p["chat_id"]) for m, p in api.enviats], [("sendMessage", "1")])
        self.assertIn("amb /trens", api.enviats[0][1]["text"])
        B.migra(api, subs, {})
        self.assertEqual(len(api.enviats), 1)

    def test_el_menu_cap_en_una_linia(self):
        # «Situacions de perill», curt (Juanjo, 08-10-2026: amb el parèntesi no hi cabia).
        self.assertEqual(B.T["ca"]["perill"], "Situacions de perill")
        self.assertEqual(B.T["es"]["perill"], "Situaciones de peligro")

    def test_dades_velles(self):
        subs = {"7": {"idioma": "ca", "avisos": [], "resum": None}}
        with unittest.mock.patch.object(B, "ara", return_value=ARA + dt.timedelta(hours=3)):
            api = Api()
            B.atén(api, subs, {"message": {"chat": {"id": 7, "type": "private"}, "from": {}, "text": "/trens"}})
        self.assertIn("no s'actualitzen", api.enviats[-1][1]["text"])


class Comptador(unittest.TestCase):
    """Comptador anònim de les ordres (Juanjo, 08-10-2026): sense qui, sense Juanjo."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.abans = B.COMPTADOR
        B.COMPTADOR = os.path.join(self.dir.name, "comptador.json")

    def tearDown(self):
        B.COMPTADOR = self.abans
        self.dir.cleanup()

    def test_compta_sense_qui_i_sense_juanjo(self):
        with unittest.mock.patch.object(B, "chat_juanjo", return_value="99"):
            for ordre, chat in (("/resum", "1"), ("/resum", "2"), ("/trens", "1"), ("/resum", "99"), ("/hola", "3")):
                B.compta(ordre, chat, dia="2026-10-08")
        c = json.load(open(B.COMPTADOR))
        self.assertEqual(c, {"2026-10-08": {"/resum": 2, "/trens": 1, "altres": 1}})
        self.assertNotIn("1", json.dumps(c).replace('"/resum": 2', "").replace('"/trens": 1', "").replace("2026-10-08", "").replace('"altres": 1', ""))
        text = B.text_estadistiques(avui=dt.date(2026, 10, 8))
        self.assertIn("Últims 7 dies: 4 (/resum 2, /trens 1, altres 1)", text)

    def test_estadistiques_nomes_per_a_juanjo(self):
        B.compta("/ara", "1", dia=ARA.date().isoformat())
        with unittest.mock.patch.object(B, "chat_juanjo", return_value="99"), \
                unittest.mock.patch.object(B, "ara", return_value=ARA):
            api = Api()
            B.atén(api, {"99": {"idioma": "es", "avisos": [], "resum": None}},
                   {"message": {"chat": {"id": 99, "type": "private"}, "from": {}, "text": "/estadistiques"}})
            self.assertTrue(api.enviats[-1][1]["text"].startswith("Usos del bot"))
            api = Api()
            B.atén(api, {"5": {"idioma": "es", "avisos": [], "resum": None}},
                   {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "/estadistiques"}})
            self.assertFalse(api.enviats[-1][1]["text"].startswith("Usos del bot"))


class AvisosPublics(unittest.TestCase):
    def test_riera_avis_i_final(self):
        # Atenció una vegada i, 3 hores després de calmar-se, el missatge de final (Juanjo, 08-10-2026).
        def riera(index):
            return {"fins": ARA.isoformat(timespec="minutes"), "mm_3h": index, "mm_6h": index + 20,
                    "radar_1h": 0, "index": index, "index_6h": index + 20}
        estat, nous = {}, []
        for i, index in enumerate([38, 30, 10, 5, 5, 5, 5, 5, 5]):
            nous += AB.decideix(estat, {"riera": riera(index)}, ARA + dt.timedelta(minutes=30 * i))
        self.assertEqual([(a["nivell"], a["id"].split(":")[-1]) for a in nous], [("atencio", "atencio"), ("fi", "fi")])
        self.assertTrue(nous[0]["ca"].startswith("🟠 <b>Temps a Montflorit: possible desbordament"))
        self.assertTrue(nous[1]["ca"].startswith("🟢 <b>Temps a Montflorit: ja no hi ha risc de desbordament de la riera de Sant Cugat</b>"))
        self.assertIn("ya no hay riesgo de desbordamiento", nous[1]["es"])
        self.assertIn("Fa 3 hores que no plou fort a Sant Cugat", nous[1]["ca"])   # curt, sense la nota (ADR 0076)
        self.assertEqual(nous[0]["tipus"], nous[1]["tipus"], "riera")

    def test_trens_ja_no_avisen(self):
        # ADR 0053: els trens es consulten amb /trens; l'estat vell es treu.
        estat = {"trens": {"R7": {"avisat": "va", "candidat": None}}, "talls": {}}
        linia = {"linies": [{"linia": "R7", "estacio": "Cerdanyola Universitat", "estat": "sense_trens"}]}
        for m in (0, 15, 30):
            self.assertEqual(AB.decideix(estat, {"trens": linia}, ARA + dt.timedelta(minutes=m)), [])
        self.assertNotIn("trens", estat)
        self.assertNotIn("talls", estat)

    def test_riera_amb_avis_orientatiu(self):
        estat = {}
        riera = {"fins": ARA.isoformat(), "mm_3h": 52, "mm_6h": 70, "radar_1h": 3.0, "index": 55, "index_6h": 75,
                 "capcalera": None}
        nous = AB.decideix(estat, {"riera": riera}, ARA)
        self.assertEqual(nous[0]["nivell"], "perill")
        self.assertTrue(nous[0]["ca"].startswith("🔴 <b>Temps a Montflorit: perill de desbordament de la riera de Sant Cugat</b>"))
        self.assertIn("Aviso en pruebas, orientativo y no oficial", nous[0]["es"])
        self.assertEqual(AB.decideix(estat, {"riera": riera}, ARA + dt.timedelta(minutes=15)), [])

    def test_perill_en_castella(self):
        r = {"clau": "previsio:ratxa", "tipus": "ratxa", "origen": "previsio", "nivell": "groc", "valor": 75,
             "des_de": "2026-10-07T15:00+02:00", "fins": "2026-10-07T16:00+02:00",
             "text": "Vent fort previst: ratxes de fins a 75 km/h, avui de 15 a 16 h."}
        nous = AB.decideix({}, {"riscos": [r]}, ARA)
        self.assertIn("Viento fuerte previsto: rachas de hasta 75 km/h, hoy de 15 a 16 h.", nous[0]["es"])
        self.assertTrue(nous[0]["es"].startswith("🟡 <b>Temps a Montflorit: aviso de peligro por viento fuerte en el barrio</b>"))

    def test_pluja_amb_el_radar(self):
        # El radar en directe que ha donat l'avís: enllaç a Telegram; a la
        # notificació, en tocar-la (Juanjo, 08-10-2026).
        def salida(imatge, arriba="2026-10-07T07:15+02:00"):
            return {"radar": {"imatge": imatge, "hora": "2026-10-07T07:00+02:00", "arriba": arriba,
                              "arriba_mm_h": 5}}
        with unittest.mock.patch.object(AB.PA, "falta_min", return_value=12):
            t = AB.text_pluja(salida("rainviewer"), ARA)
        self.assertEqual(t["url"], AB.C.RADAR_EN_DIRECTE["rainviewer"])
        self.assertTrue(t["ca"].endswith(f'Radar en directe: <a href="{AB.html.escape(t["url"])}">RainViewer</a>'))
        # 5 mm/h: moderada, com al radar (franges de l'AEMET, 18-10-2026).
        self.assertIn("Será moderada.\nRadar en directo:", t["es"])
        self.assertTrue(t["push"]["ca"].endswith("Serà moderada. Toca per veure el radar."))
        self.assertNotIn("<a ", t["push"]["es"])
        with unittest.mock.patch.object(AB.PA, "falta_min", return_value=1):
            t = AB.text_pluja(salida("meteocat"), ARA)
        self.assertEqual(t["url"], "https://www.meteo.cat/observacions/radar")
        self.assertIn("Temps a Montflorit: pluja imminent", t["ca"])

    def test_el_radar_en_directe_igual_a_tot_arreu(self):
        casa_js = open(os.path.join(ARREL, "web", "casa.js"), encoding="utf-8").read()
        for font, url in AB.C.RADAR_EN_DIRECTE.items():
            self.assertEqual(B.RADAR_EN_DIRECTE[font], url)
            self.assertIn(f"{font}: '{url}'", casa_js)

    def test_una_sola_escala_de_colors(self):
        # ADR 0065: els avisos i les consultes del bot fan servir els mateixos cercles.
        for n in ("groc", "taronja", "vermell"):
            self.assertEqual(AB.CERCLE[n], B.CERCLE_AVIS[n])
        for f in ("alerta", "emergència"):
            self.assertEqual(AB.CERCLE[f], B.CERCLE_FASE[f])
        self.assertEqual(AB.CERCLE["fi"], B.CERCLE["baix"])
        # La pluja que arriba no porta cercle: el títol ja ho diu.
        self.assertTrue(AB.negreta("Pluja imminent a Montflorit").startswith("<b>"))

    def test_la_icona_de_la_pluja_es_la_de_l_hora_pitjor(self):
        fila = lambda h, p, mm, codi: {"hora": f"2026-10-10T{h:02d}:00", "fins": f"2026-10-10T{h + 1:02d}:00",
                                       "probabilitat": p, "pluja_mm": mm, "codi": codi, "nuvols": 90}
        self.assertIsNone(B.emoji_pluja([fila(12, 0.1, 0, 3)]))
        self.assertEqual(B.emoji_pluja([fila(12, 0.3, 0.5, 61)]), "🌦️")              # possible, de dia
        self.assertEqual(B.emoji_pluja([fila(12, 0.3, 0.5, 61), fila(13, 0.7, 3, 61)]), "🌧️")
        self.assertEqual(B.emoji_pluja([fila(12, 0.7, 3, 61), fila(13, 0.6, 5, 95)]), "⛈️")
        self.assertEqual(B.text_pluja([fila(12, 0.1, 0, 3)], "ca"), "Sense pluja prevista.")
        self.assertTrue(B.text_pluja([fila(12, 0.6, 5, 95)], "es").startswith("⛈️ Lluvia de 12 a 13 h"))
        # «Pluja» des del 50 %, «possible pluja» des del 20 %, com la columna «Cel» de la web (ADR 0076).
        self.assertEqual(B.text_pluja([fila(12, 0.3, 1, 61), fila(13, 0.1, 0, 3), fila(14, 0.95, 5, 61)], "ca", icona=False),
                         "Possible pluja de 12 a 13 h (probabilitat fins al 30 %); pluja de 14 a 15 h (fins al 95 %).")

    def test_perill_acabat(self):
        # Quan ja no en queda cap, un avís que ho diu (abans només el rebia Juanjo).
        r = {"clau": "previsio:ratxa", "tipus": "ratxa", "origen": "previsio", "nivell": "groc", "valor": 75,
             "text": "Vent molt fort previst."}
        dades = {"hores": [{}], "ara_casa": {"temperatura": 18}}
        estat = {}
        AB.decideix(estat, {**dades, "riscos": [r]}, ARA)
        self.assertEqual(AB.decideix(estat, dades, ARA + dt.timedelta(hours=1)), [])
        fi = AB.decideix(estat, dades, ARA + dt.timedelta(hours=3))
        self.assertEqual([(a["tipus"], a["nivell"]) for a in fi], [("perill", "fi")])
        # Un que s'havia quedat obert de fa dies es tanca sense avisar.
        estat2 = {}
        AB.decideix(estat2, {**dades, "riscos": [r]}, ARA)
        self.assertEqual(AB.decideix(estat2, dades, ARA + dt.timedelta(days=2)), [])
        self.assertEqual(estat2["perill"], {})
        self.assertTrue(fi[0]["ca"].startswith("🟢 <b>Temps a Montflorit: s'acaba l'avís per vent fort al barri</b>"))
        self.assertIn(f"des de les {ARA:%H:%M}", fi[0]["ca"])
        self.assertNotIn("avisos oficials", fi[0]["ca"])
        self.assertEqual(AB.decideix(estat, dades, ARA + dt.timedelta(hours=4)), [])
        # Sense previsió no es pot saber: no es dona per acabat.
        estat = {}
        AB.decideix(estat, {**dades, "riscos": [r]}, ARA)
        self.assertEqual(AB.decideix(estat, {}, ARA + dt.timedelta(hours=3)), [])



class Registre(unittest.TestCase):
    """Los fallos de Telegram dejan rastro y un aviso que caduca sin
    entregarse se dice (auditoría del 07-10-2026)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        B.DADES = B.BASE = self.dir.name
        self.avisos, self.original = [], B.avisa_juanjo
        B.avisa_juanjo = self.avisos.append

    def tearDown(self):
        B.avisa_juanjo = self.original
        self.dir.cleanup()

    def registre(self):
        try:
            with open(os.path.join(self.dir.name, "errors.log")) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def test_un_avis_que_caduca_queda_apuntat_i_avisa(self):
        ara = ARA.replace(hour=10)
        with open(os.path.join(self.dir.name, "avisos.json"), "w") as f:
            json.dump({"avisos": [{"id": "riera:1", "tipus": "riera", "hora": ara.isoformat(timespec="minutes"),
                                   "ca": "R ca", "es": "R es"}]}, f)
        with open(os.path.join(self.dir.name, "montflorit.json"), "w") as f:
            json.dump(dades(), f)
        subs = {"1": {"idioma": "ca", "avisos": ["riera"], "resum": None}}
        api, estat = Api(canal_falla=True), {}
        api.falla_tot = True

        class Tot(Api):
            def __call__(self, metode, temps=30, **p):
                if metode == "sendMessage":
                    raise RuntimeError("Too Many Requests")
                return super().__call__(metode, temps, **p)
        api = Tot()
        B.reparteix(api, subs, estat, ara + dt.timedelta(minutes=1))
        self.assertIn("el canal no lo acepta: Too Many Requests", self.registre())
        self.assertIn("1 chat(s) sin entregar: Too Many Requests", self.registre())
        self.assertNotIn('"1"', self.registre())      # sin identificadores
        self.assertEqual(self.avisos, [])
        B.reparteix(api, subs, estat, ara + dt.timedelta(hours=4))
        self.assertIn("aviso riera:1 caducado sin entregar a el canal y 1 chat(s)", self.registre())
        self.assertEqual(len(self.avisos), 1)
        self.assertIn("ha caducado sin llegar", self.avisos[0])
        self.assertEqual(estat["pendents"], {})
        # Un aviso de lluvia caducado deja rastro, pero no molesta a Juanjo.
        with open(os.path.join(self.dir.name, "avisos.json"), "w") as f:
            json.dump({"avisos": [{"id": "pluja:1", "tipus": "pluja", "hora": ara.isoformat(timespec="minutes"),
                                   "ca": "P", "es": "P"}]}, f)
        subs = {"1": {"idioma": "ca", "avisos": ["pluja"], "resum": None}}
        B.reparteix(api, subs, estat, ara + dt.timedelta(minutes=5))
        B.reparteix(api, subs, estat, ara + dt.timedelta(minutes=40))
        self.assertIn("aviso pluja:1 caducado", self.registre())
        self.assertEqual(len(self.avisos), 1)


class RepartimentAmbReintents(unittest.TestCase):
    """Un fallo pasajero de Telegram no pierde ningún aviso (ADR 0034)."""

    class ApiQueFalla(Api):
        def __init__(self, falla_chats=(), **kw):
            super().__init__(**kw)
            self.falla_chats = set(falla_chats)

        def __call__(self, metode, temps=30, **p):
            if metode == "sendMessage" and str(p["chat_id"]) in self.falla_chats:
                self.falla_chats.discard(str(p["chat_id"]))      # falla una sola vez
                raise RuntimeError("Telegram")
            return super().__call__(metode, temps, **p)

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        B.DADES = self.dir.name
        with open(os.path.join(self.dir.name, "avisos.json"), "w") as f:
            json.dump({"avisos": [{"id": "riera:1", "tipus": "riera", "hora": ARA.isoformat(timespec="minutes"),
                                   "ca": "R ca", "es": "R es"}]}, f)
        with open(os.path.join(self.dir.name, "montflorit.json"), "w") as f:
            json.dump(dades(), f)

    def tearDown(self):
        self.dir.cleanup()

    def test_qui_treu_la_categoria_no_rep_el_pendent(self):
        # Auditoría del 09-10-2026: lo mismo que en las notificaciones web.
        subs = {"2": {"idioma": "es", "avisos": ["riera"], "resum": None}}
        api, estat = self.ApiQueFalla(falla_chats=["2"]), {}
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=10))
        self.assertEqual(estat["pendents"]["riera:1"]["chats"], ["2"])
        subs["2"]["avisos"] = []
        api = Api()
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=11))
        self.assertEqual([p["chat_id"] for _, p in api.enviats if p["chat_id"] != B.CANAL], [])
        self.assertEqual(estat["pendents"], {})

    def test_un_chat_que_falla_ho_rep_al_minut_seguent(self):
        subs = {"1": {"idioma": "ca", "avisos": ["riera"], "resum": None},
                "2": {"idioma": "es", "avisos": ["riera"], "resum": None}}
        api, estat = self.ApiQueFalla(falla_chats=["2"]), {}
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=10))
        enviats = [(str(p["chat_id"]), p["text"]) for _, p in api.enviats]
        self.assertIn(("1", "R ca"), enviats)
        self.assertNotIn(("2", "R es"), enviats)
        self.assertEqual(estat["pendents"]["riera:1"]["chats"], ["2"])
        api.enviats.clear()
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=11))
        self.assertEqual([(str(p["chat_id"]), p["text"]) for _, p in api.enviats], [("2", "R es")])
        self.assertEqual(estat["pendents"], {})
        api.enviats.clear()
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=12))
        self.assertEqual(api.enviats, [])

    def test_el_canal_que_falla_es_reintenta_i_despres_es_deixa_estar(self):
        subs = {"1": {"idioma": "ca", "avisos": ["riera"], "resum": None}}
        api, estat = Api(canal_falla=True), {}
        # Fora de les 7, perquè el resum del canal no es barregi amb l'avís.
        ara = ARA.replace(hour=10)
        with open(os.path.join(self.dir.name, "avisos.json"), "w") as f:
            json.dump({"avisos": [{"id": "riera:1", "tipus": "riera", "hora": ara.isoformat(timespec="minutes"),
                                   "ca": "R ca", "es": "R es"}]}, f)
        B.reparteix(api, subs, estat, ara + dt.timedelta(minutes=10))
        self.assertEqual([str(p["chat_id"]) for _, p in api.enviats], ["1"])   # el bot no espera el canal
        self.assertTrue(estat["pendents"]["riera:1"]["canal"])
        api.canal_falla = False
        api.enviats.clear()
        B.reparteix(api, subs, estat, ara + dt.timedelta(minutes=11))
        self.assertEqual([(p["chat_id"], p["text"]) for _, p in api.enviats], [(B.CANAL, "R ca")])
        self.assertEqual(estat["pendents"], {})
        # Si el aviso caduca antes de que el canal responda, se deja de intentar.
        api, estat = Api(canal_falla=True), {}
        B.reparteix(api, subs, estat, ara + dt.timedelta(minutes=10))
        B.reparteix(api, subs, estat, ara + dt.timedelta(days=1))
        self.assertEqual(estat["pendents"], {})

    def test_el_resum_del_canal_es_reintenta_dins_de_la_mateixa_hora(self):
        subs = {}
        api, estat = Api(canal_falla=True), {}
        B.reparteix(api, subs, estat, ARA)
        self.assertNotIn("7", estat["canal_resums"])
        api.canal_falla = False
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=1))
        self.assertEqual(estat["canal_resums"]["7"], ARA.date().isoformat())
        api.enviats.clear()
        B.reparteix(api, subs, estat, ARA + dt.timedelta(minutes=2))
        self.assertEqual(api.enviats, [])

    def test_trens_sense_dades_no_son_sense_incidencies(self):
        d = dades()
        d["trens"]["linies"] = [{"linia": "R4", "estat": "sense_dades"}, {"linia": "S2", "estat": "sense_dades"}]
        self.assertIn("Trens de Cerdanyola: ara mateix no hi ha dades de Renfe ni d'FGC.", B.resum(d, "ca", ARA))
        self.assertIn("ahora mismo no hay datos de Renfe ni de FGC.", B.resum(d, "es", ARA))
        d["trens"]["linies"] = [{"linia": "R4", "estat": "sense_dades"}, {"linia": "S2", "estat": "circula"}]
        self.assertIn("Trens de Cerdanyola: ⚪ R4 sense dades.", B.resum(d, "ca", ARA))


class AltesIRiscos(unittest.TestCase):
    def test_un_text_qualsevol_no_dona_d_alta(self):
        api, subs = Api(), {}
        B.atén(api, subs, {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "hola"}})
        self.assertEqual(subs, {})
        self.assertEqual(len(api.enviats), 1)       # només l'ajuda
        B.atén(api, subs, {"message": {"chat": {"id": 5, "type": "private"}, "from": {}, "text": "/start"}})
        self.assertIn("5", subs)

    def test_un_risc_no_caduca_mentre_falten_dades(self):
        r = {"clau": "previsio:ratxa", "tipus": "ratxa", "origen": "previsio", "nivell": "groc", "valor": 75,
             "des_de": "2026-10-07T15:00+02:00", "fins": "2026-10-07T16:00+02:00",
             "text": "Vent fort previst: ratxes de fins a 75 km/h, avui de 15 a 16 h."}
        complet = {"riscos": [r], "hores": [{}], "ara_casa": {"temperatura": 1}}
        estat = {}
        self.assertEqual(len(AB.decideix(estat, complet, ARA)), 1)
        # Sense previsió ni estació durant hores: el risc segueix apuntat i no es repeteix en tornar.
        AB.decideix(estat, {"riscos": [], "hores": None, "ara_casa": None}, ARA + dt.timedelta(hours=5))
        self.assertIn("previsio:ratxa", estat["perill"])
        self.assertEqual(AB.decideix(estat, complet, ARA + dt.timedelta(hours=6)), [])
        # Amb dades i sense veure'l 3 hores, caduca i es tornaria a avisar.
        AB.decideix(estat, {"riscos": [], "hores": [{}], "ara_casa": {"temperatura": 1}}, ARA + dt.timedelta(hours=10))
        self.assertNotIn("previsio:ratxa", estat["perill"])


ARA_R = dt.datetime(2026, 10, 19, 13, 9).astimezone()


class FitxesDelRevisor(unittest.TestCase):
    """Revisor, 19 i 20-10-2026 (ADR 0101): fitxes d'avisos que es contradeien."""

    def test_final_del_propi_amb_oficials_oberts(self):
        # Revisor, 19-10-2026 18:22: «ja no hi ha cap situació de perill al barri» amb INUNCAT,
        # Meteocat i AEMET oberts, i «Fa 3 hores» sense dir des de quan.
        r = {"clau": "previsio:ratxa", "tipus": "ratxa", "origen": "previsio", "nivell": "groc", "valor": 77,
             "text": "Vent fort previst: ratxes de fins a 77 km/h, avui de 17 a 18 h."}
        dades = {"hores": [{}], "ara_casa": {"temperatura": 18},
                 "avisos": [{"zona": "Prelitoral de Barcelona", "tipo": "tempestes", "nivel": "groc",
                             "inicio": "2026-10-19T19:00:00+02:00", "fin": "2026-10-20T08:59:59+02:00"}],
                 "plans": [{"pla": "INUNCAT", "nom": "inundacions", "fase": "alerta"}]}
        estat = {}
        AB.decideix(estat, {**dades, "riscos": [r]}, ARA_R)
        AB.decideix(estat, {**dades, "riscos": [r]}, ARA_R + dt.timedelta(hours=2, minutes=12))   # 15:21
        fi = [a for a in AB.decideix(estat, dades, ARA_R + dt.timedelta(hours=5, minutes=12)) if a["nivell"] == "fi"]
        self.assertEqual(len(fi), 1)
        self.assertNotIn("cap situació", fi[0]["ca"])
        self.assertIn("vent fort", fi[0]["ca"])
        self.assertIn("des de les 15:21", fi[0]["ca"])
        self.assertIn("Continuen els avisos oficials de l'AEMET i Protecció Civil.", fi[0]["ca"])
        self.assertIn("Siguen los avisos oficiales de la AEMET y Protección Civil.", fi[0]["es"])
        self.assertNotIn("perill_tipus", estat)

    def test_la_fitxa_propia_diu_que_la_xifra_ha_canviat(self):
        # Revisor, 20-10-2026 03:10: l'avís de les 13:09 deia 77 km/h i la fitxa, 89, sense dir-ho.
        r = {"clau": "previsio:ratxa", "tipus": "ratxa", "origen": "previsio", "nivell": "groc", "valor": 77,
             "text": "Vent fort previst: ratxes de fins a 77 km/h, avui de 17 a 18 h."}
        dades = {"hores": [{}], "ara_casa": {"temperatura": 18}}
        estat = {}
        nous = AB.decideix(estat, {**dades, "riscos": [r]}, ARA_R)
        self.assertNotIn("Ha pujat", nous[0]["ca"])
        self.assertNotIn("Ha pujat", estat["perill_text"]["ca"])
        r89 = dict(r, valor=89, text=r["text"].replace("77", "89"))
        self.assertEqual(AB.decideix(estat, {**dades, "riscos": [r89]}, ARA_R + dt.timedelta(hours=1)), [])  # mateix nivell
        self.assertIn("Ha pujat des de l'avís de les 13:09, que deia 77 km/h.", estat["perill_text"]["ca"])
        self.assertIn("Ha subido desde el aviso de las 13:09, que decía 77 km/h.", estat["perill_text"]["es"])
        # Amb la mateixa xifra arrodonida, res.
        AB.decideix(estat, {**dades, "riscos": [dict(r, valor=77.4)]}, ARA_R + dt.timedelta(hours=1, minutes=30))
        self.assertNotIn("Ha ", estat["perill_text"]["ca"].split("\n")[2] if len(estat["perill_text"]["ca"].split("\n")) > 2 else "")

    def test_l_aemet_substituit_per_un_que_comenca_mes_tard(self):
        # Revisor, 19-10-2026 19:28: el de tempestes de 16 h a 8:59 (allargat) canviat a les 19:27
        # per un de 19 h a 8:59 es tancava amb «L'AEMET l'ha retirat abans d'hora».
        ara = dt.datetime.fromisoformat("2026-10-19T19:27:00+02:00")
        vell, nou = "aemet:tempestes:2026-10-19T16:00:00+02:00", "aemet:tempestes:2026-10-19T19:00:00+02:00"
        fitxa = lambda k, inici: {"clau": k, "tipus": "perill", "inici": inici, "nivell": "groc", "ca": "x", "es": "x",
                                  "fins": "2026-10-20T08:59:59+02:00"}
        estat = {"historial": [fitxa(vell, "2026-10-18T00:15+02:00"), fitxa(nou, "2026-10-19T19:27+02:00")],
                 "aemet_vigents": {nou: {"fin": "2026-10-20T08:59:59+02:00", "cobert": False}}}
        h = {e["clau"]: e for e in AB.historial(estat, [], ara)}
        self.assertEqual(h[vell]["fi_ca"], AB.INCLOS["ca"])
        self.assertEqual(h[vell]["substituit_per"], {"clau": nou, "inici": "2026-10-19T19:27+02:00"})
        # Un altre fenomen, o un que no arriba a cobrir el que en queda, continua essent retirat.
        estat = {"historial": [fitxa(vell, "2026-10-18T00:15+02:00")],
                 "aemet_vigents": {"aemet:tempestes:2026-10-19T21:00:00+02:00": {"fin": "2026-10-20T08:59:59+02:00",
                                                                                 "cobert": False}}}
        self.assertEqual(AB.historial(estat, [], ara)[0]["fi_ca"], AB.RETIRAT["ca"])

    def test_meteocat_retirat_queda_en_pausa(self):
        # Revisor, 20-10-2026: retirat l'avís de 5 a 6 h, la fitxa seguia «Actiu ara» la mitja hora de relleu.
        a = {"meteor": "Intensitat de pluja en 30 minuts", "tipus": "previsio", "llindar": None, "perill": 3,
             "emissio": "2026-10-19T16:35Z", "dies": {"2026-10-20": [(5, 6)]}}
        t1 = dt.datetime.fromisoformat("2026-10-20T05:10:00+02:00")
        estat = {}
        AB.decideix(estat, {"smp": {"avisos": [a]}}, t1)
        AB.decideix(estat, {"smp": {"avisos": [a]}}, t1 + dt.timedelta(minutes=5))
        self.assertNotIn("pausa", estat["oficials"]["smp"])
        AB.decideix(estat, {"smp": {"avisos": []}}, t1 + dt.timedelta(minutes=15))
        import hora as HR
        self.assertEqual(HR.utc(estat["oficials"]["smp"]["pausa"]), HR.utc("2026-10-20T05:15+02:00"))

    def test_dos_avisos_de_l_aemet_amb_la_mateixa_clau(self):
        # Revisor, 19-10-2026 19:58: pluja de 40 mm/1 h (19-23:59, la cobreix Meteocat) i de 80 mm/12 h
        # (19-8:59, visible de 6 a 9) amb la mateixa clau: guanyava el darrer i la fitxa es tancava
        # com a «Substituït per l'avís de Meteocat».
        base = {"zona": "Prelitoral de Barcelona", "tipo": "pluja", "nivel": "groc", "inicio": "2026-10-19T19:00:00+02:00"}
        a40 = dict(base, fin="2026-10-19T23:59:59+02:00", descripcio="40 mm")
        a80 = dict(base, fin="2026-10-20T08:59:59+02:00", descripcio="80 mm")
        mc = [{"meteor": "Intensitat de pluja en 30 minuts", "tipus": "previsio", "llindar": None, "perill": 4,
               "emissio": "2026-10-19T16:35Z", "dies": {"2026-10-19": [(12, 24)], "2026-10-20": [(0, 6)]}}]
        k = "aemet:pluja:2026-10-19T19:00:00+02:00"
        for ordre in ([a40, a80], [a80, a40]):
            avisos = [dict(a) for a in ordre]
            SMP.marca_coberts(avisos, {"avisos": mc})
            estat = {"oficials": {"aemet": {}, "plans": {}}}
            AB.decideix(estat, {"avisos": avisos}, dt.datetime.fromisoformat("2026-10-19T19:57:00+02:00"))
            self.assertEqual(estat["aemet_coberts"], [])
            self.assertEqual(estat["aemet_vigents"][k], {"fin": "2026-10-20T08:59:59+02:00", "cobert": False,
                                                        "comenca": "2026-10-20T06:00:00+02:00"})


if __name__ == "__main__":
    unittest.main()


class GraficaDelResum(unittest.TestCase):
    """ADR 0098: el resum amb la gràfica a dalt, si la imatge és recent."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.dir))
        B.FOTOS.clear()

    def imatge(self, nom, fa_min):
        ruta = os.path.join(self.dir, nom)
        open(ruta, "wb").write(b"\x89PNG\r\n\x1a\n")
        t = ARA.timestamp() - fa_min * 60
        os.utime(ruta, (t, t))

    def test_la_imatge_del_dia_que_toca_i_recent(self):
        self.imatge("grafica-avui-ca.png", 10)
        self.imatge("grafica-dema-es.png", 10)
        self.assertTrue(B.imatge_resum("ca", ARA, dades=self.dir).startswith(B.URL_DADES + "grafica-avui-ca.png?v="))
        # De vespre, la de demà, com el text; /resum, sempre la d'avui.
        vespre = ARA.replace(hour=21)
        self.imatge("grafica-dema-es.png", -14 * 60 + 10)
        self.assertIn("grafica-dema-es.png", B.imatge_resum("es", vespre, dades=self.dir))
        self.assertIsNone(B.imatge_resum("es", vespre, avui=True, dades=self.dir))
        # Vella, cap: el resum surt només amb text.
        self.imatge("grafica-avui-ca.png", B.IMATGE_MAX_MIN + 5)
        self.assertIsNone(B.imatge_resum("ca", ARA, dades=self.dir))

    def test_foto_amb_el_text_a_sota(self):
        api = Api()
        B.envia_resum(api, 1, "<b>Avui</b>\nTemperatura 20 °C.", "https://x/grafica-avui-ca.png?v=1")
        self.assertEqual([m for m, _ in api.enviats], ["sendPhoto"])
        self.assertEqual(api.enviats[0][1]["caption"], "<b>Avui</b>\nTemperatura 20 °C.")
        self.assertEqual(api.enviats[0][1]["parse_mode"], "HTML")

    def test_text_llarg_foto_i_despres_text(self):
        api = Api()
        B.envia_resum(api, 1, "x" * (B.PEU_MAX + 1), "https://x/g.png")
        self.assertEqual([m for m, _ in api.enviats], ["sendPhoto", "sendMessage"])
        self.assertIsNone(api.enviats[0][1].get("caption"))

    def test_si_la_foto_no_entra_nomes_el_text(self):
        class SenseFoto(Api):
            def __call__(self, metode, temps=30, **p):
                if metode == "sendPhoto":
                    raise RuntimeError("sendPhoto: wrong file identifier/HTTP URL specified")
                return super().__call__(metode, temps, **p)
        api = SenseFoto()
        B.envia_resum(api, 1, "Avui", "https://x/g.png")
        self.assertEqual([m for m, _ in api.enviats], ["sendMessage"])
        # Sense imatge, com abans.
        api = Api()
        B.envia_resum(api, 1, "Avui", None)
        self.assertEqual([m for m, _ in api.enviats], ["sendMessage"])


class Paraigua(unittest.TestCase):
    """El paraigua, darrere de la roba, amb les hores de la línia de la pluja."""

    def hores(self, probs, inici):
        return [{"hora": (inici + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M"), "probabilitat": p, "pluja_mm": 1}
                for i, p in enumerate(probs)]

    def test_les_hores_de_la_pluja(self):
        h = self.hores([0, 0.3, 0.6, 0, 0, 0.2], dt.datetime(2026, 10, 17, 15))
        self.assertEqual(B.text_paraigua(h, "ca"), "Paraigua de 16 a 18 h i de 20 a 21 h.")
        self.assertEqual(B.text_paraigua(h, "es"), "Paraguas de 16 a 18 h y de 20 a 21 h.")
        self.assertIsNone(B.text_paraigua(self.hores([0, 0.1], dt.datetime(2026, 10, 17, 15)), "ca"))

    def test_dema_amb_la_nit_davant(self):
        nit = self.hores([0.8, 0.8], dt.datetime(2026, 10, 17, 22))
        dia = self.hores([0.5, 0.5, 0, 0], dt.datetime(2026, 10, 18, 6))
        self.assertEqual(B.text_paraigua(dia, "ca", nit), "Paraigua aquesta nit i de 6 a 8 h.")
        self.assertEqual(B.text_paraigua(self.hores([0, 0], dt.datetime(2026, 10, 18, 6)), "es", nit), "Paraguas esta noche.")


class PeuDeTelegram(unittest.TestCase):
    def test_hora_de_les_dades_i_la_web(self):
        d = dades()
        t = B.resum(d, "ca", ARA, avui=True, telegram=True)
        self.assertTrue(t.endswith(f"Previsió de les 07:00. La de cada moment, a {B.WEB}"), t[-120:])
        self.assertTrue(B.resum(d, "es", ARA, avui=True, telegram=True).endswith(f"Previsión de las 07:00. La de cada momento, en {B.WEB}"))
        # Fora de Telegram (notificacions i «Consultes»), l'enllaç sol, com abans.
        self.assertTrue(B.resum(d, "ca", ARA, avui=True).endswith("\n" + B.WEB))


class AraComLaWeb(unittest.TestCase):
    """/ara amb les dades de la targeta «Ara» de la web (Juanjo, 17-10-2026)."""

    def test_totes_les_dades_i_els_avisos(self):
        d = dades()
        d["ara_casa"].update(hora=ARA.isoformat(timespec="minutes"), humitat=88, pressio=1012.4, pressio_3h=-1.4,
                             pluja_avui=2.35, dif_alta=1.2)
        d["vent"] = {"mitja": 6.2, "ratxa": 18.4}
        t = B.text_ara_bot(d, "ca", ARA)
        self.assertEqual(t.split("\n")[0], "<b>Ara a Montflorit</b> (mesura de les 07:00)")
        for tros in ("16 °C, no plou.", "A la part alta, 1 °C més.", "Pluja d'avui: 2,4 mm.", "Vent: 6 km/h, ratxes de 18 km/h.",
                     "Humitat 88 % · pressió 1012 hPa, baixant.", "1 avís actiu: /avisos_actius"):
            self.assertIn(tros, t)
        es = B.text_ara_bot(d, "es", ARA)
        for tros in ("En la parte alta, 1 °C más.", "Lluvia de hoy: 2,4 mm.", "Viento: 6 km/h, rachas de 18 km/h.",
                     "Humedad 88 % · presión 1012 hPa, bajando.", "1 aviso activo: /avisos_actius"):
            self.assertIn(tros, es)

    def test_avui_i_resum_fan_el_mateix(self):
        self.assertIn("/avui", B.ORDRES)
        self.assertIn("/resum", B.ORDRES)
        self.assertIn("/avui la previsió d'avui", B.T["ca"]["ajuda"])


class PlujaPrevista(unittest.TestCase):
    def test_quan_arriba_segons_la_previsio(self):
        # ADR 0019: la primera hora amb un 20 % o més, sense minuts.
        self.assertEqual(B.text_pluja_prevista(dades(), "ca", ARA),
                         "Possible pluja d'aquí a unes 5 hores, cap a les 12 h (40 %).")
        self.assertEqual(B.text_pluja_prevista(dades(), "es", ARA),
                         "Posible lluvia dentro de unas 5 horas, hacia las 12 h (40 %).")
        sec = dades()
        for f in sec["hores"]:
            f["probabilitat"] = 0.05
        self.assertIsNone(B.text_pluja_prevista(sec, "ca", ARA))


class FraseCel(unittest.TestCase):
    """La frase d'«Ara» als resums (Juanjo, 23-10-2026): la d'avui, amb tots els trams que queden d'avui
    (també la nit); la de demà, amb «Al matí» i «A la tarda», que el títol ja diu demà."""

    @staticmethod
    def hores(dia, desde, fins, temp, nuvols):
        res = []
        t = dt.datetime.fromisoformat(f"{dia}T{desde:02d}:00")
        while t < dt.datetime.fromisoformat(f"{dia}T00:00") + dt.timedelta(hours=fins):
            res.append({"hora": t.isoformat(timespec="minutes"), "fins": (t + dt.timedelta(hours=1)).isoformat(timespec="minutes"),
                        "temperatura": temp(t.hour), "nuvols": nuvols(t.hour), "vent": 0, "codi": 3, "pluja_mm": 0})
            t += dt.timedelta(hours=1)
        return res

    def test_avui_amb_la_nit_i_dema_sense_repetir_dema(self):
        avui = dt.date(2026, 10, 23)
        files = self.hores("2026-10-23", 9, 31, lambda h: 20 if 13 <= h <= 17 else 12, lambda h: 10)
        self.assertEqual(B.frase_cel(files, "ca", avui),
                         "Aquest matí, fresc i després agradable, i serè; aquesta tarda, temperatura agradable i serè; "
                         "aquesta nit, fresc i serè.")
        dema = self.hores("2026-10-24", 7, 14, lambda h: 12, lambda h: 10) + self.hores("2026-10-24", 14, 21, lambda h: 12, lambda h: 95)
        self.assertEqual(B.frase_cel(dema, "es", dt.date(2026, 10, 24), dema=True),
                         "Por la mañana, fresco y despejado; por la tarde, todavía fresco y cubierto.")
        # El tram en curs amb una sola hora ja no compta si en ve un altre.
        files = self.hores("2026-10-23", 13, 21, lambda h: 20, lambda h: 10)
        self.assertTrue(B.frase_cel(files, "ca", avui).startswith("Aquesta tarda,"))
