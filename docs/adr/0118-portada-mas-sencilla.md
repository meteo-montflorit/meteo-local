# 118. Una portada más sencilla: la conclusión arriba

Fecha: 2026-10-21 · Estado: aceptado

## Contexto

Juanjo pidió «la aplicación del tiempo más sencilla y atractiva». El agente
hizo una maqueta en un lienzo de diseño (la portada actual al lado de la
propuesta, en el móvil claro y oscuro y en el ordenador). Juanjo preguntó si
la gráfica seguía teniendo sus opciones; el agente vio que en la maqueta la
había sustituido por una tira más simple, que dejaba sin ver las franjas
elegidas (viento, humedad…), y recomendó conservar la gráfica de verdad.
Juanjo pidió implementarla «con la posibilidad de volver atrás»: se hizo en
una rama aparte, enseñada en el servidor local con los datos del momento y
con una simulación de avisos. Juanjo: «me gusta, publica la portada nueva».

## Decisión

- **«Ara», destacada** (`.targeta.ara.heroi`): una tarjeta azul oscura con
  la conclusión arriba, la temperatura en grande con la parte alta al lado
  (sin el termómetro, para que quepa) y los datos en pastillas. El
  recuadro del radar, desde la 3.188.0, va debajo de la gráfica (Juanjo,
  22-10-2026: «prefiero que salga bajo la gráfica»): dentro de la tarjeta
  empujaba la gráfica hacia abajo justo cuando llueve. En la tarjeta queda su
  conclusión, en una línea (`resum-linia pluja-radar`), para que la lluvia
  que llega se vea al abrir: en un móvil de 360 × 800 el recuadro queda
  fuera de la primera pantalla. La frase se repite como título del
  recuadro; se aceptó al verlo con lluvia simulada.
- **La conclusión la escribe el programa** (`casa.fraseCelAra`): el cel de
  los dos tramos que vienen, con las mismas piezas de la tabla
  (`resumTrams`); si el tramo en curso solo tiene una hora, empieza por el
  siguiente; con el mismo cielo, una sola frase («Aquesta tarda i aquesta
  nit, ennuvolat.»). Debajo, la línea de lluvia de siempre
  (`liniaPlujaPrevista`, con su cuenta atrás) o «Sense pluja prevista.». Si
  llueve o el radar ve lluvia, en lugar de esa línea, la conclusión del
  radar («Pluja d’aquí a 24 minuts (cap a les 17:44).»). Si
  los modelos no ven lluvia pero hay aviso de lluvia o tempestades en 24
  horas (`casa.avisDePluja`), lo dice: «Els models no hi veuen pluja, però
  hi ha avís: mira'l a dalt.» (ADR 0101: lo oficial manda).
- **Cómo se nota cada tramo, en la misma frase** (desde la 3.179.0): «Aquesta
  nit, fred i molt ennuvolat; aquest matí, encara fred i cobert.». Palabras
  de la calle, sin cifras (Juanjo, 22-10-2026: «algo que haga referencia a
  si hace frío o calor o heladas… no quiero datos»), con siete niveles que
  fijó Juanjo como orientativos, no una clasificación oficial: fred intens
  (bajo 0 °C), molt fred (0–5), fred (6–11), fresc (12–17),
  temperatura agradable (18–25; «agradable» solo no se entendía, Juanjo),
  calor (26–32) y molta calor (33 o más). Se mide la temperatura
  que se nota (`esNota`, el índice de Environment Canada que ya usaban la
  ropa y «Si surts», ahora en `comu.js`), redondeada: la mínima por la noche
  y por la mañana y la máxima por la tarde (`casa.sensacioTram`). Por la
  mañana, si después sube hasta otra palabra, se dicen las dos: «fresc i
  després agradable, i ennuvolat», con el cielo tras una coma para que no se
  lea «agradable i ennuvolat» (Juanjo, 22-10-2026). La mínima de la mañana es
  la del amanecer, la misma de la noche, y sin esto la subida de la mañana no
  salía en ningún sitio: con «Aquesta nit… demà al matí…», que se lee la
  víspera para decidir qué ponerse, las dos palabras salían de mínimas casi
  iguales. En la previsión del 06-10-2026 la mañana iba de 16 °C a las 7 a
  23 °C a las 13, y decía solo «fresc». Solo la mañana: el enfriamiento de la
  tarde ya lo dice la noche, el tramo siguiente, y repetirlo dentro de cada
  tramo alargaba frases que ya se entendían. Si la máxima llega antes que la
  mínima (una mañana que se enfría), solo la mínima. Si los dos
  tramos coinciden, el segundo dice «encara», también cuando la mañana empieza
  como acaba la noche («encara fresc i després agradable»); con el mismo cielo y la misma
  sensación, una sola frase. La leyenda de la tabla («Fred, fresc, calor…»)
  da los intervalos y dice que son orientativos. Sin «glaçada»: tiene un
  significado meteorológico propio y ya sale como fenómeno en los tramos.
  La sensación va delante del cielo: «molt ennuvolat i fred» se leía «molt
  fred» (Juanjo, 22-10-2026). La frase gana dos o tres palabras: a 412 px y en el ordenador cabe igual;
  a 360 px puede pasar a tres líneas (la tarjeta, de 302 a 327 px con los
  datos del 22-10-2026), y la gráfica sigue entera en una pantalla de
  360 × 800.
