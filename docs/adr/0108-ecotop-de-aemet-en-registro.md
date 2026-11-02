# 108. El ecotop del radar de AEMET, en registro

Fecha: 2026-10-19 · Estado: retirado el 02-11-2026 (registro del 19-10 al 02-11-2026; nunca se mostró en la web)

## Contexto

Juanjo preguntó si merecía la pena incorporar el radar de AEMET a la web
(19-10-2026). Comprobado:

- La imagen ya llega. RainViewer, la imagen preferida desde la 3.129.0
  (ADR 0026), en España sale de AEMET OpenData y de Euskalmet, según [su
  página de fuentes](https://www.rainviewer.com/es/sources.html). La
  comparación diaria del NAS la daba como la que más acierta en casa (Brier
  0,029 frente a 0,037 de Meteocat, 408 casos con lluvia en 6 días).
- La imagen regional directa de AEMET (`/api/red/radar/regional/ba` de
  OpenData) es un GIF de 480 × 530 píxeles con las fronteras pintadas en el
  amarillo de los 48 dBZ, y la de las 16:30 se publicó a las 16:38; por
  RainViewer llega en 1 a 3 minutos. No aporta nada.
- Lo que no llega es el **ecotop**: la altura máxima de los ecos de 12 dBZ o
  más, en km. Separa una tormenta (8-10 km o más) de la lluvia de un frente
  (4-6 km), y la web no tiene ahora ninguna medida de eso. AEMET lo publica
  del radar de Gelida (código GLD, a unos 22 km de casa), cada 10 minutos, en
  la «Descarga de datos georreferenciados» de su visor
  (`https://www.aemet.es/es/api-eltiempo/radar/download/GLD`): un `.tar.gz`
  con los quince radares y las tres últimas imágenes de cada producto (37 MB),
  GeoTIFF RGBA en EPSG:4326 a 0,005° (unos 0,4 × 0,55 km), con compresión
  JPEG y la escala de colores por clases en los metadatos (`ESCALA`: de 1 a
  20 km o más). Licencia: CC BY 4.0, citando a AEMET
  ([ficha en datos.gob.es](https://datos.gob.es/es/catalogo/e05068001-datos-de-radares)).
  El 19-10-2026 la imagen de las 16:20 se publicó a las 16:30 (entre 10 y 16
  minutos de retraso), y desde el NAS el paquete baja en menos de un segundo.

## Decisión

Dos semanas de registro antes de decidir si se usa (Juanjo: «sí, localiza el
ecotop y regístralo un par de semanas»), sin mostrar nada en la web.
`ecotop.py apunta`, desde `publica.sh` en cada pasada del NAS, cada 25
minutos como mucho (el paquete guarda 30) y solo con lluvia a la vista (radar
a 60 km o menos, lluvia ahora, o un 20 % o más en las próximas 6 horas).
Por cada imagen nueva de Gelida, una fila en `registre/ecotop.csv`: la hora
de los datos, cuándo los publicó AEMET y cuándo se bajaron; el ecotop más
alto sobre casa y a 5, 15, 30 y 60 km; la superficie con 8 y 10 km o más a
30 km o menos, y la distancia y el rumbo de los más cercanos. También el trozo
de 60 km alrededor de casa, en clases, en `registre/ecotop/`, para medirlo de
otra manera después. Los colores se leen por el más cercano de la escala
(con la compresión JPEG no son exactos); los que no se parecen a ninguno se
cuentan aparte (unos 5 de 87.000 píxeles en las primeras imágenes).

## Cómo se decidirá

El 02-11-2026, con `ecotop.py estat` y el registro: para cada vez que el
ecotop pasa de 8 o 10 km a 15 km o menos de casa, si en la hora siguiente
llovió fuerte en el barrio (`veines-5min.csv`) o hubo aviso de Meteocat por
intensidad, y con cuánta antelación respecto a lo que ya dice la web (el
radar, ADR 0019; la lluvia que crece, ADR 0019). Aciertos, fallos y falsas
alarmas, con la regla de mejora del programa (ADR 0105) si se compara con lo
que hay.

## Resultado y retirada (02-11-2026, 3.208.2)

505 imágenes de Gelida, del 19-10 a las 14:00 al 02-11 a las 16:30 (hora
UTC), con un retraso de publicación de 11 minutos de mediana
(`ecotop.py estat`). El ecotop de 8 km o más llegó a 15 km o menos de casa
diez veces:

- **Seis el 19-10, todas con la lluvia ya en el barrio.** La red de
  estaciones (`veines-5min.csv`) medía lluvia desde las 12:00 UTC y el primer
  ecotop cercano se publicó a las 14:26; en el segundo chubasco, la lluvia
  empezó a las 17:10 y el ecotop se publicó a las 17:46. Ninguno se adelantó
  al radar ni a la lluvia que crece.
- **Cuatro el 27 y el 28-10 (de 20:10 a 00:30 UTC), sin una gota en el
  barrio**, con ecotops de 16 a 20 km en las imágenes de esa noche: falsas
  alarmas.

Juanjo, ante el resultado y la recomendación de retirarlo: «de acuerdo,
retiralo». Se quitan `ecotop.py`, `tests/test_ecotop.py` y el enganche de
`publica.sh`, y su entrada del inventario de automatismos del NAS. El
registro (`registre/ecotop.csv` y `registre/ecotop/`) se queda en el NAS; el
programa, en el historial de git (hasta la 3.208.1).

## Riesgos y lo no comprobado

- Cerca del radar el ecotop es poco fiable: en la imagen de las 16:00 del
  19-10 salió una mancha de 20 km o más a unos 7 km de Gelida, en una sola
  imagen. Casa está a 22 km del radar; en el análisis se mirarán aparte los
  píxeles a menos de 10 km de Gelida.
- La descarga no está documentada como servicio con dirección fija: es la del
  botón del visor. Si cambia o el radar se para, `ecotop.py` lo dice en el
  registro del NAS (ninguna imagen de Gelida de la última hora).
- Hipótesis, sin comprobar: que un ecotop alto cerca anuncie la lluvia fuerte
  antes que el radar y la lluvia que crece.

Validación: `tests/test_ecotop.py`; con el paquete real del 19-10-2026 a las
16:41, tres imágenes (16:00, 16:10 y 16:20) en 0,7 s, con la zona de 8-10 km
sobre el mar al este que coincidía con el aviso de Meteocat por intensidad de
lluvia de esa tarde.
