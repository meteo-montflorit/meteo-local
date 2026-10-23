# 110. Página «Fiabilitat» y comparación con Meteocat y AEMET

Fecha: 2026-10-20 · Estado: aceptado

## Contexto

Desde la 3.112.0, el acierto de la previsión y el historial de cada día
estaban en la vista en grande de la gráfica, detrás del botón «Com encerta»
(ADR 0099). Juanjo, el 20-10-2026: «el com encerta del grafico creo que
debería pasarse a una página propia y quitarlo de ahí», «la mayoría de la
gente jamás lo utilizará y solo estorbaría», y pidió además «alguna prueba
estadística para ver cómo predice el tiempo», «una comparación en cómo lo
predice el propio meteocat para cerdanyola», «también estaría bien la
comparación con la prediccion de aemet para cerdanyola» y, «dado que la
pagina aprende», «una comparación semana a semana para ver si mejora con el
tiempo», dejando el periodo a criterio del agente. Para enlazarla: «por los
tres puntos y hazlo». Al ver la primera versión en el servidor local: «el
como acierta, llamale de otro modo y sobre todo falta claridad... texto
vertical, haz alguna grafica comparativa de lo que dices y no veo nada sobre
como aprende la web», y «en como aprende quiero q aparezcan las mejoras que
hay dia a dia».

## Decisión

- **Página propia, `fiabilitat.html` («Fiabilitat»; «Fiabilidad» en
  castellano)**, a la que se llega desde el menú ⋮ (`comu.menuMes`), debajo
  de «Com funciona». No es una pestaña. El nombre abarca lo que ofrece: cuánto
  acierta, frente a quién y cómo aprende («Com encerta» solo decía lo
  primero). Poco texto y gráficas comparativas, por este orden:
  - **Resumen**, con la antelación encima, en seis cifras grandes con su
    conclusión debajo: error de temperatura (y el sesgo), cuántas veces
    llueve cuando dice que lloverá (50 % o más) y cuántas no llueve cuando
    dice que no (menos del 20 %), diferencia con Meteocat y con AEMET, y si
    mejora con el tiempo.
  - **Semana a semana** y **Dia a dia**, que también dependen de la
    antelación y lo dicen («Amb la previsió feta 1 h abans. Es canvia a
    «Resum»»).
  - **Error según la antelación**, de 1 a 23 h, con la elegida marcada, que
    no depende del selector.
  - **Com aprèn**: una ficha por cada cosa que aprende (probabilidad de
    lluvia, temperatura, radar, cielo) con lo que usa ahora y, si espera
    datos, una barra con lo que lleva («17 de 30 hores de pluja per poder
    decidir»); **los cambios que ha hecho sola, con la fecha**; las gráficas
    de «la que fa servir» contra «la que prova» día a día, y una tabla de
    los últimos 10 días con las horas de lluvia y los dos errores.
  - Un solo desplegable con las cifras en tablas (la vista en tabla de las
    gráficas) y cómo se calcula.
  **Temperatura y lluvia, siempre las dos**, una gráfica para cada una con su
  título («Temperatura: error mitjà, en °C»; «Pluja: error, de 0 (perfecte) a
  1»). Hubo un selector Temperatura · Pluja y se quitó: solo cambiaba algunas
  gráficas y no se sabía qué se estaba viendo (Juanjo, 20-10-2026: «sin
  selector que confunde porque solo cambia alguna grafica», «esto que es?
  temperatura, lluvia???? debes identificar lo que haces» y «el usuario debe
  saber lo que está viendo en cada momento»). Por lo mismo, el selector de
  antelación va junto a lo que cambia y lo que depende de él lo dice.
  **La antelación, con un deslizador** de 1 a 23 h: se elige de una vez.
  Al principio llevaba encima 23 barras con el error de temperatura de cada
  antelación; se quitaron el mismo día (Juanjo: «quita las columnas de aquí,
  deja solo el deslizador»). Antes eran dos flechas
  que pasaban de una en una (Juanjo: «hay que pasar una a una. Haz algo util
  pero profesional y vistoso»). Es un `input type="range"` nativo: flechas
  del teclado, arrastre con el dedo y lector de pantalla.
  **Los textos, para cualquiera**: sin jerga («probabilitat habitual»,
  «diferència segura», «la que prova»). La lluvia, con lo que pasó de verdad
  («Quan diu que plourà: 54 % de les vegades, plou», con las horas); la
  seguridad, como «no és casualitat» o «encara pot ser casualitat»; el
  aprendizaje, «l'actual» y «la nova, en entrenament», sin cifras sueltas en
  las fichas (están en la tabla). El error de Brier y la comparación con la
  climatología se explican en el desplegable (Juanjo: «hazte a la idea de que
  hablas para gente sin conocimientos ni de esta web y con pocos estudios. No
  quiere decir dar información menos precisa, simplemente explicarlo bien»).
  Las gráficas tienen una sola escala (más abajo, mejor), leyenda, un rótulo
  al pasar el dedo o el ratón con los valores de cada serie, y cada serie su
  color y su trazo (la web, continuo; Meteocat, discontinuo; AEMET,
  punteado), con la paleta comprobada con el validador de paletas también
  para daltonismo, en claro y oscuro. La antelación y el día van en la
  dirección (`?h=6&dia=2026-10-15`), para que
  compartir dé lo mismo que se ve.
