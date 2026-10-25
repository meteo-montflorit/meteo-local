# SPDX-License-Identifier: AGPL-3.0-or-later
"""La migració dels registres a UTC (ADR 0128), una sola vegada.

Fins a la 3.200.0 els registres desaven l'hora de Madrid sense zona
(«2026-10-25T03:00»), amb el desfasament només a l'hora que es repeteix a
l'octubre («…T02:00+02:00»), i alguns amb el desfasament sempre. Des de la
3.201.0 tot es desa en UTC amb «Z». El programa entén igualment les formes
d'abans (hora.llegeix), però els registres es comparen i s'ordenen com a text:
per això es migren tots d'un cop.

- Abans de tocar res, una còpia de tot el registre comprimida al costat
  (registre-abans-utc-AAAAMMDD-HHMM.tar.gz).
- Als CSV i als JSONL, cada hora (valor o clau) passa a UTC; les dates soles
  («2026-10-25», dies de Madrid) i la resta, tal com són. Les files dels CSV
  per hores queden ordenades.
- Una marca (registre/.utc) diu que ja s'ha fet: la segona vegada no fa res.

    python3 migra_utc.py              migra el registre del NAS (REGISTRE_DIR)
    python3 migra_utc.py CARPETA      migra una carpeta (per provar-ho en una còpia)
"""
import csv
import fcntl
import glob
import json
import os
import sys
import tarfile

import hora as H

REGISTRE = os.environ.get("REGISTRE_DIR", "/estat/registre")
MARCA = ".utc"
def valor(v):
    """Una hora de les d'abans, en UTC; la resta, igual."""
    return H.interna(v) if isinstance(v, str) else v


objecte = H.interna


def migra_csv(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        camps = lector.fieldnames
        files = [{k: valor(v) for k, v in r.items()} for r in lector]
    if not camps:
        return 0
    # Els CSV per hores, ordenats per «fins» (ja tot en UTC, el text s'ordena bé).
    if "fins" in camps:
        files.sort(key=lambda r: r.get("fins") or "")
    with open(ruta + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=camps)
        w.writeheader()
        w.writerows(files)
    os.replace(ruta + ".tmp", ruta)
    return len(files)


def migra_jsonl(ruta):
    linies = []
    with open(ruta, encoding="utf-8") as f:
        for l in f:
            if not l.strip():
                continue
            try:
                linies.append(json.dumps(objecte(json.loads(l)), ensure_ascii=False))
            except ValueError:
                linies.append(l.rstrip("\n"))         # una línia trencada es queda com era
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        f.write("".join(l + "\n" for l in linies))
    os.replace(ruta + ".tmp", ruta)
    return len(linies)


def migra(carpeta=REGISTRE, ara=None):
    """Migra la carpeta si no ho està. Torna què ha fet ({fitxer: files}) o None
    si ja estava migrada o no hi ha registre."""
    if not os.path.isdir(carpeta) or os.path.exists(os.path.join(carpeta, MARCA)):
        return None
    with open(os.path.join(carpeta, ".utc.lock"), "w") as cadenat:
        fcntl.flock(cadenat, fcntl.LOCK_EX)
        if os.path.exists(os.path.join(carpeta, MARCA)):
            return None
        ara = ara or H.ara()
        copia = os.path.join(os.path.dirname(carpeta.rstrip("/")),
                             f"registre-abans-utc-{H.local(ara):%Y%m%d-%H%M}.tar.gz")
        with tarfile.open(copia, "w:gz") as tar:
            tar.add(carpeta, arcname=os.path.basename(carpeta.rstrip("/")))
        fet = {}
        for ruta in sorted(glob.glob(os.path.join(carpeta, "**", "*.csv"), recursive=True)):
            fet[os.path.relpath(ruta, carpeta)] = migra_csv(ruta)
        for ruta in sorted(glob.glob(os.path.join(carpeta, "**", "*.jsonl"), recursive=True)):
            fet[os.path.relpath(ruta, carpeta)] = migra_jsonl(ruta)
        with open(os.path.join(carpeta, MARCA), "w", encoding="utf-8") as f:
            json.dump({"fet": H.clau(ara), "copia": os.path.basename(copia), "fitxers": fet}, f, ensure_ascii=False)
        return fet


MARCA_AEMET = ".utc-aemet"


def corregeix_elaborat_aemet(carpeta=REGISTRE):
    """Una sola vegada: l'hora d'elaboració de les previsions d'AEMET ja desades
    (previsio-oficial-*.jsonl). AEMET la dona en UTC sense zona i fins a la
    3.201.0 es llegia com a hora de Madrid: la correcta és la de rellotge de
    Madrid de la desada, presa com a UTC. Torna les línies corregides, o None
    si ja estava fet."""
    if not os.path.isdir(carpeta) or os.path.exists(os.path.join(carpeta, MARCA_AEMET)):
        return None
    fetes = 0
    for ruta in sorted(glob.glob(os.path.join(carpeta, "previsio-oficial-*.jsonl"))):
        linies = []
        with open(ruta, encoding="utf-8") as f:
            for l in f:
                if not l.strip():
                    continue
                try:
                    d = json.loads(l)
                except ValueError:
                    linies.append(l.rstrip("\n"))
                    continue
                if d.get("font") == "aemet" and d.get("elaborat"):
                    d["elaborat"] = H.clau(H.local(d["elaborat"]).replace(tzinfo=H.UTC))
                    fetes += 1
                linies.append(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
        with open(ruta + ".tmp", "w", encoding="utf-8") as f:
            f.write("".join(l + "\n" for l in linies))
        os.replace(ruta + ".tmp", ruta)
    with open(os.path.join(carpeta, MARCA_AEMET), "w", encoding="utf-8") as f:
        f.write(str(fetes))
    return fetes


if __name__ == "__main__":
    fet = migra(sys.argv[1] if len(sys.argv) > 1 else REGISTRE)
    if fet is None:
        print("Res a fer: ja estava migrat (o no hi ha registre).")
    else:
        print(f"Migrats {len(fet)} fitxers a UTC: {sum(fet.values())} files.")
