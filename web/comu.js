// SPDX-License-Identifier: AGPL-3.0-or-later
// Peces comunes de les dues pàgines: utilitats, horari d'actualització,
// versió i commutador de tema.

// Marge abans de dir que una actualització prevista no s'ha fet.
const MARGE_RETARD_MIN = 20;

const $ = (id) => document.getElementById(id);

// Idioma. La pàgina és en català; la pública en castellà (ADR 0025) carrega
// abans es.js, que deixa a IDIOMA les traduccions. Cada text que es veu passa
// per T, i cada paraula que ve a les dades (nivells, tipus d'avís, rumbs),
// per TD. Sense traducció, surt el text tal com està escrit aquí.
var IDIOMA = IDIOMA || { codi: 'ca', textos: {}, dades: {} };

// T`Ara a ${lloc}` o T('No plou'): el text en l'idioma de la pàgina. La clau
// és el text català amb {0}, {1}… on van els valors; la traducció pot ser un
// text amb les mateixes marques o una funció que rep els valors.
function T(parts, ...valors) {
  const trossos = typeof parts === 'string' ? [parts] : parts;
  const clau = trossos.reduce((acc, tros, i) => `${acc}{${i - 1}}${tros}`);
  const traduccio = IDIOMA.textos[clau];
  if (typeof traduccio === 'function') return traduccio(...valors);
  return (traduccio === undefined ? clau : traduccio).replace(/\{(\d+)\}/g, (_, i) => valors[i]);
}

function TD(paraula) {
  return IDIOMA.dades[paraula] || paraula;
}

// On són els fitxers comuns: la pàgina en castellà és en una subcarpeta.
const ARREL = document.documentElement.dataset.arrel || '';

// --- La hora de Madrid (ADR 0128). Les dades porten cada hora en hora de
// Madrid amb el seu desfasament («2026-10-25T09:45+01:00»); les d'abans de la
// 3.201.0, sense («2026-10-25T09:45»), que també és hora de Madrid. La pàgina
// diu i compta sempre en hora de Madrid, sigui quina sigui la zona del
// dispositiu (Canàries, Portugal, qui viatja, Firefox amb «resistFingerprinting»,
// que va en UTC): res de getHours, getDate, toDateString ni toLocale* sense
// zona, que donen la del dispositiu. Tot passa per aquestes funcions.
const ZONA_HORA = 'Europe/Madrid';
const FORMAT_HORA = new Intl.DateTimeFormat('en-CA', { timeZone: ZONA_HORA, hourCycle: 'h23', year: 'numeric',
  month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', weekday: 'short' });
const SETMANA_HORA = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
// Un text ISO sense zona: el dia sol o el dia i l'hora.
const ISO_SENSE_ZONA = /^(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d)(?::(\d\d)(?:\.(\d{1,3})\d*)?)?)?$/;
const PARTS_HORA = new Map();

// El moment d'una data, d'un nombre o d'un text ISO. Un text sense zona és
// hora de Madrid: «new Date('2026-10-25T09:45')» la llegiria en la del
// dispositiu, i «new Date('2026-10-25')», en UTC.
function llegeixHora(x) {
  const m = typeof x === 'string' && ISO_SENSE_ZONA.exec(x);
  if (!m) return new Date(x);
  const t = deRellotge(+m[1], +m[2], +m[3], +(m[4] || 0), +(m[5] || 0)).getTime();
  return new Date(t + (+(m[6] || 0)) * 1000 + (+(m[7] || '0').padEnd(3, '0')));
}

// L'hora de Madrid d'un moment, per parts: { any, mes (1-12), dia, hora,
// minut, setmana (0, diumenge), data («AAAA-MM-DD»), desfas (minuts, 60 o
// 120) }. No s'ha de modificar: es reaprofita.
function partsHora(x) {
  const t = llegeixHora(x).getTime();
  let p = PARTS_HORA.get(t);
  if (p) return p;
  if (Number.isNaN(t)) return { any: NaN, mes: NaN, dia: NaN, hora: NaN, minut: NaN, setmana: NaN, data: '', desfas: NaN };
  const v = {};
  for (const { type, value } of FORMAT_HORA.formatToParts(t)) v[type] = value;
  const [any, mes, dia, hora, minut] = [+v.year, +v.month, +v.day, +v.hour % 24, +v.minute];
  p = { any, mes, dia, hora, minut, setmana: SETMANA_HORA[v.weekday], data: `${v.year}-${v.month}-${v.day}`,
    desfas: Math.round((Date.UTC(any, mes - 1, dia, hora, minut) - Math.floor(t / 60000) * 60000) / 60000) };
  if (PARTS_HORA.size > 5000) PARTS_HORA.clear();
  PARTS_HORA.set(t, p);
  return p;
}

// El dia de Madrid («AAAA-MM-DD») i l'hora de rellotge (0-23) d'un moment.
const diaLocal = (x) => partsHora(x).data;
const horaLocal = (x) => partsHora(x).hora;

// El desfasament de Madrid en un moment, en minuts (60 a l'hivern, 120 a
// l'estiu), i escrit com a les dades («+01:00»).
const desfasHora = (x) => partsHora(x).desfas;
// El que porta escrit una hora de les dades («…+01:00» → 60); sense, el de Madrid.
function desfasDe(iso) {
  const m = /([+-])(\d\d):(\d\d)$/.exec(typeof iso === 'string' ? iso : '');
  return m ? (m[1] === '-' ? -1 : 1) * (+m[2] * 60 + +m[3]) : desfasHora(iso);
}

function textDesfas(min) {
  const a = Math.abs(min);
  return `${min < 0 ? '-' : '+'}${String(Math.floor(a / 60)).padStart(2, '0')}:${String(a % 60).padStart(2, '0')}`;
}

// El moment d'una hora de rellotge de Madrid. L'hora que es repeteix a
// l'octubre és la primera (la d'estiu), i la que no existeix al març cau en
// la de després (de 2:30 a 3:30), com «hora.llegeix» de Python.
function deRellotge(any, mes, dia, hora = 0, minut = 0) {
  const w = Date.UTC(any, mes - 1, dia, hora, minut);
  const abans = partsHora(w - 864e5).desfas;
  const despres = partsHora(w + 864e5).desfas;
  for (const d of [Math.max(abans, despres), Math.min(abans, despres)]) {
    if (partsHora(w - d * 60000).desfas === d) return new Date(w - d * 60000);
  }
  return new Date(w - abans * 60000);
}

// La mitjanit (hora de Madrid) del dia d'un moment o d'un dia «AAAA-MM-DD».
function mitjanit(x) {
  const p = partsHora(x);
  return deRellotge(p.any, p.mes, p.dia);
}

// El dia de Madrid («AAAA-MM-DD») n dies després (o abans) del d'un moment.
function sumaDies(x, n) {
  const p = partsHora(x);
  return new Date(Date.UTC(p.any, p.mes - 1, p.dia + n)).toISOString().slice(0, 10);
}

// El moment de l'hora de rellotge «hora:minut» de Madrid del dia n dies
// després (o abans) del d'un moment o d'un dia «AAAA-MM-DD».
function horaDelDia(x, n = 0, hora = 0, minut = 0) {
  const [a, m, d] = sumaDies(x, n).split('-').map(Number);
  return deRellotge(a, m, d, hora, minut);
}

// Quants dies de calendari de Madrid hi ha del dia d'«a» al de «b».
function diesEntre(a, b) {
  const [pa, pb] = [partsHora(a), partsHora(b)];
  return Math.round((Date.UTC(pb.any, pb.mes - 1, pb.dia) - Date.UTC(pa.any, pa.mes - 1, pa.dia)) / 864e5);
}

const mateixDia = (a, b) => diaLocal(a) === diaLocal(b);

// Les dades, amb el desfasament a cada hora sense zona (valors i claus), com
// les que publica la 3.201.0: les d'abans (l'historial de la gràfica fins al
// 23-10-2026) es llegeixen igual que les noves, també tallant el text.
function ambDesfas(d) {
  if (typeof d === 'string') return d.length > 10 && ISO_SENSE_ZONA.test(d) ? d + textDesfas(desfasHora(d)) : d;
  if (Array.isArray(d)) return d.map(ambDesfas);
  if (d && typeof d === 'object') return Object.fromEntries(Object.entries(d).map(([k, v]) => [ambDesfas(k), ambDesfas(v)]));
  return d;
}

// La data d'un moment a Madrid, com la diu el navegador en l'idioma de la pàgina («25/10/2026»).
function textData(data) {
  return llegeixHora(data).toLocaleDateString(IDIOMA.codi, { timeZone: ZONA_HORA });
}

function horaCurta(data) {
  return llegeixHora(data).toLocaleTimeString(IDIOMA.codi, { hour: '2-digit', minute: '2-digit', timeZone: ZONA_HORA });
}

function element(etiqueta, classe, text) {
  const el = document.createElement(etiqueta);
  if (classe) el.className = classe;
  if (text) el.textContent = text;
  return el;
}

// Icona del full de símbols de la pàgina (Lucide).
function icona(id) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '#' + id);
  svg.append(use);
  return svg;
}

function coma(x, decimals = 1) {
  return Number(x).toFixed(decimals).replace('.', ',');
}

// Temperatura que es nota amb el vent (índex d'Environment Canada, el de la
// roba del trajecte i el de bot.es_nota): només amb 10 °C o menys i vent. A
// «Si surts», el vent és la velocitat del mitjà; a la portada, el previst.
function esNota(t, kmh) {
  if (t > 10 || kmh < 5) return t;
  const v = kmh ** 0.16;
  return 13.12 + 0.6215 * t - 11.37 * v + 0.3965 * t * v;
}

