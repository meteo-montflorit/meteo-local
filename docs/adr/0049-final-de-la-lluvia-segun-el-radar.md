# 49. Final de la lluvia según el radar, en pruebas y aprendiendo

Fecha: 2026-10-08 · Estado: aceptado

**14-11-2026 (3.223.0).** El final real deja fuera la llovizna de cola, se apunta en paralelo el borde de atrás de la lluvia (vora) y se archivan los recortes del radar con lluvia cerca (al final).


**09-10-2026 (ADR 0058).** La verdad pasa a ser la lluvia de casa cada 5 minutos (`estacio-casa-5min.csv`), no la de Montflorit; un final visto antes de tiempo por no marcar la llovizna cuenta como error de la regla.

## Contexto

Cuando llueve, la tarjeta «Ara» dice «Pluja a sobre». Juanjo preguntó si
podía decir también cuándo se prevé que acabe. El radar llevado hacia
delante (ADR 0019) ya da, cada 5 minutos y hasta 2 horas, la probabilidad de
lluvia en casa; solo se usaba para la llegada.

## Decisión

- **Regla propuesta** (`fi_pluja.py`): el final previsto es el primer
  momento, desde la pasada, en que la probabilidad baja del 20 % durante 15
  minutos seguidos; si no pasa en las 2 horas del radar, «no s'acaba en 2
  hores».
- **Se muestra ya, «en entrenament»** (Juanjo, 08-10-2026: «y si pones la
  estimación actual y pones en fase de entrenamiento… poco a poco irá
  mejorando»; unas horas fue «en proves», hasta que pidió «entrenando»:
  «todo el mundo sabe lo que es entrenar y probar es poco preciso»): en «Ara», «Pluja a sobre · pararia cap a les 20:10 (en
  entrenament)» o «· no s'acaba en 2 hores», con la explicación al pasar por
  encima («Hora estimada amb el radar. Encara s'està entrenant amb la pluja
  real: pot fallar»). `casa.py` lo calcula con la regla
  vigente (`fi_radar`, en `radar.fi` y `radar.sense_fi`), desde ahora o desde
  que llegue la lluvia.
- **Lo medido manda** (Juanjo, 08-10-2026, ante «Pluja a prop: pot arribar»
  sin hora mientras Montflorit medía 0,8 mm/h): si Montflorit o la estación
  de casa miden lluvia, la página dice «Pluja a sobre» aunque el radar solo
  vea lluvia posible, con la hora de final; si el radar no ve ninguna, sin
  hora. El `/radar` del bot, igual, con «(en entrenament: pot fallar)» en el
  texto, porque Telegram no tiene dónde poner la explicación.
- **Qué es «llueve ahora»** (3.27.4, en toda la web, el NAS, la reserva y
  el bot; `config.PLOU_ARA_MIN`): que una de las dos estaciones haya recogido
  lluvia en los últimos 15 minutos. Antes contaban la intensidad que dan
  (tarda en volver a cero: la de casa daba 1,8 mm/h a las 19:55 sin lluvia
  desde las 19:45) y la última media hora: el 08-10-2026 las dos pararon a
  las 19:50 y la página dijo «Pluja a sobre» hasta las 20:15.
- **Aprende sola**: cada día prueba nueve variantes (umbral del 10, 20 o 30 %
  durante 10, 15 o 20 minutos) con lo registrado; con 3 episodios o más, si
  una se equivoca al menos un 5 % menos que la vigente, pasa a usarla
  (`aprenentatge/fi-pluja.json`) y avisa a Juanjo; el archivo `atura` lo
  para. El error de cada pasada: con hora de final, la distancia al final
  real; sin ella, nada si de verdad acababa más allá del radar y, si no, lo
  que faltaba hasta el horizonte.
