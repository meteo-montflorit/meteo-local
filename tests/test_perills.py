# SPDX-License-Identifier: AGPL-3.0-or-later
"""Totes les alertes de perill, a tot arreu (ADR 0093).

Juanjo, 16-10-2026: «las alertas de peligro deben ir siempre juntas, que sale
tanto en un lado como en el otro, lo mismo con otras alertas de peligro que
ahora no están activas. Deberías tener un sistema para no dejártelas nunca».

Unes dades amb una alerta de cada tipus (bot.TIPUS_PERILL) passen per cada
lloc que les diu: /avisos_actius, el resum d'avui i el de demà (bot i
«Consultes»), el bloc «Avisos actius» de la portada i de «Si surts», i
«Perill». Si un lloc en deixa una, o si apareix un tipus nou sense afegir-lo
aquí, la prova falla."""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
sys.path.insert(0, os.path.join(ARREL, "bot"))
import bot as B  # noqa: E402
import smp  # noqa: E402

ARA = dt.datetime(2026, 10, 17, 10, 0).astimezone()
AVUI, DEMA = "2026-10-17", "2026-10-18"

# Una alerta de cada tipus. Les que tenen hora toquen avui i demà.
MC = [{"meteor": "Intensitat de pluja en 30 minuts", "tipus": "previsio", "llindar": "Intensitat > 20 mm / 30 minuts",
       "perill": 3, "emissio": "2026-10-16T16:20Z", "dies": {AVUI: [(12, 24)], DEMA: [(0, 6)]}}]
RIERA = {"clau": "riera:2026-10-17T09:30+02:00", "tipus": "riera", "inici": "2026-10-17T09:30+02:00", "nivell": "perill",
         "ca": "🔴 <b>Perill de desbordament de la riera de Sant Cugat</b>\nNo t'hi acostis.",
         "es": "🔴 <b>Peligro de desbordamiento de la riera de Sant Cugat</b>\nNo te acerques."}
DADES = {
    "plans": [{"pla": "INUNCAT", "nom": "d'inundacions", "fase": "alerta", "des_de": "17/10/2026 08:00"}],
    "smp": {"avisos": MC, "linies": smp.textos(MC, "09:55"), "fenomens": smp.per_fenomen(MC)},
    "avisos": [{"zona": "Prelitoral de Barcelona", "tipo": "tempestes", "nivel": "groc",
                "inicio": "2026-10-17T12:00:00+02:00", "fin": "2026-10-18T05:59:59+02:00"}],
    "perill_riera": [{"nivell": "maxim", "ca": "Perill de desbordament de la riera de Sant Cugat",
                      "es": "Peligro de desbordamiento de la riera de Sant Cugat"}],
    "entorn": {"incendis": [{"id": "1", "municipi": "Cerdanyola del Vallès", "inici": "2026-10-17T09:40+02:00",
                             "km": 1.2, "collserola": False}],
               "pla_alfa": {"avui": 3, "dema": 4, "tancaments": []}},
    "riscos": [{"clau": "previsio:ratxa", "tipus": "ratxa", "origen": "previsio", "nivell": "groc", "valor": 75,
                "llindar": 70, "unitat": "km/h", "des_de": "2026-10-17T22:00+02:00", "fins": "2026-10-18T02:00+02:00",
                "text": "Vent molt fort previst: ratxes de fins a 75 km/h, avui de 22 a 2 h."}],
}
# L'historial de «Perill» amb una fitxa oberta per a cada tipus que avisa.
def episodi(clau, nivell="groc"):
    return {"clau": clau, "tipus": "riera" if clau.startswith("riera:") else "perill", "inici": "2026-10-17T09:30+02:00",
            "nivell": nivell, "ca": "x", "es": "x"}


HISTORIAL = [RIERA, episodi("pla:INUNCAT", "pc"), episodi("meteocat:2026-10-16T07:55+02:00", "alt"),
             episodi("aemet:tempestes:2026-10-17T12:00:00+02:00"), episodi("incendi:1", "incendi"), episodi("propi")]
