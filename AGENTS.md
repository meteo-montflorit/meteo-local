# Instrucciones para agentes

Este repositorio calcula y publica «Temps a Montflorit»
(<https://meteo-montflorit.github.io/>): el tiempo en el barrio y «Si surts»
(medios, ropa, consejos y trenes para quien sale). Lugares, horario, fuentes y
umbrales: [README.md](README.md), `config.py` y `docs/adr/`. La página del
trayecto «Moto o cotxe?» y su agente con IA se retiraron el 07-10-2026 (ADR
0030): su dirección redirige a «Si surts».

Al preguntar por el tiempo, ejecuta `python3 casa.py --json /tmp/casa.json`
y **mira el radar en imagen**, no solo los números. Si falla alguna fuente,
consúltala a mano: no la des por vacía.

Al cambiar algo:

- La web está en catalán y castellano y va dirigida a cualquier vecino.
- **El repositorio es público**: nada de direcciones exactas ni nombres. Las
  coordenadas van redondeadas.
- **Si cambias una clave del NAS o de IONOS** (claves SSH, `ecowitt.env`,
  `ionos.env`, `claude.env`, el token de un bot o el usuario de IONOS),
  vuelve a cifrar el archivo correspondiente (`claus/claus-nas.tar.gz.gpg` o
  `claus/claus-ionos.tar.gz.gpg`) en el repositorio privado
  `meteo-montflorit/meteo-local-registre` y súbelo, con la misma orden de
  `RESTAURAR.md` al revés (`tar czf - … | gpg --symmetric --cipher-algo AES256`).
  La contraseña la escribe Juanjo en la ventana de gpg; avísale antes. Nada
  lo hace solo (ADR 0044 y 0045). Los suscriptores del bot no se copian.
- **La hora, en UTC por dentro** (ADR 0128): todo se calcula y se guarda en
  tiempo universal, con las claves «AAAA-MM-DDTHH:MMZ» (`hora.clau`,
  `prevision.clau_hora`), y se lee cualquier forma de antes (`hora.llegeix`).
  La hora de Madrid, solo en la frontera: lo que se publica (`hora.publica`
  pasa cada «…Z» a la hora de Madrid con su desfase: `montflorit.json`,
  `avisos.json`, el historial), lo que se escribe a la gente y las reglas de
  las personas (`hora.local`, `hora.hora_local`, `hora.dia_local`,
  `hora.de_rellotge`). Nada de `.astimezone()` sin zona ni de restar horas de
  Madrid: Python las resta como horas de reloj. Lo que depende del sol, en
  hora solar (`prevision.hora_solar`, ADR 0090).
- **Las alertas de peligro van todas juntas en todas partes** (ADR 0093): la
  portada, «Perill», /avisos_actius y el resumen del día (bot y «Consultes»).
  «Si surts» no las repite: una línea dice cuántas pueden afectar la
  conducción y lleva a «Perill» (`sortir.liniaAvisosConduccio`, 3.149.0).
  La previsión de crecida de la riera (`riera.previsio`, página «Riera», ADR
  0107) no es una alerta: no avisa por ningún canal y solo marca la pestaña.
  Un tipo de alerta nuevo se añade a `bot.TIPUS_PERILL` y a
  `tests/test_perills.py`, que falla si algún sitio se lo deja. Por fenómeno
  manda Meteocat; AEMET, para lo que Meteocat no cubre (`smp.marca_coberts`).
- **Todo lo que dice la web tiene que cuadrar** (ADR 0101): la lluvia de
  ahora sale solo de `pluja_ara` (`casa.estat_pluja`), y lo que se muestra en
  dos sitios usa el mismo umbral y la misma palabra. Si añades una frase que
  afirma algo del tiempo de ahora, mira qué otra puede contradecirla. En el
  NAS, `revisor.py` revisa con IA lo publicado y lo enviado; sus hallazgos de
  código van al registro (`docker exec meteo-local python3 /proyecto/revisor.py
  estat`) y a Juanjo: arréglalos en el código, no solo en los datos.
- Si cambia un umbral, actualiza `config.py`, el texto «Com es decideix» de
  `web/sortir.html` (o «D'on surt» de `web/casa.html`), el README, las pruebas
  y el ADR.
- Pasa las pruebas (`python3 -m unittest discover -s tests -b`; con `-b`, lo
  que escriben las que pasan no se ve), la revisión del código (`ruff check .`
  y `npx eslint web montflorit eslint.config.mjs`, con ESLint instalado en la
  carpeta: `npm install --no-save --no-package-lock eslint@9.39.1
  globals@16.5.0`; GitHub las pasa también y
  el NAS no publica si fallan, ADR 0112; pasada media hora, el reparador del
  NAS lanza un agente que lo arregla, ADR 0113: si una sesión lo deja a
  medias, mira antes `docker exec meteo-local python3 /proyecto/reparador.py
  estat`) y `probar-web` antes de publicar; sube `VERSION` en
  `config.py` y etiqueta la versión (la release de GitHub, adonde lleva el
  «versió» del pie, la crea sola `.github/workflows/release.yml`; ADR 0095).
  Pasa también axe-core si cambia el HTML,
  el CSS o el JavaScript que crea o modifica elementos de la página; no hace
  falta si el cambio es solo de cálculo, de datos, del bot o de textos dentro
  de elementos que ya existen.
- Los datos públicos (`montflorit.json`) se publican en IONOS
  (`bilateria.org/app/meteo-local/`) y la web, cada media hora como mucho
  (ADR 0020). Este repositorio no publica ninguna web: las direcciones
  antiguas (`jjdeharo.github.io/meteo-local/…`) las redirige
  `jjdeharo/jjdeharo.github.io` (ADR 0035). La clave del NAS para IONOS solo
  puede ejecutar `reserva/rep-dades.sh` (orden fija en el `authorized_keys` de
  IONOS, instalado en `.meteo-reserva/bin/rep-dades` por `reserva/instalar.sh`),
  que solo acepta `montflorit.json` y `avisos.json` como archivos normales con
  JSON válido y de 2 MB como mucho, también descomprimidos (ADR 0038 y 0057),
  y las cuatro imágenes de la gráfica del resumen (`grafica-{avui,dema}-{ca,es}.png`,
  PNG de 600 KB como mucho, que dibuja el NAS con `grafica_imatge.py`; ADR 0098), y el
  historial de la gráfica (`historial.json` e `historial-AAAA-MM-DD.json`, que
  prepara `historial.py`; ADR 0099); la carpeta tiene un `.htaccess` que permite leer los
  datos desde `meteo-montflorit.github.io`.
- La web pública (repositorio `meteo-montflorit/meteo-montflorit.github.io`;
  ADR 0024, 0028 y 0029) la genera `montflorit.py` a partir de
  `web/casa.html`, `web/sortir.html` y `web/fonts.html`, y no puede decir
  «casa» ni nada del trayecto (en «Si surts» sí «moto» y «cotxe»; los créditos
  y el README enlazan este repositorio y sus ADR). Si cambias
  un texto que esté en sus listas de cambios, cámbialo también allí; las
  pruebas avisan. En ese repositorio no se edita nada a mano.
- La web pública está también en castellano (ADR 0025). Todo texto visible de
  `web/comu.js`, `web/casa.js` y `web/sortir.js` va con `T` (o `TD` si viene
  en los datos) y tiene su traducción en `montflorit/es.js`; los textos fijos
  de las páginas, en `i18n/es.json`. Los avisos de Renfe y FGC no se traducen:
  van en el idioma en que los publican. Si añades o cambias
  uno, tradúcelo: las pruebas fallan si falta.
- Las actualizaciones programadas las hace el NAS (`nas/`, ADR 0005). Si cambias
  `nas/`, copia los archivos a `/volume1/docker/meteo-local` y reconstruye
  (`docker compose up -d --build`). Ver el estado: `docker logs meteo-local`.
- Si el NAS no publica, lo hace la reserva de IONOS (`reserva/`, ADR 0032).
  Estado: `ssh ionos-webspace '.meteo-reserva/v/bin/python
  .meteo-reserva/repo/reserva/reserva.py estat'`; tras cambiar `reserva/`,
  `reserva/instalar.sh` (se pone al día sola cada hora con `git pull`).
- El bot de Telegram vive en IONOS (`bot/`, ADR 0034). Estado: `ssh
  ionos-webspace 'python3 .meteo-reserva/repo/bot/bot.py estat'`; tras cambiar
  sus órdenes o descripción, `bot/instalar.sh`. Los suscriptores son datos
  personales: no se copian fuera de IONOS ni se publican. Los avisos en el
  navegador (página «Avisos», ADR 0048) también viven allí: `bot/push.py`
  envía cada minuto y `bot/subscripcio.php` guarda las suscripciones en
  `.temps-bot/push.json`, igual de personales. Las altas y bajas de los dos (ADR 0084) van
  a `.temps-bot/moviments.json`, sin identificadores; el resumen va en el
  informe de los lunes (`bot.py informe`). Estado: `ssh ionos-webspace
  '.meteo-reserva/v/bin/python .meteo-reserva/repo/bot/push.py estat'`.
- La app de Android (ADR 0082) es la web publicada dentro de una TWA de
  Bubblewrap, en `android/`. No se toca con cada versión de la web; solo al
  cambiar el envoltorio o cuando Play exija otra versión de Android
  (`bubblewrap update`, subir `appVersionCode`, `android/construeix.sh`). La
  clave de subida está en `~/.config/meteo-montflorit/android/` y, cifrada, en
  `claus/claus-android.tar.gz.gpg` de `meteo-local-registre`; nunca en este
  repositorio. Si cambia la clave, cambia también su huella en
  `montflorit/.well-known/assetlinks.json`.
- Los automatismos de este proyecto figuran en el inventario del NAS
  (`vigilancia-nas/config/automatismos.json`, ficha «Automatismos» de
  bilateria.org/nas). Si se añade, cambia o retira uno, se actualiza allí.
- El registro está en el NAS, en `/volume1/docker/meteo-local/estat/registre`
  (avisos de lluvia, episodios de la riera y lo medido). Resúmenes:
  `docker exec meteo-local python3 /proyecto/pluja_arriba.py resum`,
  `docker exec meteo-local python3 /proyecto/riera.py resum` y, lo que dijo
  «Si surts» de cada medio y lo que pasó, `docker exec meteo-local python3
  /proyecto/aprenentatge.py sortir` (ADR 0047 y 0068); el final de la lluvia según el
  radar, `docker exec meteo-local python3 /proyecto/fi_pluja.py resum`
  (ADR 0049); los pesos de los modelos del cielo y cuánto se equivoca cada
  uno contra el aeropuerto de Sabadell, `docker exec meteo-local python3
  /proyecto/nuvols.py estat` (ADR 0088).
