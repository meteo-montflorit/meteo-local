# 120. Los autobuses del barrio: horas de paso e incidencias del AMB

Fecha: 2026-10-22 · Estado: aceptado

## Contexto

El transporte público de «Si surts» solo hablaba de los trenes de Cerdanyola
(ADR 0029): de los autobuses no había datos en tiempo real. El 14-10-2026 las
líneas urbanas de Cerdanyola (CV) aparecieron por primera vez en el tiempo
real del AMB (GTFS-RT). Antes de usarlas se midió durante una semana si eran
de fiar (`calibracio/mostreig_busos.py`, una lectura cada 2 minutos en el
NAS).

Con esos datos se hizo una propuesta en una rama de prueba, que Juanjo fue
ajustando en pantalla el 22-10-2026: trenes y autobuses en apartados
separados de «Si surts»; las horas de cada línea en «Consultes», con las
líneas plegadas para mirar solo la que interesa. Ese mismo día pidió ponerlo
en producción, con la etiqueta «Nou!» en «Consultes» y en «Busos» durante
tres días, que desaparece al abrir cada una, y no en «Si surts».

## Decisión

- **`busos.py`** calcula en cada pasada, sin IA, las líneas del barrio:
  CV1 (Canaletes – Flor de Maig), CV4 (La Farigola – Can Cerdà) y CV5 (FGC
  Bellaterra – Parc Tecnològic), con las paradas del barrio o a tocar en el
  orden en que pasa el autobús. Para cada parada, las horas de paso: las del
  horario oficial (GTFS) corregidas con el tiempo real; si el tiempo real de
  un viaje no trae esa parada, se le aplica el retraso de la parada más
  cercana que sí trae. Y los avisos del AMB (GTFS-RT de alertas) para esas
  líneas, vigentes o futuros, en catalán y castellano tal como los publica.
- **El horario oficial se baja una vez al día.** Es un ZIP de 8,5 MB que el
  AMB renueva cada noche y que cubre unos seis días: se guarda solo lo que
  hace falta (unos 90 KB, `busos-horari.json` en el estado del NAS). Si un
  día no se puede bajar, sirve el guardado mientras cubra hoy (cuatro días).
- **Sin tiempo real**, salen las horas del horario y el pie de la consulta lo
  dice («Hores de l'horari de l'AMB: ara no arriben les del temps real»).
- **«Consultes › Busos»**: cada línea, plegada, con un triángulo de aviso en
  el título si tiene incidencias; abierta, la incidencia, cada sentido con
  sus paradas y las dos próximas horas, y los enlaces al recorrido y al
  horario del AMB en PDF.
- **«Si surts»**: dentro del transporte público, un apartado «Busos» con las
  incidencias de esas líneas a la hora elegida y un enlace a «Consultes».
  Las incidencias de los autobuses no cambian el nivel del transporte
  público, que sigue decidiéndolo el estado de los trenes.
- **«Nou!»** en la pestaña «Consultes» y en la opción «Busos» hasta el
  25-10-2026 a las 10:00, o hasta que se abre cada una en ese dispositivo
  (`FI_NOU_BUSOS` en `web/comu.js`).
- El AMB se acredita en «Fonts» con su licencia.

## Alternativas descartadas

- **Bajar el horario en cada pasada** (cada 15 minutos): unos 800 MB al día
  para un archivo que cambia una vez al día.
- **Que las incidencias de los autobuses bajen el nivel del transporte
  público**: un desvío de una línea no impide ir en tren ni en otra línea, y
  el nivel dejaría de decir lo mismo que hasta ahora.
- **Las líneas desplegadas**: con tres líneas y dos sentidos la consulta era
  larga; Juanjo pidió plegarlas.

## Consecuencias

- Una fuente más que puede fallar: si falla, la consulta dice «Ara aquesta
  consulta no està disponible» y el error va al registro (`errors` de
  `casa.json`), como las demás.
- El bot de Telegram responde a **/busos** (desde la 3.182.0, a petición
  de Juanjo el mismo 22-10-2026) con lo mismo que la web: cada línea con sus
  incidencias, cada sentido con sus paradas y las dos próximas horas, el
  horario en PDF y la hora de los datos (`bot.text_busos_bot`). En la web,
  «Consultes › Busos» se sigue dibujando con los datos, no con ese texto,
  para poder plegar las líneas.
- El muestreo de `calibracio/mostreig_busos.py` sigue en marcha en el NAS.

## Evidencia

- Fuentes: horario `https://www.ambmobilitat.cat/OpenData/google_transit.zip`
  (`feed_info.txt` del 22-10-2026: del 22 al 27 de octubre), tiempo real
  `https://www.ambmobilitat.cat/transit/trips-updates/trips.bin` y avisos
  `https://www.ambmobilitat.cat/transit/alerts/alerts.bin`.
- Licencia: CC BY 4.0, la general de los datos abiertos del AMB según sus
  [condiciones de uso](https://www.amb.cat/web/area-metropolitana/dades-obertes/condicions-d-us),
  que piden citar la fuente; no se ha encontrado una ficha propia de estos
  conjuntos con otra licencia.
- Muestreo del 15 al 21-10-2026 (`docker exec meteo-local python3
  /proyecto/calibracio/mostreig_busos.py resum`): todos los viajes previstos
  de la CV1, la CV4 y la CV5 aparecieron en el tiempo real (salvo uno de la
  CV5 el 20 y el 21) y casi todos antes de salir; en las paradas del barrio,
  entre 5 y 15 minutos antes de pasar, la hora de la CV1 se equivocaba
  típicamente en 0,7-1,2 minutos, y del 65 al 83 % de las lecturas, en menos
  de 2 minutos.
- Las horas de los avisos vienen en hora local escrita como si fuera UTC: el
  22-10-2026 el desvío de la CV1 «hasta el viernes a las 23:59» llegaba como
  23:59Z.

## Riesgos y limitaciones

- La precisión solo se ha medido en la CV1; de la CV4 y la CV5 se sabe que
  aparecen en el tiempo real, no cuánto aciertan.
- Las horas del GTFS se cuentan desde la medianoche local: el día del cambio
  de hora podrían desviarse una hora en viajes de madrugada, que en estas
  líneas no hay.
- La página de condiciones de uso del AMB y el formato de sus feeds pueden
  cambiar sin aviso.

## Validación

- `tests/test_busos.py`: el calendario del horario (también las
  excepciones), la corrección con el tiempo real, la lectura del protobuf, los
  avisos con su hora y el horario guardado cuando no se puede bajar.
- Comparado con el prototipo de la rama de prueba el 22-10-2026: mismas horas
  e incidencias. Probado en Chromium y Firefox, móvil y ordenador, tema claro
  y oscuro.