// Altura del sol (graus) a Cerdanyola en un moment donat, amb la fórmula
// aproximada de la NOAA: n'hi ha prou per saber si és de dia o de nit. I cap
// on és (azimut, en graus des del nord cap a l'est), per al recorregut del
// sol de «Consultes».
const CASA_COORD = [41.5, 2.1];
function posicioSol(data) {
  const rad = Math.PI / 180;
  const dies = data.getTime() / 864e5 + 2440587.5 - 2451545;
  const l = (280.46 + 0.9856474 * dies) % 360;
  const g = ((357.528 + 0.9856003 * dies) % 360) * rad;
  const lambda = (l + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * rad;
  const eps = (23.439 - 0.0000004 * dies) * rad;
  const dec = Math.asin(Math.sin(eps) * Math.sin(lambda));
  const ar = Math.atan2(Math.cos(eps) * Math.sin(lambda), Math.cos(lambda));
  const gmst = (18.697374558 + 24.06570982441908 * dies) % 24;
  const angle = (gmst * 15 + CASA_COORD[1]) * rad - ar;
  const lat = CASA_COORD[0] * rad;
  const altura = Math.asin(Math.sin(lat) * Math.sin(dec) + Math.cos(lat) * Math.cos(dec) * Math.cos(angle)) / rad;
  const azimut = (Math.atan2(Math.sin(angle), Math.cos(angle) * Math.sin(lat) - Math.tan(dec) * Math.cos(lat)) / rad + 540) % 360;
  return { altura, azimut };
}

function alturaSol(data) {
  return posicioSol(data).altura;
}

// --- La Lluna (lluna.py, ADR 0127): les fases, calculades al NAS amb
// Astronomy Engine. Una fase principal es diu fins a FASE_A_PROP_H hores abans
// i després, a «Ara» i a «Consultes» igual: les dues vesprades i nits que la
// Lluna es veu així, sigui l'hora de la fase quina sigui. Amb 12 hores, la de
// les 5:12 del matí desapareixia a les 17:12, abans que sortís la Lluna aquella
// nit, encara plena al 99 % (Juanjo, 25-10-2026: «sí, ponlo a 24 horas»).
const FASE_A_PROP_H = 24;
// Les dades de la Lluna de la pàgina, per a la gràfica (les posa qui les llegeix).
let LLUNA = null;
const ANGLE_FASE = { nova: 0, quart_creixent: 90, plena: 180, quart_minvant: 270 };
const NOM_FASE_LLUNA = () => ({ nova: T('Lluna nova'), quart_creixent: T('Quart creixent'), plena: T('Lluna plena'),
  quart_minvant: T('Quart minvant') });

function faseAProp(lluna, ara = new Date()) {
  return ((lluna && lluna.fases) || []).find((f) => Math.abs(new Date(f.hora) - ara) <= FASE_A_PROP_H * 36e5) || null;
}

// El nom de la fase d'ara: la principal, si és a prop; si no, la de pas.
function nomFaseLluna(lluna, ara = new Date()) {
  const f = faseAProp(lluna, ara);
  if (f) return NOM_FASE_LLUNA()[f.fase];
  const a = lluna.angle;
  return a < 90 ? T('Lluna creixent') : a < 180 ? T('Gibosa creixent') : a < 270 ? T('Gibosa minvant') : T('Lluna minvant');
}

// «5:12», «demà, 5:12» o «ahir, 23:40»; amb el dia de la setmana si és més
// lluny («dilluns 2, 21:28»).
function quanFase(iso, ara = new Date()) {
  const d = llegeixHora(iso);
  const hora = d.toLocaleTimeString(IDIOMA.codi, { hour: 'numeric', minute: '2-digit', timeZone: ZONA_HORA });
  const dies = diesEntre(ara, d);
  if (dies === 0) return hora;
  if (dies === 1) return T`demà, ${hora}`;
  if (dies === -1) return T`ahir, ${hora}`;
  return `${d.toLocaleDateString(IDIOMA.codi, { weekday: 'long', day: 'numeric', timeZone: ZONA_HORA })}, ${hora}`;
}

// La Lluna tal com es veu des d'aquí, amb la part il·luminada de veritat: el
// costat il·luminat (a la dreta quan creix, a l'hemisferi nord) és mig disc, i
// el terminador, mitja el·lipse d'amplada |cos angle|. Sense els dibuixos de
// Meteocons, que no hi són fidels (el quart creixent hi és una falç).
function dibuixLluna(angle) {
  const ns = 'http://www.w3.org/2000/svg';
  const svgL = document.createElementNS(ns, 'svg');
  svgL.setAttribute('viewBox', '-12 -12 24 24');
  svgL.setAttribute('aria-hidden', 'true');
  svgL.setAttribute('class', 'lluna');
  const r = 10;
  const fi = angle * Math.PI / 180;
  const rx = (Math.abs(Math.cos(fi)) * r).toFixed(2);
  const creix = angle < 180;
  const gibosa = Math.cos(fi) < 0;
  const vora = creix ? 1 : 0;
  const terminador = creix ? (gibosa ? 1 : 0) : (gibosa ? 0 : 1);
  const fosca = document.createElementNS(ns, 'circle');
  fosca.setAttribute('r', r);
  fosca.setAttribute('class', 'lluna-fosca');
  const clara = document.createElementNS(ns, 'path');
  clara.setAttribute('d', `M0 ${-r}A${r} ${r} 0 0 ${vora} 0 ${r}A${rx} ${r} 0 0 ${terminador} 0 ${-r}Z`);
  clara.setAttribute('class', 'lluna-clara');
  // La vora, a sobre, perquè la plena es vegi també sobre un fons clar.
  const vora2 = document.createElementNS(ns, 'circle');
  vora2.setAttribute('r', r);
  vora2.setAttribute('class', 'lluna-vora');
  svgL.append(fosca, clara, vora2);
  return svgL;
}

// Amb dades de més de DADES_VELLES_H hores, la previsió, els veredictes i els
// trens ja no es mostren: algú que no llegeixi l'avís s'hi podria fiar
// (ADR 0031). Es diu de quan són i on mirar mentrestant.
const DADES_VELLES_H = 2;

function dadesVelles(dades, ara = new Date()) {
  return ara - new Date(dades.generat) > DADES_VELLES_H * 3600000;
}

function blocDadesVelles(dades) {
  const generat = new Date(dades.generat);
  const dia = mateixDia(generat, new Date()) ? ''
    : T` del ${textData(generat)}`;
  const caixa = element('section', 'avis avis-velles');
  caixa.append(element('p', null,
    T`Les dades són de les ${horaCurta(generat) + dia}: fa més de ${DADES_VELLES_H} hores que no s’actualitzen. La previsió i l’estat dels trens no es mostren fins que tornin.`));
  const p = element('p', null, T('Mentrestant: '));
  [[T('previsió de Meteocat'), 'https://www.meteo.cat/prediccio/municipal/082665'],
    [T('radar'), 'https://www.meteo.cat/observacions/radar'],
    ['Rodalies', `https://rodalies.gencat.cat/${IDIOMA.codi === 'es' ? 'es' : 'ca'}/inici/`],
    ['FGC', 'https://x.com/fgc']].forEach(([text, href], n) => {
    const a = element('a', null, text);
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener';
    p.append(...(n ? [' · ', a] : [a]));
  });
  caixa.append(p);
  return caixa;
}

// Data d'avui (hora de Madrid) a l'hora «HH:MM»; amb «dies», la d'un altre dia.
function avuiA(hhmm, dies = 0) {
  const [h, m] = hhmm.split(':').map(Number);
  return horaDelDia(new Date(), dies, h, m);
}

// Totes les hores d'actualització d'avui, segons l'horari de les dades.
function horesActualitzacio(horari) {
  const hores = [];
  const desfase = (horari.desfase_min || 0) * 60000;
  for (const [inici, fi] of horari.trams) {
    const fins = avuiA(fi).getTime() + desfase;
    for (let t = new Date(avuiA(inici).getTime() + desfase); t <= fins;
      t = new Date(t.getTime() + horari.cada_min * 60000)) {
      hores.push(t);
    }
  }
  return hores;
}

// Cada quan s'actualitza, en el «?» de «Actualitzat a les… · propera…». Abans,
// a sobre, «Mode normal» o «Mode vigilància» amb el motiu (ADR 0010): amb
// «pluja al radar» al costat de «No plou» i «Serè», qui no coneixia la pàgina
// no sabia què es vigilava (Juanjo, 12-10-2026; ADR 0074).
function textActualitzacio(horari) {
  const normal = horari.normal_min || (horari.mode_avis && horari.mode_avis.length ? 15 : horari.cada_min);
  const avis = horari.avis_min || (horari.mode_avis && horari.mode_avis.length ? horari.cada_min : 6);
  const [[inici]] = horari.trams;
  const totElDia = horari.trams.length === 1 && inici === '00:00';
  const franges = horari.trams.map(([a, b]) => `${a}\u2013${b}`).join(T(' i '));
  const trams = totElDia ? '' : T` Només s’actualitza de ${franges}.`;
  return motiuActualitzacio(horari, avis) + T`La pàgina s’actualitza cada ${normal} minuts, i cada ${avis} quan hi ha un avís del Meteocat o de l’AEMET, un pla de Protecció Civil en alerta o emergència, pluja a Montflorit o pluja al radar a menys de ${horari.radar_km || 15} km.` + trams;
}

// En mode avís, el motiu d'ara, al davant (Juanjo, 20-10-2026: «por qué se
// actualiza cada 6 minutos si no hay ningun aviso?»). Els motius arriben en
// català, com els escriu prevision.motivos_modo_aviso.
function motiuActualitzacio(horari, avis) {
  const motius = horari.mode_avis || [];
  if (!motius.length) return '';
  const textos = {
    'avís del Meteocat': T('hi ha un avís del Meteocat'),
    'avís de l\'AEMET': T('hi ha un avís de l’AEMET'),
    'pla de Protecció Civil': T('hi ha un pla de Protecció Civil en alerta o emergència'),
    'pluja a les estacions': T('plou a Montflorit'),
    'pluja al radar': horari.km_pluja != null ? T`el radar veu pluja a ${coma(horari.km_pluja, 0)}\u00a0km`
      : T('el radar veu pluja que pot arribar en la propera hora'),
  };
  const llista = motius.map((m) => textos[m] || m);
  const junts = llista.length > 1 ? `${llista.slice(0, -1).join(', ')}${T(' i ')}${llista[llista.length - 1]}` : llista[0];
  return T`Ara cada ${avis} minuts perquè ${junts}. `;
}

// Un «?» que mostra o amaga una explicació al costat (els plans de Protecció
// Civil i el mode avís). Torna [botó, explicació].
function botoAjuda(text, etiqueta, obert = false, enCanviar = () => {}) {
  const id = `ajuda-${++numAjuda}`;
  const boto = element('button', 'ajuda-fase', '?');
  boto.type = 'button';
  boto.setAttribute('aria-expanded', String(obert));
  boto.setAttribute('aria-controls', id);
  boto.setAttribute('aria-label', etiqueta);
  boto.title = etiqueta;
  const sentit = element('span', 'sentit-fase', text);
  sentit.id = id;
  sentit.hidden = !obert;
  boto.addEventListener('click', () => {
    sentit.hidden = !sentit.hidden;
    boto.setAttribute('aria-expanded', String(!sentit.hidden));
    enCanviar(!sentit.hidden);
  });
  return [boto, sentit];
}
let numAjuda = 0;
// L'explicació segueix oberta quan la línia es torna a pintar.
let ajudaModeOberta = false;

// Les fonts de «El temps»: la previsió, el que es mesura i els avisos. Cada
// pàgina avisa només de les fonts que fa servir (Juanjo, 09-10-2026: «cada
// pagina solo avisa de lo que usa»): un error del sol, per exemple, no fa
// menys segura la previsió. Els noms són els que posa casa.py davant de «:».
const FONTS_TEMPS = ['previsió', 'ensemble', 'estació', 'estació de casa', 'estacions veïnes', 'vent', 'radar',
  'final de la pluja', 'avisos', 'plans', 'riera', 'entorn'];

// Les fonts de la pàgina que han fallat, què falla i què deixa de funcionar
// (Juanjo, 21-10-2026: abans només deia «menys segura»). La riera, amb el seu
// text, i només si no s'ha pogut calcular: sense Meteocat la calculen les
// estacions particulars de Sant Cugat i no cal avisar. La resta, el general.
// La previsió que falla i s'ha substituït per l'anterior ja té el seu avís.
function avisosFonts(dades, fonts) {
  const avisos = [];
  const errors = (dades.errors || []).filter((e) => fonts.includes(e.split(':')[0])
    && !(dades.previsio_de && e.startsWith('previsió')));
  const riera = errors.filter((e) => e.startsWith('riera:'));
  if (riera.some((e) => e.includes('sense dades recents')) && !dades.riera) {
    const fins = dades.riera_meteocat_fins;
    const dia = fins && !mateixDia(fins, new Date())
      ? T` del ${textData(fins)}` : '';
    const falta = fins ? T`Sense dades de Meteocat a Sant Cugat des de les ${horaCurta(fins) + dia}`
      : T('Sense dades recents de Meteocat a Sant Cugat');
    avisos.push(T`${falta}: ara no es pot calcular el risc de la riera.`);
  } else if (riera.some((e) => e.includes('falten mitges hores'))) {
    avisos.push(T('A l’estació de Meteocat de Sant Cugat li falten mitges hores de pluja: el risc de la riera pot quedar curt.'));
  }
  // La resta, cadascuna amb el que falla i el que deixa de sortir, i no un
  // «menys segura» general: semblava que fallava tota la pàgina (Juanjo,
  // 25-10-2026, amb els avisos de l'AEMET sense respondre a les 12 h). Que
  // no sembli per sempre («que no parezca algo permanente»): si és d'aquesta
  // actualització, ho diu, i quan es torna a provar; si fa més d'una
  // actualització que falla, des de quan (fonts_falla.py, ADR 0031).
  const vistos = new Set();
  let ara = true;
  for (const e of errors) {
    if (e.startsWith('riera')) continue;
    const font = e.startsWith('entorn: ') ? e.split(':').slice(0, 2).join(':') : e.split(':')[0];
    const des = (dades.fonts_falla || {})[font];
    const fa = des && ((dades.generat ? new Date(dades.generat) : new Date()) - llegeixHora(des)) / 60000;
    const t = (TEXT_FONT_FALLA()[font] || TEXT_FONT_DESCONEGUDA)();
    let text;
    if (fa > FONT_FALLA_ACTUALITZACIO_MIN) {
      ara = false;
      text = T`Des ${quanDes(des)} ${t.des}: ${t.efecte}.`;
    } else {
      text = T`En aquesta actualització ${t.ara}: ${t.efecte}.`;
    }
    if (!vistos.has(text)) {
      vistos.add(text);
      avisos.push(text);
    }
  }
  if (vistos.size) {
    const pendent = dades.horari && properaPendent(dades);
    const quan = pendent && horaCurta(new Date(pendent.getTime() + ESPERA_PUBLICACIO_MIN * 60000));
    avisos[avisos.length - 1] += ' ' + (!ara ? T('Es torna a provar a cada actualització.')
      : quan ? T`Es torna a provar a la propera actualització, a les ${quan}.`
        : T('Es torna a provar a la propera actualització.'));
  }
  return avisos;
}

// Més d'aquests minuts fallant: ja no és d'aquesta actualització (n'hi ha
// cada 15 minuts, i amb pluja, més sovint).
const FONT_FALLA_ACTUALITZACIO_MIN = 20;

// «de les 12:00», «d’ahir a les 18:00», «del dilluns 19 a les 18:00».
function quanDes(iso) {
  const h = horaCurta(iso);
  const dies = diesEntre(llegeixHora(iso), new Date());
  if (dies <= 0) return T`de les ${h}`;
  if (dies === 1) return T`d’ahir a les ${h}`;
  return T`del ${textData(iso)} a les ${h}`;
}

// Per a cada font de la pàgina: el que no ha arribat en aquesta actualització
// (ara), el mateix quan fa estona que falla (des) i què no surt (efecte).
const TEXT_FONT_DESCONEGUDA = () => ({ ara: T('una de les fonts no ha respost'),
  des: T('una de les fonts no respon'), efecte: T('la resta de la informació és al dia') });
const TEXT_FONT_FALLA = () => {
  const estacio = { ara: T('l’estació del barri no ha respost'), des: T('l’estació del barri no respon'),
    efecte: T('el temps d’ara surt de les estacions veïnes') };
  return {
    previsió: () => ({ ara: T('no ha arribat la previsió dels models'), des: T('no arriba la previsió dels models'),
      efecte: T('no hi ha previsió hora a hora') }),
    ensemble: () => ({ ara: T('no han arribat les 40 variants del model alemany'),
      des: T('no arriben les 40 variants del model alemany'), efecte: T('la probabilitat de pluja és menys afinada') }),
    estació: () => estacio,
    'estació de casa': () => estacio,
    'estacions veïnes': () => ({ ara: T('les estacions veïnes no han respost'), des: T('les estacions veïnes no responen'),
      efecte: T('si plou ara, només ho sap l’estació del barri') }),
    vent: () => ({ ara: T('l’estació de Meteocat de Sant Cugat no ha respost'),
      des: T('l’estació de Meteocat de Sant Cugat no respon'), efecte: T('no surt el vent mesurat') }),
    radar: () => ({ ara: T('el radar no ha respost'), des: T('el radar no respon'),
      efecte: T('no es pot dir si s’acosta pluja') }),
    'final de la pluja': () => ({ ara: T('no s’ha pogut calcular quan pararà de ploure'),
      des: T('no es pot calcular quan pararà de ploure'), efecte: T('la resta de la previsió és al dia') }),
    avisos: () => ({ ara: T('no han arribat els avisos de l’AEMET'), des: T('no arriben els avisos de l’AEMET'),
      efecte: T('els de Meteocat, sí') }),
    plans: () => ({ ara: T('no han arribat els plans de Protecció Civil'), des: T('no arriben els plans de Protecció Civil'),
      efecte: T('si n’hi hagués un d’activat, no sortiria') }),
    'entorn: incendis': () => ({ ara: T('no han arribat els incendis dels Bombers'),
      des: T('no arriben els incendis dels Bombers'), efecte: T('si n’hi hagués un a prop, no sortiria') }),
    'entorn: pla_alfa': () => ({ ara: T('no ha arribat el Pla Alfa d’avui'), des: T('no arriba el Pla Alfa'),
      efecte: T('no surt el risc d’incendi forestal') }),
    trens: () => ({ ara: T('no ha arribat l’estat dels trens'), des: T('no arriba l’estat dels trens'),
      efecte: T('no se sap si hi ha incidències') }),
    trànsit: () => ({ ara: T('no ha arribat l’estat del trànsit'), des: T('no arriba l’estat del trànsit'),
      efecte: T('no se sap si hi ha incidències a prop') }),
    'índex UV': () => ({ ara: T('no ha arribat l’índex UV'), des: T('no arriba l’índex UV'),
      efecte: T('no surt la protecció solar recomanada') }),
  };
};

function pintaHorari(dades, fonts = FONTS_TEMPS) {
  const ara = new Date();
  const generat = horaDades(dades);
  const hores = horesActualitzacio(dades.horari);
  // La propera, quan la pàgina tornarà a llegir les dades: l'hora prevista i
  // el marge que deixa perquè s'hagin publicat (Juanjo, 22-10-2026: amb l'hora
  // prevista, «la gente se queda mirando la hora y ve que no pasa»).
  const pendent = properaPendent(dades, ara);
  const propera = pendent && new Date(pendent.getTime() + ESPERA_PUBLICACIO_MIN * 60000);
  const darreraPrevista = hores.filter((t) => t <= ara).pop();
  // L'hora d'actualització, destacada, al capdamunt de la pàgina (Juanjo, 09-10-2026:
  // «visible nada más abrir»).
  const dia = mateixDia(generat, ara) ? '' : T` del ${textData(generat)}`;
  // Al costat, el «?» de cada quan s'actualitza (ADR 0074), enganxat a
  // l'última paraula perquè no baixi sol a una altra línia.
  const [boto, sentit] = botoAjuda(textActualitzacio(dades.horari), T('Cada quan s’actualitza?'), ajudaModeOberta,
    (obert) => { ajudaModeOberta = obert; });
  const linia = element('span', 'hores');
  const final = element('span', 'sense-tall');
  final.append(element('strong', null, propera ? horaCurta(propera) : T`demà a les ${dades.horari.trams[0][0]}`), '.', boto);
  linia.append(T('Actualitzat a les '), element('strong', null, horaCurta(generat) + dia), T(' · propera: '), final);
  $('horari').replaceChildren(linia, sentit);
  // Calculades fora de casa perquè el servidor habitual no publica (ADR 0032).
  if (dades.reserva) linia.append(' ', element('span', 'reserva', T('Dades del servidor de reserva.')));
  const avisos = [];
  if (darreraPrevista && new Date(dades.generat) < darreraPrevista - 5 * 60000
      && ara - darreraPrevista > MARGE_RETARD_MIN * 60000) {
    avisos.push(T`L’actualització de les ${horaCurta(new Date(darreraPrevista.getTime() + ESPERA_PUBLICACIO_MIN * 60000))} no s’ha fet: les dades són de les ${horaCurta(generat)}.`);
  }
  avisos.push(...avisosFonts(dades, fonts));
  $('avis-dades').textContent = avisos.join(' ');
  $('avis-dades').hidden = !avisos.length;
}

// La pàgina oberta es posa al dia sola: torna a llegir les dades després de
// cada actualització prevista. La publicació (càlcul i GitHub Pages) tarda
// un minut o dos: es mira ESPERA_PUBLICACIO_MIN després de l'hora i, si les
// dades encara no són noves, cada minut fins a REINTENTS vegades.
const ESPERA_PUBLICACIO_MIN = 2;
const REINTENTS = 10;

// La propera actualització que han de portar les dades: la primera de
// l'horari després de la seva hora, encara que ja hagi passat i s'estigui
// publicant. Comptada des del rellotge, a les 13:31 amb dades de les 13:15
// deia «propera: 13:45» i se saltava la de les 13:30 (Juanjo, 11-10-2026:
// «por qué pone esto si se tiene que actualizar cada 15min?»), i la pàgina
// no la tornava a llegir fins a les 13:47. Si fa més de MARGE_RETARD_MIN
// que havia d'arribar, ja no s'espera: mana el rellotge. Null si avui no
// en queda cap.
function properaPendent(dades, ara = new Date()) {
  const hores = horesActualitzacio(dades.horari);
  const generat = new Date(dades.generat);
  const pendent = hores.find((t) => t > generat);
  if (pendent && ara - pendent <= MARGE_RETARD_MIN * 60000) return pendent;
  return hores.find((t) => t > ara) || null;
}

// Propera actualització segons l'horari: avui o, si ja no n'hi ha cap, la
// primera de demà.
function properaActualitzacio(horari, ara = new Date()) {
  const propera = horesActualitzacio(horari).find((t) => t > ara);
  if (propera) return propera;
  const dema = avuiA(horari.trams[0][0], 1);
  return new Date(dema.getTime() + (horari.desfase_min || 0) * 60000);
}

// Les dades les puja el NAS a IONOS a cada actualització; la còpia de GitHub
// (al costat de la pàgina) es renova cada mitja hora com a molt i és la
// reserva si IONOS no respon (ADR 0020) o si el que serveix va per darrere
// (dadesEndarrerides): quan la pujada a IONOS falla, publica.sh publica a
// GitHub, i IONOS es queda amb les dades d'abans (auditoria del 07-10-2026,
// ADR 0038).
const DADES_URL = 'https://bilateria.org/app/meteo-local/';
const ESPERA_DADES_MS = 6000;
const DADES_RESERVA_MIN = 45;

// Baixa un JSON amb un temps màxim que cobreix tota la descàrrega, també el
// cos: «fetch» es resol amb les capçaleres, i el temporitzador s'aturava
// abans de llegir el cos, de manera que una connexió penjada a mig cos no es
// tallava mai (auditoria del 09-10-2026).
function baixa(url) {
  const control = new AbortController();
  const temps = setTimeout(() => control.abort(), ESPERA_DADES_MS);
  return fetch(`${url}?t=${Date.now()}`, { cache: 'no-store', signal: control.signal })
    .then((r) => {
      if (!r.ok) throw new Error(r.status);
      // L'hora en què el fitxer va arribar al servidor (Last-Modified), per
      // dir quan s'han actualitzat de veritat les dades (horaDades).
      const publicat = r.headers && r.headers.get('Last-Modified');
      return r.json().then((d) => ambDesfas(d)).then((d) => {
        if (publicat && d && typeof d === 'object' && !Array.isArray(d)) d.publicat_servidor = new Date(publicat).toISOString();
        return d;
      });
    })
    .finally(() => clearTimeout(temps));
}

// L'hora real de les dades: quan van arribar al servidor, que és uns segons o
// un minut després de calcular-les (Juanjo, 22-10-2026: «la primera puede ser
// la hora real de carga de datos»). Sense la capçalera, o si no quadra (més
// d'hora que el càlcul o mitja hora més tard), la del càlcul.
function horaDades(dades) {
  const generat = new Date(dades.generat);
  const publicat = dades.publicat_servidor && new Date(dades.publicat_servidor);
  return publicat && publicat >= generat && publicat - generat < 30 * 60000 ? publicat : generat;
}

// Si les dades d'IONOS van per darrere: tenen més de DADES_RESERVA_MIN o, si
// porten l'horari, n'hi falta una actualització que ja s'hauria d'haver
// publicat. Cada matí, de 06:01 a 06:15, IONOS tanca l'SSH, la pujada falla i
// el NAS publica a GitHub; amb només els 45 minuts, la pàgina es quedava amb
// les dades de les 06:00 fins a les 06:15 (11-10-2026).
function dadesEndarrerides(dades, ara = new Date()) {
  const generat = new Date(dades.generat);
  if (ara - generat > DADES_RESERVA_MIN * 60000) return true;
  if (!dades.horari) return false;
  const limit = ara - ESPERA_PUBLICACIO_MIN * 60000;
  const darrera = horesActualitzacio(dades.horari).filter((t) => t <= limit).pop();
  return Boolean(darrera) && generat < darrera;
}

function llegeixDades(nom) {
  return baixa(DADES_URL + nom).then((dades) => {
    if (!dadesEndarrerides(dades)) return dades;
    // IONOS respon, però amb dades velles: es mira la còpia de GitHub i es
    // fa servir la més nova de les dues.
    return baixa(ARREL + nom)
      .then((copia) => (new Date(copia.generat) > new Date(dades.generat) ? copia : dades), () => dades);
  }, () => baixa(ARREL + nom));
}

function carrega(url, pinta, error) {
  let dades = null;
  let reintents = 0;
  let temporitzador = null;
  let previst = 0;

  function programa() {
    clearTimeout(temporitzador);
    // Primer, la que han de portar les dades encara que ja hagi passat (com a
    // molt d'aquí a un minut); acabats els reintents, la de l'horari.
    const pendent = !reintents && properaPendent(dades);
    previst = reintents && reintents <= REINTENTS ? Date.now() + 60000
      : pendent ? Math.max(pendent.getTime() + ESPERA_PUBLICACIO_MIN * 60000, Date.now() + 60000)
        : properaActualitzacio(dades.horari).getTime() + ESPERA_PUBLICACIO_MIN * 60000;
    temporitzador = setTimeout(llegeix, previst - Date.now());
  }

  function llegeix() {
    clearTimeout(temporitzador);
    llegeixDades(url)
      .then((noves) => {
        // Les mateixes dades d'abans: la publicació encara no ha arribat.
        reintents = dades && noves.generat === dades.generat ? reintents + 1 : 0;
        dades = noves;
        // Es torna a pintar sempre: l'hora també canvia el que es mostra.
        pinta(dades);
        programa();
      })
      .catch(() => {
        if (!dades) {
          // Sense cap dada encara (cobertura fluixa, per exemple): s'avisa i
          // es torna a provar al cap d'un minut, sense que calgui recarregar.
          error();
          previst = Date.now() + 60000;
          temporitzador = setTimeout(llegeix, 60000);
          return;
        }
        // Les d'abans es tornen a pintar: si ja tenen massa hores, la pàgina
        // ho diu i amaga la previsió (dadesVelles) encara que no arribi res
        // de nou (auditoria del 07-10-2026).
        pinta(dades);
        reintents += 1;
        programa();
      });
  }

  // Amb la pestanya amagada (sobretot al mòbil) els temporitzadors s'aturen:
  // en tornar-hi, es mira si ja tocava (o si encara no hi ha dades) i, si no,
  // es torna a pintar el que hi ha, perquè l'edat de les dades es comprovi.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    if (!dades || Date.now() >= previst) llegeix();
    else pinta(dades);
  });
  enArribarUnAvis(llegeix);
  llegeix();
}

