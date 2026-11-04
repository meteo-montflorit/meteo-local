# 38. Correcciones de la auditoría del 7 de octubre de 2026

Fecha: 2026-10-08 · Estado: aceptado

## Contexto

El 07-10-2026, con la versión 3.11.1 publicada, Juanjo encargó a Codex una
auditoría de solo lectura de todo el conjunto: web, NAS, reserva y bot de
IONOS, canal de Telegram y vigilancia. El informe (de trabajo, no se publica:
su primer punto describe un fallo de seguridad) encontró seis hallazgos de
prioridad alta y cinco de media, reproducidos en memoria, en un navegador
aislado o con archivos ficticios, sin tocar producción. Juanjo acordó qué
corregir de cada uno en la conversación de esa noche y pidió hacerlo al día
siguiente. Este ADR recoge las decisiones; cada una está en su sitio del
código con la referencia «auditoría del 07-10-2026».

## Decisión

1. **Subida a IONOS** (`reserva/rep-dades.sh`, orden fija de la clave del
   NAS en el `authorized_keys` de IONOS). La orden antigua extraía el tar
   tal cual: un enlace simbólico llamado `*.json` habría acabado en la
   carpeta pública, con `chmod` siguiéndolo. Ahora la clave solo puede
   ejecutar el receptor, que guarda el envío (2 MB como mucho), lista el tar
   y rechaza todo lo que no sea un archivo normal llamado `montflorit.json` o
   `avisos.json`, extrae solo esos nombres, comprueba que no son enlaces y
   que son JSON válido, y solo entonces los mueve. Lo instala
   `reserva/instalar.sh` en `.meteo-reserva/bin/rep-dades`.
2. **Web con la pestaña abierta y sin red** (`web/comu.js`, `carrega`):
   cuando una lectura falla, se vuelven a pintar los datos que hay, para que
   `dadesVelles` (ADR 0031) retire la previsión al cumplir las dos horas sin
   esperar a que llegue nada; al volver a la pestaña, lo mismo.
3. **Copia de GitHub con IONOS atrasado** (`web/comu.js`, `llegeixDades`): si
   lo que sirve IONOS tiene más de 45 minutos (`DADES_RESERVA_MIN`), se pide
   también la copia de GitHub y se usa la más nueva de las dos. Antes solo se
   consultaba si IONOS daba error, y `publica.sh` publica en GitHub justo
   cuando falla la subida a IONOS. Desde la 3.62.2 (11-10-2026) también se
   pide si a los datos de IONOS les falta una actualización del horario que
   ya debería estar publicada (`dadesEndarrerides`: la última hora prevista,
   con los dos minutos de espera, es posterior a `generat`). Motivo: cada
   mañana IONOS cierra el SSH entre las 06:01 y las 06:15 («Connection
   closed by … port 22», registro del NAS del 09 al 11-10-2026); las subidas
   de las 06:03 y las 06:09 fallan y van a GitHub, y con solo los 45 minutos
   la página seguía con los datos de las 06:00 hasta las 06:15. Prueba:
   `test_copia_de_github_si_a_ionos_li_falta_una_actualitzacio`. El corte de
   IONOS se mide con una sonda del 12-10-2026 (`estat/sonda-ionos.log` en el
   NAS).
4. **Avisos privados con reintento** (`avis_privat.py`): `riscos.py`,
   `pluja_arriba.py` y `riera.py` apuntan el episodio como avisado antes de
   enviarlo, y un fallo de Telegram o de red perdía el aviso. Ahora el envío
   pasa por una cola (`avisos-pendents.jsonl`, junto al estado) que el reloj
   del NAS y la reserva reintentan en cada pasada mientras el aviso tenga
   vigencia (3 horas; el de lluvia inminente, 20 minutos); lo que caduca sin
   entregarse queda en el registro. El `avisar-juanjo` de la reserva devuelve
   error si Telegram lo rechaza (`curl -f`).
5. **Riera con huecos en la estación** (`riera.py`, `cobertura` e
   `incomplet`): las medias horas ausentes contaban como cero. Ahora se
   cuentan las presentes en las ventanas de 3 y 6 horas; con más de un hueco
   en 3 o dos en 6 (`FORATS_MAX`) el cálculo sale marcado `incomplet`, se
   apunta en `errors`, los mensajes lo dicen («la pluja real pot ser més
   alta») y el episodio no se cierra hasta tener los datos.
