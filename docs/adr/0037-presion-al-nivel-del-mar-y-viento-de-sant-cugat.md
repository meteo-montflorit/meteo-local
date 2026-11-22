# 37. Presión al nivel del mar y viento de Sant Cugat

Fecha: 2026-10-07 · Estado: aceptado

**22-11-2026 (ADR 0130).** El viento medio de «Ara» es el de la estación de Cerdanyola Centre de MeteoCerdanyola; Sant Cugat da la racha y, si Centre no responde, también la media.


**10-10-2026 (ADR 0064).** Se calcula también el viento estimado con las estaciones vecinas, en prueba; la página sigue con el de Sant Cugat hasta que Juanjo decida.

**09-10-2026 (ADR 0058).** Montflorit se retiró; el viento de ahora sigue siendo el de Sant Cugat, ahora porque el anemómetro de la estación de casa no funciona bien (ADR 0017).

## Contexto

La revisión del 07-10-2026 de la web y de los datos publicados encontró dos
medidas de «ahora» que no eran verdad:

- **Presión.** La tarjeta mostraba «1002 hPa» mientras la estación de
  Montflorit daba 1008, Open-Meteo 1010,2 al nivel del mar y el METAR del
  aeropuerto de Sabadell (a 5 km) un QNH de 1011. El valor de la estación
  particular coincidía exactamente con la presión en superficie de Open-Meteo
  a 70 m (1002,1): la «relativa» que entrega la API de Ecowitt no está
  calibrada y sale igual que la absoluta, la medida a la altura de la
  estación. Lo que publican las demás estaciones, los mapas y los partes es la
  presión reducida al nivel del mar.
- **Viento.** La tarjeta mostraba «Vent 0 km/h» con 13 km/h de media y rachas
  de 32 según Open-Meteo. El anemómetro de la estación de Montflorit
  (meteocerdanyola.com) marcó 0 en 1.072 de los 1.094 minutos anteriores: no
  da un viento real. No afecta a los avisos de peligro, que usan la racha
  prevista (ADR 0018).

## Decisión

- **La presión se reduce al nivel del mar** en `ecowitt.py` (`pressio_mar`)
  a partir del valor absoluto de la API, con la fórmula hipsométrica, la
  temperatura del aire de la misma lectura y la altitud `ALTITUD_CASA_M` de
  `config.py` (70 m, del modelo digital del terreno de Open-Meteo para las
  coordenadas redondeadas). Se aplica a la lectura de ahora y al historial, así
  que la tendencia de tres horas sale de valores homogéneos. La web, el bot y
  el registro siguen usando el mismo campo `pressio`.
- **El viento de ahora es el de la estación de Meteocat de Sant Cugat (CAR)**
  (`VENT_ESTACIO` en `config.py`), por medias horas, leído de la misma tabla de
  meteo.cat que ya se consulta para la lluvia y la riera
  (`prevision.vent_meteocat`). El dato va en `vent` de `casa.json` y de
  `montflorit.json` (estación, media, racha y hasta cuándo vale) y la tarjeta
  lo muestra con la estación y la hora. El viento de Montflorit deja de
  publicarse (`ara.vent` queda a `null`).
- La página lo explica en «D'on surt» y en «Fonts i crèdits».

## Alternativas descartadas

- **Calibrar la presión relativa en la consola de Ecowitt.** Dependería de
  un ajuste manual fuera del repositorio que nadie vería si se perdiera; la
  reducción en código es reproducible y queda documentada.
- **Ocultar el viento sin sustituirlo.** El viento de ahora es útil para quien
  sale (ADR 0029); la estación oficial más cercana lo da con media hora de
  retraso como mucho.
- **Viento de Open-Meteo.** Es un modelo, no una medida: para «ahora» se
  prefiere la estación.

## Consecuencias

- La presión publicada sube unos 8 hPa respecto a lo mostrado hasta ahora y
  coincide con las demás fuentes. Las filas anteriores de
  `estat/registre/estacio-casa.csv` del NAS guardan la presión a la altura de
  la estación; al desplegar se convierten una vez con la misma fórmula y la
  temperatura de cada fila.
- La tabla de meteo.cat se lee una vez por pasada y se reutiliza dos minutos
  (`get_recent`), también para la riera.
- Si la estación de Sant Cugat no da viento (o la tabla falla), la tarjeta no
  muestra viento y `errors` lo apunta.

## Evidencia

- Lecturas del 07-10-2026 a las 18:30: estación particular 1002,1 hPa y 23 °C;
  Open-Meteo `surface_pressure` 1002,1 y `pressure_msl` 1010,2 a 70 m de
  elevación; METAR LELL 071730Z Q1011; estación de Montflorit 1008,1.
- Viento: serie minuto a minuto de meteocerdanyola.com del 06-10-2026 18:34 al
  07-10-2026 18:33, columna `VEL`: 22 valores distintos de 0 de 1.094.
- `tests/test_estacio_casa.py` (reducción: 1002,1 hPa a 23 °C y 70 m dan
  1010,2) y `tests/test_vent.py` (lectura de la tabla de meteo.cat).

## Riesgos y limitaciones

- La altitud es la de las coordenadas redondeadas, no la exacta de la
  estación: un error de 10 m son unos 1,2 hPa.
- Sant Cugat está a unos 4 km y a otra altura: su viento orienta, no es el del
  barrio.

## Validación

Pruebas sin red del repositorio y comprobación en la web publicada de que la
presión coincide con la de Montflorit y el QNH de Sabadell a menos de 2 hPa.