// Quan arriba un avís al dispositiu amb la web oberta, el service worker ho
// diu (sw.js) i la pàgina torna a llegir ara mateix les dades i l'historial de
// «Perill», en lloc d'esperar la propera lectura (Juanjo, 12-10-2026; ADR 0048).
const ALARRIBAR_AVIS = [];
function enArribarUnAvis(f) { ALARRIBAR_AVIS.push(f); }
function arribaUnAvis() { ALARRIBAR_AVIS.forEach((f) => f()); }
if ('serviceWorker' in navigator && navigator.serviceWorker.addEventListener) {
  navigator.serviceWorker.addEventListener('message', (e) => {
    if (e.data && e.data.tipus === 'avis') arribaUnAvis();
  });
}

// Avisos de l'AEMET al Vallès, amb el dia i la franja de cadascun.

// «avui», «demà» o el dia de la setmana.
function nomDiaCurt(data, ara) {
  const dies = diesEntre(ara, data);
  if (dies === 0) return T('avui');
  if (dies === 1) return T('demà');
  return llegeixHora(data).toLocaleDateString(IDIOMA.codi, { weekday: 'long', timeZone: ZONA_HORA });
}

// «a les 18:00», «a la 01:00» o «a mitjanit».
function aLaHora(data) {
  const h = horaCurta(data);
  if (h === '00:00') return T('a mitjanit');
  return h.startsWith('01:') ? T`a la ${h}` : T`a les ${h}`;
}

// Franja d'un avís, amb el dia: «avui fins a les 20:00», «demà de 09:00 a
// 18:00», «demà de 22:00 a mitjanit». Si ja ha començat, només el final.
function textFranja(inici, fi, ara) {
  // Mitjanit és el final del dia de l'avís, no el començament del següent.
  const diaFi = nomDiaCurt(new Date(fi - 1), ara);
  if (inici <= ara) return diaFi === T('avui') ? T`avui fins ${aLaHora(fi)}` : T`fins ${diaFi} ${aLaHora(fi)}`;
  const h = horaCurta(inici);
  const de = /^(01|11):/.test(h) ? T`d\u2019${h}` : T`de ${h}`;
  const dia = nomDiaCurt(inici, ara);
  if (diaFi !== dia) return T`${dia} ${de} fins ${diaFi} ${aLaHora(fi)}`;
  // «de 09:00 a 18:00», «de 22:00 a mitjanit».
  const fins = horaCurta(fi) === '00:00' ? T('a mitjanit') : T`a ${horaCurta(fi)}`;
  return `${dia} ${de} ${fins}`;
}

// Una frase per nivell i tipus d'avís, amb totes les franges i el dia de
// cadascuna: «Avís groc de l'AEMET per pluja i tempestes al Vallès: avui fins
// a les 20:00; demà de 09:00 a 18:00 i de 22:00 a mitjanit.»
// Els avisos de l'AEMET, un element per nivell i tipus, amb el seu text tal
// com el publica: en castellà, citat i marcat com a tal, agrupat per dia
// (ADR 0033). El dia només es diu si n'hi ha més d'un.
function blocAvisosAemet(avisos, ara = new Date()) {
  return frasesAvisos(avisos, ara).map((f) => {
    const item = element('p', `avis-item ${f.nivell}`);
    item.dataset.detall = fitxaPerill((h) => h.clau.startsWith('aemet:') && f.tipus.has(h.clau.split(':')[1]));
    const tipus = [...f.tipus].sort();
    item.dataset.curt = T`AEMET: avís ${TD(f.nivell)} per ${tipus.map((x) => TD(x)).join(T(' i '))}, ${f.quan}`;
    item.dataset.clau = `aemet:${f.nivell}:${tipus.join(',')}:` + avisos
      .filter((a) => a.nivel === f.nivell && f.tipus.has(a.tipo)).map((a) => `${a.inicio}/${a.fin}`).sort().join(',');
    item.append(element('strong', null, f.titol), `: ${f.quan}.`);
    const perDia = [];
    for (const a of [...avisos].sort((x, y) => new Date(x.inicio) - new Date(y.inicio))) {
      if (a.nivel !== f.nivell || !f.tipus.has(a.tipo) || !a.descripcio) continue;
      if (new Date(a.fin).getTime() + 1000 <= ara.getTime()) continue;
      const dia = nomDiaCurt(new Date(Math.max(new Date(a.inicio).getTime(), ara.getTime())), ara);
      let d = perDia.find((x) => x.dia === dia);
      if (!d) perDia.push(d = { dia, textos: [] });
      if (!d.textos.includes(a.descripcio)) d.textos.push(a.descripcio);
    }
    perDia.forEach((d, n) => {
      item.append(n ? '; ' : ' ', ...(perDia.length > 1 ? [`${d.dia}: `] : []));
      d.textos.forEach((t, m) => {
        const cita = element('q', null, t);
        cita.lang = 'es';
        item.append(...(m ? [' ', cita] : [cita]));
      });
    });
    return item;
  });
}

function textAvisos(avisos, ara = new Date()) {
  return frasesAvisos(avisos, ara).map((f) => `${f.titol}: ${f.quan}.`).join(' ');
}

// Una frase per nivell i tipus: {nivell, tipus (Set), titol, quan}, del més
// greu al més lleu.
function frasesAvisos(avisos, ara = new Date()) {
  // 1. Franges de cada nivell i tipus, ajuntant les que es toquen. Els avisos
  // acaben a «hh:59:59»: un segon més dona l'hora en punt.
  const perTipus = {};
  for (const a of avisos) {
    const fi = new Date(a.fin).getTime() + 1000;
    if (fi <= ara.getTime()) continue;
    const inici = Math.max(new Date(a.inicio).getTime(), ara.getTime());
    (perTipus[`${a.nivel}|${a.tipo}`] = perTipus[`${a.nivel}|${a.tipo}`] || []).push([inici, fi]);
  }
  // 2. Tipus que comparteixen franja: «pluja i tempestes».
  const perFranja = {};
  for (const [clau, franges] of Object.entries(perTipus)) {
    const [nivell, tipus] = clau.split('|');
    franges.sort((x, y) => x[0] - y[0]);
    const juntes = [];
    for (const f of franges) {
      const darrera = juntes[juntes.length - 1];
      if (darrera && f[0] <= darrera[1]) darrera[1] = Math.max(darrera[1], f[1]);
      else juntes.push([...f]);
    }
    for (const [inici, fi] of juntes) {
      const k = `${nivell}|${inici}|${fi}`;
      (perFranja[k] = perFranja[k] || new Set()).add(tipus);
    }
  }
  // 3. Una frase per nivell i tipus, amb les franges en ordre i agrupades
  // per dia.
  const frases = {};
  const tipusDe = {};
  for (const [k, tipus] of Object.entries(perFranja)) {
    const [nivell, inici, fi] = k.split('|');
    const clau = `${nivell}|${[...tipus].sort().map((x) => TD(x)).join(T(' i '))}`;
    (frases[clau] = frases[clau] || []).push([Number(inici), Number(fi)]);
    (tipusDe[clau] = tipusDe[clau] || new Set()); tipus.forEach((t) => tipusDe[clau].add(t));
  }
  const ordre = { vermell: 0, taronja: 1, groc: 2 };
  return Object.entries(frases)
    .sort(([a, fa], [b, fb]) => (ordre[a.split('|')[0]] ?? 3) - (ordre[b.split('|')[0]] ?? 3)
      || Math.min(...fa.map((f) => f[0])) - Math.min(...fb.map((f) => f[0])))
    .map(([clau, franges]) => {
      const [nivell, tipus] = clau.split('|');
      franges.sort((x, y) => x[0] - y[0]);
      // Les franges del mateix dia, juntes: «demà de 09:00 a 18:00 i de 22:00 a mitjanit».
      const dies = [];
      for (const [inici, fi] of franges) {
        const text = textFranja(new Date(inici), new Date(fi), ara);
        const dia = text.split(' ')[0];
        const darrer = dies[dies.length - 1];
        if (darrer && darrer.dia === dia && text.startsWith(`${dia} d`)) {
          darrer.parts.push(text.slice(dia.length + 1));
        } else {
          dies.push({ dia, parts: [text] });
        }
      }
      const quan = dies.map((d) => d.parts.join(T(' i '))).join('; ');
      // Les franges, també per a «Perill», que agrupa les fitxes com aquestes frases (perill.grupsAemet).
      return { nivell, tipus: tipusDe[clau], titol: T`AEMET: avís ${TD(nivell)} per ${tipus} al Vallès`, quan, franges };
    });
}

// Quan Open-Meteo no respon, la previsió és l'última bona (ADR 0016).
function textPrevisioAnterior(dades) {
  if (!dades || !dades.previsio_de) return '';
  const de = new Date(dades.previsio_de);
  const dia = mateixDia(de, new Date()) ? '' : T` del ${textData(de)}`;
  return T`Open-Meteo, d\u2019on surten els models, ara no respon: la previsió és la de les ${horaCurta(de)}${dia}.`;
}

// Plans de Protecció Civil que depenen del temps (inundacions, vent, neu,
// onades de calor i de fred, contaminació), en prealerta, alerta o emergència:
// avís destacat a dalt de la pàgina, amb l'enllaç al comunicat (ADR 0051).
const NOM_FASE = { prealerta: 'prealerta', alerta: 'alerta', 'emergència': 'emergència' };
// La franja, del color de la fase: la prealerta no ha d'espantar.
const COLOR_FASE = { prealerta: 'prealerta', alerta: 'taronja', 'emergència': 'vermell' };
// Què vol dir cada fase, resumit de la definició oficial del conjunt de dades
// de Protecció Civil; es desplega amb el «?» (Juanjo, 09-10-2026).
const SENTIT_FASE = {
  prealerta: () => T('Es preveu un risc a mitjà termini. El pla no està activat: només cal estar-ne pendent.'),
  alerta: () => T('El pla està activat: es preveu un risc important a curt termini, o hi ha afectacions que no són greus.'),
  'emergència': () => T('El pla està activat per un risc greu per a la població: segueix les indicacions de Protecció Civil.'),
};

// El «?» de la fase: obre i tanca, a sota, una línia amb què vol dir.
function ajudaFase(fase) {
  if (!SENTIT_FASE[fase]) return [];
  return botoAjuda(SENTIT_FASE[fase](), T`Què vol dir ${TD(NOM_FASE[fase])}?`);
}

// «de prealerta», però «d’alerta» i «d’emergència»; en castellà, sempre «de».
function deFase(fase) {
  if (IDIOMA.codi.startsWith('es')) return `de ${fase}`;
  return /^[aeiouàèéíòóúh]/i.test(fase) ? `d’${fase}` : `de ${fase}`;
}

// «15/10/2026 10:33», l'hora de Madrid de les dades de Protecció Civil.
function dataPla(text) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})$/.exec(text || '');
  return m ? deRellotge(+m[3], +m[2], +m[1], +m[4], +m[5]) : null;
}

// L'adreça de la fitxa d'un pla a «Perill»: en prealerta, una de fixa per
// pla (perill.js); si ha avisat, la del seu episodi a l'historial.
function idPla(p) {
  return `pla-${p.pla}`.toLowerCase().replace(/[^a-z0-9-]+/g, '-');
}

function fitxaDelPla(p) {
  const e = p.fase !== 'prealerta' && (HISTORIAL_PERILL || [])
    .find((h) => h.clau && h.clau.startsWith(`pla:${p.pla}`) && !h.fi);
  return e ? idFitxa(e) : idPla(p);
}

// La fitxa a «Perill» de cada alerta, perquè l'enllaç hi porti i la destaqui
// (Juanjo, 16-10-2026: «con este enlace no me sale el resalte»): la de
// l'historial que és activa i passa la prova; si no n'hi ha, «Perill».
function actiuPerill(e, ara = new Date()) {
  return !e.fi && !(e.fins && new Date(e.fins) <= ara);
}

function fitxaPerill(prova) {
  const e = (HISTORIAL_PERILL || []).find((h) => h.clau && actiuPerill(h) && prova(h));
  return e ? `perill.html#${idFitxa(e)}` : 'perill.html';
}

const FITXA_ALFA = 'perill.html#pla-alfa';

// Les línies d'alerta del resum del dia (bot.linies_perill_dia), amb la
// marca del nivell o la icona al davant.
const LINIA_PERILL = /^(⟦[^⟧]+⟧ ?|\S+ )?(Avís|Aviso|Protecció Civil|Protección Civil|Perill de|Peligro de|Incendi|Incendio|Pla Alfa|Plan Alfa|Meteocat|AEMET|Bombers|Temps a Montflorit)[ :]|no (é|e)s oficial\)|\(no oficial\)/;

