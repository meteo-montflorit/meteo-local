# 124. Historial de lo medido en la gráfica

Fecha: 2026-10-24 · Estado: propuesto (rama `historial-mesurat`)

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
  llovió. La previsión y el acierto siguen en «Fiabilitat». Las opciones de
  la previsión (viento, humedad…) se esconden: no hay datos medidos de eso.
  La escala de grados a la izquierda, como en «Fiabilitat», y fija al
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

- Solo hay datos desde el 4 de octubre de 2026, y solo temperatura y lluvia:
  el viento de la estación no se usa y la parte alta no se mide.
- La lluvia medida por debajo de 0,2 mm en una hora no dibuja barra (el mismo
  umbral que la gráfica de la previsión), pero cuenta en el total.
- Un día con pocas horas (hoy de madrugada) ocupa todo el ancho: las horas
  salen anchas.
- La imagen de la gráfica (cámara) dice qué se midió y de cuándo («mesurat al barri: les 24 h fins a les 05:00»), no la hora de la previsión.

## Validación

- `tests/test_web.py`, `test_historial_mesurat`: las 24 horas con ayer y hoy,
  sin las horas sin medir ni la previsión; el resumen con lluvia, sin dato,
  con sol sobre el termómetro y sin medidas; el enlace y el nombre del día.
- En un servidor local con los datos reales de IONOS (24-10-2026): las 24
  horas, el 18 de octubre con 8,6 mm, las flechas, el enlace directo, volver
  a la previsión y «Fiabilitat» sin cambios. `probar-web` en Chromium,
  Firefox y WebKit, escritorio, móvil y tableta, tema claro y oscuro, sin más
  errores que la lectura de IONOS desde `localhost` (que cae en la copia
  local); axe-core sin infracciones en la portada y en la ventana.
- El calendario del navegador no sale en las capturas: queda por comprobar a
  mano en el móvil.
