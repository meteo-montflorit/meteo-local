# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de la vuelta del bot de Telegram (bot/bot.py, ADR 0034, 0038, 0053,
0084 y 0101): la llamada a Telegram, el registro de errores, las órdenes, la
migración, las correcciones, la vuelta del cron, el estado y el informe.

Sin red: Telegram es de mentira, los chats son números inventados y todo se
escribe en carpetas temporales."""
import contextlib
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
sys.path.insert(0, os.path.join(ARREL, "bot"))
import bot as B  # noqa: E402

ARA = dt.datetime(2026, 10, 7, 7, 0).astimezone()


class Api:
    """Telegram de mentira: apunta lo que se envía; «falla» decide qué métodos fallan."""
    def __init__(self, falla=None):
        self.enviats, self.falla = [], falla or {}

    def __call__(self, metode, temps=30, **p):
        ex = self.falla.get(metode)
        if callable(ex):
            ex = ex(p)
        if ex:
            raise ex
        self.enviats.append((metode, p))
        if metode == "getChatMemberCount":
            return 12
        return {"message_id": len(self.enviats)} if metode == "sendMessage" else {}


class Aillat(unittest.TestCase):
    """Cada prova, amb la seva carpeta: res a ~/.temps-bot ni a la xarxa."""

    def setUp(self):
        dir_ = tempfile.TemporaryDirectory()
        self.addCleanup(dir_.cleanup)
        self.dir = d = dir_.name
        for nom, valor in (("BASE", d), ("DADES", d), ("REPO", d), ("SUBS", os.path.join(d, "subscriptors.json")),
                           ("ESTAT", os.path.join(d, "estat.json")), ("COMPTADOR", os.path.join(d, "comptador.json"))):
            p = unittest.mock.patch.object(B, nom, valor)
            p.start()
            self.addCleanup(p.stop)
        self.config = os.path.join(d, "vigilancia.json")
        for p in (unittest.mock.patch.dict(os.environ, {"AVISAR_CONFIG": self.config}),
                  unittest.mock.patch("urllib.request.urlopen", side_effect=AssertionError("sense xarxa")),
                  unittest.mock.patch.object(B.time, "sleep"),
                  unittest.mock.patch.object(sys, "path", list(sys.path))):
            p.start()
            self.addCleanup(p.stop)

    def registre(self):
        try:
            with open(os.path.join(self.dir, "errors.log"), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""


class Telegram(Aillat):
    def resposta(self, cos):
        return unittest.mock.patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(cos).encode()))

    def test_la_crida_a_l_api(self):
        with self.resposta({"ok": True, "result": {"message_id": 5}}) as urlopen:
            r = B.Api("123:abc")("sendMessage", chat_id=7, text="Hola", reply_markup={"a": 1}, parse_mode=None)
        self.assertEqual(r, {"message_id": 5})
        url, dades = urlopen.call_args[0]
        self.assertEqual(url, "https://api.telegram.org/bot123:abc/sendMessage")
        # Els diccionaris, en JSON; el que és None no s'envia.
        self.assertEqual(dades, b"chat_id=7&text=Hola&reply_markup=%7B%22a%22%3A+1%7D")
        self.assertEqual(urlopen.call_args[1], {"timeout": 30})

    def error(self, codi, descripcio):
        return urllib.error.HTTPError("https://api.telegram.org/", codi, "x", {},
                                      io.BytesIO(json.dumps({"ok": False, "description": descripcio}).encode()))

    def test_bloquejat_i_altres_errors(self):
        with unittest.mock.patch("urllib.request.urlopen", side_effect=self.error(403, "Forbidden: bot was blocked")):
            with self.assertRaises(B.Bloquejat):
                B.Api("t")("sendMessage", chat_id=7, text="x")
        with unittest.mock.patch("urllib.request.urlopen", side_effect=self.error(400, "Bad Request: chat not found")):
            with self.assertRaisesRegex(RuntimeError, "^sendMessage: Bad Request: chat not found$"):
                B.Api("t")("sendMessage", chat_id=7, text="x")


class Registre(Aillat):
    def test_el_registre_es_renova_quan_es_gran(self):
        ruta = os.path.join(self.dir, "errors.log")
        with open(ruta, "w") as f:
            f.write("vell\n" * 10)
        with unittest.mock.patch.object(B, "REGISTRE_MAX", 20), unittest.mock.patch.object(B, "ara", return_value=ARA):
            B.registra("nou")
        with open(ruta + ".1") as f:
            self.assertEqual(f.read(), "vell\n" * 10)
        self.assertEqual(self.registre(), "2026-10-07 07:00:00  nou\n")

    def test_si_no_es_pot_escriure_no_atura_el_bot(self):
        fitxer = os.path.join(self.dir, "no-és-carpeta")
        open(fitxer, "w").close()
        with unittest.mock.patch.object(B, "BASE", fitxer):
            B.registra("res")          # no llança cap excepció
        self.assertFalse(os.path.exists(os.path.join(self.dir, "errors.log")))


class Grafica(Aillat):
    def test_si_l_han_bloquejat_mentre_va_la_foto(self):
        api = Api({"sendPhoto": B.Bloquejat()})
        with self.assertRaises(B.Bloquejat):
            B.envia_resum(api, "7", "<b>Avui</b>", "https://x/g.png")
        self.assertEqual(api.enviats, [])

    def test_si_la_foto_falla_el_text_i_queda_apuntat(self):
        api = Api({"sendPhoto": RuntimeError("wrong file")})
        B.envia_resum(api, "7", "<b>Avui</b>", "https://x/g.png")
        self.assertEqual([(m, p["text"]) for m, p in api.enviats], [("sendMessage", "<b>Avui</b>")])
        self.assertIn("la gràfica del resum no ha entrat: wrong file", self.registre())


    def test_la_foto_es_reaprofita(self):
        # Telegram la baixa una vegada; després, el seu file_id.
        respostes = iter([{"photo": [{"file_id": "petita"}, {"file_id": "gran"}]}, {}])
        crides = []

        def foto(metode, temps=30, **p):
            crides.append(p.get("photo"))
            return next(respostes)

        with unittest.mock.patch.dict(B.FOTOS, clear=True):
            B.envia_resum(foto, "7", "<b>Avui</b>", "https://x/g.png?v=1")
            B.envia_resum(foto, "8", "<b>Avui</b>", "https://x/g.png?v=1")
            self.assertEqual(B.FOTOS, {"https://x/g.png?v=1": "gran"})
        self.assertEqual(crides, ["https://x/g.png?v=1", "gran"])


class Ordres(Aillat):
    def missatge(self, text, chat=7, idioma="ca"):
        return {"message": {"chat": {"id": chat, "type": "private"}, "from": {"language_code": idioma}, "text": text}}

    def test_avisos_obre_el_menu(self):
        api, subs = Api(), {"7": {"idioma": "es", "avisos": ["riera"], "resum": "7"}}
        B.atén(api, subs, self.missatge("/avisos@TempsMontfloritBot"))
        metode, p = api.enviats[-1]
        self.assertEqual(p["text"], B.T["es"]["menu"])
        self.assertEqual(p["reply_markup"], {"inline_keyboard": B.teclat(subs["7"])})

    def test_el_comptador_que_falla_no_atura_la_resposta(self):
        api, subs = Api(), {"7": {"idioma": "ca", "avisos": [], "resum": None}}
        with unittest.mock.patch.object(B, "compta", side_effect=OSError("disc ple")):
            B.atén(api, subs, self.missatge("/menu"))
        self.assertEqual(api.enviats[-1][1]["text"], B.T["ca"]["menu"])
        self.assertIn("comptador: disc ple", self.registre())

    def test_baixa_sense_estat_i_moviments_que_fallen(self):
        api, subs = Api(), {"7": {"idioma": "es", "avisos": ["riera"], "resum": None}}
        with unittest.mock.patch.object(B, "moviment", side_effect=OSError("bloqueig")):
            B.atén(api, subs, self.missatge("/baixa"))
        self.assertEqual(subs, {})
        self.assertEqual(api.enviats[-1][1]["text"], B.T["es"]["baixa"])
        self.assertIn("moviments: bloqueig", self.registre())

    def test_l_alta_sense_moviments_avisa_igualment(self):
        subs, avisos = {}, []
        with unittest.mock.patch.object(B, "moviment", side_effect=OSError("x")), \
                unittest.mock.patch.object(B, "avisa_juanjo", side_effect=avisos.append):
            sub = B.alta(subs, "7", {"language_code": "es-ES"})
        self.assertEqual((sub["idioma"], sub["avisos"]), ("es", ["riera", "perill"]))
        self.assertEqual(avisos, ["Temps a Montflorit: alta nova al bot (ja en són 1)."])

    def test_el_comptador_guarda_400_dies(self):
        with unittest.mock.patch.object(B, "COMPTADOR_DIES", 2):
            for dia in ("2026-10-01", "2026-10-02", "2026-10-03"):
                B.compta("/ara", "1", dia=dia)
        self.assertEqual(sorted(B.llegeix(B.COMPTADOR, {})), ["2026-10-02", "2026-10-03"])


class Juanjo(Aillat):
    def test_sense_configuracio_no_s_envia_res(self):
        with unittest.mock.patch.object(B, "Api") as api:
            B.avisa_juanjo("hola")
        api.assert_not_called()

    def test_si_el_seu_bot_falla_queda_apuntat(self):
        B.desa(self.config, {"token": "t", "chat_id": 99})
        api = Api({"sendMessage": RuntimeError("timeout")})
        with unittest.mock.patch.object(B, "Api", return_value=api):
            B.avisa_juanjo("hola")
        self.assertIn("no se ha podido avisar a Juanjo: timeout", self.registre())

    def test_el_canal_sense_el_total(self):
        cm = {"chat": {"username": "TempsMontflorit"}, "old_chat_member": {"status": "left"},
              "new_chat_member": {"status": "member"}}
        avisos = []
        with unittest.mock.patch.object(B, "avisa_juanjo", side_effect=avisos.append):
            B.canvi_canal(Api({"getChatMemberCount": RuntimeError("x")}), cm)
        self.assertEqual(avisos, ["Temps a Montflorit: alta nova al canal."])

    def test_qui_es_al_canal_si_telegram_falla(self):
        # Davant el dubte, no és al canal: millor un avís repetit que un de perdut.
        memoria = {}
        self.assertFalse(B.al_canal(Api({"getChatMember": RuntimeError("x")}), "7", memoria))
        self.assertEqual(memoria, {"7": False})


class Migracio(Aillat):
    def test_els_avisos_de_trens_es_reintenta_o_es_dona_de_baixa(self):
        subs = {"1": {"idioma": "ca", "avisos": ["riera", "trens"], "resum": "20"},
                "2": {"idioma": "es", "avisos": ["trens"], "resum": None},
                "3": {"idioma": "ca", "avisos": ["trens", "pluja"], "resum": None}}
        estat = {"resums": {"2": "2026-10-07"}, "pendents": {}}
        falla = lambda p: {"2": B.Bloquejat(), "3": RuntimeError("429")}.get(p["chat_id"])
        api = Api({"sendMessage": falla})
        with unittest.mock.patch.object(B, "moviment"):
            B.migra(api, subs, estat)
        # El 1, avisat i sense trens; la previsió de les 20 h, a la de la nit.
        self.assertEqual(subs["1"], {"idioma": "ca", "avisos": ["riera"], "resum": None, "nit": True})
        self.assertEqual(api.enviats[0][1]["text"], B.T["ca"]["sense_trens"])
        # El 2 ha bloquejat el bot: fora, també de l'estat.
        self.assertNotIn("2", subs)
        self.assertEqual(estat["resums"], {})
        # El 3 no ha rebut el missatge: es queda amb trens per tornar-ho a provar.
        self.assertEqual(subs["3"]["avisos"], ["trens", "pluja"])
        self.assertIn("l'avís de la fi dels avisos de trens no ha entrat: 429", self.registre())


class Correccions(Aillat):
    def test_correccio_amb_pendents_i_un_xat_que_falla(self):
        B.desa(os.path.join(self.dir, "avisos.json"),
               {"correccions": [{"id": "riera:1", "hora": "07:05", "ca": "<b>Riera</b> corregit", "es": "<b>Riera</b> corregido"},
                                {"hora": "sense id"}]})
        estat = {"enviats": {"riera:1": ARA.isoformat()},
                 "pendents": {"riera:1": {"avis": {"ca": "vell", "es": "viejo", "tipus": "riera"}, "chats": ["9"]}},
                 "missatges": {"riera:1": [["7", 3, "es"], ["8", 4, "ca"]]},
                 "corregits": {"ja-no-hi-és": "06:00"}}
        api = Api({"editMessageText": lambda p: RuntimeError("message is not modified") if p["chat_id"] == "8" else None})
        B.corregeix(api, estat, ARA + dt.timedelta(minutes=10))
        # Qui encara l'ha de rebre, ja el rep corregit.
        self.assertEqual(estat["pendents"]["riera:1"]["avis"]["es"], "<b>Riera</b> corregido")
        self.assertEqual([(p["chat_id"], p["text"]) for _, p in api.enviats], [("7", "<b>Riera</b> corregido")])
        self.assertIn("correcció de riera:1 a 8: message is not modified", self.registre())
        # Les correccions d'avisos que ja no es recorden, fora.
        self.assertEqual(estat["corregits"], {"riera:1": "07:05"})

    def test_el_que_es_repartit_fa_tres_dies_s_oblida(self):
        vell = (ARA - dt.timedelta(days=4)).isoformat(timespec="minutes")
        estat = {"enviats": {"vell": vell}, "missatges": {"vell": [["7", 1, "ca"]]},
                 "canal_resum": ARA.date().isoformat()}
        api = Api()
        B.reparteix(api, {}, estat, ARA)
        self.assertEqual((estat["enviats"], estat["missatges"]), ({}, {}))
        # L'estat d'abans del 09-10-2026: la previsió del canal de les 7 ja feta.
        self.assertEqual(estat["canal_resums"], {"7": ARA.date().isoformat()})
        self.assertNotIn("canal_resum", estat)
        self.assertEqual(api.enviats, [])


    def test_la_previsio_de_cadascu_que_falla(self):
        B.desa(os.path.join(self.dir, "montflorit.json"), {})
        subs = {"1": {"idioma": "ca", "avisos": [], "resum": "8"}, "2": {"idioma": "es", "avisos": [], "resum": "8"}}
        estat = {"resums": {"1": {"7": "2026-10-06"}}}
        falla = lambda p: {"1": B.Bloquejat(), "2": RuntimeError("429 Too Many Requests")}.get(p["chat_id"])
        with unittest.mock.patch.object(B, "moviment"), unittest.mock.patch.object(B, "ara", return_value=ARA):
            B.reparteix(Api({"sendMessage": falla}), subs, estat, ARA.replace(hour=8))
        # Qui ha bloquejat el bot, fora; l'altre, sense marcar: es reintenta dins de l'hora.
        self.assertEqual(list(subs), ["2"])
        self.assertEqual(estat["resums"], {})
        self.assertIn("un resumen de las 8 h no ha entrado: 429 Too Many Requests", self.registre())


class Repositori(Aillat):
    def test_com_a_molt_un_cop_per_hora(self):
        estat = {"pull": B.time.time() - 60}
        with unittest.mock.patch.object(B.subprocess, "run") as run, \
                unittest.mock.patch.dict(sys.modules, {"desplegament": None}):
            B.actualitza_repo(estat)
        run.assert_not_called()

    def test_amb_desplegament_o_amb_git_pull(self):
        desplegament = unittest.mock.Mock()
        estat = {"pull": 0}
        with unittest.mock.patch.dict(sys.modules, {"desplegament": desplegament}):
            B.actualitza_repo(estat)
        desplegament.actualitza.assert_called_once_with(self.dir, {}, B.registra)
        self.assertGreater(estat["pull"], 0)
        # Amb proves pendents, cada volta, encara que sigui de fa poc.
        estat["desplegament"] = {"proves_pendents": "abc"}
        with unittest.mock.patch.dict(sys.modules, {"desplegament": None}), \
                unittest.mock.patch.object(B.subprocess, "run") as run:
            B.actualitza_repo(estat)
        self.assertEqual(run.call_args[0][0], ["git", "-C", self.dir, "pull", "-q", "--ff-only"])

    def test_si_falla_queda_apuntat(self):
        desplegament = unittest.mock.Mock()
        desplegament.actualitza.side_effect = RuntimeError("git fetch")
        with unittest.mock.patch.dict(sys.modules, {"desplegament": desplegament}):
            B.actualitza_repo({})
        self.assertIn("no se ha podido poner al día el repositorio: git fetch", self.registre())


class Volta(Aillat):
    def test_una_volta_amb_missatges_i_errors(self):
        B.desa(os.path.join(self.dir, "config.json"), {"token": "t"})
        B.desa(B.SUBS, {"5": {"idioma": "ca", "avisos": ["riera"], "resum": None}})
        B.desa(B.ESTAT, {"resums": {"fora": "2026-10-06"}, "pull": 0})
        updates = [RuntimeError("Conflict"),
                   [{"update_id": 10, "message": {"chat": {"id": 7, "type": "private"}, "from": {}, "text": "/start"}},
                    {"update_id": 11, "callback_query": {}}]]

        class ApiVolta(Api):
            def __call__(self, metode, temps=30, **p):
                if metode == "getUpdates":
                    self.enviats.append((metode, p))
                    r = updates.pop(0)
                    if isinstance(r, Exception):
                        raise r
                    return r
                return super().__call__(metode, temps, **p)

        api = ApiVolta()
        temps = iter([1000, 1000, 1000, 1049])
        with unittest.mock.patch.object(B, "Api", return_value=api) as fabrica, \
                unittest.mock.patch.object(B.time, "time", side_effect=lambda: next(temps)), \
                unittest.mock.patch.object(B, "actualitza_repo") as repo, \
                unittest.mock.patch.object(B, "avisa_juanjo"), \
                unittest.mock.patch.object(B, "ara", return_value=ARA):
            B.volta()
        fabrica.assert_called_once_with("t")
        repo.assert_called_once()
        crides = [p for m, p in api.enviats if m == "getUpdates"]
        self.assertEqual([(p["offset"], p["timeout"]) for p in crides], [(None, 25), (None, 25)])
        estat = B.llegeix(B.ESTAT, {})
        # L'offset avança també pel missatge que ha fallat, i els restes de
        # xats que ja no hi són s'esborren.
        self.assertEqual(estat["offset"], 12)
        self.assertNotIn("fora", estat["resums"])
        self.assertIn("7", B.llegeix(B.SUBS, {}))
        registre = self.registre()
        self.assertIn("getUpdates: Conflict", registre)
        self.assertIn("al atender un mensaje: 'message'", registre)

    def test_si_la_volta_anterior_no_ha_acabat(self):
        import fcntl
        cadenat = open(os.path.join(self.dir, "bot.lock"), "w")
        self.addCleanup(cadenat.close)
        fcntl.flock(cadenat, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with unittest.mock.patch.object(B, "Api") as api:
            B.volta()
        api.assert_not_called()


class EstatIInforme(Aillat):
    def dades(self):
        B.desa(B.SUBS, {"1": {"idioma": "ca", "avisos": ["riera", "perill"], "resum": "7"},
                        "2": {"idioma": "es", "avisos": ["pluja"], "resum": None}})
        B.desa(B.ESTAT, {"enviats": {"riera:1": ARA.isoformat()}, "pendents": {"perill:2": {}}})
        B.desa(os.path.join(self.dir, "push.json"), {"https://push/1": {"avisos": ["riera", "pluja"], "resum": "8"}})
        with open(os.path.join(self.dir, "errors.log"), "w") as f:
            f.write("".join(f"error {i}\n" for i in range(8)))

    def test_estat(self):
        self.dades()
        sortida = io.StringIO()
        with contextlib.redirect_stdout(sortida):
            B.mostra_estat()
        text = sortida.getvalue()
        for linia in ("Subscriptors: 2", "  riera: 1", "  pluja: 1", "  llum: 0", "  resum: 1",
                      "Avisos repartits (3 dies): 1", "Pendents d'entregar: perill:2"):
            self.assertIn(linia + "\n", text)
        # Només els cinc últims errors.
        self.assertTrue(text.endswith("Últims errors:\nerror 3\nerror 4\nerror 5\nerror 6\nerror 7\n"))

    def test_estat_sense_errors(self):
        with contextlib.redirect_stdout(io.StringIO()) as sortida:
            B.mostra_estat()
        self.assertTrue(sortida.getvalue().startswith("Subscriptors: 0\n"))
        self.assertNotIn("Últims errors", sortida.getvalue())

    def test_informe_a_juanjo(self):
        self.dades()
        B.desa(os.path.join(self.dir, "config.json"), {"token": "t"})
        B.desa(self.config, {"token": "propi", "chat_id": 99})
        api = Api()
        with unittest.mock.patch.object(B, "Api", return_value=api) as fabrica, \
                contextlib.redirect_stdout(io.StringIO()) as sortida:
            B.informe()
        self.assertEqual([c[0][0] for c in fabrica.call_args_list], ["t", "propi"])
        text = api.enviats[-1][1]["text"]
        self.assertEqual(api.enviats[-1][1]["chat_id"], 99)
        self.assertTrue(text.startswith("Temps a Montflorit: 2 suscriptores en el bot (riera 1, peligro 1, lluvia 1, "
                                        "previsión diaria 1) y 12 miembros en el canal.\n"))
        self.assertIn("Avisos en el navegador: 1 dispositivos (riera 1, peligro 0, lluvia 1, previsión diaria 1).\n", text)
        self.assertIn(text, sortida.getvalue())

    def test_informe_sense_canal_ni_bot_propi(self):
        # Sense la configuració del bot, el canal «?»; sense la de Juanjo, només per pantalla.
        with contextlib.redirect_stdout(io.StringIO()) as sortida:
            B.informe()
        self.assertIn("y ? miembros en el canal.", sortida.getvalue())

    def test_l_ordre_estat_des_de_la_linia_d_ordres(self):
        self.dades()
        with unittest.mock.patch.dict(os.environ, {"BOT_DIR": self.dir}), \
                unittest.mock.patch.object(sys, "argv", ["bot.py", "estat"]), \
                contextlib.redirect_stdout(io.StringIO()) as sortida:
            runpy.run_path(os.path.join(ARREL, "bot", "bot.py"), run_name="__main__")
        self.assertIn("Subscriptors: 2\n", sortida.getvalue())


if __name__ == "__main__":
    unittest.main()