function fitxaDeLinia(text) {
  const pla = /Protecci(ó|ón) Civil/.test(text) && text.match(/\(([A-Z]+)\)/);
  if (pla) return `perill.html#${fitxaDelPla({ pla: pla[1], fase: 'alerta' })}`;
  if (/Meteocat/.test(text)) return fitxaPerill((h) => h.clau.startsWith('meteocat:'));
  if (/AEMET/.test(text)) {
    const t = text.toLowerCase();
    return fitxaPerill((h) => h.clau.startsWith('aemet:')
      && [h.clau.split(':')[1], TD(h.clau.split(':')[1])].some((x) => t.includes(x.toLowerCase())));
  }
  if (/riera/i.test(text)) return fitxaPerill((h) => h.clau.startsWith('riera:'));
  if (/ncendi/.test(text)) return fitxaPerill((h) => h.clau.startsWith('incendi:'));
  if (/Alfa/.test(text)) return FITXA_ALFA;
  if (/oficial\)/.test(text)) return fitxaPerill((h) => h.clau === 'propi');
  return 'perill.html';
}

// Els plans de Protecció Civil, un element per pla, del color de la fase. Els
// avisos de Meteocat, a part, amb la seva franja i la seva fitxa (Juanjo,
// 17-10-2026: «separalos de proteccion civil porque son avisos aparte»).
function blocPlans(plans) {
  return (plans || []).map((p) => {
    const item = element('p', `avis-item ${COLOR_FASE[p.fase] || 'vermell'}`);
    item.setAttribute('aria-label', T('Avís de Protecció Civil'));
    item.dataset.tipus = 'pla';
    item.dataset.clau = `pla:${p.pla}:${p.fase}`;
    item.dataset.curt = T`Protecció Civil: pla ${TD(p.nom)} (${p.pla}) en ${TD(NOM_FASE[p.fase] || p.fase)}`;
    item.append(element('strong', null,
      T`Protecció Civil: pla ${TD(p.nom)} (${p.pla}) en fase ${deFase(TD(NOM_FASE[p.fase] || p.fase))}.`),
    ...ajudaFase(p.fase));
    if (p.fase === 'emergència') {
      item.append(T(' Evita els desplaçaments que no siguin necessaris.'));
    }
    // El comunicat en PDF, a la fitxa de «Perill», on porta la línia (ADR 0075):
    // la de l'historial si el pla ha avisat (alerta o emergència) o, en
    // prealerta, la que «Perill» fa a «Ara» (ADR 0091).
    item.dataset.detall = `perill.html#${fitxaDelPla(p)}`;
    const des = dataPla(p.des_de);
    if (des) item.dataset.desDe = des.toISOString();
    return item;
  });
}

// Tots els avisos vigents en un sol bloc, «Avisos actius»: Protecció Civil,
// el risc calculat (si n'hi ha) i l'AEMET, cadascun amb la franja del seu
// nivell. Sense cap, res (proposta del 08-10-2026: amb dos avisos, al mòbil
// la temperatura quedava fora de la pantalla).
// Incendis forestals en curs que interessen al barri (Bombers, ADR 0071) i el Pla Alfa de Cerdanyola des
// del nivell 3, amb els tancaments que toquen Collserola (Agents Rurals, ADR 0046).
const ALFA_NIVELL_MOSTRAR = 3;

function blocEntorn(entorn) {
  const items = [];
  // Els mapes de Bombers i dels Agents Rurals, a «Perill» (ADR 0075).
  const nouItem = (nivell, titol, resta, clau) => {
    const item = element('p', `avis-item ${nivell}`);
    item.append(element('strong', null, titol), resta);
    item.dataset.clau = clau;
    item.dataset.curt = titol;
    return item;
  };
  for (const i of (entorn && entorn.incendis) || []) {
    const km = i.km != null ? T`, a ${coma(i.km)}\u00a0km de Montflorit` : '';
    // Dins del parc, dit clarament (Juanjo, 11-10-2026; ADR 0071).
    const item = nouItem('vermell', i.collserola ? T`Bombers: incendi forestal dins del Parc de Collserola (${i.municipi})`
      : T`Bombers: incendi forestal a ${i.municipi}`,
      T`${km}, des de les ${horaCurta(i.inici)}.`, `incendi:${i.id}`);
    item.dataset.detall = fitxaPerill((h) => h.clau === `incendi:${i.id}`);
    items.push(item);
  }
  const alfa = (entorn && entorn.pla_alfa) || {};
  for (const [dia, nom] of [['avui', () => T('avui')], ['dema', () => T('demà')]]) {
    const n = alfa[dia];
    if (n != null && n >= ALFA_NIVELL_MOSTRAR) {
      const item = nouItem(n >= 4 ? 'vermell' : 'taronja', T`Pla Alfa de Cerdanyola: nivell ${n} ${nom()}`,
        T(': accés restringit als espais forestals.'), `alfa:${dia}:${n}`);
      item.dataset.detall = FITXA_ALFA;
      items.push(item);
    }
  }
  for (const t of alfa.tancaments || []) {
    const item = nouItem('vermell', T`Agents Rurals: tancat ${t.espai}`, '.', `tancat:${t.espai}`);
    item.dataset.detall = FITXA_ALFA;
    items.push(item);
  }
  return items;
}

// Els avisos de Meteocat, un per línia, del color del seu grau (ADR 0071),
// sempre a part dels plans de Protecció Civil, que són avisos d'un altre
// organisme (Juanjo, 17-10-2026; abans anaven dins del pla, ADR 0067).
const COLOR_SMP = { mig: 'groc', alt: 'taronja', maxim: 'vermell' };

// Agrupats per fenomen, com al bloc plegat: «Avisos actius (3)» deia 3 i,
// desplegat, en sortien 4, perquè Meteocat dona un avís per cada meteor de la
// pluja (revisor, 18-10-2026; ADR 0101). Cada grup, del color del pitjor.
const RANG_SMP = { mig: 1, alt: 2, maxim: 3 };
function blocSmp(smp) {
  if (!smp) return [];
  const es = IDIOMA.codi.startsWith('es');
  const grups = new Map();
  (smp.linies || []).filter((l) => COLOR_SMP[l.nivell]).forEach((l, n) => {
    const clau = l.fenomen || `linia${n}`;
    if (!grups.has(clau)) grups.set(clau, []);
    grups.get(clau).push(l);
  });
  return [...grups.values()].map((ls) => {
    ls.sort((a, b) => RANG_SMP[b.nivell] - RANG_SMP[a.nivell]);
    const item = element(ls.length > 1 ? 'div' : 'p', `avis-item ${COLOR_SMP[ls[0].nivell]}`);
    item.dataset.tipus = 'smp';
    item.dataset.detall = fitxaPerill((h) => h.clau.startsWith('meteocat:'));
    if (ls.length === 1) item.append(es ? ls[0].es : ls[0].ca);
    else item.append(...ls.map((l) => element('span', 'smp-linia', es ? l.es : l.ca)));
    return item;
  });
}

// Els avisos de Meteocat per al bloc plegat (ADR 0094): una línia per fenomen,
// amb el nivell més alt i les hores (smp.per_fenomen). Amb dades d'abans de la
// 3.90.0, sense «fenomens», les línies senceres: que no en falti cap.
const GRAU_SMP = { mig: () => T('moderat'), alt: () => T('alt'), maxim: () => T('molt alt') };

function quanDies(dies, ara) {
  return Object.entries(dies || {}).sort().map(([dia, franges]) => {
    const hores = franges.map(([i, f]) => T`de ${i} a ${f} h`).join(T(' i '));
    return `${nomDiaCurt(dia, ara)} ${hores}`;
  }).join('; ');
}

function curtsSmp(smp, href, ara) {
  if (!smp) return [];
  const es = IDIOMA.codi.startsWith('es');
  const fenomens = (smp.fenomens || []).filter((f) => COLOR_SMP[f.nivell]);
  if (!fenomens.length) {
    return (smp.linies || []).filter((l) => COLOR_SMP[l.nivell]).map((l, n) => {
      const p = element('p', `avis-item curt ${COLOR_SMP[l.nivell]}`, es ? l.es : l.ca);
      p.dataset.clau = `smp:${n}:${l.nivell}:${l.ca}`;
      return ambDetall(p, href);
    });
  }
  return fenomens.map((f) => {
    const p = element('p', `avis-item curt ${COLOR_SMP[f.nivell]}`);
    p.append(T`Meteocat: perill ${GRAU_SMP[f.nivell]()} per ${TD(f.fenomen)}, ${quanDies(f.dies, ara)}`);
    p.dataset.clau = `smp:${f.fenomen}:${f.nivell}:${JSON.stringify(f.dies)}`;
    return ambDetall(p, href);
  });
}

// Els talls de llum del barri (llum.py, ADR 0072), també a «Avisos actius»:
// fins ara només eren a «Consultes › Llum» (Juanjo, 12-10-2026; ADR 0074). Els
// carrers, estimats (e-distribució no els dona), i el detall, a «Llum».
function quanLlum(iso, desDe = false, ara = new Date()) {
  const t = llegeixHora(iso);
  if (mateixDia(t, ara)) return desDe ? T`des de les ${horaCurta(t)}` : T`les ${horaCurta(t)}`;
  const d = `${partsHora(t).dia}/${partsHora(t).mes}`;
  return desDe ? T`des del ${d} a les ${horaCurta(t)}` : T`el ${d} a les ${horaCurta(t)}`;
}

function textTall(t, ara = new Date()) {
  const titol = t.on === 'vora' ? T('Tall de llum al límit del barri') : T('Tall de llum al barri');
  const qui = t.clients == null ? T('Clients sense llum') : t.clients === 1 ? T('1 client sense llum')
    : T`${t.clients} clients sense llum`;
  let frase = `${t.programat ? T('treballs programats') : T('avaria')}. ${qui}`;
  if (t.inici) frase += ` ${quanLlum(t.inici, true, ara)}`;
  if (t.fins) frase += T`; previst fins a ${quanLlum(t.fins, false, ara)}`;
  frase += '.';
  if ((t.carrers || []).length) {
    frase += ' ' + (t.carrers.length === 1 ? T`Carrer probable (estimació): ${t.carrers[0]}.`
      : T`Carrers probables (estimació): ${t.carrers.join(T(' o '))}.`);
  }
  return [titol, frase];
}

// Cada fitxa de «Perill» té la seva adreça (perill.html#…), per compartir-la
// (ADR 0072) i per anar-hi des de la portada (ADR 0076).
function idFitxa(e) {
  return 'a-' + `${e.clau}-${e.inici}`.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9-]+/g, '-').replace(/-+/g, '-').toLowerCase();
}

// La riera de Sant Cugat activa, també a «Avisos actius» (Juanjo, 12-10-2026;
// ADR 0076): fins ara només era a «Perill», perquè les dades públiques no en
// porten l'estat. Surt de l'historial de «Perill» (avisos.json), que la pàgina
// ja llegeix per al punt vermell. El títol i què cal fer; la resta, a la fitxa.
let HISTORIAL_PERILL = null;
const NIVELL_RIERA = { perill: 'vermell', atencio: 'taronja' };

function blocRiera(historial, ara = new Date()) {
  return (historial || []).filter((e) => e.tipus === 'riera' && !e.fi && !(e.fins && new Date(e.fins) <= ara))
    .map((e) => {
      const text = e[IDIOMA.codi === 'es' ? 'es' : 'ca'] || e.ca;
      const titol = trossos(text)[0].map((t) => t.t).join('').replace(/^\S+\s/, '').trim();
      const item = element('p', `avis-item ${NIVELL_RIERA[e.nivell] || 'vermell'}`);
      item.append(element('strong', null, titol), '. ', T('No t’acostis a la riera.'));
      item.dataset.clau = `riera:${e.clau}:${e.nivell}`;
      item.dataset.curt = `${titol}. ${T('No t’acostis a la riera.')}`;
      item.dataset.detall = `perill.html#${idFitxa(e)}`;
      return item;
    });
}

function blocLlum(llum, ara = new Date()) {
  return ((llum && llum.talls) || []).map((t) => {
    const [titol, frase] = textTall(t, ara);
    const item = element('p', 'avis-item compte');
    item.append(element('strong', null, titol), `: ${frase}`);
    item.dataset.clau = `llum:${t.id || t.inici}:${t.on}`;
    item.dataset.curt = `${titol}: ${t.programat ? T('treballs programats') : T('avaria')}.`;
    return item;
  });
}

// L'enllaç per activar els avisos, a cada apartat que en té un de configurable
// (Juanjo, 11-10-2026: «todos los avisos que tengan una alerta configurable
// (como la luz) deben tener un enlace, como ya has hecho con la pestaña
// peligros»; ADR 0072). Com a «Perill»: «…, activa els avisos.»
function enllacAvisos(davant) {
  const p = element('p', 'enllac-avisos');
  const a = element('a', null, T('activa les notificacions'));
  a.href = 'avisos.html';
  p.append(davant, a, '.');
  return p;
}

// Els noms curts de cada risc que calcula la pàgina (riscos.py), per a la
// taula per hores de «El temps» i per al bloc «Avisos actius» plegat.
const NOM_RISC = () => ({ pluja_30min: T('pluja intensa'), pluja_3h: T('pluja intensa'), pluja_24h: T('molta pluja'),
  ratxa: T('vent fort'), calor: T('calor intensa'), fred: T('fred intens'), neu_24h: T('neu') });

// El temps extrem que calcula la pàgina: situacions de perill segons el que mesuren les estacions i el que preveu
// la pàgina (riscos.py, ADR 0018), amb el color del nivell de l'AEMET.
// La xifra d'un risc com la diu el text (riscos.num): sense decimals, les
// meitats cap amunt; la temperatura i la neu, amb un si no és enter. Abans, la
// línia curta deia «vent fort (92,5 km/h)» i el text «92» (revisor, 19-10-2026).
function numRisc(r) {
  const v = Number(r.valor);
  const ambDecimal = ['calor', 'fred', 'neu_24h'].includes(r.tipus) && Math.abs(v - Math.round(v)) >= 0.05;
  return (ambDecimal ? v.toFixed(1) : v.toFixed(0)).replace('.', ',').replace('-', '\u2212');
}

function blocRiscos(riscos) {
  if (!riscos || !riscos.length) return null;
  const pitjor = riscos[0].nivell;
  const caixa = element('section', `avis risc-previst ${pitjor}`);
  caixa.setAttribute('aria-label', T('Risc previst'));
  caixa.dataset.detall = fitxaPerill((h) => h.clau === 'propi');
  caixa.dataset.clau = 'risc:' + riscos.map((r) => `${r.clau}:${r.nivell}`).join(',');
  // Qui avisa, primer (Juanjo, 17-10-2026).
  caixa.dataset.curt = T`Temps a Montflorit: risc ${TD(pitjor)} (no oficial)` + ': '
    + riscos.map((r) => `${NOM_RISC()[r.tipus] || r.tipus} (${numRisc(r)} ${r.unitat})`).join(', ') + '.';
  const titol = element('p', 'titol-risc');
  titol.append(icona('i-triangle-alert'), T`Temps a Montflorit: risc ${TD(pitjor)}`);
  caixa.append(titol);
  const llista = element('ul');
  for (const r of riscos) {
    // El text ve fet en català a les dades; en un altre idioma es torna a fer.
    const li = element('li', null, IDIOMA.risc ? IDIOMA.risc(r) : r.text);
    const llindar = coma(r.llindar, 0).replace('-', '\u2212');
    li.append(' ', element('span', 'detall', T`(llindar ${TD(r.nivell)} de Meteocat: ${llindar} ${r.unitat})`));
    llista.append(li);
  }
  caixa.append(llista);
  return caixa;
}

// Totes les alertes de perill, juntes i en el mateix ordre a cada pàgina
// (Juanjo, 16-10-2026: «las alertas de peligro deben ir siempre juntas»; ADR
// 0093): Protecció Civil, Meteocat, l'AEMET del que
// Meteocat no cobreix, la riera, els incendis i el Pla Alfa i el temps extrem
// d'aquesta web. tests/test_perills.py comprova que no en falta cap.
function avisosAemet(dades) {
  // Dels que Meteocat cobreix en part, només les hores que no cobreix (smp.visible).
  return (dades.avisos || []).filter((a) => !a.cobert)
    .map((a) => ({ ...a, inicio: a.inicio_visible || a.inicio, fin: a.fin_visible || a.fin }));
}

