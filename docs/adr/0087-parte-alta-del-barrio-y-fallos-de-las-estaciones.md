# 87. La parte alta del barrio y qué pasa si fallan las estaciones

Fecha: 2026-10-13 · Estado: aceptado

## Contexto

La estación de casa está en el carrer Canaletes, junto a la riera, en la
zona más fría del barrio; ICERDA6 también está junto a la riera. ICERDA18,
ICERDA28 e ICERDA48 están en la parte alta. Juanjo, 13-10-2026: en su calle
los coches tienen hielo casi todos los días en invierno y casi cada año se
llega a −4 °C (en 2024 y 2025), cosa que no pasa en el resto; como las
temperaturas de la web son siempre las de la riera, propuso decir que son de
ahí y cuánto hay que sumar para el resto, «1, 2... grados, dependiendo del
momento y del frío». Pidió «riera» y no «zona baja», que no se entiende, y la
cifra junto a la temperatura de cada tramo. Y que el programa prevea qué
hace si fallan las estaciones, las de abajo, las de arriba o el servicio
entero: «aparte de avisarme para tomar decisiones, la web debe seguir
funcionando».

## Evidencia

- Verano y otoño de 2026 (27-07 a 06-10, cada 10 minutos): la parte alta,
  menos casa, de +0,1 a +0,4 °C de noche y de +1,4 a +1,9 °C de 12 a 18 h
  (`calibracio/part_alta.py`, sin las horas con sol directo sobre el
  termómetro). ICERDA6, de noche, 0,3 °C más fría que casa; ICERDA18, casi
  igual que casa a todas horas; ICERDA28 e ICERDA48, unos 2 °C más cálidas
  por la tarde.
- Invierno de 2025-2026 (mínimas diarias de Weather Underground, 143
  noches): la parte alta, +0,5 °C de mediana y +0,8 °C en las 20 noches con
  casa a 2 °C o menos; fue un invierno suave (mínima de casa, −2,5 °C).
- Enero y febrero de 2024 y de 2025 (mínimas diarias de las vecinas y medias
  de 4 horas o de un día de casa, lo que guarda Ecowitt): la mínima de arriba
  (ICERDA18 o, sin ella, ICERDA28) supera a la de ICERDA6 en **2 °C de
  mediana y hasta 4 °C**, los dos inviernos; la media del día de arriba, a la
  de casa, en 1,1 °C (hasta 3,7). El 14-01-2025: ICERDA6, −5 °C; ICERDA28,
  −4; ICERDA18, −1; la media de 4 horas más baja de casa, −3,9 °C (su mínima
  real, más baja). Lo que Juanjo ve en su calle se confirma; el invierno de
  2025-2026 fue la excepción. Datos en `calibracio/dades/hivern/` (no se
  suben).

## Decisión

Versión 3.78.0.

> **Desde la 3.191.0 (ADR 0123)**, la portada ya no pone la parte alta al lado
> de cada temperatura: un botón arriba elige la riera o la parte alta, y todas
> las temperaturas son de la zona elegida, con la misma diferencia de este ADR
> (`dif_alta`). Lo que sigue describe cómo se calcula; lo que dice de las
> etiquetas de «Ara» y de los tramos ya no vale para la web. El bot y el
> resumen del día siguen igual.

- **Las vecinas, marcadas**: `config.VEINES` lleva `alta` (ICERDA18,
  ICERDA28 e ICERDA48).
- **«Ara»**: debajo de la temperatura, «Vora la riera. A la part alta, 2 °C
  més.» cuando la mediana de las vecinas de arriba leídas en la última media
  hora (al menos dos) se separa un grado o más (`part_alta.ara`). Es una
  medida.
- **Previsión**: cada fila lleva `dif_alta`, la diferencia habitual a esa hora
  solar (en tiempo universal, `prevision.hora_solar`, ADR 0090; desde la 3.82.1) en los
  últimos 30 días del registro (al menos 10 casos por hora, sin las
  horas con sol directo); si no hay bastantes, la de partida
  (`calibracio/part_alta.json`). La recalcula el NAS en cada pasada, así que
  sigue la época del año. Junto a la temperatura del tramo, «(+2 a la part
  alta)» si la máxima (de día) o la mínima (de noche) se separan un grado o
  más.
