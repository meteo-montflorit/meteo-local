# 101. Coherencia de lo que dice la web: un solo estado de la lluvia, reglas fijas y un revisor con IA

Fecha: 2026-10-18 · Estado: aceptado

## Contexto

En unos días Juanjo encontró varias contradicciones que nadie había visto y
que ninguna prueba detectaba:

- la ficha de Meteocat en «Perill» seguía diciendo el domingo «Observat ara…
  dissabte 17 de 19 a 22 h» (ADR 0092);
- el radar decía «Pluja a sobre» mientras ninguna estación medía lluvia («lo
  decía el radar: lluvia encima, pero no había»);
- una cuenta atrás de lluvia convivía con una hora «sense pluja».

Juanjo: «no debería comprobar la coherencia de todo lo que se anuncia en la
web? … puede haber incoherencias de otro tipo que no te he dicho o que
todavía no hemos detectado. la ia debe estar atenta a ellas, también cuando
se mandan las previsiones, alertas, etc. hazlo todo».

Un inventario del código (todo lo que la web y el bot afirman, de dónde sale
cada cosa y qué pares pueden contradecirse) dio 25 pares y dos fallos claros.
La causa común: cada bloque decide con sus propios datos y sus propios
umbrales.

## Decisión

### 1. Un solo estado de la lluvia (`casa.estat_pluja`)

`pluja_ara` se calcula una vez en el NAS: `plou` (alguna estación del barrio
que cuenta ha medido lluvia en los últimos 15 minutos), `radar_sobre` (el
radar la pone encima, llegada en 5 minutos o menos o ya pasada, y ninguna
estación la mide), `arriba` y `possible` (el radar la ve venir, 50 % y 20 %)
o `no`. Manda lo medido, luego el radar, luego el modelo. De él salen el
recuadro del radar de la portada y del bot, que con `radar_sobre` dice «Pluja
a sobre segons el radar · cap estació del barri no en mesura». Las tres
primeras horas de la tabla se ajustan a él (`ajusta_hores`): si el radar la
pone encima o la ve llegar dentro de una hora, esa hora no puede decir «sense
pluja». Esto vale también con la previsión anterior, que no llevaba el
radar.

### 2. Lo que se arregla del inventario

- **Fallos**: los riesgos propios no se cerraban nunca (`avisos_bot` miraba
  `ara`, que no existe; los que llevaban días abiertos se cierran sin avisar);
  la web y el bot decían «llindars de l'AEMET» y los umbrales son de Meteocat
  desde el 16-10-2026.
- **Radar**: si llueve encima, no sale «la més propera»; la lluvia de la
  tabla que solo viene de la que acaba de caer (persistencia) no se presenta
  como «pluja que el radar encara no veu»; «Plou» no va con «0 mm avui»; la
  nota «els models no veuen aquesta pluja» usa la lluvia del barrio
  (mediana), la misma que «Ara».
- **Fechas**: los avisos de AEMET dicen el día («Des del dilluns 19…»), no
  «demà», porque la ficha se relee otros días. Una ficha de un aviso que aún
  no ha empezado dice «Previst · Comença …», no «Actiu ara» (`comenca`).
- **Umbrales y palabras, una sola regla**: la intensidad del aviso de lluvia
  usa las franjas de AEMET del radar (2, 15, 30 y 60 mm/h; antes, «forta»
  desde 4); las etiquetas del tramo «ratxes» y «calor», los umbrales del
  riesgo propio (más de 72 km/h y de 36,8 °C; una prueba lo comprueba); la
  nieve, con un decimal y redondeada (no «0 cm»); el riesgo «Pluja intensa
  prevista» y las etiquetas «pluja forta / torrencial» solo cuentan las horas
  en que puede llover (20 % o más) y, si ninguna llega al 50 %, dicen la
  probabilidad.
- **Si surts**: el temps violent de Meteocat cuenta como las tormentas; «ni el
  radar… hi veuen pluja» solo si el radar de verdad no ve nada; por debajo del
  20 %, donde la tabla dice «sense pluja», «poca probabilitat de pluja» en vez
  de «pot ploure» (el umbral aprendido no cambia, ADR 0069); «Sense pluja ni
  vent fort a l'anada ni a la tornada» en los vehículos, que solo miran esas
  horas; y, como con los planes de Protecció Civil, se dice que el consejo no
  tiene en cuenta el peligro de la riera ni un incendio cercano.
- **Resumen del día**: la lluvia de 0 a 6 h de la tarjeta de hoy es «De
  matinada» («Aquesta nit» del resumen de mañana va de 18 a 6 h); la
  temperatura «d'aquí a mitjanit» incluye la medida ahora.
- **El bot**: «no plou» ya no va con un icono de lluvia.