// «Avisos actius» de la portada: només les línies curtes; cadascuna porta a
// la fitxa del seu avís (Juanjo, 17-10-2026: «quita lo de desplegar, que
// muestre la información como sale ahora plegado y al pulsar lleva al detalle
// del aviso, es para simplificar la pagina inicial»). I plegades sota el
// títol, amb el nombre d'avisos (ADR 0094); des del 20-10-2026, sempre, amb
// un punt vermell si n'hi ha de nous. Fins a la 3.148.0, «Si surts» en mostrava els
// textos sencers; ara hi surt una sola línia que remet a «Perill» (sortir.js,
// liniaAvisosConduccio).
function blocAvisos(dades, { ara = new Date() } = {}) {
  const aemet = avisosAemet(dades);
  const perills = [...blocPlans(dades.plans), ...blocSmp(dades.smp),
    ...(aemet.length ? blocAvisosAemet(aemet, ara) : []),
    ...blocRiera(HISTORIAL_PERILL, ara), ...blocEntorn(dades.entorn), blocRiscos(dades.riscos)].filter(Boolean);
  const talls = blocLlum(dades.llum, ara);
  if (!perills.length && !talls.length) return null;
  const hrefDe = (i) => (i.dataset && i.dataset.detall) || 'perill.html';
  const curts = curtsAvisos(perills, talls, dades.smp, hrefDe, ara);
  const empremta = curts.map((c) => c.dataset.clau).sort().join('\n');
  const sec = element('section', 'avisos-actius');
  sec.setAttribute('aria-label', T('Avisos actius'));
  const plec = element('details', 'avisos-plec');
  const resum = element('summary');
  resum.append(element('h2', 'seccio', T`Avisos actius (${curts.length})`));
  const llista = element('div', 'avisos-curts');
  llista.append(...curts);
  plec.append(resum, llista);
  // Sempre plegat, també amb un de nou o de vermell: un punt vermell diu que hi
  // ha novetats (el de la pestanya «Avisos») i la franja, del color del més
  // greu, quant importa; així la gràfica cap a la pantalla del mòbil (Juanjo,
  // 20-10-2026: «los avisos activos siempre plegados, solo cuando hay uno nuevo
  // aparecerá un punto rojo»). Fins a la 3.163.0 es desplegava sol.
  const pitjor = NIVELLS_AVIS.find((n) => curts.some((c) => nivellDe(c) === n));
  if (pitjor) sec.classList.add(`nivell-${pitjor}`);
  const nou = curts.some((c) => c.querySelector('.avis-nou'));
  if (nou) {
    const punt = element('span', 'punt-perill');
    punt.setAttribute('role', 'img');
    punt.setAttribute('aria-label', T('Hi ha un avís nou'));
    punt.title = T('Hi ha un avís nou');
    resum.append(punt);
  }
  plec.open = Boolean(PLEC_AVISOS && PLEC_AVISOS.empremta === empremta && PLEC_AVISOS.obert);
  plec.addEventListener('toggle', () => {
    PLEC_AVISOS = { empremta, obert: plec.open };
    if (plec.open) resum.querySelector('.punt-perill')?.remove();
  });
  sec.append(plec);
  return sec;
}

// Com l'ha deixat la persona en aquesta pàgina, mentre els avisos no canviïn.
let PLEC_AVISOS = null;   // {empremta, obert}

const NIVELLS_AVIS = ['vermell', 'taronja', 'groc', 'prealerta', 'compte'];
function nivellDe(item) {
  return (item.className || '').split(' ').find((c) => NIVELLS_AVIS.includes(c)) || '';
}

// Les línies curtes, en el mateix ordre que les senceres: els plans, Meteocat
// per fenomen (sempre a la seva fitxa de «Perill», encara que desplegat vagi
// dins del pla; Juanjo, 16-10-2026: «si pulso sobre meteocat me lleva a
// protección civil»), i la resta amb el text curt que cada bloc ha deixat a «curt».
function curtsAvisos(perills, talls, smp, hrefDe, ara) {
  const curts = [];
  let smpFet = false;
  const posaSmp = () => {
    if (smpFet) return;
    smpFet = true;
    curts.push(...curtsSmp(smp, fitxaPerill((h) => h.clau.startsWith('meteocat:')), ara));
  };
  for (const i of perills) {
    if (i.dataset.tipus === 'smp') { posaSmp(); continue; }
    if (i.dataset.tipus !== 'pla') posaSmp();
    const p = element('p', `avis-item curt ${nivellDe(i)}`, i.dataset.curt || i.textContent);
    p.dataset.clau = i.dataset.clau || i.textContent;
    curts.push(ambDetall(p, hrefDe(i)));
  }
  posaSmp();
  for (const i of talls) {
    const p = element('p', 'avis-item curt compte', i.dataset.curt || i.textContent);
    p.dataset.clau = i.dataset.clau || i.textContent;
    curts.push(ambDetall(p, 'consultes.html#llum'));
  }
  const desDe = new Map(perills.filter((i) => i.dataset.desDe).map((i) => [hrefDe(i), i.dataset.desDe]));
  marcaPublicacio(curts, desDe, ara);
  return curts;
}

// Quan es va publicar cada avís i, si s'ha actualitzat, quan (Juanjo,
// 17-10-2026: «la fecha y hora de publicación del aviso y si tiene
// actualizacion se sustituye por esta, asi se sabe si la hemos visto antes o
// no»), al costat del text, en un tros que no es parteix: si no hi cap, passa
// a la línia de sota. L'hora és la de l'historial de «Perill», la mateixa dels
// avisos al mòbil i a Telegram; la d'un pla, també la del seu comunicat més
// recent. I «Nou» als que aquest dispositiu encara no havia mostrat.
const CLAU_AVISOS_LLEGITS = 'meteo.avisos-llegits';
let LLEGITS_ABANS = null;     // els que ja s'havien mostrat en obrir la pàgina

function episodiDe(href) {
  const id = (href || '').split('#')[1];
  return id ? (HISTORIAL_PERILL || []).find((e) => e.clau && idFitxa(e) === id) : null;
}

// L'hora del comunicat d'un pla, del nom del PDF: «…_202610171110.pdf», en
// hora de Madrid.
function horaComunicat(url) {
  const m = /_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})\.pdf$/.exec(url || '');
  return m ? deRellotge(+m[1], +m[2], +m[3], +m[4], +m[5]) : null;
}

function publicacioEpisodi(e) {
  let hora = new Date(e.darrer || e.inici);
  const comunicat = e.clau.startsWith('pla:') && horaComunicat(e.comunicat);
  if (comunicat && comunicat > hora) hora = comunicat;
  return { hora, actualitzat: hora > new Date(e.inici) };
}

function diaPassat(data, ara) {
  const dies = diesEntre(data, ara);
  if (dies === 0) return T('avui');
  if (dies === 1) return T('ahir');
  const nom = llegeixHora(data).toLocaleDateString(IDIOMA.codi, { weekday: 'long', timeZone: ZONA_HORA });
  return dies < 7 ? nom : `${nom} ${partsHora(data).dia}`;
}

function textPublicacio(pub, ara = new Date()) {
  const [dia, hora] = [diaPassat(pub.hora, ara), horaCurta(pub.hora)];
  return pub.actualitzat ? T`actualitzat ${dia} ${hora}` : T`publicat ${dia} ${hora}`;
}

function llegeixLlegits() {
  try { return JSON.parse(localStorage.getItem(CLAU_AVISOS_LLEGITS) || '[]'); } catch (e) { return []; }
}

function marcaPublicacio(curts, desDe, ara) {
  // Sense l'historial encara no se sap l'hora: ni «Nou» ni es recorda res.
  const ambHistorial = Array.isArray(HISTORIAL_PERILL);
  if (ambHistorial && !LLEGITS_ABANS) LLEGITS_ABANS = new Set(llegeixLlegits());
  const ara_ = [];
  for (const c of curts) {
    const href = c.dataset.href;
    const e = episodiDe(href);
    const pub = e ? publicacioEpisodi(e) : desDe.has(href) ? { hora: new Date(desDe.get(href)), actualitzat: false } : null;
    if (pub) c.insertBefore(element('span', 'publicat', ` · ${textPublicacio(pub, ara)}`), c.querySelector('a.detall'));
    if (!ambHistorial) continue;
    const clau = `${c.dataset.clau}|${pub ? pub.hora.toISOString() : ''}`;
    ara_.push(clau);
    c.dataset.llegit = clau;
    if (!LLEGITS_ABANS.has(clau)) {
      const nou = element('span', 'avis-nou', T('Nou'));
      c.insertBefore(nou, c.firstChild);
      // En pulsar-lo ja s'ha vist: fora el «Nou», també a les repintades
      // d'aquesta visita (Juanjo, 19-10-2026: «cuando pulso en un aviso que
      // tiene la etiqueta nou, debe desaparecer el nou»).
      const a = c.querySelector('a.detall');
      if (a) a.addEventListener('click', () => { nou.remove(); LLEGITS_ABANS.add(clau); });
    }
  }
  if (ambHistorial) {
    try { localStorage.setItem(CLAU_AVISOS_LLEGITS, JSON.stringify(ara_)); } catch (e) { /* sense memòria, sempre «Nou» */ }
  }
}

// Les línies del resum del dia (a «El temps» i a «Consultes») amb un detall
// al darrere (ADR 0075): els trens, a «Consultes › Trens»; totes les alertes
// de perill (ADR 0093), a «Perill».
// Les alertes, a la seva fitxa (fitxaDeLinia).
function detallLinia(text) {
  const t = text.trim();
  if (/^(Trens|Trenes) /.test(t)) return 'consultes.html#trens';
  return LINIA_PERILL.test(t) ? fitxaDeLinia(t) : null;
}

function ambDetalls(files) {
  return files.map((f) => {
    const href = detallLinia(f.textContent || '');
    return href ? ambDetall(f, href) : f;
  });
}

// Cada línia amb un detall al darrere porta «›» a la dreta i es pot tocar
// sencera (Juanjo, 12-10-2026: «que hay que hacer si alguien quiere saber
// cuales son? se aplica lo mismo para cualquier alerta»; ADR 0075). Sempre a
// una pàgina d'aquesta web: els perills, a «Perill»; els talls i els trens, a
// «Consultes». L'enllaç cobreix tota la línia, per sota del text; la «›» la
// dibuixa l'estil, i el «?» dels plans queda per sobre.
function ambDetall(item, href) {
  item.classList.add('amb-detall');
  item.dataset.href = href;
  const a = element('a', 'detall');
  a.href = href;
  const nom = ((item.querySelector && item.querySelector('strong')) || item).textContent || '';
  a.setAttribute('aria-label', T`Detall: ${nom.trim().replace(/[.:]$/, '').slice(0, 90)}`);
  item.append(a);
  return item;
}

// Destaca on porta un enllaç (la fitxa de «Perill», el plec de «Si surts», la
// consulta): s'hi va i, quan la pàgina ja és quieta, parpelleja dues vegades
// (2 s), queda marcada 2 s i s'apaga en 1,2 s (estil.css, .assenyalat; Juanjo,
// 16-10-2026: «que empiece cuando esté quieta» i «en vez de 3 parpadeos, haz 2»).
const ASSENYALAT_MS = 4000;     // els parpelleigs i el temps marcada
const QUIETA_MS = 150;          // sense desplaçar-se tant de temps, és quieta
const QUIETA_MAX_MS = 2000;     // per si el desplaçament no s'acaba mai
function assenyala(el) {
  if (!el) return;
  const suau = !matchMedia('(prefers-reduced-motion: reduce)').matches;
  el.classList.add('assenyalable');
  el.classList.remove('assenyalat');
  clearTimeout(el.assenyalat);
  let fet = false;
  let espera = null;
  const comença = () => {
    if (fet) return;
    fet = true;
    clearTimeout(espera);
    clearTimeout(maxim);
    removeEventListener('scroll', quieta);
    void el.offsetWidth;        // perquè l'animació torni a començar
    el.classList.add('assenyalat');
    el.assenyalat = setTimeout(() => el.classList.remove('assenyalat'), ASSENYALAT_MS);
  };
  const quieta = () => { clearTimeout(espera); espera = setTimeout(comença, QUIETA_MS); };
  const maxim = setTimeout(comença, QUIETA_MAX_MS);
  addEventListener('scroll', quieta, { passive: true });
  el.scrollIntoView({ block: 'center', behavior: suau ? 'smooth' : 'auto' });
  quieta();
}

function posaVersio(versio) {
  $('versio').textContent = T`versió ${versio}`;
  // La pàgina pública enllaça el seu propi repositori (ADR 0024).
  $('versio').href = document.documentElement.dataset.notes
    || 'https://github.com/meteo-montflorit/meteo-local/releases/tag/v' + versio;
}

// --- Trens i trànsit (ADR 0029 i 0052): les fitxes que fan servir «Si surts» i
// «Consultes» (ADR 0054). ---

const TEXT_ESTAT = {
  circula: 'Sense incidències', incidencies: 'Amb incidències', retard: 'Amb retard', bus: 'Servei per carretera',
  sense_trens: 'Sense trens', fora_horari: 'Fora d’horari', sense_dades: 'Sense dades',
};
// On publica cada operador l'estat del servei: Rodalies, a la portada; FGC
// remet a la seva compte d'X; dels busos, la mobilitat de l'AMB.
const ESTAT_OPERADOR = {
  rodalies: { text: () => 'Rodalies', href: () => `https://rodalies.gencat.cat/${IDIOMA.codi === 'es' ? 'es' : 'ca'}/inici/` },
  fgc: { text: () => 'FGC', href: () => 'https://x.com/fgc' },
  amb: { text: () => T('Busos de l’AMB'), href: () => `https://www.amb.cat/${IDIOMA.codi === 'es' ? 'es/' : ''}web/mobilitat` },
};
const COLOR_ESTAT = {
  circula: 'be', incidencies: 'compte', retard: 'compte', bus: 'compte', sense_trens: 'no', fora_horari: 'neutre',
  sense_dades: 'neutre',
};

// Trànsit (config.TRANSIT_NIVELL_SORTIDA): des d'aquest nivell (3, retencions;
// 4, congestió; 5, calçada tallada), si surts ara, el cotxe i la moto passen a
// «compte». La circulació intensa (2) només es llista (ADR 0052).
const NIVELL_TRANSIT = 3;

function enllacExtern(text, href) {
  const a = element('a', null, text);
  a.href = href;
  a.target = '_blank';
  a.rel = 'noopener';
  return a;
}

// Els busos urbans de l'AMB que passen pel barri (CV1, CV4 i CV5; proposta,
// 22-10-2026). «Si surts» només en diu les incidències i porta a «Consultes»,
// on cada línia té les hores d'arribada a cada parada i els PDF de l'AMB amb
// el recorregut i l'horari (Juanjo, 22-10-2026: «en la sección de salir solo
// pondría las incidencias»). L'hora ja porta sumat el retard del temps real
// de l'AMB quan n'hi ha: la gent només vol saber a quina hora arriba el bus.

// «divendres 23».
function diaBus(d) {
  return `${d.toLocaleDateString(IDIOMA.codi, { weekday: 'long', timeZone: ZONA_HORA })} ${partsHora(d).dia}`;
}

function incidenciesBusos(busos, quan, linia) {
  return (busos.incidencies || []).filter((inc) => (!linia || inc.linies.includes(linia))
    && (!inc.fi || new Date(inc.fi) >= quan) && (linia || !inc.inici || new Date(inc.inici) <= quan));
}

// «CV1: Desviament provisional… (enllaç a l'avís de l'AMB), fins al divendres 23.»
function liniaIncidenciaBus(inc, des, ambLinia) {
  const idioma = IDIOMA.codi === 'es' ? 'es' : 'ca';
  const p = element('p', 'bus-incidencia');
  p.append(icona('i-triangle-alert'));
  const text = element('span');
  p.append(text);
  if (ambLinia) text.append(element('strong', null, inc.linies.join(', ')), ': ');
  const titol = inc.titol[idioma] || inc.titol.ca;
  const url = (inc.url || {})[idioma] || (inc.url || {}).ca;
  text.append(url ? enllacExtern(titol, url) : titol);
  const [inici, fi] = [inc.inici && new Date(inc.inici), inc.fi && new Date(inc.fi)];
  if (inici && inici > des) {
    text.append(mateixDia(inici, des) ? T`, a partir de les ${horaCurta(inici)}.` : T`, a partir del ${diaBus(inici)} a les ${horaCurta(inici)}.`);
  } else if (fi) text.append(mateixDia(fi, des) ? T`, fins a les ${horaCurta(fi)}.` : T`, fins al ${diaBus(fi)}.`);
  else text.append('.');
  return p;
}

// Per a «Si surts»: les incidències de l'hora triada i l'enllaç als horaris.
function liniesBusosSortida(busos, quan) {
  const incs = incidenciesBusos(busos, quan);
  const parts = incs.length ? incs.map((inc) => liniaIncidenciaBus(inc, quan, true))
    : [element('p', 'mitja-motiu', T('Cap incidència a les línies del barri.'))];
  const p = element('p', 'mitja-roba');
  const a = element('a', null, T('Horaris dels busos'));
  a.href = 'consultes.html#busos';
  p.append(a);
  if (busos.prova) parts.unshift(element('p', 'bus-prova', busos.prova));
  return [...parts, p];
}

// Les hores d'una parada: les de les 2 hores següents (com a molt 2) o, si no
// n'hi ha cap, la propera, amb el dia si no és avui.
function horesParada(hores, des) {
  const futures = hores.filter((h) => new Date(h) >= des);
  const limit = des.getTime() + 2 * 3600e3;
  const properes = futures.filter((h) => new Date(h).getTime() <= limit).slice(0, 2);
  if (properes.length) return properes.map(horaCurta).join(T(' i '));
  if (!futures.length) return '—';
  const d = new Date(futures[0]);
  return mateixDia(d, des) ? horaCurta(d) : T`${diaBus(d)} a les ${horaCurta(d)}`;
}

