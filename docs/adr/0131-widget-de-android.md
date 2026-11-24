# 131. Widget de Android con la tarjeta de «Ara»

Fecha: 2026-11-24 · Estado: aceptado (la parte de los datos, publicada; la app 1.1.0, en la prueba interna de Google Play desde el 24-11-2026 a las 9:58, pendiente de probarla en el móvil de Juanjo y de enviarla a producción)

## Contexto

El 24-11-2026 Juanjo preguntó si se podía poner en la pantalla de inicio de
Android la tarjeta de «Ara» de la portada (la frase del día, la lluvia
prevista, la temperatura, la máxima y la mínima, el dibujo del cielo y la
Luna). Lo pidió completo, con el título «Temps a Montflorit (Cerdanyola)» y
«con aspecto profesional, como los del tiempo de grandes aplicaciones», y sin
la hora del dato, como los widgets de tiempo de Google («los widgets de tiempo
creo que no llevan la hora, hay que inspirarse en ellos»). Se aceptó la
propuesta del agente de avisar solo cuando el dato sea viejo.

La app de Play es una TWA (ADR 0082): la web dentro de Chrome, sin código
propio. Un widget de Android sí necesita código propio, y no puede mostrar
una página web: se dibuja con las piezas de Android (textos, imágenes). El
estándar de widgets para webs instaladas solo funciona en Windows.

## Decisión

Versión 3.239.0 de la web; versión 1.1.0 (código 2) de la app; con la gota de la lluvia, 3.239.1 y 1.1.1 (código 3).