FITXES = ["perill.html#a-pla-inuncat-2026-10-17t09-30-02-00", "perill.html#a-meteocat-2026-10-16t07-55-02-00-2026-10-17t09-30-02-00",
          "perill.html#a-aemet-tempestes-2026-10-17t12-00-00-02-00-2026-10-17t09-30-02-00",
          "perill.html#a-riera-2026-10-17t09-30-02-00-2026-10-17t09-30-02-00", "perill.html#a-incendi-1-2026-10-17t09-30-02-00",
          "perill.html#pla-alfa", "perill.html#a-propi-2026-10-17t09-30-02-00"]
# Com es reconeix cada tipus al text, en català i en castellà.
MARQUES = {"pla": ("INUNCAT", "INUNCAT"), "meteocat": ("Meteocat", "Meteocat"), "aemet": ("AEMET", "AEMET"),
           "riera": ("riera", "riera"), "incendi": ("ncendi", "ncendio"), "alfa": ("Alfa", "Alfa"),
           "propi": ("75 km/h", "75 km/h")}
# Les que diuen el que passa ara: al resum de demà no hi van.
NOMES_AVUI = {"riera", "incendi"}


def dades():
    hores = []
    for i in range(36):
        h = (ARA + dt.timedelta(hours=i)).replace(minute=0, tzinfo=None)
        hores.append({"hora": h.isoformat(timespec="minutes"), "fins": (h + dt.timedelta(hours=1)).isoformat(timespec="minutes"),
                      "temperatura": 16, "probabilitat": 0.0, "pluja_mm": 0})
    return {"generat": ARA.isoformat(timespec="minutes"), "ara_casa": {"temperatura": 16, "intensitat": 0, "plou": False},
            "hores": hores, **json.loads(json.dumps(DADES))}


