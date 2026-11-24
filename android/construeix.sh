#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Compila l'app d'Android (ADR 0082): app-release-bundle.aab per a Google Play
# i app-release-signed.apk per instal·lar-la a mà en un mòbil de prova.
# La clau de pujada és fora del repositori: ~/.config/meteo-montflorit/android/
# (o, si es perd, desxifrada de claus/claus-android.tar.gz.gpg de
# meteo-local-registre).
set -eu
cd "$(dirname "$0")"
CLAU="${CLAU_ANDROID:-$HOME/.config/meteo-montflorit/android}"
[ -f "$CLAU/upload.jks" ] && [ -f "$CLAU/clau.env" ] || { echo "Falta la clau a $CLAU" >&2; exit 1; }
ln -sf "$CLAU/upload.jks" upload.jks
set -a; . "$CLAU/clau.env"; set +a
BUBBLEWRAP="${BUBBLEWRAP:-$(command -v bubblewrap || echo "$HOME/.npm-global/bin/bubblewrap")}"
# El giny (ADR 0131): el seu codi i els seus recursos són a giny/main, perquè
# «bubblewrap update» esborra app/src; aquí es copien a l'app i es posa el
# receptor al manifest.
cp -R giny/main/. app/src/main/
python3 giny/manifest.py
"$BUBBLEWRAP" build --skipPwaValidation
ls -l app-release-bundle.aab app-release-signed.apk
