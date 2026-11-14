# 27. Aviso de desbordamiento de la riera de Sant Cugat

Fecha: 2026-10-07 · Estado: aceptado; el envío a Juanjo, retirado el 08-10-2026

**08-10-2026:** el aviso ya no se manda aparte a Juanjo por Telegram (lo pidió
al ver que le llegaba repetido): lo reciben todos por las notificaciones, el
bot y el canal (`avisos_bot.py`, ADR 0034 y 0048), con la misma detección.
Este programa sigue llevando el estado y el registro.


**09-10-2026 (ADR 0058).** La lluvia de Montflorit deja de guardarse y de decirse en el aviso (`montflorit_3h` y `montflorit_3h_max` desaparecen). El Fabra sigue igual.

## Contexto

La riera de Sant Cugat nace en Collserola, en la zona de Les Planes, cruza
Sant Cugat y pasa por Montflorit. Su cuenca tiene unos 50 km²
([Wikipedia](https://es.wikipedia.org/wiki/Riera_de_San_Cugat)). Se ha
desbordado otras veces, pero en dos semanas de 2026 lo hizo dos veces con más
fuerza que nunca. Juanjo preguntó si se podía prever «mirando los registros
de Sant Cugat y los locales de Montflorit», con un margen de horas, y aprobó
la propuesta: «prepáralo así y lo vamos ajustando».

La ACA no mide el nivel de la riera: su aforo más cercano está en el Ripoll,
en Montcada, aguas abajo. Solo queda la lluvia.

## Decisión

- **El índice** (`riera.py`, calculado en cada pasada de la página de casa y
  guardado en `casa.json`, fuera de la web pública): la lluvia de 3 horas más
  alta que se alcanzará en la hora siguiente en Sant Cugat. Junta la lluvia
  semihoraria de la estación de Meteocat de Sant Cugat (XV), en la página de
  meteo.cat, y la que el radar ve y lleva hacia delante sobre el centro de la
  cuenca (nowcast.py, ADR 0019; lugar «conca»). El radar cubre también la
  media hora que la estación va por detrás.
- **Umbrales** (`config.py`): desde 20 mm en 3 horas se abre un episodio y
  se apunta; con 35 mm, aviso de **atención** por Telegram, y con 50 mm en 3
  horas y 60 en 6 (el mismo índice, con 6 horas), de **peligro**. La
  condición de 6 horas se añadió el mismo día (versión 2.19.0) al saber que
  el 13-09-2025, con 52 mm en 3 horas y nada antes, la riera no se desbordó.
  Hay un aviso por nivel y episodio. El episodio acaba tras 3 horas por debajo
  de 20 mm, y entonces se apunta en `/estat/registre/riera.csv` con sus
  máximos y una columna `desbordament` que se rellena a mano con lo que pasó.
- **El final se dice** (Juanjo, 08-10-2026: «para quitar la ansiedad», sin
  que «se convierta en una sucesión de mensajes de alerta y contraalerta»):
  cuando se cierra un episodio en el que hubo aviso, se manda un solo
  mensaje, por los mismos medios (`missatge_fi` en `riera.py` para Juanjo,
  `text_riera_fi` en `avisos_bot.py` para el canal y el bot): «ha passat el
  perill de desbordament» si llegó a peligro, «ja no hi ha risc de
  desbordament» si solo hubo atención, con la lluvia de las últimas 3 horas
  y «si torna a ploure fort, tornarà l'avís». Las 3 horas de calma del
  cierre son las que evitan el vaivén: mientras el episodio sigue abierto no
  se repite ningún nivel, y si después vuelve a llover fuerte es un episodio
  nuevo, con sus avisos. Un episodio que solo llegó al registro (20-35 mm)
  no manda nada, tampoco al acabar.
- **Lo que se dice pero no decide**: la lluvia de 3 horas del Observatori
  Fabra (D5), en la cresta de Collserola junto a Les Planes, donde nace la
  riera, y la de Montflorit (meteocerdanyola.com), minuto a minuto y sin
  retraso, en la parte baja. Ninguna tiene aún casos para fijarle un umbral.
- **El mensaje**, en catalán: lo medido en Sant Cugat y hasta qué hora, lo que
  añade el radar, el Fabra y Montflorit, y la referencia de los desbordamientos
  conocidos.
- A cualquier hora, como el aviso de lluvia (ADR 0022). Lo hace el programa en
  el NAS, sin IA y sin coste.

## Alternativas descartadas

- **Solo lo medido**: el aviso llega tarde (ver Evidencia).
- **Lluvia de la cuenca como media de Sant Cugat y el Fabra**: el 29-04-2024
  llovió sobre todo en Sant Cugat (53 mm frente a 22 en el Fabra) y la media
  no llegaba al umbral; Sant Cugat solo marca los tres casos.
- **Peligro solo con la lluvia de 3 horas** (versión 2.18.0): habría avisado
  en falso el 13-09-2025.
- **Peligro con la lluvia de 24 horas o del Fabra**: también separan los
  cuatro casos, pero el 29-09-2026 casi toda la lluvia cayó en 2 horas; la de
  6 horas es la que menos retrasa el aviso.
- **Que Montflorit decida**: es la única estación sin retraso, pero recoge la
  lluvia de la parte baja y no hay historial para saber qué umbral le toca. El
  29-09-2026 la estación de casa marcó unos 120 mm en dos horas, frente a 67
  en Sant Cugat. Se apunta para decidirlo con datos.
- **Un modelo con la humedad del suelo o la lluvia de días antes**: con tres
  casos no se puede ajustar. El registro dirá si hace falta.
- **Publicarlo en la web pública**: el umbral es una hipótesis; un aviso de
  inundación para el barrio necesita estar comprobado.

## Consecuencias

- Hay que copiar `nas/reloj.sh` al NAS y reconstruir el contenedor.
- Dos o cuatro peticiones más a meteo.cat por pasada (Sant Cugat y el Fabra,
  hoy y, de madrugada, ayer).
- `casa.json` lleva `riera`, y el nowcast, un lugar más («conca»).

## Evidencia

Lluvia de Sant Cugat (XV) y del Fabra (D5) del portal de datos abiertos de la
Generalitat (conjunto `nzvn-apee`), 2013-2026, por medias horas.

| Desbordamiento | Qué pasó | XV 3 h | XV 6 h | D5 3 h | Fin de las 3 h más lluviosas |
|---|---|---|---|---|---|
| 29-04-2024 | El agua llegó a la puerta de las casas (vídeo de Juanjo, 20:30) | 53 | 75 | 22 | 20:30 |
| 29-09-2026 | Entró en las casas; el Ayuntamiento cita el desbordamiento en Canaletes | 67 | 67 | 76 | 12:30 |
| 04-10-2026 | Entró en las casas a la 1-2; el Ayuntamiento lo cita en Montflorit | 67 | 104 | 43 | 02:00 |
| 13-09-2025 | **No se desbordó**: una foto de Juanjo del día 14 muestra que llovió, sin rastro de desbordamiento | 52 | 52 | 17 | 17:30 |

Lo que separa el 13-09-2025 de los desbordamientos es la lluvia de antes: fue
un chaparrón de 3 horas sobre suelo seco, con poca lluvia en Collserola (18 mm
en 24 horas en el Fabra, frente a 64 o más). Los tres desbordamientos tenían
67 mm o más en 6 horas. Del 11-05-2025 (48 mm en 3 horas) y del 06-11-2025
(38) no hay fotos; con la regla, ninguno de los dos daría peligro.

En los tres, el desbordamiento coincide con el final de las 3 horas más
lluviosas: la cuenca responde enseguida.

**Simulación con lo medido** (cada media hora desde 2013, con los 30 minutos
de retraso de la tabla de meteo.cat, sin radar porque no hay archivo):

- 51 episodios de 20 mm o más; 13 con atención y 5 con peligro en 13 años
  (con solo la condición de 3 horas eran 7). Los de peligro: 28-09-2014,
  15-11-2018, 29-04-2024, 29-09-2026 y 04-10-2026. De los dos primeros no se
  sabe si hubo desbordamiento.
- Margen en los tres casos: la atención habría llegado a las 20:00 (30 minutos
  antes del vídeo), a las 12:00 (con el desbordamiento ya en marcha) y a las
  0:30 (de 30 a 90 minutos antes). El peligro, siempre después.
- Con la hora siguiente conocida (el radar perfecto), la atención habría
  llegado a las 18:30, a las 10:30 y a las 23:00: de 1 a 3 horas antes. El
  radar real queda entre los dos extremos.

Fuentes del desbordamiento: notas del Ayuntamiento de Cerdanyola del
[29-09-2026](https://www.cerdanyola.cat/actualitat/els-serveis-municipals-treballen-recuperar-la-normalitat-despres-de-lepisodi-de-pluges)
y del [04-10-2026](https://www.cerdanyola.cat/node/20295).

## Riesgos y limitaciones

- **Cuatro casos** (tres desbordamientos y uno sin desbordamiento): los
  umbrales son una hipótesis. No se sabe qué pasó en la mayoría de los
  episodios de la simulación.
- El margen depende del radar: la lluvia que nace encima de la cuenca no se
  ve venir, y la relación de Marshall-Palmer suele quedarse corta con los
  chaparrones fuertes.
- Si meteo.cat no responde o la estación va más de 2 horas atrasada, no hay
  índice ni aviso.
- La estación de Sant Cugat está en el centro de la cuenca; una tormenta solo
  en la cabecera la ve el Fabra, que no decide.

## Validación

`tests/test_riera.py`: acumulados por medias horas enteras con datos del
04-10-2026, índice sin radar, el radar que adelanta el peligro, los niveles
de los cuatro casos conocidos, el chaparrón sobre suelo seco que solo da
atención, el hueco entre
estación e imagen, estación atrasada, un aviso por nivel, peligro sin
atención previa, cierre y registro del episodio, lluvia débil, y que la web
pública no lleve la riera. Prueba real el 07-10-2026 sin lluvia: índice 0.
Simulación de 2013-2026 (arriba). Pendiente de ver un aviso real.

## Cambio del 09-10-2026: las dos lluvias, del mismo momento

El nivel se decidía con el máximo de 3 horas y el máximo de 6 tomados por
separado, de momentos distintos, y podía dar peligro sin que ningún
momento cumpliera las dos condiciones (auditoría del 09-10-2026, ADR
0057). Ahora `nivell_amb_radar` calcula las dos para cada media hora de
aquí a una hora y aplica la regla a cada pareja. La regla no cambia.

## Cambio del 18-10-2026 (3.138.0): las estaciones particulares de Sant Cugat

Juanjo: «para predecir la riera, se podría buscar una estación meteorológica
cercana a la riera que esté por Sant Cugat, así se podría mirar la lluvia no
solo de la estación de Meteocat que es cada media hora». La ACA sigue sin
medir el nivel de la riera, y hay unas 190 estaciones particulares de Sant
Cugat en Weather Underground, con dato cada 5 minutos.

- **Elección**: de las diez más cercanas al centro y a la parte alta de la
  cuenca, seis midieron con coherencia los cuatro episodios conocidos
  (ISANTC157, ISANTC147, ISANTC65 e ISANTC37 en el centro; ISANTC40 e
  ISANTC89 en la parte alta). ISANTC179 daba siempre cero, ISANTC57 y
  ISANTC67 un día sí y otro no, e ISANTC134 se quedaba corta.
- **Calibración** (tabla en `docs/estadistica.md`, 12.2): la mediana suele
  dar más que Meteocat (el 29-09-2026, 93 mm en 3 horas frente a 67) y no
  separa mejor los episodios que se desbordan; con lo medido, adelanta los
  avisos de 40 a 55 minutos, y el 13-09-2025 habría dado un peligro de más.
  Juanjo aceptó el riesgo («habrá que arriesgarse») y que el registro se
  lleve a la vez que el aviso, no antes.
- **Decisión**: el índice se calcula también con la mediana de las seis (con
  al menos tres con dato de los últimos 20 minutos) y manda el nivel más
  alto de las dos fuentes; sin Meteocat, las estaciones solas. El aviso dice
  «segons 6 estacions particulars» cuando deciden ellas. Solo se consultan
  si llueve, el radar ve lluvia sobre la cuenca o hay un episodio abierto,
  con un tope diario de 500 consultas (`riera-wu.json`) y el día anterior
  guardado una vez. Cada pasada con estaciones se apunta con las dos fuentes
  en `registre/riera-veines.csv`.
- **Riesgos**: más falsas alarmas de peligro con chaparrones sobre suelo
  seco; estaciones particulares sin mantenimiento (por eso la mediana y el
  mínimo de tres); si se agota la cuota, el aviso sigue con Meteocat.
- **Validación**: `tests/test_riera.py` (manda la más alta, mínimo de tres
  estaciones, sin lluvia no se consulta, tope diario); los datos históricos
  de las seis y de Meteocat en los cuatro episodios.

## Cambio del 18-10-2026 (3.139.1): también con lluvia moderada en el barrio

Las estaciones particulares solo se consultaban si la estación del Meteocat
de Sant Cugat llevaba 1 mm o más en 3 horas, si el radar preveía 1 mm o más
sobre la cuenca en la hora siguiente o si había un episodio abierto. Quedaba
un hueco: una lluvia que el radar aún no ve sobre la cuenca mientras el
Meteocat no se ha actualizado (llega con 30-45 minutos). Ahora también se
consultan si la red del barrio mide 1 mm o más en la última media hora (la
mediana, la de «Ara»): 2 mm/h, el primer escalón de la escala de intensidad
de la web (`config.RIERA_VEINES_BARRI_MM`). Juanjo: «que llueva, pero de
forma importante? no llovizna»; con llovizna la riera no sube y no se gasta
cuota. No se usa el «Plou» de una sola estación, que salta con una gota. Con
lluvia moderada son unas 60 consultas por hora como mucho, dentro del tope
diario de 500. Prueba: `tests/test_riera.py`
(`test_pluja_moderada_al_barri_les_consulta`).

## Cambio del 18-10-2026 (3.141.0): ¿se desbordó? La pregunta a Juanjo

La auditoría de los métodos del 18-10-2026 señaló que el registro de
episodios (`riera.csv`) tiene la columna `desbordament` y nadie la
rellenaba: sin el desenlace no se puede medir si el aviso acierta, cuántas
falsas alarmas da ni cuánto se adelanta. Como con la niebla y el plugim
(ADR 0100 y 0019; `confirmacio.py`), lo que solo se ve desde el barrio se le
pregunta a Juanjo por Telegram con botones: al cerrarse un episodio con
aviso de atención o de peligro (tres horas de calma), el bot de los agentes
le manda «¿se ha desbordado en Montflorit en este episodio?», con el
principio y el final de la lluvia, la hora del aviso y el índice máximo, y
los botones «Sí, se ha desbordado», «No se ha desbordado» y «No lo sé». La
pregunta se apunta en `riera-preguntes.csv`; la respuesta, en
`riera-confirmacions.csv` y, si es sí o no, en la columna `desbordament` del
episodio (`riera.py respostes`, que `avisa` ejecuta cada minuto; la reserva
de IONOS no tiene el bot y no pregunta). Los episodios solo de registro,
sin aviso, no se preguntan. Validación: `tests/test_riera.py`
(`Desbordament`).


## Cambio del 21-10-2026 (3.173.0): sin Meteocat, las estaciones particulares siempre

El 21-10-2026 todas las estaciones del Meteocat dejaron de publicar a las
10:00 (la tabla, «(s/d)» en todas las medidas). Con tiempo seco no se cumplía
ninguna condición para consultar las estaciones particulares, la riera quedó
sin calcular y la portada mostró «No s'han pogut llegir totes les fonts».
Juanjo: «si el resto de estaciones de sant cugat sí que funcionan, por qué no
la reemplazan? pensaba que era así».

- **Decisión**: sin datos recientes del Meteocat de Sant Cugat (más de dos
  horas, `RETARD_MAX`), `cal_veines` consulta siempre las estaciones
  particulares, llueva o no: sin el Meteocat no se sabe qué ha llovido en la
  cuenca en las últimas horas. Si ellas calculan la riera, la página no
  avisa; el fallo sigue en `errors` para el registro. Si fallan las dos, la
  página dice desde cuándo falta el Meteocat y que no se puede calcular el
  riesgo (`comu.avisosFonts`, con `riera_meteocat_fins` en los datos), en
  lugar del aviso general.
- **Coste**: 6 consultas por pasada mientras dure la caída (unas 70 en tres
  horas), dentro del tope diario de 500 de la riera.
- **Validación**: `tests/test_riera.py`
  (`test_sense_meteocat_les_consulta_encara_que_no_plogui`,
  `test_darrera_meteocat_diu_des_de_quan_falta`) y `tests/test_web.py`
  (`test_cada_pagina_avisa_de_les_seves_fonts`).

## Cambio del 14-11-2026 (3.217.0): el aviso que solo sale del radar

- **Contexto**: el 14-11-2026 a las 16:51 salió el aviso de atención con
  0,0 mm en 3 horas en Sant Cugat (Meteocat hasta las 16:30) y 0,1 en las
  estaciones particulares: todo el índice (50,4) era la lluvia que el radar
  preveía sobre la cuenca en la hora siguiente. No llegó: en el barrio llovió
  a 1,9 mm/h donde el radar daba unos 30, y a las 17:03 la previsión ya había
  bajado a 31,7. El mensaje («0,0 mm… y el radar ve venir más: si sigue
  lloviendo fuerte, se puede desbordar») no decía cuánto preveía el radar, y
  se reenvió fuera de los canales de la web. La web siguió diciendo «posible
  desbordamiento» y, en el estado, «Llueve en la cuenca» con 0 mm medidos,
  y el episodio no se habría cerrado hasta 3 horas por debajo de 20.
- **Decisión**:
  - Un episodio cuya lluvia medida no ha llegado al registro
    (`riera.nomes_radar`: menos de 20 mm en 3 horas, el máximo de Meteocat y
    de las estaciones particulares, `riera.mesurat`) se cierra cuando la
    previsión lleva `RIERA_FI_RADAR_MIN` (30) minutos por debajo de atención
    y lo medido sigue por debajo del registro, sin esperar las 3 horas. El
    mensaje de final dice que la lluvia que preveía el radar no ha llegado,
    con lo medido, y la ficha de «Perill» queda cerrada con ese motivo.
  - Para no repetir aviso y contraaviso con el vaivén del radar, durante
    `RIERA_FI_H` horas después de un cierre así un aviso nuevo necesita esa
    misma lluvia medida (`estat["radar_fallat"]`).
  - El aviso dice la cifra del radar. Sin lluvia medida (menos de 1 mm):
    «De moment a Sant Cugat no ha plogut (0,0 mm…), però el radar en preveu
    uns 50 mm a la conca fins d'aquí a una hora. Si es compleix, la riera es
    pot desbordar: no t'hi acostis.» Con lluvia: «Han caigut 22 mm… i el
    radar en preveu uns 30 més…». El título de atención pasa de «possible
    desbordament» a «avís per la riera de Sant Cugat»; el de peligro no cambia.
  - En la web, el estado de registro sin lluvia medida dice «El radar veu
    pluja a la conca» y no «Plou a la conca» (`comu.titolRiera`), y la tarjeta
    de la portada da la lluvia de 3 horas, la de los umbrales, y lo que prevé el radar,
    en lugar de la de 6 horas sin el radar.
- **Pendiente**: si el radar solo debe poder dar atención. La cifra de lluvia
  medida que haría falta se comprobará antes con los cuatro desbordamientos
  registrados, para no avisar tarde de ninguno.
- **Validación**: `tests/test_riera.py`
  (`test_avis_del_radar_que_no_es_compleix_es_tanca_abans`) y
  `tests/test_bot.py` (`test_riera_avis_nomes_del_radar`, con los datos del
  14-11-2026).

## Cambio del 14-11-2026 (3.218.0): el aviso lleva a «Riera»

- **Contexto**: la ficha de «Avisos» seguía diciendo «0,0 mm» del mensaje de
  las 16:51 cuando en Sant Cugat ya habían caído 5,4, y la página «Riera»
  daba el dato nuevo. Juanjo: «quizás las alertas de la riera no deberían
  llevar a avisos sino al apartado riera. En avisos quedaría como historial».
- **Decisión**: mientras está abierto, el aviso de la riera lleva a
  `riera.html`, que tiene el aviso arriba y los datos de ahora debajo: la línea
  de «Avisos actius» (`comu.blocRiera`), las líneas del resumen
  (`comu.fitxaDeLinia`), la notificación y el «Més informació» de Telegram
  (`avisos_bot.pagina`). El mensaje de final lleva a la ficha. La ficha de
  «Perill» queda como registro: «Missatge enviat …:» antes del texto y,
  mientras dura, «Estat actual, a «Riera»». En «Riera», el enlace del aviso es
  «missatge enviat», a esa ficha. El aviso sigue saliendo con los demás en
  «Avisos actius» (ADR 0093); solo cambia adónde lleva.
- **Validación**: `tests/test_perills.py` (`test_la_portada_i_si_surts`) y
  `tests/test_bot.py` (`test_riera_avis_nomes_del_radar`).
