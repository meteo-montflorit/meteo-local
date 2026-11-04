#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ssh para git (GIT_SSH_COMMAND) que vuelve a probar si la conexión falla.
# El 04-11-2026, durante una incidencia de GitHub, la mitad de las conexiones
# se rechazaban («Permission denied (publickey)» con la clave buena) y la web
# pública, que se intentaba subir una vez por pasada, se quedó de 10:32 a
# 12:07 sin publicar; reintentando cada pocos segundos entró a la primera
# (ADR 0020). ssh devuelve 255 solo si falla él (conexión o autenticación),
# antes de que git envíe nada, así que repetir es seguro; cualquier otro
# código es de git en el servidor y se devuelve tal cual.
# Uso: GIT_SSH_COMMAND="eines/ssh-reintenta.sh -i CLAVE -o IdentitiesOnly=yes"
INTENTS=${SSH_INTENTS:-8}
for ((i = 1; i <= INTENTS; i++)); do
  ssh -o ConnectTimeout=10 "$@"
  rc=$?
  [ "$rc" -ne 255 ] && exit "$rc"
  [ "$i" -lt "$INTENTS" ] && sleep 3
done
exit 255
