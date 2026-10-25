#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Servidor de reserva de Temps a Montflorit en IONOS (ADR 0032).

El NAS calcula la web y sube montflorit.json a IONOS cada 15 minutos (cada 6
con avisos). Si se va la luz en casa, el NAS se cuelga o el contenedor falla,
la web se queda sin datos justo cuando más falta hacen (un temporal). Este
programa vive en el hosting de IONOS, fuera de casa, y lo ejecuta el cron cada
5 minutos:

- **vigila**: si los datos del NAS tienen más de LLINDAR_MIN minutos, calcula
  con el mismo programa (casa.py), sube los datos marcados como «reserva» y
  manda los avisos por Telegram (peligro, lluvia y riera) en lugar del NAS. Al
  activarse y cuando el NAS vuelve, avisa a Juanjo. Si el NAS vuelve mientras
  calcula, no pisa sus datos.
- **prova**: una vez al día, calcula sin publicar ni avisar y comprueba el
  resultado; si falla, avisa. Así una reserva rota no se descubre el día que
  hace falta.

Los avisos a Juanjo pasan por avis_privat.py: si Telegram no los acepta, se
reintentan en cada vuelta mientras tengan sentido (ADR 0038). Y la copia del
repositorio solo avanza hasta el último commit con las pruebas de GitHub en
verde (desplegament.py, ADR 0038).

Sin la estación de casa (sus claves están en el NAS) ni el modelo aprendido
(usa el del archivo, que va en el repositorio). numpy, con un solo hilo: el
hosting limita la memoria.

Uso (con el Python del entorno de la reserva):
  reserva.py vigila      lo que hace el cron
  reserva.py prova       la comprobación diaria
  reserva.py estat       cómo está
