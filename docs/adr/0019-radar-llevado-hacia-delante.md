# 19. Radar llevado hacia delante

Fecha: 2026-10-06 · Estado: aceptado

## Contexto

Juanjo preguntó si la evolución de la lluvia en el radar entra en la
predicción, porque «probablemente sea uno de los mejores indicadores». Hasta
ahora, el trayecto solo miraba a qué distancia estaba la lluvia y si crecía en
la última hora (ADR 0001), y la página de casa usaba el radar solo para pasar
al modo aviso. Ninguna de las dos sabía hacia dónde iba la lluvia. El
05-10-2026 los modelos daban 0,3 mm por hora mientras caían más de 20.

Preguntó también si RainViewer, la fuente de entonces, es mejor que el radar
de Meteocat, que es el que él mira.

## Decisión

- **Imagen**: la última de Meteocat, la composición corregida de su red de
  radares (XRAD: Vallirana, a unos 20 km de casa, Puig d'Arques, Tivissa-
  Llaberia y La Panadella), cada 6 minutos. Si se queda más de 15 minutos por
  detrás de la de RainViewer (composición de AEMET, cada 10 minutos), se usa
  la de RainViewer. Desde el ADR 0026, con 10 minutos basta (desde la
  3.129.0, con RainViewer como preferida, su imagen siempre que no sea más
  vieja), y una comparación diaria decide cuál de las dos acierta más.
- **Movimiento**: el de la advección de Meteocat, su predicción a una hora,
  que calcula el campo de movimiento con las tres últimas imágenes. Se mide
  cuánto se desplaza su lluvia de la primera imagen prevista a la última, en
  la lluvia de cerca del trayecto y, si hay poca, en un cuadro de unos 300 km
  (ADR 0023). Si la advección tiene más de una hora, el de
  RainViewer (pares a 30 minutos de la última hora), solo si los pares
  coinciden (menos de 20 km/h de diferencia). Si no, la lluvia se deja quieta.
- **Hacia delante** (`nowcast.py`): cada 5 minutos y hasta 2 horas, la lluvia
  de ahora en el punto de donde vendrá y en un círculo que crece con el tiempo
  (3 km más 0,08 km por minuto; 13 km a las 2 horas). Cada píxel es un caso
  posible: la lluvia esperada es la media y la probabilidad, la fracción con
  0,5 mm/h o más. Colores a dBZ con la leyenda de cada fuente; dBZ a mm/h con
  Marshall-Palmer (Z = 200 R^1,6).
- **Trayecto** (`prevision.py`): si la ventana del viaje cae dentro de las 2
  horas, el radar llevado hacia delante sustituye a la regla de la distancia,
  con los umbrales de los modelos: lluvia probable (50 %) y de 1 mm/h o más,
  riesgo alto; posible (20 %), moderado. Entre 2 y 3 horas, la distancia de
  siempre. Lluvia probable en casa en la hora siguiente activa el modo aviso.
- **Página de casa**: en las dos primeras horas de la tabla, si el radar da
  más lluvia o más probabilidad que los modelos, se usa la del radar, marcada
  con †; nunca rebaja la previsión, porque la lluvia que aún no se ha formado
  no está en el radar. La probabilidad cuenta aunque el radar cubra solo una
  parte de la hora; los mm, solo si cubre 30 minutos o más. En
  «Ara a casa», una línea dice cuándo llegaría la lluvia, hacia dónde va y a
  qué velocidad. El riesgo propio (ADR 0018) lo recoge a través de la tabla.
  Si el radar no ve lluvia que se acerque, la franja solo sale cuando la
  tabla da lluvia, al menos posible (20 %), en alguna de las dos horas
  siguientes: entonces «No s'acosta pluja en 2 hores» contradice la previsión
  y es noticia. Si no, no sale, porque no dice nada que no diga ya la tabla
  (Juanjo, 10-10-2026, ante la franja en un día seco: «si no anuncia nada
  como ahora mejor que no salga»). El enlace «Radar de Meteocat» del final de
  la página sigue para quien quiera mirarlo.
