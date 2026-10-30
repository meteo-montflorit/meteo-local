# 29. Página «Si surts» y estado de los trenes

Fecha: 2026-10-07 · Estado: aceptado

## Contexto

La página del trayecto («Moto o cotxe?») recomendaba un medio para un viaje
fijo. Juanjo quiso generalizarla «para que fuese útil para todo el barrio»:
que cada uno ponga su hora de salida y de vuelta y reciba recomendaciones de
ropa, transporte y lo que haga falta. Al día siguiente de un temporal, con
Rodalies parado, preguntó además si se podía saber si funcionaban los trenes
y otros transportes.

## Decisión

- **Una página nueva en Temps a Montflorit**, «Si surts» (`web/sortir.html` y
  `web/sortir.js`), en catalán y castellano, con un menú «El temps · Si
  surts» con iconos. Todo se calcula en el navegador a partir de la previsión
  hora a hora que ya se publica; el servidor solo añade el índice UV y el
  estado de los trenes. No hay destino: los datos de Montflorit valen para
  moverse por la zona, y la página lo dice.
- **Dos selectores**: hora de salida («Ara» o cualquier hora de la tabla) y de
  vuelta (por defecto, 3 horas después).
- **Un veredicto por medio para toda la salida** (ida y vuelta, porque quien va
  en moto vuelve en moto): a pie, bici o patinete, moto, coche y transporte
  público, en verde, ámbar o rojo con el motivo. Coche y transporte público
  van por separado, porque uno puede ir bien y el otro no (Juanjo, 07-10-2026).
  Umbrales en `web/sortir.js`: los de lluvia son los del trayecto, comprobados
  con datos, salvo en moto y en bici, que desde el 08-10-2026 deciden solo por
  la probabilidad (40 % y 10 %, ADR 0047); los de viento y frío de bici y moto, una primera propuesta que la
  página declara sin comprobar. El coche no sale «bé» con lluvia (auditoría
  del 08-10-2026, antes solo miraba el viento). Desde el 18-10-2026 (ADR
  0039), con los umbrales de Meteocat de los peligros: más de 40 mm medidos
  en la última media hora, si se sale ahora, o más de 90 mm previstos en 3
  horas, «no»; más de 20 o de 60, lluvia probable o hielo (1 °C), «compte»;
  posible, se dice sin cambiar el nivel.
  «Sense pluja ni vent fort» solo cuando ninguna hora del viaje la ve.
- **Avisos de AEMET por lluvia o tormentas**: cuentan como lluvia probable,
  como en el trayecto. Si son lo único que la ve (probabilidad, que ya lleva el
  radar, por debajo del 20 %, menos de 0,2 mm en los modelos y ninguna
  estación con lluvia), el veredicto se mantiene, pero el motivo lo dice: «Avís
  de l'AEMET per pluja a l'anada (18 h): ni el radar, ni les estacions, ni els
  models hi veuen pluja», y los consejos hablan del aviso y no del riesgo de
  lluvia. Es el criterio del ADR 0008 para los planes de Protección Civil. Lo
  pidió Juanjo el 07-10-2026, con un aviso amarillo hasta las 20 h, el cielo
  despejado y un 1 %: la página decía «Pluja probable». **Desde el
  08-10-2026, en moto y en bici el aviso solo lleva a «compte»**, con el mismo
  motivo y «porta l'impermeable» en moto (ADR 0047): ese día desaconsejó la
  moto y no llovió.
- **Transporte público según los trenes**: «Bé» si circulan todos, «Amb
  incidències» si alguno no circula, va por carretera o tiene avisos, «Sense
  trens» si no circula ninguno. El estado de cada línea iba en un bloque
  «Trens ara» debajo de las fichas; desde el 09-10-2026 va dentro de la ficha,
  plegado («Estat de cada línia»), para no tener que saltar a otro sitio de la
  página (Juanjo: «creo que debería estar todo junto», ADR 0052). El enlace
  `sortir.html#trens` de los avisos abre ese plegable.
- **Ropa por medio**, según la temperatura que se nota a la ida y a la vuelta:
  con la velocidad del medio en bici (18 km/h) y en moto (45 km/h), y con el
  viento previsto a pie, en coche y en transporte público (el rato a pie hasta
  el coche o la estación), con el índice de Environment Canada (10 °C o menos).
  A pie, ocho tramos, de «Màniga curta» (más de 24 °C) a «Abric, gorro, bufanda
  i guants» (0 °C o menos); en bici, manga corta desde 21 °C. Si la vuelta pide
  otra prenda, se dice aparte con su hora y temperatura, en lugar del antiguo
  «millor capes» (Juanjo pidió el 07-10-2026 distinguir manga corta y larga y
  que fuese «algo más completo… sin caer en tonterías»). En moto, una sola
  chaqueta para toda la salida, la del momento más frío, porque no se cambia por
  el camino. Se dejan fuera pantalón, calzado y humedad: dependen de cada
  persona y la previsión no trae humedad. **Consejos**: lluvia que empieza o
  acaba, cambio de temperatura, protector solar, gorra y gafas de sol (UV 3 o
  más), salida o vuelta de noche y calor (32 °C o más).
