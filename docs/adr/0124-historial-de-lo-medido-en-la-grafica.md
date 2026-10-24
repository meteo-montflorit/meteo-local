# 124. Historial de lo medido en la gráfica

Fecha: 2026-10-24 · Estado: aceptado

## Contexto

Juanjo (24-10-2026): «me gustaría que fuese posible consultar un historial,
por ejemplo si llovió las horas pasadas o ver la temperatura hace una semana.
pero no sé cómo mostrarlo, consultarlo ni dónde ponerlo en la app».

Los datos ya existían: `historial.py` prepara para cada día desde el 4 de
octubre, hora a hora, la temperatura medida por la estación y la lluvia del
barrio (como la cuenta el aprendizaje), y `publica.sh` los sube a IONOS
(`historial-AAAA-MM-DD.json`, unos 14 KB por día; ADR 0099). Hasta la 3.164.0
la gráfica en grande tenía ‹ › para ir a días pasados, pero solo con «Com
encerta», que mezclaba lo medido con lo previsto; con el ADR 0110 todo pasó a
«Fiabilitat», que habla de cuánto acierta la previsión, no de qué tiempo hizo.
Faltaba la parte que ve la gente.

El agente propuso ponerlo en la gráfica en grande, detrás de un botón, con
las últimas 24 horas al abrir, y Juanjo lo aprobó («sí, hazlo en una rama y
enséñamelo»). El botón también en la portada, junto a «Opcions», lo añadió
el agente al construirlo: la gráfica en grande solo se abre con «Opcions», y
ahí el historial quedaba escondido.

## Decisión

- **Botón «Historial»** (icono `history` de Lucide) en dos sitios: en la
  leyenda de la gráfica de la portada, delante de «Opcions» y igual que él
  (en el móvil, solo el icono), que abre la gráfica en grande ya en el
  historial; y dentro de la gráfica en grande, como interruptor
  (`aria-pressed`): pulsado, la gráfica enseña lo medido; otra vez, vuelve
  a la previsión desde el principio.
- **Al abrir, las últimas 24 horas** con medida (`darreres24`): las de ayer
  y las de hoy ya acabadas, sin las últimas que aún no tienen medida porque
  la publicación va por detrás. Es lo que se busca para saber si ha llovido.
  La gráfica se desplaza al final, a las horas más recientes.
- **‹ y ›** pasan de día en día hasta el 4 de octubre; el orden es cada día
  y, al final, las 24 horas. **El nombre del día** («Darreres 24 h», «Avui»,
  «Ahir» o la fecha) es un botón que abre el calendario del navegador (un
  campo de fecha oculto, `showPicker`, con el primer día y hoy como límites)
  para saltar a cualquier día.
- **Solo lo medido**: temperatura en línea, lluvia en barras («Pluja
  mesurada» en la leyenda, sin probabilidad) y el cielo de lluvia donde
  llovió. La previsión y el acierto siguen en «Fiabilitat».
- **Lo demás que se mide, con los mismos interruptores que la previsión**
  (Juanjo, 24-10-2026, al ver la primera versión: «Yo te preguntaba de otro
  tipo de datos como la presion, nubosidad, etc»; el agente propuso cuáles y
  cómo, y Juanjo lo aprobó): humedad y presión de la estación de casa; viento
  y rachas de Sant Cugat, el mismo que enseña «Ara» (`C.VENT_ESTACIO`), y el
  cielo tapado observado en el aeropuerto de Sabadell (desde el 13-10-2026),
  que da también el icono del cielo de cada hora. Quien tenga encendida la
  presión la ve igual en la previsión y en lo medido. Cada interruptor sale
  solo si el día que se ve trae ese dato; el UV no se mide y no sale. La ficha
  de cada hora dice dónde se mide lo que no es del barrio («Vent a Sant
  Cugat», «Cel tapat a Sabadell»), y el cielo tapado va tal cual se observó,
  sin el mínimo del 50 % que la previsión pone a las horas con lluvia.
  `historial.py` (formato 6) lo añade a cada hora solo cuando se sabe; al
  cambiar el formato, los días ya publicados se rehacen solos, tres por
  pasada. Cada día pasa de unos 14 a unos 21 KB.
