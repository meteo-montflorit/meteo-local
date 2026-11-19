# 93. Todas las alertas de peligro juntas, y AEMET para lo que Meteocat no cubre

Fecha: 2026-10-16 · Estado: aceptado (cambia el ADR 0092 en qué avisa AEMET)

## Contexto

Con la 3.87.0 publicada, Juanjo vio que el resumen de mañana en «Consultes»
solo decía el aviso amarillo de AEMET, sin el peligro alto de Meteocat:
«¿aquí no sale nada del meteocat?». Y después: «y protección civil, las
alertas de peligro deben ir siempre juntas, que sale tanto en un lado como en
el otro, lo mismo con otras alertas de peligro que ahora no están activas.
Deberías tener un sistema para no dejártelas nunca».

Cada pantalla armaba su propia lista. Revisado el código:

| | Portada | Si surts | Perill | /avisos_actius | Resumen del día |
|---|---|---|---|---|---|
| Protecció Civil | sí | sí | sí | sí | **no** |
| Meteocat | sí | sí | sí | sí | **no** |
| AEMET | sí | sí | **no desde la 3.87.0** | sí | sí |
| Riera | sí | sí | sí | **no** | **no** |
| Incendios | sí | sí | sí | sí | **no** |
| Pla Alfa | sí | sí | sí | sí | **no** |
| Tiempo extremo propio | sí | **no** | sí | sí | **no** |

El resumen del día es el mismo texto en «Avui» y «Demà» de «Consultes», en los
mensajes del bot de las 7 y las 21 h y en /avui y /dema. La tabla por horas de
«El temps» también pintaba solo AEMET.

Sobre AEMET, el ADR 0092 la dejó de reserva (solo si no se podía leer
Meteocat). Juanjo lo corrigió: «si meteocat no tiene aviso y aemet sí, debe
salir aemet, prima la información y seguridad de los usuarios». Y al saber
que de AEMET solo se leían la lluvia y las tormentas: «¿por qué se descartan
algunos avisos de aemet? seguridad e información ante todo». No había motivo
escrito: venía de la primera versión (ADR 0001), que solo decidía entre moto y
coche.

## Decisión

### Meteocat o AEMET, por fenómeno y horas (`smp.py`)

- Un aviso de AEMET está **cubierto** si Meteocat tiene aviso del mismo
  fenómeno en alguna de sus horas (`smp.cobreix`; `casa.py` lo marca con
  `cobert`). Los cubiertos no se muestran ni avisan; los demás sí, como
  siempre. Sin lectura de Meteocat, ninguno está cubierto.
- Fenómenos que Meteocat también avisa: lluvia, viento, calor, frío y nieve.
  Las tormentas, la niebla, el polvo y el resto salen siempre de AEMET.
- Un aviso de AEMET que deja de estar cubierto se avisa: el cubierto no se
  apunta como avisado. Uno ya avisado que pasa a estar cubierto cierra su ficha
  de «Perill» diciendo que ahora se muestra el de Meteocat.
- **AEMET se lee entero**: todos los tipos de Meteoalarm para el Prelitoral de
  Barcelona (`prevision.TIPUS_METEOALARM`: tormentas, inundaciones, lluvia,
  viento, calor, frío, nieve, niebla, riesgo de incendios, fenómenos costeros,
  aludes, polvo y, si llega uno desconocido, «otros fenómenos»).

### Una sola lista, en el mismo orden, en todas partes

- Los tipos son `bot.TIPUS_PERILL`: Protecció Civil, Meteocat, AEMET, riera,
  incendios, Pla Alfa y el tiempo extremo que calcula la web. En ese orden en
  la portada y «Si surts» (`blocAvisos` de `web/comu.js`, que ahora incluye el
  tiempo extremo y lo usan las dos), en /avisos_actius (añade la riera) y en
  el resumen del día (`bot.linies_perill_dia`).
- En el resumen, una línea por alerta: los planes (no tienen final) hoy y
  mañana; Meteocat, una línea por fenómeno con su nivel más alto
  (`smp.per_fenomen`); AEMET, lo no cubierto; la riera y los incendios, solo
  hoy, porque dicen lo que pasa ahora; el Pla Alfa, el nivel de cada día; el
  tiempo extremo, si toca el día, dicho como no oficial. Cada línea lleva a
  «Perill» en «Consultes».
- La riera abierta va en los datos públicos (`perill_riera`, de avisos.json):
  sus datos son privados, su aviso no. Para tenerla al día, `publica.sh` hace
  los avisos antes que los datos públicos.