- **Los textos, del mismo código de la web.** `giny.js` carga `comu.js`,
  `grafica.js` y `casa.js` (y `montflorit/es.js` para el castellano) en Node
  con un DOM mínimo, llama a `blocAra`, la función que pinta la tarjeta, y
  lee sus textos. El resultado es `giny.json`, de unos 2 KB, con la tarjeta
  en catalán y en castellano: título, frase, línea de la lluvia, temperatura,
  máxima y mínima con la comparación con ayer, la hora del sol en el alba y
  la posta, la fase de la Luna, las pastillas (lluvia de ahora, viento) y el
  cielo (fondo y dibujo). Nada de la lógica se repite en Java: el widget dice
  lo mismo que la web, con la zona por defecto (la riera). La cuenta atrás de
  la lluvia («d'aquí a unes 10 hores») va aparte, con su hora y los textos de
  `textCompte` en cada idioma, y el widget la vuelve a calcular cada vez que
  se pinta, porque los datos pueden tener media hora.
- **Lo genera el NAS en cada publicación** (`publica.sh`, después de
  `montflorit.json`) y va a IONOS con los demás datos; `reserva/rep-dades.sh`
  acepta `giny.json` desde esta versión. También va en la copia de la web en
  GitHub, de donde lo lee el widget si IONOS no responde. Si Node falla, no
  se publica y el widget se queda con el anterior. La reserva de IONOS no
  tiene Node: si el NAS cae, el widget dice de cuándo son los datos.
- **El widget** (`android/giny/`): `GinyProvider` descarga `giny.json` cada
  media hora (el mínimo de Android, `updatePeriodMillis`), lo guarda y lo
  pinta. Si no puede descargarlo, vuelve a probar a los 10 minutos (una
  alarma inexacta, sin permisos) y, mientras no tiene datos, tocarlo lo
  vuelve a pedir. Cinco formas según el tamaño, con las medidas de un Pixel
  (24-11-2026: el 4×1 mide unos 290×90 dp; el 2×2, 140×185; el 4×2,
  290×185, y el 4×3, 290×280):
  - **una fila** (menos de 125 dp de alto): dibujo, temperatura, lugar,
    máxima y mínima;
  - **pequeña** (menos de 220 dp de ancho): «Montflorit», dibujo,
    temperatura, máxima y mínima, y la frase si mide 260 dp de alto o más;
  - **mediana baja** (de 125 a 170 dp de alto): título, frase en dos líneas,
    temperatura, dibujo y «Avui: màx. 15°, mín. 5° · semblant a ahir»;
  - **mediana alta** (de 170 a 250 dp, el 4×2 de la mayoría de móviles y la
    que sale al ponerlo): lo mismo con la frase en tres líneas, como la
    tarjeta de la web;
  - **grande** (250 dp o más, el 4×3): la tarjeta entera, con la lluvia
    prevista en la pastilla azul de la web, el sol y la Luna.

  Android 12 o posterior recibe una forma para cada tamaño que puede tener el
  widget (en vertical y en horizontal) y elige él; con el tamaño de verdad, el
  widget mide si la comparación con ayer cabe en la misma línea y, si no, la
  pasa a la de abajo (en la mediana alta) o la deja (en la baja). En Android
  11 o anterior, el widget elige la forma con el tamaño que le da el
  lanzador. Al tocarlo se abre la app. En el selector de widgets, una muestra
  con un día de ejemplo (Android 12 o posterior) o una captura del widget de
  verdad en el idioma del móvil (antes).
- **El aspecto, el de la tarjeta.** Los fondos de los 15 cielos se fotografían
  de `web/estil.css` con Chromium y los dibujos son los mismos de Meteocons,
  en WebP (108 KB en total); los colores del texto de cada cielo (los dos
  textos, el rojo de la máxima, el azul de la mínima y si llevan el reborde
  blanco) se leen del CSS con el navegador y se escriben en `GinyEstil.java`.
  Lo hace `android/giny/recursos.py`, que hay que volver a ejecutar si
  cambia la tarjeta. La Luna se dibuja como `dibuixLluna` (`GinyLluna`).
  Esquinas redondeadas con el radio del sistema en Android 12 o posterior;
  letra del sistema.
- **Sin la hora del dato**: con datos de 2 horas o más, el título añade «dades
  de fa 3 h» («datos de hace 3 h»; en la fila y la pequeña, «fa 3 h») y la
  temperatura sale en gris.
- **El idioma, el del móvil**: catalán si el móvil está en catalán; si no,
  castellano. El widget no puede leer el idioma elegido dentro de la app.
- **Fuera de `app/src`.** `bubblewrap update` borra `app/src` entero y lo
  vuelve a generar (comprobado al subir a la 1.1.0: se llevó el widget). El
  código y los recursos del widget están en `android/giny/main/`;
  `android/construeix.sh` los copia a `app/src/main/` y
  `android/giny/manifest.py` pone el receptor y el permiso de internet en el
  manifiesto antes de compilar. Las copias no van al repositorio
  (`android/.gitignore`).

## Cambio del 24-11-2026: la gota de la lluvia en los widgets pequeños

Juanjo, ya con el widget de 4×2 en su móvil, preguntó «lo de la lluvia no
sale?»: la línea de la lluvia solo cabía en el de 4×3. Aprobó la propuesta de
una gota con la lluvia en corto, al estilo de los widgets de tiempo («sí,
hazlo»). Desde la 3.239.1, `giny.js` da también `gota`, con el mismo criterio
que la línea de debajo de la frase (`titularAra`): si llueve, «Plou»
(«Llueve»); si el radar la ve llegar, la hora o la franja del radar; si no, la
primera hora de lluvia prevista y su probabilidad («19 h · 22 %»). Sin
lluvia, nada. En la mediana, entre la temperatura y el dibujo; en la pequeña,
debajo de la máxima y la mínima, y en la de una fila, como tercera línea si
mide 70 dp de alto o más. La gota es «droplet» de Lucide, en el azul de la
mínima de cada cielo. La app pasa a la 1.1.1.

## Alternativas descartadas

- **Rehacer en Java la lógica de la tarjeta**: dos programas que dirían cosas
  distintas en cuanto cambiara uno (ADR 0101, «todo lo que dice la web tiene
  que cuadrar»).
- **Que el NAS dibuje el widget como imagen**: el mismo aspecto sin esfuerzo,
  pero el texto no se adapta al tamaño ni se lee con el lector de pantalla, y
  pesa más.
- **Leer `montflorit.json` desde el widget**: 60 KB cada media hora en lugar de
  2 KB, y habría que repetir la lógica.

## Riesgos

- Android puede retrasar las actualizaciones con el móvil en reposo; el aviso
  de datos viejos lo cubre.
- En Android 11 o anterior, sin esquinas redondeadas.
- Solo en la app de Play: en iPhone o con la web instalada no hay widget.
- Play revisa la versión nueva: la app pide ahora el permiso de internet (de
  los que no se preguntan) y sigue sin recoger datos.

## Validación

- `tests/test_giny.py`: la tarjeta de los datos del 24-11-2026 a las 9:05 en
  catalán y en castellano, la línea de la lluvia con la cuenta atrás aparte,
  los textos de la cuenta atrás, el cielo de noche, sin datos de ahora, y que
  cada cielo y cada dibujo que puede pedir `casa.js` tiene su recurso en la
  app. `tests/test_rep_dades.py`: IONOS acepta `giny.json`.
- Con los datos de las 9:00 del 24-11-2026, `giny.js` da lo mismo que la
  tarjeta de la web que Juanjo capturó esa mañana.
- La app 1.1.0 compila (`android/construeix.sh`, APK de 1,2 MB, AAB de
  1,3 MB; pide además el permiso de internet).
- En el emulador de Android 15 con la pantalla de un Pixel 7 (1080×2400, 420
  ppp), con los datos publicados: la mediana alta, la grande, la pequeña y la
  de una fila, en castellano y en catalán (el idioma de la app cambiado con
  `cmd locale set-app-locales`), y con los fondos de noche, alba y lluvia, el
  aviso de datos viejos y la frase en la pequeña forzados en compilaciones de
  prueba que no se guardaron. Al tocarlo se abre la app. El lector de
  pantalla lee «Temps a Montflorit (Cerdanyola). 8 °C. Aquest matí…».
- Dos fallos encontrados así y corregidos: Android no deja usar `Space` en un
  widget («Class not allowed to be inflated»), y el 4×2 del Pixel es más alto
  de lo previsto y salía la forma grande cortada.
- Sin probar: Android 11 o anterior (no hay imagen del emulador) y el móvil de
  Juanjo.
