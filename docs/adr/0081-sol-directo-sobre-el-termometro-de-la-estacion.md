# 81. Sol directo sobre el termómetro de la estación

Fecha: 2026-10-12 · Estado: aceptado

## Contexto

Juanjo preguntó si, cuando a su estación le da el sol y sube mucho, se corrige
con las estaciones cercanas: «mi estación está en una zona del barrio
normalmente más fría que el resto y quiero que siga siendo así, pero en el caso
de que dé el sol se podría sacar de las otras?». Y luego: «¿no se puede mirar
directamente la radiación en lugar de suponer?», y que el pico «va variando con
el sol», a veces también por la tarde.

Con las lecturas cada 5 minutos de Ecowitt (9 al 12-10-2026), las mañanas
soleadas la estación sube de 3 a 5 °C entre las 8:35 y las 9:05 y luego baja
un poco, mientras las vecinas suben poco a poco (el 9: 9,2 °C a las 8:30, 14,7
a las 9:05; vecinas, 10,5 a las 9). Los días nublados (5 y 7) no pasa. El
resto del día, la estación marca alrededor de 1 °C menos que la mediana de las
vecinas.

El sensor de radiación no lo ve: durante el salto marca de 20 a 37 W/m², lo
mismo que a las 9:45 o 10:00 sin pico, y mucho menos que los 100 W/m² del 11 a
las 10:30, también sin pico.

## Decisión

Versión 3.72.0. `sol_estacio.py`:

- **Se detecta por el salto de la estación, no por la hora ni por la
  radiación**, para que valga a cualquier hora y en cualquier época:
  - empieza, de día (radiación > 0), si la estación ha subido 1,5 °C o más en
    los últimos 30 minutos y está 1,5 °C o más por encima de lo esperado;
  - sigue mientras esté 0,7 °C o más por encima, de día y como mucho 3 horas.
- **Lo esperado**: la mediana de las vecinas de Weather Underground leídas en
  los últimos 30 minutos (al menos dos) más la **diferencia habitual** de la
  estación, la mediana de (casa − vecinas) en las horas en punto de los últimos
  30 días, sin las horas con sol directo. Así la zona más fría se conserva.
  Desde la 3.215.0, de la **franja de 3 horas de hora solar** (UTC,
  `prevision.hora_solar`, ADR 0090) de la hora que se corrige: 0-2, 3-5, 6-8
  h…; si la franja tiene menos de 10 horas comparables, la de todo el día
  (`sol_estacio.ofsets`; ver «Validación»).
- **Mientras dura**, «Ara» muestra la temperatura esperada, sin nota: en la
  3.72.1 se quitó la que decía «Estimada: el sol toca l'estació» (Juanjo:
  «quita lo de que está dando el sol... esos detalles no interesan a la
  gente»); el método sigue explicado en «D'on surt». La
  **humedad relativa** también se corrige: se recalcula con el punto de rocío
  medido, que el sol no cambia, y la temperatura esperada (Juanjo: «si lo ves
  conveniente aplica lo mismo al resto de mediciones»). La presión y la lluvia
  no las toca el sol.
- **No se aprende de esas horas**: cada episodio se apunta en
  `registre/sol-estacio.csv`, y sus horas no cuentan para la corrección de la
  temperatura de la previsión (`aprenentatge.mostres`).
- **Para comparar con ayer llevan la temperatura esperada** (versión 3.75.4;
  `sol_estacio.amb_esperades`, desde `registre.temperatures_casa` y
  `casa.py`), la misma cuenta que «Ara». Hasta la 3.75.3 se quitaban, y como
  la comparación de un tramo necesita todas sus horas, la mañana de los días
  de sol se quedaba sin «graus més o menys que ahir». Juanjo (13-10-2026):
  «no es que no haya datos, solo no hay datos de mi estación». Si en esa hora
  no hay dos vecinas o no hay diferencia habitual, la hora se quita, como
  antes.
- `python3 sol_estacio.py omple [DIES]` repasa el historial cada 5 minutos y
  apunta los episodios pasados (donde hay vecinas por horas).
