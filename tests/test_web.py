# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del JavaScript de la web (sin red ni navegador): el texto de los
avisos de la página de casa, la hora en que la página vuelve a leer los
datos y la ropa de «Si surts». Necesita Node."""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
sys.path.insert(0, os.path.dirname(WEB))
import config as C  # noqa: E402

# Carga comu.js y casa.js con un DOM mínimo y evalúa una expresión con la
# hora «ara» fijada.
ARNES = r"""
const vm = require('vm');
const fs = require('fs');
const [web, ara, expr, pagina] = process.argv.slice(1);
const RealDate = Date;
class FakeDate extends RealDate {
  constructor(...a) { super(...(a.length ? a : [ara])); }
  static now() { return new RealDate(ara).getTime(); }
}
const el = () => ({ setAttribute() {}, addEventListener() {}, append() {}, after() {}, replaceChildren() {}, classList: { add() {} },
  querySelector: () => ({ setAttribute() {} }), dataset: {}, style: { setProperty() {} } });
const ctx = vm.createContext({
  Date: FakeDate, Math, JSON, Number, Object, Set, URL, URLSearchParams, console,
  document: { querySelectorAll: () => [], getElementById: el, createElement: el, createElementNS: el, addEventListener() {},
    documentElement: { dataset: {} } },
  matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, AbortController,
  localStorage: { getItem: () => null, setItem() {} }, navigator: {}, location: { pathname: '/', hash: '' },
  history: { replaceState() {} }, window: { addEventListener() {} }, setInterval: () => 0, clearInterval() {},
  fetch: () => new Promise(() => {}), setTimeout: () => 0, clearTimeout() {},
});
for (const f of ['comu.js', ...(['casa.js', 'consultes.js', 'fiabilitat.js'].includes(pagina) ? ['grafica.js'] : []), pagina]) vm.runInContext(fs.readFileSync(`${web}/${f}`, 'utf8'), ctx);
console.log(JSON.stringify(vm.runInContext(expr, ctx)));
"""

# Lo mismo, pero la expresión puede devolver una promesa, «fetch» se puede
# sustituir desde la expresión y los temporizadores largos de la página (un
# minuto o más) se disparan enseguida, para seguir el ciclo de «carrega» sin
# esperar; los cortos (los de la propia prueba) se respetan.
ARNES_ASYNC = ARNES.replace("fetch: () => new Promise(() => {}), setTimeout: () => 0, clearTimeout() {},",
                            "fetch: () => new Promise(() => {}), setTimeout: (f, ms) => setTimeout(f, ms >= 1000 ? 0 : ms),"
                            " clearTimeout() {},") \
    .replace("console.log(JSON.stringify(vm.runInContext(expr, ctx)));",
             "Promise.resolve(vm.runInContext(expr, ctx)).then((v) => console.log(JSON.stringify(v)));")


# Carga sw.js con un «self» de mentira y evalúa una expresión con la hora «ara».
ARNES_SW = r"""
const vm = require('vm');
const fs = require('fs');
const [web, ara, expr] = process.argv.slice(1);
const RealDate = Date;
class FakeDate extends RealDate {
  constructor(...a) { super(...(a.length ? a : [ara])); }
  static now() { return new RealDate(ara).getTime(); }
}
const ctx = vm.createContext({ Date: FakeDate, URL, JSON, String, console, location: { origin: 'https://m.test' },
  self: { addEventListener() {}, registration: { scope: 'https://m.test/' } } });
