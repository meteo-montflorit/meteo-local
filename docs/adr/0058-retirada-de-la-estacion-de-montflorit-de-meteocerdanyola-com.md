# 58. Retirada de la estación de Montflorit de meteocerdanyola.com

Fecha: 2026-10-09 · Estado: sustituido por el ADR 0130

**22-11-2026 (ADR 0130).** Con el permiso de su responsable, la estación de Montflorit vuelve como vecina para la lluvia y la temperatura, y la de Cerdanyola Centre da el viento medio de «Ara». Lo que sigue explica la retirada de octubre.

## Contexto

Desde el 05-10-2026 (ADR 0004) la página leía minuto a minuto la estación de
Montflorit de meteocerdanyola.com, una web particular, y la usaba como
primera fuente de «¿llueve ahora?», como verdad de la lluvia para aprender
(ADR 0012, 0026 y 0049), como referencia del pluviómetro de casa (ADR 0017)
y como dato complementario de la riera (ADR 0027). El permiso para usarla
era deducido, no expreso, y el ADR 0004 ya dejaba escrito que si su
responsable lo pedía, se quitaba. El 09-10-2026 Juanjo pidió quitar toda
referencia a esa estación. El motivo es personal y no se escribe aquí.

## Decisión

- **No se lee nada de meteocerdanyola.com** y ninguna página, README ni
  código la cita como fuente. `ara` desaparece de `casa.json` y de
  `montflorit.json`; la única estación del barrio es la de casa (`ara_casa`,
  ADR 0017).
- **«¿Llueve ahora?»** lo dice solo el pluviómetro de casa: «plou» si ha
  recogido algo en los últimos 15 minutos (`PLOU_ARA_MIN`). Su cero se
  muestra como «no plou» en la web y el bot; «D'on surt» avisa de que a veces
  no marca la lluvia débil, y la línea del radar lo completa («Pluja a
  sobre» cuando el radar la ve encima). Lo mismo en el modo aviso, el aviso
  de antes de llover (ADR 0022), los riesgos de ahora (ADR 0018, que pierden
  la lluvia de 12 horas medida: solo queda la prevista) y la riera (ADR 0027,
  que deja de decir la lluvia de Montflorit).
- **Verdad de la lluvia para aprender** (`aprenentatge.pluja_observada`,
  ADR 0012): lo que marca casa es lluvia; su cero solo cuenta como hora seca
  si las estaciones de Meteocat de Sabadell (XF) y Sant Cugat (XV) tampoco
  recogieron nada en esa hora (con una que tenga dato basta). Si alguna
  recogió lluvia y casa marcó cero, no se sabe qué pasó en casa y la hora no
  se usa. Para eso el registro guarda la lluvia por horas de las dos
  (`meteocat-XF.csv` y `meteocat-XV.csv`, `registre.apunta_meteocat`), de la
  misma tabla de meteo.cat que ya se leía para el viento y la riera. Con solo
  horas de lluvia, o solo secas, no se ajusta nada.
- **Final de la lluvia** (ADR 0049): la verdad pasa a ser la lluvia de casa
  cada 5 minutos (`estacio-casa-5min.csv`, `registre.cincs_casa`, de las
  mismas lecturas de Ecowitt que ya se piden en cada pasada). Un final que el
  pluviómetro vea antes de tiempo por no marcar la llovizna cuenta como error
  de la regla; se acepta como ruido de la medida.
- **Comparación de radares** (ADR 0026): la observación es solo casa; sin
  estación en la pasada, la pasada no cuenta.
- **Vigilancia del pluviómetro** (ADR 0017): la referencia es la menor de
  las lluvias de Sabadell y Sant Cugat en cada hora, para contar solo la
  lluvia que cae en toda la zona; el mecanismo no cambia.
- **«Los modelos no ven esta lluvia»**: se compara con las tres últimas
  horas de casa, solo si las lecturas de la pasada las cubren.
- **Los datos ya guardados se borraron del NAS** el mismo 09-10-2026, a
  petición de Juanjo («borra los datos guardados de montflorit del nas»):
  `montflorit.csv` y `montflorit-5min.csv`; el campo `ara` de cada línea de
  `casa-2026-10.jsonl` (a `null`); las lecturas de la estación dentro del
  registro de la página del trayecto retirada (`2026-10.jsonl`,
  `dades.json` y `resultats.csv`: observaciones, estaciones y las frases que
  citaban su medida; la lluvia de ida y vuelta de `resultats.csv` se recalculó
  con las estaciones que quedan); la columna `montflorit_3h_max` de `riera.csv`; y `moto.csv`, cuya
  lluvia observada salía de esa estación (se regenera solo con la verdad
  nueva). Lo mismo en la copia de trabajo del repositorio privado
  `meteo-local-registre` que hay en el NAS, que la copia diaria sube. En el
  historial de ese repositorio privado quedan las versiones anteriores; no
  se ha reescrito. Ningún modelo aprendido salía de esos datos: el
  aprendizaje seguía con el archivo.

