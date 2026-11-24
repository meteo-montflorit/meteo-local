#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Els dibuixos i els colors del giny d'Android (ADR 0131), a partir de la web,
perquè el giny es vegi com la targeta d'«Ara» i no se'n separi:

- el fons de cada cel (`.heroi.cel-*` de web/estil.css, amb els dibuixos de
  web/img/cel), fotografiat amb Chromium, en WebP;
- el dibuix gran del cel (Meteocons, web/img/meteocons), retallat al dibuix, en WebP;
- els colors del text de cada cel (--t, --s, la màxima i la mínima i si
  porten vora blanca), llegits del CSS amb el navegador, a GinyEstil.java.

Només cal tornar-ho a fer si canvia el CSS o un dibuix de la targeta:

    python3 android/giny/recursos.py
"""
import io
import os
import pathlib
import subprocess
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

ARREL = pathlib.Path(__file__).resolve().parents[2]
WEB = ARREL / "web"
# Fora de app/: «bubblewrap update» esborra app/src sencer; construeix.sh ho hi copia.
APP = ARREL / "android" / "giny" / "main"
RES = APP / "res" / "drawable-nodpi"
JAVA = APP / "java" / "io" / "github" / "meteo_montflorit" / "GinyEstil.java"

# Els cels de la targeta (casa.js, celPortada: FONS_NIT, FONS_ALBA i els de dia).
CELS = ["sere", "poc", "nuvol", "cobert", "boira", "pluja", "tempesta", "nit", "nitnuvol", "nitcobert",
        "albasere", "albapoc", "albanuvol", "albacobert", "albapluja"]
# Proporció d'un giny de 4×2 i 4×3 a mig camí; el giny el retalla pel mig.
AMPLE, ALT = 960, 560
DIBUIX_PX = 288
DIBUIX_MARGE = 4
QUALITAT = 82


def fons_i_colors():
    html = f"""<!doctype html><html lang="ca" data-theme="light"><head><meta charset="utf-8">
<link rel="stylesheet" href="{(WEB / 'estil.css').as_uri()}">
<style>body {{ margin: 0; }} .heroi {{ width: {AMPLE}px; height: {ALT}px; box-sizing: border-box;
  border-radius: 0 !important; margin: 0 !important; padding: 0 !important; }}
  .heroi > * {{ visibility: hidden; }}</style></head><body>
<section id="t" class="decisio targeta ara heroi"><div class="titular"><p class="titular-cel">x</p></div>
<p class="ara-dia"><span class="temp-max">m</span><span class="temp-min">n</span></p></section></body></html>"""
    colors = {}
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        fitxer = pathlib.Path(tmp) / "fons.html"
        fitxer.write_text(html, encoding="utf-8")
        nav = p.chromium.launch()
        pag = nav.new_page(viewport={"width": AMPLE, "height": ALT})
        pag.goto(fitxer.as_uri())
        for cel in CELS:
            pag.evaluate("(c) => { document.getElementById('t').className = 'decisio targeta ara heroi cel-' + c; }", cel)
            pag.wait_for_timeout(150)
            png = pag.locator("#t").screenshot()
            Image.open(io.BytesIO(png)).convert("RGB").save(RES / f"giny_fons_{cel}.webp", "WEBP", quality=QUALITAT)
            colors[cel] = pag.evaluate("""() => {
              const s = getComputedStyle(document.getElementById('t'));
              const max = getComputedStyle(document.querySelector('.temp-max'));
              const min = getComputedStyle(document.querySelector('.temp-min'));
              return { t: s.getPropertyValue('--t').trim(), s: s.getPropertyValue('--s').trim(),
                max: max.color, min: min.color, vora: max.textShadow !== 'none' };
            }""")
        nav.close()
    return colors


def hex_argb(color):
    """«#0d2340» o «rgb(185, 28, 28)» → 0xFF0D2340."""
    c = color.strip()
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            h = "".join(x * 2 for x in h)
        return f"0xFF{h.upper()}"
    r, g, b = [int(float(x)) for x in c[c.index("(") + 1:c.index(")")].replace(",", " ").split()[:3]]
    return f"0xFF{r:02X}{g:02X}{b:02X}"


def escriu_java(colors):
    files = "\n".join(
        f'        C.put("{cel}", new int[] {{{hex_argb(c["t"])}, {hex_argb(c["s"])}, {hex_argb(c["max"])}, '
        f'{hex_argb(c["min"])}, {1 if c["vora"] else 0}}});'
        for cel, c in colors.items())
    JAVA.write_text(f"""// SPDX-License-Identifier: AGPL-3.0-or-later
// Generat per android/giny/recursos.py a partir de web/estil.css: no es toca a mà.
package io.github.meteo_montflorit;

import java.util.HashMap;
import java.util.Map;

/** Els colors de la targeta d'«Ara» per a cada cel: text, text suau, màxima, mínima i si porten vora blanca. */
final class GinyEstil {{
    static final Map<String, int[]> C = new HashMap<>();

    static {{
{files}
    }}

    private GinyEstil() {{}}
}}
""", encoding="utf-8")


def dibuixos():
    """Retallats al dibuix, amb un marge petit: els de Meteocons porten molt de buit al voltant
    (el núvol en ocupa el 40 % de l'alçada) i al giny, en una capsa petita, es veien diminuts."""
    for svg in sorted((WEB / "img" / "meteocons").glob("*.svg")):
        png = subprocess.run(["rsvg-convert", "-w", str(DIBUIX_PX), "-h", str(DIBUIX_PX), str(svg)],
                             check=True, capture_output=True).stdout
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        x0, y0, x1, y1 = im.getchannel("A").getbbox()
        m = DIBUIX_MARGE
        im = im.crop((max(0, x0 - m), max(0, y0 - m), min(im.width, x1 + m), min(im.height, y1 + m)))
        nom = "giny_cel_" + svg.stem.replace("-", "_") + ".webp"
        im.save(RES / nom, "WEBP", quality=90, method=6)


if __name__ == "__main__":
    os.makedirs(RES, exist_ok=True)
    escriu_java(fons_i_colors())
    dibuixos()
    mida = sum(f.stat().st_size for f in RES.glob("giny_*.webp"))
    print(f"{len(list(RES.glob('giny_*.webp')))} dibuixos, {mida // 1024} KB; colors a {JAVA.relative_to(ARREL)}")
