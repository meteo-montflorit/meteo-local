# 31. Datos viejos y vigilancia externa

Fecha: 2026-10-07 · Estado: aceptado

## Contexto

Juanjo preguntó qué pasa si el NAS deja de funcionar. La web (GitHub Pages)
y sus datos (IONOS) siguen en pie, pero congelados: la página avisaba a los 20
minutos de que faltaba una actualización y seguía mostrando debajo la
previsión, los veredictos de «Si surts» y el estado de los trenes como si
fueran de ahora. Para un vecino que no lea el aviso, eso puede llevar a
error. Además, si el NAS contesta pero el contenedor no publica, nadie avisaba
a Juanjo: el latido de IONOS solo mira si el NAS responde.

## Decisión

- **En la web** (`comu.js`, `dadesVelles` y `blocDadesVelles`): con datos de
  más de 2 horas (`DADES_VELLES_H`), las dos páginas dejan de mostrar la
  previsión, los avisos, los veredictos, las casillas y los trenes, y dicen de
  cuándo son los datos y dónde mirar mientras tanto: la previsión de Meteocat
  para Cerdanyola, su radar, Rodalies y FGC. Cuando llegan datos nuevos, todo
  vuelve.
- **En IONOS** (`ionos/latido.sh` de `vigilancia-nas`): en la misma vuelta de
  cada 10 minutos, si `montflorit.json` lleva más de 60 minutos sin renovarse,
  avisa a Juanjo por Telegram una vez, y otra cuando vuelve a renovarse.

## Alternativas descartadas

- **Ocultar antes** (20-30 minutos): un fallo pasajero de una fuente dejaría
  la página vacía; el aviso de retraso ya sale a los 20.
- **Una página de reserva calculada fuera del NAS**: es otra decisión, mayor;
  ver la conversación del 07-10-2026 y, si se hace, su propio ADR.

## Consecuencias

- Con el NAS caído, quien abra la web ve un aviso claro y enlaces oficiales,
  no una previsión vieja.
- Los avisos por Telegram de la página (peligro, lluvia, riera) siguen
  parándose con el NAS.

## Evidencia

- Enlace de Meteocat para Cerdanyola: código municipal 082665, sacado de la
  lista de municipios de su web (`/prediccio/municipal/082665`, 200 el
  07-10-2026).
- `date -r` funciona en la shell de IONOS; el `$HOME` del cron ya es `htdocs`.

## Riesgos y limitaciones

- La hora del archivo en IONOS es la de la subida, no la de los datos: si el
  NAS subiera datos viejos, el latido no lo vería (la web sí, por `generat`).

## Validación

`tests/test_web.py` (`dadesVelles` con 2 h 10 min y 1 h 50 min); las dos
páginas, en catalán y castellano, con datos de hace 3 horas en Firefox y WebKit
móvil; `latido.sh --probar` con un archivo de hace 2 horas (avisa) y con el
real (no avisa), en IONOS, el 07-10-2026.

## Cambio del 09-10-2026: el aviso de fuentes caídas, solo de las que usa cada página

El aviso «No s'han pogut llegir totes les fonts: la informació és menys
segura» salía en todas las páginas en cuanto fallaba cualquiera de las fuentes
de `errors`. El 09-10-2026 salió en «El temps» por un 503 pasajero de
Open-Meteo al pedir la salida y la puesta del sol, con la previsión completa.
Juanjo: «esto solo afecta a la tarjeta del sol, no? no afecta a la previsión,
por lo tanto no debe aparecer», y «cada pagina solo avisa de lo que usa».

- **El temps** (`FONTS_TEMPS` en `web/comu.js`): previsión, ensemble,
  estaciones (Montflorit, la de casa y el viento), radar y final de la
  lluvia, avisos de AEMET, planes de Protección Civil, riera, incendios y
  Pla Alfa (`entorn`).
- **Si surts** (`FONTS_SORTIR` en `web/sortir.js`): lo mismo, más el índice
  UV (la ropa), los trenes y el tráfico.
- **Consultes** (`fontsConsulta` en `web/consultes.js`): según la ficha
  elegida; «Avui», las de «El temps» y los trenes; «Demà», las de «El
  temps»; las demás no avisan, porque si les falta el dato ya dicen «Ara
  aquesta consulta no està disponible».

Los nombres son los que pone `casa.py` delante de «:» en cada error; una
fuente nueva hay que añadirla a la lista de la página que la usa.
Validación: `test_cada_pagina_avisa_de_les_seves_fonts` y, en Firefox, las
tres páginas con un error simulado del sol (ningún aviso), del radar (en
todas menos en la ficha del sol) y de los trenes (en «Si surts» y en
«Avui»).

## Cambio del 25-10-2026 (3.204.0): cada fuente caída, qué deja de salir, desde cuándo y quién se ocupa

El aviso general «No s’han pogut llegir totes les fonts: la informació és
menys segura» hacía parecer que fallaba toda la web: el 25-10-2026 a las 12:00
salió en la portada solo porque Meteoalarm (los avisos de AEMET) respondió con
un error 500 (Juanjo: «en lugar de ese mensaje genérico no puedes poner un
mensaje más concreto? indicando lo que puede fallar, ahora parece que toda la
web va mal», y «que no parezca algo permanente»). Y si una fuente caía un día
entero, la web lo repetía en cada actualización y nadie se enteraba: la S2
estuvo dos días «sense dades» (ADR 0079). Desde la 3.204.0:

- **La web dice qué no llega, qué deja de salir y desde cuándo**
  (`avisosFonts` y `TEXT_FONT_FALLA` en `web/comu.js`). Si es de esta
  actualización: «En aquesta actualització no han arribat els avisos de
  l’AEMET: els de Meteocat, sí. Es torna a provar a la propera actualització,
  a les 12:18.». Si dura más de FONT_FALLA_ACTUALITZACIO_MIN (20) minutos:
  «Des de les 12:00 no arriben els avisos de l’AEMET: els de Meteocat, sí. Es
  torna a provar a cada actualització.» (o «Des d’ahir a les 18:00…»). Una
  fuente sin texto propio: «una de les fonts no ha respost: la resta de la
  informació és al dia». La riera mantiene su texto (21-10-2026).
- **El NAS apunta desde cuándo falla cada fuente** (`fonts_falla.py`, en
  `/estat/fonts-falla.json`) y lo publica (`fonts_falla` en los datos). En la
  reserva de IONOS, sin estado, desde ahora.
- **Si dura LLINDAR_H (3) horas**: si el error es de la red o del servidor (no
  responde, un 500…), un aviso a Juanjo por Telegram, una vez, y otro cuando
  vuelve; si parece del programa (la fuente ha cambiado de formato), se lo
  encarga al reparador (ADR 0113), que solo publica el arreglo si con él la
  fuente se vuelve a leer y, si no lo consigue, avisa a Juanjo. Meteocat
  (`smp.py`) y las estaciones (`estacions.py`) ya tenían su aviso y no se
  vigilan aquí.

Una fuente nueva que se añada a la lista de una página lleva también su texto
en `TEXT_FONT_FALLA` y en `fonts_falla.QUE`. Validación:
`tests/test_fonts_falla.py` y `test_cada_pagina_avisa_de_les_seves_fonts`.
