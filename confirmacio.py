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
# Una resposta que arriba més tard que això pregunta per a quina hora val: la
# de la pregunta o la de la resposta (Juanjo, 28-10-2026, en respondre a les
# 8:16 la pregunta de la boira de les 7:01: «no había niebla a las 7»).
TARDA = dt.timedelta(minutes=30)


def telegram(metode, config=None, **params):
    c = json.load(open(config or CONFIG_BOT, encoding="utf-8"))
    dades = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                    for k, v in params.items()}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{c['token']}/{metode}", dades, timeout=30) as r:
        return json.load(r).get("result"), c


def capcalera(text):
    """La pregunta, amb la capçalera dels altres avisos d'un programa (la
    d'avisar-juanjo): qui escriu i quan. Juanjo, 19-10-2026: «cualquier ia que
    me escriba debe identificarse de algún modo, así conozco el contexto»."""
    import hora as H
    return f"⚙️ Temps a Montflorit · {H.local(H.ara()):%Y-%m-%d %H:%M}\n\n{text}"


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
    preguntar (pregunta_…), i per a quin moment val la resposta (val_per)."""
    return (["missatge", "pregunta", "resposta", "resposta_t"] + camps + [f"pregunta_{c}" for c in camps]
            + ["val_per"])


def val_per(fila):
    """El moment per al qual val una resposta: «pregunta» (la seva hora i les
    dades pregunta_…) o «resposta» (resposta_t i les dades de camps). Buit és
    «resposta»: una resposta tardana sense triar, les d'abans del 28-10-2026 i
    les de la riera, que no parlen d'ara."""
    return fila.get("val_per") or "resposta"


def canvia(ruta, missatge, **canvis):
    """Canvia unes columnes de la fila d'un missatge i reescriu el fitxer."""
    with open(ruta, encoding="utf-8") as f:
        r = csv.DictReader(f)
        camps, totes = r.fieldnames, list(r)
    for fila in totes:
        if fila["missatge"] == str(missatge):
            fila.update(canvis)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, camps)
        w.writeheader()
        w.writerows(totes)


def al_dia(confirmacions, camps):
    """Les respostes d'abans del 18-10-2026 només portaven les dades de la
    pregunta, a les columnes de camps: passen a pregunta_… i les de la
    resposta queden buides. Les d'abans del 28-10-2026, amb val_per buit."""
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
                        **{f"pregunta_{c}": v.get(f"pregunta_{c}", v.get(c, "")) for c in camps},
                        "val_per": v.get("val_per", "")})


def respostes(prefix, preguntes, confirmacions, textos, camps, telegram, ara, estat_ara=None, quan=False):
    """_respostes amb un cadenat: el rellotge del NAS les llegeix cada pocs
    segons en un bucle a part (19-10-2026) i la riera també en cada passada;
    dues lectures alhora apuntarien la mateixa resposta dues vegades."""
    os.makedirs(os.path.dirname(confirmacions) or ".", exist_ok=True)
    with open(confirmacions + ".lock", "w") as cadenat:
        fcntl.flock(cadenat, fcntl.LOCK_EX)
        return _respostes(prefix, preguntes, confirmacions, textos, camps, telegram, ara, estat_ara, quan)


