# 94. «Avisos actius» plegado cuando no hay nada nuevo

Fecha: 2026-10-16 · Estado: aceptado

## Contexto

Juanjo, sobre la portada de la 3.90.0: «la pantalla inicial se ha ido
complicando con información. ¿Se te ocurre alguna mejora que, sin perder
información, permita una lectura más clara? Sobre todo al entrar en la página
inicial, la primera impresión».

Medido en un Pixel 7 con los avisos del día (INUNCAT en alerta con dos avisos
de Meteocat dentro y uno amarillo de AEMET): la cabecera ocupaba un 15 % de la
primera pantalla, «Avisos actius» un 55 % (ocho líneas, con los textos
íntegros de Meteocat: umbrales y hora de emisión), la temperatura asomaba
abajo y «El temps avui», lo que se quiere saber al abrir, quedaba fuera. El
bloque usaba a la vez franja de color, texto en naranja, negrita, cursiva, «?»
y «›». Arriba había dos horas distintas: «Actualitzat a les 09:21» y «Ara a
Montflorit (09:20)».

Propuesta de Juanjo: «la primera vez que se entra la tarjeta Avisos actius
aparece desplegada, pero, si no hay cambios, las veces sucesivas aparecería
plegada, indicando entre paréntesis el número de avisos». Objeción del agente:
plegado del todo, «(3)» no dice cuáles son; el sábado a las 11, con el aviso de
lluvia intensa a las 12, se vería solo el número porque nada habría cambiado
desde ayer, contra el criterio de que lo esencial se vea al abrir y de
«seguridad e información ante todo» (ADR 0093). Acordado (Juanjo: «sí, hazlo
en local»; tras probarlo en el móvil: «correcto, publica»): el mecanismo de
Juanjo con dos estados.

## Decisión

Versión 3.91.0.

- **«Avisos actius» es un plegable** (`details`), en «El temps» y en «Si
  surts», con el título «Avisos actius (3)»: el número cuenta cada aviso,
  también los cortes de luz.
- **Plegado, una línea por aviso**, con la franja de su nivel y «›» a su
  ficha de «Perill»: quién, qué y cuándo (`curtsAvisos`). La de Meteocat va a
  la ficha de Meteocat también cuando hay un plan, aunque desplegado su texto
  vaya dentro del del plan (3.91.1; Juanjo: «si pulso sobre meteocat me lleva
  a protección civil»). Protecció Civil: «pla d'inundacions (INUNCAT) en alerta».
  Meteocat: una línea por fenómeno con el nivel más alto y las horas
  (`smp.per_fenomen`, que ya llevaban los datos desde el ADR 0093); con datos
  anteriores sin `fenomens`, las líneas enteras, para que no falte ninguna.
  AEMET: «avís groc per tempestes, demà de 12:00 a mitjanit». La riera, los
  incendios, el Pla Alfa y los cierres, su título. El tiempo extremo propio:
  «Risc groc calculat per aquesta web: vent molt fort (75 km/h)». Los cortes
  de luz: el título y si es avería o trabajos. Las formas de las horas son las
  de cada fuente (Meteocat «de 12 a 24 h», AEMET «de 12:00 a mitjanit»).
- **Desplegado, los textos completos de antes**, sin cambiar nada (el oficial
  de Meteocat tal cual, ADR 0067; la cita de AEMET en castellano).
- **Se despliega solo la primera vez y cuando cambia el conjunto**: un aviso
  nuevo, un nivel que sube, uno que acaba, unas horas distintas. Lo que cuenta
  como cambio es la huella de las líneas cortas (`dataset.clau` de cada una:
  fuente, fenómeno, nivel y horas), independiente del idioma; la hora de
  emisión de un texto no cuenta. **Un aviso rojo no se pliega nunca** al
  cargar.
- **Lo visto se recuerda en el dispositivo** (`localStorage`,
  `meteo.avisos-vistos`), común a «El temps» y «Si surts»: se marca al pintar
  el bloque desplegado y al plegarlo o desplegarlo a mano. Sin memoria
  (navegación privada), cada vez desplegado.