class Perills(unittest.TestCase):
    def test_el_registre_te_una_marca_per_tipus(self):
        self.assertEqual(set(MARQUES), set(B.TIPUS_PERILL))

    def assertTots(self, text, idioma, tipus, on):
        i = 0 if idioma == "ca" else 1
        for t in tipus:
            self.assertIn(MARQUES[t][i], text, f"{on} ({idioma}) no diu l'alerta «{t}»")

    def test_avisos_actius_del_bot(self):
        for idioma in ("ca", "es"):
            self.assertTots(B.text_avisos_actius(dades(), idioma, ARA), idioma, B.TIPUS_PERILL, "/avisos_actius")

    def test_resum_d_avui_i_de_dema(self):
        for idioma in ("ca", "es"):
            self.assertTots(B.resum(dades(), idioma, ARA, avui=True), idioma, B.TIPUS_PERILL, "el resum d'avui")
            dema = B.resum(dades(), idioma, ARA, dema=True)
            self.assertTots(dema, idioma, [t for t in B.TIPUS_PERILL if t not in NOMES_AVUI], "el resum de demà")
            for t in NOMES_AVUI:
                self.assertNotIn(MARQUES[t][0 if idioma == "ca" else 1], dema)

    def test_els_que_cobreix_meteocat_no_surten(self):
        d = dades()
        d["avisos"].append({"zona": "Prelitoral de Barcelona", "tipo": "pluja", "nivel": "groc", "cobert": "meteocat",
                            "inicio": "2026-10-17T12:00:00+02:00", "fin": "2026-10-17T23:59:59+02:00"})
        for text in (B.text_avisos_actius(d, "ca", ARA), B.resum(d, "ca", ARA, avui=True)):
            self.assertNotIn("Avís groc de l'AEMET per pluja", text)
            self.assertNotIn("per pluja i tempestes", text)

    def test_la_portada_i_si_surts(self):
        if not shutil.which("node"):
            self.skipTest("cal Node")
        # Les dues pàgines fan servir el mateix bloc, sense afegir-hi ni treure'n res.
        # «Si surts» ja no els mostra: una línia que remet a «Perill» (19-10-2026; test_web).
        for pagina, crida in (("casa.js", "blocAvisos(dades)"), ("sortir.js", "liniaAvisosConduccio(DADES)")):
            with open(os.path.join(ARREL, "web", pagina), encoding="utf-8") as f:
                self.assertIn(crida, f.read(), pagina)
        # Les línies d'alerta del resum del dia (bot i «Consultes»), sense la marca del nivell.
        linies = [re.sub(r"^\S+ ", "", l) for l in B.resum(dades(), "ca", ARA, avui=True).split("\n")
                  if any(m[0] in l for m in MARQUES.values())]
        codi = ARNES_DOM % tuple(json.dumps(x) for x in (os.path.join(ARREL, "web", "comu.js"), HISTORIAL, dades(),
                                                         ARA.isoformat(), linies))
        r = json.loads(subprocess.run(["node", "-e", codi], capture_output=True, text=True, check=True).stdout)
        self.assertTots(r["text"], "ca", B.TIPUS_PERILL, "«Avisos actius» de la web")
        # Plegat, una línia per avís: tampoc no se'n pot deixar cap (ADR 0094).
        self.assertTots(r["curts"], "ca", B.TIPUS_PERILL, "«Avisos actius» plegat")
        # A la portada, sempre plegat sota el títol, també amb un de nou o de vermell (Juanjo,
        # 20-10-2026: «los avisos activos siempre plegados»; abans, des del 18-10, s'obria sol).
        self.assertEqual(r["plec"], ["details", False, False, False], "«Avisos actius» a la portada, sempre plegat")
        # Cada alerta porta a la seva fitxa de «Perill», perquè s'hi destaqui
        # (Juanjo, 16-10-2026: «con este enlace no me sale el resalte»): a
        # «Avisos actius» i a les línies del resum.
        # Amb un pla, les línies senceres de Meteocat van dins del del pla (ADR 0067) i hi porten;
        # la línia curta de Meteocat, sempre a la seva fitxa (ADR 0094).
        # La riera, a «Riera», amb les dades d'ara; la fitxa en queda com a historial (Juanjo, 14-11-2026).
        fitxes = [("riera.html" if "-riera-" in f else f) for f in FITXES]
        self.assertEqual(set(r["detalls"]), set(fitxes), "«Avisos actius»: cada alerta, a la seva fitxa")
        self.assertEqual(set(r["sensePla"]), set(fitxes) - {fitxes[0]}, "«Avisos actius» sense pla")
        self.assertEqual(sorted(r["linies"]), sorted(fitxes), "el resum: cada alerta, a la seva fitxa")

    def test_perill_te_cada_tipus(self):
        # «Perill» és l'historial dels avisos: cada tipus que avisa hi té fitxa
        # (l'episodi de avisos_bot.py), i el Pla Alfa i els plans en prealerta,
        # que no avisen, hi surten a part.
        with open(os.path.join(ARREL, "avisos_bot.py"), encoding="utf-8") as f:
            codi = f.read()
        episodis = set(re.findall(r'episodi=f?"([a-z]+)[:"]', codi)) | set(re.findall(r'f"(meteocat):\{hora\}"', codi))
        per_tipus = {"pla": "pla", "meteocat": "meteocat", "aemet": "aemet", "riera": "riera", "incendi": "incendi",
                     "propi": "propi"}
        self.assertEqual(episodis, set(per_tipus.values()) | {"riera"},
                         "un avís de perill nou ha de tenir el seu tipus a bot.TIPUS_PERILL")
        self.assertEqual(set(per_tipus) | {"alfa"}, set(B.TIPUS_PERILL))
        with open(os.path.join(ARREL, "web", "perill.js"), encoding="utf-8") as f:
            self.assertIn("fitxaAlfa(dades.pla_alfa)", f.read())


