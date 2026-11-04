# 43. Terminología del manual de estilo de Meteocat

Fecha: 2026-10-08 · Estado: aceptado

**13-10-2026 (ADR 0088).** La nubosidad en % ya no es la de un solo modelo, sino la mezcla de cuatro y, en la hora en curso, la observada en el aeropuerto de Sabadell. Los umbrales y los nombres no cambian.

## Contexto

«Poc núvol» le sonó raro a Juanjo y preguntó si era la forma estándar. No lo
era, y al repasar el resto de estados del tiempo que escribe la página
(lluvia, nieve, granizo…) pidió que fueran normativos. La fuente es el
*Manual d'estil* del Servei Meteorològic de Catalunya (meteo.cat, PDF de
2014), apartados «Estat del cel», «Precipitació» y «Visibilitat».

## Decisión

- **Cielo**, por octavos de cielo tapado según el manual (serè 0, poc
  ennuvolat 1–2, mig ennuvolat 3–5, molt ennuvolat 6–7, cobert 8), con la
  nubosidad del modelo en %: serè < 20, poc ennuvolat 20–44, mig ennuvolat
  45–69, molt ennuvolat 70–84, cobert ≥ 85. En castellano, los términos de
  AEMET: despejado, poco nuboso, nuboso, muy nuboso, cubierto.
- **Lluvia por intensidad**: el manual la define por 30 minutos (feble < 3
  mm, moderada 3–20, forta 20–40, torrencial > 40); la tabla es horaria, así
  que el doble: feble < 6 mm, moderada 6–40, forta 40–80, torrencial > 80
  (`INTENSITAT_PLUJA` en `web/casa.js`). Antes «Pluja forta» empezaba en
  4 mm, que para Meteocat es lluvia débil.
- **Tipos que antes no se nombraban**, por el código de tiempo de
  Open-Meteo: neu (71–77, 85–86; feble < 2 cm en una hora, moderada 2–10,
  forta > 10, el doble del manual por 30 minutos), pluja gelant (56–57,
  66–67) y tempesta amb calamarsa (96, 99; el modelo no da el tamaño, así
  que no se distingue de «pedra», ≥ 10 mm). «Possible neu» cuando la
  probabilidad es media. Boira (45, 48) ya estaba.
- **Fichas de matí/tarda/nit** (ADR 0041): «pluja forta» desde 40 mm en una
  hora y «pluja torrencial» desde 80; «gel» pasa a «glaçada» / «helada».
- **Coche** (ADR 0039): los umbrales siguen siendo los de AEMET (20 y 40 mm
  en una hora), pero el texto da la cifra («Fins a 25 mm de pluja en una
  hora…») en vez de «forta» / «molt forta», que para Meteocat significan
  otra cosa.
- «Possible pluja» y «Possible tempesta» no están en el manual porque son
  probabilidad, no observación: se mantienen.

## Validación

- `tests/test_web.py` (`test_el_cel_surt_de_la_probabilitat`, el coche y los
  tramos) y `tests/test_montflorit.py` (traducciones): 218 pruebas el
  08-10-2026. Juanjo dio por bueno publicar sin servidor local: «es cambio
  de nomenclatura».

## Cambio del 25-10-2026 (3.203.0): «cobert» con su propio icono

«Molt ennuvolat» y «cobert» tenían el mismo dibujo, las dos nubes de Lucide
(`i-cloudy`). Lucide no tiene uno de cielo cubierto: «cobert» lleva las mismas
dos nubes rellenas de un gris más denso (`i-cloudy-cobert`, `--c-cobert-fons`),
el cielo cerrado, en la tabla y la gráfica por horas, la semana, «Fiabilitat»
y la imagen de la gráfica del bot (`grafica.js` `celNuvols`, `bot.icona_cel`,
que en los mensajes de texto sigue siendo ☁️, porque no hay emoji de cielo
cubierto). Juanjo, 25-10-2026: «cobert y molt ennuvolat tienen el mismo
icono, no convendría diferenciarlos?».

## Cambio del 04-11-2026 (3.211.0): el radar, también con la escala de Meteocat

El radar (el cuadro, el mapa y su leyenda), la «pluja … a X km» del titular,
el aviso de lluvia que llega («Serà moderada») y el bot usaban las franjas de
AEMET por hora (`nowcast.FRANGES_MMH` = 2, 15, 30 y 60 mm/h, con «molt
forta»), mientras la tabla por horas usaba las de este manual. El revisor
(03-11-2026) vio 3,9 y 4,2 mm/h como «Pluja feble» en la tabla, lo que el
radar llamaba «moderada». Recomendé AEMET por ser la escala oficial por
hora; Juanjo: «y no es mejor la del meteocat que es la de aqui?». Ahora todo
usa las del manual, en mm/h: feble < 6, moderada 6–40, forta 40–80,
torrencial ≥ 80; «molt forta» desaparece y el mapa pasa de cinco colores a
cuatro (azul claro, azul, naranja y rojo).

- **Lo que no cambia de comportamiento.** La lluvia intensa que el titular
  dice aunque no venga hacia aquí (`nowcast.forta`, ADR del 17-10-2026, con
  truenos) sigue saliendo desde 15 mm/h (`INTENSA_MMH`), con la palabra de
  Meteocat: una tormenta de 20 mm/h a 10 km es «Pluja moderada a 10 km».
  Con el umbral de «forta» de Meteocat (40) no se habría dicho. La distancia
  de la lluvia de 2 mm/h del registro del crecimiento (`km_moderada`,
  `MODERADA_REGISTRE_MMH`) se mantiene, porque la medida está en curso.
- **El aviso de lluvia** dice «Serà …» hasta moderada y «Pot ser …» desde
  forta (antes, desde 15 mm/h).
- **Validación**: `tests/test_nowcast.py` (las franjas, en los límites:
  5,9 feble, 6 moderada, 40 forta, 80 torrencial; la lluvia intensa de
  20 mm/h, que se dice como moderada), `test_bot.py`, `test_pluja_arriba.py`
  y `test_web.py`; 761 pruebas.
