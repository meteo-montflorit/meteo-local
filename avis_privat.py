#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Avisos privados a Juanjo por Telegram (avisar-juanjo) con reintento (ADR
0038).

Los avisos que el NAS o la reserva mandan a Juanjo (por ejemplo, la reserva
cuando toma el relevo) salen con avisar-juanjo. Hasta el 08-10-2026 también
los de peligro, lluvia inminente y riera, que ahora le llegan como a cualquier
suscriptor (ADR 0048). Hasta la auditoría del 07-10-2026, si Telegram o la red
fallaban en ese momento, el aviso se perdía. Ahora el envío pasa por aquí: si
avisar-juanjo no devuelve 0, el aviso queda en una cola (avisos-pendents.jsonl,
junto al estado) y el reloj del NAS (nas/reloj.sh) y la reserva de IONOS
(reserva/reserva.py) la reintentan en cada pasada mientras el aviso tenga
sentido (su vigencia, 3 horas si no se dice otra). Lo que caduca sin
entregarse se apunta en el registro de la pasada.

Uso:
  python3 avis_privat.py reintenta     reenvía los pendientes (lo hacen el reloj y la reserva)
  python3 avis_privat.py estat         los pendientes
"""
import datetime as dt
import json
import os
import subprocess
import sys

import hora as H

DIR = os.path.dirname(os.environ.get("REGISTRE_DIR", "/estat/registre"))
PENDENTS = os.path.join(DIR, "avisos-pendents.jsonl")
ORDRE = os.environ.get("AVISAR_JUANJO", "avisar-juanjo")
ASSUMPTE = "meteo-local"
VIGENCIA_MIN = 180


def ara_():
    return H.ara()


def _executa(text, assumpte):
    """True si avisar-juanjo lo ha entregado (código 0)."""
    try:
        # Firma el programa, no Claude (Juanjo, 19-10-2026); por la variable y no
        # con --de, que el avisar-juanjo de la reserva no entiende.
        return subprocess.run([ORDRE, "--asunto", assumpte, text], check=False, timeout=120,
                              env={**os.environ, "AVISAR_AGENTE": "Temps a Montflorit"},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def pendents():
    try:
        with open(PENDENTS, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        return []


def _desa(llista):
    os.makedirs(os.path.dirname(PENDENTS) or ".", exist_ok=True)
    with open(PENDENTS + ".tmp", "w", encoding="utf-8") as f:
        for p in llista:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    os.replace(PENDENTS + ".tmp", PENDENTS)


def envia(text, assumpte=ASSUMPTE, vigencia_min=VIGENCIA_MIN, ara=None):
    """Manda el aviso. True si Telegram lo ha aceptado; si no, queda apuntado
    para reintentarlo hasta que caduque."""
    if _executa(text, assumpte):
        return True
    ara = ara or ara_()
    llista = pendents()
    llista.append({"hora": H.clau(ara),
                   "fins": H.clau(ara + dt.timedelta(minutes=vigencia_min)),
                   "assumpte": assumpte, "text": text})
    _desa(llista)
    return False


def reintenta(ara=None):
    """Reenvía los pendientes vigentes. Devuelve (entregados, caducados sin
    entregar, aún pendientes)."""
    llista = pendents()
    if not llista:
        return [], [], []
    ara = ara or ara_()
    entregats, caducats, queden = [], [], []
    for p in llista:
        if H.llegeix(p["fins"]) < ara:
            caducats.append(p)
        elif _executa(p["text"], p["assumpte"]):
            entregats.append(p)
        else:
            queden.append(p)
    _desa(queden)
    return entregats, caducats, queden


if __name__ == "__main__":
    ordre = sys.argv[1] if len(sys.argv) > 1 else ""
    if ordre == "reintenta":
        entregats, caducats, queden = reintenta()
        for p in entregats:
            print(f"aviso privado entregado al reintentar (de las {H.local(p['hora']):%H:%M}): {p['text'][:80]}")
        for p in caducats:
            print(f"aviso privado caducado sin entregar (de las {H.local(p['hora']):%H:%M}): {p['text'][:80]}")
        if queden:
            print(f"{len(queden)} aviso(s) privado(s) pendiente(s) de entregar")
    elif ordre == "estat":
        print(json.dumps(pendents(), ensure_ascii=False, indent=1))
    else:
        print(__doc__)
        sys.exit(1)
