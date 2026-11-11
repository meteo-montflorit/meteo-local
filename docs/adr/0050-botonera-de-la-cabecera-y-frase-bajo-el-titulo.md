# 50. Botonera de la cabecera y frase bajo el título

Fecha: 2026-10-09 · Estado: aceptado

## Contexto

Bajo «Temps a Montflorit» solo ponía «Cerdanyola del Vallès · Castellano»: el
título habla del tiempo, pero la web también da los avisos y «Si surts».
Juanjo prefirió no cambiar el título (09-10-2026) y pidió una frase que dijera
qué hay en la web, con el idioma «junto al icono del tema con su propio
icono». El primer intento, un botón con el icono solo, no decía en qué idioma
se estaba («no se ve el idioma seleccionado»). Después pidió que «Avisos al
mòbil» fuera a la misma botonera, con la campana, y que siguiera saliendo el
«Nou!».

## Decisión

- **Frase bajo el título de la portada** (`DESCRIPCIO` en `montflorit.py`),
  con el texto de Juanjo: «Montflorit, Cerdanyola del Vallès: la predicció
  del temps del barri, les alertes i què cal saber si surts.» El lugar va
  delante y separado: hasta el 11-11-2026 iba al final («…i què cal saber si
  surts, a Cerdanyola del Vallès.») y parecía que «si surts» quería decir ir
  a Cerdanyola. Las demás páginas mantienen «Montflorit, Cerdanyola del
  Vallès».
- **Una botonera a la derecha del título** (`.cap-botons`), igual en todas
  las páginas y en este orden: idioma, avisos y tema.
  - **Idioma** (solo en la web pública, `selector_idioma`): el icono
    «languages» de Lucide y «CA | ES», con el idioma actual marcado como la
    pestaña activa del menú; el otro lleva a la misma página en esa lengua.
  - **Avisos**: la campana, que lleva a «Avisos» y en esa página sale
    marcada. El «Nou!» («¡Nuevo!») va encima de la campana, con las mismas
    reglas que antes (ADR 0048).
  - **Tema**: el botón de siempre.
- **En móvil (menos de 30rem) la botonera va en una fila encima del título**:
  a su lado, el título no cabe y a 360 px la página se salía de la pantalla.
  La frase va siempre a todo lo ancho, debajo del título.
- La tabla de «Pròximes 24 hores», que en móvil se desplaza de lado, se puede
  alcanzar con el teclado (`tabindex`, con nombre de región).

## Alternativas descartadas

- **Cambiar el título de la web**: Juanjo lo dejó tal cual.
- **El icono de idioma solo**: no dice en qué idioma se está.
- **«Avisos al mòbil» como enlace con texto en la fila del menú** (ADR 0040):
  queda sustituido por la campana; la palabra va en el rótulo emergente y en
  el nombre accesible.

## Consecuencias

- La web privada «Temps a casa» comparte las páginas: también tiene la campana
  en la botonera y la frase a todo lo ancho, sin selector de idioma.
- Se modifican el ADR 0025 (dónde está el enlace a la otra lengua), el 0040
  (fila de navegación) y el 0048 (dónde va el «Nou!»).

## Validación

- 258 pruebas (`tests/test_montflorit.py`: selector en cada página y en las
  dos lenguas, con la página correcta; antes, «Fuentes y créditos» llevaba a
  «Si surts» en catalán).
- `probar-web` en Chromium, Firefox y WebKit, móvil, tableta y escritorio,
  claro y oscuro, y medidas a 320, 360 y 393 px sin desbordamiento; axe-core
  sin incidencias en las diez páginas, móvil y escritorio, claro y oscuro, el
  09-10-2026. Juanjo lo probó en el servidor local antes de publicar.
