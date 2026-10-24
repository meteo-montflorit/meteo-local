# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del receptor de datos de IONOS (reserva/rep-dades.sh), en local."""
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(ARREL, "reserva", "rep-dades.sh")


def paquet(entrades):
    """Un tar.gz en memoria con (nombre, contenido) por entrada."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for nom, cos in entrades:
            info = tarfile.TarInfo(nom)
            info.size = len(cos)
            t.addfile(info, io.BytesIO(cos))
    return buf.getvalue()


@unittest.skipUnless(shutil.which("tar") and shutil.which("sh"), "cal tar i sh")
class RepDades(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def rep(self, dades):
        return subprocess.run(["sh", REP], input=dades, env={**os.environ, "REP_DIR": self.dir},
                              capture_output=True, timeout=60)

    def test_accepta_els_dos_json(self):
        r = self.rep(paquet([("montflorit.json", b'{"a": 1}'), ("avisos.json", b'{"avisos": []}')]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.load(open(os.path.join(self.dir, "montflorit.json"))), {"a": 1})

    def test_rebutja_el_que_es_fa_gran_en_descomprimir(self):
        # Auditoría del 09-10-2026: un tar.gz de 5 KB traía un JSON de 5 MB y
        # el límite de 2 MB solo miraba el comprimido.
        gran = b'{"a": "' + b"x" * 5_000_000 + b'"}'
        d = paquet([("montflorit.json", gran)])
        self.assertLess(len(d), 20_000)
        r = self.rep(d)
        self.assertEqual(r.returncode, 1)
        self.assertIn(b"descomprimit", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "montflorit.json")))

    def test_accepta_les_imatges_de_la_grafica(self):
        # ADR 0098: les quatre imatges del resum, només si són PNG de veritat.
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 100
        r = self.rep(paquet([("montflorit.json", b"{}"), ("grafica-avui-ca.png", png), ("grafica-dema-es.png", png)]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "grafica-avui-ca.png")))
        for nom, cos in (("grafica-avui-ca.png", b"<?php echo 1; ?>"), ("altra.png", png), ("grafica-avui-ca.png.php", png),
                         ("grafica-avui-ca.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 700_000)):
            r = self.rep(paquet([("montflorit.json", b'{"b": 2}'), (nom, cos)]))
            self.assertEqual(r.returncode, 1, nom)
        self.assertEqual(json.load(open(os.path.join(self.dir, "montflorit.json"))), {})

    def test_accepta_l_historial(self):
        # ADR 0099: l'índex i els dies, JSON; cap altre nom.
        r = self.rep(paquet([("historial.json", b'{"dies": []}'), ("historial-2026-10-16.json", b'{"hores": []}')]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "historial-2026-10-16.json")))
        for nom, cos in (("historial-2026-10-16.json", b"no"), ("historial-x.json", b"{}"), ("historial-2026-10-16.php", b"{}")):
            self.assertEqual(self.rep(paquet([(nom, cos)])).returncode, 1, nom)

    def test_accepta_l_arxiu_de_perill(self):
        # ADR 0124: els arxius per any de l'historial de «Perill».
        r = self.rep(paquet([("avisos-2026.json", b'{"any": 2026, "historial": []}')]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "avisos-2026.json")))
        for nom, cos in (("avisos-2026.json", b"no"), ("avisos-26.json", b"{}"), ("avisos-2026.php", b"{}")):
            self.assertNotEqual(self.rep(paquet([(nom, cos)])).returncode, 0, nom)

    def test_rebutja_noms_repetits_i_de_mes(self):
        r = self.rep(paquet([("montflorit.json", b"{}"), ("montflorit.json", b"{}")]))
        self.assertEqual(r.returncode, 1)
        self.assertIn(b"repetit", r.stderr)
        r = self.rep(paquet([("montflorit.json", b"{}"), ("avisos.json", b"{}"), ("avisos.json", b"{}")]))
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