## Alternativas descartadas

- **Fiarse del cero de casa sin más**: el pluviómetro a veces no marca la
  lluvia débil (ADR 0017). Como verdad para aprender daría horas secas que
  no lo fueron; con Meteocat de confirmación, las horas dudosas se descartan.
- **Usar Sant Cugat o Sabadell como verdad de la lluvia**: están a 2,5 y
  4,6 km, por medias horas y con retraso; la lluvia convectiva no coincide.
  Sirven para confirmar que no llovió en la zona, no para decir que llovió
  en casa.
- **La estación del Consorci del Parc de Collserola** (Davis, en el Centre
  d'Informació, en Vallvidrera): publica solo las condiciones actuales en
  una página sin hora de actualización ni historial, y está más lejos que
  Sant Cugat.
- **La misma estación por Meteoclimatic** («Cerdanyola - Montflorit»,
  ESCAT0800000008290D, del mismo observador): son los mismos datos por otra
  puerta, y el `robots.txt` de Meteoclimatic cierra sus canales a los
  programas (ya en el ADR 0004).
- **Las estaciones particulares de Weathercloud** (el 09-10-2026 había seis
  a menos de 1 km, además de la de Juanjo y la de meteocerdanyola.com, con
  datos cada pocos minutos): sus condiciones de servicio (13-09-2021)
  prohíben el scraping, los robots, «accessing Weathercloud's API with an
  unauthorized client» y las aplicaciones de terceros sin consentimiento
  escrito; no hay API pública de lectura. Solo valdría que el dueño de una
  estación cediera el acceso directo a sus datos (por ejemplo, las claves de
  la API de su fabricante), y eso lo decide Juanjo.
- **Dejar el aprendizaje en pausa** (lo que había empezado a hacer otro
  agente): Juanjo pidió el 05-10-2026 que el programa aprenda de sus
  aciertos y fallos («es imperativo»).
- **Mantener `ara` vacío por compatibilidad**: el bot y la web se publican
  a la vez que los datos y ya leen solo `ara_casa`; los datos antiguos con
  `ara` se ignoran.

## Consecuencias

- Una fuente menos y ninguna dependencia de una web particular. «¿Llueve
  ahora?» depende de un solo pluviómetro, que puede perder la llovizna.
- La riera pierde un dato de la parte baja de la cuenca que no decidía.
- Las horas con lluvia cerca y cero en casa no entran en el aprendizaje:
  tardará algo más en reunir las 30 horas de lluvia (`MIN_HORES_PLUJA`).

## Evidencia

- Consorci de Collserola: `parcnaturalcollserola.cat/meteo/Current_Vantage.htm`
  (09-10-2026): condiciones actuales sin hora ni historial.

## Riesgos y limitaciones

- Si el pluviómetro de casa falla del todo, no hay segunda estación del
  barrio: la web diría «no plou» mientras llueve, salvo por el radar.
- La confirmación con Meteocat llega con la media hora de retraso de sus
  tablas: el registro de una hora se completa en la pasada siguiente.

## Validación

Pruebas automáticas de la verdad de la lluvia (`tests/test_aprenentatge.py`),
del registro de Meteocat y de los 5 minutos de casa
(`tests/test_registre_casa.py`), del pluviómetro con dos referencias
(`tests/test_pluviometre.py`), del bot, los riesgos, los radares y la riera
sin `ara`, y de la web pública sin la palabra meteocerdanyola
(`tests/test_montflorit.py`).

## Actualización del 22-11-2026: un enlace en la portada (3.233.0)

Juanjo pidió enlazar la web desde la portada: «una cosa es que su dueño no me
deje usar sus datos y otra que yo haga como si no existiese, creo que esta web
puede ser útil para otros». Al final de la portada, debajo de «D'on surt», una
línea dice «Per conèixer el temps a la resta de Cerdanyola, consulta
MeteoCerdanyola.com» (en castellano, «Para conocer el tiempo en el resto de
Cerdanyola…»), con el enlace a su portada. Lo demás de esta decisión no
cambia: no se lee nada de esa web, no es fuente de ningún dato y no se compara
con ella.

