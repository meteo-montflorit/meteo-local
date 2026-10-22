#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Les preguntes a Juanjo per Telegram, amb botons, del que només ell pot veure
des de casa (la boira, ADR 0100; el plugim, ADR 0019), i les seves respostes.

Fa servir el bot dels agents (avisar-juanjo) i llegeix les respostes sense
marcar-les com a llegides (getUpdates sense offset), per no treure res a qui
llegeixi el xat. Cada pregunta té el seu prefix als botons («boira:si»), el
seu fitxer de preguntes i el de respostes, al registre.
"""
import csv
import datetime as dt
import fcntl
import json
import os
import urllib.parse
import urllib.request

CONFIG_BOT = os.path.expanduser("~/.config/avisar-juanjo/config.json")


def telegram(metode, config=None, **params):
    with open(config or CONFIG_BOT, encoding="utf-8") as f:
        c = json.load(f)
    dades = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                    for k, v in params.items()}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{c['token']}/{metode}", dades, timeout=30) as r:
        return json.load(r).get("result"), c


def capcalera(text):
    """La pregunta, amb la capçalera dels altres avisos d'un programa (la
    d'avisar-juanjo): qui escriu i quan. Juanjo, 19-10-2026: «cualquier ia que
    me escriba debe identificarse de algún modo, así conozco el contexto»."""
    return f"⚙️ Temps a Montflorit · {dt.datetime.now():%Y-%m-%d %H:%M}\n\n{text}"


def files(ruta):
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def afegeix(ruta, camps, fila):
    """Una fila al final. Si el fitxer té unes altres columnes (d'una versió
    anterior), primer el reescriu amb les d'ara, amb buits on no hi havia res."""
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            r = csv.DictReader(f)
            velles = None if r.fieldnames == camps else list(r)
        if velles is not None:
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, camps)
                w.writeheader()
                w.writerows({c: v.get(c, "") for c in camps} for v in velles)
    nou = not os.path.exists(ruta)
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, camps)
        if nou:
            w.writeheader()
        w.writerow(fila)


def camps_confirmacio(camps):
    """Les columnes de les respostes: quan es va preguntar i quan es va
    respondre, el que deien les dades en respondre (camps) i el que deien en
    preguntar (pregunta_…)."""
    return ["missatge", "pregunta", "resposta", "resposta_t"] + camps + [f"pregunta_{c}" for c in camps]


def al_dia(confirmacions, camps):
    """Les respostes d'abans del 18-10-2026 només portaven les dades de la
    pregunta, a les columnes de camps: passen a pregunta_… i les de la
    resposta queden buides."""
    if not os.path.exists(confirmacions):
        return
    with open(confirmacions, encoding="utf-8") as f:
        r = csv.DictReader(f)
        if r.fieldnames == camps_confirmacio(camps):
            return
        velles = list(r)
    with open(confirmacions, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, camps_confirmacio(camps))
        w.writeheader()
        for v in velles:
            w.writerow({"missatge": v.get("missatge"), "pregunta": v.get("pregunta"), "resposta": v.get("resposta"),
                        "resposta_t": v.get("resposta_t", ""), **{c: v.get(c, "") if "resposta_t" in v else ""
                                                                    for c in camps},
                        **{f"pregunta_{c}": v.get(f"pregunta_{c}", v.get(c, "")) for c in camps}})


def respostes(prefix, preguntes, confirmacions, textos, camps, telegram, ara, estat_ara=None):
    """_respostes amb un cadenat: el rellotge del NAS les llegeix cada pocs
    segons en un bucle a part (19-10-2026) i la riera també en cada passada;
    dues lectures alhora apuntarien la mateixa resposta dues vegades."""
    os.makedirs(os.path.dirname(confirmacions) or ".", exist_ok=True)
    with open(confirmacions + ".lock", "w") as cadenat:
        fcntl.flock(cadenat, fcntl.LOCK_EX)
        return _respostes(prefix, preguntes, confirmacions, textos, camps, telegram, ara, estat_ara)


def _respostes(prefix, preguntes, confirmacions, textos, camps, telegram, ara, estat_ara=None):
    """Les respostes als botons d'una pregunta, una vegada cadascuna, a
    confirmacions. La resposta val per al moment en què es respon, no per al
    de la pregunta (Juanjo, 18-10-2026: «si respondo a destiempo… la situación
    puede haber cambiado totalmente»): s'apunta amb l'hora i amb el que diuen
    les dades llavors (estat_ara(), un diccionari amb camps), i també amb el
    que deien en preguntar. Només consulta Telegram si n'hi ha alguna de les
    darreres 24 hores sense resposta: el rellotge ho mira cada minut, perquè
    la confirmació arribi de seguida."""
    pendents = {int(p["missatge"]): p for p in files(preguntes)}
    fetes = {int(r["missatge"]) for r in files(confirmacions)}
    if not any(m not in fetes and ara - dt.datetime.fromisoformat(p["t"]) < dt.timedelta(hours=24)
               for m, p in pendents.items()):
        return 0
    updates, cfg = telegram("getUpdates", allowed_updates=["callback_query"])
    al_dia(confirmacions, camps)
    ara_dades = None
    n = 0
    for u in updates or []:
        q = u.get("callback_query") or {}
        m = (q.get("message") or {}).get("message_id")
        dada = q.get("data") or ""
        if not dada.startswith(prefix + ":") or m not in pendents or m in fetes \
                or str((q.get("from") or {}).get("id")) != str(cfg["chat_id"]):
            continue
        clau = dada.split(":", 1)[1]
        p = pendents[m]
        if ara_dades is None:
            try:
                ara_dades = (estat_ara and estat_ara()) or {}
            except Exception:
                ara_dades = {}
        afegeix(confirmacions, camps_confirmacio(camps),
                {"missatge": m, "pregunta": p["t"], "resposta": clau, "resposta_t": ara.isoformat(timespec="minutes"),
                 **{k: ara_dades.get(k) for k in camps}, **{f"pregunta_{k}": p.get(k) for k in camps}})
        fetes.add(m)
        n += 1
        # Primer, el missatge diu què s'ha apuntat: és la confirmació que es
        # veu. Després, el toc; si ha passat massa estona, Telegram ja no
        # l'accepta, i abans això deixava el missatge sense canviar (17-10-2026).
        try:
            telegram("editMessageReplyMarkup", chat_id=cfg["chat_id"], message_id=m,
                     reply_markup={"inline_keyboard": [[{"text": f"Apuntado a las {ara:%H:%M}: {textos.get(clau, clau)}",
                                                         "callback_data": f"{prefix}:fet"}]]})
        except Exception:
            pass
        try:
            telegram("answerCallbackQuery", callback_query_id=q["id"], text="Apuntado, gracias")
        except Exception:
            pass
    return n
