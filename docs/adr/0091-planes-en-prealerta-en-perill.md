# 91. Los planes de Protección Civil en prealerta, con ficha en «Perill»

Fecha: 2026-10-15 · Estado: aceptado

## Contexto

El 15-10-2026 la portada mostraba en «Avisos actius» «Protecció Civil: pla
d'inundacions (INUNCAT) en fase de prealerta». Al tocarla, llevaba a «Perill»,
que decía «Ara no hi ha cap situació de perill». Juanjo: «si hago clic me lleva
a la sección de avisos y me dice que ahora no hay nada. Si hay algo debería
salir con un enlace para ampliar la información si es que existe».

La causa: «Perill» (ADR 0071) se construye con el historial de los avisos
enviados, y la prealerta no envía aviso (ADR 0051), así que no tenía ficha. El
comunicado de Protección Civil en PDF, que viene en los datos (`comunicat`),
tenía que verse en esa ficha (ADR 0075) y no salía en ningún sitio. La línea
del plan llevaba además a `perill.html` sin más, no a su ficha, también en
alerta o emergencia.

## Decisión

- `avisos_bot.py` añade a `avisos.json` los planes en prealerta que muestra la
  web (`plans_prealerta`: plan, nombre, fase, desde cuándo, motivo y
  comunicado), sin avisar ni guardarlos en el historial, como el Pla Alfa.
- «Perill» les hace una ficha en «Ara», con la franja de la prealerta: el
  título de la portada, «Actiu ara · Des de…», que la prealerta no llega como
  aviso, qué quiere decir la fase, el motivo tal como lo publica Protección
  Civil (en catalán también en la página en castellano) y el enlace
  «Comunicat de Protecció Civil (PDF)»; sin comunicado, la página de Protección
  Civil. Con el botón de compartir de las demás fichas. Su dirección es fija
  por plan (`perill.html#pla-inuncat`).
- La línea del plan en la portada lleva a su ficha: en prealerta, esa; en
  alerta o emergencia, la del episodio abierto en el historial (`idFitxa`); si
  aún no se ha leído el historial, la ficha fija.
- Con un plan en prealerta, «Perill» ya no dice que no hay nada.

## Consecuencias

- La prealerta sigue sin avisar al móvil ni a Telegram (ADR 0051): solo se ve
  en la web.
- No quedaba en el historial: al acabar, la ficha desaparecía de «Ara» sin
  dejar rastro. Desde el 24-10-2026, sí (ver el cambio de esa fecha, abajo).

## Cómo se validó

- Pruebas: `plans_prealerta` en `avisos.json` (solo prealerta y solo esos
  campos) y la dirección de la ficha calculada en la portada, con Node.
- En local, con los datos del 15-10-2026: de la portada a la ficha en catalán
  y castellano, en Chromium (móvil) y Firefox (ordenador), sin errores de
  JavaScript; el enlace abre el comunicado del día. axe-core sin infracciones
  en «Perill» y en la portada.

## Cambio del 15-10-2026: el comunicado más reciente, también en alerta

El INUNCAT pasó a alerta el 15-10-2026 a las 19:09, sin comunicado todavía; el
PDF salió a las 19:43. La ficha del episodio, que sale del historial, se quedó
con el enlace a la página general de Protección Civil que llevaba el aviso, y
Juanjo preguntó: «el enlace no lleva a un pdf como es habitual por que?».

Desde la 3.85.2, `comunicats` de `avisos_bot.py` pone en cada pasada, en la
ficha de cada plan activo, el comunicado más reciente (`comunicat`); si
Protección Civil publica una actualización, la ficha pasa a la nueva, y al
acabar el episodio se queda con la última. El texto pierde el enlace al
comunicado que llevaba, si lo tenía, para que no haya dos. «Perill» lo
muestra como «Comunicat de Protecció Civil (PDF)», como la prealerta. El
mensaje ya enviado por Telegram o al navegador no cambia, pero su enlace lleva
a la ficha, que ya tiene el PDF.