- **Heladas**: si la mínima de la riera llega a 0 °C y la de la parte alta
  no, «glaçada vora la riera».
- **El resumen del día** («El temps avui» de la web, «Consultes» y el bot,
  hoy y mañana; `bot.text_alta`): «Temperatura d'aquí a mitjanit: entre 16 °C
  i 24 °C (fins a 26 °C a la part alta)», con la máxima de arriba (3.79.0;
  Juanjo: «en el temps avui también hay que ponerlo»).
- **Un grau, arrodonit**: la diferencia sale desde 0,5 °C, que se redondea a
  1 (Juanjo, 13-10-2026: «0.9 yo lo consideraría como 1»); hasta la 3.78.1
  hacía falta 1 °C justo. En el resumen del día, la cifra de arriba es la
  máxima redondeada más la diferencia redondeada, lo mismo que se lee en los
  tramos («18 °C» y «+2»): redondear la suma daba «fins a 21 °C» con 18,2 y
  2,4 (revisor, 20-10-2026; 3.170.2). Así nunca repite la máxima: con 15,6 y
  16,4 °C salía «entre 11 °C y 16 °C (hasta 16 °C en la parte alta)» (Juanjo,
  20-10-2026: «el 2º 16 sobra»), y ahora «hasta 17 °C», como la fila
  («16 °C» y «+1»).
- **Si falla la estación de casa**, «Ara» sale de las vecinas
  (`casa.ara_sense_casa`): la temperatura, la de ICERDA6, para que siga
  siendo la de la riera; sin ella, la de la parte alta menos su diferencia
  habitual a esa hora; la lluvia y la humedad, por consenso (ADR 0085); sin
  presión. La previsión ya se corregía sin la estación (ADR 0017).
- **Si fallan las de arriba**, no se da la diferencia de ahora y la
  previsión usa la habitual. **Si falla Weather Underground entero**, todo
  sale de casa, como antes del ADR 0060. **Si fallan casa y Weather
  Underground**, no hay «Ara», como hasta ahora, y la previsión sigue.
- **Avisos a Juanjo** (`estacions.py`, en cada pasada del NAS, con la cola
  de reintentos de `avis_privat`): una vez cuando falla y otra cuando
  vuelve; la estación de casa a los 30 minutos, la parte alta (menos de dos
  de arriba) y Weather Underground entero a la hora, y cada vecina sola al
  día. Sin Weather Underground no se avisa de la parte alta ni de cada
  vecina. Estado en `/estat/estacions-falla.json`. Solo se vigila lo que
  tiene claves para leerse (3.83.2): la reserva de IONOS no tiene las de
  Ecowitt ni las de Weather Underground, y su prueba diaria de las 04:30
  tomaba eso por un fallo; el 15-10-2026 avisó a Juanjo de que no respondían
  ni la estación de casa ni Weather Underground, cuando en el NAS se leían
  bien.
- La web no dice el nombre de la calle; «D'on surt» explica la riera y la
  parte alta, y «Com es llegeix la previsió» (antes «… la taula», Juanjo:
  «cambia taula por previsió») lo que quiere decir «+2 a la part alta», solo
  si algún tramo lo lleva (3.78.1).
- «Com es llegeix la previsió», como lista: cada término en negrita y lo que
  quiere decir (3.79.1; Juanjo: «usa negritas… esto es muy rancio»). «Prob.»
  dice qué hacer con la cifra, con los mismos umbrales que el cielo de la
  tabla (20 % y 50 %), y un ejemplo de lo que significa un 40 %. El término
  de la parte alta es «+1, +2… a la part alta», y la explicación dice que la
  cifra sale de lo medido y cambia con la época (3.79.2; Juanjo: «no pongas
  +2 como si siempre fuese eso, explícalo»).
