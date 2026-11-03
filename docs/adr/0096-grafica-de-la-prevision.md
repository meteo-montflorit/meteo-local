# 96. Una gráfica de la previsión encima de los tramos

Fecha: 2026-10-16 · Estado: aceptado

## Contexto

La previsión de la portada es una lista de tramos (Matí, Tarda, Nit, Demà
matí, Demà tarda) que se despliegan en tablas hora a hora. Para ver de un
vistazo cómo irá el día hay que leer varias tarjetas. Juanjo pidió «un
resumen visual … donde se vea la temperatura, el estado del cielo, la
lluvia, avisos, peligros» que fuera «muy visual y muy claro», y propuso
ponerlo antes de «D'on surt». Se le propuso arriba de «Previsió» (al final
de la página quedaba debajo de las tablas y repetía lo que se acababa de
leer) y un meteograma, el patrón de Yr o meteoblue; lo aprobó. Señaló que
una línea vertical de «ara» no tenía sentido, porque la gráfica empieza
siempre en la hora en curso.

## Decisión

- **Un meteograma al principio de «Previsió»**, antes de los tramos, de la
  hora en curso hasta el final de la tabla (las 21 h de mañana). Las mismas
  horas y los mismos datos que las tablas (`casa.grafica`), sin nada que no
  esté debajo.
- **De arriba abajo**: la franja de peligro, del color del nivel y con el
  texto de la tabla («Perill alt: pluja»); si no cabe dentro (un aviso de
  pocas horas), al lado, y completo al tocarla. Debajo, «Avui» y «Demà»,
  separados por una raya discontinua a medianoche, y el cielo, un icono cada
  3 h (cada 2 h si hay sitio), el de lluvia si llueve en alguna hora del
  bloque. El cielo queda aparte, arriba: nada llega a su fila.
- **Temperatura y lluvia en la misma zona**, las barras detrás de la línea,
  como en los meteogramas habituales (Juanjo: «mezclando ambas, con las barras
  por detrás, será lo mejor y más natural»). La línea lleva un borde del
  color del fondo para verse sobre las barras. Desde la 3.96.1 la línea es
  una curva suave (cúbica monótona, la «monotoneX» de d3: pasa por cada hora
  y no sube ni baja más que los datos) con un relleno rojo muy tenue debajo,
  detrás de las barras (Juanjo: «tiene picos… que parezca más profesional»).
- **La temperatura**: la cifra, debajo de cada icono del cielo, la de la
  hora del medio de su bloque (Juanjo: «no quedaría bien la temperatura bajo
  el cielo?»): cielo y temperatura se leen juntos. La línea, sin cifras, dice
  si sube o baja. Antes llevaba la máxima y la mínima de cada día y la de la
  hora en curso; esta, prevista, no coincidía con la medida de «Ara», y dos
  cifras iguales a distinta altura parecían un error. La máxima exacta puede
  caer entre dos iconos: está en el resumen del día y en cada tramo.
- **La lluvia**: la altura es la cantidad, no la probabilidad (con la
  probabilidad, una hora de 0,5 mm y una de 45 mm salían iguales). Escala fija,
  para que un día de llovizna no parezca un diluvio, y de raíz cuadrada, para
  que 1 o 2 mm se vean: arriba del todo, 40 mm en una hora. Azul lleno si es
  probable (desde el 50 %), claro si solo es posible (del 20 al 50 %) y sin
  barra por debajo, los mismos umbrales que el cielo de la tabla. La pluja
  forta (desde 40 mm en una hora) en naranja y la torrencial (desde 80) en
  rojo: las intensidades del manual de estilo de Meteocat, las palabras de la
  columna «Cel» (ADR 0043). Los avisos no colorean las barras: van en la
  franja. Los milímetros, con su unidad, en la hora más fuerte de cada
  episodio.
- **La noche**, sombreada en gris, de la puesta a la salida del sol: un color
  que no se confunda con la lluvia.
- **El eje empieza por «Ara»**, sin línea vertical: la gráfica empieza siempre
  en la hora en curso. Cada hora lleva una marca: larga y con número las que
  tocan (cada 3 h, o 2), corta y sin número la resta (Juanjo, 16-10-2026).
