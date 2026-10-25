# 54. Página «Consultes», y el sol, el aire y el polen en la web y en el bot

Fecha: 2026-10-09 · Estado: aceptado

## Contexto

Juanjo preguntó cómo dar en la web lo mismo que el bot, para quien usa la
aplicación: «que el que use la app pueda acceder a la misma información que el
bot». Descartó un botón en la cabecera y una página con todo: quería una
tercera pestaña junto a «El temps» y «Si surts», aunque repita lo que ya está en
otras páginas, porque «es más fácil a veces ir a donde sabes que está», y que
funcione como el bot: «se elige lo que se quiere ver y entonces sale». Quitó
después «Ara», «Radar» y «Avisos actius», que ya se ven en «El temps», y pidió
añadir el polen, la calidad del aire y el sol, también en el bot.

## Decisión

- **Página «Consultes»** (`web/consultes.html` y `web/consultes.js`), con su
  pestaña en el menú de todas las páginas (icono «message-square-text» de
  Lucide); el nombre puede cambiar más adelante (Juanjo: «luego valoraremos si
  lo cambiamos»). Siete opciones, en el orden del bot: Avui, Demà, Sol, Aire,
  Pol·len, Trens y Trànsit. Se marca una y debajo sale solo su texto. Al
  entrar, la última vista en ese dispositivo o, la primera vez, «Avui»; cada
  opción tiene su dirección (`consultes.html#pollen`).
- **Los textos son los del bot**, hechos por sus mismas funciones en el NAS al
  publicar (`montflorit.py`, `consultes`): web y bot dicen siempre lo mismo,
  en catalán y en castellano. Llevan el HTML de Telegram (`<b>`, `<i>` y
  `<a>`); la página lo lee sin `innerHTML` y solo enlaza direcciones `https`.
  «Demà» llega hasta donde llega la previsión, 24 horas, como en el bot.
- **Polen** (`pollen.py`, `/pollen`): el nivel de la semana de cada tipo de
  polen y de espora en la estación de Bellaterra (campus de la UAB, a 3,1 km) y
  su tendencia, de la API del Punt d'Informació Aerobiològica
  (`aerobiologia.cat/api/v0/forecast/bellaterra/{ca,es}/xml`), guardada 3 horas.
  Se dicen los niveles de más a menos, los tipos en aumento aunque estén a
  cero y, si la semana ya ha pasado, que son los últimos publicados. Licencia
  CC BY-NC-SA 4.0, con el enlace a su página junto a los datos y en los
  créditos; se les avisó por correo el 09-10-2026, como piden.
- **Calidad del aire** (`aire.py`, `/aire`): el índice europeo de calidad del
  aire del modelo CAMS Europa de Copernicus, que sirve Open-Meteo, ahora y el
  peor momento de lo que queda de hoy, con los nombres del índice español
  (bona, raonablement bona, regular, desfavorable, molt desfavorable,
  extremadament desfavorable) y el contaminante que más pesa. El texto dice que
  es un modelo y no una medida, y enlaza la web de la Generalitat con las
  medidas de las estaciones.
- **Sol** (`casa.py`, `sol`, `/sol`): salida y puesta del sol, horas de luz e
  índice UV máximo de hoy, con el consejo de «Si surts» desde 3, y la salida y
  la puesta de mañana, de Open-Meteo.
- En el bot siguen `/ara`, `/radar` y `/avisos_actius`: en un chat no hay otra
  página donde verlos.

## Cambio del 09-10-2026 (3.35.0): fichas más visuales

Juanjo, ante el polen en texto: «podríamos poner los niveles de forma algo más
visual?… es una sección un poco aburrida»; después pidió lo mismo para el aire y
el resto de fichas. En la web, ya no todas son el texto del bot:

- **Polen**: una fila por tipo con una barra de 4 tramos del color de su nivel
  (verde bajo, amarillo medio, naranja alto, rojo máximo, los de los avisos) y
  la tendencia (↑ ↓); los que están a cero y estables, en una línea. El bot
  añade también esa línea («Nul: Olivera, …»): a la persona alérgica le sirve
  saber que su polen no está.
- **Aire**: la escala europea con los colores oficiales de la Agencia Europea
  de Medio Ambiente y una marca donde está ahora, una barra por contaminante y
  la evolución hora a hora del resto del día (`aire.py` guarda ahora el índice
  de cada contaminante y de cada hora).
