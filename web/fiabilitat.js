// SPDX-License-Identifier: AGPL-3.0-or-later
// «Fiabilitat»: quant encerta la previsió de la web, comparada amb el que es
// mesura al barri i amb les de Meteocat i AEMET per a Cerdanyola, si millora
// setmana a setmana i com aprèn (ADR 0110). Abans era el botó «Com encerta»
// de la gràfica en gran (ADR 0099); Juanjo, 20-10-2026: «debería pasarse a una
// página propia y quitarlo de ahí… la mayoría de la gente jamás lo utilizará»,
// i després, en veure-la: «llamale de otro modo y sobre todo falta claridad…
// texto vertical, haz alguna grafica comparativa de lo que dices y no veo nada
// sobre como aprende la web». S'hi arriba des del menú ⋮.
// Les dades, de historial.py: historial.json (l'índex: l'encert, les setmanes,
// les oficials i l'aprenentatge) i historial-AAAA-MM-DD.json (cada dia, hora a
// hora). L'antelació i el dia van a l'adreça (?h=6&dia=2026-10-15), perquè
// compartir doni el mateix. La temperatura i la pluja, sempre totes dues, una
// gràfica per a cadascuna: un selector que només canviava algunes gràfiques
// confonia (Juanjo, 20-10-2026: «sin selector que confunde»).

const ANTELACIO_MAX = 23;
const SEGURETAT = 0.95;
let INDEX = null;
const estat = { antelacio: 1, dia: null };

// Les sèries, cadascuna amb el seu color i el seu traç (no només el color).
const SERIES = () => ({
  web: T('Aquesta web'), meteocat: 'Meteocat', aemet: 'AEMET', vigent: T('L’actual'), candidata: T('La nova, en entrenament'),
});

// llegeixHistorial, llegeixDiaHistorial i avuiIso, de grafica.js: també els fa
// servir l'historial de la gràfica en gran (ADR 0124).

function codiData() {
  return IDIOMA.codi === 'es' ? 'es' : 'ca';
}

function nomData(iso, opcions = { day: 'numeric', month: 'long' }) {
  return new Date(`${iso}T12:00`).toLocaleDateString(codiData(), opcions);
}

function dataCurta(iso) {
  return new Date(`${iso}T12:00`).toLocaleDateString(codiData(), { day: 'numeric', month: 'short' });
}

// --- L'adreça ---
function llegeixAdreca() {
  const p = new URLSearchParams(location.search);
  const h = Number(p.get('h'));
  if (h >= 1 && h <= ANTELACIO_MAX) estat.antelacio = Math.round(h);
  const d = p.get('dia');
  if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) estat.dia = d;
}

function desaAdreca() {
  const p = new URLSearchParams();
  if (estat.antelacio !== 1) p.set('h', String(estat.antelacio));
  if (estat.dia && estat.dia !== avuiIso()) p.set('dia', estat.dia);
  const cerca = p.toString();
  history.replaceState(history.state, '', location.pathname + (cerca ? `?${cerca}` : '') + location.hash);
}

// --- Com es diu: conclusions curtes ---

function textPeriode(periode) {
  if (!periode || periode.dies >= 30) return T('Els darrers 30 dies.');
  return T`Des del ${nomData(periode.des_de)} fins ara (${periode.dies} dies).`;
}

// Si una diferència és segura (95 % dels remostrejos per dies, remostreig.py),
// dit perquè ho entengui tothom: «no és casualitat» (Juanjo, 20-10-2026: «hazte
// a la idea de que hablas para gente sin conocimientos ni de esta web y con
// pocos estudios… lo que se ponga sea realmente informativo»).
function textSegur(s) {
  if (s == null) return T('encara poques dades per saber-ho');
  if (s >= SEGURETAT || s <= 1 - SEGURETAT) return T('no és casualitat');
  return T('encara pot ser casualitat');
}

// Una xifra gran amb el que vol dir a sota (Juanjo: «sin tener que descifrar cifras»).
function xifra(titol, valor, peu, nota) {
  const el = element('div', 'fb-xifra');
  el.append(element('p', 'fb-xifra-titol', titol), element('p', 'fb-xifra-valor', valor), element('p', 'fb-xifra-peu', peu));
  if (nota) el.append(element('p', 'fb-xifra-nota', nota));
  return el;
}

function xifraTemperatura(t, minim) {
  if (!t || t.error == null || t.hores < minim) {
    return xifra(T('Temperatura a la riera'), '—', T`Encara poques dades (${t ? t.hores : 0} hores).`);
  }
  let nota = null;
  if (t.biaix != null && Math.abs(t.biaix) >= 0.1) {
    nota = t.biaix > 0 ? T`Sol dir ${coma(t.biaix)}\u00a0°C més del que fa.` : T`Sol dir ${coma(-t.biaix)}\u00a0°C menys del que fa.`;
  }
  return xifra(T('Temperatura a la riera'), `${coma(t.error)}\u00a0°C`, T('és el que s’equivoca, de mitjana'), nota);
}

// La part alta (ADR 0125): el que diu la web per a dalt contra el que mesuren
// les veïnes de dalt i, a les mateixes hores, el que s'equivoca a la riera.
function xifraAlta(a, minim) {
  if (!a || a.error == null || a.hores < minim) {
    return xifra(T('Temperatura a la part alta'), '—', T`Encara poques dades (${a ? a.hores : 0} hores).`);
  }
  const notes = [T`A les mateixes hores, a la riera: ${coma(a.error_riera)}\u00a0°C; la diferència ${textSegur(a.seguretat)}.`];
  if (a.biaix != null && Math.abs(a.biaix) >= 0.1) {
    notes.push(a.biaix > 0 ? T`Sol dir ${coma(a.biaix)}\u00a0°C més del que fa.` : T`Sol dir ${coma(-a.biaix)}\u00a0°C menys del que fa.`);
  }
  return xifra(T('Temperatura a la part alta'), `${coma(a.error)}\u00a0°C`, T('és el que s’equivoca, de mitjana'), notes.join(' '));
}

