# 128. La hora, en UTC por dentro y en hora de Madrid solo en la frontera

Fecha: 2026-10-25 · Estado: aceptado. Sustituye, de los ADR 0089 y 0090, la
regla «lo que se guarda, en hora local».

## Contexto

El 25-10-2026, el día del cambio de hora, al ver que las curvas del 21 de
junio y del 21 de diciembre de «Sol i lluna» salían desplazadas por el horario
de verano, Juanjo pidió: «el cambio horario no debe nunca distorsionar
resultados. por que no utilizas internamente siempre utc y al mostrar datos
los adaptas al horario actual?», y luego: «me refiero a toda la web, no solo
el sol», «tenemos que usar un método robusto para la hora, yo diría que lo
que te he dicho lo es, pero decide tú». El agente decidió hacerlo así.

Hasta la 3.200.0 las horas viajaban como texto en hora de Madrid sin zona
(«2026-10-25T03:00»), con el desfase solo en la hora que se repite en octubre
(«…T02:00+02:00» y «…T02:00+01:00», ADR 0089), y el «ahora» del programa
llevaba el desfase fijo del momento (`now().astimezone()`). Un inventario de
todo el programa hecho ese día (unos 300 sitios que crean, guardan, leen o
agrupan horas) encontró 37 fallos con el cambio de hora, comprobados al
corregirlos:

- **Cinco que paraban un proceso** al mezclar horas con zona y sin ella: la
  publicación entera (`casa.ajusta_hores` con lluvia en el radar en la hora
  repetida, y `riscos` con viento fuerte la víspera), el aprendizaje diario
  (`remostreig.episodis`) y la vigilancia del pluviómetro.
- **Uno que afectó a los vecinos ese mismo día**: los autobuses sin tiempo
  real salían una hora antes todo el día (ADR 0120; corregido aparte en la
  3.199.1).
- Respuestas de Open-Meteo que no pasaban por la conversión (el viento cada
  15 minutos, la niebla de ICON, la previsión de la riera, el viento a 700 hPa):
  una hora desplazadas cerca de un cambio.
- El desfase fijo del «ahora», arrastrado al sumar horas: textos y franjas de
  avisos una hora desplazados después del cambio.
- Comparaciones y ordenaciones de horas como texto con desfases distintos.
- La segunda hora de 2 a 3 que no se apuntaba (`registre.apunta_casa`), la
  hora en curso que desaparecía de la tabla a las 2:xx de verano, nombres de
  archivo que chocaban y franjas de Meteocat con la hora repetida como una sola.

En los registros del NAS había cuatro formas de escribir la hora: sin zona,
con desfase solo en la hora repetida, siempre con desfase y en UTC. Y en
`part-alta-nit.csv` la hora repetida de esa noche estaba guardada al revés.

## Decisión

Versión 3.201.0.

- **Un módulo común, `hora.py`**: el «ahora» en UTC (`ara`); la clave de un
  momento en UTC, «AAAA-MM-DDTHH:MMZ» (`clau`); la lectura de cualquier forma
  de antes, sin zona como hora de Madrid (`llegeix`), que devuelve UTC; la hora
  de Madrid para leer la hora, el día o el texto (`local`, `hora_local`,
  `dia_local`, `iso_local`); la medianoche de un día de Madrid (`mitjanit`) y
  las horas de reloj de un día (`de_rellotge`, para las franjas «de 0 a 24 h»).
- **Todo se calcula y se guarda en UTC**: las claves de la previsión, de los
  registros y del estado. Con el mismo formato y «Z», se comparan y ordenan
  bien como texto, también la noche del cambio. `prevision.clau_hora` pasa a
  dar la clave en UTC y `prevision.horas_locales` convierte a ella las
  respuestas de Open-Meteo (también `minutely_15`); las consultas que no
  pasaban por ella piden ahora la hora en UTC (`timezone=GMT`).
- **La hora de Madrid, solo en la frontera**: lo que se publica pasa por
  `hora.publica`, que convierte cada «…Z» (valor o clave de un diccionario) en
  la hora de Madrid con su desfase («2026-10-25T02:00+01:00»), nunca ambigua:
  `montflorit.json`, `avisos.json` y sus archivos anuales, y el historial de la
  gráfica. Así la web y el bot ven la hora de aquí, como antes, y casi no
  cambian. Lo que se escribe a la gente y las reglas de las personas (las horas
  de salir, la ropa, el resumen de mañana, las preguntas de Telegram) usan
  `hora.local`.
- **Nada depende de la zona del sistema**: fuera los `.astimezone()` sin zona
  y los `now()` sin zona en el código (el bot y la reserva fijan la de Madrid
  al arrancar). Y nada de restar dos horas de Madrid con `ZoneInfo`: Python las
  resta como horas de reloj y el día del cambio se equivoca en una; los
  cálculos, en UTC.
