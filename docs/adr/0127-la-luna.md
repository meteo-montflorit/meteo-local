# 127. La Luna: la fase en «Ara» y en la gráfica, y sus datos en «Sol i lluna»

Fecha: 2026-10-25 · Estado: aceptado

## Contexto

Juanjo pidió el 25-10-2026 tres cosas de la Luna: «12h antes y después de una
fase de la luna salga en la tarjeta de avui», «que salga la fase en la gráfica
horaria, solo en la hora que le corresponde» y «datos de la luna en la pestaña
de sol (que deberá cambiar de nombre)». Las fuentes que ya usa el programa
(Open-Meteo, Meteocat, AEMET) no dan la Luna.

## Decisión

Versión 3.200.0, con el recorrido del sol de «Consultes» (ADR 0054).

- **El cálculo, en el NAS** (`lluna.py`), con **Astronomy Engine** de Don
  Cross (licencia MIT, versión 2.1.19), copiado sin cambios en
  `tercers/astronomy.py` con su origen en `tercers/README.md`: un solo archivo
  de Python, sin red ni dependencias. `casa.py` añade a los datos `lluna`: el
  ángulo de la fase (0 nueva, 90 cuarto creciente, 180 llena, 270 cuarto
  menguante), la parte iluminada en %, las cuatro fases principales desde dos
  días antes hasta un mes después, y la salida y la puesta de hoy y de mañana
  (`null` el día del mes en que no sale o no se pone). Se calcula en tiempo
  universal y las horas salen en hora local con su desfase, como pidió
  Juanjo para toda la web el mismo día («internamente siempre utc y al
  mostrar datos los adaptas al horario actual»).
- **«Ara»**: de 24 horas antes a 24 después de una fase principal, debajo
  del dibujo del cielo, con su dibujo pequeño delante: «Lluna plena: demà,
  5:12» (con el día solo si no es hoy), con la misma forma que «Sortida del
  sol: 7:14» (ADR 0121) y en el mismo hueco, para que la tarjeta no crezca
  (Juanjo: «para no aumentar la altura de la tarjeta no se puede poner encima
  o debajo del sol o la nube?»; al principio era una pastilla). Si coincide
  con la hora del sol, una línea debajo de la otra. En el móvil, el texto
  largo («Quart minvant: demà, 5:12») pasa a dos líneas; a 320 px, a tres.
  Medido en Chromium, Firefox y WebKit: con una línea, la tarjeta mide lo
  mismo; con dos, unos 8 px más a 393 px y 13 a 360. Fuera del margen de 12
  horas, nada (`FASE_A_PROP_H`, `faseAProp`). Solo si no hay dibujo del
  cielo, va en una pastilla. El dibujo y lo que lleva debajo suben unos 6 px
  en el móvil y 8 en el ordenador, con la misma altura total («un poco más
  arriba, así no toca el margen inferior»): el texto queda a 11-12 px del
  borde en vez de 2-6. Con texto debajo, los dibujos que llegan hasta abajo
  (el sol de día, la lluvia, la niebla) se reducen al 84 % desde arriba para
  que el texto no pise los rayos; el alba y la puesta, no, porque tienen la
  parte de abajo vacía.
- **La gráfica horaria**: la fase solo en la columna de la hora en que pasa,
  a media altura de la zona de la temperatura y con su nombre al lado
  («Lluna plena»), sobre el fondo de la gráfica para que la curva no la tape;
  si no cabe a la derecha, a la izquierda. Va por encima de la curva y las
  barras y por debajo de las zonas de cada hora, que siguen abriendo su ficha.
  La leyenda no la repite desde la 3.204.1: ya lleva el nombre en la gráfica
  (Juanjo, 25-10-2026). Hasta la 3.203.0 iba pequeña en la fila de
  los días, sin nombre, y quedaba en el borde de arriba (Juanjo, 25-10-2026:
  «preferiría que estuviese por enmedio del grafico … con una etiqueta visible
  indicando la fase»).
- **«Consultes»**: la pestaña «Sol» pasa a «Sol i lluna» (la dirección sigue
  siendo `consultes.html#sol`). Debajo del sol, «La lluna avui a Montflorit»:
  la Luna dibujada como se ve, la fase de ahora y la parte iluminada («Lluna
  plena, il·luminada al 100 %»), la salida y la puesta por orden, y las
  próximas cuatro fases con su día. La fase de ahora se nombra con la
  principal si está a 24 horas o menos (la misma regla que «Ara»); si no,
  con la de paso: creciente, gibosa creciente, gibosa menguante, menguante.
- **El dibujo, propio y fiel** (`dibuixLluna`): el disco oscuro, el lado
  iluminado (a la derecha cuando crece, desde el hemisferio norte) y el
  terminador como media elipse de anchura |cos ángulo|, con el ángulo real.
  Los dibujos de fases de Meteocons no se usan: en ellos el cuarto creciente
  es una hoz y la luna nueva no se ve.

## Alternativas descartadas

- **Calcularlo en el navegador** (Astronomy Engine en JavaScript o SunCalc):
  más peso en cada página, y la portada lo cargaría siempre. Los datos se
  toman de donde se generan.
- **SunCalc**: más ligero, pero menos preciso en la hora de las fases.
- **Los dibujos de Meteocons**: no son fieles a la fase real.

## Consecuencias

