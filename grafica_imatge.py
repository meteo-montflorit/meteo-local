#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La gráfica del resumen del día como imagen, para Telegram y los avisos de la
web y la app (ADR 0098; Juanjo, 17-10-2026: «el gráfico resumen … se podría
enviar por telegram en las previsiones? pero solo la parte de la que se hace
la predicción»).

El dibujo es el de la web: una página temporal con estil.css, comu.js,
grafica.js (y es.js en castellano) y los datos dentro, sin pedir nada fuera,
que Chromium sin pantalla convierte en PNG; Pillow recorta el margen. Así la
imagen no puede separarse de lo que se ve en la web.

Cuatro imágenes: la de hoy (de ahora a medianoche, la del resumen de la
mañana) y la de mañana (de la noche de hoy al final de mañana, la del de las
21 h), en catalán y en castellano. Las usa el bot y push.py en IONOS solo si
son recientes; si falta alguna, el resumen sale solo con texto.

  python3 grafica_imatge.py montflorit.json CARPETA   las cuatro, en CARPETA
"""
import datetime as dt
import html as html_mod
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops

AQUI = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(AQUI, "web")
IMATGES = [(dia, idioma) for dia in ("avui", "dema") for idioma in ("ca", "es")]
# Ancho de la gráfica en píxeles CSS y densidad: 1000 a doble resolución se lee
# bien en el móvil y pesa unos 100 KB.
AMPLE = 1000
ESCALA = 2
MARGE = 16
TEMPS_S = 60


def nom(dia, idioma):
    return f"grafica-{dia}-{idioma}.png"


def chromium():
    for ordre in (os.environ.get("CHROMIUM"), "chromium", "chromium-browser", "google-chrome"):
        if ordre and shutil.which(ordre):
            return shutil.which(ordre)
    return None


DIES = {"ca": ["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"],
        "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]}
MESOS = {"ca": ["gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre",
                "novembre", "desembre"],
         "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
                "noviembre", "diciembre"]}


def credits(dades, idioma):
    """Las dos líneas de debajo (Juanjo, 17-10-2026: «si alguien la copia y la
    pega no sale la web… breve pero suficiente para saber lo que es»): qué es,
    de dónde, de cuándo y dónde verla; y que lo oficial manda, con la frase de
    «Perill»."""
    g = dt.datetime.fromisoformat(dades["generat"])
    mes = MESOS[idioma][g.month - 1]
    if idioma == "es":
        quan = f"previsión del {DIES['es'][g.weekday()]} {g.day} de {mes}, {g:%H:%M}"
        avis = "No es oficial: si la AEMET, Meteocat o Protección Civil dan un aviso, manda el suyo."
    else:
        quan = f"previsió de {DIES['ca'][g.weekday()]} {g.day} {'d’' if mes[0] in 'ao' else 'de '}{mes}, {g:%H:%M}"
        avis = "No és oficial: si l’AEMET, Meteocat o Protecció Civil donen un avís, mana el seu."
    return (f"Temps a Montflorit (Cerdanyola del Vallès) · {quan} · meteo-montflorit.github.io", avis)


def pagina(dades, dia, idioma):
    """La página que dibuja solo la gráfica, con todo dentro: también los
    iconos del cielo, que son símbolos de la página de la web (casa.html)."""
    def llegeix(*r):
        with open(os.path.join(*r), encoding="utf-8") as f:
            return f.read()
    icones = re.search(r'<svg width="0" height="0".*?</svg>', llegeix(WEB, "casa.html"), re.S).group(0)
    # Nada de «</script>» dentro de los datos: cerraría la etiqueta.
    json_dades = json.dumps(dades, ensure_ascii=False).replace("</", "<\\/")
    es = f"<script>{llegeix(AQUI, 'montflorit', 'es.js')}</script>" if idioma == "es" else ""
    return f"""<!doctype html>
