# 97. Peso de los avisos oficiales en la probabilidad de lluvia

Fecha: 2026-10-16 · Actualizado: 2026-11-16 · Estado: probado con AEMET y con Meteocat; no adoptado

## Contexto

El 16-10-2026 la página daba para el sábado 17 por la tarde entre un 6 y un
16 % de lluvia, con un aviso de peligro alto de Meteocat por intensidad de
lluvia (más de 40 mm en 30 minutos) en el Vallès Occidental, uno amarillo de
AEMET por lluvia y tormentas y el INUNCAT en alerta. La probabilidad sale
solo de los modelos (apartado 6 de la metodología: «los avisos se muestran
tal cual»); AROME daba 0 mm, ICON-EU 0,7, ECMWF 3,9 y GFS, que no entra en
la fórmula, 14,8.

Imponer el aviso a la tabla («possible pluja» en cada hora con aviso) se
descartó: un aviso de tormentas cubre toda la comarca y en un punto concreto
a menudo no llueve, y Juanjo recordó que un plan de Protecció Civil que
mandaba sobre lo calculado dio consejos de lluvia en días secos (ADR 0008 y
0062). Juanjo: «sí, aplica el 2», que el peso del aviso salga de los datos.

La variante del modelo propio con los avisos (ADR 0047) solo aprende del
registro del barrio, que el 16-10-2026 tenía 5 horas de lluvia de las 30 que
necesita, y no tenía los de Meteocat.

## Decisión

- **El aviso entra como señal de la regresión del archivo**, no como regla:
  `avis_aemet` (aviso de AEMET por lluvia o tormentas en el Prelitoral de
  Barcelona que cubre la hora) y, si hay su histórico, `avis_meteocat` y
  `avis_meteocat_alt` (aviso de Meteocat por lluvia o tiempo violento en el
  Vallès Occidental, y de peligro alto o más, grado 3 o más). Se ajusta con
  las mismas previsiones archivadas y la lluvia de Sabadell y Sant Cugat
  (`calibracio/pluja_casa_avisos.py`), sobre el modelo con ECMWF (ADR 0086).
- **Solo cuentan los avisos ya emitidos al prever**: una hora antes del
  tramo a corto plazo y un día antes en la previsión de un día vista. Un
  aviso de AEMET sustituido o cancelado por un mensaje posterior ya emitido
  no cuenta.
- **Se adopta solo si la mejora es segura**: con las mismas muestras, en
  semanas que el modelo no ha visto, se equivoca menos que el modelo sin
  avisos en al menos el 95 % de 2.000 remuestreos por días, a corto plazo y
  un día antes, y la fiabilidad no empeora: el desvío medio entre lo dado y
  lo que llovió, ponderado por horas, no pasa del del modelo sin avisos. (Se
  pensó en que no se separara más de 5 puntos en ningún tramo, como la prueba
  del modelo del archivo, pero el modelo con ECMWF ya no lo cumple un día
  antes: da un 24 % y llueve el 32 % en 352 horas desde octubre de 2025.) `pluja_casa_avisos.json` lleva `adoptat`; la página
  lo usa solo si es true y la pasada tiene los avisos
  (`aprenentatge.prob_pluja`). Si no, todo sigue como antes.
- **El histórico**: AEMET OpenData (`/api/avisos_cap/archivo`, desde el
  18-06-2018), con `calibracio/avisos_descarrega.py`. La API de Meteocat solo
  da de hoy a tres días vista (ADR 0109), así que su histórico se pidió por su
  formulario de solicitud de servicios (19-10-2026) y lo mandó su Unitat
  d'Atenció a l'Usuari i al Client por correo el 16-11-2026: tres CSV con
  todas las actualizaciones de los avisos del Vallès Occidental desde el
  01-01-2024, en `calibracio/dades/smp_csv/` (`meteocat_csv`). Cada fila es
  una franja de una actualización, con su hora de emisión; el aviso se
  actualiza cada 12 horas y puede cambiar de franjas o de grado, así que en
  cada momento cuenta la última actualización de cada episodio emitida hasta
  entonces. Las franjas son horas UTC del día UTC de «Data Avís», como en la
  API; Excel convirtió «06-12» y «12-18» en fechas («6-des», «des-18») y se
  leen como tales. Las claves son de Juanjo y no van en el repositorio. Los
  datos de Meteocat no se difunden; se publican solo los pesos.
