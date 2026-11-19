# 18. Situaciones de peligro y aviso por Telegram

Fecha: 2026-10-06 · Estado: aceptado; el envío a Juanjo, retirado el 08-10-2026

**08-10-2026:** el aviso ya no se manda aparte a Juanjo por Telegram (lo pidió
al ver que le llegaba repetido): lo reciben todos por las notificaciones, el
bot y el canal (`avisos_bot.py`, ADR 0034 y 0048), con la misma detección.
Este programa sigue llevando el estado y el registro. Desde entonces el aviso
público dice también cuándo ya no queda ningún peligro, como hacía el privado.


**09-10-2026 (ADR 0058).** Sin Montflorit, lo medido de ahora es solo casa: la lluvia de la última hora cuando marca y la temperatura. La lluvia de 12 horas medida ya no se evalúa; queda la prevista.


**16-10-2026 (3.100.0): umbrales de Meteocat.** Juanjo: «el tiempo extremo se
usan los límites de aemet, deberían usarse los de meteocat?». Por fenómeno
manda Meteocat (ADR 0092), y sus umbrales son locales: los de temperatura,
del municipio (Cerdanyola: calor intensa a más de 36,8 °C y muy intensa a
38,8; frío intenso a menos de −1,6 y muy intenso a −3,6), y los de viento,
de la comarca (más de 72 y de 108 km/h). La lluvia pasa a 30 minutos (medida,
más de 20 y de 40 mm), 3 horas (más de 60 y de 90) y 24 horas (más de 100 y
de 200); la nieve, a cualquier espesor por debajo de 300 m (y más de 5 cm).
Dos niveles, amarillo y naranja: el rojo de Meteocat combina el umbral alto
con la probabilidad. El frío se mide junto a la riera, la zona más fría,
aunque avise más que el centro de Cerdanyola (Juanjo: «el frío con la
riera»). El tiempo violento (granizo, tornados, reventones) no se puede medir
aquí y llega por los avisos oficiales. Fuentes: «Situació Meteorològica de
Perill» y «Llindars_municipi_2026.pdf» de meteo.cat. «Si surts» sigue usando
para el coche los umbrales de lluvia en una hora de AEMET (20 y 40 mm), que
son otra cosa: si conviene conducir.
## Contexto

Juanjo pidió que la página de casa indique las situaciones de riesgo («viento
muy fuerte, lluvia, etc.») y que, cuando las haya, le llegue un mensaje por
Telegram. Al verlo en marcha concretó: con aviso amarillo de AEMET pero sin
ninguna previsión de lluvia torrencial, no quiere el mensaje; «solo lo quiero
si predices una situación meteorológica peligrosa, no avisos de otros».

En la misma petición quiso iconos en el bloque «Ara a casa», para leerlo más
deprisa.

## Decisión

- **Qué es peligro**: los umbrales de aviso de AEMET para el Prelitoral de
  Barcelona, la zona del Vallès (`RISC_LLINDARS` en `config.py`), aplicados a
  lo que mide y prevé la propia página, no a los avisos que emite AEMET:

  | | Amarillo | Naranja | Rojo |
  |---|---|---|---|
  | Lluvia en 1 h | 20 mm | 40 mm | 90 mm |
  | Lluvia en 12 h | 60 mm | 100 mm | 180 mm |
  | Racha máxima | 70 km/h | 90 km/h | 130 km/h |
  | Temperatura máxima | 36 °C | 39 °C | 42 °C |
  | Temperatura mínima | −4 °C | −8 °C | −12 °C |
  | Nieve en 24 h | 2 cm | 5 cm | 20 cm |

- **De dónde salen los valores** (`riscos.py`, que llama `casa.py` y guarda en
  `casa.json` como `riscos`):
  - Previsión, las 24 horas de la tabla: la lluvia de cada hora (la mayor de
    los tres modelos finos, la misma de la tabla), la ventana de 12 horas que
    más acumula, las rachas, la temperatura corregida y la nieve de AROME.
  - Ahora: la lluvia de la última hora y de las últimas 12 en Montflorit (y la
    de casa solo cuando marca lluvia, ADR 0017) y la temperatura de casa. El
    viento medido no cuenta: Montflorit da la media y el anemómetro de casa no
    va bien.
  - Lo medido y lo previsto son riesgos distintos: «ara plou molt fort» no es
    lo mismo que «es preveu».
- **En la página**: un recuadro «Risc» con el color del peor nivel, debajo de
  los planes de Protección Civil y encima de los avisos de AEMET, con cada
  situación, cuándo y el umbral que supera. «D'on surt» lo explica.
