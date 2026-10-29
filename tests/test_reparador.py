# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del reparador (ADR 0113), con repositorios git locales, el agente
simulado y sin red."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import reparador as R  # noqa: E402

ENTORN = {**os.environ, "GIT_AUTHOR_NAME": "p", "GIT_AUTHOR_EMAIL": "p@p",
          "GIT_COMMITTER_NAME": "p", "GIT_COMMITTER_EMAIL": "p@p"}


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env=ENTORN).stdout.strip()


def escriu(carpeta, nom, text):
    p = os.path.join(carpeta, nom)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


class Reparador(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = self.dir.name
        self.origen = os.path.join(d, "origen.git")
        self.treball = os.path.join(d, "treball")
        self.estat = os.path.join(d, "estat")
        git("init", "-q", "--bare", "-b", "main", self.origen, cwd=d)
        git("clone", "-q", self.origen, self.treball, cwd=d)
        escriu(self.treball, "config.py", 'VERSION = "3.170.0"\n')
        escriu(self.treball, "programa.py", "X = 1\n")
        escriu(self.treball, "ruff.toml", "")
        escriu(self.treball, "tests/test_a.py", "def test_u():\n    pass\n\ndef test_dos():\n    pass\n")
        git("add", "-A", cwd=self.treball)
        git("commit", "-q", "-m", "inici", cwd=self.treball)
        git("push", "-q", "origin", "HEAD:main", cwd=self.treball)
        self.sha = git("rev-parse", "HEAD", cwd=self.treball)
        self.avisos = []
        self.agents = []
        for p in (mock.patch.object(R, "URL_REPO", self.origen),
                  mock.patch.object(R, "ESTAT_DIR", self.estat),
                  mock.patch.object(R, "REGISTRE_DIR", os.path.join(self.estat, "registre")),
                  mock.patch.object(R, "instala_eslint", lambda copia: None),
                  mock.patch.object(R, "avisa", self.avisos.append),
                  mock.patch.object(R, "AUTOR", ["-c", "user.name=p", "-c", "user.email=p@p"])):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.dir.cleanup)
        os.makedirs(self.estat)
        self.falla(self.sha)

    def falla(self, sha):
        with open(os.path.join(self.estat, "desplegament.json"), "w") as f:
            json.dump({"proves_fallides": {"sha": sha, "hora": time.time()}}, f)

    def registre(self):
        try:
            with open(os.path.join(self.estat, "registre", "reparador.jsonl")) as f:
                return [json.loads(linia) for linia in f]
        except OSError:
            return []

    def origen_main(self):
        return git("rev-parse", "main", cwd=self.origen)

    def comprova(self, resultats, agent=None, minuts=31):
        """resultats: una lista de booleanos por pasada de las comprobaciones."""
        pasades = iter(resultats)

        def comprovacions(repo):
            ok = next(pasades)
            return [{"nom": "proves", "ok": ok, "sortida": "" if ok else "FAIL: test_u"}]

        def agent_fals(repo, fallades):
            self.agents.append(fallades)
            return agent(repo) if agent else {"arreglat": False, "detall": "no"}

        with mock.patch.object(R, "comprovacions", comprovacions), mock.patch.object(R, "agent", agent_fals):
            R.comprova(ara=time.time() + minuts * 60)

    def font_que_falla(self, agent):
        import fonts_falla as FF
        fitxer = os.path.join(self.estat, "fonts-falla.json")
        s = {"des_de": "2026-10-29T13:30Z", "error": "riera: x", "avisat": False, "reparar": True}
        with open(fitxer, "w") as f:
            json.dump({"riera": s}, f)
        with mock.patch.object(FF, "FITXER", fitxer), mock.patch.object(R, "prepara_copia", lambda sha: True), \
                mock.patch.object(R, "versio", lambda copia: "3.170.0"), mock.patch.object(R, "proves", lambda c: 2), \
                mock.patch.object(R, "agent", lambda *a: agent):
            R.repara_font("riera", s, {})
        with open(fitxer) as f:
            return json.load(f)["riera"]

    def test_si_la_font_no_es_del_programa_ho_diu_aixi(self):
        # 29-10-2026: el «no ho ha aconseguit» semblava una avaria pendent.
        s = self.font_que_falla({"arreglat": False, "de_la_font": True, "causa": "la estación no da datos.",
                                 "detall": "x" * 2000})
        self.assertEqual(len(self.avisos), 1)
        self.assertIn("És de la font, no del programa: la estación no da datos. Si dura", self.avisos[0])
        self.assertNotIn("xxx", self.avisos[0])
        self.assertEqual(self.registre()[-1]["resultat"], "de_la_font")
        self.assertTrue(s["avisat"])

    def test_si_no_ho_arregla_el_detall_va_al_registre(self):
        self.font_que_falla({"arreglat": False, "detall": "x" * 2000})
        self.assertNotIn("xxx", self.avisos[0])
        self.assertIn("no ho ha aconseguit", self.avisos[0])
        self.assertEqual(self.registre()[-1]["resultat"], "no_arreglat")

    def test_espera_que_la_sessio_ho_arregli_abans(self):
        R.comprova(ara=time.time())
        self.comprova([False], minuts=10)
        self.assertEqual(self.agents, [])
        self.assertEqual(self.registre(), [])

    def test_arregla_puja_la_versio_i_avisa_quan_es_publica(self):
        def agent(repo):
            escriu(repo, "programa.py", "X = 2\n")
            return {"arreglat": True, "causa": "una traducción sin hacer.", "commit": "Traducció que faltava"}
        R.comprova(ara=time.time())
        self.comprova([False, True], agent)
        self.assertEqual(len(self.agents), 1)
        nou = self.origen_main()
        self.assertNotEqual(nou, self.sha)
        missatge = git("log", "-1", "--format=%s", nou, cwd=self.origen)
        self.assertEqual(missatge, "Traducció que faltava (reparador, 3.170.1, ADR 0113)")
        self.assertIn("v3.170.1", git("tag", cwd=self.origen))
        self.assertEqual(self.registre()[-1]["resultat"], "arreglat")
        self.assertEqual(self.avisos, [])                       # aún no publicado
        with mock.patch.object(R, "publicat", lambda sha: sha == nou):
            R.comprova()
        self.assertEqual(self.avisos, ["Temps a Montflorit: las comprobaciones de la 3.170.0 fallaban "
                                       "(una traducción sin hacer). Un agente lo ha arreglado y ya está "
                                       "publicada la 3.170.1."])
        with mock.patch.object(R, "publicat", lambda sha: True):
            R.comprova()
        self.assertEqual(len(self.avisos), 1)                    # una sola vez

    def test_cada_commit_fallit_s_intenta_un_sol_cop(self):
        R.comprova(ara=time.time())
        self.comprova([False])
        self.comprova([False])
        self.assertEqual(len(self.agents), 1)
        self.assertEqual(self.registre()[-1]["resultat"], "no_arreglat")
        self.assertEqual(self.origen_main(), self.sha)

    def test_no_puja_si_toca_el_que_no_pot(self):
        def agent(repo):
            escriu(repo, "ruff.toml", "[lint]\nignore = ['F']\n")
            return {"arreglat": True, "causa": "x", "commit": "x"}
        R.comprova(ara=time.time())
        self.comprova([False, True], agent)
        self.assertEqual(self.origen_main(), self.sha)
        self.assertIn("ha tocado ruff.toml", self.registre()[-1]["motiu"])

    def test_no_puja_si_treu_o_salta_proves(self):
        def agent(repo):
            escriu(repo, "tests/test_a.py", "import unittest\n@unittest.skip('x')\ndef test_u():\n    pass\n")
            return {"arreglat": True, "causa": "x", "commit": "x"}
        R.comprova(ara=time.time())
        self.comprova([False, True], agent)
        self.assertEqual(self.origen_main(), self.sha)
        motiu = self.registre()[-1]["motiu"]
        self.assertIn("menos pruebas", motiu)
        self.assertIn("skip", motiu)

    def test_no_puja_si_continua_fallant(self):
        def agent(repo):
            escriu(repo, "programa.py", "X = 3\n")
            return {"arreglat": True, "causa": "x", "commit": "x"}
        R.comprova(ara=time.time())
        self.comprova([False, False], agent)
        self.assertEqual(self.origen_main(), self.sha)
        self.assertIn("sigue fallando", self.registre()[-1]["motiu"])

    def test_si_al_nas_passa_tot_github_les_repeteix_un_cop(self):
        R.comprova(ara=time.time())
        self.comprova([True])
        self.assertEqual(self.agents, [])
        nou = self.origen_main()
        self.assertEqual(git("diff", "--name-only", self.sha, nou, cwd=self.origen), "")
        self.assertEqual(self.registre()[-1]["resultat"], "repetides")
        # Si vuelve a fallar, no se insiste: queda para la próxima sesión.
        self.falla(nou)
        self.comprova([True])
        self.assertEqual(self.origen_main(), nou)
        self.assertEqual(self.registre()[-1]["resultat"], "no_arreglat")

    def test_no_fa_res_si_main_ha_canviat(self):
        escriu(self.treball, "programa.py", "X = 9\n")
        git("commit", "-qam", "un altre", cwd=self.treball)
        git("push", "-q", "origin", "HEAD:main", cwd=self.treball)
        R.comprova(ara=time.time())
        self.comprova([False])
        self.assertEqual(self.agents, [])
        self.assertEqual(self.registre()[-1]["resultat"], "main_ha_canviat")

    def test_versions_d_eslint_de_l_accio(self):
        arrel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paquets = R.versions_ci(arrel)
        self.assertEqual(sorted(p.split("@")[0] for p in paquets), ["eslint", "globals"])

    def test_les_comprovacions_son_les_de_github(self):
        arrel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(arrel, ".github", "workflows", "previsio.yml"), encoding="utf-8") as f:
            accio = f.read()
        self.assertIn("ruff check", accio)
        self.assertIn("eslint web montflorit eslint.config.mjs", accio)
        self.assertIn("unittest discover -s tests -b", accio)


if __name__ == "__main__":
    unittest.main()
