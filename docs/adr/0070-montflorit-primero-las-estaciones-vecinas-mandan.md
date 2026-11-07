# 70. Montflorit primero: las estaciones vecinas mandan sobre Sabadell y Sant Cugat

Fecha: 2026-10-10 · Estado: aceptado

## Contexto

Para aprender, una hora contaba como lluviosa solo si la estación de casa lo
marcaba; con casa a cero, contaba como seca solo si tampoco recogieron nada
Sabadell, Sant Cugat (Meteocat, a 2,5 y 4,6 km) e ICERDA6 (ADR 0058 y 0060).
La vigilancia del pluviómetro usaba la menor de esas tres. Juanjo, 10-10-2026:
«para la predicción de la lluvia en Montflorit para mí tiene mucho más valor
las estaciones de aquí mismo que las de Sant Cugat o Sabadell» y «si está
lloviendo en 2 estaciones de Montflorit eso no puede ser una hora seca, a lo
mejor sí lo es en Sant Cugat o Sabadell».

## Evidencia

Historial de cada 5 minutos de las cuatro vecinas (Weather Underground,
`history/all`, del 27-07 al 09-10-2026, en `calibracio/dades/veines`, sin
subir) contra la estación de casa y Meteocat, hora a hora, del 27-07 al
04-10-2026 (1.679 horas); scripts `calibracio/veines_*.py`:

- De las 36 horas en que llovió en casa, ICERDA6 y ICERDA28 no vieron lluvia
  en 2, ICERDA18 en 3, ICERDA48 en 7, Sabadell en 8 y Sant Cugat en 4.
- Con casa a cero, una vecina sola con las demás secas marca lluvia en 0 a
  2 horas de 1.643: casi nunca en falso. Cuando marca, suelen marcar varias.
- Con la regla nueva, 11 horas que no se sabían pasan a lluviosas (el
  03-10-2026 de 14 a 21 h las cuatro vecinas recogieron de 1 a 5 mm por hora
  y casa, cero), 10 pasan a secas (llovía en Sabadell o Sant Cugat, no aquí),
  1 seca pasa a no saberse y el resto no cambia.
- Como señal de la probabilidad a corto plazo (archivo, 1.674 horas, 47 con
  lluvia, validación por semanas): Brier 0,0149 solo con los modelos,
  0,0139 con la lluvia de casa de la hora anterior y 0,0128 con la de casa y
  la mediana de las vecinas.
- El modelo base del archivo, ajustado con la lluvia de Montflorit (un año)
  en lugar de con Sabadell y Sant Cugat (casi tres), no acierta más en
  Montflorit: Brier 0,0207 contra 0,0207 a corto plazo y 0,0273 contra 0,0267
  un día antes. Con solo los modelos como entrada, más años pesan más.

## Decisión

- **Qué pasó en Montflorit** (`aprenentatge.pluja_observada`, para aprender
  y para la comprobación de «Si surts»): llueve si casa lo marca o si lo
  marcan al menos dos vecinas de las que cuentan (`C.VEINES_PLUJA_MIN`;
  ICERDA6, ICERDA18 e ICERDA28); seca si casa marca cero, ninguna de esas ve
  lluvia y las que confirman (`sec`, ahora las tres) están a cero. Si una
  sola ve lluvia, no se sabe. Sin vecinas, como antes: Sabadell y Sant Cugat.
  ICERDA48 sigue sin contar: pierde demasiada lluvia. Desde la 3.213.0, los
  milímetros de una hora con lluvia son la mediana de casa y de esas tres
  vecinas, de las que tengan dato, y sin dato de casa deciden las vecinas
  (revisión del 07-11-2026, al final).
- **Vigilancia del pluviómetro**: la referencia es la mediana de las vecinas
  fiables (con dos al menos); si no hay, la menor de Sabadell y Sant Cugat.
- **La lluvia de las vecinas, en el registro y en el modelo**: cada línea
  del registro guarda desde hoy la lluvia de la última hora de cada vecina
  (`veines`), y la variante `RASGOS_PROPIS_VEINES` (la mediana de las que
  cuentan, como la persistencia) se ajusta cada día y solo se adopta si
  acierta más que el base en sus mismas horas, como la de Sant Cugat
  (ADR 0042). Al prever, la misma mediana de esa pasada.
- **El modelo base del archivo no cambia** (lo dice la evidencia).

## Riesgos y limitaciones

- Las vecinas son estaciones personales: pueden moverse, cambiar o dejar de
  emitir. Si faltan, se vuelve solo a la regla con Meteocat.
- La variante tardará en tener las 30 horas de lluvia que pide el
  aprendizaje: el registro las guarda desde hoy.
- 75 días y 36 horas de lluvia en casa: el examen se repitió con más datos
  el 07-11-2026 (abajo).

## Revisión del 07-11-2026 (3.213.0)

