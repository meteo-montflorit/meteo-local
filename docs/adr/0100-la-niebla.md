# 100. La niebla

Fecha: 2026-10-17 · Estado: en curso (la hora en curso, aplicada; ICON, en vigilancia hasta el 17-11-2026)

## Contexto

El 17-10-2026 por la mañana había niebla en Montflorit y la web no decía nada
(Juanjo: «investiga por qué ahora hay niebla y la predicción del tiempo no
dice nada sobre esto»). Comprobado en los datos:

- El aeropuerto de Sabadell (METAR LELL) daba niebla desde las 6:30
  (visibilidad de 100 a 150 m, «FG VV002»); la estación de casa, 99-100 % de
  humedad y la temperatura en el punto de rocío.
- El tipo de tiempo de cada hora (`codi`, el que da «Boira») sale solo de
  AROME (`weather_code` de `meteofrance_seamless`), que en Open-Meteo no da
  visibilidad y no dio niebla. ICON sí: código 45 de 4 a 9 h y 720 m de
  visibilidad a las 9. ECMWF y GFS, no.
- En la hora en curso, el METAR de Sabadell solo se usaba para el % de cielo
  tapado (ADR 0088): «FG VV002» pasaba a «tapado al 100 %», y la web decía
  «Cobert».

Juanjo añadió: «Sabadell está a varios km y aquí tenemos la riera al lado
que muchas veces tiene niebla ella sola, no en Sabadell».

## Decisión

- **La hora en curso**: «Boira» (código 45) si el METAR de Sabadell, de los
  últimos 45 minutos, da niebla (FG, BCFG, PRFG, MIFG, FZFG; la neblina, BR,
  no) y la estación de casa está saturada (`C.HUMITAT_BOIRA`, 97 %). Es una
  observación oficial; la humedad de casa evita decirlo cuando Montflorit
  está seco.
- **La humedad, la de la estación de casa** (3.112.0): junto a la riera, no
  la media del barrio. A las 10 h del 17-10 la del barrio daba el 96 % y la
  de casa el 99 %, con niebla.
- **La confirmación de Juanjo** (3.112.0; «cuando los datos son favorables
  a niebla me mandas un mensaje y yo te respondo, así hay confirmación
  visual»): con casa al 98 % o más y sin lluvia, de 7 a 23 h y como mucho
  una vez cada 6 horas, el bot de los agentes le pregunta si ve niebla
  junto a la riera, con botones (sí, no, no lo sé); la respuesta se apunta
  en `registre/boira-confirmacions.csv`, y el mensaje cambia a «Apuntado: …».
  Las respuestas se miran cada minuto desde el reloj del NAS (3.112.2): antes
  solo en cada publicación, y el toque llegaba tarde para Telegram, que lo
  rechazaba, y el mensaje no cambiaba (Juanjo, 17-10-2026: «si se repiten
  dame confirmación de que mi respuesta se ha registrado»).
  Las respuestas se leen sin marcarlas como leídas, para no quitar nada a
  quien lea ese chat. Servirá para ajustar una regla de la riera con la
  humedad, la temperatura y el viento.
- **La niebla de la riera sola** no se dice todavía: en el barrio no hay nada
  que mida la visibilidad, y la humedad sola no basta. Del 4 al 17-10-2026,
  99 de 315 horas tenían en casa el 98 % o más y la temperatura a medio grado
  del rocío (88 sin lluvia), casi siempre de noche y al amanecer; no se sabe
  en cuántas había niebla.
- **ICON, en vigilancia antes de usarlo** (`boira.py`): una vez por hora,
  desde `publica.sh`, se apunta lo que da ICON para las próximas 12 horas
  (`registre/boira-icon.csv`). `boira.py resum` lo compara, con 1 a 6 horas
  de antelación, con la niebla de Sabadell con casa saturada y con casa
  saturada sin lluvia (lo que se tiene de la riera): aciertos, fallos y
  falsas alarmas. Se decide con un mes de datos, a partir del 17-11-2026.

## Riesgos

- La niebla que solo está en la riera no sale en la hora en curso.
- Un mes de otoño puede traer pocos episodios de niebla.