- **Debajo, una leyenda** de una palabra por clave, sin paréntesis:
  Temperatura y Nit, y cada clase de lluvia solo cuando sale: «Pluja, 50 % o
  més», «Pluja, del 20 al 50 %», Pluja forta y Pluja torrencial. Desde la
  3.97.1 la probabilidad va en cifras; hasta entonces ponía «Pluja probable» y
  «Pluja possible». Juanjo: «entre lluvia probable y puede llover no hay
  diferencia para un usuario normal»; los porcentajes son los mismos umbrales
  que el cielo de la tabla (`PROB_PLUJA` y `PROB_POSSIBLE` de `casa.js`).
  Desde la 3.97.2, también «Pluja, del 10 al 20 %», en turquesa
  (`PROB_POCA`, solo en la gráfica): en el archivo de 2024-2026, con un 10-20 %
  llovió una de cada siete horas, y por debajo del 20 % caía una de cada cinco
  horas de lluvia, que la gráfica no enseñaba. Desde el 1 % se descartó (por
  debajo del 5 % llueve menos de una vez de cada cien) y desde el 5 %, porque
  añadía marcas con poca información. El color, propio y no un azul más
  claro (Juanjo: «el color que se diferencie de los que ya hay»). La tabla no
  cambia: «possible pluja» sigue siendo desde el 20 %.
- **Fuera de entrada**: el viento, la parte alta y el UV, que ya están en las
  tablas. Se añadirán si se echan en falta.
- **Tocar una hora** (o pasar el ratón, en el ordenador) muestra encima un
  rótulo con su hora, sus milímetros y su probabilidad («17 h · 6 mm ·
  70 %»), y marca la columna; se quita al tocar fuera o la misma hora. Desde
  la 3.98.0: Juanjo preguntó si se podían poner los milímetros en todas las
  barras («solo pone la lluvia del mayor?»), pero en el móvil cada hora mide
  de 9 a 15 px y la cifra unos 17; con litros sería igual de larga y habría
  que escribir «l/m²». La cifra de la hora más fuerte de cada episodio (desde
  0,5 mm) sigue a la vista.
- **La ficha de cada hora** (desde la 3.101.0; Juanjo, 17-10-2026: «no se
  podrían añadir el resto de datos meteorológicos de previsión de esa
  hora?»): el rótulo pasa a ser una ficha con la hora y el cielo, la
  temperatura, la lluvia (mm y probabilidad) y el viento con sus rachas.
  La parte alta, solo si difiere al menos 1 °C (el mismo redondeo que las
  tablas); la nieve, solo si se espera, y el UV, solo de día y desde 3,
  donde la escala de la OMS ya pide protección. Fuera, el porcentaje de
  nubes (ya lo dice el cielo) y los avisos (la franja está encima de la
  columna). No hay humedad ni dirección del viento en los datos. La ficha
  va al lado de la columna, donde quepa, para no tapar la hora; si no cabe
  a ningún lado (en el móvil, las horas del centro), debajo del eje,
  encima de la leyenda.
- **La gráfica en grande** (desde la 3.101.0; Juanjo, 17-10-2026: «verlo en
  su propia ventana o sección y con posibilidad de alguna configuración»):
  el botón «Amplia», junto a «Desplega-ho tot» (en el móvil, solo el icono,
  para que los dos quepan al lado del título), la abre sobre la página, con
  margen, más alta y con su dirección (`#grafica`) para compartirla. No es
  una página más del menú: sería la misma gráfica repetida. Opciones: qué
  horas (hoy, mañana o todo; hoy y mañana, solo si tienen al menos 3 horas)
  y el viento como capa (media y rachas, escala de 10 en 10 desde 20 km/h).
  La parte alta y el UV no son capas: ya salen en la ficha de cada hora. Lo
  elegido se recuerda en el dispositivo. Se cierra con la X, Esc o tocando
  fuera. Con columnas anchas, el cielo y las horas salen cada hora.
- **El nombre de cada día, por su fecha** (Juanjo, 17-10-2026): de noche la
  tabla llega hasta pasado mañana, y la segunda medianoche decía otra vez
  «Demà»; ahora «Demà passat». El primer nombre se quita si no cabe antes de
  la medianoche («si avui no cabe no se escriba nada, ya se entiende»).