- **La vista en grande de la gráfica queda solo con la previsión**: sin el
  botón «Com encerta», sin las flechas de los días pasados y sin la
  antelación. Las opciones que se recuerdan (viento, parte baja y alta) no
  cambian.
- **El menú ⋮ también en el ordenador.** En la 3.164.0 se dejó en el
  ordenador la botonera entera a la vista, y el comentario del código y el
  ADR 0074 lo atribuían a Juanjo, que no lo había pedido. Desde la 3.165.0 la
  cabecera es igual en todas partes: compartir, la campana y ⋮ (con «Com
  funciona», «Com encerta», el idioma y el tema). De paso, en «Riera» el «?»
  enlazaba a `com-funciona.html#riera` y el menú no lo encontraba: ahora se
  busca por el principio de la dirección.
- **Las pruebas estadísticas** (`historial.py`), para cada antelación:
  - Temperatura: el error medio absoluto, como antes, y el **sesgo** (la
    media del error con signo: si suele dar más o menos temperatura).
  - Lluvia: el **error de Brier**, $\mathrm{BS} = \frac{1}{N}\sum (p_h -
    o_h)^2$, comparado con el de decir siempre la climatología $c$ (la parte
    de las horas con lluvia en todo el registro): $1 - \mathrm{BS} /
    \mathrm{BS}_c$, que la página dice como «encerta un 35 % més que dir
    sempre la probabilitat habitual». Si la diferencia con la climatología es
    segura se dice con la regla de siempre (`remostreig.seguretat`, ADR 0105:
    95 % de 2.000 remuestreos por días). La tabla de franjas (calibración)
    sigue, en el desplegable.
- **Semana a semana** (`setmanes`), de lunes a domingo: el error de la
  temperatura y la mejora de la lluvia sobre la climatología (fija, la de
  todo el registro, para que las semanas se puedan comparar). La semana en
  curso va marcada. Se eligió la semana: un día está dominado por el tiempo
  que hace (un día de lluvia cambia toda la cifra) y un mes tarda demasiado
  en dar el primer dato. **Si mejora** (`millora`): las 4 últimas semanas
  completas contra las 4 anteriores (el «30 días contra 30» que había, en
  semanas), con el error medio por hora de cada periodo y un remuestreo por
  días de cada periodo por separado, porque no tienen los mismos casos
  (`remostreig.seguretat_periodes`, la misma regla del 95 %). Hasta tener 8
  semanas completas, la página dice cuántas hay.
