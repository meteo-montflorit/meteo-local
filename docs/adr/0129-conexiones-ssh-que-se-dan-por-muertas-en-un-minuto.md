# 129. Las conexiones ssh del NAS se dan por muertas en un minuto

Fecha: 2026-11-19 · Estado: aceptado

## Contexto

El 19-11-2026 el NAS dejó de publicar «Temps a Montflorit» de 02:34 a 04:53;
la reserva de IONOS (ADR 0032) publicó en su lugar desde las 03:10 y avisó a
Juanjo. El NAS no se colgó (el cron siguió cada cinco minutos) ni se reinició:
hacia las 02:38 la red de casa se cortó un momento (los bots del NAS dan
«Network is unreachable» de 02:38 a 02:40, y a las 02:39:44 el NAS renovó su
dirección por DHCP y rehízo su ruta). Una conexión ssh que el reloj tenía
abierta en ese momento se quedó esperando una respuesta que no iba a llegar.

Ninguna de las conexiones ssh del contenedor tenía forma de notar que la otra
punta ya no estaba: solo `ConnectTimeout`, que vale para abrirla, no para una
conexión ya abierta. La cerró el núcleo con su keepalive de TCP, que en el NAS
espera 7200 s y luego hace 9 pruebas cada 75 s: 2 h 11 min. De 02:39 a 04:51,
más la pasada que tocaba, cuadra con la publicación de las 04:53:35. El reloj
es un solo bucle (`nas/reloj.sh`), así que mientras tanto no hizo nada más.

No se sabe cuál de las conexiones se quedó colgada (los datos de las 02:33 son
los últimos que llegaron a IONOS). La más probable es el `git ls-remote` que el
reloj hace cada minuto para ver si hay código nuevo (`hay_cambios`), que no
tenía límite de tiempo; pero el envío a IONOS y el `git push` de la web podían
quedarse igual.

## Decisión

- La imagen del contenedor (`nas/Dockerfile`) instala
  `/etc/ssh/ssh_config.d/conexio-viva.conf` con `ServerAliveInterval 15` y
  `ServerAliveCountMax 4`: ssh pregunta al servidor cada 15 s si no recibe nada
  y, tras cuatro preguntas sin respuesta, cierra la conexión con error. Vale
  para todas las conexiones ssh del contenedor (git con GitHub, los datos a
  IONOS, la copia del registro), sin tocar cada orden.
- `hay_cambios` lleva además `timeout 90`, como las órdenes de git de
  `desplegament.py` (120 s): se ejecuta cada minuto y no debe poder parar el
  reloj por ningún motivo.

Con esto, un corte de la red a media conexión cuesta como mucho un minuto y
medio de espera, y el reloj sigue: si la red ya ha vuelto, publica en la misma
pasada o en la siguiente.

## Alternativas descartadas

- **Bajar el keepalive de TCP del sistema del NAS.** Afecta a todo el NAS y a
  sus otros servicios, y solo actúa en los programas que lo piden.
- **Poner `timeout` a cada orden de red del reloj y de `publica.sh`.** Un
  límite total corta también un envío lento pero vivo; ServerAlive solo corta
  la conexión que no responde. Se pone solo en `hay_cambios`, que no envía nada
  grande.

## Consecuencias

Si GitHub o IONOS tardan más de un minuto en responder a una conexión abierta
sin mandar nada, ssh la cierra y la pasada da su fallo de siempre («IONOS ha
fallat», «no s'ha pogut publicar la web»), que se reintenta en la siguiente.

## Evidencia

- Registro del contenedor (`docker logs meteo-local`): «publicado» a las
  02:34:42 y el siguiente a las 04:53:35, sin nada en medio.
- `karla-bot` en el mismo NAS: «Network is unreachable» de 02:38:32 a
  02:40:17. `/var/log/dhclient/dhclient@eth0.log`: renovación a las 02:38:41
  y 02:39:43. `/var/log/cron.log`: el cron siguió cada cinco minutos.
- `/proc/sys/net/ipv4/tcp_keepalive_time` 7200, `tcp_keepalive_probes` 9,
  `tcp_keepalive_intvl` 75 en el NAS.
- Reserva de IONOS (`reserva.py estat`): avisó a las 03:10:33 de que el NAS no
  publicaba desde las 02:33 y se paró a las 04:55:01.

## Riesgos y limitaciones

Que la conexión colgada fuera el `git ls-remote` es una hipótesis: cuadra con
los tiempos, pero no quedó registrado qué proceso esperaba.

## Validación

- Tras reconstruir el contenedor, `ssh -G github.com` dentro de él da
  `serveraliveinterval 15` y `serveralivecountmax 4`, y el reloj vuelve a
  publicar.
- Prueba de corte (19-11-2026): una conexión ssh abierta con esas opciones, a
  la que el NAS deja de contestar (regla de iptables solo para esa conexión),
  se cierra sola en unos 75 s con error 255.
