# 90. Hora solar para lo que depende del sol, hora local para lo que depende de las personas

Fecha: 2026-10-14 · Estado: aceptado

**25-10-2026 (3.201.0):** la regla «lo que se guarda, en hora local» queda
sustituida por el ADR 0128: se guarda y se calcula en UTC, y la hora de
Madrid se usa solo para lo que se muestra y para las reglas de las personas.
Lo demás de este ADR sigue igual.

## Contexto

Tras el ADR 0089 (el cambio de hora) quedaban dos cálculos agrupados por la
hora del reloj: la diferencia de la parte alta (ADR 0087) y la hora del día en
el modelo aprendido (ADR 0012). El mes siguiente a cada cambio de hora, la
misma hora del reloj corresponde a dos alturas del sol distintas. La parte
alta se pasó a hora solar en la 3.82.1; el modelo se dejó con la del reloj
porque la hora solar no lo mejoraba de forma apreciable. Juanjo preguntó el
14-10-2026 si eso no mezclaba criterios («para ser coherentes y evitar
problemas en el futuro no habría que hacerlo todo en hora solar?») y, con la
regla que sigue, pidió aplicarla («sí, hazlo»).

Repaso de todo lo que usa la hora del día en el programa (14-10-2026): además
de esos dos cálculos, solo lo que depende de las personas. «Si surts» mira las
horas en que la gente sale (`HORES_SORTIR`) y viste para ellas (`HORES_ROBA`
del bot); el bot y los avisos de la web dan el resumen de mañana a partir de
una hora (`HORA_DEMA`) y escriben «de 18 a 19 h»; la tarjeta de la tabla cierra
los tramos a horas fijas (`FI_TRAMS`). La detección del sol sobre el termómetro
(ADR 0081) no agrupa por horas.

## Decisión

Versión 3.83.0.

- **Lo que depende del sol, en hora solar**: el calentamiento, la
  convección, la diferencia entre la parte alta y la riera y las señales del
  modelo aprendido. Se usa `prevision.hora_solar`: la hora del tiempo
  universal, que no cambia con el reloj. En Montflorit (2,1° E) el sol pasa por
  su punto más alto hacia las 12 de esa hora todo el año (con la hora oficial,
  hacia las 13 en invierno y las 14 en verano).
- **Lo que depende de las personas, en hora local**: lo que se muestra y se
  escribe, las horas de salir, la ropa, el resumen de mañana y todo horario.
  Pasarlo a hora solar haría que, en invierno, «Si surts» mirase las 7 en vez
  de las 8.
- **Lo que se guarda, en hora local**, como hasta ahora (ADR 0089): la
  conversión se hace al calcular.
- **El modelo aprendido** (`aprenentatge.rasgos`) toma la hora y el día del
  año del tiempo universal, y los tres modelos de partida
  (`calibracio/pluja_casa.json`, `pluja_casa_ecmwf.json` y
  `temperatura_casa.json`) se han vuelto a ajustar con ella. En el NAS no
  había modelo propio guardado: cada día se ajusta desde cero con el
  registro, ya con la hora nueva.
- **La parte alta** (ADR 0087) usa la misma función.
- Un cálculo nuevo que agrupe o use la hora del día se pregunta primero de
  qué depende y sigue esta regla. Está en `CLAUDE.md` y `AGENTS.md`.

## Alternativas descartadas

- **Todo en hora solar**, también lo que se muestra y los horarios: la gente
  vive con el reloj; los tramos, las horas de salir y los avisos dejarían de
  corresponderse con lo que se lee.
- **Dejar el modelo con la hora del reloj** (3.82.1): acierta igual, pero la
  regla dejaba de ser una sola, y un cálculo nuevo podía copiar la forma
  equivocada.
- **Hora solar verdadera** (con la longitud y la ecuación del tiempo): el
  tiempo universal se separa de ella entre unos −6 y +25 minutos según la
  época, sin saltos; para agrupar por horas y para el seno y el coseno de la
  hora no cambia nada.

## Consecuencias

- La hora del modelo y la de la parte alta no se desplazan con el cambio de
  hora; la tabla y los textos sí siguen el reloj.
- Quien lea los pesos de los modelos de partida debe saber que la hora es la
  del tiempo universal (lo dicen `aprenentatge.rasgos` y `docs/estadistica.md`).

## Evidencia

- `calibracio/hora_solar.py`: con las mismas muestras y los mismos grupos de
  semanas no vistas, solo cambiando la hora. Temperatura (43.099 horas de 363
  días): error de 1,031 °C con la del reloj y 1,029 °C con la solar; la
  diferencia, −0,002 °C, con intervalo del 95 % por bootstrap de días de
  −0,004 a −0,0002 °C. Sin la estación al prever, 1,162 y 1,159 °C. Lluvia
  (94.380 muestras de 1.000 días): Brier 0,02480 y 0,02479, sin diferencia.
- Los tres modelos de partida, vueltos a ajustar (antes con el código de la
  3.82.1, que los reproducía idénticos): lluvia a corto plazo 0,02253 y a un
  día 0,0271, iguales; con ECMWF, 0,02195 → 0,02194 y 0,02575 → 0,02574;
  temperatura, 1,031 → 1,029 °C (0,77 → 0,76 °C a una hora).
- En el NAS, el 14-10-2026, `/estat/aprenentatge/` no tenía `model.json`: el
  modelo en uso era el de los archivos de partida.

## Riesgos y limitaciones

- La mejora es de milésimas: el cambio se hace por coherencia, no por
  acierto. Lo que sí evita es que el mes siguiente a cada cambio de hora el
  modelo vea el sol una hora desplazado.

## Validación

- `tests/test_aprenentatge.py`, `test_la_hora_es_la_del_sol`: las 15 h de
  verano y las 14 h de invierno dan la misma señal; las dos horas de 2 a 3 del
  25-10, distintas. `tests/test_part_alta.py`, las de la 3.82.1.
- 455 pruebas en verde.
