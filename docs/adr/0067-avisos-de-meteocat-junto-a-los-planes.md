# 67. Avisos de peligro de Meteocat para el Vallès Occidental, junto a los planes

Fecha: 2026-10-10 · Estado: aceptado (cuándo se leen, cambiado por el ADR 0071; la lectura y cómo avisan, por el ADR 0092; la API de reserva, por el ADR 0109)

## Contexto

Un plan de Protección Civil en alerta («Pla d'inundacions (INUNCAT) en fase
d'alerta») no dice a qué zona afecta, y el vecino no sabe si va con él (ADR
0066). Juanjo preguntó qué se podía hacer y aprobó esta vía (10-10-2026:
«de acuerdo hazlo así»).

Lo comprobado ese día:

- Los datos abiertos de los planes (conjunto `wj9c-j6vf`) solo traen plan,
  fase, si está activado, una descripción corta («Emergència INUNCAT 3-7
  Octubre») y el PDF del comunicado. En el catálogo de datos abiertos de la
  Generalitat no hay ningún conjunto con la zona de cada activación.
- El comunicado (PDF del 08-10-2026, I-127743) describe la zona en texto
  libre y no siempre con nombres («comarques del litoral i prelitoral nord i
  central»): leerlo daría errores.
- Los avisos de peligro de Meteocat (situació meteorològica de perill, SMP)
  son por comarca, y el propio comunicado se apoya en ellos.
- **La API de Meteocat no sirve**: sus condiciones de uso dicen «No difondre
  a tercers, total ni parcialment, la informació rebuda de l'SMC», el alta
  pide el NIF y la suscripción gratuita dura como mucho un año.
