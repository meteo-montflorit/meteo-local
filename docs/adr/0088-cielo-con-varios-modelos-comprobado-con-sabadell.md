# 88. El cielo, con varios modelos y comprobado con el aeropuerto de Sabadell

Fecha: 2026-10-13 · Estado: aceptado

## Contexto

El 13-10-2026, a las 16:43, la tabla decía «Serè» de 16 a 19 h y Juanjo veía
más de la mitad del cielo tapado. Preguntó si el cielo se calibraba o «sale lo
que sale sin mirar nunca si acierta». No se calibraba: era la nubosidad de un
solo modelo, AROME (`cloud_cover` de `meteofrance_seamless`), y nunca se
comparaba con nada. Las nubes de AROME saltan de una hora a otra. Esa tarde,
para casa, daba un 100 % a las 16 h, un 14 % a las 17 h y un 0 % a las 18 h.
ICON-EU daba entre el 68 y el 89 % y GFS, el 100 %. El aeropuerto de Sabadell
observaba «FEW020 BKN030 BKN040», entre 5 y 7 octavos tapados.

La estación de casa no sirve para medir las nubes con la radiación: en días
de sol su máximo ronda los 150 W/m², cuando a pleno sol en octubre serían
unos 550-600. El sensor queda a la sombra parte del día.

Juanjo pidió (13-10-2026) usar varios modelos ya y que el cielo aprenda con
lo observado en el aeropuerto de Sabadell, y que en la hora en curso mande lo
observado.

## Decisión

- **El cielo de cada hora es la media ponderada de cuatro modelos**: AROME
  (`meteofrance_seamless`), ICON-EU, ECMWF IFS y GFS (`nuvols.py`, `MODELS`).
  ECMWF y GFS llegan en una petición aparte a Open-Meteo cada uno; si falla
  uno, el cielo sale de los demás (desde la 3.81.1: el mismo día de
  publicarlo, Open-Meteo, sobrecargado, rechazaba ECMWF y no siempre GFS). Se empieza con los cuatro al 25 %.
- **La observación es el METAR del aeropuerto de Sabadell** (LELL, a unos
  7 km), cada media hora, día y noche. Se lee del servicio público de la
  NOAA (aviationweather.gov, en JSON) y da cuánto tapa cada capa, en octavos.
  El cielo tapado es el de la capa que más tapa, en el punto medio de su
  intervalo: FEW 19 %, SCT 44 %, BKN 75 %, OVC 100 %. Si el servicio da un
  error, se reintenta una vez.
- **En la hora en curso, lo observado manda en las nubes bajas** si el último
  METAR tiene 45 minutos o menos, también si no da capas (CAVOK, NSC, NCD: 0 %
  de nubes bajas). Las de encima, que el METAR no da, son las de la mezcla de
  modelos, y el cielo es lo que tapen las unas o las otras, lo que sea más
  (`nuvols.cel_ara`, desde la 3.189.0; ver el apartado del 22-10-2026). Sin
  modelos, en la previsión de reserva, las de encima son las de la previsión
  anterior.
- **Se registra todo.** Lo observado, por horas, en `registre/nuvols-sabadell.csv`
  (el %, si había capas y los METAR). Lo que daba cada modelo, todas sus
  nubes y las bajas, va en el registro de la previsión (`nuvols_<modelo>` y
  `nuvols_baixos_<modelo>` en `casa-AAAA-MM.jsonl`).
- **Cada día, en `aprenentatge.diari`, se ajustan los pesos con un método
  estadístico** con lo apuntado los últimos 30 días (desde la 3.81.3; antes
  se probaban pesos de 0,1 en 0,1 y se cambiaba con un 5 % menos de error en
  los mismos datos, y Juanjo lo cuestionó el 13-10-2026: «si vas probando no
  estás usando ninguna metodología estadística»). Las horas con capas se
  comparan con todas las nubes de la mezcla; las horas sin capas, con sus
  nubes bajas, que tendrían que ser cero.
  - **Ajuste**: la combinación de previsiones de Granger y Ramanathan (1984),
    mínimos cuadrados con los pesos positivos y sumando 1, resuelta de forma
    exacta (el sistema de Lagrange en cada subconjunto de modelos, 15 con
    cuatro modelos). Sin scipy, que no está en el NAS ni en IONOS: solo numpy.
  - **Comprobación**: validación cruzada por semanas, como la lluvia y la
    temperatura (cuatro grupos por la semana de la hora observada).
  - **Cambio**: solo si los pesos ajustados se equivocan menos que los de
    ahora, en las semanas no vistas, en al menos el 95 % de 2.000 remuestreos
    de los días con reposición (*bootstrap*), con al menos 300 horas
    observadas en 14 días, y salvo que exista `aprenentatge/atura`. Los pesos se guardan en
  `aprenentatge/nuvols-pesos.json`, se usan en la pasada siguiente y se
  avisa a Juanjo por Telegram.
- **La página lo explica** en «D'on surt», en «Com funciona», en «Fonts i
  crèdits» y, desde la 3.81.2, en «Com es llegeix la previsió»: qué parte del
  cielo tapa cada nombre, cuándo sale la lluvia en su lugar y que la hora en
  curso es lo observado en Sabadell (Juanjo, 13-10-2026: «no hay nada sobre
  el cel»).
