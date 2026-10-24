# 126. El cielo tapado según el satélite, en observación

Fecha: 2026-10-24 · Estado: aceptado

## Contexto

El cielo tapado observado que usa la web es el del aeropuerto de Sabadell
(`nuvols.py`, ADR 0088 y 0100): el METAR automático, a unos 8 km, que solo da
las nubes que importan a los aviones; las altas no las ve. Juanjo
(24-10-2026): «ahora mismo el % de cielo tapado se mide de sabadell que está a
varios km, no hay una forma mejor de medirlo? las imagenes de satelite no se
pueden usar?».

El agente buscó qué había:

- **La máscara de nubes de Meteosat** (MSG, posición de 0°), que EUMETSAT
  publica en su servidor de mapas EUMETView (`https://view.eumetsat.int/geoserver/ows`,
  capa `msg_fes:clm`), abierto y sin clave: cada 15 minutos, con unos 30 de
  retraso, cada píxel es nube o despejado; el histórico llega a 2020. Aquí, un
  píxel son unos 4-5 km.
- La del satélite nuevo, MTG (FCI, unos 2 km según EUMETSAT, METIS), no está
  en EUMETView como dato, solo como imágenes en color: haría falta darse de
  alta en el Data Store y bajar el disco entero cada vez. Descartada.
- La radiación de la estación de casa para desempatar no sirve: el sensor
  está a la sombra (como mucho 31 W/m² un día despejado).

Con la máscara, del 13 al 24 de octubre (86 horas, una de cada tres), el
satélite y Sabadell coincidían en «tapado o no» 55 veces y la correlación era
de 0,37. El satélite veía nubes con Sabadell despejado a mediodía (lo más
probable, nubes altas que el METAR no ve) y, de noche y por la mañana, se le
escapaban las bajas que sí ve Sabadell. Sin una medida en el barrio no se
puede saber cuál se acerca más a lo que se ve. El agente propuso observarla un
mes y preguntar a Juanjo cuando discrepen; Juanjo: «sí, prepáralo así».

## Decisión

- **`nuvols_satellit.py apunta`**, en cada pasada de `publica.sh` en el NAS:
  los cuartos de hora publicados que faltan (de las últimas 3 horas), con la
  parte de los píxeles con nube en un recuadro de unos 18 × 17 km con el barrio
  en medio (`CAIXA`), en `registre/nuvols-satellit.csv` (`t` en tiempo
  universal, `nuvols` en %, `pixels` con dato). Si el servidor no tiene ese
  cuarto de hora devuelve el más cercano y lo dice en una cabecera
  (`Warning: 99 Nearest value used`): no se apunta. La cabecera sale también
  con la misma hora si se pide sin milésimas, y en la 3.196.0 eso dejó sin
  apuntar todos los cuartos: desde la 3.196.1 se pide como la escribe el
  servidor (`…T05:30:00.000Z`) y solo se descarta si la hora es otra. No se
  usa en ningún sitio.
- **`pregunta`**: de 9 a 19 h, si las dos observaciones vigentes (75 minutos
  como mucho) discrepan de verdad, una por debajo del 30 % y la otra por
  encima del 70 %, un mensaje a Juanjo con botones (`confirmacio.py`, como la
  niebla y la llovizna): «Despejado», «Solo nubes altas y finas», «Algunas
  nubes», «Cubierto», «No lo sé». Como mucho dos al día, separados 4 horas.
  «Solo nubes altas y finas» dice si el satélite acierta lo que Sabadell no ve.
- **`respostes`** las apunta en `registre/cel-confirmacions.csv` con lo que
  decían las dos fuentes al preguntar y al responder; **`resum`**, cómo va.
- Se decide a partir del 24-11-2026: el satélite, Sabadell o una combinación
  (por ejemplo, el satélite para las nubes altas y Sabadell para las bajas).

## Alternativas descartadas

- **Usar ya el satélite**: con 55 coincidencias de 86 no se sabe cuál es
  mejor; una fuente nueva se observa antes de usarla.
- **MTG con el Data Store de EUMETSAT**: más resolución, pero un alta, una
  clave y bajar el disco entero cada 10 minutos.
- **La radiación de la estación de casa**: el sensor está a la sombra.
- **El WCS de EUMETView**, que daría el valor de cada píxel y no un dibujo
  (Juanjo señaló los servicios de la página, «API access»: WMS, WFS y WCS): el
  24-10-2026 solo ofrece ocho coberturas (temperatura y clorofila del mar, un
  canal de MTG y uno de satélite polar), no la máscara. Se usa el WMS con el
  estilo fijado (`msg_clm`), para que los colores no cambien si cambia el de
  por defecto.

## Consecuencias

- Una consulta pequeña a EUMETSAT por cuarto de hora (una imagen de 24 × 24
  puntos), sin coste ni clave. Un automatismo más en el inventario del NAS.
- A Juanjo, como mucho dos preguntas al día, solo cuando discrepan.
- Cuando se use en la web, habrá que acreditar a EUMETSAT en «Fonts i
  crèdits».

## Evidencia

- `GetCapabilities` de EUMETView (24-10-2026): `msg_fes:clm`, consultable, con
  dimensión de tiempo de 15 minutos desde 2020-09-01; el blanco es nube y el
  verde, despejado sobre tierra.
- La comparación con `nuvols-sabadell.csv` del 13 al 24 de octubre, con el
  registro del NAS de ese día.

## Riesgos y limitaciones

- La máscara es nube o despejado por píxel: unas nubes altas finas cuentan
  como nube entera. De noche, la detección de las bajas es peor.
- El servicio de EUMETView no tiene compromiso de servicio para terceros: si
  falla, no se apunta y se vuelve a probar en la pasada siguiente.

## Validación

- `tests/test_nuvols_satellit.py`: el porcentaje con píxeles transparentes,
  la discrepancia, los cuartos que faltan sin apuntar el más cercano ni un
  error, la pregunta con sus botones y su respuesta, y cuándo no pregunta (de
  noche, sin discrepancia, con datos viejos, más de dos al día).
- Con el servidor real (24-10-2026): 13 cuartos de hora apuntados, el barrio
  cubierto como Sabadell.
