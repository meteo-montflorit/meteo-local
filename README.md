# meteo-local

**Objetivo**: dar a los vecinos de Montflorit predicciones fiables, en la
medida de lo posible al 100 %, con datos de fuera y del propio barrio, y que
la web aprenda de sus errores en todo lo que predice (Juanjo, 10-10-2026).

Calcula y publica **Temps a Montflorit** (<https://meteo-montflorit.github.io/>),
la web del tiempo del barrio de Montflorit (Cerdanyola del Vallès), en catalán
y en [castellano](https://meteo-montflorit.github.io/es/). Tiene cuatro páginas:

- **El temps**: lo que miden ahora las estaciones del barrio (la temperatura
  y la presión, de una estación particular junto a la riera, en el carrer
  Canaletes; la lluvia y la humedad, por consenso de esa y de las vecinas de
  Weather Underground, ADR 0085; cuánto más hace en la parte alta, ahora y en
  cada tramo de la previsión, ADR 0087; la tarjeta de arriba, con el fondo y un dibujo del cielo que anuncia, de día, de noche o al salir y ponerse el sol, ADR 0121) y la de Montflorit, el resumen del día (el de «Consultes › Avui», sin la ropa; desde las 18 h,
  también el de mañana; ADR 0074) y la previsión hora a hora, de 24 horas como mínimo y hasta
  las 21 h de mañana, plegada por mañana, tarde y noche
  con el resumen de cada una (probabilidad de lluvia, temperaturas y
  fenómenos destacables; ADR 0041), con los avisos de AEMET y los planes de
  Protección Civil (ADR 0007 y 0024), y junto a cada plan si Meteocat tiene
  aviso de peligro para el Vallès Occidental (ADR 0067). Cada aviso lleva
  «›» a su detalle dentro de la web (ADR 0075). Desde la 3.152.0, tras «Ara»
  (con el radar, compacto si no es urgente) va la gráfica de la previsión,
  luego el resumen del día y los tramos; los trenes no salen en la portada
  (ADR 0074).
  «Avisos actius» sale desplegado la primera vez y cuando cambia el conjunto
  de avisos (o hay uno rojo); si no, plegado, con el número de avisos y una
  línea corta por aviso (ADR 0094).
- **Riera**: la riera de Sant Cugat en una página (ADR 0107): ahora (la
  lluvia medida y el radar, el mismo índice que decide el aviso), las
  próximas horas (lo que prevén los cuatro modelos en la cuenca: «risc de
  crescuda possible» desde 20 mm en 3 horas, una previsión que no avisa,
  con un punto ámbar en la pestaña mientras no se haya visto) y los
  episodios desde 2024.
- **Perill**: las situaciones de peligro en Montflorit, con el texto de los
  avisos tal como llegaron y un enlace para saber más: avisos oficiales de AEMET, de Meteocat y de Protección Civil, incendios
  forestales de Collserola y de Cerdanyola, la riera de Sant Cugat y el tiempo
  excepcional que calcula la web; la pestaña lleva un punto rojo si hay uno
  activo sin ver (ADR 0071 y 0074). Los planes de Protección Civil en
  prealerta, que no avisan, tienen también su ficha en «Ara», con el comunicado
  en PDF, y la portada lleva a ella (ADR 0091). Cada aviso se comparte entero, con el
  menú de compartir del dispositivo, y la riera y el tiempo extremo que
  calcula la web se explican en «Com funciona» (ADR 0076).
- **Si surts**: para quien sale a una hora y vuelve a otra, cómo irá cada
  medio (a pie, bici o patinete, moto, coche y transporte público), qué ropa
  ponerse, consejos (lluvia, sol, noche, calor), si circulan los trenes que
  paran en Cerdanyola (ADR 0029), las incidencias de los autobuses del barrio
  (ADR 0120) y las de tráfico de cerca (ADR 0052). Arriba, una línea con los medios que van bien y una por cada uno de
  los demás (ADR 0074). Cada persona elige qué medios ve. Cada ficha se abre en
  grande al tocar su título y se comparte con su propio enlace (ADR 0119).
- **Consultes**: lo mismo que el bot, eligiendo qué ver: hoy, mañana, el sol,
  la calidad del aire, el polen, los trenes, los autobuses, el tráfico o los cortes de luz del
  barrio; sale solo lo elegido, con los mismos textos del bot (ADR 0054 y 0072).
  Cada corte de luz, con un mapa del punto y las calles probables (ADR 0077).

Cada página y cada consulta se puede compartir con un enlace directo, y cada
aviso de «Perill», con el suyo (ADR 0072).

La probabilidad de lluvia sale de una regresión logística ajustada con lo que
llovió de verdad y comprobada con todo el archivo (ADR 0021); la temperatura se
corrige con un año de la estación particular (ADR 0017), igual que el punto de
rocío del que sale la humedad de la gráfica (ADR 0114), y el NAS guarda cada
hora lo previsto y lo medido para seguir aprendiendo (ADR 0012; explicación en
[docs/estadistica.md](docs/estadistica.md)). Las dos primeras horas tienen en
cuenta hacia dónde va la lluvia del radar (ADR 0019).

Los vecinos pueden recibir los avisos como notificaciones del móvil o del
ordenador, sin Telegram, desde la página «Avisos» de la web («Avisos al mòbil»;
ADR 0048): riera de Sant Cugat, peligro, lluvia en unos minutos y la
previsión del día, lo que elija cada uno. También por Telegram: el «Bot Temps a Montflorit»
([@TempsMontfloritBot](https://t.me/TempsMontfloritBot)), donde cada uno elige
riera de Sant Cugat, peligro, lluvia en unos minutos y la previsión del día,
y al que se puede preguntar por los trenes (/trens), los autobuses (/busos,
ADR 0120) y el tráfico (/transit) (ADR 0053), y el «Canal Temps a Montflorit»
([@TempsMontflorit](https://t.me/TempsMontflorit)), informativo, con la
riera, el peligro, los avisos oficiales nuevos de Meteocat y Protección Civil (los de
AEMET, para lo que Meteocat no avisa: ADR 0093) y la
previsión de las 7 y la de mañana a las 21 (ADR 0055). La web tiene una página de ayuda
con capturas, «Avisos a Telegram». El bot y el envío de las notificaciones
viven en IONOS (ADR 0034 y 0048).

Los avisos de peligro (umbrales de Meteocat para Cerdanyola con lo medido o
lo previsto, ADR 0018), de lluvia en unos 15 minutos (ADR 0022) y de la riera de Sant Cugat (ADR
0027) los recibe todo el mundo igual, por las notificaciones, el bot o el canal.
Hasta el 08-10-2026 el NAS los mandaba además a Juanjo por Telegram; ahora solo
le escribe para lo que es de mantenimiento.

Hasta el 07-10-2026 el repositorio publicaba también la página «Moto o cotxe?»,
que recomendaba un medio para un trayecto fijo, con un agente diario con IA.
Se retiró: su dirección (<https://jjdeharo.github.io/meteo-local/>) lleva a «Si
surts», que hace lo mismo para cualquier salida, y la de «Temps a casa», a
Temps a Montflorit (ADR 0030).

## Cómo funciona

Un contenedor en el NAS de casa (`nas/`) ejecuta `publica.sh` cada cuarto de
hora, todo el día; en modo aviso (aviso de Meteocat o de AEMET, plan de Protección Civil
activado o lluvia en las estaciones o en el radar a menos de 15 km), cada 6
minutos, justo después de cada imagen nueva del radar de Meteocat (ADR 0010 y
0020). El horario lo decide `que_toca.py` con el mismo dato que muestra la web.

`publica.sh` calcula los datos con `casa.py`, deja una copia en el NAS para los
avisos y sube los públicos (`montflorit.json`) a IONOS
(`bilateria.org/app/meteo-local/`), de donde los lee la página. La web, que
genera `montflorit.py` a partir de `web/`, va a su repositorio
(`meteo-montflorit/meteo-montflorit.github.io`, ADR 0028) solo cuando cambia
el código, cada media hora como mucho o si IONOS falla: GitHub admite unas 10
publicaciones por hora, y esa copia es la reserva si IONOS no responde. Las
direcciones antiguas (`jjdeharo.github.io/meteo-local/…`) las redirige el
repositorio aparte `jjdeharo/jjdeharo.github.io` (ADR 0035).

**Reserva en IONOS** (`reserva/`, ADR 0032): si el NAS lleva más de 35
minutos sin subir datos, el hosting de IONOS los calcula con el mismo programa,
los publica marcados como «reserva» y manda los avisos por Telegram en su
lugar; cuando el NAS vuelve, se aparta. Lo monta `reserva/instalar.sh`, y una
prueba diaria avisa si deja de funcionar.

Al subir cambios a `main`, una acción de GitHub pasa las pruebas, y el NAS, que
mira cada minuto si hay código nuevo, publica. Solo publica el NAS.

En cada pasada, la estación particular se sube también a la red de
estaciones personales de Weather Underground (`wunderground.py`, ADR 0059),
y con la clave de lectura de esa red se leen cuatro estaciones vecinas del
barrio (ADR 0060).
A las 16:00 el NAS rellena las horas que falten de la estación particular y la
previsión aprende de sus aciertos (`aprenentatge.py`). En `main` no hay commits
automáticos.

Fuentes de la previsión:

1. **Estaciones**: la particular del barrio (Ecowitt), al minuto, cuya lluvia
   solo cuenta cuando marca (ADR 0017) y cuya presión se reduce al nivel del
   mar (ADR 0037); cuatro vecinas de la red de Weather Underground, cada cinco
   minutos, que también hacen que «plou ara» cuente si alguna marca, y la
   más fiable confirma las horas secas (ADR 0060); y las de Meteocat en
   Sabadell y Sant Cugat, que también confirman las horas secas para
   aprender (ADR 0058). El viento de ahora es
   el de Sant Cugat, por medias horas: el anemómetro de la particular no
   funciona bien (ADR 0037). Además se estima con las vecinas que lo siguen
   bien, llevadas a 10 m con un factor que se aprende cada día; está en
   prueba y la página no lo muestra hasta que se decida (ADR 0064). Las nubes,
   del METAR del aeropuerto de Sabadell, cada media hora, para las nubes bajas
   de la hora en curso (las altas, que el METAR no da, salen de los modelos) y
   para elegir qué mezcla de modelos acierta más (ADR 0088).
2. **Radar** de RainViewer o de Meteocat: una comparación diaria decide cuál
   acierta más, y se usa la imagen de esa salvo que sea más vieja que la de
   la otra (con Meteocat, hasta 15 minutos más vieja; ADR 0026).
3. **Modelos** de Open-Meteo (AROME HD, AROME e ICON-EU, y el ensemble
   ICON-EU-EPS; ECMWF IFS a 9 km, solo para la probabilidad de lluvia, ADR
   0086), con el índice UV del modelo por defecto. El cielo es la mezcla de
   las nubes de AROME, ICON-EU, ECMWF IFS y GFS (ADR 0088). Cada tramo dice
   cuántos grados más o menos que el día antes, con lo medido en la
   estación particular (ADR 0061).
4. **Avisos de AEMET** del Prelitoral de Barcelona y **planes de Protección
   Civil** (ADR 0008).
5. **Trenes**: los avisos de Rodalies, de la API de su web (ADR 0078; si no
   responde, los de Renfe), la posición en tiempo real de Renfe (R4, R7 y R8)
   y de FGC (S2), para «Si surts» (`trens.py`, ADR 0029), con el horario de
   cada línea en Cerdanyola sacado de sus GTFS (ADR 0038).
   **Autobuses**: el horario, las horas de paso en tiempo real y los avisos del
   AMB para las líneas CV1, CV4 y CV5 en las paradas del barrio, para
   «Consultes» y «Si surts» (`busos.py`, ADR 0120; CC BY 4.0).
6. **Tráfico**: las incidencias del Servei Català de Trànsit a 5 km o menos
   (retenciones, accidentes, averías y obras que desvían o cortan la vía), de
   los datos abiertos de la Generalitat (`transit.py`, ADR 0052).
7. **Polen**: los niveles de la semana en Bellaterra del Punt d'Informació
   Aerobiològica de la UAB, con su API (`pollen.py`, ADR 0054; CC BY-NC-SA 4.0).
8. **Calidad del aire**: el índice europeo del modelo CAMS de Copernicus, a
   través de Open-Meteo, para una zona de unos 10 km, corregido con las
   medidas de las estaciones de la Generalitat del último mes (`aire.py`,
   ADR 0054). La salida y la puesta del sol y el índice UV máximo, también de
   Open-Meteo.

Umbrales y lugares, en `config.py`. El porqué, en los ADR.

## Archivos

| Archivo | Para qué |
|---|---|
| `casa.py` | Datos de la web (`casa.json`): lo de ahora, la previsión hora a hora, el índice UV, los trenes, el tráfico y la riera |
| `prevision.py` | Recogida de datos que usa `casa.py`: avisos de AEMET, planes de Protección Civil, radar, lluvia y viento de las estaciones, y el modo aviso |
| `smp.py` | Con un plan de Protección Civil a la vista, si Meteocat tiene aviso de peligro para el Vallès Occidental, leído de meteo.cat o, si falla, de su API (como mucho cada 30 min, ADR 0109), y su prueba diaria (ADR 0067) |
| `config.py` | Coordenadas, horario, estaciones, zonas de aviso, modelos y umbrales |
| `setmana.py` | La previsión de 7 días: ECMWF con la máxima y la mínima corregidas con el error de los últimos 30 días en la estación de casa, y la lluvia del ensemble; se apunta en el registro para comprobarla (ADR 0122). Su validación, `calibracio/setmana.py` |
| `web/` | Las fuentes de la web pública: `casa.html` y `casa.js` (el tiempo ahora), `sortir.html` y `sortir.js` («Si surts»), `perill.html` y `perill.js` («Avisos», antes «Perill»), `riera.html` y `riera.js` («Riera»), `consultes.html` y `consultes.js` («Consultes»), `avisos.html` y `avisos.js` («Notificacions»: avisos en el navegador), `telegram.html` (ayuda de Telegram), `privacitat.html` (qué se guarda y qué no, ADR 0073), `comu.js` (lo común), `estil.css`, `fonts.html` (fuentes y créditos), `manifest.webmanifest`, `sw.js`, `icones/` y `fonts/` (la letra Figtree, ADR 0118) |
| `montflorit.py`, `montflorit/` | Genera la web pública a partir de `web/` y sus datos sin lo privado; manifiesto, iconos y README propios (ADR 0024), y `es.js`, los textos del programa en castellano (ADR 0025) |
| `i18n/` | `es.json`, la traducción de los textos fijos, y `claus.js`, que saca del programa los textos por traducir (ADR 0025) |
| `publica.sh` | Calcula y publica (lo usa el NAS) |
| `entorn.py` | Incendios forestales en curso que interesan al barrio (Bombers: en Collserola y, fuera del parque, a 2 km o menos) y nivel del Pla Alfa de Cerdanyola (Agents Rurals), para la web y los avisos de peligro (ADR 0046 y 0071) |
| `desplegament.py` | Pone al día la copia del repositorio (NAS, reserva y bot) hasta el último commit con las pruebas de GitHub en verde; si GitHub no responde o las pruebas llevan más de 20 minutos sin acabar, despliega igualmente y lo apunta (ADR 0038) |
| `avis_privat.py` | Avisos de mantenimiento a Juanjo por Telegram con cola de reintento si Telegram no los acepta (ADR 0038) |
| `llum.py` | Cortes de luz de e-distribución dentro de los límites del barrio, para «Llum» y `/llum`, y su prueba diaria (ADR 0072) |
| `montflorit-limits.geojson` | Los límites de Montflorit, calcados del mapa de barrios del Ayuntamiento (PLACC 2023) y con el poblado de Ca n'Oliver; para cualquier uso que necesite saber si algo es del barrio (ADR 0072) |
| `montflorit-carrers.geojson` | Las calles con nombre del barrio y alrededores, de OpenStreetMap (ODbL), para estimar la calle probable de un corte de luz (ADR 0072) |
| `eines/limits.py` | Editor de esos límites en un mapa: guarda en un borrador y `aplica` lo pasa a la web (ADR 0072) |
| `eines/fons_radar.py` | Hace el fondo del mapa del radar (`web/img/radar-fons.webp`), del mapa base gris del ICGC; se rehace si cambia el radio del mapa (ADR 0019) |
| `eines/compartir.py` | Hace las imágenes de la vista previa al compartir un enlace (`web/img/compartir-capvespre-{ca,es}.jpg`), con el fondo y el dibujo del atardecer de «Ara» (ADR 0117) |
| `eines/mapa_barri.py` | Dibuja el mapa de esos límites que sale en «Com funciona» (`web/img/montflorit-limits.svg`) y, para el mapa de cada corte de luz, el fondo (`web/img/mapa-base.svg`) y las calles (`web/img/carrers.json`); se rehace al cambiarlos (ADR 0072 y 0077) |
| `avisos_bot.py` | Decide los avisos públicos para el bot y el canal y los deja en `avisos.json`, con el historial de un año de la página «Perill» (ADR 0034 y 0071) |
| `bot/` | Lo que vive en IONOS para repartir avisos: el bot de Telegram, `bot.py` (menú, suscripciones, reparto y resumen, ADR 0034); los avisos en el navegador, `push.py` (envío) y `subscripcio.php` (altas y bajas, ADR 0048); e `instalar.sh` |
| `reserva/` | Servidor de reserva en IONOS: `reserva.py` (vigila, calcula y avisa si el NAS no publica), `avisar-juanjo`, `rep-dades.sh` (recibe los datos que sube el NAS: la orden fija de su clave, ADR 0038) e `instalar.sh` (ADR 0032) |
| `que_toca.py` | Si toca actualizar en este minuto, según el horario publicado |
| `historial.py` | El historial de cada día y el acierto de la previsión para la página «Fiabilitat»: error y sesgo de la temperatura, Brier de la lluvia frente a la climatología, semana a semana, frente a Meteocat y AEMET y cómo aprende (ADR 0099 y 0110) |
| `previsio_oficial.py` | Apunta en el NAS las previsiones por horas de Meteocat (cada 3 horas) y AEMET (cada hora) para Cerdanyola, para compararlas con la de la web (ADR 0110) |
| `nas/` | Contenedor del NAS: `compose.yml`, `Dockerfile` y `reloj.sh`; `copia-registre.sh`, la copia diaria del registro en el repositorio privado `meteo-local-registre`, (ADR 0044) |
| `RESTAURAR.md` | Cómo volver a montarlo todo en otro NAS o en otro hosting, con las claves y el registro de la copia privada (ADR 0044 y 0045) |
| `sol_estacio.py` | Detecta el sol directo sobre el termómetro de la estación de casa y estima la temperatura y la humedad con las vecinas (ADR 0081) |
| `trens.py` | Estado de las líneas de tren de Cerdanyola con los avisos de Rodalies y los datos en tiempo real de Renfe y FGC (ADR 0029 y 0078) |
| `busos.py` | Las líneas de autobús del barrio (CV1, CV4 y CV5): horas de paso por cada parada, con el horario del AMB corregido con su tiempo real, y sus avisos (ADR 0120) |
| `transit.py` | Incidencias de tráfico de cerca, del Servei Català de Trànsit (ADR 0052) |
| `pollen.py` | Polen y esporas de la semana en Bellaterra, del Punt d'Informació Aerobiològica (ADR 0054) |
| `aire.py` | Calidad del aire ahora y lo peor de hoy, del modelo CAMS por Open-Meteo (ADR 0054) |
| `nowcast.py` | La lluvia del radar llevada hacia delante hasta 2 horas (ADR 0019 y 0023) |
| `ecowitt.py` | La estación particular con la API oficial de Ecowitt; las claves, fuera del repositorio (ADR 0017) |
| `wunderground.py` | La estación particular, subida a Weather Underground, y las vecinas de esa red, leídas con su API; las claves, fuera del repositorio (ADR 0059 y 0060) |
| `pluviometre.py` | Comprueba una vez, tras limpiarlo, si el pluviómetro marca la lluvia débil y avisa por Telegram (ADR 0017) |
| `riscos.py` | Situaciones de peligro según lo medido y lo previsto, que usan la página y los avisos (ADR 0018) |
| `fi_pluja.py` | Comprueba a qué hora para la lluvia según el radar, antes de enseñarlo (ADR 0049) |
| `moviment_registre.py` | Registra si el movimiento del radar acierta, comparado con dejar la lluvia quieta y con el viento en altura, y cuánta lluvia crece a 15 km o menos de casa; se decide con un mes de datos (ADR 0019) |
| `pluja_arriba.py` | Cuándo llegará la lluvia que ve el radar (la usa el aviso público de lluvia) y registro de sus aciertos (ADR 0022) |
| `riera.py` | Lluvia en la cuenca de la riera de Sant Cugat y aviso de atención o peligro de desbordamiento, con registro de episodios (ADR 0027) |
| `radar_fonts.py` | Apunta lo que daba cada radar y, cada día, elige el que acierta más (ADR 0026) |
| `nuvols.py` | El cielo de cada hora: mezcla las nubes de cuatro modelos, lee el METAR del aeropuerto de Sabadell y, cada día, elige los pesos que aciertan más (ADR 0088) |
| `nuvols_satellit.py` | El cielo tapado sobre el barrio según la máscara de nubes de Meteosat (EUMETSAT), en observación, y la pregunta a Juanjo cuando discrepa de Sabadell (ADR 0126) |
| `registre.py` | Registro en el NAS de lo medido en Montflorit y en la estación particular, y de lo que daban los modelos, para aprender (ADR 0006 y 0012) |
| `aprenentatge.py` | Aprendizaje de la previsión: regresiones, comprobación y cambio de método (ADR 0012, `docs/estadistica.md`) |
| `calibracio/` | Descarga del histórico, análisis y calibración (los datos, en `dades/`, no se suben) |
| `tests/` | Pruebas sin red |
| `.github/workflows/previsio.yml` | Al subir a `main`: pruebas |
| `docs/adr/` | Registro de decisiones |

## Uso local

```sh
python3 casa.py --json /tmp/casa.json          # los datos, con red
python3 montflorit.py web /tmp/web             # la web pública
python3 montflorit.py dades /tmp/casa.json /tmp/web/montflorit.json
python3 trens.py                               # el estado de los trenes
python3 busos.py                               # los autobuses del barrio
python3 transit.py                             # las incidencias de tráfico de cerca
python3 pollen.py                              # el polen de la semana en Bellaterra
python3 aire.py                                # la calidad del aire
python3 riera.py ara                           # el índice de la riera
python3 calibracio/regla_moto.py               # la regla de lluvia de la moto, con el archivo
python3 -m unittest discover -s tests -b       # pruebas (-b: solo se ve lo que escriben las que fallan)
```

Necesita Python 3 con `numpy` y `Pillow`, y Node para las pruebas de la web.
La estación particular se lee si están las variables `ECOWITT_APPLICATION_KEY`,
`ECOWITT_API_KEY` y `ECOWITT_MAC` o el archivo
`~/.config/meteo-local/ecowitt.env`; sin ellas, todo funciona con Montflorit.
Para ver la web en local, sírvela con un servidor (desde `localhost` no puede
leer los datos de IONOS y usa la copia de su carpeta).

## Comprobaciones tras cada cambio

- Pasan las pruebas.
- La revisión del código no da avisos: `ruff check .` (Python) y `npx eslint
  web montflorit eslint.config.mjs` (JavaScript; antes, una vez, `npm install
  --no-save --no-package-lock eslint@9.39.1 globals@16.5.0`). GitHub las pasa en cada
  cambio, con la cobertura de las pruebas en el resumen (ADR 0112).
- La web carga en Firefox, Chromium y WebKit, en móvil y escritorio, en tema
  claro y oscuro, sin desbordamiento horizontal (`probar-web`).
- Si cambia el HTML, el CSS o el JavaScript que crea o modifica elementos de
  la página, axe-core no encuentra incidencias.
- Con una fuente caída, la web lo avisa y sigue mostrando lo demás.
- Con datos de más de 2 horas, la web solo muestra el aviso y enlaces
  oficiales (ADR 0031); si los datos de IONOS llevan más de una hora sin
  renovarse, el vigía de IONOS avisa a Juanjo (desde que existe la reserva,
  ADR 0032, eso solo pasa si fallan el NAS y la reserva: una caída del NAS
  sola la avisa la propia reserva a los 35 minutos).

## Fuentes y licencias

Previsión de [Open-Meteo](https://open-meteo.com/) (CC BY 4.0), observaciones
de [Meteocat](https://www.meteo.cat/observacions/xema) y del
[portal de datos abiertos de la Generalitat](https://analisi.transparenciacatalunya.cat/d/nzvn-apee),
estación particular con la [API de Ecowitt](https://doc.ecowitt.net/web/#/apiv3en?page_id=1),
estaciones vecinas de [Weather Underground](https://www.wunderground.com/) (The
Weather Company; uso personal y no comercial),
nubes observadas en el aeropuerto de Sabadell (METAR) del
[Aviation Weather Center](https://aviationweather.gov/data/api/) de la NOAA,
radar y advección de [Meteocat](https://www.meteo.cat/observacions/radar) y,
de reserva, de [RainViewer](https://www.rainviewer.com/), avisos de AEMET a
través de [Meteoalarm](https://meteoalarm.org/), avisos de trenes de la
[web de Rodalies de Catalunya](https://rodalies.gencat.cat/), y trenes de
[Renfe](https://data.renfe.com/) y de las
[dades obertes d'FGC](https://dadesobertes.fgc.cat/) (las dos, CC BY 4.0), e
incidencias de tráfico del
[Servei Català de Trànsit](https://transit.gencat.cat/es/informacio-viaria/estat-transit/)
(Generalitat de Catalunya, Departament d'Interior i Seguretat Pública), de los
[datos abiertos de la Generalitat](https://analisi.transparenciacatalunya.cat/d/uyam-bs37),
con la [licencia abierta de uso de información de Cataluña](https://web.gencat.cat/es/generalitat/dades-indicadors/dades-obertes/llicencies);
el polen de Bellaterra, del [Punt d'Informació Aerobiològica de la UAB](https://aerobiologia.cat/pia/es/forecast/bellaterra)
(CC BY-NC-SA 4.0: no se puede usar con fines comerciales), y la calidad del
aire, del [Copernicus Atmosphere Monitoring Service](https://atmosphere.copernicus.eu/)
a través de Open-Meteo.
Iconos de [Lucide](https://lucide.dev/) (ISC). Los datos de terceros se
consultan automáticamente: el autor no se hace responsable de su exactitud.

Código bajo AGPL-3.0-or-later ([LICENSE](LICENSE)); contenidos bajo CC BY-SA
4.0 ([LICENSE-CONTINGUTS.md](LICENSE-CONTINGUTS.md)). Hecho con IA (Claude Code): qué hace la IA y qué revisa el autor, en
[«Com s'ha fet»](https://meteo-montflorit.github.io/fonts.html#com-sha-fet).
