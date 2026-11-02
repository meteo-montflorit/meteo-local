# 62. Planes de Protección Civil sin motivo meteorológico

Fecha: 2026-10-10 · Estado: aceptado

**02-11-2026 (3.208.0):** tampoco se muestra un plan de otras comarcas (al final).

**16-10-2026 (ADR 0093):** el motivo es un aviso del fenómeno del plan (lluvia para el INUNCAT, viento para el VENTCAT…), de AEMET o de Meteocat; un plan sin fenómeno meteorológico se muestra siempre.

## Contexto

El 10-10-2026 la web seguía mostrando arriba del todo «Protecció Civil: pla
d'inundacions (INUNCAT) en fase d'alerta» y estaba en «Mode avís», sin
lluvia ni previsión de lluvia. Juanjo: «es fuente de desinformación» y,
después, «el plan no está abierto por motivos meteorológicos sino de
recuperación, ¿no hay forma de detectarlo y eliminar ese aviso de la web?
Repito que confunde mucho».

El plan seguía activo de verdad: los datos abiertos de la Generalitat
(reescritos el 09-10 a las 19:05) lo daban en alerta desde el 08-10 a las
17:14, con la descripción «Emergència INUNCAT 3-7 Octubre». El último
comunicado, del 08-10 a las 17:35, pasaba de emergencia a alerta «per la
previsió de continuació de les pluges» de esa tarde y por la recuperación
en el Vallès Oriental, el Maresme y Xerta. Las noticias de Protecció Civil
no publicaban nada del INUNCAT después del 07-10.

Los datos no dicen por qué se mantiene un plan. Pero durante un temporal
Protecció Civil publica comunicados cada pocas horas, y activa el INUNCAT
por previsiones que llegan con avisos de AEMET.

## Decisión

- **Un plan en prealerta o alerta se muestra** solo si su último
  comunicado tiene menos de 24 horas (`PLA_COMUNICAT_H`) o si AEMET tiene
  un aviso por lluvia o tormentas en el Vallès, vigente o para las
  próximas 24 horas (`PLA_AVIS_H`). **La emergencia se muestra siempre.**
  Si no se han podido leer los avisos de AEMET, o el plan no trae fecha,
  se muestra (`prevision.pla_per_temps`).
- **Uno que no cumple** va aparte (`plans_ocults` en los datos): no sale en
  «Avisos actius», «Si surts», «Consultes» ni el bot, no pone la página en
  modo aviso y el registro del aprendizaje lo apunta como no activo
  (`pla_inuncat`), porque es el estado que se mostraba.
- **Los avisos del canal, el bot y el navegador**: ocultarlo no es un final
  («ja no està en alerta» sería falso); si vuelve a mostrarse en la misma
  fase no es nuevo; si se desactiva mientras está oculto, no se avisa,
  porque ya no se mostraba. Si sube de fase, sí.
- **«/avisos_actius»** no dice «no hi ha plans de Protecció Civil
  activats» mientras haya uno oculto: dice solo que no hay avisos de AEMET
  ni tiempo excepcional.
- «D'on surt» explica la regla.

## Alternativas descartadas

- **Mostrarlo con una nota que diga la contradicción** («Ara no plou ni se'n
  preveu…»): fue la primera propuesta, con el criterio del 07-10-2026 (lo
  oficial se mantiene y se dice la contradicción). Juanjo prefirió quitarlo:
  un plan mantenido por la recuperación no habla del tiempo, que es de lo que
  trata la web.
- **Usar también el riesgo que calcula la página**: el riesgo ya sale como
  aviso propio, y la regla no depende así de nuestra propia previsión.
- **Avisar a Protecció Civil**: no hay indicios de error; mantenerlo es
  decisión suya.

## Consecuencias

Un plan oficial activo puede no verse en la web. Si Protecció Civil lo
mantiene por un riesgo que no viene de la lluvia prevista (crecidas de
ríos lejanos, por ejemplo) y no publica comunicado nuevo, la web no lo
dirá; los ríos de la zona los vigila el aviso de la riera (ADR 0027).

## Evidencia

Datos abiertos `wj9c-j6vf` del 10-10-2026: INUNCAT, ALERTA, activado,
`fasedatahora` «08/10/2026 17:14». Comunicado
`I-127743_ACTUALITZACIO--ACTIVAT_INUNCAT_202610081735.pdf`. Noticias de
Protecció Civil (interior.gencat.cat) del 06-10 al 09-10-2026, sin nada del
INUNCAT después del 07-10. Con los datos del 10-10-2026 a las 08 h, el plan
queda oculto.