vm.runInContext(fs.readFileSync(`${web}/sw.js`, 'utf8'), ctx);
console.log(JSON.stringify(vm.runInContext(expr, ctx)));
"""


def avis(inicio, fin, tipo, nivel="groc"):
    return {"inicio": inicio, "fin": fin, "tipo": tipo, "nivel": nivel,
            "zona": "Prelitoral de Barcelona"}


@unittest.skipUnless(shutil.which("node"), "cal Node")
class Web(unittest.TestCase):
    def avalua(self, ara, expr, pagina="casa.js", arnes=ARNES):
        r = subprocess.run(["node", "-e", arnes, WEB, ara, expr, pagina], capture_output=True,
                           text=True, check=True, env={**os.environ, "TZ": "Europe/Madrid"})
        return json.loads(r.stdout)

    # Un «fetch» de mentira: a cada petición (por orden) le toca una respuesta:
    # un objeto (JSON con 200), «null» (error de red) o «'penja'» (no contesta).
    def fetch_fals(self, respostes):
        return (f"peticions = []; respostes = {json.dumps(respostes)};"
                "fetch = (url) => { peticions.push(url.split('?')[0]); const r = respostes.shift();"
                " if (r === 'penja') return new Promise(() => {});"
                " if (r === null) return Promise.reject(new Error('xarxa'));"
                " return Promise.resolve({ ok: true, json: () => Promise.resolve(r) }); };")

    def text(self, ara, avisos):
        return self.avalua(ara, f"textAvisos({json.dumps(avisos)}, new Date())")

    def test_avisos_de_avui_i_dema(self):
        # El cas del 05-10-2026: un avís avui i dos demà, que la pàgina
        # donava com tres avisos d'avui.
        avisos = [
            avis("2026-10-05T05:00:00+02:00", "2026-10-05T19:59:59+02:00", "tempestes"),
            avis("2026-10-05T10:00:00+02:00", "2026-10-05T19:59:59+02:00", "pluja"),
            avis("2026-10-06T09:00:00+02:00", "2026-10-06T17:59:59+02:00", "pluja"),
            avis("2026-10-06T09:00:00+02:00", "2026-10-06T17:59:59+02:00", "tempestes"),
            avis("2026-10-06T22:00:00+02:00", "2026-10-06T23:59:59+02:00", "pluja"),
            avis("2026-10-06T22:00:00+02:00", "2026-10-06T23:59:59+02:00", "tempestes"),
        ]
        self.assertEqual(
            self.text("2026-10-05T16:41:00+02:00", avisos),
            "AEMET: avís groc per pluja i tempestes al Vallès: avui fins a les 20:00; "
            "demà de 09:00 a 18:00 i de 22:00 a mitjanit.")

    def test_tipus_i_nivells_diferents(self):
        avisos = [
            avis("2026-10-05T18:00:00+02:00", "2026-10-05T23:59:59+02:00", "pluja", "taronja"),
            avis("2026-10-05T10:00:00+02:00", "2026-10-06T11:59:59+02:00", "tempestes"),
            avis("2026-10-07T11:00:00+02:00", "2026-10-07T13:59:59+02:00", "pluja"),
        ]
        self.assertEqual(
            self.text("2026-10-05T16:41:00+02:00", avisos),
            "AEMET: avís taronja per pluja al Vallès: avui de 18:00 a mitjanit. "
            "AEMET: avís groc per tempestes al Vallès: fins demà a les 12:00. "
            "AEMET: avís groc per pluja al Vallès: dimecres d’11:00 a 14:00.")

    def test_franges_seguides_i_acabades(self):
        # Dues franges que es toquen fan una sola; la que ja ha acabat no surt.
        avisos = [
            avis("2026-10-05T07:00:00+02:00", "2026-10-05T09:59:59+02:00", "pluja", "vermell"),
            avis("2026-10-05T18:00:00+02:00", "2026-10-05T19:59:59+02:00", "pluja"),
            avis("2026-10-05T20:00:00+02:00", "2026-10-05T22:59:59+02:00", "pluja"),
        ]
        self.assertEqual(
            self.text("2026-10-05T16:41:00+02:00", avisos),
            "AEMET: avís groc per pluja al Vallès: avui de 18:00 a 23:00.")

    def test_fase_de_proteccio_civil_amb_apostrof(self):
        # «d’alerta» i «d’emergència», però «de prealerta» (abans sortia «d’prealerta»).
        ara = "2026-10-07T13:00:00+02:00"
        self.assertEqual(self.avalua(ara, "deFase('prealerta')"), "de prealerta")
        self.assertEqual(self.avalua(ara, "deFase('alerta')"), "d’alerta")
        self.assertEqual(self.avalua(ara, "deFase('emergència')"), "d’emergència")

    def test_el_cel_surt_de_la_probabilitat(self):
        # ADR 0021: els mil·límetres del model més plujós no fan «pluja» si la
        # probabilitat és baixa (el cas del 06-10-2026: «Pluja feble» amb un 2 %).
        def cel(**f):
            fila = {"hora": "2026-10-06T15:00", "codi": 3, "nuvols": 100, **f}
            return self.avalua("2026-10-06T13:00:00+02:00", f"cel({json.dumps(fila)})[0]")
        self.assertEqual(cel(pluja_mm=0.3, probabilitat=0.02), "Cobert")
        self.assertEqual(cel(pluja_mm=0.3, probabilitat=0.2), "Possible pluja")
        self.assertEqual(cel(pluja_mm=0.3, probabilitat=0.5), "Pluja feble")
        # Intensitats del manual d'estil de Meteocat, en una hora (ADR 0043).
        self.assertEqual(cel(pluja_mm=5, probabilitat=0.6), "Pluja feble")
        self.assertEqual(cel(pluja_mm=8, probabilitat=0.9), "Pluja moderada")
        self.assertEqual(cel(pluja_mm=45, probabilitat=0.9), "Pluja forta")
        self.assertEqual(cel(pluja_mm=90, probabilitat=0.9), "Pluja torrencial")
        self.assertEqual(cel(pluja_mm=5, probabilitat=0.9, codi=95), "Tempesta")
        self.assertEqual(cel(pluja_mm=5, probabilitat=0.9, codi=96), "Tempesta amb calamarsa")
        self.assertEqual(cel(pluja_mm=1, probabilitat=0.9, codi=73, neu=0.5), "Neu feble")
        self.assertEqual(cel(pluja_mm=5, probabilitat=0.9, codi=75, neu=3), "Neu moderada")
        self.assertEqual(cel(pluja_mm=12, probabilitat=0.9, codi=75, neu=12), "Neu forta")
        self.assertEqual(cel(pluja_mm=1, probabilitat=0.3, codi=71, neu=0.5), "Possible neu")
        self.assertEqual(cel(pluja_mm=2, probabilitat=0.9, codi=66), "Pluja gelant")
        self.assertEqual(cel(pluja_mm=0, probabilitat=0.01, nuvols=30), "Poc ennuvolat")
        self.assertEqual(cel(pluja_mm=0, probabilitat=0.01, nuvols=60), "Mig ennuvolat")
        self.assertEqual(cel(pluja_mm=0, probabilitat=0.01, nuvols=75), "Molt ennuvolat")
        self.assertEqual(cel(pluja_mm=2, probabilitat=0.3, codi=95), "Possible tempesta")
        self.assertEqual(cel(pluja_mm=2, probabilitat=0.05, codi=95), "Cobert")
        # Amb pluja d'algun model (0,2 mm o més), mai «Serè»: com a mínim núvols
        # (el cas del 07-10-2026: «Serè» amb 0,4 mm i un 13 %).
        self.assertEqual(cel(pluja_mm=0.4, probabilitat=0.13, nuvols=0), "Mig ennuvolat")
        self.assertEqual(cel(pluja_mm=0.4, probabilitat=0.13, nuvols=90), "Cobert")
        self.assertEqual(cel(pluja_mm=0.1, probabilitat=0.05, nuvols=0), "Serè")
        self.assertEqual(cel(pluja_mm=0, probabilitat=0.01, nuvols=10), "Serè")
        # Sense probabilitat, manen els mil·límetres, com abans.
        self.assertEqual(cel(pluja_mm=0.3, probabilitat=None), "Pluja feble")
        self.assertEqual(self.avalua("2026-10-06T13:00:00+02:00",
                                     "plujaHora({plou_ara: true, probabilitat: 1, pluja_mm: 0})"), "pluja")

    def roba(self, mitja, anada, tornada, pluja=False):
        tram = [{"hora": f"2026-10-07T{h:02d}:00", "temperatura": t, "vent": v}
                for h, t, v in (anada, tornada)]
        return self.avalua("2026-10-07T08:00:00+02:00",
                           f"roba({json.dumps(mitja)}, {json.dumps(tram)}, {json.dumps(pluja)})", "sortir.js")

    def test_roba_a_peu(self):
        # Trams de la temperatura que es nota, sense vent.
        casos = [(28, "Màniga curta."), (23, "Màniga curta o màniga llarga fina."),
                 (19, "Màniga llarga o jersei fi."), (16, "Jaqueta lleugera o jersei."),
                 (12, "Jaqueta."), (8, "Abric."), (3, "Abric, bufanda i guants."),
                 (-1, "Abric, gorro, bufanda i guants.")]
        for t, text in casos:
            self.assertEqual(self.roba("peu", (9, t, 0), (11, t, 0)), text)

    def test_roba_amb_vent_a_peu(self):
        # 8 °C amb 30 km/h es noten com 4 °C (índex d'Environment Canada).
        self.assertEqual(self.roba("peu", (9, 8, 30), (11, 8, 30)),
                         "Abric, bufanda i guants. Amb vent de 30\u00a0km/h, 8\u00a0°C es noten com 4\u00a0°C.")

    def test_roba_diferent_a_la_tornada(self):
        self.assertEqual(self.roba("peu", (16, 26, 5), (21, 15, 5)),
                         "Màniga curta. A la tornada (21\u00a0h, 15\u00a0°C): jaqueta lleugera o jersei.")
        # En moto, una sola jaqueta: la del moment més fred.
        self.assertEqual(self.roba("moto", (16, 26, 5), (21, 15, 5)),
                         "Jaqueta de moto amb folre i guants d’entretemps.")

    def test_resum_per_trams_del_dia(self):
        # Juanjo, 08-10-2026: probabilitat de pluja i fenòmens destacables per matí, tarda i nit.
        def fila(h, prob, mm, t, ratxa=10, codi=0, neu=0):
            dia = "2026-10-08" if h < 24 else "2026-10-09"
            return {"hora": f"{dia}T{h % 24:02d}:00", "fins": f"{'2026-10-09' if h + 1 >= 24 else dia}T{(h + 1) % 24:02d}:00",
                    "probabilitat": prob, "pluja_mm": mm, "temperatura": t, "ratxa": ratxa, "codi": codi, "neu": neu, "avisos": []}
        hores = ([fila(h, 0.1, 0.2, 17 + h - 9) for h in range(9, 14)]      # matí: 17–21 °C
                 + [fila(h, 0.8 if h == 16 else 0.3, 45 if h == 16 else 2, 22, 75 if h == 15 else 20, 95 if h == 16 else 0) for h in range(14, 21)]
                 + [fila(h, 0.05, 0, -1 if h == 23 else 5, 10, 0, 0.5 if h == 22 else 0) for h in range(21, 31)]
                 + [fila(31, 0.2, 0.5, 37)])
        r = self.avalua("2026-10-08T09:30:00+02:00", f"resumTrams({json.dumps(hores)}, new Date())")
        # Juanjo, 09-10-2026: tots els trams de la previsió, cadascun desplegable; l'últim, fins on arriben les hores.
        self.assertEqual([(t["nom"], t["hores"]) for t in r],
                         [("Matí", "fins a les 14 h"), ("Tarda", "14–21 h"), ("Nit", "21–7 h"), ("Demà matí", "7–8 h")])
        self.assertEqual((r[0]["prob"], r[0]["tMin"], r[0]["tMax"], r[0]["fenomens"]), (0.1, 17, 21, []))
        # Juanjo, 09-10-2026: la pluja, només si va a ploure (alguna hora amb un 20 % o més).
        self.assertEqual([t["plou"] for t in r], [False, True, False, True])
        self.assertEqual([f[0] for f in r[1]["fenomens"]], ["tempesta", "pluja forta", "ratxes de 75\u00a0km/h"])
        # La quantitat del tram és l'esperada: 0,8·45 + 6·0,3·2 (ADR 0103); abans, la suma, 57.
        self.assertAlmostEqual(r[1]["mm"], 39.6)
        self.assertEqual([f[0] for f in r[2]["fenomens"]], ["neu", "glaçada"])
        # A la nit, surten la nit i els trams de demà.
        r = self.avalua("2026-10-08T22:30:00+02:00", f"resumTrams({json.dumps(hores)}, new Date())")
        self.assertEqual([t["nom"] for t in r], ["Nit", "Demà matí"])
        self.assertEqual([f[0] for f in r[1]["fenomens"]], ["calor"])
        self.assertEqual(self.avalua("2026-10-08T22:30:00+02:00", f"resumTrams({json.dumps(hores)}, new Date())", "casa.js", ARNES)[0]["hores"], "fins a les 7 h")

    def test_frase_de_dalt_de_la_portada(self):
        # La conclusió d'«Ara» (ADR 0118): el cel dels dos trams que venen, amb
        # les peces de la taula; el mateix cel, en una sola frase.
        def fila(h, nuvols, prob=0.0, avisos=()):
            dia, fi = ("2026-10-21" if h < 24 else "2026-10-22"), h + 1
            return {"hora": f"{dia}T{h % 24:02d}:00", "fins": f"{'2026-10-22' if fi >= 24 else dia}T{fi % 24:02d}:00",
                    "probabilitat": prob, "pluja_mm": 0, "temperatura": 15, "nuvols": nuvols,
                    "avisos": [{"nivell": "groc", "tipus": list(avisos)}] if avisos else []}
        hores = [fila(h, 60) for h in range(15, 21)] + [fila(h, 90) for h in range(21, 31)] \
            + [fila(h, 90) for h in range(31, 38)]
        frase = self.avalua("2026-10-21T15:30:00+02:00", f"fraseCelAra({json.dumps(hores)}, new Date())")
        self.assertEqual(frase, "Aquesta tarda, fresc i mig ennuvolat; aquesta nit, encara fresc i cobert.")
        # A les 20:30 la tarda ja no és la que ve: la nit i demà al matí, amb el mateix cel.
        frase = self.avalua("2026-10-21T20:30:00+02:00", f"fraseCelAra({json.dumps(hores)}, new Date())")
        self.assertEqual(frase, "Aquesta nit i demà al matí, fresc i cobert.")
        # Un avís de pluja en les 24 hores, encara que els models no en vegin.
        self.assertFalse(self.avalua("2026-10-21T15:30:00+02:00", f"avisDePluja({json.dumps(hores)}, new Date())"))
        hores[10] = fila(25, 90, avisos=("pluja",))
        self.assertTrue(self.avalua("2026-10-21T15:30:00+02:00", f"avisDePluja({json.dumps(hores)}, new Date())"))
        hores[10] = fila(25, 90, avisos=("vent",))
        self.assertFalse(self.avalua("2026-10-21T15:30:00+02:00", f"avisDePluja({json.dumps(hores)}, new Date())"))

    def test_la_frase_de_dalt_diu_com_es_nota(self):
        # Juanjo, 22-10-2026: si fa fred o calor, en paraules i sense xifres; els
        # seus set nivells (fred intens sota 0, molt fred de 0 a 5, fred de 6 a 11,
        # fresc de 12 a 17, agradable de 18 a 25, calor de 26 a 32, molta calor
        # des de 33), amb la mínima a la nit i la màxima a la tarda.
        def frase(tarda, nit, vent=0):
            hores = [{"hora": f"2026-10-21T{h:02d}:00", "fins": f"2026-10-21T{h + 1:02d}:00", "probabilitat": 0,
                      "pluja_mm": 0, "nuvols": 0, "vent": vent, "avisos": [], "temperatura": t}
                     for h, t in zip(range(15, 21), tarda)]
            hores += [{"hora": f"2026-10-{21 + (h >= 24)}T{h % 24:02d}:00",
                       "fins": f"2026-10-{21 + (h + 1 >= 24)}T{(h + 1) % 24:02d}:00", "probabilitat": 0,
                       "pluja_mm": 0, "nuvols": 0, "vent": vent, "avisos": [], "temperatura": t}
                      for h, t in zip(range(21, 31), nit)]
            return self.avalua("2026-10-21T15:30:00+02:00", f"fraseCelAra({json.dumps(hores)}, new Date())")
        self.assertEqual(frase([20, 25.4, 22, 21, 20, 19], [17] * 10),
                         "Aquesta tarda, temperatura agradable i serè; aquesta nit, fresc i serè.")
        self.assertEqual(frase([24, 26, 25, 24, 23, 22], [22, 21, 20, 18.6, 20, 21, 22, 22, 22, 22]),
                         "Aquesta tarda, amb calor i serè; aquesta nit, temperatura agradable i serè.")
        self.assertEqual(frase([30, 33, 32, 31, 29, 28], [26] * 10),
                         "Aquesta tarda, amb molta calor i serè; aquesta nit, amb calor i serè.")
        self.assertEqual(frase([12, 16, 13, 12, 12, 12], [11, 9, 8, 7, 6, 6, 7, 8, 9, 10]),
                         "Aquesta tarda, fresc i serè; aquesta nit, fred i serè.")
        self.assertEqual(frase([8, 11, 10, 9, 8, 8], [5, 3, 1, 0.4, 1, 2, 3, 4, 5, 6]),
                         "Aquesta tarda, fred i serè; aquesta nit, amb molt de fred i serè.")
        self.assertEqual(frase([4, 5, 4, 3, 2, 1], [0, -1, -0.6, -2, -1, 0, 1, 2, 3, 4]),
                         "Aquesta tarda, amb molt de fred i serè; aquesta nit, amb fred intens i serè.")
        # Amb vent, el que es nota: 6,5 °C amb 20 km/h es noten com 3 °C. A la
        # tarda, amb més de 10 °C, el vent no hi compta.
        self.assertEqual(frase([14, 15, 14, 13, 12, 12], [6.5] * 10, vent=20),
                         "Aquesta tarda, fresc i serè; aquesta nit, amb molt de fred i serè.")

    def test_el_radar_va_sota_la_grafica(self):
        # Juanjo, 22-10-2026: «prefiero que salga bajo la gráfica». A «Ara» en
        # queda la conclusió, perquè la pluja que arriba es vegi en obrir.
        dom = ("const nou = (t) => ({ tag: t, fills: [], className: '', setAttribute() {}, addEventListener() {},"
               " classList: Object.assign([], { add() {}, remove() {} }), dataset: {}, style: { setProperty() {} },"
               " append(...c) { this.fills.push(...c); }, prepend(...c) { this.fills.unshift(...c); },"
               " get textContent() { return this.fills.map((f) => (typeof f === 'string' ? f : f.textContent)).join(''); },"
               " set textContent(v) { this.fills = [v]; } });"
               "document.createElement = nou; document.createElementNS = (ns, t) => nou(t);")
        hores = [{"hora": f"2026-10-21T{h:02d}:00", "fins": f"2026-10-21T{h + 1:02d}:00", "probabilitat": 0,
                  "pluja_mm": 0, "nuvols": 90, "avisos": [], "temperatura": 15} for h in range(15, 24)]
        radar = {"arriba": "2026-10-21T15:55:00+02:00", "hora": "2026-10-21T15:20:00+02:00", "pluja": {"estat": "arriba"}}
        linies = self.avalua("2026-10-21T15:30:00+02:00",
                             dom + f"titularAra({json.dumps(hores)}, {json.dumps(radar)}, false).fills"
                             ".map((f) => [f.className, f.textContent])")
        self.assertEqual(linies[1], ["resum-linia pluja-radar", "Pluja d’aquí a 25 minuts (cap a les\u00a015:55)."])

    def test_al_mati_tambe_com_es_nota_despres(self):
        # Juanjo, 22-10-2026: la mínima del matí és la de l'alba, i si després
        # escalfa fins a una altra paraula, també es diu.
        def frase(nit, mati):
            hores = [{"hora": f"2026-10-{21 + (h >= 24)}T{h % 24:02d}:00",
                      "fins": f"2026-10-{21 + (h + 1 >= 24)}T{(h + 1) % 24:02d}:00", "probabilitat": 0,
                      "pluja_mm": 0, "nuvols": 0, "vent": 0, "avisos": [], "temperatura": t}
                     for h, t in zip(range(21, 38), nit + mati)]
            return self.avalua("2026-10-21T21:30:00+02:00", f"fraseCelAra({json.dumps(hores)}, new Date())")
        # El 6 d'octubre de 2026: de 16 °C a les 7 a 23 °C a les 13.
        self.assertEqual(frase([19, 18, 17, 17, 17, 16, 16, 16, 16, 16], [16, 17, 18, 20, 22, 22, 23]),
                         "Aquesta nit, fresc i serè; demà al matí, encara fresc i després agradable, i serè.")
        self.assertEqual(frase([14] * 10, [8, 9, 12, 18, 24, 27, 28]),
                         "Aquesta nit, fresc i serè; demà al matí, fred i després amb calor, i serè.")
        # Sense canvi de paraula, com abans.
        self.assertEqual(frase([16] * 10, [14, 15, 16, 16, 17, 17, 17]), "Aquesta nit i demà al matí, fresc i serè.")
        # Un matí que es refreda no escalfa: la mínima, al final, i res més.
        self.assertEqual(frase([22] * 10, [21, 20, 18, 16, 15, 14, 14]),
                         "Aquesta nit, temperatura agradable i serè; demà al matí, fresc i serè.")

    def test_l_hora_de_les_dades_es_la_d_arribada_al_servidor(self):
        # Juanjo, 22-10-2026: «la primera puede ser la hora real de carga de datos».
        ara = "2026-10-22T11:50:00+02:00"
        hora = lambda d: self.avalua(ara, f"horaDades({json.dumps(d)}).toISOString()")  # noqa: E731
        self.assertEqual(hora({"generat": "2026-10-22T11:45+02:00", "publicat_servidor": "2026-10-22T09:46:39.000Z"}),
                         "2026-10-22T09:46:39.000Z")
        # Sense la capçalera, o si no quadra, la del càlcul.
        self.assertEqual(hora({"generat": "2026-10-22T11:45+02:00"}), "2026-10-22T09:45:00.000Z")
        self.assertEqual(hora({"generat": "2026-10-22T11:45+02:00", "publicat_servidor": "2026-10-22T10:46:00.000Z"}),
                         "2026-10-22T09:45:00.000Z")

    def test_el_fons_i_el_dibuix_d_ara_segons_el_cel(self):
        # Juanjo, 22-10-2026 (ADR 0121): el fons i el dibuix, del cel del primer
        # tram; de nit, a l'alba i a la posta, segons l'altura del sol; si plou, la pluja.
        def cel(ara, nuvols, plou=False, codi=3, boira=False):
            hores = [{"hora": f"2026-10-{21 + (h >= 24)}T{h % 24:02d}:00",
                      "fins": f"2026-10-{21 + (h + 1 >= 24)}T{(h + 1) % 24:02d}:00", "probabilitat": 0, "pluja_mm": 0,
                      "nuvols": nuvols, "vent": 0, "avisos": [], "temperatura": 15, "codi": 45 if boira else codi}
                     for h in range(6, 34)]
            return self.avalua(ara, f"celPortada({json.dumps(hores)}, {json.dumps(plou)}, null, new Date())")
        mati, tarda, nit = "2026-10-21T10:30:00+02:00", "2026-10-21T15:30:00+02:00", "2026-10-21T23:30:00+02:00"
        self.assertEqual(cel(tarda, 5), {"fons": "sere", "dibuix": "clear-day"})
        self.assertEqual(cel(tarda, 30), {"fons": "poc", "dibuix": "partly-cloudy-day"})
        self.assertEqual(cel(tarda, 75), {"fons": "nuvol", "dibuix": "cloudy"})
        self.assertEqual(cel(tarda, 95), {"fons": "cobert", "dibuix": "overcast"})
        self.assertEqual(cel(mati, 95, boira=True), {"fons": "boira", "dibuix": "fog"})
        self.assertEqual(cel(tarda, 95, plou=True), {"fons": "pluja", "dibuix": "rain"})
        self.assertEqual(cel(tarda, 95, plou=True, codi=95), {"fons": "tempesta", "dibuix": "thunderstorms-rain"})
        self.assertEqual(cel(nit, 5), {"fons": "nit", "dibuix": "starry-night"})
        self.assertEqual(cel(nit, 30), {"fons": "nitnuvol", "dibuix": "partly-cloudy-night"})
        self.assertEqual(cel(nit, 95), {"fons": "nitcobert", "dibuix": "overcast-night"})
        # El 21-10-2026 el sol es pon a Montflorit cap a les 18:50 i surt cap a les 8:10.
        self.assertEqual(cel("2026-10-21T18:45:00+02:00", 5), {"fons": "albasere", "dibuix": "sunset"})
        self.assertEqual(cel("2026-10-21T08:10:00+02:00", 5), {"fons": "albasere", "dibuix": "sunrise"})
        self.assertEqual(cel("2026-10-21T18:45:00+02:00", 95, plou=True), {"fons": "albapluja", "dibuix": "rain"})

    def test_la_riera_a_la_portada_nomes_si_anuncia_alguna_cosa(self):
        # Juanjo, 21-10-2026: «que solo aparezcan cuando anuncien algo».
        ara = "2026-10-21T20:30:00+02:00"
        self.assertIsNone(self.avalua(ara, "estatPortada({riera: {nivell: null, mm_6h: 0}})"))
        self.assertIsNotNone(self.avalua(ara, "estatPortada({riera: {nivell: 'registre', mm_6h: 3.2}})"))
        # Si l'avís de la riera ja surt a dalt, no es repeteix.
        self.assertIsNone(self.avalua(ara, "HISTORIAL_PERILL = [{tipus: 'riera', clau: 'x', nivell: 'atencio',"
                                           " ca: 'Avís: risc a la riera'}]; estatPortada({riera: {nivell: 'atencio'}})"))

    def test_les_temperatures_de_la_zona_triada(self):
        # Juanjo, 23-10-2026 (ADR 0123): un botó tria la riera o la part alta, i totes les temperatures
        # en són; sense etiquetes «+2». La part alta, la riera més la diferència de cada hora (ADR 0087).
        def fila(h, t, dif):
            return {"hora": f"2026-10-08T{h:02d}:00", "fins": f"2026-10-08T{h + 1:02d}:00", "probabilitat": 0,
                    "pluja_mm": 0, "temperatura": t, "ratxa": 10, "codi": 0, "neu": 0, "avisos": [], "dif_alta": dif}
        hores = [fila(h, 20 + (h == 16) * 3, 1.8 if h == 16 else 0.3) for h in range(14, 21)] \
            + [fila(21, -1, 1.5), fila(22, 0.5, 0.2)]
        expr = f"resumTrams({json.dumps(hores)}, new Date()).map((t) => [t.tMax, t.tMin, t.fenomens.map((f) => f[0])])"
        riera = self.avalua("2026-10-08T13:30:00+02:00", expr)
        alta = self.avalua("2026-10-08T13:30:00+02:00", "ZONA = 'alta'; " + expr)
        self.assertEqual(riera[0][0], 23)
        self.assertAlmostEqual(alta[0][0], 24.8)                    # 23 + 1,8 a les 16 h
        # A la nit, −1 a la riera i 0,5 a dalt: a la riera, glaçada; a dalt, la de la riera, que s'hi passa.
        self.assertEqual(riera[1][2], ["glaçada"])
        self.assertEqual(alta[1][2], ["glaçada vora la riera"])
        self.assertEqual(self.avalua("2026-10-08T13:30:00+02:00", "ZONA = 'alta'; [tempZona({temperatura: 10, dif_alta: 2}),"
                                     " tempZona({temperatura: 10}), tempZona({temperatura: 10, dif_alta: 2, mesura: true})]"),
                         [12, 10, 10])
        # Al resum del dia del bot, «(fins a 26 °C a la part alta)» queda a part, per a l'etiqueta.
        r = self.avalua("2026-10-08T13:30:00+02:00",
                        "ambMarques([{t: 'Temperatura: entre 16 °C i 24 °C (fins a 26 °C a la part alta), semblant a la d\\'ahir.'}])")
        self.assertEqual([x.get("alta") or x.get("t") for x in r],
                         ["Temperatura: entre 16 °C i 24 °C", "fins a 26 °C a la part alta", ", semblant a la d'ahir."])

    def test_trams_oberts_de_sortida(self):
        # Juanjo, 09-10-2026: «no debería ser persistente?»: amb «Desplega-ho tot» desat, tots. Des del
        # 17-10-2026, la resta plegats, també els de perill (l'avís ja surt a la capçalera).
        trams = [{"clau": "a", "avis": False, "fenomens": []}, {"clau": "b", "avis": True, "fenomens": []},
                 {"clau": "c", "avis": False, "fenomens": [["calor", "i"]]}, {"clau": "d", "avis": False, "fenomens": []}]
        expr = f"{json.dumps(trams)}.map((t) => obertDeSortida(t))"
        self.assertEqual(self.avalua("2026-10-09T18:00:00+02:00", expr), [False] * 4)
        self.assertEqual(self.avalua("2026-10-09T18:00:00+02:00", "localStorage.getItem = () => '1'; " + expr), [True] * 4)
        # El que s'ha obert o tancat a mà mana mentre la pàgina és oberta.
        self.assertEqual(self.avalua("2026-10-09T18:00:00+02:00", "obertsAMa.set('a', false); obertsAMa.set('d', true); " + expr),
                         [False, False, False, True])

    def test_cel_de_cada_tram(self):
        # El cel del tram, amb el seu nom i la seva icona: la mitjana dels núvols, i de nit, la lluna.
        def fila(h, nuvols, codi=0, mm=0):
            return {"hora": f"2026-10-08T{h:02d}:00", "fins": f"2026-10-08T{h + 1:02d}:00", "probabilitat": 0,
                    "pluja_mm": mm, "temperatura": 20, "nuvols": nuvols, "codi": codi, "avisos": []}
        hores = ([fila(h, 10) for h in range(9, 14)] + [fila(h, 40, 45 if h < 18 else 0) for h in range(14, 21)]
                 + [fila(h, 30) for h in range(21, 23)])
        r = self.avalua("2026-10-08T09:30:00+02:00", f"resumTrams({json.dumps(hores)}, new Date()).map((t) => t.cel)")
        self.assertEqual(r, [["Serè", "i-sun"], ["Boira", "i-cloud-fog"], ["Poc ennuvolat", "i-cloud-moon"]])
        # Si algun model hi posa pluja, com a mínim mig ennuvolat, com a la taula.
        r = self.avalua("2026-10-08T09:30:00+02:00",
                        f"resumTrams({json.dumps([fila(10, 10, mm=0.5)])}, new Date())[0].cel")
        self.assertEqual(r, ["Mig ennuvolat", "i-cloud"])

    def test_plans_del_color_de_la_fase_i_amb_el_que_vol_dir(self):
        # ADR 0051: la prealerta no espanta; el «?» desplega què vol dir cada fase.
        plans = [{"pla": "VENTCAT", "nom": "de vent", "fase": f} for f in ("prealerta", "alerta", "emergència")]
        r = self.avalua("2026-10-09T10:00:00+02:00", f"blocPlans({json.dumps(plans)}).map((p) => p.className)")
        self.assertEqual(r, ["avis-item prealerta", "avis-item taronja", "avis-item vermell"])
        r = self.avalua("2026-10-09T10:00:00+02:00",
                        "ajudaFase('prealerta').map((e) => [e.className, e.textContent, e.hidden === true])")
        self.assertEqual(r[0][:2], ["ajuda-fase", "?"])
        self.assertEqual(r[1], ["sentit-fase", "Es preveu un risc a mitjà termini. El pla no està activat: "
                                "només cal estar-ne pendent.", True])

    def test_les_franges_acabades_no_compten(self):
        hores = [{"hora": "2026-10-08T06:00", "fins": "2026-10-08T07:00"}, {"hora": "2026-10-08T07:00", "fins": "2026-10-08T08:00"},
                 {"hora": "2026-10-08T08:00", "fins": "2026-10-08T09:00"}]
        r = self.avalua("2026-10-08T07:44:00+02:00", f"horesVigents({json.dumps(hores)}, new Date()).map((f) => f.hora)", "sortir.js")
        self.assertEqual(r, ["2026-10-08T07:00", "2026-10-08T08:00"])
        self.assertEqual(self.avalua("2026-10-08T07:44:00+02:00", "horesVigents(null, new Date())", "sortir.js"), [])

    def test_graus_mes_o_menys_que_ahir_igual_que_el_bot(self):
        # ADR 0061: la web i el bot fan el mateix compte.
        sys.path.insert(0, os.path.join(os.path.dirname(WEB), "bot"))
        import bot as B
        def fila(dia, h, t):
            return {"hora": f"2026-10-{dia}T{h:02d}:00", "fins": f"2026-10-{dia}T{h + 1:02d}:00", "temperatura": t}
        avui = [fila(10, 14, 20.0), fila(10, 15, 23.4)]
        dema = [fila(11, 15, 18.0)]
        mes = {"2026-10-09T14:00": 19.0, "2026-10-09T15:00": 20.0, "2026-10-09T16:00": 21.0}
        casos = [(avui, False, mes), (avui, True, mes), (dema, False, mes), (dema, False, {}),
                 (avui, False, {"2026-10-09T14:00": 19.0})]
        for files, nit, m in casos:
            js = self.avalua("2026-10-10T13:00:00+02:00", f"comparaTemp({json.dumps(files)}, {json.dumps(nit)}, {json.dumps(m)}, {json.dumps(avui + dema)})")
            self.assertEqual(js, B.compara_temp({"temperatura_mesurada": m, "hores": avui + dema}, files, nit))
        self.assertEqual(self.avalua("2026-10-10T13:00:00+02:00", "[textComparacio(3, false), textComparacio(-2, true), textComparacio(1, false), textComparacio(null, false)]"),
                         ["3° més que ahir", "2° menys que avui", "semblant a ahir", None])
        # A la capçalera del tram, al costat de la temperatura.
        hores = [{**fila(10, h, 20.0 + h - 14), "codi": 0, "nuvols": 0} for h in range(14, 21)]
        mes = {f"2026-10-09T{h:02d}:00": 15.0 for h in range(14, 22)}
        r = self.avalua("2026-10-10T13:30:00+02:00", f"resumTrams({json.dumps(hores)}, new Date(), {json.dumps(mes)}).map((t) => t.compara)")
        self.assertEqual(r, ["11° més que ahir"])                          # 26,5 contra 15

    def test_el_dia_com_l_anterior_a_ara_igual_que_el_bot(self):
        # Juanjo, 23-10-2026: «si el día es como el de ayer, más frío, más cálido».
        # La mateixa xifra que la línia de la temperatura del resum del bot.
        sys.path.insert(0, os.path.join(os.path.dirname(WEB), "bot"))
        import bot as B
        def fila(dia, h, t):
            return {"hora": f"2026-10-{dia}T{h:02d}:00", "fins": f"2026-10-{dia}T{h + 1:02d}:00", "temperatura": t}
        hores = [fila(10, h, 14.0 + h % 7) for h in range(9, 24)] + [fila(11, h, 11.0 + h % 5) for h in range(0, 22)]
        mes = {f"2026-10-09T{h:02d}:00": 15.0 for h in range(0, 24)} | {f"2026-10-10T{h:02d}:00": 16.0 for h in range(0, 10)}
        d = {"temperatura_mesurada": mes, "hores": hores}
        mati = self.avalua("2026-10-10T09:30:00+02:00", f"comparaDia({json.dumps(hores)}, {json.dumps(mes)}, new Date())")
        self.assertEqual(mati["text"], "Avui, 5° més que ahir")             # 20 contra 15
        # A la part alta, amb el que van mesurar ahir les estacions de dalt (ADR 0123).
        alta = [{**f, "dif_alta": 1.0} for f in hores]
        mesalta = {k: v + 3 for k, v in mes.items()}
        r = self.avalua("2026-10-10T09:30:00+02:00", f"ZONA = 'alta'; comparaDia({json.dumps(alta)}, {json.dumps(mesalta)}, new Date())")
        self.assertEqual(r["text"], "Avui, 3° més que ahir")                   # 21 contra 18
        self.assertIn("estacions de la part alta", r["explica"])
        self.assertEqual(B.compara_resum(d, [f for f in hores if f["hora"] < "2026-10-11"]), 5)
        # Des de les 18 h, demà contra avui, com el resum, que llavors passa a demà.
        vespre = self.avalua("2026-10-10T19:30:00+02:00", f"comparaDia({json.dumps(hores)}, {json.dumps(mes)}, new Date())")
        self.assertEqual(vespre["text"], "Demà, 5° menys que avui")          # 15 contra 20
        self.assertEqual(B.compara_resum(d, [f for f in hores if "2026-10-11T06" <= f["hora"] < "2026-10-12"]), -5)
        # Sense l'estació (la reserva), res.
        self.assertIsNone(self.avalua("2026-10-10T09:30:00+02:00", f"comparaDia({json.dumps(hores)}, null, new Date())"))
        # En prémer-la, què compara (etiquetaAlta amb «explica»); com la part alta.
        r = self.avalua("2026-10-10T09:30:00+02:00", "etiquetaAlta('Avui', false, 'La màxima…').dataset.explica")
        self.assertEqual(r, "La màxima…")

    def test_la_setmana_avui_i_dema_de_la_pagina_i_la_resta_d_ecmwf(self):
        # ADR 0122: avui i demà, de la previsió de la pàgina (com la gràfica i els trams); la resta, de setmana.py.
        def fila(dia, h, t, p=0.0, mm=0.0):
            return {"hora": f"2026-10-{dia}T{h:02d}:00", "fins": f"2026-10-{dia}T{h + 1:02d}:00", "temperatura": t,
                    "probabilitat": p, "pluja_mm": mm, "nuvols": 10, "codi": 3}
        hores = [fila(23, h, 15.0 + (h == 15) * 5) for h in range(9, 24)] \
            + [fila(24, h, 12.0, 0.6 if h == 12 else 0.0, 2.0 if h == 12 else 0.0) for h in range(0, 21)]
        mesurada = {"2026-10-23T06:00": 9.0, "2026-10-23T08:00": 11.0}
        setmana = [{"dia": f"2026-10-{d}", "max": 30.0, "min": 1.0, "nuvols": 90, "codi": 3, "probabilitat": p, "pluja_mm": 3.0}
                   for d, p in zip(range(22, 30), (0, 0, 0, 0.6, 0.3, 0.1, 0, 0))]
        dades = {"hores": hores, "temperatura_mesurada": mesurada, "setmana": setmana}
        r = self.avalua("2026-10-23T09:30:00+02:00", f"diesSetmana({json.dumps(dades)}, new Date())"
                        ".map((d) => [d.dia, d.max, d.min, d.pluja, celDia(d)[1]])")
        self.assertEqual(r[0], ["2026-10-23", 20, 9, None, "i-sun"])          # amb la mínima ja mesurada
        self.assertEqual(r[1], ["2026-10-24", 12, 12, "pluja", "i-cloud-rain"])
        self.assertEqual(r[2], ["2026-10-25", 30, 1, "pluja", "i-cloud-rain"])  # d'ECMWF: 60 %
        self.assertEqual(r[3][3:], ["possible", "i-cloud-sun-rain"])              # 30 %
        self.assertEqual(r[4][3:], [None, "i-cloudy"])                              # 10 %: només el cel
        self.assertEqual(len(r), 7)                                                 # sense ahir
        # A la part alta (ADR 0123): avui i demà amb la diferència de cada hora i el mesurat a dalt; la
        # resta, amb la màxima i la mínima de la part alta de setmana.py.
        for f in hores:
            f["dif_alta"] = 2.0
        setmana[3].update(max_alta=32.0, min_alta=2.5)
        dades = {"hores": hores, "temperatura_mesurada": mesurada, "temperatura_mesurada_alta": {"2026-10-23T06:00": 10.5},
                 "setmana": setmana}
        r = self.avalua("2026-10-23T09:30:00+02:00", f"ZONA = 'alta'; diesSetmana({json.dumps(dades)}, new Date())"
                        ".map((d) => [d.max, d.min])")
        self.assertEqual(r[:3], [[22, 10.5], [14, 14], [32, 2.5]])
        self.assertEqual(r[3], [30, 1])                                             # sense part alta: la de la riera

        # Sense dades de la setmana (la reserva d'abans), no hi ha bloc.
        self.assertIsNone(self.avalua("2026-10-23T09:30:00+02:00", f"blocSetmana({json.dumps({'hores': hores})}, new Date())"))

    def test_el_cel_del_bot_es_el_de_la_web(self):
        # ADR 0065: la icona del cel als missatges del bot surt de la mateixa
        # regla que la taula de la web (cel de casa.js): les dues han de coincidir.
        sys.path.insert(0, os.path.join(os.path.dirname(WEB), "bot"))
        import bot as B
        files = []
        # De dia, al vespre (la posta, cap a les 19:15 l'octubre) i de nit.
        for dia, h in (("2026-10-10", 12), ("2026-10-10", 18), ("2026-10-10", 19), ("2026-10-10", 23),
                       ("2026-10-11", 7), ("2026-01-15", 17), ("2026-06-21", 21)):
            base = {"hora": f"{dia}T{h:02d}:00", "fins": f"{dia}T{h:02d}:59"}
            for nuvols in (0, 30, 60, 80, 95, None):
                files.append({**base, "nuvols": nuvols, "codi": 3, "probabilitat": 0.05, "pluja_mm": 0})
            files.append({**base, "nuvols": 10, "codi": 3, "probabilitat": 0.1, "pluja_mm": 0.4})   # mulla: núvols
            files.append({**base, "nuvols": 50, "codi": 45, "probabilitat": 0.0, "pluja_mm": 0})    # boira
            for p, mm, codi in ((0.3, 0.5, 61), (0.3, 0, 95), (0.3, 1, 73), (0.6, 0.5, 61), (0.6, 7, 63),
                                (0.6, 45, 65), (0.6, 90, 65), (0.6, 2, 95), (0.6, 2, 96), (0.6, 2, 75),
                                (0.6, 2, 66), (None, 0.3, 61), (None, 0.1, 61)):
                files.append({**base, "nuvols": 90, "codi": codi, "probabilitat": p, "pluja_mm": mm, "neu": 3})
            files.append({**base, "nuvols": 20, "codi": 1, "probabilitat": 0.0, "pluja_mm": 0, "plou_ara": True})
        js = self.avalua("2026-10-10T13:00:00+02:00", f"{json.dumps(files)}.map((f) => cel(f)[1])")
        self.assertEqual(js, [B.icona_cel(f) for f in files])
        # Cada icona de la web té el seu emoji, i de nit no surt el sol.
        self.assertTrue(set(js) - {None} <= set(B.EMOJI_CEL))
        self.assertEqual(B.emoji_cel(files[0]), "☀️")                      # dia 10, 12 h, serè
        nit = next(f for f in files if f["hora"] == "2026-10-10T23:00" and f["nuvols"] == 60)
        self.assertEqual(B.emoji_cel(nit), "☁️")

    def test_la_previsio_de_dema_tocada_despres_de_mitjanit(self):
        # La de les 21 h porta a «Demà»; si es toca quan aquell dia ja ha arribat, a «Avui».
        def desti(ara, url, dia):
            r = subprocess.run(["node", "-e", ARNES_SW, WEB, ara, f"destiAvis({json.dumps(url)}, {json.dumps(dia)})"],
                               capture_output=True, text=True, check=True, env={**os.environ, "TZ": "Europe/Madrid"})
            return json.loads(r.stdout)
        dema = "https://m.test/consultes.html#dema"
        self.assertEqual(desti("2026-10-10T21:30:00+02:00", dema, "2026-10-11"), dema)
        self.assertEqual(desti("2026-10-11T00:20:00+02:00", dema, "2026-10-11"), "https://m.test/consultes.html#avui")
        self.assertEqual(desti("2026-10-12T08:00:00+02:00", dema, "2026-10-11"), "https://m.test/consultes.html#avui")
        self.assertEqual(desti("2026-10-11T00:20:00+02:00", dema, None), dema)        # avisos d'abans, sense dia
        self.assertEqual(desti("2026-10-11T07:00:00+02:00", "https://m.test/", None), "https://m.test/")

    def test_zona_de_la_temperatura_de_les_opcions_velles(self):
        # Fins a la 3.173.2, dos interruptors; ara una zona (Juanjo, 21-10-2026).
        def zona(o):
            return self.avalua("2026-10-21T12:00:00+02:00", f"ambZona({json.dumps(o)})", "casa.js")
        self.assertEqual(zona({"alta": True, "baixa": False, "vent": True}), {"vent": True, "zona": "alta"})
        self.assertEqual(zona({"alta": True, "baixa": True})["zona"], "baixa")
        self.assertEqual(zona({"alta": False, "baixa": False})["zona"], "baixa")
        self.assertEqual(zona({})["zona"], "baixa")
        self.assertEqual(zona({"zona": "alta"})["zona"], "alta")

    def test_cada_pagina_avisa_de_les_seves_fonts(self):
        # Juanjo, 09-10-2026: «cada pagina solo avisa de lo que usa»; un 503 del sol no fa menys segura la previsió.
        def falla(errors, fonts, pagina="casa.js", previsio_de=None):
            d = json.dumps({"errors": errors, "previsio_de": previsio_de})
            return self.avalua("2026-10-09T18:05:00+02:00", f"avisosFonts({d}, {fonts}).length > 0", pagina)
        sol = ["sol: HTTP Error 503: Service Unavailable"]
        self.assertFalse(falla(sol, "FONTS_TEMPS"))
        self.assertFalse(falla(sol, "FONTS_SORTIR", "sortir.js"))
        self.assertTrue(falla(["radar: timeout"], "FONTS_TEMPS"))
        self.assertTrue(falla(["estació de casa: 500"], "FONTS_TEMPS"))
        self.assertFalse(falla(["trens: 500"], "FONTS_TEMPS"))
        self.assertTrue(falla(["trens: 500"], "FONTS_SORTIR", "sortir.js"))
        self.assertTrue(falla(["índex UV: 500"], "FONTS_SORTIR", "sortir.js"))
        # La previsió substituïda per l'anterior ja té el seu avís.
        self.assertFalse(falla(["previsió: 503"], "FONTS_TEMPS", previsio_de="2026-10-09T17:00+02:00"))
        # La riera diu què falla i què deixa de funcionar (Juanjo, 21-10-2026).
        def text(dades):
            return self.avalua("2026-10-09T12:05:00+02:00", f"avisosFonts({json.dumps(dades)}, FONTS_TEMPS)", "casa.js")
        caiguda = "riera: Sant Cugat (Meteocat) sense dades recents"
        self.assertEqual(text({"errors": [caiguda], "riera": None, "riera_meteocat_fins": "2026-10-09T10:00+02:00"}),
                         ["Sense dades de Meteocat a Sant Cugat des de les 10:00: ara no es pot calcular el risc de la riera."])
        self.assertEqual(text({"errors": [caiguda], "riera": None, "riera_meteocat_fins": None}),
                         ["Sense dades recents de Meteocat a Sant Cugat: ara no es pot calcular el risc de la riera."])
        # Si les estacions particulars l'han substituït, la riera funciona i no s'avisa.
        self.assertEqual(text({"errors": [caiguda], "riera": {"sense_meteocat": True}}), [])
        self.assertEqual(len(text({"errors": [caiguda, "radar: timeout"], "riera": None})), 2)
        self.assertIn("pot quedar curt", text({"errors": ["riera: a Sant Cugat (Meteocat) li falten mitges hores de pluja"],
                                               "riera": {}})[0])
        # A «Consultes», segons la fitxa: el sol no avisa enlloc; els trens, només a «Avui».
        def consulta(triada, errors):
            return self.avalua("2026-10-09T18:05:00+02:00",
                               f"triada = '{triada}'; avisosFonts({json.dumps({'errors': errors})}, fontsConsulta()).length > 0",
                               "consultes.js")
        self.assertEqual([consulta(t, sol) for t in ("avui", "dema", "sol")], [False, False, False])
        self.assertEqual([consulta(t, ["trens: 500"]) for t in ("avui", "dema", "trens")], [True, False, False])
        self.assertEqual([consulta(t, ["radar: x"]) for t in ("avui", "dema", "aire")], [True, True, False])

    def test_hores_de_si_surts_amb_el_dia(self):
        # La previsió pot arribar a l'endemà de demà al matí (ADR 0041): no és «demà».
        hores = ["2026-10-08T23:00", "2026-10-09T17:00", "2026-10-10T06:00"]
        r = self.avalua("2026-10-08T22:10:00+02:00",
                        f"{json.dumps(hores)}.map((h) => etiquetaHora({{hora: h}}, new Date()))", "sortir.js")
        self.assertEqual(r, ["23:00", "demà 17:00", "dissabte 06:00"])

    def test_public_amb_linies_sense_dades(self):
        # Auditoria del 08-10-2026: amb Renfe caigut i la S2 circulant deia «cap incidència».
        def public(linies):
            return self.avalua("2026-10-08T12:00:00+02:00", f"estatPublic({json.dumps(linies)})", "sortir.js")
        sd = [{"linia": x, "estat": "sense_dades"} for x in ("R4", "R7", "R8")]
        r = public(sd + [{"linia": "S2", "estat": "circula"}])
        self.assertEqual((r["nivell"], r["etiqueta"]), ("neutre", "Dades parcials"))
        self.assertEqual(r["motius"], ["S2 sense incidències; de R4, R7, R8 ara no hi ha dades."])
        r = public(sd + [{"linia": "S2", "estat": "incidencies"}])
        self.assertEqual(r["nivell"], "compte")
        self.assertEqual(r["motius"], ["Trens: S2 amb incidències.", "De R4, R7, R8 ara no hi ha dades."])
        self.assertEqual(public(sd)["etiqueta"], "Sense dades")
        self.assertEqual(public([{"linia": "S2", "estat": "circula"}])["nivell"], "be")

    def test_cotxe_amb_pluja(self):
        # Auditoria del 08-10-2026: amb 90 mm/h el cotxe sortia «bé, sense pluja». Des de la
        # 3.139.0, els llindars de Meteocat: la pluja prevista en 3 hores (60 i 90 mm) i la
        # mesurada a l'última mitja hora si se surt ara (20 i 40 mm), que cal passar (ADR 0039).
        def tram(mm, prob, t=20, n=2):
            return [{"hora": f"2026-10-08T{h:02d}:00", "fins": f"2026-10-08T{h + 1:02d}:00", "temperatura": t,
                     "ratxa": 10, "pluja_mm": mm, "probabilitat": prob, "avisos": []} for h in range(12, 12 + n)]
        def cotxe(mm, prob, t=20, ara=None, futur=False):
            entorn = {"hores": tram(mm, prob, t, 4), "ara": ara}
            return self.avalua("2026-10-08T12:00:00+02:00",
                               f"avalua('cotxe', {json.dumps(tram(mm, prob, t))}, [], {json.dumps(futur)}, [], "
                               f"{json.dumps(entorn)})", "sortir.js")
        self.assertEqual(cotxe(35, 1), {"nivell": "no", "motius": [
            "Fins a 105\u00a0mm de pluja en 3 hores (de 12 a 15\u00a0h): millor no agafar el cotxe."]})
        self.assertEqual(cotxe(25, 0.9), {"nivell": "compte", "motius": [
            "Fins a 75\u00a0mm de pluja en 3 hores (de 12 a 15\u00a0h): condueix amb compte."]})
        # 20 mm en una hora ja no basta (abans, «compte»): és la probabilitat la que diu «pluja probable».
        self.assertEqual(cotxe(20, 0.9)["motius"], ["Pluja probable a l’anada i a la tornada: condueix amb compte."])
        # El que plou ara al barri, si se surt ara; més tard, no compta.
        self.assertEqual(cotxe(2, 0.7, ara={"pluja_30min": 45.2}), {"nivell": "no", "motius": [
            "Ara plou amb molta intensitat al barri (45\u00a0mm en mitja hora): millor no agafar el cotxe."]})
        self.assertEqual(cotxe(2, 0.7, ara={"pluja_30min": 25}), {"nivell": "compte", "motius": [
            "Ara plou amb força al barri (25\u00a0mm en mitja hora): condueix amb compte."]})
        self.assertEqual(cotxe(2, 0.7, ara={"pluja_30min": 20})["motius"],
                         ["Pluja probable a l’anada i a la tornada: condueix amb compte."])
        self.assertEqual(cotxe(2, 0.7, ara={"pluja_30min": 45}, futur=True)["motius"],
                         ["Pluja probable a l’anada i a la tornada: condueix amb compte."])
        self.assertEqual(cotxe(2, 0.7), {"nivell": "compte", "motius": [
            "Pluja probable a l’anada i a la tornada: condueix amb compte."]})
        self.assertEqual(cotxe(0.3, 0.25), {"nivell": "be", "motius": ["Pot ploure a l’anada i a la tornada."]})
        # Un sol model amb 1 mm i poca probabilitat: des de la 3.56.0 decideix la
        # probabilitat també en cotxe (ADR 0069), i només es diu.
        self.assertEqual(cotxe(1.7, 0.25), {"nivell": "be", "motius": ["Pot ploure a l’anada i a la tornada."]})
        self.assertEqual(cotxe(0, 0.05), {"nivell": "be", "motius": ["Sense pluja ni vent fort a l’anada ni a la tornada."]})
        # Per sota del 20 %, on la taula diu «sense pluja»: «poca probabilitat» (18-10-2026).
        self.assertEqual(cotxe(0.3, 0.15), {"nivell": "be", "motius": ["Poca probabilitat de pluja a l’anada i a la tornada."]})
        self.assertEqual(cotxe(0, 0.05, 0)["motius"], ["0\u00a0°C: compte amb el gel a primera hora."])

    def test_pluja_en_3_hores_igual_que_la_comprovacio_diaria(self):
        sys.path.insert(0, os.path.dirname(WEB))
        import aprenentatge as A
        hores = [{"hora": f"2026-10-08T{12 + i:02d}:00", "pluja_mm": mm, "probabilitat": p}
                 for i, (mm, p) in enumerate(((5, 0.5), (30, 0.9), (40, 0.9), (20, 0.1), (1, 0.3)))]
        js = self.avalua("2026-10-08T12:00:00+02:00",
                         f"(() => {{ const h = {json.dumps(hores)}; return h.map((f) => plujaTresHores(h, f).mm); }})()",
                         "sortir.js")
        self.assertEqual(js, [A.pluja_3h(hores, i) for i in range(5)])

    def test_la_comprovacio_diaria_jutja_amb_les_regles_de_la_pagina(self):
        # ADR 0068: el nivell de cada mitjà que calcula aprenentatge.py per a
        # una hora és el mateix que dona la pàgina («Si surts», avalua).
        sys.path.insert(0, os.path.dirname(WEB))
        import aprenentatge as A
        casos = []
        for p, mm, plou, avis in ((0.02, 0, False, False), (0.12, 0, False, False), (0.15, 0, False, False),
                                  (0.25, 0.3, False, False), (0.4, 0, False, False),
                                  (0.45, 0.5, False, False), (0.6, 2, False, False), (None, 0.3, False, False),
                                  (None, 1.2, False, False), (0.0, 0, True, False), (0.0, 0, False, True),
                                  (0.3, 25, False, False), (0.8, 45, False, False)):
            for ratxa, temp in ((10, 15), (45, 15), (55, 15), (75, 15), (95, 15), (10, 2.5), (10, 0.5)):
                casos.append({"probabilitat": p, "pluja_mm": mm, "plou_ara": plou, "avis": avis,
                              "ratxa": ratxa, "temperatura": temp})
        # Dues hores: d'aquí a 2 (llindars «curt») i a 7 (llindars «llarg»), ADR 0069.
        casos = [{**c, "antelacio_h": a} for c in casos for a in (2, 7)]
        trams = [[{"hora": f"2026-10-09T{8 + c['antelacio_h'] - 1:02d}:00", "fins": f"2026-10-09T{8 + c['antelacio_h']:02d}:00",
                   "temperatura": c["temperatura"],
                   "ratxa": c["ratxa"], "pluja_mm": c["pluja_mm"], "probabilitat": c["probabilitat"],
                   "plou_ara": c["plou_ara"], "avisos": [{"tipus": ["pluja"]}] if c["avis"] else []}] for c in casos]
        for mitja in A.MITJANS_SORTIR:
            js = self.avalua("2026-10-09T08:00:00+02:00",
                             f"{json.dumps(trams)}.map((t) => avalua('{mitja}', t, [], true, []).nivell)", "sortir.js")
            self.assertEqual(js, [A.nivell_sortir(mitja, c) for c in casos], mitja)

    def test_transit_al_cotxe_i_la_moto(self):
        # ADR 0052: si surts ara, retencions o talls a prop posen el cotxe i la moto en «compte».
        tram = [{"hora": f"2026-10-09T{h:02d}:00", "fins": f"2026-10-09T{h + 1:02d}:00", "temperatura": 20,
                 "ratxa": 10, "pluja_mm": 0, "probabilitat": 0.02, "avisos": []} for h in (9, 10)]
        transit = [{"tipus": "retencio", "nivell": 3, "carretera": "C-58"},
                   {"tipus": "retencio", "nivell": 4, "carretera": "C-58"},
                   {"tipus": "retencio", "nivell": 2, "carretera": "AP-7"},
                   {"tipus": "obres", "nivell": 5, "carretera": "BV-1414"}]
        def v(mitja, futur, t=transit):
            return self.avalua("2026-10-09T09:30:00+02:00",
                               f"avalua('{mitja}', {json.dumps(tram)}, [], {json.dumps(futur)}, {json.dumps(t)})",
                               "sortir.js")
        self.assertEqual(v("cotxe", False), {"nivell": "compte", "motius": [
            "Sense pluja ni vent fort a l’anada ni a la tornada.", "Ara hi ha retencions o talls a menys de 5\u00a0km: C-58."]})
        self.assertEqual(v("moto", False)["nivell"], "compte")
        # Més tard, el trànsit d'ara no compta; a peu o en bici, tampoc.
        self.assertEqual(v("cotxe", True), {"nivell": "be", "motius": ["Sense pluja ni vent fort a l’anada ni a la tornada."]})
        self.assertEqual(v("bici", False)["nivell"], "be")
        # Només circulació intensa i obres: es llisten, però no canvien el consell.
        self.assertEqual(v("cotxe", False, transit[2:])["nivell"], "be")
        self.assertEqual(v("cotxe", False, None)["nivell"], "be")

    def test_distancia_del_transit(self):
        # Igual que el bot: en metres per sota d'1 km (Juanjo, 09-10-2026).
        r = self.avalua("2026-10-09T09:30:00+02:00", "[0.01, 0.73, 1.0, 4.04, 4.35].map(distancia)", "sortir.js")
        self.assertEqual(r, ["50\u00a0m", "750\u00a0m", "1\u00a0km", "4\u00a0km", "4,4\u00a0km"])

    def test_roba_bici(self):
        self.assertEqual(self.roba("bici", (9, 22, 0), (11, 22, 0)), "Màniga curta.")
        self.assertEqual(self.roba("bici", (9, 19, 0), (11, 19, 0), pluja=True),
                         "Màniga llarga o una jaqueta molt lleugera. Impermeable.")

    def test_la_roba_del_bot_es_la_de_la_web(self):
        # El bot (Python, a IONOS) repeteix la taula de «Si surts»: han de dir el mateix.
        sys.path.insert(0, os.path.join(os.path.dirname(WEB), "bot"))
        import bot
        graus = list(range(-5, 36))
        web = self.avalua("2026-10-07T08:00:00+02:00",
                          f"{json.dumps(graus)}.map((s) => peca('peu', s))", "sortir.js")
        self.assertEqual(web, [bot.peca(s, "ca") + "." for s in graus])

    def test_pluja_nomes_per_l_avis_de_l_aemet(self):
        # El cas del 07-10-2026 a les 18 h: avís groc fins a les 20 h, cel serè i un 1 %.
        # Es manté el que diu l'avís, però es diu que cap altra dada hi veu pluja (ADR 0008 i 0029).
        avis = [{"nivell": "groc", "tipus": ["pluja", "tempestes"]}]
        def tram(prob):
            return [{"hora": f"2026-10-07T{h:02d}:00", "probabilitat": prob, "pluja_mm": 0,
                     "temperatura": 22, "avisos": avis if h < 20 else []} for h in (18, 19, 20, 21)]
        def avalua(mitja, prob):
            return self.avalua("2026-10-07T18:10:00+02:00",
                               f"avalua({json.dumps(mitja)}, {json.dumps(tram(prob))}, [])", "sortir.js")
        # En bici i en moto, l'avís tot sol és «compte», no «no» (08-10-2026, ADR 0047).
        bici = avalua("bici", 0.01)
        self.assertEqual(bici["nivell"], "compte")
        self.assertEqual(bici["motius"], ["Avís oficial per pluja a l’anada (18\u00a0h): ni el radar, "
                                          "ni les estacions, ni els models hi veuen pluja."])
        moto = avalua("moto", 0.01)
        self.assertEqual(moto["nivell"], "compte")
        self.assertTrue(moto["motius"][0].endswith("Per si de cas, porta l’impermeable."))
        cotxe = avalua("cotxe", 0.01)
        self.assertEqual(cotxe["nivell"], "compte")
        self.assertTrue(cotxe["motius"][0].startswith("Avís oficial per pluja a l’anada (18\u00a0h)"))
        # El cas del 08-10-2026 a les 17 h: avís i un 10 %. Com la moto, «pot ploure».
        self.assertEqual(avalua("cotxe", 0.1)["motius"], ["Pot ploure a l’anada i a la tornada: condueix amb compte."])
        self.assertTrue(avalua("peu", 0.01)["motius"][0].startswith("Avís oficial per pluja mentre ets fora"))
        # Si els models també hi veuen pluja, com sempre.
        self.assertEqual(avalua("bici", 0.6)["motius"], ["Pluja probable a l’anada i a la tornada."])
        # «Ni el radar…» val per a tota la sortida (revisor, 20-10-2026: pluja que el radar veu
        # arribar cap a les 02:10 i un 37 % a la fila de les 2, amb sortida a la 1 i tornada a les 4).
        avis_mc = [{"nivell": "groc", "tipus": ["pluja"], "font": "meteocat"}]
        nit = [{"hora": f"2026-10-20T{h:02d}:00", "probabilitat": p, "pluja_mm": 0, "temperatura": 14,
                "avisos": avis_mc} for h, p in ((1, 0.03), (2, 0.37), (3, 0.06), (4, 0.0))]
        def entremig(mitja, entorn):
            return self.avalua("2026-10-20T01:28:00+02:00",
                               f"avalua({json.dumps(mitja)}, {json.dumps(nit)}, [], false, null, {json.dumps(entorn)})",
                               "sortir.js")["motius"][0]
        radar = {"pluja_ara": {"estat": "possible", "possible": "2026-10-20T02:10:00+02:00"}}
        self.assertEqual(entremig("bici", radar), "Avís oficial per pluja a l’anada i a la tornada, "
                                                  "i el radar veu pluja que pot arribar cap a les 02:10.")
        self.assertTrue(entremig("moto", radar).endswith("02:10. Per si de cas, porta l’impermeable."))
        self.assertEqual(entremig("cotxe", {"hores": nit}), "Avís oficial per pluja a l’anada i a la tornada, "
                                                            "i entremig pot ploure, cap a les 2\u00a0h. Condueix amb compte.")
        consells = self.avalua("2026-10-07T18:10:00+02:00",
                               f"consells({json.dumps(tram(0.01))}, new Date())", "sortir.js")
        self.assertIn("Cap a les 20\u00a0h s’acaba l’avís oficial.", consells)

    def test_si_ara_plou_ho_diu_i_qui_ho_veu(self):
        # 19-10-2026, plovent: «Si surts» deia «Pluja probable a l'anada (6 h)», i a les 7, amb les dades de
        # les 6:57, «a l'anada (7 h)»: l'hora en curs de la taula ja no hi era. Si se surt ara i l'estat de
        # la pluja d'ara (pluja_ara, el de la portada) diu que plou, es diu i qui ho veu; només amb «Ara».
        def tram(tornada=0.82):
            return [{"hora": "2026-10-19T07:00", "probabilitat": 0.3, "pluja_mm": 0.7, "temperatura": 13, "avisos": []},
                    {"hora": "2026-10-19T08:00", "probabilitat": 0.65, "pluja_mm": 1.8, "temperatura": 14, "avisos": []},
                    {"hora": "2026-10-19T09:00", "probabilitat": tornada, "pluja_mm": 3.0, "temperatura": 14, "avisos": []}]
        def avalua(mitja, estat="plou", radar=None, tornada=0.82, futur=False):
            entorn = {"hores": tram(tornada), "ara": {}, "pluja_ara": {"estat": estat}, "radar": radar}
            return self.avalua("2026-10-19T07:05:00+02:00", f"avalua({json.dumps(mitja)}, {json.dumps(tram(tornada))}, [], "
                               f"{json.dumps(futur)}, [], {json.dumps(entorn)})", "sortir.js")
        moto = avalua("moto")
        self.assertEqual(moto["nivell"], "no")
        self.assertEqual(moto["motius"], ["Ara plou al barri, segons les estacions, i pluja probable a la tornada (9\u00a0h)."])
        sobre = {"arriba": "2026-10-19T07:04:00+02:00"}
        self.assertEqual(avalua("bici", radar=sobre, tornada=0.05)["motius"], ["Ara plou al barri, segons les estacions i el radar."])
        self.assertEqual(avalua("bici", estat="radar_sobre", radar=sobre, tornada=0.05)["motius"], ["Ara plou al barri, segons el radar."])
        # Sense pluja a la tornada, només l'ara; en cotxe, amb «condueix amb compte»; a peu, el paraigua.
        self.assertEqual(avalua("moto", tornada=0.05)["motius"], ["Ara plou al barri, segons les estacions."])
        self.assertEqual(avalua("cotxe", tornada=0.05)["motius"], ["Ara plou al barri, segons les estacions: condueix amb compte."])
        self.assertEqual(avalua("peu")["motius"], ["Ara plou al barri, segons les estacions: porta paraigua."])
        # Si no plou ara, o si se surt més tard, com sempre.
        self.assertEqual(avalua("moto", estat="no")["motius"], ["Pluja probable a la tornada (9\u00a0h)."])
        self.assertEqual(avalua("moto", futur=True)["motius"], ["Pluja probable a la tornada (9\u00a0h)."])
        # A peu, «pluja probable» amb el mateix llindar que els vehicles (revisor, 19-10-2026: deia «pot ploure»).
        self.assertEqual(avalua("peu", futur=True)["motius"], ["Pluja probable mentre ets fora: porta paraigua."])

    def test_pausa_en_el_risc_de_pluja_no_es_el_final(self):
        # Revisor, 18-10-2026: «Cap a les 15 h s'acaba el risc de pluja» amb pluja possible de 16 a 0 h.
        def tram(probs):
            return [{"hora": f"2026-10-18T{14 + i:02d}:00", "probabilitat": p, "pluja_mm": 0,
                     "temperatura": 17, "avisos": []} for i, p in enumerate(probs)]
        def consells(probs):
            return self.avalua("2026-10-18T14:30:00+02:00", f"consells({json.dumps(tram(probs))}, new Date())",
                               "sortir.js")
        self.assertIn("De 15 a 16\u00a0h, sense risc de pluja.", consells([0.6, 0.05, 0.6, 0.6]))
        self.assertNotIn("Cap a les 15\u00a0h s’acaba el risc de pluja.", consells([0.6, 0.05, 0.6, 0.6]))
        self.assertIn("Cap a les 15\u00a0h s’acaba el risc de pluja.", consells([0.6, 0.05, 0.05, 0.05]))

    def test_pluja_en_moto_per_la_probabilitat(self):
        # El cas del 08-10-2026: avís groc des de les 10 h, cap dada hi veia pluja
        # a les 10 i a les 17 h només ICON-EU donava 1,7 mm (un 25 %). Va dir «no»
        # i no va ploure. Ara, en moto i en bici, decideix la probabilitat (ADR 0047).
        avis = [{"nivell": "groc", "tipus": ["pluja"]}]
        def viatge(prob, mm, avisos=avis):
            return [{"hora": f"2026-10-08T{h:02d}:00", "probabilitat": p, "pluja_mm": m,
                     "temperatura": 18, "avisos": avisos} for h, p, m in ((10, 0.0, 0.0), (17, prob, mm))]
        def avalua(mitja, tram):
            return self.avalua("2026-10-08T09:50:00+02:00",
                               f"avalua({json.dumps(mitja)}, {json.dumps(tram)}, [])", "sortir.js")
        moto = avalua("moto", viatge(0.25, 1.7))
        self.assertEqual(moto["nivell"], "compte")
        self.assertEqual(moto["motius"], ["Pot ploure a l’anada i a la tornada: porta l’impermeable."])
        # La tornada, d'aquí a 7 hores: «millor no» des del 60 % (ADR 0069).
        self.assertEqual(avalua("moto", viatge(0.45, 0.3))["nivell"], "compte")
        self.assertEqual(avalua("moto", viatge(0.65, 0.3))["nivell"], "no")
        self.assertEqual(avalua("moto", viatge(0.12, 0.0, []))["nivell"], "compte")
        self.assertEqual(avalua("moto", viatge(0.05, 0.6, []))["nivell"], "be")
        # Sense probabilitat, manen els mil·límetres.
        self.assertEqual(avalua("bici", viatge(None, 1.2, []))["nivell"], "no")
        # En cotxe també decideix la probabilitat (ADR 0069): un sol model amb 1,7 mm, no.
        self.assertEqual(avalua("cotxe", viatge(0.25, 1.7, []))["nivell"], "be")

    def test_nou_al_costat_dels_avisos_i_de_perill(self):
        # «Nou!» fins que s'entra a la pàgina i, per a tothom, una setmana
        # després de publicar-la: «Avisos» (ADR 0048) i «Perill» (ADR 0071).
        def nou(ara, vistos=(), pagina="/", despres=""):
            expr = ("posats = []; botons = {};"
                    "boto = (nom) => botons[nom] ||= { classList: { add() {}, remove() {} }, querySelector: () => botons[nom].xip,"
                    " append: (e) => { e.remove = () => { posats = posats.filter((x) => x !== nom + ':' + e.textContent);"
                    " botons[nom].xip = null; }; botons[nom].xip = e; posats.push(nom + ':' + e.textContent); } };"
                    "document.querySelectorAll = (s) => s === '.boto-avisos' ? [boto('avisos')]"
                    " : s.includes('perill.html') ? [boto('perill')] : [];"
                    f"location.pathname = {json.dumps(pagina)};"
                    f"desats = Object.fromEntries({json.dumps(list(vistos))}.map((k) => [k, '1']));"
                    "localStorage.getItem = (k) => desats[k] || null;"
                    "localStorage.setItem = (k, v) => { desats[k] = v; };"
                    f"element = (e, c, t) => ({{ textContent: t }}); marcaNovetats(new Date()); {despres} posats")
            return self.avalua(ara, expr)
        self.assertEqual(nou("2026-10-12T10:00:00+02:00"), ["avisos:Nou!", "perill:Nou!"])
        self.assertEqual(nou("2026-10-12T10:00:00+02:00", ["meteo.avisos-vist"]), ["perill:Nou!"])
        self.assertEqual(nou("2026-10-12T10:00:00+02:00", pagina="/es/perill.html"), ["avisos:Nou!"])
        self.assertEqual(nou("2026-10-16T00:00:00+02:00"), ["perill:Nou!"])
        self.assertEqual(nou("2026-10-19T00:00:00+02:00"), [])
        # Tornant enrere, la pàgina es pot restaurar tal com era: es torna a
        # mirar, sense repetir el «Nou!» i traient el de la pàgina ja vista.
        self.assertEqual(nou("2026-10-12T10:00:00+02:00", despres="marcaNovetats(new Date());"),
                         ["avisos:Nou!", "perill:Nou!"])
        self.assertEqual(nou("2026-10-12T10:00:00+02:00",
                             despres="desats['meteo.perill-vist'] = '1'; marcaNovetats(new Date());"),
                         ["avisos:Nou!"])

    def test_compartir(self):
        # ADR 0072 i 0076: compartir obre el menú del sistema; sense, es copia sol (primer de la manera
        # clàssica; si no va, amb el portapapers). Un avís va sencer, amb l'enllaç.
        base = ("dit = []; avisBreu = (t) => dit.push(t); compartit = null; copiat = null; classic = null;"
                "document.body = { append() {} };"
                "document.execCommand = () => { classic = 'ok'; return true; };"
                "element = (e) => ({ value: '', style: {}, setAttribute() {}, select() {}, setSelectionRange() {}, remove() {} });")
        expr = (base + "navigator.share = (d) => { compartit = d; return Promise.resolve(); };"
                "comparteix('https://m.test/perill.html#a-x', 'Riera', 'Perill a la riera\\nNo t’hi acostis.');"
                "new Promise((r) => setTimeout(r, 10)).then(() => [compartit, classic, dit])")
        r = self.avalua("2026-10-12T10:00:00+02:00", expr, arnes=ARNES_ASYNC)
        self.assertEqual(r[0], {"title": "Riera", "text": "Perill a la riera\nNo t’hi acostis.", "url": "https://m.test/perill.html#a-x"})
        self.assertEqual(r[1:], [None, []])      # amb el menú, no es copia
        # Sense còpia clàssica ni menú, el portapapers; una pàgina, només l'enllaç.
        expr = (base + "document.execCommand = () => false;"
                "navigator.clipboard = { writeText: (u) => { copiat = u; return Promise.resolve(); } };"
                "comparteix('https://m.test/consultes.html#llum');"
                "new Promise((r) => setTimeout(r, 10)).then(() => [copiat, dit])")
        r = self.avalua("2026-10-12T10:00:00+02:00", expr, arnes=ARNES_ASYNC)
        self.assertEqual(r, ["https://m.test/consultes.html#llum", ["Enllaç copiat"]])

    def test_etiquetes_amb_els_llindars_del_temps_extrem(self):
        # Inventari del 18-10-2026: «ratxes de 71 km/h» sense l'avís, que és de
        # més de 72. Les etiquetes del tram, amb els llindars de config.
        with open(os.path.join(WEB, "casa.js"), encoding="utf-8") as f:
            codi = f.read()
        m = re.search(r"const FENOMENS = \{[^}]*ratxa: ([\d.]+), calor: ([\d.]+)", codi)
        self.assertEqual((float(m.group(1)), float(m.group(2))),
                         (C.RISC_LLINDARS["ratxa"][0], C.RISC_LLINDARS["calor"][0]))
        m = re.search(r"const RATXA_TARONJA = ([\d.]+);", codi)
        self.assertEqual(float(m.group(1)), C.RISC_LLINDARS["ratxa"][1])

    def test_xifra_del_risc_com_el_text(self):
        # Revisor, 19-10-2026: «vent fort (92,5 km/h)» a la portada, «92» a l'avís i «93» a la taula.
        r = self.avalua("2026-10-19T14:00:00+02:00",
                        "[numRisc({tipus: 'ratxa', valor: 92.5}), numRisc({tipus: 'calor', valor: 36.85}),"
                        " numRisc({tipus: 'calor', valor: 37}), numRisc({tipus: 'fred', valor: -1.6})]")
        self.assertEqual(r, ["93", "36,9", "37", "\u22121,6"])

    def test_ratxa_de_l_avis_a_la_taula(self):
        # 19-10-2026: l'avís de vent fort (77 km/h) i, a la taula, «13 (77)» com qualsevol
        # altra xifra. La ratxa que passa el llindar, del color del nivell i amb l'enllaç.
        ara = "2026-10-19T13:15:00+02:00"
        # Un DOM mínim que guarda el text i els fills (el de l'arnès no en guarda).
        expr = ("element = (tag, cls, text) => { const n = {tag, className: cls || '', fills: text ? [text] : [],"
                " setAttribute() {}, addEventListener() {}, append(...x) { this.fills.push(...x); },"
                " set textContent(t) { this.fills = [t]; },"
                " get textContent() { return this.fills.map((f) => typeof f === 'string' ? f : (f.textContent || '')).join(''); } };"
                " return n; };"
                "[celVent({vent: 13.4, ratxa: 76.6}), celVent({vent: 5, ratxa: 72}), celVent({vent: 20, ratxa: 110})]"
                ".map((td) => [td.textContent, (td.fills.find((f) => f.tag === 'a') || {className: ''}).className])")
        self.assertEqual(self.avalua(ara, expr, "casa.js"),
                         [["13 (77)", "ratxa-forta groc"], ["5 (72)", ""], ["20 (110)", "ratxa-forta taronja"]])

    def test_fiabilitat_dita_com_a_conclusio(self):
        # «Fiabilitat», pàgina pròpia (ADR 0110): conclusions curtes, si la
        # diferència és segura (95 % dels remostrejos per dies) i els canvis apresos.
        ara = "2026-10-20T10:00:00+02:00"
        av = lambda expr: self.avalua(ara, expr, "fiabilitat.js")
        # Dit perquè ho entengui tothom (Juanjo, 20-10-2026: «hablas para gente sin conocimientos»).
        self.assertEqual(av("[textSegur(0.97), textSegur(0.02), textSegur(0.5), textSegur(null)]"),
                         ["no és casualitat", "no és casualitat", "encara pot ser casualitat", "encara poques dades per saber-ho"])
        self.assertEqual(av("textCanvi({dia: '2026-10-07', que: 'radar', a: 'rainviewer'})"),
                         "Fa servir el radar de RainViewer, que encertava més la pluja al barri.")
        self.assertEqual(av("textCanvi({dia: '2026-10-30', que: 'pluja', a: 'local'})"),
                         "La probabilitat de pluja passa a ser la pròpia, apresa al barri, que encertava més.")
        self.assertEqual(av("[fraseNova(1.11, 1.07), fraseNova(0.9, 1.07), fraseNova(null, 1)]"),
                         ["De moment, la nova s’equivoca més que l’actual.",
                          "La nova ja s’equivoca menys: la farà servir quan es vegi que no és casualitat.", None])
        self.assertEqual(av("[escalaMax(0.67), escalaMax(1.16), escalaMax(0.0488), escalaMax(3.2)]"), [0.8, 1.5, 0.06, 4])
        self.assertEqual(av("textPeriode({des_de: '2026-10-04', dies: 15})"), "Des del 4 d’octubre fins ara (15 dies).")
        self.assertEqual(av("textPeriode({des_de: '2026-09-19', dies: 30})"), "Els darrers 30 dies.")

    def test_meteocat_agrupat_per_fenomen(self):
        # 18-10-2026: «Avisos actius (3)» i, desplegat, 4 línies (dos meteors de la pluja).
        expr = ("element = (t, c, x) => ({ className: c, fills: x ? [x] : [], dataset: {},"
                " append(...a) { this.fills.push(...a); } });"
                "blocSmp({linies: [{nivell: 'mig', fenomen: 'pluja', ca: 'A'}, {nivell: 'alt', fenomen: 'pluja', ca: 'B'},"
                " {nivell: 'mig', fenomen: 'vent', ca: 'C'}]})"
                ".map((i) => [i.className, i.fills.map((f) => (typeof f === 'string' ? f : f.fills[0])).join('')])")
        self.assertEqual(self.avalua("2026-10-18T07:00:00+02:00", expr),
                         [["avis-item taronja", "BA"], ["avis-item groc", "C"]])

    def test_final_de_la_pluja_en_entrenament(self):
        # «Pluja a sobre» amb l'hora en què pararia, marcat «en entrenament» (ADR 0049).
        r = {"arriba": "2026-10-08T19:00", "fi": "2026-10-08T20:10:00+02:00"}
        ara = "2026-10-08T19:02:00+02:00"
        self.assertEqual(self.avalua(ara, f"textRadar({json.dumps(r)}, true)"),
                         ["arriba", "Pluja a sobre · pararia cap a les\u00a020:10", True, True])
        self.assertEqual(self.avalua(ara, f"textRadar({json.dumps({**r, 'fi': None, 'sense_fi': True})}, true)"),
                         ["arriba", "Pluja a sobre · no s’acaba en 2 hores", True, True])
        # Ja plou però el radar només veu pluja possible: mana el que es mesura (08-10-2026, 20:04).
        possible = {"arriba": None, "possible": "2026-10-08T20:00", "fi": "2026-10-08T20:10:00+02:00"}
        les20 = "2026-10-08T20:04:00+02:00"
        self.assertEqual(self.avalua(les20, f"textRadar({json.dumps(possible)}, true)"),
                         ["arriba", "Pluja a sobre · pararia cap a les\u00a020:10", True, True])
        self.assertEqual(self.avalua(les20, f"textRadar({json.dumps(possible)}, false)")[1], "Pluja a prop: pot arribar")
        # Plou i el radar no en veu gens: es diu que la mesuren les estacions
        # (Juanjo, 18-10-2026), també si en veu venir més tard.
        self.assertEqual(self.avalua(ara, 'textRadar({"arriba": null, "possible": null, "fi": null, "sense_fi": false}, true)'),
                         ["arriba", "Pluja a sobre segons les estacions del barri · el radar no la veu", False, True])
        # Plugim als dos radars, sense pluja mesurada (Juanjo, 18-10-2026).
        plugim = {"arriba": None, "possible": None, "pluja": {"estat": "no", "plugim": True}}
        self.assertEqual(self.avalua(ara, f"textRadar({json.dumps(plugim)}, false)"),
                         ["possible", "El radar veu pluja molt feble a sobre (plugim), que les estacions no mesuren"])
        mes_tard = {"arriba": "2026-10-08T19:30", "sense_fi": True, "pluja": {"estat": "plou"}}
        self.assertEqual(self.avalua(ara, f"textRadar({json.dumps(mes_tard)}, true)")[1],
                         "Pluja a sobre segons les estacions del barri · el radar no la veu")
        self.assertEqual(self.avalua(ara, 'textRadar({"arriba": null, "possible": null}, false)')[1],
                         "El radar no veu pluja que vingui cap aquí")
        # El radar la posa a sobre i cap estació no en mesura: es diu (ADR 0101; Juanjo,
        # 18-10-2026: «lo decía el radar: lluvia encima, pero no había»).
        sobre = {**r, "pluja": {"estat": "radar_sobre"}}
        self.assertEqual(self.avalua(ara, f"textRadar({json.dumps(sobre)}, false)")[1],
                         "Pluja a sobre segons el radar · cap estació del barri no en mesura · pararia cap a les\u00a020:10")
        # Amb l'estat, mana l'estat: «arriba» lluny no és «a sobre».
        lluny = {"arriba": "2026-10-08T19:30", "pluja": {"estat": "arriba"}}
        self.assertTrue(self.avalua(ara, f"textRadar({json.dumps(lluny)}, false)")[1][0].startswith("Pluja "))
        # Pluja forta a prop que no ve cap aquí: al titular (17-10-2026, amb trons).
        forta = {"arriba": None, "possible": None, "forta": {"km": 10.2, "rumb": "al nord", "classe": 4}}
        self.assertEqual(self.avalua(ara, f"textRadar({json.dumps(forta)}, false)"),
                         ["a-prop", "Pluja molt forta a 10\u00a0km al nord, que de moment no ve cap aquí"])
        # La pluja que creix al voltant (17-10-2026).
        c = {"creixement": {"creix": True, "km2": 216, "km2_abans": 113, "pct": 31, "pct_abans": 16}}
        self.assertEqual(self.avalua(ara, f"textCreixement({json.dumps(c)})"),
                         "La pluja s’està formant a prop: ja ocupa el 31\u00a0% del terreny a 15\u00a0km o menys; "
                         "fa mitja hora, el 16\u00a0%.")
        c["creixement"].update(km2=52, km2_abans=0, pct=7, pct_abans=0)
        self.assertEqual(self.avalua(ara, f"textCreixement({json.dumps(c)})"),
                         "La pluja s’està formant a prop: ja ocupa el 7\u00a0% del terreny a 15\u00a0km o menys; "
                         "fa mitja hora, gens.")
        self.assertIsNone(self.avalua(ara, 'textCreixement({"creixement": {"creix": false, "pct": 3}})'))
        # Sense dada (dades d'abans), com sempre.
        self.assertEqual(self.avalua(ara, 'textRadar({"arriba": "2026-10-08T19:00"}, true)'),
                         ["arriba", "Pluja a sobre", False, True])

    def test_llegenda_del_mapa_nomes_el_que_es_dibuixa(self):
        # 17-10-2026: deia «moderada» i «forta» per pluja de la vora del tros,
        # fora del quadrat de 30 km que es dibuixa.
        n = 5
        classes = ["0"] * n * n
        classes[0] = "3"          # a la cantonada: (2 px) × 20 km > 30 km
        classes[2 * n + 3] = "1"  # al costat de casa
        m = {"n": n, "fila": 2, "col": 2, "km_px": 20, "classes": "".join(classes)}
        self.assertEqual(self.avalua("2026-10-17T17:00:00+02:00", f"[...classesDibuixades({json.dumps(m)}, 30)]"), ["1"])

    def test_propera_lectura(self):
        horari = {"trams": [["00:00", "23:50"]], "cada_min": 10, "desfase_min": 1}
        expr = f"properaActualitzacio({json.dumps(horari)}).toISOString()"
        self.assertEqual(self.avalua("2026-10-05T16:41:30+02:00", expr), "2026-10-05T14:51:00.000Z")
        # Després de la darrera del dia, la primera de demà.
        self.assertEqual(self.avalua("2026-10-05T23:55:00+02:00", expr), "2026-10-05T22:01:00.000Z")
        trajecte = {"trams": [["05:00", "07:30"], ["13:00", "15:30"]], "cada_min": 30}
        expr = f"properaActualitzacio({json.dumps(trajecte)}).toISOString()"
        self.assertEqual(self.avalua("2026-10-05T09:00:00+02:00", expr), "2026-10-05T11:00:00.000Z")

    def test_propera_des_de_les_dades(self):
        # 11-10-2026: a les 13:31, amb dades de les 13:15, deia «propera: 13:45»
        # i la pàgina no tornava a llegir fins a les 13:47.
        dades = {"generat": "2026-10-11T13:15+02:00", "horari": {"trams": [["00:00", "23:45"]], "cada_min": 15}}
        expr = f"properaPendent({json.dumps(dades)}).toISOString()"
        self.assertEqual(self.avalua("2026-10-11T13:31:00+02:00", expr), "2026-10-11T11:30:00.000Z")
        # Abans de l'hora, la mateixa.
        self.assertEqual(self.avalua("2026-10-11T13:20:00+02:00", expr), "2026-10-11T11:30:00.000Z")
        # Si fa més de MARGE_RETARD_MIN que no arriba, la de l'horari.
        self.assertEqual(self.avalua("2026-10-11T13:55:00+02:00", expr), "2026-10-11T12:00:00.000Z")
        # Amb les dades noves, la següent.
        noves = {**dades, "generat": "2026-10-11T13:30+02:00"}
        expr = f"properaPendent({json.dumps(noves)}).toISOString()"
        self.assertEqual(self.avalua("2026-10-11T13:31:00+02:00", expr), "2026-10-11T11:45:00.000Z")
        # Després de la darrera del dia, cap.
        tard = {**dades, "generat": "2026-10-11T23:45+02:00"}
        self.assertIsNone(self.avalua("2026-10-11T23:50:00+02:00", f"properaPendent({json.dumps(tard)})"))

    def test_dades_velles(self):
        # Amb més de 2 hores, la previsió ja no es mostra (ADR 0031).
        expr = ("[dadesVelles({generat: '2026-10-07T06:50:00+02:00'}), "
                "dadesVelles({generat: '2026-10-07T07:10:00+02:00'})]")
        self.assertEqual(self.avalua("2026-10-07T09:00:00+02:00", expr), [True, False])

    def test_copia_de_github_si_ionos_serveix_dades_velles(self):
        # Auditoria del 07-10-2026: IONOS contestava amb dades de fa 3 hores i
        # la còpia de GitHub, més nova, no es mirava.
        ara = "2026-10-08T09:00:00+02:00"
        velles, noves = {"generat": "2026-10-08T06:00+02:00"}, {"generat": "2026-10-08T08:51+02:00"}
        expr = self.fetch_fals([velles, noves]) + "llegeixDades('casa.json').then((d) => [d.generat, peticions])"
        self.assertEqual(self.avalua(ara, expr, arnes=ARNES_ASYNC),
                         [noves["generat"], ["https://bilateria.org/app/meteo-local/casa.json", "casa.json"]])
        # Si la còpia és més vella, es queden les d'IONOS; si falla, també.
        expr = self.fetch_fals([noves, velles]) + "llegeixDades('casa.json').then((d) => d.generat)"
        self.assertEqual(self.avalua(ara, expr, arnes=ARNES_ASYNC), noves["generat"])
        expr = self.fetch_fals([velles, None]) + "llegeixDades('casa.json').then((d) => d.generat)"
        self.assertEqual(self.avalua(ara, expr, arnes=ARNES_ASYNC), velles["generat"])
        # Amb dades d'IONOS de fa menys de 45 minuts, una sola petició.
        recents = {"generat": "2026-10-08T08:30+02:00"}
        expr = self.fetch_fals([recents, noves]) + "llegeixDades('casa.json').then((d) => [d.generat, peticions.length])"
        self.assertEqual(self.avalua(ara, expr, arnes=ARNES_ASYNC), [recents["generat"], 1])
        # Si IONOS no respon, la còpia, com sempre.
        expr = self.fetch_fals([None, noves]) + "llegeixDades('casa.json').then((d) => d.generat)"
        self.assertEqual(self.avalua(ara, expr, arnes=ARNES_ASYNC), noves["generat"])

    def test_copia_de_github_si_a_ionos_li_falta_una_actualitzacio(self):
        # 11-10-2026: cada matí IONOS tanca l'SSH de 06:01 a 06:15; el NAS
        # publica les de les 06:03 a GitHub i IONOS es queda amb les de les 06:00.
        horari = {"trams": [["00:00", "23:54"]], "cada_min": 6, "desfase_min": 3}
        ionos = {"generat": "2026-10-11T06:00+02:00", "horari": horari}
        github = {"generat": "2026-10-11T06:03+02:00", "horari": horari}
        expr = self.fetch_fals([ionos, github]) + "llegeixDades('casa.json').then((d) => [d.generat, peticions.length])"
        self.assertEqual(self.avalua("2026-10-11T06:05:00+02:00", expr, arnes=ARNES_ASYNC), [github["generat"], 2])
        # Abans que la de les 06:03 s'hagi pogut publicar, només IONOS.
        self.assertEqual(self.avalua("2026-10-11T06:04:30+02:00", expr, arnes=ARNES_ASYNC), [ionos["generat"], 1])
        # Al dia amb l'horari: una sola petició.
        al_dia = {**ionos, "generat": "2026-10-11T06:03+02:00"}
        expr = self.fetch_fals([al_dia, github]) + "llegeixDades('casa.json').then((d) => [d.generat, peticions.length])"
        self.assertEqual(self.avalua("2026-10-11T06:07:00+02:00", expr, arnes=ARNES_ASYNC), [al_dia["generat"], 1])

    def test_la_descarrega_es_talla_tambe_a_mig_cos(self):
        # Auditoria del 09-10-2026: «fetch» es resol amb les capçaleres i el
        # temporitzador s'aturava abans de llegir el cos: un cos que no acabava
        # mai deixava la lectura penjada i no s'anava a la còpia.
        ara = "2026-10-09T18:00:00+02:00"
        expr = ("fetch = (url, opts) => Promise.resolve({ ok: true, json: () => new Promise((_, no) => "
                "opts.signal.addEventListener('abort', () => no(new Error('abortat')))) });"
                "baixa('x.json').then(() => 'ok', (e) => e.message)")
        self.assertEqual(self.avalua(ara, expr, arnes=ARNES_ASYNC), "abortat")
        expr = "fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ a: 1 }) }); baixa('x.json')"
        self.assertEqual(self.avalua(ara, expr, arnes=ARNES_ASYNC), {"a": 1})

    def test_en_fallar_una_lectura_es_torna_a_pintar(self):
        # Auditoria del 07-10-2026: amb la pestanya oberta i la xarxa caiguda,
        # les dades velles es quedaven a la pantalla. Ara cada lectura fallida
        # torna a pintar el que hi ha (i dadesVelles decideix).
        # Lectura bona (dades recents: una sola petició), dues lectures fallides
        # (IONOS i la còpia) i la següent que no contesta: dues pintades.
        # Les de les 08:45: a les 09:00 encara no toca la de les 09:00, i van al dia.
        dades = {"generat": "2026-10-08T08:45+02:00", "horari": {"trams": [["00:00", "23:50"]], "cada_min": 15}}
        expr = (self.fetch_fals([dades, None, None, 'penja']) + "pintats = 0;"
                "carrega('casa.json', () => { pintats += 1; }, () => {});"
                "new Promise((r) => setTimeout(() => r([pintats, peticions.length]), 50))")
        self.assertEqual(self.avalua("2026-10-08T09:00:00+02:00", expr, arnes=ARNES_ASYNC), [2, 4])

    def test_si_surts_trens_d_ara_i_pla_de_proteccio_civil(self):
        trens = [{"linia": "R4", "estat": "circula"}, {"linia": "S2", "estat": "circula"}]
        ara = "2026-10-08T09:00:00+02:00"
        self.assertEqual(self.avalua(ara, f"avaluaPublic({json.dumps(trens)}, false).motius", "sortir.js"),
                         ["Cap incidència als trens de Cerdanyola."])
        self.assertEqual(self.avalua(ara, f"avaluaPublic({json.dumps(trens)}, true).motius", "sortir.js"),
                         ["Cap incidència als trens de Cerdanyola.", "Són els trens d’ara, no els de l’hora triada."])
        plans = [{"pla": "INUNCAT", "nom": "d'inundacions", "fase": "emergència"}]
        # El pla no surt sencer a «Si surts» (19-10-2026): la línia que remet a «Perill» diu
        # què no tenen en compte els consells, sense «vegeu l'avís de dalt», que ja no hi és.
        nota = lambda d: self.avalua(ara, f"noTeEnCompte({json.dumps(d)})", "sortir.js")
        self.assertEqual(nota({"plans": plans}),
                         "El consell de cada mitjà surt del temps previst i del trànsit: no té en compte l’emergència de Protecció Civil.")
        plans[0]["fase"] = "alerta"
        self.assertEqual(nota({"plans": plans, "perill_riera": [{}], "entorn": {"incendis": [{}]}}),
                         "El consell de cada mitjà surt del temps previst i del trànsit: no té en compte l’alerta de Protecció "
                         "Civil, el perill de la riera de Sant Cugat ni l’incendi proper.")
        plans[0]["fase"] = "prealerta"
        self.assertIsNone(nota({"plans": plans}))
        self.assertIsNone(nota({}))

    def test_si_surts_nomes_remet_a_perill_amb_els_avisos_de_conduccio(self):
        # Juanjo, 19-10-2026: «en si surts salen todas las alertas, prefiero simplificarlo. si hay alertas
        # que afectan a la conduccion lo mejor es que remita a la pestaña perill». No compten la calor,
        # el mar, el Pla Alfa ni els tancaments forestals.
        ara = "2026-10-19T09:00:00+02:00"
        aemet = lambda tipo, nivel: {"zona": "Prelitoral de Barcelona", "tipo": tipo, "nivel": nivel,
                                     "inicio": "2026-10-19T08:00:00+02:00", "fin": "2026-10-19T20:00:00+02:00"}
        dades = {"plans": [{"pla": "INUNCAT", "nom": "d'inundacions", "fase": "alerta"}],
                 "smp": {"fenomens": [{"fenomen": "pluja", "nivell": "alt", "dies": []},
                                      {"fenomen": "calor", "nivell": "mig", "dies": []}]},
                 "avisos": [aemet("tempestes", "groc"), aemet("calor", "taronja")],
                 "entorn": {"pla_alfa": {"avui": 4}, "tancaments": [], "incendis": []},
                 "riscos": [{"clau": "calor", "tipus": "calor", "nivell": "groc", "valor": 37, "unitat": "°C"}]}
        claus = self.avalua(ara, f"avisosConduccio({json.dumps(dades)}).map((i) => i.dataset.clau.split(':')[0] + ':' + i.dataset.clau.split(':')[1])",
                            "sortir.js")
        self.assertEqual(claus, ["pla:INUNCAT", "smp:pluja", "aemet:groc"])
        # Sense cap que afecti la conducció, no hi ha línia.
        sense = {"smp": {"fenomens": [{"fenomen": "calor", "nivell": "mig", "dies": []}]}, "entorn": {"pla_alfa": {"avui": 4}}}
        self.assertEqual(self.avalua(ara, f"avisosConduccio({json.dumps(sense)}).length", "sortir.js"), 0)
        self.assertIsNone(self.avalua(ara, f"liniaAvisosConduccio({json.dumps(sense)})", "sortir.js"))
        with open(os.path.join(WEB, "sortir.js"), encoding="utf-8") as f:
            codi = f.read()
        self.assertNotIn("blocAvisos(", codi)
        self.assertNotIn("avís de dalt", codi.replace("// a «l'avís de dalt»", ""))

    def test_punt_de_perill_nomes_amb_un_perill_actiu(self):
        # ADR 0074: el punt vermell, només mentre la situació és activa i no s'ha vist;
        # abans durava 24 hores i sortia amb «Ara no hi ha cap situació de perill».
        ara = "2026-10-12T05:30:00+02:00"
        historial = [{"inici": "2026-10-11T19:30+02:00", "fi": "2026-10-11T19:36+02:00"},
                     {"inici": "2026-10-12T05:00+02:00"},
                     {"inici": "2026-10-12T04:00+02:00", "fins": "2026-10-12T05:00+02:00"}]
        nous = lambda vist: self.avalua(ara, f"perillsNous({json.dumps(historial)}, {json.dumps(vist)}).map((e) => e.inici)")
        self.assertEqual(nous(None), ["2026-10-12T05:00+02:00"])
        self.assertEqual(nous("2026-10-12T05:10:00+02:00"), [])
        self.assertEqual(self.avalua(ara, "perillsNous([{inici: '2026-10-11T19:30+02:00', fi: '2026-10-11T19:36+02:00'}], null)"), [])
        # En pausa (la previsió ja no el veu i espera a tancar-se), no és nou ni actiu (revisor, 19-10-2026).
        self.assertEqual(self.avalua(ara, "perillsNous([{inici: '2026-10-12T05:00+02:00', en_pausa: '2026-10-12T05:20+02:00'}], null)"), [])
        # Un avís actualitzat després de l'última visita també és nou (19-10-2026): l'hora de
        # publicació és la de «Nou» a «Avisos actius» (darrer, o el comunicat d'un pla).
        actualitzat = [{"clau": "smp:pluja", "inici": "2026-10-11T19:30+02:00", "darrer": "2026-10-12T05:20+02:00"}]
        self.assertEqual(self.avalua(ara, f"perillsNous({json.dumps(actualitzat)}, '2026-10-12T05:10:00+02:00').length"), 1)
        self.assertEqual(self.avalua(ara, f"perillsNous({json.dumps(actualitzat)}, '2026-10-12T05:25:00+02:00').length"), 0)
        # I a «Perill», la fitxa porta «Nou» amb el mateix criteri, amb el vist d'en obrir.
        expr = ("desats = {'meteo.perill-vist-fins': '2026-10-12T05:10:00+02:00'};"
                "localStorage.getItem = (k) => desats[k] || null; localStorage.setItem = (k, v) => { desats[k] = v; };"
                f"[esNou({json.dumps(actualitzat[0])}, new Date('{ara}')), "
                f"esNou({json.dumps({'clau': 'smp:x', 'inici': '2026-10-11T19:30+02:00'})}, new Date('{ara}')), "
                f"esNou({json.dumps({'clau': 'smp:y', 'inici': '2026-10-12T05:00+02:00', 'fi': '2026-10-12T05:05+02:00'})}, new Date('{ara}'))]")
        self.assertEqual(self.avalua(ara, expr, pagina="perill.js"), [True, False, False])
        # I a «Ara», les noves primer (19-10-2026): l'actualitzada, tot i haver començat abans,
        # passa davant de la que va començar més tard i ja s'havia vist.
        actius = [{"clau": "smp:vist", "inici": "2026-10-12T05:00+02:00"}, actualitzat[0],
                  {"clau": "smp:nou", "inici": "2026-10-12T05:15+02:00"}]
        expr = ("desats = {'meteo.perill-vist-fins': '2026-10-12T05:10:00+02:00'};"
                "localStorage.getItem = (k) => desats[k] || null; localStorage.setItem = (k, v) => { desats[k] = v; };"
                f"ordreActius({json.dumps(actius)}, new Date('{ara}')).map((e) => e.clau)")
        self.assertEqual(self.avalua(ara, expr, pagina="perill.js"), ["smp:pluja", "smp:nou", "smp:vist"])

    def test_perill_avui_i_dema_d_un_altre_dia(self):
        # Revisor, 20-10-2026: la fitxa acabada del vent del dilluns deia «avui de 17 a 18 h» el dimarts.
        propi = {"clau": "propi", "inici": "2026-10-19T13:09+02:00", "escrit": "2026-10-19T15:00+02:00",
                 "ca": "títol\nVent fort previst: ratxes de fins a 89 km/h, avui de 17 a 18 h.",
                 "es": "título\nViento fuerte previsto: rachas de hasta 89 km/h, hoy de 17 a 18 h."}
        aemet = {"clau": "aemet:pluja:2026-10-17T12:00", "inici": "2026-10-16T00:09+02:00",
                 "ca": "títol\nDes de demà a les 12 h fins a mitjanit.", "es": "título\nDesde mañana a las 12 h hasta medianoche."}
        def text(e, ara, idioma="ca"):
            return self.avalua(ara, f"IDIOMA.codi = '{idioma}'; textFitxa({json.dumps(e)}, new Date('{ara}')).split('\\n')[1]",
                               pagina="perill.js")
        self.assertEqual(text(propi, "2026-10-20T17:31:00+02:00"), "Vent fort previst: ratxes de fins a 89 km/h, dilluns 19 de 17 a 18 h.")
        self.assertEqual(text(propi, "2026-10-20T17:31:00+02:00", "es"), "Viento fuerte previsto: rachas de hasta 89 km/h, lunes 19 de 17 a 18 h.")
        self.assertEqual(text(propi, "2026-10-20T17:31:00+02:00", "gl"), "Vent fort previst: ratxes de fins a 89 km/h, dilluns 19 de 17 a 18 h.")
        # El mateix dia, com es va escriure.
        self.assertEqual(text(propi, "2026-10-19T20:00:00+02:00"), "Vent fort previst: ratxes de fins a 89 km/h, avui de 17 a 18 h.")
        # Les d'abans, sense `escrit`: el començament; «demà», el dia següent.
        self.assertEqual(text(aemet, "2026-10-20T17:31:00+02:00"), "Des del dissabte 17 a les 12 h fins a mitjanit.")
        self.assertEqual(text(aemet, "2026-10-20T17:31:00+02:00", "es"), "Desde el sábado 17 a las 12 h hasta medianoche.")
        # La franja de l'AEMET d'abans del 18-10-2026, amb coma (revisor, 20-10-2026 21:01).
        franja = {"clau": "aemet:pluja:2026-10-18T00:00", "inici": "2026-10-17T00:39+02:00",
                  "ca": "títol\nDemà, de les 0 h a les 4 h.", "es": "título\nMañana, de las 0 h a las 4 h."}
        self.assertEqual(text(franja, "2026-10-20T21:01:00+02:00"), "Diumenge 18, de les 0 h a les 4 h.")
        self.assertEqual(text(franja, "2026-10-20T21:01:00+02:00", "es"), "Domingo 18, de las 0 h a las 4 h.")

    def test_grafica_sempre_totes_les_hores(self):
        # Juanjo, 20-10-2026: «quiero que hagas siempre tot pero con barra de desplazamiento
        # horizontal… hora a hora». Sense el selector «24 h · Demà · Tot»; cada hora, COL_HORA px.
        hores = [{"hora": f"2026-10-{20 + (6 + h) // 24}T{(6 + h) % 24:02d}:00",
                  "fins": f"2026-10-{20 + (7 + h) // 24}T{(7 + h) % 24:02d}:00", "temperatura": 15} for h in range(40)]
        ara = "2026-10-20T08:10:00+02:00"
        r = self.avalua(ara, f"HORES_GRAFICA = {json.dumps(hores)}; [horesVista().length, typeof tramGrafica, COL_HORA]")
        self.assertEqual(r, [38, "undefined", 36])

    def test_perill_agrupa_els_de_l_aemet_que_coincideixen(self):
        # Juanjo, 20-10-2026: la portada deia 2 avisos i «Perill» 5, amb tres de l'AEMET (tempestes de
        # 19 a 9 h i pluja de 20 mm i de 80 mm de 6 a 9 h) que la portada fa en una sola línia.
        def aemet(tipus, inici, comenca, nivell="groc"):
            return {"clau": f"aemet:{tipus}:{inici}", "inici": "2026-10-19T19:27+02:00", "nivell": nivell,
                    "comenca": comenca, "fins": "2026-10-20T08:59:59+02:00"}
        actius = [{"clau": "pla:INUNCAT", "inici": "2026-10-15T19:09+02:00"},
                  aemet("pluja", "2026-10-20T00:00", "2026-10-20T06:00:00+02:00"),
                  aemet("tempestes", "2026-10-19T19:00", "2026-10-19T19:00:00+02:00"),
                  aemet("pluja", "2026-10-19T19:00", "2026-10-20T06:00:00+02:00"),
                  dict(aemet("vent", "2026-10-20T00:00", "2026-10-20T06:00:00+02:00"), nivell="taronja"),
                  dict(aemet("neu", "2026-10-21T00:00", "2026-10-21T10:00:00+02:00"), fins="2026-10-21T12:00:00+02:00")]
        def grups(actius, ara):
            expr = (f"grupsAemet({json.dumps(actius)}, new Date('{ara}'))"
                    ".map((g) => g.map((e) => e.clau.split(':')[1] || e.clau))")
            return self.avalua(ara, expr, pagina="perill.js")
        # A les 06:10, les tres van de «ara» a les 9: una sola línia a la portada i una sola fitxa.
        self.assertEqual(grups(actius, "2026-10-20T06:10:00+02:00"),
                         [["INUNCAT"], ["pluja", "tempestes", "pluja"], ["vent"], ["neu"]])
        # A les 05:50, la pluja encara comença a les 6 i les tempestes ja són actives: la portada en fa
        # dues línies («tempestes, fins a les 9» i «pluja, de 6 a 9»), i «Perill», dues fitxes.
        self.assertEqual(grups(actius, "2026-10-20T05:50:00+02:00"),
                         [["INUNCAT"], ["pluja", "pluja"], ["tempestes"], ["vent"], ["neu"]])

    def test_grafica_pluja_forta_i_torrencial(self):
        # ADR 0096: les barres de la gràfica, amb les intensitats de Meteocat (les de la columna «Cel»).
        ara = "2026-10-12T10:00:00+02:00"
        self.assertEqual([self.avalua(ara, f"intensitatPluja({mm})") for mm in (5, 39.9, 40, 79.9, 80)],
                         [None, None, "forta", "forta", "torrencial"])
        self.assertEqual(self.avalua(ara, "cel({hora: '2026-10-12T12:00', probabilitat: 0.9, pluja_mm: 40, codi: 63, nuvols: 100})[0]"),
                         "Pluja forta")

    def test_resum_del_dia_a_la_portada(self):
        # ADR 0074 i 0076: el text de «Consultes › Avui», sense «Ara mateix», la roba ni l'AEMET (ja és a dalt);
        # des de les 18 h, també demà.
        avui = ("<b>El temps avui</b>\n⟦i-sun⟧ Ara mateix: 13 °C, no plou.\nSense pluja prevista.\n"
                "⟦alt⟧ Avís taronja de l'AEMET per pluja al Vallès fins a les 15:46.\n\n"
                "Roba per anar a peu: a les 7 h (13 °C), jaqueta.")
        dades = lambda h: json.dumps({"generat": f"2026-10-12T{h}:00+02:00", "consultes": {"ca": {"avui": avui, "dema": "<b>Demà</b>"}}})
        self.assertEqual(self.avalua("2026-10-12T10:00:00+02:00", f"textosResum({dades('10:00')})"),
                         ["<b>El temps avui</b>\nSense pluja prevista.\n"])
        self.assertEqual(len(self.avalua("2026-10-12T18:10:00+02:00", f"textosResum({dades('18:00')})")), 2)
        self.assertEqual(self.avalua("2026-10-12T10:00:00+02:00", "textosResum({generat: '2026-10-12T10:00:00+02:00'})"), [])

    def test_talls_de_llum_als_avisos_actius(self):
        # ADR 0074: els talls del barri també a «Avisos actius», amb els carrers estimats.
        tall = {"programat": False, "on": "dins", "clients": 143, "inici": "2026-10-12T04:52+02:00",
                "fins": "2026-10-12T07:52+02:00", "carrers": ["Carrer A", "Carrer B"]}
        self.assertEqual(self.avalua("2026-10-12T05:30:00+02:00", f"textTall({json.dumps(tall)})"),
                         ["Tall de llum al barri", "avaria. 143 clients sense llum des de les 04:52; previst fins a les 07:52. "
                          "Carrers probables (estimació): Carrer A o Carrer B."])
        tall = {"programat": True, "on": "vora", "clients": 1, "inici": "2026-10-11T09:00+02:00"}
        self.assertEqual(self.avalua("2026-10-12T05:30:00+02:00", f"textTall({json.dumps(tall)})"),
                         ["Tall de llum al límit del barri", "treballs programats. 1 client sense llum des del 11/10 a les 09:00."])

    def test_enrere_porta_a_la_portada_i_despres_fora(self):
        # ADR 0074 i 0076: de la portada a una pestanya s'apunta; entre pestanyes se substitueix; d'una
        # pestanya a una explicació s'apunta (enrere torna a l'avís); tornar a la portada és fer enrere
        # tots els passos; el canvi d'idioma no s'apunta. [acció, profunditat de la pàgina nova].
        w = "https://meteo-montflorit.github.io/"
        com = lambda a, b, p: self.avalua("2026-10-12T10:00:00+02:00", f"comNavega({json.dumps(w + a)}, {json.dumps(w + b)}, {json.dumps(p)})")
        self.assertEqual(com("", "perill.html", 0), ["apunta", 1])
        self.assertEqual(com("perill.html", "sortir.html", 1), ["substitueix", 1])
        self.assertEqual(com("sortir.html", "", 1), ["enrere", 0])
        self.assertEqual(com("perill.html", "com-funciona.html", 1), ["apunta", 2])
        self.assertEqual(com("com-funciona.html", "", 2), ["enrere", 0])
        self.assertEqual(com("com-funciona.html", "fonts.html", 2), ["substitueix", 2])
        # D'una explicació a una pestanya, enrere fins a la de sota i se substitueix (16-10-2026).
        self.assertEqual(com("avisos.html", "consultes.html", 2), ["torna", 1])
        self.assertEqual(com("avisos.html", "consultes.html", 1), ["substitueix", 1])  # de la portada a «Avisos»
        self.assertEqual(com("avisos.html", "consultes.html", None), ["substitueix", None])
        self.assertEqual(com("perill.html", "./", None), ["substitueix", None])     # hi ha entrat per un enllaç
        self.assertEqual(com("perill.html", "com-funciona.html", None), ["apunta", None])
        self.assertEqual(com("", "es/", 0), ["substitueix", 0])                      # l'idioma
        self.assertEqual(com("es/perill.html", "perill.html", 1), ["substitueix", 1])
        self.assertEqual(com("casa.html", "perill.html", 0), ["apunta", 1])         # la pàgina de casa

    def test_linies_del_resum_amb_detall(self):
        # ADR 0075: els trens, a «Consultes › Trens»; els avisos de l'AEMET, a «Perill»; la resta, sense.
        d = lambda t: self.avalua("2026-10-12T10:00:00+02:00", f"detallLinia({json.dumps(t)})")
        self.assertEqual(d("Trens de Cerdanyola:  R4 amb incidències."), "consultes.html#trens")
        self.assertEqual(d(" Trenes de Cerdanyola sin incidencias."), "consultes.html#trens")
        self.assertEqual(d(" Avís groc de l'AEMET per pluja al Vallès fins a les 20:00."), "perill.html")
        self.assertEqual(d("AEMET: aviso amarillo por lluvia en el Vallès hasta las 20:00."), "perill.html")
        self.assertIsNone(d("Sense pluja prevista."))
        self.assertIsNone(d("Temperatura d'aquí a mitjanit: entre 13 °C i 23 °C."))

    def test_perill_a_les_hores_i_als_trams(self):
        # ADR 0076: el perill calculat per la web marca les hores que toca, com els avisos de l'AEMET,
        # i el tram en porta el nivell més alt i què és.
        ara = "2026-10-12T07:30:00+02:00"
        f = lambda h, avisos=(): {"hora": f"2026-10-12T{h:02d}:00", "fins": f"2026-10-12T{h + 1:02d}:00", "avisos": list(avisos)}
        risc = {"tipus": "pluja_3h", "origen": "previsio", "nivell": "taronja",
                "des_de": "2026-10-12T08:00+02:00", "fins": "2026-10-12T09:00+02:00"}
        hores = [f(7), f(8, [{"nivell": "groc", "tipus": ["pluja"]}]), f(9)]
        expr = (f"hs = {json.dumps(hores)}; for (const x of hs) x.riscos_hora = riscosHora(x, [{json.dumps(risc)}]);"
                "[hs.map((x) => avisHora(x) && [avisHora(x).nivell, avisHora(x).fonts, avisHora(x).noms]), perillTram(hs)]")
        r = self.avalua(ara, expr)
        # Només el que dona el nivell més alt: el groc de l'AEMET per pluja queda sota el taronja de la web.
        self.assertEqual(r[0], [None, ["taronja", "web", ["pluja intensa"]], None])
        self.assertEqual(r[1], {"nivell": "taronja", "noms": ["pluja intensa"], "fonts": "web",
                                "perFont": [["web", ["pluja intensa"], "taronja"]]})
        # Fenòmens diferents de nivells diferents, tots dos, del més alt al més baix
        # (Juanjo, 17-10-2026: «que la franja diga las dos cosas»).
        dos = f(8, [{"nivell": "taronja", "tipus": ["pluja"], "font": "meteocat"}, {"nivell": "groc", "tipus": ["tempestes"]},
                    {"nivell": "groc", "tipus": ["pluja"], "font": "meteocat"}])
        self.assertEqual(self.avalua(ara, f"[textPerillCurt(avisHora({json.dumps(dos)})), textPerill(avisHora({json.dumps(dos)})), avisHora({json.dumps(dos)}).nivell]"),
                         ["Perill alt: pluja · Avís groc: tempestes",
                          "Meteocat: perill alt per pluja; AEMET: avís groc per tempestes", "taronja"])
        # El text del tram: Meteocat en grau de perill; i, en passar-hi el ratolí, d'on surt (ADR 0093).
        p = {"nivell": "taronja", "noms": ["pluja", "tempestes"], "fonts": "meteocataemet",
             "perFont": [["meteocat", ["pluja"]], ["aemet", ["tempestes"]]]}
        self.assertEqual(self.avalua(ara, f"[textPerillCurt({json.dumps(p)}), textPerill({json.dumps(p)})]"),
                         ["Perill alt: pluja · Avís taronja: tempestes",
                          "Meteocat: perill alt per pluja; AEMET: avís taronja per tempestes"])
        self.assertIsNone(self.avalua(ara, f"perillTram({json.dumps([f(7)])})"))
        # D'on surt la tempesta, sense repetir l'avís del perill ni «aEMET» (revisor, 19-10-2026).
        aemet = {"nivell": "groc", "noms": ["pluja", "tempestes"], "fonts": "aemet",
                 "perFont": [["aemet", ["pluja", "tempestes"]]]}
        tram = lambda perill, origen: f"origenTram({{perill: {json.dumps(perill)}, fenomens: [['tempesta', 'i-cloud-lightning', {json.dumps(origen)}]]}})"
        self.assertEqual(self.avalua(ara, tram(aemet, "AEMET: avís groc per tempestes")),
                         "AEMET: avís groc per pluja i tempestes.")
        self.assertEqual(self.avalua(ara, tram(aemet, "AEMET: avís groc per tempestes; Els models preveuen tempesta")),
                         "AEMET: avís groc per pluja i tempestes. Tempesta: els models preveuen tempesta.")
        self.assertEqual(self.avalua(ara, tram(None, "AEMET: avís groc per tempestes")),
                         "Tempesta: AEMET: avís groc per tempestes.")

    def test_en_obrir_la_web_marxen_les_notificacions(self):
        # ADR 0048: en obrir la web o tornar-hi, les seves notificacions es treuen de la safata.
        expr = ("tancades = 0; const n = () => ({ close() { tancades += 1; } });"
                "navigator.serviceWorker = { getRegistration: () => Promise.resolve({ getNotifications: () => Promise.resolve([n(), n()]) }) };"
                "tancaNotificacions().then((k) => [k, tancades])")
        self.assertEqual(self.avalua("2026-10-12T10:00:00+02:00", expr, arnes=ARNES_ASYNC), [2, 2])
        # Sense service worker (un navegador antic), res.
        self.assertEqual(self.avalua("2026-10-12T10:00:00+02:00", "tancaNotificacions()", arnes=ARNES_ASYNC), 0)

    def test_un_avis_amb_la_web_oberta_la_posa_al_dia(self):
        # ADR 0048: el service worker mostra la notificació i avisa les finestres obertes; la pàgina,
        # en rebre-ho, torna a llegir el que tenia apuntat.
        sw = r"""
