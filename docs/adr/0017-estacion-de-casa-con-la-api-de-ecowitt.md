# 17. Estación de casa con la API de Ecowitt

Fecha: 2026-10-06 · Estado: aceptado

**08-10-2026, el pluviómetro mide bien; el fallo era nuestro.** Juanjo pidió
averiguar por qué fallaba su pluviómetro. Comparado con su historial de
Ecowitt (cada 5 minutos), con Montflorit hora a hora (4 al 8 de octubre) y con
Sabadell y Sant Cugat día a día (octubre de 2025 a octubre de 2026), mide
bien, también la lluvia débil: el 5 de octubre, 45,5 mm frente a 52,4 de
Montflorit; el 6, 10,9 frente a 8,6; el 8, 1,0 frente a 0,6; solo se le
escaparon dos horas de 0,2 mm (una marca) y el 6 de agosto (4,5 mm en
Sabadell, 8,8 en Sant Cugat y nada en casa). Lo que fallaba era
`ecowitt.hores`: en cada pasada guardaba la lluvia de la primera hora de la
ventana, cortada, encima de la buena (el 6 de octubre, 1,3 mm de 20 a 21 h en
lugar de 3,5 y 0,2 de 21 a 22 h en lugar de 5,6), y con eso también se
equivocaba la vigilancia del pluviómetro. Desde la 3.27.5 solo cuenta horas
enteras, y `python3 registre.py rehaz-pluja-casa` rehízo el registro con el
historial (con copia del archivo de antes). Que esté en una esquina entre dos
paredes puede hacer que recoja de menos o de más según el viento, pero los
datos no lo muestran. La regla de no fiarse de sus ceros
(`PLUVIOMETRE_CASA_FIABLE_FINS`) se mantiene mientras la vigilancia, ya con
datos buenos, no dé su resultado.


**09-10-2026 (ADR 0058).** Montflorit se retiró: casa es la única estación del barrio. «Plou ara» lo dice solo su pluviómetro; su cero se muestra como «no plou» con la advertencia de la llovizna. La vigilancia del pluviómetro compara con la menor de las lluvias de Sabadell y Sant Cugat en cada hora.

## Contexto

Juanjo tiene una estación Ecowitt en casa, a unos 300-400 m de la de
Montflorit (ADR 0004). Pidió leerla con la API oficial desde el NAS y
«sacarle el máximo provecho, también para aprender en la predicción». Avisó de
dos fallos: el anemómetro no va bien, y el pluviómetro, que iba bien, desde
hace un mes a veces no marca la lluvia débil («si llueve es que realmente está
lloviendo, pero si no llueve no lo podemos asegurar»).

A diferencia de Montflorit, que solo da las últimas 24 horas, Ecowitt guarda el
historial de la estación: un año cada 30 minutos y 90 días cada 5. Con él se
puede aprender desde el primer día en lugar de esperar semanas de registro
propio (ADR 0012).

## Decisión

- **Lectura** (`ecowitt.py`): API v3 de Ecowitt, `real_time` para ahora y
  `history` para las tres últimas horas y para rellenar huecos. Las claves y la
  dirección MAC no están en el repositorio: en el NAS, en
  `home/.config/meteo-local/ecowitt.env`, que el contenedor carga. Sin claves,
  todo sigue como antes, con Montflorit.
- **Qué se usa**: temperatura, humedad, punto de rocío, presión y radiación.
  El viento, nunca. La lluvia, solo cuando marca lluvia
  (`PLUVIOMETRE_CASA_FIABLE_FINS` en `config.py`): hasta el 31-08-2026 cuenta
  también su cero.
- **Temperatura corregida desde hoy** con un año de la estación
  (`calibracio/estacio_casa.py` → `calibracio/temperatura_casa.json`):
  regresión ridge del error del modelo (ADR 0012) con dos señales nuevas, la
  radiación y el día del año, y **el error que tiene el modelo al prever**, que
  se apaga con la antelación (una parte en unas 3 horas y otra en un día). Si
  la estación falla al prever, se usan los pesos ajustados sin esa señal. El
  aprendizaje diario compara cada día esta corrección con la que sale del
  registro propio y cambia solo si el error baja un 5 %.
