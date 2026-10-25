# 61. Grados más o menos que ayer

Fecha: 2026-10-10 · Estado: aceptado

## Contexto

Juanjo pidió que la previsión de un día o de un tramo dijera cuántos grados
más o menos hará que ayer: «la mayoría de predicciones de otros servicios lo
llevan y es muy útil» (10-10-2026). La estación de casa guarda la
temperatura de cada hora (`estacio-casa.csv`, ADR 0017) y la previsión ya
está corregida con esa misma estación (ADR 0036): las dos cifras se pueden
comparar.

## Decisión

- **Lo previsto contra lo medido.** Cada tramo se compara con las mismas
  horas del día antes: los de hoy, con lo que midió la estación ayer; los
  de mañana, con hoy (lo medido hasta ahora y lo previsto para el resto).
  Cada hora del día antes vale lo mismo que en la previsión: la media de sus
  dos extremos (ADR 0036).
- **La máxima de día y la mínima de noche**: en el día, la mañana y la tarde
  se compara la máxima; en la noche, la mínima.
- **La cifra, desde 2 grados** (`COMPARA_MIN`): la previsión de la máxima
  se equivoca en torno a un grado (ADR 0036), así que «1 grau més» sería
  ruido. Por debajo, «semblant a ahir».
- **Dónde sale**: en la cabecera de cada tramo de «El temps», junto a la
  temperatura («16–23 °C · 2° més que ahir»), y en la línea de la
  temperatura de la previsión del bot, que también usan «Consultes», el
  canal y los avisos del navegador («Temperatura: entre 11 °C i 23 °C, 2
  graus més que ahir»). Mañana se compara con hoy: «2 graus menys que avui».
- **En «Ara», el día entero** (desde la 3.190.0; Juanjo, 23-10-2026: «si
  el día es como el de ayer, más frío, más cálido»): debajo de la
  temperatura y de la parte alta, junto al dibujo del cielo para que la
  tarjeta no crezca, «Avui, 2° més que ahir» o «Avui, semblant a ahir». Es la
  misma cuenta que la línea de la temperatura del resumen del bot
  (`bot.compara_resum`): la máxima de las horas de día (de 7 a 21 h) que
  quedan, contra las mismas horas de ayer. Desde las 18 h (`HORA_DEMA`),
  cuando el resumen pasa a mañana, mañana contra hoy: «Demà, 3° menys que
  avui». Al pulsarla, una burbuja dice qué compara, como la de la parte alta
  (`casa.comparaDia`). Con la línea nueva, la tarjeta se reduce en el móvil
  (letra de la frase, temperatura, dibujo y pastillas): en un móvil de 393 ×
  755 px pasa de 353 a 252 px de alto y la gráfica cabe entera sin desplazar
  (medido el 23-10-2026 con los datos de las 8:00). Para eso, las pastillas
  de debajo van en una fila: la de la lluvia de hoy («3,2 mm avui») solo sale
  si ha llovido algo (Juanjo: «0,0 mm avui» a primera hora no dice nada). Si
  ha llovido, con tres pastillas, van en dos filas. Desde el 25-10-2026
  (3.198.2), la de la lluvia de ahora tampoco sale si no llueve: solo «Plou»
  o «Plugim segons el radar», no «No plou» (Juanjo: «esto solo debe salir
  cuando llueve»). Y el viento, solo cuando molesta (`VENT_MOLEST`): 20 km/h
  o más de media, la fuerza 4 de Beaufort, que según la tabla de AEMET y las
  de los servicios meteorológicos levanta polvo y papeles, o rachas de 40 km/h
  o más, las de «compte» en bici en «Si surts». Del 2 al 25-10-2026, en la
  estación de Sant Cugat, ninguna media hora llegó (media máxima de 14 km/h,
  racha de 33). Sin lluvia ni viento, la tarjeta no lleva pastillas y queda
  más baja; el viento se sigue viendo en la gráfica. Los nombres de la escala
  («fresquito», «fresco») no se usan: son de marinos y «fresco» se leería como
  temperatura. Las rachas del viento,
  solo la cifra entre paréntesis: «Vent 7 km/h (16)».
- **Los datos**: `casa.py` añade a los datos `temperatura_mesurada`, la de
  cada hora en punto de las últimas 72 horas, del registro del NAS y de la
  lectura de la pasada (`registre.temperatures_casa`). La web
  (`web/casa.js`, `comparaTemp`) y el bot (`bot.compara_temp`) hacen la
  misma cuenta, y las pruebas lo comprueban.
- **Sin dato, nada**: si falta alguna hora del día antes, si falla la
  estación o si publica la reserva de IONOS (que no tiene el registro), no
  se compara. Nunca con una previsión del día antes.

## Alternativas descartadas

- **Comparar con la previsión de ayer**: una previsión no es lo que pasó, y
  la estación ya da lo medido.
- **Mañana contra ayer**: «mañana, 3 grados más que ayer» confunde; se
  compara con el día anterior a cada tramo.
- **Decir siempre la cifra**: con diferencias de un grado, más que
  informar, se repetiría el error de la previsión.

## Consecuencias

En el móvil, entre una y tres de las cinco cabeceras de tramo pasan a
ocupar dos líneas, según la anchura (medido el 10-10-2026 de 320 a 412 px:
el bloque de la previsión crece entre 0 y 78 px). Sin desbordamiento.
Juanjo lo vio en un servidor local antes de publicarlo.

## Evidencia

Con los datos reales del 10-10-2026 a las 07 h: la máxima prevista para el
resto del día, 22,7 °C, contra 20,7 °C medidos a las mismas horas del
09-10 (el bot dice «2 graus més que ahir»); mañana, 23 °C contra los 22,7
de hoy («semblant a la d'avui»).

## Riesgos y limitaciones

- El tramo en curso solo compara las horas que quedan («Matí, fins a les
  14 h»), contra las mismas horas de ayer.
- En los días de cambio de hora, las horas se emparejan por la hora del
  reloj, no por el instante.

## Validación

`tests/test_bot.py`: la cuenta (máxima de día, mínima de noche, mañana con
lo previsto de hoy, sin dato no se dice nada) y el texto en los dos
idiomas. `tests/test_web.py`: la web da lo mismo que el bot en los mismos
casos y la cabecera del tramo lleva la diferencia. Probado en Chromium,
Firefox y WebKit de 320 a 1280 px, en catalán y castellano.
`tests/test_web.py` (`test_el_dia_com_l_anterior_a_ara_igual_que_el_bot`):
la frase de «Ara», de día y desde las 18 h, da la misma cifra que el bot.
La tarjeta, en Chromium, Firefox y WebKit a 360, 393 y 1280 px, en tema
claro y oscuro, con el texto más largo («Demà, 12° menys que avui»), sin
desbordamiento.
