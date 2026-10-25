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
- **«Ara»**: de 12 horas antes a 12 después de una fase principal, una
  pastilla con su dibujo y «Lluna plena: demà, 5:12» (con el día solo si no
  es hoy), con la misma forma de nombre que «Sortida del sol: 7:14»
  (ADR 0121). Fuera de ese margen, nada (`FASE_A_PROP_H`, `faseAProp`).
- **La gráfica horaria**: la fase, pequeña, en la fila de los días y solo en
  la columna de la hora en que pasa; al tocarla, qué fase es y cuándo. Si
  coincide con el nombre de un día, el nombre se corre a la derecha. La
  leyenda la nombra cuando sale.
- **«Consultes»**: la pestaña «Sol» pasa a «Sol i lluna» (la dirección sigue
  siendo `consultes.html#sol`). Debajo del sol, «La lluna avui a Montflorit»:
  la Luna dibujada como se ve, la fase de ahora y la parte iluminada («Lluna
  plena, il·luminada al 100 %»), la salida y la puesta por orden, y las
  próximas cuatro fases con su día. La fase de ahora se nombra con la
  principal si está a 12 horas o menos (la misma regla que «Ara»); si no,
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
- `tests/test_web.py`: la fase sale de 12 horas antes a 12 después y no
  fuera; «demà, 5:12»; los nombres de las fases de paso.
- En el navegador, con el reloj a las 20:00 del 25-10-2026 y los datos de
  esa hora: la pastilla «Lluna plena: demà, 5:12» en «Ara», la Luna en la
  columna de 5 a 6 de la gráfica con su leyenda, y «Sol i lluna» con la Luna,
  en Chromium, Firefox y WebKit, móvil y escritorio, claro y oscuro; axe-core
  sin incidencias.
