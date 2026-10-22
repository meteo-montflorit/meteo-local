# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del envío de los avisos en el navegador (bot/push.py, ADR 0048 y
0084): las claves VAPID, la llamada a pywebpush, los fallos que no pueden
perder un aviso ni una previsión, la vuelta del cron y el estado.

Sin red: pywebpush y py_vapid son de mentira, las suscripciones son
direcciones inventadas y todo se escribe en carpetas temporales."""
import contextlib
import datetime as dt
import io
import json
import os
import runpy
import stat
import sys
import tempfile
import types
import unittest
import unittest.mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ARREL, "bot"))
import bot as B  # noqa: E402
import push as P  # noqa: E402

ARA = dt.datetime(2026, 10, 8, 7, 0).astimezone()
CA = "https://fcm.googleapis.com/fcm/send/prova-ca"
ES = "https://updates.push.services.mozilla.com/wpush/v2/prova-es"
CLAUS_SUB = {"keys": {"p256dh": "x", "auth": "y"}}

try:
    import cryptography  # noqa: F401
    TE_CRYPTOGRAPHY = True
except ImportError:
    TE_CRYPTOGRAPHY = False


class Aillat(unittest.TestCase):
    """Cada prova, amb la seva carpeta, i el bot i push.py apuntant-hi."""

    def setUp(self):
        dir_ = tempfile.TemporaryDirectory()
        self.addCleanup(dir_.cleanup)
        self.dir = d = dir_.name
        pegats = [unittest.mock.patch.object(B, "BASE", d), unittest.mock.patch.object(B, "DADES", d),
                  unittest.mock.patch.object(P, "SUBS", os.path.join(d, "push.json")),
                  unittest.mock.patch.object(P, "ESTAT", os.path.join(d, "push-estat.json")),
                  unittest.mock.patch.object(P, "CLAUS", os.path.join(d, "vapid.json")),
                  unittest.mock.patch.object(P, "CADENAT_SUBS", os.path.join(d, "push.lock")),
                  unittest.mock.patch.object(P, "_vapid", None),
                  unittest.mock.patch.object(B, "avisa_juanjo"),
                  unittest.mock.patch.object(B, "ara", return_value=ARA),
                  unittest.mock.patch("urllib.request.urlopen", side_effect=AssertionError("sense xarxa")),
                  unittest.mock.patch.object(sys, "path", list(sys.path))]
        for p in pegats:
            p.start()
            self.addCleanup(p.stop)

    def registre(self):
        try:
            with open(os.path.join(self.dir, "errors.log"), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""


class Claus(Aillat):
    def test_les_que_ja_hi_son_no_es_toquen(self):
        B.desa(P.CLAUS, {"privada": "PEM", "publica": "PUB"})
        self.assertEqual(P.claus(), {"privada": "PEM", "publica": "PUB"})

    @unittest.skipUnless(TE_CRYPTOGRAPHY, "cal cryptography")
    def test_es_creen_una_vegada_i_nomes_les_llegeix_el_propietari(self):
        dades = P.claus()
        self.assertTrue(dades["privada"].startswith("-----BEGIN PRIVATE KEY-----"))
        # La pública, el punt sense comprimir (65 bytes) en base64url sense «=».
        self.assertEqual(len(dades["publica"]), 87)
        self.assertNotIn("=", dades["publica"])
        self.assertEqual(stat.S_IMODE(os.stat(P.CLAUS).st_mode), 0o600)
        self.assertEqual(P.claus(), dades)


class WebPushException(Exception):
    def __init__(self, missatge, response=None):
        super().__init__(missatge)
        self.response = response


class EnviaPush(Aillat):
    def setUp(self):
        super().setUp()
        B.desa(P.CLAUS, {"privada": "PEM", "publica": "PUB"})
        self.webpush = unittest.mock.Mock()
        self.vapid = types.SimpleNamespace(Vapid=unittest.mock.Mock())
        moduls = {"pywebpush": types.SimpleNamespace(webpush=self.webpush, WebPushException=WebPushException),
                  "py_vapid": self.vapid}
        p = unittest.mock.patch.dict(sys.modules, moduls)
        p.start()
        self.addCleanup(p.stop)

    def test_l_enviament(self):
        sub = {"endpoint": CA, **CLAUS_SUB, "avisos": ["riera"]}
        P.envia_push(sub, {"title": "Riera", "body": "Puja l'aigua"}, 600, urgent=True)
        P.envia_push(sub, {"title": "Previsió"}, 60)
        # La clau es carrega una sola vegada, del PEM com a bytes.
        self.vapid.Vapid.from_pem.assert_called_once_with(b"PEM")
        (subscripcio, cos), kw = self.webpush.call_args_list[0]
        self.assertEqual(subscripcio, {"endpoint": CA, "keys": CLAUS_SUB["keys"]})
        self.assertEqual(json.loads(cos), {"title": "Riera", "body": "Puja l'aigua"})
        self.assertEqual((kw["ttl"], kw["headers"], kw["vapid_claims"]), (600, {"Urgency": "high"}, {"sub": P.CONTACTE}))
        self.assertEqual(self.webpush.call_args_list[1][1]["headers"], {"Urgency": "normal"})

    def test_morta_o_error(self):
        sub = {"endpoint": CA, **CLAUS_SUB}
        for codi in (404, 410):
            self.webpush.side_effect = WebPushException("Gone", types.SimpleNamespace(status_code=codi))
            with self.assertRaises(P.Morta):
                P.envia_push(sub, {}, 60)
        # Un error del servei no és una subscripció morta: es reintenta.
        self.webpush.side_effect = WebPushException("Server error", types.SimpleNamespace(status_code=503))
        with self.assertRaisesRegex(RuntimeError, "^503: Server error$"):
            P.envia_push(sub, {}, 60)
        self.webpush.side_effect = WebPushException("timeout")
        with self.assertRaisesRegex(RuntimeError, "^None: timeout$"):
            P.envia_push(sub, {}, 60)


class Envia:
    """El servei de notificacions de mentira: «respostes» diu què passa a cada
    enviament de cada adreça, per ordre (None, entra)."""
    def __init__(self, **respostes):
        self.enviats, self.respostes = [], {e: list(r) for e, r in respostes.items()}

    def __call__(self, sub, dades, ttl, urgent=False):
        r = (self.respostes.get(sub["endpoint"]) or [None]).pop(0)
        if r:
            raise r
        self.enviats.append((sub["endpoint"], dades))


class Repartiment(Aillat):
    def setUp(self):
        super().setUp()
        B.desa(P.SUBS, {CA: {**CLAUS_SUB, "avisos": ["riera"], "resum": "7", "idioma": "ca"},
                        ES: {**CLAUS_SUB, "avisos": ["pluja"], "resum": "", "idioma": "es"}})

    def avisos(self, *llista):
        B.desa(os.path.join(self.dir, "avisos.json"), {"avisos": list(llista)})

    def avis(self, tipus, hora=ARA):
        return {"id": f"{tipus}:1", "tipus": tipus, "hora": hora.isoformat(timespec="minutes"),
                "ca": f"<b>Avís de {tipus}</b>\nText.", "es": f"<b>Aviso de {tipus}</b>\nTexto."}

    def test_la_previsio_que_no_entra_es_reintenta(self):
        estat = {}
        P.reparteix(estat, ARA, Envia(**{CA: [RuntimeError("503 Service Unavailable")]}))
        self.assertIn("push: una previsión de las 7 h no ha entrado: 503 Service Unavailable", self.registre())
        self.assertNotIn(CA, estat["resums"])
        envia = Envia()
        P.reparteix(estat, ARA.replace(minute=1), envia)
        self.assertEqual([e for e, _ in envia.enviats], [CA])
        self.assertEqual(estat["resums"][CA], {"7": ARA.date().isoformat()})

    def test_la_prova_que_no_entra_queda_apuntada_i_no_es_repeteix(self):
        subs = B.llegeix(P.SUBS, {})
        subs[ES]["prova"] = (ARA - dt.timedelta(minutes=1)).isoformat()
        B.desa(P.SUBS, subs)
        P.reparteix({}, ARA, Envia(**{ES: [RuntimeError("413")]}))
        self.assertIn("push: la prueba no ha entrado: 413", self.registre())
        self.assertNotIn("prova", B.llegeix(P.SUBS, {})[ES])

    def test_la_que_mor_despres_surt_dels_pendents(self):
        # La riera no entra (es reintentarà), i la previsió diu que l'adreça és
        # morta: fora de tot, també del que quedava pendent.
        self.avisos(self.avis("riera"))
        estat = {}
        mortes = P.reparteix(estat, ARA, Envia(**{CA: [RuntimeError("503"), P.Morta()]}))
        self.assertEqual(mortes, {CA})
        self.assertEqual(estat["pendents"]["riera:1"]["subs"], [])
        self.assertNotIn(CA, B.llegeix(P.SUBS, {}))
        self.assertNotIn(CA, estat["resums"])

    def test_els_avisos_de_fa_tres_dies_s_obliden(self):
        estat = {"enviats": {"vell:1": (ARA - dt.timedelta(days=4)).isoformat(timespec="minutes"),
                             "recent:1": (ARA - dt.timedelta(days=1)).isoformat(timespec="minutes")}}
        P.reparteix(estat, ARA.replace(hour=12), Envia())
        self.assertEqual(list(estat["enviats"]), ["recent:1"])


class Volta(Aillat):
    def test_desa_l_estat_encara_que_falli(self):
        B.desa(P.ESTAT, {"enviats": {"x": "y"}})

        def reparteix(estat, moment):
            estat["tocat"] = moment.isoformat()
            raise RuntimeError("push.json malmès")

        with unittest.mock.patch.object(P, "reparteix", side_effect=reparteix), \
                unittest.mock.patch.object(P, "altes") as altes:
            with self.assertRaises(RuntimeError):
                P.volta()
        altes.assert_not_called()
        self.assertEqual(B.llegeix(P.ESTAT, {}), {"enviats": {"x": "y"}, "tocat": ARA.isoformat()})

    def test_les_mortes_van_a_les_altes(self):
        with unittest.mock.patch.object(P, "reparteix", return_value={CA}) as reparteix, \
                unittest.mock.patch.object(P, "altes") as altes:
            P.volta()
        reparteix.assert_called_once_with({}, ARA)
        altes.assert_called_once_with({}, {CA})

    def test_si_la_volta_anterior_no_ha_acabat(self):
        import fcntl
        cadenat = open(os.path.join(self.dir, "push-volta.lock"), "w")
        self.addCleanup(cadenat.close)
        fcntl.flock(cadenat, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with unittest.mock.patch.object(P, "reparteix") as reparteix:
            P.volta()
        reparteix.assert_not_called()
        self.assertFalse(os.path.exists(P.ESTAT))


class Estat(Aillat):
    def setUp(self):
        super().setUp()
        B.desa(P.SUBS, {CA: {"avisos": ["riera", "perill"], "resum": "8", "idioma": "ca"},
                        ES: {"avisos": ["pluja"], "idioma": "es"}})

    def test_estat(self):
        B.desa(P.ESTAT, {"pendents": {"riera:1": {}, "pluja:2": {}}})
        with contextlib.redirect_stdout(io.StringIO()) as sortida:
            P.mostra_estat()
        self.assertEqual(sortida.getvalue(), "Subscripcions: 2\n  riera: 1\n  perill: 1\n  pluja: 1\n  llum: 0\n"
                                             "  resum: 1\n  ca: 1, es: 1\nPendents d'entregar: riera:1, pluja:2\n")

    def test_les_ordres(self):
        B.desa(os.path.join(self.dir, "vapid.json"), {"privada": "PEM", "publica": "PUB"})
        ruta = os.path.join(ARREL, "bot", "push.py")
        for ordre, esperat in (("estat", "Subscripcions: 2\n"), ("claus", "PUB\n")):
            with self.subTest(ordre=ordre), unittest.mock.patch.object(sys, "argv", ["push.py", ordre]), \
                    contextlib.redirect_stdout(io.StringIO()) as sortida:
                runpy.run_path(ruta, run_name="__main__")
                self.assertTrue(sortida.getvalue().startswith(esperat))
        # Sense ordre, una volta: sense avisos ni previsió a l'hora, res a enviar.
        with unittest.mock.patch.object(sys, "argv", ["push.py"]):
            runpy.run_path(ruta, run_name="__main__")
        self.assertEqual(B.llegeix(os.path.join(self.dir, "push-estat.json"), {})["coneguts"], [CA, ES])


if __name__ == "__main__":
    unittest.main()
