# 10. Modo aviso: actualización al ritmo del radar

Fecha: 2026-10-05 · Estado: aceptado · Actualizado el 06-10-2026 (ADR 0020):
cada 6 minutos, al ritmo del radar de Meteocat

## Contexto

La página de casa se actualizaba cada hora y la del trayecto cada media hora.
El 05-10-2026 la lluvia en Montflorit pasó de casi nada a 26 mm/h en veinte
minutos (de 9:00 a 9:20). Juanjo preguntó si en situaciones de riesgo no
convendría actualizar más a menudo.

## Decisión

- **Modo aviso** cuando se da cualquiera de estas cosas
  (`motivos_modo_aviso` en `prevision.py`): aviso de Meteocat vigente para
  el Vallès Occidental a esa hora (desde la 3.96.2; cuenta aunque AEMET no
  tenga ninguno: «si solo hay meteocat que cuente para los 6 minutos»,
  Juanjo, 16-10-2026), aviso de AEMET vigente en el Vallès, plan de Protección Civil en alerta o emergencia, lluvia en alguna
  estación (Montflorit o Meteocat), lluvia en el radar a menos de 15 km
  (`RADAR_AVISO_KM`) o lluvia que el radar llevado hacia delante ve llegar a
  casa en la próxima hora (ADR 0019).
- **En modo aviso, cada 6 minutos** (`MODO_AVISO_INTERVALO_MIN`): la página de
  casa todo el día y la del trayecto dentro de sus franjas. Es el ritmo del
  radar de Meteocat, la imagen principal desde el ADR 0019; más deprisa no
  sirve. Hasta el 06-10-2026 era cada 10 minutos, el ritmo de RainViewer, y
  no se podía bajar porque GitHub Pages admite unas 10 publicaciones por hora;
  ahora los datos van a IONOS (ADR 0020).
- **Con 3 minutos de desfase** (:03, :09, :15…; `MODO_AVISO_DESFASE_MIN`), para
  coger siempre la imagen nueva: Meteocat la saca a :00, :06, :12… y la publica
  unos 13-14 minutos después. Es la misma idea que propuso Juanjo con
  RainViewer («puedes actualizar un minuto después de que se actualice»), con
  un intervalo fijo que no se desplaza respecto a las imágenes.
- **El horario lo decide un solo sitio:** cada publicación escribe su horario
  en los datos (`horari`, con `cada_min`, `desfase_min` y `mode_avis`), la web
  lo muestra («Mode avís: dades cada 6 min») y el reloj del NAS lo lee con
  `que_toca.py` para decidir qué hacer en cada minuto. Lo que dice la página y
  lo que se hace no pueden separarse.
- **La decisión de la mañana** se sigue recalculando en la pasada de las 7:31:
  el corte es el final de la ida más el desfase y dos minutos.

## Alternativas descartadas

- **Cada 11 minutos:** el minuto de actualización iría cambiando respecto a
  las imágenes del radar; unas veces cogería la nueva y otras no.
- **Cada 10 minutos siempre:** sin riesgo no aporta y multiplica las consultas.

## Consecuencias

En un día de aviso, la estación de Montflorit pasa de 24 a hasta 144
consultas (unos 380 KB cada una), y el registro guarda más líneas. Con un plan
de Protección Civil activado sin hora de fin, el modo aviso dura hasta que lo
desactivan.

## Evidencia

- Medida del 05-10-2026: la imagen de las 11:10 ya estaba disponible a las
  11:10:47; el archivo de RainViewer indicaba la de las 11:00 generada a las
  11:00:23.

## Riesgos y limitaciones

- Si RainViewer se retrasa más de un minuto, esa pasada coge la imagen
  anterior; la siguiente, diez minutos después, ya tiene la nueva.

## Validación

Pruebas automáticas del horario normal, del modo aviso con desfase, del paso
por las 23:50 y de las razones que activan el modo aviso
(`tests/test_horario.py`).

## Cambio del 09-10-2026: cómo se dice en la página