## Riesgos y limitaciones

- Si un temporal empieza sin aviso de AEMET y Protecció Civil no publica
  comunicado en 24 horas, el plan no se vería; es poco probable, porque
  cada activación lleva comunicado.
- La hora de `fasedatahora` se lee como hora local.

## Validación

`tests/test_avisos.py`: la regla con el caso del 10-10-2026 (oculto),
comunicado reciente, emergencia, aviso de AEMET dentro y fuera de las 24
horas, de otro tipo o de otra zona, y sin avisos leídos. `tests/test_bot.py`:
ocultarlo, volver a mostrarlo y desactivarlo oculto no envían nada; subir de
fase sí; «/avisos_actius» con un plan oculto.

## Cambio del 02-11-2026 (3.208.0): planes de otras comarcas

A las 12:07 la Generalitat activó el INUNCAT en alerta («SMP - Intensitat de
pluja en 30 minuts 2 i 3/11») y la web lo daba como peligro alto para el
barrio, con la página en modo aviso. El comunicado
(`I-128574_INICI--ACTIVAT_INUNCAT_202611021221.pdf`) lo basaba en los avisos
de Meteocat y nombraba el Barcelonès, el Baix Llobregat, el Garraf, el Baix
Penedès y el Tarragonès y, de madrugada, el Alt Camp, el Alt Penedès y el
Baix Camp. Meteocat tenía avisos de intensidad de lluvia en esas mismas
ocho comarcas (idComarca 1, 3, 8, 11, 12, 13, 17 y 36) y ninguno en el
Vallès Occidental (40). Juanjo: «no se puede mejorar el sistema para no dar
alertas que no afectan al barrio?».

**Decisión.** Un plan en prealerta o alerta tampoco se muestra si Meteocat
tiene avisos vigentes de su fenómeno en alguna comarca y ninguno en el
Vallès Occidental (`prevision.de_altres_comarques`). Esta regla va antes de
la del comunicado reciente: un plan de otras comarcas no se muestra ni en
sus primeras 24 horas. Si Meteocat amplía el aviso al Vallès Occidental, el
plan vuelve a salir. `smp.llegeix` publica para ello `fenomens_catalunya`,
los fenómenos con aviso vigente (no preaviso) en cualquier comarca,
leídos de la misma página o de la API. Ocultarlo sigue lo dicho arriba: no
avisa de final ni, si vuelve, de novedad en la misma fase.

**Lo que no cambia.** La emergencia se muestra siempre. Si Meteocat no
tiene avisos del fenómeno en ninguna comarca, el plan responde a otra cosa
(recuperación, crecidas) y sigue la regla anterior. Sin lectura de Meteocat,
o con datos de antes de la 3.208.0, se muestra. Los avisos de AEMET se
muestran aparte como siempre: el 02-11-2026, el amarillo por lluvia en el
Prelitoral de Barcelona de 22:00 a 04:00.

**Alternativas descartadas.** Leer las comarcas del comunicado o de la
descripción del plan: son texto libre y cambian de forma («SMP - Intensitat
de pluja…», «Avís-Intensitat de pluja», «Pluges intenses», «Emergència
INUNCAT 3-6 Octubre» en el registro del NAS), y el comunicado es un PDF.
Mostrar junto al plan una línea «Meteocat no té cap avís per al Vallès
Occidental»: el vecino seguiría viendo un peligro alto que no es suyo.

**Riesgo.** Que Protección Civil extienda un plan a una comarca sin aviso de
Meteocat. El comunicado del 02-11-2026 dice que el plan se basa en las
previsiones de Meteocat, y en el registro no hay ningún caso así; una
emergencia se vería igualmente.

**Validación.** `tests/test_avisos.py` (`test_un_pla_d_altres_comarques_no_es_mostra`):
el plan del 02-11-2026 con el aviso de AEMET en el Vallès queda oculto; se
muestra en emergencia, con aviso de Meteocat en el Vallès, sin avisos de su
fenómeno en Cataluña, sin lectura de Meteocat y si el plan es de otro
fenómeno. `tests/test_smp.py` (`test_fenomens_amb_avis_a_qualsevol_comarca`):
avisos de previsión y de observación, sin los preavisos. Con los datos reales
de las 12:33, Meteocat da `["pluja"]` en Cataluña y ningún aviso en el
Vallès Occidental.