- **Sol**: desde el 25-10-2026 (3.200.0), el recorrido del sol de hoy sobre
  el horizonte de Montflorit, en un cuadrado (Juanjo, tras pedirlo más alto
  dos veces: «para evitar problemas, hazlo cuadrado»): en el móvil, de todo
  el ancho de la ficha («que la gráfica ocupe todo el ancho»); desde 640 px,
  no («y en pantallas anchas que no ocupe el 100%»): el cuadrado a la
  izquierda, del 55 % del ancho y 560 px como mucho, y el texto al lado, como
  pide su criterio de que lo apilado en el móvil vaya en fila en el
  ordenador. De
  7° bajo el horizonte a 76° sobre él (la franja de la noche, «a la mitad»;
  arriba, los 72° de junio y el sitio justo para su cifra: «sobra mucho
  espacio por arriba»), con el sol donde está ahora (de noche, hueco y al fondo de la
  franja de la noche). Juanjo enseñó el de la app LunaSolCal: «algo parecido
  a esto … adáptalo como quieras … centrado en Montflorit». Como allí, las
  líneas de la salida, el mediodía y la puesta con su hora arriba, la altura
  máxima y, finos, el 21 de junio (rayas) y el 21 de diciembre (puntos) para
  comparar, con el nombre en la leyenda: en el dibujo no cabía sin tocar las
  curvas. Las curvas se calculan en tiempo universal y se dibujan todas con
  la hora oficial de hoy (Juanjo: «el cambio horario no debe nunca
  distorsionar resultados … internamente siempre utc»): las tres culminan
  juntas, como en la app, y la de junio no sale una hora más tarde por el
  horario de verano; las horas que se leen, las de hoy, son las del reloj. El
  eje va centrado en el mediodía de hoy, con tanto a cada lado como hay del
  mediodía a la salida o la puesta del 21 de junio, la más lejana, y media
  hora más: de 0 a 24 h «sobra mucho espacio por los lados», y redondeado a la
  media hora el día de hoy no quedaba simétrico. Las curvas de junio y
  diciembre culminan hacia las 12:50 y la de hoy, en octubre, a las 12:35: es
  la ecuación del tiempo, real, y no se corrige. El dibujo se hace al ancho
  de la ficha en píxeles (y se rehace si cambia), para que la ocupe entera
  con la letra siempre del mismo tamaño. A diferencia de la app, la dirección va en palabras en el texto,
  no en grados: «Surt a les 7:14 per
  l'est i es pon a les 17:55 per l'oest: 10 h 41 min de llum. A les 12:35, el
  migdia, puja fins a 36° sobre l'horitzó.» La posición sale de la fórmula
  de la NOAA que ya usaba `alturaSol` (`posicioSol`, en `comu.js`, que ahora
  da también el azimut); comprobada con la app el mismo día: a las 7:37, 3,1°
  de altura y 109,2° de azimut en las dos, y 36,3° a mediodía. La salida y
  la puesta siguen siendo las de los datos, como en la tabla. Sustituye a la
  barra del día, que decía lo mismo con menos. El índice UV, en una pastilla
  con los colores de la OMS.
- **Avui y Demà**: el texto del bot con un icono por línea (temperatura,
  lluvia, avisos, trenes, ropa).
- **Trens y Trànsit**: las mismas fichas de color que «Si surts»; esas piezas
  pasan a `comu.js`, que comparten las dos páginas.

El bot sigue en texto: Telegram no admite colores ni barras.

## Cambio del 09-10-2026 (3.37.0): el aire, corregido con las estaciones

Juanjo preguntó si la calidad del aire era de verdad la de Montflorit. No lo
es: CAMS da un valor por celda de 0,1° (unos 11 × 8 km); la de Montflorit tiene
el centro en Bellaterra (41,5 N, 2,1 E). Comparado con las estaciones de la
Generalitat la noche del 8 al 9 de octubre, el modelo daba de NO₂ 22-36 µg/m³
y las estaciones 6-26; de partículas PM10, 9-10 frente a 16-26 en Montcada.
Juanjo pidió las tres cosas propuestas, sin quitar las barras de colores:

- **La ficha dice qué es**: «Estimació del model europeu CAMS per a una zona
  d'uns 10 km al voltant de Bellaterra, no mesurada a Montflorit», y qué se ha
  corregido.
- **Las últimas medidas de Barberà, Sant Cugat y Montcada**, con su hora y su
  categoría (llegan con 7 u 8 horas de retraso). Quitadas en la 3.37.1: «para
  los vecinos es ruido». Se siguen usando, por dentro, para la corrección.
- **El modelo, corregido con lo medido** (`aire.py`): una vez al día, para cada
  contaminante, el cociente entre la suma de lo medido (media de las
  estaciones) y la del modelo en las horas del último mes que tienen las dos
  cosas (Open-Meteo guarda los días pasados); las concentraciones se
  multiplican por él y el índice se recalcula con la tabla del índice europeo
  de Open-Meteo. Solo con al menos dos estaciones y 72 horas: el 09-10-2026,
  NO₂ ×0,70 y ozono ×0,71 (725 horas). Las PM10 solo las mide Montcada, junto a
  la cementera, y su factor (×2,5) diría más de Montcada que de Montflorit: no
  se corrigen. Es una corrección media, hipótesis a validar: no cambia según la
  hora ni el tipo de día.

