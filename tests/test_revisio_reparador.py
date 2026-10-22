# SPDX-License-Identifier: AGPL-3.0-or-later
"""El reparador (reparador.py, ADR 0113): les comprovacions, l'agent, ESLint,
el candau i els avisos, amb subprocess simulat: ni git, ni Claude, ni npm."""
import contextlib
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import reparador as R  # noqa: E402


def escriu(carpeta, nom, text):
    p = os.path.join(carpeta, nom)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def fet(stdout="", stderr="", codi=0):
    return subprocess.CompletedProcess([], codi, stdout=stdout, stderr=stderr)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.estat = os.path.join(self.dir.name, "estat")
        os.makedirs(self.estat)
        for p in (mock.patch.object(R, "ESTAT_DIR", self.estat),
                  mock.patch.object(R, "REGISTRE_DIR", os.path.join(self.estat, "registre"))):
            p.start()
            self.addCleanup(p.stop)

    def registre(self):
        try:
            with open(R.ruta("registre")) as f:
                return [json.loads(linia) for linia in f]
        except OSError:
            return []


class Comprovacions(unittest.TestCase):
    def test_les_tres_amb_l_hora_de_madrid(self):
        crides = []

        def executa(ordre, **kw):
            crides.append((ordre, kw))
            if ordre[0] == "ruff":
                return fet("x" * (R.SORTIDA_MAX + 50), "FINAL", codi=1)
            return fet("ok")

        res = R.comprovacions("/copia", executa)
        self.assertEqual([(c["nom"], c["ok"]) for c in res], [("proves", True), ("ruff", False), ("eslint", True)])
        # Només el final de la sortida, que és on és l'error.
        self.assertEqual(len(res[1]["sortida"]), R.SORTIDA_MAX)
        self.assertTrue(res[1]["sortida"].endswith("FINAL"))
        self.assertEqual([c[0] for c in crides], [o for _, o in R.COMPROVACIONS])
        self.assertTrue(all(kw["cwd"] == "/copia" and kw["env"]["TZ"] == "Europe/Madrid" for _, kw in crides))

    def test_una_que_no_es_pot_executar_es_una_fallada(self):
        def executa(ordre, **kw):
            if ordre[0] == "npx":
                raise FileNotFoundError("npx")
            raise subprocess.TimeoutExpired(ordre, 1800)

        res = R.comprovacions("/copia", executa)
        self.assertFalse(any(c["ok"] for c in res))
        self.assertTrue(all(c["sortida"].startswith("no s'ha pogut executar") for c in res))

    def test_incompliments(self):
        noms = {"programa.py", ".github/workflows/previsio.yml", "nas/Dockerfile", "web/nas/x.js"}  # nas/ només a l'arrel
        self.assertEqual(R.incompliments(noms, (10, 0), (10, 0)),
                         ["ha tocado .github/workflows/previsio.yml", "ha tocado nas/Dockerfile"])
        self.assertEqual(R.incompliments({"programa.py"}, (10, 1), (11, 1)), [])


class Versio(unittest.TestCase):
    def test_puja_nomes_el_parche(self):
        with tempfile.TemporaryDirectory() as d:
            escriu(d, "config.py", '# VERSION = "1.0.0" de mostra\nVERSION = "3.9.9"\nALTRE = "3.9.9"\n')
            self.assertEqual(R.versio(d), "3.9.9")
            self.assertEqual(R.puja_versio(d), "3.9.10")
            with open(os.path.join(d, "config.py")) as f:
                self.assertEqual(f.read(), '# VERSION = "1.0.0" de mostra\nVERSION = "3.9.10"\nALTRE = "3.9.9"\n')

    def test_proves_i_salts(self):
        with tempfile.TemporaryDirectory() as d:
            escriu(d, "tests/test_a.py", "def test_u():\n    pass\n    def test_dins():\n        pass\n")
            escriu(d, "tests/test_b.py", "@unittest.skipIf(x)\ndef test_c():\n    self.skipTest('y')\n")
            escriu(d, "tests/dades.json", "def test_no\n")
            self.assertEqual(R.proves(d), (3, 2))


