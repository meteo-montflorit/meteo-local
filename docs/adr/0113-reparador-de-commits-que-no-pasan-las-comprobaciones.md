# 113. Un agente con IA arregla los commits que no pasan las comprobaciones

Fecha: 2026-10-20 · Estado: aceptado

## Contexto

El NAS solo despliega un commit de main con las comprobaciones de GitHub en
verde (`desplegament.py`, ADR 0038; desde la 3.169.2 también Ruff y ESLint,
ADR 0112). Si fallan, la web sigue con la versión anterior, pero el NAS solo
lo apuntaba en su registro: si la sesión que subió el cambio ya había
terminado, el cambio se quedaba sin publicar hasta que alguien mirara (pasó
el 07 y el 08-10-2026). El agente propuso avisar a Juanjo por Telegram; él
prefirió que se arreglara solo (20-10-2026): «en lugar de avisarme a mi no
puede abrir un agente de ia que se encargue de arreglarlo?», y aprobó el
diseño con el aviso posterior, solo informativo.

## Decisión

- **`reparador.py`**, que el reloj del NAS llama cada minuto, aparte, para no
  frenar las pasadas (`nas/reloj.sh`). Con un commit fallido nuevo en
  `desplegament.json`:
  1. **Espera media hora** (`ESPERA_MIN`): la sesión que lo subió puede estar
     arreglándolo. Si main cambia, no hace nada.
  2. En **una copia aparte** (`/estat/reparador/repo`, no la que publica la
     web) repite las comprobaciones con las mismas órdenes que GitHub. Si
     pasan todas, el fallo no era del código (GitHub, la red): sube un commit
     vacío para que GitHub las repita, una sola vez.
  3. Si fallan, lanza **Claude Code con Claude Opus 5.5**
     (`config.REPARADOR_MODEL = "claude-opus-5-5"`, por su nombre exacto),
     como mucho 45 minutos, con `reparador-instruccions.md` y la salida de
     lo que ha fallado. Usa el token de la suscripción que ya tiene el
     contenedor (el del revisor, ADR 0101): no hay ningún pago nuevo.
  4. **Lo comprueba el programa, no el agente**: que las comprobaciones
     pasan; que no ha tocado `.github/`, `ruff.toml`, `eslint.config.mjs`,
     `.coveragerc`, `desplegament.py`, `reparador.py`, sus instrucciones ni
     `nas/`; que no hay menos pruebas ni más `skip`, y que no ha cambiado
     `VERSION`. Así no puede «arreglarlo» quitando lo que falla.
  5. Si todo está en orden, el programa sube la versión de parche, hace el
     commit («… (reparador, 3.170.1, ADR 0113)», firmado «meteo-local
     (NAS)»), la etiqueta y lo sube a main **solo si main no ha cambiado**.
     GitHub repite las comprobaciones y el NAS despliega como siempre.
  6. **Cuando el arreglo está publicado**, avisa a Juanjo por el bot de los
     agentes, una vez y solo para informar: «Temps a Montflorit: las
     comprobaciones de la 3.170.0 fallaban (una traducción sin hacer). Un
     agente lo ha arreglado y ya está publicada la 3.170.1.»
- **Cada commit fallido se intenta una sola vez**, y un commit del propio
  reparador que vuelve a fallar no se repara otra vez: no hay bucles.
- **Lo que no se arregla** queda en `registre/reparador.jsonl` con
  `"resultat": "no_arreglat"`, el motivo y lo que vio el agente. El aviso de
  inicio de sesión del portátil de Juanjo lo lee
  (`~/.claude/hooks/reparador-pendent.sh`) y la siguiente sesión lo arregla.
  Por Telegram no se le avisa: es trabajo del agente, no decisión suya.
- **El contenedor** lleva Ruff (la misma versión que la acción) y Node;
  ESLint se instala en la copia del reparador con las versiones que lee de la
  acción de GitHub.

## Alternativas descartadas