Se dejan, con su motivo: la hora en que pararía la lluvia (radar, en
entrenamiento, ADR 0049) frente a la persistencia de la tabla, que es
estadística y está validada; los ecos débiles que ponen el modo vigilancia
(pendiente de decidir con un mes de datos, a partir del 07-11-2026); los
umbrales aprendidos de «Si surts» (ADR 0069), y el plan de Protecció Civil
oculto por no tener motivo meteorológico (ADR 0062).

### 3. Reglas fijas y revisor con IA (`revisor.py`)

En el NAS, tras cada publicación y aparte del reloj:

- **Reglas fijas** (`regles`), sin IA, en cada pasada: ninguna ficha abierta
  habla de horas pasadas, «Observat ara» solo con la observación vigente, la
  hora en curso dice «Plou ara» si llueve, y las páginas no dicen «No plou» y
  «Pluja a sobre» sin aclarar que es el radar.
- **El revisor** (Claude, `C.REVISOR_MODEL` = `claude-sonnet-5-5`, con el
  Claude Code y el token del contenedor; una sola respuesta, sin
  herramientas) se despierta solo cuando: ha salido un aviso a los vecinos;
  es la hora de los resúmenes (05:50, antes de los de 6, 7 y 8, y 20:50, antes
  del de mañana); falla una regla nueva, o cambia lo que concluye la web
  (llueve o no, el modo, los avisos y sus niveles, las fichas abiertas), como
  mucho cada 30 minutos (`C.REVISOR_MIN_MIN`). Lee las páginas ya dibujadas
  (con Chromium sin pantalla y los datos que se acaban de publicar; cuáles,
  en «Todas las páginas», más abajo), el resumen del bot, los últimos avisos y los datos
  medidos y oficiales, y dice qué es falso, caducado o contradictorio. Se le
  pasa lo que ya ha contado los dos últimos días, para que no lo repita.
- **Qué hace con lo que encuentra** (Juanjo, 18-10-2026: «me parece bien»):
  - corrige solo lo que únicamente quita líneas de una ficha o de un aviso
    enviado (`treu_linies`); lo comprueba el código, no la IA. La corrección
    vive en `correccions.json`, `avisos_bot` la aplica en cada pasada mientras
    el texto siga siendo el corregido, y el bot edita los mensajes de Telegram
    de las últimas 48 horas (`bot.corregeix`). Los avisos al navegador ya
    llegados no se pueden corregir. El reloj publica en el minuto siguiente;
  - lo demás (cambiar un texto, cerrar una ficha) se lo pregunta a Juanjo con
    botones (Aplicar / Dejar); nunca inventa un aviso ni envía nada a los
    vecinos;
  - avisa siempre a Juanjo por el bot de los agentes: un mensaje por cada
    corrección, con «Deshacer»; uno por revisión con lo grave y lo medio que
    hay que arreglar en el código; lo leve, al registro
    (`registre/revisor.jsonl`, `revisor.py estat`).

## Alternativas descartadas

- **Que la IA escriba los avisos**: los avisos de peligro tienen que salir en
  el momento y siempre igual; los errores encontrados no eran de entender el
  texto oficial, que llega con datos estructurados, sino del manejo propio.
- **Que la IA corrija sin límites**: una corrección equivocada que quite un
  aviso vigente hace más daño que una línea caducada.
- **Una revisión en cada pasada**: con la lluvia, decenas al día; con los
  desencadenantes, unas pocas, y en épocas secas, casi solo las de los
  resúmenes.

## Consecuencias

- Coste: una revisión tarda de 50 a 75 segundos y gasta lo equivalente a unos
  0,35-0,40 USD de la API (va con la suscripción del token). Con dos al día y
  las de los avisos y cambios, de 2 a 10 al día según el tiempo.
- `nas/reloj.sh` cambia: hay que copiarlo al NAS y reconstruir el contenedor.
  `publica.sh` deja `avisos.json` junto al estado para el revisor.
- El bot guarda el número de cada mensaje de aviso que envía (sin más datos,
  y lo borra a los 3 días con el aviso) para poder corregirlo.

## Evidencia

- 18-10-2026 a las 6:40: Meteocat aún daba las franjas del sábado en el aviso
  vigente; la ficha decía «Observat ara».
- Inventario del código del 18-10-2026: 25 pares que pueden contradecirse y
  los dos fallos, comprobados en el código (`avisos_bot.py`, `casa.py` no
  escribe `ara`; `config.py`, umbrales de Meteocat).
- Revisión de prueba con los datos de las 7:14 (antes de los arreglos):
  encontró, entre otras cosas, las fichas cerradas de AEMET con «demà»; la de
  las 7:40, «Actiu ara» en avisos que empiezan el lunes. Las dos, corregidas.
  También dio dos falsas alarmas (la barra vertical de la tabla y la franja
  del resumen), explicadas ahora en sus instrucciones.

## Riesgos y limitaciones

- La IA puede equivocarse: por eso solo quita líneas sola, y todo se le dice
  a Juanjo con el texto de antes y de después.