- **La etiqueta de la parte alta** (3.80.0; Juanjo, 13-10-2026, viendo
  cada propuesta en local): en color melocotón, el mismo en «Ara» («A la part
  alta, 2 °C més»), en el resumen del día («fins a 26 °C a la part alta») y
  en cada tramo solo la cifra, «+2» (3.80.2; Juanjo: «el texto ponlo solo
  en ahora y el tiempo hoy… en el resto pon solo el número con un +»);
  «semblant a ahir», en gris. Se descartaron el gris, el naranja en negrita (se confunde con los
  avisos naranja), la lavanda y el verde azulado. **Qué quiere decir sale al
  pulsarla**, en una burbuja que se cierra con cualquier clic o toque, al
  desplazarse o con Esc; en los tramos no despliega el tramo. Se probaron y
  descartaron una línea fija encima de la previsión (la etiqueta salía antes
  en «Ara» y el resumen), la explicación bajo la primera etiqueta de la página
  y un recuadro de color («demasiado agresivo»), y un «?» en la etiqueta.
  «Com es llegeix la previsió» la explica, con el término en la misma
  etiqueta; en la 3.80.0 desapareció por error al descartar la línea fija y
  volvió en la 3.80.1. Los textos de «D'on surt» y «Com
  funciona» dicen que la diferencia cambia según la hora del día y la época
  del año.
- En el móvil, la línea de la temperatura del tramo se parte por trozos
  enteros («19–24 °C», «(+2 a la part alta)», «· semblant a ahir»): con el
  añadido no cabía y se salía (Juanjo: «en movil … se desborda»). Medido en
  Chromium, Firefox y WebKit a 320, 360, 375 y 412 px, en catalán y
  castellano.

- **La hora, la solar** (3.82.1, 14-10-2026; Juanjo, tras el ADR 0089:
  «lo haremos mañana»). La tabla se agrupaba por la hora del reloj: el mes
  siguiente a cada cambio de hora mezclaba dos horas de sol distintas, y la
  tarde con el sol más alto quedaba repartida entre dos filas. Ahora se
  agrupa y se consulta por la hora del tiempo universal, también en «Ara»
  sin la estación de casa. La tabla de partida es la misma, con las horas
  pasadas a tiempo universal (los datos eran todos de horario de verano).

## Alternativas descartadas

- **Un conmutador «carrer Canaletes»** o dos temperaturas: más trabajo para
  quien lee por una diferencia que muchas veces no llega a un grado.
- **La temperatura principal, la del barrio** (la de casa más la diferencia
  habitual): sería una estimación en vez de una medida, y la diferencia va y
  viene.
- **«Zona baixa»**: Juanjo, «no se entiende».

## Riesgos y limitaciones

- La diferencia habitual es una mediana de 30 días: suaviza las noches de
  helada fuerte, que son pocas. Pendiente: con el invierno hora a hora,
  comprobar si conviene un ajuste para las noches despejadas y sin viento, y
  solo si la validación lo respalda. Desde el 13-10-2026 un temporizador del NAS
  (`meteo-hivern-wu.timer`, de usuario, en el anfitrión) baja
  cada madrugada (01:30) unas 400 consultas del historial horario de las
  cuatro vecinas, de noviembre a marzo de 2023-2024, 2024-2025 y 2025-2026
  (`calibracio/descarrega_hivern.py`, 1.816 consultas, unos cinco días), para
  no quitar cuota a la web; lo deja en `estat/hivern-wu/` y escribe
  `complet` al acabar.
- Las vecinas dan grados enteros: la diferencia tiene medio grado de margen.
- Con ICERDA6 en lugar de casa, la temperatura de «Ara» va en grados
  enteros.
- El calor (36 °C) y el riesgo por frío siguen calculándose con la
  temperatura de la riera.

## Validación

- `tests/test_part_alta.py`: la diferencia de ahora, la tabla con el registro
  y la de partida, «Ara» con ICERDA6, con la parte alta y sin vecinas, y los
  avisos (a los 30 minutos, una sola vez, al volver, sin repetir cuando falla
  todo Weather Underground; sin claves, nada, y lo que deja de vigilarse se
  olvida sin avisar de que vuelve). `tests/test_web.py`,
  `test_part_alta_al_costat_de_la_temperatura`. 423 pruebas en verde.
