# 78. Avisos de Rodalies de su web y no del canal de Renfe

Fecha: 2026-10-12 · Estado: aceptado

## Contexto

El 12-10-2026 Juanjo vio que la web decía, para la R4, «Amb incidències», con
dos avisos:

- «Per causes alienes a Rodalies no es pot garantir la prestació del servei…»;
- «Servei alternatiu per carretera en tot el seu recorregut».

En cambio, la web de Rodalies decía «12/10/2026 07:34h — Servei ferroviari a
tot el recorregut».

Los avisos se leían del canal GTFS-RT de Renfe (`gtfsrt.renfe.com/alerts.json`).
Ese canal seguía con dos avisos generales: uno del 6-10-2026 a las 17:13 para
19 líneas (el de carretera) y uno del 7-10-2026 a las 07:42. No traía los de
hoy. La web de Rodalies saca sus avisos de su propia API
(`serveisgrs.rodalies.gencat.cat/api/notices`, encontrada en el código de su
página), que solo lleva los vigentes: seis, todos de esa mañana.

## Decisión

Versión 3.69.0.

- **Los avisos de Rodalies, de la API de su web** (`trens.avisos_rodalies`).
  Si no responde, los del canal de Renfe, como antes, y se apunta en los
  errores. Las posiciones de los trenes siguen saliendo del canal de Renfe, y
  FGC no cambia.
- **Un aviso que solo dice que el servicio es normal** a toda la línea
  («Servei ferroviari a tot el recorregut», «Circulació ferroviària…», también
  en castellano; `trens.NORMAL`) no es una incidencia. Con trenes a la vista,
  la línea sale «Circula», con el aviso debajo. Uno parcial («entre X i Y»)
  sigue siendo una incidencia. «Servei ferroviari» cuenta además como aviso de
  servicio (`SERVEI`), como «Circulació ferroviària».
- **Los avisos generales de Rodalies también deciden** si una línea va por
  carretera o en tren: la API está al día. Los generales del canal de Renfe
  siguen sin decidir, porque se quedaban viejos (ADR 0029, auditoría del
  07-10-2026).
- **Vigilancia diaria** (`trens.comprova`, desde `aprenentatge.diari`): la API
  no es un servicio documentado. Si deja de responder o cambia, se avisa a
  Juanjo una vez, y otra cuando vuelve (marca `rodalies-falla`), como con el
  mapa de cortes de luz (ADR 0072).
- **Fuentes** en «Com es decideix» de «Si surts», «Fonts i crèdits», «Com
  funciona», la nota de los trenes y el README.

## Alternativas descartadas

- **Seguir con el canal de Renfe y filtrar los avisos viejos por fecha.** No
  arregla los que faltan: el de las 07:34 no estaba.
- **Leer la portada de rodalies.gencat.cat.** La API da lo mismo, ordenado, con
  líneas y en catalán y castellano.

## Consecuencias

- La R4 dice lo que dice Rodalies: «Circula», con «Servei ferroviari a tot el
  recorregut».
- Si Rodalies cambia la API, la vigilancia lo dice y, mientras, se usan los
  avisos del canal de Renfe.

## Evidencia

- 12-10-2026, 10:22: `notices` con 6 avisos (R1, R2, R4, R7, R8 a las 07:34:
  «Servei ferroviari a tot el recorregut.»; R3, RL4, R13/R14, RG1/R11 y
  R15–RT2, entre las 07:21 y las 07:33). `trens.avisos_renfe()` a la misma
  hora: solo los dos generales del 6 y del 7.
- `python3 trens.py` con el código nuevo: R4 «circula», con el aviso de las
  07:34.

## Riesgos y limitaciones

- La API no está documentada: puede cambiar sin aviso. La vigilancia diaria y
  la reserva de Renfe cubren ese caso.
- El canal de Renfe sigue con avisos viejos: si un día se usa como reserva,
  pueden volver a salir.

## Validación

- 400 pruebas en verde, con nuevas para leer la API, el aviso de servicio
  normal, los generales de Rodalies que deciden y los de Renfe que no, y la
  reserva de Renfe.

## Cambio del 19-11-2026 (3.226.1): la franja que dice el texto

La API de Rodalies seguía dando a las 13:31 el aviso «Entre les 11.26 h i les
13.13 h no hi ha circulació ferroviària…», con servicio por carretera, y la
R8 salía «per carretera» en «Si surts» y en «Consultes» (revisor). Los avisos
de Rodalies no traen final: ahora se toma del texto si dice «entre les … h i
les … h» (o «entre las … h y las … h»), el día en que se publicó o el
siguiente si acaba antes de empezar; si el texto nombra otro día, sin final.
Un aviso ya acabado, de cualquier fuente, ni decide ni se muestra: antes se
mostraba y dejaba la línea «amb incidències». Prueba: `tests/test_trens.py`
(`test_la_franja_del_text_de_rodalies`, `test_un_avis_futur_o_acabat_no_decideix`).