- `casa.json` y los datos públicos llevan `lluna`. Sin ella (datos de antes),
  la web no enseña nada de la Luna.
- El bot no da la Luna; si se pide, `lluna` ya está en los datos.

## Evidencia

- Luna llena del 26-10-2026: Astronomy Engine da las 4:12 UTC (5:12 en hora
  oficial); Moongiant da las 4:11 UTC y Star Walk, las 4:12 GMT (consultado
  el 25-10-2026).
- `tercers/astronomy.py`: el del wheel `astronomy_engine-2.1.19-py3-none-any.whl`
  de PyPI (subido el 14-12-2023), con SHA-256 `232ba7dd2bbf42225c48be6721b676e8c6c079dbd4588d2781dfa68adcb6f67f`,
  el que publica PyPI. Solo importa la biblioteca estándar.

## Riesgos y limitaciones

- La salida y la puesta son para el horizonte matemático a 70 m de altitud:
  con Collserola delante, la Luna se ve salir o ponerse unos minutos más
  tarde o antes según la dirección. Pasa igual con el sol (datos de
  Open-Meteo).
- Si Astronomy Engine falla, `lluna` queda en `None` y un error en la lista
  de errores, como el sol y el aire.

## Validación

- `tests/test_lluna.py`: la luna llena del 26-10-2026 a las 4:11-4:13 UTC y
  con «+01:00»; las fases en orden, con la de antes; el mismo resultado
  pedido con dos desfases distintos; la salida y la puesta del día local, y
  uno a tres días al mes sin una de las dos.
- `tests/test_web.py`: la fase sale de 24 horas antes a 24 después y no
  fuera; «demà, 5:12»; los nombres de las fases de paso.
- En el navegador, con el reloj a las 20:00 del 25-10-2026 y los datos de
  esa hora: «Lluna plena: demà, 5:12» bajo el dibujo de «Ara», la Luna en la
  columna de 5 a 6 de la gráfica con su leyenda, y «Sol i lluna» con la Luna,
  en Chromium, Firefox y WebKit, móvil y escritorio, claro y oscuro; axe-core
  sin incidencias.

## Cambio del 25-10-2026 (3.204.0): 24 horas, la gráfica de la Luna, el enlace y la opción

### 24 horas en lugar de 12

Con 12 horas, la Luna llena del 26-10 a las 5:12 salía en «Ara» el domingo
por la tarde y desaparecía el lunes a las 17:12, antes de que la Luna saliera
esa noche, iluminada aún al 99 %. La fase se ve casi igual las dos tardes y
noches que la rodean, así que la ventana es de 24 horas antes y después
(`FASE_A_PROP_H`), en «Ara» y en «Consultes». La gráfica por horas la sigue
marcando solo en su hora. Lo propuso el agente y Juanjo lo aprobó: «sí, ponlo
a 24 horas».

### La gráfica del arc de la Luna en «Sol i lluna»

Juanjo, 25-10-2026: «puedes hacer un grafico similar al del sol para la luna
del dia?». El mismo cuadrado que el del sol, con el texto al lado en pantallas
anchas: la altura de la Luna cada 10 minutos (`lluna.recorregut`, Astronomy
Engine con la refracción), las horas de noche más oscuras (cuando el sol está
bajo el horizonte, para ver cuándo se ve con el cielo negro), las líneas de la
salida, el momento más alto y la puesta con su hora, y la Luna, con su fase,
donde está ahora si está dentro del dibujo.

No es el día de reloj: la Luna sale cada día unos 50 minutos más tarde y el día
de 0 a 24 h la cortaría a media noche. Son 24 horas centradas en su momento
más alto, del arco que interesa: si ahora está sobre el horizonte, el de ahora;
si no, el siguiente (a mediodía, el de esa tarde y noche, no el de la noche
pasada). El texto dice ese arco como el del sol: «Surt avui a les 17:14 per
l’est i es pon demà a les 07:37 pel nord-oest. A les 00:18 puja fins a 64°
sobre l’horitzó.» Con datos de antes de la 3.204.0, sin recorrido, el dibujo
grande de la fase y la frase de la salida y la puesta del día.

### Un toque lleva a la Luna de «Consultes»

Juanjo, 25-10-2026: «si pulso encima de la etiqueta de la luna quiero que se
vaya a la sección de la luna en consultas». La línea de la fase de «Ara» y la
etiqueta de la gráfica llevan a `consultes.html#lluna`: abre «Sol i lluna»,
baja hasta la Luna y la destaca un momento. La etiqueta va por encima de las
zonas de cada hora de la gráfica. Para que el destacado no se perdiera,
«Sol i lluna» solo se vuelve a pintar si cambia el ancho de la ventana: en el
móvil, la barra de direcciones que se esconde al desplazar la página también
avisa de un cambio de tamaño (4 de cada 12 llegadas perdían el destacado).

### Se puede quitar de la gráfica

Juanjo, 25-10-2026: «en opciones del gráfico añade la posibilidad de quitar la
luna». Un interruptor más, «Lluna», al final de las opciones de la gráfica,
encendido de serie y recordado para todas las gráficas, como los demás; solo
aparece si la gráfica tiene alguna fase en sus horas. Su icono es una Luna en
cuarto con el trazo de los demás, no el icono de la luna, que es el del tema
oscuro.