- La hora solar (3.82.1): `test_hora_solar_als_dos_costats_del_canvi_dhora`
  (las 15 h de verano y las 14 h de invierno, la misma hora; las dos horas de
  2 a 3 del 25-10, distintas) y `test_el_mes_del_canvi_no_barreja_hores_de_sol`
  (15 días a cada lado del cambio: con la hora del reloj fallaba).
  `calibracio/part_alta.py` vuelto a ejecutar: la misma tabla desplazada dos
  horas, sin otra diferencia.
- En el NAS (13-10-2026, con una copia del registro): diferencia de ahora
  0,9 °C (no sale la línea); en la previsión, de +1,6 a +1,8 °C por la
  tarde. Sin la estación de casa, con las vecinas reales: 18 °C con ICERDA6
  (casa marcaba 18,1) y 18,4 °C con la parte alta.
- `probar-web` en Chromium, Firefox y WebKit, móvil y escritorio, y axe-core
  sin errores en catalán y castellano.

## Cambio del 19-10-2026 (3.159.0): el ajuste de las noches de helada

Juanjo (13-10-2026): las noches de helada había que afinarlas, y «pensé que
de esto te encargabas tú de ir bajando cada día poco a poco los datos». El
NAS bajó del 13 al 18 de octubre los tres últimos inviernos hora a hora de las
vecinas, y el análisis (informe personal del 19-10-2026, «Heladas en la riera
y en la parte alta») mostró que la mediana de 30 días se queda corta en las
noches despejadas y en calma: la parte alta queda unos 2 °C por encima de la
riera y la web daba 1-1,5. Juanjo: «sí, adóptalo y vigílalo este invierno».

- **El ajuste** (`part_alta.correccio_nit`): en las horas de noche (de 17 a
  8 h en tiempo universal), la diferencia de la fila es la mediana de 30 días
  más $`\beta_0 + \beta_1 c + \beta_2 v + \beta_3 c v + \beta_4 \min(T,15)`$,
  con $`c`$ la parte de cielo despejado, $`v`$ la calma
  ($`\max(0, 1 - V/15)`$) y $`T`$ la temperatura previstas en la propia fila.
  Los cinco coeficientes, fijos, en `calibracio/part_alta.json`
  («ajust_nit»). Una noche despejada y en calma suma unos 0,7 °C a 1 °C; una
  nubosa y con viento resta unos 0,3. De día no cambia nada.
- **La evidencia**: 310 noches de tres inviernos (2023-2026), ICERDA6 como
  riera (no hay datos horarios de casa de esos inviernos), la media de
  ICERDA18 e ICERDA28 como parte alta, y la previsión ICON-EU emitida el día
  anterior. Validado por semanas (4.000 remuestreos) y dejando fuera cada
  invierno: en las 32 noches con la riera a 0 °C o menos, el error de la
  mínima de arriba baja de 1,03 a 0,85 °C y gana en el 99 %; «glaçada vora la
  riera», 26 de 32 frente a 23.
- **Riesgos e hipótesis**: el análisis usó ICERDA6 y ICON-EU; la web usa la
  estación de casa, las nubes de cuatro modelos (ADR 0088) y el viento medio
  de AROME. Que la corrección sirva igual es una hipótesis. Por eso, desde
  hoy, cada pasada apunta en `registre/part-alta-nit.csv` lo que dio la web
  con el ajuste y sin él (la última previsión hecha 3 horas antes o más), y
  `part_alta.py nit-resum` lo compara con lo medido (vecinas de arriba menos
  casa), en todas las horas de noche y en las de helada. Se decide con el
  invierno 2026-27, a partir del 01-03-2027: si no acierta más que la
  mediana sola, se retira. Está en el inventario de automatismos del NAS.
- **Textos**: «Com es llegeix la previsió» («+1, +2…»), «D'on surt» y «Com
  funciona» dicen que de noche cuentan las nubes y el viento, y que se vigila
  este invierno.

Validación: `tests/test_part_alta.py` (`AjustNit`: coeficientes, noche
despejada y en calma +0,68 y nubosa con viento −0,28, solo en las horas de
noche, registro y resumen).
