#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# El reloj de meteo-local dentro del contenedor del NAS.
#
# Cada minuto pregunta a que_toca.py si es hora de actualizar «Temps a
# Montflorit»: lo decide con el horario de los últimos datos publicados, el
# mismo que muestra la web (cada 15 minutos; en modo aviso, cada 6), así que
# lo que dice la página y lo que se hace no pueden separarse. Si toca, pone al
# día el repositorio y publica con publica.sh. A HORA_VERIFICACION rellena las
# horas que falten de la estación de casa y la página aprende de sus aciertos
# (aprenentatge.py). Mientras exista /estat/vigila-pluviometre.json, cada hora
# comprueba si el pluviómetro de casa marca la lluvia débil; al tener
# resultado avisa y lo borra (pluviometre.py, ADR 0017).
# Tras cada publicación, el revisor de coherencia (revisor.py, ADR 0101)
# mira si toca revisar con IA lo que dice la web y lo que se ha enviado; va
# aparte, para no frenar el reloj. Cada minuto lee los botones de Juanjo y,
# si se ha aplicado o deshecho una corrección, publica enseguida.
# Tras cada publicación apunta en el registro las situaciones de peligro
# (riscos.py, ADR 0018), la lluvia que el radar anuncia y si acertó
# (pluja_arriba.py, ADR 0022) y los episodios de la riera de Sant Cugat
# (riera.py, ADR 0027). Los avisos de los tres solo van a los suscriptores
# (avisos_bot.py, ADR 0034 y 0048): desde el 08-10-2026 ya no se mandan aparte
# a Juanjo.
# Además, cada minuto mira si main tiene commits nuevos y, si los tiene,
# publica enseguida: es el único que publica la web (ADR 0005). Solo se
# despliega un commit cuyas pruebas de GitHub han pasado (desplegament.py,
# ADR 0038): si están pendientes se espera, si han fallado se queda el
# anterior, y si GitHub no responde se despliega como antes. Y en cada vuelta
# reintenta los avisos privados a Juanjo que Telegram no aceptó
# (avis_privat.py, ADR 0038).
# Si un commit de main no pasa las comprobaciones, el reparador (reparador.py,
# ADR 0113) lanza, pasada media hora, un agente con IA que lo arregla en una
# copia aparte; va aparte, cada minuto, para no frenar el reloj.
# Una vez al día, a HORA_COPIA, copia el registro y el aprendizaje en un
# repositorio privado de GitHub (nas/copia-registre.sh, ADR 0044).
# La página del trayecto, su registro de aciertos y el agente diario con IA se
# retiraron el 07-10-2026 (ADR 0030).
#
#   reloj.sh         bucle (lo que arranca el contenedor)
#   reloj.sh --ara   una sola pasada, ya
set -u

REPO=/proyecto
URL_REPO=git@github.com:meteo-montflorit/meteo-local.git
ESTAT_DIR=/estat
HORA_COPIA=04:15

registro() { printf '%s  %s\n' "$(date '+%F %T')" "$*"; }

prepara() {
  if [ ! -d "$REPO/.git" ]; then
    git clone -q "$URL_REPO" "$REPO" || { registro "no he podido clonar"; return 1; }
  fi
  if [ -f "$REPO/desplegament.py" ]; then
    # Solo hasta el último commit con las pruebas en verde; lo que apunta,
    # con la fecha, al registro.
    python3 "$REPO/desplegament.py" actualitza "$REPO" "$ESTAT_DIR/desplegament.json" 2>&1 >/dev/null \
      | while IFS= read -r linia; do registro "$linia"; done
    [ "${PIPESTATUS[0]}" = 0 ] || { registro "no he podido poner al día el repositorio"; return 1; }
  else
    git -C "$REPO" fetch -q origin main && git -C "$REPO" reset -q --hard origin/main \
      || { registro "no he podido poner al día el repositorio"; return 1; }
  fi
}