- **Cada uno elige qué medios ve**: casillas con icono, en verde (✓) o rojo
  (✕), guardadas en el navegador (`localStorage`); sin «Transport públic» no
  sale el bloque de los trenes. Una explicación corta desaparece tras la
  primera vez que se desmarca uno. En pantalla ancha, las fichas en columnas.
- **Trenes** (`trens.py`): R4, R7 y R8 de Rodalies y S2 de FGC, las que paran
  en el término de Cerdanyola (la S1 no). Avisos y posición en tiempo real de
  Renfe (GTFS-RT en JSON) y de FGC (GTFS-RT en protobuf, leído con un lector
  mínimo propio: el contenedor no tiene la biblioteca). Una línea circula si
  en la última hora se ha visto un tren suyo moviéndose a 6 km o menos de su
  estación: un tren parado también envía su posición, y el 07-10-2026 la R4
  circulaba solo por el tramo sur. Estados: «Sense incidències», «Amb
  incidències», «Servei per carretera», «Sense trens» y «Fora d'horari». Los
  avisos se muestran en el idioma en que los publica el operador, sin
  traducirlos (Juanjo, 07-10-2026); Renfe marca como castellano también el
  texto catalán, y se distinguen por el contenido.
- **Dónde lo explican los operadores**: «Estat del servei: Rodalies · FGC ·
  Busos de l'AMB», una sola vez, en el bloque de trenes. Rodalies publica las
  incidencias en su portada; FGC remite el estado del servicio a su cuenta de
  X.
- **Aviso de responsabilidad** junto a los trenes y en los créditos: los
  datos de terceros se consultan automáticamente y el autor no se hace
  responsable de su exactitud (Juanjo, 07-10-2026).

## Alternativas descartadas

- **Pedir el destino**: complica la página y, a esta distancia, apenas cambia
  la previsión.
- **Recomendar un solo medio**: cada vecino tiene medios distintos.
- **Autobuses urbanos de Cerdanyola (CV1, CV3, CV4)**: la AMB publica en
  abierto el tiempo real de sus autobuses, pero el 07-10-2026 las CV no
  aparecían. Un aviso de un solo uso del vigía del NAS
  (`busos-cv-temps-real`) comprueba hasta el 09-10-2026 si aparecen; si lo
  hacen, se añaden. Del B4 interurbano no se ha encontrado tiempo real.
- **Cruzar los viajes en tiempo real con el horario oficial** para saber si
  paran en Cerdanyola: el 07-10-2026 la R4 hacía solo el tramo sur con los
  identificadores de los viajes completos.
- **Retrasos**: Renfe los publica tren a tren, pero «Sense incidències» se
  refiere a los avisos; se añadirán si hace falta.
- **Polen y calidad del aire**: fuentes nuevas que mantener, fuera del núcleo.
  Las incidencias de tráfico, que también estaban aquí, se añadieron el
  09-10-2026 (ADR 0052).

## Cambio del 09-10-2026 (3.36.0): manda el aviso oficial