class Agent(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        instr = os.path.join(self.dir.name, "instr.md")
        escriu(self.dir.name, "instr.md", "INSTRUCCIONS")
        p = mock.patch.object(R, "INSTRUCCIONS", instr)
        p.start()
        self.addCleanup(p.stop)

    def agent(self, r):
        with mock.patch.object(R.subprocess, "run", return_value=r) as run:
            res = R.agent("/copia", [{"nom": "ruff", "sortida": "F401 os"}])
        return res, run

    def test_la_resposta_de_l_agent(self):
        sortida = {"result": 'Fet.\n{"arreglat": true, "causa": "un import", "commit": "Treu un import"}',
                   "total_cost_usd": 1.5}
        res, run = self.agent(fet(json.dumps(sortida)))
        self.assertEqual((res["arreglat"], res["causa"], res["cost_usd"]), (True, "un import", 1.5))
        self.assertIsInstance(res["minuts"], float)
        ordre, kw = run.call_args[0][0], run.call_args[1]
        self.assertEqual(ordre[:2], ["claude", "-p"])
        self.assertEqual(ordre[ordre.index("--model") + 1], R.C.REPARADOR_MODEL)
        self.assertEqual(kw["cwd"], "/copia")
        self.assertEqual(kw["timeout"], R.AGENT_MAX_MIN * 60)
        self.assertTrue(kw["input"].startswith("INSTRUCCIONS"))
        self.assertIn("## Ha fallado: ruff\n\n```\nF401 os\n```", kw["input"])

    def test_sense_json_no_esta_arreglat(self):
        for result in ("No he pogut.", '{"arreglat": tru}', None):
            res, _ = self.agent(fet(json.dumps({"result": result})))
            self.assertFalse(res["arreglat"], result)

    def test_si_l_agent_no_respon_be(self):
        res, _ = self.agent(fet("Error: no hi ha token", "stderr"))
        self.assertFalse(res["arreglat"])
        self.assertIn("no hi ha token", res["detall"])
        self.assertNotIn("cost_usd", res)


class Eslint(unittest.TestCase):
    def test_s_instal_la_un_sol_cop_amb_les_versions_de_l_accio(self):
        with tempfile.TemporaryDirectory() as d:
            escriu(d, ".github/workflows/previsio.yml", "run: npm install eslint@9.39.1 globals@16.5.0\n")
            crides = []

            def run(ordre, **kw):
                crides.append(ordre)
                os.makedirs(os.path.join(d, "node_modules"), exist_ok=True)
                return fet()

            with mock.patch.object(R.subprocess, "run", run):
                R.instala_eslint(d)
                R.instala_eslint(d)
            self.assertEqual(len(crides), 1)
            self.assertEqual(crides[0][0], "npm")
            self.assertEqual(crides[0][-2:], ["eslint@9.39.1", "globals@16.5.0"])
            # Si l'acció canvia de versió, es torna a instal·lar.
            escriu(d, ".github/workflows/previsio.yml", "run: npm install eslint@9.40.0 globals@16.5.0\n")
            with mock.patch.object(R.subprocess, "run", run):
                R.instala_eslint(d)
            self.assertEqual(crides[-1][-2], "eslint@9.40.0")


class Git(unittest.TestCase):
    """Les ordres de git, simulades: només es mira què es demana."""

    def test_git_a_la_copia(self):
        with mock.patch.object(R.subprocess, "run", return_value=fet(" abc \n")) as run:
            self.assertEqual(R.git("/c", "rev-parse", "HEAD"), "abc")
        self.assertEqual(run.call_args[0][0], ["git", "-C", "/c", "rev-parse", "HEAD"])
        self.assertTrue(run.call_args[1]["check"])

    def test_no_puja_si_main_ha_canviat(self):
        ordres = []

        def git(repo, *args, **kw):
            ordres.append(args)
            return "un-altre" if args[0] == "rev-parse" else ""

        with mock.patch.object(R, "git", git), self.assertRaisesRegex(RuntimeError, "main ha cambiado"):
            R.puja("/c", "sha", "missatge", etiqueta="v1.0.1")
        self.assertFalse(any(a[0] in ("commit", "push", "tag") for a in ordres))

    def test_canviats_inclou_els_nous(self):
        def git(repo, *args, **kw):
            return "a.py\nb.py" if args[0] == "diff" else "nou.py\n"

        with mock.patch.object(R, "git", git):
            self.assertEqual(R.canviats("/c", "sha"), {"a.py", "b.py", "nou.py"})

    def test_publicat(self):
        with mock.patch.object(R.subprocess, "run", return_value=fet()) as run:
            self.assertTrue(R.publicat("abc"))
        self.assertEqual(run.call_args[0][0][-4:], ["merge-base", "--is-ancestor", "abc", "HEAD"])
        for error in (subprocess.CalledProcessError(1, "git"), subprocess.TimeoutExpired("git", 60)):
            with mock.patch.object(R.subprocess, "run", side_effect=error):
                self.assertFalse(R.publicat("abc"))

    def test_avisa_juanjo(self):
        with mock.patch.object(R.subprocess, "run") as run:
            R.avisa("Arreglat")
        ordre = run.call_args[0][0]
        self.assertEqual((ordre[0], ordre[-1]), ("avisar-juanjo", "Arreglat"))
        self.assertFalse(run.call_args[1]["check"])


class Repara(Base):
    def test_si_l_agent_canvia_la_versio_no_es_puja(self):
        copia = R.ruta("copia")
        escriu(copia, "config.py", 'VERSION = "3.170.0"\n')
        escriu(copia, "tests/test_a.py", "def test_u():\n    pass\n")

        def agent(repo, fallades):
            escriu(repo, "config.py", 'VERSION = "3.170.1"\n')
            return {"arreglat": True, "commit": "x", "cost_usd": 2.0, "minuts": 3.0}

        puja = mock.Mock()
        with mock.patch.object(R, "prepara_copia", return_value=True), \
                mock.patch.object(R, "comprovacions", return_value=[{"nom": "proves", "ok": False, "sortida": ""}]), \
                mock.patch.object(R, "agent", agent), mock.patch.object(R, "canviats", return_value={"config.py"}), \
                mock.patch.object(R, "puja", puja), contextlib.redirect_stdout(io.StringIO()):
            estat = {}
            R.repara("abc1234", estat)
        puja.assert_not_called()
        r = self.registre()[-1]
        self.assertEqual((r["resultat"], r["motiu"], r["versio"]), ("no_arreglat", "ha cambiado VERSION", "3.170.0"))
        self.assertEqual((r["cost_usd"], r["minuts"], r["fallades"]), (2.0, 3.0, ["proves"]))
        self.assertEqual(estat, {})

    def test_prepara_copia(self):
        ordres = []

        def git(repo, *args, **kw):
            ordres.append(args)
            return "sha" if args[0] == "rev-parse" else ""

        clona = mock.Mock(return_value=fet())
        with mock.patch.object(R, "git", git), mock.patch.object(R.subprocess, "run", clona), \
                mock.patch.object(R, "instala_eslint") as eslint:
            self.assertTrue(R.prepara_copia("sha"))
            self.assertEqual(clona.call_args[0][0][:3], ["git", "clone", "-q"])
            self.assertEqual([a[0] for a in ordres], ["fetch", "rev-parse", "reset", "clean"])
            eslint.assert_called_once_with(R.ruta("copia"))
            # Amb la còpia ja feta no es torna a clonar; si main ja és un altre, no es toca.
            os.makedirs(os.path.join(R.ruta("copia"), ".git"))
            clona.reset_mock()
            ordres.clear()
            self.assertFalse(R.prepara_copia("un-altre"))
            clona.assert_not_called()
            self.assertEqual([a[0] for a in ordres], ["fetch", "rev-parse"])


class Comprova(Base):
    def desplegament(self, sha):
        with open(R.ruta("desplegament"), "w") as f:
            json.dump({"proves_fallides": {"sha": sha}} if sha else {}, f)

    def test_si_ja_hi_ha_un_arreglo_en_marxa_no_fa_res(self):
        self.desplegament("abc")
        with mock.patch.object(R.fcntl, "flock", side_effect=BlockingIOError), \
                mock.patch.object(R, "repara") as repara:
            self.assertIsNone(R.comprova(ara=time.time() + 3600))
        repara.assert_not_called()
        self.assertFalse(os.path.exists(R.ruta("estat")))

    def test_un_arreglo_propi_que_torna_a_fallar_no_s_avisa(self):
        R.desa(R.ruta("estat"), {"avisa": {"sha": "nou", "text": "Arreglat"}, "propis": ["nou"]})
        self.desplegament("nou")
        avisos = []
        with mock.patch.object(R, "publicat", return_value=False), mock.patch.object(R, "avisa", avisos.append), \
                contextlib.redirect_stdout(io.StringIO()):
            R.comprova(ara=time.time())
        self.assertEqual(avisos, [])
        estat = R.llegeix(R.ruta("estat"))
        self.assertNotIn("avisa", estat)
        self.assertEqual(estat["intentats"], ["nou"])
        self.assertEqual(self.registre()[-1]["motiu"], "el commit del reparador también falla en GitHub")

    def test_l_avis_espera_que_es_publiqui(self):
        R.desa(R.ruta("estat"), {"avisa": {"sha": "nou", "text": "Arreglat"}})
        self.desplegament(None)
        with mock.patch.object(R, "publicat", return_value=False), mock.patch.object(R, "avisa") as avisa:
            R.comprova(ara=time.time())
        avisa.assert_not_called()
        self.assertEqual(R.llegeix(R.ruta("estat"))["avisa"]["sha"], "nou")

    def test_un_error_del_reparador_queda_apuntat(self):
        self.desplegament("abc1234")
        R.comprova(ara=1000)
        with mock.patch.object(R, "repara", side_effect=subprocess.CalledProcessError(128, "git")), \
                contextlib.redirect_stdout(io.StringIO()) as sortida:
            R.comprova(ara=1000 + R.ESPERA_MIN * 60)
        r = self.registre()[-1]
        self.assertEqual(r["resultat"], "no_arreglat")
        self.assertTrue(r["motiu"].startswith("error del reparador:"))
        self.assertIn("abc1234: no_arreglat (error del reparador", sortida.getvalue())
        # Intentat: no es torna a provar.
        with mock.patch.object(R, "repara") as repara:
            R.comprova(ara=1000 + R.ESPERA_MIN * 120)
        repara.assert_not_called()

    def test_mostra_estat(self):
        sortida = io.StringIO()
        with contextlib.redirect_stdout(sortida):
            R.mostra_estat()
        self.assertEqual(sortida.getvalue(), "{}\n(sin registro)\n")
        R.desa(R.ruta("estat"), {"intentats": ["abc"]})
        with contextlib.redirect_stdout(io.StringIO()):
            for i in range(7):
                R.apunta({"sha": f"sha{i}", "resultat": "no_arreglat"})
        sortida = io.StringIO()
        with contextlib.redirect_stdout(sortida):
            R.mostra_estat()
        linies = sortida.getvalue().splitlines()
        self.assertEqual(json.loads("\n".join(linies[:-5])), {"intentats": ["abc"]})
        self.assertEqual([json.loads(x)["sha"] for x in linies[-5:]], [f"sha{i}" for i in range(2, 7)])


class Ordres(unittest.TestCase):
    def executa(self, *args):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        sortida = io.StringIO()
        with mock.patch.dict(os.environ, {"ESTAT_DIR": d.name, "REGISTRE_DIR": os.path.join(d.name, "r")}), \
                mock.patch.object(sys, "argv", ["reparador.py", *args]), mock.patch("subprocess.run") as run, \
                contextlib.redirect_stdout(sortida):
            runpy.run_path(os.path.join(ARREL, "reparador.py"), run_name="__main__")
        return sortida.getvalue(), run, d.name

    def test_comprova_sense_res_fallit(self):
        text, run, d = self.executa("comprova")
        self.assertEqual(text, "")
        run.assert_not_called()
        self.assertTrue(os.path.exists(os.path.join(d, "reparador.lock")))

    def test_estat_i_ajuda(self):
        self.assertEqual(self.executa("estat")[0], "{}\n(sin registro)\n")
        with self.assertRaises(SystemExit) as e:
            self.executa()
        self.assertEqual(e.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