- **La riera, debajo de «Ara», solo cuando anuncia algo** (`casa.estatPortada`):
  si llueve en la cuenca o hay riesgo, con el título y el color de la página
  «Riera» (`comu.titolRiera`, `COLOR_NIVELL`, que pasan de `riera.js` a
  `comu.js` para que las dos digan lo mismo), y no si su aviso ya sale arriba,
  en «Avisos actius». Lleva a «Riera». En la 3.178.0 había además una línea
  «Ara no hi ha cap avís.» y la riera salía también sin nada que decir; en
  la 3.178.1 se quitan (Juanjo, 21-10-2026: «que solo aparezcan cuando
  anuncien algo»).
- **Los avisos activos, más visibles**: el bloque sigue plegado (ADR 0094),
  pero con el fondo y el borde del color del más grave y el título más
  grande, para no quedar a la sombra de «Ara».
- **Fuera de la portada, el resumen de texto de hoy y el de mañana**: lo
  dicen la conclusión y los tramos. Sin datos de «ara», el de hoy, como
  siempre. Se retira el código que añadía la cuenta atrás a ese resumen
  (`posaComptePluja`).
- **Los enlaces a los radares, dentro de «D'on surt»**.
- **La gráfica, igual**, con sus opciones recordadas.
- **En todo el sitio**: la letra Figtree (SIL OFL 1.1, servida desde
  `web/fonts`, sin Google; crédito en «Fonts») y las tarjetas algo más
  redondeadas, para que las demás páginas no desentonen.

- **También en los resúmenes** (desde la 3.192.0; Juanjo, 23-10-2026:
  «cuando envías las alertas de hoy, podrías poner el texto que pones de si
  hará fresco… solo el de hoy. Y cuando envías el de mañana, también.
  Telegram y app… y en Consultes»): `bot.frase_cel`, la misma cuenta en
  Python, debajo de «Ara mateix» en el de hoy y del título en el de mañana.
  Lo usan el bot y el canal de Telegram, los avisos en el navegador y
  «Consultes» (`montflorit.consultes`), que salen todos de `bot.resum`. El de
  hoy, con todos los tramos que quedan de hoy, también la noche («aquesta
  nit»); el de mañana, sus tramos con «Al matí» y «A la tarda», porque el
  título ya dice que es mañana. Los tramos seguidos iguales van juntos («Al
  matí i a la tarda, fresc i cobert») y «encara» compara con el anterior. A
  la riera, como el resto del resumen (el bot no sabe la zona de cada uno,
  ADR 0123). `tests/test_web.py` comprueba que el bot y la tarjeta dicen lo
  mismo con los mismos tramos, en catalán y castellano.

## Alternativas descartadas

- **Una tira hora a hora en lugar de la gráfica**, como en la maqueta: más
  simple, pero quien había encendido una franja dejaba de verla al abrir.
- **Los avisos dentro de la tarjeta de la riera**, siempre en el mismo sitio:
  con peligro, lo primero que hay que ver es el aviso, arriba.
- **Figtree desde Google Fonts**: cada visita avisaría a Google.
- **La temperatura máxima y mínima en «Ara»**, como en la maqueta: ya las
  dicen los tramos justo debajo.
- **Una línea con la mínima, la máxima y la comparación con ayer** bajo la
  frase (probada el 22-10-2026): Juanjo quería palabras, no datos.

## Consecuencias

- La portada del móvil queda algo más corta (de unos 1.600 a unos 1.500 px
  con los datos del 21-10-2026); los tramos conservan su aspecto.
- La conclusión depende de los tramos: si cambia cómo se calcula el cielo de
  un tramo, cambia también la frase, y no pueden contradecirse.

## Validación

Pruebas (`test_frase_de_dalt_de_la_portada` en `test_web.py`, y la frase en
castellano en `test_montflorit.py`), Ruff y ESLint; `probar-web` de la
portada en Chromium, Firefox y WebKit, en móvil y escritorio, claro y
oscuro, con los datos del momento y con una simulación de un aviso naranja
de viento y uno amarillo de lluvia; las demás páginas en Chromium y Firefox,
móvil y escritorio; axe-core sin incidencias en todas, en los dos temas,
también con los avisos de la simulación.