- **Frente a Meteocat y AEMET** (`previsio_oficial.py`, `historial.comparacio`):
  - Se apuntan en el NAS, en cada pasada de `publica.sh`, la previsión
    municipal por horas de Meteocat para Cerdanyola
    (`/pronostic/v1/municipalHoraria/082665`: temperatura y milímetros por
    hora, 72 horas) cada 3 horas, y la predicción horaria de AEMET para el
    municipio 08266 (temperatura y milímetros por hora y probabilidad por
    tramos de 6 horas, con la hora en que se elaboró) cada hora, en
    `registre/previsio-oficial-AAAA-MM.jsonl`. Si nada ha cambiado, una línea
    corta que dice que seguía vigente.
  - Meteocat: el plan es de 1.500 consultas al mes para todo lo de
    predicción, y la reserva de los avisos (`smp.py`, ADR 0109) puede
    necesitar una cada 30 minutos. Por eso, como mucho 260 al mes y ninguna
    si la reserva ha consultado la API en las últimas 2 horas: los avisos van
    primero. AEMET no tiene un límite mensual que preocupe.
  - **Cada previsión oficial se compara con la que publicaba la web en el
    mismo momento** (la publicación más cercana, a 35 minutos como mucho), en
    las mismas horas y con la misma antelación (de la lectura al principio de
    la hora). La temperatura oficial del tramo es la media de su principio y
    su final, como la de la web y la medida. La lluvia oficial es de sí o no
    (0,2 mm o más en la hora), y su Brier es el de una previsión del 0 o del
    100 %. Se dice en qué parte de los remuestreos por días acierta más la
    web (`seguretat`): con un 95 % o más, la web acierta más; con un 5 % o
    menos, la oficial.
  - En la semana, la diferencia de error de temperatura con cada oficial en
    las horas comparadas («0,3 menys»), en una tabla aparte: ayuda a ver si
    una mejora es de la web o de que la semana fue fácil.
  - La página dice que sus previsiones son para todo el municipio y la de la
    web para Montflorit. Ni Meteocat ni AEMET guardan sus previsiones
    pasadas: la comparación empieza el 20-10-2026.
- **El aprendizaje, en el índice** (`historial.aprenentatge`): de lo que
  deja cada día el NAS en `aprenentatge/`, el método vigente de la lluvia y
  de la temperatura con el error del candidato y del vigente y lo que le
  falta para decidir (`historial.csv`, `MIN_HORES_PLUJA`,
  `MIN_DIES_TEMPERATURA`), el radar preferido con su seguridad
  (`radar-font.json`) y los pesos del cielo (`nuvols-pesos.json`). **Los
  cambios** (`historial.canvis`): el día en que cambió el método de la lluvia
  o de la temperatura, y desde cuándo rigen el radar y la regla del final de
  la lluvia (de esos dos solo se guarda la vigente; las pasadas de
  `radar-fonts-*.jsonl` no sirven, porque cambian de radar cuando uno falla).
- `FORMAT` del historial pasa a 5 (el sesgo y el Brier de cada día): los días
  se rehacen por tandas. Las claves: la de Meteocat ya estaba en el NAS; la de
  AEMET se copia a `home/.config/meteo-local/aemet.env`.

## Riesgos e hipótesis

- **Hipótesis por comprobar con las primeras lluvias**: que los milímetros de
  la hora que dan Meteocat («data» en UTC) y AEMET («periodo» HH) son los
  caídos en la hora que acaba a esa hora. Si fuera la que empieza, la lluvia
  oficial quedaría desplazada una hora y saldría peor de lo que es. Se
  comprobará comparando la hora de la lluvia prevista con la medida en los
  primeros episodios.
- Meteocat se lee cada 3 horas: para cada hora solo hay una antelación de
  cada tres con su previsión, así que tiene menos horas comparadas que AEMET.
  Como se compara con la de la web del mismo momento, la frecuencia no da
  ventaja a nadie.
- La probabilidad por tramos de 6 horas de AEMET se apunta pero todavía no se
  compara: la de la web es por horas y combinarlas exige una suposición sobre
  la relación entre las horas de un mismo tramo. Queda pendiente.
- Con pocas horas de lluvia (en octubre, unas 20 de 270), la lluvia tardará
  semanas en dar diferencias seguras; la página lo dice.

## Validación