Desde la 3.41.0, la línea de actualización (arriba en las tres páginas, ADR
0040) dice solo «Mode avís» con un «?» al lado, el mismo de los planes de
Protección Civil (`botoAjuda` en `web/comu.js`). Al pulsarlo, debajo: «Quan
hi ha un avís de l'AEMET, un pla de Protecció Civil en alerta o emergència,
pluja a Montflorit o pluja al radar a menys de 15 km, la pàgina s'actualitza
més sovint: cada 6 minuts en lloc de cada 15, al ritme de les imatges del
radar.» Los 15 km y los 15 minutos van en los datos (`radar_km` y
`normal_min` del horario, `prevision.horario`), para que el texto siga a
`config.py`. Juanjo, 09-10-2026: «como la gente no sabe qué es modo aviso,
un ? que al pulsarlo salga la descripción». Antes decía «Mode avís: dades
cada 6 min.», y fuera del modo aviso, «Dades en directe cada 15 min.», que
se quita porque la próxima hora ya lo dice.

## Cambio del 10-10-2026: «Seguiment de prop»

En la página, el modo aviso se llama «Seguiment de prop» («Seguimiento de
cerca»), con el mismo «?» que explica cuándo y por qué. Juanjo: «modo aviso
no me gusta, ¿qué tal modo alerta Montflorit?». «Alerta» se descartó porque
es el nombre de una fase de los planes de Protección Civil que la misma
página muestra, y se habría leído como una alerta oficial. En el código y en
los datos sigue siendo `mode_avis`. Desde la 3.49.0, un plan sin motivo
meteorológico a la vista no lo activa (ADR 0062).

## Cambio del 10-10-2026, por la tarde: «Mode normal» y «Mode vigilància»

Juanjo: «no me gusta de prop, no dice nada», y pidió que la línea de la
actualización empezara por el modo, con un «?» que explicara la diferencia
entre los dos y, en el modo aviso, el motivo entre paréntesis. Los nombres
son «Mode normal» y «Mode vigilància» («Modo normal», «Modo vigilancia»):
vigilancia dice qué pasa (hay algo cerca y la página lo mira más a menudo).

- **Una línea propia para el modo**, encima de «Actualitzat a les… ·
  propera…», igual en los dos modos, para que la página no dé un salto al
  cambiar de uno a otro. Medido en el móvil (360-412 px): con el modo delante
  de la hora, la línea ocupaba dos en cualquier forma que conservara
  «actualitzat»; así son siempre dos, partidas por el sitio que toca.
- **El motivo entre paréntesis**, con los nombres de `motivos_modo_aviso`
  traducidos («Mode vigilància (pluja al radar)»; varios, separados por
  comas). El «?» va pegado a la última palabra para que no baje solo.
- **El «?» en los dos modos**, con el mismo texto: «Mode normal: la pàgina
  s'actualitza cada 15 minuts. Mode vigilància: s'actualitza cada 6 minuts,
  just després de cada imatge nova del radar de Meteocat. La pàgina es posa
  en mode vigilància quan hi ha un avís de l'AEMET, un pla de Protecció Civil
  en alerta o emergència, pluja a Montflorit o pluja al radar a menys de
  15 km. Quan ja no hi ha res d'això, torna al mode normal.» Juanjo corrigió
  la primera redacción («hi passa sola no queda bien… ninguno se entiende»):
  se nombra cada modo con todas las letras, sin pronombres.
- **El horario de los datos lleva siempre los dos ritmos** (`normal_min`,
  `avis_min`) y la distancia del radar (`radar_km`), también en modo normal,
  para que el «?» pueda explicarlos; con datos de antes, los valores de
  siempre.
