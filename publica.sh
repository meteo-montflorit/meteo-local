#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Calcula el tiempo en Montflorit (casa.py) y publica «Temps a Montflorit»
# (ADR 0024 y 0029): los datos en IONOS y la web en su repositorio. La rama
# gh-pages de la web tiene siempre un solo commit: se rehace en cada
# publicación. Las direcciones antiguas (jjdeharo.github.io/meteo-local) las
# redirige el repositorio jjdeharo/jjdeharo.github.io, aparte (ADR 0035).
#
# Lo usa el NAS (con reloj.sh), que es el único que publica; a mano también
# se puede ejecutar desde un ordenador con acceso a los repositorios.
# Variables:
#   ESTAT_DIR   carpeta del estado (en el NAS, /estat): ahí se deja casa.json
#               para los avisos y se lee el de la pasada anterior, por si
#               Open-Meteo falla (ADR 0016). Sin ella, el publicado.
#   DESTINO_MONTFLORIT  adónde se empuja la web pública; vacío, no se publica
#
# En el NAS, los datos de la web pública (montflorit.json: los de casa sin lo
# privado) se suben en cada pasada a IONOS (bilateria.org/app/meteo-local/),
# de donde los lee la página, y las webs a GitHub solo si ha cambiado el
# código, si hace GH_CADA_MIN minutos de la última vez o si IONOS falla:
# GitHub Pages admite unas 10 publicaciones por hora (ADR 0020). La copia de
# los datos en el repositorio de la web pública es la reserva si IONOS no
# responde; desde la 3.58.0 también la de avisos.json, que lleva el historial
# de la página «Perill» (ADR 0071). Fuera del NAS, sin la clave de IONOS, todo
# va a GitHub.
set -euo pipefail
cd "$(dirname "$0")"

ESTAT_DIR=${ESTAT_DIR:-}
DESTINO_MONTFLORIT=${DESTINO_MONTFLORIT-git@github.com:meteo-montflorit/meteo-montflorit.github.io.git}

publica=$(mktemp -d)
dades=$(mktemp -d)
trap 'rm -rf "$publica" "$dades"' EXIT

# Si Open-Meteo falla, casa.py reutiliza la última previsión buena (ADR 0016).
if [ -n "$ESTAT_DIR" ]; then
  CASA_ANTERIOR="$ESTAT_DIR/casa.json"
else
  CASA_ANTERIOR=https://bilateria.org/app/meteo-local/montflorit.json
fi
python3 casa.py --json "$dades/casa.json" --anterior "$CASA_ANTERIOR" >/dev/null
# Una copia para los avisos por Telegram (riscos.py, pluja_arriba.py, riera.py).
[ -z "$ESTAT_DIR" ] || cp "$dades/casa.json" "$ESTAT_DIR/casa.json"
# Los avisos para el bot y el canal de Telegram, que los reparte desde IONOS
# (ADR 0034). Llevan estado: solo en el NAS. Van antes que los datos públicos:
# la riera abierta en avisos.json sale en el resumen del día (ADR 0093).
if [ -n "$ESTAT_DIR" ]; then
  python3 avisos_bot.py "$dades/casa.json" "$dades/avisos.json" https://bilateria.org/app/meteo-local/avisos.json >/dev/null \
    || echo "$(date '+%F %T')  han fallat els avisos del bot" >&2
  # Per al revisor de coherència, que el llegeix després de publicar (ADR 0101).
  [ ! -f "$dades/avisos.json" ] || cp "$dades/avisos.json" "$ESTAT_DIR/avisos.json"
fi
# Los datos de la web pública: los de casa sin lo privado.
python3 montflorit.py dades "$dades/casa.json" "$publica/montflorit.json" "$dades/avisos.json"
# La gráfica del resumen del día como imagen, para el bot, el canal y los
# avisos de la web y la app (ADR 0098): solo en el NAS, que tiene Chromium.
# Si falla, los resúmenes salen solo con texto, como antes.
grafiques=""
if [ -n "$ESTAT_DIR" ]; then
  python3 grafica_imatge.py "$publica/montflorit.json" "$dades/grafiques" >/dev/null 2>"$dades/grafiques.err" \
    || echo "$(date '+%F %T')  han fallat les imatges de la gràfica: $(tr '\n' ' ' < "$dades/grafiques.err" | cut -c1-300)" >&2
  grafiques=$(cd "$dades/grafiques" 2>/dev/null && ls grafica-*.png 2>/dev/null | tr '\n' ' ' || true)
