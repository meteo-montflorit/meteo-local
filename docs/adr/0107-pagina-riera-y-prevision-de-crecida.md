# 107. Página «Riera» y previsión de crecida con los modelos

Fecha: 2026-10-19 · Estado: aceptado

## Contexto

Juanjo preguntó si se puede prever la crecida de la riera con horas de
antelación a partir de las previsiones («sería algo muy provisional pero
podría alertar de una situación de posible peligro»). El aviso de la riera
(ADR 0027) sale de la lluvia medida en Sant Cugat y del radar de la hora
siguiente: avisa cuando ya llueve fuerte, con una hora de margen como mucho.
Con las previsiones pasadas de los modelos (Open-Meteo las archiva;
`calibracio/dades`, 2024-2026) se midió qué habrían dicho: el modelo que más
da, con 20 mm o más en 3 horas, señala 21 días en 2,75 años, 4 con 35 mm
reales; de los tres desbordamientos vio venir dos y no el del 29-09-2026
(13 mm previstos, 66 caídos). Juanjo decidió: «estos avisos previos de
momento no saldrían como alerta ya que no podemos dar falsos positivos que
provoquen alarma. Quedaría únicamente en su pestaña (con punto cuando
aparezca) indicando que hay una situación de riesgo pero dejando muy claro
que es una previsión y que la situación puede cambiar en cualquier momento.
Hay que indicar la diferencia con las alertas de la riera que sí se basan en
datos reales del momento». Aprobó la propuesta con el punto ámbar y las tres
partes («hazlo así»).

## Decisión

- **Una pestaña «Riera»** (`web/riera.html`, `riera.js`), tras «Perill», con
  lo que necesita el vecino y nada más (Juanjo, tras la primera versión:
  «demasiada información para el vecino del barrio… si quieres pon aparte
  todos estos datos de ahora»; «demasiados desplegables, deja solo uno
  donde esté todo»): bajo la entrada, la misma invitación que en «Perill» a
  activar las notificaciones, con el enlace a «Notificacions» (desde la
  3.169.0; Juanjo, 20-10-2026: «en la riera añade un enlace para activar las
  notificaciones, como en la sección de avisos»); encima de todo, la línea
  «Actualitzat a les…», justo debajo de las pestañas como en las demás
  páginas (desde la 3.169.1; antes iba tras la entrada); **Avís**, si hay uno activo (la misma franja que en
  «Perill», con el enlace), **Ara** (una línea con el nivel y la lluvia
  medida: «Sense risc de crescuda ara…», en verde), **Properes hores** (la
  previsión, con el recuadro «És una previsió en fase de proves…» que dice
  qué es el aviso de la riera y de dónde sale; desde la 3.161.1, solo con
  «Risc de crescuda possible»: en verde no hay nada que matizar, Juanjo,
  19-10-2026) y un solo desplegable «Més
  informació» con el detalle (radar, índice, Fabra, cada modelo, las 24
  horas), los episodios con aviso, los desbordamientos conocidos, el enlace
  al mapa de la riera (montflorit.github.io/riera/) y cómo se deciden el
  aviso y la previsión.
- **La previsión** (`riera.previsio`, `riera.previsio_models`): cada pasada,
  la lluvia por horas de AROME HD, AROME, ICON-EU y ECMWF en
  `config.CONCA_RIERA`, 24 horas; para cada modelo su máximo de 3 horas y
  manda el que más da (ADR 0103: el máximo no rebaja la lluvia fuerte), con
  su ventana y la media de los modelos en ella; lo mismo a 6 horas; la
  lluvia de las últimas 24 horas en Sant Cugat (el suelo mojado, 12.3).
  «Risc de crescuda possible» desde `RIERA_PREVISIO_MM = 20`. Va en
  `casa.json` (`riera_previsio`) y en `avisos.json`, para la pestaña.
- **No es un aviso**: no sale por Telegram, ni en el navegador, ni en «Avisos
  actius», ni en «Perill», ni en «Si surts». Solo en su página, con un texto
  fijo que dice que es una previsión que puede cambiar, que fallan a menudo
  (uno de tres desbordamientos visto) y que los avisos de la riera salen de
  lo medido.