- **Lluvia**:
  - «Plou ara» y el modo aviso, si llueve en Montflorit **o** en casa.
  - En la página del trayecto, casa aparece entre las estaciones solo cuando
    marca lluvia; su cero no se presenta como «no llueve». En la verificación
    del día, casa sin lluvia no cuenta como dato.
  - El modelo de lluvia del archivo no cambia: las señales de casa no lo
    mejoran (apartado Evidencia). El modelo propio (ADR 0012) aprende con la
    lluvia de Montflorit **y** la de casa cuando marca, y prueba una señal más,
    la sequedad del aire al prever; solo se adopta si mejora.
- **Registro** (`registre.py`): `estacio-casa.csv`, hora a hora, y lo que
  medía casa al prever en cada línea de `casa-AAAA-MM.jsonl`. Cada día, a la
  hora de la verificación, se rellenan con el historial de Ecowitt las horas
  que falten (hasta 89 días), por si el NAS ha estado apagado.
- **Página de casa**: «Ara a casa» con la temperatura, la humedad y la presión
  de casa y cómo cambia en tres horas (estable si cambia menos de 1 hPa;
  rápido desde 3,6 hPa), y la lluvia y el viento de Montflorit. Si falla una
  de las dos, la otra.

- **Comprobación tras limpiar el pluviómetro** (`pluviometre.py`): Juanjo
  lo limpia y pidió que el NAS lo vigile y le avise por Telegram. Mientras
  exista `/estat/vigila-pluviometre.json`, el reloj compara cada hora la
  lluvia de casa con la de Montflorit por episodios. Un episodio débil (de 0,6
  a 4 mm en Montflorit, al menos dos vuelcos del cubo de 0,254 mm) cuenta como
  detectado si casa marca algo en él o en la hora de antes o de después. Con
  tres episodios débiles da resultado («funciona» si los marca todos, «falla»
  si marca la mitad o menos; si no, espera a seis y pide el 80 %); a los 45
  días, avisa con lo que haya. Si casa marca lluvia sin lluvia en Montflorit,
  se toma como el movimiento de la limpieza y se cuenta desde ahí. Avisa una
  vez y borra el archivo. Volver a fiarse del cero del pluviómetro lo decide
  Juanjo con ese resultado.

## Alternativas descartadas

- **Usar Montflorit como verdad de la temperatura**: no tiene historial y
  habría que esperar 14 días; con 14 días no se ven todas las estaciones del
  año. Casa tiene un año entero, y las dos coinciden (Evidencia).
- **Sustituir el modelo de lluvia del archivo por uno ajustado con casa**: da
  más error que el actual (Evidencia). Casa tiene 11 meses de lluvia fiable;
  el archivo, casi tres años y dos estaciones.
- **La presión y su tendencia como señal de lluvia**: no mejora nada en la
  comprobación. Se muestra en la página porque es útil al leerla, no porque
  decida.
- **Comprobar el pluviómetro con una jeringa**, como propone Ecowitt: el
  sensor tiene mal acceso. Lo comprueba la lluvia de verdad, con Montflorit al
  lado.
- **Pedir el historial en cada actualización**: la API corta si se le pregunta
  muy seguido. Cada pasada hace dos consultas; el relleno, una por día que
  falte, con pausa.

## Consecuencias

La temperatura de la tabla deja de ser la de una celda de 1,5 km y pasa a ser
la esperada en casa, desde el primer día y con el año completo detrás. Una
fuente más para saber si llueve ahora. El registro propio aprende con la
temperatura de casa, sin huecos aunque el NAS se apague. Dos consultas a
Ecowitt por pasada (cada 10 o 30 minutos) y una al día para rellenar, sin
coste.

## Evidencia

- **Historial de Ecowitt** (consultas del 06-10-2026): cada 5 minutos los
  últimos 90 días, con un día por consulta; cada 30 minutos el último año, con
  7 días por consulta; más atrás, cada 4 horas o diario. Si se pregunta muy
  seguido responde «The number of interface accesses reached the upper limit»
  u «Operation too frequent».
- **Pluviómetro, octubre de 2025 a junio de 2026**, frente a Sabadell (XF) y
  Sant Cugat (XV): totales mensuales parecidos (por ejemplo, enero: casa 105
  mm, XF 115, XV 120; marzo: 79, 76, 102) y marca lluvia 52 de los 53 días en
  que una de las dos recogió 1 mm o más.
