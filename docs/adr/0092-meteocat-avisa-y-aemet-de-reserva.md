# 92. Meteocat avisa por fenómeno y AEMET queda de reserva

Fecha: 2026-10-16 · Estado: aceptado; AEMET de reserva, sustituido el mismo día por el ADR 0093 (AEMET avisa de lo que Meteocat no cubre)

## Contexto

El 16-10-2026 Juanjo vio en la página del radar de meteo.cat el mapa de
avisos de peligro del sábado 17: el Vallès Occidental en peligro alto por
intensidad de lluvia. La app no lo mostraba. Dos causas:

- **La lectura fallaba** (`smp: 'list' object has no attribute 'get'`, en
  `errors` de cada pasada). Con avisos, la página entrega la lista agrupada en
  bloques que repiten los mismos episodios (`[[…], […]]`); el ADR 0067 se probó
  con la lista vacía y con el ejemplo de la API, que es plana. La prueba diaria
  solo miraba que la lista estuviera, no que se pudiera leer, y no avisó. Como
  decidió el ADR 0067, sin lectura no se decía nada: la app callaba un peligro
  alto en el barrio.
- **Los avisos de observación no se leían**: «Avís Vigilància» y «Avís
  Vigilància per Temps Violent», los que Meteocat emite cuando el fenómeno ya
  ocurre, vienen en los mismos datos con otra forma (hora de inicio y de fin y
  las comarcas en el propio aviso, sin franjas).

Al arreglarlo surgió lo que preocupaba a Juanjo: «lo que no quiero son avisos
repetidos que molesten a la gente». AEMET (Prelitoral de Barcelona) y
Meteocat (comarca) avisan del mismo episodio con zonas, umbrales y escalas
distintos: para el sábado, AEMET daba amarillo por lluvia y por tormentas, y
Meteocat alto por lluvia en 30 minutos y moderado en 3 horas. El bot avisaba
por cada aviso y cada fuente: cinco notificaciones del mismo episodio. Una
notificación al día no sirve («en situación de peligro no podemos dar un aviso
al día, … a media mañana el aviso puede cambiar y subir de nivel»). Juanjo
propuso quedarse con Meteocat, «que es el local de aquí», y aprobó dejar AEMET
de reserva («sí, hazlo así y publícalo hoy»).

## Decisión

### Lectura (`smp.py`, 3.87.0)

- La lista de la página se aplana y cada episodio va una vez; cada aviso
  (meteoro, tipo y emisión), también.
- Cuentan los avisos vigentes que no son preavisos: los de previsión, por
  franjas, y los de observación y de temps violent, con su hora de inicio y de
  fin pasadas a franjas de hora local. En el texto, «avís d'observació de
  perill …» / «aviso de observación de peligro …».
- La prueba diaria lee los avisos de verdad (`de_la_comarca`), no solo la
  lista.

### Quién avisa (`avisos_bot.py`)

