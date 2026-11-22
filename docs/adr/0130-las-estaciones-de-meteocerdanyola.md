# 130. Las estaciones de MeteoCerdanyola: Montflorit para la lluvia y Cerdanyola Centre para el viento

Fecha: 2026-11-22 · Estado: aceptado

## Contexto

Desde el 09-10-2026 (ADR 0058) no se usaba nada de meteocerdanyola.com. El
22-11-2026 su responsable volvió a decir a Juanjo que usara sus datos, y
Juanjo pidió un estudio de lo que aportarían. Su respuesta tras verlo:
«si merece la pena puedes comenzar la incorporación de las dos estaciones».

Se estudiaron dos de sus cuatro estaciones con sus datos de cada minuto del
01-10 al 22-11-2026, leídos de su historial diario, frente a lo que registra
el NAS: la estación de casa, las cuatro vecinas de Weather Underground,
Meteocat de Sant Cugat y Sabadell y el METAR del aeropuerto de Sabadell.

- **Montflorit** (Davis Vantage Vue, según su ficha «sobre la teulada d'una
  casa a 1,5 m d'alçada», con «arbres més alts que poden dificultar les
  ratxes de vent»), junto a la riera.
- **Cerdanyola Centre** (Davis Vantage Pro2 en la azotea de un edificio de
  cinco plantas, «als 4 vents en un lloc alt i ventilat»), a unos 900 m al
  norte del barrio.

## Decisión

- **Las dos, como vecinas** en `config.VEINES`, con `font`: `meteocerdanyola`
  y su `slug`, leídas en cada pasada con `meteocerdanyola.py` (la serie de
  las últimas 24 horas de su web, al minuto, unos 25 KB comprimida). Pasan
  por el mismo camino que las de Weather Underground (`WU.veina_ara`):
  «plou ara», el consenso de lluvia y humedad, el registro por horas y cada
  5 minutos, el aprendizaje y la vigilancia de estaciones caídas. Weather
  Underground solo se da por caída si no responde ninguna de las suyas
  (`WU.estacions`).
- **Montflorit, para la lluvia y la temperatura.** Cuenta para «plou ara» y
  para las horas lluviosas y secas (`plou` y `sec`), pero solo desde 0,4 mm
  (`plou_min_mm`): su pluviómetro marca a veces 0,2 mm sueltos, con calma y
  humedad alta, que nadie más ve (rocío). Por debajo de ese mínimo cuenta
  como seca (`aprenentatge._llindar`). Su temperatura entra en la de la riera
  si falla la estación de casa (`ara_sense_casa`, con ICERDA6). Su viento
  queda en el registro, pero el aprendizaje del ADR 0064 la deja fuera.
- **Cerdanyola Centre, para el viento medio de «Ara»** (`C.VENT_ARA`,
  `meteocerdanyola.vent_ara`): la media de la última media hora, con 15
  lecturas como mínimo y la última de hace 10 minutos o menos. Si no, todo el
  viento sale de Sant Cugat, como antes. **La racha es la de Sant Cugat**
  (`ratxa_estacio`), porque Centre no la publica. Su temperatura, su humedad
  y su presión no se leen (`temperatura`: False): son las de la ciudad.
- **El historial de la gráfica, como «Ara»** (desde la 3.235.0, formato 12;
  Juanjo, al ver que seguía saliendo Sant Cugat: «hazlo»): el viento medio de
  cada hora es el de Cerdanyola Centre si tiene las dos medias horas y, si
  no, el de Sant Cugat; `vent_de` dice de cuál es y la gráfica lo nombra. Las
  rachas, de Sant Cugat. Las medias horas de Centre del 01-10 al 21-11-2026
  se rellenaron en `vent-mitges-hores.csv` con los datos del estudio (2.418;
  copia previa en `estat/vent-mitges-hores.csv.bak-20261122`).
- La racha observada con que se aprende sigue siendo la de Sant Cugat
  (`C.VENT_ESTACIO`), como la de «Ara».
- Las dos se citan en «D'on surt», «Com funciona» y «Fonts», con el permiso
  de su responsable. Las otras dos estaciones de la web (Ateneu y Can Coll)
  no se han estudiado.

## Alternativas descartadas

- **El viento de Montflorit.** Marca cero el 73 % de las medias horas en que
  sopla en Sant Cugat, y con viento fuerte, 7,4 km/h de media frente a 19,2.
  Correlación 0,62; no pasa el filtro del ADR 0064.
- **La racha de Centre como el minuto más alto de la media hora.** El
  22-11-2026, con rachas de 55 a 73 km/h en Sant Cugat y de 64 a 68 en
  Sabadell, se quedaba en 34 a 42: subestimaría el viento justo cuando
  importa.