- **Las páginas públicas de meteo.cat llevan los mismos avisos**, con la
  estructura de `/smp/episodis-oberts` de la API, en la llamada
  `Meteocat.avisosSMP({… avisos: [...] …})` (la portada y
  <https://www.meteo.cat/prediccio/general>, unos 310 KB). Su aviso legal
  (<https://www.meteo.cat/wpweb/avis-legal/>) permite reutilizar lo que
  publica en abierto sin alterarlo, sin desnaturalizarlo, citando la fuente
  e indicando la fecha: la misma base que el radar (ADR 0019).
- En `script.min.js` de meteo.cat (`_crearAvisosCombinatsLayer`) el grado de
  peligro va de 1 a 6: 1-2 moderado, 3-4 alto, 5-6 muy alto, y el mapa solo
  pinta los avisos vigentes que no son preavisos. El Vallès Occidental es la
  comarca 40 (`IDComarca` de `comarquesAmbMar.json`, el mapa de la web).

## Decisión

- **Con un plan a la vista** (los que no se ocultan por el ADR 0062), cada
  pasada lee la página de predicción general de meteo.cat (`smp.py`) y se
  queda con los avisos vigentes, no preavisos, que afectan a la comarca 40.
  Sin plan, no se lee: no se muestra en ningún otro sitio.
- **Junto al plan** (web, /avisos_actius y el aviso del plan nuevo por
  Telegram y el navegador) va una línea por aviso, con el círculo de su grado
  (ADR 0065):
  «Meteocat: avís de perill alt per «Intensitat de pluja» al Vallès
  Occidental, dissabte 10 de 12 a 24 h (Intensitat > 20 mm / 30 minuts; emès
  a les 10:09).» El meteoro y el umbral, tal como los publica Meteocat, en
  catalán también en la versión castellana (lo oficial ajeno, en su idioma);
  las franjas, las suyas, juntas si son seguidas; los días, por su nombre,
  para que no caduquen al pasar la medianoche.
- **Sin aviso**: «Meteocat no té cap avís de perill per al Vallès Occidental
  (dades de les 19:00)», con un círculo blanco.
- **Si la lectura falla**, no se dice nada: ni que hay aviso ni que no.
  El error queda en `errors` («smp: …»), que no avisa en la página.
- **Prueba diaria** (`aprenentatge.diari`, a la hora de verificación): si la
  página deja de traer los avisos, se le dice una vez a Juanjo por Telegram,
  y otra cuando vuelven (marca `smp-falla` en el directorio de aprendizaje).
- «Fonts i crèdits» cita a Meteocat como fuente de estos avisos.

## Cambio del 11-10-2026 (3.58.0)

Se leen en cada pasada, no solo con un plan: avisan como los de AEMET, van a
la página «Perill» y, sin plan, salen solos en «Avisos actius» (ADR 0071).

## Cambio del 16-10-2026 (3.87.0)

La lectura fallaba desde el primer aviso real: la página agrupa la lista en
bloques repetidos. Se arregla, se leen también los avisos de observación y de
temps violent, y la prueba diaria lee los avisos de verdad. Meteocat pasa a
avisar por fenómeno y AEMET queda de reserva (ADR 0092).

## Riesgos y limitaciones

- No es una API: si Meteocat cambia su página, la lectura falla hasta que se
  arregle (lo detecta la prueba diaria).
- **Hipótesis descartada el 25-10-2026 (3.202.0)**: las franjas («12-18»)
  no son horas locales, sino horas UTC del día UTC («…T00:00Z»). El aviso de
  acumulación del 19-10-2026 iba de `dataInici` 06:00Z a `dataFi` 05:59Z del
  20, justo de la franja 06-12 a la 00-06, y la prensa daba esas franjas
  desplazadas el desfase de cada época. Hasta la 3.201.0 se reproducían tal
  cual y cada aviso de previsión salía 1 h antes en invierno y 2 h en verano
  (el 20-10, «ja no hi ha cap avís» a las 6:03 con el aviso vigente hasta las
  7:59). Desde la 3.202.0 cada franja pasa a su intervalo UTC y de ahí a horas
  de Madrid (`smp.hores`, ADR 0128). Sigue sin comprobar que
  `auxiliar` no cambia nada: se cuentan todas las afectaciones de la
  comarca. No había ningún aviso vigente el 10-10-2026 para verlo con datos
  reales: las pruebas usan el ejemplo de la documentación de la API.
- Cada lectura pesa unos 310 KB; con un plan activo y el modo vigilancia,
  cada 6 minutos.

## Validación

`tests/test_smp.py`: lectura de la página, filtro de comarca y de
preavisos, grado, franjas juntas, textos en los dos idiomas, la línea en
/avisos_actius y en el aviso del plan, sin lectura nada, y la prueba diaria.
Contra meteo.cat real el 10-10-2026 a las 19:25: lee la lista (vacía) y da
«Meteocat no té cap avís de perill per al Vallès Occidental». En la web, con
un plan y un aviso simulados, `probar-web` en Chromium y Firefox, escritorio
y móvil, catalán y castellano.

## Cambio del 17-10-2026 (3.119.0): Meteocat, aparte de Protecció Civil

Juanjo: «si pulso en un aviso de meteocat me sale proteccion civil, separalos
de proteccion civil porque son avisos aparte». Con un plan activo, los avisos
de Meteocat iban dentro del bloque del plan en «Avisos actius» desplegado, y
la línea entera llevaba a la ficha del plan. Ahora van siempre aparte, con
un plan o sin él, como ya estaba sin plan (ADR 0071): cada uno con la franja
de su grado y el enlace a su ficha de «Perill», detrás de Protecció Civil.
Lo mismo en /avisos_actius del bot (bloque «Meteocat» propio) y en el aviso
de un plan nuevo, que ya no lleva las líneas de Meteocat, porque Meteocat
tiene sus propios avisos (`decideix_smp`). Se quitan `liniesSmp` (web) y
`text_smp` (avisos_bot.py). Validación: Chromium y Firefox con los avisos
del momento (INUNCAT en alerta y tres de Meteocat), «El temps» y «Si surts»,
en catalán y castellano; `tests/test_smp.py`.

## Cambio del 17-10-2026 (3.129.0): el grado de cada franja

Un aviso de Meteocat lleva el grado y el umbral en cada franja de seis horas,
y hasta la 3.128.0 se tomaba el grado más alto del aviso para todas sus
horas. El aviso de lluvia en 30 minutos de las 18:05 tenía grado 5 el sábado
17 de 18 a 24 h y grado 1 el lunes 19, y la web decía «Dilluns 19: Perill molt
alt»; el enlace a meteo.cat lo enseñaba en amarillo (Juanjo: «cual es lo
correcto?»). Lo correcto era Meteocat.

Ahora `smp.de_la_comarca` parte cada aviso en uno por nivel de la página
(moderado, alto, muy alto) y umbral, cada uno con sus horas, y el resumen
por fenómeno (`smp.per_fenomen`) da una línea por fenómeno y nivel, con cada
hora en el nivel más alto que tiene, sin franjas repetidas (decía «dilluns de
0 a 24 h i de 12 a 24 h») y sin las horas ya pasadas. Afecta a todo lo que
lee los avisos: la portada, la gráfica, los tramos, «Perill», el bot y el
grado que guarda el aprendizaje de la probabilidad de lluvia (ADR 0097), que
hasta ahora apuntaba el grado más alto del aviso también en sus horas de
grado menor. Los avisos por Telegram y en el navegador comparan por
fenómeno (nivel más alto y horas), así que el cambio no dispara ninguno.