fi
# Lo que dice ICON de la niebla, para comprobar en un mes si acierta antes de
# usarlo (boira.py, ADR 0100); una vez por hora como mucho.
[ -z "$ESTAT_DIR" ] || python3 boira.py apunta >/dev/null 2>&1 \
  || echo "$(date '+%F %T')  ha fallat la vigilància de la boira" >&2
# El ecotop del radar de AEMET en Gelida, dos semanas, para ver si anuncia las
# tormentas antes que lo que ya se usa (ecotop.py, ADR 0108); cada 25 minutos
# como mucho y solo con lluvia a la vista. Después de casa.json.
[ -z "$ESTAT_DIR" ] || timeout 180 python3 ecotop.py apunta "$ESTAT_DIR/casa.json" >/dev/null \
  || echo "$(date '+%F %T')  ha fallat el registre de l'ecotop" >&2
# Las previsiones de Meteocat y AEMET para Cerdanyola, para compararlas con la
# de la web en «Fiabilitat» (previsio_oficial.py, ADR 0110): Meteocat cada 3
# horas, AEMET cada hora. Antes del historial, que las lee.
[ -z "$ESTAT_DIR" ] || timeout 120 python3 previsio_oficial.py apunta >/dev/null \
  || echo "$(date '+%F %T')  ha fallat el registre de les previsions oficials" >&2
# Y, como en el barrio nada mide la visibilidad, la pregunta a Juanjo si casa
# está saturada, y sus respuestas (ADR 0100). Después de casa.json.
if [ -n "$ESTAT_DIR" ]; then
  python3 boira.py respostes >/dev/null 2>&1 || echo "$(date '+%F %T')  han fallat les respostes de la boira" >&2
  python3 boira.py pregunta >/dev/null 2>&1 || echo "$(date '+%F %T')  ha fallat la pregunta de la boira" >&2
  # El mateix amb el plugim que només veu el radar (plugim.py, ADR 0019).
  python3 plugim.py respostes >/dev/null 2>&1 || echo "$(date '+%F %T')  han fallat les respostes del plugim" >&2
  python3 plugim.py pregunta >/dev/null 2>&1 || echo "$(date '+%F %T')  ha fallat la pregunta del plugim" >&2
  # El cel tapat segons el satèl·lit (Meteosat, EUMETView), en observació, i
  # la pregunta quan discrepa de Sabadell (nuvols_satellit.py, ADR 0126).
  timeout 150 python3 nuvols_satellit.py apunta >/dev/null 2>&1 || echo "$(date '+%F %T')  ha fallat el cel del satèl·lit" >&2
  python3 nuvols_satellit.py respostes >/dev/null 2>&1 || echo "$(date '+%F %T')  han fallat les respostes del cel" >&2
  python3 nuvols_satellit.py pregunta >/dev/null 2>&1 || echo "$(date '+%F %T')  ha fallat la pregunta del cel" >&2
fi
# El historial de la gráfica y el acierto de la previsión (ADR 0099): el
# índice y los dos últimos días (hoy cambia a cada hora; ayer se cierra a
# medianoche). Los anteriores ya están en IONOS. Solo en el NAS, con el registro.
historial=""
if [ -n "$ESTAT_DIR" ]; then
  python3 historial.py fes "$dades/historial" 2 >/dev/null 2>"$dades/historial.err" \
    || echo "$(date '+%F %T')  ha fallat l'historial: $(tr '\n' ' ' < "$dades/historial.err" | cut -c1-300)" >&2
  historial=$(cd "$dades/historial" 2>/dev/null && ls historial*.json 2>/dev/null | tr '\n' ' ' || true)
fi