def _respostes(prefix, preguntes, confirmacions, textos, camps, telegram, ara, estat_ara=None, quan=False):
    """Les respostes als botons d'una pregunta, una vegada cadascuna, a
    confirmacions. La resposta val per al moment en què es respon, no per al
    de la pregunta (Juanjo, 18-10-2026: «si respondo a destiempo… la situación
    puede haber cambiado totalmente»): s'apunta amb l'hora i amb el que diuen
    les dades llavors (estat_ara(), un diccionari amb camps), i també amb el
    que deien en preguntar. Només consulta Telegram si n'hi ha alguna de les
    darreres 24 hores sense resposta: el rellotge ho mira cada minut, perquè
    la confirmació arribi de seguida.

    Amb quan (les preguntes d'«ara»: boira, plugim i cel), si la resposta
    arriba més de TARDA després de la pregunta, el missatge demana també per
    a quina hora val, amb dos botons («Vale para las 07:01», «Vale para las
    08:16»), i la tria va a val_per. Mentre no es tria, val per a la resposta,
    com abans del 28-10-2026."""
    import hora as H
    pendents = {int(p["missatge"]): p for p in files(preguntes)}
    conf = files(confirmacions)
    fetes = {int(r["missatge"]) for r in conf}
    sense_triar = {int(r["missatge"]): r for r in conf
                   if quan and not r.get("val_per") and r.get("resposta_t")
                   and ara - H.llegeix(r["resposta_t"]) < dt.timedelta(hours=24)}
    if not sense_triar and not any(m not in fetes and ara - H.llegeix(p["t"]) < dt.timedelta(hours=24)
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
        if not dada.startswith(prefix + ":") or str((q.get("from") or {}).get("id")) != str(cfg["chat_id"]):
            continue
        clau = dada.split(":", 1)[1]
        if clau.startswith("val:"):
            if m in sense_triar and clau[4:] in ("pregunta", "resposta"):
                tria(confirmacions, sense_triar.pop(m), clau[4:], prefix, textos, telegram, cfg, q)
                n += 1
            continue
        if m not in pendents or m in fetes:
            continue
        p = pendents[m]
        tard = quan and ara - H.llegeix(p["t"]) > TARDA
        if ara_dades is None:
            try:
                ara_dades = (estat_ara and estat_ara()) or {}
            except Exception:
                ara_dades = {}
        afegeix(confirmacions, camps_confirmacio(camps),
                {"missatge": m, "pregunta": p["t"], "resposta": clau, "resposta_t": H.clau(ara),
                 **{k: ara_dades.get(k) for k in camps}, **{f"pregunta_{k}": p.get(k) for k in camps},
                 "val_per": "resposta" if quan and not tard else ""})
        fetes.add(m)
        n += 1
        # Primer, el missatge diu què s'ha apuntat: és la confirmació que es
        # veu. Després, el toc; si ha passat massa estona, Telegram ja no
        # l'accepta, i abans això deixava el missatge sense canviar (17-10-2026).
        if tard:
            botons = [[{"text": f"Apuntado: {textos.get(clau, clau)}", "callback_data": f"{prefix}:fet"}],
                      [{"text": f"Vale para las {H.local(H.llegeix(p['t'])):%H:%M}",
                        "callback_data": f"{prefix}:val:pregunta"},
                       {"text": f"Vale para las {H.local(ara):%H:%M}", "callback_data": f"{prefix}:val:resposta"}]]
        else:
            botons = [[{"text": f"Apuntado a las {H.local(ara):%H:%M}: {textos.get(clau, clau)}",
                        "callback_data": f"{prefix}:fet"}]]
        try:
            telegram("editMessageReplyMarkup", chat_id=cfg["chat_id"], message_id=m,
                     reply_markup={"inline_keyboard": botons})
        except Exception:
            pass
        try:
            telegram("answerCallbackQuery", callback_query_id=q["id"], text="Apuntado, gracias")
        except Exception:
            pass
    return n


def tria(confirmacions, fila, quin, prefix, textos, telegram, cfg, q):
    """La tria de l'hora per a la qual val una resposta tardana: a val_per, i
    el missatge queda amb un sol botó, «Apuntado a las 07:01: …»."""
    import hora as H
    canvia(confirmacions, fila["missatge"], val_per=quin)
    hora = H.local(H.llegeix(fila["pregunta"] if quin == "pregunta" else fila["resposta_t"]))
    try:
        telegram("editMessageReplyMarkup", chat_id=cfg["chat_id"], message_id=int(fila["missatge"]),
                 reply_markup={"inline_keyboard": [[{"text": f"Apuntado a las {hora:%H:%M}: "
                                                             f"{textos.get(fila['resposta'], fila['resposta'])}",
                                                     "callback_data": f"{prefix}:fet"}]]})
    except Exception:
        pass
    try:
        telegram("answerCallbackQuery", callback_query_id=q["id"], text="Apuntado, gracias")
    except Exception:
        pass
