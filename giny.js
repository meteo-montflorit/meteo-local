#!/usr/bin/env node
// SPDX-License-Identifier: AGPL-3.0-or-later
// El giny de la pantalla d'inici d'Android (ADR 0131): el que diu la targeta
// d'«Ara» de la portada, en català i en castellà, en un JSON petit
// (giny.json) que l'app llegeix cada mitja hora. Els textos no es tornen a
// escriure aquí: es carreguen comu.js, grafica.js i casa.js (i es.js per al
// castellà) amb un DOM mínim, es crida la mateixa funció que pinta la targeta
// (blocAra) i se'n llegeix el text. Així el giny diu sempre el mateix que la
// web, amb la zona per defecte (la riera).
//
// Ús: node giny.js montflorit.json giny.json
'use strict';
const vm = require('vm');
const fs = require('fs');
const path = require('path');

const ARREL = __dirname;

// Per a les proves, una hora fixa (GINY_ARA, ISO): «ara» és aquella hora.
const ARA = process.env.GINY_ARA;
const DataReal = Date;
class DataFixa extends DataReal {
  constructor(...a) { super(...(a.length ? a : [ARA])); }
  static now() { return new DataReal(ARA).getTime(); }
}
const DATA = ARA ? DataFixa : Date;

// --- Un DOM mínim: el que fan servir element(), icona() i blocAra.
class Text {
  constructor(t) { this.nodeType = 3; this.data = String(t); this.parentElement = null; }
  get textContent() { return this.data; }
}

class Element {
  constructor(tag) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.childNodes = [];
    this.attrs = {};
    this.dataset = {};
    this.style = { setProperty() {} };
    this.hidden = false;
    this.className = '';
    this.parentElement = null;
    this.isConnected = true;
  }
  get classList() {
    const el = this;
    const llista = () => el.className.split(/\s+/).filter(Boolean);
    return {
      add: (...c) => { el.className = [...new Set([...llista(), ...c])].join(' '); },
      remove: (...c) => { el.className = llista().filter((x) => !c.includes(x)).join(' '); },
      toggle: (c, si) => {
        const posa = si === undefined ? !llista().includes(c) : si;
        if (posa) el.classList.add(c); else el.classList.remove(c);
        return posa;
      },
      contains: (c) => llista().includes(c),
      [Symbol.iterator]: () => llista()[Symbol.iterator](),
    };
  }
  get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
  get childElementCount() { return this.children.length; }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(''); }
  set textContent(t) { this.replaceChildren(t); }
  node(x) {
    const n = x instanceof Element || x instanceof Text ? x : new Text(x);
    if (n.parentElement) n.parentElement.childNodes = n.parentElement.childNodes.filter((c) => c !== n);
    n.parentElement = this;
    return n;
  }
  append(...xs) { this.childNodes.push(...xs.map((x) => this.node(x))); }
  prepend(...xs) { this.childNodes.unshift(...xs.map((x) => this.node(x))); }
  replaceChildren(...xs) { this.childNodes = []; this.append(...xs); }
  remove() { if (this.parentElement) this.parentElement.childNodes = this.parentElement.childNodes.filter((c) => c !== this); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k === 'src' && this.src !== undefined ? this.src : (this.attrs[k] ?? null); }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
  // Els descendents amb una classe, en ordre.
  ambClasse(c) {
    const r = [];
    for (const n of this.children) {
      if (n.classList.contains(c)) r.push(n);
      r.push(...n.ambClasse(c));
    }
    return r;
  }
}

// El text d'un element en trossos: el text fix i els comptes enrere
// («d'aquí a unes 10 hores»), que el giny torna a escriure a cada
// actualització, perquè l'hora del JSON ja no és la d'ara.
function trossos(el) {
  const r = [];
  const posa = (t) => {
    if (typeof t === 'string' && typeof r[r.length - 1] === 'string') r[r.length - 1] += t;
    else r.push(t);
  };
  const recorre = (n) => {
    if (n.nodeType === 3) return posa(n.data);
    if (n.hidden || n.tagName === 'svg' || n.tagName === 'SVG') return;
    if (n.classList.contains('compte') && n.dataset.t) {
      return posa({ compte: n.dataset.t, hores: Boolean(n.dataset.hores) });
    }
    n.childNodes.forEach(recorre);
  };
  recorre(el);
  return r.map((t) => (typeof t === 'string' ? t.replace(/[ \t\n\r]+/g, ' ') : t))
    .map((t, i, a) => (typeof t !== 'string' ? t : i === 0 ? t.trimStart() : i === a.length - 1 ? t.trimEnd() : t))
    .filter((t) => t !== '');
}

const text = (el) => (el ? trossos(el).map((t) => (typeof t === 'string' ? t : '')).join('').trim() : null);

function context(idioma) {
  const el = (tag) => new Element(tag);
  // Els elements fixos de la pàgina (botons, capçalera): no hi són, i el que
  // s'hi fa es perd.
  const rebuig = () => {
    const e = el('div');
    e.querySelector = () => el('use');
    return e;
  };
  const ctx = vm.createContext({
    Date: DATA, Math, JSON, Number, Object, Set, Map, String, Array, Boolean, RegExp, Intl, console, URLSearchParams,
    document: {
      querySelectorAll: () => [], querySelector: () => null, getElementById: () => rebuig(),
      createElement: el, createElementNS: (_, tag) => el(tag), createTextNode: (t) => new Text(t),
      addEventListener() {}, body: null,
      documentElement: { dataset: { lloc: 'Montflorit', estacio: idioma === 'es' ? 'la estación particular' : 'l’estació particular' },
        setAttribute() {}, classList: { add() {}, remove() {}, toggle() {} } },
    },
    matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, AbortController,
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    sessionStorage: { getItem: () => null, setItem() {} },
    navigator: {}, location: { pathname: '/', search: '' },
    fetch: () => new Promise(() => {}), setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0,
    requestAnimationFrame: () => 0,
  });
  const fitxers = [...(idioma === 'es' ? ['montflorit/es.js'] : []), 'web/comu.js', 'web/grafica.js', 'web/casa.js'];
  for (const f of fitxers) vm.runInContext(fs.readFileSync(path.join(ARREL, f), 'utf8'), ctx, { filename: f });
  return ctx;
}