6. **Trenes** (`trens.py`): cada aviso guarda el inicio de su periodo activo
   (`activePeriod` en Renfe, campo 1 del `Alert` en FGC). Entre los avisos
   propios de una línea que hablan del servicio («carretera» o «circulació
   ferroviària»), decide el más reciente; sin fechas, como antes. Los avisos
   se muestran del más nuevo al más viejo. Y cada línea tiene su horario en
   Cerdanyola (`TRENS_HORARI_LINIA`, del GTFS de Renfe y de FGC): hasta
   media hora después de su primer tren no se dice que no circula.
7. **Bot, `/ara`** (`bot/bot.py`, `text_ara_bot`): el mismo límite de edad
   que el resumen (2 horas), también para la propia medida, y la hora de la
   medida en la respuesta.
8. **Reloj del NAS** (`nas/reloj.sh`): el reloj corregido se desplegó la noche
   del 07-10; ahora, además, una verificación de las 16:00 que falla queda
   dicha en el registro.
9. **Publicar solo con las pruebas en verde** (`desplegament.py`): NAS,
   reserva y bot ponían al día su copia con cualquier commit de `main`. Ahora
   consultan la API pública de GitHub (`/commits/<sha>/check-runs`) solo
   cuando `main` ha cambiado: en verde se despliega; pendientes, se espera
   hasta 20 minutos; fallidas, se queda el commit anterior y no se vuelve a
   preguntar por ese commit en 15 minutos; si la API no responde, se
   despliega como antes y se dice. El reloj del NAS mueve la copia con
   `prepara` también en las pasadas programadas, así que un commit fallido no
   llega por ninguna vía. Si lo que falla es traer `main` (el `git fetch`),
   el reloj publica con el commit que ya tiene y lo dice en el registro
   (`sin_poner_al_dia` en `nas/reloj.sh`, 3.211.1): el 04-11-2026, una
   incidencia de las operaciones git de GitHub dejó la web con los datos de
   las 10:30 hasta que se publicó a mano a las 11:01.
10. **Bot sin rastro de fallos** (`bot/bot.py`, `registra`): cada fallo de
    Telegram queda en `errors.log` (junto al estado, sin identificadores de
    nadie: el aviso, cuántos chats y el motivo), y un aviso de riera o de
    peligro que caduca sin entregarse se le dice a Juanjo. `bot.py estat`
    muestra los pendientes y los últimos errores.
11. **`/baixa`** (`bot/bot.py`, `esborra` y `neteja`): la baja borra el chat
    también de `resums` y de los `chats` de cada aviso pendiente, y al
    arrancar cada vuelta se limpian los restos de bajas anteriores.
12. **Observaciones**: en «Si surts», con una salida más tarde que ahora, el
    transporte público dice que los trenes son los de ahora; y con un plan de
    Protección Civil en alerta o emergencia, los veredictos no cambian (ADR
    0008) pero encima sale, con la franja roja del aviso, lo que pide el plan
    y que los veredictos solo miran la lluvia y el viento.

## Alternativas descartadas

- **Un temporizador propio en la web para la caducidad** (lo que sugería el
  informe): el ciclo de lecturas ya vuelve cada minuto o cada cuarto de hora;
  repintar al fallar y al volver a la pestaña cubre lo mismo con menos
  piezas.
- **Esperar sin límite a las pruebas de GitHub**: si la acción no arranca,
  la publicación quedaría bloqueada; 20 minutos es cuatro veces lo que
  tardan.
- **Horario por línea y tipo de día**: el GTFS da horas distintas entre
  semana y en fin de semana (la R4 empieza a las 04:50 o a las 05:20); se
  toma la más tardía de cada línea, que como mucho retrasa media hora decir
  «sense trens» en un día laborable.
- **Reintentar la verificación de las 16:00 el mismo día**: un fallo
  persistente la repetiría cada minuto; queda dicha y se repite al día
  siguiente.

## Consecuencias

- La carpeta `app/meteo-local` de IONOS solo puede recibir dos archivos con
  nombre y contenido comprobados; cualquier otra cosa se rechaza entera.
- La web puede mostrar datos de la copia de GitHub aunque IONOS responda; el
  origen no se muestra (los dos son el mismo cálculo del NAS).
