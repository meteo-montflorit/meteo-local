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
