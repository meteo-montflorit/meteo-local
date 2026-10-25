# 79. Retrasos de la S2 con la puntualidad de FGC

Fecha: 2026-10-12 · Estado: aceptado

## Contexto

Juanjo preguntó si se podía sacar información de GeoTren
(`geotren.fgc.cat`), el mapa de trenes de FGC. Su archivo de trenes
(`/tracker/trens.geojson`) es el mismo contenido que el conjunto
«posicionament-dels-trens» del portal de datos abiertos de FGC, que la web ya
lee (mismos identificadores y campos), y el portal tiene licencia CC BY 4.0 y
está documentado. Lo que no se usaba de esos datos:

- el campo `en_hora`, si cada tren va puntual;
- la ocupación, que no cambia la decisión de salir.

Juanjo: «hazlo así», marcar la S2 «amb retard» si la mayoría de los trenes
vistos en la última media hora van tarde, para que un solo tren no lo decida.

## Decisión

Versión 3.70.0.

- **«Amb retard»** (`retard`), en las líneas de FGC (la S2). Se marca si, de
  los trenes vistos a `TRENS_RADI_KM` o menos de la estación en los últimos
  `RETARD_MIN` (30) minutos, van tarde al menos `RETARD_TRENS_MIN` (2) y más
  que los puntuales. Cada tren cuenta una vez, con lo último que se sabe de
  él (`trens.puntualitat` y `amb_retard`). El registro va en el estado de los
  trenes del NAS (`trens-posicions.json`, clave `puntualitat`).
- **Solo sustituye «Circula»**: si la línea ya está «amb incidències», «per
  carretera» o «sense trens», manda eso.
- **Dónde se ve**:
  - «Consultes › Trens» y la ficha del transporte público de «Si surts»:
    «Amb retard», en ámbar, y «N trens han passat amb retard a la darrera mitja
    hora»;
  - el resumen del día y el bot: «S2 amb retard» («con retraso»).
  - «Com es decideix» explica la regla.
- **Renfe no da esta información**: la R4, la R7 y la R8 siguen como antes.
- **La ocupación no se usa.**

## Alternativas descartadas

- **Leer GeoTren**: los mismos datos, sin licencia declarada ni documentación.
- **Marcar el retraso con un solo tren**: un tren tarde de vez en cuando no es
  un problema de la línea.

## Evidencia

- 12-10-2026, 10:36: los 6 trenes de la S2 del portal, con `en_hora` «True»;
  3 de ellos cerca de la estación, apuntados en el registro.
- El primer tren de GeoTren y el del portal: el mismo `id`
  (`6c4bdae602747644e61684|…`), con los mismos campos.

## Riesgos y limitaciones

- `en_hora` lo calcula FGC; no se sabe por cuántos minutos.
- Con pocos trenes (de noche), puede no llegar nunca a dos tarde en media
  hora: entonces no se marca.

## Validación

- 401 pruebas en verde, con `test_retard_de_la_s2` (un tren no basta; 2 tarde
  y 1 puntual, sí; 2 tarde y 3 puntuales, no; los de hace más de media hora y
  los de lejos de la estación no cuentan).

## Cambio del 19-10-2026 (3.151.0): Rodalies, cuando se recupera

De Renfe no hay puntualidad, pero el 19-10 la R4 salía «amb incidències»
con un único aviso: «Un cop resolta la incidència… els trens recuperen
progressivament els seus horaris habituals de pas» (lo señaló el revisor,
ADR 0101). Los trenes aún van tarde, pero no hay incidencia abierta: si todos
los avisos que quedan coinciden con `trens.RECUPERA` («resolta la
incidència», «recuperen progressivament» y sus formas en castellano), la línea
sale «amb retard», sin número de trenes. Con otro aviso abierto, sigue «amb
incidències». Explicado en «Com es decideix» de «Si surts».

## Cambio del 25-10-2026 (3.202.0): el archivo de avisos de FGC trae avisos de PHP delante

El archivo GTFS-RT de avisos de FGC (`alerts-gtfs_realtime`) llega con avisos
de PHP del servidor delante del binario («<br />\n<b>Warning</b>: Undefined
property…»). Al leerlo fallaba («tipus de camp desconegut: 4») y, como sin
avisos la línea no se puede decidir, la S2 salía «sense dades» en la web y en
el bot; en el NAS se vio por última vez el 23-10-2026 a las 19:15. Desde la
3.202.0, `trens.sense_avisos_php` los quita antes de leerlo (`tests/test_trens.py`).
