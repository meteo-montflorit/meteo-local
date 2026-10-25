# 89. El cambio de hora

Fecha: 2026-10-13 · Estado: aceptado

**25-10-2026 (3.201.0): sustituido en parte por el ADR 0128.** Desde entonces
las horas se guardan y se calculan en UTC («…Z») y solo lo que se publica va
en hora de Madrid, siempre con el desfase; `prevision.clau_hora` da la clave
en UTC. Lo de este ADR que sigue valiendo: Open-Meteo pone a toda la serie el
desfase del momento de la consulta, y `prevision.horas_locales` lo corrige.

## Contexto

Juanjo preguntó el 13-10-2026 cómo trataba la web el paso de la hora de
verano a la de invierno y al revés: «una hora salga duplicada o falte». No lo
trataba. Comprobado ese día con la previsión real de Open-Meteo para el
25-10-2026 (el próximo cambio, a 12 días):

- **Open-Meteo pone a toda la serie el desfase del momento de la consulta**
  (`utc_offset_seconds`, `timezone_abbreviation` «GMT+2»), no el de cada hora.
  Pedido el 13-10, el 26-10 a las 22 h según Open-Meteo era en realidad las
  21 h de invierno; y un día de enero, pedido en octubre, también salía a
  GMT+2. Con `timeformat=unixtime`, en cambio, el 25-10 tenía las 2 h dos
  veces (02:00+02:00 y 02:00+01:00).
- **El programa tomaba esas horas como hora local** (`casa.py`, `aire.py`).
  Los dos días antes de cada cambio, la previsión de después del cambio iba
  una hora desplazada, y no casaba con las fuentes que dan la hora universal
  (Meteocat, el radar, las estaciones). En octubre la noche del cambio no
  repetía «2–3», cuando ese día tiene 25 horas; en marzo el navegador habría
  convertido las 2 (que no existen) en las 3 y «3–4» habría salido dos veces.
  Lo mismo con la salida y la puesta del sol de esos días, y el registro de lo
  previsto habría guardado esas horas emparejadas con la medida equivocada.
- **Las horas viajan como texto sin desfase** («2026-10-25T02:00») en todo el
  programa, los registros del NAS y la web: se comparan como texto, se cortan
  (`[11:13]`) y son la clave de los CSV. En octubre, la segunda hora de 2 a 3
  habría pisado a la primera en los registros de lo medido.

## Decisión

- **Las horas de Open-Meteo se pasan a la hora de Madrid nada más llegar**
  (`prevision.horas_locales`), con el desfase que declara la propia
  respuesta: las horas, la salida y la puesta del sol. En todas las consultas
  de `casa.py` (modelos, ensemble, ECMWF, nubes, UV, sol) y la del aire.
- **Una sola forma de escribir una hora, `prevision.clau_hora`**: la de
  siempre («…T02:00»), salvo la hora que se repite en octubre, que lleva el
  desfase («…T02:00+02:00» y «…T02:00+01:00»), para que sean dos horas
  distintas. Así no hay que migrar ningún registro ni cambiar las 55 líneas
  que leen las horas como texto: el corte `[11:13]` sigue dando la hora, la
  comparación como texto sigue valiendo y `fromisoformat` entiende las dos
  formas. La usan la previsión (`casa.py`) y los registros de lo medido
  (`registre.py`, `vent_veines.py`, `nuvols.py`, `sol_estacio.py`,
  `aprenentatge.ratxa_observada`), que se ordenan por el momento real
  (`prevision.ordre_hora`): como texto, «+01:00» iría antes que «+02:00».
- **El bot** compara y ordena las horas de la previsión con
  `bot.hora_local`, que les quita el desfase: mezclar horas con y sin él da
  error en Python.
- **La web** coloca cada hora donde toca (`new Date` entiende el desfase): la
  noche de octubre, «2–3» sale dos veces, y la de marzo no sale. «Com es
  llegeix la previsió» lo explica solo cuando la tabla incluye un cambio de
  hora. `diaAbans` (la comparación con ayer) quita el desfase para buscar la
  misma hora del día anterior.

## Alternativas descartadas

- **Pedir las horas en tiempo universal y escribir todas con desfase**: más
  limpio, pero obligaba a migrar los registros del NAS y a cambiar todas las
  lecturas de horas como texto, con riesgo de romper el aprendizaje por una
  hora al año.
- **Quitar la hora repetida**: se perdía una hora de lluvia y de registro
  cada octubre.

## Evidencia y validación

- Open-Meteo, 13-10-2026: `api.open-meteo.com/v1/forecast` del 24 al 26-10
  con `timezone=Europe/Madrid` (72 horas, GMT+2 en todas) y con
  `timeformat=unixtime` (las 2 h dos veces); `historical-forecast-api` del
  15-01-2026, también GMT+2.
- `tests/test_canvi_hora.py` (nuevo), con los dos cambios reales (25-10-2026
  y 28-03-2027): las horas, la salida del sol, la tabla de la previsión de
  punta a punta (cada fila acaba donde empieza la siguiente y dura una hora),
  el bot y el registro, que guarda las dos horas de 2 a 3 en su orden.
- `casa.py` ejecutado el 13-10-2026: las mismas horas, sol y UV que lo
  publicado. Los registros del NAS reescritos con la nueva ordenación salen
  idénticos.
- En el navegador, con el reloj puesto en las dos noches y datos simulados,
  en Chromium y Firefox, catalán y castellano: la tabla y la explicación.

## Consecuencias

- Los datos públicos pueden llevar, una hora al año, `hora` y `fins` con
  desfase. Quien los lea debe usar `fromisoformat` (o `new Date`), no
  comparar fechas sin zona con fechas con zona.
- Lo que se agrupa por hora del reloj mezcla, el mes siguiente a cada
  cambio, horas de sol distintas. Resuelto el 14-10-2026: la parte alta
  (3.82.1, ADR 0087) y el modelo aprendido (3.83.0, ADR 0012) van por hora
  solar, con la regla del ADR 0090: lo que depende del sol, en hora solar; lo
  que depende de las personas, en hora local.