- **Dentro de una misma página manda la persona**: la web repinta el bloque
  cada pocos minutos; si los avisos no han cambiado, se queda como lo dejó
  (`PLEC_AVISOS`); si cambian, se despliega en ese momento.
- **Una sola hora en la portada**: la línea «Actualitzat a les … · propera: …
  ?» pasa al pie de la tarjeta «Ara», y el título de la tarjeta deja de llevar
  la hora de la medida (difería un minuto de la otra y parecía un error). En
  «Si surts» sigue arriba, que no tiene tarjeta «Ara». Los avisos de datos
  (actualización que no llega, fuentes que fallan) siguen arriba.
- `NOM_RISC` pasa de `casa.js` a `comu.js`, porque la línea corta del tiempo
  extremo lo necesita también en «Si surts».

Resultado en el Pixel 7, segunda visita: la primera pantalla enseña los tres
avisos en tres líneas, la tarjeta «Ara» entera con la hora de actualización y
el resumen del día.

## Alternativas descartadas

- **Solo el número al plegar** (la propuesta literal): no dice cuáles son los
  avisos sin tocar nada; se descartó por seguridad e información.
- **Líneas cortas siempre, sin plegable** (la propuesta inicial del agente):
  obligaba a un toque para leer el texto oficial completo; la de Juanjo lo
  conserva a la vista la primera vez y cuando hay novedad.
- **Recordar cómo lo deja cada persona** (como «Desplega-ho tot», ADR 0074):
  Juanjo pidió plegado siempre que no haya cambios; así, lo que una persona
  despliega para leer no se le queda desplegado para siempre.
- Las demás propuestas (una sola tarjeta «Ara» + «Avui», dos columnas en el
  ordenador, no repetir la frase de peligro en cada tramo) quedaron para otro
  momento: con el plegable ya cabe la primera pantalla.

## Consecuencias

- `tests/test_perills.py` comprueba también el bloque plegado: cada tipo de
  alerta tiene su línea corta, y se despliega la primera vez, no la segunda,
  otra vez al cambiar el conjunto y siempre con un rojo.
- Un tipo de aviso nuevo tiene que dejar `dataset.clau` y `dataset.curt` en su
  elemento; sin ellos sale el texto entero, y la prueba de arriba lo detecta
  si falta.
- axe-core, sin incidencias en la portada (catalán y castellano) y «Si surts»,
  desplegado y plegado.

## Cambio del 17-10-2026 (3.118.0): en la portada, siempre plegado

Juanjo: «los avisos activos de la portada siempre colapsados». En «El temps»,
«Avisos actius» se abre plegado siempre, también la primera vez, cuando cambia
el conjunto y con un aviso rojo: plegado ya muestra una línea por aviso con la
franja de su nivel, así que se ve cuáles hay sin tocar nada. Si la persona lo
abre, queda abierto en esa página mientras los avisos no cambien.
`blocAvisos(dades, { plegat: true })` en `casa.js`; «Si surts» sigue con la
regla de arriba (se despliega solo con algo nuevo o rojo). Validación:
Chromium y Firefox con los avisos del momento (Meteocat en rojo): la portada
plegada al cargar, «Si surts» desplegada; prueba en `tests/test_perills.py`.

## Cambio del 17-10-2026 (3.120.0): en la portada, sin desplegable

Juanjo: «en avisos activos quita lo de desplegar, que muestre la información
como sale ahora plegado y al pulsar lleva al detalle del aviso, es para
simplificar la pagina inicial». En «El temps», «Avisos actius» es ahora el
título con el número y una línea corta por aviso, con la franja de su nivel;
cada línea lleva a la ficha de su aviso en «Perill», donde está el texto
entero, el comunicado y el «?» de la fase. Sustituye al «siempre plegado» de
la 3.118.0: `blocAvisos(dades, { curts: true })`. «Si surts» sigue con el
desplegable y la regla de arriba. Validación: Chromium y Firefox, en catalán
y castellano, con los avisos del momento; cada línea lleva a su ficha.

## Cambio del 17-10-2026 (3.121.0): cuándo se publicó cada aviso y «Nou»

