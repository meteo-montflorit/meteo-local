# 60. Las estaciones vecinas de Weather Underground: «plou ara» y horas secas

Fecha: 2026-10-10 · Estado: aceptado

> Desde la 3.57.0 (ADR 0070), las tres vecinas fiables confirman las horas secas
> y, con dos, dan lluvia aunque casa no la marque; Sabadell y Sant Cugat
> quedan de respaldo. Desde la 3.213.0, los milímetros de la hora son la
> mediana de casa y las tres vecinas fiables; «plou ara» con una vecina sola
> se revisó el 07-11-2026 y se mantiene (ADR 0070).

## Contexto

El ADR 0059 dejó la estación de casa subiendo a Weather Underground para
tener la clave de lectura de esa red, y aplazó qué hacer con las estaciones
de los vecinos hasta tenerla. El 10-10-2026, con la estación ya reconocida
como contribuidora, se generó la clave (la página de claves del sitio nuevo
seguía diciendo «You must own a Personal Weather Station»; la versión
antigua del sitio sí la daba, tras aceptar las condiciones con el permiso
de Juanjo). Caduca a los seis meses.

Juanjo había pedido examinar primero las vecinas («habría que examinar las
3 y ver si las podemos usar como verdad de lluvia y quizás también de más
datos») y decidir con los números delante. En la red hay cuatro a menos de
1 km: ICERDA28 (a 300 m al noroeste), ICERDA48 (a 600 m al nordeste), ICERDA18
(en el Puig de la Guàrdia) e ICERDA6 (a 1 km al este, junto a la riera).

## Decisión

- **«Plou ara» cuenta con las vecinas fiables.** Llueve si el pluviómetro
  de casa ha recogido lluvia en los últimos `PLOU_ARA_MIN` minutos o si lo
  ha hecho ICERDA6, ICERDA18 o ICERDA28 (`config.VEINES`, `plou: True`).
  ICERDA48 no cuenta: se queda corta. Como en casa, solo cuenta el sí (ADR
  0017). El bot, los avisos y la primera hora de la tabla usan el mismo
  `plou_ara` de los datos; el bloque «Ara» de la web dice «Plou en una
  estació veïna» cuando es una vecina la que marca. La lluvia en una vecina
  que cuenta también dispara el modo aviso («pluja a les estacions»).
- **Hora seca confirmada, también con ICERDA6.** Cuando casa marca cero,
  la hora cuenta como seca para aprender (`aprenentatge.pluja_observada`)
  y para vigilar el pluviómetro (`pluviometre.REFERENCIA`) solo si las
  estaciones de Meteocat y ICERDA6 (`sec: True`) tampoco recogieron nada.
  ICERDA28 no confirma: deja 0,2 mm sueltos en horas secas.
- **Ni presión ni viento de las vecinas** sustituyen a lo que hay: ninguna
  mejora la presión de casa ni el viento de Sant Cugat. Se registran por si
  sirven más adelante.
- **Una consulta por vecina y pasada** (las lecturas de hoy, cada 5
  minutos: `observations/all/1day`), con la misma lógica de lluvia que la
  estación de casa (`ecowitt.pluja_entre`). Las horas completas van al
  registro del NAS (`veina-<id>.csv`: lluvia, temperatura, humedad, rocío,
  presión, viento y racha), y una vez al día se pide el historial de ayer
  para cerrar la última hora del día. Unas 400 consultas al día en modo
  normal y hasta unas 1.000 en modo aviso; la documentación no fija un
  límite y la página de la clave muestra el uso diario.
- **Si falla una vecina, solo se apunta** en el registro del NAS. Si no se
  puede leer ninguna teniendo clave (caducada, red caída), la página lo
  dice («estacions veïnes»), porque «plou ara» cuenta con ellas (ADR 0031).
  Tres semanas antes de que caduque la clave (`config.WU_CLAU_CADUCA`),
  cada pasada lo avisa en el registro.
- **Atribución** a Weather Underground en «Fonts i crèdits», con el mapa de
  la red centrado en el barrio, y en el README, con las condiciones: uso
  personal y no comercial.
- **Los identificadores de las vecinas son públicos** en esa red; en el
  repositorio van con una descripción aproximada del lugar, sin
  direcciones ni nombres.

## Alternativas descartadas

- **Leer solo las observaciones actuales** (`observations/current`) y
  guardar el acumulado entre pasadas: menos datos por consulta, pero con
  estado entre pasadas y sin las horas para el registro. Las lecturas de
  hoy dan las dos cosas con una sola consulta.
- **Usar ICERDA48 para «plou ara»**: con 34,8 mm el 05-10 frente a 45-55 en
  las demás y sin marcar el milímetro del 08-10, su sí vale pero su umbral
  es más alto que el de las otras; como las otras tres ya cubren el barrio,
  no aporta.