- **Las alertas de cada hora, con la misma franja que la previsión**
  (Juanjo, 24-10-2026: «en el historial deberían aparecer las alertas que
  afectan a cada uno, es posible?»; el agente lo entendió como cada día y
  propuso cómo, y Juanjo lo aprobó): una fila por organismo, del color del
  nivel y solo en las horas en que estuvo en vigor; tocar un tramo dice qué
  era, y la ficha de cada hora lo añade. `historial.py` (formato 7) pone en
  cada hora `avisos` y `riscos_hora`, el formato de la gráfica de la
  previsión:
  - AEMET, Meteocat y los riesgos de la propia web: lo que pintaba la gráfica
    en la publicación más cercana antes de la hora, que el registro guarda
    desde la 3.194.0 (`mostrat.avisos` y `mostrat.riscos`; `casa.riscos_hora`
    hace lo mismo que `riscosHora` de la web).
  - En los días de antes (4-24 de octubre): AEMET, del historial de «Perill»
    (desde que valía hasta que acabó o lo sustituyó Meteocat); Meteocat, de
    la marca que el registro guardaba cada hora para el aprendizaje (lluvia o
    tiempo violento, moderado o alto: `avis_meteocat`, `avis_meteocat_alt`),
    sin el fenómeno exacto, y dicho «pluja». Los riesgos propios de esos días
    no se guardaron y no salen (el viento fuerte previsto del 19-10).
  - Siempre, del historial de «Perill» (`avisos.json` del estado,
    `historial.ruta_avisos`): los planes de Protección Civil, en su fase
    («Protecció Civil · INUNCAT en alerta», también la prealerta), los
    incendios («Bombers») y la riera, mientras estuvieron en curso.
  En el móvil, como la gráfica del historial se desplaza, los nombres de las
  filas van siempre arriba y fijos a la izquierda, con las cifras de la
  escala; un día pasado se abre en las 0 h y las 24 horas, en la última.
- La escala de grados a la izquierda, como en «Fiabilitat», y fija al
  desplazar la gráfica (antes se perdía; vale también para «Fiabilitat»).
- **El resumen debajo**, como conclusión (`resumMesurat`): «No ha plogut» o
  «Han caigut 3,2 mm» (en un día acabado, «No va ploure» / «Van caure»),
  cuántas horas no tienen dato de lluvia, y «Mínima: 10 °C, avui a les 2 h.
  Màxima: 21 °C, ahir a les 14 h.». Las temperaturas son la media de cada
  hora; las horas con sol sobre el termómetro no cuentan.
- **Enlace directo**: `#historial` (las 24 horas) y `#historial-AAAA-MM-DD`;
  la dirección cambia al moverse, así que compartir da lo que se ve. Un
  enlace con la ventana ya abierta va a ese día.
- `llegeixHistorial`, `llegeixDiaHistorial` y `avuiIso` pasan de
  `fiabilitat.js` a `grafica.js`, que cargan las dos páginas.

## Alternativas descartadas

- **Una opción «Ahir» en «Consultes»**: ahí van los textos del bot, y para
  ver cómo evolucionó el tiempo sirve más una gráfica.
- **Una pestaña propia**: otra pestaña para algo que cabe en la gráfica que
  ya se conoce.
- **Las horas pasadas delante de la previsión**, sin botón: mezcla lo que
  pasó con lo que vendrá (Juanjo, 17-10-2026, ADR 0099).
- **Rellenar el día de hoy hasta medianoche con horas vacías**: el resumen y
  las fichas de esas horas dirían «no se sabe» de lo que aún no ha pasado.