- Sustituye a la decisión del 09-10-2026 de no decir nada en el ritmo normal.
- **Cada modo con su color** (3.51.1; Juanjo: «¿puedes poner con colores
  apropiados cada modo? Así destaca un poco más»): el nombre va en una
  etiqueta, verde el normal y ámbar el de vigilancia, los dos colores con que
  la web ya dice «va bien» y «atención» (el rojo queda para el peligro). El
  motivo y el «?» siguen al lado, en texto normal. Contraste del nombre sobre
  su fondo: 6,4:1 y 4,7:1 en claro (el verde de la etiqueta, `--verd-text`,
  es más oscuro que `--verd`, que daba 4,5 justos), 8,8:1 y 9,1:1 en oscuro.

## Cambio del 12-10-2026: el modo deja de mostrarse con nombre

El ADR 0074 quita de la web «Mode normal» y «Mode vigilància»: con «pluja al
radar» al lado de «No plou» y «Serè», quien no conocía la página no sabía qué
se vigilaba. Queda «Actualitzat a les … · propera: …», y un «?» que explica
cada cuánto se actualiza y por qué. El modo aviso sigue igual en el servidor.
Desde la 3.68.2, el «?» ya no dice «just després de cada imatge nova del radar
de Meteocat» (Juanjo: «esto sobra»): solo cada cuánto se actualiza y cuándo.

## Cambio del 19-10-2026 (3.148.1): las horas que el reloj no pudo mirar

A las 06:56, lloviendo, la web decía «Actualitzat a les 06:50 · propera:
06:51» (lo vio Juanjo). Una pasada fuera de horario, por código nuevo en
main, empezó a las 06:50:05 y acabó a las 06:51:37: el reloj solo mira el
minuto en que vuelve a empezar la vuelta, así que la hora de las 06:51 no se
miró nunca y no hubo pasada hasta la de las 06:57 (publicada a las 06:58).
Pasaba igual con cualquier pasada que cruzara una hora del horario. Ahora
`nas/reloj.sh` mira todos los minutos desde el último que miró (media hora
como mucho; al arrancar, solo el de ahora) y, si alguno tocaba, hace una
pasada. Probado con `que_toca.py` y el horario de hoy: de 06:50 a 06:52 toca
(06:51 saltada); de 06:52 a 06:53 no; de 06:51 a 06:52, ya mirada, no.


## Cambio del 20-10-2026 (3.166.2): la lluvia del radar, la que enseña la página

«Pluja al radar» pone la página en modo aviso con la lluvia de 0,5 mm/h o más
(`nowcast.PLOU_MMH`) a `RADAR_AVISO_KM` o menos, la misma que la página enseña
como «pluja» y como la más cercana (`nowcast.propera`). Antes contaba desde
0,08 mm/h (unos 6 dBZ, casi siempre llovizna que no llega al suelo): el
20-10-2026 la página se actualizaba cada 6 minutos por ecos de 0,1 mm/h a 14,6
km mientras decía que la lluvia más cercana estaba a 36 km (Juanjo: «por qué
se actualiza cada 6 minutos si no hay ningun aviso?»). La lluvia débil que se
acerca sigue cubierta por la otra regla (un 20 % o más en casa en la próxima
hora, según el radar llevado hacia delante). Y el «?» de «Actualitzat a
les…» dice primero el motivo de ahora («Ara cada 6 minuts perquè el radar veu
pluja a 13 km.»), con la distancia (`horari.km_pluja`). Con el radar de ese
momento, la lluvia de 0,5 mm/h más cercana estaba a 61 km: sin modo aviso.

Desde la 3.212.2 (05-11-2026), la distancia solo se dice cuando es el motivo
(`km_pluja` a `RADAR_AVISO_KM` o menos, `prevision.horario`). Si el modo aviso
viene de la otra regla (lluvia que el radar prevé en casa en la próxima hora),
el «?» dice «el radar veu pluja que pot arribar en la propera hora». El
revisor (ADR 0101) lo vio dos veces el 05-11-2026: «perquè el radar veu
pluja a 21 km» (y «a 15 km», con 15,4) junto a una explicación que pedía
menos de 15 km. La explicación nombra ahora las dos reglas: «pluja al radar
a 15 km o menys o que pot arribar en la propera hora».