- **Trato con Meteocat**: lo que se le pide equivale a tener abierta su
  página del radar con la actualización automática (unas 27 teselas nuevas
  cada 6 minutos y una vez su página por pasada, compartida entre las dos
  páginas). Si rechaza las peticiones (errores 403 o 429), se deja de pedir
  una hora (`/estat/meteocat-pausa`) y se usa RainViewer; si solo falla o
  está caído, la misma pasada sigue con RainViewer y se vuelve a probar en la
  siguiente. Su aviso legal permite reutilizar la información que ofrece
  libremente sin alterarla, citando la fuente y la fecha de la última
  actualización: por eso la franja del radar dice de quién es la imagen y de
  qué hora («Radar de Meteocat de les 12:42»).
- **Registro**: cada hora de la tabla guarda lo que daba el radar
  (`radar_mm`, `radar_prob`), y el trayecto, en sus señales
  (`radar_nowcast`), para comprobar con Montflorit si acierta y ajustarlo.

## Alternativas descartadas

- **Calcular el movimiento solo con RainViewer** (correlación de fase de
  toda la zona): con chubascos dispersos salta de 15 a 185 km/h entre pares
  seguidos (Evidencia). La advección de Meteocat da 21-29 km/h y la misma
  dirección.
- **Usar directamente la advección de Meteocat**: llega solo a una hora
  desde su imagen base, que se publica con unos 12 minutos de retraso. Queda
  menos de una hora por delante, y el trayecto se decide con hasta 2 horas.
- **Solo RainViewer o solo Meteocat**: Meteocat se para a veces (Evidencia);
  RainViewer marca más lluvia de la que hay.

## Consecuencias

- Las dos páginas descargan unas 90 teselas en cada pasada; el cálculo tarda
  unos 15 segundos.
- Si las dos fuentes fallan, todo sigue como antes, sin radar.
- La regla del trayecto cambia dentro de las 2 horas: `index.html` («Com es
  decideix») y el README lo explican.

## Evidencia

- Página del radar de Meteocat (consultada el 06-10-2026): fuentes, método de
  la advección («càlcul del camp de moviment de les tres darreres imatges»,
  horizonte de una hora, varias predicciones combinadas) y aviso de que La
  Panadella está fuera de servicio desde el 14-09-2026 durante unos 5 meses.
  Las teselas y la leyenda (franjas de 3 dBZ, de 9 a 66) salen de su script.
- Retraso: la imagen de las 09:42 UTC se publicó a las 09:54:24 (cabecera
  `last-modified`). Entre las 09:54 y las 10:14 UTC el servicio se paró (la
  página decía «Servei d'actualització d'imatges no disponible»); RainViewer
  tenía entonces la de las 10:10.
- Movimiento el 06-10-2026: RainViewer, pares de las 10:40 a las 12:10:
  25, 37, 34, 118, 51, 50, 58, 185, 169 y 15 km/h. Advección de Meteocat de las
  09:36 UTC: 21, 29 y 26 km/h hacia el nord-est y el est.
- Misma imagen (12:00), cuadro de 300 km: con 0,5 mm/h o más, 4.485 km² en
  Meteocat y 7.040 en RainViewer; con 20 mm/h, 108 y 188 km²; máximo, 107 y 205
  mm/h. El 66 % de la lluvia de Meteocat coincide con la de RainViewer.