## Consecuencias y riesgos

- Las alertas de Meteocat de antes del 24 de octubre son aproximadas: la
  marca horaria no distingue la lluvia del tiempo violento.
- Solo hay datos desde el 4 de octubre de 2026 (las nubes, desde el 13). El
  viento no es del barrio (el anemómetro de casa no se usa) ni las nubes
  tampoco (Sabadell, a unos 8 km). La parte alta, medida por las vecinas,
  solo desde el 9-10-2026 (ver el cambio de la 3.194.1).
- La lluvia medida por debajo de 0,2 mm en una hora no dibuja barra (el mismo
  umbral que la gráfica de la previsión), pero cuenta en el total.
- Un día con pocas horas (hoy de madrugada) ocupa todo el ancho: las horas
  salen anchas.
- La imagen de la gráfica (cámara) dice qué se midió y de cuándo («mesurat
  al barri: les 24 h fins a les 05:00»), no la hora de la previsión.
- Con todas las capas encendidas, en el móvil la ventana se desplaza hacia
  abajo, como en la previsión.

## Validación

- `tests/test_web.py`, `test_historial_mesurat`: las 24 horas con ayer y hoy,
  sin las horas sin medir ni la previsión; el resumen con lluvia, sin dato,
  con sol sobre el termómetro y sin medidas; el enlace y el nombre del día.
  `tests/test_historial_grafica.py`, `test_humitat_pressio_vent_i_nuvols`:
  las medias de la hora, la racha mayor y que lo que falta no va.
- Con una copia del registro del NAS: el historial en formato 6 de los 21
  días, y el 18 de octubre en la web con viento, humedad, presión y nubes, en
  móvil (WebKit y Chromium) y escritorio; axe-core sin infracciones con todas
  las capas, en Chromium y Firefox, claro y oscuro.
- Alertas: `test_les_alertes_de_cada_hora` (lo guardado, lo reconstruido, los
  planes y la prealerta superpuestos, sin «Perill»), `test_riscos_de_la_hora`
  (`casa.riscos_hora`). Con el registro y el historial de «Perill» reales, los
  incendios del 10 y el 16, el INUNCAT del 15 al 20, AEMET y Meteocat del 17
  al 20 y el aviso de AEMET de hoy; el 19 de octubre en el móvil (WebKit,
  Chromium y Firefox) con los nombres fijos; axe-core sin infracciones.
- En un servidor local con los datos reales de IONOS (24-10-2026): las 24
  horas, el 18 de octubre con 8,6 mm, las flechas, el enlace directo, volver
  a la previsión y «Fiabilitat» sin cambios. `probar-web` en Chromium,
  Firefox y WebKit, escritorio, móvil y tableta, tema claro y oscuro, sin más
  errores que la lectura de IONOS desde `localhost` (que cae en la copia
  local); axe-core sin infracciones en la portada y en la ventana.
- El calendario del navegador no sale en las capturas: queda por comprobar a
  mano en el móvil.

## Cambio del 24-10-2026: el historial de «Perill», sin borrar nada

Juanjo preguntó cuánto se guardaba y si era costoso ampliarlo a varios años,
y después: «pero podré consultar las condiciones de un día de hace 3 años?».
Lo medido ya se guardaba sin límite (el registro del NAS y un archivo por día
en IONOS), pero el historial de «Perill» se borraba al año
(`HISTORIAL_DIES = 366`). Además de perderse las fichas, al rehacer los días
del historial de la gráfica (un formato nuevo, o IONOS reconstruido desde el
NAS) los de hace más de un año perderían las alertas que salen de él. Ampliar
el plazo en el mismo archivo no convenía: cada página de la web descarga
`avisos.json` en cada visita (el punto de «Perill») y el receptor de IONOS
rechaza archivos de más de 2 MB. El agente propuso repartirlo por años y
Juanjo lo aprobó («sí, añádelo a la rama»).

