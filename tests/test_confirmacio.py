# SPDX-License-Identifier: AGPL-3.0-or-later
"""Les lectures de les respostes del bot (confirmacio.telegram): una sola
alhora i, si Telegram diu que xoquen, un segon intent."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import confirmacio as CF  # noqa: E402


class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def conflicte(codi=409):
    return urllib.error.HTTPError("https://api.telegram.org", codi, "Conflict", {}, None)


class Telegram(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = os.path.join(self.tmp.name, "config.json")
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"token": "1:prova", "chat_id": 7}, f)
        for nom, valor in (("CADENAT_BOT", os.path.join(self.tmp.name, "bot.lock")), ("ESPERA_CONFLICTE_S", 0)):
            p = mock.patch.object(CF, nom, valor)
            p.start()
            self.addCleanup(p.stop)

    def crida(self, efectes, metode="getUpdates"):
        with mock.patch.object(CF.urllib.request, "urlopen", side_effect=efectes) as obre:
            try:
                return CF.telegram(metode, self.config), obre.call_count
            except urllib.error.HTTPError as ex:
                return ex.code, obre.call_count

    def test_un_xoc_es_torna_a_provar(self):
        # 14-11-2026: la boira i el cel llegien alhora i Telegram en rebutjava una (409).
        be = lambda: Resposta(json.dumps({"ok": True, "result": [{"update_id": 1}]}).encode())
        (resultat, cfg), n = self.crida([conflicte(), be()])
        self.assertEqual((resultat, cfg["chat_id"], n), ([{"update_id": 1}], 7, 2))
        self.assertTrue(os.path.exists(CF.CADENAT_BOT))        # amb el cadenat comú
        # Dos xocs seguits, o un altre error: falla, com abans.
        self.assertEqual(self.crida([conflicte(), conflicte()]), (409, 2))
        self.assertEqual(self.crida([conflicte(502), be()]), (502, 1))
        # Enviar un missatge no espera ni repeteix.
        self.assertEqual(self.crida([conflicte(), be()], "sendMessage"), (409, 1))


if __name__ == "__main__":
    unittest.main()