// Per a «Consultes»: cada línia amb les seves incidències, cada sentit amb les
// parades del barri i, al peu, el recorregut i l'horari de l'AMB.
function blocBusos(busos, des) {
  const parts = [];
  if (busos.prova) parts.push(element('p', 'bus-prova', busos.prova));
  // Cada línia, plegada: es mira la que interessa (Juanjo, 22-10-2026). Si
  // té incidències, el títol ho avisa amb la icona.
  for (const l of busos.linies || []) {
    const targeta = element('details', 'bus-targeta');
    const resum = element('summary');
    const cap = element('h2', 'bus-linia');
    cap.append(element('span', 'bus-xip', l.linia), ' ', l.nom);
    const incidencies = incidenciesBusos(busos, des, l.linia);
    if (incidencies.length) {
      const avis = element('span', 'bus-avis');
      avis.append(icona('i-triangle-alert'));
      avis.title = T('Amb incidències');
      avis.setAttribute('role', 'img');
      avis.setAttribute('aria-label', avis.title);
      cap.append(avis);
    }
    resum.append(cap);
    targeta.append(resum, ...incidencies.map((inc) => liniaIncidenciaBus(inc, des, false)));
    for (const s of l.sentits) {
      targeta.append(element('h3', 'bus-sentit', T`Cap a ${s.cap_a}`));
      const taula = element('dl', 'busos');
      for (const p of s.parades) taula.append(element('dt', null, TD(p.parada)), element('dd', null, horesParada(p.hores, des)));
      targeta.append(taula);
    }
    const enllacos = element('p', 'bus-enllacos');
    if (l.mapa) enllacos.append(enllacExtern(T('Mapa del recorregut (PDF)'), l.mapa));
    if (l.mapa && l.horari) enllacos.append(' · ');
    if (l.horari) enllacos.append(enllacExtern(T('Horari complet (PDF)'), l.horari));
    targeta.append(enllacos);
    parts.push(targeta);
  }
  // Sense el temps real, les hores són les de l'horari: es diu (busos.py).
  parts.push(element('p', 'bus-nota', busos.temps_real_de
    ? T`Hora d’arribada estimada, amb dades de l’AMB de les ${horaCurta(busos.temps_real_de)}.`
    : T('Hores de l’horari de l’AMB: ara no arriben les del temps real.')));
  return parts;
}

// L'estat de cada línia de tren, per al plec del transport públic.
function blocTrens(trens) {
  const llista = element('ul', 'llista-trens');
  for (const l of trens.linies) {
    const li = element('li', 'tren ' + COLOR_ESTAT[l.estat]);
    const cap = element('p', 'tren-cap');
    cap.append(element('span', 'tren-linia', l.linia), ' ', element('span', 'tren-estacio', TD(l.estacio)),
      ' ', element('span', 'tren-estat', TD(TEXT_ESTAT[l.estat])));
    li.append(cap);
    // L'avís oficial diu que hi ha trens, però no se n'ha vist cap (trens.py).
    if (l.no_vist) {
      li.append(element('p', 'tren-nota', l.operador === 'fgc'
        ? T('FGC diu que hi ha circulació, però a l’última hora no s’ha vist cap tren a prop de l’estació.')
        : T('Rodalies diu que hi ha circulació ferroviària, però a l’última hora no s’ha vist cap tren a prop de l’estació.')));
    }
    // Amb retard: quants trens han passat tard (trens.py, ADR 0079).
    if (l.estat === 'retard' && l.trens_tard) {
      li.append(element('p', 'tren-nota', l.trens_tard === 1 ? T('1 tren ha passat amb retard a la darrera mitja hora.')
        : T`${l.trens_tard} trens han passat amb retard a la darrera mitja hora.`));
    }
    // Els avisos, tal com els publica l'operador: no es tradueixen.
    const textos = (l.avisos || []).map((a) => (IDIOMA.codi === 'es' ? a.es : a.ca) || a.ca || a.es);
    if (textos.length) {
      const plecAvisos = element('details', 'tren-avisos');
      plecAvisos.append(element('summary', null, l.operador === 'fgc' ? T('Avís d’FGC') : T('Avís de Rodalies')));
      for (const t of textos) plecAvisos.append(element('p', null, t));
      li.append(plecAvisos);
    }
    llista.append(li);
  }
  // On publiquen els operadors l'estat del servei.
  const estat = element('p', 'nota');
  estat.append(T('Estat del servei: '));
  Object.values(ESTAT_OPERADOR).forEach((e, n) => estat.append(...(n ? [' · '] : []), enllacExtern(e.text(), e.href())));
  return [llista, estat, element('p', 'nota',
    T`Dades de Rodalies, Renfe i FGC de les ${horaCurta(trens.hora)}, consultades automàticament: l’autor no es fa responsable de la seva exactitud.`)];
}

// Les incidències de trànsit de prop (ADR 0052), tal com les publica el Servei
// Català de Trànsit, en català: no es tradueixen. Es veuen si es mira el cotxe
// o la moto.
const COLOR_TRANSIT = (nivell) => (nivell >= 5 ? 'no' : nivell >= NIVELL_TRANSIT ? 'compte' : 'neutre');
const ESTAT_TRANSIT = () => `https://transit.gencat.cat/${IDIOMA.codi === 'es' ? 'es' : 'ca'}/informacio-viaria/estat-transit/`;

// Sense hora per incidència: la del fitxer és la de l'última actualització, no
// la de l'inici, i semblava que no estigués al dia. El que surt és el que el
// Servei Català de Trànsit dona com a vigent a l'hora de la consulta, que es
// diu a sota (Juanjo, 09-10-2026; ADR 0052).
// La distància en línia recta fins al punt que dona la font per al tram: en
// metres (de 50 en 50) per sota d'1 km; si no, en km amb un decimal.
function distancia(km) {
  if (km == null) return null;
  if (km < 1) return `${Math.max(50, Math.round(km * 20) * 50)}\u00a0m`;
  const x = Math.round(km * 10) / 10;
  return `${Number.isInteger(x) ? x : coma(x)}\u00a0km`;
}

function filaTransit(i) {
  const li = element('li', 'tren ' + COLOR_TRANSIT(i.nivell));
  const cap = element('p', 'tren-cap');
  cap.append(element('span', 'tren-linia', i.carretera));
  const lloc = [i.municipi, i.km != null && T`a ${distancia(i.km)}`].filter(Boolean).join(', ');
  if (lloc) cap.append(' ', element('span', 'tren-estacio', lloc));
  cap.append(' ', element('span', 'tren-estat', i.descripcio || ''));
  // «Circulació» com a causa no diu res que no digui ja l'estat.
  const causa = i.tipus === 'obres' ? T`Obres: ${i.causa}` : i.causa !== 'Circulació' && i.causa;
  const detall = [causa, i.sentit, i.pk && T`km ${i.pk}`].filter(Boolean);
  li.append(cap, element('p', 'transit-detall', detall.join(' · ')));
  return li;
}

// Les incidències de trànsit de prop, per al plec del cotxe i de la moto.
function blocTransit(transit) {
  const llista = element('ul', 'llista-trens');
  for (const i of transit.incidencies) llista.append(filaTransit(i));
  const estat = element('p', 'nota');
  estat.append(T('Estat del trànsit: '), enllacExtern('Servei Català de Trànsit', ESTAT_TRANSIT()));
  return [llista, estat, element('p', 'nota',
    T`Dades del Servei Català de Trànsit de les ${horaCurta(transit.hora)}, consultades automàticament: l’autor no es fa responsable de la seva exactitud.`)];
}

// Tema: segueix el del dispositiu mentre no se'n triï un altre; si es tria
// el mateix que el del dispositiu, es torna a seguir-lo (com a Sirena).
const sistemaFosc = matchMedia('(prefers-color-scheme: dark)');

function aplicaFosc(fosc, manual) {
  document.documentElement.dataset.theme = fosc ? 'dark' : 'light';
  if (manual) {
    try {
      if (fosc === sistemaFosc.matches) localStorage.removeItem('meteo.fosc');
      else localStorage.setItem('meteo.fosc', fosc ? '1' : '0');
    } catch (_) {}
  }
  $('btn-fosc').querySelector('use').setAttribute('href', fosc ? '#i-sun' : '#i-moon');
}

function segueixSistema() {
  try { return localStorage.getItem('meteo.fosc') === null; } catch (_) { return true; }
}

aplicaFosc(document.documentElement.dataset.theme === 'dark', false);
$('btn-fosc').addEventListener('click', () => {
  aplicaFosc(document.documentElement.dataset.theme !== 'dark', true);
});
sistemaFosc.addEventListener('change', (e) => {
  if (segueixSistema()) aplicaFosc(e.matches, false);
});

// Visor d'imatges: a l'ordinador, una imatge enllaçada amb la classe «amplia»
// s'obre a sobre de la pàgina, tan gran com hi càpiga, amb una X per tancar
// (també Esc o un clic fora). Al mòbil s'obre sola, on es pot ampliar
// amb els dits (Juanjo, 07-10-2026).
const pantallaGran = matchMedia('(min-width: 900px) and (pointer: fine)');

function obreVisor(enllac) {
  const visor = element('dialog', 'visor');
  const imatge = element('img');
  imatge.src = enllac.href;
  imatge.alt = enllac.querySelector('img')?.alt || '';
  // Tancar: la X de sempre, a dalt a la dreta (icona «x» de Lucide).
  const tanca = element('button', 'visor-tanca');
  tanca.type = 'button';
  tanca.title = T('Tanca');
  tanca.setAttribute('aria-label', T('Tanca'));
  tanca.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  tanca.addEventListener('click', () => visor.close());
  visor.append(imatge, tanca);
  visor.setAttribute('aria-label', imatge.alt);
  visor.addEventListener('click', (e) => { if (e.target === visor) visor.close(); });
  visor.addEventListener('close', () => visor.remove());
  document.body.append(visor);
  visor.showModal();
  tanca.focus();
}

document.addEventListener('click', (e) => {
  const enllac = e.target.closest('a.amplia');
  if (!enllac || !pantallaGran.matches || e.ctrlKey || e.metaKey || e.shiftKey) return;
  e.preventDefault();
  obreVisor(enllac);
});

// Els missatges del bot (a «Consultes» i a «Perill») porten l'HTML de Telegram: <b>, <i> i <a href="…">, amb la
// resta escapat. Es parteix en línies de trossos {t, b, i, href} i es pinta
// amb elements, sense innerHTML: el que no sigui això surt com a text.
const ENTITATS = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#39;': "'" };
const desescapa = (t) => t.replace(/&(amp|lt|gt|quot|#x27|#39);/g, (e) => ENTITATS[e]);
const ADRECA = /(https:\/\/[^\s<]+[^\s<.,;:)»])/;

function trossos(text) {
  const linies = [];
  let linia = [];
  let b = false;
  let i = false;
  let href = null;
  const afegeix = (t) => {
    const parts = t.split('\n');
    parts.forEach((part, n) => {
      if (n > 0) { linies.push(linia); linia = []; }
      // Les adreces soltes (el radar en directe), també enllaçades.
      for (const tros of desescapa(part).split(ADRECA)) {
        if (!tros) continue;
        const esAdreca = !href && ADRECA.test(tros) && tros.match(ADRECA)[0] === tros;
        linia.push({ t: tros, b, i, href: esAdreca ? tros : href });
      }
    });
  };
  const etiqueta = /<(\/?)(b|i)>|<a href="([^"]*)">|<\/a>/g;
  let pos = 0;
  for (const m of text.matchAll(etiqueta)) {
    afegeix(text.slice(pos, m.index));
    pos = m.index + m[0].length;
    if (m[2] === 'b') b = !m[1];
    else if (m[2] === 'i') i = !m[1];
    else if (m[3] !== undefined) href = /^https:\/\//.test(desescapa(m[3])) ? desescapa(m[3]) : null;
    else href = null;
  }
  afegeix(text.slice(pos));
  linies.push(linia);
  return linies;
}

// Els trossos d'una línia, com a elements.
function nodesLinia(linia) {
  return linia.map((tros) => {
    let node = document.createTextNode(tros.t);
    if (tros.href) {
      const a = element('a');
      a.href = tros.href;
      a.target = '_blank';
      a.rel = 'noopener';
      a.append(node);
      node = a;
    }
    if (tros.i) { const em = element('em'); em.append(node); node = em; }
    if (tros.b) { const st = element('strong'); st.append(node); node = st; }
    return node;
  });
}

// --- Avui i demà: el text del bot, a «Consultes» i a «El temps» (ADR 0074).
// Les icones, només les que porta el text (ADR 0065): el bot hi posa emojis i, per a la web, marques («⟦i-sun⟧»,
// «⟦alt⟧») que aquí es dibuixen amb les icones de colors de la web. La que
// obre la línia va a la columna de les icones; les altres línies hi porten la
// del seu tema. ---
const MARCA = /⟦([a-z-]+)⟧ ?/;
// La part alta del barri, «(fins a 26 °C a la part alta)», en l'etiqueta de
// color préssec de la previsió (ADR 0087; Juanjo, 13-10-2026).
const ALTA = / ?\(((?:fins a|hasta) [^()]*? (?:a la part alta|en la parte alta))\)/;
const NOM_CEL = () => ({
  'i-sun': T('Serè'), 'i-moon-cel': T('Serè'), 'i-cloud-sun': T('Poc ennuvolat'), 'i-cloud-moon': T('Poc ennuvolat'),
  'i-cloud': T('Mig ennuvolat'), 'i-cloudy': T('Molt ennuvolat'), 'i-cloudy-cobert': T('Cobert'), 'i-cloud-fog': T('Boira'),
  'i-cloud-sun-rain': T('Possible pluja'), 'i-cloud-moon-rain': T('Possible pluja'), 'i-cloud-drizzle': T('Pluja feble'),
  'i-cloud-rain': T('Pluja'), 'i-cloud-rain-wind': T('Pluja forta'), 'i-cloud-snow': T('Neu'),
  'i-cloud-lightning': T('Tempesta'), 'i-cloud-hail': T('Tempesta amb calamarsa'), 'i-umbrella': T('Plou ara'),
});
const NIVELLS_MARCA = ['nul', 'baix', 'mig', 'alt', 'maxim', 'extrem'];
// Les línies sense marca també en porten una, perquè la columna no quedi amb
// forats (Juanjo, 10-10-2026: «haría falta 1 icono por línea»): sense pluja,
// el paraigua tancat; la resta, la del tema, en gris.
const ICONA_LINIA = [
  [/^(Sense pluja|Sin lluvia)/, 'i-umbrella-off'],
  [/^Temperatura/, 'i-thermometer'],
  [/^(Trens|Trenes)/, 'i-train-front'],
  [/^(Roba|Ropa)/, 'i-shirt'],
];

// Una marca, com a element: el cel, amb la icona i el seu nom per a qui no la
// veu; el nivell, un cercle del seu color (el text ja diu quin és).
function nodeMarca(clau) {
  if (NIVELLS_MARCA.includes(clau)) {
    const punt = element('span', 'punt-nivell punt-' + clau);
    punt.setAttribute('aria-hidden', 'true');
    return punt;
  }
  const nom = NOM_CEL()[clau];
  const s = element('span', 'icona-cel');
  s.append(icona(clau));
  if (nom) {
    s.setAttribute('role', 'img');
    s.setAttribute('aria-label', nom);
    s.title = nom;
  }
  return s;
}

// Els trossos d'una línia amb les marques separades: [{marca}] o el tros.
function ambMarques(linia) {
  const res = [];
  for (const tros of linia) {
    tros.t.split(MARCA).forEach((part, n) => {
      if (n % 2) res.push({ marca: part });
      else if (part) {
        part.split(ALTA).forEach((p, m) => {
          if (m % 2) res.push({ alta: p });
          else if (p) res.push({ ...tros, t: p });
        });
      }
    });
  }
  return res;
}

function nodesAmbMarques(trossos) {
  const nodes = [];
  for (const tros of trossos) {
    if (tros.marca) nodes.push(nodeMarca(tros.marca));
    else if (tros.alta) nodes.push(' ', etiquetaAlta(tros.alta));
    else nodes.push(...nodesLinia([tros]));
  }
  return nodes;
}

// La part alta del barri (ADR 0087): l'etiqueta de color préssec es pot prémer
// i obre una bombolla amb què vol dir, que es tanca amb qualsevol clic o toc
// (Juanjo, 13-10-2026). Dins de la capçalera d'un tram, que ja es prem per
// desplegar-lo, és un «span» amb la descripció al «title»; a la resta, un botó.
const TEXT_ALTA = () => T('Les temperatures són les de vora la riera, la zona més freda del barri; a la part alta sol fer més calor, i aquesta etiqueta diu quants graus més.');
let BOMBOLLA = null;

// L'estat de la riera ara: el color i el títol, els mateixos a «Riera» i a la
// portada (casa.estatPortada).
const COLOR_NIVELL = { perill: 'vermell', atencio: 'taronja', registre: 'groc' };
function titolRiera(nivell) {
  return nivell === 'perill' ? T('Perill de desbordament.') : nivell === 'atencio' ? T('Atenció.')
    : nivell === 'registre' ? T('Plou a la conca.') : T('Sense risc de crescuda ara.');
}

// Amb «explica», la mateixa etiqueta per a una altra dada, amb la seva
// descripció (la comparació amb ahir d'«Ara», casa.comparaDia).
function etiquetaAlta(text, dinsDeTram = false, explica = null) {
  const el = element(dinsDeTram ? 'span' : 'button', 'alta');
  if (explica) el.dataset.explica = explica;
  if (dinsDeTram) el.title = explica || TEXT_ALTA();
  else {
    el.type = 'button';
    el.setAttribute('aria-expanded', 'false');
  }
  el.append(text);
  return el;
}