- Aviso legal de Meteocat (<https://www.meteo.cat/wpweb/avis-legal/>),
  apartado «Informació continguda a Meteocat»: reutilización según la Llei
  37/2007 con cuatro condiciones (no alterar, no desnaturalizar, citar la
  fuente e indicar la fecha de la última actualización).
- Tabla de colores de RainViewer: <https://www.rainviewer.com/api/color-schemes.html>
  (`calibracio/rainviewer_colors.csv`); todos los píxeles de las teselas
  descargadas están en ella.
- Hipótesis sin comprobar: los umbrales de probabilidad y del círculo. No hay
  archivo del radar (RainViewer guarda 2 horas); se comprobarán con el
  registro.

## Riesgos y limitaciones

- Un solo vector para toda la zona, medido en la lluvia de cerca (ADR 0023):
  si hay corrientes distintas en sitios distintos, se equivoca en las lejanas.
- No ve la lluvia que nace ni la que crece o se deshace.
- **Ecos sueltos cerca de casa** (comprobado el 10-10-2026, día seco): la
  imagen de Meteocat tenía de 1 a 6 píxeles a 15 km o menos, todos en su
  franja más baja (10-16 dBZ, menos de 0,4 mm/h), y uno de ellos en el
  mismo sitio en las seis imágenes de 10:54 a 11:24 (a 12,8 km hacia el
  sur-suroeste, entre Esplugues y Cornellà); los demás, sueltos por la
  falda sur de Collserola y cerca de Montjuïc. Ninguna estación medía
  lluvia y RainViewer no veía nada en 200 km. Como la página usa Meteocat
  en unas pasadas y RainViewer en otras (según cuánto se retrase la imagen
  de Meteocat), el modo aviso se encendía en las de :00 y :30 y se apagaba
  tres minutos después. Sin avisos: el de lluvia depende de la probabilidad
  en casa, no de esta distancia. Juanjo: «no me preocupa si va alternando»,
  pero pidió seguirlo para decidir más adelante. Desde la 3.50.1 cada pasada
  apunta en `radar-a-prop-AAAA-MM.jsonl` del NAS (`registre.py`) los píxeles
  con lluvia a 15 km o menos de cada radar (distancia, rumbo y mm/h, los 40
  más cercanos), el modo aviso y sus motivos y qué estaciones medían lluvia.
  Con un mes de datos se decidirá si un eco suelto de la franja más baja deja
  de contar como lluvia cerca; hasta entonces no cambia nada.
- Las teselas de Meteocat no son una API documentada: si cambian, se usa
  RainViewer. Su API oficial, con clave y cuotas mensuales por plan, no
  tiene radar: su documentación
  (<https://apidocs.meteocat.gencat.cat/documentacio/>, leída entera el
  06-10-2026) solo recoge XEMA, XDDE, predicción, referencia y consumo. Sus
  cuotas (mensuales, y 1.000 peticiones por segundo) son de la API y no dicen
  nada de las teselas de la web.

## Validación

`tests/test_nowcast.py` (conversiones, leyendas, desplazamiento de un
chubasco, coincidencia de los pares, advección vieja, llegada, alejamiento,
niveles del trayecto y modo aviso), cálculo real de las dos páginas con
Meteocat parado y en marcha, `probar-web` y axe-core.

## Cuánto falta para la lluvia (17-10-2026)

Juanjo: «cuando haya previsión de lluvia puedes añadir donde corresponda que
empezará a llover en x horas o minutos (se actualizará en tiempo real) y la
hora prevista?», y «luego está la previsión de los 15 minutos, eso también
debe salir». Desde la 3.116.0, en «Ara» de la portada (desde la 3.188.0, el
recuadro va debajo de la gráfica y en «Ara» queda su primera línea; ADR 0118):

1. Si llueve, como antes: «Pluja a sobre · pararia cap a les…».
2. Si el radar la ve llegar (hasta unas 2 horas, también la del aviso de los
   15 minutos), en minutos y con la hora: «Pluja d’aquí a 24 minuts (cap a les
   11:50)»; la cuenta se actualiza sola cada 30 segundos, sin recargar.
3. Si no, la primera hora de las 24 siguientes con lluvia según la previsión
   (desde el 20 %, «possible pluja», como en la tabla), por horas y sin
   minutos, porque la previsión es horaria: «Possible pluja d’aquí a unes 6
   hores, cap a les 17 h (25 %)»; desde el 50 %, «Pluja prevista».

/ara del bot dice lo mismo, sin la cuenta en directo.

Destacado (17-10-2026, 3.123.0): Juanjo pidió destacar «Comença d'aquí a
unes 3 hores» («quizás en negrita? decide tu»). Va en una etiqueta del color
de la lluvia, como la de la parte alta, porque ya había pedido destacar con
un recurso visual y no con negrita; también la cuenta de la línea «Possible
pluja d'aquí a…» cuando hoy no llueve.

## Cambio del 17-10-2026 (3.126.0): distancia, mapa y sin «a 0 km/h»

Juanjo, ante un recuadro que solo decía «Pluja a sobre»: «aqui se puede poner
más informacion? por ejemplo distancia de la lluvia, un mapa donde se vea
montflorit y la lluvia (puede ser estatico…) … solo si se puede facilmente y
sin complicar más la visualizacion de la web». De la misma imagen de radar con
que se calcula cuándo llega (`prevision.radar`), el NAS añade a `radar`:

- `propera`: la lluvia más cercana que llega al suelo (`PLOU_MMH`), a 60 km o
  menos: distancia, rumbo y clase de intensidad. La web y /radar del bot
  dicen «La més propera, a 6 km al nord-oest (moderada).», salvo si está a
  menos de 1 km (ya es «Pluja a sobre»).
- `mapa`: el trozo de la imagen de 30 km alrededor de casa, una cifra por
  píxel (0 sin lluvia; 1-5, las franjas de intensidad de AEMET en mm/h:
  débil, moderada, fuerte, muy fuerte y torrencial), unos 4,5 KB; None si no
  llueve en ese cuadro. La web lo dibuja en SVG (`svgMapa`): una miniatura a
  la derecha del texto del recuadro (debajo si no cabe) que se amplía al
  pulsarla, con círculos cada 10 km, el norte, ocho poblaciones de
  referencia, la leyenda de las intensidades presentes y la hora y la fuente
  de la imagen. Sin servidores de mapas: la privacidad no cambia.

Además, sin movimiento (menos de 1 km/h) ya no se dice hacia dónde va: «va
cap al sud-oest a 0 km/h» no significaba nada (web y bot).

Las franjas de AEMET (2, 15, 30 y 60 mm/h) no coinciden con las del aviso
de lluvia en unos minutos (`pluja_arriba.intensitat`: 1 y 4 mm/h); queda por
decidir si se igualan. Validación: con la imagen real de RainViewer
desplazada para poner la lluvia cerca, en Chromium y Firefox, 320, 390 y
1280 px, claro y oscuro, catalán y castellano; pruebas de `propera`, `mapa`,
`textPropera` y /radar.

## Cambio del 17-10-2026 (3.127.0): mapa de verdad, flecha, enlace y textos

Juanjo, ante el mapa de la 3.126.0, que solo tenía círculos y puntos: «pero y
el mapa? se suupone que esto es un mapa». Ahora:

- **Fondo**: el Mapa base estándar gris del ICGC (© ICGC, CC BY 4.0), con la
  costa, las poblaciones, las carreteras y las comarcas, en una imagen fija de
  la propia web (`web/img/radar-fons.webp`, 524 × 524 px, 46 KB, hecha con
  `eines/fons_radar.py` a partir de las teselas del nivel 10, en la misma
  proyección que el radar). Al abrir la página no se pide nada a ningún
  servidor de mapas. El gris y no el de color, porque en este las carreteras
  van en naranja y se confundirían con la lluvia fuerte; la versión gris sin
  rótulos (`topografic-gris-mut`) tiene teselas que faltan. Va aclarado
  (opacidad 0,55 sobre blanco) para que destaque lo de encima («el mapa de
  fondo puede ser un poco mas claro»), también en tema oscuro, como el de los
  cortes de luz; lo de encima, con colores fijos. La lluvia, con opacidad 0,9.
- **Nombres**: los ocho de referencia, encima del mapa («ahora ya no se ve
  mucho»), con un contorno blanco semitransparente que no tapa la lluvia (con
  el opaco, el de «Martorell» vaciaba un píxel y parecía un cuadrado vacío).
  Los del ICGC quedan debajo, más tenues.
- **«30 km»** dentro de su círculo, como los otros: escrita por encima quedaba
  fuera del dibujo.
- **Movimiento**: una flecha abajo a la izquierda, con «moviment de la pluja»
  y la velocidad («un vector… y también la velocidad»; «no dice lo que es y
  debería decirlo»). Es uno solo para toda la lluvia, el mismo con que se
  calcula cuándo llega: flechas por foco dirían lo mismo repetido, y seguir
  cada foco es poco fiable con tormentas que nacen y se deshacen en diez
  minutos. Sin movimiento (menos de 1 km/h o no medido), sin flecha. Los datos
  llevan `graus`, que ya se calculaba. Una segunda flecha discontinua desde la
  lluvia más cercana, con lo que recorrería en una hora, se probó y se quitó:
  repetía la de la esquina («por que hay una flecha de puntos?»).
- **Enlace**: el nombre de la fuente del título del mapa ampliado lleva al
  radar en directo, como en el recuadro («aquí puedes poner un enlace
  clicable al radar en tiempo real?»).

**Textos que se contradecían.** Con la previsión dando lluvia a las 17 h y el
radar sin nada que se acercara, la página decía a la vez «Comença d'aquí a
menys d'una hora» y «No s'acosta pluja en 2 hores» («son mensajes
contrarios»). Los dos podían ser ciertos: el radar no ve la lluvia que aún no
se ha formado, y ese día las tormentas nacían donde no había nada. Pero la
frase del radar decía más de lo que sabe, y «Comença» hablaba de una hora del
49 %. Ahora:

- El recuadro dice solo lo que ve: «El radar no veu pluja que vingui cap
  aquí»; y, si la previsión da lluvia en las dos horas siguientes, «La
  previsió en dona d'aquí a menys d'una hora (49 %): seria pluja que es formi
  a prop, que el radar encara no veu.», con la misma hora y cifra que la
  etiqueta de la previsión. El /radar del bot, «El radar no veu pluja que
  vingui cap a Montflorit.».
- La etiqueta lleva la probabilidad y dice «Comença» desde el 50 % y «Pot
  començar» por debajo («ese me interesa que siga ahí, con las matizaciones
  que hagan falta»).

**¿Acierta el movimiento?** Juanjo: «el calculo de la velocidad y direccion
de la lluvia es correcto o habria que revisarlo?». El 17-10-2026 a las 17:00,
la advección de Meteocat daba 12 km/h hacia los 121°; el viento a 700 hPa de
Open-Meteo, 17 km/h del 298° (hacia los 118°): la misma dirección y algo más
deprisa, como es normal en las tormentas. El centro de la lluvia a 40 km
avanzó unos 20 km/h hacia el este, pero porque la lluvia pasó de 26 a 209 km²
con tormentas nuevas por delante, no por moverse más rápido. Los pares de
RainViewer daban de 0,2 a 44 km/h; como no concuerdan, el programa los
descarta y deja la lluvia quieta. El método solo se había comprobado con la
tarde del 06-10-2026 (ADR 0023) y el movimiento no se guardaba: desde la
3.127.0 lo registra `moviment_registre.py` (en cada pasada del NAS, sin
descargas nuevas), que compara la lluvia llevada hacia delante 30 y 60
minutos con la que ve después el mismo radar y con dejarla quieta, y la
dirección con el viento a 700 hPa. Con un mes de datos, el 17-11-2026, se
decide si hay que revisarlo.

Validación: `probar-web` con el mapa abierto (Chromium, Firefox y WebKit;
escritorio, móvil y tableta; claro y oscuro), catalán y castellano, con la
lluvia real del 17-10-2026; axe-core sin incidencias tras dos arreglos (la
miniatura, oculta a los lectores de pantalla dentro de su botón, que ya dice
qué es; la etiqueta «Comença…», con el azul oscuro del texto de lluvia, que
tenía un contraste de 4,2); prueba del registro con un chubasco que se
desplaza una distancia conocida.

En la 3.127.1, la leyenda del mapa ampliado solo nombra las intensidades que
se dibujan: el trozo de los datos (67 píxeles, unos 61 km) es algo mayor que
el cuadro de 60 km, y la lluvia de su borde ponía «moderada» y «forta» en
un mapa sin ninguna (visto en producción el 17-10-2026, con la 3.127.0).

En la 3.128.0 la etiqueta dice de qué es la cifra: «Pot començar d'aquí a una
hora (29 % en aquesta hora)», porque es la probabilidad de que llueva en esa
hora (0,2 mm o más), no la de que empiece (Juanjo: «este % que indica
exactamente?»). En el móvil la etiqueta se parte en dos líneas si no cabe.

En la 3.129.0, si el radar ve lluvia fuerte o más a 15 km o menos que no
llega a casa, el titular lo dice («Pluja molt forta a 10 km al nord, que de
moment no ve cap aquí», en azul, como «pot arribar») en lugar de «El radar no
veu pluja que vingui cap aquí» (`nowcast.forta`: la intensidad más alta en
ese radio y su punto más cercano). Juanjo, con truenos y a punto de llover:
«esta imagen es compatible con el mensaje?»; el radar veía una tormenta
torrencial a 10 km al norte que, con el movimiento, pasaba de largo, y el
recuadro solo nombraba la lluvia débil más cercana. Si el radar ve lluvia a
15 km o menos, la línea de la previsión ya no dice «seria pluja que es formi
a prop, que el radar encara no veu», que era falso, sino «la pluja de prop
pot créixer o desviar-se cap aquí». La línea «La més propera…» no se repite
si es el mismo punto que el titular. Lo mismo en /radar del bot. Esa tarde
el registro del movimiento daba más acierto a dejar la lluvia quieta que a
moverla (20 comparaciones, una sola tarde): las tormentas crecían más que se
desplazaban, y por eso el texto no promete que pasen de largo.

En la 3.131.0, el recuadro dice también cuándo la lluvia crece alrededor de
casa: «La pluja s'està formant a prop: a 15 km o menys n'hi ha el triple que
fa mitja hora» (o «fa mitja hora no n'hi havia»), en azul, con al menos 20
km² con lluvia a 15 km o menos en la última imagen de RainViewer y el doble
que en la de 30 minutos antes (`nowcast.creixement`, del mismo radar). Juanjo,
viendo la tormenta acercarse imagen a imagen aunque el movimiento la llevaba
de largo: «no se trata solo de la direccion de la lluvia sino de hacia donde
crece». Con las imágenes de esa tarde, la distancia de la lluvia más cercana
saltaba de 3 a 27 km y volvía a 7 (píxeles sueltos), y la tormenta fuerte no
se acercó sino que se formó: a las 18:24 la más cercana estaba a 28 km y a
las 18:30 había una a 8 km. Lo que creció sin parar fue la superficie con
lluvia a 15 km o menos (Meteocat: 0, 42, 67, 94 y 118 km² de 18:24 a 19:00).
La línea dice lo medido, no una hora de llegada; si anuncia la lluvia en
casa lo dirá un mes de registro (`creixement.csv`, docs/estadistica.md),
revisado junto con el del movimiento el 17-11-2026. Lo mismo en /radar.

En la 3.132.0 la línea cuenta lo que gana la lluvia, no cuántas veces crece:
sale si a 15 km o menos ha ganado 50 km² o más en media hora (unos 7 de cada
100 del círculo) y dice qué parte del terreno ocupa ahora y hace media hora:
«La pluja s'està formant a prop: ja ocupa el 31 % del terreny a 15 km o
menys; fa mitja hora, el 16 %» (o «gens»). Juanjo, ante la regla del doble,
que a las 19:20 no salía con 216 km² frente a 113: «no es lo mismo el doble
de 10km² que de 216». Con las imágenes de esa tarde, la regla nueva salta
desde las 18:36 en Meteocat (+50 km²) y desde las 18:40 en RainViewer
(+70), sigue a las 19:00 (+145) y a las 19:20 (+103), y no salta con un paso
de 10 a 20 km². Los 50 km² salen de una sola tarde y solo deciden cuándo se
dice lo medido; si sirve para anunciar la lluvia lo dirá el registro.

En la 3.134.0 el mapa ampliado dice dentro de la imagen, arriba a la
izquierda, quién lo ha hecho y con qué: el nombre de lo que se está mirando
(«Temps a Montflorit» en la web, «Montflorit al dia» dentro de la app de
Android, que la web reconoce por el referrer android-app://; «Temps a casa»
en la de casa), «Mapa d'elaboració pròpia» y el radar y la hora de la imagen.
Juanjo: «que se vea que es una elaboración de la propia app y no una captura
de otra web». Los nombres no se traducen; también lo dice la descripción
para lectores de pantalla.

## Cambio del 18-10-2026 (3.138.4): lluvia que miden las estaciones y el radar no ve

Con llovizna, las estaciones del barrio midieron lluvia y el radar no veía
nada encima de casa. El recuadro decía «Pluja a sobre · no s'acaba en 2
hores» junto a un mapa sin lluvia en el barrio, y Juanjo lo leyó como una
contradicción (llovía de verdad). Ahora, si llueve según las estaciones y el
radar no ve lluvia (ni probable ni posible) encima de casa en los próximos 5
minutos, el titular dice «Pluja a sobre segons les estacions del barri · el
radar no la veu», sin la hora de final, que saldría del radar. Lo mismo en
/radar del bot. Es el caso contrario de «segons el radar · cap estació del
barri no en mesura» (ADR 0101).

## Cambio del 18-10-2026 (3.138.6): el radar sube la tabla solo desde el 20 %

Los milímetros del radar llevado hacia delante subían una hora de la tabla
(«†») aunque su probabilidad fuera del 5 %, y el recuadro, que solo habla de
lluvia que llega desde `PROB_ATENCION` (20 %), decía «El radar no veu pluja
que vingui cap aquí». Ahora la probabilidad y los milímetros del radar solo
cuentan si su probabilidad llega a ese umbral. Solo rebaja casos dudosos: en
el registro de octubre, 1 de las 36 horas marcadas por el radar (ADR 0101).

## Cambio del 18-10-2026 (3.140.0): el plugim que solo ve el radar

A las 18:45 empezaba a lloviznar en casa y la web decía «El radar no veu pluja
que vingui cap aquí», con el radar de Meteocat pintando lluvia sobre el
barrio. Los dos radares la veían: 31 píxeles del Meteocat y 27 de RainViewer a
3 km o menos de casa, el más cercano a 400 m, todos de 0,1 a 0,4 mm/h, por
debajo de la lluvia que cuenta (`nowcast.PLOU_MMH`, 0,5 mm/h); las estaciones,
0 mm, porque el pluviómetro no recoge la llovizna. Con el registro de ecos
cercanos (1.756 pasadas desde el 10-10): sin nada a 3 km, llueve en las
estaciones en la hora siguiente el 2 % de las veces; con pocos píxeles
débiles, el 3 % (los ecos sueltos del 10-10); con muchos en un solo radar, el
28 %; con muchos en los dos, 4 pasadas, todas de este episodio.

Ahora, si los dos radares ven 15 píxeles débiles o más a 3 km o menos
(`casa.plugim_radar`, `config.PLUGIM_PX` y `PLUGIM_KM`) y ninguna estación mide
lluvia, el estado de la lluvia (ADR 0101) lleva `plugim`: el recuadro del radar
dice «El radar veu pluja molt feble a sobre (plugim), que les estacions no
mesuren», «Ara» dice «Plugim segons el radar» en vez de «No plou», y lo mismo
/ara y /radar del bot. No cambia la previsión ni los avisos. Como con la
niebla (ADR 0100), se pregunta a Juanjo por Telegram si llueve en casa, con
botones, de 7 a 22 h y como mucho cada 3 horas (`plugim.py`); sus respuestas,
en `registre/plugim-confirmacions.csv`, dirán si la señal acierta lo bastante
para usarla en la previsión, junto con los ecos cercanos, a partir del
07-11-2026. La pregunta y la lectura de respuestas de la niebla y del plugim
comparten `confirmacio.py`. Pruebas: `tests/test_plugim.py`, `test_web.py` y
`test_bot.py`; la portada, en Chromium, Firefox y WebKit con una simulación.

3.140.1: con plugim encima, el recuadro del radar y /radar ya no dicen «La més
propera, a 4 km…»: junto a «plugim a sobre» confundía (Juanjo, «quita la línea
de la más cercana cuando hay plugim»).

3.140.2: si el recuadro dice plugim, el mapa del radar (miniatura y ampliado)
lo pinta en lila claro, el color de la franja más baja del Meteocat, con
«plugim» en la leyenda. Juanjo: «si habla de llovizna el miniradar tiene que
mostrarla, de lo contrario no se entiende qué está diciendo»; la web de
RainViewer no pinta ecos tan débiles aunque sus datos los tengan. El mapa
(`nowcast.mapa`) lleva aparte los ecos de `FEBLE_MMH` a `PLOU_MMH` («febles»)
y sale también si solo hay eso; la web solo los pinta con plugim. El titular
no nombra radares: la condición ya es que lo vean los dos.

## Cambio del 18-10-2026 (3.140.3): la respuesta vale para cuando se responde

Juanjo respondió «No lo sé» a una pregunta del plugim porque la veía tarde y no
quería dar un dato falso: la respuesta se apuntaba con los datos del momento de
la pregunta. Como la pregunta dice «ahora» y se contesta mirando por la
ventana, ahora la respuesta vale para el momento en que se responde
(`confirmacio.respostes`): se apunta con su hora (`resposta_t`, la de la pasada
del reloj que la lee, cada minuto) y con lo que dicen los datos entonces (la
última pasada, de 6 minutos como mucho en modo aviso: píxeles de cada radar,
plugim y lluvia medida; en la niebla, la humedad de casa y Sabadell), y también
con lo que decían al preguntar (`pregunta_…`). Sin caducidad: cualquier
respuesta sirve (Juanjo: «30 minutos no es demasiado? la situación puede haber
cambiado totalmente»; descartados los botones que caducan, que perderían
respuestas). El mensaje dice «Apuntado a las 19:42: …». Las respuestas de antes
pasan sus datos a `pregunta_…` y quedan sin los del momento de responder.

3.140.4: la línea del recuadro que explica la lluvia de la previsión cuando el
radar no ve nada venir decía «La previsió en dona d'aquí a menys d'una hora
(37 %)…» («La previsión la da…» en castellano), sin que se supiera quién la
daba (Juanjo: «quien da la previsión? queda extraño así»). Ahora dice «La
previsió per hores sí que dona pluja a partir de les 20 h (37 %): pot ser pluja
de prop que creixi o es desviï cap aquí» (o «per a aquesta hora»), con la hora
en lugar de la cuenta atrás, que ya está en la etiqueta de arriba.

## Cambio del 28-10-2026 (3.206.0): la respuesta tardía dice para qué hora vale

Si la respuesta llega más de 30 minutos después de la pregunta, el mensaje
pide para qué hora vale, la de la pregunta o la de la respuesta, y la elección
va a la columna `val_per` (detalle en el ADR 0100).