- **Por Telegram** (el reloj del NAS, tras cada publicación de la página de
  casa): un mensaje en catalán cuando aparece un riesgo o sube de nivel, con el
  enlace a la página, y otro cuando ya no queda ninguno. Un riesgo se da por
  acabado tras 3 horas sin verlo (`RISC_FI_H`), para que el vaivén de los
  modelos no repita el mensaje. Si falta la previsión o las estaciones, lo que
  dependía de ellas no se da por acabado. Estado en `/estat/riscos.json`.
- **Iconos de Lucide** en «Ara a casa»: termómetro, paraguas (o paraguas
  tachado si no llueve), nube con lluvia para la lluvia del día, gotas para la
  humedad, manómetro para la presión y viento.

## Alternativas descartadas

- **Avisar también de los avisos de AEMET y de los planes de Protección
  Civil**: era la primera idea. Juanjo la descartó: ya salen en la página y
  muchos avisos amarillos no llegan a nada en casa.
- **La tormenta prevista por el modelo (código 95-99) como riesgo**: el código
  solo dice que hay tormenta, no que sea fuerte, y en otoño sale a menudo. La
  tormenta fuerte la avisa AEMET y la tabla ya la muestra.
- **Umbrales propios**: los de AEMET son oficiales, están pensados para el
  Vallès y se pueden citar.

## Consecuencias

- Pocos mensajes, en días que lo merecen (Evidencia). Puede callar en un
  episodio que los modelos no ven; si la lluvia llega a los umbrales en
  Montflorit, lo medido sí avisa.
- `nas/reloj.sh` cambia: hay que reconstruir el contenedor.

## Evidencia