- **Avisar a Juanjo para que abra una sesión**: era la propuesta inicial; él
  prefirió que lo arreglara un agente.
- **Un agente en GitHub (Claude Code Action)**: necesita una clave de API o
  el token en los secretos del repositorio, y el NAS ya tiene Claude Code, la
  clave con escritura y el registro. A igual coste, mejor en el NAS.
- **Arreglarlo al momento, sin esperar**: chocaría con la sesión que acaba
  de subir el cambio y puede estar arreglándolo.
- **Volver a lanzar las comprobaciones con la API de GitHub**: necesita un
  token con permiso sobre las acciones; un commit vacío consigue lo mismo con
  la clave que ya hay.

## Consecuencias

- Puede llegar a la web código que nadie ha mirado. Los límites del punto 4
  lo acotan a arreglos que pasan todas las comprobaciones, y Juanjo recibe el
  aviso con cada uno.
- Un arreglo gasta cuota de la suscripción de Claude (minutos de Opus 5.5)
  solo cuando un commit falla.
- Si alguien sube a main mientras el agente trabaja, el arreglo no se sube
  (main ha cambiado) y queda en el registro.

## Evidencia

- `desplegament.py`: el NAS despliega solo si todas las comprobaciones del
  commit están en verde (`check-runs` de la API pública de GitHub).
- La clave del NAS en GitHub (`NAS meteo-local`) tiene escritura (API de
  claves de despliegue, 20-10-2026).
- Claude Code 2.1.301 en el contenedor, con `--permission-mode
  bypassPermissions` (el contenedor no corre como root).

## Riesgos y limitaciones

- Un fallo que solo se da en GitHub (Python 3.12 allí, 3.11 en el NAS)
  pasaría en el NAS: se repiten las comprobaciones una vez y, si vuelve a
  fallar, queda para la siguiente sesión.
- Las pruebas en el NAS son lentas (medio procesador para el contenedor); el
  agente tiene 45 minutos y cada comprobación 30.

## Validación

- `tests/test_reparador.py`: con repositorios git locales y el agente
  simulado, la espera de media hora, el arreglo con su versión, etiqueta y
  aviso cuando se publica (una vez), un solo intento por commit, los
  límites (archivos prohibidos, pruebas quitadas o saltadas, comprobaciones
  que siguen fallando), el commit vacío cuando en el NAS pasa todo y que no
  se insiste, y que no hace nada si main ha cambiado.
- En el NAS, el 20-10-2026, el agente de verdad sobre un fallo provocado en
  una copia, sin subir nada (se quitó la traducción de una frase de
  «Riera»). Las comprobaciones tardaron 7,5 minutos; el agente, 7,8 minutos
  y 0,23 USD de cuota de la suscripción. Devolvió la traducción y encontró
  otro fallo que solo se daba en el NAS: una prueba de la API de Meteocat
  «sin clave» encontraba la clave de verdad en `~/.config/meteo-local/` y no
  fallaba como esperaba. Cambió la prueba para que no dependa de la máquina
  (aplicado en el repositorio el mismo día). El programa no encontró ningún
  incumplimiento y las tres comprobaciones pasaron después. Sin ese arreglo,
  el reparador no habría podido distinguir nunca un fallo de GitHub de uno
  del código.

## Cambio del 25-10-2026 (3.204.0): también las fuentes que cambian de formato

Cuando una fuente lleva 3 horas sin poder leerse por un error del programa y
no de la red (`fonts_falla.py`, ADR 0031), y no hay ningún commit por arreglar,
el reparador lanza el agente con `reparador-fonts-instruccions.md` y el error.
Además de las comprobaciones de siempre, el programa vuelve a ejecutar
`casa.py` en la copia, con el estado en una carpeta temporal, y solo sube el
arreglo si el error de esa fuente ha desaparecido. Si no lo consigue, avisa a
Juanjo con qué falla y qué ha encontrado el agente. Cada caída de cada fuente
(fuente y desde cuándo) se intenta una sola vez.