- **También en «Consultes»** (Juanjo, 17-10-2026: «en las fichas de
  consulta: avui y demà también deberá aparecer el gráfico
  correspondiente»): bajo el título de «Avui», la gráfica de ahora a
  medianoche; en «Demà», la de mañana (de 0 h al final de los datos). Con
  menos de 3 horas, ninguna. El dibujo es el mismo: la gráfica y lo que
  necesita (el cielo, la lluvia y el perill de cada hora) pasan de
  `casa.js` a `web/grafica.js`, que cargan la portada y «Consultes».
- **Los textos de los avisos, sin pisarse** (Juanjo, 17-10-2026: «sin que
  se pierda información vital. si es necesario usa dos filas»): dentro de
  la franja, el texto entero (nivel y fenómenos) si cabe. Si no, al lado,
  a la derecha o a la izquierda, solo si allí no hay ninguna franja ni
  otro texto (el texto debajo, solo, «no lo entiendo»). Si tampoco, en una
  fila debajo, con un cuadrito del color del aviso, desde donde empieza;
  si choca con el anterior, en otra fila (hasta tres), y solo si tampoco
  cabe, el nivel solo. Antes iba al lado sin comprobarlo y caía encima del
  texto de otra. Al tocar la franja o su texto, siempre el aviso completo.
  Probado con cuatro avisos seguidos a 320 px: nada se pisa.
- **Todos los avisos de la hora en la franja** (Juanjo, 17-10-2026: con
  perill alt de Meteocat por lluvia y aviso amarillo de AEMET por
  tormentas, la franja solo decía el primero; «que la franja diga las dos
  cosas»): el color es el del nivel más alto y el texto los dice todos, del
  más alto al más bajo («Perill alt: pluja · Avís groc: tempestes»). Cada
  fenómeno, una sola vez y en su nivel más alto: un amarillo de AEMET por
  lluvia no se repite bajo un naranja de lluvia intensa de la web. Vale
  también para la barra de las tablas y la etiqueta de cada tramo, que usan
  lo mismo (`avisHora`, `perillTram`).
- **El cielo, la temperatura y la hora, cada hora si hay sitio** (Juanjo,
  17-10-2026: «la gráfica está bastante vacía, mejor que salga cada hora»):
  desde 30 px por hora; si no, cada 2 (desde 18 px) o cada 3.
- **El origen de cada aviso en la franja** (Juanjo, 17-10-2026: «añade el
  origen: meteocat, aemet, etc»): «Perill alt (Meteocat): pluja · Avís groc
  (AEMET): tempestes»; los de la web, «(aquesta web)». Solo en la gráfica:
  las tablas lo dicen al tocar la barra. Debajo de la franja, cada aviso va
  por separado, con el cuadrito de su nivel, y abre las filas que hagan
  falta: con cuatro avisos seguidos a 320 px, el rojo se quedaba sin sitio
  con el límite de tres filas.
- **La imagen para Telegram y los avisos** sale de esta misma gráfica (ADR
  0098).
- **La barra de lluvia, proporcional** (3.114.1; Juanjo, 17-10-2026: «la
  columna mayor de lluvia pone 3.7mm y debería ser más o menos 1/3 del
  espacio que queda hasta los 10mm»): la escala de raíz cuadrada (3,7 mm
  llegaban al 61 % del techo) pasa a lineal (37 %). Con el techo rotulado,
  la altura se lee como proporción de esa cifra; con los escalones, 1 mm ya
  es el 10 % de la altura, y las barras muy bajas tienen 3 px como mínimo.
- **Los avisos de después de la gráfica** (3.114.0; Juanjo, 17-10-2026, ante
  un perill molt alt de Meteocat para el lunes que no salía en la gráfica ni
  en los tramos, que llegan a mañana a las 21 h): encima de la gráfica, una
  línea por día con los avisos oficiales que empiezan después de su última
  hora («Dilluns 19: Perill molt alt (Meteocat): pluja ›»), con el cuadrito
  del nivel, cada fenómeno una vez en su nivel más alto, y que lleva a su
  ficha de «Perill». También en «Consultes» y en la imagen de Telegram.