- La tabla por horas pinta Meteocat («Perill alt de Meteocat per pluja») y lo
  de AEMET que no cubre. «Si surts» cuenta como lluvia probable el aviso de
  cualquiera de los dos, y lo dice como «avís oficial».
- **Un plan de Protección Civil se mantiene a la vista con un aviso de su
  fenómeno, de AEMET o de Meteocat** (`prevision.pla_per_temps`). Antes, solo
  con lluvia o tormentas de AEMET: un plan de viento, de nieve o de calor, o
  uno con aviso solo de Meteocat, se ocultaba a las 24 horas. Un plan sin
  fenómeno meteorológico (contaminación) se muestra siempre.

### Para no dejarse ninguna

`tests/test_perills.py` mete una alerta de cada tipo y comprueba que salen en
/avisos_actius, en el resumen de hoy y en el de mañana (salvo riera e
incendios), en catalán y castellano, y en el bloque de la web; que la portada
y «Si surts» usan ese bloque tal cual; que cada aviso de peligro que crea
`avisos_bot.py` tiene su tipo, y que un tipo nuevo sin marca hace fallar la
prueba. Las instrucciones del repositorio lo piden.

## Cambio del 16-10-2026 (3.88.1)

La ficha cerrada de un aviso de AEMET que pasa a cubrir Meteocat decía «🟢
Acabat», y Juanjo preguntó si se había retirado: el aviso seguía vigente. Ahora
lleva `substituit_per` (la ficha de Meteocat) y «Perill» dice «Substituït per
l'avís de Meteocat», con enlace a esa ficha, sin el círculo verde.

## Cambio del 16-10-2026 (3.90.0): de dónde sale cada aviso, también en el móvil

La etiqueta de peligro de cada tramo decía «Avís taronja: pluja» para un
aviso de Meteocat, que habla de grado de peligro. Ahora dice «Perill alt:
pluja», como la franja vertical («Perill alt · pluja»), y si hay de las dos
maneras, juntas («Perill alt: pluja · Avís groc: tempestes»; `textPerillCurt`).
De dónde sale cada cosa (`textPerill`, «Perill alt de Meteocat per pluja»;
`origenTempesta`, si la tempesta es de un aviso o de los modelos) sale al
pasar el ratón y, para el móvil (Juanjo: «¿en móvil esta info se ve?»), en
una línea al abrir el tramo y en un mensaje breve al tocar la franja vertical.

## Alternativas descartadas

- **AEMET solo de reserva** (ADR 0092): calla avisos que Meteocat no da.
- **Las dos fuentes siempre**: repite el mismo fenómeno con niveles distintos y
  confunde (el amarillo de AEMET junto al alto de Meteocat).
- **Generar todas las listas en un solo sitio y pintarlas igual**: el bot
  (texto de Telegram) y la web (elementos con ayuda y enlaces) tienen formas
  distintas; lo que se garantiza es el contenido, con la prueba.

## Consecuencias

- El sábado 17: Protecció Civil, Meteocat (alto por lluvia) y AEMET (amarillo
  por tormentas) en todas partes; el amarillo de AEMET por lluvia ya no sale y
  su ficha de «Perill» se cierra.
- Llegarán avisos de AEMET que antes se descartaban (viento, calor, frío,
  niebla…), cuando Meteocat no los cubra.

## Evidencia

- Datos reales del 16-10-2026, 08:20: AEMET con lluvia (dos avisos) y
  tormentas amarillos de 12 a 24 h del sábado; Meteocat, lluvia alta. Con
  `casa.py`: las dos de lluvia salen `cobert`, las tormentas no; INUNCAT en
  alerta, visible; la tabla, «Perill alt de Meteocat per pluja».
- Feed de Meteoalarm del mismo día: `Moderate rain warning`, `Moderate
  thunderstorm warning`, `Moderate coastalevent warning`.

## Riesgos y limitaciones

- La correspondencia entre fenómenos de AEMET y de Meteocat es por nombre;
  un meteoro de Meteocat con otro nombre no cubriría a AEMET (saldrían los
  dos).
- En la reserva de IONOS la riera del resumen sale del avisos.json de la
  pasada anterior.

## Validación

477 pruebas, con `tests/test_perills.py` y las nuevas de `tests/test_smp.py`.
Con los datos reales: la web en local en Chromium y Firefox, móvil y
escritorio (portada, «Si surts», «Consultes › Demà»), sin errores de
JavaScript ni desbordamiento; axe-core (WCAG 2.1 AA y buenas prácticas) sin
infracciones en la portada, «Si surts», «Consultes» y «Perill», en catalán y
castellano.