## Validación

- Pruebas: el METAR con FG y BCFG es niebla y con BR no; solo si es
  reciente; observada solo con casa saturada.

## Cambio del 18-10-2026 (3.140.3): la respuesta vale para cuando se responde

Juanjo respondió «No lo sé» a una pregunta del plugim porque la veía tarde y no
quería dar un dato falso: la respuesta se apuntaba con los datos del momento de
la pregunta. Como la pregunta dice «ahora» y se contesta mirando por la
ventana, ahora la respuesta vale para el momento en que se responde
(`confirmacio.respostes`): se apunta con su hora (`resposta_t`, la de la pasada
del reloj que la lee, cada minuto) y con lo que dicen los datos entonces (la
última pasada, de 6 minutos como mucho en modo aviso: píxeles de cada radar,
plugim y lluvia medida; en la niebla, la humedad de casa y Sabadell), y también
con lo que decían al preguntar (`pregunta_…`). Sin caducidad: cualquier
respuesta sirve (Juanjo: «30 minutos no es demasiado? la situación puede haber
cambiado totalmente»; descartados los botones que caducan, que perderían
respuestas). El mensaje dice «Apuntado a las 19:42: …». Las respuestas de antes
pasan sus datos a `pregunta_…` y quedan sin los del momento de responder.

## Cambio del 19-10-2026 (3.150.2): las respuestas, aparte de las pasadas

Juanjo respondió varias veces a la pregunta de la llovizna (plugim, de las
09:28) y el mensaje no decía «Apuntado». El reloj del NAS leía las respuestas
en la misma vuelta que las publicaciones, después de ellas: con lluvia (cada
6 minutos) y código nuevo, el bucle estuvo casi todo el rato publicando y la
lectura esperaba minutos (la de la riera, solo dentro de cada pasada). Ahora
`nas/reloj.sh` lee las de la niebla, la llovizna y la riera en un bucle aparte
cada 15 segundos (`respostes_rapides`), y `confirmacio.respostes` lleva un
candado para que dos lecturas a la vez no apunten la misma respuesta dos
veces. Sin preguntas pendientes de las últimas 24 horas no se consulta
Telegram. Leerlas tan a menudo es también lo que evita perderlas: Telegram
solo guarda cada pulsación unos dos minutos (141 s en dos pruebas del
25-10-2026, con un botón pulsado desde la cuenta de Juanjo), no las 24 horas
que se suponían; desde la 3.204.2 el bucle lee también las del cielo tapado
(ADR 0126).


## Cambio del 28-10-2026 (3.206.0): la respuesta tardía dice para qué hora vale

Juanjo contestó a las 8:16 «No hay niebla» a la pregunta de las 7:01, y lo
que había visto era la riera a las 7 («no había niebla a las 7, pero el bot lo
ha registrado con la hora actual»). Con la regla del 18-10, la respuesta valía
para las 8:16. Las dos cosas pasan: quien contesta tarde puede describir lo
que vio al recibir la pregunta o lo que ve al contestar, y solo él lo sabe.

Ahora, en las preguntas de «ahora» (niebla, llovizna y cielo tapado; la de la
riera habla de un episodio y no cambia), si la respuesta llega más de 30
minutos después de la pregunta (`confirmacio.TARDA`), el mensaje queda con
«Apuntado: …» y dos botones debajo, «Vale para las 07:01» y «Vale para las
08:16». La elección va a la columna `val_per` de las confirmaciones
(`pregunta`: su hora y los datos `pregunta_…`; `resposta`: `resposta_t` y los
datos del momento de responder), y el mensaje pasa a «Apuntado a las 07:01:
…». Mientras no elige, vale para la respuesta, como hasta ahora; también las
respuestas de antes y las que llegan a tiempo, que se apuntan con
`resposta`. `confirmacio.val_per(fila)` da el valor que cuenta (vacío es
`resposta`), y el resumen del 17-11 tiene que usarlo. El reloj sigue leyendo
la elección cada 15 segundos mientras haya respuestas sin elegir de las
últimas 24 horas. La respuesta del 28-10 (mensaje 551) se marcó a mano como
válida para las 7:01.