- **Meteocat avisa**, agrupado por fenómeno (lluvia, nieve, viento, calor,
  frío, mar, temps violent; la lluvia en 30 minutos y en 3 horas son la misma
  lluvia). Se notifica en el momento, a cualquier hora:
  1. el primer aviso del episodio;
  2. una subida de nivel (moderado, alto, muy alto) de un fenómeno ya avisado:
     «Actualització: Meteocat puja a perill molt alt per pluja…»;
  3. un fenómeno nuevo: «… avisa també de perill moderat per vent…»;
  4. horas que el aviso no cubría: «… amplia l'avís…»;
  5. un aviso de observación, aparte de los de previsión del mismo fenómeno:
     dice que ya está ocurriendo («Meteocat: s'observa perill alt per pluja…»);
  6. el final, cuando ya no queda ningún aviso: «Meteocat ja no té cap avís de
     perill per al Vallès Occidental».
- No se notifica una nueva emisión igual, una bajada de nivel ni un aviso menor
  del mismo fenómeno: se ven en «Perill» y en «Avisos actius». El grado de
  Meteocat cuenta por nivel: pasar de 3 a 4 sigue siendo «alto».
- Un fenómeno que deja de constar se da por acabado a los `SMP_FI_MIN` (30)
  minutos, para que el relevo entre dos emisiones no avise dos veces.
- Cada notificación lleva, debajo de lo que ha cambiado, todos los avisos
  vigentes de la comarca, uno por línea con su círculo. Todo el episodio es una
  sola ficha en «Perill» (`meteocat:<hora del primero>`), que se queda con el
  último texto y el peor nivel.
- **AEMET, de reserva**: sus avisos se siguen apuntando en cada pasada, pero
  solo notifican si en esa pasada no se ha podido leer Meteocat. En «Perill» y
  en «Avisos actius» siguen a la vista.
- **Si la lectura falla, a Juanjo en el momento**: cada pasada del NAS lo mira
  y se lo dice una vez por Telegram (`avis_privat`, con reintento), y otra
  cuando vuelve a leerse. Usa la misma marca que la prueba diaria
  (`aprenentatge/smp-falla`), para no decírselo dos veces.
- El estado de antes (`{clave: grado}`, vacío porque la lectura fallaba) se
  toma como vacío: lo vigente al publicar se avisa una vez.

## Alternativas descartadas

- **Una notificación al día por fenómeno**: se descartó por lo dicho; el aviso
  puede subir a media mañana.
- **Solo Meteocat, sin AEMET**: la página de Meteocat no es una API y puede
  cambiar sin aviso, como acaba de pasar; sin reserva, el vecino no recibiría
  nada.
- **Avisar también si AEMET da más nivel que Meteocat**: se planteó a Juanjo y
  no lo pidió. Para la comarca afina más el servicio de aquí.
- **Avisar de las bajadas**: no se pidió; añaden mensajes sin cambiar lo que
  hay que hacer.

## Consecuencias

- Menos notificaciones y ninguna repetida entre fuentes. El sábado 17, tras
  los dos amarillos de AEMET que ya habían salido, llega una sola: el alto de
  Meteocat.
- El final puede llegar de noche, cuando Meteocat retira el aviso.
- Los planes de Protección Civil, el riesgo propio (ADR 0018), la riera y los
  incendios no cambian.

## Evidencia

- Página <https://www.meteo.cat/prediccio/general> del 16-10-2026: la llamada
  `Meteocat.avisosSMP` trae `avisos: [[…], […]]`, dos bloques iguales; cada
  aviso, una versión «Ampliat» (la anterior) y una «Vigent». Para la comarca
  40, el sábado de 12 a 24 h: «Intensitat de pluja en 30 minuts», grado 3, e
  «Intensitat de pluja en 3 hores», grado 2.
- `montflorit.json` publicado ese día: `"smp": null` y el error de arriba.
- `script.min.js` de meteo.cat: `TIPUS_OBSERVACIO="Avís Vigilància"`,
  `TIPUS_TEMPS_VIOLENT="Avís Vigilància per Temps Violent"`; para esos tipos,
  `_calcularAfectacionsDelDiaAvis` usa `dataInici`, `dataFi` y
  `a.afectacions`.
- Estado del bot en el NAS: los dos amarillos de AEMET del sábado ya avisados
  y `"smp": {}`.

## Riesgos y limitaciones

- **Hipótesis sin comprobar con datos reales**: la forma de los avisos de
  observación y de temps violent sale de cómo los usa la web de Meteocat; no
  había ninguno vigente el 16-10-2026. Si llegan con otra forma, la prueba
  diaria y la de cada pasada lo dicen.
- La agrupación por fenómeno depende del nombre del meteoro; uno que no encaje
  en la lista es un fenómeno propio.
- Si Meteocat falla a mitad de un episodio, AEMET solo avisa de lo que no
  estuviera ya apuntado; al volver Meteocat, lo vigente se avisa de nuevo si
  el estado se perdió.

## Validación

`tests/test_smp.py`: la lista agrupada, un recorte de la página real del
16-10-2026, los avisos de observación y de temps violent, las reglas de
notificación paso a paso (primero, nueva emisión, 3 a 4, bajada, subida,
horas nuevas, fenómeno nuevo, observación, final y episodio nuevo), el estado
de antes, AEMET de reserva y el aviso a Juanjo al fallar y al volver. Con la
página real y el estado real del NAS, la primera pasada da una notificación
(el alto de Meteocat) y la siguiente, ninguna. Las 470 pruebas del proyecto.

## Cambio del 18-10-2026 (3.135.0): solo lo que queda

Meteocat mantiene en el aviso vigente las franjas ya pasadas: el domingo 18 a
las 6:40 seguía dando las del sábado 17 junto a las del lunes 19, y la ficha
de «Perill» decía «Observat ara, perill alt per temps violent: dissabte 17 de
19 a 22 h» con el círculo naranja. Juanjo: «ahora mismo marca esto, pero no
está una parte ya pasada?». Había dos fallos: el texto copiaba todas las
franjas (el mensaje del sábado a las 19:13 ya traía «de 12 a 18 h») y la
ficha se quedaba con el texto del último mensaje enviado.

- **Solo las horas que quedan** (`smp.pendents`), desde la hora en curso: las
  líneas de `montflorit.json` (que salen desplegadas en «Avisos actius» y en
  /avisos_actius del bot), el resumen por fenómeno (que ya lo hacía) y lo que
  decide y escribe `avisos_bot.py`. Un aviso sin ninguna hora por delante no
  sale. Los avisos enteros siguen en `montflorit.json` para la gráfica y para
  saber qué cubre Meteocat (ADR 0093).
- **El final, a su hora**: como se decide con lo que queda, el episodio se
  cierra con «ja no hi ha cap avís de perill» media hora después de la última
  hora avisada, aunque Meteocat no haya retirado el aviso.
- **La ficha dice lo que queda**: en cada pasada sin nada nuevo, si las líneas
  cambian (una franja que pasa, una observación que acaba), la ficha abierta
  de «Perill» se rehace sin enviar ningún mensaje, con el título neutro («avís
  de perill moderat per pluja») y el color de lo que queda. El texto se
  guarda en el estado (`oficials.smp.text`) y lo aplica `historial`. Si las
  líneas son las mismas, se queda el texto del último aviso.

Los mensajes ya enviados no se tocan: son lo que se envió. Validación:
`tests/test_smp.py` con el caso del 17-18-10 (aviso observado a las 19:13, la
ficha el domingo solo con el lunes y en amarillo, ningún mensaje, y el final
al acabar el lunes); la lectura real de Meteocat del 18-10 a las 6:40, que
deja solo el amarillo del lunes; la ficha vista en Chromium y Firefox.

## Un estado viejo no continúa el episodio de antes (24-11-2026, 3.239.4)

El NAS y la reserva de IONOS llevan cada uno su estado de Meteocat
(`oficials.smp` en `bot-avisos.json`). La reserva se paró el 19-11 a media
avisada de viento, con su episodio sin cerrar; el 24-11, al cubrir unos
minutos al NAS, tomó la lluvia de ese día por «actualització, avisa també de
perill moderat per pluja» del episodio del 19 y abrió con esa clave una
segunda ficha del mismo aviso que el NAS ya tenía abierta desde el 23. El NAS
la recogió del historial publicado (`fusiona`) y «Perill» mostró dos fichas
de un solo aviso, que al recortarse las horas acabaron diciendo horas
distintas (revisor, 24-11-2026).

- **Un estado viejo es un episodio acabado** (`decideix_smp`): si ninguno de
  sus fenómenos se ha visto en `SMP_FI_MIN` minutos y Meteocat trae avisos,
  empieza un episodio nuevo («avís de perill…», no «actualització») y el
  viejo se cierra en el historial sin mensaje.
- **Se adopta el episodio de la otra máquina** (`adopta_smp`): si además el
  historial publicado tiene una ficha de Meteocat abierta que no es la de
  este estado, se toma esa ficha como episodio y lo que Meteocat dice ahora
  como ya avisado: la otra máquina lo avisó. No se manda nada.
- **Una sola ficha abierta de Meteocat** (`historial`): si aun así hay otra,
  se cierra con «Era el mateix avís de Meteocat que una altra fitxa» y el
  enlace a la del episodio actual. Esto cierra también la duplicada del 24-11.

Validación: `tests/test_bot.py` (estado del 19-11 con la lluvia del 24-11, con
y sin ficha abierta publicada, y un estado vivo que no se toca) y
`tests/test_historial.py` (dos fichas abiertas); el estado real del NAS del
24-11 pasado por `historial` deja abierta solo la del 23-11.