- Lo que se corrige en la web es una corrección de los datos, no del
  programa: el fallo vuelve hasta que se arregle el código.
- Si Chromium no está, el revisor trabaja sin las páginas dibujadas.

## Validación

`tests/test_revisor.py` (reglas, correcciones solo de líneas, que la
corrección caduca si el texto cambia, que va al bot, cuándo se despierta, un
mensaje por revisión), `tests/test_bot.py` (edición de los mensajes enviados,
una vez y no pasadas las 48 horas; cierre de los riesgos propios),
`tests/test_web.py` (el radar con el estado único, las etiquetas con los
umbrales de config, «Si surts»), `tests/test_riscos.py`, `tests/test_smp.py`
y `tests/test_pluja_arriba.py`. Dos revisiones reales con Sonnet 5.5 y los
datos del momento. La web, vista en Chromium y Firefox, en escritorio y
móvil.

## Cambio del 18-10-2026 (3.136.1): lo que vio la primera revisión en el NAS

La primera revisión real (07:46, 34 s, 0,17 USD) encontró tres cosas, y se
arreglan en el código:

- La ficha de AEMET de tormentas, abierta con la versión anterior, no llevaba
  cuándo empieza y decía «Actiu ara»: las fichas abiertas de AEMET lo toman
  de su clave (`aemet:tipus:inici`).
- «Avisos actius (3)» en «Si surts» tenía 4 líneas al desplegarlo: Meteocat
  da un aviso por meteoro. Las líneas de Meteocat se agrupan por fenómeno
  (`smp.textos` da el fenómeno), como en el bloque plegado.
- Una ficha creada el día 16 decía «demà» de su día: la nota del revisor
  cubre ahora las fichas creadas antes del 18-10-2026, no solo las cerradas.

## Cambio del 18-10-2026 (3.136.2): el texto de antes y el de después

El mensaje de una corrección automática lleva el texto de antes y el de
después, sin el HTML de Telegram, y el de una propuesta, el texto actual y el
propuesto (Juanjo: «sí, añádelo»). Hasta ahora solo decía dónde estaba el
error y por qué.

## Cambio del 18-10-2026 (3.138.1): el asterisco de la persistencia

El revisor encontró «*» («Hi compta la pluja que cau ara al barri») y «Pluja
feble» en la tabla con «No plou» arriba. La persistencia sube las primeras
horas por la lluvia de la última hora (`consens_pluja(...)["pluja_1h"]`),
aunque ya haya parado: el cálculo es el validado, el rótulo era inexacto.
Ahora dice «Hi compta la pluja de l'última hora al barri, encara que ja hagi
parat», y «Com funciona», «Si ha plogut a l'última hora…» en vez de «Si ja
plou». La parte alta redondeada («1 °C més» con 0,5) era la regla de Juanjo
del 13-10-2026 y se le explica al revisor.

## Cambio del 18-10-2026 (3.138.2): la ficha alargada por AEMET

El revisor encontró en el historial de «Perill» la ficha de tormentas del
17-10 con «fins a mitjanit» en el texto y final a las 03:59 del 18. La hora
era la buena: AEMET juntó en ese aviso el del día siguiente de 0 a 4 h y lo
alargó (`tanca_aemet`); el texto es el que publicó al principio. No era un
desfase de zona horaria, como suponía el revisor. Juanjo aprobó que la ficha
lo diga en vez de enseñar al revisor a callarlo: al alargarse, la ficha guarda
el final con que se publicó (`allargat_de`) y, debajo de la línea de cuándo
dura, dice «L'AEMET l'ha allargat fins a dg. 18/10, 03:59», también en el
texto que se comparte. La ficha del 17-10 se completó a mano en el estado del
NAS. Los mensajes de Telegram y del navegador no cambian: se enviaron con el
final que tenían.

## Falsa alarma del 18-10-2026: asterisco con hueco

El revisor avisó cuatro veces (filas 9–10, 11–12, 12–13 y, a las 12:58,
14–15 y 15–16) de que el «*» salía en horas futuras y no en una intermedia,
y lo tomaba por un fallo que debía limitarse a la hora en curso. No lo es: la
persistencia cubre las cuatro primeras filas (ADR 0007) y cada fila lleva la
cifra mayor, la del modelo o la de la persistencia. A las 12:58, con 0,5 mm en
la última hora, la persistencia daba 47,5 %, 40 % y 34 % para las tres horas
siguientes, y el modelo, 54 %, 39 % y 14 %: la fila 13–14 era del modelo y
las otras dos, de la persistencia. Se explica en `revisor-instruccions.md`;
el cálculo no cambia.

## Cambio del 18-10-2026 (3.138.5): la leyenda del asterisco explica el hueco