// La pluja, amb el que va passar de veritat: de les hores en què deia que
// plouria (50 % o més), en quantes va ploure; i de les que deia que no (menys
// del 20 %), en quantes no va ploure.
function xifraPluja(p, plourà, minim) {
  const [encerts, de] = (plourà ? p.plou : p.sec) || [0, 0];
  const titol = plourà ? T('Quan diu que plourà') : T('Quan diu que no plourà');
  if (!de) return xifra(titol, '—', T('Encara no ho ha dit cap hora.'));
  const peu = plourà ? T('de les vegades, plou') : T('de les vegades, no plou');
  const nota = plourà ? T`${encerts} de ${de} hores (quan dona un 50\u00a0% o més).`
    : T`${encerts} de ${de} hores (quan dona menys d’un 20\u00a0%).`;
  const poques = de < minim ? ` ${T('Encara són poques.')}` : '';
  return xifra(titol, `${Math.round((encerts / de) * 100)}\u00a0%`, peu, nota + poques);
}

// Contra una oficial: quants graus menys o més s'equivoca la web, a les mateixes hores.
function xifraOficial(nom, o) {
  const t = o && o.temperatura;
  if (!t || !t.hores) return xifra(T`Contra ${nom}`, '—', T`Encara no hi ha hores per comparar amb ${nom}.`);
  const d = t.oficial - t.web;
  if (Math.abs(d) < 0.05) {
    return xifra(T`Contra ${nom}`, T('Igual'), T`en la temperatura, la web i ${nom} s’equivoquen igual`,
      T`${t.hores} hores comparades.`);
  }
  const peu = d > 0 ? T`menys d’error que ${nom} en la temperatura` : T`més d’error que ${nom} en la temperatura`;
  return xifra(T`Contra ${nom}`, `${coma(Math.abs(d))}\u00a0°C`, peu,
    T`${t.hores} hores comparades: ${textSegur(t.seguretat)}.`);
}

function xifraMillora(m) {
  if (!m || m.setmanes < m.cal || !m.temperatura) {
    const n = m ? m.setmanes : 0;
    return xifra(T('Amb el temps'), '—', T`Es podrà saber si millora quan hi hagi ${m ? m.cal : 8} setmanes de dades; ara n’hi ha ${n}.`);
  }
  const t = m.temperatura;
  const s = t.seguretat;
  const valor = s != null && s >= SEGURETAT ? T('Millora') : s != null && s <= 1 - SEGURETAT ? T('Empitjora') : T('Igual');
  return xifra(T('Amb el temps'), valor, T`En la temperatura, s’equivocava ${coma(t.abans)}\u00a0°C i ara ${coma(t.ara)}\u00a0°C (les 4 darreres setmanes contra les 4 anteriors).`,
    textSegur(s));
}

function pintaXifres(e) {
  const m = INDEX.minims || {};
  const p = e.darrers.pluja;
  $('xifres').replaceChildren(xifraTemperatura(e.darrers.temperatura, m.temperatura_hores || 48),
    xifraAlta(e.darrers.temperatura_alta, m.temperatura_hores || 48),
    xifraPluja(p, true, m.pluja_casos || 20), xifraPluja(p, false, m.pluja_casos || 20),
    xifraOficial('Meteocat', e.oficial && e.oficial.meteocat), xifraOficial('AEMET', e.oficial && e.oficial.aemet),
    xifraMillora(e.millora));
  $('resum-periode').textContent = textPeriode(INDEX.periode);
}

// --- Les gràfiques: línies, una escala, la més baixa és la millor ---

function escalaMax(v) {
  const pas = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5].find((p) => v / p <= 4) || 10;
  return Math.max(pas, Math.ceil((v * 1.05) / pas) * pas);
}

