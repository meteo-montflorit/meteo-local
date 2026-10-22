#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Monta el bot de Telegram de Temps a Montflorit en IONOS (ADR 0034). Se
# ejecuta EN EL PORTÁTIL; se puede repetir. Usa el clon del repositorio de la
# reserva (.meteo-reserva/repo, reserva/instalar.sh) y la clave del bot de
# ~/.config/credenciales/temps-montflorit-bot.json, que va directa a IONOS.
#
#   bot/instalar.sh            instala, registra las órdenes y programa el cron
#   bot/instalar.sh --sin-cron sin tocar el cron
set -euo pipefail

IONOS="${IONOS_HOST:-ionos-webspace}"
DIR=.temps-bot
BASE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
CLAU="$HOME/.config/credenciales/temps-montflorit-bot.json"

echo "Carpeta, candado y clave…"
ssh "$IONOS" "mkdir -p $DIR && chmod 700 $DIR && git -C .meteo-reserva/repo pull -q --ff-only"
cat "$BASE/htaccess" | ssh "$IONOS" "cat > $DIR/.htaccess"
cat "$CLAU" | ssh "$IONOS" "cat > $DIR/config.json && chmod 600 $DIR/config.json"

echo "Órdenes y descripción en Telegram…"
TOKEN=$(python3 -c "import json; print(json.load(open('$CLAU'))['token'])")
python3 - "$TOKEN" <<'PY'
import json, sys, urllib.parse, urllib.request
api = f"https://api.telegram.org/bot{sys.argv[1]}/"
def crida(metode, **p):
    dades = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, list) else v for k, v in p.items()}).encode()
    with urllib.request.urlopen(api + metode, dades, timeout=30) as r:
        assert json.load(r)["ok"], metode
# El bot porta un nom diferent del canal, perquè no es confonguin (Juanjo, 07-10-2026).
# Les descripcions de les ordres, d'una línia: amb dues, el menú de Telegram no
# hi cap sencer i amaga /avisos (Juanjo, 08-10-2026).
NOM = "Bot Temps a Montflorit"
TEXTOS = {
    "ca": ([("avisos", "Tria quins avisos reps"), ("avui", "La previsió d'avui"), ("dema", "La previsió de demà"),
            ("ara", "El temps ara"), ("radar", "El radar ara"), ("sol", "El sol i l'índex UV"),
            ("aire", "La qualitat de l'aire"), ("pollen", "El pol·len de la setmana"), ("trens", "Els trens de Cerdanyola"), ("busos", "Els busos del barri"),
            ("transit", "El trànsit a menys de 5 km"), ("llum", "Talls de llum al barri"),
            ("avisos_actius", "Avisos oficials vigents"), ("baixa", "Dona't de baixa")],
           "Bot personal: tu tries quins avisos del temps a Montflorit (Cerdanyola del Vallès) vols rebre: "
           "riera de Sant Cugat (en proves), perill per pluja o vent, pluja a punt de començar, talls de llum del barri i la previsió diària; "
           "i li pots preguntar pel sol, l'aire, el pol·len, els trens, els busos, el trànsit i els talls de llum. Orientatiu, no oficial. Si no vols triar res, hi ha el Canal Temps a Montflorit: @TempsMontflorit.",
           "Bot personal: tria quins avisos del temps a Montflorit vols rebre."),
    "es": ([("avisos", "Elige qué avisos recibes"), ("avui", "La previsión de hoy"), ("dema", "La previsión de mañana"),
            ("ara", "El tiempo ahora"), ("radar", "El radar ahora"), ("sol", "El sol y el índice UV"),
            ("aire", "La calidad del aire"), ("pollen", "El polen de la semana"), ("trens", "Los trenes de Cerdanyola"), ("busos", "Los autobuses del barrio"),
            ("transit", "El tráfico a menos de 5 km"), ("llum", "Cortes de luz en el barrio"),
            ("avisos_actius", "Avisos oficiales vigentes"), ("baixa", "Darse de baja")],
           "Bot personal: tú eliges qué avisos del tiempo en Montflorit (Cerdanyola del Vallès) quieres recibir: "
           "riera de Sant Cugat (en pruebas), peligro por lluvia o viento, lluvia a punto de empezar, cortes de luz del barrio y la previsión "
           "diaria; y le puedes preguntar por el sol, el aire, el polen, los trenes, los autobuses, el tráfico y los cortes de luz. Orientativo, no oficial. Si no quieres elegir nada, está el Canal Temps a Montflorit: @TempsMontflorit.",
           "Bot personal: elige qué avisos del tiempo en Montflorit quieres recibir."),
}
for idioma, (ordres, descripcio, curta) in TEXTOS.items():
    for codi in ([idioma, ""] if idioma == "ca" else [idioma]):
        extra = {"language_code": codi} if codi else {}
        crida("setMyCommands", commands=[{"command": c, "description": d} for c, d in ordres], **extra)
        crida("setMyDescription", description=descripcio, **extra)
        crida("setMyShortDescription", short_description=curta, **extra)
        crida("setMyName", name=NOM, **extra)
print("fet")
PY

# Los avisos en el navegador (ADR 0048): pywebpush en el entorno de la
# reserva, las claves VAPID (se crean una vez y no se copian) y, en la carpeta
# de los datos, un subscripcio.php que carga el del repositorio, que se pone
# al día con el git pull del bot.
echo "Avisos en el navegador…"
ssh "$IONOS" ".meteo-reserva/v/bin/python -c 'import pywebpush' 2>/dev/null \
  || .meteo-reserva/v/bin/pip install -q --disable-pip-version-check pywebpush; \
  .meteo-reserva/v/bin/python .meteo-reserva/repo/bot/push.py claus >/dev/null"
ssh "$IONOS" "cat > app/meteo-local/subscripcio.php" <<'PHP'
<?php
// Temps a Montflorit: els avisos al navegador (meteo-local, ADR 0048).
define('TEMPS_BOT', dirname(__DIR__, 2) . '/.temps-bot');
require dirname(__DIR__, 2) . '/.meteo-reserva/repo/bot/subscripcio.php';
PHP

if [ "${1:-}" != "--sin-cron" ]; then
  echo "Cron: cada minuto (bot y avisos en el navegador), y el recuento los lunes a las 9…"
  ssh "$IONOS" "
    ( crontab -l 2>/dev/null | grep -v 'repo/bot/bot.py' | grep -v 'repo/bot/push.py' ;
      echo '* * * * * python3 \$HOME/.meteo-reserva/repo/bot/bot.py >>\$HOME/$DIR/cron.log 2>&1' ;
      echo '* * * * * \$HOME/.meteo-reserva/v/bin/python \$HOME/.meteo-reserva/repo/bot/push.py >>\$HOME/$DIR/cron.log 2>&1' ;
      echo '0 9 * * 1 python3 \$HOME/.meteo-reserva/repo/bot/bot.py informe >>\$HOME/$DIR/cron.log 2>&1' ) | crontab -
    crontab -l | grep 'repo/bot/'"
fi
echo "Hecho. Estado: ssh $IONOS 'python3 .meteo-reserva/repo/bot/bot.py estat'"