- Pruebas: `tests/test_previsio_oficial.py` (lectura de las dos respuestas,
  el «-0.0» de Meteocat, el «Ip» de AEMET, los tramos que pasan de
  medianoche, el ritmo de cada fuente, la cesión a la reserva de avisos y el
  tope mensual, que un error no pare la otra fuente);
  `tests/test_historial_grafica.py` (sesgo, Brier y climatología, semanas,
  «si mejora» con 8 semanas, la comparación con la previsión oficial del
  mismo momento, el aprendizaje y sus cambios con fecha); `tests/test_remostreig.py` (periodos con casos
  distintos); `tests/test_web.py` (los textos de la página).
- Con el registro real del NAS (4 al 20-10-2026), a 1 h: 0,67 °C de error,
  sesgo −0,2 °C; la lluvia, un 35 % mejor que la climatología (seguridad del
  88 %, aún no segura); 3 semanas, «si mejora» todavía sin datos.
- Las consultas reales a las dos APIs el 20-10-2026: 72 horas de Meteocat y
  47 de AEMET (elaborada a las 06:13).
- La página, en Chromium, Firefox y WebKit, escritorio y móvil, claro y
  oscuro, sin errores ni desbordamiento (también a 360, 393 y 412 px en las
  dos lenguas, con el desplegable abierto); con previsiones oficiales
  simuladas para ver la comparación y el aprendizaje real del NAS. axe-core
  sin fallos en la página y en el menú ⋮ abierto.

**Fuera del menú mientras haya pocos datos** (20-10-2026, 3.167.2). Con tres
semanas de la web y un solo día de Meteocat y AEMET, la página dice todavía
poco. Se quita del menú ⋮ (`MENU_FIABILITAT` en `web/comu.js`) y de la lista
de «Com funciona»; la página sigue en su dirección, enlazada desde «Fonts i
crèdits», donde se explica para qué se leen las previsiones oficiales (Juanjo:
«quita el enlace de fiabilidad del menu de 3 puntos, lo pondremos cuando haya
más datos»). Para volver a ponerla: `MENU_FIABILITAT = true` y la línea de
«Com funciona» con su traducción (está en el historial de este ADR).

**De vuelta en el menú** (23-10-2026, 3.192.1). Con 20 días de la web (414
horas de temperatura, 28 de lluvia prevista) y tres de Meteocat y AEMET (18 y
69 horas comparadas en temperatura, con diferencia segura), hay datos que
publicar, aunque no todos (Juanjo: «me avisarás cuando la página fiabilitat
tenga datos publicables? aunque no sean todos»; «sí, publica»). Los apartados
sin bastantes datos ya dicen en la página cuándo los tendrán («si mejora»,
con 8 semanas; las correcciones nuevas). La hipótesis de la hora de los
milímetros oficiales sigue sin comprobar: desde que se apuntan (20-10-2026,
9:08) la estación no ha medido lluvia, así que por ahora no cambia la
comparación; se comprobará con la primera lluvia.

**Datos en lugar de frases fijas** (20-10-2026, 3.168.0). Las fichas del
radar y de las nubes solo decían cuál se usa (Juanjo: «esto es solo
información estática, por qué no pones los datos de quien acierta y se
equivoca más? un diagrama de barras»). Ahora `historial.aprenentatge` exporta
el error de cada radar (Brier de `radar_fonts.compara`, con los casos) y el de
cada modelo del cielo y de la media que se usa (`nuvols.compara`, en puntos de
cielo tapado), y cada ficha los dibuja en barras, con la que usa la web en
color, y lo dice en una frase («RainViewer se equivoca un 29 % menos que
Meteocat»). Si los datos no traen esas cifras, queda la frase de antes. Y las
gráficas dicen qué es cada punto: «de cada semana» y «de cada día» en el
título, y una nota bajo la semanal («Cada punto es una semana, con el día en
que empieza»), porque las fechas del eje se leían como días (Juanjo: «y donde
pone que es una semana? no lo dice en ningun lado»).

**La humedad en «Com aprèn»** (21-10-2026, 3.171.0; Juanjo: «añade estos
datos a la pagina de fiabilitat»). Una ficha «Humitat» con el resultado del
año de casa en barras (corregida y sin corregir, en puntos de humedad) y lo
que lleva el aprendizaje del barrio, su gráfica día a día y sus cambios en la
lista. Los datos, de `historial.humitat` (ADR 0114).