Juanjo: «se podría poner en esta pagina inicial la fecha y hora de
publicación del aviso y si tiene actualizacion se sustituye por esta, asi se
sabe si la hemos visto antes o no», y luego «debajo no, cabe al lado, si no
cabe entonces pasa abajo». Cada línea corta de «Avisos actius» (portada y
«Si surts» plegado) acaba con «· publicat avui 00:09» o, si ha cambiado,
«· actualitzat avui 11:10», en gris y en un trozo que no se parte. Lleva la
palabra porque varias líneas ya tienen horas del fenómeno («avui de 12 a
24 h») y una hora suelta se confundiría con ellas.

La hora es la del historial de «Perill» (`inici` y `darrer` de avisos.json),
la misma con que llegaron los avisos al móvil y a Telegram; en un plan de
Protecció Civil, también la de su comunicado más reciente (del nombre del PDF,
`…_202610171110.pdf`), y en un plan en prealerta, sin historial, `des_de`.
Las líneas sin historial (cortes de luz, Pla Alfa) no llevan hora. Las fichas
activas de «Perill» añaden «· actualitzat …» con la misma regla
(`publicacioEpisodi`), para que digan lo mismo que la portada.

«Nou», delante de la línea, en los avisos que este dispositivo no había
mostrado al abrir la página: la clave es el aviso y su hora, así que una
actualización vuelve a salir como nueva. Lo mostrado se guarda en
`localStorage` (`meteo.avisos-llegits`) y la marca se mantiene mientras la
página sigue abierta; no se calcula hasta tener el historial, para que no
parpadee. Validación: Chromium y Firefox, catalán y castellano, con los
avisos del momento; primera visita con «Nou» y la siguiente sin él;
`tests/test_perills.py` con la hora en las líneas.

## Cambio del 17-10-2026 (3.128.0): «Actualitzat a les…», otra vez arriba

En la portada, la línea «Actualitzat a les… · propera: …» vuelve a ir arriba,
bajo el subtítulo y las pestañas, como en «Si surts» y «Consultes», y no al
pie de la tarjeta «Ara». Juanjo: «está oculto en medio del texto, lo quiero
arriba bajo el subtítulo o donde quieras pero que se vea nada más entrar».
Ocupa una línea pequeña; los avisos siguen saliendo justo debajo. La tarjeta
sigue sin la hora de la medida, que ya dice esa línea.

## Cambio del 18-10-2026 (3.135.0): en la portada, plegado si no hay nada nuevo

Juanjo, ante la portada con tres avisos ya vistos: «también quiero que esto
aparezca plegado a no ser que haya algo nuevo». En «El temps», «Avisos
actius (n)» vuelve a ser un desplegable; dentro, las mismas líneas cortas de
la 3.120.0, cada una con su ficha. Se abre solo si alguna línea lleva «Nou»
(un aviso o una actualización que este dispositivo no había mostrado) o si
hay un aviso rojo, que no se pliega nunca; si no, solo el título con el
número. Lo que haga la persona manda mientras la página sigue abierta y los
avisos no cambian. «Nou» se calcula con el historial de «Perill»: hasta que
llega, el bloque sale plegado, salvo un rojo. «Si surts» no cambia.
Validación: `tests/test_perills.py` (plegado la segunda vez, abierto con algo
nuevo o rojo); Chromium y Firefox, escritorio y móvil, primera visita abierta
con «Nou» y la siguiente plegada.

## Cambio del 19-10-2026 (3.147.0): «Nou» también en las fichas de «Perill», con el criterio del punto rojo

Juanjo, tras ver el punto rojo de «Perill»: «al entrar no sé qué es lo nuevo
porque hay muchos mensajes activos, hay que marcar como nuevo lo que sea
nuevo». El punto rojo (ADR 0071 y 0074) solo contaba el comienzo de una
situación posterior a la última visita, y en «Perill» ninguna ficha decía
cuál era. Ahora el punto rojo y las fichas usan el mismo criterio que el
«Nou» de «Avisos actius»: una situación activa publicada **o actualizada**
(`publicacioEpisodi`: `darrer`, o el comunicado de un plan) después de la
última visita a «Perill». En «Perill», esas fichas llevan el chip «Nou»
delante del título; el «visto hasta» se lee una vez al abrir la página, de
modo que las repintadas de la misma visita no lo borran, y se guarda al
pintar, como antes. Validación: `tests/test_web.py`
(`test_punt_de_perill_nomes_amb_un_perill_actiu`: una actualización
posterior a la visita es nueva; `esNou` en «Perill» con el visto de al
abrir), y la página en Chromium y Firefox.


