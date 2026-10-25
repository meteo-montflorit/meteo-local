#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""El reparador (ADR 0113): si el último commit de main no pasa las
comprobaciones de GitHub, un agente con IA lo arregla en el NAS.

El NAS solo despliega un commit con las comprobaciones en verde
(desplegament.py, ADR 0038); si fallan, la web sigue con la versión anterior
y antes solo quedaba una línea en el registro. Juanjo (20-10-2026): «en lugar
de avisarme a mi no puede abrir un agente de ia que se encargue de
arreglarlo?».

El reloj del NAS llama a `comprova` cada minuto, aparte (no frena las
pasadas). Con un commit fallido nuevo en desplegament.json:

1. Espera ESPERA_MIN minutos: la sesión que lo subió puede estar arreglándolo.
   Si main cambia mientras tanto, no hace nada (el commit nuevo se juzga solo).
2. En una copia aparte (no la que publica la web), repite las comprobaciones
   de GitHub con las mismas órdenes. Si pasan todas, el fallo no era del
   código: sube un commit vacío para que GitHub las repita, una sola vez.
3. Si fallan, lanza Claude Code (C.REPARADOR_MODEL, como mucho
   AGENT_MAX_MIN minutos) con reparador-instruccions.md y la salida de lo que
   ha fallado.
4. El programa, no el agente, comprueba el resultado: que las comprobaciones
   pasan, que no se han tocado los archivos de PROHIBITS ni se han quitado o
   saltado pruebas y que main no ha cambiado. Entonces sube la versión de
   parche, hace el commit, la etiqueta y lo sube.
5. Cuando el NAS despliega el arreglo, avisa a Juanjo con un mensaje breve,
   solo informativo.

Un commit del propio reparador que vuelve a fallar no se repara otra vez. Lo
que no se arregla queda en el registro (REGISTRE_DIR/reparador.jsonl) con
`"resultat": "no_arreglat"`: el aviso de inicio de sesión de Juanjo lo lee y
la siguiente sesión lo arregla. Cada commit fallido se intenta una sola vez.

Uso:
  python3 reparador.py comprova     lo que hace el reloj del NAS cada minuto
  python3 reparador.py estat        el estado y los últimos intentos