Con el registro del NAS del 10-10 al 07-11-2026 (680 horas, 26 con lluvia
según `pluja_observada`; `estacio-casa.csv`, `veina-*.csv`,
`estacio-casa-5min.csv` y `veines-5min.csv`). Lo decidió Juanjo el
07-11-2026 con estas cifras delante.

- **«Plou ara» con una vecina sola: se mantiene.** Se estudió exigir más de
  0,4 mm en los últimos 15 minutos cuando solo una vecina que cuenta marca
  lluvia y casa no. De los 25 ratos seguidos (en tramos de 5 minutos) en que
  pasó, la regla quitaría 20; solo 2 eran falsas alarmas y en los otros 18
  llovía en otra estación a 30 minutos o menos. Sigue lloviendo si lo marca
  casa o una vecina que cuenta (ADR 0060 y 0101).
- **La variante con la lluvia de las vecinas** (`RASGOS_PROPIS_VEINES`)
  sigue sin adoptarse: a 4 horas o menos de antelación, Brier 0,05356 con
  ella y sin ella, seguridad del 51 %.
- **Los milímetros de la hora: la mediana** de casa y de ICERDA6, ICERDA18
  e ICERDA28, de las que tengan dato (`aprenentatge.pluja_observada`). Hasta
  la 3.212.4 eran los de casa si casa marcaba lluvia y, si no, la mediana de
  las vecinas mojadas. Cuándo llueve no cambia: lo sigue decidiendo la regla
  de arriba. Si la mediana queda por debajo del umbral en una hora que la
  regla da por lluviosa (casa a cero y dos vecinas con poco), vale el umbral
  (0,2 mm la hora, 0,1 mm los 5 minutos): así la hora sigue contando como
  lluviosa; esta salvaguarda la añadió el agente al programarla. Con el
  registro, ninguna hora cambia de lluviosa a seca ni al revés; en 3 de las
  26 lluviosas casa y la mediana difieren 1 mm o más (el 19-10 de 5 a 6 UTC,
  4,1 en casa y 3,05 de mediana; de 13 a 14 UTC, 4,3 y 3,3; y la del 17-10,
  abajo); 2 quedan en el umbral (el 18-10 de 4 a 5 UTC y el 03-11 de 22 a 23
  UTC, con 0,5 mm antes), y el total de las 26 pasa de 47,0 a 40,6 mm: el
  pluviómetro de casa recoge algo más que las vecinas cuando llueve fuerte.
- **Sin dato de casa, deciden las vecinas**: la mediana de las que haya si
  llueve en dos, «no se sabe» si en una, y seca si las que confirman están a
  cero (antes era siempre «no se sabe»). Coincide con lo que ya enseña
  «Ara» cuando falla la estación de casa (ADR 0087). En las horas del
  registro no ha pasado nunca; en los tramos de 5 minutos (`fi_pluja`), 22
  pasan de «no se sabe» a secos, y los 13 episodios de lluvia salen
  idénticos. También vale para «ahora» (`plou_ara_barri`, ADR 0102).
- **El cero de casa del 17-10-2026 de 23 a 24 UTC** (las tres vecinas, de
  3,8 a 4,8 mm; Sabadell, 5,0; Sant Cugat, 3,6) es del pluviómetro, no de
  cómo se tratan sus datos: el historial de 5 minutos de Ecowitt (consultado
  el 07-11-2026 con `ecowitt.historial`) da el acumulado del día a 0,0 y la
  intensidad a 0 desde las 20:00 UTC del 17 hasta las 05:25 UTC del 18, y
  la lluvia de las 05:30 sube desde cero dentro del mismo día de la
  estación (que vuelve a cero a las 22:00 UTC, medianoche en Madrid; visto
  también el 18-10): el balancín no basculó en toda la noche. La
  temperatura de casa bajó de 18,2 a 17,2 °C y la humedad subió del 93 al
  98 % justo cuando empezó a llover en las vecinas (23:05 UTC), y la lluvia
  de las 05:30 casa la marca de 5 a 10 minutos antes que las vecinas: la
  hora de los datos está bien. El registro (`estacio-casa.csv` y
  `estacio-casa-5min.csv`) dice lo mismo que Ecowitt. La regla de la hora ya la daba por lluviosa
  (4,3 mm, la mediana de las vecinas mojadas); ahora da 4,05, la mediana de
  las cuatro. Ver ADR 0017.

Los días ya publicados del historial se rehacen con la regla nueva, por
tandas de 3 por pasada (`historial.FORMAT` pasa a 11, ADR 0099); el
aprendizaje y «Com encerta» la aplican solos, porque leen el registro, que
no cambia (guarda lo que midió cada estación).

Validación: `tests/test_aprenentatge.py` (`test_mm_de_l_hora_amb_la_mediana`:
casa normal, casa a cero con las vecinas mojadas, casa sin dato, una vecina
sin dato y el umbral; `PlouAra` sin casa) y `tests/test_fi_pluja.py`;
comparación de la regla vieja y la nueva con el registro copiado del NAS el
07-11-2026.