# Los datos, a IONOS: una conexión con una clave que solo puede ejecutar
# reserva/rep-dades.sh (la orden la fija IONOS en authorized_keys), que acepta
# únicamente montflorit.json y avisos.json, archivos normales con JSON válido
# (ADR 0038), y las imágenes de la gráfica, PNG de verdad (ADR 0098).
# El usuario y el servidor están en el NAS, fuera del repositorio, que es
# público: ~/.config/meteo-local/ionos.env (IONOS=usuario@servidor).
CLAU_IONOS=${CLAU_IONOS:-$HOME/.ssh/id_ionos}
CONF_IONOS=${CONF_IONOS:-$HOME/.config/meteo-local/ionos.env}
[ -f "$CONF_IONOS" ] && . "$CONF_IONOS"
GH_CADA_MIN=${GH_CADA_MIN:-30}
a_ionos=0
if [ -f "$CLAU_IONOS" ] && [ -n "${IONOS:-}" ]; then
  # Lo que responde la conexión (ssh o el receptor) se guarda para el
  # registro: falla cada día a las 06:03 y a las 06:09 y sin el mensaje no
  # se sabe si rechaza SSH o el receptor (10-10-2026).
  if tar -czf - -C "$publica" montflorit.json $([ -f "$dades/avisos.json" ] && echo "-C $dades avisos.json") \
      $([ -n "$grafiques" ] && echo "-C $dades/grafiques $grafiques") \
      $([ -n "$historial" ] && echo "-C $dades/historial $historial") \
      | ssh -i "$CLAU_IONOS" -o BatchMode=yes -o ConnectTimeout=20 "$IONOS" 2>"$dades/ionos.err"; then
    a_ionos=1
    echo "$(date '+%F %T')  dades a IONOS"
  else
    sortida=$?
    echo "$(date '+%F %T')  IONOS ha fallat (sortida $sortida: $(tr '\n' ' ' < "$dades/ionos.err" | cut -c1-300)): es publica a GitHub" >&2
  fi
  # Los archivos por año del historial de «Perill» (avisos-AAAA.json, ADR
  # 0124), solo cuando avisos_bot.py ha pasado algo a ellos, y en un envío
  # aparte: si IONOS los rechazara, los datos de siempre ya han entrado.
  arxius=$(cd "$dades" && ls avisos-20[0-9][0-9].json 2>/dev/null | tr '\n' ' ' || true)
  if [ "$a_ionos" = 1 ] && [ -n "$arxius" ]; then
    tar -czf - -C "$dades" $arxius | ssh -i "$CLAU_IONOS" -o BatchMode=yes -o ConnectTimeout=20 "$IONOS" 2>"$dades/ionos.err" \
      || echo "$(date '+%F %T')  IONOS ha rebutjat l'arxiu de «Perill» ($arxius): $(tr '\n' ' ' < "$dades/ionos.err" | cut -c1-300)" >&2
  fi
fi

# A GitHub: siempre sin IONOS; con IONOS, si cambia el código o toca.
estat_gh="${ESTAT_GH:-${ESTAT_DIR:-$dades}/gh-darrer}"
codi=$(git rev-parse HEAD 2>/dev/null || echo "?")
if [ "$a_ionos" = 1 ] && [ -f "$estat_gh" ]; then
  read -r darrer_t darrer_codi < "$estat_gh" || true
  if [ "$darrer_codi" = "$codi" ] && [ $(( $(date +%s) - ${darrer_t:-0} )) -lt $(( GH_CADA_MIN * 60 )) ]; then
    exit 0
  fi
fi

# La web pública, a su repositorio, con su propia clave de despliegue si la
# hay (en el NAS). Un fallo aquí no detiene nada: se reintenta en la próxima
# pasada, porque la marca de «ya publicado» solo se apunta si el push entra.
if [ -z "$DESTINO_MONTFLORIT" ]; then
  [ -z "$ESTAT_DIR" ] || echo "$(date +%s) $codi" > "$estat_gh"
else
  CLAU_MONTFLORIT=${CLAU_MONTFLORIT:-$HOME/.ssh/id_montflorit}
  # Cada paso encadenado con &&: dentro de la condición de un «if» Bash no
  # aplica «set -e», y un fallo del generador seguía con el commit y el push
  # de una web a medias (auditoría del 09-10-2026). Antes de Git se comprueba
  # que están las piezas esenciales.
  if (
    python3 montflorit.py web "$publica" \
    && { [ ! -f "$dades/avisos.json" ] || cp "$dades/avisos.json" "$publica/avisos.json"; } \
    && [ -f "$publica/index.html" ] && [ -f "$publica/montflorit.json" ] \
    && { [ ! -f "$CLAU_MONTFLORIT" ] || export GIT_SSH_COMMAND="ssh -i $CLAU_MONTFLORIT -o IdentitiesOnly=yes"; } \
    && git -C "$publica" init -q -b gh-pages \
    && git -C "$publica" add -A \
    && git -C "$publica" -c user.name="Juan José de Haro" -c user.email="8707929+jjdeharo@users.noreply.github.com" \
      commit -q -m "Previsió $(date '+%F %H:%M')" \
    && git -C "$publica" push -q -f "$DESTINO_MONTFLORIT" gh-pages
  ); then
    echo "$(date '+%F %T')  publicada la web de Montflorit"
    [ -z "$ESTAT_DIR" ] || echo "$(date +%s) $codi" > "$estat_gh"
  else
    echo "$(date '+%F %T')  no s'ha pogut publicar la web de Montflorit" >&2
  fi
fi
