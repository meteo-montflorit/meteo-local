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
  de antes, sin zona como hora de Madrid (`llegeix`), que devuelve siempre UTC;
  la conversión de un dato entero a claves UTC (`interna`, desde la 3.202.0); la hora
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

## Revisión del mismo día (3.202.0)

Juanjo pidió no dar nada por bueno sin revisarlo todo («no quiero que el uso
de utc provoque a corto o medio plazo problemas por no haberlo revisado todo
bien. especialmente datos que se leen de apis»). Cuatro revisiones completas,
cada una de una parte (las fuentes externas una a una, contra su
documentación, una consulta real y los registros; el guardado, las
comparaciones y los cálculos; la web, el bot y los avisos; y cada hora que se
formatea para la gente), con cada hallazgo comprobado en el código antes de
corregirlo:

- **De lo publicado hoy**:
  - «Perill» habría duplicado cada ficha nueva: el historial interno, en UTC,
    se unía con el `avisos.json` publicado, en hora de Madrid, comparando el
    comienzo como texto.
  - Las correcciones del revisor no se habrían aplicado nunca, por lo mismo en
    la clave `clau|inici` (`revisor.clau_fitxa`).
  - La web pasaba las horas, ahora con desfase, a la zona del dispositivo.
  - `hora.llegeix` solo convertía a UTC las horas sin zona.
- **De las fuentes, de antes de la 3.201.0**:
  - Las franjas de los avisos de previsión de Meteocat son horas UTC y se
    leían como de Madrid (ADR 0067).
  - La hora de elaboración de AEMET es UTC y se leía como de Madrid; se
    corrigen una vez las ya guardadas (`migra_utc.corregeix_elaborat_aemet`).
  - El horario de autobuses guardado con el cálculo anterior (ADR 0120).
  - Y, sin relación con la hora, el archivo de avisos de FGC con avisos de PHP
    delante (ADR 0079).
- **Los días del cambio**: franjas partidas o duplicadas (`smp.junta` y las del
  bot, ahora unidas por el momento), la hora en curso del bot en la primera
  de 2 a 3, «d'aquí a N hores», el desfase de las franjas visibles de AEMET, el
  aviso de «demà» en «Consultes» la víspera y la hora de marzo que no existe en
  la calidad del aire.

Lo que cambia en la regla:

- **`hora.llegeix` devuelve siempre UTC**, venga con «Z», con desfase, sin zona
  o con `ZoneInfo`; para mostrar, `hora.local`.
- **`hora.interna`, el contrario de `hora.publica`**: pasa a clave UTC toda
  hora con desfase o sin zona. Se aplica a lo que se lee de lo publicado
  (`avisos_bot.anterior_publicat`, `llegeix_arxiu`) y al estado de antes
  (`bot-avisos.json`), y a lo que se escribe: `casa.json` entero
  (`casa.recoger`) y cada línea de los JSONL del registro. Así un archivo
  interno no mezcla formas y se compara bien como texto.
- **Lo que se compara, se compara como momento** (`H.utc`, `H.clau`) cuando
  puede venir de dos sitios: la unión del historial, las claves del revisor,
  los máximos de horas.
- Los lectores del registro que no normalizaban (`boira`, `nuvols`,
  `part_alta`, `vent_veines`) pasan también las claves a UTC al leer.
- **La web, siempre en hora de Madrid**, sea cual sea la zona del dispositivo:
  hasta la 3.200.0 casi todas las horas llegaban sin zona y el navegador las
  enseñaba tal cual; desde la 3.201.0 llevan el desfase y el navegador las
  pasaba a la zona del dispositivo (en Nueva York, la tabla «5–6» en lugar de
  «10–11»). Unas pocas (la hora de actualización, las fases de la Luna,
  «Perill») ya fallaban así antes. Ahora todo pasa por las funciones de
  `web/comu.js` (`ZONA_HORA`, `llegeixHora`, `partsHora`, `diaLocal`,
  `horaLocal`, `deRellotge`, `mitjanit`…), y `baixa()` pone el desfase a las
  horas sin zona de los datos de antes (`ambDesfas`, los días del historial
  hasta el 23-10). La web habla de un lugar: «plourà cap a les 15 h» es la
  hora de Montflorit, como en los horarios de trenes, el bot y las imágenes.
  `tests/test_web_zona.py` lo comprueba con el dispositivo en cinco zonas y
  las dos noches del cambio; con Playwright, cada página dio el mismo texto en
  Madrid, Nueva York, UTC, Canarias y Tokio, en Chromium, Firefox y WebKit.

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
- El hueco de casi dos horas en `ecotop.csv` la noche del cambio no fue un
  fallo: el NAS publicó cada 15 minutos toda la noche, y `ecotop.py` solo baja
  imágenes con lluvia a la vista; de 23:45 a 1:15 UTC la más cercana estaba a
  más de 60 km (`radar-a-prop-2026-10.jsonl`). Lo único que falló esa noche,
  cada hora de 2:05 a 8:05, fue la vigilancia del pluviómetro (horas con zona
  y sin ella), uno de los cinco fallos que paraban un proceso; desde la
  3.201.0 acaba bien.

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
- La batería entera (726 pruebas en la 3.201.0; 743 en la 3.202.0), ruff y ESLint.
