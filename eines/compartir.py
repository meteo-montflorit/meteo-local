#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La imatge de la vista prèvia en compartir un enllaç (Open Graph, ADR 0117):
web/img/compartir-capvespre-{ca,es}.jpg, 1200 × 630.

El fons i el dibuix de la targeta «Ara» al capvespre amb pocs núvols
(estil.css, .cel-albapoc; Meteocons «sunset»), amb la lletra de la web
(Figtree), el nom, què és i l'adreça (Juanjo, 23-10-2026: «las del amanecer y
atardecer son muy bonitas»; de dues propostes, «la A»). Es dibuixa amb
Playwright a partir dels mateixos fitxers de web/ i es desa en JPEG, que amb
els degradats pesa una cinquena part del PNG.

Si canvia el nom del fitxer, canvieu-lo també a montflorit.open_graph: els
serveis que ja tenien la imatge en demanen una de nova només si l'adreça
canvia.

  python3 eines/compartir.py
"""
import io
import os
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

ARREL = pathlib.Path(__file__).resolve().parent.parent
WEB = ARREL / "web"
NOM = "compartir-capvespre-{}.jpg"
QUALITAT = 86

TEXTOS = {
    "ca": ("Temps a<br>Montflorit", "La previsió del barri, hora a hora i de 7 dies, els avisos i la riera, a Cerdanyola del Vallès."),
    "es": ("El tiempo en<br>Montflorit", "La previsión del barrio, hora a hora y de 7 días, los avisos y la riera, en Cerdanyola del Vallès."),
}

PLANTILLA = """<!doctype html><html><head><meta charset="utf-8"><base href="{base}/">
<style>
@font-face {{ font-family: 'Figtree'; font-weight: 300 900; src: url(fonts/figtree-latin.woff2) format('woff2'); }}
@font-face {{ font-family: 'Figtree'; font-weight: 300 900; src: url(fonts/figtree-latin-ext.woff2) format('woff2');
  unicode-range: U+0100-02BA; }}
html, body {{ margin: 0; }}
.targeta {{ width: 1200px; height: 630px; box-sizing: border-box; display: flex; align-items: center; gap: 44px;
  padding: 0 70px 0 60px; font-family: Figtree, sans-serif; color: #1d1a33;
  background: radial-gradient(circle at 88% 82%, rgb(255 236 170 / .95) 0, rgb(255 180 110 / .55) 16%, transparent 42%),
    url("img/cel/nuvols-tenyits.svg") center / cover, url("img/cel/nuvols-tenyits-clars.svg") center / cover,
    linear-gradient(175deg, #6a86c4 0%, #d9a0b2 55%, #ffcf9a 100%); }}
img {{ width: 330px; height: 330px; flex: none; filter: drop-shadow(0 10px 18px rgb(20 35 60 / .3)); }}
h1 {{ margin: 0 0 22px; font-size: 92px; line-height: 1; font-weight: 800; letter-spacing: -.02em; }}
p {{ margin: 0; font-size: 33px; line-height: 1.3; color: #2e2847; }}
p.web {{ white-space: nowrap; margin-top: 30px; font-size: 28px; font-weight: 700; color: #1d1a33; }}
</style></head><body>
<div class="targeta"><img src="img/meteocons/sunset.svg" alt="">
<div><h1>{titol}</h1><p>{subtitol}</p><p class="web">meteo-montflorit.github.io</p></div></div>
</body></html>"""


def main():
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1200, "height": 630})
        for idioma, (titol, subtitol) in TEXTOS.items():
            html = PLANTILLA.format(base=WEB.as_uri(), titol=titol, subtitol=subtitol)
            fitxer = ARREL / "eines" / f".compartir-{idioma}.html"
            fitxer.write_text(html, encoding="utf-8")
            try:
                pagina.goto(fitxer.as_uri())
                pagina.wait_for_timeout(800)
                png = pagina.screenshot()
            finally:
                fitxer.unlink()
            desti = WEB / "img" / NOM.format(idioma)
            Image.open(io.BytesIO(png)).convert("RGB").save(desti, "JPEG", quality=QUALITAT, optimize=True, progressive=True)
            print(desti.relative_to(ARREL), f"{os.path.getsize(desti) // 1024} KB")
        navegador.close()


if __name__ == "__main__":
    main()