- La subida a Weather Underground (ADR 0059) sigue con lo que mide la
  estación: es una medida, no una estimación.

## Alternativas descartadas

- **Por la radiación**: no lo ve (arriba).
- **Por la hora** (8:30–9:30): cambia con la época, y en verano o invierno
  también hay tardes (Juanjo).
- **Sustituir la temperatura por la de las vecinas sin más**: perdería la
  zona más fría de la estación.

## Consecuencias

- «Ara» no enseña los picos de sol, y lo que se aprende de la estación queda
  limpio.
- Si las vecinas no se pueden leer, o hay menos de 24 horas comparables, no
  se corrige (como hasta ahora).

## Riesgos y limitaciones

- Un cambio de tiempo real muy brusco de día (una entrada de aire cálido)
  podría parecer un pico; para eso se exige también estar por encima de las
  vecinas.
- Mejor aún sería que el sol no llegara al termómetro (una sombra o un
  protector de radiación): la corrección es una red de seguridad.
- Sin 24 horas comparables o sin dos vecinas leídas en la última media hora,
  no se corrige; la reserva de IONOS tampoco corrige (no tiene el registro de
  la estación ni el de las vecinas).
- Las franjas se han validado con un mes de otoño (10-10 al 09-11-2026). En
  invierno o en verano el reparto puede cambiar; como cada franja es una
  mediana móvil de 30 días, se ajusta sola. Las franjas de la noche tienen
  menos datos (unas 75 horas frente a 90), pero de sobra por encima del
  mínimo de 10.

## Validación

- `tests/test_sol_estacio.py`: el salto del 9 de octubre se detecta, sigue y
  acaba; sin salto, de noche, sin diferencia habitual o con una sola vecina, no
  se decide; la diferencia habitual sin las horas de sol; la humedad con el
  punto de rocío; apuntar y alargar un episodio. 407 pruebas en verde.
- 3.75.4: `test_les_hores_de_sol_amb_la_temperatura_esperada` (la hora de sol
  con la esperada; con una sola vecina o sin diferencia habitual, fuera). Con
  el registro del NAS del 12-10-2026 (diferencia habitual −1,1 °C), las 9 h
  pasan a 12,9 °C (vecinas 14, 14, 14 y 15) y las 10 h a 14,9 °C (16, 15, 16 y
  16). 412 pruebas en verde.
- 3.215.0, franjas de hora solar. Hasta la 3.214 la diferencia habitual era
  una para todo el día, y del 9 al 12-10-2026 ya se veía que cambiaba con la
  hora (de −0,5 a −0,9 °C de 8 a 10 h y hasta −2,7 °C por la tarde). Juanjo
  aceptó revisarlo con un mes de datos (12-10-2026: «si, de acuerdo») y aprobó
  el cambio el 09-11-2026. Con el registro del NAS del 10-10 al 09-11-2026
  (684 horas comparables, sin las 4 de episodios de sol), la diferencia de
  todo el día es −0,8 °C, y por franjas de hora solar: 0-2 h −0,5; 3-5 h
  −0,5; 6-8 h −0,4; 9-11 h −1,4; 12-14 h −1,8; 15-17 h −1,4; 18-20 h −0,7;
  21-23 h −0,5 °C (de 74 a 90 horas cada una). Validado dejando fuera un día
  cada vez y calculando con los demás, el error medio de la temperatura
  esperada baja de 0,71 a 0,59 °C en todo el día y de 0,70 a 0,61 °C de 6 a
  9 h. Prueba pareada de permutación de signos por días (20.000 repeticiones)
  con bootstrap por días para el intervalo: en todo el día, 0,12 °C menos de
  error (IC 95 %: 0,06 a 0,18; p = 0,002), mejor en 22 de 31 días; de 6 a
  9 h, 0,09 °C menos (IC 95 %: 0,02 a 0,15; p = 0,014), mejor en 21 de 30.
  Hora a hora casi no gana más (0,58 °C) con un tercio de los datos por
  hora; con franjas de 6 h, menos (0,69 °C de 6 a 9 h).
  `test_diferencia_habitual_per_franges_d_hora_solar`.
