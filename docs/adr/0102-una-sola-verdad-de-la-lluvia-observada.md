# 102. Una sola verdad de la lluvia observada

Fecha: 2026-10-18 · Estado: aceptado

## Contexto

La evaluación de los métodos de predicción del 18-10-2026 (informe de
Codex, `Informes/meteo-local/2026-10-18-evaluacion-metodos-prediccion.md`)
señaló que la lluvia «de verdad» no era la misma en todas partes. El
aprendizaje por horas (ADR 0070) usa el consenso del barrio: llueve si lo
marca la estación de casa o dos vecinas que cuentan, y una hora solo es seca
si casa y las vecinas que confirman marcan cero; si no, no se sabe. En
cambio, la elección del radar (`radar_fonts.py`, ADR 0026), el registro de
la llegada de la lluvia (`pluja_arriba.py`, ADR 0022) y el final de la lluvia
(`fi_pluja.py`, ADR 0049) miraban solo el pluviómetro de casa, aunque desde
el principio se sabe que no recoge la lluvia débil (ADR 0017). Sus ceros
podían dar por fallido un radar que acertaba, apuntar «avís sense pluja»
cuando llovía en el barrio o dar por acabado un episodio antes de tiempo.
Juanjo, al ver el informe, pidió hacer esto primero («Haz la 1»).

## Decisión

Una sola regla para decir si llueve en Montflorit, la de
`aprenentatge.pluja_observada`, aplicada a tres escalas de tiempo:

- **La hora**, como hasta ahora (ADR 0070), para el aprendizaje y el
  historial (`historial.py`).
- **Los 5 minutos**, para el final de la lluvia: `fi_pluja.pluja_5min`
  junta la lluvia de casa (`estacio-casa-5min.csv`) con la de las vecinas,
  que desde esta versión se apunta también cada 5 minutos
  (`registre.apunta_veines_5min`, `veines-5min.csv`, una columna por
  estación, con las mismas lecturas de Weather Underground que ya se leen
  en cada pasada). Un tramo cuenta como lluvia desde 0,1 mm (la resolución
  del pluviómetro) y, si no se sabe, vale None: ni corta ni alarga un
  episodio.
- **Ahora**, para comprobar el radar: `aprenentatge.plou_ara_barri` aplica
  la regla a la lluvia de los últimos 15 minutos de casa y de las vecinas,
  y `casa.py` lo publica en `pluja_ara.mesurada` (sí, no o no se sabe).
  `radar_fonts.py` apunta eso en cada pasada en lugar del `plou` de casa.
  Un cero dudoso no cuenta: con «plugim segons el radar» (los dos radares
  ven ecos débiles sobre el barrio y ninguna estación mide nada, ADR 0019)
  la pasada queda como desconocida, porque el pluviómetro no recoge la
  llovizna.

La llegada de la lluvia (`pluja_arriba.plou`) usa el estado único de la web
(`pluja_ara.estat == "plou"`, ADR 0101: casa o una vecina que cuenta), que
es lo que el vecino ve como «Plou»: el aviso no puede contradecir a la
portada, y el registro del episodio apunta cuándo empezó a llover según
ese mismo estado. Es la única diferencia con la regla de las dos vecinas, y
es deliberada: para avisar basta una estación; para aprender hacen falta dos.

Con una salida de antes de esta versión (sin `pluja_ara`), las tres piezas
siguen leyendo el pluviómetro de casa, para que los registros viejos y la
reserva de IONOS no fallen.

## Alternativas descartadas

- **Corregir el pluviómetro de casa** (sumar lo que ven las vecinas): se
  perdería la medida real de casa y el registro dejaría de decir qué midió
  cada estación.
- **Usar el radar como verdad** para el final de la lluvia: es lo que se
  quiere evaluar.
- **Tratar el cero de casa como seco cuando las vecinas no se pueden leer**:
  es el cero dudoso que el informe pedía apartar; ahora queda como
  desconocido, y la comparación tiene menos casos pero más limpios.

## Consecuencias

- La comparación de radares, el final de la lluvia y los episodios de
  llegada cambian de referencia desde la 3.142.0: las cifras anteriores
  (Brier 0,0259 frente a 0,0279; 3 de 11 finales a ±15 minutos) se hicieron
  contra casa sola y no son comparables con las nuevas.
- `veines-5min.csv` crece unas 288 filas al día. Las lecturas de la última
  hora de ayer no se rellenan a 5 minutos (sí por horas, ADR 0060).
- Quedan pendientes del mismo informe la cantidad central de milímetros y la
  comparación de cada candidato con el modelo en servicio.

## Validación

- `tests/test_aprenentatge.py` (`PlouAra`: casa o dos vecinas, una sola, sin
  confirmación, plugim; el umbral de 0,1 mm para los 5 minutos),
  `tests/test_fi_pluja.py` (`test_pluja_del_barri_cada_5_minuts`),
  `tests/test_radar_fonts.py` (`test_que_plou`), `tests/test_pluja_arriba.py`
  (`test_plou_segons_la_web_no_nomes_casa`) y `tests/test_registre_casa.py`
  (`VeinesCincMinuts`); 567 pruebas en verde.
- Con el registro del NAS copiado el 18-10-2026, `fi_pluja.pluja_5min` da los
  mismos episodios que antes mientras no haya `veines-5min.csv` (los ceros de
  casa pasan a desconocidos y los tramos con lluvia de casa se conservan).

## Cambio del 07-11-2026 (3.213.0): la mediana y las horas sin casa

La regla única cambia en dos cosas, en las tres escalas a la vez (detalle y
cifras en el ADR 0070, revisión del 07-11-2026): cuando llueve, los
milímetros son la mediana de casa y de las vecinas que cuentan, de las que
tengan dato (con el umbral como mínimo, para que un tramo lluvioso no pase a
seco); y sin dato de casa deciden las vecinas, en lugar de quedar siempre
como desconocido: seco si las que confirman marcan cero. Para «ahora»,
`plou_ara_barri` sin la lectura de casa da «no llueve» si las vecinas que
confirman están a cero (antes, «no se sabe»), como el recuadro «Ara» cuando
falla la estación de casa (ADR 0087). Lo que se descartó arriba (tratar como
seco el cero de casa cuando no se pueden leer las vecinas) sigue igual: sin
casa ni vecinas, no se sabe. En los 5 minutos del registro, 22 tramos pasan
de desconocidos a secos y los episodios no cambian.
