# 42. Lluvia de Sant Cugat como señal del modelo propio

Fecha: 2026-10-08 · Estado: aceptado


**09-10-2026 (ADR 0058).** Las estaciones del barrio son ahora solo la de casa. La lluvia por horas de Sant Cugat y Sabadell se registra además para confirmar las horas secas del aprendizaje.

## Contexto

Juanjo preguntó si la estación del aeropuerto de Sabadell (AEMET, a 5 km al
norte) serviría para mejorar la previsión de Montflorit y el aprendizaje.
Pedirla exige una clave de OpenData, llega con cadencia horaria y retraso, y
no hay evidencia de que lo que llueve a 5 km mejore una previsión que ya
lleva el radar llevado hacia delante y las estaciones de Montflorit y de
casa. Antes de montar una dependencia nueva, conviene medir si una estación
cercana ayuda, y hay una a mano: la de Meteocat de Sant Cugat (XV, a 4,6 km
al oeste, en la cuenca de la riera), que la app ya descarga cada pasada para
el aviso de la riera (ADR 0027).

## Decisión

- **Se registra** en cada línea de `casa-*.jsonl` la lluvia de la última
  hora en Sant Cugat (`sant_cugat.pluja_1h`, de `riera.mm_1h`), desde el
  08-10-2026 (`registre.apunta_casa`).
- **Es un rasgo más del modelo propio**, `sant_cugat`, como la persistencia:
  $\ln(1 + \text{mm})$ si la antelación es de 4 horas o menos; si no, 0. Va en
  una lista aparte, `RASGOS_PROPIS_XV`, para no perder las muestras
  anteriores al 08-10-2026, que no lo tienen.
- **Dos variantes, y gana la que acierta más**: `candidat` valida el modelo
  propio sin y con Sant Cugat (cada una con sus muestras) y adopta la de
  menor error entre las que cumplen las 30 horas de lluvia y la mejora del
  5 % (apartado 4 de `docs/estadistica.md`). El historial diario apunta las
  dos.
- **Quién se acuerda**: el programa. El día en que la variante con Sant
  Cugat llegue a las 30 horas de lluvia, `aprenentatge.py diari` manda a
  Juanjo un solo Telegram con el error de las dos variantes y la del
  archivo, y dice si ayuda («demana la clau d'OpenData de l'AEMET i afegim
  l'aeroport de Sabadell») o no; deja `/estat/aprenentatge/avis-sant-cugat`
  para no repetirlo (Juanjo, 08-10-2026: «¿quién se acordará de mirarlo
  pasado un tiempo?»).
- **El aeropuerto de Sabadell no se añade todavía**: solo si Sant Cugat
  demuestra que una estación cercana aporta algo.

## Alternativas descartadas

- **Añadir el aeropuerto directamente**: clave, otra fuente que puede fallar
  y ninguna medida de que sirva; con Sant Cugat se obtiene la respuesta sin
  coste.
- **Meter el rasgo en `RASGOS_PROPIS`**: habría descartado las muestras de
  antes del 08-10-2026 (sin el dato) y retrasado las 30 horas.
- **Rellenar con 0 el dato que falta**: un cero que no es una medida
  sesgaría el ajuste.

## Validación

- `tests/test_aprenentatge.py`: el rasgo (valor, antelación larga, sin
  dato), las muestras con y sin el dato, la validación con la lista aparte y
  el aviso de una vez (umbral, huella, «Ajuda» / «No ajuda»);
  `tests/test_riera.py`: `mm_1h`. 218 pruebas el 08-10-2026.
- Qué se gana solo lo dirá el registro: la hipótesis queda abierta hasta el
  aviso.

## Cambio del 09-10-2026: la señal llega a la previsión y se compara bien

La auditoría del 09-10-2026 (ADR 0057) encontró dos fallos: `pluja_1h_xv`
se guardaba en el registro y entrenaba la variante, pero `al_prever` no lo
pasaba al prever, y en las cuatro primeras horas la variante caía al
archivo sin decirlo; y la variante se comparaba con el base medido en
todas las horas, cuando ella solo tenía las que llevan el dato. Ahora
`al_prever` recibe `riera["mm_1h"]`, y `valida_variant` ajusta y valida el
base con las mismas muestras (`error_base`): la variante solo se adopta si
lo mejora en un 5 % en esas horas, y el aviso de una vez compara con ese
error.

## Resultado del 04-11-2026: no ayuda, el aeropuerto de Sabadell no se añade

El aviso de una vez llegó el 04-11-2026, con 31 horas de lluvia en el
registro: error (Brier) en días no vistos, a las mismas horas, 0,0601 con
la lluvia de Sant Cugat y 0,0601 sin ella; el archivo tal como lo publica
la web, 0,0337. Que las dos variantes empaten no es un fallo del rasgo:
de 15.178 muestras con su dato, solo 142 (un 1 %) tienen lluvia en Sant
Cugat al prever, y en 60 de ellas llovió en casa; con tan pocas, el rasgo
no mueve el error medio. Se cierra la hipótesis: **no se pide la clave de
OpenData de la AEMET ni se añade el aeropuerto de Sabadell**. El rasgo
sigue en la variante, que `candidat` solo adoptaría si mejorase con
seguridad.