function tancaBombolla() {
  if (!BOMBOLLA) return;
  if (BOMBOLLA.etiqueta.tagName === 'BUTTON') {
    BOMBOLLA.etiqueta.removeAttribute('aria-describedby');
    BOMBOLLA.etiqueta.setAttribute('aria-expanded', 'false');
  }
  BOMBOLLA.el.remove();
  BOMBOLLA = null;
}

function obreBombolla(etiqueta, text = TEXT_ALTA()) {
  const b = element('div', 'bombolla-alta', text);
  b.id = 'bombolla-alta';
  b.setAttribute('role', 'tooltip');
  // Dins del contingut principal, i fixa a la pantalla: es tanca en desplaçar-se.
  // Dins d'una finestra (la gràfica en gran), a la finestra, que va per sobre.
  (etiqueta.closest('dialog') || document.querySelector('main') || document.body).append(b);
  // A sota de l'etiqueta i dins de la pantalla; si no hi cap (la barra de
  // pestanyes del mòbil, a baix), a sobre.
  const r = etiqueta.getBoundingClientRect();
  const marge = 8;
  const ample = document.documentElement.clientWidth;
  const x = Math.max(marge, Math.min(r.left + r.width / 2 - b.offsetWidth / 2, ample - b.offsetWidth - marge));
  let y = r.bottom + 6;
  if (y + b.offsetHeight > innerHeight - 90) y = r.top - b.offsetHeight - 6;
  b.style.left = `${x}px`;
  b.style.top = `${y}px`;
  if (etiqueta.tagName === 'BUTTON') {
    etiqueta.setAttribute('aria-describedby', b.id);
    etiqueta.setAttribute('aria-expanded', 'true');
  }
  BOMBOLLA = { el: b, etiqueta };
}

document.addEventListener('click', (e) => {
  // El toc que ha obert una descripció amb el dit no fa res més.
  if (TOC_LLARG) {
    TOC_LLARG = false;
    e.preventDefault();
    e.stopPropagation();
    return;
  }
  // La de la llegenda ja té l'explicació al costat.
  const etiqueta = e.target.closest && !e.target.closest('.llegenda') && e.target.closest('.alta');
  const jaOberta = BOMBOLLA && BOMBOLLA.etiqueta === etiqueta;
  tancaBombolla();
  if (!etiqueta) return;
  // Que no desplegui el tram.
  e.preventDefault();
  e.stopPropagation();
  if (!jaOberta) obreBombolla(etiqueta, etiqueta.dataset.explica || TEXT_ALTA());
}, true);
// Tocar qualsevol altre lloc la tanca, també on el clic no arriba (Safari
// de l'iPhone no envia «click» si es toca una cosa que no es pot prémer).
document.addEventListener('pointerdown', (e) => {
  if (BOMBOLLA && !(e.target.closest && e.target.closest('.alta'))) tancaBombolla();
}, true);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') tancaBombolla(); });
addEventListener('scroll', tancaBombolla, { passive: true });
addEventListener('resize', tancaBombolla);

// Què hi ha a cada pestanya, en passar-hi el ratolí o mantenint-hi el dit
// (Juanjo, 21-10-2026: «habría que poner descripciones por todo el programa»).
const DESCRIPCIO_PESTANYA = {
  temps: () => T('El temps al barri: ara, la previsió hora a hora i la gràfica.'),
  'perill.html': () => T('Els avisos de perill: els oficials, els incendis, la riera i el temps extrem.'),
  'riera.html': () => T('La riera de Sant Cugat: el risc de crescuda ara i en les properes hores.'),
  'sortir.html': () => T('Si has de sortir: com anirà cada mitjà de transport, què posar-te i els trens.'),
  'consultes.html': () => T('Fitxes per consultar: avui, demà, el sol, l’aire, el pol·len, els trens, els busos, el trànsit i els talls de llum.'),
};
for (const a of document.querySelectorAll('.pagines a')) {
  const fitxer = (a.getAttribute('href') || '').split('/').pop();
  const d = DESCRIPCIO_PESTANYA[['', '.', 'index.html', 'casa.html'].includes(fitxer) ? 'temps' : fitxer];
  if (d && !a.title) a.title = d();
}

// La descripció de cada control (el «title») surt en passar-hi el ratolí; amb
// el dit, que no en té, mantenint-lo premut mig segon, com a Android: s'obre
// la mateixa bombolla i el control no fa res (Juanjo, 21-10-2026: «al poner
// el raton encima quiero que salga una descripción»). Un toc normal fa el de
// sempre; si el dit es mou (desplaçar, arrossegar), no s'obre.
const PREMUT_MS = 500;
let TOC_LLARG = false;
let premut = null;
const cancelaPremut = () => {
  if (premut) clearTimeout(premut.temps);
  premut = null;
};
document.addEventListener('pointerdown', (e) => {
  TOC_LLARG = false;
  cancelaPremut();
  if (e.pointerType === 'mouse' || !e.target.closest) return;
  const el = e.target.closest('[title]');
  if (!el || el.closest('.alta') || !el.title.trim()) return;
  premut = { x: e.clientX, y: e.clientY, temps: setTimeout(() => {
    premut = null;
    TOC_LLARG = true;
    tancaBombolla();
    obreBombolla(el, el.title);
  }, PREMUT_MS) };
});
document.addEventListener('pointermove', (e) => {
  if (premut && Math.hypot(e.clientX - premut.x, e.clientY - premut.y) > 10) cancelaPremut();
});
document.addEventListener('pointerup', cancelaPremut);
document.addEventListener('pointercancel', cancelaPremut);
// Sense el menú del navegador (copiar l'enllaç, seleccionar) en lloc de la descripció.
document.addEventListener('contextmenu', (e) => { if (TOC_LLARG || premut) e.preventDefault(); });

function pintaResum(text) {
  const peces = [];
  for (const linia of trossos(text)) {
    if (!linia.length) continue;
    const trs = ambMarques(linia);
    const fila = element('p', 'resum-linia');
    if (peces.length) {
      const primera = trs[0] && trs[0].marca ? trs.shift() : null;
      const pla = trs.map((t) => t.t || '').join('');
      const tema = (ICONA_LINIA.find(([re]) => re.test(pla)) || [])[1];
      fila.append(primera ? nodeMarca(primera.marca) : tema ? icona(tema) : element('span', 'resum-buit'));
    }
    const cos = element('span');
    cos.append(...nodesAmbMarques(trs));
    fila.append(cos);
    peces.push(fila);
  }
  return peces;
}

// «Nou!» damunt d'una pàgina nova: fins que s'hi entra (ho recorda el
// navegador) i, per a tothom, una setmana després de publicar-la. El «Nou:»
// del començament de la pàgina, igual (Juanjo, 08-10-2026). La campana
// d'«Avisos al mòbil» (ADR 0048) i la pestanya «Perill» (ADR 0071; Juanjo,
// 11-10-2026: «con las mismas reglas»). La pestanya «Consultes», pels busos
// (ADR 0120), tres dies, com l'opció «Busos» de dins (consultes.js; Juanjo,
// 22-10-2026: «al abrir cada uno de ellos desaparece la etiqueta»).
const FI_NOU_BUSOS = new Date('2026-10-25T10:00:00+01:00');
const NOVETATS = [
  { pagina: 'avisos.html', boto: '.boto-avisos', clau: 'meteo.avisos-vist', fins: new Date('2026-10-16T00:00:00+02:00') },
  { pagina: 'perill.html', boto: '.pagines a[href$="perill.html"]', clau: 'meteo.perill-vist',
    fins: new Date('2026-10-19T00:00:00+02:00') },
  { pagina: 'consultes.html', boto: '.pagines a[href$="consultes.html"]', clau: 'meteo.consultes-vist', fins: FI_NOU_BUSOS },
];

function marcaNovetats(ara = new Date()) {
  for (const n of NOVETATS) {
    const aqui = new RegExp(`(^|/)${n.pagina.replace('.', '\\.')}$`).test(location.pathname);
    let vist = false;
    try {
      if (aqui) localStorage.setItem(n.clau, '1');
      vist = localStorage.getItem(n.clau) === '1';
    } catch (_) {}
    if (aqui && ara >= n.fins) {
      document.querySelectorAll('.novetat').forEach((p) => {
        p.classList.remove('novetat');
        p.querySelector('.nou')?.remove();
        // Sense «Nou:», la frase comença amb majúscula: «Els avisos de
        // perill…», no «els avisos…» (Juanjo, 20-10-2026).
        const t = p.firstChild;
        if (t && t.nodeType === Node.TEXT_NODE) {
          const text = t.textContent.trimStart();
          t.textContent = text.charAt(0).toUpperCase() + text.slice(1);
        }
      });
    }
    for (const a of document.querySelectorAll(n.boto)) {
      const xip = a.querySelector('.xip-nou');
      if (vist || ara >= n.fins) {
        a.classList.remove('amb-nou');
        xip?.remove();
      } else if (!xip) {
        a.classList.add('amb-nou');
        a.append(element('span', 'xip-nou', T('Nou!')));
      }
    }
  }
}

marcaNovetats();

// Un punt vermell a la pestanya «Perill» quan hi ha un avís
// activa que no s'ha vist, tant si s'han activat els avisos com si no (Juanjo,
// 11-10-2026; ADR 0071), fins que s'obre «Perill», que apunta fins a quan
// s'ha vist. Només mentre és activa: abans durava 24 hores, i el punt vermell
// sortia al costat de «Ara no hi ha cap situació de perill» (Juanjo,
// 12-10-2026; ADR 0074).
const CLAU_PERILL_VIST = 'meteo.perill-vist-fins';

// Nou: actiu i publicat o actualitzat (publicacioEpisodi: l'hora de «Nou» a
// «Avisos actius») després de l'última visita a «Perill». Fins a la 3.146.0
// només comptava el començament: el punt vermell no sortia per una
// actualització, i a «Perill» res deia què era nou (Juanjo, 19-10-2026: «hay
// que marcar como nuevo lo que sea nuevo»).
function perillsNous(historial, vist, ara = new Date()) {
  return (historial || []).filter((e) => {
    // En pausa (la previsió ja no el veu i espera a tancar-se): no és actiu.
    const actiu = !e.fi && !e.en_pausa && !(e.fins && new Date(e.fins) <= ara);
    const hora = e.clau ? publicacioEpisodi(e).hora : new Date(e.darrer || e.inici);
    return actiu && (!vist || hora.getTime() > new Date(vist).getTime());
  });
}

function senyalaPerill(historial, ara = new Date()) {
  let vist = null;
  try { vist = localStorage.getItem(CLAU_PERILL_VIST); } catch (_) {}
  const nous = perillsNous(historial, vist, ara).length > 0;
  for (const a of document.querySelectorAll('.pagines a[href$="perill.html"]')) {
    let punt = a.querySelector('.punt-perill');
    if (nous && !punt) {
      punt = element('span', 'punt-perill');
      punt.setAttribute('role', 'img');
      punt.setAttribute('aria-label', T('Hi ha un avís nou'));
      punt.title = T('Hi ha un avís nou');
      a.append(punt);
    } else if (!nous && punt) punt.remove();
  }
}

// El punt de la pestanya «Riera» (ADR 0107): vermell si hi ha un avís de la
// riera actiu que no s'ha vist (el mateix criteri que el punt de «Perill»,
// només amb la riera); ambre si la previsió dels models diu «risc de
// crescuda possible» i no s'ha vist: ambre i no vermell, perquè el vermell
// és el d'una situació de perill amb dades reals (Juanjo, 19-10-2026). Fins
// que s'obre «Riera», que apunta fins a quan s'ha vist.
const CLAU_RIERA_VIST = 'meteo.riera-vist-fins';

function rieraNova(previsio, vist) {
  return Boolean(previsio && previsio.nivell === 'possible' && previsio.inici
    && (!vist || new Date(previsio.inici).getTime() > new Date(vist).getTime()));
}

function puntRiera(previsio, historial, vist, ara = new Date()) {
  if (perillsNous((historial || []).filter((e) => e.tipus === 'riera'), vist, ara).length) return 'vermell';
  return rieraNova(previsio, vist) ? 'ambre' : null;
}

function senyalaRiera(previsio, historial) {
  let vist = null;
  try { vist = localStorage.getItem(CLAU_RIERA_VIST); } catch (_) {}
  const color = puntRiera(previsio, historial, vist);
  const text = color === 'vermell' ? T('Hi ha un avís de la riera nou') : T('Previsió de risc de crescuda de la riera');
  for (const a of document.querySelectorAll('.pagines a[href$="riera.html"]')) {
    let punt = a.querySelector('.punt-riera');
    if (color && !punt) {
      punt = element('span', 'punt-riera');
      punt.setAttribute('role', 'img');
      a.append(punt);
    }
    if (color) {
      punt.className = `punt-riera ${color}`;
      punt.setAttribute('aria-label', text);
      punt.title = text;
    } else if (punt) punt.remove();
  }
}

let PREVISIO_RIERA = null;

// A «Perill» mateix no cal: s'hi és. A les altres, es mira en carregar i cada
// cinc minuts.
if (!/(^|\/)perill\.html$/.test(location.pathname) && document.querySelectorAll('.pagines a[href$="perill.html"]').length) {
  // Amb l'historial, també la riera a «Avisos actius»: la pàgina el torna a pintar (repintaAvisos).
  const miraPerill = () => llegeixDades('avisos.json').then((d) => {
    HISTORIAL_PERILL = d.historial;
    senyalaPerill(d.historial);
    PREVISIO_RIERA = d.riera_previsio || null;
    if (!/(^|\/)riera\.html$/.test(location.pathname)) senyalaRiera(PREVISIO_RIERA, d.historial);
    // eslint-disable-next-line no-undef -- la defineix la pàgina, si en té (casa.js, sortir.js, consultes.js).
    if (typeof repintaAvisos === 'function') repintaAvisos();
  }, () => {});
  miraPerill();
  setInterval(miraPerill, 5 * 60000);
  enArribarUnAvis(miraPerill);
  // Amb el mòbil bloquejat o la pestanya al fons, el navegador atura la
  // pàgina i l'avís pot arribar sense que es repinti: es torna a mirar en
  // tornar-la a tenir davant (Juanjo, 16-10-2026: «aunque esté abierta debe
  // salir que ha aparecido una alerta nueva en perill»).
  document.addEventListener('visibilitychange', () => { if (!document.hidden) miraPerill(); });
}

// Els avisos de la portada que ja s'havien mostrat en aquest dispositiu (el
// que hi ha apuntat ara) perden el «Nou», com en tornar a carregar la pàgina.
function treuNousVistos() {
  const llegits = new Set(llegeixLlegits());
  if (LLEGITS_ABANS) for (const c of llegits) LLEGITS_ABANS.add(c);
  for (const c of document.querySelectorAll('.avis-item[data-llegit]')) {
    if (llegits.has(c.dataset.llegit)) c.querySelector('.avis-nou')?.remove();
  }
}

// En tornar enrere, el navegador pot restaurar la pàgina tal com era (memòria
// cau d'enrere i endavant), sense tornar a executar res: el punt vermell i el
// «Nou!» seguien allà després d'haver obert «Perill» (Juanjo, 16-10-2026). Es
// tornen a mirar amb el que ara hi ha apuntat.
addEventListener('pageshow', (e) => {
  if (!e.persisted) return;
  marcaNovetats();
  treuNousVistos();
  if (HISTORIAL_PERILL && !/(^|\/)perill\.html$/.test(location.pathname)) senyalaPerill(HISTORIAL_PERILL);
  if (!/(^|\/)riera\.html$/.test(location.pathname)) senyalaRiera(PREVISIO_RIERA, HISTORIAL_PERILL);
});

// Compartir (Juanjo, 11-10-2026: «cualquier pagina o consulta … quiero que se
// pueda compartir»; ADR 0072): l'adreça del que es mira, amb l'opció triada
// (consultes.html#llum) o l'avís (perill.html#…). Al mòbil, el menú de
// compartir del sistema; si el navegador no en té, es copia l'enllaç i es diu.
function avisBreu(text) {
  document.querySelector('.avis-breu')?.remove();
  const p = element('p', 'avis-breu', text);
  p.setAttribute('role', 'status');
  llocActiu().append(p);
  setTimeout(() => p.remove(), 4000);
}

// Compartir obre el menú de compartir del dispositiu (Juanjo, 12-10-2026:
// «me refiero a compartir, debe salir el menu de compartir»; ADR 0076); on no
// n'hi ha (alguns navegadors d'ordinador), es copia sol, en el moment
// («tienen que copiar automaticamente»). Amb un text (un avís de «Perill»), el
// missatge sencer i l'enllaç, per enviar-lo de seguida a altres.
function comparteix(url = location.href, titol = document.title, text = '') {
  if (navigator.share) {
    navigator.share(text ? { title: titol, text, url } : { title: titol, url }).catch((e) => {
      if (e.name !== 'AbortError') copiaEnllac(url, text);
    });
    return;
  }
  copiaEnllac(url, text);
}