- **Desde la 3.97.0 el registro apunta también el aviso de Meteocat** de cada
  hora (`avis_meteocat`, `avis_meteocat_alt`; `casa.senyals_avis` y
  `smp.graus_pluja`), para que el modelo propio pueda aprenderlo.

## Alternativas descartadas

- **Que el aviso mande en la tabla** (cielo «possible pluja» y paraguas en las
  horas con aviso): un umbral a ojo que repetiría el error del ADR 0062.
- **Decir solo la contradicción en cada hora**: se puede añadir si hace falta;
  la franja de peligro ya sale encima de esas horas.
- **Esperar al registro del barrio**: meses de otoño hasta las 30 horas de
  lluvia, y sin la historia de 2024-2026.

## Riesgos y limitaciones

- Los CSV de Meteocat traen solo las filas del Vallès Occidental: si una
  actualización sacó a la comarca de un episodio, no aparece, y se sigue
  contando la anterior hasta que el episodio acaba. Puede sobrar alguna hora
  con aviso, nunca faltar.
- Las horas con aviso son pocas en el archivo: puede que la mejora no llegue
  al 95 % y el modelo no se adopte.

## Validación

`tests/test_registre_casa.py`: las señales de Meteocat de cada hora (lluvia y
peligro alto sí, viento no; sin lectura, None). `tests/test_aprenentatge.py`:
la página solo usa el modelo con avisos si está adoptado y la pasada tiene el
dato.

**Resultado con AEMET (16-10-2026).** El archivo de AEMET OpenData del
25-12-2023 al 04-10-2026 (507 tramos de dos días; 498 avisos de lluvia o
tormentas para el Prelitoral, con sus actualizaciones). En las horas con aviso
ya emitido llovió el 31 % a corto plazo (2.258 muestras) y el 35 % un día
antes (646), frente a un 4 % en general. Pero los modelos ya lo ven casi
todo: con el aviso como señal (peso 0,66, multiplica por 1,9 las posibilidades
de lluvia), el error baja un 0,1 % a corto plazo y un 0,7 % un día antes, y
gana solo en el 57 % y el 74 % de los remuestreos por días, lejos del 95 %. La
fiabilidad no empeora (desvío 0,0011 frente a 0,0012; 0,0049 frente a 0,0052).
**No se adopta** (`adoptat: false`): la página sigue con el modelo con ECMWF.
Queda probar con los avisos de Meteocat, por comarca y con su grado, cuando
llegue la clave de su API; y el registro del barrio apunta ya los dos.

**Resultado con Meteocat (16-11-2026).** Con los CSV del Meteocat, sobre el
mismo archivo (01-01-2024 a 04-10-2026) y con el aviso de AEMET también
dentro. En las horas con aviso de Meteocat ya emitido llovió el 25 % a corto
plazo (2.330 muestras) y el 33 % un día antes (522). Los pesos: 0,49 el de
AEMET, 0,39 el de Meteocat y 0,27 más si es de peligro alto. Pero los modelos
ya lo ven: el error es el mismo a corto plazo (0,02194 frente a 0,02195;
gana en el 50 % de los remuestreos) y baja un 0,5 % un día antes (65 %),
lejos del 95 %, y la fiabilidad empeora (desvío 0,0014 frente a 0,0012;
0,0058 frente a 0,0052). **No se adopta** (`adoptat: false`): la página sigue
con el modelo con ECMWF y los avisos se muestran aparte. El registro del
barrio sigue apuntando los dos avisos (desde la 3.97.0), por si el modelo
propio (ADR 0047) encuentra con el tiempo lo que el archivo no da. Pruebas:
`tests/test_avisos_meteocat_csv.py` (las franjas que Excel hizo fecha, los
de tiempo violento sin franja y que solo cuente la última actualización ya
emitida).
