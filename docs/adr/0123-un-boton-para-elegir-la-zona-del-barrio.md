# 123. Un botón para elegir la zona del barrio

Fecha: 2026-10-23 · Estado: aceptado

## Contexto

Desde el ADR 0087, las temperaturas de la portada son las de la riera, la
zona más fría del barrio, y la parte alta salía al lado: «Part alta: +1 °C»
en «Ara», una etiqueta «+2» en cada tramo, «(part alta: X °C)» en cada hora
de la gráfica y su leyenda. En la gráfica, «Opcions» dejaba ver una zona u
otra (3.173.2), con la parte alta en otro color y con trazo discontinuo.

Juanjo (23-10-2026): «ahora hay muchos sitios que pone parte alta / parte
baja… eso crea mucho ruido por toda la aplicación. ¿Por qué no hacemos un
selector de parte baja (riera) y parte alta de forma que marque las
temperaturas en base a lo elegido? La tarjeta que dice si hará fresco, etc.
deberá amoldarse a la zona». Lo quiso en la botonera de arriba, «con el
dibujo de una riera y de una montaña», con su descripción al pasar el ratón
o al mantenerlo pulsado, sin añadir líneas, y la gráfica «todo igual sin
distinción, ya que el botón de arriba es el que marca la distinción».

## Decisión

Versión 3.191.0.

- **Un botón doble en la botonera de arriba** (`casa.botoZona`): las olas, la
  riera, y la montaña, la parte alta, los dibujos que ya tenía la gráfica. La
  elegida, del color de la pestaña activa. Cada mitad, con su descripción en
  el `title` (al pasar el ratón o con una pulsación larga, como el resto de
  botones). En pantallas de menos de 23,4 rem (unos 375 px), donde no cabe
  junto al título, solo la elegida, del tamaño de los demás botones, y tocarla
  pasa a la otra (medido: a 360 px quedaban 72 px y hacen falta unos 80).
- **Por defecto, la riera**: la de la estación. La elección se recuerda en el
  dispositivo (`meteo.zona`); la primera vez, la que cada uno tenía en
  «Opcions» de la gráfica, para que nadie tenga que volver a elegirla.
- **La dirección lleva `?zona=alta`** cuando se mira la parte alta, para que
  compartir la página la enseñe igual; quien la abre la ve así sin que se
  guarde como suya.
- **Todo lo que dice una temperatura en la portada sale de la zona elegida**
  (`grafica.tempZona`, la riera más `dif_alta`, ADR 0087):
  - «Ara»: en la parte alta, la que miden ahora las estaciones de arriba
    (`part_alta.ara`), sin decimal: las estaciones de arriba (Weather
    Underground) la dan en grados enteros y el decimal siempre salía «,0»
    (Juanjo: «sin decimal»). Si no hay, la de la riera.
  - La frase de arriba («fresc», «agradable»…), los tramos, la tabla por
    horas, la gráfica (una sola curva y una sola leyenda, «Temperatura»,
    dibujada igual en las dos zonas) y su burbuja.
  - La comparación con ayer, en la parte alta, con lo que midieron las
    estaciones de arriba (`part_alta.mesurada`, en
    `temperatura_mesurada_alta`, la mediana de cada hora).
  - La previsión de 7 días: hoy y mañana con la diferencia de cada hora; los
    demás días, con `max_alta` y `min_alta` de `setmana.py`, que suma a cada
    hora de ECMWF la diferencia de la parte alta (con el ajuste de las noches
    por nubes y viento) antes de la máxima y la mínima, y aplica la misma
    corrección de la estación.
- **Fuera**: las etiquetas «+1, +2…», «Part alta: +1 °C», la opción de zona
  de «Opcions» y el color y el trazo propios de la parte alta en la gráfica.
- **La helada de la riera se avisa en las dos zonas**: mirando la parte alta,
  si solo hiela abajo, «glaçada vora la riera», porque se pasa por allí para
  entrar y salir del barrio.
- **No cambian**: el bot, el canal y los avisos en el navegador, que no saben
  dónde vive cada uno (siguen con la riera y «fins a X °C a la part alta»);
  «Consultes», que muestra sus textos; «Si surts»; los avisos de temperatura.

## Alternativas descartadas

- **Seguir con las dos a la vista**: es el ruido que motivó el cambio.
- **Un interruptor en «Opcions» de la gráfica para toda la página**: escondido;
  Juanjo lo quiso arriba, a la vista.
- **Una línea con el selector encima de «Ara»**: Juanjo: «no añadas más
  líneas».
- **Un solo botón que cambia en todas las anchuras**: con el doble se ve que
  hay dos zonas y cuál está elegida; solo se recoge donde no cabe.

## Consecuencias

- Cada vecino ve las temperaturas de donde vive, sin cifras de la otra zona.
- Quien mira la parte alta ve un aviso de la riera si hiela abajo.
- El bot y la web pueden decir cifras distintas a quien mira la parte alta:
  el bot sigue con la riera y añade la parte alta entre paréntesis.

## Evidencia

- Medido en la web publicada el 23-10-2026: entre el título y el botón de
  compartir, 105 px a 393 de ancho y 72 px a 360.
- Con los datos del 23-10-2026 a las 9:00: «Ara», 12,9 °C en la riera y
  14 °C en la parte alta (14, 13 y 14 °C en las tres de arriba); la
  semana, de 1 a 2 °C más arriba en las máximas.

## Riesgos y limitaciones

- La parte alta de los días 3 a 7 usa la diferencia habitual de los últimos 30
  días, la misma que la previsión por horas, pero no se ha comparado aparte con
  lo medido a varios días vista.
- Las estaciones de arriba dan la temperatura en grados enteros: la mediana
  de las tres, también.
- Si las estaciones de arriba fallan, «Ara» en la parte alta enseña la de la
  riera sin decirlo.

## Validación

- `tests/test_web.py`: las temperaturas de la zona (`test_les_temperatures_de_la_zona_triada`:
  tramos, glaçada de la riera desde la parte alta, `tempZona`), la semana y la
  comparación con ayer en la parte alta.
- `tests/test_setmana.py` (`test_la_part_alta`).
- En un servidor local con los datos del 23-10-2026: Chromium, Firefox y
  WebKit, a 360 y 393 px; al pulsar, cambian «Ara», tramos, gráfica y semana,
  la dirección pasa a `?zona=alta` y al recargar se conserva; sin
  desbordamiento; axe-core sin incidencias en toda la página, también a
  1280 px.

## Cambio del 24-10-2026 (3.195.0): la riera, también sin decimal en «Ara»

Juanjo: «para uniformizar la temperatura de la riera de la tarjeta inicial
debería mostrarse sin decimales como la de la parte alta? así no se ve
diferencia». El agente estuvo de acuerdo: al cambiar de zona, la cifra pasaba
de «11,1 °C» a «12 °C», y el resto de la web (gráfica, tramos, semana,
comparación con ayer, bot) ya va en grados enteros; la décima de la estación
de casa es real, pero no aporta a quien mira el barrio (la previsión se
equivoca 0,7 °C de media). Juanjo: «sí, hazlo y publícalo». La temperatura de
la riera en «Ara» se redondea a grados enteros, como la de la parte alta
(`casa.js`, `blocAra`); nada más cambia.