# Las respuestas de Juanjo a los botones (niebla, boira.py, ADR 0100;
# llovizna que solo ve el radar, plugim.py, ADR 0019; desbordamiento de la
# riera, riera.py, ADR 0027; cielo tapado, nuvols_satellit.py, ADR 0126), cada RESPOSTES_S segundos y aparte del bucle de
# las pasadas, para que el mensaje diga enseguida que se han apuntado. Dentro
# del bucle esperaban a que acabara la publicación: con lluvia (cada 6
# minutos) y código nuevo, el «Apuntado» tardaba minutos (Juanjo,
# 19-10-2026: «he respondido varias veces pero no veo el mensaje de
# confirmación»). Además, Telegram solo guarda cada pulsación unos dos
# minutos (en las pruebas del 25-10-2026, 141 s): leídas una vez por pasada,
# se perdían todas (las del cielo, hasta el 25-10-2026). Sin preguntas
# pendientes, no consultan Telegram; confirmacio.respostes lleva un candado.
RESPOSTES_S=15
respostes_rapides() {
  while true; do
    if [ -d "$REPO/.git" ]; then
      for m in boira plugim riera nuvols_satellit; do
        (cd "$REPO" && timeout 60 python3 "$m.py" respostes >/dev/null 2>&1) || true
      done
    fi
    sleep "$RESPOSTES_S"
  done
}

# Los avisos privados que Telegram no aceptó, mientras tengan sentido.
reintenta_avisos() {
  [ -s "$ESTAT_DIR/avisos-pendents.jsonl" ] || return 0
  (cd "$REPO" && python3 avis_privat.py reintenta) | while IFS= read -r linia; do registro "$linia"; done
}

riscos() {
  (cd "$REPO" && python3 riscos.py avisa /estat/casa.json >/dev/null) \
    || registro "ha fallado el aviso de riesgos"
  aviso=$(cd "$REPO" && python3 pluja_arriba.py avisa /estat/casa.json) \
    || registro "ha fallado el aviso de antes de llover"
  [ -z "${aviso:-}" ] || registro "lluvia anunciada: $aviso"
  aviso=$(cd "$REPO" && python3 riera.py avisa /estat/casa.json) \
    || registro "ha fallado el aviso de la riera"
  [ -z "${aviso:-}" ] || registro "riera: $aviso"
}

revisor() {
  [ -f "$REPO/revisor.py" ] && [ -f "$ESTAT_DIR/avisos.json" ] || return 0
  ( cd "$REPO" && python3 revisor.py revisa "$ESTAT_DIR/casa.json" "$ESTAT_DIR/avisos.json" 2>&1 \
      | while IFS= read -r linia; do registro "revisor: $linia"; done ) &
}

reparador() {
  [ -f "$REPO/reparador.py" ] || return 0
  ( cd "$REPO" && ESTAT_DIR="$ESTAT_DIR" python3 reparador.py comprova 2>&1 \
      | while IFS= read -r linia; do registro "reparador: $linia"; done ) &
}

respostes_revisor() {
  [ -f "$REPO/revisor.py" ] || return 0
  (cd "$REPO" && python3 revisor.py respostes >/dev/null 2>&1) || true
  if [ -f "$ESTAT_DIR/publica-ara" ]; then
    rm -f "$ESTAT_DIR/publica-ara"
    registro "corrección del revisor: se publica ya"
    pasada
  fi
}

pasada() {
  prepara || return
  if ESTAT_DIR="$ESTAT_DIR" bash "$REPO/publica.sh" >/dev/null; then
    registro "publicado"
    riscos
    revisor
  else
    registro "ha fallado la publicación"
  fi
}

verificacion() {
  prepara || return 1
  fallos=0
  # Las horas que falten de la estación de casa, con su historial (ADR 0017).
  (cd "$REPO" && python3 registre.py estacio >/dev/null) \
    || { registro "no he podido completar la estación de casa"; fallos=1; }
  # La página de casa aprende de lo que pasó (ADR 0012).
  (cd "$REPO" && python3 aprenentatge.py diari >/dev/null) \
    && registro "aprendizaje de casa hecho" || { registro "ha fallado el aprendizaje de casa"; fallos=1; }
  return $fallos
}