- **Si deja de llegar el METAR**, la página sigue con los modelos. La
  comparación diaria avisa a Juanjo si hace más de un día que no se apunta
  ninguna hora.

## Alternativas descartadas

- **Seguir solo con AROME**: es el que más se equivoca de los cuatro con las
  nubes (Evidencia).
- **Medir las nubes con la radiación de la estación de casa**: el sensor
  queda a la sombra.
- **Radiación del satélite o de una estación de Meteocat**: solo valen de
  día y dan una estimación, no una observación de las nubes. Juanjo eligió
  Sabadell para las dos cosas.
- **La máscara de nubes del satélite** (medido el 19-10-2026, ver el
  apartado del final): ve el cielo del barrio mejor que Sabadell, pero no
  mejora los pesos y para la hora en curso llega tarde.
- **Contar las horas sin capas como cielo despejado**: con CAVOK o NSC puede
  haber nubes altas. Contadas como 0 %, todos los modelos parecen equivocarse
  unos 40 puntos de cielo tapado.
- **Probar pesos de 0,1 en 0,1 y cambiar con un 5 % menos de error** (la
  3.81.0 a la 3.81.2): los pesos eran aproximados y se elegían y puntuaban con
  las mismas horas, y el 5 % no decía si la mejora era casualidad.
- **Minimizar el error absoluto en lugar del cuadrático**: es lo que se lee
  en el resumen, pero para resolverlo de forma exacta hace falta programación
  lineal (scipy), que no está en el NAS ni en IONOS. Mínimos cuadrados con
  restricciones es además el método de referencia para combinar previsiones.
- **Corregir el sesgo de los modelos con el METAR**: los modelos dan, de
  media, más nubes de las que observa Sabadell, también en las horas con capas
  (de 19 a 32 puntos). Parte puede ser de nubes altas que el METAR no recoge.
  Una corrección aprendida así podría quitar nubes que sí hay. Solo se aprenden
  los pesos.

## Consecuencias

- El cielo cambia menos de una hora a otra y sale menos «Serè» con nubes de
  verdad: en los 17 días de la Evidencia, AROME dio «Serè» 12 horas en que
  Sabadell observaba la mitad del cielo tapado o más; la media de los cuatro,
  ninguna.
- La media también suaviza los extremos: «Serè» y «Cobert» salen menos.
- Dos peticiones más a Open-Meteo por pasada y una a aviationweather.gov.
  Unos 4 KB más por línea del registro de la previsión.
- El bot de Telegram y la tarjeta de «Ara» usan el mismo dato (`nuvols` de
  cada hora): cambian igual.

## Evidencia

- Prueba con el archivo, repetible: METAR de LELL del 27-09 al 13-10-2026
  (aviationweather.gov, unos 800 informes) contra la previsión archivada de
  Open-Meteo (`historical-forecast-api`, los cuatro modelos) para las
  coordenadas de casa: 378 horas en 17 días, 246 con capas y 132 sin capas.
- Error medio, en puntos de cielo tapado, con la comparación de la Decisión:
  AROME 28,8; ICON-EU 29,7; ECMWF 27,0; GFS 29,3. Media de los cuatro, 25,8.
  Con el método de la 3.81.3: pesos ajustados AROME 0,23, ICON-EU 0,20,
  ECMWF 0,30 y GFS 0,27; en semanas no vistas, 26,3. Ganan a todos iguales
  solo en el 0,4 % de los remuestreos (no se cambiaría) y a AROME solo en el
  100 %: mezclar es claramente mejor; afinar los pesos, con estos datos, no.
- Si las horas sin capas contaran como despejadas: AROME 44,7, ICON-EU 40,7,
  ECMWF 37,9, GFS 43,2. En esas horas los modelos daban de media entre un 44
  y un 54 % de cielo tapado, sobre todo nubes medias y altas.
- La previsión archivada es la de las primeras horas de cada pasada del
  modelo; la de la página llega a 45 horas. Hipótesis pendiente: que a más
  antelación la mezcla también acierte más que AROME. Lo dirá el registro.

## Riesgos y limitaciones

- Sabadell está a unos 7 km; con niebla o nubes bajas
  locales el cielo puede ser otro en Montflorit.
- El METAR solo recoge las nubes que importan a los aviones, no las altas. Por eso, en las horas sin capas,
  la comparación no castiga las nubes medias y altas de los modelos, y el
  aprendizaje no puede saber si las hay de verdad.
- El tanto por ciento observado es aproximado: la capa que más tapa, en el
  punto medio de su intervalo de octavos.
- aviationweather.gov es un servicio público documentado de la NOAA, sin
  clave. Si cambia su formato, `nuvols.llegeix` falla y la página sigue con
  los modelos; el aviso diario lo dice.

## Validación

- Pruebas: `tests/test_nuvols.py` (lectura del METAR, horas, observación de
  ahora, mezcla, comparación diaria y aviso sin observaciones; el ajuste
  recupera unos pesos conocidos, respeta las restricciones y ningún punto de
  una rejilla fina lo mejora; sin mejora clara, no cambia).
