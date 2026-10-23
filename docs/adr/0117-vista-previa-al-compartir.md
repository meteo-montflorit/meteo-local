# 117. La vista previa al compartir un enlace (Open Graph)

Fecha: 2026-10-21 · Estado: aceptado

## Contexto

Juanjo preguntó si convenía «aplicar OG data». Las páginas solo tenían
`<title>` y `<meta name="description">`: al compartir un enlace por WhatsApp,
Telegram o las redes (el botón de compartir de la página, los grupos, los
avisos del bot que enlazan a su ficha) salía como mucho el título y un texto,
sin imagen. El agente recomendó las etiquetas Open Graph con una imagen fija
por lengua, en una versión aparte; Juanjo: «no hace falta [enseñármelo], lo
puedes aplicar todo».

## Decisión

- **`montflorit.py` (`open_graph`) añade a cada página pública** `og:type`,
  `og:site_name`, `og:title`, `og:description`, `og:url`, `og:locale` (y la
  otra lengua como `og:locale:alternate`), `og:image` con su tamaño y texto
  alternativo, y `twitter:card`. El título y la descripción se toman de la
  propia página ya traducida: nada se escribe dos veces. Las páginas sin
  descripción (fuentes, cómo funciona, privacidad) van sin
  `og:description`.
- **Una imagen fija por lengua** (`web/img/compartir-ca.png`,
  `compartir-es.png`, 1200 × 630, unos 25 KB): un sol detrás de una nube
  sobre un cielo azul, el nombre, qué es y la dirección. En la 3.177.0 era el
  icono de la app, con la nube y la moto de cuando la web trataba también del
  trayecto; Juanjo: «es muy malo… ¿algo del tiempo más tradicional?». De dos
  propuestas (cielo azul o el azul oscuro de «Ara») eligió la del cielo
  (3.178.2). El nombre del archivo cambia para que los servicios que
  guardaban la anterior pidan la nueva.
- **Sin el tiempo del momento en la imagen**: WhatsApp y Telegram guardan la
  vista previa días, y enseñaría un tiempo caducado.
- De paso, los títulos en castellano de «Consultas», «Privacidad» y «Riera»,
  que seguían diciendo «Temps a Montflorit».

- **Desde la 3.193.0, el atardecer de «Ara»** (`web/img/compartir-capvespre-ca.jpg`
  y `-es.jpg`, 51 y 54 KB): el fondo de la tarjeta al ponerse el sol con
  pocas nubes (`.cel-albapoc`, nubes teñidas) y el dibujo «sunset» de
  Meteocons, con la letra de la web y el subtítulo con la previsión de 7 días
  (Juanjo, 23-10-2026: «las del amanecer y atardecer son muy bonitas»; de dos
  propuestas, el atardecer con nubes o el amanecer liso, eligió la primera,
  la que recomendó el agente). En JPEG: con los degradados, el PNG pesaba
  unos 400 KB. Las hace `eines/compartir.py` con los mismos archivos de
  `web/`; las de cielo azul (`compartir-ca.png`, `compartir-es.png`) se
  quitan. A la vez, la descripción de la portada ya no dice «les pròximes 24
  hores» (la previsión llega a mañana a las 21 h, ADR 0041, y hay la de 7
  días): «El temps ara a Montflorit (Cerdanyola del Vallès), la previsió hora
  a hora fins demà i la de 7 dies, i els avisos de perill.»; y la de «Si
  surts» nombra los autobuses (ADR 0120).

## Consecuencias

- La vista previa es la de la página: un enlace a `#grafica` o a la ficha de
  un aviso enseña la de la página que lo contiene.
- Los servicios que ya tengan un enlace guardado no lo renuevan enseguida.

## Validación

`tests/test_montflorit.py` (`test_vista_previa_en_compartir`): las etiquetas
en catalán y castellano, la dirección de cada lengua y las dos imágenes.