Para que quien lee la tabla entienda lo mismo que ahora sabe el revisor, la
leyenda del «*» dice «Xifra que ve de la pluja de l'última hora al barri,
encara que ja hagi parat: els models en donaven menys» (antes, «Hi compta la
pluja de l'última hora al barri, encara que ja hagi parat»), en catalán y
castellano (Juanjo: «sí, aplica la leyenda»). Y la R4 «per carretera» por un
autobús entre Terrassa Nord y Manresa se corrige en el código (ADR 0029).

## Cambio del 18-10-2026 (3.138.6): tres hallazgos leves del revisor

- **«Si surts» daba por acabado un riesgo que volvía**: «Cap a les 15 h
  s'acaba el risc de pluja» con lluvia posible de 16 a 0 h. Si el riesgo
  vuelve dentro de la salida, dice «De 15 a 16 h, sense risc de pluja» (o
  «sense avís oficial per pluja»); «s'acaba» solo si no vuelve.
- **La lluvia de 15 minutos era solo la de casa** y la de la última hora, la
  mediana del barrio: 0,3 mm en 15 minutos y 0 en la hora. Ahora también va
  por consenso (ADR 0085); con las mismas estaciones, las medianas no se
  cruzan. El revisor sabe que «Plou» basta con una estación.
- **El radar marcaba «†» con un 5 %**: la regla de los milímetros no pedía
  probabilidad, y el recuadro, que dice «Pot arribar pluja» desde el 20 %,
  decía que no venía lluvia. Ahora el radar solo sube una hora si su
  probabilidad llega a `PROB_ATENCION` (ADR 0019). En el registro de octubre,
  de 36 horas marcadas por el radar, esta era la única por debajo.

## Cambio del 19-10-2026 (3.148.0): «Si surts» dice que llueve si llueve

A las 06:40, lloviendo (`pluja_ara.estat` «plou», según las estaciones),
«Si surts» decía en bici, moto y coche «Pluja probable a l'anada (6 h)», y a
pie «Pot ploure mentre ets fora». Juanjo: «si llueve, debe decir que llueve
sea por radar, estaciones o ambas». Ahora, si la hora de salida lleva
`plou_ara` (la misma verdad de la lluvia de la portada y la tabla), el motivo
dice «Ara plou al barri, segons les estacions / el radar / les estacions i
el radar» (de `segons_estacio` y `segons_radar` de la hora), y la vuelta
aparte si también ve lluvia («…, i pluja probable a la tornada (9 h)»); a
pie, «Ara plou al barri, segons …: porta paraigua». El nivell no cambia.
Prueba: `tests/test_web.py` (`test_si_ara_plou_ho_diu_i_qui_ho_veu`).

Corrección en la 3.149.0 (el mismo día): a las 07:0x, con los datos de las
06:57, «Si surts» volvía a decir «Pluja probable a l'anada (7 h)» lloviendo:
pasada la hora en punto, la hora en curso de esos datos (de 6 a 7, la que
llevaba `plou_ara`) ya no cuenta y «Ara» es la de 7 a 8. Ahora sale del
estado único de la lluvia de ahora (`pluja_ara`: «plou», con «les estacions»
o, si el radar también la pone encima, «les estacions i el radar»;
«radar_sobre», «el radar»), y solo con «Surto: Ara» (Juanjo: «esto solo hay
que tenerlo en cuenta cuando surto está en ara»); con una hora posterior, la
previsión como siempre.


## Cambio del 19-10-2026 (3.151.0): hallazgos leves del revisor

Comprobados en el código los leves de la noche del 18 al 19:

- **Redondeo distinto en el bot y en la web.** El resumen decía «entre 13 °C
  i 18 °C» y la tabla, 19 °C a las 17 h: el valor era 18,5, que `round()` de
  Python lleva a 18 (al par) y `Math.round` a 19. `bot.graus` y los
  porcentajes del resumen redondean ahora como la web (`floor(x + 0,5)`).
- **La comparación con el día de antes restaba sin redondear.** «Demà tarda
  14–19 °C · 2° més que avui» con «Tarda 15–18 °C»: restaba 19,4 − 17,6 = 1,8
  y redondeaba el resultado. Ahora `comparaTemp` y `bot.compara_temp` restan
  las cifras ya redondeadas, las que se leen en las cabeceras (19 − 18 = 1,
  «semblant»). Con el día de ayer medido, que no se muestra, la diferencia
  puede variar en un grado respecto a la de antes; se prefiere que cuadre con
  lo que se lee.
- **Falsa alarma del revisor: la fila 6–7 sin aviso.** Una barra de aviso de
  una sola fila no tiene sitio para el texto y queda vacía (`ajustaFranges`);
  el texto completo está en el `aria-label` del botón, que el revisor no leía.
  `revisor.Text` lo lee ahora. Las franjas de Meteocat estaban bien.
- **«R4 · Amb incidències» con una incidencia ya resuelta.** Ver ADR 0079: un
  aviso que solo dice que la incidencia se ha resuelto y los trenes recuperan
  los horarios pone la línea «amb retard».
- **Viento «2 (30)»**: no es un fallo de cálculo; el viento de AROME es el
  instantáneo al final de la hora y la racha, el máximo de la hora. Queda por
  decidir con Juanjo.

Pruebas: `tests/test_bot.py` (18,5 → 19; 17,6 frente a 19,4 → 1) y
`tests/test_trens.py` (`test_incidencia_resolta_que_es_recupera_va_amb_retard`).

## Cambio del 19-10-2026 (3.155.0): el viento de cada hora, la media de la hora

El revisor vio en la tabla por horas «3 (37)» en la fila de 17 a 18 (y antes
otro parecido de madrugada): el viento era el de un instante, el de AROME a la
hora en punto (`wind_speed_10m`), y la racha, la máxima de toda la hora; en
una hora de tormenta, con el viento a ráfagas, el instante podía caer en una
calma. La leyenda decía «la mitjana». Juanjo, tras preguntar si había riesgo
de pasarse del límite de Open-Meteo (no: unas 2.900 peticiones al día en el
peor caso, de 10.000; esta añade unas 240): «sí, hazlo y publica». Ahora
`casa.vent_hora` da la media de la hora con el viento cada 15 minutos de
AROME (`minutely_15`, una petición más por pasada), por trapecios; sin esos
datos, la media del principio y el final de la hora, como la temperatura. La
racha no cambia. Con los datos del 19-10-2026, la fila de 17 a 18 pasó de «3
(37)» a «9 (37)». La leyenda dice ahora «La mitjana de l'hora en km/h i,
entre parèntesis, la ratxa més forta de l'hora». Prueba:
`tests/test_casa_fonts.py` (`VentHora`).


## Cambio del 19-10-2026 (3.158.0): los hallazgos del revisor de 11:34 a 14:18

Juanjo: «sí, arregla los del revisor». Cada uno comprobado en el código:

- **Redondeo** (14:18): la racha de 92,5 km/h salía «92» en el aviso
  (Python redondea las mitades a par), «93» en la tabla y «92,5» en la
  portada. `riscos.num` redondea las mitades hacia arriba, como la web, y la
  línea corta de la portada usa `numRisc`, la misma regla que el texto.
- **«Tempesta: aEMET…»** (11:34): `origenTram` pasaba a minúscula la primera
  letra aunque fuera una sigla, y repetía el aviso que el perill del tramo ya
  decía. Ahora no repite la fuente que ya nombra el perill con tormentas y no
  toca las siglas.
- **Hora de «actualitzat» de un plan** (13:10): era la del PDF de Protecció
  Civil (12:08) con el mensaje enviado a las 12:15. El comunicado nuevo pone
  ahora `darrer` con la hora del mensaje, la misma que en el móvil (ADR 0094);
  el texto de la ficha sigue sin cambiar.
- **«A peu»** (11:34): decía «Pot ploure mentre ets fora» con un 60 % y los
  vehículos «Pluja probable a la tornada». A pie hay ahora «Pluja probable
  mentre ets fora: porta paraigua» con el mismo umbral (`plouRodes`).
- **«uns 31 mm» en la cabecera de un tramo** (14:18): es la cantidad esperada
  (ADR 0103), no la suma de la columna, y la página no lo decía. La leyenda
  «Com es llegeix la previsió» lo explica («Pluja del tram») cuando algún
  tramo la muestra.
- **El aviso de la web, activo en «Perill» y ausente de la portada** (13:44):
  cuando la previsión deja de ver el riesgo, la ficha espera 3 horas a
  cerrarse (`RISC_FI_H`, para que el vaivén de los modelos no repita
  mensajes). Durante esa espera ahora lleva `en_pausa`: dice «Ja no es
  preveu» y desde cuándo, y no cuenta como activa ni como «Nou»
  (`perillsNous`), igual que la portada, que ya no la lista. Si el riesgo
  vuelve, deja de estar en pausa.
- La de las 13:44 sobre «77 km/h» frente a «20 (66)» ya la resolvió la
  3.157.0 (la racha, la del modelo que da más; ADR 0018).

Validación: `tests/test_riscos.py`, `tests/test_web.py`,
`tests/test_historial.py`; «Perill» con la ficha en pausa y la leyenda, en
Chromium y Firefox, móvil, claro y oscuro; axe-core sin fallos en las dos
páginas.


## Cambio del 19-10-2026 (3.159.2): los hallazgos del revisor de 15:28 y 16:22

- **Ficha de AEMET alargada** (15:28): decía «Dimarts 20, de les 6 h a les
  7 h» y debajo «L'AEMET l'ha allargat fins a dt. 20/10, 08:59», con la
  portada de 6 a 9. Ahora, cuando AEMET alarga un aviso, `avisos_bot.refa_franja`
  rehace la línea de cuándo dura con el final nuevo («de les 6 h a les
  9 h»), en catalán y castellano, y guarda en `franja_fins` el final que dice;
  la web, con la línea ya al día, solo añade «L'AEMET l'ha allargat.». Si la
  línea no está (la quitó el revisor, o es un texto anterior con «demà»), se
  queda como antes, con la hora debajo. Las fichas ya alargadas se corrigen
  en la pasada siguiente.
- **Bloque del radar** (16:22): decía «La previsió per hores sí que dona
  pluja a partir de les 17 h (56 %)» con la hora en curso, de 16 a 17, al
  78 %. Ahora se mira primero la hora en curso («per a aquesta hora») y solo
  si no da lluvia, la primera hora siguiente.

Validación: `tests/test_smp.py` (`test_la_fitxa_de_l_aemet_allargada_diu_el_final_nou`);
el bloque del radar, con las horas de las 16:22, en Node; «Perill» y la
portada con los datos del NAS, en Chromium y Firefox, móvil y escritorio.


## Cambio del 20-10-2026 (3.162.0): los hallazgos del revisor del 19-10 (18:22) al 20-10 (03:10)

- **Fin del aviso propio** (18:22): decía «ja no hi ha cap situació de
  perill al barri» con INUNCAT, Meteocat y AEMET abiertos, y «Fa 3 hores»
  sin decir desde cuándo (las tres horas eran correctas: se cuentan desde
  que la previsión dejó de ver la racha, a las 15:21, no desde el final de la
  franja de la ficha). Ahora nombra lo que acaba («s'acaba l'avís per vent
  fort al barri»), dice desde qué hora no se mide ni se prevé y, si hay
  avisos oficiales abiertos, «Continuen els avisos oficials de…»
  (`avisos_bot.text_perill_fi`, `oficials_actius`).
- **Cifra de la ficha propia** (03:10): el aviso de las 13:09 decía 77 km/h y
  la ficha, que lo enlaza, 89, porque se pone al día en cada pasada. Sigue
  poniéndose al día (sin mensaje nuevo: solo una subida de nivel lo merece,
  ADR 0092), pero añade «Ha pujat des de l'avís de les 13:09, que deia
  77 km/h» si la cifra redondeada ya no es la enviada (`linia_canvi`).
- **AEMET sustituido por uno que empieza más tarde** (19:28): el de
  tormentas de 16 h a 8:59 cambiado por uno de 19 h a 8:59 se cerraba como
  «L'AEMET l'ha retirat abans d'hora». `aemet_que_inclou` busca ahora el que
  cubre lo que queda del viejo (desde ahora, si ya había empezado), con
  fechas y no con texto.
- **Dos avisos de AEMET con la misma clave** (19:58): lluvia de 40 mm en 1 h
  (cubierta por Meteocat) y de 80 mm en 12 h empezaban a la vez; ganaba el
  último de la lista, cuyo orden cambia, y la ficha del de 80 mm se cerró
  como «Substituït per l'avís de Meteocat». `aemet_per_clau` deja uno por
  clave: el que Meteocat no cubre, luego el de más nivel y luego el que acaba
  más tarde. `smp.marca_coberts` era correcto.
- **Mañana «sense pluja» con avisos** (19:58): el resumen del día decía «Sense
  pluja prevista» con avisos oficiales de lluvia de 0 a 9 h, y en la portada
  esas líneas se quitan porque van en «Avisos actius». Ahora, si la previsión
  no da lluvia pero hay aviso oficial, «La previsió no dona pluja, però hi ha
  avís oficial per pluja de 0 a 9 h» (`bot.text_pluja`).
- **«Si surts» negaba el radar** (01:28): con aviso a la ida y a la vuelta y
  nada más, bici, moto y coche decían «ni el radar, ni les estacions, ni els
  models hi veuen pluja», mientras el radar veía llegar lluvia hacia las
  02:10, entre medias. Ahora la frase vale para toda la salida: si el radar
  ve lluvia que llega antes de la vuelta, o una hora intermedia tiene datos
  de lluvia, lo dice (`sortir.plujaEntremig`).
- **Comparación con ayer del resumen** (19:04): «Temperatura d'aquí a
  mitjanit» decía «2 graus més que ahir» con Tarda y Nit «semblant», porque
  comparaba la máxima de 19 a 24 h y los 17 °C caían pasadas las 21 h, en el
  tramo de noche, que compara la mínima. `bot.compara_resum` usa el criterio
  de las cabeceras: si quedan horas de día (7 a 21 h), la máxima de esas
  horas; si no, la mínima de la noche hasta las 7.
- **Rocío por encima de la temperatura** (23:10): 16 °C con 15,2 °C. El rocío
  es la mediana de casa y de las vecinas, que lo dan en grados enteros, y
  casa está en la zona fría; `casa.consens` lo limita a la temperatura (en
  octubre pasaba en 17 de 334 horas). No entra en ningún cálculo.
- **Queda por decidir** (01:28): «Demà matí 9–18 °C · semblant a avui» con una
  mañana unos 2 °C más fría de media sigue la regla del ADR 0061 (solo la
  máxima de día, 18 frente a 19). Cambiarla es una decisión de criterio.

Validación: `tests/test_bot.py` (`FitxesDelRevisor`,
`test_sense_pluja_pero_amb_avis_oficial`, la comparación del resumen),
`tests/test_web.py` (lluvia entre medias en «Si surts»),
`tests/test_estacio_casa.py` (`test_rosada_no_supera_la_temperatura`); las
609 pruebas pasan.


## Cambio del 20-10-2026 (3.162.1): los hallazgos del revisor de las 05:40

- **Meteocat retirado, ficha «Actiu ara»**: Meteocat retiró el aviso de 5 a
  6 h y la ficha seguía activa la media hora de relevo (`SMP_FI_MIN`, para no
  avisar dos veces entre emisiones), cuando la portada ya no lo listaba.
  Ahora, si Meteocat no muestra ningún fenómeno del episodio, el estado guarda
  desde cuándo (`oficials.smp.pausa`) y la ficha queda en pausa: «Ja no
  consta» y «Meteocat ja no el mostra des de les 05:45. Si no torna en mitja
  hora, es dona per acabat.», como la ficha propia («Ja no es preveu»).
- **AEMET «Previst · Comença a les 6 h» con Meteocat retirado**: la ficha
  empezaba a las 6 porque hasta entonces lo cubría Meteocat. `aemet_vigents`
  guarda ahora cuándo empieza la parte que no cubre Meteocat, y la ficha
  abierta adelanta su comienzo si esa hora se adelanta.
- **AEMET de 80 mm sin ficha**: era la del cambio 3.162.0 (dos avisos con la
  misma clave); la ficha, cerrada por error, se reabrió a mano en el NAS y en
  el `avisos.json` publicado, y la de tormentas del 19-10 se rotuló «inclòs
  en un altre avís».

Validación: `tests/test_historial.py` (`test_la_fitxa_de_meteocat_retirat_espera_en_pausa`,
`test_l_aemet_avanca_l_inici_si_meteocat_ja_no_el_cobreix`), `tests/test_bot.py`
(`test_meteocat_retirat_queda_en_pausa`); 612 pruebas; «Perill» en Chromium y
Firefox, móvil y escritorio.


## Cambio del 20-10-2026 (3.163.0): «Perill» agrupa los avisos de AEMET que coinciden

La portada decía «Avisos actius (2)» y «Perill» enseñaba cinco fichas: tres
eran avisos amarillos de AEMET (tormentas de 19 a 9 h y lluvia de 20 mm en
una hora y de 80 mm en 12 horas, de 6 a 9 h) que la portada resume en una
línea, «AEMET: avís groc per pluja i tempestes, avui fins a les 09:00», y la
quinta, la de Meteocat retirada y en la media hora de relevo. Juanjo aprobó
agrupar también en «Perill» (20-10-2026: «sí, hazlo así»): los avisos activos
de AEMET van agrupados como las líneas de la portada, con la misma función
(`comu.frasesAvisos`, que ahora devuelve también sus franjas): mismo nivel y,
para juntar fenómenos distintos, las mismas horas desde ahora. Así no se
separan nunca: una primera versión juntaba los que solo se tocaban
(tormentas de 19 a 9 h con lluvia de 6 a 9 h a las 5:50, que la portada da en
dos líneas). Cada grupo es una sola tarjeta (`perill.grupsAemet`), con el
título de la línea, «Actiu ara» o «Previst» y el
número de avisos; dentro, cada aviso con su estado, sus horas, su texto y su
botón de compartir, con el mismo identificador de antes, de modo que los
enlaces de los mensajes enviados siguen llevando a su aviso. «És un avís
oficial…» y «Més informació», una sola vez al pie. Es solo cómo se pinta la
página: los mensajes y el historial no cambian, y las acabadas siguen una a
una.

Validación: `tests/test_web.py`
(`test_perill_agrupa_els_de_l_aemet_que_coincideixen`); «Perill» con los
datos de las 06:00 en Chromium y Firefox, móvil y escritorio, claro y oscuro,
en catalán y castellano; axe-core sin fallos.

## Cambio del 20-10-2026 (3.170.4): «avui» y «demà» en las fichas de otro día

El revisor (20-10-2026, 17:31) vio en el historial de «Avisos» la ficha
acabada del viento del lunes, que el martes seguía diciendo «ratxes de fins a
89 km/h, avui de 17 a 18 h». El texto de la ficha es el del aviso enviado, que
dice «avui» o «demà» respecto al momento en que se escribió. Juanjo aprobó el
mismo día que pasen a ser el día: «dilluns 19 de 17 a 18 h».

- Cada ficha guarda cuándo se escribió su texto (`escrit`, en
  `avisos_bot.historial`: al abrirse, con un aviso nuevo y cuando se rehace
  el texto de Meteocat o del aviso propio). Las de antes de la 3.170.4 usan el
  último aviso o el comienzo.
- La página, al pintar la ficha (`textFitxa` en `perill.js`), cambia «avui»,
  «demà», «hoy» y «mañana» seguidos de «de 17…» o «a les 12 h» por el día de
  la semana y del mes, como `nom_dia` (con «Des del…», «Desde el…»), solo si
  se lee otro día. El mismo día, el texto queda como se envió. Los mensajes de
  Telegram y del móvil no cambian.
- Se quita de `revisor-instruccions.md` la excepción de las fichas anteriores
  al 18-10-2026: ya salen con el día.

Validación: `tests/test_web.py` (`test_perill_avui_i_dema_d_un_altre_dia`:
catalán, castellano y gallego, el mismo día y otro, con y sin `escrit`) y
`tests/test_historial.py` (`escrit` al rehacer el texto propio).

**Fichas antiguas de AEMET y fichas acabadas por su hora** (21-10-2026,
3.171.1). El revisor vio el 20-10 a las 21:01 dos fichas de AEMET del 17 que
seguían diciendo «Demà, de les 0 h a les 4 h.»: la regla de la 3.170.4 no
reconocía la forma de las franjas de AEMET de antes del 18-10 (con coma y
«de les»). Ahora sí («Diumenge 18, de les 0 h a les 4 h.»). Y el 21-10 a las
5:53 creyó abiertas cuatro fichas de AEMET con la hora final pasada: un aviso
de AEMET acaba a su hora sin mensaje de final, y «Perill» ya lo da por
acabado. El revisor recibe ahora las fichas abiertas con la misma regla que
«Perill», y sus instrucciones lo explican. Validación: `tests/test_web.py` y
`tests/test_revisor.py`.

**Todas las páginas** (26-10-2026, 3.205.0). Juanjo, al ver que el revisor
solo leía la portada, «Si surts» y «Perill»: «no debería repasarlas todas?».
No todas en cada revisión: las que no cambian con el tiempo no pueden
contradecir los datos de ahora, y leerlas siempre sería gastar para nada.

- **En cada revisión** (`PAGINES`), las que hablan del tiempo de ahora: la
  portada (que sale de `web/casa.html`, «Temps a casa»), «Si surts», «Perill»,
  «Riera» y «Consultes».
- **Con el resumen de las 20:50** (`PAGINES_DIA`), también «Fiabilitat», que
  mira hacia atrás. Necesita el historial: el revisor lo genera en su copia
  con `historial.fes(…, 1, refa=False)`, el índice y el día de hoy, sin rehacer
  los días de un formato anterior ni tocar su marca, que son trabajo de
  `publica.sh`. Si falla, la página se deja fuera y queda en el registro del
  reloj.
- **En esa misma revisión, si ha salido una versión nueva** (`C.VERSION`
  distinta de la de la última vez, en `revisor.json`), las fijas
  (`PAGINES_FIXES`: «Com funciona», «Fonts», «Avisos», «Telegram» y
  «Privacitat») junto con `config.py`. Pueden dejar de ser verdad cuando
  cambia lo que hace el programa (un horario, un umbral, una fuente), y
  `config.py` reúne esos valores con su explicación. Una vez al día como
  mucho, aunque salgan varias versiones: en la semana del 19 al 26-10 salieron
  43, y los textos de esas páginas cambiaron casi a diario.
- Cada página entra hasta 16.000 caracteres (antes 12.000: «Com funciona»
  tiene unos 13.600). Las instrucciones explican qué buscar en cada grupo.
- Límite: las páginas fijas no se comparan con los datos, solo con
  `config.py` y las otras páginas; lo que dicen del bot o del servidor de
  avisos (IONOS) no se puede comprobar desde aquí.

Coste, medido con `revisor.py prova` en el NAS el 26-10-2026 a las 19:24 (todas
las páginas y `config.py`): 0,34 $ y 70 s, frente a unos 0,15 $ y 20 s de las
revisiones de antes. Esa prueba encontró tres incoherencias leves, todas en
páginas nuevas: dos cifras distintas del mismo histórico de la riera (página
y comentario de `config.py`), un texto de «Fiabilitat» que dice que Meteocat y
AEMET aún no tienen error de lluvia junto a una tabla que sí lo da, y una
franja de «Riera» que empezaba antes de la hora actual.

Validación: `tests/test_revisor.py` (`test_pagines_de_cada_revisio`: qué
páginas pide cada revisión y que las fijas no se repiten con la misma
versión) y `tests/test_historial_grafica.py`
(`test_el_revisor_no_avanca_la_feina_de_publica`); las páginas nuevas,
dibujadas en el NAS con los datos reales (Riera 3.444 caracteres, Consultes
1.282, Fiabilitat con su historial).
