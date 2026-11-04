# 20. Datos en IONOS y actualización más frecuente

Fecha: 2026-10-06 · Estado: aceptado

## Contexto

Juanjo preguntó si había algún problema en actualizar cada 15 minutos o
menos: límites de las fuentes o de GitHub. El límite real era GitHub Pages,
que, publicando desde una rama, admite unas 10 publicaciones por hora. Con el
radar de Meteocat como imagen principal (ADR 0019), que saca una imagen cada
6 minutos, el modo aviso pedía justo ese ritmo.

Se valoraron dos salidas: servir los datos desde el NAS o desde IONOS, el
hosting de `bilateria.org`. Juanjo propuso IONOS y aprobó hacerlo así.

## Decisión

- **La página sigue en GitHub Pages; los datos que cambian, en IONOS**
  (`https://bilateria.org/app/meteo-local/dades.json` y `casa.json`). El
  navegador los pide allí (`DADES_URL` en `web/comu.js`) y, si no responden en
  6 segundos, lee la copia de GitHub, al lado de la página.
- **El NAS sube los dos archivos en cada pasada** por SSH, en una sola
  conexión (`publica.sh`). Lo hace con una clave propia (`~/.ssh/id_ionos` en
  el contenedor), autorizada en IONOS con una orden fija: solo puede
  descomprimir archivos `.json` en esa carpeta, y los mueve de golpe para que
  nadie lea uno a medias. El usuario y el servidor están en el NAS
  (`~/.config/meteo-local/ionos.env`), no en el repositorio, que es público.
- **La carpeta de IONOS** tiene un `.htaccess` que deja leer los datos desde
  `https://jjdeharo.github.io`, que no los guarde en caché y que no liste su
  contenido.
- **A GitHub solo se publica** cuando cambia el código, cuando hace 30 minutos
  de la última vez (`GH_CADA_MIN`) o cuando IONOS falla. Así quedan como mucho
  2 publicaciones por hora más las de código.
- **Ritmo**: cada 15 minutos en modo normal (las dos páginas; antes, 30) y
  cada 6 en modo aviso, 3 minutos después de cada imagen de Meteocat (antes,
  10; ADR 0010).
- **Menos descargas**: las teselas del radar se guardan en el NAS
  (`/estat/radar-cache`, 3 horas), porque cada imagen tiene su dirección y no
  cambia; y Montflorit se consulta una vez por pasada, no una por página
  (`/estat/cache-web`, 2 minutos).

## Alternativas descartadas

- **Servir los datos desde el NAS**: si se corta la luz o internet en casa, la
  página se queda sin nada que mostrar; con IONOS muestra los últimos datos y
  su hora. Además habría que abrir un subdominio nuevo en el NAS.
- **Publicar en GitHub con una acción**, que no tiene el límite de 10 por
  hora: seguiría subiendo una versión cada 6 minutos y tardando unos 30-60
  segundos en salir.
- **Actualizar más deprisa de 6 minutos**: el radar no cambia tan rápido y los
  modelos se renuevan cada una a tres horas.

## Consecuencias

- Con IONOS caído, la página lee la copia de GitHub, de hasta 30 minutos, y
  avisa del retraso como siempre.
- Una clave más que mantener; si se revoca en IONOS, todo sigue yendo a
  GitHub.
- En un día de aviso, unas 240 pasadas: Open-Meteo, unas 2.000 llamadas de
  las 10.000 diarias gratuitas; Montflorit, 240 consultas.
- La subida de la web a GitHub vuelve a probar si GitHub rechaza la conexión
  (`eines/ssh-reintenta.sh`, 3.212.1): hasta 8 intentos separados 3
  segundos, con 10 segundos como mucho para conectar. El 04-11-2026, durante
  una incidencia de GitHub, la mitad de las conexiones se rechazaban y la web
  se quedó de 10:32 a 12:07 sin subir, con un solo intento por pasada; con
  reintentos entró a la primera. Solo se repite cuando falla ssh (código
  255), antes de que git envíe nada. Riesgo de bloqueo: GitHub no publica un
  límite de conexiones SSH; como mucho son 8 conexiones cada 30 minutos
  (`GH_CADA_MIN`), frente a las 60 por hora con que el reloj ya mira cada
  minuto si `main` ha cambiado (`hay_cambios`). El peor caso, sin red, alarga
  la pasada unos dos minutos.

## Evidencia

- Límites de GitHub Pages: «soft limit of 10 builds per hour», que no se aplica
  publicando con una acción
  (<https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits>).
- Open-Meteo gratuito: 10.000 llamadas al día, 5.000 por hora y 600 por minuto;
  más de 10 variables cuentan como varias (<https://open-meteo.com/en/pricing>).
  Cada pasada hace dos al servicio de previsión (24 y 36 variables) y dos al
  de conjuntos: unas 8 llamadas.
- Ecowitt: 1 llamada por segundo con la clave de API (documentación v3).
- RainViewer: dos horas de imágenes cada 10 minutos, zoom 7 como máximo; no
  publica límite de peticiones. Cada pasada pedía 63 teselas por página.
- Meteocat: imagen de las 10:06 UTC publicada a las 10:19:43 (ADR 0019).
- IONOS respondió con `access-control-allow-origin: https://jjdeharo.github.io`
  y `cache-control: no-cache` a una prueba; la subida desde el contenedor
  funcionó y la misma clave no sirve para listar archivos.

## Riesgos y limitaciones

- Si IONOS cambia su política de SSH o de cabeceras, la página usa la copia de
  GitHub.
- El desfase de 3 minutos supone un retraso de publicación de Meteocat de unos
  14 minutos; si un día tarda más, se coge la imagen anterior.

## Validación

Pruebas (`tests/test_horario.py` con el ritmo de 6 minutos, `test_nowcast.py`
con la caché), una pasada real en el NAS con subida a IONOS sin publicar en
GitHub, y la página publicada leyendo de IONOS en Firefox y Safari.