Corrección del 09-10-2026 (3.39.0): la clase `.opcio` de los botones de
«Consultes» ya existía en las páginas «Avisos» y «Avisos a Telegram», y sus
estilos (fondo oscuro al estar marcado, forma de pastilla) se les aplicaban:
el recuadro de «Avisos» salía oscuro y con poco contraste. Pasa a
`.consulta-opcio`.

## Alternativas descartadas

- **Un botón en la cabecera** que desplegara las consultas, y **una página con
  todo a la vez**: Juanjo prefirió una pestaña y ver una sola cosa.
- **La calidad del aire medida por la Generalitat** (XVPCA, datos abiertos
  `tasf-thgu`), con estaciones en Barberà (3,5 km), Sant Cugat (3,9 km) y
  Montcada (4,4 km): el 09-10-2026 a las 11:40 sus datos llegaban hasta las 4
  h, con 7 u 8 horas de retraso, y no sirven para decir cómo está el aire ahora.
- **Polen en tiempo real** del equipo automático del campus (SwisensPoleno,
  ligado al proyecto AtPollenFluo, PID2020-117873RB-I00, que dirige el
  CIEMAT): publicó lecturas del ciprés en `aerobiologia.cat/tr` desde marzo de
  2023, «en desarrollo», pero esa dirección redirige a la portada (ya en julio
  de 2024) y el acceso está comentado en el código de la portada. Preguntado
  el PIA, Jordina Belmonte respondió el 09-10-2026 que ya no tienen ese
  captador y que por ahora no saben si podrán volver a publicarlas.

## Consecuencias

- `montflorit.json` pasa de unos 10,7 KB a unos 19 KB, con `consultes`, `sol`,
  `aire` y `pollen`.
- Tres consultas más por pasada a Open-Meteo (sol y aire) y, cada 3 horas, dos
  al Punt d'Informació Aerobiològica; la reserva de IONOS guarda también el
  polen (`POLLEN_DIR`).
- Los datos del polen no son CC BY-SA como el resto de contenidos: los créditos
  lo dicen.
- Hay que volver a registrar las órdenes en Telegram (`bot/instalar.sh`).

## Evidencia

- API del polen probada el 09-10-2026 (respuestas guardadas en `tests/dades`):
  semana del 5 al 11 de octubre, artemisa y compuestas en nivel medio,
  Alternaria y Cladosporium en máximo, cipreses a cero y en aumento. Su página
  `aerobiologia.cat/pia/ca/api` da la licencia y pide avisar por correo; la
  dirección (`aerobiologia.pia@uab.cat`) es la de `aerobiologia.cat/pia/ca/terms`.
- Open-Meteo, documentación de la API de calidad del aire: índice europeo por
  tramos de 0-20, 20-40, 40-60, 60-80, 80-100 y más de 100, del modelo CAMS
  Europa de 11 km; pide citar CAMS y Open-Meteo.

## Validación

`tests/test_consultes.py` (lectura de la API del polen, texto del polen y aviso
de semana pasada, categorías y texto del aire, texto del sol, que las consultas
de la web son las del bot, lectura del HTML de Telegram sin `innerHTML` y orden
de las opciones). `probar-web` de «Consultes» en Chromium y Firefox,
escritorio, móvil y tableta, claro y oscuro, en las dos lenguas; axe-core sin
fallos en «Consultes», «El temps» y «Fonts i crèdits».

## Cambio del 09-10-2026: la corrección del aire, solo si acierta más

El factor se aplicaba sin comprobar que mejorara el modelo (limitación
anotada en la auditoría del 09-10-2026, ADR 0057). Ahora `valida_factor`
calcula, para cada día de los 30, el factor con los demás días y lo aplica
a ese; el factor se adopta solo si el error medio corregido es al menos un
5 % menor que el del modelo sin corregir (`AIRE_MILLORA`). Los descartados
quedan en `aire-correccio.json` con sus dos errores, y la página y el bot
solo dicen «corregit» de los adoptados. `tests/test_aire.py` (nuevo): un
sesgo constante se corrige; uno que cambia de signo entre días se descarta.

## Cambio del 13-10-2026: la salida y la puesta del sol, también en la tabla

Juanjo pidió indicar en la tabla de la previsión, «de algún modo que no
estorbe», la salida y la puesta del sol. En la fila de la hora en que pasan,
al lado del cielo: el icono de Lucide (`sunrise`, `sunset`) y la hora sin cero
delante (8:02, como «8–9»), en gris y pequeños; para los lectores de pantalla,
«Surt el sol a les…» y «Es pon el sol a les…». Hasta 480 px van en la línea
del icono del cielo, que tenía sitio; si no caben, bajan de línea dentro de su
casilla, nunca encima de la columna de al lado. Medido en Chromium y Firefox
en 17 anchuras: de 320 a 400 px y desde 540 px, la fila mide lo mismo que las
de su mismo cielo sin marca; a 412-500 px y justo a 640 px, una línea más (la
columna del cielo no da para el icono, el texto en dos líneas y la hora).
«Com es llegeix la previsió» lo explica con los dos iconos.

