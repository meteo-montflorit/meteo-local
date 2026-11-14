# 76. Avisos que se comparten y se entienden en un momento de peligro

Fecha: 2026-10-12 · Estado: aceptado

## Contexto

Juanjo: «quiero que se pueda compartir para poder enviar el mensaje
rápidamente a otros, puede llevar a una página ad hoc que explique la alerta
… tanto la riera como las alertas calculadas por la app».

Al revisar la versión 3.65.0:

- **Compartir:** el botón de cada ficha de «Perill» enviaba solo el título y
  el enlace.
- **Más información de la riera y del tiempo extremo** (los dos avisos que
  calcula la web): llevaba a la metodología técnica, en GitHub, con fórmulas
  y solo en castellano.
- **La riera no salía en la portada**, solo en «Perill», porque los datos
  públicos no llevan su estado.
- **En la tabla de previsión**, el peligro que calcula la web no se veía. Un
  tramo con lluvia muy fuerte decía «pluja forta», y Juanjo: «eso en sí no
  indica ningún peligro especial».

Al ver el ejemplo:

- «demasiado texto para leerlo en un momento de peligro, condénsalo», primero
  de las explicaciones y luego del propio aviso;
- «los botones de compartir tienen que copiar automáticamente» y, después,
  «me refiero a compartir, debe salir el menú de compartir».

## Decisión

Versión 3.66.0.

- **Compartir el aviso entero.** El botón de cada ficha de «Perill» abre el
  menú de compartir del dispositivo con el mensaje completo (sin las líneas
  que son solo un enlace y, si ha acabado, con el final) y el enlace a la
  ficha. Donde no hay menú (algunos navegadores de ordenador, o fuera de
  `https`), se copia solo, al momento: primero de la forma clásica
  (`execCommand`), que funciona también sin `https`; si no, con el
  portapapeles del navegador. Solo si nada de eso funciona se muestra el
  texto ya seleccionado. Nunca se pide copiar a mano.
- **Una explicación corta de los avisos propios**, en «Com funciona», en
  catalán y castellano: «L'avís de la riera de Sant Cugat» (`#riera`) y «Els
  avisos de temps extrem de la web» (`#temps-extrem`). Arriba, destacado,
  qué hacer o qué significa; después, los umbrales en una lista corta y una
  línea con el enlace a la metodología. Las fichas de la riera y del tiempo
  extremo llevan «Què vol dir aquest avís» a esos apartados, en lugar de «Més
  informació» a la metodología. `avisos_bot.ENLLAC_RIERA` y `ENLLAC_PROPI`
  apuntan allí, en la lengua de quien lo lee.
- **Los avisos de la riera y del tiempo extremo, condensados**: primero qué
  hacer, después un solo dato y una nota corta. El de la riera: «No t'acostis
  a la riera. / 54 mm en 3 hores a Sant Cugat (a les 07:26) i el radar en veu
  venir més: amb aquesta pluja ja s'ha desbordat altres vegades. / Avís en
  proves, orientatiu i no oficial.». Los finales, en una línea, sin la nota.
  El del tiempo extremo termina con «Calculat per aquesta web, no oficial.».
  Son los mismos textos de Telegram, del móvil y de «Perill».
- **La riera activa, en «Avisos actius»** de «El temps» y de «Si surts»: el
  título y «No t'acostis a la riera.», con «›» a su ficha exacta de «Perill».
  Sale del historial de `avisos.json`, que la página ya leía cada 5 minutos
  para el punto rojo. `idFitxa` pasa de `perill.js` a `comu.js`.
- **El peligro, en la tabla de previsión.** Cada hora junta los avisos de la
  AEMET y los riesgos que calcula la web (`riscos`) y lleva la barra de color
  de la columna de avisos. El tramo lleva la franja lateral del color del
  nivel y, en la cabecera, «⚠ Avís taronja: pluja molt forta», y se abre
  solo. Se nombra solo lo que da el nivel más alto: con un amarillo de la
  AEMET por lluvia y un naranja de la web, «taronja: pluja molt forta».
  Desde el 17-10-2026 (ADR 0096), los fenómenos distintos de un nivel más
  bajo también se dicen, detrás («Perill alt: pluja · Avís groc:
  tempestes»); el mismo fenómeno sigue diciéndose una sola vez.
- **El aviso de la AEMET no se repite** en el resumen del día de la portada:
  ya sale arriba, en «Avisos actius». En «Consultes › Avui» se queda.
- **«Atrás» vuelve a donde se estaba** desde una página de explicación
  («Com funciona», «Fonts i crèdits»…). De una pestaña a una de esas páginas
  el navegador lo apunta; entre pestañas se sigue sustituyendo, y «El temps»
  vuelve a la portada deshaciendo todos los pasos (`history.go`). Corrige el
  ADR 0074: desde «Què vol dir aquest avís», «atrás» llevaba a la portada y no
  al aviso.
- **El Pla Alfa de «Perill», con su botón de compartir** (era la 3.65.1, que
  se retiró antes de desplegarse para publicarla con todo esto; ADR 0075).

## Alternativas descartadas

- **Una página nueva para cada aviso propio.** Dos apartados en «Com
  funciona», que ya está traducida y enlazada, son menos piezas.
- **Mostrar el estado de la riera desde los datos públicos.** Habría que
  publicar `riera`, que hoy es privado (ADR 0027). El historial de «Perill»
  ya dice lo que cuenta: si hay aviso y de qué nivel.
- **Una tabla de umbrales en «Com funciona».** La traducción automática de la
  página trabaja por párrafos y elementos de lista, no por celdas: va en
  lista.

## Consecuencias

