# 125. El acierto de la parte alta

Fecha: 2026-10-24 · Estado: aceptado

## Contexto

La temperatura de la parte alta del barrio es la previsión de la riera (la
que aprende contra la estación de casa, ADR 0012 y 0017) más una diferencia:
la mediana de «parte alta menos riera» de los últimos 30 días por hora solar
y, de noche, un ajuste por nubes y viento con coeficientes fijos (ADR 0087).
Juanjo preguntó si el aprendizaje era separado para la riera y la parte alta
(24-10-2026). No lo es, y nunca se había medido cuánto acierta arriba:
«Fiabilitat» solo compara con la estación de casa. El agente propuso medirlo
antes de decidir si la parte alta debía aprender por separado o si el ajuste
de noche debía recalcularse solo, y Juanjo pidió que lo preparara («sí,
prepara lo del error de la parte alta»).

## Decisión

- El registro guarda en cada hora de cada publicación la diferencia de la
  parte alta que sumaba la web (`mostrat.dif_alta`, `casa.filas_registro`).
- `historial.py` (formato 9) pone en `prev` un cuarto valor, la temperatura
  prevista para arriba, y calcula el acierto de la parte alta
  (`temperatura_alta`: error medio, sesgo y el error de la riera en las mismas
  horas), por día, por ventana y por antelación. En el índice, con la
  seguridad del remuestreo por días de que la diferencia con la riera no es
  casualidad. Fórmulas, en la metodología (`docs/estadistica.md`, 17 bis).
- Para las publicaciones de antes de guardarlo (del 13 al 24 de octubre), la
  diferencia se rehace (`difs_alta`) con el mismo cálculo de la web y solo
  con lo registrado hasta la publicación; de noche, la que apuntó
  `part-alta-nit.csv`, si la hay. Antes del 13-10-2026 la web no daba la
  parte alta: no hay nada que comprobar.
- «Fiabilitat», en el resumen, una cifra más: «Temperatura a la part alta»,
  el error medio, con el de la riera a las mismas horas, si la diferencia es
  casualidad y el sesgo. La de la riera pasa a llamarse «Temperatura a la
  riera», para que se sepa cuál es cuál. Con siete cifras, la última ocupa la
  fila entera si se queda sola, en el ordenador y en el móvil. «Com es
  calcula» explica la comparación y lo que aportan los grados enteros de las
  vecinas.

## Alternativas descartadas

- **Hacer ya que la parte alta aprenda por separado** o recalcular el ajuste
  de noche: primero medir, y decidir con la cifra (perfil de Juanjo: medir
  antes que suponer).
- **Esperar a tener datos guardados** en vez de rehacer los de antes: dos
  semanas más sin cifra, cuando el cálculo de entonces se puede repetir con
  los mismos datos.

## Consecuencias

- La primera cifra, con la previsión hecha 1 h antes (239 horas del 13 al 24
  de octubre): la parte alta se equivoca 0,89 °C de media y la riera, en las
  mismas horas, 0,61 °C; la diferencia no es casualidad (en ningún remuestreo
  la parte alta se equivoca menos). Sesgo de −0,21 °C: suele dar algo menos
  de lo que hace. Con 3, 6 y 12 h, 0,99, 1,05 y 1,05 °C (riera: 0,76, 0,85 y
  0,85).
- Queda por decidir, con esta cifra, si la parte alta aprende por separado o
  si el ajuste de noche se recalcula solo.

## Evidencia

- Registro del NAS copiado el 24-10-2026; `historial.tots` y `historial.index`
  con la antelación de 1 h.

## Riesgos y limitaciones

- Las vecinas dan grados enteros: una parte del error de arriba es redondeo de
  la medida. La cifra de la riera no tiene ese ruido (la estación de casa da
  décimas), así que la comparación favorece algo a la riera.
- La reconstrucción de antes del 24 de octubre repite el cálculo, pero puede no
  coincidir del todo con lo que se publicó si en alguna pasada faltaba una
  vecina o una lectura que llegó después.

## Validación

- `tests/test_historial_grafica.py`: `test_l_encert_de_la_part_alta` (error,
  sesgo, riera en las mismas horas, sin las horas sin medida ni con sol) y
  `test_la_diferencia_de_la_part_alta_es_refa` (antes del 13-10 nada; la
  guardada se respeta; sin registro, la tabla de partida).
- En local, con los datos reales: «Fiabilitat» con la cifra nueva en Chromium,
  Firefox y WebKit, en móvil y ordenador; axe-core sin infracciones.