// La targeta d'«Ara» d'un idioma, en dades.
function targeta(dades, idioma) {
  const ctx = context(idioma);
  ctx.DADES = dades;
  const r = vm.runInContext(`(() => {
    const d = DADES;
    const radar = d.radar && d.pluja_ara ? { ...d.radar, pluja: d.pluja_ara } : d.radar;
    const sec = d.ara_casa && blocAra(d.ara_casa, radar, d.vent, d.veines, d.hores, mesuradaZona(d), d.sol, d.lluna);
    const fase = faseAProp(d.lluna);
    const plou = !!(d.ara_casa && d.ara_casa.plou) || (d.veines || []).some((v) => v.plou && v.compta);
    const cel = d.hores && celPortada(d.hores, plou, radar);
    // La pluja en curt, per a la gota dels ginys petits (ADR 0131), amb el mateix
    // criteri que la línia de sota la frase (titularAra): si el radar en diu
    // alguna cosa, el radar; si no, la primera hora de pluja de la previsió.
    const estat = radar && radar.pluja && radar.pluja.estat;
    let gota = null;
    if (plou || estat === 'plou' || estat === 'radar_sobre') gota = T('Plou');
    else if (['arriba', 'possible'].includes(estat) && radar) {
      const quan = radar.arriba || radar.possible;
      if (quan) gota = franjaRadar(quan) || horaCurta(quan);
    } else {
      const f = primeraPluja(d.hores);
      if (f) {
        const pct = f.probabilitat == null ? '' : ' · ' + Math.round(f.probabilitat * 100) + '\\u00a0%';
        gota = horaLocal(f.hora) + '\\u00a0h' + pct;
      }
    }
    return { sec, fase, cel, gota, nomFase: fase ? NOM_FASE_LLUNA()[fase.fase] : null, quanFase: fase ? quanFase(fase.hora) : null };
  })()`, ctx);
  if (!r.sec) return null;
  // Els textos del compte enrere (textCompte), amb {0} i {1} on van les xifres,
  // perquè el giny el torni a escriure. T rep els trossos com una plantilla.
  const T = (...trossos) => ctx.T(trossos, ...trossos.slice(1).map((_, i) => `{${i}}`));
  r.textos = {
    menys_hora: T('d’aquí a menys d’una hora'), una_hora: T('d’aquí a una hora'), hores: T('d’aquí a unes ', ' hores'),
    ara: T('ara mateix'), un_minut: T('d’aquí a 1 minut'), minuts: T('d’aquí a ', ' minuts'),
    h_min: T('d’aquí a ', '\u00a0h ', '\u00a0min'), h: T('d’aquí a ', '\u00a0h'),
  };
  const sec = r.sec;
  const primer = (c) => sec.ambClasse(c)[0] || null;
  const titular = primer('titular');
  const frase = primer('titular-cel');
  // La línia de sota la frase: la pluja prevista, la del radar o «Sense pluja prevista».
  const linia = titular ? titular.children.find((n) => n !== frase) : null;
  const dia = primer('ara-dia');
  const max = dia && dia.ambClasse('temp-max')[0];
  const min = dia && dia.ambClasse('temp-min')[0];
  const compara = dia && dia.ambClasse('alta')[0];
  const sol = primer('heroi-sol');
  const titol = idioma === 'es' ? 'Tiempo en Montflorit (Cerdanyola)' : 'Temps a Montflorit (Cerdanyola)';
  return {
    titol,
    frase: text(frase),
    linia: linia ? trossos(linia) : null,
    linia_pluja: Boolean(linia && /pluja-prevista|pluja-radar/.test(linia.className)),
    temperatura: text(primer('veredicte')),
    dia: dia ? {
      quan: text(dia).split(':')[0] + ':',
      max: text(max), min: text(min), compara: text(compara),
    } : null,
    sol: sol && !sol.hidden ? text(sol) : null,
    lluna: r.fase ? { text: `${r.nomFase}: ${r.quanFase}`, angle: { nova: 0, quart_creixent: 90, plena: 180, quart_minvant: 270 }[r.fase.fase] } : null,
    pastilles: (primer('dades-ara') ? primer('dades-ara').children : []).map(text).filter(Boolean),
    cel: r.cel ? { fons: r.cel.fons, dibuix: r.cel.dibuix, moment: r.cel.moment } : null,
    gota: r.gota,
    textos: r.textos,
  };
}

function giny(dades) {
  const ca = targeta(dades, 'ca');
  const es = targeta(dades, 'es');
  return {
    versio: dades.versio, generat: dades.generat, mesura: dades.ara_casa ? dades.ara_casa.hora : null,
    web: { ca: 'https://meteo-montflorit.github.io/', es: 'https://meteo-montflorit.github.io/es/' },
    ca, es,
  };
}

if (require.main === module) {
  const [entrada, sortida] = process.argv.slice(2);
  if (!entrada || !sortida) {
    console.error('Ús: node giny.js montflorit.json giny.json');
    process.exit(2);
  }
  const g = giny(JSON.parse(fs.readFileSync(entrada, 'utf8')));
  fs.writeFileSync(sortida, JSON.stringify(g));
}

module.exports = { giny };
