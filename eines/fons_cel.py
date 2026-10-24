#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Els dibuixos del fons d'«Ara» a la portada (ADR 0121): estrelles, núvols
difuminats, gotes, llamps i bancs de boira, en SVG, a web/img/cel/.

Surten de l'atzar amb una llavor fixa: si es tornen a fer, surten iguals.
Només cal tornar-los a fer si es vol canviar el dibuix.

    python3 eines/fons_cel.py
"""
import os
import random

DESTI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "img", "cel")
AMPLE, ALT = 600, 260


def svg(cos):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {AMPLE} {ALT}" '
            f'preserveAspectRatio="xMidYMid slice">{cos}</svg>\n')


def estrelles(r, n, creus, alt=ALT):
    """Més a dalt que a baix, de mides i brillantors diferents; les més
    brillants, en creu."""
    cos = "".join(f'<circle cx="{r.uniform(3, AMPLE - 3):.0f}" cy="{r.uniform(0, 1) ** 1.4 * alt:.0f}" '
                  f'r="{r.choice([.5, .7, .8, 1, 1, 1.2, 1.5, 1.8])}" fill="#fff" opacity="{r.uniform(.3, .95):.2f}"/>'
                  for _ in range(n))
    for x, y, m in creus:
        cos += (f'<path d="M{x} {y - m}v{2 * m}M{x - m} {y}h{2 * m}" stroke="#fff" stroke-width="1" '
                f'stroke-linecap="round" opacity=".85"/><circle cx="{x}" cy="{y}" r="1.4" fill="#fff"/>')
    return svg(cos)


def nuvols(r, n, color, opacitat, y0=20, y1=ALT - 10, difuminat=14):
    cos = "".join(f'<ellipse cx="{r.uniform(0, AMPLE):.0f}" cy="{r.uniform(y0, y1):.0f}" rx="{r.uniform(70, 150):.0f}" '
                  f'ry="{r.uniform(18, 38):.0f}" fill="{color}" opacity="{opacitat}"/>' for _ in range(n))
    return svg(f'<defs><filter id="b"><feGaussianBlur stdDeviation="{difuminat}"/></filter></defs>'
               f'<g filter="url(#b)">{cos}</g>')


def taques(r, clares, fosques, clares_des_de=-40):
    """El cobert de dia (Juanjo, 24-10-2026: «no se trata de clarearlo todo
    sino que no parezca de noche»; i, amb una foto del cel: un gris uniforme,
    fred, amb taques suaus una mica més fosques i una mica més clares, sense
    núvols amb contorn). clares, fosques: (color, opacitat) de cada mena;
    clares_des_de: on comencen les clares (amb text blanc, només a la dreta,
    on no hi ha text, perquè es llegeixi)."""
    def grup(n, color, opacitat, des_de=-40):
        return f'<g fill="{color}" opacity="{opacitat}">' + "".join(
            f'<ellipse cx="{r.uniform(des_de, AMPLE + 40):.0f}" cy="{r.uniform(-20, ALT + 20):.0f}" '
            f'rx="{r.uniform(60, 150):.0f}" ry="{r.uniform(25, 60):.0f}"/>' for _ in range(n)) + "</g>"
    return svg('<defs><filter id="t"><feGaussianBlur stdDeviation="22"/></filter></defs>'
               f'<g filter="url(#t)">{grup(7, *clares, clares_des_de)}{grup(8, *fosques)}</g>')


def gotes(r):
    return svg("".join(f'<path d="M{r.uniform(0, AMPLE + 10):.0f} {r.uniform(-10, ALT - 5):.0f} l-5 14" stroke="#cfe3ff" '
                       f'stroke-opacity="{r.uniform(.15, .4):.2f}" stroke-width="1.4" stroke-linecap="round"/>'
                       for _ in range(90)))


def llamps():
    """Dos llamps en ziga-zaga, al centre i cap a la dreta: no passen per
    sota del text de l'esquerra."""
    def llamp(punts, gruix, opacitat):
        d = "M" + " L".join(f"{x} {y}" for x, y in punts)
        return (f'<path d="{d}" stroke="#fff5c4" stroke-opacity="{opacitat / 4:.2f}" stroke-width="{gruix * 4.5}"/>'
                f'<path d="{d}" stroke="#fff5c4" stroke-opacity="{opacitat}" stroke-width="{gruix}"/>')
    return svg('<g fill="none" stroke-linejoin="round" stroke-linecap="round">'
               + llamp([(330, -5), (312, 55), (332, 57), (300, 135), (324, 137), (296, 230)], 2.2, .55)
               + '<path d="M312 55 L286 88" stroke="#fff5c4" stroke-opacity=".35" stroke-width="1.4"/>'
               + llamp([(455, -5), (440, 45), (458, 47), (434, 110)], 1.8, .4) + '</g>')


def boira():
    bandes = [(40, 22, .55), (105, 28, .5), (175, 24, .6), (225, 30, .45)]
    return svg('<defs><filter id="b"><feGaussianBlur stdDeviation="9"/></filter></defs><g filter="url(#b)" fill="#fff">'
               + "".join(f'<rect x="-40" y="{y}" width="{AMPLE + 80}" height="{h}" rx="20" opacity="{o}"/>'
                         for y, h, o in bandes) + '</g>')


def fes():
    os.makedirs(DESTI, exist_ok=True)
    r = random.Random(21)
    dibuixos = {
        "estrelles": estrelles(r, 130, [(470, 40, 6), (120, 30, 5), (300, 22, 4), (540, 110, 4), (40, 90, 4), (220, 70, 3.5)]),
        "estrelles-poques": estrelles(r, 14, [], alt=120),
        "nuvols-poc": nuvols(r, 4, "#ffffff", .55),
        "nuvols": nuvols(r, 8, "#ffffff", .5),
        "nuvols-cobert": nuvols(r, 9, "#22292f", .38),
        "cobert-dia-clar": taques(random.Random(24), ("#e6e9ee", .45), ("#7d848e", .35)),
        "nuvols-nit": nuvols(r, 6, "#8fa3c9", .25),
        # A la sortida i a la posta del sol, els núvols de baix encesos.
        "nuvols-tenyits": nuvols(r, 5, "#ff9f8a", .55, 40, 200),
        "nuvols-tenyits-clars": nuvols(r, 5, "#ffd2a6", .6, 60, 230),
        "nuvols-calents": nuvols(r, 5, "#ff9f6b", .32, 150, ALT),
        "gotes": gotes(r),
        "llamps": llamps(),
        "boira": boira(),
    }
    for nom, contingut in dibuixos.items():
        with open(os.path.join(DESTI, f"{nom}.svg"), "w", encoding="utf-8") as f:
            f.write(contingut)
    return dibuixos


if __name__ == "__main__":
    for nom in fes():
        print(f"web/img/cel/{nom}.svg")