# comu.js amb un DOM mínim que guarda el text, per llegir el bloc sencer.
ARNES_DOM = r"""
const vm = require('vm');
const fs = require('fs');
const [comu, historial, dades, ara, linies] = [%s, %s, %s, %s, %s];
class Node_ {
  constructor(tag) { this.tag = tag; this.fills = []; this.dataset = {}; this.style = { setProperty() {} };
    this.classList = { add() {}, remove() {}, toggle() {} }; this.attrs = {}; }
  append(...xs) { this.fills.push(...xs); }
  prepend(...xs) { this.fills.unshift(...xs); }
  insertBefore(x, ref) { const i = this.fills.indexOf(ref); this.fills.splice(i < 0 ? this.fills.length : i, 0, x); }
  get firstChild() { return this.fills[0]; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener() {}
  // «etiqueta.classe», «.classe» o «etiqueta», entre els descendents; una
  // etiqueta sola que no hi és (les icones, que aquí no es dibuixen), un node buit.
  querySelector(sel) { return this.cerca(sel) || (sel.includes('.') ? null : new Node_('x')); }
  cerca(sel) {
    const [t, c] = sel.split('.');
    for (const f of this.fills) {
      if (typeof f === 'string') continue;
      if ((!t || f.tag === t) && (!c || (f.className || '').split(' ').includes(c))) return f;
      const r = f.cerca(sel);
      if (r) return r;
    }
    return null;
  }
  set textContent(t) { this.fills = [String(t)]; }
  get textContent() { return this.fills.map((f) => (typeof f === 'string' ? f : f.textContent)).join(''); }
}
const RealDate = Date;
class FakeDate extends RealDate {
  constructor(...a) { super(...(a.length ? a : [ara])); }
  static now() { return new RealDate(ara).getTime(); }
}
const ctx = vm.createContext({
  Date: FakeDate, Math, JSON, Number, Object, Set, Map, URL, console, String, Array, RegExp,
  document: { querySelectorAll: () => [], getElementById: () => new Node_('div'), createElement: (t) => new Node_(t),
    createElementNS: (n, t) => new Node_(t), addEventListener() {}, documentElement: { dataset: {}, lang: 'ca' } },
  matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, AbortController,
  localStorage: (() => { const m = {}; return { getItem: (k) => (k in m ? m[k] : null), setItem(k, v) { m[k] = String(v); } }; })(),
  navigator: {}, location: { pathname: '/', hash: '' },
  history: { replaceState() {} }, window: { addEventListener() {} },
  fetch: () => new Promise(() => {}), setTimeout: () => 0, clearTimeout() {},
});
vm.runInContext(fs.readFileSync(comu, 'utf8'), ctx);
vm.runInContext(`HISTORIAL_PERILL = ${JSON.stringify(historial)};`, ctx);
ctx.__dades = dades;
const detalls = (n) => (typeof n === 'string' ? [] : [...(n.tag === 'a' && n.className === 'detall' ? [n.href] : []), ...n.fills.flatMap(detalls)]);
const bloc = vm.runInContext('blocAvisos(__dades)', ctx);
ctx.__linies = linies;
ctx.__sensePla = { ...dades, plans: [] };
const sensePla = detalls(vm.runInContext('blocAvisos(__sensePla)', ctx));
const liniesFitxa = vm.runInContext('__linies.map(detallLinia)', ctx);
// Sense cap avís vermell (la riera, l'incendi i el Pla Alfa 4 ho són), per veure quan es plega.
vm.runInContext(`HISTORIAL_PERILL = ${JSON.stringify(historial.filter((e) => e.tipus !== 'riera'))};`, ctx);
ctx.__pocs = { ...dades, entorn: null };
ctx.__mes = { ...ctx.__pocs, riscos: [{ ...dades.riscos[0], nivell: 'taronja' }] };
ctx.__vermell = { ...ctx.__pocs, entorn: dades.entorn };
// A la portada, sempre plegat (20-10-2026), també amb un «Nou» o un vermell.
const portada = (nom) => vm.runInContext(
  `LLEGITS_ABANS = null; PLEC_AVISOS = null; blocAvisos(${nom}).fills[0]`, ctx);
const plec = [portada('__vermell').tag, (portada('__pocs'), portada('__pocs').open), portada('__mes').open,
  portada('__vermell').open];
console.log(JSON.stringify({ text: bloc.textContent, curts: bloc.fills[0].textContent, detalls: detalls(bloc),
  sensePla, linies: liniesFitxa, plec }));
"""


if __name__ == "__main__":
    unittest.main()