- **«Opcions», que valen para toda la web** (3.108.0; Juanjo, 17-10-2026:
  «no me gusta esa doble flecha… o un botón de configuración… decide tú
  cómo hacerlo, que sea fácil de entender y útil», «lo que se decida en la
  vista ampliada se conserva para la vista normal… en toda la web» y «que
  se pueda desactivar la temperatura de la parte baja del barrio, para el
  que no la necesite»): el botón pasa a «Opcions», con el icono de ajustes
  (`sliders-horizontal` de Lucide), porque lo que hace sobre todo es
  configurar la gráfica. Lo que se elige allí se recuerda en el dispositivo
  y vale para todas las gráficas: el viento y las dos
  temperaturas, «Part baixa» (la de la estación, junto a la riera; por
  defecto, sí) y «Part alta» (por defecto, no). Sin la de abajo, las cifras
  bajo los iconos y el relleno son los de arriba; sin ninguna, no hay
  curva. Las horas no (3.108.1; «lo que no afectará a todas las gráficas es
  el periodo que se visualizará, porque eso depende del sitio donde está la
  gráfica»): la portada, de ahora a mañana a las 21 h; «Consultes», las de
  su ficha; la vista en grande, las que se eligen allí.
- **La máxima toca la raya del techo** (3.107.0; Juanjo, 17-10-2026: «la
  temperatura debe llegar al máximo de la lluvia y poner esa temperatura
  máxima a la izquierda, así la misma línea indica el máximo de lluvia (por
  tramos) y por temperatura»): la escala de la temperatura va de un grado
  por debajo de la mínima a la máxima, que toca la raya del techo de la
  lluvia; la raya, ahora gris y siempre a la vista, lleva la máxima a la
  izquierda («24 °C», en el rojo de la temperatura) y el techo de la lluvia a
  la derecha («10 mm», solo si llueve). La curva es monótona entre horas,
  así que no pasa de la raya.
- **La mínima, abajo a la izquierda** (3.210.0; Juanjo, 03-11-2026: «igual
  que sale la maxima del periodo arriba a la izquierda, me gustaria que
  saliese también la minima abajo a la izquierda»): una raya gris a la
  altura de la mínima del periodo, con su cifra a la izquierda («7 °C», en
  el azul de la mínima de la previsión de 7 días). No sale si redondeada es
  igual que la máxima, si no cabe bajo la del techo (16 px) ni en las
  gráficas con escala cada 2 °C («Historial» y «Fiabilitat»), donde ya se lee
  y las cifras se pisarían.
- **La parte alta, como segunda curva** (3.107.0; Juanjo, 17-10-2026: «una
  opción en la vista de gráfico que actúe como conmutador para mostrar la
  temperatura en la parte baja y alta»): botón «Part alta» en la vista en
  grande, junto a «Vent», que añade la temperatura de la parte alta
  (temperatura + `dif_alta`) en discontinua, del color de la parte alta; las
  dos a la vez, para ver a qué horas y cuánto difieren, en lugar de cambiar
  una por otra. Apagado por defecto; la elección se recuerda y vale para
  todas las gráficas, como el viento. Con ella, la raya del techo marca la
  máxima de las dos, sin decir de cuál (3.172.0; Juanjo, 21-10-2026: «no
  hace falta el paréntesis»). Bajo la cifra de cada icono, la de la parte
  baja, va otra con la de la parte alta, del color de su curva; si se quita
  la parte baja, la de la parte alta ocupa su sitio con su color, para
  distinguirlas (Juanjo, 21-10-2026: «deberían aparecer debajo de las
  temperaturas de la parte baja las de la parte alta» y «para distinguirlos
  debe mantener su color»). Las horas pasadas no la llevan: allí no se
  calcula.
  Deshace en parte lo de la ficha de cada hora («las capas de UV y parte
  alta sobran»): la ficha sigue dando el valor; la curva enseña la forma.
- **El viento, por defecto en todas las gráficas** (3.106.0; Juanjo,
  17-10-2026: «el viento aparecerá marcado por defecto, aunque el usuario lo
  podrá quitar si quiere» y «también en la página inicial saldrá»): en la
  portada, en la vista en grande y en «Consultes». «Vent» de la vista en
  grande lo quita, y la elección se recuerda en el dispositivo para todas;
  al cerrar la vista se redibujan las demás. Clave nueva
  (`meteo.grafica.2`): la anterior guardaba «vent: false» sin que nadie lo
  eligiera, solo por cambiar las horas.
