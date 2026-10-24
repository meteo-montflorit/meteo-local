#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Recibe por SSH, desde el NAS, el tar.gz con los datos públicos de Temps a
# Montflorit y lo deja en app/meteo-local (ADR 0020). Es la orden fija de la
# clave del NAS en ~/.ssh/authorized_keys de IONOS:
#
#   command="sh .meteo-reserva/bin/rep-dades",restrict ssh-ed25519 …
#
# Solo acepta montflorit.json y avisos.json, como archivos normales (nada de
# enlaces, carpetas ni rutas), con JSON válido y de menos de MAX bytes, y desde
# el 17-10-2026 las cuatro imágenes de la gráfica del resumen del día
# (grafica-avui-ca.png…, ADR 0098), que tienen que ser PNG de verdad, y el
# historial de la gráfica (historial.json e historial-AAAA-MM-DD.json, ADR
# 0099), JSON como los otros, y desde la 3.194.0 los archivos por año del
# historial de «Perill» (avisos-AAAA.json, ADR 0124). Si
# algo no cuadra, se rechaza el envío entero y no se toca nada: hasta la
# auditoría del 07-10-2026 la orden extraía el tar tal cual, y un enlace
# simbólico llamado *.json habría acabado en la carpeta pública (ADR 0038).
# Lo instala reserva/instalar.sh; se puede probar con REP_DIR=carpeta.
set -eu
d=${REP_DIR:-app/meteo-local}
t=$d/.rep
MAX=2000000
rebutja() { echo "rep-dades: rebutjat: $*" >&2; exit 1; }
rm -rf "$t"
mkdir "$t"
trap 'rm -rf "$t"' EXIT
head -c $((MAX + 1)) > "$t/in.tgz"
[ "$(wc -c < "$t/in.tgz")" -le "$MAX" ] || rebutja "més de $MAX bytes"
# Cada entrada del tar: un archivo normal («-») con uno de los nombres
# admitidos, de MAX bytes como mucho también descomprimido (el tamaño que
# declara el tar; las imágenes, MAX_PNG), sin repetirse y no más de doce: un
# tar.gz de 5 KB podía traer un JSON de 5 MB (auditoría del 09-10-2026).
MAX_PNG=600000
tar -tzvf "$t/in.tgz" | awk -v max="$MAX" -v maxpng="$MAX_PNG" '
  { tipus = substr($1, 1, 1); nom = $NF; mida = $3 + 0; total += mida; n++
    png = nom ~ /^grafica-(avui|dema)-(ca|es)\.png$/
    hist = nom ~ /^historial(-20[0-9][0-9]-[01][0-9]-[0-3][0-9])?\.json$/ || nom ~ /^avisos-20[0-9][0-9]\.json$/ }
  tipus != "-" || (nom != "montflorit.json" && nom != "avisos.json" && !png && !hist) { print "rep-dades: rebutjat: " $0 > "/dev/stderr"; mal = 1 }
  mida > (png ? maxpng : max) { print "rep-dades: rebutjat: " nom " fa " mida " bytes descomprimit" > "/dev/stderr"; mal = 1 }
  vist[nom]++ { print "rep-dades: rebutjat: " nom " repetit" > "/dev/stderr"; mal = 1 }
  END { if (total > max || n > 12) { print "rep-dades: rebutjat: " n " entrades, " total " bytes" > "/dev/stderr"; mal = 1 }; exit mal }' || exit 1
noms=$(tar -tzf "$t/in.tgz")
[ -n "$noms" ] || rebutja "buit"
tar -xzf "$t/in.tgz" -C "$t" --no-same-owner --no-same-permissions $noms
for n in $noms; do
  [ -f "$t/$n" ] && [ ! -L "$t/$n" ] || rebutja "$n no és un fitxer normal"
  [ "$(wc -c < "$t/$n")" -le "$MAX" ] || rebutja "$n fa més de $MAX bytes"
  case "$n" in
    *.png)
      python3 -c 'import sys; sys.exit(open(sys.argv[1], "rb").read(8) != b"\x89PNG\r\n\x1a\n")' "$t/$n" \
        || rebutja "$n no és PNG" ;;
    *)
      python3 -c 'import json, sys; json.load(open(sys.argv[1], encoding="utf-8"))' "$t/$n" 2>/dev/null \
        || rebutja "$n no és JSON" ;;
  esac
  chmod 604 "$t/$n"
done
for n in $noms; do
  mv -f "$t/$n" "$d/$n"
done