- `avisos_bot.py` ya no borra nada. Lo que acabó hace más de `ARXIU_DIES`
  (35) días sale de `avisos.json` y pasa al archivo del año en que empezó,
  `avisos-AAAA.json` (`parteix`, `arxiva`): el propio, en la carpeta del estado
  (en el NAS, `/estat`; en la reserva, la suya), unido con el publicado (el
  NAS y la reserva llevan cada uno el suyo, como `fusiona`) y con los nuevos.
  Se escribe en la carpeta del estado y al lado del `avisos.json` que se
  publica. Lo que sigue en curso no se archiva nunca.
- `publica.sh` sube los archivos por año que se hayan escrito en la pasada,
  en un envío aparte: si IONOS los rechazara, los datos de siempre ya han
  entrado. `rep-dades.sh` acepta `avisos-20AA.json`, JSON como los demás.
- «Perill» los lee una vez por visita, de 2026 al año actual, y los une al
  historial (sin repetir episodios): las fichas viejas, sus meses plegados y
  sus enlaces directos siguen funcionando. Las demás páginas no los
  descargan.
- `historial.py` lee el historial de «Perill» entero (`historial_perill`:
  `avisos.json` y los archivos por año de su carpeta) para las alertas de cada
  hora.
- Si el NAS perdiera su copia, la recupera de la publicada en IONOS en la
  siguiente pasada que archive algo de ese año.

**Al publicar**: `reserva/instalar.sh` en IONOS, para que el receptor acepte
los archivos nuevos (si no, solo se rechaza el envío aparte). El primer
episodio que se archivará acabó el 10-10-2026: pasará hacia el 15-11-2026.

Validado: `tests/test_historial.py`,
`test_no_es_perd_res_i_el_vell_va_a_l_arxiu_del_seu_any`;
`tests/test_rep_dades.py`, `test_accepta_l_arxiu_de_perill`;
`tests/test_historial_grafica.py` (las alertas, también desde el archivo del
año); en local, «Perill» con los incendios de octubre pasados a un
`avisos-2026.json` simulado: salen en su sitio y el enlace directo lleva a la
ficha.

## Cambio del 24-10-2026 (3.194.1): la parte alta, también en el historial

Juanjo: «cuando tengo activado riera o parte alta, el historial lo tiene en
cuenta?». No: enseñaba siempre la temperatura de la estación de casa, la de
la riera, sin decirlo. Además, este ADR decía que la parte alta no se mide, y
no era cierto: las vecinas de arriba (ICERDA18, ICERDA28 e ICERDA48,
`part_alta.ALTES`) se registran hora a hora desde el 9-10-2026, y la web ya las
usa para el «ahora» de la parte alta (ADR 0087). El error fue del agente. Juanjo
aprobó la corrección («sí, hazlo y publícalo»).

- `historial.py` (formato 8) añade a cada hora `temperatura_alta`: en cada
  extremo de la hora, la mediana de las vecinas de arriba con al menos dos
  (`part_alta.mediana_alta`, la regla del «ahora»), y la media de los dos,
  como la de casa. Las vecinas dan grados enteros: el resultado va de medio en
  medio grado.
- Con el selector de zona en la parte alta (ADR 0123), el historial usa esa
  temperatura en la gráfica, la ficha de cada hora y la mínima y la máxima
  (`ambZonaHistorial`); el sol sobre el termómetro de casa no cuenta en ella.
  Un día sin datos de arriba (del 4 al 8 de octubre) enseña la riera y lo
  dice: «D'aquest dia només hi ha la temperatura de la riera».

Validado: `test_la_temperatura_de_la_part_alta` y, en `test_historial_mesurat`,
la zona; con el registro real, la parte alta de 1 a 2 °C por encima de la
riera a mediodía; en el móvil, el 17-10 con la parte alta (26 °C a las 14 h) y
el 6-10 con la nota de la riera.

