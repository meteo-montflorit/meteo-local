# 119. Cada ficha de «Si surts», en grande y con su enlace

Fecha: 2026-10-22 · Estado: aceptado

## Contexto

Juanjo pidió (22-10-2026): «quiero que se pueda compartir cada tarjeta.
haciendo clic el titulo de la tarjeta se abre en un modal con todo desplegado.
un botón compartir en cada tarjeta que muestre la tarjeta abierta. La idea es
mejorar la visualizacion si crees que es mejor hacerlo de otro modo puedes
hacerlo».

Hasta ahora, los plegables de una ficha («Trànsit ara: 4 incidències…»,
«Estat de cada línia») se abrían dentro de la cuadrícula, y la ficha pasaba a
ocupar todo el ancho (`.mitja:has(> .mitja-plec[open])`): en el ordenador
movía las demás fichas. Solo la página entera tenía enlace para compartir.

## Decisión

- **El título de cada ficha es un botón** que la abre en grande, en una
  ventana (`dialog.vista-mitja`) como la de la gráfica (ADR 0096): arriba, el
  medio, compartir y la X; debajo, las horas elegidas («Surto: Ara · Torno:
  11:00») y el consejo; después, el motivo, la ropa y todos los plegables
  abiertos, cada uno con su título. La ventana lleva la franja del color del
  consejo, como la ficha. Se cierra con la X, con Esc o tocando fuera.
- **Los plegables de la ficha abren también la ventana**, situada en ese
  apartado y destacado (`assenyala`). Ya no se despliegan en la cuadrícula:
  así hay una sola manera de ver el detalle, y la cuadrícula no se mueve. El
  título lleva «›» en lugar del triángulo de desplegar.
- **Cada ficha tiene su botón de compartir**, redondo y a la derecha del
  consejo, como las fichas de «Perill» (ADR 0076). Comparte con `comparteix`
  (el menú del dispositivo o, si no hay, se copia solo) **solo el enlace**,
  que abre la ficha, sin su texto. Una primera versión compartía también el
  medio, el consejo, las horas, el motivo y la ropa; Juanjo, al probarla: «el
  enlace a la ficha, se abre la ficha. no incluyas la descripción … quiero
  solo el enlace».
- **El enlace de una ficha** es `sortir.html#moto` (`peu`, `bici`, `moto`,
  `cotxe`, `public`) y abre la ventana. Lleva la hora de salir y la de volver
  (`?surto=…&torno=…`) solo si no son las de siempre (ahora y tres horas
  después), para que quien lo abra vea el mismo trayecto; si esa hora ya ha
  pasado, se usa la de siempre. Abrir la ventana pone la dirección en la
  barra, y cerrarla la quita.
- **Compatibilidad**: los enlaces a un plegable que ya circulan
  (`sortir.html#trens`, desde los avisos de trenes; `#transit-cotxe`,
  `#transit-moto`) abren la ficha que lo contiene, situada en él.
- Se construyen todas las fichas, también las de los medios que alguien ha
  ocultado, para que un enlace compartido las abra igual; las ocultas no se
  ponen en la página.
- Si llegan datos nuevos con la ventana abierta, se rehace con ellos.

## Alternativas descartadas

- **Mantener los plegables dentro de la ficha y añadir la ventana**: dos
  maneras de ver lo mismo, y la cuadrícula seguía moviéndose.
- **Un botón de ampliar aparte del título**: otro icono por ficha; Juanjo
  pidió el título, y el botón de compartir ya ocupa ese sitio.
- **Generar una imagen de la ficha para compartir**, como la gráfica: el
  mensaje de texto con el enlace se lee en cualquier aplicación y no queda
  desfasado; la imagen se puede añadir si se pide.

## Consecuencias

- Las fichas tienen dos botones nuevos cada una (el título y compartir); la
  ficha de «Transport públic» pone el consejo en una segunda línea, como ya
  hacía antes.
- Los autobuses (ADR 0120) cambiaron antes la misma parte de `pintaSortida`:
  sus apartados («Trens» y «Busos») y el plegable de los trenes entran solos
  en la ventana, porque esta copia el contenido de la ficha.
- Juanjo pidió ponerla en producción el 22-10-2026, tras la 3.180.0; sale
  en la 3.181.0.

## Validación

- Pruebas (660), Ruff y ESLint, sin fallos.
- `probar-web` con Chromium, Firefox y WebKit, en escritorio, móvil y tableta,
  claro y oscuro (18 combinaciones), con los datos públicos de las 08:30 del
  22-10-2026: se abre la ventana desde el plegable de «Moto», la dirección
  pasa a `#moto` y se limpia al cerrar con Esc; se abre la de «Transport
  públic» desde el título.
- Con Playwright: `#trens` abre «Transport públic»; el enlace compartido de
  «Bici» con la vuelta a las 14:00 lleva `?torno=…#bici` y, abierto en otra
  pestaña, muestra la ventana con las 14:00 elegidas; se comparte solo el
  enlace, sin texto.
- axe-core (WCAG 2.1 AA), con la ventana abierta y sin ella: sin fallos.
