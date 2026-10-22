# 119. Pruebas en las pull requests y más cobertura

Fecha: 2026-10-21 · Estado: propuesto

## Contexto

El ADR 0112 añadió Ruff, ESLint y la medida de la cobertura a la acción de
pruebas (`.github/workflows/previsio.yml`), con la cifra en el resumen de
cada ejecución y sin mínimo. Quedaban dos cosas:

- La acción solo se ejecuta al subir a `main`: una pull request de fuera,
  como las del fork de Las Palmas (`erseco/meteo-local`), no se comprueba
  hasta después de aceptarla, cuando un fallo ya para la publicación
  (`desplegament.py`, ADR 0038) y despierta al reparador (ADR 0113).
- La cobertura de partida era del 81 %. Lo menos cubierto era lo que lee
  fuentes de fuera y lo que junta todo: `casa.py` (50 %, sobre todo
  `recoger`), `boira.py` (46 %), `ecowitt.py` (51 %), `grafica_imatge.py`
  (51 %), `sol_estacio.py` (60 %), `revisor.py` (68 %) y `prevision.py`
  (70 %).

## Decisión

- **La acción también en las pull requests a `main`**, con las mismas
  comprobaciones (Ruff, ESLint, pruebas y cobertura). No publica nada: la
  web la sigue publicando solo el NAS. Sigue sin haber mínimo de cobertura
  (ADR 0112).
- **Pruebas nuevas** (443, de 659 a 1102), sobre lo que hace cada parte y
  no para subir la cifra. Lo que comprueban por encima de todo es que una
  fuente que falla se ve como «sin datos» y nunca como «no llueve», «sin
  avisos» o «sin incidencias», y que los umbrales y el orden de las fuentes
  son los de los ADR. Sin red ni claves: las fuentes se sustituyen con
  `unittest.mock` y todo se escribe en carpetas temporales; cada archivo
  tarda menos de 2 segundos.
  - `casa.recoger` con un banco de fuentes falsas (`tests/test_casa_recoger.py`,
    `OpenMeteoFals` y `Fonts`): la estructura completa del JSON, las fuentes
    que fallan, la previsión anterior cuando falla Open-Meteo, el estado de
    la lluvia de ahora (ADR 0101), la niebla y lo que se apunta en el
    registro.
  - Las fuentes de previsión (`prevision`, `previsio_oficial`, `aire`,
    `entorn`, `wunderground`), la estación de casa (`ecowitt`,
    `sol_estacio`, `registre`), la niebla de ICON (`boira`), el radar
    (`nowcast`, `moviment_registre`), la riera, los trenes, el aprendizaje,
    el bot y los avisos del navegador, el revisor y el reparador, y la
    imagen de la gráfica.
- **Archivos sin cerrar** que encontraron las pruebas con
  `-W always::ResourceWarning`: `open()` sin `with` en `boira.py`,
  `plugim.py`, `confirmacio.py`, `grafica_imatge.py` e `historial.py`. El de
  `historial.py` escribe los JSON que se suben a IONOS: hoy los cierra
  CPython al momento, pero el lenguaje no lo garantiza. Ahora van con `with`.

## Alternativas descartadas

- **Un mínimo de cobertura que pare la acción**: el ADR 0112 lo descarta
  para no parar un arreglo urgente; con el 97 %, la cifra del resumen ya
  avisa si una versión deja código sin probar.
- **Codecov** u otro servicio que guarde la evolución: obliga a dar de alta
  el repositorio y un secreto, y `desplegament.py` no publica un commit con
  una comprobación externa en rojo. Se puede añadir más adelante, solo
  informativo.
- **Cambiar pip por uv en la acción**: con dos dependencias, la instalación
  ya tarda segundos.

## Consecuencias

- Cada pull request a `main` lleva su resultado antes de aceptarla.
- Las pruebas tardan unos 40 segundos (antes, unos 37).
- Una prueba de `bot/push.py` necesita `cryptography` y se salta si no está
  (en la acción no está; en el NAS y en IONOS sí).
- Para cambiar algo de `casa.recoger` o de una fuente, las pruebas nuevas
  dicen qué se rompe; el banco de `test_casa_recoger.py` admite una fuente
  nueva con una línea.

## Evidencia

- Sobre el commit 0239086 (3.178.2): Ruff 0.17.1 sin avisos; 1102 pruebas
  en verde dos veces seguidas y dentro de coverage 7.16.2, con
  `TZ=Europe/Madrid`. Cobertura del **81 % al 97 %** (de 2.081 a 299
  instrucciones sin recorrer). Por módulo, entre otros: `casa.py` del 50 %
  al 100 %, `revisor.py` del 68 % al 100 %, `prevision.py` del 70 % al
  100 %, `sol_estacio.py` del 60 % al 100 %, `bot/bot.py` del 88 % al
  100 %, `boira.py` del 46 % al 93 %.
- Probado antes en una pull request a la copia de `main` de
  `erseco/meteo-local`.

## Riesgos y limitaciones

Posibles fallos que las pruebas dejan a la vista y **no se cambian aquí**
(las pruebas fijan el comportamiento de ahora); para decidir:

- `revisor.py`, `demana`: `json.loads(r.stdout)` sin control. Si la orden
  `claude` devuelve algo que no es JSON, `revisa` falla antes de guardar el
  estado y en la pasada siguiente vuelve a llamar a la IA por el mismo
  motivo. Propuesta: capturar `ValueError` y guardar el estado con el error.
- `revisor.py`, `respostes` (Aplicar): una propuesta con solo `ca` guarda
  `es` con el texto catalán, que sale en la página en castellano.
- `vent_veines.py`, `ajusta`: `and info.get("error_quadratic")` deja fuera
  una vecina con error cuadrático 0,0, que sería la mejor. Propuesta:
  `is not None`. Con estaciones reales es muy improbable.
- `bot/bot.py`, `Api.__call__`: un error HTTP con un cuerpo que no es JSON
  da `ValueError` en lugar de `Bloquejat`; un 403 así no daría de baja el
  chat bloqueado. Propuesta: leer el cuerpo con `try`.
- `trens.py`, `calcula(ara)`: no pasa `ara` a `trens_renfe`, que mira la
  frescura del feed con el reloj real (solo importa al repetir un momento
  pasado).
- `previsio_oficial.py`, `apunta`: sin clave, hace igualmente la consulta y
  la cuenta en el límite mensual de Meteocat.
- Algunas pruebas anteriores cambian variables de módulo sin devolverlas
  (`tests/test_nowcast.py`, `tests/test_aprenentatge.py`) o dejan archivos
  abiertos; las nuevas no dependen de ello.

## Validación

- La acción en verde en una pull request y, tras aceptarla, en `main`.