const vm = require('vm'); const fs = require('fs');
const [web] = process.argv.slice(1);
const h = {}; const enviats = []; let mostrades = 0;
const ctx = vm.createContext({ Date, URL, JSON, String, Promise, console, location: { origin: 'https://m.test' },
  self: { addEventListener(t, f) { h[t] = f; }, registration: { scope: 'https://m.test/',
    showNotification() { mostrades += 1; return Promise.resolve(); } },
    clients: { matchAll: () => Promise.resolve([{ postMessage: (m) => enviats.push(m) }]) } } });
vm.runInContext(fs.readFileSync(`${web}/sw.js`, 'utf8'), ctx);
let espera;
h.push({ data: { json: () => ({ title: 'Perill', body: 'x' }) }, waitUntil(p) { espera = p; } });
espera.then(() => console.log(JSON.stringify([mostrades, enviats])));
"""
        r = subprocess.run(["node", "-e", sw, WEB], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(r.stdout), [1, [{"tipus": "avis"}]])
        self.assertEqual(self.avalua("2026-10-12T10:00:00+02:00",
                                     "n = 0; enArribarUnAvis(() => { n += 1; }); enArribarUnAvis(() => { n += 10; }); arribaUnAvis(); n"), 11)

    def test_oferta_d_avisos_nomes_a_qui_te_la_web_installada(self):
        # ADR 0080: la targeta surt si la web és instal·lada, encara no té els avisos, no s'ha dit
        # «Ara no» i el navegador no els té bloquejats.
        def cal(installada=True, subscrit=False, no=False, permis="default"):
            expr = (f"matchMedia = (q) => ({{ matches: {json.dumps(installada)} && q.includes('standalone'), addEventListener() {{}} }});"
                    f"Notification = {{ permission: {json.dumps(permis)} }}; PushManager = function () {{}};"
                    "window.Notification = Notification; window.PushManager = PushManager;"
                    f"navigator.serviceWorker = {{ ready: Promise.resolve({{ pushManager: {{ getSubscription: () => Promise.resolve({json.dumps(subscrit)} ? {{}} : null) }} }}) }};"
                    f"localStorage.getItem = (k) => ({json.dumps(no)} && k === 'meteo.oferta-avisos' ? 'no' : null);"
                    "calOfertaAvisos()")
            return self.avalua("2026-10-12T10:00:00+02:00", expr, arnes=ARNES_ASYNC.replace(
                "Date: FakeDate, Math,", "Date: FakeDate, Math, PushManager: undefined, Notification: undefined,"))
        self.assertTrue(cal())
        self.assertFalse(cal(installada=False))
        self.assertFalse(cal(subscrit=True))
        self.assertFalse(cal(no=True))
        self.assertFalse(cal(permis="denied"))

    def test_la_franja_del_radar_nomes_si_diu_alguna_cosa(self):
        # «No s'acosta pluja» només surt si la previsió en dona en les dues
        # hores que venen (Juanjo, 10-10-2026; ADR 0019).
        ara = "2026-10-10T10:20:00+02:00"
        hora = lambda h, p: {"hora": f"2026-10-10T{h:02d}:00", "fins": f"2026-10-10T{h + 1:02d}:00",
                             "probabilitat": p, "pluja_mm": 0}
        sec = [hora(10, 0), hora(11, 0), hora(12, 0.1), hora(13, 0.6)]
        self.assertFalse(self.avalua(ara, f"plujaPrevistaAviat({json.dumps(sec)}, new Date())"))
        aviat = [hora(10, 0), hora(11, 0), hora(12, 0.25)]
        self.assertTrue(self.avalua(ara, f"plujaPrevistaAviat({json.dumps(aviat)}, new Date())"))
        # Una hora que comença passades les dues hores no compta.
        self.assertFalse(self.avalua(ara, f"plujaPrevistaAviat({json.dumps([hora(13, 0.9)])}, new Date())"))
        self.assertFalse(self.avalua(ara, "plujaPrevistaAviat(undefined, new Date())"))
        # La primera hora amb pluja que comença, i la seva probabilitat
        # (17-10-2026): la de les 12, encara que la de les 10 en curs en doni.
        hores = [hora(10, 0.3), hora(11, 0.1), hora(12, 0.49), hora(13, 0.7)]
        self.assertEqual(self.avalua(ara, f"primeraPluja({json.dumps(hores)}, new Date()).hora"), "2026-10-10T12:00")
        self.assertEqual(self.avalua(ara, f"textPct(primeraPluja({json.dumps(hores)}, new Date()))"), " (49\u00a0%)")
        self.assertIsNone(self.avalua(ara, f"primeraPluja({json.dumps(sec[:2])}, new Date())"))

    def test_icones_del_cel_amb_els_seus_colors(self):
        # ADR 0063: cada icona del temps que posa la pàgina de casa té les
        # peces pintades amb els colors del cel (sol, núvol, aigua, neu, lluna);
        # i la paleta és als dos temes.
        import re
        # El cel de cada hora és a grafica.js (el comparteix amb «Consultes»).
        codi = "".join(open(os.path.join(WEB, n), encoding="utf-8").read() for n in ("grafica.js", "casa.js"))
        usades = set(re.findall(r"'(i-(?:cloud[a-z-]*|sun|moon-cel|snowflake|umbrella|droplets))'", codi))
        with open(os.path.join(WEB, "casa.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("i-cloud-sun", usades)
        for id_ in usades:
            simbol = re.search(rf'<symbol id="{id_}"[^>]*>(.*?)</symbol>', html).group(1)
            self.assertIn("var(--ic-", simbol, id_)
        with open(os.path.join(WEB, "estil.css"), encoding="utf-8") as f:
            css = f.read()
        temes = css.split(':root[data-theme="dark"]')
        for color in ("--c-sol:", "--c-nuvol:", "--c-aigua:", "--c-aigua-text:", "--c-neu:", "--c-lluna:", "--c-maxima:", "--c-minima:"):
            self.assertIn(color, temes[0], color)
            self.assertIn(color, temes[1].split("}")[0], color)


if __name__ == "__main__":
    unittest.main()
