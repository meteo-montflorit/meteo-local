# 114. La humedad y el índice UV en la gráfica, con el rocío corregido

Fecha: 2026-10-21 · Estado: aceptado

## Contexto

La gráfica de la previsión (ADR 0096) tenía tres opciones que se recuerdan en
el dispositivo: el viento, la parte baja y la parte alta. Juanjo preguntó si
se podían añadir más (21-10-2026: «en la app de meteo se pueden añadir más
opciones?»). El agente le propuso, por coste, el índice UV y las nubes (ya
estaban en cada hora), la humedad (se descargaba y no se publicaba), la
sensación térmica, la calidad del aire y la dirección del viento, y
recomendó empezar por el UV y la humedad. Juanjo: «haz el UV y la humedad y
enseñamelos».

Al probarlo con los datos del momento salió un problema: a las 5:30 el barrio
medía un 93 % y la gráfica, con la humedad de AROME pasada a la temperatura
de la página, daba un 82 % para esa hora. Las dos cosas se contradecían en la
misma pantalla (ADR 0101). El agente le propuso corregirla como la
temperatura, con un método medido, o acercar las primeras horas a lo medido
con un ritmo elegido a ojo, y recomendó lo primero. Juanjo eligió la
corrección («para la humedad lo 1») y preguntó con qué estaciones aprendería;
el agente midió que el rocío es el mismo en todo el barrio y propuso el
barrio; Juanjo: «sí, hazlo así». Después pidió ver los resultados en
«Fiabilitat» («añade estos datos a la pagina de fiabilitat»).

## Decisión

- **Dos interruptores nuevos, «Humitat» y «UV»**, detrás de los tres de
  siempre, apagados por defecto como el viento, y recordados en el
  dispositivo con los demás (`meteo.grafica.3`, sin cambiar de clave: las
  claves nuevas faltan y valen «no»). Cada uno solo sale si los datos lo
  traen.
- **La humedad, una línea violeta en su franja, debajo del viento.** Arriba,
  el 100 %; abajo, la decena por debajo de la mínima, con su cifra: de 0 a
  100 % un día de 55 a 95 % parecía plano. La ficha de cada hora la dice.
- **El UV, una casilla por hora de sol con la cifra y el color de la OMS**,
  los mismos del «Sol» de «Consultes» (la escala `UV` pasa de `consultes.js`
  a `grafica.js` para que la usen los dos). Ni de noche ni con UV 0. Es el
  índice de Open-Meteo que cuenta con las nubes previstas (tiene otro «con
  cielo despejado», que no se usa): el 22-10-2026, con el cielo cubierto,
  daba 3,5 a las 14 h en lugar de 4,1. Con la franja a la vista, la ficha
  dice el UV de todas las horas de sol, no solo desde 3.
- **La humedad sale del punto de rocío corregido y de la temperatura de la
  página** (`casa.humitat_hora`, `aprenentatge.rosada`). El rocío solo
  depende del agua del aire; la humedad, también de la temperatura, que está
  corregida (ADR 0017). Método y cifras en `docs/estadistica.md`, apartado
  «3 bis».
- **La corrección del rocío, como la de la temperatura**: regresión ridge del
  error del modelo con sus señales, el propio rocío y el error que tenía al
  prever (`error_rosada_ara`, que `casa.al_prever` guarda desde esta versión
  en el registro).
- **La verdad es el rocío del barrio**, la mediana de casa y las vecinas, el
  mismo del recuadro «Ara». El primer modelo se ajusta con el año de casa
  (`calibracio/humitat_casa.py`), porque las vecinas solo se registran desde
  octubre y su rocío es el mismo; el NAS ajusta cada día otro con el barrio
  (`valida_humitat`) y lo usa si gana con la regla de siempre (ADR 0105 y
  0106), con 14 días como mínimo. Su día a día va a
  `historial-humitat.csv`, aparte del `historial.csv` de siempre, que ya
  tenía sus columnas.
- **«Fiabilitat» lo enseña**: una ficha «Humitat» con el resultado del año
  en barras (corregida y sin corregir, en puntos de humedad), lo que lleva el
  aprendizaje del barrio, su gráfica día a día y los cambios de método en la
  lista de lo que la web ha cambiado sola.

## Alternativas descartadas

- **La humedad de AROME tal cual**: no cuadra con la temperatura corregida ni
  con lo medido (7,3 puntos de error medio en un año).
- **Acercar las primeras horas a lo medido**, con un ritmo fijo: quitaba la
  contradicción de la hora en curso, pero el ritmo se habría elegido a ojo y
  el resto de horas seguía igual de seco.
- **Aprender solo con la estación de casa**: su rocío y el del barrio son el
  mismo, pero el recuadro «Ara» usa el del barrio, y con la mediana un fallo
  de casa no cambia nada.
- **El resto de opciones propuestas** (sensación térmica, calidad del aire,
  dirección del viento) quedan para cuando Juanjo las pida. Las nubes, con
  la presión, llegaron en la 3.176.0 (ADR 0116).

## Consecuencias

- La gráfica crece en altura con cada franja que se enciende; en el móvil,
  los cinco interruptores ocupan tres filas.
- La humedad de la primera hora cuadra con la medida: a las 5:30 del
  21-10-2026, 91 % en la gráfica con 92 % medido (antes, 82 %).
- Hasta tener 14 días con el error al prever, el NAS no tiene candidato del
  barrio y se usa el del año de casa.

## Evidencia

Del rocío entre estaciones (registro del NAS, del 09 al 21-10-2026, 280
horas): respecto a casa, ICERDA6 +0,22 °C, ICERDA18 −0,06, ICERDA28 −0,19,
ICERDA48 −0,11; la mediana de las vecinas, −0,07 °C (desviación 0,55).

Del primer modelo (`calibracio/humitat_casa.json`): 43.099 horas de 363 días
(08-10-2025 a 06-10-2026), 356 evaluados con avance temporal. El rocío de
AROME queda 1,28 °C por debajo de media; su error medio baja de 1,82 a
0,98 °C, y el de la humedad, de 7,3 a 4,4 puntos (de 7,2 a 3,7 en la hora
siguiente, de 7,7 a 5,1 a 24 horas). Gana en el 100 % de los remuestreos
por días.

Validación: pruebas (`tests/test_humitat_hora.py` y la del aprendizaje en
`test_historial_grafica.py`), Ruff y ESLint; la gráfica en Chromium y Firefox,
en escritorio y a 390 px, con tema claro y oscuro, y «Fiabilitat» en los dos
anchos, sin errores ni desplazamiento horizontal.

## Corrección (23-10-2026, 3.192.3)

«Fiabilitat» decía de la humedad «calen 14 dies; en porta 0» con casos de
tres días (del 21 al 23-10). `valida_humitat` no devolvía nada hasta poder
evaluar algún día, y para eso el avance temporal pide 7 días de
entrenamiento (`remostreig.MIN_DIES_ENTRENAMENT`). Ahora, mientras tanto,
devuelve los días y las muestras sin error ni pesos (`aprenentatge.sense_avaluar`),
que no pueden ganar a la corrección vigente. `valida_temperatura` tenía el
mismo fallo (no se veía porque ya pasó esa fase) y se corrige igual. Juanjo:
«¿por qué la humedad no tiene ningún día?».

