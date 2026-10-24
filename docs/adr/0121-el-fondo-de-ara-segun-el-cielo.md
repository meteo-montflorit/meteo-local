# 121. El fondo de «Ara» según el cielo, con dibujos

Fecha: 2026-10-22 · Estado: aceptado

## Contexto

Desde la portada nueva (ADR 0118), la tarjeta «Ara» tenía siempre el mismo
fondo azul marino, hiciera el tiempo que hiciera. Juanjo preguntó si el fondo
podía «amoldarse a lo que anuncia» y si podía llevar «algún sol o nubes
dibujados». El agente propuso un color para cada cielo con el texto blanco y
el icono de líneas de la gráfica en grande; Juanjo lo vio en una simulación
local y lo rechazó: «son azules muy feos y todo muy parecido». Siguieron tres
simulaciones más, con los cambios que él fue pidiendo: fondos con dibujos
(«el de tormentas es por rayos, no?», estrellas de noche), la salida y la
puesta del sol solo cuando el cielo deja verlas, pero también con cubierto y
lluvia «como el nuboso», más estrellas en la noche despejada y «dibujos más
realistas» en lugar de los iconos de líneas. Pidió publicarlo el mismo día.

## Decisión

- **Cielo**: el del primer tramo de la frase de arriba (`tramsFrase`, el mismo
  que dice la frase): despejado, poco nuboso, nuboso (medio o muy nuboso),
  cubierto o niebla. Si ahora llueve (medido o con el radar encima), lluvia;
  con código de tormenta en la hora, tormenta. Lo mismo que dice el resto de
  la portada (ADR 0101).
- **Momento**: según la altura del sol ahora (`alturaSol`): de noche por
  debajo de −6°; la salida o la puesta del sol entre −6° y +6° (el crepúsculo
  civil y la primera media hora larga de sol); de día, por encima.
- **Cambia a su hora** (desde la 3.186.0; Juanjo, 22-10-2026): la tarjeta se
  rehace con cada lectura de los datos, y además, mientras el sol está entre
  8° bajo el horizonte y 8° sobre él, el fondo y el dibujo se vuelven a
  decidir cada minuto (`posaCel`), sin descargar nada. Así el amanecer, la
  puesta y la noche no llegan hasta 15 minutos tarde. El 22-10-2026, en
  Montflorit: amanecer de 7:44 a 8:50 y puesta de 18:22 a 19:29.
- **Fondo** (`web/estil.css`, clases `cel-…` de `.heroi`): un degradado y unos
  dibujos para cada caso. De día: cielo azul con resplandor de sol; poco
  nuboso, con nubes blancas; gris perla con nubes; gris plomo con nubes
  oscuras; bancos de niebla; lluvia con gotas; tormenta morada con rayos. De
  noche: estrellas (pocas si hay alguna nube) o nubes azuladas si está
  cubierto. Al salir o ponerse el sol: degradado azul, rosa y naranja si está
  despejado o poco nuboso (con las nubes teñidas), y un resplandor cálido
  abajo y en las nubes bajas si está nuboso, cubierto o llueve.
- **Texto**: oscuro sobre los cielos claros y blanco sobre los oscuros;
  todos pasan de 4,5:1, también la línea en gris suave.
- **Dibujo**: un dibujo realista del cielo a la derecha de la temperatura, de
  [Meteocons](https://meteocons.com/) (Bas Milius, licencia MIT, paquete
  `@meteocons/svg-static` 0.1.0, estilo «fill»), en `web/img/meteocons/` con
  su licencia, y acreditado en «Fonts». Es decorativo (`alt=""`): el cielo ya
  lo dice la frase.
- **La parte alta, debajo de la temperatura y sin color** (desde la 3.184.0):
  en el móvil, la etiqueta de color al lado de la temperatura empujaba el
  dibujo fuera de la tarjeta, y Juanjo la veía desentonar. Para que la
  tarjeta no crezca, sin la línea de la humedad y la presión, que se pueden
  ver en la gráfica (Juanjo, 22-10-2026: «podemos prescindir de la humedad y
  presión»). La temperatura no se parte en dos líneas: si falta sitio,
  encoge el dibujo.
- **Los dibujos del fondo** son propios, en SVG (`web/img/cel/`), y los hace
  `eines/fons_cel.py` con una semilla fija.