- **El punto de la pestaña «Riera»** (`comu.senyalaRiera`, `.punt-riera`):
  **rojo** si hay un aviso de la riera activo no visto (el criterio del
  punto de «Perill», solo con la riera; Juanjo: «en esta página deberá
  aparecer también con punto rojo las alertas de la riera»); **ámbar**
  mientras la previsión diga «possible» y haya aparecido después de la
  última visita (`inici`, que se conserva en `estat/riera-previsio.json`
  mientras dura). Ámbar y no rojo: el rojo es el de una situación de
  peligro con datos reales.
- **Se mide**: `registre/riera-previsio.csv` apunta cada pasada;
  `riera.py previsio-resum` compara por días con lo que midió Sant Cugat.
  En primavera de 2027, con la temporada de otoño registrada, se decide con
  datos si el umbral cambia o si entra el conjunto de previsiones (una
  probabilidad en vez de una cifra).
- La barra de pestañas pasa a cinco en el móvil (`grid-template-columns:
  repeat(5, 1fr)`); «Riera» cabe en 320 px.

## Alternativas descartadas

- **Avisar por Telegram o en el navegador**: de 4 a 8 falsas alarmas al
  año por cada acierto, y el episodio más grave invisible.
- **El máximo por hora entre modelos** (sumar en cada hora el modelo más
  alto): da cifras que ningún modelo prevé (31,9 mm el 19-10-2026 cuando el
  modelo que más daba preveía 23,5) y con el archivo, 27 días de señal por
  21. Se usa el máximo por modelo.
- **Meter la previsión en «Perill»**: mezclaría una previsión con las
  situaciones con datos reales, justo lo que Juanjo quiere separar.
- **Solo la previsión en la pestaña**: alguien podría mirarla en plena
  crecida y ver «possible» mientras el aviso real está en «Perill»; la
  pestaña lleva primero lo medido.

## Validación

- `tests/test_riera.py` (`Previsio`: el modelo que más da, la ventana, la
  media, el nivel, 25 horas; con red simulada, el `inici` que se conserva
  entre pasadas, el registro y el resumen), `tests/test_montflorit.py` (la
  página en las dos lenguas) y la prueba de traducciones (`i18n/claus.js`
  recorre `riera.js`).
- La medida del archivo: `riera_prev.py` en la carpeta de trabajo de la
  sesión del 19-10-2026 (las cifras están en `docs/estadistica.md`, 12.6).
- La página en Chromium y Firefox, móvil y escritorio, claro y oscuro, con
  los datos del 19-10-2026 (AROME HD preveía 23,5 mm de 16 a 19 h:
  «possible»), y axe-core.

**Tres correcciones del revisor** (26-10-2026, 3.205.1; ADR 0101, la primera
revisión con todas las páginas). Juanjo: «arregla los fallos».

- **La ventana empieza en la hora en curso.** La lluvia de 3 horas más alta se
  buscaba en las ventanas que acaban en cada hora del horizonte, y la que
  acaba en la primera empezaba dos horas antes. Con 0 mm en todos los modelos
  era la que quedaba: a las 19:24 la página decía «entre les 17 i les 20 h».
  Ahora solo cuentan las ventanas que empiezan en la hora en curso o después
  (`previsio_models`), y con 0 mm la página no da horas: «Els models no hi
  preveuen pluja». Validación: `tests/test_riera.py`
  (`test_la_finestra_no_comenca_abans_d_ara`).
- **Los desbordamientos que vio venir.** La página decía que la señal de 20 mm
  solo vio venir el del 4-10-2026; según la medida (`docs/estadistica.md`,
  12.6), vio dos: abril de 2024 (30 mm previstos) y 4-10-2026 (88). Se corrige
  en catalán y castellano.
- **27 días en `config.py`.** El comentario de `RIERA_PREVISIO_MM` daba la
  cifra del máximo por hora, descartado (ver «Alternativas descartadas»); la
  del método que se usa es 21, la de la página.
