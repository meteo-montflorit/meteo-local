# 66. Cada mensaje dice de qué zona habla

Fecha: 2026-10-10 · Estado: aceptado

## Contexto

Al revisar la ficha «Trànsit» de «Consultes», titulada «Trànsit a prop de
Montflorit», Juanjo señaló que debería decir que es en un radio de 5 km de
Montflorit: «la gente en principio no sabe si es el tráfico en Cataluña, en
Montflorit o qué. Esto se aplica a otras alertas». «A prop» no dice nada
(como ya había dicho del «Seguiment de prop», ADR 0010).

## Decisión

Cada texto del bot, del canal, de los avisos y de la web dice de qué zona
habla, con la cifra si hay un radio:

- **Tráfico** (radio `config.TRANSIT_RADI_KM`, 5 km, ADR 0052): «Trànsit a
  menys de 5 km de Montflorit» en «Consultes» y en /transit; en «Si surts»,
  «Trànsit ara: 2 incidències a menys de 5 km», «cap incidència a menys de
  5 km» y «Ara hi ha retencions o talls a menys de 5 km»; el menú del bot,
  «El trànsit a menys de 5 km»; «Com funciona», igual. Una prueba comprueba
  que el radio sigue siendo 5 km: si cambia, hay que cambiar los textos.
- **Radar** (/radar): «No s'acosta pluja a Montflorit en 2 hores», «Arribaria
  pluja a Montflorit…», «Pluja a sobre de Montflorit». En la web no hace
  falta: va dentro de «Ara a Montflorit».
- **AEMET** en el resumen y en /avisos_actius: «… al Vallès», como ya decían
  la web y el aviso (la zona de AEMET es el Prelitoral de Barcelona).
- **Peligro calculado**: «Avís de perill a Montflorit (groc): …» y, en
  /avisos_actius, «Temps excepcional a Montflorit».
- **Incendios**: la distancia, «a 3,2 km de Montflorit», en la web y en
  /avisos_actius (el aviso ya decía «a prop de Montflorit» con la distancia).

Ya lo decían y no se tocan: el sol, el aire (zona de unos 10 km alrededor de
Bellaterra), el polen (Bellaterra, a 3,1 km), los trenes (cada estación), el
Pla Alfa (Cerdanyola), la riera (Sant Cugat) y los avisos de lluvia.

## Los planes de Protección Civil

Se activan para Cataluña o para unas comarcas, según cada comunicado, y ni
los datos abiertos ni el comunicado (texto libre) dicen de forma fiable qué
zona abarcan: el texto del plan no dice zona, para no afirmar una que no se
sabe. De la 3.54.0 a la 3.118.x iba acompañado de si Meteocat tenía aviso
de peligro para el Vallès Occidental; desde la 3.119.0 los avisos de
Meteocat van aparte (ADR 0067). Desde la 3.208.0, un plan cuyo fenómeno
Meteocat avisa en otras comarcas y no en el Vallès Occidental no se muestra
(ADR 0062).