- En local, el 13-10-2026 a las 16:52, la hora de 16 a 17 pasó de «Serè»
  (AROME, 14 %) a 75 % observado, «Molt ennuvolat»; las siguientes, a la media
  de los cuatro (45 y 48 %).


## Comprobación del 19-10-2026: la máscara de nubes del satélite

Juanjo preguntó si había algún registro de nubes, en concreto del satélite,
que sirviera para el cielo y el sol. Se midió con 92 días (del 18-07 al
18-10-2026), fuera del repositorio: la máscara de nubes de Meteosat (MSG,
cada 15 minutos, del servicio público de EUMETSAT, EUMETView) a 10 km o menos
de casa, el METAR de Sabadell, los cuatro modelos del archivo de Open-Meteo y,
como referencia independiente, la radiación de la estación de Meteocat de
Sant Cugat - CAR (sol tapado: menos del 70 % de la de cielo despejado de esa
hora). Medida: Brier, el % de nubes como probabilidad de sol tapado.

- **Como observación, el satélite gana**: Brier 0,091 frente a 0,118 del
  METAR (836 horas de día). En el 16 % de las horas sin capas en el METAR ve
  medio cielo tapado o más, y de día esas horas tenían el sol tapado la mitad
  de las veces; con el satélite despejado, nunca.
- **Para los pesos, no**: ajustados con el satélite, Brier 0,1353 frente a
  0,1385; gana en el 89 % de los remuestreos por días, por debajo del 95 %
  (ADR 0105).
- **Para la hora en curso, depende del retraso**: con la imagen de hace 30,
  60, 90 y 120 minutos, un 38, 28, 15 y 6 % mejor que ahora (seguridad del
  100, 100, 97 y 76 %). En EUMETView, la de MSG llegaba con unos 90 minutos
  (una lectura); la del satélite nuevo (MTG), en unos 30, pero allí no da la
  máscara de nubes, solo imágenes compuestas en color.

Decisión (Juanjo, 19-10-2026): no se usa. Solo mejoraría el icono de la hora
en curso, a cambio de una fuente más que vigilar, sin servicio documentado.
Se retoma si EUMETSAT publica la máscara de nubes de MTG con poco retraso:
los programas del análisis están con el informe personal de Juanjo del
19-10-2026 («Las nubes vistas desde el satélite»).


## Corrección del 22-10-2026: el METAR solo ve las nubes bajas

El 22-10-2026, a las 18:45, Juanjo veía el cielo medio nuboso, con nubes
delgadas, y la tabla ponía sol en la hora en curso y nubes en todas las
demás. Sabadell había dado «FEW035» (pocas nubes a unos 1.000 m, un 19 %)
todo el día, y en la hora en curso mandaba eso. Pero el METAR da solo las
nubes que importan a la aviación: las altas no salen nunca, y si hay
alguna capa baja, el 19 % se tomaba como todo el cielo. Los modelos daban de
un 70 a un 100 % de nubes medias y altas, y casi ninguna baja; la máscara de
nubes del satélite (10 km alrededor de casa) veía tapado entre el 70 y el
100 % del cielo de 14:30 a 19 h.

**Medida** (repetible, fuera del repositorio, como la del 19-10-2026, con los
datos del 18-07 al 22-10-2026: METAR de la Iowa Environmental Mesonet,
previsión archivada de Open-Meteo, máscara de nubes de MSG en EUMETView y
radiación de Sant Cugat - CAR de la XEMA). Las nubes de encima de cada
modelo salen de sus nubes totales y bajas, con las capas solapadas al azar.
Error medio de la hora en curso, en puntos de cielo tapado, contra el
satélite (2.281 horas, 96 días):

| Regla | Con capas (875 h) | Sin capas (1.406 h) | Todas |
|---|---|---|---|
| Hasta la 3.188: el METAR si da capas; si no, los modelos | 34,5 | 17,6 | 24,1 |
| Bajas del METAR y de encima de los modelos, solapadas al azar | 27,4 | 15,9 | 20,3 |
| **Lo que tapen las unas o las otras, lo que sea más** | **25,8** | **15,9** | **19,7** |

La regla elegida gana a la anterior en el 100 % de los remuestreos por días
(ADR 0105). Contra el sol tapado en Sant Cugat (de día, 874 horas) no hay
diferencia segura (Brier 0,1400 frente a 0,1381; gana en el 39 % de los
remuestreos): las nubes altas y delgadas tapan cielo sin tapar el sol, y lo
que dice la tabla es qué parte del cielo tapan. La regla solapada al azar sí
empeora contra el sol (0,1600, el 2 %): por eso no se usa.

**El aprendizaje no cambia.** Se midió también comparar las horas con capas
con las nubes bajas de cada modelo, en lugar de con todas. Los pesos que
salen (ICON-EU 0,59) aciertan menos, en los días siguientes, contra el
satélite (20,4 frente a 19,2; el 0 % de los remuestreos) y contra el sol
tapado (Brier 0,1494 frente a 0,1399; el 1 %). Lo medido no lo respalda.