- **Los registros se migran una vez** (`migra_utc.py`), en la primera pasada
  de `casa.py` con la 3.201.0: antes, una copia comprimida de todo el registro
  al lado (`registre-abans-utc-AAAAMMDD-HHMM.tar.gz`); en los CSV y los JSONL,
  cada hora a UTC, con los segundos si los tiene; las fechas solas y los
  textos, como estaban; una marca (`registre/.utc`) para no repetirla. Los
  lectores de los registros normalizan además las claves al leer
  (`registre.llegeix_per_hores`, `aprenentatge._llegeix`, `sol_estacio`,
  `historial.emissions`, …): un archivo que alguien escriba con el formato de
  antes sigue sirviendo.
- **El enlace de cada aviso a su ficha** (`avisos_bot.id_fitxa`) se forma con
  la hora como se publica, la misma con la que la web hace el id de la ficha.

## Alternativas descartadas

- **La hora de Madrid con el desfase siempre**, por dentro también: sin
  ambigüedad, pero no es lo pedido, y como texto se ordena mal la noche del
  cambio.
- **Seguir con la hora local y arreglar los 37 fallos uno a uno**: el mismo
  trabajo y la misma fragilidad para el código nuevo.
- **Publicar en UTC y que la web y el bot conviertan**: cambiaban muchos más
  sitios, y el bot de IONOS se pone al día una hora más tarde que el NAS.

## Consecuencias

- Los datos públicos llevan ahora el desfase en todas las horas, no solo en la
  repetida de octubre. La web y el bot los leían ya así; la comparación con
  ayer (`casa.js` `comparaTemp`, `bot.compara_temp`) y los autobuses del bot,
  que buscaban por el texto sin zona, normalizan antes las claves.
- Los registros nuevos y migrados tienen «fins» en UTC: un análisis a mano tiene
  que pasar a la hora de Madrid para leer las horas del día.
- Los nombres de archivo con la hora (`moviment/`, `ecotop/`) pasan a UTC, con «Z».

## Evidencia

- Los registros del NAS del 25-10-2026 (copia en local): cuatro formatos y la
  hora repetida al revés en `part-alta-nit.csv`.
- Migración de esa copia (35 archivos, 26.382 filas): el aprendizaje
  (`aprenentatge.mostres`, 11.044 muestras) y el historial de los últimos días
  dan exactamente lo mismo antes y después; ninguna hora sin zona queda en los
  CSV; las filas de esa noche, en orden y sin repetirse.
- `casa.py` con las fuentes reales y `montflorit.py dades`: ninguna «Z» en los
  datos públicos; la web (siete páginas, Chromium y Firefox) y los textos del
  bot con la hora de Madrid (el sol a las 7:14, lo peor del aire a las 21:00).
- `avisos_bot.py` con su estado real del NAS: ningún aviso nuevo ni repetido.

## Riesgos y limitaciones

- Una lectura concurrente durante la migración (otro proceso que escribe en un
  CSV a la vez) podría perder una fila: se migra en la primera pasada, con un
  candado, y la copia de antes queda al lado.
- AEMET da la previsión por horas de reloj sin zona: la hora repetida de
  octubre solo puede ser una (la primera) y la de marzo, que no existe, cae en
  la siguiente. Es lo que da la fuente.
- Las pruebas construyen horas «de Madrid» con la zona del sistema: pasan con
  `TZ=Europe/Madrid`, como en GitHub y en el NAS. El código no depende de ella.
- Un hueco de casi dos horas en `ecotop.csv` la noche del cambio no es de cómo
  se guarda la hora: el programa no se ejecutó en ese rato; la causa está por
  averiguar en los registros del NAS.

## Validación

- `tests/test_canvi_hora.py`, con los dos cambios de verdad (25-10-2026 y
  28-03-2027): las claves y su forma publicada; las formas de antes; la resta
  sin error de una hora; las horas de reloj del día del cambio; Open-Meteo
  con el desfase de la consulta; la tabla de punta a punta (las dos franjas de
  2 a 3 en octubre, ninguna en marzo, la hora en curso a las 2:30 de verano);
  la lluvia del radar y el viento fuerte de esa noche sin que nada caiga; el
  bot con los datos publicados; las franjas de Meteocat de 2 a 3; y un registro
  de antes que se migra al guardar sin duplicarse.
- `tests/test_migra_utc.py`: la migración, la copia, que no se repite, los
  segundos y las fechas solas.
- La batería entera (726 pruebas), ruff y ESLint.