- **La temperatura de Centre.** Está 1,4 °C por encima de la estación de
  casa de media, y unos 2 °C de noche: calor urbano y de azotea.
- **La lluvia de Centre.** Coincide en cantidades, pero está en otro barrio y
  la de Montflorit ya cubre ese papel.
- **Leer el historial diario en cada pasada.** Va de 250 en 250 filas y no
  dice cuántas hay: la serie de 24 horas comprimida es una sola petición.

## Consecuencias

- El viento de «Ara» llega al minuto, de una estación a 900 m, en lugar de
  por medias horas y con media hora de retraso o más desde 4 km. La racha
  sigue llegando con ese retraso.
- «Plou ara» y el consenso de lluvia tienen un pluviómetro más junto a la
  riera, que ya marcó una hora de lluvia que el de casa no recogió (18-10).
- Dos peticiones más por pasada a un servidor particular: de 5 a 12 MB al
  día comprimidos, según la frecuencia. Si su responsable da un archivo más
  ligero con la última lectura, se cambia `meteocerdanyola.URL`.
- Si el responsable lo pide, se quitan las dos entradas de `config.VEINES`
  y `C.VENT_ARA`, y la web vuelve a lo de antes.

## Evidencia

Estudio del 22-11-2026, del 01-10 al 22-11-2026 (informes privados de
Juanjo; el programa y los datos, rehacibles en minutos con la API pública
`/2026/api/history/daily.php` de su web):

| Viento, medias horas | Media | Factor hasta Sant Cugat | Correlación | Ceros cuando sopla en Sant Cugat |
|---|---|---|---|---|
| Cerdanyola Centre | 5,2 km/h | 0,76 | 0,79 | 1 % |
| Sabadell (Meteocat) | 6,1 | 0,70 | 0,74 | 0 % |
| Sant Cugat (Meteocat) | 4,7 | — | — | — |
| ICERDA18 | 3,2 | 1,33 | 0,77 | 2 % |
| Montflorit | 0,3 | 2,6 | 0,62 | 73 % |

- Con Sant Cugat a 15 km/h o más (45 medias horas): Centre 21,7 km/h de
  media, Sant Cugat 19,4, Sabadell 22,8, ICERDA18 11,5, Montflorit 7,4.
- Lluvia por días: Montflorit y Centre coinciden con la estación de casa y
  las vecinas (19-10: 21,0 y 20,4 mm frente a 25,2 en casa y 20,8 en
  ICERDA6; 12-11: 22,8 y 23,6 frente a 23,5). El 18-10, de 1 a 2 h, casa no
  recogió 4 mm que marcaron Montflorit y las tres vecinas.
- Marcas sueltas de 0,2 mm en Montflorit: 24 en siete semanas, todas con
  viento a cero y humedad del 89 al 98 %; 18 de ellas en horas en que
  ninguna otra estación marcó nada.
- Temperatura de Montflorit: +0,05 °C de media frente a ICERDA6, con décimas
  y 12 cortes de más de 10 minutos en 52 días (5,7 horas).
- Presión: Montflorit 1,7 hPa por debajo del QNH de Sabadell, y la de casa,
  1,8 por encima; por eso no se usa la suya.

## Riesgos y limitaciones

- La comparación del viento dice cuánto se parece Centre a Sant Cugat, no
  cuánto acierta en Montflorit: en el barrio no hay ningún anemómetro bien
  colocado. Su nivel y su exposición la hacen la más representativa que hay.
- Una azotea urbana puede acelerar o frenar el viento según de dónde
  sople. **Hipótesis pendiente**: que el factor sea estable con todas las
  direcciones. El registro (`vent-mitges-hores.csv`, columna `MC_CENTRE`)
  permite comprobarlo.
- Centre tuvo 15 cortes de más de 10 minutos en 52 días, que suman 32 horas
  (el más largo, de 8 horas): entonces manda Sant Cugat.
- Es una web particular sin API documentada: si cambia el formato, falla la
  lectura y todo vuelve a ser como antes del cambio, con el fallo apuntado.

## Validación

- `tests/test_meteocerdanyola.py`: la forma de las lecturas, la marca suelta
  que no llueve y las dos que sí, una estación que falla sin parar la otra,
  y el viento con lecturas recientes, viejas o pocas.
- `tests/test_aprenentatge.py`: las marcas sueltas no hacen lluviosa la hora
  ni impiden que sea seca.
- `tests/test_part_alta.py`: Weather Underground se da por caído aunque
  respondan las de MeteoCerdanyola.
- Pasada real del 22-11-2026, 10:40: Centre 25,5 km/h de media; Sant Cugat
  30,6 km/h y rachas de 73,4.