- **Comprobación.** Desde el 08-10-2026 el NAS guarda la
  lluvia de Montflorit cada 5 minutos (`montflorit-5min.csv`, `registre.py`;
  la estación solo ofrece las últimas 24 horas). Cada día, con el ajuste del
  aprendizaje, `fi_pluja.py` compara la regla con lo que pasó en cada pasada
  registrada mientras llovía (`radar-fonts-*.jsonl`, con el radar que usaba la
  página). Con 5 episodios de lluvia, manda a Juanjo las cifras una vez
  (aciertos a 15 minutos o menos, demasiado pronto, demasiado tarde, error
  medio y aciertos de «no s'acaba en 2 hores») para que decida si se quita el
  «en entrenament» o se deja de mostrar.
  `python3 fi_pluja.py resum` las da en cualquier momento.

## Alternativas descartadas

- **Esperar a tener datos para enseñarlo**: era la primera propuesta; Juanjo
  prefirió enseñarlo ya, diciendo que está en pruebas, y que aprenda.
- **Comprobar con la estación de casa**: su pluviómetro no marca bien la
  lluvia débil (ADR 0017), que es justo la del final de un episodio.
- **Comprobar con las horas de Montflorit**: no dicen en qué minuto para.

## Consecuencias

`montflorit-5min.csv` crece unos 9 KB al día y va en la copia diaria del
registro (ADR 0044).

## Evidencia

Comprobación del 08-10-2026 con lo registrado (un solo episodio, el 6 de
octubre por la noche, 29 pasadas): con la estación de casa como verdad (lluvia
de 20:25 a 22:30 y de 23:30 a 23:45), el final previsto llegaba entre 40 y
90 minutos tarde; pero Montflorit recogió 0,8 mm de 22 a 23 h y otros 0,8 de
23 a 24 h, y el radar, desde las 21:57, daba el final entre las 23:12 y las
00:05. Con un solo episodio y sin la lluvia minuto a minuto de Montflorit no
se puede saber si acierta.

## Riesgos y limitaciones

- El radar solo desplaza la lluvia que hay: no ve que un chubasco crezca o se
  deshaga; acierta más con lluvia que pasa que con tormentas que nacen encima.
- El círculo que se mira crece con la antelación: puede adelantar el final a
  una hora vista.
- Cinco episodios dan una cifra orientativa.

## Validación

`tests/test_fi_pluja.py` (tramos de 5 minutos completos, episodios y pausas,
final previsto, el de la página, la variante que se aprende, `atura`, cifras y
aviso una sola vez) y `tests/test_web.py` (el texto «en entrenament»).

## Cambio del 09-10-2026: validación dejando un episodio fuera y propuesta

La regla se elegía y se medía con los mismos episodios, y el cambio se
aplicaba el mismo día (limitación anotada en la auditoría del 09-10-2026,
ADR 0057). Ahora `error_validat` mide el error de «elegir la mejor»: para
cada episodio, la combinación que menos se equivoca en los demás, juzgada
solo en ese; si ese error es al menos un 5 % menor que el de la regla en
uso, `aprèn` escribe una propuesta (`fi-pluja-proposat.json`), avisa, y
`aplica_proposta` la aplica al día siguiente si no existe «atura», como el
aprendizaje de la lluvia (ADR 0012). `tests/test_fi_pluja.py`:
`test_l_error_validat_deixa_fora_cada_episodi` y la prueba de la propuesta.

## Cambio del 18-10-2026 (3.142.0): el final real con las vecinas

El final real de un episodio sale de la lluvia del barrio cada 5 minutos (casa y las vecinas, `veines-5min.csv`), con la regla única de `aprenentatge.pluja_observada` desde 0,1 mm; un tramo del que no se sabe (None) ni corta ni alarga. Antes, el pluviómetro de casa solo, que daba finales antes de tiempo con lluvia débil; las cifras anteriores no son comparables. Detalle y motivo en el ADR 0102.

## Cambio del 14-11-2026 (3.223.0): el borde de atrás, el final sin la llovizna de cola y los recortes

**Contexto.** Con 20 episodios (280 pasadas) la regla en uso (menos del 30 %
durante 10 minutos) acertaba a 15 minutos o menos 58 de las 147 veces que
daba hora, con un error medio de 54 minutos, y de las 133 que decía «no
s'acaba en 2 hores» acertaba 68. Juanjo: «no me creo que la observacion de
tantos episodios no haga mejorar la prediccion, quizas haya que cambiar la
metodologia». Comprobado con los datos del NAS:

- Ninguna combinación de umbral y minutos (36 probadas, cada radar por
  separado, la media de los dos y la duración esperada, la suma de la serie)
  mejora de forma clara: todas, entre 30 y 50 minutos de error, y las que
  ganan contando por pasadas pierden contando cada episodio igual.
- La probabilidad es la fracción con lluvia de un círculo que crece (3 km
  ahora, unos 13 km a dos horas): con chubascos sueltos se queda entre el 20 y
  el 40 % durante horas, y el final depende del tamaño del círculo. Cuando
  daba el final a 15 minutos o menos acertaba 30 de 57; a una hora o más, 3
  de 40; la correlación entre lo que faltaba según el radar y lo que faltó,
  0,22.
- Contando cada episodio igual, decir siempre «parará en 15 minutos» se
  equivocaba 34 minutos de media; la regla, 30.
- De 55 finales «demasiado pronto», en 15 lo que seguía cayendo era medio
  milímetro o menos: llovizna de cola, que para quien sale ya no es llover.
- Solo se guardaba la serie de cada pasada, no la imagen: otro cálculo no se
  podía probar con lo pasado.

**Decisión** (Juanjo, 14-11-2026: «haz el 1 y el 2, y cambia el final
también»):

1. **El borde de atrás** (`nowcast.serie`, clave `vora`): en el mismo punto de
   donde vendrá la lluvia, la fracción con lluvia de un círculo fijo de
   `VORA_RADI_KM` (2 km), que no crece; el final es cuando esa fracción baja
   del umbral durante los minutos de la regla. Mismo radar y mismo
   movimiento: solo cambia lo que se mira.
2. **En paralelo, sin enseñarlo.** Cada pasada apunta `vora` con `prob` en
   `radar-fonts-*.jsonl` (`nowcast.fonts`). El aprendizaje compara las nueve
   variantes de `prob` y nueve de `vora` (umbral del 30, 50 o 70 % durante 15,
   20 o 30 minutos) cuando hay `MIN_EPISODIS_VORA` (10) episodios con `vora`
   apuntado, todas con esas mismas pasadas, y cambia solo si la elegida gana
   en el 95 % de los remuestreos por episodios (ADR 0105), como hasta ahora.
   La regla guarda el método (`metode`) y la página lo usa (`fi_radar`). Con
   esos 10 episodios, el resultado llega a Juanjo una vez (`AVIS_VORA`), gane
   o no. `python3 fi_pluja.py resum` lo da en cualquier momento.
3. **Los recortes del radar.** Los trozos de 60 km alrededor de casa que
   guarda el registro del movimiento (`moviment_registre.py`), que se
   borraban a las 3 horas, se archivan si tienen lluvia a 30 km o menos
   (`registre/radar-retalls/AAAA-MM/`, unos 5 kB cada uno), con la hora y el
   movimiento: otro cálculo del final se podrá probar con lo ya pasado.
4. **El final real, sin la llovizna de cola** (`final_real`): el último tramo
   del episodio después del cual caen `CUA_MM` (0,5 mm) o menos en total. Con
   los 20 episodios, lo que queda fuera son dos o tres tramos sueltos de 0,1 a
   0,25 mm al final. Con este final, la regla en uso acierta menos (27 de 101
   con hora, error medio de 69 minutos): el círculo que crece sigue viendo
   lluvia alrededor cuando en casa ya ha parado, el defecto que corrige el
   borde de atrás. Las cifras de antes y de después no son comparables.

**Riesgos.** El borde de atrás tampoco ve la lluvia que nace o se deshace, y
con el círculo fijo depende más de que el movimiento sea bueno (el registro
del movimiento lo mide, ADR 0019). Cuántos episodios hacen falta depende de
cuánto llueva: al ritmo de este otoño, de tres a cinco semanas.

**Validación.** `tests/test_nowcast.py` (`test_la_vora_de_darrere_de_la_pluja`),
`tests/test_fi_pluja.py` (`test_el_final_sense_el_plugim_de_cua`,
`test_la_vora_en_paral_lel_i_quan_entra`) y `tests/test_moviment_registre.py`
(`test_els_trossos_amb_pluja_a_prop_es_guarden`).
