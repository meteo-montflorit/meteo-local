# 57. Correcciones de la auditoría del 9 de octubre de 2026

Fecha: 2026-10-09 · Estado: aceptado

## Contexto

Codex auditó una copia aislada de la 3.41.0 (commit `15ed0dd`) y entregó un
informe de trabajo, que no se publica, con ocho hallazgos reproducidos con
datos ficticios y sin tocar producción: dos de prioridad alta (la decisión
de peligro de la riera y la publicación tras fallar el generador), cinco
medias y una baja. Juanjo lo pasó con «mira este informe y aplica lo que
consideres necesario». Claude comprobó cada hallazgo en el código antes de
corregirlo: los ocho eran reales. Cada corrección lleva en el código la
referencia «auditoría del 09-10-2026» y una prueba de regresión con el caso
del informe.

## Decisión

1. **La riera decide el nivel con la lluvia de 3 y de 6 horas del mismo
   momento** (`riera.py`, `nivell_amb_radar`, que sustituye a
   `maxim_amb_radar`). Antes el máximo de 3 horas y el de 6 se tomaban por
   separado, de momentos distintos: 50 mm de un chaparrón sobre suelo seco
   ahora (el patrón del 13-09-2025, que no se desbordó) y 60 en 6 horas una
   hora después, con 10 mm más, daban «perill» sin que ningún momento
   cumpliera las dos condiciones de la regla del ADR 0027. Ahora, para cada
   media hora de aquí a una hora, se calculan las dos lluvias juntas, se
   aplica `nivell` a la pareja y se toma el nivel más alto; `index`,
   `index_6h` e `index_d_aqui_a_min` son los de la pareja que lo alcanza
   (la de más lluvia de 3 horas, como antes). El caso del informe pasa de
   peligro a atención; con 10 mm más antes del chaparrón, sigue en peligro.
   A igual nivel y lluvia de 3 horas, gana la pareja con más lluvia de 6 y,
   después, el momento más cercano (3.210.1). Hasta entonces ganaba el más
   lejano: sin lluvia en 3 horas, el índice de 6 dejaba fuera la medida
   hace 5 o 6 horas y la página decía «0,0 en 6» con 3,0 mm medidos
   (revisor, 04-11-2026; `test_sense_pluja_en_3_hores_l_index_de_6_es_el_mesurat`).
   El nivel no cambia: solo las cifras que se muestran.
2. **La publicación se detiene si falla el generador** (`publica.sh`).
   Dentro de la condición de un `if`, Bash no aplica `set -e`: con
   `montflorit.py web` fallando, seguían el `git add`, el `commit` y el
   `push -f` de una web a medias, y se apuntaba la marca `gh-darrer`. Los
   pasos van ahora encadenados con `&&`, y antes de Git se comprueba que
   existen `index.html` y `montflorit.json`. `tests/test_publica.py` ejecuta
   el script real con un `python3` y un `git` de mentira: con el generador
   fallando, ni push ni marca; sin fallo, las dos cosas.
3. **La lluvia de Sant Cugat llega a la previsión** (`casa.py`, `al_prever`
   con `riera`, que `previsio` y `filas_registro` reciben de `casa.py`).
   La variante con Sant Cugat (ADR 0042) se entrenaba con `pluja_1h_xv` del
   registro, pero al prever ese dato no se pasaba, `rasgos` devolvía `None`
   en las cuatro primeras horas y `prob_pluja` caía al modelo del archivo
   sin decirlo: justo donde la observación debía aportar. Ahora `al_prever`
   lleva `pluja_1h_xv` desde `riera["mm_1h"]`, el mismo valor que guarda el
   registro. Si Sant Cugat no tiene dato reciente (`riera` es `None`, más de
   2 horas), la variante usa el archivo en esas horas, y el error «riera:
   Sant Cugat (Meteocat) sense dades recents» de la pasada ya lo deja
   apuntado; el registro no repite el dato en cada hora (`pop`), porque va
   una vez por línea en `sant_cugat`.
4. **Las variantes del aprendizaje se comparan con el base en sus mismas
   horas** (`aprenentatge.py`, `valida_variant`, `candidat`,
   `avis_sant_cugat`). `candidat` elegía entre el base, la variante de Sant
   Cugat y la de los avisos por el menor error, aunque cada una se hubiera
   medido en horas distintas (la de Sant Cugat, solo en las que tienen el
   dato), y `avis_sant_cugat` comparaba lo mismo. Ahora cada variante se
   valida con sus muestras y, con esas mismas, se ajusta y valida otra vez
   el base (`error_base`, `mostres_base`); una variante solo se adopta si,
   además de mejorar al archivo en `MILLORA_MINIMA`, mejora al base en sus
   mismas horas en esa misma proporción (5 %), y entre varias gana la de
   mayor mejora relativa; si ninguna, el base si mejora al archivo. El
   aviso de Sant Cugat y el mensaje de cambio de método dicen el error del
   base «a les mateixes hores». Las métricas del base con todas las
   muestras se conservan aparte.
5. **Quitar una categoría cancela sus avisos pendientes** (`bot/push.py`
   y `bot/bot.py`, bucles de reintento). Los destinatarios se fijaban al
   entrar el aviso en la cola y el reintento solo miraba si la suscripción
   seguía existiendo: alguien que desactivara «pluja» recibía un aviso de
   lluvia pendiente. Ahora, antes de cada entrega, se comprueba que el
   destinatario sigue teniendo esa categoría; si no, se retira de la cola.
