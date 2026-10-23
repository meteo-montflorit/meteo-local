# 122. La previsión de 7 días

Fecha: 2026-10-23 · Estado: aceptado

## Contexto

Juanjo pidió «la previsión de los próximos 6 días, o sea una semana completa
empezando por hoy… del cielo, temperatura y lluvia», debajo de la gráfica, y
la quiso como la de la app del tiempo de su móvil, «algo parecido a esto pero
sin la gráfica»: una columna por día con el cielo, la máxima y la mínima.
Preguntó si mejoraría con el tiempo; se le propuso medir el error, corregir
lo que se repite y apuntar lo publicado para aprender, y respondió «hazlo
todo».

La página solo pedía datos hasta mañana a las 21 h, y sus modelos finos no
llegan a una semana. Comprobado en Open-Meteo el 23-10-2026: AROME llega al
25-10 a las 8 h, ARPEGE al 27-10, ICON-EU al 28-10 de madrugada; ECMWF, GFS y
el ensemble de ECMWF (51 miembros) cubren los siete días.

## Decisión

- **Hoy y mañana, con la previsión de la página** (`casa.js`,
  `diaDeLaPagina`), para que la semana diga lo mismo que la gráfica y los
  tramos (ADR 0101): la máxima y la mínima del día (hoy, con lo ya medido en
  `temperatura_mesurada`; mañana, hasta las 21 h, donde acaban los datos), la
  nubosidad media de 7 a 21 h, la probabilidad más alta de sus horas y la
  lluvia esperada (ADR 0103).
- **Los demás días, de ECMWF a 9 km** (`setmana.py`, `config.MODEL_ECMWF`, el
  que ya usa la página para la lluvia):
  - **Temperatura**: la máxima y la mínima de las 24 horas, corregidas con la
    estación de casa. Para cada día vista, el error medio (medido − previsto)
    de ECMWF a ese mismo día vista en los 30 días anteriores, la máxima y la
    mínima por separado (sesgo móvil). ECMWF da allí las máximas más bajas y
    las mínimas más altas que lo que mide la estación vora la riera. Los
    errores pasados salen de la API de ejecuciones anteriores de Open-Meteo
    (`temperature_2m_previous_dayN`) y lo medido, del registro del NAS. Con
    menos de 15 días medidos, o sin registro (la reserva de IONOS), sin
    corrección (`corregit: false`).
  - **Cielo**: la nubosidad media de 7 a 21 h.
  - **Lluvia**: del ensemble de ECMWF (`ecmwf_ifs025`, 51 miembros), la parte
    de los miembros a los que llueve ese día (`C.UMBRAL_MM`, 0,2 mm, o más en
    el día) y la lluvia esperada, la media de lo que da cada miembro (ADR 0103).
- **El icono del día**, con los de la gráfica y su regla (`celDia`): desde el
  50 % (`PROB_PLUJA`), lluvia (tormenta o nieve según el código); desde el
  20 % (`PROB_POSSIBLE`), posible lluvia; si no, el cielo (`celNuvols`).
- **La forma**: debajo de la gráfica y del radar, «Previsió de 7 dies», siete
  columnas a la vista sin desplazar (día, fecha, icono, máxima en rojo y
  mínima en azul, ADR 0063) y, solo si algún día llega a posible lluvia, una
  fila con su probabilidad. Cada columna lleva una frase para los lectores de
  pantalla. Mide unos 200 px de alto en el móvil.
- **Consultas**: ECMWF sale cada seis horas; la semana se pide a Open-Meteo
  como mucho cada hora (`setmana-cache.json` en el registro) y la corrección,
  una vez al día. Son unas 50 consultas más al día, frente a unas 2.900 y un
  límite de 10.000 (ADR 0020 y 0101).
- **Se apunta para aprender**: cada vez que se calcula, la semana publicada va
  a `registre/setmana-AAAA-MM.jsonl`, para comprobar la probabilidad de
  lluvia con la que cae (el ensemble no tiene archivo de ejecuciones
  anteriores con el que comprobarla ahora).
- Si falla Open-Meteo, la semana de la pasada anterior; la página quita los
  días ya pasados.
- Se explica en «D'on surt» y en «Com funciona», con el error medido.

## Alternativas descartadas

- **ECMWF tal cual**: se equivoca más (abajo), siempre hacia el mismo lado.
- **ECMWF a 0,25°**: corregido, casi igual que el de 9 km, y sin corregir,
  bastante peor (máxima a un día vista: 2,20 °C frente a 1,50). Se queda el de
  9 km, el que ya usa la página.