hay_cambios() {
  remoto=$(git -C "$REPO" ls-remote -q origin refs/heads/main 2>/dev/null | cut -f1)
  [ -n "$remoto" ] && [ "$remoto" != "$(git -C "$REPO" rev-parse HEAD)" ]
}

hora_verificacion() {
  python3 -c 'import sys; sys.path.insert(0, "/proyecto"); import config; print(config.HORA_VERIFICACION)'
}


if [ "${1:-}" = "--ara" ]; then pasada; exit; fi

# Las horas que tocaban mientras el reloj estaba ocupado también cuentan: el
# 19-10-2026, la pasada por código nuevo de las 06:50 duró hasta las 06:51:37,
# la de las 06:51 no se miró nunca y la web dijo «propera: 06:51» hasta las
# 06:58. Se miran todos los minutos desde el último mirado (media hora como
# mucho) y, si alguno tocaba, una sola pasada.
toca_desde() {   # toca_desde <minuto anterior, epoch> <minuto de ahora, epoch>
  local m=$(( $1 + 60 ))
  if [ "$1" -eq 0 ] || [ $(( $2 - $1 )) -gt 1800 ]; then m=$2; fi
  while [ "$m" -le "$2" ]; do
    [ "$(cd "$REPO" && python3 que_toca.py "$(date -d "@$m" +%H:%M)" "$ESTAT_DIR/casa.json")" = casa ] && return 0
    m=$(( m + 60 ))
  done
  return 1
}

registro "reloj en marcha"
respostes_rapides &
ultim_minut=0
while true; do
  # Espera al principio del minuto siguiente.
  sleep $(( 60 - 10#$(date +%S) ))
  ahora=$(date +%H:%M)
  minut=$(( $(date +%s) / 60 * 60 ))
  if [ ! -d "$REPO/.git" ]; then
    prepara
  else
    toca_desde "$ultim_minut" "$minut" && pasada
  fi
  ultim_minut=$minut
  # Código nuevo en main: se publica ya, sin esperar a la próxima hora, si
  # sus pruebas han pasado (prepara solo mueve la copia entonces).
  if [ -d "$REPO/.git" ] && hay_cambios; then
    antes=$(git -C "$REPO" rev-parse HEAD)
    if prepara && [ "$(git -C "$REPO" rev-parse HEAD)" != "$antes" ]; then
      registro "hay código nuevo en main"
      pasada
    fi
  fi
  # A la hora de verificación o después, una vez al día: una pasada larga
  # que cruce la hora en punto no la deja sin hacer. Si falla, queda dicho:
  # se vuelve a intentar al día siguiente.
  if [ -d "$REPO/.git" ] && [[ "$ahora" > "$(hora_verificacion)" || "$ahora" = "$(hora_verificacion)" ]] \
      && [ "$(cat "$ESTAT_DIR/verificacio-feta" 2>/dev/null)" != "$(date +%F)" ]; then
    date +%F > "$ESTAT_DIR/verificacio-feta"
    verificacion || registro "la verificación de las $(hora_verificacion) ha fallado: se repetirá mañana"
  fi
  [ -d "$REPO/.git" ] && reintenta_avisos
  [ -d "$REPO/.git" ] && respostes_revisor
  [ -d "$REPO/.git" ] && reparador
  # La copia del registro, una vez al día a partir de HORA_COPIA.
  if [ -f "$REPO/nas/copia-registre.sh" ] && [[ "$ahora" > "$HORA_COPIA" || "$ahora" = "$HORA_COPIA" ]] \
      && [ "$(cat "$ESTAT_DIR/copia-feta" 2>/dev/null)" != "$(date +%F)" ]; then
    date +%F > "$ESTAT_DIR/copia-feta"
    ESTAT_DIR="$ESTAT_DIR" REPO="$REPO" bash "$REPO/nas/copia-registre.sh" \
      | while IFS= read -r linia; do registro "$linia"; done
  fi
  if [ -d "$REPO/.git" ] && [ "${ahora#*:}" = "05" ] && [ -f /estat/vigila-pluviometre.json ]; then
    (cd "$REPO" && python3 pluviometre.py vigila) || registro "ha fallado la vigilancia del pluviómetro"
  fi
done