Validado: prueba `test_el_pla_porta_el_comunicat_mes_recent`; en local, con
los datos de esa tarde, la ficha enlaza el PDF en catalán y castellano, en
Chromium, Firefox y WebKit, en ordenador y móvil.

## Cambio del 15-10-2026: aviso de cada comunicado nuevo

Juanjo propuso que quien recibió la alerta reciba también el comunicado
cuando cambie («no digo enviar ahora, digo cuando cambie»; «exacto,
publicalo»). Desde la 3.86.0, con un plan en alerta o emergencia, cada
comunicado distinto del último avisado (también el primero, si la alerta salió
sin él) es un aviso de peligro, por Telegram y en el navegador:
«Protecció Civil: actualització del pla … (…)», el enlace «Comunicat (PDF)»
y el de la ficha; breve, porque el plan ya se avisó (Juanjo, 3.86.1: «yo
hablaria de actualizacion, texto breve porque ya se ha publicado antes»). En
la notificación de la app de Android y de la web, que no admite enlaces en el
texto, «Toca per veure el comunicat.», y al tocarla se abre el PDF, como el
radar en el aviso de lluvia. Lleva a la ficha del episodio sin
cambiarla (`nomes_avis`). No avisa si en la misma pasada cambia la fase (ese
aviso ya lleva el PDF), ni en prealerta, ni si la fuente deja de traer el
comunicado una pasada y vuelve el mismo: el estado guarda el último avisado.
Un estado anterior a este cambio, sin esa clave, da por avisado el comunicado
vigente, para que al publicarlo no salga el del INUNCAT de las 19:43.

Validado: `test_un_comunicat_nou_s_avisa_una_vegada` y
`test_el_comunicat_nou_porta_a_la_fitxa_sense_canviar_la`.

## Cambio del 24-10-2026: la prealerta, en el historial al acabar

De madrugada salió en la web una prealerta de Protección Civil, que
desapareció cuando Protección Civil vació su lista de planes (a las 04:47,
según la fecha de actualización del conjunto de datos de la Generalitat).
Juanjo: «ya no está y tampoco está en el historial de avisos, que ha
pasado?». No quedaba rastro ni en el NAS, así que ni siquiera se pudo saber
qué plan era. No guardarla fue decisión del agente (este ADR), no de Juanjo.
El agente propuso guardarla, sin avisar al móvil, y Juanjo lo aprobó («si,
hazlo»).

- `avisos_bot.prealertes` apunta en el estado (`prealertes`) cada plan en
  prealerta que se ve, con su comienzo oficial (`des_de`, hora de Madrid), el
  motivo y el comunicado. Cuando deja de estar en prealerta, añade al
  historial una ficha **ya cerrada** (`prealerta:<PLA>`, nivel `prealerta`):
  «Protecció Civil: pla … en fase de prealerta», qué quería decir, el motivo
  según Protección Civil (en catalán, tal como lo publica, también en
  castellano), «La prealerta no arriba com a avís», el comunicado o la página
  de Protección Civil y el final: «Ha passat a fase d'alerta» o «Ja no consta
  en prealerta». En «Perill» sale en «Últims 30 dies» como las demás.
- Mientras dura no hay ficha en el historial: la de «Ara» sigue saliendo de
  `plans_prealerta`, así que no se duplica ni enciende el punto de «Perill»,
  y sigue sin avisar (ADR 0051).
- Una prealerta oculta por no tener motivo meteorológico (ADR 0062) solo se
  apunta si llegó a mostrarse. Sin datos de Protección Civil en una pasada,
  no se toca nada.

Validado: `tests/test_historial.py`,
`test_la_prealerta_queda_a_l_historial_quan_acaba` (la ficha al acabar, sin
repetirse, el paso a alerta, la oculta y la pasada sin datos); en local, una
prealerta simulada en «Perill», con su ficha en «Últims 30 dies».