- Un aviso se reenvía con un toque, entero, y quien lo recibe llega a su
  ficha y, desde allí, a una explicación breve.
- La portada enseña todos los peligros activos, la riera incluida, y la
  previsión marca cuándo.

## Evidencia

- Ejemplo con datos inventados sobre los publicados del 12-10-2026: lluvia,
  aviso amarillo de la AEMET, riesgo naranja de la web de 7 a 8 h y peligro
  de la riera.
- En Chromium, sin `https` (la copia local por la IP de casa), sin menú de
  compartir: el botón copia el aviso entero con el enlace, leído después del
  portapapeles.

## Riesgos y limitaciones

- El menú de compartir solo existe en `https` y en los navegadores que lo
  ofrecen; la copia de prueba local no lo enseña.
- La riera llega a la portada con hasta 5 minutos de retraso (la lectura del
  historial).

## Validación

- 393 pruebas en verde, con nuevas para compartir (menú y copia), el peligro
  por hora y por tramo, las líneas del resumen y «atrás».
- «Atrás» en Chromium, Firefox y WebKit: Perill → «Què vol dir aquest avís» →
  atrás, a Perill → atrás, a la portada → atrás, fuera; «El temps» desde la
  explicación, a la portada.
- `probar-web` (tres navegadores, móvil, tableta y escritorio, claro y
  oscuro) en «El temps», «Perill», «Si surts», «Consultes» y «Com funciona»,
  en catalán y castellano, sin errores ni desbordamiento; axe-core sin
  incidencias.

## Ampliación del 12-10-2026 (3.66.1): «pluja» o «possible pluja»

El resumen del día decía «Pluja: possible de 7 a 10 h (probabilitat fins al
95 %)»: «possible» con un 95 %. Ahora usa las palabras de la columna «Cel» de
la tabla (Juanjo: «hazlo»): «pluja» desde el 50 % y «possible pluja» desde el
20 %, en cada franja: «Pluja de 7 a 10 h (probabilitat fins al 95 %); possible
pluja de 18 a 19 h (fins al 25 %).». Lo mismo en «Aquesta nit: …», en
«Consultes › Avui» y «Demà», y en el resumen diario de Telegram y del móvil
(`bot.text_franges`).


## Corrección del 16-10-2026 (3.93.1): de una explicación a otra pestaña

Juanjo vio en el móvil que «atrás» pasaba por todas las páginas vistas, en
vez de ir a la portada. La causa: de una pestaña a una explicación
(«Avisos», «Com funciona»…) el navegador apunta un paso, y si desde la
explicación se iba a otra pestaña, esta sustituía a la explicación, pero la
pestaña de debajo seguía apuntada. Con El temps → Si surts → campana →
Consultes, «atrás» iba a Si surts y después a la portada; cada explicación
visitada dejaba una pestaña más.

Ahora, de una explicación a una pestaña (con la portada dos pasos atrás),
`comNavega` responde `torna`: se vuelve a la pestaña de debajo
(`history.go`) y, al llegar, se sustituye por la nueva (el destino viaja en
`sessionStorage`; si el navegador no lo permite, se sustituye la explicación,
como antes). Así solo queda la portada debajo de la pestaña. Al volver, la
pestaña de debajo puede verse un instante antes de la nueva. «Atrás» desde
una explicación sigue volviendo a la pestaña de donde se venía.

Validación: prueba nueva en `tests/test_web.py`; en Chromium (Pixel 7),
WebKit (iPhone 15) y Firefox, ocho recorridos que mezclan pestañas,
«Avisos» y «Com funciona», con la portada después de un «atrás» y fuera
después del segundo, y la pestaña de origen después de un «atrás» desde
una explicación.

## Con una ventana abierta (17-10-2026)

Desde la gráfica en grande (ADR 0096), compartir decía «Enllaç copiat» sin
copiar nada (Juanjo: «dice copiado pero no se copia nada»). Con una ventana
modal abierta, el resto de la página queda inerte: el texto que se
seleccionaba para copiar y el aviso iban fuera de la ventana. Ahora los dos
van dentro de la ventana abierta, si la hay (`llocActiu` en `comu.js`).
Comprobado en Chromium leyendo el portapapeles.

## Simplificación del 14-11-2026 (3.221.0): la riera, sin cifras

- **Contexto**: tras el aviso de la riera del 14-11-2026, que se reenvió por
  WhatsApp, Juanjo: «demasiados números para la gente en los mensajes.
  Simplifica los mensajes, que sean más fáciles de entender sin leer tanto».
- **Decisión**: los mensajes de la riera dicen lo que pasa y qué hacer, sin
  cifras ni horas; las cifras están en «Riera», adonde lleva el enlace del
  mensaje (ADR 0027). Preaviso: «El radar ve venir lluvia fuerte, pero aún no
  ha llovido mucho. Si empieza a llover fuerte, no te acerques a la riera. Te
  avisaremos si se confirma.» Atención: «Ya llueve fuerte en Sant Cugat y
  viene más. La riera se puede desbordar: no te acerques.» (sin más lluvia en
  el radar: «Si sigue, la riera se puede desbordar…»). Peligro: «No te
  acerques a la riera. Ha llovido tanto como otras veces en que se
  desbordó.» Final: «Hace 3 horas que no llueve fuerte. Si vuelve, volverá el
  aviso.» o, si salió del radar, «La lluvia fuerte que preveía el radar no ha
  llegado…». Los avisos siguen con «Aviso en pruebas, orientativo y no
  oficial».
- **Validación**: `tests/test_bot.py` (`test_riera_avis_i_final` comprueba
  que la línea del aviso no lleva cifras).