## La etiqueta del tramo, solo plegado (17-10-2026)

Juanjo: «cuando despliego una franja horaria quiero que desaparezcan estas
alertas de peligro porque ya salen en vertical además del color que hay a la
izquierda, así se simplifica la visualización» y «plegadas sí aparecen,
desplegadas no». Desde la 3.113.1, la etiqueta de peligro de la cabecera de
cada tramo («⚠ Perill molt alt: pluja · Avís groc: tempestes») se ve con el
tramo plegado y se oculta al desplegarlo: entonces lo dicen la barra de
color de cada hora y el borde del tramo. Desde la 3.114.2, también la del
fenómeno destacado («tempesta»): desplegado queda el resumen normal, sin
avisos («que solo quede el resumen normal, sin avisos»).

## Quién avisa, lo primero de todo (17-10-2026)

Una persona recibió el aviso de Meteocat, cuya segunda línea empezaba por
«Intensitat de pluja en 30 minuts», y creyó que la app anunciaba lluvia en
30 minutos (Juanjo: «quizás habría que identificar claramente el origen del
mensaje»; y «aplícalo a todos los avisos, también los de la app»). Desde la
3.115.0 todos los avisos empiezan por quién avisa, también en la
notificación y en «Perill», aunque el título se corte: «Meteocat:»,
«AEMET:», «Protecció Civil:», «Bombers:», «e-distribució:» y, en los que
calcula la app (lluvia inminente, riera, peligro propio), «Temps a
Montflorit:», que dicen además «Calculat per aquesta aplicació, no oficial»
(antes, «aquesta web»). En las líneas de Meteocat, primero qué es y luego el
nombre oficial entre comillas: «🟠 Perill alt per «Intensitat de pluja en 30
minuts»: …». El nivel ya no va entre paréntesis en el título de los avisos
propios (lo dice el círculo), y la lluvia inminente lleva 🌧️. Lo mismo en el
resumen del día, «Avisos actius» y la franja de la gráfica
(«Meteocat: perill alt per pluja; AEMET: avís groc per tempestes»). Las
fichas ya guardadas en «Perill» conservan su título.

## Corrección del 17-10-2026 (3.122.0): las fichas de AEMET siguen a AEMET

«Perill» enseñaba como activos dos avisos de AEMET de mañana de 0 a 4 h
(lluvia y tormentas) que AEMET ya había juntado en los de hoy, alargados
hasta las 4 h; en la portada no salían. Causa: `avisos_bot.py` solo cerraba
una ficha de AEMET al llegar su hora final o al cubrirla Meteocat; un aviso
que AEMET deja de publicar antes de acabar seguía abierto, y un aviso que
AEMET alarga mantenía en su ficha la hora final de antes.