// cont: on va; etiquetes: les de l'eix x; series: [{clau, valors}]; marca: l'índex a destacar.
function graficaLinies(cont, { etiquetes, series, unitat, decimals, marca, descripcio }) {
  const amb = series.filter((s) => s.valors.some((v) => v != null));
  const vals = amb.flatMap((s) => s.valors).filter((v) => v != null);
  if (!vals.length) {
    cont.replaceChildren(element('p', 'nota', T('Encara no hi ha dades per dibuixar-ho.')));
    return;
  }
  const W = Math.max(280, (cont.clientWidth || 600) - 6);
  const H = W < 480 ? 180 : 220;
  const m = { e: 40, d: 14, a: 10, b: 26 };
  const max = escalaMax(Math.max(...vals));
  const n = etiquetes.length;
  const x = (i) => (n === 1 ? (m.e + W - m.d) / 2 : m.e + (i * (W - m.e - m.d)) / (n - 1));
  const y = (v) => H - m.b - (v / max) * (H - m.a - m.b);
  const arrel = svg('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img', 'aria-label': descripcio });
  const fmt = (v) => `${coma(v, decimals)}${unitat}`;
  for (const v of [0, max / 2, max]) {
    arrel.append(svg('line', { class: 'fb-reixa', x1: m.e, x2: W - m.d, y1: y(v), y2: y(v) }));
    arrel.append(svg('text', { class: 'fb-eix', x: m.e - 6, y: y(v) + 4, 'text-anchor': 'end' }, coma(v, decimals)));
  }
  const cada = Math.max(1, Math.ceil(n / (W < 480 ? 5 : 9)));
  etiquetes.forEach((t, i) => {
    // Una de cada «cada» i l'última, sense la que quedaria enganxada a l'última.
    if (i !== n - 1 && (i % cada || n - 1 - i < cada)) return;
    // La primera i l'última, cap endins, perquè no es tallin.
    const ancora = n > 1 && i === 0 ? 'start' : n > 1 && i === n - 1 ? 'end' : 'middle';
    arrel.append(svg('text', { class: 'fb-eix', x: x(i), y: H - 8, 'text-anchor': ancora }, t));
  });
  if (marca != null && marca >= 0 && marca < n) {
    arrel.append(svg('line', { class: 'fb-marca', x1: x(marca), x2: x(marca), y1: m.a, y2: H - m.b }));
  }
  for (const s of amb) {
    let d = '';
    s.valors.forEach((v, i) => {
      if (v == null) return;
      d += `${d && s.valors[i - 1] != null ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    });
    arrel.append(svg('path', { class: `fb-linia fb-${s.clau}`, d }));
    s.valors.forEach((v, i) => {
      if (v != null && (n <= 12 || s.valors[i - 1] == null || s.valors[i + 1] == null)) {
        arrel.append(svg('circle', { class: `fb-punt fb-${s.clau}`, cx: x(i), cy: y(v), r: 4 }));
      }
    });
  }
  // El rètol en passar el dit o el ratolí: el valor de cada sèrie en aquell punt.
  const guia = svg('line', { class: 'fb-guia', y1: m.a, y2: H - m.b, visibility: 'hidden' });
  arrel.append(guia);
  const retol = element('div', 'fb-retol');
  retol.hidden = true;
  const caixa = element('div', 'fb-grafica');
  const mou = (ev) => {
    const r = arrel.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(n - 1, Math.round(n === 1 ? 0 : ((px - m.e) / (W - m.e - m.d)) * (n - 1))));
    guia.setAttribute('x1', x(i));
    guia.setAttribute('x2', x(i));
    guia.setAttribute('visibility', 'visible');
    retol.replaceChildren(element('strong', null, etiquetes[i]));
    for (const s of amb) {
      const f = element('span', 'fb-retol-fila');
      f.append(element('span', `fb-clau fb-${s.clau}`), `${SERIES()[s.clau]}: ${s.valors[i] == null ? '—' : fmt(s.valors[i])}`);
      retol.append(f);
    }
    retol.hidden = false;
    const esquerra = (x(i) / W) * caixa.clientWidth;
    retol.style.left = `${Math.min(Math.max(0, esquerra - 70), Math.max(0, caixa.clientWidth - 150))}px`;
  };
  arrel.addEventListener('pointermove', mou);
  arrel.addEventListener('pointerdown', mou);
  arrel.addEventListener('pointerleave', () => { retol.hidden = true; guia.setAttribute('visibility', 'hidden'); });
  const llegenda = element('p', 'fb-llegenda');
  for (const s of amb) {
    const c = element('span', 'fb-llegenda-clau');
    c.append(element('span', `fb-clau fb-${s.clau}`), SERIES()[s.clau]);
    llegenda.append(c);
  }
  caixa.append(arrel, retol);
  cont.replaceChildren(caixa, llegenda);
}

// Cada gràfica, dues vegades: la temperatura (°C) i la pluja (error de Brier).
const TIPUS = [['temperatura', '\u00a0°C', 1], ['pluja', '', 2]];

function valorWeb(enc, tipus) {
  if (!enc) return null;
  return tipus === 'pluja' ? (enc.pluja && enc.pluja.brier) : enc.darrers.temperatura.error;
}

// La pluja de Meteocat i AEMET, només quan ha plogut en alguna de les hores
// comparades: sense pluja, el seu error només compta les falses alarmes i
// semblava que encertaven sempre (Juanjo, 23-10-2026: «aemet acierta siempre
// con la lluvia?»).
function valorOficial(o, tipus) {
  const v = o && o[tipus];
  if (!v || !v.hores || (tipus === 'pluja' && !v.plogudes)) return null;
  return v.oficial;
}

// La web, on hi ha alguna oficial, a les mateixes hores que l'AEMET (la que
// en té més; si no, les de Meteocat): la línia de tots els dies des del 4
// d'octubre, amb pluja, es comparava amb les oficials de dies secs.
function valorWebComparat(general, oficial, tipus) {
  const o = oficial || {};
  const font = valorOficial(o.aemet, tipus) != null ? o.aemet : valorOficial(o.meteocat, tipus) != null ? o.meteocat : null;
  return font ? font[tipus].web : general;
}

// Si hi ha oficials però encara no ha plogut a les seves hores, es diu.
function notaPlujaOficials(cont, oficials) {
  const sense = oficials.some((o) => o && ['meteocat', 'aemet'].some((f) => o[f] && o[f].pluja && o[f].pluja.hores && !o[f].pluja.plogudes));
  const amb = oficials.some((o) => o && ['meteocat', 'aemet'].some((f) => valorOficial(o[f], 'pluja') != null));
  if (sense && !amb) cont.append(element('p', 'nota', T('Meteocat i AEMET hi sortiran quan hagi plogut en alguna de les hores comparades; de moment no hi ha plogut.')));
}

function pintaAntelacions() {
  const ns = Array.from({ length: ANTELACIO_MAX }, (_, i) => i + 1);
  const enc = ns.map((n) => INDEX.encert[String(n)]);
  for (const [tipus, unitat, decimals] of TIPUS) {
    graficaLinies($(`grafica-antelacio-${tipus}`), {
      etiquetes: ns.map((n) => `${n}\u00a0h`),
      series: [{ clau: 'web', valors: enc.map((e) => valorWebComparat(valorWeb(e, tipus), e && e.oficial, tipus)) },
        { clau: 'meteocat', valors: enc.map((e) => valorOficial(e && e.oficial && e.oficial.meteocat, tipus)) },
        { clau: 'aemet', valors: enc.map((e) => valorOficial(e && e.oficial && e.oficial.aemet, tipus)) }],
      unitat, decimals, marca: estat.antelacio - 1,
      descripcio: tipus === 'pluja' ? T('L’error de la pluja segons l’antelació, de la web, Meteocat i AEMET.')
        : T('L’error de la temperatura segons l’antelació, de la web, Meteocat i AEMET.'),
    });
    if (tipus === 'pluja') notaPlujaOficials($(`grafica-antelacio-${tipus}`), enc.map((e) => e && e.oficial));
  }
}

function pintaSetmanes(e) {
  const setmanes = (e.setmanes || []).filter((s) => s.temperatura.hores || (s.pluja && s.pluja.hores));
  for (const [tipus, unitat, decimals] of TIPUS) {
    graficaLinies($(`grafica-setmanes-${tipus}`), {
      etiquetes: setmanes.map((s) => dataCurta(s.des_de) + (s.en_curs ? '*' : '')),
      series: [{ clau: 'web', valors: setmanes.map((s) => valorWebComparat(tipus === 'pluja' ? s.pluja.brier : s.temperatura.error, s.oficial, tipus)) },
        { clau: 'meteocat', valors: setmanes.map((s) => valorOficial(s.oficial && s.oficial.meteocat, tipus)) },
        { clau: 'aemet', valors: setmanes.map((s) => valorOficial(s.oficial && s.oficial.aemet, tipus)) }],
      unitat, decimals,
      descripcio: tipus === 'pluja' ? T('L’error de la pluja setmana a setmana, de la web, Meteocat i AEMET.')
        : T('L’error de la temperatura setmana a setmana, de la web, Meteocat i AEMET.'),
    });
    if (tipus === 'pluja') notaPlujaOficials($(`grafica-setmanes-${tipus}`), setmanes.map((s) => s.oficial));
  }
  // Sense «Cada setmana comença en dilluns», que és una obvietat (Juanjo, 20-10-2026).
  // Que es vegi què és cada punt (Juanjo, 20-10-2026: «donde pone que es una semana?»).
  $('setmanes-nota').textContent = (setmanes.some((s) => s.en_curs)
    ? T('Cada punt és una setmana, amb el dia que comença; * la setmana en curs.') : T('Cada punt és una setmana, amb el dia que comença.'))
    + (setmanes.some((s) => s.oficial && (s.oficial.aemet || s.oficial.meteocat))
      ? ' ' + T('Les setmanes amb Meteocat i AEMET, la web a les mateixes hores que l’AEMET.') : '');
}

// --- Com aprèn ---

function barra(fet, cal) {
  const b = element('span', 'fb-barra');
  const dins = element('span', 'fb-barra-fet');
  dins.style.width = `${Math.min(100, Math.round((fet / cal) * 100))}%`;
  b.append(dins);
  b.setAttribute('aria-hidden', 'true');
  return b;
}

function fitxaAprenentatge(titol, ara, progres, text, dades = null) {
  const f = element('div', 'fb-apren');
  f.append(element('h3', null, titol), element('p', 'fb-apren-ara', ara));
  if (progres) {
    const p = element('p', 'fb-apren-progres');
    p.append(barra(progres.fet, progres.cal), element('span', null, progres.text));
    f.append(p);
  }
  if (dades) f.append(dades);
  if (text) f.append(element('p', null, text));
  return f;
}

// Qui s'equivoca més i qui menys, en barres (Juanjo, 20-10-2026: «esto es solo
// información estática, por qué no pones los datos de quien acierta y se
// equivoca más? un diagrama de barras»): una fila per opció, la barra
// proporcional a l'error, i la que fa servir la web, en color i rotulada.
function barresError(titol, files, decimals, marca = T(' (la que fa servir)')) {
  const max = Math.max(...files.map((f) => f.valor), 1e-9);
  const taula = element('div', 'fb-comp');
  const cap = element('p', 'fb-comp-titol', titol);
  const llista = element('ul', 'fb-comp-files');
  for (const f of files) {
    const li = element('li', f.enUs ? 'en-us' : null);
    const nom = element('span', 'fb-comp-nom', f.nom);
    if (f.enUs) nom.append(element('span', 'fb-comp-marca', marca));
    const b = element('span', 'fb-comp-barra');
    const dins = element('span', 'fb-comp-fet');
    dins.style.width = `${Math.max(2, Math.round((f.valor / max) * 100))}%`;
    b.append(dins);
    b.setAttribute('aria-hidden', 'true');
    li.append(nom, b, element('span', 'fb-comp-xifra', coma(f.valor, decimals)));
    llista.append(li);
  }
  taula.append(cap, llista);
  return taula;
}

// Quant s'equivoca menys la millor que la segona, en paraules.
function percentMenys(millor, altra) {
  return Math.round((1 - millor / altra) * 100);
}

// La nova, en entrenament, contra l'actual: sense xifres soltes, que són a la taula.
function fraseNova(err, vigent) {
  if (err == null || vigent == null) return null;
  if (err < vigent) return T('La nova ja s’equivoca menys: la farà servir quan es vegi que no és casualitat.');
  return T('De moment, la nova s’equivoca més que l’actual.');
}

function pintaAprenentatge() {
  const a = INDEX.aprenentatge;
  if (!a) {
    $('apren-cos').replaceChildren(element('p', 'nota', T('Encara no hi ha dades de l’aprenentatge.')));
    return;
  }
  const dies = a.dies || [];
  const darrer = dies[dies.length - 1] || {};
  const mn = a.minims || {};
  const fitxes = [];
  const hp = darrer.hores_pluja || 0;
  const calP = mn.hores_pluja || 30;
  fitxes.push(fitxaAprenentatge(T('Probabilitat de pluja'),
    darrer.pluja === 'local' ? T('Ara fa servir la seva, apresa amb la pluja del barri.')
      : T('Ara fa servir la que va aprendre amb la pluja de Sabadell i Sant Cugat del 2024 al 2026.'),
    darrer.pluja === 'local' ? null : { fet: hp, cal: calP, text: T`Per provar-ne una de nova apresa al barri, calen ${calP} hores de pluja; en porta ${hp}.` },
    fraseNova(darrer.error_pluja, darrer.error_pluja_vigent)));
  const dt = darrer.dies_temperatura || 0;
  const calT = mn.dies_temperatura || 14;
  fitxes.push(fitxaAprenentatge(T('Temperatura'),
    darrer.temperatura === 'casa' ? T('Ara corregeix els models amb el que ha après de l’estació del barri aquests dies.')
      : T('Ara corregeix el que diuen els models amb un any de mesures de l’estació del barri.'),
    darrer.temperatura === 'casa' ? null : { fet: Math.min(dt, calT), cal: calT, text: T`Per provar una correcció nova, calen ${calT} dies; en porta ${dt}.` },
    fraseNova(darrer.error_temp, darrer.error_temp_vigent)));
  if (a.humitat) fitxes.push(fitxaHumitat(a.humitat, mn.dies_humitat || 14));
  if (a.radar) {
    const NOMS_RADAR = { meteocat: 'Meteocat', rainviewer: 'RainViewer' };
    const nom = NOMS_RADAR[a.radar.preferida] || a.radar.preferida;
    const ara = a.radar.des_de ? T`Ara fa servir el radar de ${nom}, des del ${nomData(a.radar.des_de)}.` : T`Ara fa servir el radar de ${nom}.`;
    const err = a.radar.error || {};
    const radars = Object.keys(NOMS_RADAR).filter((r) => err[r] != null);
    let dades = null;
    let text = T`Hi ha dos radars, el de Meteocat i el de RainViewer. Cada dia mira quin ha encertat més la pluja al barri l’últim mes: ara és el de ${nom}, i ${textSegur(a.radar.seguretat)}.`;
    if (radars.length === 2) {
      dades = barresError(T('Error de cada radar l’últim mes (0 vol dir que encerta sempre)'),
        radars.map((r) => ({ nom: NOMS_RADAR[r], valor: err[r], enUs: r === a.radar.preferida })), 3, T(' (el que fa servir)'));
      const [millor, altra] = [...radars].sort((x, y) => err[x] - err[y]);
      const menys = percentMenys(err[millor], err[altra]);
      text = (menys > 0 ? T`${NOMS_RADAR[millor]} s’equivoca un ${menys}\u00a0% menys que ${NOMS_RADAR[altra]}`
        : T('Els dos s’equivoquen igual'))
        + (a.radar.casos ? T`, en ${a.radar.casos.toLocaleString('ca')} previsions de les dues hores següents, ${a.radar.amb_pluja || 0} amb pluja al barri, de ${a.radar.dies_pluja || 0} dies diferents.` : '.');
      // La que fa servir canvia només si l'altra guanya i no és casualitat.
      if (millor !== a.radar.preferida) text += T(' Encara no canvia: pot ser casualitat.');
    }
    fitxes.push(fitxaAprenentatge(T('Radar (les dues primeres hores)'), ara, null, text, dades));
  }
  if (a.cel) {
    const pesos = Object.values(a.cel.pesos);
    const iguals = pesos.every((p) => Math.abs(p - pesos[0]) < 0.01);
    const NOMS_MODEL = { arome: 'AROME', icon_eu: 'ICON-EU', ecmwf: 'ECMWF', gfs: 'GFS' };
    const err = a.cel.error || {};
    const models = Object.keys(a.cel.pesos).filter((m) => err[m] != null);
    let dades = null;
    let text = T('Cada dia ho compara amb els núvols que es veuen a l’aeroport de Sabadell; només canvia els pesos si uns altres encerten més i no és casualitat.');
    if (models.length && a.cel.error_actual != null) {
      const files = [{ nom: T('La mitjana'), valor: a.cel.error_actual, enUs: true },
        ...models.map((m) => ({ nom: NOMS_MODEL[m] || m, valor: err[m] }))];
      dades = barresError(T('Error mitjà de cada un, en punts de cel tapat (de 0 a 100)'), files, 1);
      const millor = files.reduce((x, y) => (y.valor < x.valor ? y : x));
      text = (millor.enUs ? T('La mitjana s’equivoca menys que cada model per separat.')
        : T`${millor.nom} sol s’equivoca una mica menys, però els pesos només canvien si la millora no és casualitat.`)
        + ' ' + (a.cel.dies ? T`Comparat amb els núvols de l’aeroport de Sabadell, els darrers ${a.cel.dies} dies.`
          : T('Comparat amb els núvols de l’aeroport de Sabadell.'));
    }
    fitxes.push(fitxaAprenentatge(T('Núvols'), iguals ? T('Ara fa la mitjana de quatre models del temps, tots amb el mateix pes.')
      : T('Ara fa la mitjana de quatre models del temps, amb més pes per als que més encerten.'), null, text, dades));
  }
  $('apren-cos').replaceChildren(...fitxes);
  pintaCanvis(a.canvis || []);
  pintaDiesAprenentatge(dies);
  // La que prova contra la que fa servir, dia a dia.
  for (const [tipus, unitat] of TIPUS) {
    const pluja = tipus === 'pluja';
    const amb = dies.filter((d) => (pluja ? d.error_pluja != null : d.error_temp != null));
    graficaLinies($(`grafica-apren-${tipus}`), {
      etiquetes: amb.map((d) => dataCurta(d.dia)),
      series: [{ clau: 'vigent', valors: amb.map((d) => (pluja ? d.error_pluja_vigent : d.error_temp_vigent)) },
        { clau: 'candidata', valors: amb.map((d) => (pluja ? d.error_pluja : d.error_temp)) }],
      unitat, decimals: pluja ? 3 : 2,
      descripcio: pluja ? T('L’error de la pluja de la previsió actual i de la nova, dia a dia.')
        : T('L’error de la temperatura de la previsió actual i de la nova, dia a dia.'),
    });
  }
  const hum = ((a.humitat || {}).dies || []).filter((d) => d.error != null);
  graficaLinies($('grafica-apren-humitat'), {
    etiquetes: hum.map((d) => dataCurta(d.dia)),
    series: [{ clau: 'vigent', valors: hum.map((d) => d.error_vigent) }, { clau: 'candidata', valors: hum.map((d) => d.error) }],
    unitat: '', decimals: 1,
    descripcio: T('L’error de la humitat de la previsió actual i de la nova, dia a dia.'),
  });
}

// La humitat de la gràfica (ADR 0114): el punt de rosada dels models, corregit
// amb el que s'ha après, i la temperatura de la web. El que va sortir amb un
// any de l'estació del barri i, dia a dia, el que aprèn amb totes les del
// barri, en punts d'humitat (Juanjo, 21-10-2026: «añade estos datos a la
// pagina de fiabilitat»).
const ANY = { day: 'numeric', month: 'long', year: 'numeric' };
function fitxaHumitat(h, calH) {
  const dies = h.dies || [];
  const darrer = dies[dies.length - 1] || {};
  const barri = darrer.humitat === 'barri';
  const arxiu = h.arxiu || {};
  const ara = barri ? T('Ara corregeix la humitat dels models amb el que ha après aquests dies de les estacions del barri.')
    : arxiu.adoptat ? T('Ara corregeix la humitat dels models amb un any de mesures de l’estació del barri.')
      : T('Ara fa servir la humitat dels models sense corregir.');
  const dh = darrer.dies || 0;
  const progres = barri ? null : { fet: Math.min(dh, calH), cal: calH, text: T`Per provar una correcció apresa amb totes les estacions del barri, calen ${calH} dies; en porta ${dh}.` };
  let dades = null;
  let text = fraseNova(darrer.error, darrer.error_vigent);
  if (arxiu.error != null && arxiu.error_model != null) {
    dades = barresError(T('Error mitjà de la humitat, en punts de % (0 vol dir que encerta sempre)'), [
      { nom: T('Corregida'), valor: arxiu.error, enUs: Boolean(arxiu.adoptat) && !barri },
      { nom: T('Models sense corregir'), valor: arxiu.error_model }], 1);
    const linia = T`Els models veuen l’aire més sec del que és. Corregida, la humitat s’equivoca ${coma(arxiu.error, 1)} punts de mitjana, en lloc de ${coma(arxiu.error_model, 1)}: un ${percentMenys(arxiu.error, arxiu.error_model)} % menys, en ${arxiu.dies} dies que no havia vist (del ${nomData(arxiu.des_de, ANY)} al ${nomData(arxiu.fins, ANY)}), i ${textSegur(arxiu.seguretat)}.`;
    text = text ? `${linia} ${text}` : linia;
  }
  return fitxaAprenentatge(T('Humitat'), ara, progres, text, dades);
}

// Els canvis que la web ha fet sola, amb la data (Juanjo, 20-10-2026: «en como
// aprende quiero q aparezcan las mejoras que hay dia a dia»).
function textCanvi(c) {
  if (c.que === 'radar') {
    return T`Fa servir el radar de ${c.a === 'meteocat' ? 'Meteocat' : 'RainViewer'}, que encertava més la pluja al barri.`;
  }
  if (c.que === 'fi_pluja') return T('Regla nova per dir quan s’acaba la pluja, que encertava més els episodis registrats.');
  if (c.que === 'pluja') {
    return c.a === 'local' ? T('La probabilitat de pluja passa a ser la pròpia, apresa al barri, que encertava més.')
      : T('La probabilitat de pluja torna a la de l’arxiu: la pròpia havia deixat d’encertar més.');
  }
  if (c.que === 'humitat') {
    return c.a === 'barri' ? T('La correcció de la humitat passa a ser l’apresa amb les estacions del barri, que encertava més.')
      : T('La correcció de la humitat torna a la de l’arxiu: la del barri havia deixat d’encertar més.');
  }
  if (c.que === 'temperatura') {
    return c.a === 'casa' ? T('La correcció de la temperatura passa a ser la pròpia, que encertava més.')
      : T('La correcció de la temperatura torna a la de l’arxiu: la pròpia havia deixat d’encertar més.');
  }
  return null;
}

function pintaCanvis(canvis) {
  const llista = element('ul', 'fb-canvis');
  for (const c of canvis) {
    const text = textCanvi(c);
    if (!text) continue;
    const li = element('li');
    li.append(element('span', 'fb-canvi-dia', dataCurta(c.dia)), element('span', null, text));
    llista.append(li);
  }
  $('apren-canvis').replaceChildren(...(llista.children.length ? [llista]
    : [element('p', 'nota', T('Encara no ha canviat res: cap prova ha encertat prou més.'))]));
}

// Dia a dia, el que porta cada aprenentatge: les hores de pluja que ja té, i
// l'error de la que prova i de la que fa servir.
function pintaDiesAprenentatge(dies) {
  const darrers = dies.filter((d) => d.hores_pluja != null || d.error_temp != null).slice(-10).reverse();
  if (!darrers.length) {
    $('apren-dies').replaceChildren();
    return;
  }
  const parella = (prova, vigent, dec, u) => (prova == null || vigent == null ? '—'
    : `${coma(prova, dec)}${u} / ${coma(vigent, dec)}${u}`);
  $('apren-dies').replaceChildren(taula([T('Dia'), T('Hores de pluja'), T('Pluja: nova / actual'), T('Temperatura (°C): nova / actual')],
    darrers.map((d) => [dataCurta(d.dia), d.hores_pluja == null ? '—' : String(d.hores_pluja),
      parella(d.error_pluja, d.error_pluja_vigent, 3, ''), parella(d.error_temp, d.error_temp_vigent, 2, '')])),
  element('p', 'nota', T('L’error de la nova i el de l’actual, cada dia, a les mateixes hores (com més baix, millor). Quan la nova s’equivoca menys i no és casualitat, la web passa a fer-la servir.')));
}

// --- Dia a dia ---

const FIGURA = figuraGrafica([], T('Gràfica d’un dia: la temperatura i la pluja mesurades, i el que deia la previsió.'));
FIGURA.classList.add('gran');

function ambAntelacio(files, a) {
  return files.map((f) => {
    const v = f.prev && f.prev[String(a)];
    const { prev, ...resta } = f;
    return v ? { ...resta, prev: { temperatura: v[0], probabilitat: v[1], mm: v[2] ?? null } } : resta;
  });
}

function textDia(dades, a) {
  if (!dades) return T('Aquest dia no es pot llegir.');
  const e = dades.encert && dades.encert[String(a)];
  if (!e || (!e.temperatura.hores && !(e.pluja.brier || [0])[0])) return T('D’aquest dia no hi ha previsions per comparar.');
  const parts = [];
  if (e.temperatura.error != null) parts.push(T`la temperatura es va equivocar ${coma(e.temperatura.error)}\u00a0°C de mitjana`);
  const b = e.pluja.brier;
  if (b && b[0]) parts.push(b[1] ? T`va ploure ${b[1]} de ${b[0]} hores` : T`no va ploure`);
  return T`Aquest dia, ${parts.join('; ')}.`;
}

async function pintaDia() {
  const dies = (INDEX && INDEX.dies) || [];
  if (!dies.length) return;
  if (!estat.dia || !dies.includes(estat.dia)) estat.dia = dies[dies.length - 1];
  const pos = dies.indexOf(estat.dia);
  $('dia-enrere').disabled = pos <= 0;
  $('dia-endavant').disabled = pos >= dies.length - 1;
  $('dia-avui').hidden = estat.dia === avuiIso();
  $('dia-nom').textContent = estat.dia === avuiIso() ? T('Avui')
    : nomData(estat.dia, { weekday: 'long', day: 'numeric', month: 'long' });
  const dia = estat.dia;
  const dades = await llegeixDiaHistorial(dia);
  if (dia !== estat.dia) return;
  const a = estat.antelacio;
  // Avui, només les hores que ja han acabat: la resta encara no té mesura.
  const ara = new Date();
  FIGURA._files = dades ? ambAntelacio(dades.hores, a).filter((f) => new Date(f.fins) <= ara) : [];
  FIGURA._opcions = { gran: true, antelacio: a, escala: true };
  FIGURA._amaga?.();
  dibuixaGrafica(FIGURA);
  $('dia-text').textContent = textDia(dades, a);
}

// --- Les xifres, en taules, i el detall ---

const FRANGES_PLUJA = [0, 20, 50, 70];
function nomFranja(de, a) {
  if (de === 0) return T`menys del ${a}\u00a0%`;
  if (a == null) return T`${de}\u00a0% o més`;
  return T`del ${de} al ${a}\u00a0%`;
}

function taula(columnes, files) {
  const t = element('table', 'vg-encert-taula');
  const cap = element('tr');
  columnes.forEach((c, i) => {
    const th = element('th', i ? 'num' : null, c);
    th.scope = 'col';
    cap.append(th);
  });
  t.append(element('thead'), element('tbody'));
  t.firstChild.append(cap);
  for (const [nom, ...cel] of files) {
    const tr = element('tr');
    const th = element('th', null, nom);
    th.scope = 'row';
    tr.append(th, ...cel.map((c) => element('td', 'num', c)));
    t.lastChild.append(tr);
  }
  const caixa = element('div', 'taula-desplaca');
  caixa.append(t);
  return caixa;
}

const graus = (v) => (v == null ? '—' : `${coma(v)}\u00a0°C`);
const brier = (v) => (v == null ? '—' : coma(v, 3));

function pintaDetall(e) {
  const res = [];
  // Contra les oficials, a les mateixes hores.
  const files = [];
  for (const [clau, nom] of [['meteocat', 'Meteocat'], ['aemet', 'AEMET']]) {
    const o = e.oficial && e.oficial[clau];
    if (!o) continue;
    files.push([T`Aquesta web (hores de ${nom})`, graus(o.temperatura.web), brier(o.pluja.web), String(o.temperatura.hores)]);
    files.push([nom, graus(o.temperatura.oficial), brier(o.pluja.oficial), String(o.temperatura.hores)]);
  }
  if (files.length) {
    res.push(element('h3', null, T('Contra Meteocat i AEMET')),
      taula([T('Previsió'), T('Error de temperatura'), T('Error de pluja'), T('Hores')], files));
  }
  // Setmana a setmana.
  const setmanes = [...(e.setmanes || [])].reverse();
  if (setmanes.length) {
    res.push(element('h3', null, T('Setmana a setmana')), taula([T('Setmana'), T('Error de temperatura'), T('Error de pluja'), T('Millora')],
      setmanes.map((s) => [dataCurta(s.des_de) + (s.en_curs ? ` (${T('en curs')})` : ''), graus(s.temperatura.error), brier(s.pluja.brier),
        s.pluja.millora_clima == null ? '—' : `${s.pluja.millora_clima >= 0 ? '+' : '−'}${Math.round(Math.abs(s.pluja.millora_clima) * 100)}\u00a0%`])));
  }
  // La probabilitat de pluja, per franges.
  const d = e.darrers;
  const fr = d && d.pluja.franges;
  if (fr) {
    const fl = (INDEX.franges || FRANGES_PLUJA).map((de, i, l) => [de, l[i + 1], fr[String(de)] || [0, 0, 0]])
      .filter(([, , [h]]) => h > 0)
      .map(([de, a, [h, pl, s]]) => [nomFranja(de, a), `${Math.round((s / h) * 100)}\u00a0%`, String(h), `${pl} (${Math.round((pl / h) * 100)}\u00a0%)`]);
    if (fl.length) {
      res.push(element('h3', null, T('La probabilitat de pluja, per franges')),
        element('p', null, T('Quan deia cada probabilitat, en quantes hores va ploure. Si la probabilitat és bona, el «va ploure» s’acosta al que deia.')),
        taula([T('Quan deia'), T('De mitjana'), T('Hores'), T('Va ploure')], fl));
    }
  }
  if (d && d.mm && d.mm.hores) {
    res.push(element('p', null, T`Pluja esperada (probabilitat per quantitat de cada hora): en preveia ${coma(d.mm.previst)}\u00a0mm i en van caure ${coma(d.mm.mesurat)}.`));
  }
  $('detall-cos').replaceChildren(...res);
}

// --- Tot plegat ---

function pintaGrafiques(e) {
  pintaAntelacions();
  pintaSetmanes(e);
  pintaAprenentatge();
}

function pinta() {
  if (!INDEX) return;
  const a = estat.antelacio;
  pintaLliscador();
  // El que depèn de l'antelació ho diu (Juanjo, 20-10-2026: «el usuario debe saber lo que está viendo en cada momento»).
  // Amb un enllaç al lliscador de dalt, que és on es canvia (Juanjo,
  // 23-10-2026: «no entiendo lo de resum»).
  for (const p of document.querySelectorAll('.fb-amb-antelacio')) {
    const enllac = element('a', null, T('puja al selector de dalt'));
    enllac.href = '#antelacio';
    enllac.addEventListener('click', (ev) => {
      ev.preventDefault();
      $('antelacio').scrollIntoView({ behavior: 'smooth', block: 'center' });
      $('antelacio').focus({ preventScroll: true });
    });
    p.replaceChildren(T`Amb la previsió feta ${a}\u00a0h abans. Per triar-ne una altra, `, enllac, '.');
  }
  const e = INDEX.encert && INDEX.encert[String(a)];
  if (!e) return;
  pintaXifres(e);
  pintaGrafiques(e);
  pintaDetall(e);
  pintaDia();
  desaAdreca();
}

// L'antelació, amb un lliscador d'1 a 23 h (Juanjo, 20-10-2026: «el selector
// de horas no me gusta porque hay que pasar una a una. Haz algo util pero
// profesional y vistoso»). Només el lliscador: les barres de l'error per
// antelació que hi havia a sobre es van treure (Juanjo, 20-10-2026: «quita
// las columnas de aquí, deja solo el deslizador»).
function pintaLliscador() {
  const a = estat.antelacio;
  const r = $('antelacio');
  r.value = String(a);
  r.style.setProperty('--fet', `${((a - 1) / (ANTELACIO_MAX - 1)) * 100}%`);
  r.setAttribute('aria-valuetext', T`${a} hores abans`);
  const rotol = $('antelacio-rotol');
  rotol.replaceChildren(T('Previsió feta '), element('strong', null, `${a}\u00a0h`), T(' abans'));
}

let pendent = null;
function canviaAntelacio(valor) {
  const a = Math.min(ANTELACIO_MAX, Math.max(1, Math.round(Number(valor) || 1)));
  if (a === estat.antelacio) return;
  estat.antelacio = a;
  pintaLliscador();
  // Mentre s'arrossega, la resta es repinta un cop per fotograma.
  if (pendent) cancelAnimationFrame(pendent);
  pendent = requestAnimationFrame(() => { pendent = null; pinta(); });
}

function canviaDia(d) {
  const dies = (INDEX && INDEX.dies) || [];
  const nou = dies[dies.indexOf(estat.dia) + d];
  if (!nou) return;
  estat.dia = nou;
  pintaDia();
  desaAdreca();
}

llegeixAdreca();
// Els rètols que no són en un paràgraf, aquí, perquè es tradueixin (montflorit.py tradueix els blocs).
$('antelacio-eix').replaceChildren(...[1, 6, 12, 18, 23].map((h) => {
  const s = element('span', null, `${h}\u00a0h`);
  s.style.left = `calc(var(--polze) / 2 + (100% - var(--polze)) * ${(h - 1) / (ANTELACIO_MAX - 1)})`;
  return s;
}));
$('dia-nom').textContent = T('Avui');
$('dia-avui').textContent = T('Avui');
$('grafica-dia').append(FIGURA);
$('antelacio').addEventListener('input', (e) => canviaAntelacio(e.target.value));
$('dia-enrere').addEventListener('click', () => canviaDia(-1));
$('dia-endavant').addEventListener('click', () => canviaDia(1));
$('dia-avui').addEventListener('click', () => {
  estat.dia = avuiIso();
  pintaDia();
  desaAdreca();
});
let ampleAnterior = window.innerWidth;
addEventListener('resize', () => {
  if (!INDEX || Math.abs(window.innerWidth - ampleAnterior) < 20) return;
  ampleAnterior = window.innerWidth;
  pintaGrafiques(INDEX.encert[String(estat.antelacio)]);
});

llegeixHistorial('historial.json').then((d) => {
  INDEX = d;
  pinta();
}, () => {
  $('avis-dades').textContent = T('No s’han pogut carregar les dades. Torna-ho a provar d’aquí a una estona.');
  $('avis-dades').hidden = false;
});
llegeixDades(document.documentElement.dataset.dades || 'casa.json').then((d) => posaVersio(d.versio)).catch(() => {});