- **Pluviómetro desde agosto**: el 06-08-2026 XF y XV recogieron 4,5 y 8,8 mm
  y casa nada; puede ser un chubasco local o el principio del fallo (hipótesis
  no comprobable sin otra estación cercana). El 06-10-2026 a la 1:00
  Montflorit marcó 0,2 mm y casa 0: el fallo que describió Juanjo. Con lluvia
  fuerte las dos se parecen (05-10-2026, de 6 a 13 h: Montflorit 52,4 mm, casa
  45,5). El último día fiable se fija en el 31-08-2026, el día antes de «hace
  un mes», por prudencia.
- **Temperatura casa frente a Montflorit** (05 y 06-10-2026, 36 horas): casa da
  de media 0,4 °C menos; como mucho, 2,1 °C menos.
- **Corrección de la temperatura** (`calibracio/estacio_casa.py`, 08-10-2025 a
  06-10-2026, 43.099 horas-antelación de 364 días, validación cruzada por
  semanas): el modelo da 0,81 °C más de media. Error medio absoluto:

  | Antelación | Modelo | Corregida | Sin la estación al prever |
  |---|---|---|---|
  | 1 h | 1,44 °C | 0,77 °C | 1,13 °C |
  | 3 h | 1,45 °C | 1,04 °C | 1,13 °C |
  | 6 h | 1,45 °C | 1,14 °C | 1,13 °C |
  | 24 h | 1,54 °C | 1,26 °C | 1,29 °C |
  | Todas | 1,46 °C | 1,03 °C | 1,16 °C |

- **Señales de casa para la lluvia** (mismo script, 08-10-2025 a 31-08-2026,
  297 horas con lluvia en casa): error de Brier del modelo del archivo 0,0236;
  con la lluvia de la última hora y la sequedad del aire al prever, 0,0241.
  Solo mejora la primera hora (0,0227 → 0,0223); a partir de la segunda,
  empeora. Son las cifras con la fórmula del ADR 0021; con la anterior eran
  0,02629 y 0,02657, con la misma conclusión. La presión no mejora en ninguna antelación (análisis exploratorio
  del 06-10-2026).

## Riesgos y limitaciones

- La API de Ecowitt es de un fabricante: puede cambiar o cortar. Si falla, la
  página sigue con Montflorit y la corrección sin la estación.
- La verdad de la temperatura es una estación de aficionado. Coincide con
  Montflorit, pero no hay comprobación con días de sol fuerte en las dos.
- Las «previsiones a corto plazo» del archivo unen las primeras horas de cada
  pasada del modelo; la antelación real puede ser algo mayor que la supuesta.
  El aprendizaje diario, con las antelaciones reales, lo corregirá si hace
  falta.
- Si el pluviómetro empeora y deja de marcar también la lluvia fuerte, la
  lluvia de casa dejaría de servir incluso en positivo. Si se arregla, basta
  mover `PLUVIOMETRE_CASA_FIABLE_FINS`. Ya no es solo la lluvia débil: el
  17-10-2026 de 23 a 24 UTC no marcó nada mientras las tres vecinas fiables
  recogían de 3,8 a 4,8 mm, y su propio historial de Ecowitt da el acumulado
  y la intensidad a cero toda esa noche (el fallo es del aparato, no del
  registro; detalle en el ADR 0070, revisión del 07-11-2026). Un cero así
  no deja la hora seca: con dos vecinas mojadas es lluviosa (desde la
  3.57.0) y, desde la 3.213.0, sus milímetros son la mediana de casa y de
  las vecinas fiables.
- Los acumulados semanal, mensual y anual de la estación no se usan: el anual
  (2.221 mm) no cuadra con la suma de los días.

## Validación

- `tests/test_estacio_casa.py`: horas de la estación, paso por medianoche,
  tendencia de la presión, lluvia solo en positivo (página, modo aviso y
  verificación), error del modelo al prever.
- `tests/test_pluviometre.py`: episodios, limpieza, resultado y borrado tras
  avisar.
- `tests/test_aprenentatge.py`: rasgos nuevos, corrección con y sin la
  estación, modelo propio que recurre al del archivo sin la estación, lluvia
  observada de las dos estaciones, propuesta y aplicación de la corrección
  propia.
- Página probada en Chromium, Firefox y WebKit, escritorio y móvil, temas
  claro y oscuro; axe-core sin infracciones.