- Umbrales: AEMET, Plan Meteoalerta, anexo 1, «Umbrales y niveles de aviso»,
  versión del 31-05-2022, tabla de Cataluña, zona 690803
  (<https://www.aemet.es/documentos/es/eltiempo/prediccion/avisos/plan_meteoalerta/METEOALERTA_ANX1_Umbrales_y_niveles_de_aviso.pdf>).
- Frecuencia, con el archivo de `calibracio/` (enero de 2024 a 4 de octubre de
  2026): la previsión (la mayor de los tres modelos finos) llega a 20 mm en una
  hora en 5 días (12-07-2025, 20-08-2025, 13-09-2025, 3 y 4 de octubre de
  2026) y a 60 mm en 12 horas en 3 (13-09-2025, 3 y 4 de octubre de 2026). Las
  estaciones de Meteocat midieron 20 mm en una hora en 7 días en Sabadell y 9
  en Sant Cugat.
- El 05-10-2026, con el INUNCAT en emergencia, Montflorit midió como mucho
  16,4 mm en una hora y 52 mm en el día: no habría avisado por lo medido.
- El 06-10-2026, con aviso amarillo de AEMET por lluvia y tormentas, la
  previsión daba como mucho 3,2 mm en una hora y rachas de 19 km/h: sin
  riesgo, sin mensaje, como pidió Juanjo.
- Hipótesis sin comprobar: la frecuencia de las rachas de 70 km/h previstas
  por AROME (el archivo no guarda el viento).

## Riesgos y limitaciones

- Los umbrales de AEMET son para la zona entera; en un punto se superan menos.
- La lluvia prevista es la mayor de tres modelos: algún aviso de más es
  posible (2 de los 5 días del archivo no tuvieron esa lluvia en Sabadell ni
  en Sant Cugat).

## Validación

`tests/test_riscos.py` (detección, niveles, tramos, aviso una vez, subida de
nivel, final tras 3 horas y fuente caída), `probar-web` en Chromium, Firefox y
WebKit, escritorio, móvil y tableta, claro y oscuro, con un riesgo simulado, y
axe-core sin fallos en las dos páginas.

## Cambio del 19-10-2026 (3.156.0): cada aviso dice de dónde sale y cuánto fiarse; la racha, resaltada en la tabla

Juanjo, ante «Vent fort previst: ratxes de fins a 77 km/h» con la tabla en
«13 (77)» como cualquier otra cifra: «en la tabla sin embargo no sale nada»;
y luego: «hay que indicar el origen de la alerta y a ser posible la validez
que tiene… dado que viene de un modelo no debe decir que la ha calculado
nuestra web», y «para este tipo de alertas puntuales en la tabla se puede
añadir una i de info que lleve a la explicación de la alerta».

- **Origen y fiabilidad** (`riscos.font`, en catalán y castellano): cada
  riesgo lleva una línea con su fuente. Las rachas: la previsión de
  Météo-France para Montflorit y cuántos de los tres modelos finos (AROME HD,
  AROME, ICON-EU) pasan el umbral en el mismo tramo, con la racha de cada
  uno (`casa.py` guarda `ratxes_models` en cada hora); si llega menos de la
  mitad, «previsió poc segura». La lluvia prevista: la del modelo que da más
  y, las primeras horas, el radar y las estaciones. La temperatura prevista:
  Météo-France corregida con una estación del barrio (error medio de un
  grado, «Com funciona»). Lo medido: las estaciones del barrio. El mensaje
  del aviso (Telegram, notificaciones y ficha de «Perill») pone esa línea
  bajo cada riesgo y acaba en «Avís no oficial.», en lugar de «Calculat per
  aquesta aplicació, no oficial.». «Com funciona» lo explica; el enlace
  «Què vol dir aquest avís» sigue llevando allí.
- **La tabla**: la racha que pasa el umbral amarillo (72 km/h) o naranja
  (108 km/h) va en el color del nivel, con una «i» (icono `info` de Lucide)
  que lleva a la ficha del aviso en «Perill» o, sin aviso activo (más allá
  de las 24 horas), a «Com funciona». La leyenda lo explica. En móvil, la
  columna de viento se ensancha solo en los tramos que lo llevan.

- **La ficha abierta, al día** (3.156.1): como la de Meteocat, la ficha
  abierta del temps extrem en «Perill» toma en cada pasada los riesgos de
  ahora con su origen (`estat["perill_text"]`), sin `darrer`, de modo que no
  se marca «Nou». Así la del 19-10-2026 a las 13:09, publicada con «Calculat
  per aquesta aplicació», se corrige sola, y la fiabilidad que cambia de una
  pasada a otra (cuántos modelos llegan) está siempre al día. Prueba:
  `tests/test_historial.py`.

- **La frase de los modelos, clara** (3.156.2). Juanjo, ante «Dels 3 models
  consultats, 2 hi arriben (AROME HD, 92; AROME, 89; ICON-EU, 12 km/h)»:
  «que significa esta frase…?». No decía a qué llegaban, faltaban unidades y
  los 77 km/h del aviso no cuadraban con los 92 y 89 de los modelos. Ahora:
  «Origen: la previsió combinada de Météo-France per a Montflorit. Dels 3
  models que es consulten, 2 també preveuen ratxes de més de 72 km/h: AROME
  HD, fins a 92 km/h, i AROME, fins a 89 km/h; ICON-EU, només 12 km/h.» La
  cifra del aviso es la combinada (mezcla los modelos y suaviza los picos);
  la de cada modelo va detrás. Aprobado por Juanjo («sí, aplícalo y
  publícalo»).

- **La racha, la del modelo que da más** (3.157.0). En la pasada de las
  13:43 del 19-10-2026, la previsión combinada de Météo-France daba 66 km/h
  de 17 a 18 h, con AROME HD a 92 y AROME a 89: el aviso desapareció aunque
  dos de tres modelos pasaban el umbral, porque la combinada mezcla modelos
  y rebaja los picos. Ahora la racha de cada hora es la más fuerte de los
  modelos finos (`casa.ratxa_modelos`), como los mm de lluvia
  (`lluvia_modelos`); sin ninguno, la combinada. Vale para todo lo que la
  usa: el aviso, la tabla, la gráfica, las etiquetas de los tramos y «Si
  surts» (bici, moto y a pie, que así es más prudente). El aviso dice
  «Origen: el model que en preveu més, AROME HD.» y, detrás, cuántos la
  ven. Juanjo: «hazlo». Prueba: `tests/test_casa_fonts.py` (`RatxaHora`).

Validación: `tests/test_riscos.py` (`FontTest`), `tests/test_web.py`
(`test_ratxa_de_l_avis_a_la_taula` y el umbral naranja igual al de
`config`); la web generada con los datos del 19-10-2026 en Chromium y
Firefox, móvil (412 y 320 px) y escritorio, claro y oscuro; axe-core sin
fallos con la tabla desplegada. A 320 px la tabla ya se desplazaba de lado
antes del cambio (ancho mínimo de 19rem).

## Cambio del 19-11-2026 (3.226.0): el umbral, con la cifra que se muestra

Una racha de 72,4 km/h pasaba el umbral de 72 y la ficha decía «ratxes de
fins a 72 km/h» y «només 1 també preveu ratxes de més de 72 km/h: AROME HD,
fins a 72» (revisor, 18-11-2026). Los modelos no dan décimas de verdad: el
umbral se compara ahora con la cifra tal como se escribe (`riscos.nivell`,
con `num`: sin decimales; la temperatura, con uno). En la tabla de la web,
igual (`casa.js`: la racha redondeada y la calor con un decimal). Un valor
justo en el borde (72,4 km/h, 36,84 °C) ya no avisa; desde 72,5 y 36,85, sí.
Prueba: `tests/test_riscos.py` (`test_el_llindar_amb_la_xifra_que_es_mostra`).