<html lang="{idioma}" data-lloc="Montflorit" data-theme="light">
<head><meta charset="utf-8"><style>{llegeix(WEB, 'estil.css')}
body {{ margin: 0; padding: 0; max-width: none; background: #fff; width: {AMPLE + 2 * MARGE}px; }}
main {{ padding: {MARGE}px; max-width: none; margin: 0; }}
.grafica {{ margin: 0; padding: 0; border: none; background: #fff; }}
.credits {{ margin: 10px 0 0; color: #475569; font-size: 13px; line-height: 1.45; }}
.g-mes-enlla-avis::after {{ content: none; }}
</style></head>
<body>{icones}<main id="lloc"></main>
{es}<script>{llegeix(WEB, 'comu.js')}</script>
<script>{llegeix(WEB, 'grafica.js')}</script>
<script>
const dades = {json_dades};
GENERAT_GRAFICA = dades.generat;
AVISOS_GRAFICA = dades;
const fig = graficaDia(dades.hores, dades.riscos, {json.dumps(dia)});
if (fig) {{
  // Amb el vent (Juanjo, 17-10-2026: «aporta información útil con poco cambio
  // del gráfico»).
  // La part alta, només si en alguna hora s'allunya 2 °C o més de la de baix:
  // per sota, les dues corbes gairebé es toquen i la previsió ja s'equivoca
  // en un grau (Juanjo, 17-10-2026: «en telegram valdría la pena poner la
  // parte alta?»; el mateix llindar que COMPARA_MIN del bot).
  const alta = fig._files.some((f) => Math.abs(arrodoneixAlta(f.dif_alta)) >= 2);
  fig._opcions = {{ gran: true, vent: true, alta }};
  // Sense la càmera de «Consultes»: en una imatge no serveix (Juanjo, 17-10-2026).
  fig._botoImatge = false;
  // Compacta, a l'amplada de la imatge, sense desplaçament (dibuixaGrafica, COL_HORA).
  fig._compacte = true;
  document.getElementById('lloc').append(fig);
  dibuixaGrafica(fig);
  document.getElementById('lloc').insertAdjacentHTML('beforeend', {json.dumps('<p class="credits">' + '<br>'.join(html_mod.escape(l) for l in credits(dades, idioma)) + '</p>')});
  document.body.dataset.fet = '1';
}}
</script></body></html>
"""


def retalla(ruta):
    """Quita el blanco de debajo (la ventana es más alta que la gráfica) y deja
    un margen igual alrededor."""
    im = Image.open(ruta).convert("RGB")
    caixa = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    if not caixa:
        return False
    m = MARGE * ESCALA
    im.crop((0, 0, im.width, min(im.height, caixa[3] + m))).save(ruta, optimize=True)
    return True


def fes(dades, carpeta, navegador=None):
    """Las cuatro imágenes en la carpeta. Devuelve los nombres hechos; la que
    no se puede hacer (sin horas suficientes, Chromium falla) no está."""
    navegador = navegador or chromium()
    if not navegador:
        return []
    os.makedirs(carpeta, exist_ok=True)
    fetes = []
    with tempfile.TemporaryDirectory() as tmp:
        for dia, idioma in IMATGES:
            html = os.path.join(tmp, f"{dia}-{idioma}.html")
            png = os.path.join(carpeta, nom(dia, idioma))
            with open(html, "w", encoding="utf-8") as f:
                f.write(pagina(dades, dia, idioma))
            if os.path.exists(png):
                os.remove(png)
            try:
                subprocess.run([navegador, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                                "--no-first-run", "--disable-extensions", f"--user-data-dir={tmp}/perfil",
                                f"--window-size={AMPLE + 2 * MARGE},900", f"--force-device-scale-factor={ESCALA}",
                                f"--screenshot={png}", "file://" + html],
                               capture_output=True, timeout=TEMPS_S, check=False)
            except subprocess.TimeoutExpired:
                continue
            if os.path.exists(png) and retalla(png):
                fetes.append(nom(dia, idioma))
            elif os.path.exists(png):
                os.remove(png)
    return fetes


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        print(" ".join(fes(json.load(f), sys.argv[2])) or "cap imatge")