6. **El tiempo de vida de la notificación es lo que le queda al aviso**
   (`bot/push.py`), no toda su vigencia: el servicio lo cuenta desde que
   recibe el envío (RFC 8030, 5.2), y un aviso de lluvia de 20 minutos
   reintentado a los 19 salía con 1200 s de TTL. Ahora `ttl` es la
   vigencia que queda, y la notificación lleva `expira`; `web/sw.js` no
   la muestra si al recibirla ya ha pasado.
7. **El tiempo máximo de descarga cubre también el cuerpo** (`web/comu.js`,
   `baixa`). `fetch` se resuelve con las cabeceras y el temporizador se
   paraba antes de `r.json()`: una conexión colgada a mitad de cuerpo no se
   cortaba nunca, y ni la copia de GitHub ni el reintento entraban. El
   temporizador se limpia en un `finally`, después de leer y analizar el
   cuerpo.
8. **El receptor de IONOS limita también el tamaño descomprimido**
   (`reserva/rep-dades.sh`). Limitaba a 2 MB el `tar.gz` recibido, pero un
   paquete de 5 KB podía traer un JSON de 5 MB. Ahora el `awk` que valida
   las entradas comprueba el tamaño que declara cada una, la suma, que no
   haya nombres repetidos ni más de dos entradas, y tras extraer se vuelve
   a medir el archivo. Requiere la clave restringida del NAS: no es una
   subida anónima.

## Alternativas descartadas

- **Comparar las tres variantes sobre la intersección de horas de todas**
  (4): la de los avisos se registra desde el 08-10-2026 y la de Sant Cugat
  desde antes; la intersección sería la menor de las tres y tiraría datos
  del base. La mejora relativa de cada una sobre el base en sus propias
  horas es comparable entre variantes sin perderlos.
- **Anunciar en la riera el primer momento que alcanza el nivel** (1) en
  lugar del de más lluvia de 3 horas: `index_d_aqui_a_min` solo se guarda
  en `casa.json`, no se muestra, y el criterio de antes ya tenía su prueba.
- **Mostrar igualmente en `sw.js` una notificación caducada** (6): el TTL
  corregido ya evita casi todos los casos; si uno llega, es mejor callar
  que anunciar una lluvia que ya ha pasado.

## Consecuencias

- El NAS y la reserva de IONOS se ponen al día solos con el commit (ADR
  0038); el bot y las notificaciones, en su pasada horaria. **El receptor
  `rep-dades` no sale del repositorio**: hay que copiarlo a IONOS
  (`reserva/instalar.sh`, o su línea del `cat … | ssh`), y la subida
  siguiente del NAS lo prueba de verdad.
- Las metodología (`docs/estadistica.md`, apartados 8 y 12) y los ADR 0027,
  0038, 0042 y 0048 describen el comportamiento nuevo.
- Lo que el informe no certifica sigue sin certificar: que el aprendizaje
  mejore la previsión publicada (combina modelo, persistencia y radar) se
  comprueba con el registro, no con las pruebas; y la calibración del
  radar, de los umbrales de la riera y de la corrección del aire no se ha
  recalculado con observaciones nuevas.

## Evidencia

- Informe local de Codex, «Auditoría técnica de Temps a Montflorit», 09-10-2026,
  sobre el commit `15ed0ddfed6c033e8d060260cbd354da3158088c`.
- Cada hallazgo, reproducido con el código real antes de corregirlo: la
  secuencia sintética de la riera daba `nivell='perill'` con `index=50` e
  `index_6h=60`; `publica.sh` con un generador que salía con 9 llamaba
  igualmente a `git push`; `al_prever` no devolvía `pluja_1h_xv`; la
  variante de Sant Cugat se validaba con 56 de 112 muestras y el base con
  112; el reintento de `push.py` entregaba con la lista de categorías
  vacía; el TTL era 1200 s a los 19 minutos; `baixa` seguía pendiente a los
  6,5 s con el cuerpo abierto; el receptor aceptaba 5 MB en 4980 bytes.

## Riesgos y limitaciones

- Si una notificación caducada llega y `sw.js` no la muestra, Chrome puede
  enseñar su aviso genérico de «sitio actualizado en segundo plano». Con el
  TTL correcto debería ser raro; si se ve, se revisará.
- El `awk` del receptor lee el tamaño en la tercera columna de `tar -tzvf`,
  la de GNU tar y BusyBox; probado en local con `sh` (dash).
- La regla nueva de adopción de variantes es más exigente: una variante que
  solo mejore al base por debajo del 5 % en sus horas no se adopta. Es lo
  pretendido.

## Validación

13 pruebas nuevas, 309 en total el 09-10-2026: `test_riera.py`
(`test_perill_nomes_amb_3_i_6_hores_del_mateix_moment`), `test_publica.py`
(dos), `test_previsio_anterior.py`
(`test_la_pluja_de_sant_cugat_arriba_al_model`), `test_aprenentatge.py`
(`test_variant_i_base_amb_les_mateixes_mostres`,
`test_la_variant_nomes_guanya_si_millora_el_base_a_les_seves_hores`),
`test_push.py` (`test_qui_treu_la_categoria_no_rep_el_pendent`,
`test_el_temps_de_vida_es_el_que_queda`), `test_bot.py`
(`test_qui_treu_la_categoria_no_rep_el_pendent`), `test_web.py`
(`test_la_descarrega_es_talla_tambe_a_mig_cos`) y `test_rep_dades.py`
(tres, con `sh` y `tar` reales). `probar-web` de las tres páginas en
Firefox y Chromium, escritorio y móvil, con el `comu.js` nuevo.