- **Que las vecinas sustituyan al viento de Sant Cugat**: la semana del
  examen fue de calma (Sant Cugat no pasó de 11 km/h de media horaria) y
  dos de ellas están resguardadas (casi siempre 0): no hay base para
  decidirlo. Se registran y se revisará con un episodio de viento.
- **Netatmo** (estación con pluviómetro en el centro de Cerdanyola, a 1,3
  km, API oficial gratuita): queda como opción secundaria.

## Consecuencias

«Plou ara» deja de depender de un solo pluviómetro. Una clave más que
guardar, cifrar (`RESTAURAR.md`) y regenerar cada seis meses. Cuatro
consultas más por pasada a un servicio externo, y cuatro archivos más en el
registro del NAS. Las condiciones de The Weather Company prohíben crear
«obras derivadas» de los datos: usarlos como comprobación interna y
mostrarlos con atribución se entiende como uso personal, pero no está
escrito; si la red lo objetara, se quitarían.

## Evidencia

Examen del 10-10-2026 con el historial por horas de la API
(`history/hourly`, 05-10 a 10-10) contra `estacio-casa.csv` y el viento de
Sant Cugat (portal de datos abiertos, variable 30):

| Lluvia (mm) | 05-10 | 06-10 | 07-10 | 08-10 | 09-10 |
|---|---|---|---|---|---|
| Casa (ICERDA50) | 45,5 | 10,9 | 0 | 1,0 | 0 |
| ICERDA6 | 54,4 | 8,9 | 0 | 0,5 | 0 |
| ICERDA18 | 55,1 | 9,1 | 0 | 1,0 | 0 |
| ICERDA28 | 54,6 | 7,9 | 0,2 | 0,2 | 0 |
| ICERDA48 | 34,8 | 6,3 | 0 | 0 | 0 |

- ICERDA6: coincide hora a hora con casa (ninguna hora con lluvia en una y
  no en la otra en 126 horas); presión al nivel del mar, 0,8 hPa por debajo
  de la de casa; cada 5 minutos sin huecos.
- ICERDA18: lluvia correcta; la mejor en viento (correlación 0,85 con Sant
  Cugat); dejó de subir el 09-10 a las 23 h; su acumulado del día no se
  reinicia a medianoche local (la lluvia se calcula por diferencias, como
  en casa, y así da igual).
- ICERDA28: lluvia correcta, con 0,2 mm sueltos en dos horas secas;
  presión absoluta (11 hPa por debajo, estable).
- ICERDA48: corta en lluvia fuerte y sin el milímetro del 08-10; presión
  absoluta (8 hPa por debajo).
- Las cuatro marcan entre 0,4 y 1,2 °C más que casa y menos humedad.
- Documentación: «APIs for Personal Weather Station Contributors» (The
  Weather Company) y la ficha «PWS Recent History - 1 Day - Rapid
  History»; condiciones en el apartado 18 de los términos de uso de The
  Weather Company (uso personal y no comercial, atribución visible, sin
  obras derivadas).

## Riesgos y limitaciones

- Cinco días de datos, con un episodio fuerte y dos débiles: suficiente
  para la lluvia, no para el viento ni para los sesgos finos. El registro
  del NAS permitirá repetir el examen con más datos.
- Si una vecina deja de publicar (ICERDA18 lo hizo el 09-10), «plou ara»
  sigue con las demás y con casa; no se avisa de cada vecina caída.
- La clave caduca el 10-04-2027: si no se regenera, la página avisará de
  que no puede leer las vecinas y «plou ara» volverá a depender solo de
  casa.
- Las lecturas de hoy de la API llegan con unos 5-10 minutos de retraso
  (en la primera pasada en el NAS, a las 06:42, la última era de las 06:34):
  una lectura de más de 30 minutos no vale, como en casa. Y el registro de
  cada vecina empieza en la segunda hora del día que se lee entera: la
  primera, cortada, no cuenta (como en `ecowitt.hores`).
- La lluvia de cada vecina cada 5 minutos no se guarda: la API la da para
  cualquier día pasado (`history/all`, comprobado el 10-10-2026 hasta el
  01-06-2026). La 3.47.1 la guardaba en el NAS por error, creyendo que solo
  daba la del día; se quitó en la 3.47.2.
- `pluja_arriba.py` (cuándo llega la lluvia que ve el radar) sigue mirando
  solo el pluviómetro de casa: mide cuándo llega a casa, no al barrio.

## Validación

`tests/test_wunderground.py`: las lecturas de la API con la forma de las de
Ecowitt, «plou» con lluvia en los últimos 15 minutos y no con una lectura
vieja, qué vecinas cuentan, sin clave no se lee. `tests/test_registre_casa.py`:
las horas de una vecina con su viento. `tests/test_estacio_casa.py`: llueve
con una vecina que cuenta y no con una que no. `tests/test_aprenentatge.py`:
la vecina fiable confirma las horas secas. `tests/test_bot.py`: el bot lee
`plou_ara`.