## Cambio del 19-10-2026 (3.155.1): en «Perill», lo nuevo primero

Juanjo: «se etiqueta con nou lo que se acaba de añadir, pero me aparece en
último lugar, debe aparecer en primer lugar», y «luego ya se ordena otra vez
por fecha… pero al entrar tiene que estar lo nuevo en primer lugar». Las
fichas de «Ara» iban por la hora de comienzo, y una actualización de un
episodio antiguo (el comunicado nuevo de un plan, un aviso que cambia) lleva
«Nou» pero había empezado antes, así que quedaba abajo. Ahora
(`perill.ordreActius`) las fichas con «Nou» van delante, de la publicada o
actualizada más tarde a la más antigua, y detrás las demás, por comienzo como
antes. Como «Nou» se calcula con el «visto hasta» de al abrir, el orden se
mantiene durante la visita; en la siguiente ya no son nuevas y vuelven a su
sitio por fecha. Validación: `tests/test_web.py`
(`test_punt_de_perill_nomes_amb_un_perill_actiu`: la actualizada pasa delante
de la que empezó después y ya se había visto) y el historial publicado del
19-10-2026, con una visita simulada tres horas antes: el plan INUNCAT del 15,
actualizado, sale primero.

## Cambio del 19-10-2026 (3.161.1): pulsar un aviso le quita el «Nou»

Juanjo, 19-10-2026: «cuando pulso en un aviso que tiene la etiqueta nou,
debe desaparecer el nou, ahora cuando vuelvo sigue estando». El «Nou» se
calculaba una vez al abrir la página (`LLEGITS_ABANS`), y al volver atrás el
navegador puede enseñar la página tal como estaba, sin volver a ejecutar
nada (memoria caché de atrás y adelante). Ahora, al pulsar una línea con
«Nou», se le quita en ese momento y no vuelve en las repintadas de la misma
visita; y al volver de esa memoria (`pageshow` con `persisted`),
`treuNousVistos` quita el «Nou» de lo que ya se había mostrado, como al
recargar. Validado en Chromium y Firefox, a 360 y 1.280 px: cinco «Nou» al
abrir, cuatro tras pulsar uno, ninguno al volver de la memoria (simulada con
el evento, porque el navegador de pruebas no la usa).


## Cambio del 20-10-2026 (3.164.0): siempre plegado, con punto rojo y franja

Juanjo (20-10-2026): «los avisos activos siempre plegados, solo cuando hay uno
nuevo aparecerá un punto rojo indicando que hay novedades». «Avisos actius»
ya no se despliega solo con un aviso nuevo o rojo: queda siempre plegado. Si
hay alguno con «Nou», lleva al lado el mismo punto rojo que la pestaña
«Avisos», que desaparece al desplegarlo; y la franja de la izquierda toma el
color del aviso más grave (amarillo, naranja o rojo), para que se vea cuánto
importa sin desplegarlo. Se planteó pasar el bloque debajo del gráfico, ya
que los avisos meteorológicos salen en él, y se descartó: el gráfico no
enseña los planes de Protecció Civil, los incendios, la riera, el Pla Alfa ni
los cortes de luz. Así el gráfico cabe en la pantalla del móvil (ADR 0074).

## Cambio del 18-11-2026 (3.225.1 y 3.225.2): lo visto no se olvida si el aviso falta un rato

Juanjo, 18-11-2026, con la portada abierta desde hacía horas: el amarillo de
viento de la AEMET publicado a las 11:15, que ya había salido sin «Nou», salió
por la tarde con «Nou». Causa: cada pintada guardaba en
`meteo.avisos-llegits` solo los avisos que mostraba en ese momento, y una
lectura fallida de la AEMET (`casa.py` publica entonces `avisos` vacío, con el
aviso de la fuente que falla) quitó la línea de la portada; en la pintada
siguiente se borró de lo visto y, al recargar la página con la AEMET ya
respondiendo, volvió como nuevo. Pasaba igual con cualquier fuente que fallara
un rato (Meteocat, la riera, los incendios).

