# Método y estadística de «Temps a Montflorit»

«Temps a Montflorit» (<https://meteo-montflorit.github.io/>) es una web del
tiempo para el barrio de Montflorit, en Cerdanyola del Vallès. Junta
previsiones de varios modelos, el radar, estaciones cercanas y los avisos
oficiales, y aprende de lo que pasa de verdad para que sus porcentajes
signifiquen lo que dicen.

Este documento explica con detalle cómo se calcula lo que muestra. Trata la
probabilidad y los milímetros de lluvia de cada hora, la temperatura, el uso
del radar en las dos primeras horas, los avisos, las recomendaciones de «Si
surts» y la calidad del aire. Está pensado para un lector con nociones de
estadística; la ayuda de la web lo cuenta sin fórmulas. Todo lo hace un
programa normal en un servidor doméstico, con numpy y sin coste. El
aprendizaje automático son regresiones estadísticas clásicas, ajustadas con
lo que ha pasado de verdad: **no interviene ninguna inteligencia artificial
generativa** ni ningún modelo de lenguaje. El último apartado, «Operación»,
recoge los detalles internos que solo necesita la persona que mantiene el
código.

El documento está en castellano. Las decisiones y su porqué están en los
registros de decisiones de arquitectura (ADR, siglas en inglés de
*Architecture Decision Record*) de la carpeta [`adr/`](adr/).

## Índice

1. [Qué se registra](#1-qué-se-registra)
2. [La probabilidad de lluvia: regresión logística](#2-la-probabilidad-de-lluvia-regresión-logística)
3. [La temperatura: regresión lineal](#3-la-temperatura-regresión-lineal)
   - [La humedad](#3-bis-la-humedad)
4. [Las dos primeras horas: el radar llevado hacia delante](#4-las-dos-primeras-horas-el-radar-llevado-hacia-delante)
5. [La persistencia de la lluvia medida](#5-la-persistencia-de-la-lluvia-medida)
6. [Cómo se calcula cada hora de la tabla](#6-cómo-se-calcula-cada-hora-de-la-tabla)
7. [Cómo se dice en la página](#7-cómo-se-dice-en-la-página)
8. [Cuándo se usa un modelo nuevo](#8-cuándo-se-usa-un-modelo-nuevo)
9. [Cuándo para la lluvia](#9-cuándo-para-la-lluvia)
10. [Aviso antes de llover](#10-aviso-antes-de-llover)
11. [Situaciones de peligro](#11-situaciones-de-peligro)
12. [La riera de Sant Cugat](#12-la-riera-de-sant-cugat)
13. [Cuando los modelos no ven la lluvia](#13-cuando-los-modelos-no-ven-la-lluvia)
14. [Si surts](#14-si-surts)
15. [La calidad del aire](#15-la-calidad-del-aire)
16. [El viento de ahora con las vecinas](#16-el-viento-de-ahora-con-las-vecinas)
17. [El sol sobre el termómetro de casa](#17-el-sol-sobre-el-termómetro-de-casa)
18. [Límites](#18-límites)
19. [Operación](#19-operación)
20. [Dónde está cada cosa](#20-dónde-está-cada-cosa)

## 1. Qué se registra

Para aprender hace falta saber qué se dijo y qué pasó. Los modelos que se
usan llegan a través de Open-Meteo: AROME (*Applications of Research to
Operations at Mesoscale*) es el de Météo-France, a 1,5 km en su versión HD y
a 2,5 km en la normal, e ICON-EU (*ICOsahedral Nonhydrostatic*) es el del
servicio meteorológico alemán, a 7 km. Para las nubes se suman ECMWF IFS, el
del Centro Europeo, a 9 km, y GFS, el global de la NOAA de Estados Unidos
(apartado 8). En cada pasada, el servidor guarda:

- **Lo que midió una estación particular del barrio** («la estación de
  casa»), hora a hora: la lluvia de la hora y la temperatura, la humedad, el
  punto de rocío, la presión y la radiación en la hora en punto, y la lluvia
  cada 5 minutos. Ecowitt, el fabricante, guarda su historial, y cada día se
  rellenan las horas que falten. Su pluviómetro solo cuenta cuando marca
  lluvia (ADR 0017). Hasta el 09-10-2026 se guardaba también lo que medía la
  estación de Montflorit de meteocerdanyola.com, retirada desde entonces
  (ADR 0058). Desde el 12-10-2026 se apuntan también los ratos en que el sol
  da en su termómetro, que no cuentan para aprender (apartado 17).
- **La lluvia por horas de las estaciones vecinas de Montflorit** (Weather
  Underground, a menos de 1 km) y, de respaldo, **de las de Meteocat** de
  Sabadell y Sant Cugat (a 2,5 y 4,6 km): deciden qué pasó en las horas en que
  el pluviómetro de casa marca cero (apartado 2.2, ADR 0070). Desde el
  18-10-2026, también la de las vecinas cada 5 minutos, para el final de la
  lluvia (apartado 9, ADR 0102).
- **Lo que daban los modelos**, una vez por hora y para las 24 horas
  siguientes: la lluvia de los tres modelos finos (AROME HD, AROME e ICON-EU)
  y, desde el 13-10-2026, la de ECMWF IFS,
  la fracción de las 40 simulaciones del conjunto ICON-EU-EPS con lluvia, la
  temperatura, las nubes (desde el 13-10-2026, las de los cuatro modelos del
  cielo, todas y las bajas), el viento, la humedad, la radiación, la antelación,
  lo que medían las estaciones al prever y lo que mostró la página. Desde el
  08-10-2026, también lo oficial de cada hora: si había aviso de la Agencia
  Estatal de Meteorología (AEMET) por lluvia o tormentas y si el plan de
  inundaciones de Protección Civil de Cataluña (INUNCAT) estaba en alerta o
  emergencia (ADR 0047).
- **Las nubes que observa el aeropuerto de Sabadell**, a unos 7 km, por
  horas, desde el 13-10-2026, y las que daba cada uno de los cuatro modelos
  que forman el cielo (apartado 8, ADR 0088).
- **El veredicto de cada medio en «Si surts»** (apartado 14).

Al cruzar lo previsto con lo medido se obtiene, para cada hora prevista, qué
se dijo y qué pasó. Con eso se ajustan dos regresiones, una para la lluvia y
otra para la temperatura.

## 2. La probabilidad de lluvia: regresión logística

### Qué es

Una fórmula que convierte varias señales $`x_1, \dots, x_k`$ en una
probabilidad entre 0 y 1:

```math
p = \frac{1}{1 + e^{-(w_0 + w_1 x_1 + \dots + w_k x_k)}}
```

Cada señal $`x_j`$ tiene un peso $`w_j`$. **Los pesos se ajustan con los casos
reales**: son los que hacen más verosímil lo que pasó en las $`n`$ horas
registradas, con una penalización pequeña que evita pesos exagerados cuando
hay pocos datos. Si $`y_i = 1`$ cuando llovió en la hora $`i`$ e $`y_i = 0`$ cuando
no, y $`p_i`$ es la probabilidad que da la fórmula, se minimiza

```math
-\sum_{i=1}^{n} \left[ y_i \ln p_i + (1 - y_i) \ln (1 - p_i) \right]
+ \frac{\lambda}{2} \sum_{j=1}^{k} w_j^2, \qquad \lambda = 1,
```

con el método de Newton-Raphson. La constante $`w_0`$ no se penaliza
(`aprenentatge.py`, `ajustar`).

«Llueve» quiere decir 0,2 mm o más en la hora, el umbral a partir del cual ya
moja en moto (`UMBRAL_MM` de `config.py`).

### Señales

| Señal | Cómo entra | Por qué |
|---|---|---|
| Lluvia de AROME HD, AROME e ICON-EU | $`\ln(1 + \text{mm})`$, una por modelo | Cada modelo acierta de forma distinta; el logaritmo evita que un chubasco extremo pese demasiado |
| Si cada modelo da lluvia | 1 si da 0,1 mm o más; si no, 0. Una por modelo | Que un modelo ponga algo de lluvia ya dice mucho, aunque sea poca: con solo ICON-EU dando 0,2 mm llovió una de cada diez horas |
| Cuántos modelos coinciden | 1 si dan lluvia dos o más; otra, 1 si la dan los tres | La coincidencia no suma sin más: con un modelo solo llovió el 21-23 % de las horas; con los tres, el 66 % |
| Lo anterior según la antelación | La cantidad de cada modelo, «alguno da lluvia» y «la dan los tres», multiplicados por la antelación | La lluvia prevista para dentro de un día se cumple menos que la de las próximas horas |
| Lluvia de ECMWF‡ | $`\ln(1 + \text{mm})`$, si la da (0,1 mm o más), su cantidad por la antelación, 1 si la dan los cuatro modelos y 1 si solo la da ECMWF | El modelo europeo de referencia (ECMWF IFS, a 9 km) acierta más a un día vista: con el archivo, el error baja un 5,5 % un día antes y un 2,6 % a corto plazo (ADR 0086 y 0090) |
| Antelación | $`\min(t / 24, 1)`$, con $`t`$ en horas | Una previsión a 24 horas es menos segura que una a 2 |
| Hora del día | $`\sin(2\pi h / 24)`$ y $`\cos(2\pi h / 24)`$, con $`h`$ la hora solar (la del tiempo universal, ADR 0090) en que acaba el tramo | Las tormentas de tarde no se reparten igual que la lluvia de frente |
| Día del año | $`\sin(2\pi d / 365\text{,}25)`$ y $`\cos(2\pi d / 365\text{,}25)`$ | La lluvia de otoño no es la de verano |
| Fracción del conjunto* | de 0 a 1 | Cuántas de las 40 simulaciones de ICON-EU-EPS ven lluvia |
| Lluvia medida al prever* | $`\ln(1 + \text{mm de la última hora})`$ en casa si $`t \le 4`$; si no, 0 | Si ya llueve, es probable que siga |
| Sequedad del aire al prever* | $`\min(\max(T - T_d, 0), 15) / 10`$ en casa si $`t \le 4`$; si no, 0 | Con el aire seco, la lluvia cercana es menos probable |
| Lluvia en Sant Cugat al prever*† | $`\ln(1 + \text{mm de la última hora})`$ en la estación de Meteocat de Sant Cugat (4,6 km al oeste, en la cuenca de la riera) si $`t \le 4`$; si no, 0 | Lo que llueve cerca puede llegar o anticipar. Es una hipótesis: se ajusta en una variante aparte y solo se adopta si acierta más (ADR 0042) |
| Lluvia en las vecinas al prever*† | $`\ln(1 + \text{mm de la última hora})`$, la mediana de las vecinas fiables de Montflorit, si $`t \le 4`$; si no, 0 | Lo que llueve ahora en el barrio, aunque el pluviómetro de casa no lo recoja. En el archivo (75 días) bajó el error a corto plazo un 8 %; se ajusta en una variante aparte y solo se adopta si acierta más (ADR 0070) |

‡ Desde el 13-10-2026, en un modelo del archivo aparte
(`calibracio/pluja_casa_ecmwf.json`, ajustado con `pluja_casa_ecmwf.py`) que
se usa cuando la pasada tiene ECMWF; si no, el de siempre. Con un día de
antelación solo hay ECMWF de 9 km desde octubre de 2025: ese modelo se
ajusta con las horas a corto plazo de todo el archivo y las de un día antes
de ese año. \* Solo con datos propios: el archivo no las tiene (apartado 2.2). $`T_d`$ es
el punto de rocío. † Registrada desde el 08-10-2026. Meteocat es el Servei
Meteorològic de Catalunya.

### 2.1 Primer modelo: el archivo de 2024-2026

La estación de casa no tiene historial de lluvia en el que fiarse (ADR
0017), así que el primer modelo se ajusta con lo que sí lo tiene
(`calibracio/pluja_casa.py`):

- previsiones archivadas de Open-Meteo para el barrio, del 01-01-2024 al
  04-10-2026, a corto plazo y hechas un día antes;
- lluvia medida cada media hora en Sabadell y Sant Cugat (portal de datos
  abiertos de la Generalitat), cada estación como una muestra.

Son 94.380 muestras (una por hora y estación), con lluvia en 3.622, el 4 %.

**Comprobación antes de usarlo.** Se hace con todo el archivo, en semanas que
el modelo no ha visto: los días se reparten en cuatro grupos por semanas y
cada grupo se predice con un modelo ajustado con los otros tres
(apartado 8). Se mira por separado el corto plazo y la previsión hecha un día
antes. Se mide con el error de Brier, la media del cuadrado de la diferencia
entre la probabilidad dada y lo que pasó:

```math
B = \frac{1}{n} \sum_{i=1}^{n} (p_i - y_i)^2
```

Menos es mejor.

| Método | Corto plazo | Un día antes |
|---|---|---|
| Frecuencia habitual de lluvia (siempre la misma probabilidad) | 0,0368 | 0,0370 |
| Regresión solo con la cantidad de lluvia de cada modelo (hasta la versión 2.11) | 0,0251 | 0,0296 |
| **Regresión con las señales de la tabla** | **0,0225** | **0,0271** |

Más que el error importa la **fiabilidad**: que cuando la página dice un
15 % llueva el 15 % de las veces. A corto plazo (1.825 horas de lluvia):

| Probabilidad dada | Horas | Media dada | Llovió | Parte de toda la lluvia |
|---|---|---|---|---|
| 0-5 % | 42.327 | 0,6 % | 0,6 % | 13 % |
| 5-10 % | 1.049 | 8 % | 8 % | 5 % |
| 10-20 % | 1.736 | 14 % | 15 % | 15 % |
| 20-30 % | 713 | 24 % | 27 % | 10 % |
| 30-50 % | 817 | 40 % | 38 % | 17 % |
| 50-70 % | 538 | 59 % | 62 % | 18 % |
| 70-100 % | 496 | 82 % | 79 % | 22 % |

Con la previsión de un día antes (1.797 horas de lluvia):

| Probabilidad dada | Horas | Media dada | Llovió | Parte de toda la lluvia |
|---|---|---|---|---|
| 0-5 % | 41.538 | 1 % | 1 % | 24 % |
| 5-10 % | 642 | 8 % | 9 % | 3 % |
| 10-20 % | 1.983 | 15 % | 14 % | 16 % |
| 20-30 % | 1.012 | 24 % | 27 % | 15 % |
| 30-50 % | 879 | 39 % | 37 % | 18 % |
| 50-70 % | 456 | 59 % | 58 % | 15 % |
| 70-100 % | 194 | 79 % | 81 % | 9 % |

La última columna dice dónde cae la lluvia de verdad: **el 13 % de las horas
de lluvia a corto plazo, y el 24 % un día antes, llegan cuando la página daba
menos de un 5 %**. Es lluvia que ninguno de los tres modelos veía, y ninguna
fórmula hecha con ellos la recupera.

**Por qué se cambió la fórmula (06-10-2026).** La primera solo usaba la
cantidad de lluvia de cada modelo y se comprobó con los últimos 90 días, que
tenían 95 horas de lluvia: parecía fiable. Con todo el archivo no lo era:
cuando daba un 7 % llovió el 25 % de las horas; con un 14 %, el 33 %; con un
24 %, el 44 %, y cuando daba un 89 %, el 77 %. El logaritmo de los
milímetros casi no distingue 0 de 0,2 mm, y esa diferencia es la que más
cuenta. La comparación de entonces con la fracción del conjunto tampoco
valía: Open-Meteo solo conservaba simulaciones de 96 de las 4.368 muestras, y
las demás se contaron como «0 %» (ADR 0021).

Una prueba (`tests/test_aprenentatge.py`) falla si, al volver a ajustar, lo
dado y lo que llovió se separan más de 5 puntos en algún tramo con 150 horas
o más.

Después de comprobarlo, el modelo se ajusta con todos los datos. Sus pesos y
las dos tablas están en `calibracio/pluja_casa.json`.

### 2.2 Segundo modelo: los datos de casa

Montflorit primero (ADR 0070). Una hora cuenta como lluviosa si casa recoge
0,2 mm o más (lo que marca es lluvia, ADR 0017) o si lo recogen al menos dos
de las tres vecinas fiables (ICERDA6, ICERDA18 e ICERDA28): el pluviómetro de
casa a veces no marca la lluvia débil, y el 03-10-2026 no marcó ni la fuerte.
Con cero en casa, la hora cuenta como seca si ninguna de esas vecinas ve
lluvia; si solo una la ve, no se sabe y la hora no se usa. Sin vecinas, como
antes: seca si Sabadell y Sant Cugat tampoco recogieron nada (ADR 0058). En
75 días, las tres vecinas vieron la lluvia de casa en 33 o 34 de cada 36
horas; Sabadell, en 28, y Sant Cugat, en 32; y una vecina sola casi nunca
marca en falso (de 0 a 2 horas de 1.643).

Cuando el registro reúna **30 horas con lluvia** (horas observadas distintas:
cada hora se prevé muchas veces, con distintas antelaciones, y no cuenta más
por eso), se ajusta un modelo propio con todas las señales de la tabla,
incluidas las que el archivo no tiene. Sustituye al del archivo solo si,
en días que no ha visto (cada uno predicho con los anteriores), acierta mejor
que lo que la web publica con el archivo (apartado 8). En otoño llueve unas
25 horas al mes (entre 9 y 48 en Sabadell y Sant Cugat desde 2024): puede
tardar de uno a varios meses.

Mientras manda el modelo del archivo, se usa el que lleva ECMWF si la
pasada lo tiene, y si no, el de siempre. Si al prever falta alguna señal del
modelo propio (por ejemplo, la estación de casa), se usa el del archivo. Si
tampoco se puede, porque falta la lluvia de alguno de los tres modelos, la
probabilidad es la fracción del conjunto ICON-EU-EPS (apartado 6).

Se ajustan dos variantes, sin y con la lluvia de Sant Cugat. La variante
se valida solo con las muestras que llevan ese dato y, con esas mismas
muestras, se ajusta y valida otra vez el modelo sin él: un error medido en
horas distintas no se puede comparar (hasta el 09-10-2026 se comparaba con
el error del modelo base en todas las horas; ADR 0057). La variante se
adopta si gana al modelo base en sus mismas horas con la regla común del
apartado 8 (el 95 % de los remuestreos por días; hasta la 3.144.0, un 5 %
menos de error), además de ganar al archivo. Al prever, la lluvia de Sant Cugat es la de
la última media hora medida que usa la riera (apartado 12), si tiene menos
de 2 horas; sin ella, en las cuatro primeras horas se usa el modelo del
archivo. Cuando la variante llegue a las 30 horas de lluvia, se comunica
una sola vez el error de las dos a las mismas horas. Si la estación cercana
ayuda, se valorará añadir la del aeropuerto de Sabadell (5 km al norte),
que publica la AEMET (ADR 0042).

Una tercera variante añade lo oficial de cada hora (ADR 0047): $`a`$, 1 si hay
aviso de la AEMET por lluvia o tormentas en el Prelitoral de Barcelona, y
$`c`$, 1 si el INUNCAT está en alerta o emergencia. Así el peso de un aviso
sale de lo que pasa en Montflorit en lugar de fijarse a mano. Como se
registran desde el 08-10-2026, se valida solo con esas horas y se adopta con
las mismas condiciones que las otras.

Desde la 3.97.0 el registro apunta también si Meteocat avisa por lluvia o
tiempo violento en el Vallès Occidental, y si el aviso es de peligro alto o
más. Mientras tanto, el peso de los avisos se aprende con el archivo
(ADR 0097): $`a`$ de AEMET y, cuando haya su histórico, $`m`$ y
$`m_{\text{alt}}`$ de Meteocat entran en el modelo con ECMWF, con los avisos
ya emitidos al prever. Se adopta solo si se equivoca menos que sin ellos en
el 95 % de los remuestreos por días y sigue siendo fiable.

### 2.3 Lo que aporta casa con su historial

Con la lluvia de casa de octubre de 2025 a agosto de 2026, cuando el
pluviómetro iba bien (297 horas con lluvia), se comprobó si las señales de
casa mejoran el modelo del archivo (`calibracio/estacio_casa.py`). El error
de Brier pasa de 0,0236 a 0,0241: solo mejora la primera hora (de 0,0227 a
0,0223) y empeora a partir de la segunda. La presión y su tendencia no
mejoran en ninguna antelación. Por eso el modelo del archivo no cambia: las
señales de casa solo entran en el modelo propio, que se adopta si demuestra
que acierta más.

Esta comprobación sirve además de contraste de la fórmula con una estación
que no se usó para ajustarla: con la lluvia de casa como verdad, el error del
modelo del archivo bajó de 0,0263 a 0,0236 al pasar a la fórmula del
apartado 2.1.

## 3. La temperatura: regresión lineal

La temperatura que da el modelo (AROME a 1,5 km) es la de una celda, no la de
casa. La diferencia suele repetirse: en casa, el modelo da de media 0,8 °C
más, y sobre todo de noche.

Se ajusta una regresión lineal del **error del modelo**,
$`e = T_{\text{modelo}} - T_{\text{medida}}`$, con la temperatura medida en la
estación de casa, a partir de unas señales $`\mathbf{z}`$:

| Señal | Cómo entra | Por qué |
|---|---|---|
| Temperatura prevista | en °C | El error no es el mismo con frío que con calor |
| Nubes y humedad previstas | de 0 a 1 | Las noches despejadas y secas enfrían más en casa que en la celda |
| Radiación prevista | en kW/m² | Con sol fuerte, el error de día cambia |
| Hora solar y día del año | seno y coseno, en tiempo universal (ADR 0090) | El error tiene ciclo diario y estacional, que marca el sol |
| Antelación | $`\min(t / 24, 1)`$ | Cuanto más lejos, más incierto |
| Error al prever* | $`e_0 \, e^{-t/3}`$ y $`e_0 \, e^{-t/24}`$ | Si el modelo se equivoca ahora, en las horas siguientes suele equivocarse igual |

\* $`e_0`$ es el error del modelo en el momento de prever: su temperatura en
ese momento, interpolada entre las dos horas en punto, menos la que mide
casa. Se apaga con la antelación $`t`$: una parte en unas tres horas y otra en
un día. Los pesos deciden cuánto cuenta cada una.

Los pesos $`\mathbf{v}`$ minimizan

```math
\sum_{i=1}^{n} \left( e_i - \mathbf{v}^\top \mathbf{z}_i \right)^2
+ \lambda \sum_{j \ge 1} v_j^2, \qquad \lambda = 1,
```

una regresión *ridge*, con la misma penalización pequeña que en la lluvia
(`aprenentatge.py`, `ajustar_ridge`). La temperatura que se muestra es la del
modelo menos el error esperado:

```math
T_{\text{mostrada}} = T_{\text{modelo}} - \mathbf{v}^\top \mathbf{z}
```

La corrección se calcula para cada hora en punto, que es lo que se compara
con lo medido. Como la temperatura es la de un instante, cada tramo de la
tabla («de 18 a 19») muestra la media de sus dos extremos, los dos
corregidos:

```math
T_{18\text{–}19} = \tfrac{1}{2}\left(T_{\text{mostrada}}(18) + T_{\text{mostrada}}(19)\right)
```

Se mide con el error medio absoluto,
$`\frac{1}{n} \sum_i \lvert T_i - T_{\text{medida},i} \rvert`$.

### 3.1 Primer modelo: un año de la estación de casa

Ecowitt guarda un año de lecturas cada 30 minutos. Con ellas y las
previsiones archivadas de Open-Meteo, a corto plazo y hechas un día antes,
se ajusta el primer modelo (`calibracio/estacio_casa.py`, pesos en
`calibracio/temperatura_casa.json`): 43.099 horas de 364 días, del
08-10-2025 al 06-10-2026. Comprobado en semanas que no ha visto:

| Antelación | Modelo sin corregir | Corregida | Corregida sin el error al prever |
|---|---|---|---|
| 1 h | 1,44 °C | **0,76 °C** | 1,13 °C |
| 3 h | 1,45 °C | **1,04 °C** | 1,13 °C |
| 6 h | 1,45 °C | 1,14 °C | 1,13 °C |
| 24 h | 1,54 °C | **1,26 °C** | 1,29 °C |
| Todas | 1,46 °C | **1,03 °C** | 1,16 °C |

La corrección quita un 30 % del error, y en la hora siguiente casi la mitad.
Si la estación de casa falla al prever, se usan los pesos ajustados sin el
error al prever (última columna).

### 3.2 Segundo modelo: el registro propio

Con **14 días** registrados, cada día se ajusta el mismo modelo con lo que
se previó de verdad y lo que midió casa, con la antelación real de cada hora,
y se compara con el primero (apartado 8). Las horas con sol en el termómetro
de casa no cuentan (apartado 17).

La hora y el día del año, en la lluvia y en la temperatura, son los del
sol: los del tiempo universal, que no cambian con el reloj (desde el
14-10-2026, ADR 0090). Antes eran los del reloj, y el mes siguiente a cada
cambio de hora iban desplazados una hora respecto al sol. Con las mismas
muestras y semanas no vistas (`calibracio/hora_solar.py`), el error de la
temperatura baja 0,002 °C (de 1,031 a 1,029 °C; intervalo del 95 % por
bootstrap de días, de 0,0002 a 0,004 °C) y el de la lluvia no cambia: con
un solo armónico diario y la radiación, que ya sigue al sol, la hora apenas
pesa. Se cambió por coherencia, y los tres modelos de partida se volvieron
a ajustar con ella sin empeorar.

### La parte alta del barrio (ADR 0087)

La estación de casa está junto a la riera, en la zona más fría del barrio,
como ICERDA6; ICERDA18, ICERDA28 e ICERDA48 están en la parte alta. Las
temperaturas de la página son las de la riera, y se dice cuánto más hace
arriba:

- **Ahora**: $`\Delta = \operatorname{mediana}(T_{\text{alta}}) - T`$, con
  las vecinas de arriba leídas en la última media hora (al menos dos). Sale
  si, redondeada, llega a un grado: desde 0,5 °C.
- **En la previsión**, para cada hora solar $`h`$ (la hora del tiempo
  universal, que no cambia con el reloj: la diferencia la marcan el sol y el
  aire que se calienta; desde el 14-10-2026, ADR 0087):

```math
\Delta_h = \operatorname{mediana}_{d \in \text{últimos 30 días}}
\left[ \operatorname{mediana}(T_{\text{alta}}(d, h)) - T_{\text{casa}}(d, h) \right]
```

  sin las horas con sol directo sobre el termómetro y con 10 casos como
  mínimo; si no, la de partida (`calibracio/part_alta.json`, verano y otoño
  de 2026: de +0,1 a +0,4 °C de noche y de +1,4 a +1,9 °C de 12 a 18 h en
  horario de verano, de 10 a 16 h en tiempo universal).
  **De noche** (de 17 a 8 h en tiempo universal; desde el 19-10-2026), la
  mediana se corrige con las nubes $`N`$ (%), el viento $`V`$ (km/h) y la
  temperatura $`T`$ (°C) previstos de la propia fila:

```math
\Delta'_h = \Delta_h + \beta_0 + \beta_1 c + \beta_2 v + \beta_3 c\,v + \beta_4 \min(T, 15),
\qquad c = 1 - \tfrac{N}{100},\quad v = \max\!\left(0,\ 1 - \tfrac{V}{15}\right)
```

  con $`\beta = (-0{,}12;\ -0{,}21;\ 0{,}22;\ 1{,}01;\ -0{,}02)`$, ajustados por
  mínimos cuadrados con las horas de noche de tres inviernos (2023-2026,
  ICERDA6 como riera, ICERDA18 e ICERDA28 como parte alta, ICON-EU emitido el
  día anterior; `calibracio/part_alta.json`, «ajust_nit»). Con el cielo
  despejado y en calma, la inversión deja la parte alta unos 2 °C por encima
  y la mediana de 30 días, que mezcla todo tipo de noches, da 1-1,5; con
  nubes o viento casi no cambia. Validado por semanas y dejando fuera cada
  invierno: en las 32 noches con la riera a 0 °C o menos, el error de la
  mínima de arriba baja de 1,03 a 0,85 °C (gana en el 99 % de los
  remuestreos) y «glaçada vora la riera» acierta 26 de 32 (23 sin el
  ajuste). Como la web usa la estación de casa, las nubes de cuatro modelos y
  el viento de AROME, el invierno 2026-27 se vigila: `part_alta.py nit-resum`
  compara lo que dio la web con el ajuste y sin él (registre/part-alta-nit.csv)
  con lo medido.
  Cada fila lleva la media de $`\Delta`$ en sus dos extremos, y el tramo dice
  la diferencia de su máxima (de día) o de su mínima (de noche) si,
  redondeada, llega a un grado; el resumen del día, la máxima de arriba. Si la mínima de la riera llega a 0 °C y la de arriba no, la
  helada es «vora la riera».

Si falla la estación de casa, la temperatura de «Ara» es la de ICERDA6 o, sin
ella, la de arriba menos $`\Delta_h`$.

### 3 bis. La humedad

*(ADR 0114.)* La gráfica puede mostrar la humedad relativa de cada hora. No
se toma la de AROME tal cual: es la de su temperatura, y la temperatura de
la página está corregida (apartado 3); con la misma agua en el aire y menos
temperatura, la humedad es mayor. Por eso se corrige el **punto de rocío**,
que solo depende del agua que lleva el aire, y la humedad sale de él y de la
temperatura que se muestra.

El rocío del modelo sale de su temperatura $`T`$ y su humedad $`H`$ con la
fórmula de Magnus ($`a = 17{,}625`$, $`b = 243{,}04`$ °C), y la humedad, al
revés:

```math
\gamma = \ln\frac{H}{100} + \frac{a\,T}{b + T}, \qquad
T_d = \frac{b\,\gamma}{a - \gamma}, \qquad
H = 100 \, \frac{e^{a T_d / (b + T_d)}}{e^{a T / (b + T)}}
```

El error del rocío, $`e_d = T_{d,\text{modelo}} - T_{d,\text{medido}}`$, se
corrige con la misma regresión *ridge* que la temperatura y las mismas
señales, más el propio rocío previsto; el error al prever es el del rocío
($`e_{d,0}\,e^{-t/3}`$ y $`e_{d,0}\,e^{-t/24}`$). Lo medido es el rocío del
barrio: la mediana de casa y las vecinas, el mismo del recuadro «Ara». El
rocío casi no cambia dentro del barrio (del 9 al 21-10-2026, en 280 horas,
la mediana de las vecinas quedó a −0,07 °C del de casa de media): lo que
cambia de un sitio a otro es la temperatura.

En cada tramo, como la temperatura, el rocío es la media de los dos extremos,
y no pasa de la temperatura del tramo:

```math
H_{18\text{–}19} = H\!\left(\min\!\left(\tfrac{1}{2}\big(T_d(18) + T_d(19)\big),\; T_{18\text{–}19}\right),\; T_{18\text{–}19}\right)
```

**Primer modelo: un año de la estación de casa** (`calibracio/humitat_casa.py`,
pesos en `calibracio/humitat_casa.json`). Las vecinas solo están registradas
desde octubre de 2026; como su rocío es el mismo, el primer año es el de
casa: 43.099 horas de 363 días, del 08-10-2025 al 06-10-2026, con las mismas
previsiones archivadas que la temperatura. AROME ve el aire más seco de lo
que está: su rocío queda 1,28 °C por debajo de media. Comprobado con avance
temporal (cada día, con los pesos ajustados con los anteriores; apartado 8),
356 días evaluados, en puntos de humedad (la humedad que sale de cada rocío
con la temperatura medida):

| Antelación | Modelo sin corregir | Corregida | Corregida sin el error al prever |
|---|---|---|---|
| 1 h | 7,2 | **3,7** | 4,5 |
| 3 h | 7,2 | **4,3** | 4,5 |
| 6 h | 7,2 | **4,5** | 4,5 |
| 24 h | 7,7 | **5,1** | 5,2 |
| Todas | 7,3 | **4,4** | 4,6 |

En rocío, el error medio baja de 1,82 a 0,98 °C, y gana en el 100 % de los
remuestreos por días: se adopta (`"adoptat": true`). Sin ninguna estación al
prever, se usan los pesos sin el error al prever.

**Segundo modelo: el registro del barrio.** Cada día el NAS ajusta el mismo
modelo con lo previsto y el rocío del barrio, con **14 días** como mínimo, y
lo usa si gana al del año de casa con la regla del apartado 8
(`aprenentatge.valida_humitat`; el día a día, en `historial-humitat.csv` y
en la página «Fiabilitat»). El error al prever se guarda desde la 3.171.0:
hasta tener 14 días con él, no hay candidato.

## 4. Las dos primeras horas: el radar llevado hacia delante

En las primeras horas, la lluvia que ya existe y cómo se mueve dicen más que
los modelos: el 05-10-2026 los modelos daban 0,3 mm por hora mientras caían
más de 20 (ADR 0019). Por eso, hasta dos horas, se usa también el radar
(`nowcast.py`). Es un cálculo fijo, no aprendido; lo único que se aprende es
qué radar usar (apartado 8).

### De color a lluvia

La imagen es la última del radar que más acierta (ver más abajo): la de
RainViewer, una composición de la AEMET cada 10 minutos, o la de Meteocat
(cada 6 minutos; el radar de Vallirana está a unos 20 km), que publica cada
imagen unos 15 minutos después de tomarla. Cada píxel se pasa a
reflectividad en dBZ (decibelios de reflectividad) con la leyenda de cada
radar, y de ahí a intensidad $`R`$ en mm/h con la relación de Marshall-Palmer:

```math
Z = 200\,R^{1\text{,}6}, \qquad Z = 10^{\text{dBZ}/10}
\quad\Longrightarrow\quad
R = \left(\frac{Z}{200}\right)^{1/1\text{,}6}
```

Se considera que llueve en un píxel desde $`R \ge 0\text{,}5`$ mm/h, unos 18 dBZ.

### El movimiento

Se usa el de la advección de Meteocat, su previsión a una hora calculada con
las tres últimas imágenes, si tiene menos de 60 minutos. Se mide el
desplazamiento entre su primera y su última imagen prevista, **en la lluvia
que hay a 60 km o menos de casa** (ADR 0023): la que puede llegar es esa, y
la de más lejos puede moverse de otra manera. Se busca la traslación
$`\Delta`$ que más hace coincidir las dos manchas de lluvia, con el índice de
Jaccard

```math
J(\Delta) = \frac{\left|A_{\Delta} \cap B\right|}{\left|A_{\Delta} \cup B\right|},
```

donde $`A_{\Delta}`$ son los píxeles con lluvia de la primera imagen
desplazados y $`B`$ los de la segunda. Solo se acepta si $`J \ge 0\text{,}3`$, si cada
imagen tiene al menos 50 píxeles con lluvia cerca y si el mejor salto no
queda en el borde de la búsqueda, que llega a 120 km/h como mucho.

Si no se cumple, el movimiento se mide en un cuadro de unos 300 km con la
correlación de fase de las dos imágenes $`a`$ y $`b`$, tomadas como
$`\ln(1 + R)`$ y con una ventana de Hann:

```math
c = \mathcal{F}^{-1}\!\left[\frac{\mathcal{F}(b)\,\overline{\mathcal{F}(a)}}{\left|\mathcal{F}(b)\,\overline{\mathcal{F}(a)}\right|}\right]
```

El desplazamiento es la posición del máximo de $`c`$, afinada con una parábola
en cada eje. Sin advección, se usan pares de imágenes de RainViewer separados
30 minutos, solo si los pares difieren menos de 20 km/h.

Con las imágenes de la tarde del 06-10-2026 (ADR 0023,
`calibracio/moviment_radar.py`), el error de la flecha a 60 minutos bajó de
16,3 km, midiendo en el cuadro de 300 km, a 8,0 km, midiendo en la lluvia de
cerca. En 97 puntos a menos de 55 km de casa, el error de Brier a 60 minutos
pasó de 0,184 a 0,126 (0,179 con la lluvia quieta).

Como esa comprobación es de una sola tarde, desde el 17-10-2026 el NAS
registra el movimiento en cada pasada (`moviment_registre.py`): guarda el
trozo de 60 km alrededor de casa de la última imagen de cada radar y, 30 y 60
minutos después, compara con la imagen nueva del mismo radar, en el círculo de
50 km, la lluvia llevada hacia delante y la lluvia quieta, con el índice de
acierto

```math
\mathrm{CSI} = \frac{\text{aciertos}}{\text{aciertos} + \text{fallos} + \text{falsas alarmas}},
```

contando píxeles con 0,5 mm/h o más. El resumen (`python3 moviment_registre.py
resum`) da el CSI medio de los dos por antelación y por fuente del
movimiento, en cuántos casos gana cada uno y cuánto se aparta la dirección del
viento a 700 hPa de Open-Meteo. Con un mes de datos se decidirá si hay que
revisar el método.

El movimiento solo desplaza la imagen: no ve la lluvia que crece o se forma
cada vez más cerca, como la tormenta del 17-10-2026, que pasó de 0 a 118 km²
a 15 km o menos de casa en media hora sin acercarse. Desde ese día se
registra también, para cada imagen de RainViewer (`creixement.csv`), la
superficie con lluvia (0,5 mm/h o más) a 15 km o menos, $`A_t`$, la de 30
minutos antes, $`A_{t-30}`$, y la distancia de la lluvia moderada (2 mm/h o
más) en las dos. La página solo dice lo medido, como parte del círculo de
15 km (unos 707 km²) que ocupa la lluvia ahora y hace media hora («ja ocupa
el 31 % del terreny a 15 km o menys; fa mitja hora, el 16 %»), cuando ha
ganado al menos 50 km²: $`A_t - A_{t-30} \ge 50`$ km². Se cuenta lo que gana
y no cuántas veces crece, porque el doble de 10 km² son unos píxeles y el de
216 es buena parte del entorno. Con un mes
de datos se comprobará, con regresión logística y validación con días que el
modelo no ha visto, si $`A_t`$, $`A_t / A_{t-30}`$ y esas distancias
anuncian lluvia en casa en la hora siguiente; solo si la mejora es segura
pasarán a dar una hora de llegada.

### Hacia delante

Para cada lugar (casa y el centro de la cuenca de la riera) y cada 5 minutos
$`t`$, hasta 120, se mira la lluvia de ahora en el punto de donde vendrá,
$`\mathbf{x} - \mathbf{v}\,t`$, y en un círculo $`\mathcal{C}_t`$ alrededor, de
radio

```math
r(t) = 3 + 0\text{,}08\,t \ \text{km} \qquad (t \ \text{en minutos}),
```

que crece porque el movimiento es incierto. Cada píxel del círculo es un caso
posible:

```math
\hat R(t) = \frac{1}{\left|\mathcal{C}_t\right|}\sum_{j \in \mathcal{C}_t} R_j,
\qquad
p(t) = \frac{\left|\{\, j \in \mathcal{C}_t : R_j \ge 0\text{,}5 \,\}\right|}{\left|\mathcal{C}_t\right|}
```

La lluvia que nace o muere en ese tiempo no se ve: por eso solo dos horas, y
por eso el radar **nunca baja** lo que dan los modelos.

### En la tabla y en la tarjeta de ahora

Para una hora de la tabla, el radar da

```math
p_{\text{radar}} = \max_{t \in \text{hora}} p(t), \qquad
\text{mm}_{\text{radar}} = \sum_{t \in \text{hora}} \hat R(t) \cdot \frac{5}{60}
```

sobre los pasos de 5 minutos que caen en ella. Cómo se combina con lo demás
está en el apartado 6.

En la tarjeta de ahora, «Arribaria pluja cap a les…» es el primer paso con
$`p(t) \ge 0\text{,}5`$, la mitad del círculo con lluvia, y «Pot arribar pluja cap a
les…», el primero con $`p(t) \ge 0\text{,}2`$. La hora en que pararía está en el
apartado 9.

## 5. La persistencia de la lluvia medida

Si ya llueve, lo más probable es que siga lloviendo un rato, aunque los
modelos no lo vean. Con la lluvia cada media hora de Sabadell y Sant Cugat
entre 2024 y 2026 (`calibracio/analitza.py`, guardada en
`calibracio/calibracio.json`), se cuenta qué pasó después de cada hora con
lluvia. Para una clase $`c`$ de lluvia en una hora y $`k`$ horas después:

```math
P_k(c) = \frac{\#\{\, h : \text{mm}(h) \ge c,\ \text{mm}(h+k) \ge 0\text{,}2 \,\}}{\#\{\, h : \text{mm}(h) \ge c \,\}}
```

y la lluvia esperada es la mediana de $`\text{mm}(h+k)`$ en esas horas:

| Lluvia en la última hora | 1 h después | 2 h | 3 h | 4 h | Casos |
|---|---|---|---|---|---|
| 0,2 mm o más | 63 % (0,4 mm) | 48 % (0,1 mm) | 40 % (0 mm) | 34 % (0 mm) | 1.842 |
| 1 mm o más | 78 % (1,1 mm) | 56 % (0,3 mm) | 44 % (0,1 mm) | 38 % (0 mm) | 859 |
| 4 mm o más | 86 % (2,0 mm) | 57 % (0,4 mm) | 43 % (0 mm) | 38 % (0 mm) | 245 |

Se aplica a las cuatro primeras filas de la tabla con la lluvia de la última
hora en Montflorit: la mediana de la estación de casa y de las tres vecinas
que cuentan para la lluvia (`casa.consens_pluja`, ADR 0085); la primera fila,
la hora en curso, usa $`k = 1`$. Con la mediana, una estación que no marca
(el cero del pluviómetro de casa no es fiable, ADR 0017) o una que marca de
más no deciden solas.

## 6. Cómo se calcula cada hora de la tabla

Para cada hora, en este orden (`casa.py`, `previsio`):

1. **Probabilidad aprendida** con el modelo en uso (apartado 2). Si al
   modelo propio le falta una señal, se usa el del archivo; si tampoco se
   puede, porque falta la lluvia de algún modelo, la fracción de las 40
   simulaciones de ICON-EU-EPS con 0,2 mm o más.
2. **Milímetros**: el máximo de los tres modelos finos,
   $`\text{mm} = \max(\text{AROME HD}, \text{AROME}, \text{ICON-EU})`$; sin
   ninguno, el de Météo-France que Open-Meteo da por defecto. Un solo modelo
   puede fallar: la mañana del 05-10-2026 AROME daba 0,0 mm mientras en
   Montflorit caían más de 20 mm/h. **La regresión da la probabilidad, no los
   milímetros.** Son los milímetros *si llueve* en esa hora (así lo dice la
   leyenda), y el archivo 2024-2026 respalda el máximo como esa cantidad
   condicional (apartado 6 bis, ADR 0103).
3. **Temperatura** corregida (apartado 3), media de los dos extremos de la
   hora.
4. **Persistencia**, en las cuatro primeras horas: si en la última hora han
   caído 0,2 mm o más, la probabilidad y los milímetros suben a los del
   apartado 5, cada uno si es mayor. Estas cifras llevan «*».
5. **Radar**, en las dos primeras horas: la probabilidad sube a
   $`p_{\text{radar}}`$ si es mayor y llega al 20 %; los milímetros suben a
   $`\text{mm}_{\text{radar}}`$ si es mayor, llega a 0,2 mm y el radar cubre al
   menos 30 minutos de la hora. Nunca baja nada. Estas cifras llevan «†».
6. **Lo medido manda**: si casa ha recogido lluvia en los últimos 15
   minutos, la primera hora es «Plou ara» con el 100 %.
7. **Cielo**: la mezcla de las nubes de cuatro modelos; en la primera hora,
   lo observado en el aeropuerto de Sabadell si ve capas de nubes (apartado 8,
   «Qué modelos dan el cielo»).

**Cuántas horas.** Desde la versión 3.40.0 (ADR 0041), la tabla llega a 24
horas como mínimo y hasta las 21 h de mañana. Acaba siempre al final de un
tramo del día, a las 7, las 14 o las 21 h, así que tiene entre 24 y 38 filas:
38 cuando se calcula a las 7 h. Más allá de 24 horas, la antelación del modelo de lluvia y
de la corrección de temperatura vale como un día, porque
$`\min(t/24, 1) = 1`$ (apartado 18). El registro con que se aprende y el riesgo
propio (apartado 11) usan solo las 24 primeras horas.

### 6 bis. La cantidad: lo que dice el archivo (ADR 0103)

La evaluación del 18-10-2026 señaló que el máximo de modelos sobreestima la
lluvia (en octubre, 88 mm previstos a 1 hora por 20 caídos). Se comprobó con
el archivo de 2024-2026 (94.380 horas-estación, 3.622 con lluvia, apartado
2.1), con la probabilidad calculada en semanas que el modelo no había visto:

| A corto plazo | Horas | Medido | Máximo de modelos | Media de modelos |
|---|---:|---:|---:|---:|
| Horas con lluvia (0,2 mm o más) | 1.825 | 3.898 mm | 3.787 mm | 2.334 mm |
| Horas con 50 % o más que llovieron | 727 | 2.252 mm | 2.994 mm | |
| Horas con menos del 20 % que llovieron | 605 | 828 mm | 161 mm | |
| Todas las horas | 47.676 | 3.962 mm | 6.720 mm | 3.826 mm |

**Por hora, si llueve, el máximo no sesga** (2,07 mm por hora frente a 2,14
medidos); la media de los tres modelos se queda un 40 % corta, y una
regresión ridge sobre los modelos reduce el error absoluto pero aplana los
extremos (da 2 mm cuando caen 19). En las horas en que la página dice 50 % o
más, el máximo se pasa un tercio; en las de menos del 20 %, la lluvia que
cae es la que ningún modelo ve y nada la recupera. Un día antes, el máximo
se queda un tercio corto en las horas con lluvia. Por eso **el máximo se
mantiene como cantidad de cada hora**: es la que mejor distingue una hora de
chubasco de una de llovizna y la única que no rebaja la lluvia fuerte.

**El exceso estaba en las sumas.** Sumar los milímetros de todas las horas
de un tramo suma cantidades «si llueve» de horas en las que no va a llover.
Por tramos del día (mañana, tarde y noche) en los que la página ponía el
paraguas (alguna hora con 20 % o más), a corto plazo:

| Total del tramo | Previsto | Medido | Error medio por tramo | Correlación |
|---|---:|---:|---:|---:|
| Suma de todas las horas (hasta la 3.142) | 6.360 mm | 3.644 mm | 10,1 mm | 0,64 |
| Suma de las horas con 20 % o más | 5.838 mm | 3.644 mm | 9,4 mm | 0,64 |
| Suma de las horas con 50 % o más | 4.026 mm | 3.644 mm | 7,5 mm | 0,65 |
| **Esperada: probabilidad por milímetros de cada hora** | **3.796 mm** | 3.644 mm | **6,8 mm** | **0,67** |

Un día antes la esperada da 2.600 mm por 3.440 medidos (error medio 6,6 mm
frente a 9,4 de la suma), corta por la lluvia que los modelos no ven con esa
antelación. Desde la 3.143.0 **el total de cada tramo y el del acierto son
la cantidad esperada**,
$$\text{mm}_{\text{tram}} = \sum_{h} p_h \cdot \text{mm}_h,$$
con $`p_h = 1`$ en la hora en que ya llueve. No se añade un «hasta X mm»: el
máximo de modelos no es un escenario alto (queda por debajo de lo medido en
la mitad de las horas con lluvia a corto plazo y en dos tercios un día antes).
«Si surts» sigue usando para el coche la suma de los máximos en 3 horas
(«fins a X mm»), como escenario prudente frente a los umbrales de Meteocat
(apartado 14).

**Lo que no cambia la estadística.** Los avisos de la AEMET y los planes de
Protección Civil se muestran tal cual, encima de la tabla y en cada hora. Si se adopta el modelo con los avisos (ADR 0097), el aviso
de la hora es una señal más de la probabilidad, con el peso aprendido.

## 7. Cómo se dice en la página

**El cielo de cada hora** sale de la probabilidad (`web/casa.js`, `cel`):
«pluja» desde el 50 %, «possible pluja» desde el 20 %, y por debajo, solo las
nubes. La gráfica pinta además, en turquesa, las horas del 10 al 20 %
(ADR 0096). Antes salía de los milímetros del modelo más lluvioso, y la tabla podía
decir «Pluja feble» con un 2 %. Con los nombres del manual de estilo de
Meteocat (ADR 0043):

- **Nubes**, por la fracción del cielo tapado: serè por debajo del 20 %, poc
  ennuvolat hasta el 45 %, mig ennuvolat hasta el 70 %, molt ennuvolat hasta
  el 85 % y cobert por encima. La fracción es la mezcla de cuatro modelos y,
  en la hora en curso, la que observa el aeropuerto de Sabadell si ve capas
  de nubes (apartado 8, «Qué modelos dan el cielo»). Hasta la 3.80 era la de
  AROME solo. Si la lluvia de la hora llega a 0,2 mm, las
  nubes cuentan al menos como un 50 %, para que una hora con lluvia prevista
  no salga serena. De noche, la luna en lugar del sol.
- **Intensidad de la lluvia**, por los milímetros de la hora: feble,
  moderada desde 6 mm, forta desde 40 y torrencial desde 80. El manual da
  esos valores por media hora; aquí se usan por hora, el doble.
- **Nieve**: moderada desde 2 cm y forta desde 10.

**El resumen de cada tramo** (mañana de 7 a 14, tarde de 14 a 21 y noche de 21
a 7) va en la cabecera de cada desplegable. El cielo es la media de las nubes
de sus horas, o niebla si la hay en más de la mitad. Le siguen la temperatura
mínima y máxima y, solo si alguna hora llega al 20 %, el paraguas con la
probabilidad máxima y la cantidad esperada del tramo (la probabilidad de cada
hora por sus milímetros, apartado 6 bis) si llega a 1 mm. Solo cuando se
dan, y en color ámbar, se añaden tormenta, lluvia forta (40 mm en una hora) o torrencial (80),
rachas de 70 km/h, calor de 36 °C, helada (0 °C o menos) y nieve (0,1 cm o más
en el tramo). Las rachas y el calor son los umbrales amarillos del apartado
11 (ADR 0041).

## 8. Cuándo se usa un modelo nuevo

Cada día, a las 16:00, el servidor completa las horas que falten de la
estación de casa y ejecuta `aprenentatge.py diari`:

1. Vuelve a ajustar los dos modelos con todo lo registrado.
2. **Los comprueba con avance temporal** (ADR 0106; `remostreig.avanc`):
   cada día se predice con el modelo ajustado solo con los días anteriores,
   siete como mínimo, como hará el programa, que se reajusta cada día y se
   aplica a los días siguientes. Hasta la 3.145.1 la comprobación era una
   validación cruzada en cuatro grupos de semanas, que podía ajustar con
   semanas posteriores a la evaluada: útil para la relación estadística, pero
   no reproduce una actualización en el tiempo. El día lo fija la hora
   observada, no el momento en que se hizo la previsión: así todas las
   previsiones de una misma hora se evalúan juntas y ninguna observación se
   usa a la vez para ajustar y comprobar. Un episodio de lluvia que cruza la
   medianoche (horas con lluvia separadas por 6 horas secas o menos) se
   aparta del ajuste del día que evalúa su parte final: si no, el modelo ya
   lo habría visto. Los siete primeros días del registro solo sirven para
   ajustar: el error se mide en los demás, para el candidato y para lo que
   publica la web por igual.
3. Lo compara con **lo que publica la web** con las mismas horas. Para la
   lluvia, el modelo del archivo tal como se usa al publicar: el que lleva
   ECMWF cuando la pasada lo tiene, o el de los avisos si está adoptado
   (apartado 2.2), no los coeficientes de los tres modelos solos, que la web
   no usa en la mitad de las horas (hasta la 3.143.0 el competidor era ese;
   ADR 0104). Para la temperatura, la corrección del año de casa, que es la
   misma función que corrige la tabla. Las variantes de la lluvia (Sant
   Cugat, las vecinas, los avisos) se comparan además con el modelo sin su
   señal ajustado a sus mismas horas, y solo ganan si lo mejoran en la misma
   proporción (apartado 2). El modelo propio en uso no se congela: se
   reajusta cada día con todo lo registrado (punto 5), así que entre dos
   métodos propios la comparación es la de los dos ajustados y comprobados
   en las mismas semanas.
4. **Solo cambia si la mejora es segura, no por un margen fijo** (ADR 0105;
   hasta la 3.144.0, un 5 % menos de error). Es la misma regla para todo el
   programa (`remostreig.py`): se remuestrean los días con reposición 2.000
   veces (*bootstrap*), días enteros porque las horas de un mismo día se
   parecen y no son casos independientes, y en cada remuestreo se compara el
   error del candidato, en los días evaluados, con el del que se usa. El
   candidato gana si se equivoca menos en al menos el 95 % de los
   remuestreos:
   $`\Pr^{*}\!\left(\sum_{d \in D^{*}} E_{\text{nuevo}}(d) < \sum_{d \in D^{*}} E_{\text{actual}}(d)\right) \ge 0\text{,}95`$,
   con $`D^{*}`$ cada remuestreo de días y $`E(d)`$ el error acumulado del
   día. Una mejora grande que depende de un solo día no es segura; una
   pequeña y constante sí. El 95 % no es la probabilidad de acertar en el
   futuro: dice que con estos datos la ventaja no es azar. Un método nuevo se
   propone, se comunica con las cifras y se aplica al día siguiente, salvo
   que se pare antes (apartado 19).
5. Si el método no cambia, los pesos se ponen al día con los datos nuevos.
6. Si un modelo propio deja de mejorar, se propone volver al anterior, de la
   misma manera.

### Qué radar se usa

El mismo día se comparan también los dos radares (`radar_fonts.py`, ADR
0026). En cada pasada se apunta la probabilidad que daba cada uno para casa,
$`p_M`$ (Meteocat) y $`p_R`$ (RainViewer), con su última imagen y el mismo
movimiento, y si llovía en ese momento en el barrio ($`o = 1`$ u $`o = 0`$),
con la regla única de la lluvia observada (apartado 2.2, ADR 0102): llueve
si lo marca la estación de casa o dos vecinas que cuentan; seco si casa y
las vecinas que confirman marcan cero; si no (una sola vecina, sin vecinas,
o llovizna que solo ven los dos radares), no se sabe y la pasada no cuenta.
Hasta el 18-10-2026 solo contaba el pluviómetro de casa. Para cada hora prevista entre 10 y 60 minutos después de la
pasada, con una observación a menos de 4 minutos, se calcula la puntuación de
Brier de los últimos 30 días:

```math
B_M = \frac{1}{n}\sum_{i=1}^{n} (p_{M,i} - o_i)^2, \qquad
B_R = \frac{1}{n}\sum_{i=1}^{n} (p_{R,i} - o_i)^2
```

Cuanto más baja, mejor. Con al menos 30 casos con lluvia en 3 días
distintos, se cambia de radar si el otro cumple la regla común del apartado
8: se equivoca menos en al menos el 95 % de los remuestreos por días (hasta
la 3.144.0, un 5 % menos de error). Con RainViewer como
preferido, su imagen se usa siempre que no sea más vieja que la de Meteocat
(hasta la 3.128.0, solo si era 10 minutos más nueva); con Meteocat, la de
RainViewer solo si es más de 15 minutos más nueva.

### Qué modelos dan el cielo

El cielo de cada hora es la media ponderada de las nubes de cuatro modelos,
AROME, ICON-EU, ECMWF IFS y GFS (`nuvols.py`, ADR 0088). Con $`n_m`$ el
cielo tapado que da el modelo $`m`$, en %, y $`w_m`$ su peso:

```math
n = \frac{\sum_m w_m \, n_m}{\sum_m w_m}
```

contando solo los modelos que tienen dato. Se empieza con los cuatro al 25 %.
En la hora en curso manda lo observado si el último informe del aeropuerto de
Sabadell (METAR), de 45 minutos como mucho, da capas de nubes.

**Lo observado.** El METAR dice cuánto tapa cada capa en octavos. Se toma la
capa que más tapa, en el punto medio de su intervalo: FEW (1-2 octavos) 19 %,
SCT (3-4) 44 %, BKN (5-7) 75 % y OVC (8) 100 %. El de una hora es la media de
sus dos informes (y media y en punto). Si no da capas (CAVOK, NSC o NCD),
solo se sabe que no hay nubes por debajo de unos 1.500 m: puede haber nubes
más altas.

**Qué se compara.** Cada día se toman todas las previsiones apuntadas para
las horas observadas de los últimos 30 días. En las horas con capas, la mezcla
$`n`$ se compara con lo observado $`o`$; en las horas sin capas, las nubes
bajas de la mezcla, $`b`$, con cero, porque es lo único que se sabe. Para
leerlo se da el error medio, en puntos de cielo tapado:

```math
E(w) = \frac{1}{N}\Big(\sum_{\text{con capas}} |n - o| + \sum_{\text{sin capas}} b\Big)
```

**Cómo se ajustan los pesos.** Con la combinación de previsiones de Granger y
Ramanathan (1984): una regresión de mínimos cuadrados de lo observado sobre
lo que dio cada modelo, sin término independiente y con los pesos positivos y
sumando 1. Con $`x_{i,m}`$ lo que dio el modelo $`m`$ para el caso $`i`$ y
$`y_i`$ lo observado:

```math
\hat w = \arg\min_{w} \sum_{i} \Big(y_i - \sum_m w_m x_{i,m}\Big)^2
\quad \text{con} \quad w_m \ge 0, \quad \sum_m w_m = 1
```

La solución es exacta: el mínimo está en el interior de alguna cara del
conjunto de pesos posibles (cada cara es un subconjunto de modelos). En cada
una se resuelve el sistema de Lagrange con la suma igual a 1, y de las
soluciones con todos los pesos positivos se queda la de menor error. Con
cuatro modelos son 15 sistemas.

**Cómo se comprueban.** Como la lluvia y la temperatura, con avance
temporal (apartado 8, ADR 0106): cada día se predice con los pesos ajustados
con los días anteriores, siete como mínimo (hasta la 3.145.1, validación
cruzada en cuatro grupos de semanas). Los pesos de ahora, fijos, se aplican a
las mismas horas.

**Cuándo se cambian.** Solo si la mejora es segura, no por un margen fijo. Se
remuestrean los días con reposición 2.000 veces (*bootstrap*); los días
enteros, porque las horas de un mismo día se parecen y no son casos
independientes. En cada remuestreo se compara el error cuadrático medio de
los pesos ajustados, en los días evaluados, con el de los de ahora. Si los
ajustados se equivocan menos en al menos el 95 % de los remuestreos, y hay al
menos 300 horas observadas en 14 días distintos, pasan a usarse los ajustados
con todos los datos. Se avisa a Juanjo, y también si pasa más de un día sin
que llegue ningún METAR.

**Con el archivo.** Del 27-09 al 13-10-2026 (378 horas en 16 días, 246 con
capas), el error medio fue: AROME 28,8 puntos, ICON-EU 29,7, ECMWF 27,0 y GFS
29,3; la media de los cuatro, 25,8. Los pesos ajustados (AROME 0,23, ICON-EU
0,20, ECMWF 0,30, GFS 0,27) se equivocan 26,3 en las semanas no vistas y ganan
a la media solo en el 0,4 % de los remuestreos: con estos datos, afinar los
pesos no mejora nada y se usan todos iguales. Frente a AROME solo, en cambio,
ganan en el 100 %: mezclar sí es claramente mejor. AROME dio «serè» 12 horas
en que Sabadell veía la mitad del cielo tapado o más; la media, ninguna.

## 9. Cuándo para la lluvia

Cuando ya llueve, la tarjeta de ahora dice a qué hora pararía según el radar,
con la marca «en entrenament» (`fi_pluja.py`, ADR 0049). Con la serie $`p(t)`$
del apartado 4, el final previsto es el primer paso $`t_k`$, desde ahora o desde
que llegue la lluvia, en que la probabilidad queda por debajo de un umbral
$`u`$ durante $`s`$ pasos seguidos de 5 minutos:

```math
t_{\text{fi}} = \min\left\{\, t_k \ge t_0 :\ p(t_{k+m}) < u \ \text{para}\ m = 0, \dots, s-1 \,\right\}
```

Si no pasa en las dos horas del radar, «no s'acaba en 2 hores». La regla de
partida es $`u = 0\text{,}2`$ y $`s = 3`$, es decir, menos del 20 % durante 15
minutos.

**Qué es la verdad.** La lluvia del barrio cada 5 minutos (ADR 0102): la de
casa y la de las vecinas, con la regla única del apartado 2.2 aplicada a
cada tramo de 5 minutos desde 0,1 mm (llueve si lo marca casa o dos vecinas
que cuentan; seco si casa y las que confirman marcan cero; si no, no se sabe
y el tramo ni corta ni alarga). Un episodio son los tramos con lluvia
separados por menos de 30 minutos secos, y su final, el último tramo con
lluvia. Hasta el 18-10-2026 solo contaba el pluviómetro de casa, que no
marca la lluvia débil y daba finales antes de tiempo. Se juzgan las pasadas registradas mientras llovía,
con el radar que usaba la página. El error de una pasada es
$`\lvert t_{\text{fi}} - t_{\text{real}} \rvert`$ en minutos. Si la regla no da
final, el error es cero cuando el final real cae más allá del horizonte del
radar y, si no, lo que faltaba hasta el horizonte. Un acierto es un error de
15 minutos o menos.

**Cómo aprende.** Cada día se prueban las nueve combinaciones de
$`u \in \{0\text{,}1;\ 0\text{,}2;\ 0\text{,}3\}`$ y $`s \in \{2, 3, 4\}`$ con todos los
episodios registrados. Como con pocos episodios y nueve combinaciones la
mejor puede ganar por azar, el error que decide no es el de la mejor
combinación en los episodios con que se eligió, sino el de *elegir la
mejor*: para cada episodio $`j`$ se toma la combinación que menos se equivoca
en los demás y se mide solo en $`j`$ (validación dejando un episodio fuera),

```math
E_{\text{val}} = \frac{1}{N} \sum_{j} \sum_{i \in j} \left| t_{\text{fi}}^{(u_j, s_j)}(i) - t_{\text{real}}(i) \right|,
\qquad (u_j, s_j) = \arg\min_{(u, s)} E_{-j}(u, s),
```

donde $`i`$ recorre las pasadas del episodio $`j`$, $`N`$ es el total de pasadas y
$`E_{-j}`$ es el error medio sin el episodio $`j`$. Con tres episodios o más, si
la regla elegida se equivoca menos que la regla en uso (que, al estar fija,
se mide sin sesgo en todos los episodios) en al menos el 95 % de los
remuestreos por episodios, los mismos casos con las dos reglas (la regla
común del apartado 8, con el episodio como bloque; hasta la 3.144.0, un 5 %
menos de error), se propone
la combinación mejor con todos los episodios, se comunica con las cifras y
se aplica al día siguiente, salvo que se pare antes, como el aprendizaje de
la lluvia y la temperatura (apartado 8). Hasta el 09-10-2026 la regla se
elegía y se medía con los mismos episodios y el cambio se aplicaba el mismo
día (ADR 0049). Con cinco episodios, el resultado se comunica una vez, para
decidir si se sigue mostrando «en entrenament».

**Limitación conocida.** Con pocos episodios, $`E_{\text{val}}`$ sigue
siendo una cifra con mucha incertidumbre, y el remuestreo de tres o cinco
episodios es grueso: con tres, basta ganar en los tres; por eso la propuesta
espera un día y se puede parar.

## 10. Aviso antes de llover

Tras cada pasada se mira cuántos minutos faltan para la llegada que da el
radar, el primer paso con $`p(t) \ge 0\text{,}5`$ (`pluja_arriba.py`, ADR 0022). Si
faltan 21 o menos (15 minutos más el intervalo de 6 del modo aviso) y aún no
llueve en el barrio según la web (el estado único de la lluvia: casa o una
vecina que cuenta, ADR 0101 y 0102), se avisa a los suscriptores (ADR 0048). La
intensidad que se anuncia es el máximo de $`\hat R`$ en los 30 minutos
siguientes a la llegada: feble por debajo de 1 mm/h, moderada desde 1 y forta
desde 4.

Los avisos van por episodios: uno empieza cuando el radar anuncia la lluvia o
cuando empieza a llover, y acaba tras 60 minutos sin lluvia medida ni
anunciada. En cada episodio hay un aviso como mucho. Al acabar se apunta qué
pasó: acierto si llovió en los 45 minutos siguientes al aviso, «avís sense
pluja» si no, y «pluja sense avís» si llovió sin aviso.

## 11. Situaciones de peligro

Lo medido en las estaciones y la previsión de las 24 primeras horas se
comparan con los umbrales bajo y alto de los avisos de situación
meteorológica de peligro de Meteocat para Cerdanyola y el Vallès Occidental
(`riscos.py`, `RISC_LLINDARS` de `config.py`, ADR 0018; hasta el 16-10-2026,
los de la AEMET para el Prelitoral). Hay que pasar el umbral:

| Fenómeno | Amarillo (umbral bajo) | Naranja (umbral alto) | De dónde |
|---|---|---|---|
| Lluvia en 30 minutos | más de 20 mm | más de 40 mm | medida |
| Lluvia en 3 horas | más de 60 mm | más de 90 mm | medida y prevista |
| Lluvia en 24 horas | más de 100 mm | más de 200 mm | prevista |
| Racha | más de 72 km/h | más de 108 km/h | prevista |
| Calor | más de 36,8 °C | más de 38,8 °C | medida y prevista |
| Frío | menos de −1,6 °C | menos de −3,6 °C | medida y prevista, junto a la riera |
| Nieve en 24 horas | cualquier espesor | más de 5 cm | prevista |

Los de temperatura son los del municipio (percentiles 98 y 2 de los últimos
15 años, y dos grados más allá para el alto). El rojo de Meteocat depende
también de la probabilidad, que la web no tiene para estos fenómenos: no hay
rojo propio. La media hora no se puede prever con modelos de horas enteras;
la lluvia de 3 y de 24 horas es la ventana de horas seguidas que más acumula.
Para cada fenómeno se da el peor valor y el tramo de horas seguidas en que
ocurre. Un riesgo se da por acabado tras 3 horas sin verlo, para que el
vaivén de los modelos entre pasadas no repita el aviso. No sustituye a los
avisos de la AEMET, que se muestran aparte.

## 12. La riera de Sant Cugat

La riera nace en Collserola, en la zona de Les Planes, cruza Sant Cugat y
pasa por Montflorit, donde se desbordó el 29-09-2026 y el 04-10-2026 con el
agua dentro de las casas. Su cuenca es pequeña (unos 50 km²) y responde
enseguida: las tres veces conocidas se desbordó al acabar las tres horas más
lluviosas (`riera.py`, ADR 0027). Es la parte más delicada de la web, y por
eso se explica entera: qué se mide, cómo se calcula el índice, de dónde
salen los umbrales, qué habría avisado en el pasado y cómo llega el aviso.

### 12.1 Qué se mide

La Agència Catalana de l'Aigua no mide el nivel de la riera: su aforo más
cercano está en el Ripoll, en Montcada, aguas abajo. Solo queda la lluvia.
Decide la de la estación de Meteocat de Sant Cugat (CAR, código XV), en
medio de la cuenca, por medias horas y unos 30 minutos por detrás, leída en
la web de meteo.cat o, si falla, en el portal de datos abiertos de la
Generalitat. Se guarda y se dice en el aviso, pero no decide, la del
Observatori Fabra (D5), en la cresta de Collserola junto a donde nace la
riera: aún no hay historial para saber qué umbral le corresponde. A lo medido se suma lo que el radar lleva hacia
delante sobre el centro de la cuenca (apartado 4), que cubre también la
media hora que la estación va por detrás.

Desde el 18-10-2026 se mira también la lluvia de seis estaciones
particulares de Sant Cugat de la red de Weather Underground, del centro y de
la parte alta de la cuenca (Valldoreix y el oeste), que dan un dato cada 5
minutos casi sin retraso (`C.RIERA_VEINES`). Se eligieron porque midieron con
coherencia los cuatro episodios conocidos; otras cuatro cercanas fallaban
(siempre a cero o un día sí y otro no). Se usa su mediana, con al menos tres
estaciones con dato de los últimos 20 minutos, para que una estropeada no
decida. Solo se consultan cuando llueve en Sant Cugat, el radar ve lluvia
sobre la cuenca en la hora siguiente o hay un episodio abierto, con un tope
de 500 consultas al día para no quitar cuota a la web.

### 12.2 El índice

El índice es la lluvia de tres horas más alta que se alcanzará en la hora
siguiente, y la de seis horas del mismo momento:

```math
I_3(k) = M_{3-k} + P_k, \qquad I_6(k) = M_{6-k} + P_k, \qquad k \in \{0;\ 0\text{,}5;\ 1\}
```

donde $`M_h`$ es la lluvia medida en las últimas $`h`$ horas y $`P_k`$ la prevista
por el radar para las $`k`$ horas siguientes, contando también el hueco entre
la última media hora medida y la imagen del radar. Para cada momento $`k`$ se
aplica la tabla a la pareja $`(I_3(k), I_6(k))`$ y el nivel de la pasada es
el más alto que alcanza algún momento; el índice que se publica es el de
ese momento (entre varios, el de más lluvia de 3 horas). Hasta el
09-10-2026 se tomaban el máximo de $`I_3`$ y el máximo de $`I_6`$ por separado,
de momentos distintos, y 50 mm sobre suelo seco ahora con 60 en 6 horas
una hora después daban peligro sin que ningún momento cumpliera las dos
condiciones (ADR 0057).

| Nivel | Condición, en un mismo momento $`k`$ |
|---|---|
| Se registra el episodio | $`I_3 \ge 20`$ mm |
| Atención: aviso | $`I_3 \ge 35`$ mm |
| Peligro: segundo aviso | $`I_3 \ge 50`$ mm y $`I_6 \ge 60`$ mm |

Cada nivel se avisa una sola vez por episodio, y un episodio acaba tras 3
horas por debajo de 20 mm; al acabar se apunta en el registro con sus
máximos. Si a la ventana de 3 horas le falta más de una media hora medida,
o a la de 6 más de dos, el índice se da por incompleto: un hueco cuenta
como cero y no se puede decir que el riesgo haya bajado.

El mismo índice se calcula con la mediana de las estaciones particulares
(lo medido hasta ahora más el radar de la hora siguiente), y el nivel es el
más alto de las dos fuentes: las estaciones solo pueden adelantar o subir un
aviso, nunca quitarlo. El aviso dice de dónde sale la cifra.

| Episodio | ¿Se desbordó? | Meteocat, 3 h | Mediana de las 6, 3 h / 6 h | Atención: Meteocat → estaciones | Peligro: Meteocat → estaciones |
|---|---|---|---|---|---|
| 29-04-2024 | sí | 53 | 85 / 112 (4 estaciones) | | |
| 13-09-2025 | no | 52 | 65 / 66 | 17:00 → 16:15 | no → 17:25 |
| 29-09-2026 | sí | 67 | 93 / 93 | 12:00 → 11:20 | 12:30 → 11:35 |
| 03/04-10-2026 | sí | 67 | 66 / 67 | 00:30 → 23:45 | 02:30 → 01:40 |

Las horas son las de lo medido, sin el radar, con el retraso de 30 minutos de
Meteocat. Con las estaciones, los avisos de los dos desbordamientos de 2026
habrían llegado de 40 a 55 minutos antes; a cambio, el 13-09-2025, sobre
suelo seco, habrían dado un peligro de más. La mediana no separa mejor que
Meteocat los episodios que se desbordan: lo que aporta es tiempo. Con cuatro
casos no se puede calibrar otro umbral; se usan los mismos y se apunta cada
pasada con las dos fuentes (`registre/riera-veines.csv`) para ajustarlos.

### 12.3 De dónde salen los umbrales

De cuatro casos, con la lluvia de Sant Cugat (XV) y del Fabra (D5) del
portal de datos abiertos de la Generalitat (conjunto `nzvn-apee`), por
medias horas:

| Día | Qué pasó | XV, 3 h | XV, 6 h | D5, 3 h | Fin de las 3 h más lluviosas |
|---|---|---:|---:|---:|---|
| 29-04-2024 | El agua llegó a la puerta de las casas | 53 | 75 | 22 | 20:30 |
| 29-09-2026 | Entró en las casas | 67 | 67 | 76 | 12:30 |
| 04-10-2026 | Entró en las casas, entre la 1 y las 2 | 67 | 104 | 43 | 02:00 |
| 13-09-2025 | **No se desbordó** | 52 | 52 | 17 | 17:30 |

Lo que separa el 13-09-2025 de los desbordamientos es la lluvia de antes:
fue un chaparrón de 3 horas sobre suelo seco, con poca lluvia en Collserola
(18 mm en 24 horas en el Fabra, frente a 64 o más), y los tres
desbordamientos tenían 67 mm o más en 6 horas. De ahí la segunda condición
del peligro. Del 11-05-2025 (48 mm en 3 horas) y del 06-11-2025 (38) no
hay fotos; con la regla, ninguno de los dos daría peligro. En los tres
desbordamientos el agua llegó al acabar las 3 horas más lluviosas.

### 12.4 Qué habría avisado desde 2013

Con la lluvia medida cada media hora desde 2013, con los 30 minutos de
retraso de la tabla de meteo.cat y sin radar, porque no hay archivo de
imágenes, la regla da 51 episodios de 20 mm o más, 13 avisos de atención y
5 de peligro en 13 años: el 28-09-2014, el 15-11-2018, el 29-04-2024, el
29-09-2026 y el 04-10-2026. De los dos primeros no se sabe si hubo
desbordamiento. Con solo la condición de 3 horas habrían sido 7.

El margen, en los tres casos conocidos: la atención habría llegado a las
20:00 el 29-04-2024 (30 minutos antes de que el agua llegara a las
puertas), a las 12:00 el 29-09-2026 (con el desbordamiento ya en marcha) y a
las 0:30 el 04-10-2026 (de 30 a 90 minutos antes); el peligro, siempre
después. Con la hora siguiente conocida, que es lo que aporta el radar
cuando acierta, la atención habría llegado a las 18:30, a las 10:30 y a las
23:00: de 1 a 3 horas antes. El radar real queda entre los dos extremos.

### 12.5 Cómo llega el aviso

El aviso de atención y el de peligro van a todo el mundo igual: al canal de
Telegram, a cada persona que lo ha elegido en el bot y a las notificaciones
del navegador (ADR 0034 y 0048), con la lluvia de Sant Cugat y del Fabra y
lo que el radar prevé para la hora siguiente. Al cerrarse el
episodio llega un solo mensaje de final (ADR 0027). La web pública no
muestra el índice: solo los avisos. Los textos dicen que el aviso está en
pruebas y no es oficial, y que mandan siempre las indicaciones de Protección
Civil.

**Limitación conocida.** Los umbrales son una hipótesis basada en cuatro
casos. Cada episodio se guarda con sus máximos para ajustarlos con lo que
pase; ese ajuste no es automático. Hasta el 18-10-2026 no se ha visto
ningún aviso real.

**El desenlace lo confirma una persona.** Nada mide el nivel de la riera:
al cerrarse un episodio con aviso, el programa pregunta a Juanjo por
Telegram, con botones, si se ha desbordado, y la respuesta queda en la
columna `desbordament` del episodio (`riera.csv`). Con esos desenlaces se
podrán contar aciertos, falsas alarmas y minutos de anticipación.

### 12.6 La previsión de crecida (ADR 0107)

La página «Riera» dice, además de lo que pasa ahora, lo que puede pasar en
las próximas 24 horas según los modelos, **como previsión y no como aviso**:
no sale por ningún canal, solo en su página, con un punto ámbar en la pestaña
mientras no se haya visto. Cada pasada pide a Open-Meteo la lluvia por horas
de AROME HD, AROME, ICON-EU y ECMWF en el centro de la cuenca
(`config.CONCA_RIERA`) y calcula, para cada modelo $`m`$, su lluvia de 3 horas
más alta en el horizonte:

```math
P_3 = \max_{m}\ \max_{k} \sum_{i=k-2}^{k} p_{m,i}, \qquad P_6 \text{ igual con 6 horas,}
```

y «risc de crescuda possible» si $`P_3 \ge 20`$ mm (`RIERA_PREVISIO_MM`).
Manda el modelo que más da porque es el único que no rebaja la lluvia fuerte
(apartado 6 bis); al lado va la media de los modelos en la misma ventana, el
modelo que lo da y las horas, y la lluvia de las últimas 24 horas en Sant
Cugat, que es lo que distingue los casos (12.3). Cada pasada se apunta en
`registre/riera-previsio.csv` (`riera.py previsio-resum` compara con lo que
después midió Sant Cugat).

**Con el archivo 2024-2026** (`calibracio/dades/prev_casa.csv` y
`ecmwf/`, las previsiones pasadas de los modelos en Montflorit, última pasada
y pasada del día anterior; `obs_XV.csv`, Sant Cugat por medias horas; 1.008
días, 7 con 35 mm o más en 3 horas):

| $`P_3`$ previsto | Días con señal | Con 35 mm reales | Se escapan | Falsas |
|---|---|---|---|---|
| 15 mm | 34 | 4 | 3 | 30 |
| **20 mm** | **21** | **4** | **3** | **17** |
| 25 mm | 16 | 4 | 3 | 12 |
| 35 mm | 5 | 3 | 4 | 2 |

Con la pasada del día anterior, a 20 mm: 13 días con señal, 3 reales. En los
episodios conocidos (última pasada, $`P_3`$ previsto / real): 29-04-2024,
30 / 53 (desbordamiento); 13-09-2025, 52 / 47 (no se desbordó);
29-09-2026, 13 / 66 (desbordamiento, invisible para los modelos);
03-10-2026, 111 / 37; 04-10-2026, 88 / 67 (desbordamiento). De los tres
desbordamientos, la señal de 20 mm habría salido en dos (abril de 2024 y
octubre de 2026) y no en el 29 de septiembre de 2026, el más grave. Por eso
es una previsión que se muestra y no un aviso que se envía; el umbral se
revisará con el registro propio.

## 13. Cuando los modelos no ven la lluvia

En cada pasada se suman la lluvia medida en casa en las tres últimas horas
completas, $`M`$, y la que daban los modelos en esas horas, $`P`$ (el
máximo de los tres, hora a hora). Si

```math
M \ge 3 \ \text{mm} \quad \text{y} \quad M > 3P + 1,
```

la página avisa de que los modelos no ven esta lluvia: las primeras horas de
la tabla parten de lo que mide la estación (apartados 5 y 6), y para el resto
conviene hacer más caso de los avisos (`casa.py`, `comprobacion_modelos`).

## 14. Si surts

«Si surts» dice, para una hora de salida y otra de vuelta, cómo irá cada
medio de transporte, qué ropa conviene y algunos consejos (ADR 0029). Los
umbrales están en `web/sortir.js`.

### La lluvia en moto y en bici

Desde el 08-10-2026 (ADR 0047), en moto y en bici decide **solo la
probabilidad** $`p`$ de cada hora, la de la tabla, que ya reúne los modelos, el
conjunto de simulaciones, el radar, las estaciones y lo aprendido. Para la
hora de ida y la de vuelta:

```math
\text{nivel} =
\begin{cases}
\text{millor no} & \text{si } p \ge 0\text{,}40 \text{ o llueve ahora} \\
\text{compte} & \text{si } p \ge 0\text{,}10 \text{ o hay aviso de la AEMET} \\
\text{bé} & \text{en otro caso}
\end{cases}
```

El nivel del viaje es el peor de las dos horas. Sin probabilidad, se usa la
lluvia del modelo más lluvioso: 1 mm, «millor no»; 0,2 mm, «compte».

Antes mandaba también la lluvia del modelo más lluvioso (1 mm, «millor no»;
0,2 mm, «compte») junto a una probabilidad del 50 % y del 20 %, y un aviso de
la AEMET solo daba «millor no». El 08-10-2026 eso desaconsejó la moto a las
10 y a las 17 h por el aviso amarillo y por 1,7 mm de ICON-EU (los dos AROME
daban 0 y la probabilidad, un 25 %), y no llovió.

**Comprobación con el archivo.** `calibracio/regla_moto.py` aplica las dos
reglas a cada hora del archivo (01-01-2024 a 05-10-2026), con la probabilidad
del modelo del archivo ajustado sin la semana que se juzga, y a un viaje de
cada día a las 10 y a las 17 h. La verdad es 0,2 mm o más en Sabadell o Sant
Cugat. Viaje con la previsión a corto plazo (992 días, 80 con lluvia):

| Regla | Días secos con «no» | Días secos con «compte» | Días de lluvia con «bé» | con «compte» | con «no» |
|---|---|---|---|---|---|
| Antes (50 % o 1 mm; 20 % o 0,2 mm) | 25 | 53 | 14 | 22 | 44 |
| Solo la probabilidad, 50 % y 20 % | 8 | 34 | 23 | 27 | 30 |
| **Solo la probabilidad, 40 % y 10 %** | **11** | 72 | **13** | 26 | 41 |

Con la previsión de un día antes (971 días, 78 con lluvia), la elegida da 14
días secos con «no» (antes, 21) y 17 de lluvia con «bé» (antes, 22). Quitar
los milímetros con los umbrales de siempre reducía las falsas alarmas, pero
dejaba sin aviso nueve días más de lluvia: por eso se bajaron los umbrales.
El precio es recomendar el impermeable unos 19 días secos más de cada 900. El
archivo no tiene avisos de la AEMET, radar ni conjunto de simulaciones: esas
partes no están comprobadas.

**Comprobación con lo que pasa** (desde el 10-10-2026, de todos los medios:
apartado siguiente).

### Los umbrales de lluvia, aprendidos (ADR 0069)

Desde el 10-10-2026 los umbrales de lluvia son los mismos para todos los
medios y se aprenden. Qué tiene que cumplir cada nivel: con «pluja probable»
tiene que llover al menos 2 de cada 3 veces; con «bé», como mucho 1 de cada
100 y nunca más de 1 de cada 10 en ninguna franja de 5 puntos. Con la
proporción $`\hat f = k/n`$ de horas con lluvia, se exige la cota de Wilson

```math
\frac{\hat f + \frac{z^2}{2n} \mp z\sqrt{\frac{\hat f(1-\hat f)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \qquad z = 1\text{,}28,
```

la baja para «pluja probable» (≥ 2/3) y la alta para «bé» (≤ 1/100). Dos
juegos: para dentro de 3 horas o menos y para más tarde. De partida, los del
archivo con la lluvia de la estación de casa (40 % y 10 %; 60 % y 10 %); cada
día, con 30 horas de lluvia o más en `sortir.csv` por banda, se buscan los
que cumplen, se proponen y se aplican al día siguiente.

### Los demás medios

- **Coche**: «millor no» con 40 mm o más en una hora y «compte» con 20 (los
  umbrales naranja y amarillo de la AEMET); con lluvia probable (el umbral
  «pluja» aprendido, lluvia ahora o aviso de la AEMET), también «compte».
- **A pie**: «compte» (paraguas) con el umbral «risc» aprendido, lluvia
  ahora o aviso de la AEMET por lluvia o tormentas.
- **Viento y frío**, como pares [«compte», «millor no»]: rachas en bici de
  40 y 50 km/h, en moto de 50 y 70, en coche «compte» desde 90 y a pie
  «millor no» desde 70; frío en bici y en moto de 3 y 1 °C, y en coche
  «compte» desde 1 °C.
- **Transporte público**: el estado de los trenes de Cerdanyola en tiempo
  real, sin umbrales meteorológicos.

**Comprobación con lo que pasa, de todos los medios** (ADR 0047 y 0068).
Las reglas son comunes: si fallan en un medio, fallan en los demás. Cada día
se apunta en `sortir.csv`, de cada hora pasada de 7 a 22 h, lo que mostró la
página con dos antelaciones (al salir, la previsión más reciente de 1 a 3
horas antes; la vuelta decidida por la mañana, de 6 a 10 horas antes): la
probabilidad, los milímetros, la lluvia ahora, el aviso de la AEMET, la
racha y la temperatura; y lo que se midió: la lluvia (con las mismas reglas
de hora seca del aprendizaje), la racha máxima de la hora en Sant Cugat y la
temperatura de casa. El resumen juzga con las reglas de ahora: de cada
medio (a pie, bici o patinete, moto y coche) y de cada regla (lluvia,
rachas y frío), cuántas horas dio cada nivel y en cuántas pasó; la moto,
también con su regla de lluvia de antes. Llega una vez a los 28 días; las
pruebas comprueban que el nivel de cada hora es el mismo que da la página.

### La ropa

La ropa sale del frío que se nota. Con 10 °C o menos y una velocidad
$`v \ge 5`$ km/h, se usa el índice de enfriamiento por viento de Environment
Canada:

```math
T_s = 13\text{,}12 + 0\text{,}6215\,T - 11\text{,}37\,v^{0\text{,}16} + 0\text{,}3965\,T\,v^{0\text{,}16}
```

con $`T`$ en °C y $`v`$ en km/h. La velocidad es la del medio (bici 18 km/h,
moto 45) y, a pie o hasta el coche o la estación, el viento previsto. La
prenda sale de $`T_s`$ por tramos. Además se avisa de un cambio de temperatura
de 6 °C o más entre la ida y la vuelta, del calor desde 32 °C y de la
protección solar con un índice ultravioleta (UV) de 3 o más.

## 15. La calidad del aire

El índice sale del modelo europeo del servicio de vigilancia atmosférica de
Copernicus (CAMS, *Copernicus Atmosphere Monitoring Service*), que sirve
Open-Meteo en celdas de 0,1°, unos 11 × 8 km aquí (`aire.py`, ADR 0054). La
celda de Montflorit tiene el centro en Bellaterra: **es una estimación de
zona, no una medida del barrio**.

Cada día se corrige con las estaciones de la red de vigilancia de la
contaminación atmosférica de la Generalitat (XVPCA) de Barberà, Sant Cugat y
Montcada. Para cada contaminante $`c`$, con las horas de los últimos 30 días
que tienen a la vez modelo y medida:

```math
f_c = \frac{\sum_t \bar m_{c,t}}{\sum_t \hat m_{c,t}}
```

donde $`\bar m_{c,t}`$ es la media de las estaciones que lo miden en la hora
$`t`$ y $`\hat m_{c,t}`$ lo que daba el modelo. Solo se corrige con 72 horas
emparejadas o más y si lo miden al menos dos estaciones. Las partículas de
menos de 10 micras (PM10) solo las mide Montcada, junto a la cementera, y
su factor diría más de Montcada que de Montflorit. El 09-10-2026 se corregían el dióxido de
nitrógeno (NO₂), ×0,70, y el ozono, ×0,71, con 725 horas.

Las concentraciones del modelo se multiplican por $`f_c`$ y el índice europeo
de calidad del aire (EAQI, *European Air Quality Index*) se recalcula
interpolando dentro del tramo de cada contaminante, con la tabla que publica
Open-Meteo; el total es el del peor contaminante.

**Solo si acierta más.** Antes de aplicar $`f_c`$ se comprueba en días que no
sirvieron para calcularlo: para cada día $`d`$ de los 30, el factor se calcula
con los demás días, $`f_c^{(-d)}`$, y se aplica a las horas de $`d`$. El error
medio del modelo corregido y el del modelo sin corregir, en µg/m³, son

```math
E_{\text{corr}} = \frac{1}{N} \sum_{d} \sum_{t \in d} \left| f_c^{(-d)} \hat m_{c,t} - \bar m_{c,t} \right|,
\qquad
E_{\text{cru}} = \frac{1}{N} \sum_{t} \left| \hat m_{c,t} - \bar m_{c,t} \right|.
```

El factor se aplica solo si el modelo corregido se equivoca menos que el
sin corregir en al menos el 95 % de los remuestreos por días (la regla común
del apartado 8; hasta la 3.144.0, $`E_{\text{corr}} < 0\text{,}95\, E_{\text{cru}}`$);
si no, ese contaminante se muestra tal como lo da el modelo, y la
corrección descartada queda guardada con sus dos errores y su seguridad
(`aire-correccio.json`). Hasta el 09-10-2026 el factor se aplicaba sin esta
comprobación (ADR 0054).

**Limitación conocida.** Es un factor único para todas las horas del día:
no corrige un sesgo que cambie entre el día y la noche. Las medidas de la
red se publican con 7 u 8 horas de retraso, por eso no se muestran en la
página.

## 16. El viento de ahora con las vecinas

**En prueba: la página sigue mostrando el viento de Sant Cugat** (ADR 0064).
Las cuatro estaciones vecinas de Weather Underground están a menos de un
kilómetro y dan una lectura cada cinco minutos, pero sus anemómetros no están
a 10 m ni en campo abierto: marcan menos viento que Meteocat. El programa
aprende cada día cuánto menos.

Para cada vecina $`i`$, con las medias horas en que hay dato suyo $`x_t`$ y de
Sant Cugat $`y_t`$, el factor es el de mínimos cuadrados por el origen y el
error, el cuadrático medio:

```math
f_i = \frac{\sum_t x_t\,y_t}{\sum_t x_t^2}, \qquad e_i = \frac{1}{n}\sum_t (f_i\,x_t - y_t)^2
```

Una vecina cuenta si tiene 96 medias horas (dos días), una correlación con
Sant Cugat de 0,6 o más y como mucho un 25 % de medias horas a cero cuando en
Sant Cugat sopla (5 km/h o más). La estimación es la media de las que cuentan
y tienen lecturas en la última media hora, cada una con un peso inverso a su
error:

```math
\hat v = \frac{\sum_i f_i\,x_i / e_i}{\sum_i 1 / e_i}
```

La racha se estima igual, con las rachas. Del 3 al 10-10-2026 contaban el
Puig de la Guàrdia ($`f = 1\text{,}29`$, correlación 0,82) y la de 600 m al nordeste
($`f = 1\text{,}87`$, 0,75); las otras dos marcaban cero en el 36 % y el 68 % de las
medias horas con viento.

**Cómo se comprueba.** Se deja fuera cada día: se aprende con los demás y se
mide el error medio absoluto contra Sant Cugat de la estimación, de Sabadell
(otra estación oficial, a 5 km) y de Sant Cugat media hora antes, que es lo
que enseña la página, porque su dato llega con retraso. En la primera semana,
de calma, fueron 1,6, 3,3 y 1,0 km/h. Cuando haya 12 medias horas con 15 km/h
o más en Sant Cugat, el programa envía las cifras a Juanjo una vez, y él
decide si la página pasa a usar la estimación.

## 17. El sol sobre el termómetro de casa

Las mañanas de sol, un rayo llega al termómetro de la estación de casa: en
media hora sube de 3 a 5 °C y luego baja, mientras las vecinas suben poco a
poco (el 09-10-2026, de 9,2 °C a las 8:30 a 14,7 °C a las 9:05; las vecinas,
10,5 °C a las 9). La hora cambia con la época del año, y en verano o en
invierno también hay tardes. El sensor de radiación no lo ve: durante el
salto marca de 20 a 37 W/m², lo mismo que más tarde sin salto. Por eso no se
mira la hora ni la radiación, sino el salto de la propia estación comparado
con las vecinas (`sol_estacio.py`, ADR 0081).

**Lo esperado.** Con $`V`$ la mediana de las vecinas leídas en la última media
hora (al menos dos), la temperatura esperada en casa es

```math
\hat T = V + d, \qquad d = \text{mediana}_h \left( T_{\text{casa}}(h) - V(h) \right),
```

con $`d`$, la **diferencia habitual**, sobre las horas en punto de los últimos
30 días sin sol en el termómetro (hacen falta 24). La estación está en una
zona algo más fría del barrio: el 12-10-2026, $`d = -1\text{,}0`$ °C. La mediana
evita que una vecina con un fallo arrastre el resultado.

**Cuándo hay sol en el termómetro.** De día (radiación mayor que cero), con
$`T`$ la lectura de ahora y $`T_{30}`$ la más baja de los últimos 30 minutos,
empieza si se cumplen las dos condiciones

```math
T - T_{30} \ge 1\text{,}5 \text{ °C} \qquad \text{y} \qquad T - \hat T \ge 1\text{,}5 \text{ °C},
```

y sigue mientras $`T - \hat T \ge 0\text{,}7`$ °C, de día y como mucho 3 horas. Las dos condiciones de inicio separan el sol en
el termómetro de un calentamiento del aire, que es más lento y también se ve
en las vecinas.

**Cuándo no se corrige.** Si aún no hay 24 horas comparables o en la última
media hora no se han leído al menos dos vecinas (las cuatro de Weather
Underground, apartado 16), «Ara» muestra lo que mide la estación. Tampoco
corrige la reserva de IONOS, que publica cuando falla el NAS: no tiene el
registro de la estación ni el de las vecinas.

**Mientras dura**, «Ara» muestra $`\hat T`$: en la web y en el bot, redondeada
a décimas y sin ninguna nota; lo que midió la estación queda en los datos
(`temperatura_estacio`). La humedad relativa también se
corrige: el sensor caliente la marca más baja, pero el agua del aire, y por
tanto el punto de rocío $`T_d`$, no cambia. Con la fórmula de Magnus,

```math
HR = 100 \cdot \frac{E(T_d)}{E(\hat T)}\ \%, \qquad E(x) = e^{17\text{,}625\, x / (243\text{,}04 + x)}.
```

Con $`T_d = 12\text{,}7`$ °C, a 13 °C reales son un 98 %; con el sensor a 16,6 °C, la
estación marcaría un 80 %. La presión y la lluvia no las altera el sol, y el
viento no sale de esta estación.

**Esas horas no enseñan.** Cada episodio queda en `registre/sol-estacio.csv`,
y sus horas no cuentan para corregir la temperatura de la previsión
(apartado 3). Para comparar con ayer («2 graus més que ahir») llevan
$`\hat T`$, como «Ara»: el dato de esas horas existe, solo falta el de la
estación; si no hay dos vecinas o diferencia habitual, la hora se quita. Del 9 al 12-10-2026 hubo cuatro, entre
las 8:45 y las 9:25 (el 12, hasta las 10:25), de 3,4 a 5,2 °C por encima de lo
esperado.

**Límites.** Las vecinas dan grados enteros: $`\hat T`$ tiene un margen de
unos ±0,5 °C. Una subida real muy brusca del aire, de día, podría tomarse por
sol si las vecinas no la registran a la vez. La diferencia habitual es una sola para
todo el día, pero cambia con la hora: del 9 al 12-10-2026, entre −0,5 y
−0,9 °C de 8 a 10 h y hasta −2,7 °C por la tarde, con una mediana de −1,2 °C.
A primera hora, $`\hat T`$ puede quedar unos 0,5 °C por debajo de la real. Con
más días se decidirá si se calcula por franjas horarias.

## 17 bis. Cómo acierta la previsión

Lo que enseña la página «Fiabilitat» (`fiabilitat.html`, a la que se llega desde
el menú ⋮), con los archivos de `historial.py` (ADR 0099 y 0110). Para cada
hora se compara lo que mostraba la web en la publicación de N horas antes
de que empezara (N de 1 a 23, elegible; `mostrat` en `casa-AAAA-MM.jsonl`)
con lo medido en Montflorit:

- **Temperatura**: el error medio absoluto y el sesgo,
  $$\mathrm{EMA} = \frac{1}{N}\sum_{h=1}^{N} \lvert T^{\text{prevista}}_h - T^{\text{mesurada}}_h \rvert,
  \qquad \mathrm{sesgo} = \frac{1}{N}\sum_{h=1}^{N} \left(T^{\text{prevista}}_h - T^{\text{mesurada}}_h\right),$$
  donde la temperatura medida del tramo es la media de las lecturas de la
  estación de casa al principio y al final de la hora, que es lo que la
  previsión anuncia para el tramo (la media de las dos horas en punto,
  apartado 6). Un sesgo negativo quiere decir que suele dar menos
  temperatura de la que hace. Las horas con sol directo sobre el termómetro
  (apartado 17) no cuentan, como en el aprendizaje. Se da desde 48 horas.
- **Temperatura en la parte alta** (ADR 0125): el mismo EMA y el mismo sesgo,
  con la previsión de arriba, $T^{\text{prevista}}_h + \Delta_h$ (la de la
  riera más la diferencia de la parte alta de esa hora en esa publicación,
  apartado 6 y ADR 0087), contra la temperatura medida arriba: en cada extremo
  de la hora, la mediana de las vecinas de arriba (con dos como mínimo), y la
  media de los dos. Al lado, el EMA de la riera **en las mismas horas**, y si
  la diferencia es casualidad con el remuestreo por días del apartado
  siguiente, sobre las sumas de error de cada día. Cuenta desde el 13-10-2026,
  cuando la web empezó a dar la parte alta. El registro guarda $\Delta_h$
  desde la 3.195.0; en las publicaciones de antes se rehace con el mismo
  cálculo de la web y solo con lo registrado hasta entonces (la mediana de 30
  días por hora solar y, de noche, el ajuste apuntado en
  `part-alta-nit.csv`). Las vecinas dan grados enteros: el error de redondeo
  de una lectura es de hasta medio grado, y una parte del EMA de arriba viene
  de la medida, no de la previsión.
- **Lluvia**: el error de Brier de la probabilidad anunciada $p_h$ contra lo
  que pasó, $o_h = 1$ si llovió (0,2 mm o más, con `aprenentatge.observada`:
  casa, las vecinas y, para las horas secas, Meteocat) y 0 si no,
  $$\mathrm{BS} = \frac{1}{N}\sum_{h=1}^{N} (p_h - o_h)^2,$$
  comparado con el de decir siempre la climatología $c$, la parte de las
  horas con lluvia en todo el registro de esa antelación:
  $$\mathrm{BS}_c = \frac{1}{N}\sum_{h=1}^{N} (c - o_h)^2, \qquad
  \text{mejora} = 1 - \frac{\mathrm{BS}}{\mathrm{BS}_c}.$$
  La página lo dice como «encerta un 35 % més que dir sempre la probabilitat
  habitual». Con $o_h \in \{0, 1\}$, la suma de un día con $n$ horas y $r$
  con lluvia es $\sum (c - o_h)^2 = n c^2 - 2 c r + r$, y así se calcula a
  partir de lo guardado de cada día. Las horas en que no se sabe si llovió
  no cuentan. Además, en el desplegable, la comprobación de calibración por
  franjas de probabilidad anunciada (menos del 20 %, del 20 al 50, del 50 al
  70 y del 70 o más): para cada franja, las horas, la probabilidad media
  anunciada y en cuántas llovió. Si la probabilidad es buena, la fracción de
  horas con lluvia de cada franja se parece a la media anunciada.
- **Cantidad**: la lluvia esperada (la probabilidad de cada hora por sus
  milímetros, apartado 6 bis) y la medida, sumadas en las horas que tienen
  las dos.

**Si una diferencia es segura** se decide con la regla de todo el programa
(apartado 8, `remostreig.py`, ADR 0105): la web acierta más que la
referencia si su suma de errores es menor en al menos el 95 % de 2.000
remuestreos por días con reposición, con los mismos casos para las dos. Así
se compara la lluvia de la web con la climatología y la web con Meteocat y
AEMET.

**Semana a semana**, de lunes a domingo: el EMA de la temperatura y la
mejora de la lluvia sobre la climatología, con la $c$ de todo el registro
para que las semanas se puedan comparar entre sí. **Si mejora con el
tiempo**: las 4 últimas semanas completas contra las 4 anteriores. Los dos
periodos no tienen los mismos casos, así que cada uno se remuestrea por
días por su cuenta (`remostreig.seguretat_periodes`): en cada remuestreo se
calcula el error medio por hora de cada periodo,
$$\bar e = \frac{\sum_{d} E_d}{\sum_{d} n_d},$$
con $E_d$ la suma de errores del día $d$ y $n_d$ sus horas, y se mira en qué
parte de los 2.000 el periodo reciente se equivoca menos. Con un 95 % o más,
ha mejorado; con un 5 % o menos, ha empeorado. Hasta tener 8 semanas
completas no se dice nada. Como unas semanas son más fáciles de prever que
otras, la comparación con Meteocat y AEMET de cada semana ayuda a distinguir
la mejora de la web de la del tiempo que ha hecho.

**Frente a Meteocat y AEMET** (`previsio_oficial.py`, `historial.comparacio`):
la previsión municipal por horas de Meteocat para Cerdanyola (cada 3 horas) y
la predicción horaria de AEMET para el municipio (cada hora) se apuntan en el
NAS desde el 20-10-2026; ninguno de los dos guarda sus previsiones pasadas.
Cada previsión oficial leída en el momento $s$ se compara con la que
publicaba la web en el mismo momento (la publicación más cercana, a 35
minutos como mucho), en las horas que empiezan $N$ horas después de $s$
(redondeado) y tienen medida. La temperatura oficial del tramo es la media de
la de su principio y su final; la lluvia oficial, $q_h = 1$ si da 0,2 mm o
más en la hora y 0 si no, con su Brier $(q_h - o_h)^2$. Se dan los errores de
las dos en las mismas horas y la seguridad de la diferencia. Por comprobar
con las primeras lluvias: que los milímetros de cada hora oficial son los de
la hora que acaba a esa hora (ADR 0110). La probabilidad de AEMET por tramos
de 6 horas se apunta, pero todavía no se compara.

Los últimos 30 días para el resumen y la comparación con las oficiales. Las
previsiones de la web se apuntan desde el 5 de octubre de 2026; lo medido,
desde el 4.

**Cómo aprende**: la página cuenta, de lo que el aprendizaje deja cada día en
el NAS (apartados 2, 3, 8 y siguientes), qué usa ahora la web en la lluvia, la
temperatura, el radar y el cielo; lo que le falta al candidato propio para
poder decidir (30 horas de lluvia; 14 días de temperatura); su error y el del
vigente, día a día, y los cambios que ha hecho sola, con la fecha.

## 18. Límites

- **La lluvia es rara**: un 4 % de las horas. Las cifras del archivo se
  apoyan en unas 3.600 horas con lluvia; los tramos de la tabla de fiabilidad
  con pocos cientos de horas tienen un margen de unos 3 puntos.
- **Una de cada ocho horas de lluvia a corto plazo, y una de cada cuatro un
  día antes, llega con menos de un 5 %** (apartado 2.1): un porcentaje bajo
  no es un cero.
- **El archivo no es Montflorit**: Sabadell y Sant Cugat están a 5-6 km. Un
  chubasco puede caer en un sitio y no en otro. Por eso el modelo propio lo
  sustituirá cuando acierte más.
- **El corto plazo del archivo es optimista**: une las primeras horas de cada
  pasada del modelo. Con previsiones hechas un día antes el error sube de
  0,0225 a 0,0271, y las probabilidades altas casi desaparecen (194 horas por
  encima del 70 %, frente a 496). El archivo solo tiene esas dos antelaciones:
  entre una y otra, la fórmula interpola. Los datos propios, con la antelación
  real de cada hora, lo medirán mejor.
- **Más allá de 24 horas**, desde la versión 3.40.0, la antelación vale como
  un día ($`\min(t/24, 1) = 1`$): de 24 a 38 horas, la lluvia y la temperatura
  se calculan con una fórmula que no se ha comprobado a esa distancia. AROME,
  además, puede no llegar a las últimas horas: la lluvia sale entonces de los
  otros modelos y, sin la de alguno, la probabilidad es la fracción del
  conjunto. La nota de la tabla lo advierte.
- **La verdad de la temperatura es una estación de aficionado.** Coincide con
  Montflorit (casa da 0,4 °C menos de media en las primeras 36 horas
  comparadas), pero no se ha comprobado con días de sol fuerte en las dos. El
  sol directo sobre su termómetro se detecta y se quita (apartado 17).
- **El corto plazo del archivo de temperatura** también une las primeras horas
  de cada pasada: el error al prever puede parecer algo más útil de lo que es
  con la antelación real. El registro propio lo medirá.
- **El radar no ve la lluvia que nace** en las dos horas siguientes, y su
  círculo y su umbral del 50 % no se han ajustado con datos propios; el
  registro de avisos de lluvia (apartado 10) lo dirá.
- **Las nubes se comprueban a 7 km**, en el aeropuerto de Sabadell, y el
  METAR no siempre recoge las nubes altas. Los modelos dan de media más nubes
  de las que observa (de 19 a 32 puntos en las horas con capas); no se sabe
  qué parte es de nubes altas, y por eso no se corrige ese sesgo, solo se
  eligen los pesos (apartado 8).
- **Limitaciones de método** ya descritas: el error validado del final de
  la lluvia tiene mucha incertidumbre mientras haya pocos episodios
  (apartado 9), los umbrales de la riera salen de cuatro casos (apartado
  12) y la corrección del aire es un factor único para todo el día
  (apartado 15).

## 19. Operación

Detalles internos para la persona que mantiene el código.

**Dónde se guarda.** En el servidor doméstico (un NAS, *Network Attached
Storage*), en `/estat/registre/`: `estacio-casa.csv` (lo medido hora a
hora), `estacio-casa-5min.csv` (la lluvia de casa cada 5 minutos),
`meteocat-XF.csv` y `meteocat-XV.csv` (la lluvia por horas de Sabadell y
Sant Cugat), `veina-<id>.csv` (lo que miden por horas las estaciones vecinas de
Weather Underground), `casa-AAAA-MM.jsonl` (lo previsto),
`radar-fonts-*.jsonl` (lo que daba cada radar), `nuvols-sabadell.csv` (las
nubes observadas por horas en el aeropuerto de Sabadell), `radar-a-prop-*.jsonl` (los
ecos de cada radar a 15 km o menos de casa, en cada pasada), `sortir.csv` (lo que dijo «Si surts» de cada medio y lo que pasó), `avisos-pluja.csv`
(episodios del aviso de lluvia) y `riera.csv` (episodios de la riera). Los
modelos aprendidos, en `/estat/aprenentatge/`: `model.json`, `proposat.json`,
`fi-pluja.json`, `nuvols-pesos.json` (los pesos de los modelos del cielo y
su última comparación) y `historial.csv`, con las muestras, las horas de lluvia y
los errores de cada método día a día.

**Cuándo se ejecuta.** A las 16:00 (`HORA_VERIFICACION` de `config.py`) el
reloj del NAS (`nas/reloj.sh`) completa la estación de casa con
`registre.py estacio` y ejecuta `aprenentatge.py diari`, que además compara
los radares y las mezclas de modelos del cielo, juzga el final de la lluvia y
apunta lo que dijo «Si surts» de cada medio.

**Avisos al responsable.** Llegan a Juanjo por Telegram:

- cada cambio de método propuesto, con las cifras;
- el resultado de la variante con Sant Cugat, a las 30 horas de lluvia;
- el del final de la lluvia, a los 5 episodios, y el de «Si surts», a los 28 días;
- cada cambio de radar o de regla del final de la lluvia;
- cada cambio de los pesos del cielo, y si pasa más de un día sin que llegue
  el METAR de Sabadell.

**Parar un cambio.** El archivo `/estat/aprenentatge/atura` detiene la
aplicación de una propuesta, los cambios de radar, los de pesos del cielo y
los de regla del final de la lluvia.

**Consultas.** `python3 aprenentatge.py estat` (qué se usa y las últimas
cifras), `python3 aprenentatge.py sortir`, `python3 fi_pluja.py resum`,
`python3 pluja_arriba.py resum`, `python3 riera.py resum` y
`python3 nuvols.py estat` (los pesos del cielo y cuánto se equivoca cada modelo).

**El pluviómetro de casa** (`pluviometre.py`, ADR 0017). Su cero no es
fiable: solo cuenta cuando marca lluvia. Tras limpiarlo, una vigilancia de una
sola vez compara cada episodio débil de la referencia (la mediana de las
vecinas fiables o, sin ellas, la menor de Sabadell y Sant Cugat, ADR 0070;
de 0,6 a 4 mm, con dos
horas secas como mucho entre medias) con casa: cuenta como detectado si casa
marca algo en él o en la hora de antes o de después. Con tres episodios
débiles, o a los 45 días, se comunica el resultado para decidir si la página
vuelve a fiarse de su cero.

## 20. Dónde está cada cosa

| Archivo | Qué hace |
|---|---|
| `aprenentatge.py` | Señales, regresiones, validación y decisión diaria; veredicto de cada medio de «Si surts» y lo que pasó |
| `casa.py` | Calcula cada hora de la tabla (apartado 6) y guarda las previsiones |
| `nowcast.py` | El radar llevado hacia delante |
| `radar_fonts.py` | Compara los dos radares |
| `nuvols.py` | El cielo: mezcla los modelos, lee el METAR de Sabadell y elige los pesos |
| `fi_pluja.py` | La hora en que para la lluvia y su aprendizaje |
| `pluja_arriba.py` | El registro del aviso antes de llover |
| `riscos.py` | Las situaciones de peligro con los umbrales de la AEMET |
| `riera.py` | El índice de la riera |
| `aire.py` | La calidad del aire y su corrección |
| `sol_estacio.py` | El sol sobre el termómetro de casa: lo detecta, estima la temperatura y la humedad, y apunta los episodios |
| `web/casa.js`, `web/sortir.js` | Cómo se dice en la página y las reglas de «Si surts» |
| `calibracio/pluja_casa.py`, `calibracio/pluja_casa.json` | Ajusta y comprueba el modelo de lluvia del archivo; sus pesos y la comprobación |
| `calibracio/estacio_casa.py`, `calibracio/temperatura_casa.json` | Ajusta la corrección de temperatura con el año de casa y comprueba las señales de casa para la lluvia; sus pesos |
| `calibracio/analitza.py`, `calibracio/calibracio.json` | La persistencia de la lluvia |
| `calibracio/regla_moto.py` | Compara con el archivo las reglas de lluvia de la moto |
| `calibracio/moviment_radar.py` | Comprueba de dónde medir el movimiento del radar |
| `ecowitt.py`, `registre.py`, `pluviometre.py` | Leen y guardan lo que miden casa y las estaciones de Meteocat; vigilan el pluviómetro |
| `tests/test_aprenentatge.py`, `tests/test_estacio_casa.py`, `tests/test_sol_estacio.py` | Pruebas, con un registro inventado |