- **Una barra por aviso** (3.105.0; Juanjo, 17-10-2026: «por qué aemet
  tormentas sale repetido?»): la franja juntaba los avisos de cada hora, y
  un mismo aviso de AEMET quedaba partido entre la franja naranja de
  Meteocat y la del día siguiente, con su texto debajo de la que no era.
  Ahora cada aviso (fuente, nivel y fenómeno; los fenómenos que duran lo
  mismo, juntos) es una barra con su duración real, en filas cuando
  coinciden, de más grave a menos (`barresAvis`). Cada fenómeno, a cada
  hora, solo en su nivel más alto, como en las tablas. El texto, entero,
  empieza dentro de la barra y lo que no cabe sigue fuera con el color del
  texto de la página («el que no quepa sigue por fuera con el cambio de
  color necesario para verse bien»): se dibuja dos veces con recortes, así
  que nunca se acorta. Si no cabe a la derecha, se desplaza a la izquierda;
  si choca con otra barra o su texto, va a la fila siguiente. Sustituye las
  filas de debajo con cuadrito.
- **El techo de la lluvia, por escalones** (3.101.1; Juanjo, 17-10-2026: «las
  columnas me parecen cortas» y «no sería mejor una escala variable?»): en
  lugar de 40 mm siempre, el primer escalón de 10, 20, 40, 80 o 160 mm que
  cubre la lluvia más fuerte de la gráfica, nunca menos de 10 mm, con una
  raya fina arriba y su cifra («10 mm»), como la del viento. Una escala que
  se ajustara justo al máximo haría que 1 mm pareciera una tromba; con los
  escalones, la llovizna sigue viéndose pequeña y el naranja y el rojo
  siguen avisando de la fuerte y la torrencial. Con los datos del 17-10, los
  6,9 mm de la noche pasan del 41 % al 83 % de la altura. La cifra de mm que
  no cabe sin pisar otra ya no se escribe: sale en la ficha de la hora.
- **SVG dibujado desde `casa.js`**, sin bibliotecas ni conexiones externas,
  con el ancho real de la pantalla (se redibuja al cambiar de tamaño) para que
  el texto no se encoja en el móvil, y con los colores del tema claro y
  oscuro. La gráfica no va para los lectores de pantalla (`aria-hidden`):
  una descripción oculta dice que los mismos datos están en las tablas.

## Alternativas descartadas

- **Al final, antes de «D'on surt»**: la vería poca gente y repetiría las
  tablas.
- **Una cinta por tramos** (una columna por tramo): se lee al instante pero
  no enseña cómo cambian la temperatura y la lluvia a lo largo del día. Queda
  como alternativa si el meteograma no se leyera bien en el móvil.
- **Una biblioteca de gráficas**: añadiría una dependencia para un dibujo
  sencillo.
- **La altura de la lluvia por probabilidad, con una raya en el 50 %** (la
  3.94.0): la lluvia fuerte salía tan pequeña como la débil.
- **Temperatura y lluvia en zonas separadas**: se probó, primero con la lluvia
  baja y después con la misma altura; juntas se leen mejor y caben más altas.