Ahora cada aviso mostrado se recuerda una semana desde la última vez que salió
(`llegitsARecordar`; la hora, en `meteo.avisos-llegits-quan`). La 3.225.1 la
contaba desde la hora de publicación de la clave, y lo que no la tiene (el Pla
Alfa, los cortes de luz) se seguía olvidando; la 3.225.2 lo cuenta para todos
desde que se mostró. Una actualización real sigue saliendo como nueva, porque
cambia la hora de publicación que lleva la clave. `meteo.avisos-llegits`
sigue siendo la lista de claves, porque una pestaña abierta con el código
anterior la lee como lista; lo que esa pestaña reescriba sin hora cuenta como
visto en ese momento.

Por qué una semana: en el historial de «Perill» de octubre y noviembre (32
episodios), un aviso sigue saliendo como mucho 2,2 días después de su última
publicación (las tormentas de la AEMET del 17-10); la semana deja margen para
los planes de incendios de Protecció Civil del verano, que pueden durar
semanas sin comunicado nuevo, y su coste son unas decenas de claves en el
navegador. Hipótesis por validar: la duración de esos planes en verano, que
el historial aún no tiene.

Se descartó quitar el «Nou» al volver a la pestaña: no arreglaba el caso, que
venía de la recarga. Evidencia: las claves guardadas en el Chrome de Juanjo y
los datos publicados del 18-11 (la clave del aviso no cambió) y
`tests/test_web.py` (`test_avis_que_desapareix_una_estona_no_torna_a_ser_nou`),
que falla con el código anterior. Validado en Chromium, Firefox y WebKit, en
escritorio y móvil, con los datos del 18-11.

## Cambio del 21-11-2026 (3.227.0): las horas de los riesgos de esta web

La línea corta de los riesgos que calcula la web decía qué y cuánto, pero no
cuándo: «Temps a Montflorit: risc groc (no oficial): vent fort (81 km/h).»
(Juanjo: «aquí me gustaria que pusiera las horas. En todos los de la app»).
Ahora cada riesgo lleva su franja con el formato de las de Meteocat, «demà de
9 a 10 h» (`quanRisc`); si pasa de un día a otro, como los de la AEMET
(`textFranja`), y el medido, «ara». El título no se acortó: en escritorio
cabe en una línea («a lo mejor no hace falta acortarlo, si ya cabe»); en el
móvil ocupa tres líneas en catalán y cuatro en castellano, como otras.
Validación: Chromium, Firefox y WebKit, escritorio y móvil, catalán y
castellano, con el riesgo de ratxa del 22-11.

## Cambio del 21-11-2026 (3.228.0): lo visto en la portada quita el punto de «Perill»

El «Nou» de «Avisos actius» se iba al volver a cargar la portada, pero el punto
rojo de la pestaña «Avisos» (`perill.html`) seguía hasta abrirla, porque cada
uno se acordaba de lo visto por su cuenta (Juanjo: «no debería irse también
este punto rojo si ya se han visto las alertas desde la pestaña temps?»).
Ahora la portada apunta cada episodio del historial que muestra, con su hora
de publicación (`meteo.perill-vist-portada`, `apuntaVistosPortada`), y el
punto no cuenta esos episodios (`perillsNous`). Como el «Nou», vale lo
apuntado al abrir la página: el punto se va a la vez que el «Nou», al
recargar, y en las demás páginas enseguida. Si el aviso se actualiza, vuelve
a ser nuevo. Un episodio que la portada no muestra (`mostratAPortada`) sigue
encendiendo el punto. Lo apuntado se olvida a la semana, como los «Nou».
Validación: `tests/test_web.py`
(`test_punt_de_perill_fora_si_la_portada_ja_els_ha_mostrat`) y Chromium,
Firefox y WebKit en móvil con los avisos del 21-11: punto al abrir, sin punto
al recargar y en «Si surts».