- Un commit con pruebas fallidas o pendientes no llega al NAS, a la reserva
  ni al bot; el registro del NAS (`docker logs meteo-local`) dice por qué.
- El estado del NAS gana `avisos-pendents.jsonl` y `desplegament.json`; el
  del bot, `errors.log`; la reserva usa los mismos nombres en su carpeta.
- Antes de las 07:05 la R7 y antes de las 07:19 la R8 salen «fora d'horari»,
  no «sense trens».

## Evidencia

- Informe de Codex del 07-10-2026 (de trabajo, en el equipo de Juanjo), sobre
  el commit `c69da9b`.
- La orden antigua de la clave, leída en IONOS el 08-10-2026 a las 06:16:
  `tar -xzf - … && chmod 604 $t/*.json && mv -f $t/*.json $d/`.
- GTFS de Renfe (`ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip`,
  08-10-2026, servicios desde el 07-10): primer y último tren en Cerdanyola,
  R4 04:50 (laborables) o 05:20 (fines de semana) a 24:00, R7 06:35 a 22:35 en
  Cerdanyola del Vallès y 06:40 a 22:40 en Cerdanyola Universitat, R8 06:49 a
  21:50. GTFS de FGC (`dadesobertes.fgc.cat`, `gtfs_zip`): S2 en Bellaterra
  05:14 (laborables) o 05:33 a 24:26 o 26:48. El registro del bot de IONOS
  tenía un aviso «trens:R7» a las 05:39 del 08-10-2026.
- `alerts.json` de Renfe el 08-10-2026 a las 06:20: la R8 con dos avisos
  propios, «Circulación ferroviaria en todo su recorrido» (inicio
  1791354540) y «Servicio alternativo por carretera en todo su recorrido»
  (1791299580), y la web diciendo «bus».
- API de GitHub: 60 consultas por hora sin credenciales (documentación de
  `rate limits`, consultada el 08-10-2026).

## Riesgos y limitaciones

- El horario por línea es fijo en `config.py`: si Renfe o FGC lo cambian,
  hay que repetir la consulta del GTFS. Después de medianoche la S2 y la R4
  salen «fora d'horari» aunque circulen hasta las 00:26 o las 02:48.
- La cola de avisos privados reintenta solo mientras el reloj del NAS o la
  reserva pasan; si los dos están caídos, nadie reintenta.
- Si GitHub tarda más de 20 minutos en terminar las pruebas, se despliega
  sin esperar más.

## Validación

- `tests/test_avis_privat.py` (primer envío rechazado, segundo aceptado, una
  sola entrega; caducidad; la riera pasa por la cola),
  `tests/test_desplegament.py` (repositorio git local: verde, fallido,
  pendiente, pendiente más de 20 minutos, sin API, y la lectura de
  `check-runs`), `tests/test_riera.py` (cobertura, cálculo incompleto, cambio
  de día UTC, episodio que no se cierra), `tests/test_trens.py` (inicio de
  los avisos de Renfe y FGC, el más reciente manda, horario por línea),
  `tests/test_bot.py` (`/ara`, `/baixa`, registro y aviso de caducidad) y
  `tests/test_web.py` (copia de GitHub con datos viejos, repintado al fallar,
  textos de «Si surts»). 201 pruebas en verde el 08-10-2026.
- `rep-dades` en IONOS el 08-10-2026: envíos con enlaces simbólicos, otro
  nombre `.json` y JSON roto rechazados (también desde el NAS con su clave
  real), sin cambiar ningún archivo; la subida normal del NAS entra con la
  orden nueva.
- Web en Chromium, Firefox y WebKit, escritorio, móvil y tableta, claro y
  oscuro, con `probar-web`, y axe-core sobre «Si surts».

## Cambio del 09-10-2026: tamaño descomprimido

El receptor limitaba el `tar.gz` a 2 MB pero no lo que contenía: un
paquete de 5 KB podía traer un JSON de 5 MB (auditoría del 09-10-2026, ADR
0057). Ahora comprueba el tamaño declarado de cada entrada, la suma, los
nombres repetidos y el número de entradas antes de extraer, y vuelve a
medir después. Se prueba en local con `sh` y `tar` reales
(`tests/test_rep_dades.py`).