- **Una regresión fija** (medido = a + b·previsto): mejor en la mínima a 4–7
  días vista, peor en la máxima. Una sola regla para todo (ADR 0105), y el
  sesgo móvil se adapta solo al cambio de estación.
- **Ventanas de 14 o de 60 días**: la de 30 se equivoca menos o igual en casi
  todos los casos.
- **La previsión municipal de AEMET o Meteocat**: es para todo Cerdanyola, sin
  la corrección de la riera, y Meteocat tiene un cupo de consultas que ya se
  reparte entre avisos y previsiones (ADR 0110).
- **El ensemble también para hoy y mañana**: contradiría la gráfica y los
  tramos, que salen de la previsión propia.
- **Columnas que se desplazan de lado, o una lista con barras**: la primera
  esconde días; la segunda ocupa unos 280 px. Juanjo eligió las columnas.

## Consecuencias

- La portada crece unos 200 px por debajo de la gráfica; lo que ya cabía en la
  pantalla del móvil no cambia.
- Del tercer día en adelante el número sale de otro modelo que la gráfica:
  entre mañana y pasado mañana puede haber un salto que no es del tiempo.
- La probabilidad de lluvia de la semana no está calibrada como la de las
  horas (ADR 0012): se dice en «D'on surt».

## Evidencia

`python3 calibracio/setmana.py --hores` (ECMWF 9 km, la estación con una
lectura por hora, como el registro del NAS; del 08-10-2025 al 05-10-2026,
281–325 días por antelación; semanas como bloques). Error medio absoluto en
°C y, entre paréntesis, la seguridad de la mejora (`remostreig.seguretat`;
gana desde 0,95):

| Días vista | Columna | Máxima: ECMWF → corregida | Mínima: ECMWF → corregida |
|---|---|---|---|
| 1 | mañana (sale de la página) | 1,44 → 1,16 (1,00) | 1,50 → 1,32 (0,99) |
| 2 | 3.º día | 1,54 → 1,29 (0,99) | 1,56 → 1,38 (0,98) |
| 3 | 4.º día | 1,60 → 1,37 (0,99) | 1,62 → 1,45 (0,97) |
| 4 | 5.º día | 1,68 → 1,48 (0,99) | 1,71 → 1,54 (0,95) |
| 5 | 6.º día | 1,74 → 1,58 (0,98) | 1,86 → 1,69 (0,94) |
| 6 | 7.º día | 1,78 → 1,63 (0,98) | 2,45 → 2,12 (0,99) |

La mejora es segura en todos los casos salvo la mínima a 5 días vista (0,94):
también ahí el error baja, y se aplica la misma regla (una sola para todo el
programa). El sesgo medio de ECMWF en el año: la máxima, 0,4–0,8 °C más baja
que la medida; la mínima, 0,7–1,2 °C más alta. Con las lecturas a la media
hora (sin `--hores`) sale lo mismo con centésimas de diferencia. Con el
registro del 04 al 22-10-2026, la corrección del 23-10 va de −0,5 a +0,7 °C.

## Riesgos y limitaciones

- **La probabilidad de lluvia es la del ensemble, sin calibrar.** Hipótesis
  pendiente: comprobar con `setmana-AAAA-MM.jsonl` y la lluvia medida, por
  franjas, como «Com encerta» (ADR 0110), cuando haya unos dos meses (hacia el
  23-12-2026), y calibrarla si no cuadra.
- Las horas con sol directo sobre el termómetro (ADR 0081) llevan la
  temperatura esperada en el registro; en el archivo de la validación, no. No
  suelen ser las de la máxima.
- La antelación se toma en días: lo que la página publica a las 23 h para
  pasado mañana está a algo menos de dos días vista.
- La semana de la reserva de IONOS va sin corregir.

## Validación

- `tests/test_setmana.py`: la corrección (el error medio de cada antelación,
  sin corregir con pocos días), los días incompletos fuera, la lluvia del
  ensemble y la semana sin ensemble.
- `tests/test_web.py` (`test_la_setmana_avui_i_dema_de_la_pagina_i_la_resta_d_ecmwf`):
  hoy y mañana de la página (hoy, con la mínima ya medida), la resta de los
  datos de la semana, los iconos y sin bloque sin datos.
- Con datos reales del 23-10-2026 en un servidor local: Chromium, Firefox y
  WebKit, a 360, 393 y 1280 px, en tema claro y oscuro, catalán y castellano,
  sin desbordamiento; axe-core sin incidencias.