La R8 salía «Sense trens» con el aviso de Rodalies «Circulació ferroviària a
tot el recorregut» (el más nuevo) y otro más viejo de servicio por carretera:
Juanjo, «es confuso». Ahora, si el aviso de servicio más reciente (con fecha)
dice que hay circulación ferroviaria y en la última hora no se ha visto ningún
tren, la línea sale «Amb incidències» y se dice la contradicción («Rodalies
diu que hi ha circulació ferroviària, però a l'última hora no s'ha vist cap
tren a prop de l'estació»), como con los avisos del tiempo: lo oficial manda y
la contradicción se dice. Y de los avisos de servicio vigentes solo se muestra
el más nuevo: los anteriores ya no valen.

## Cambio del 13-10-2026 (3.81.4): los trenes que pasan entre dos consultas

La R8 salía «Sense trens» con el aviso de Rodalies «Circulació normalitzada.»
(16:47). Juanjo: «no es coherente». Comprobado ese día a las 18:50:

- **El feed de Renfe traía todos los trenes**: los dos de la R8 que según el
  horario (GTFS de Renfe del 13-10-2026) circulaban, y 17 de los 18 de la R4.
- **La R8 lleva un tren por hora y sentido, y los dos se cruzan en
  Cerdanyola Universitat** (a las :49 y :50). Cada uno está dentro del radio
  de 6 km unos 12 a 14 minutos (de Sant Cugat Coll Favà a Santa Perpètua
  Riera de Caldes, con Rubí Can Vallhonrat a 6,9 km y Santa Perpètua a 6,8).
  Con consultas cada 15 minutos, unos minutos de retraso bastan para que
  ninguna lo vea dentro del radio. El NAS la había visto por última vez a las
  17:07: los trenes de las 17:49 y las 17:50 no se detectaron, y a las 18:45
  la línea salía «Sense trens».
- **«Circulació normalitzada» no se reconocía como aviso de servicio**: ni
  decidía, como «Circulació ferroviària a tot el recorregut» (cambio del
  09-10-2026), ni se tenía por aviso de servicio normal (ADR 0078).

Decisión:

- **Un tren también cuenta si ha pasado por la estación entre dos
  consultas**: si se ha movido 300 m o más y el tramo recto entre su posición
  anterior y la de ahora pasa a 6 km o menos de la estación de su línea
  (`km_al_tram`). La posición anterior solo vale si es de hace 40 minutos o
  menos, como antes. Un tren que se mueve lejos de la estación, por un mismo
  lado, sigue sin contar: la R4 por el tramo sur del 07-10-2026 seguiría
  saliendo «Sense trens».
- **«Circulació normalitzada» / «Circulación normalizada» es un aviso de
  servicio y de servicio normal**: con trenes vistos, la línea sale «Sense
  incidències»; sin trenes en la última hora, «Amb incidències» con la
  contradicción dicha, como el 09-10-2026.
- Alternativa descartada: **ampliar la ventana o el radio de la R8**. Con un
  retraso que se repite cada hora (los trenes pasan siempre a la misma hora
  y las consultas también), ninguna ventana evita el fallo; un radio mayor
  dejaría de distinguir un servicio parcial.

## Consecuencias

- Los datos públicos llevan `trens` y, en cada hora, `uv`.
- Dos peticiones más a Renfe (unos 225 KB) y dos a FGC por pasada, y una a
  Open-Meteo para el índice UV.
- El NAS guarda las posiciones de la pasada anterior en
  `/estat/trens-posicions.json`.

## Evidencia

- Datos de Renfe y FGC con licencia CC BY 4.0 (metadatos de data.renfe.com y
  de dadesobertes.fgc.cat, consultados el 07-10-2026).
- 07-10-2026, 07:51: alerta de Renfe para R1-R8 «Per causes alienes a
  Rodalies no es pot garantir la prestació del servei», dos trenes de la R7
  quietos en Montcada Bifurcació y Cerdanyola Universitat, R8 con servicio por
  carretera y trenes de la R4 moviéndose solo en el tramo sur. Coincide con la
  prensa: toda la red parada por la negativa de los maquinistas a circular
  tras el temporal.
- El índice UV solo lo da el modelo por defecto de Open-Meteo; los de
  Météo-France, ECMWF e ICON lo dan vacío (07-10-2026).

## Riesgos y limitaciones

- Los umbrales de bici, patinete y a pie no están comprobados con datos, ni
  los tramos de ropa, que son orientativos: no hay fuente oficial que diga a
  qué temperatura se lleva cada prenda.
- Con trenes cada 30 minutos, una línea puede tardar hasta una hora en pasar a
  «Sense trens» tras parar.
- Si Renfe o FGC cambian el formato de sus datos, la línea queda «Sense dades».
- El lector de protobuf solo lee los campos de los avisos que se usan.

## Validación

`tests/test_web.py` (lluvia que solo ve el aviso de AEMET, tramos de ropa, viento a pie, otra prenda a la vuelta, una
sola chaqueta en moto, bici), `tests/test_trens.py` (protobuf, idiomas, trenes parados, lejos de la estación,
vistos hace poco, estados y orden de los avisos) y `tests/test_montflorit.py`
(menú, página pública, palabras permitidas, castellano). La página, probada en
Chromium, Firefox y WebKit, en escritorio, móvil y tableta, con tema claro y
oscuro, y axe-core sin incidencias, con los datos reales del 07-10-2026 (R4 y
R7 sin trenes, R8 por carretera, S2 sin incidencias). Las casillas, probadas al
desmarcar, recargar y volver a marcar.

## Cambio del 18-10-2026 (3.138.5): «per carretera», solo si el tramo pasa por Cerdanyola

El revisor (ADR 0101) encontró la R4 «Servei per carretera» con un aviso de
Rodalies que decía «Servei complementari per carretera entre Terrassa
Nord-Manresa», lejos de Cerdanyola. Bastaba la palabra «carretera» en un aviso
propio de la línea. Ahora `trens.carretera_passa` busca el tramo en la frase
del servicio por carretera y lo sitúa con las paradas de la línea en orden
(`config.TRENS_PARADES`, de la API de la web de Rodalies del 18-10-2026,
también con las formas cortas de los avisos: «Terrassa Nord», «P.Catalunya»,
«Sants»). Solo cuenta si el tramo pasa por la estación de Cerdanyola de la
línea o acaba en ella; si el aviso no nombra un tramo que se pueda situar
(«en tot el seu recorregut»), cuenta como antes, porque no se puede descartar.
Con el aviso del 18-10-2026 la R4 sale «Amb incidències». Si Rodalies cambia
las paradas de una línea, hay que actualizar la lista; un nombre que no esté
en ella deja el aviso como estaba antes de este cambio.