Ahora cada pasada que lee AEMET guarda los avisos vigentes con su final
(`aemet_vigents`) y `tanca_aemet` pone al día las fichas: alarga `fins` si
AEMET lo alarga y, si un aviso desaparece antes de acabar, cierra su ficha
diciendo que está dentro de otro aviso de AEMET (con el enlace a su ficha,
«Substituït per un altre avís de l'AEMET»), que lo cubre Meteocat, o que AEMET
lo ha retirado. Si AEMET no se ha podido leer, no se toca nada. Validación:
`tests/test_smp.py` y una pasada en seco con los datos del momento, que
cierra las dos fichas y alarga la de tormentas de hoy hasta las 03:59.

## Cambio del 19-10-2026 (3.149.0): «Si surts» remite a «Perill»

Juanjo: «en si surts salen todas las alertas, prefiero simplificarlo. si hay
alertas que afectan a la conduccion lo mejor es que remita a la pestaña
perill. hay que mirar los textos de si surt porque alguno hace referencia a
ver alertas más arriba, ya no estará ahí». «Si surts» deja de mostrar
«Avisos actius»: en su lugar, una sola línea con la franja del peor nivel,
«Hi ha N avisos de perill que poden afectar la conducció: mira'ls a
Perill», que enlaza con la pestaña. Cuentan los planes de Protección Civil,
Meteocat y AEMET por fenómeno (como las líneas cortas de la portada), la
riera, los incendios y el tiempo extremo propio; no cuentan la calor, el mar
(fenómenos costeros), el Pla Alfa y los cierres de espacios forestales
(acceso a pie al bosque) ni los cortes de luz, que siguen en la portada y en
«Perill». Sin ninguno, no hay línea. Las tres notas que decían «vegeu l'avís
de dalt» (plan de Protección Civil, riera, incendio) pasan a una sola frase
en la misma línea: «El consell de cada mitjà surt del temps previst i del
trànsit: no té en compte l'alerta de Protecció Civil, el perill de la riera
de Sant Cugat ni l'incendi proper» (solo lo que haya); y «Com es decideix» lo
explica sin «es diu a dalt». La tabla del contexto queda así para «Si surts»:
ninguna alerta entera, todas las de conducción contadas. La versión completa
de «Avisos actius» (los textos enteros, plegados), que solo usaba «Si surts»,
se quita de `web/comu.js`; la portada sigue con las líneas cortas.
Validación: `tests/test_web.py`
(`test_si_surts_nomes_remet_a_perill_amb_els_avisos_de_conduccio`, la nota
de lo que no tienen en cuenta) y `tests/test_perills.py` (la portada sigue
con todas; «Si surts», con la línea); la página en Chromium y Firefox,
móvil y escritorio, y axe-core.

## Cambio del 19-10-2026 (3.154.0): AEMET, oculto solo en las horas que cubre Meteocat

`smp.cobreix` marcaba un aviso de AEMET como cubierto, y lo ocultaba entero,
en cuanto Meteocat tenía aviso del mismo fenómeno en una sola de sus horas.
Caso real (lo vio la sesión que revisaba los hallazgos del revisor, por
encargo de Juanjo): el amarillo de lluvia de AEMET del día 20, de 4 a 6:59, no
salía en la hora de 6 a 7, aunque Meteocat avisaba hasta las 6. Contradecía la
regla de Juanjo del 16-10-2026 («si meteocat no tiene aviso y aemet sí, debe
salir aemet, prima la información y seguridad de los usuarios»). Ahora
`smp.marca_coberts` marca «cobert» solo si Meteocat cubre todas las horas; si
cubre algunas, el aviso lleva `inicio_visible` y `fin_visible` (de la primera
a la última hora que Meteocat no cubre) y se muestra con esas horas en la
franja de la tabla por horas (`casa.avisos_del_tramo`), en «Avisos actius» y
la gráfica (`comu.avisosAemet`), en el aviso y la ficha de «Perill»
(`avisos_bot`, con la clave del aviso entero, para no repetir avisos si
Meteocat cambia sus horas) y en el resumen del bot (`bot.text_avisos_aemet`).
Si las horas que no cubre no son seguidas, se muestra de la primera a la
última. De paso, el resumen del bot dice «de 06:00 a 07:00» y no «fins a les
07:00» cuando el aviso de hoy aún no ha empezado. Prueba:
`tests/test_smp.py` (`test_l_aemet_surt_a_les_hores_que_meteocat_no_cobreix`,
el caso del día 20).

## Cambio del 19-11-2026 (3.226.0): sin lectura de AEMET, los de la lectura anterior

El 18-11-2026 a las 21 h no se pudo leer AEMET: «Perill» mantenía la ficha
del amarillo por viento de 0 a 7 h, pero la portada contaba un aviso menos y
la tabla por horas y el resumen del bot lo perdían (revisor). Ahora, si AEMET
no responde, `casa.avisos_de_abans` toma sus avisos de la pasada anterior que
aún no han acabado, y la web los muestra en todas partes; la línea de fuentes
sigue diciendo que no han llegado. Para el bot (`avisos_anteriors`), la
lectura ha fallado: no avisa de nada ni abre o cierra fichas, como antes. Un
aviso que AEMET retire durante el fallo sigue saliendo hasta la lectura
siguiente, igual que su ficha.

En «Perill», la ficha de un aviso de AEMET cuyas últimas horas cubre Meteocat
lo dice: la línea da las horas que se muestran («de les 0 h a les 7 h») y
debajo, «L'AEMET l'avisa fins a…; les hores de després les cobreix l'avís de
Meteocat». El mensaje enviado decía de 0 a 10 h y la ficha acababa a las 6:59
sin explicarlo (revisor, 19-11-2026).

Validación: `tests/test_previsio_anterior.py` (`AvisosDeAbans`),
`tests/test_bot.py`
(`test_els_avisos_de_l_aemet_de_la_passada_anterior_no_toquen_res`); la
ficha, con los datos publicados, en Chromium, Firefox y WebKit, escritorio,
móvil y tableta; axe-core sin fallos en claro y oscuro.