## Alternativas descartadas

- **Texto blanco siempre**: obliga a fondos oscuros, que salían azules
  parecidos entre sí. Juanjo los rechazó.
- **Un degradado del cielo de un tramo al del siguiente**: con fondos claros
  y oscuros, el texto tendría que cambiar de color a media tarjeta. Lo que
  viene después ya lo dice la frase.
- **Los iconos de líneas de la gráfica en grande**: sobre los fondos
  dibujados quedaban «artificiales». En la gráfica y en «Per hores» siguen los
  de líneas, que en pequeño y en fila se leen mejor.
- **Dibujos propios del cielo**: más trabajo y más difícil de mantener que un
  juego completo y coherente con licencia libre.
- **Animación** (estrellas que titilan, relámpagos): distrae a quien lee y
  gasta batería; no se ha hecho.

## Consecuencias

- La tarjeta cambia de aspecto a lo largo del día; el tema oscuro de la web
  no la cambia.
- Unos 50 KB más de imágenes, que el navegador guarda.
- Si Meteocons cambia o desaparece, los dibujos copiados siguen sirviendo.

## Evidencia

- Licencia MIT de Meteocons: repositorio `basmilius/meteocons` (antes
  `weather-icons`) y el `LICENSE` del paquete de npm, copiado en
  `web/img/meteocons/LICENSE`.
- Contraste: axe-core (WCAG 2 AA) sin fallos en los 16 casos simulados, en
  tema claro y oscuro, móvil y ordenador.

## Validación

- `tests/test_web.py` (`test_el_fons_i_el_dibuix_d_ara_segons_el_cel`): cada
  cielo de día, de noche, al salir y al ponerse el sol, y con lluvia y
  tormenta.
- Simulación local con todos los casos, revisada por Juanjo en pantalla el
  22-10-2026; Chromium, Firefox y WebKit, de 360 a 1280 px, sin errores ni
  imágenes que no carguen.

## Cambio del 24-10-2026 (3.197.0): el cubierto de día, gris claro

Juanjo, ante la tarjeta con el cielo cubierto a media mañana: «esta tarjeta tan
oscura que hay ahora es correcta?». Lo era (el gris plomo con nubes oscuras),
pero parecía de noche: «no se trata de clarearlo todo sino que no parezca de
noche. Más nubes, que se vea que son nubes oscuras, pero no tanto como
ahora», y mandó una foto del cielo de ese momento: un gris uniforme y frío
con manchas suaves algo más oscuras y algo más claras, sin nubes con contorno.
Con texto blanco el gris no puede ser tan claro (para 4,5:1 el fondo tiene que
quedar por debajo de una luminancia de 0,18), así que el agente le enseñó tres
versiones en local: la de antes; texto blanco con manchas, lo más claro posible;
y gris claro con texto oscuro. Juanjo eligió la tercera («Ok, c»).

- `.heroi.cel-cobert` (solo el cubierto de día): degradado `#b3b8c0 → #a3a9b2`
  con `img/cel/cobert-dia-clar.svg`, manchas claras y oscuras muy difuminadas
  (`eines/fons_cel.py`, `taques`), texto `#0b121a` y línea `#111a24` (desde la 3.197.1), y las
  etiquetas («No plou», el viento) con el fondo de los cielos claros. El
  cubierto de noche, con lluvia y al amanecer no cambian.
- Contraste medido sobre el fondo sin el texto, en el ordenador y el móvil: el
  texto, 6,2:1; la línea, 4,6:1, en el punto más oscuro de la zona del texto.
- Desde la 3.197.1, más diferencia entre las manchas (Juanjo, 24-10-2026:
  «incrementa algo la diferencia entre nubosidad más oscura y clara» y «la zona
  oscura son nubes más negras»): claras `#f1f3f6` al 65 % y oscuras `#5a616b`
  al 55 %. Con ellas el texto anterior se quedaba en 4,0:1, así que el texto
  pasa a `#0b121a` (5,0:1) y la línea a `#111a24` (4,7:1), medidos igual. Más
  oscuras no caben: el texto tendría que ser negro.
- Se distingue de «nuboso» (gris perla azulado con nubes blancas) por ser gris
  plano y sin nubes dibujadas.