- **Barras con los colores de aviso** (desde 20, 40 y 90 mm, los umbrales de
  AEMET): no corresponden a ninguna escala de nombres y obligaban a inventar
  una etiqueta («pluja d'avís»). El aviso ya está en la franja.

## Riesgos

- En un móvil estrecho (320 px), 33 horas salen a unos 10 px por hora: los
  iconos van cada 3 h y el texto de la franja se acorta.
- La lluvia se probó con datos simulados (una tormenta con 45 y 85 mm en una
  hora y un aviso naranja propio); falta verla con un episodio real.
- La escala se corta en 40 mm: por encima, la barra llena y el color (forta,
  torrencial) dicen cuánto.

## Validación

- `probar-web` en Chromium, Firefox y WebKit, en escritorio, móvil y tableta,
  claro y oscuro, sin errores ni desbordamiento; móvil de 320 px y versión en
  castellano en móvil. axe-core sin incidencias en «Previsió».
- Ninguna hora del eje se superpone a «Ara» ni a «Ahora» en los tres
  navegadores, a 320 y 412 px. 478 pruebas en verde, una de ellas para las
  intensidades de las barras.
- 3.95.0 y 3.96.0, con datos simulados de tormenta: los mismos navegadores,
  tamaños y temas, y axe-core sin incidencias. En un móvil de 320 px, un
  primer bloque de menos de 3 horas no lleva icono ni cifra.

## Cambio del 19-10-2026 (3.152.0): el viento, apagado por defecto, y dos clases de opciones

Juanjo: «por defecto no debería mostrar el viento» y «en la configuración
debería marcarse de forma diferente lo que queda fijado y lo que no cuando
se sale de la configuración, mi propuesta es hacer lo permanente con
selectores, pero decide tú». En la vista en grande, lo que se recuerda en el
dispositivo y vale para todas las gráficas de la web (Vent, Part baixa, Part
alta) va con interruptores, abajo, bajo «Es recorda per a totes les
gràfiques»; lo de esa visita (Avui / Demà / Tot, «Com encerta», la
antelación) va con botones y vuelve a lo de siempre al cerrar. El viento
sale apagado. Clave nueva, `meteo.grafica.3`: la 2 guardaba «vent: true»
para todos al tocar cualquier opción, sin que nadie lo eligiera; de ella se
conservan la parte baja y la parte alta.

## Cambio del 19-10-2026 (3.153.0): una fila por fuente y fenómeno en las barras de avisos

Juanjo: «las barras las veo desordenadas, ¿cómo se podrían ordenar?». Cada
aviso (fuente, nivel y fenómeno) era una barra con su texto entero, ordenadas
del nivel más alto al más bajo y colocadas en la primera fila donde cabían: el
mismo aviso de Meteocat por lluvia salía partido en tres trozos repartidos en
dos filas, y el texto se salía de la barra. Ahora (`filesAvis`) hay una fila por
fuente y fenómeno, siempre en el orden Meteocat, AEMET, esta web, con el nombre
encima en pequeño («Meteocat · pluja») y, debajo, los tramos seguidos con el
color de su nivel y el nivel dentro si cabe («moderat», «alt», «groc»); el
texto entero, al tocar el tramo. Dos fenómenos de la misma fuente con los
mismos tramos comparten fila. Con los avisos del 19-10-2026, dos filas en vez
de tres.

Y en la 3.153.1, a propuesta de Juanjo («AEMET tempestes cabe a la izquierda.
En el caso de que quepa ¿se podría poner delante? Así ahorramos una fila más»):
si a la izquierda del primer tramo cabe el nombre, va en la misma línea que la
barra; si no, encima. En el escritorio, con los avisos del 19-10-2026, la fila
de AEMET ya no lleva línea de nombre; en un móvil de 412 px, ese día, no cabía
(la barra empezaba a 74 px y el nombre ocupa unos 105).

En la 3.153.2, la vista en grande en el móvil, más compacta (Juanjo: «en
móvil la gráfica de la configuración ocupa mucho espacio vertical, ¿se puede
optimizar?»): la zona de temperatura y lluvia, el 22 % de la altura de la
pantalla en vez del 32 % (unos 200 px en vez de 290 en un móvil de 915), los
botones de las horas y «Com encerta» en una fila, y la leyenda y los
interruptores más pequeños. En un móvil de 412 px la ventana ocupa 576 px y
no hace falta desplazar; en el ordenador no cambia.

En la 3.154.1, si el nombre no cabe delante de la barra, va detrás del
último tramo, si cabe (Juanjo: «¿qué te parece poner el servicio que da el
aviso a la derecha si hay espacio y no cabe a la izquierda?»); solo si no cabe
en ningún lado, encima. Sin flecha: en la misma línea y pegado a la barra ya
se lee que es suyo. Con los avisos del 19-10-2026, en un móvil de 412 px los
dos nombres van a la derecha y las barras ocupan dos líneas en vez de cuatro.



## Cambio del 20-10-2026 (3.164.0): «24 h» y el selector encima del gráfico

Juanjo (20-10-2026): «al selector del gráfico hoy y mañana añádele 24h y
además añádelo también justo encima del gráfico para que el usuario
rápidamente pueda consultar lo que quiera. Por defecto saldrá 24 horas pero
si el usuario lo cambia el cambio será persistente», y «el tot también debe
estar». El selector de horas tiene ahora «24 h» (las 24 horas desde la que
está en curso), «Demà» y «Tot», y sale también justo encima del
gráfico de la portada, no solo en «Opcions», y en la misma fila que el botón
«Opcions», con la misma altura (Juanjo, 20-10-2026: «las opciones en la misma
línea que los botones»). La fila va **debajo** del gráfico, no encima (Juanjo,
el mismo día: «los prefiero debajo de la gráfica, así no se desvía la
atención»), y «Opcions» lleva el texto también en el móvil, porque cabe. Por defecto, «24 h»; lo que se
elige se recuerda en el dispositivo (`meteo.grafica.hores`) y vale para los
dos sitios: cambiarlo en la ventana grande cambia también el de la portada.
Antes la portada enseñaba siempre todas las horas y la ventana grande
empezaba cada vez por «Tot». Si lo guardado ya no tiene horas suficientes,
sale «24 h». «Avui» se quitó el mismo día: empezaba en la hora actual como
«24 h» y era siempre un trozo suyo, cortado a medianoche; a las 12 de la noche
eran iguales (Juanjo, 20-10-2026: «si uno pone avui a las 12 de la noche es
como poner 24h»; «sí, quítalo»). Lo guardado como «Avui» pasa a «24 h». El
gráfico de «Consultes» sigue con el día del que habla el resumen.

Validación: `tests/test_web.py` (`test_grafica_24_hores_per_defecte_i_es_recorda`);
en Chromium y Firefox, el selector, la persistencia al recargar y el cambio
desde la ventana grande; capturas en móvil y escritorio; axe-core sin fallos
en la portada, claro y oscuro, catalán y castellano.

Las horas del eje van ahora con su propio paso, aparte de los iconos del
cielo (Juanjo, 20-10-2026: «en 24h y en avui, ¿no caben todas las h en el eje
x?»). Medido en el móvil, un número de hora ocupa unos 12,6 px; con «Avui»
hay de 19 a 22 px por hora y con «24 h», de 13,6 a 15,8. El eje pone todas
las horas con 18 px o más por hora, y si no, de dos en dos (antes seguía el
paso de los iconos, que necesitan unos 30: cada 2 o cada 3 h). En el móvil,
«Avui» lleva todas las horas y «24 h», de dos en dos.

El eje, natural: solo las horas en punto, a intervalos regulares, sin «Ara»
ni ningún número distinto al principio (Juanjo, 20-10-2026: «quita el ara del
gráfico» y, tras probar con la hora en curso a la izquierda, «el eje x normal,
sin números de más o menos al principio, eje x natural»). Con «Com encerta»
queda la raya donde empieza la previsión, sin rótulo.

## Cambio del 20-10-2026 (3.165.0): sin «Com encerta»

La vista en grande ya no lleva el botón «Com encerta», las flechas de los
días pasados ni la antelación: están en su propia página, «Fiabilitat», a la
que se llega desde el menú ⋮ (ADR 0110). Lo que este ADR dice de «Com
encerta» en la vista en grande ya no vale.

## Cambio del 20-10-2026 (3.166.0): hora a hora, desplazando de lado

La gráfica enseña siempre todas las horas que quedan, hasta mañana a las 21 h,
**hora a hora**: cada hora tiene como mínimo 36 píxeles (`COL_HORA`), con su
icono del cielo y su temperatura, y si no caben todas la gráfica se desplaza
de lado, con el dedo en el móvil y con la barra en el ordenador; mientras
queda gráfica a la derecha, el borde se difumina para que se vea que sigue.
Sin el selector «24 h · Demà · Tot» de la portada ni de la vista en grande
(Juanjo, 20-10-2026: «quiero que hagas siempre tot pero con barra de
desplazamiento horizontal… me interesa que salga hora a hora, no cada 2
horas»). Antes, para caber en la pantalla, el cielo salía cada 2 o 3 horas.
Vale para todas las gráficas: la portada, la vista en grande, «Consultes» y
el día a día de «Fiabilitat». La ficha de cada hora pasa a ser un recuadro
encima de la figura, fuera de la caja que se desplaza, para que no quede
recortada, y se cierra al desplazar. Las imágenes (la cámara y la que el NAS
manda a Telegram, `grafica_imatge.py`) se dibujan compactas, al ancho de la
página, como antes (`fig._compacte`), para que salga todo en una. La caja
se puede recorrer con el teclado (foco y flechas) y tiene nombre para los
lectores de pantalla.

Validación: Chromium, Firefox y WebKit en escritorio, móvil y tableta, claro y
oscuro, sin errores ni desbordamiento de la página; desplazar y tocar una hora
en móvil y ordenador (la ficha queda dentro de la pantalla); la imagen de la
cámara, de 388 px en un móvil de 393, y la de Telegram, entera; axe-core sin
fallos en la portada, «Consultes» y «Fiabilitat».

En la misma versión, **«Opcions» pasa al final de la leyenda**, dentro de la
figura, como la cámara de «Consultes»; en el móvil, solo con el icono. Así
desaparece la fila de debajo de la gráfica, que solo llevaba ese botón (Juanjo,
20-10-2026: «el botón opciones, se podría meter dentro del gráfico sin
transtornarlo? sin texto en el movil, ganariamos un espacio»). Y en la vista en
grande se quita el rótulo «Es recorda per a totes les gràfiques» de los
interruptores, que ya se entiende («quita esto, ya se entiende»); el grupo lo
conserva como nombre para los lectores de pantalla.

**Las cifras del techo, siempre a la vista** (20-10-2026). Con la gráfica
desplazándose, los milímetros del techo de la lluvia (a la derecha) y la
temperatura máxima (a la izquierda) quedaban en los extremos del dibujo y
solo se veían al principio o al final (Juanjo: «se puede hacer que estos dos
valores estén siempre visibles?»). Cuando la gráfica se desplaza, las dos
cifras van en una capa fija encima de la caja (`.g-fixes`), en los bordes de
la parte visible, a la altura de la línea del techo, que sigue dentro del
dibujo. En las imágenes (compactas, sin desplazamiento) van dentro de la
gráfica, como antes. Validación: Chromium y Firefox a 390 px, con las dos
cifras visibles al principio y al final del desplazamiento.

**Humedad e índice UV** (21-10-2026, 3.171.0). Dos interruptores más,
«Humitat» y «UV», apagados por defecto y recordados con los demás: la humedad
en una franja bajo el viento y el UV en casillas con los colores de la OMS.
La humedad sale del rocío corregido: ADR 0114.

## Cambio del 21-10-2026 (3.174.0): una zona u otra, no las dos

La parte alta se había añadido como segunda curva, junto a la de la parte
baja, con dos interruptores. Lo de ver las dos a la vez no lo pidió Juanjo:
el 17-10 pidió «un conmutador para mostrar la temperatura en la parte baja y
alta», y se interpretó como añadir una curva. Juanjo, 21-10-2026: «¿para qué
sirve tener los dos a la vez? o te interesa la de arriba o la de abajo».
Cada vecino vive en una zona, y la diferencia ya la da el «+1», «+2» de la
previsión.

- **Decisión**: en «Opcions», un selector de dos posiciones, «Part baixa» y
  «Part alta» (`vg-trams`, como los botones agrupados de la web), delante de
  los interruptores. Por defecto, la parte baja. La gráfica dibuja una sola
  curva, con una cifra bajo cada icono y la raya del techo de la zona
  elegida; la parte alta, con su color. Desaparece la combinación sin
  temperatura. Se recuerda en el dispositivo como `zona` en
  `meteo.grafica.3`.
- **Compatibilidad**: lo guardado con los dos interruptores se convierte al
  leerlo (`grafica.ambZona`): solo la parte alta pasa a «alta»; las dos,
  ninguna o solo la baja, a «baixa».
- **Se quita** el dibujo de las dos curvas y las dos cifras a la vez
  (3.172.0), que este cambio sustituye.
- **Validación**: `tests/test_web.py`
  (`test_zona_de_la_temperatura_de_les_opcions_velles`), `probar-web` en tres
  navegadores, móvil, escritorio y tableta, claro y oscuro, y axe-core sobre
  la ventana de la gráfica.
- **Descripción** (3.174.1): cada botón lleva la suya al pasar el ratón
  («La temperatura de vora la riera, la zona més freda del barri» y «… de la
  part alta del barri, que sol ser més alta que vora la riera»). Juanjo: «no
  me queda claro que la gente lo entienda a la primera».