"""
import datetime as dt
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

# La hora local de Montflorit, pase lo que pase con la del hosting: casa.py
# compara horas locales de Open-Meteo con la del sistema.
os.environ.setdefault("TZ", "Europe/Madrid")
time.tzset()

BASE = os.environ.get("RESERVA_DIR", os.path.expanduser("~/.meteo-reserva"))
REPO = os.path.join(BASE, "repo")
ESTAT = os.path.join(BASE, "estat")
DADES = os.environ.get("MONTFLORIT_JSON", os.path.expanduser("~/app/meteo-local/montflorit.json"))
LLINDAR_MIN = int(os.environ.get("RESERVA_LLINDAR_MIN", "35"))
ESTAT_RESERVA = os.path.join(ESTAT, "reserva.json")
REGISTRE = os.path.join(BASE, "registre.log")
PYTHON = sys.executable
AVISA = os.path.join(BASE, "bin", "avisar-juanjo")
sys.path.insert(0, REPO)
try:
    import avis_privat as AP
    AP.ORDRE, AP.PENDENTS = AVISA, os.path.join(ESTAT, "avisos-pendents.jsonl")
except ImportError:            # copia del repositorio anterior a la cola
    AP = None
ENTORN = dict(os.environ,
              OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
              REGISTRE_DIR=os.path.join(ESTAT, "registre"),
              APRENENTATGE_DIR=os.path.join(ESTAT, "aprenentatge"),
              RADAR_CACHE=os.path.join(ESTAT, "radar-cache"),
              CACHE_WEB=os.path.join(ESTAT, "cache-web"),
              TRENS_DIR=ESTAT,
              POLLEN_DIR=ESTAT,           # el pol·len, guardat 3 hores (pollen.py)
              AIRE_DIR=ESTAT,             # la correcció de l'aire, del dia (aire.py)
              PATH=os.path.join(BASE, "bin") + os.pathsep + os.environ.get("PATH", ""))


def ara():
    # L'hora de Madrid, sigui quina sigui la del sistema (ADR 0128).
    return dt.datetime.now(ZoneInfo("Europe/Madrid"))


def cadenat():
    """Una sola vuelta a la vez: el cron entra cada 5 minutos y un cálculo
    puede durar más (numpy a un hilo). Devuelve el archivo bloqueado, que hay
    que conservar hasta acabar, o None si otra vuelta sigue en marcha."""
    os.makedirs(BASE, exist_ok=True)
    f = open(os.path.join(BASE, "reserva.lock"), "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def apunta(text):
    with open(REGISTRE, "a", encoding="utf-8") as f:
        f.write(f"{ara():%F %T}  {text}\n")


def avisa(text):
    apunta("avís: " + text.splitlines()[0])
    if os.environ.get("RESERVA_SENSE_AVISOS"):
        print("(sense avisar)", text)
        return
    if AP is None:
        subprocess.run([AVISA, "--asunto", "meteo-local", text], check=False)
    elif not AP.envia(text):
        apunta("Telegram no ha acceptat l'avís: queda pendent")


def reintenta_avisos():
    if AP is None or os.environ.get("RESERVA_SENSE_AVISOS"):
        return
    entregats, caducats, queden = AP.reintenta()
    for p in entregats:
        apunta(f"avís entregat en reintentar (de les {AP.H.local(p['hora']):%H:%M}): {p['text'][:60]}")
    for p in caducats:
        apunta(f"avís caducat sense entregar (de les {AP.H.local(p['hora']):%H:%M}): {p['text'][:60]}")


def llegeix_estat():
    try:
        with open(ESTAT_RESERVA, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"activa": False}


def desa_estat(estat):
    with open(ESTAT_RESERVA + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estat, f, ensure_ascii=False)
    os.replace(ESTAT_RESERVA + ".tmp", ESTAT_RESERVA)


def dades_publicades():
    """(dades, minuts des que es van pujar) o (None, None)."""
    try:
        with open(DADES, encoding="utf-8") as f:
            dades = json.load(f)
        return dades, (time.time() - os.path.getmtime(DADES)) / 60
    except (OSError, ValueError):
        return None, None


def calcula(carpeta):
    """casa.py i les dades públiques, a carpeta. Retorna les dades."""
    anterior = os.path.join(ESTAT, "casa.json")
    casa = os.path.join(carpeta, "casa.json")
    publica = os.path.join(carpeta, "montflorit.json")
    subprocess.run([PYTHON, "casa.py", "--json", casa, "--anterior", anterior], cwd=REPO, env=ENTORN,
                   check=True, timeout=900, stdout=subprocess.DEVNULL)
    # La riera abierta, del último avisos.json publicado (ADR 0093).
    subprocess.run([PYTHON, "montflorit.py", "dades", casa, publica, DADES.replace("montflorit.json", "avisos.json")],
                   cwd=REPO, env=ENTORN, check=True, timeout=120)
    with open(publica, encoding="utf-8") as f:
        dades = json.load(f)
    if not dades.get("hores"):
        raise RuntimeError("sense previsió hora a hora: " + "; ".join(dades.get("errors") or []))
    return casa, dades


def actualitza_repo(estat):
    """Posa al dia la còpia del repositori, com a molt un cop per hora, i
    només fins a l'últim commit amb les proves de GitHub en verd
    (desplegament.py); mentre s'espera unes proves, a cada volta."""
    pendent = estat.get("desplegament", {}).get("proves_pendents")
    if not pendent and time.time() - estat.get("pull", 0) < 3600:
        return
    estat["pull"] = time.time()
    try:
        import desplegament
        desplegament.actualitza(REPO, estat.setdefault("desplegament", {}), apunta)
    except ImportError:
        subprocess.run(["git", "-C", REPO, "pull", "-q", "--ff-only"], check=False, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as ex:
        apunta(f"no s'ha pogut posar al dia el repositori: {ex}")


def vigila():
    pany = cadenat()
    if pany is None:
        return          # la vuelta anterior aún no ha acabado
    os.makedirs(os.path.join(ESTAT, "registre"), exist_ok=True)
    reintenta_avisos()
    estat = llegeix_estat()
    dades, edat = dades_publicades()
    nas_viu = dades is not None and not dades.get("reserva") and edat <= LLINDAR_MIN
    if nas_viu:
        if estat.get("activa"):
            estat["activa"] = False
            desa_estat(estat)
            avisa("El NAS torna a publicar Temps a Montflorit: la reserva d'IONOS s'atura.")
        return
    # Al ritme de la pàgina: cada 15 minuts, o cada 6 en mode avís.
    cada = ((dades or {}).get("horari") or {}).get("cada_min", 15) if estat.get("activa") else 0
    if estat.get("activa") and time.time() - estat.get("calcul", 0) < (cada - 1) * 60:
        return
    actualitza_repo(estat)
    inici = time.time()
    with tempfile.TemporaryDirectory(dir=BASE) as tmp:
        try:
            casa, noves = calcula(tmp)
        except Exception as ex:
            apunta(f"ha fallat el càlcul: {ex}")
            if not estat.get("error_avisat"):
                avisa(f"La reserva d'IONOS ha intentat publicar Temps a Montflorit i no ha pogut: {ex}")
                estat["error_avisat"] = True
                desa_estat(estat)
            return
        # Si el NAS ha tornat mentre es calculava, no se'n trepitgen les dades.
        actuals, _ = dades_publicades()
        if actuals is not None and not actuals.get("reserva") and os.path.getmtime(DADES) > inici:
            apunta("el NAS ha publicat mentre calculava: no es puja res")
            return
        noves["reserva"] = True
        nou = DADES + ".reserva"
        with open(nou, "w", encoding="utf-8") as f:
            json.dump(noves, f, ensure_ascii=False, separators=(",", ":"))
        os.chmod(nou, 0o604)
        os.replace(nou, DADES)
        shutil.copy(casa, os.path.join(ESTAT, "casa.json"))
    estat.update(calcul=time.time(), error_avisat=False)
    if not estat.get("activa"):
        estat.update(activa=True, des_de=ara().isoformat(timespec="minutes"))
        darrera = dades and dades.get("generat", "")[11:16]
        avisa("Temps a Montflorit: el NAS no publica" + (f" des de les {darrera}" if darrera else "")
              + ". Ara calcula i publica la reserva d'IONOS, amb els avisos de pluja, perill i riera"
              " (sense l'estació de casa).")
    desa_estat(estat)
    apunta("publicat")
    # Els avisos per al bot i el canal (ADR 0034), al costat de les dades.
    nou = DADES.replace("montflorit.json", "avisos.json.reserva")
    # El historial de «Perill» se une con el publicado, el del NAS (ADR 0071).
    publicat = DADES.replace("montflorit.json", "avisos.json")
    if subprocess.run([PYTHON, "avisos_bot.py", os.path.join(ESTAT, "casa.json"), nou, publicat], cwd=REPO, env=ENTORN,
                      check=False, timeout=120, stdout=subprocess.DEVNULL).returncode == 0:
        os.chmod(nou, 0o604)
        os.replace(nou, DADES.replace("montflorit.json", "avisos.json"))
    # El registre dels avisos (perill, pluja i riera), en lloc del NAS: des del
    # 08-10-2026 ja no s'envien a Juanjo (ADR 0048).
    for programa in ("riscos.py", "pluja_arriba.py", "riera.py"):
        subprocess.run([PYTHON, programa, "avisa", os.path.join(ESTAT, "casa.json")], cwd=REPO, env=ENTORN,
                       check=False, timeout=120, stdout=subprocess.DEVNULL)


def prova():
    """Calcula sense publicar ni avisar; si falla, ho diu."""
    pany = cadenat()
    if pany is None:
        apunta("prova ajornada: hi ha una volta en marxa")
        return
    os.makedirs(os.path.join(ESTAT, "registre"), exist_ok=True)
    estat = llegeix_estat()
    estat["pull"] = 0
    actualitza_repo(estat)
    desa_estat(estat)
    with tempfile.TemporaryDirectory(dir=BASE) as tmp:
        try:
            _, dades = calcula(tmp)
            generat = dt.datetime.fromisoformat(dades["generat"])
            if ara() - generat > dt.timedelta(minutes=30):
                raise RuntimeError(f"dades velles ({dades['generat']})")
            apunta(f"prova correcta: {len(dades['hores'])} hores, errors: {dades.get('errors') or 'cap'}")
        except Exception as ex:
            apunta(f"prova fallida: {ex}")
            avisa(f"La prova diària de la reserva d'IONOS de Temps a Montflorit ha fallat: {ex}. "
                  "Si el NAS caigués, la web es quedaria sense dades.")


def mostra_estat():
    estat = llegeix_estat()
    dades, edat = dades_publicades()
    origen = "reserva" if dades and dades.get("reserva") else "NAS"
    print(f"Dades publicades: {origen}, fa {edat:.0f} min" if edat is not None else "Sense dades publicades")
    print("Reserva activa des de " + estat["des_de"] if estat.get("activa") else "Reserva en espera")
    try:
        with open(REGISTRE, encoding="utf-8") as f:
            print("".join(f.readlines()[-5:]), end="")
    except OSError:
        pass


if __name__ == "__main__":
    ordre = sys.argv[1] if len(sys.argv) > 1 else ""
    {"vigila": vigila, "prova": prova, "estat": mostra_estat}.get(ordre, lambda: (print(__doc__), sys.exit(1)))()
