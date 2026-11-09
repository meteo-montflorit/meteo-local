# 24. Web pública Temps a Montflorit

Fecha: 2026-10-06 · Estado: aceptado


**09-10-2026 (ADR 0058).** La estación de meteocerdanyola.com se retiró de la web pública y de todo el programa. La pública sigue indexable; lo escrito abajo sobre su permiso es historia.

## Contexto

Juanjo quiere dar a conocer la página «Temps a casa» como web del tiempo del
barrio, pero sin que salga la recomendación de moto o coche, que es de uso
familiar, y sin cambiar la web actual ni su portada. Preguntó si convenía un
clon con otro nombre y si se verían datos suyos o de su NAS.

## Decisión

- **Una sola pasada de cálculo y dos webs.** La pública es la página de casa
  publicada aparte, en el repositorio `meteo-montflorit/meteo-montflorit.github.io`
  (<https://meteo-montflorit.github.io/>; hasta el 07-10-2026 estuvo en
  `jjdeharo/meteo-montflorit`, que ahora redirige: ADR 0028). No se mantiene a mano:
  `montflorit.py` la genera a partir de `web/` en cada publicación.
- **Qué cambia en la pública** (`CANVIS_INDEX` y `CANVIS_FONTS`): se llama
  «Temps a Montflorit»; no tiene el menú de páginas ni nada del trayecto;
  donde la de casa dice «casa» dice «Montflorit», y la estación propia es
  «una estació particular del barri», sin la distancia a la de Montflorit;
  manifiesto, icono (solo la nube) y caché de instalación propios; el pie
  enlaza su repositorio, no este. `casa.js` y `comu.js` son los mismos: leen
  del `<html>` el nombre del lugar, el archivo de datos y el enlace de la
  versión.
- **Datos aparte**: `montflorit.json`, los de `casa.json` sin `sortides` ni
  `sortida_per_defecte_h`, que llevan la recomendación del trayecto. Va a
  IONOS con los demás en cada pasada y, de reserva, junto a la web.
- **Publicación** (`publica.sh`): tras publicar esta web, se empuja la
  pública a la rama `gh-pages` de su repositorio (un solo commit, que se
  rehace), con una clave de despliegue del NAS que solo vale para él
  (`~/.ssh/id_montflorit`) y con la dirección anónima de GitHub en los
  commits. Si falla, esta web se publica igual y se reintenta en la
  siguiente.
- **Si la página de casa cambia** y un cambio deja de encajar, o queda una
  palabra del trayecto o «casa» en lo que se lee, `montflorit.py` falla: en
  las pruebas antes de publicar y, en el NAS, sin tocar la web pública.
- **Los buscadores**: la pública se publicó con `noindex` hasta que el
  responsable de meteocerdanyola.com respondiera sobre el uso de su
  estación (ADR 0004). Respondió el mismo día sin oponerse, y Juanjo lo dio
  por permiso: desde entonces se puede indexar (`INDEXABLE = True`).
  Desde la 3.216.0 (09-11-2026) lleva además lo que ayuda a los buscadores
  a encontrarla entera: cada página dice cuál es su dirección
  (`rel="canonical"`, una por lengua; la otra lengua va con `hreflang`),
  todas tienen descripción (faltaba en «Com funciona», «Fonts i crèdits» y
  «Privacitat»), y `montflorit.py` genera `sitemap.xml`, con las 11 páginas
  en las dos lenguas, y `robots.txt`, que lo permite todo y dice dónde está
  el sitemap. El sitemap no lleva fecha de cambio: los datos cambian cada
  pocos minutos y la página no. Hasta entonces era indexable, pero sin nada
  de esto. Las pruebas
  (`test_per_als_cercadors`) fallan si una página se queda sin descripción,
  sin dirección canónica o fuera del sitemap.
- **En catalán y, aparte, en castellano** (ADR 0025).
- **El código fuente y los ADR, enlazados** (07-10-2026). «Fonts i crèdits»
  (apartado «Codi font i decisions», y el «Codi font» del pie) y el README del
  repositorio público llevan a `meteo-montflorit/meteo-local` y a `docs/adr`. Antes la
  web pública no lo nombraba y los ADR no se encontraban desde ella; a Juanjo
  le preguntaron si había copiado la parte de los transportes, y el historial
  fechado de este repositorio es lo que muestra cómo nació cada pieza. Aceptó
  que así se vea el origen personal (el trayecto, la casa) y pidió quitar de
  los ADR el nombre de la persona del trayecto. El resto de páginas sigue sin
  nombrar este repositorio, la casa ni el trayecto.

## Alternativas descartadas

- **Un clon del programa en otro repositorio**: dos cálculos y dos códigos
  que se separarían con el tiempo.
- **Una segunda página escrita a mano**: el texto «D'on surt» cambia con el
  método y habría que acordarse de cambiarlo en dos sitios.
- **Hacer privado este repositorio y mover la web del trayecto**: oculta del
  todo el trayecto, pero GitHub Pages pide repositorio público en el plan
  gratuito y habría que cambiar de sitio la web actual. Juanjo eligió que la
  pública no lo enseñe ni lo enlace.
- **Quitar el trayecto de la web actual**: no quiere cambiarla.

## Consecuencias

- Este repositorio sigue siendo público y describe el trayecto y sus horas:
  quien llegue a él lo ve. La web pública no lo enlaza.
- Los datos públicos están en la misma carpeta de IONOS que los del trayecto
  (`bilateria.org/app/meteo-local/`), y el nombre de la carpeta se ve en el
  programa de la página.
- `estil.css` se comparte y conserva los estilos de la página del trayecto,
  que la pública no usa.
- Una publicación más en GitHub cada 30 minutos como mucho, en otro
  repositorio, con su propio límite.
- La versión es la de este programa; en la pública enlaza su repositorio.

## Evidencia

- La clave de IONOS del NAS acepta cualquier `.json` en su carpeta (orden
  fija en `authorized_keys`, comprobada el 06-10-2026): `montflorit.json` no
  ha pedido cambios allí. La carpeta ya permite leer los datos desde
  `jjdeharo.github.io`, que es también el origen de la web pública.
- En el repositorio y su historial no hay direcciones del NAS, claves ni
  tokens (búsqueda del 06-10-2026). Quien visita la web habla con GitHub y
  con bilateria.org, no con el NAS.
- Las coordenadas de `config.py` tienen tres decimales (unos 100 m) y ya
  eran públicas.

## Riesgos y limitaciones

- El permiso de meteocerdanyola.com no es expreso, sino deducido de sus
  mensajes (ADR 0004). Si su responsable cambia de idea, la página tendrá
  que funcionar sin su estación.
- El nombre puede hacer pensar que la web es de esa estación: la página dice
  de quién es cada dato en «D'on surt» y en «Fonts i crèdits».
- Los cambios de texto dependen de frases exactas de `casa.html`: tocar una
  de ellas obliga a tocar `montflorit.py`, y las pruebas lo avisan.

## Validación

`tests/test_montflorit.py` (la web se genera entera, sin archivos del
trayecto; lo que se lee no dice «casa», «cotxe», «moto», «trajecte» ni
«meteo-local»; la comprobación detecta esas palabras; si la página cambia,
falla; caché propia; los datos salen sin el trayecto). `probar-web` en
Chromium, Firefox y WebKit, en escritorio, móvil y tableta, con tema claro y
oscuro, y axe-core.