// Es copia de la manera clàssica, que funciona gairebé a tot arreu, també fora
// d'https, i dins del mateix toc; si no, amb el portapapers del navegador
// (Juanjo, 12-10-2026: «dice que lo copie yo a mano, eso no es serio»; ADR
// 0076). Només si tampoc no es pot, es mostra el text seleccionat.
function copiaEnllac(url, text = '') {
  const tot = text ? `${text}\n${url}` : url;
  const fet = () => avisBreu(text ? T('Avís copiat, amb l’enllaç') : T('Enllaç copiat'));
  if (copiaClassica(tot)) {
    fet();
    return;
  }
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(tot).then(fet, () => mostraPerCopiar(tot));
  else mostraPerCopiar(tot);
}

// Amb una finestra oberta (la gràfica en gran), la resta de la pàgina queda
// inert: el que s'hi posa no es pot seleccionar ni es veu. Va dins de la
// finestra (Juanjo, 17-10-2026: «dice copiado pero no se copia nada»).
const llocActiu = () => document.querySelector('dialog[open]') || document.body;

function copiaClassica(tot) {
  try {
    const area = element('textarea');
    area.value = tot;
    area.setAttribute('readonly', '');
    area.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
    llocActiu().append(area);
    area.select();
    area.setSelectionRange(0, tot.length);
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  } catch (_) {
    return false;
  }
}

// L'últim recurs: el text, ja seleccionat, en una finestra petita per copiar-lo.
function mostraPerCopiar(tot) {
  const visor = element('dialog', 'per-copiar');
  const area = element('textarea');
  area.value = tot;
  area.readOnly = true;
  area.rows = Math.min(8, tot.split('\n').length + 1);
  area.setAttribute('aria-label', T('Text per copiar'));
  const tanca = element('button', null, T('Tanca'));
  tanca.type = 'button';
  tanca.addEventListener('click', () => visor.close());
  visor.addEventListener('close', () => visor.remove());
  visor.append(element('p', null, T('Mantén premut el text i tria «Copia».')), area, tanca);
  document.body.append(visor);
  visor.showModal();
  area.focus();
  area.select();
}

for (const b of document.querySelectorAll('.boto-compartir')) b.addEventListener('click', () => comparteix());

// Al mòbil, la botonera de dalt ocupava una fila sencera a sobre del títol:
// ara hi queden compartir, la campana i ⋮, al costat del títol, i dins de ⋮
// el que es fa servir de tant en tant (l'ajuda, «Fiabilitat», l'idioma i el
// tema) (Juanjo, 20-10-2026: «se podría poner en un menú de 3 puntos?», i la
// proposta mixta: «sí, la B»; compartir, a la vista: «ahora cabe junto a la
// campana»). A l'ordinador, igual des de la 3.165.0 (Juanjo, 20-10-2026:
// «pon los tres puntos»); a la 3.164.0 s'hi havia deixat tot a la vista, cosa
// que ell no havia demanat.
const MENU_FIABILITAT = true;
function menuMes() {
  const botons = document.querySelector?.('.cap-botons');
  if (!botons) return;
  const boto = element('button', 'boto-icona boto-mes');
  boto.type = 'button';
  boto.title = T('Més opcions');
  boto.setAttribute('aria-label', T('Més opcions'));
  boto.setAttribute('aria-expanded', 'false');
  boto.setAttribute('aria-controls', 'menu-mes');
  // L'icona «ellipsis-vertical» de Lucide.
  boto.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="1"/>'
    + '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>';
  const menu = element('div', 'menu-mes');
  menu.id = 'menu-mes';
  menu.hidden = true;
  const tanca = () => { menu.hidden = true; boto.setAttribute('aria-expanded', 'false'); };
  const fila = (icon, text, accio) => {
    const b = element(accio.href ? 'a' : 'button', 'menu-mes-opcio');
    if (accio.href) b.href = accio.href;
    else { b.type = 'button'; b.addEventListener('click', () => { tanca(); accio(); }); }
    b.append(icona(icon), text);
    return b;
  };
  const ajuda = document.querySelector('.cap-botons a[href^="com-funciona.html"]');
  if (ajuda) menu.append(fila('i-circle-help', T('Com funciona'), { href: ajuda.href }));
  // «Fiabilitat» (ADR 0110): quant encerta la previsió, comparada amb Meteocat i AEMET, i com aprèn.
  // Fora del menú fins que hi hagi més dades (Juanjo, 20-10-2026: «quita el
  // enlace de fiabilidad del menu de 3 puntos, lo pondremos cuando haya más
  // datos»); la pàgina segueix a la seva adreça.
  if (MENU_FIABILITAT) menu.append(fila('i-target', T('Fiabilitat'), { href: 'fiabilitat.html' }));
  // Grups de botons units, el triat marcat, com el selector d'hores de la gràfica.
  const grup = (nom, opcions) => {
    const g = element('div', 'menu-mes-grup');
    const id = `menu-mes-${nom.toLowerCase().replace(/[^a-z]/g, '')}`;
    const etiqueta = element('span', 'menu-mes-nom', nom);
    etiqueta.id = id;
    const trams = element('div', 'vg-trams');
    trams.setAttribute('role', 'group');
    trams.setAttribute('aria-labelledby', id);
    trams.append(...opcions);
    g.append(etiqueta, trams);
    return g;
  };
  // L'idioma: les dues llengües, amb el nom sencer; el clic el desa (CLAU_IDIOMA).
  const idiomes = document.querySelector('.cap-botons .idiomes');
  if (idiomes) {
    menu.append(grup(T('Idioma'), [...idiomes.children].map((x) => {
      const o = element(x.tagName === 'A' ? 'a' : 'span', 'vg-opcio', x.title);
      if (x.tagName === 'A') { o.href = x.href; o.hreflang = x.hreflang; o.lang = x.lang; o.className += ' idioma-mes'; }
      else { o.lang = x.lang; o.setAttribute('aria-current', 'true'); }
      return o;
    })));
  }
  // El tema: automàtic (el del dispositiu), clar o fosc.
  const temes = [['auto', T('Automàtic')], ['clar', T('Clar')], ['fosc', T('Fosc')]].map(([clau, text]) => {
    const b = element('button', 'vg-opcio', text);
    b.type = 'button';
    b.dataset.tema = clau;
    b.addEventListener('click', () => { triaTema(clau); marcaTema(); });
    return b;
  });
  const marcaTema = () => {
    const actual = segueixSistema() ? 'auto' : document.documentElement.dataset.theme === 'dark' ? 'fosc' : 'clar';
    for (const b of temes) b.setAttribute('aria-pressed', String(b.dataset.tema === actual));
  };
  if ($('btn-fosc')) menu.append(grup(T('Tema'), temes));
  boto.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!menu.hidden) { tanca(); return; }
    marcaTema();
    menu.hidden = false;
    boto.setAttribute('aria-expanded', 'true');
  });
  document.addEventListener('click', (e) => { if (!menu.hidden && !menu.contains(e.target)) tanca(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !menu.hidden) { tanca(); boto.focus(); } });
  botons.append(boto, menu);
}

// Tria el tema des del menú: «auto» torna a seguir el del dispositiu.
function triaTema(clau) {
  try {
    if (clau === 'auto') localStorage.removeItem('meteo.fosc');
    else localStorage.setItem('meteo.fosc', clau === 'fosc' ? '1' : '0');
  } catch (_) {}
  aplicaFosc(clau === 'auto' ? sistemaFosc.matches : clau === 'fosc', false);
}

menuMes();

// «Enrere», com en una aplicació (Juanjo, 12-10-2026: «al ir hacia atrás
// fuese a la pagina principal y si pulso otra vez, entonces se sale de la
// app»; ADR 0074 i 0076). Entre les pestanyes, la nova substitueix l'anterior;
// de la portada a una pestanya, o d'una pestanya a una pàgina d'explicació
// («Com funciona», «Fonts i crèdits»…), el navegador ho apunta, perquè enrere
// torni on s'era (de «Què vol dir aquest avís», a l'avís). Tocar «El temps» és
// tornar enrere fins a la portada. D'una explicació a una pestanya, primer es
// torna a la pestanya de sota i se substitueix per la nova: si no, la de sota
// es quedava apuntada i enrere passava per totes (Juanjo, 16-10-2026: «me pasa
// por todas las páginas que he visto»). El canvi d'idioma no s'apunta. Qui entra per
// un enllaç a una altra pàgina (un avís compartit) surt amb enrere.
// La profunditat (quants passos apuntats hi ha des de la portada) va a
// history.state i, d'una pàgina a la següent, per sessionStorage.
const CLAU_PROFUNDITAT = 'meteo.profunditat';
// On anar en arribar a la pestanya de sota (l'acció 'torna').
const CLAU_DESTI = 'meteo.desti';
const esPortada = (url) => /\/(index\.html|casa\.html)?$/.test(new URL(url, location.href).pathname);
const esPestanya = (url) => /\/(index\.html|casa\.html|perill\.html|sortir\.html|consultes\.html)?$/
  .test(new URL(url, location.href).pathname);

// Què fer en anar d'«actual» a «desti», amb la profunditat d'ara (0 a la
// portada; null si no s'hi ha passat): [acció, profunditat de la pàgina nova].
// L'acció: 'apunta', 'substitueix', 'enrere' (fins a la portada) o 'torna'
// (enrere fins a la primera pestanya, que se substitueix per la nova).
function comNavega(actual, desti, prof) {
  if (esPortada(desti)) return esPortada(actual) || !prof ? ['substitueix', esPortada(actual) ? 0 : null] : ['enrere', 0];
  if (esPortada(actual)) return ['apunta', 1];
  if (esPestanya(actual) && !esPestanya(desti)) return ['apunta', prof == null ? null : prof + 1];
  if (!esPestanya(actual) && esPestanya(desti) && prof > 1) return ['torna', 1];
  return ['substitueix', prof];
}

function profunditat() {
  if (esPortada(location.href)) return 0;
  const p = history.state && history.state.profunditat;
  return Number.isInteger(p) ? p : null;
}

try {
  const portada = sessionStorage.getItem(CLAU_PROFUNDITAT);
  if (portada !== null && !esPortada(location.href)) {
    history.replaceState({ ...(history.state || {}), profunditat: Number(portada) }, '');
  }
  sessionStorage.removeItem(CLAU_PROFUNDITAT);
} catch (_) {}

// Després d'un 'torna': ja a la pestanya de sota, la nova la substitueix (si
// no és la mateixa). Al carregar i, si ve de la memòria del navegador, al pageshow.
function segueixDesti() {
  let desti = null;
  try {
    desti = sessionStorage.getItem(CLAU_DESTI);
    sessionStorage.removeItem(CLAU_DESTI);
  } catch (_) {}
  if (!desti) return;
  const d = new URL(desti, location.href);
  if (d.pathname === location.pathname && d.search === location.search) {
    if (d.hash && d.hash !== location.hash) location.replace(d.href);
    return;
  }
  try { sessionStorage.setItem(CLAU_PROFUNDITAT, '1'); } catch (_) {}
  location.replace(d.href);
}
segueixDesti();
addEventListener('pageshow', (e) => { if (e.persisted) segueixDesti(); });

// L'idioma triat amb el selector (o al menú ⋮) es recorda en aquest aparell
// (ADR 0083): la web i l'app s'obren en el del sistema (català o castellà;
// si no és cap dels dos, en català) fins que algú en tria un altre, i després
// en el triat. Qui hi porta és el <head> de cada pàgina pública (montflorit.py).
const CLAU_IDIOMA = 'meteo.idioma';
document.addEventListener('click', (e) => {
  const a = e.target.closest('.idiomes a[hreflang], .idioma-mes');
  if (a) try { localStorage.setItem(CLAU_IDIOMA, a.hreflang); } catch (_) {}
});

document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href]');
  if (!a || e.defaultPrevented || a.target || a.hasAttribute('download') || e.button !== 0
      || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
  const desti = new URL(a.href, location.href);
  // Només les pàgines d'aquesta web.
  if (desti.origin !== location.origin || !/\/([a-z-]+\.html)?$/.test(desti.pathname)) return;
  // Dins de la mateixa pàgina (la «›» dels trens a «Consultes»), sense apuntar-ho.
  if (desti.pathname === location.pathname && desti.search === location.search) {
    e.preventDefault();
    if (desti.hash !== location.hash) location.replace(desti.href);
    // El mateix enllaç un altre cop: es torna a destacar.
    else if (desti.hash) window.dispatchEvent(new Event('hashchange'));
    return;
  }
  const prof = profunditat();
  const [com, nova] = comNavega(location.href, desti.href, prof);
  if (com === 'enrere') {
    e.preventDefault();
    history.go(-prof);
    return;
  }
  if (com === 'torna') {
    try {
      sessionStorage.setItem(CLAU_DESTI, desti.href);
    } catch (_) {
      // Sense sessionStorage no es pot seguir: se substitueix, com abans.
      e.preventDefault();
      location.replace(desti.href);
      return;
    }
    e.preventDefault();
    history.go(1 - prof);
    return;
  }
  try {
    if (nova == null) sessionStorage.removeItem(CLAU_PROFUNDITAT);
    else sessionStorage.setItem(CLAU_PROFUNDITAT, String(nova));
  } catch (_) {}
  if (com === 'apunta') return;
  e.preventDefault();
  location.replace(desti.href);
});

// --- Activar els avisos al navegador (ADR 0048): el fan servir «Avisos» i
// l'oferta de la portada a qui té la web instal·lada (ADR 0080). El servidor
// (subscripcio.php, a IONOS) desa l'adreça de notificacions i què s'hi tria. ---
const SERVIDOR_AVISOS = DADES_URL + 'subscripcio.php';
// Per començar, com al bot: la riera i el perill.
const AVISOS_PER_DEFECTE = ['riera', 'perill'];

async function cridaAvisos(cos) {
  const r = await fetch(SERVIDOR_AVISOS, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cos),
  });
  const dades = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(dades.error || r.status), { estat: r.status });
  return dades;
}

// La clau pública del servidor, en bytes, com la vol el navegador.
async function clauAvisos() {
  const r = await fetch(SERVIDOR_AVISOS, { cache: 'no-store' });
  if (!r.ok) throw new Error(r.status);
  const b64 = (await r.json()).clau.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

// L'adreça de notificacions d'aquest dispositiu; si n'hi havia una d'abans
// amb una altra clau, es treu i es torna a fer.
async function subscriuAvisos(registre) {
  const clau = await clauAvisos();
  try {
    return await registre.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: clau });
  } catch (ex) {
    const vella = await registre.pushManager.getSubscription();
    if (!vella) throw ex;
    await vella.unsubscribe();
    return registre.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: clau });
  }
}

// L'enllaç a l'app d'Android (ADR 0082), només a la web pública (montflorit.py
// el posa al peu): a Android i a l'ordinador, des d'on Google Play la pot
// instal·lar al mòbil. No a l'iPhone ni a l'iPad, on no s'hi pot instal·lar
// (l'iPad es presenta com un Mac, però tàctil), ni a qui ja la té: dins de
// l'app o de la web instal·lada. L'app obre la web amb un referrer
// android-app://, que es recorda la resta de la sessió.
function ofereixApp(ua, tactil, dinsApp, instal) {
  const ios = /iPhone|iPad|iPod/i.test(ua) || (/Macintosh/i.test(ua) && tactil > 1);
  return !ios && !dinsApp && !instal;
}

function dinsApp() {
  try {
    if (document.referrer.startsWith('android-app://')) sessionStorage.setItem('meteo.app', '1');
    return sessionStorage.getItem('meteo.app') === '1';
  } catch (_) {
    return false;
  }
}

// El nom del que es mira: l'app («Montflorit al dia», ADR 0082) o la web
// («Temps a Montflorit»; la de casa, «Temps a casa»). Són noms propis: no es
// tradueixen (Juanjo, 17-10-2026: «hay dos nombres»).
function nomPropi() {
  if (dinsApp()) return 'Montflorit al dia';
  return document.documentElement.dataset.lloc === 'Montflorit' ? 'Temps a Montflorit' : 'Temps a casa';
}

(function () {
  const p = $('app-android');
  if (!p) return;
  const instal = matchMedia('(display-mode: standalone)').matches || matchMedia('(display-mode: fullscreen)').matches;
  p.hidden = !ofereixApp(navigator.userAgent || '', navigator.maxTouchPoints || 0, dinsApp(), instal);
})();

// Per poder instal·lar la web com a aplicació (sw.js).
if ('serviceWorker' in navigator) navigator.serviceWorker.register(ARREL + 'sw.js').catch(() => {});

// En obrir la web o tornar-hi, les seves notificacions marxen de la safata,
// com a Telegram o WhatsApp (Juanjo, 12-10-2026): el que deien ja és a dalt,
// a «Avisos actius», i a «Perill», i un avís vell que s'hi quedés podria fer
// creure que el perill continua (ADR 0048). Només es treuen de la safata.
function tancaNotificacions() {
  if (!('serviceWorker' in navigator) || !navigator.serviceWorker.getRegistration) return Promise.resolve(0);
  return navigator.serviceWorker.getRegistration()
    .then((r) => (r && r.getNotifications ? r.getNotifications() : []))
    .then((ns) => { ns.forEach((n) => n.close()); return ns.length; })
    .catch(() => 0);
}
tancaNotificacions();
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') tancaNotificacions();
});