"""
import fcntl
import json
import os
import re
import subprocess
import sys
import time

import config as C
import hora as H
from desplegament import llegeix, desa

ARREL = os.path.dirname(os.path.abspath(__file__))
ESTAT_DIR = os.environ.get("ESTAT_DIR", "/estat")
REGISTRE_DIR = os.environ.get("REGISTRE_DIR", os.path.join(ESTAT_DIR, "registre"))
URL_REPO = "git@github.com:meteo-montflorit/meteo-local.git"
INSTRUCCIONS = os.path.join(ARREL, "reparador-instruccions.md")
ESPERA_MIN = 30
AGENT_MAX_MIN = 45
COMPROVACIO_MAX_MIN = 30
SORTIDA_MAX = 6000            # caracteres de cada comprobación fallida para el agente
# Lo que el agente no puede tocar: lo que decide qué se comprueba y cómo se
# despliega (reparador-instruccions.md).
PROHIBITS = (".github/", "ruff.toml", "eslint.config.mjs", ".coveragerc", "desplegament.py",
             "reparador.py", "reparador-instruccions.md", "nas/")
AUTOR = ["-c", "user.name=meteo-local (NAS)", "-c", "user.email=meteo-local@users.noreply.github.com"]
# Las mismas órdenes que la acción de GitHub (.github/workflows/previsio.yml).
COMPROVACIONS = [
    ("proves", ["python3", "-m", "unittest", "discover", "-s", "tests", "-b"]),
    ("ruff", ["ruff", "check", "."]),
    ("eslint", ["npx", "--no-install", "eslint", "web", "montflorit", "eslint.config.mjs"]),
]


def ruta(nom):
    return {"estat": os.path.join(ESTAT_DIR, "reparador.json"),
            "lock": os.path.join(ESTAT_DIR, "reparador.lock"),
            "copia": os.path.join(ESTAT_DIR, "reparador", "repo"),
            "desplegament": os.path.join(ESTAT_DIR, "desplegament.json"),
            "registre": os.path.join(REGISTRE_DIR, "reparador.jsonl")}[nom]


def git(repo, *args, timeout=300):
    return subprocess.run(["git", "-C", repo, *args], check=True, timeout=timeout, text=True,
                          capture_output=True).stdout.strip()


def apunta(registre):
    os.makedirs(REGISTRE_DIR, exist_ok=True)
    registre = {"hora": H.clau(H.ara()), **registre}
    with open(ruta("registre"), "a", encoding="utf-8") as f:
        f.write(json.dumps(registre, ensure_ascii=False) + "\n")
    print(f"{registre.get('sha', '')[:7]}: {registre['resultat']}"
          + (f" ({registre['motiu']})" if registre.get("motiu") else ""))


def avisa(text):
    subprocess.run(["avisar-juanjo", "--de", "Temps a Montflorit (agente reparador)", "--asunto", "meteo-local",
                    text], check=False, timeout=120)


# --- Lo que se comprueba -------------------------------------------------------------

def versio(repo):
    with open(os.path.join(repo, "config.py"), encoding="utf-8") as f:
        return re.search(r'^VERSION = "([\d.]+)"', f.read(), re.M).group(1)


def puja_versio(repo):
    """Sube la versión de parche en config.py y la devuelve."""
    p = os.path.join(repo, "config.py")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    v = versio(repo).split(".")
    nova = ".".join(v[:-1] + [str(int(v[-1]) + 1)])
    with open(p, "w", encoding="utf-8") as f:
        f.write(re.sub(r'^VERSION = "[\d.]+"', f'VERSION = "{nova}"', text, count=1, flags=re.M))
    return nova


def versions_ci(repo):
    """Las versiones de ESLint y globals de la acción de GitHub, para usar las mismas."""
    with open(os.path.join(repo, ".github", "workflows", "previsio.yml"), encoding="utf-8") as f:
        return re.findall(r"\b((?:eslint|globals)@[\d.]+)", f.read())


def comprovacions(repo, executa=subprocess.run):
    """Las comprobaciones de GitHub en la copia: [{nom, ok, sortida}]."""
    res = []
    entorn = {**os.environ, "TZ": "Europe/Madrid"}
    for nom, ordre in COMPROVACIONS:
        try:
            r = executa(ordre, cwd=repo, env=entorn, capture_output=True, text=True,
                        timeout=COMPROVACIO_MAX_MIN * 60)
            res.append({"nom": nom, "ok": r.returncode == 0, "sortida": (r.stdout + r.stderr)[-SORTIDA_MAX:]})
        except (OSError, subprocess.TimeoutExpired) as ex:
            res.append({"nom": nom, "ok": False, "sortida": f"no s'ha pogut executar: {ex}"})
    return res


def proves(repo):
    """Cuántas pruebas hay y cuántas veces se salta alguna, en tests/."""
    n = salts = 0
    carpeta = os.path.join(repo, "tests")
    for nom in os.listdir(carpeta):
        if nom.endswith(".py"):
            with open(os.path.join(carpeta, nom), encoding="utf-8") as f:
                text = f.read()
            n += len(re.findall(r"^\s*def test", text, re.M))
            salts += len(re.findall(r"\bskip", text, re.I))
    return n, salts


def canviats(repo, base):
    """Los archivos que difieren de base, también los nuevos sin añadir."""
    noms = set(git(repo, "diff", "--name-only", base).splitlines())
    noms |= set(git(repo, "ls-files", "--others", "--exclude-standard").splitlines())
    return {n for n in noms if n}


def incompliments(noms, abans, despres):
    """Lo que el agente no podía hacer: [motivo]."""
    res = [f"ha tocado {n}" for n in sorted(noms) if any(n == p or n.startswith(p) for p in PROHIBITS)]
    if despres[0] < abans[0]:
        res.append(f"hay menos pruebas ({abans[0]} → {despres[0]})")
    if despres[1] > abans[1]:
        res.append("ha añadido pruebas saltadas (skip)")
    return res


# --- El agente -----------------------------------------------------------------------

def agent(repo, fallades):
    """Claude Code en la copia. Devuelve su respuesta final (dict)."""
    with open(INSTRUCCIONS, encoding="utf-8") as f:
        text = f.read()
    for c in fallades:
        text += f"\n\n## Ha fallado: {c['nom']}\n\n```\n{c['sortida']}\n```\n"
    t0 = time.time()
    r = subprocess.run(["claude", "-p", "--model", C.REPARADOR_MODEL, "--output-format", "json",
                        "--permission-mode", "bypassPermissions"],
                       input=text, cwd=repo, capture_output=True, text=True, timeout=AGENT_MAX_MIN * 60)
    try:
        sortida = json.loads(r.stdout)
    except ValueError:
        return {"arreglat": False, "detall": f"el agente no ha respondido bien: {(r.stdout + r.stderr)[-500:]}"}
    m = re.search(r"\{.*\}", sortida.get("result") or "", re.S)
    try:
        res = json.loads(m.group(0)) if m else {}
    except ValueError:
        res = {}
    res.setdefault("arreglat", False)
    res["cost_usd"] = sortida.get("total_cost_usd")
    res["minuts"] = round((time.time() - t0) / 60, 1)
    return res


# --- El arreglo ----------------------------------------------------------------------

def prepara_copia(sha):
    """La copia aparte, en el commit fallido y limpia. False si main ya no está ahí."""
    copia = ruta("copia")
    if not os.path.isdir(os.path.join(copia, ".git")):
        os.makedirs(os.path.dirname(copia), exist_ok=True)
        subprocess.run(["git", "clone", "-q", URL_REPO, copia], check=True, timeout=600)
    git(copia, "fetch", "-q", "origin", "main", "--tags")
    if git(copia, "rev-parse", "origin/main") != sha:
        return False
    git(copia, "reset", "-q", "--hard", sha)
    git(copia, "clean", "-q", "-fdx", "-e", "node_modules")
    instala_eslint(copia)
    return True


def instala_eslint(copia):
    """ESLint, con las versiones de la acción (node_modules no se sube)."""
    paquets = versions_ci(copia)
    marca = os.path.join(copia, "node_modules", ".reparador")
    try:
        with open(marca) as f:
            if f.read() == " ".join(paquets):
                return
    except OSError:
        pass
    subprocess.run(["npm", "install", "--no-save", "--no-package-lock", "--no-audit", "--no-fund", *paquets],
                   cwd=copia, check=True, capture_output=True, timeout=600)
    with open(marca, "w") as f:
        f.write(" ".join(paquets))


def puja(copia, sha, missatge, etiqueta=None):
    """Commit y push a main, solo si main sigue en sha. Devuelve el sha nuevo."""
    git(copia, "fetch", "-q", "origin", "main")
    if git(copia, "rev-parse", "origin/main") != sha:
        raise RuntimeError("main ha cambiado mientras tanto")
    git(copia, "add", "-A")
    git(copia, *AUTOR, "commit", "-q", "--allow-empty", "-m", missatge)
    nou = git(copia, "rev-parse", "HEAD")
    if etiqueta:
        git(copia, "tag", etiqueta)
    git(copia, "push", "-q", "origin", "HEAD:main")
    if etiqueta:
        git(copia, "push", "-q", "origin", etiqueta)
    return nou


def repara(sha, estat):
    copia = ruta("copia")
    if not prepara_copia(sha):
        apunta({"sha": sha, "resultat": "main_ha_canviat"})
        return
    fallida = versio(copia)
    fallades = [c for c in comprovacions(copia) if not c["ok"]]
    if not fallades:
        # En el NAS pasa todo: no era el código. GitHub las repite una vez.
        nou = puja(copia, sha, "Torna a passar les comprovacions: a GitHub havien fallat i al NAS passen "
                               "(reparador, ADR 0113)")
        estat.setdefault("propis", []).append(nou)
        apunta({"sha": sha, "resultat": "repetides", "nou": nou})
        return
    abans = proves(copia)
    res = agent(copia, fallades)
    motius = []
    if not res.get("arreglat"):
        motius.append("el agente no lo ha arreglado")
    else:
        motius += incompliments(canviats(copia, sha), abans, proves(copia))
        if versio(copia) != fallida:
            motius.append("ha cambiado VERSION")      # la sube el programa
        if not motius:
            motius += [f"sigue fallando: {c['nom']}" for c in comprovacions(copia) if not c["ok"]]
    if motius:
        apunta({"sha": sha, "resultat": "no_arreglat", "versio": fallida, "motiu": "; ".join(motius),
                "fallades": [c["nom"] for c in fallades], "detall": res.get("detall"),
                "cost_usd": res.get("cost_usd"), "minuts": res.get("minuts")})
        return
    nova = puja_versio(copia)
    missatge = f"{res.get('commit') or 'Arreglat el que feia fallar les comprovacions'} (reparador, {nova}, ADR 0113)"
    nou = puja(copia, sha, missatge, etiqueta=f"v{nova}")
    estat.setdefault("propis", []).append(nou)
    causa = (res.get("causa") or "").rstrip(".")
    estat["avisa"] = {"sha": nou, "text": f"Temps a Montflorit: las comprobaciones de la {fallida} fallaban"
                      + (f" ({causa})" if causa else "")
                      + f". Un agente lo ha arreglado y ya está publicada la {nova}."}
    apunta({"sha": sha, "resultat": "arreglat", "nou": nou, "versio": fallida, "versio_nova": nova,
            "fallades": [c["nom"] for c in fallades], "detall": res.get("detall"),
            "cost_usd": res.get("cost_usd"), "minuts": res.get("minuts")})


def publicat(sha):
    """Si la copia que publica la web ya incluye sha."""
    try:
        subprocess.run(["git", "-C", ARREL, "merge-base", "--is-ancestor", sha, "HEAD"], check=True,
                       capture_output=True, timeout=60)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def comprova(ara=None):
    """Lo de cada minuto: avisar del arreglo publicado y atender un fallo nuevo."""
    ara = ara or time.time()
    os.makedirs(ESTAT_DIR, exist_ok=True)
    with open(ruta("lock"), "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return                                    # ya hay un arreglo en marcha
        estat = llegeix(ruta("estat"))
        fallit = (llegeix(ruta("desplegament")).get("proves_fallides") or {}).get("sha")
        if estat.get("avisa"):
            sha = estat["avisa"]["sha"]
            if publicat(sha):
                avisa(estat.pop("avisa")["text"])
            elif fallit == sha:
                estat.pop("avisa")                    # lo apunta la rama de los commits propios
            desa(ruta("estat"), estat)
        intentats = estat.setdefault("intentats", [])
        if not fallit or fallit in intentats:
            return
        vist = estat.setdefault("vist", {})
        vist.setdefault(fallit, ara)
        desa(ruta("estat"), estat)
        if fallit in estat.get("propis", []):
            intentats.append(fallit)
            desa(ruta("estat"), estat)
            apunta({"sha": fallit, "resultat": "no_arreglat",
                    "motiu": "el commit del reparador también falla en GitHub"})
            return
        if ara - vist[fallit] < ESPERA_MIN * 60:
            return
        intentats.append(fallit)
        estat["intentats"] = intentats[-50:]
        estat["vist"] = {k: v for k, v in vist.items() if k in estat["intentats"] or k == fallit}
        desa(ruta("estat"), estat)
        try:
            repara(fallit, estat)
        except Exception as ex:
            apunta({"sha": fallit, "resultat": "no_arreglat", "motiu": f"error del reparador: {ex}"})
        finally:
            desa(ruta("estat"), estat)


def mostra_estat():
    print(json.dumps(llegeix(ruta("estat")), ensure_ascii=False, indent=1))
    try:
        with open(ruta("registre"), encoding="utf-8") as f:
            for linia in f.readlines()[-5:]:
                print(linia.rstrip())
    except OSError:
        print("(sin registro)")


if __name__ == "__main__":
    ordre = sys.argv[1] if len(sys.argv) > 1 else ""
    if ordre == "comprova":
        comprova()
    elif ordre == "estat":
        mostra_estat()
    else:
        print(__doc__)
        sys.exit(1)
