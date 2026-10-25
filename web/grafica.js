// SPDX-License-Identifier: AGPL-3.0-or-later
// La gràfica de la previsió (ADR 0096) i el que necessita per dibuixar-se: el
// cel, la pluja i el perill de cada hora. La fan servir la portada (casa.js:
// la gràfica, la vista en gran i les taules) i «Consultes» (consultes.js: la
// d'«Avui» i la de «Demà»), perquè el dibuix sigui un de sol (Juanjo,
// 17-10-2026). Es carrega després de comu.js i abans de la pàgina.

// Si l'hora és de pluja, segons la probabilitat i no segons els mil·límetres
// del model més plujós: «pluja» si és més probable que plogui que no (50 % o
// més) i «possible» des del 20 %, els mateixos llindars que config.py. Sense
// probabilitat, manen els mil·límetres.
const PROB_PLUJA = 0.5;
const PROB_POSSIBLE = 0.2;
// Només a la gràfica: de 10 al 20 % plou una de cada set hores, i per sota
// del 20 % queia una de cada cinc hores de pluja (arxiu 2024-2026; Juanjo,
// 16-10-2026). La taula no ho distingeix: al cel, «possible pluja» és des del 20 %.
const PROB_POCA = 0.1;
function plujaHora(f) {
  const p = f.probabilitat;
  if (f.plou_ara || (p == null ? f.pluja_mm >= 0.2 : p >= PROB_PLUJA)) return 'pluja';
  return p != null && p >= PROB_POSSIBLE ? 'possible' : null;
}
function plujaGrafica(f) {
  const p = f.probabilitat;
  return plujaHora(f) || (p != null && p >= PROB_POCA ? 'poca' : null);
}

// Descripció del cel i la icona que hi correspon. Els mil·límetres diuen com
// seria la pluja, no si n'hi haurà: sense prou probabilitat, només els
// núvols. De nit, la lluna en lloc del sol (a mitja hora del tram).
// Les paraules són les del manual d'estil de Meteocat (ADR 0043). Intensitat
// en una hora (el manual la dona per 30 minuts, aquí el doble): pluja
// moderada des de 6 mm, forta des de 40, torrencial des de 80; neu moderada
// des de 2 cm, forta des de 10. Tipus pels codis de temps d'Open-Meteo.
const INTENSITAT_PLUJA = [6, 40, 80];
const INTENSITAT_NEU = [2, 10];
const esNeu = (c) => (c >= 71 && c <= 77) || c === 85 || c === 86;
const esGelant = (c) => c === 56 || c === 57 || c === 66 || c === 67;
const esCalamarsa = (c) => c === 96 || c === 99;

function cel(f) {
  const nit = alturaSol(new Date(new Date(f.hora).getTime() + 18e5)) < 0;
  const pluja = plujaHora(f);
  const tempesta = f.codi >= 95;
  if (pluja === 'pluja') {
    if (tempesta) return esCalamarsa(f.codi) ? [T('Tempesta amb calamarsa'), 'i-cloud-hail'] : [T('Tempesta'), 'i-cloud-lightning'];
    if (esNeu(f.codi)) {
      const cm = f.neu || 0;
      return [cm >= INTENSITAT_NEU[1] ? T('Neu forta') : cm >= INTENSITAT_NEU[0] ? T('Neu moderada') : T('Neu feble'), 'i-cloud-snow'];
    }
    if (esGelant(f.codi)) return [T('Pluja gelant'), 'i-cloud-rain'];
    const mm = f.pluja_mm || 0;
    if (mm >= INTENSITAT_PLUJA[2]) return [T('Pluja torrencial'), 'i-cloud-rain-wind'];
    if (mm >= INTENSITAT_PLUJA[1]) return [T('Pluja forta'), 'i-cloud-rain-wind'];
    if (mm >= INTENSITAT_PLUJA[0]) return [T('Pluja moderada'), 'i-cloud-rain'];
    return [T('Pluja feble'), 'i-cloud-drizzle'];
  }
  if (pluja === 'possible') {
    if (esNeu(f.codi)) return [T('Possible neu'), 'i-cloud-snow'];
    return [tempesta ? T('Possible tempesta') : T('Possible pluja'), nit ? 'i-cloud-moon-rain' : 'i-cloud-sun-rain'];
  }
  if (esBoira(f)) return [T('Boira'), 'i-cloud-fog'];
  if (f.nuvols == null) return ['', null];
  // Si algun model hi posa pluja (0,2 mm o més, el que ja mulla), el cel no
  // pot sortir serè encara que la probabilitat sigui baixa: com a mínim, núvols.
  return celNuvols(nuvolsHora(f), nit);
}

// Les hores mesurades (l'historial), el cel tapat tal com es va observar.
const nuvolsHora = (f) => (!f.mesura && (f.pluja_mm || 0) >= 0.2 ? Math.max(f.nuvols, 50) : f.nuvols);
const esBoira = (f) => f.codi === 45 || f.codi === 48;

// Per vuitens de cel tapat: serè 0, poc 1-2, mig 3-5, molt 6-7, cobert 8.
function celNuvols(nuvols, nit) {
  if (nuvols < 20) return [T('Serè'), nit ? 'i-moon-cel' : 'i-sun'];
  if (nuvols < 45) return [T('Poc ennuvolat'), nit ? 'i-cloud-moon' : 'i-cloud-sun'];
  if (nuvols < 70) return [T('Mig ennuvolat'), 'i-cloud'];
  if (nuvols < 85) return [T('Molt ennuvolat'), 'i-cloudy'];
  // Els mateixos dos núvols que «molt ennuvolat», plens i més foscos: el cel
  // tancat (Juanjo, 25-10-2026: «cobert y molt ennuvolat tienen el mismo icono»).
  return [T('Cobert'), 'i-cloudy-cobert'];
}

// La part alta del barri, quan la diferència arriba a un grau (ADR 0087):
// «+2» al costat de la temperatura del tram i, a «Ara», una
// línia amb la mesurada ara.
// Arrodonit: 0,9 compta com un grau (Juanjo, 13-10-2026).
function arrodoneixAlta(n) {
  if (n == null) return 0;
  const r = Math.sign(n) * Math.round(Math.abs(n));
  return Math.abs(r) >= 1 ? r : 0;
}

// Avisos de Meteocat i de l'AEMET (el que Meteocat no cobreix, ADR 0093) en
// trams d'hores seguides del mateix tram del dia amb el mateix avís: per a cada hora, el tram que hi comença ({nivell, tipus, hores}),
// undefined si la cobreix un tram que ha començat abans, o null si no n'hi ha.
const ORDRE_NIVELL = ['groc', 'taronja', 'vermell'];

// El perill d'una hora: els avisos de l'AEMET i els que calcula aquesta web
// (riscos.py, ADR 0018) per a aquella hora, amb el nivell més alt (Juanjo,
// 12-10-2026: «la franja de peligro … tiene que estar destacada también …
// pluja forta en sí no indica ningún peligro especial»; ADR 0076).
// NOM_RISC, a comu.js: també el fa servir el bloc «Avisos actius» plegat (ADR 0094).

function riscosHora(f, riscos, ara = new Date()) {
  const ini = new Date(f.hora);
  const fi = new Date(f.fins);
  return (riscos || []).filter((r) => (r.origen === 'previsio'
    ? r.des_de && new Date(r.des_de) < fi && new Date(r.fins) > ini
    : ini <= ara && ara < fi));
}

// Es diu el nivell més alt i només el que el dona: amb un avís groc de
// l'AEMET per pluja i un de taronja de la web, «taronja: pluja molt forta».
// El fenomen de cada risc de la web, per no dir-lo dues vegades amb l'avís
// oficial del mateix fenomen («pluja intensa» de la web i «pluja» de l'AEMET).
const FENOMEN_RISC = { pluja_30min: 'pluja', pluja_3h: 'pluja', pluja_24h: 'pluja', ratxa: 'vent', neu_24h: 'neu' };

// Les fonts dels avisos, en l'ordre de les files i dels textos. Protecció
// Civil i Bombers només surten a l'historial (ADR 0124): els plans, en la seva
// fase («INUNCAT en alerta»), i els incendis.
const ORDRE_FONT = ['meteocat', 'aemet', 'pc', 'bombers', 'web'];
const nomAvis = (a, t) => (a.font === 'pc' ? T`${t} en ${TD(a.fase)}` : a.font === 'bombers' ? T('incendi forestal') : TD(t));

function elementsPerill(f) {
  return [...(f.avisos || []).flatMap((a) => a.tipus.map((t) => ({ nivell: a.nivell, nom: nomAvis(a, t), font: a.font || 'aemet',
    fenomen: a.font === 'pc' || a.font === 'bombers' ? `${a.font}:${t}` : t }))),
    ...(f.riscos_hora || []).map((r) => ({ nivell: r.nivell, nom: NOM_RISC()[r.tipus] || r.tipus, font: 'web',
      fenomen: FENOMEN_RISC[r.tipus] || r.tipus }))];
}

function delNivellMesAlt(elements) {
  if (!elements.length) return null;
  const nivell = elements.map((a) => a.nivell).sort((a, b) => ORDRE_NIVELL.indexOf(b) - ORDRE_NIVELL.indexOf(a))[0];
  const daquest = elements.filter((a) => a.nivell === nivell);
  const noms = [...new Set(daquest.map((a) => a.nom))].sort();
  const fonts = ORDRE_FONT.filter((x) => daquest.some((a) => a.font === x)).join('');
  // Cada nivell i cada font amb els seus fenòmens, del nivell més alt al més
  // baix: el color és el del més alt, però el text els diu tots (Juanjo,
  // 17-10-2026: amb perill alt de Meteocat per pluja i avís groc de l'AEMET
  // per tempestes, «que la franja diga las dos cosas»). Cada fenomen, una
  // sola vegada, al seu nivell més alt: un groc de l'AEMET per pluja no es
  // diu sota un taronja de pluja intensa de la web.
  const nivells = ORDRE_NIVELL.filter((nv) => elements.some((a) => a.nivell === nv)).reverse();
  const dits = new Set();
  const perFont = nivells.flatMap((nv) => {
    const aquests = elements.filter((a) => a.nivell === nv && !dits.has(a.fenomen || a.nom));
    aquests.forEach((a) => dits.add(a.fenomen || a.nom));
    return ORDRE_FONT.map((x) => [x, [...new Set(aquests.filter((a) => a.font === x).map((a) => a.nom))].sort(), nv])
      .filter(([, n]) => n.length);
  });
  return { nivell, noms, fonts, perFont };
}

function avisHora(f) {
  const p = delNivellMesAlt(elementsPerill(f));
  return p && { ...p, clau: p.perFont.map(([font, noms, nv]) => `${nv}|${font}|${noms.join(',')}`).join(';') };
}

function tramsAvis(hores) {
  const res = [];
  let obert = null;
  for (const f of hores) {
    const a = avisHora(f);
    if (a && obert && obert.clau === a.clau) {
      obert.hores += 1;
      res.push(undefined);
    } else {
      obert = a && { ...a, hores: 1 };
      res.push(obert);
    }
  }
  return res;
}

// Les files d'avisos de la gràfica (Juanjo, 19-10-2026: «las barras las veo
// desordenadas»; abans, una barra per nivell col·locada on hi cabia): una
// fila per font i fenomen, sempre en el mateix ordre (Meteocat, l'AEMET,
// aquesta web), amb el nom a sobre, i a la fila els trams seguits de cada
// nivell, d'esquerra a dreta. Dos fenòmens de la mateixa font amb els mateixos
// trams, en una sola fila («AEMET · pluja, tempestes»). Cada fenomen, a cada
// hora, només al seu nivell més alt, com a la franja de les taules (avisHora).
function filesAvis(hores) {
  const perClau = new Map();
  hores.forEach((f, i) => {
    const p = avisHora(f);
    for (const [font, noms, nivell] of (p ? p.perFont : [])) {
      for (const nom of noms) {
        const clau = `${font}|${nom}`;
        if (!perClau.has(clau)) perClau.set(clau, { font, noms: [nom], trams: [] });
        const trams = perClau.get(clau).trams;
        const darrer = trams[trams.length - 1];
        if (darrer && darrer.fi === i && darrer.nivell === nivell) darrer.fi = i + 1;
        else trams.push({ nivell, ini: i, fi: i + 1 });
      }
    }
  });
  const files = [];
  for (const f of perClau.values()) {
    const igual = files.find((g) => g.font === f.font && JSON.stringify(g.trams) === JSON.stringify(f.trams));
    if (igual) igual.noms.push(...f.noms);
    else files.push(f);
  }
  const ordre = (font) => (ORDRE_FONT.includes(font) ? ORDRE_FONT.indexOf(font) : ORDRE_FONT.length);
  return files.sort((a, b) => ordre(a.font) - ordre(b.font) || a.trams[0].ini - b.trams[0].ini)
    .map((f) => ({ ...f, noms: f.noms.sort() }));
}

// El perill dit com el diu cada font: Meteocat, en grau de perill (moderat,
// alt, molt alt); l'AEMET i aquesta web, en colors (ADR 0093). El complet, amb
// d'on surt cada cosa; el curt, per a la franja i l'etiqueta del tram.
const GRAU_METEOCAT = () => ({ groc: T('moderat'), taronja: T('alt'), vermell: T('molt alt') });

function perFonts(p) {
  return p.perFont || [[p.fonts, p.noms]];
}

function textPerill(p) {
  return perFonts(p).map(([font, noms, nv = p.nivell]) => {
    const que = noms.join(T(' i '));
    const nivell = TD(nv);
    // Qui avisa, primer (Juanjo, 17-10-2026).
    if (font === 'meteocat') return T`Meteocat: perill ${GRAU_METEOCAT()[nv]} per ${que}`;
    if (font === 'pc') return T`Protecció Civil: pla ${que}`;
    if (font === 'bombers') return T`Bombers: ${que} a prop del barri`;
    if (font === 'web') return T`Temps a Montflorit: avís ${nivell} per ${que} (no oficial)`;
    return T`AEMET: avís ${nivell} per ${que}`;
  }).join('; ');
}

// «Perill alt: pluja», «Avís groc: tempestes»; si n'hi ha de les dues maneres
// o de diversos nivells, juntes, del nivell més alt al més baix. Amb ambFont,
// també d'on surt cada un, «Perill alt (Meteocat): pluja» (la franja de la
// gràfica; Juanjo, 17-10-2026: «añade el origen: meteocat, aemet, etc»).
const NOM_FONT = () => ({ meteocat: 'Meteocat', aemet: 'AEMET', pc: T('Protecció Civil'), bombers: 'Bombers',
  web: T('aquesta aplicació') });
function partsPerill(p, ambQue = true, ambFont = false) {
  const parts = new Map();
  for (const [font, noms, nv = p.nivell] of perFonts(p)) {
    const origen = ambFont && NOM_FONT()[font] ? ` (${NOM_FONT()[font]})` : '';
    const nom = (font === 'meteocat' ? T`Perill ${GRAU_METEOCAT()[nv]}` : font === 'pc' ? T('Pla de Protecció Civil')
      : font === 'bombers' ? 'Bombers' : T`Avís ${TD(nv)}`) + (font === 'pc' || font === 'bombers' ? '' : origen);
    const abans = parts.get(nom);
    parts.set(nom, { nivell: nv, que: [...new Set([...(abans ? abans.que : []), ...noms])] });
  }
  return [...parts].map(([nom, { nivell, que }]) => ({ nivell, text: ambQue ? `${nom}: ${que.join(', ')}` : nom }));
}

function textPerillCurt(p, ambQue = true, ambFont = false) {
  return partsPerill(p, ambQue, ambFont).map((x) => x.text).join(' · ');
}

// --- La gràfica de la previsió (Juanjo, 16-10-2026: «un resumen visual …
// muy visual y muy claro»). Un meteograma, de l'hora en curs fins al final de
// la taula: la franja de perill, el cel cada 3 h, la temperatura i la
// probabilitat de pluja, amb el mateix eix d'hores. Les dades, les de la
// taula; la gràfica no diu res que no sigui a sota, tret de la fitxa de
// cada hora, que hi afegeix la part alta i l'UV. ---
const SVG_NS = 'http://www.w3.org/2000/svg';
function svg(nom, atributs = {}, text = null) {
  const e = document.createElementNS(SVG_NS, nom);
  for (const [k, v] of Object.entries(atributs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}

// L'alçada de la barra de pluja, en mil·límetres, proporcional al sostre
// rotulat (Juanjo, 17-10-2026: amb 3,7 mm i el sostre a 10 mm, la barra
// arribava al 61 % i no al 37 %: era d'arrel quadrada, perquè 1 o 2 mm no
// desapareguessin; amb el sostre per esglaons, 1 mm ja és el 10 %, i les
// barres baixes tenen 3 px com a mínim). Dalt de tot, l'esglaó que cobreix la pluja més forta de la
// gràfica, 10 mm com a mínim: les barres omplen més l'espai (Juanjo,
// 17-10-2026: «las columnas me parecen cortas… no sería mejor una escala
// variable?»), però en esglaons fixos i amb el sostre rotulat, perquè un dia
// de plovisqueig no sembli un diluvi. Del 40 amunt (el llindar taronja),
// també el color ho diu.
const MM_ESGLAONS = [10, 20, 40, 80, 160];
const sostrePluja = (files) => {
  const max = Math.max(0, ...files.filter((f) => plujaGrafica(f)).map((f) => f.pluja_mm || 0));
  return MM_ESGLAONS.find((e) => max <= e) || MM_ESGLAONS[MM_ESGLAONS.length - 1];
};
const alcadaPluja = (mm, sostre) => Math.min(1, Math.max(0, mm) / sostre);
// La pluja forta i la torrencial, amb color propi: les intensitats del manual
// d'estil de Meteocat, les mateixes paraules que la columna «Cel» de la taula
// (INTENSITAT_PLUJA; ADR 0043). L'avís, a la franja de dalt (Juanjo,
// 16-10-2026: «no hay unas etiquetas normalizadas?»).
function intensitatPluja(mm) {
  if (mm >= INTENSITAT_PLUJA[2]) return 'torrencial';
  if (mm >= INTENSITAT_PLUJA[1]) return 'forta';
  return null;
}

// El cel d'un bloc de 3 h: la pluja, si n'hi ha en alguna hora; si no, la del mig.
function celBloc(files) {
  const amb = files.map((f) => [f, cel(f)]).filter(([, c]) => c[1]);
  if (!amb.length) return null;
  const plujoses = amb.filter(([f]) => plujaHora(f));
  if (plujoses.length) return plujoses.sort(([a], [b]) => (b.probabilitat || 0) - (a.probabilitat || 0))[0][1];
  return amb[Math.floor(amb.length / 2)][1];
}

// La línia de temperatura, suau (Juanjo, 16-10-2026: «tiene picos… que
// parezca más profesional»): corba cúbica monòtona (Fritsch i Carlson, la
// «monotoneX» de d3), que passa per cada hora i no fa pujades ni baixades
// que no siguin a les dades.
function corbaSuau(p) {
  const n = p.length;
  const f = (v) => v.toFixed(1);
  if (n < 3) return 'M' + p.map(([a, b]) => `${f(a)},${f(b)}`).join(' L');
  const h = [], s = [];
  for (let i = 0; i < n - 1; i++) {
    h.push(p[i + 1][0] - p[i][0]);
    s.push((p[i + 1][1] - p[i][1]) / h[i]);
  }
  const m = new Array(n);
  for (let i = 1; i < n - 1; i++) {
    if (s[i - 1] * s[i] <= 0) { m[i] = 0; continue; }
    const q = (s[i - 1] * h[i] + s[i] * h[i - 1]) / (h[i - 1] + h[i]);
    m[i] = (Math.sign(s[i - 1]) + Math.sign(s[i])) * Math.min(Math.abs(s[i - 1]), Math.abs(s[i]), 0.5 * Math.abs(q));
  }
  m[0] = (3 * s[0] - m[1]) / 2;
  m[n - 1] = (3 * s[n - 2] - m[n - 2]) / 2;
  let d = `M${f(p[0][0])},${f(p[0][1])}`;
  for (let i = 0; i < n - 1; i++) {
    const t = h[i] / 3;
    d += ` C${f(p[i][0] + t)},${f(p[i][1] + m[i] * t)} ${f(p[i + 1][0] - t)},${f(p[i + 1][1] - m[i + 1] * t)} ${f(p[i + 1][0])},${f(p[i + 1][1])}`;
  }
  return d;
}

// Les hores de la gràfica, per a la vista gran (vistaGrafica).
let HORES_GRAFICA = null;

function grafica(hores) {
  const ara = new Date();
  const files = (hores || []).filter((f) => new Date(f.fins) > ara && f.temperatura != null);
  if (files.length < 6) return null;
  HORES_GRAFICA = hores;
  // Totes les que queden (horesVista); la de «Consultes», les del dia de què
  // parla (graficaDia).
  return figuraGrafica(files,
    T('Gràfica de la previsió: perill, cel, temperatura i probabilitat de pluja. Les mateixes dades són a les taules de sota.'));
}

function figuraGrafica(files, peu) {
  const fig = element('figure', 'grafica');
  fig.append(element('figcaption', 'visualment-amagat', peu));
  fig._files = files;
  return fig;
}

// Des d'aquesta hora, el resum del dia ja és el de demà (bot.HORA_DEMA).
const HORA_DEMA = 18;

// La gràfica del dia de què parla el resum, a «Consultes» i a la imatge que
// l'acompanya a Telegram i als avisos (grafica_imatge.py; Juanjo,
// 17-10-2026): la d'«Avui», d'ara a mitjanit; la de «Demà», com el text del
// bot (bot.resum), de la nit d'avui (des de HORA_DEMA) al final de demà.
// Amb menys de 3 hores, cap.
function graficaDia(hores, riscos, dia, ara = new Date()) {
  const dies = (n, h = 0) => horaDelDia(ara, n, h);
  const [des, fins] = dia === 'dema' ? [dies(0, HORA_DEMA), dies(2)] : [ara, dies(1)];
  const files = (hores || []).filter((f) => new Date(f.fins) > ara && new Date(f.fins) > des
    && new Date(f.hora) < fins && f.temperatura != null);
  if (files.length < 3) return null;
  for (const f of files) f.riscos_hora = riscosHora(f, riscos, ara);
  const fig = figuraGrafica(files, T('Gràfica de la previsió hora a hora: perill, cel, temperatura i probabilitat de pluja.'));
  // A «Consultes», la càmera al final de la llegenda (botoImatge).
  fig._botoImatge = true;
  return fig;
}

// Hora a hora, sempre: cada hora té com a mínim COL_HORA píxels, amb el seu
// cel i la seva temperatura, i si no hi caben totes la gràfica es desplaça
// de costat, amb el dit al mòbil (Juanjo, 20-10-2026: «quiero que hagas
// siempre tot pero con barra de desplazamiento horizontal… me interesa que
// salga hora a hora, no cada 2 horas»). Les imatges (la càmera i la de
// Telegram, grafica_imatge.py) es fan compactes, a l'amplada de la pàgina
// (fig._compacte), perquè surti tot en una.
const COL_HORA = 36;

function dibuixaGrafica(fig) {
  const files = fig._files;
  // A la vista gran: més alçada i, si es tria, el vent (vistaGrafica).
  const opcions = fig._opcions || {};
  const Wv = fig.clientWidth - (parseFloat(getComputedStyle(fig).paddingLeft) || 0)
    - (parseFloat(getComputedStyle(fig).paddingRight) || 0);
  if (!(Wv > 0) || !files.length) return;
  const n = files.length;
  const W = fig._compacte ? Wv : Math.max(Wv, n * COL_HORA);
  const col = W / n;
  const x = (i) => i * col;
  // El cel, la temperatura i les hores de l'eix, cada hora si hi ha lloc
  // (Juanjo, 17-10-2026: «la gráfica está bastante vacía, mejor que salga
  // cada hora»); si no, cada 2 o cada 3.
  const pas = col >= 30 ? 1 : col >= 18 ? 2 : 3;
  // Les hores de l'eix, a part: un número ocupa uns 13 px, i amb 18 per hora
  // hi caben totes; si no, de dues en dues (Juanjo, 20-10-2026: «en 24h y en
  // avui, ¿no caben todas las h en el eje x?»). Abans seguien el pas del cel.
  const pasEix = col >= 18 ? 1 : col >= 9 ? 2 : 3;
  const hora = (f) => horaLocal(f.hora);
  // A la pàgina des del principi: el text dels avisos s'ha de poder mesurar.
  // Dins d'una caixa que es desplaça de costat; en tornar a dibuixar, es
  // queda on era.
  const g = svg('svg', { width: W, 'aria-hidden': 'true' });
  let caixa = fig.querySelector('.g-desplaca');
  if (!caixa) {
    caixa = element('div', 'g-desplaca');
    // Amb el teclado, les fletxes la desplacen.
    caixa.tabIndex = 0;
    caixa.setAttribute('role', 'region');
    caixa.setAttribute('aria-label', T('Gràfica hora a hora: es desplaça de costat'));
    fig.prepend(caixa);
    caixa.addEventListener('scroll', () => {
      fig._amaga?.();
      caixa.classList.toggle('al-final', caixa.scrollLeft + caixa.clientWidth >= caixa.scrollWidth - 2);
    }, { passive: true });
  }
  const abans = caixa.scrollLeft;
  caixa.querySelector('svg')?.remove();
  caixa.append(g);
  caixa.scrollLeft = abans;
  caixa.classList.toggle('desplaca', W > Wv + 1);
  caixa.classList.toggle('al-final', caixa.scrollLeft + caixa.clientWidth >= caixa.scrollWidth - 2);
  const mesura = (text) => {
    const prova = svg('g', { class: 'g-avis' });
    const t = svg('text', {}, text);
    prova.append(t);
    g.append(prova);
    const llarg = t.getComputedTextLength();
    prova.remove();
    return llarg;
  };
  // Els avisos, una fila per font i fenomen (filesAvis): el nom, a l'esquerra
  // de la barra si hi cap (Juanjo, 19-10-2026: «en el caso de que quepa se
  // podría poner delante? así ahorramos una fila más»); si no, a la dreta
  // del darrer tram, si hi cap (Juanjo: «que te parece poner el servicio
  // que da el aviso a la derecha si hay espacio y no cabe a la izquierda?»),
  // i si tampoc, a sobre.
  const filesA = filesAvis(files);
  const ambAvis = filesA.length > 0;
  const yAvis = 0;
  const hNom = 13;
  const hBarra = 16;
  let yFila = yAvis;
  for (const fila of filesA) {
    fila.nom = `${NOM_FONT()[fila.font] || fila.font} · ${fila.noms.join(', ')}`;
    const llarg = mesura(fila.nom);
    // A l'historial, que es desplaça fins al final, el nom sempre a sobre i a
    // l'esquerra de la part que es veu (amb les xifres fixes, més avall): al
    // costat de la barra, quedava fora de la vista (ADR 0124).
    fila.fix = Boolean(opcions.historial) && W > Wv + 1;
    fila.davant = !fila.fix && x(fila.trams[0].ini) - 6 >= llarg;
    fila.darrere = !fila.fix && !fila.davant && x(fila.trams[fila.trams.length - 1].fi) + 6 + llarg <= W;
    fila.y = yFila;
    fila.yBarra = fila.davant || fila.darrere ? yFila : yFila + hNom;
    yFila = fila.yBarra + hBarra + 4;
  }
  const hAvis = ambAvis ? yFila - 4 - yAvis : 0;
  const yDia = hAvis + (ambAvis ? 6 : 0);
  const yCel = yDia + 16;
  const hCel = 28;
  // La temperatura i la pluja comparteixen la zona: les barres darrere de la
  // línia, com als meteogrames habituals (Juanjo, 16-10-2026).
  // El cel queda a part, a dalt: les barres no hi arriben (Juanjo, 16-10-2026).
  // Sota cada icona, la temperatura d'aquella hora (Juanjo, 16-10-2026: «no
  // quedaría bien la temperatura bajo el cielo?»).
  const yXifra = yCel + hCel + 13;
  // A la vista en gran, més alta; al mòbil, menys, perquè la gràfica i les
  // seves opcions hi càpiguen sense desplaçar (Juanjo, 19-10-2026: «ocupa
  // mucho espacio vertical, se puede optimizar?»).
  const hTemp = opcions.gran ? Math.round(Math.min(260, Math.max(110, innerHeight * (innerWidth <= 600 ? 0.22 : 0.32)))) : 100;
  // El vent, a sota de la pluja, amb el mateix eix d'hores.
  // A la vista en gran, el que s'hi tria; a la resta, el que s'hi va triar
  // (per defecte, amb vent). Sense dades de vent, res.
  const ambVent = (opcions.gran ? opcions.vent : opcions.vent ?? ambVentTriat()) && files.some((f) => f.vent != null);
  const hVent = ambVent ? (opcions.gran ? 70 : 50) : 0;
  // La temperatura de la zona triada amb el botó de dalt (zonaTriada, ADR
  // 0123), dibuixada igual a les dues: el botó ja diu quina és (Juanjo,
  // 23-10-2026: «se puede hacer todo igual sin distinción»). Sense la part
  // alta (les hores passades), la de baix.
  const ambAlta = zonaTriada() === 'alta' && files.some((f) => f.dif_alta != null && !f.mesura);
  const ambBaixa = !ambAlta;
  const yTemp = yXifra + 12;
  const yPluja = yTemp;
  const hPluja = hTemp;
  // La nit, de la posta a la sortida (a mitja hora de cada tram): l'ombra i
  // l'UV, que de nit no surt.
  const esNit = files.map((f) => alturaSol(new Date(new Date(f.hora).getTime() + 18e5)) < 0);
  // La humitat i l'índex UV, a sota del vent, si es trien (Juanjo, 21-10-2026:
  // «haz el UV y la humedad»); com el vent, per defecte no.
  const ambHumitat = (opcions.gran ? opcions.humitat : opcions.humitat ?? humitatTriada())
    && files.some((f) => f.humitat != null);
  // La pressió, a sota de la humitat (Juanjo, 21-10-2026: «Es facil añadir
  // la presión?»).
  const ambPressio = (opcions.gran ? opcions.pressio : opcions.pressio ?? pressioTriada())
    && files.some((f) => f.pressio != null);
  // Els núvols, entre la pressió i l'UV, que en depèn (Juanjo, 21-10-2026:
  // «se puede poner el % de cobertura de nubes en el grafico?»).
  const ambNuvols = (opcions.gran ? opcions.nuvols : opcions.nuvols ?? nuvolsTriats())
    && files.some((f) => f.nuvols != null);
  const ambUv = (opcions.gran ? opcions.uv : opcions.uv ?? uvTriat())
    && files.some((f, i) => !esNit[i] && f.uv != null);
  // La xifra de sota cada icona, la de la zona triada.
  const tempXifra = (f) => (f.temperatura == null ? null : ambBaixa ? f.temperatura
    : !f.mesura ? f.temperatura + (f.dif_alta || 0) : null);
  const yVent = yPluja + hPluja + (hVent ? 12 : 0);
  const fiVent = hVent ? yVent + hVent : yPluja + hPluja;
  const hHumitat = ambHumitat ? (opcions.gran ? 60 : 44) : 0;
  const yHumitat = fiVent + (hHumitat ? 14 : 0);
  const fiHumitat = hHumitat ? yHumitat + hHumitat : fiVent;
  const hPressio = ambPressio ? (opcions.gran ? 60 : 44) : 0;
  const yPressio = fiHumitat + (hPressio ? 14 : 0);
  const fiPressio = hPressio ? yPressio + hPressio : fiHumitat;
  const hNuvols = ambNuvols ? (opcions.gran ? 48 : 36) : 0;
  const yNuvols = fiPressio + (hNuvols ? 14 : 0);
  const fiNuvols = hNuvols ? yNuvols + hNuvols : fiPressio;
  const hUv = ambUv ? 16 : 0;
  const yUv = fiNuvols + (hUv ? 6 : 0);
  const baix = hUv ? yUv + hUv : fiNuvols;
  const yEix = baix + 16;
  const H = yEix + 4;
  g.setAttribute('height', H);
  g.setAttribute('viewBox', `0 0 ${W} ${H}`);

  // La nit, ombrejada, en un sol rectangle per nit.
  for (let i = 0; i < n; i++) {
    if (!esNit[i] || (i && esNit[i - 1])) continue;
    let j = i;
    while (j < n && esNit[j]) j++;
    g.append(svg('rect', { class: 'g-nit', x: x(i), y: yCel - 2, width: x(j) - x(i), height: baix - yCel + 2 }));
  }

  // Mitjanit: la ratlla que separa els dies, i el nom de cada dia.
  // Cada dia pel seu nom, segons la data: de nit, la taula arriba fins a
  // demà passat (Juanjo, 17-10-2026: «el 2º demà debería haber sido demà
  // passat»). El primer nom, només si hi cap abans de mitjanit: si no, ja
  // s'entén («si avui no cabe no se escriba nada»).
  const nomDia = (f) => {
    const d = new Date(f.hora);
    const dies = diesEntre(new Date(), d);
    // Els dies de l'historial (enrere), «Ahir» o el nom del dia de la setmana.
    if (dies < -1) return d.toLocaleDateString(IDIOMA.codi === 'es' ? 'es' : 'ca', { weekday: 'long', timeZone: ZONA_HORA });
    return dies === -1 ? T('Ahir') : dies === 0 ? T('Avui') : dies === 1 ? T('Demà') : T('Demà passat');
  };
  const mitjanits = files.map((f, i) => (i && hora(f) === 0 ? i : null)).filter((i) => i != null);
  const primer = svg('text', { class: 'g-dia', x: 2, y: yDia + 11 }, nomDia(files[0]));
  g.append(primer);
  const etiquetesDia = [primer];
  if (mitjanits.length && 2 + primer.getComputedTextLength() + 8 > x(mitjanits[0])) {
    primer.remove();
    etiquetesDia.pop();
  }
  for (const i of mitjanits) {
    g.append(svg('line', { class: 'g-mitjanit', x1: x(i), x2: x(i), y1: yDia, y2: baix }));
    const t = svg('text', { class: 'g-dia', x: x(i) + 4, y: yDia + 11 }, nomDia(files[i]));
    g.append(t);
    etiquetesDia.push(t);
  }
  // La fase principal de la Lluna, només a l'hora en què passa (Juanjo,
  // 25-10-2026; ADR 0127): a mitja alçada de la zona de la temperatura, amb
  // el nom al costat sobre el fons de la gràfica, que no la tapi la corba
  // (Juanjo, 25-10-2026: «por enmedio del grafico … con una etiqueta visible
  // indicando la fase»). Es posa damunt de tot, també de les zones de les hores.
  const llunesGrafica = [];
  const ambLluna = opcions.gran ? opcions.lluna !== false : opcions.lluna ?? llunaTriada();
  for (const fase of (ambLluna && LLUNA && LLUNA.fases) || []) {
    const t = new Date(fase.hora);
    const i = files.findIndex((f) => new Date(f.hora) <= t && t < new Date(f.fins));
    if (i < 0) continue;
    const mida = 14;
    const cx = x(i) + col / 2;
    const cy = yTemp + hTemp / 2;
    const lluna = dibuixLluna(ANGLE_FASE[fase.fase]);
    for (const [k, v] of Object.entries({ x: cx - mida / 2, y: cy - mida / 2, width: mida, height: mida })) lluna.setAttribute(k, v);
    const nom = NOM_FASE_LLUNA()[fase.fase];
    const text = `${nom}: ${quanFase(fase.hora)}`;
    // Porta a la Lluna de «Consultes» (Juanjo, 25-10-2026); per això va damunt
    // de les zones de les hores.
    // Fora del teclat: la gràfica és amagada als lectors de pantalla i s'hi
    // arriba també des de la línia de la fase d'«Ara».
    const grup = svg('a', { class: 'g-lluna', href: 'consultes.html#lluna', tabindex: '-1' });
    const fons = svg('rect', { class: 'g-lluna-fons', y: cy - 10, height: 20, rx: 5 });
    const etiqueta = svg('text', { class: 'g-lluna-nom', x: cx + mida / 2 + 4, y: cy + 4 }, nom);
    grup.append(fons, lluna, etiqueta, svg('title', {}, text));
    grup.setAttribute('aria-label', text);
    g.append(grup);
    // El nom, a la dreta; si no hi cap, a l'esquerra.
    const llarg = etiqueta.getComputedTextLength();
    let esq = cx - mida / 2 - 4;
    let dre = cx + mida / 2 + 4 + llarg + 4;
    if (dre > W - 2) {
      etiqueta.setAttribute('x', cx - mida / 2 - 4);
      etiqueta.setAttribute('text-anchor', 'end');
      esq = cx - mida / 2 - 4 - llarg - 4;
      dre = cx + mida / 2 + 4;
    }
    fons.setAttribute('x', esq);
    fons.setAttribute('width', dre - esq);
    llunesGrafica.push(grup);
  }

  // Les files dels avisos: el nom (davant o a sobre) i els trams de cada
  // nivell, un darrere l'altre; el nivell dins del tram si hi cap, i sencer
  // en tocar-lo.
  filesA.forEach((fila) => {
    const y = fila.yBarra - hNom;
    const x0f = x(fila.trams[0].ini);
    if (fila.davant) {
      g.append(svg('text', { class: 'g-avis-nom', x: x0f - 5, y: fila.yBarra + 12, 'text-anchor': 'end' }, fila.nom));
    } else if (fila.darrere) {
      g.append(svg('text', { class: 'g-avis-nom', x: x(fila.trams[fila.trams.length - 1].fi) + 5, y: fila.yBarra + 12 },
        fila.nom));
    } else if (fila.fix) {
      g.append(svg('text', { class: 'g-avis-nom g-nom-fix', x: 2, y: fila.y + 10 }, fila.nom));
    } else {
      g.append(svg('text', { class: 'g-avis-nom', x: x0f > W / 2 ? W - 2 : Math.max(2, x0f),
        y: fila.y + 10, 'text-anchor': x0f > W / 2 ? 'end' : 'start' }, fila.nom));
    }
    for (const t of fila.trams) {
      const x0 = x(t.ini) + (t.ini && fila.trams.some((u) => u.fi === t.ini) ? 0 : 1);
      const x1 = x(t.fi) - (fila.trams.some((u) => u.ini === t.fi) ? 0 : 1);
      const p = { nivell: t.nivell, perFont: [[fila.font, fila.noms, t.nivell]] };
      const grup = svg('g', { class: `g-avis ${t.nivell}` });
      grup.append(svg('rect', { x: x0, y: y + hNom, width: Math.max(1, x1 - x0), height: hBarra, rx: 3 }));
      // Els plans, la fase; els incendis, res (el nom de la fila ja ho diu).
      const FASE_NIVELL = { groc: 'prealerta', taronja: 'alerta', vermell: 'emergència' };
      const etiqueta = fila.font === 'meteocat' ? GRAU_METEOCAT()[t.nivell] : fila.font === 'pc' ? TD(FASE_NIVELL[t.nivell])
        : fila.font === 'bombers' ? '' : TD(t.nivell);
      if (etiqueta && mesura(etiqueta) + 8 <= x1 - x0) {
        grup.append(svg('text', { x: (x0 + x1) / 2, y: y + hNom + 12, 'text-anchor': 'middle' }, etiqueta));
      }
      const complet = textPerill(p);
      grup.append(svg('title', {}, complet));
      grup.addEventListener('click', () => avisBreu(`${complet}.`));
      g.append(grup);
    }
  });

  // El cel, un per bloc de 3 h (o de 2, si hi ha lloc), al centre del bloc.
  for (let i = 0; i < n;) {
    let j = i + 1;
    while (j < n && hora(files[j]) % pas !== 0) j++;
    const c = celBloc(files.slice(i, j));
    const amplada = (j - i) * col;
    if (c && amplada >= 20) {
      const mida = Math.min(24, amplada - 6);
      const cx = x(i) + amplada / 2;
      const ic = svg('use', { href: '#' + c[1], x: cx - mida / 2, y: yCel + (hCel - mida) / 2, width: mida, height: mida, class: 'g-cel' });
      g.append(ic);
      const mig = files[Math.floor((i + j - 1) / 2)];
      if (tempXifra(mig) != null) {
        // La de dalt, amb el seu color (Juanjo, 21-10-2026: «para
        // distinguirlos debe mantener su color»).
        g.append(svg('text', { class: 'g-xifra', x: cx, y: yXifra, 'text-anchor': 'middle' },
          `${Math.round(tempXifra(mig))}°`));
      }
    }
    i = j;
  }

  // La temperatura, primer el farciment (darrere de les barres) i després la
  // línia (davant), sense xifres: són sota el cel.
  // Les hores passades (historial.py) porten la temperatura mesurada, que pot
  // faltar, i la de la previsió de les 7 (prev), en una corba tènue; la part
  // alta, només a les previstes.
  const valid = (v) => v != null && !Number.isNaN(v);
  const baixes = files.map((f) => f.temperatura);
  const temps = ambBaixa ? baixes.filter(valid) : [];
  const altes = ambAlta ? files.map((f) => (f.mesura || f.temperatura == null ? null : f.temperatura + (f.dif_alta || 0))) : [];
  const previstes = files.map((f) => (f.mesura && f.prev ? f.prev.temperatura : null));
  const ambPrev = previstes.some(valid);
  const ambTemp = [...temps, ...altes].some(valid);
  // La màxima toca la ratlla del sostre de la pluja, que porta a l'esquerra
  // la seva xifra: una sola ratlla per al màxim de les dues escales (Juanjo,
  // 17-10-2026: «la temperatura debe llegar al máximo de la lluvia y poner
  // esa temperatura máxima a la izquierda»), la de la zona triada.
  const escala = [...(ambTemp ? [...temps, ...altes] : baixes), ...previstes].filter(valid);
  if (!escala.length) escala.push(0, 1);
  const tMax = Math.max(...escala);
  const tMin = Math.min(Math.floor(Math.min(...escala)) - 1, tMax - 2);
  const ySostre = yPluja + 14;
  const yT = (t) => yTemp + hTemp - ((t - tMin) / (tMax - tMin)) * (yTemp + hTemp - ySostre);
  // El farciment, sota la corba de la zona triada. Les hores sense dada, fora.
  const corbaDe = (vals) => {
    const p = vals.map((v, i) => [x(i) + col / 2, v]).filter(([, v]) => valid(v)).map(([a, v]) => [a, yT(v)]);
    return p.length > 1 ? { p, d: corbaSuau(p) } : null;
  };
  const principal = corbaDe(ambBaixa ? baixes : altes);
  const punts = principal ? principal.p : [[0, 0], [0, 0]];
  const corba = principal ? principal.d : '';
  const base = yPluja + hPluja;
  const idGrad = 'g-temp-grad';
  const defs = svg('defs');
  const grad = svg('linearGradient', { id: idGrad, x1: 0, y1: 0, x2: 0, y2: 1 });
  grad.append(svg('stop', { offset: 0, class: 'g-grad-dalt' }), svg('stop', { offset: 1, class: 'g-grad-baix' }));
  defs.append(grad);
  // Les hores en què potser va plovisquejar (historial), ratllades.
  const idRatlles = 'g-pluja-ratlles';
  const ratlles = svg('pattern', { id: idRatlles, width: 4, height: 4, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
  ratlles.append(svg('line', { class: 'g-ratlla', x1: 0, y1: 0, x2: 0, y2: 4 }));
  defs.append(ratlles);
  g.append(defs);
  if (ambTemp && principal) {
    g.append(svg('path', { class: 'g-temp-area', fill: `url(#${idGrad})`,
      d: `${corba} L${punts[punts.length - 1][0].toFixed(1)},${base} L${punts[0][0].toFixed(1)},${base} Z` }));
  }

  // La pluja: una barra per hora, tan alta com els mil·límetres; plena si és
  // probable (del 50 % amunt) i clara si només és possible (del 20 %), els
  // mateixos llindars que el cel de la taula. Per sota, cap barra.
  g.append(svg('line', { class: 'g-base', x1: 0, x2: W, y1: base, y2: base }));
  // Dalt de tot queda lloc per a la xifra dels mm.
  // La pluja prevista de les hores passades («Fiabilitat») també cap a l'escala.
  const plujaPrevista = (f) => (f.mesura && f.prev && f.prev.mm > 0 ? f.prev.mm : 0);
  const ambPrevMm = files.some((f) => plujaPrevista(f) > 0);
  const sostre = sostrePluja([...files, ...files.filter(plujaPrevista).map((f) => ({ pluja_mm: plujaPrevista(f), probabilitat: 1 }))]);
  const dalt = (f) => yPluja + hPluja - Math.max(3, alcadaPluja(f.pluja_mm || 0, sostre) * (hPluja - 14));
  // El sostre, una ratlla fina amb la seva xifra, com la del vent; només si plou.
  const ambBarres = files.some((f) => plujaGrafica(f)) || ambPrevMm;
  g.append(svg('line', { class: 'g-sostre', x1: 0, x2: W, y1: ySostre, y2: ySostre }));
  // A «Fiabilitat», una escala a l'esquerra cada 2 °C: l'eix no comença a 0
  // i, sense, no se sabia quants graus separen les corbes (Juanjo,
  // 23-10-2026: «esta grafica empieza en 0? faltan referencias y valores»).
  if (opcions.escala && (ambTemp || ambPrev)) {
    for (let v = Math.ceil(tMin / 2) * 2; v < tMax - 0.6; v += 2) {
      const y = yT(v);
      if (y < base - 1) g.append(svg('line', { class: 'g-escala', x1: 0, x2: W, y1: y, y2: y }));
      g.append(svg('text', { class: 'g-mm g-escala-xifra', x: 2, y: y - 3 }, `${v}\u00a0°C`));
    }
  }
  files.forEach((f, i) => {
    const pluja = plujaGrafica(f);
    if (!pluja) return;
    const y = dalt(f);
    const intensa = intensitatPluja(f.pluja_mm || 0);
    g.append(svg('rect', { class: `g-pluja ${pluja === 'pluja' ? 'segura' : pluja}${intensa ? ' ' + intensa : ''}`,
      x: x(i) + col * 0.15, y, width: col * 0.7, height: base - y }));
  });
  // Les hores en què només una veïna va veure pluja: una barra baixa
  // ratllada, perquè es vegi on és el «potser» del resum.
  files.forEach((f, i) => {
    if (f.pluja_mm != null || f.pluja_dubte == null) return;
    const h = Math.max(8, alcadaPluja(f.pluja_dubte, sostre) * (hPluja - 14));
    g.append(svg('rect', { class: 'g-pluja-dubte', fill: `url(#${idRatlles})`,
      x: x(i) + col * 0.15, y: base - h, width: col * 0.7, height: h }));
  });
  // Els mm que deia la previsió de les hores passades, a «Fiabilitat»: una
  // vora puntejada a la seva alçada, damunt de la barra del que va ploure
  // (Juanjo, 18-10-2026: «quiero incluir los mm de lluvia predichos»).
  files.forEach((f, i) => {
    const mm = plujaPrevista(f);
    if (!mm) return;
    const y = yPluja + hPluja - Math.max(3, alcadaPluja(mm, sostre) * (hPluja - 14));
    g.append(svg('rect', { class: 'g-pluja-prev', x: x(i) + col * 0.15, y, width: col * 0.7, height: base - y }));
  });
  // Una vora del color del fons, perquè la línia es vegi damunt de les barres.
  // La previsió de les 7 de les hores passades, tènue, darrere de la mesurada.
  const prev = ambPrev && corbaDe(previstes);
  if (prev) g.append(svg('path', { class: 'g-prev', d: prev.d }));
  if (ambBaixa && principal) {
    g.append(svg('path', { class: 'g-temp-vora', d: corba }));
    g.append(svg('path', { class: 'g-temp', d: corba }));
  }
  const corbaAlta = ambAlta && corbaDe(altes);
  if (corbaAlta) {
    g.append(svg('path', { class: 'g-temp-vora', d: corbaAlta.d }), svg('path', { class: 'g-temp', d: corbaAlta.d }));
  }
  if (ambBarres) g.append(svg('text', { class: 'g-mm g-sostre-xifra', x: W - 2, y: ySostre - 3, 'text-anchor': 'end' }, `${sostre}\u00a0mm`));
  if (ambTemp) {
    g.append(svg('text', { class: 'g-mm g-sostre-xifra g-sostre-temp', x: 2, y: ySostre - 3 },
      `${Math.round(tMax)}\u00a0°C`));
  }

  // El vent i les ratxes, en km/h: una ratlla a dalt amb la xifra de l'escala,
  // de 10 en 10 (20 com a mínim, perquè un dia calmat no sembli de vent).
  if (hVent) {
    const vents = files.flatMap((f) => [f.vent, f.ratxa]).filter((v) => v != null);
    const vDalt = Math.max(20, Math.ceil(Math.max(0, ...vents) / 10) * 10);
    const yV = (v) => yVent + hVent - (Math.max(0, v) / vDalt) * hVent;
    g.append(svg('line', { class: 'g-vent-escala', x1: 0, x2: W, y1: yVent, y2: yVent }));
    g.append(svg('line', { class: 'g-base', x1: 0, x2: W, y1: fiVent, y2: fiVent }));
    g.append(svg('text', { class: 'g-vent-xifra', x: 2, y: yVent - 3 }, `${vDalt}\u00a0km/h`));
    const linia = (camp, classe) => {
      const p = files.map((f, i) => [x(i) + col / 2, f[camp]]).filter(([, v]) => v != null).map(([a, v]) => [a, yV(v)]);
      if (p.length > 1) g.append(svg('path', { class: classe, d: corbaSuau(p) }));
    };
    linia('ratxa', 'g-ratxa');
    linia('vent', 'g-vent');
  }

  // La humitat relativa: la ratlla de dalt és el 100 % i la de baix, la
  // desena per sota de la mínima, amb la seva xifra; de 0 a 100, un dia de
  // 55 a 95 % semblava pla.
  if (hHumitat) {
    const hums = files.map((f) => f.humitat).filter((v) => v != null);
    const hBaix = Math.min(90, Math.floor(Math.min(...hums) / 10) * 10);
    const yH = (v) => yHumitat + hHumitat - ((Math.min(100, Math.max(hBaix, v)) - hBaix) / (100 - hBaix)) * hHumitat;
    g.append(svg('line', { class: 'g-vent-escala', x1: 0, x2: W, y1: yHumitat, y2: yHumitat }));
    g.append(svg('line', { class: 'g-base', x1: 0, x2: W, y1: fiHumitat, y2: fiHumitat }));
    g.append(svg('text', { class: 'g-vent-xifra', x: 2, y: yHumitat - 3 }, T('Humitat, 100\u00a0%')));
    if (hBaix > 0) g.append(svg('text', { class: 'g-vent-xifra', x: 2, y: fiHumitat - 3 }, `${hBaix}\u00a0%`));
    const p = files.map((f, i) => [x(i) + col / 2, f.humitat]).filter(([, v]) => v != null).map(([a, v]) => [a, yH(v)]);
    if (p.length > 1) g.append(svg('path', { class: 'g-humitat', d: corbaSuau(p) }));
  }

  // La pressió, en hPa al nivell del mar: d'una hora a l'altra canvia poc, i
  // amb una escala fixa la línia sortiria plana. L'escala s'ajusta als dies
  // de la gràfica: a dalt, l'hPa sencer de sobre la màxima; la mínima, a un
  // terç de l'alçada, perquè la línia no tapi la xifra de baix; i 6 hPa com
  // a mínim, perquè un dia quiet no sembli un daltabaix.
  if (hPressio) {
    const ps = files.map((f) => f.pressio).filter((v) => v != null);
    const pMin = Math.min(...ps);
    const pMax = Math.ceil(Math.max(...ps));
    const pBaix = Math.floor(pMin - Math.max(pMax - pMin, 3) / 2);
    const pDalt = Math.max(pMax, pBaix + 6);
    const yP = (v) => yPressio + hPressio - ((v - pBaix) / (pDalt - pBaix)) * hPressio;
    g.append(svg('line', { class: 'g-vent-escala', x1: 0, x2: W, y1: yPressio, y2: yPressio }));
    g.append(svg('line', { class: 'g-base', x1: 0, x2: W, y1: fiPressio, y2: fiPressio }));
    g.append(svg('text', { class: 'g-vent-xifra', x: 2, y: yPressio - 3 }, T`Pressió, ${pDalt}\u00a0hPa`));
    g.append(svg('text', { class: 'g-vent-xifra', x: 2, y: fiPressio - 3 }, `${pBaix}\u00a0hPa`));
    const p = files.map((f, i) => [x(i) + col / 2, f.pressio]).filter(([, v]) => v != null).map(([a, v]) => [a, yP(v)]);
    if (p.length > 1) g.append(svg('path', { class: 'g-pressio', d: corbaSuau(p) }));
  }

  // Els núvols, una barra grisa per hora, del 0 al 100 % sempre: un 30 %
  // s'ha de veure igual de baix cada dia. El mateix valor que tria la icona
  // (nuvolsHora), perquè la barra no digui poc sota una icona de pluja.
  if (hNuvols) {
    g.append(svg('line', { class: 'g-vent-escala', x1: 0, x2: W, y1: yNuvols, y2: yNuvols }));
    g.append(svg('line', { class: 'g-base', x1: 0, x2: W, y1: fiNuvols, y2: fiNuvols }));
    g.append(svg('text', { class: 'g-vent-xifra', x: 2, y: yNuvols - 3 }, T('Cel tapat pels núvols, 100\u00a0%')));
    files.forEach((f, i) => {
      if (f.nuvols == null) return;
      const h = (Math.min(100, Math.max(0, nuvolsHora(f))) / 100) * hNuvols;
      if (h < 0.5) return;
      g.append(svg('rect', { class: 'g-nuvols', x: x(i) + 0.5, y: fiNuvols - h, width: Math.max(1, col - 1), height: h }));
    });
  }

  // L'índex UV, una casella per hora de dia amb el color de l'OMS i la xifra
  // si hi cap, com al «Sol» de «Consultes».
  if (hUv) {
    files.forEach((f, i) => {
      if (esNit[i] || f.uv == null) return;
      const uv = Math.round(f.uv);
      // A trenc d'alba i al vespre, 0: sense casella, com de nit.
      if (!uv) return;
      const [, classe] = UV().find(([lim]) => uv <= lim);
      g.append(svg('rect', { class: `g-uv ${classe}`, x: x(i) + 0.5, y: yUv, width: Math.max(1, col - 1), height: hUv, rx: 2 }));
      if (col >= 14) {
        g.append(svg('text', { class: `g-uv-xifra ${classe}`, x: x(i) + col / 2, y: yUv + 12, 'text-anchor': 'middle' }, String(uv)));
      }
    });
  }

  // Els mil·límetres, només on la pluja és més forta de cada episodi, a sobre
  // de la barra; si hi ha una xifra de temperatura, a dins de la barra o al
  // costat, on no se superposi. Si no hi cap sense trepitjar cap altra xifra
  // (al mòbil, dos episodis seguits), no s'escriu: surt a la fitxa de l'hora.
  const xifres = [...g.querySelectorAll('.g-xifra, .g-sostre-xifra')].map((t) => t.getBBox());
  const xoca = (b) => xifres.some((c) => b.x < c.x + c.width + 4 && c.x < b.x + b.width + 4 && b.y < c.y + c.height && c.y < b.y + b.height);
  files.forEach((f, i) => {
    const mm = f.pluja_mm || 0;
    if (mm < 0.5 || !plujaHora(f)) return;
    const veins = files.slice(Math.max(0, i - 2), i + 3).map((v) => v.pluja_mm || 0);
    if (mm < Math.max(...veins) || files.slice(Math.max(0, i - 2), i).some((v) => (v.pluja_mm || 0) === mm)) return;
    const t = svg('text', { class: 'g-mm', 'text-anchor': 'middle' },
      `${mm >= 10 ? Math.round(mm) : coma(Math.round(mm * 10) / 10)}\u00a0mm`);
    g.append(t);
    const cx = x(i) + col / 2;
    const llarg = t.getComputedTextLength();
    const llocs = [[cx, dalt(f) - 4], [cx, dalt(f) + 14], [cx - llarg / 2 - col, dalt(f) + 4], [cx + llarg / 2 + col, dalt(f) + 4]];
    const lloc = llocs.find(([lx, ly]) => {
      t.setAttribute('x', Math.min(Math.max(lx, llarg / 2 + 1), W - llarg / 2 - 1));
      t.setAttribute('y', ly);
      return !xoca(t.getBBox());
    });
    if (lloc) xifres.push(t.getBBox());
    else t.remove();
  });

  // Les xifres del sostre (els mm, a la dreta, i la màxima, a l'esquerra),
  // sempre a la vista: si la gràfica es desplaça de costat, van en una capa
  // fixa damunt de la caixa, a les vores de la part que es veu (Juanjo,
  // 20-10-2026: «se puede hacer que estos dos valores estén siempre
  // visibles?»). A la imatge (compacta), dins de la gràfica, com abans.
  fig.querySelector('.g-fixes')?.remove();
  // També l'escala de graus (l'historial i «Fiabilitat»), que es perdia en
  // desplaçar la gràfica fins al final (ADR 0124).
  const sostreXifres = g.querySelectorAll('.g-sostre-xifra, .g-escala-xifra, .g-nom-fix');
  if (W > Wv + 1 && sostreXifres.length) {
    const visible = caixa.clientWidth;
    const fixes = svg('svg', { class: 'g-fixes', width: visible, height: H, viewBox: `0 0 ${visible} ${H}`, 'aria-hidden': 'true' });
    for (const t of sostreXifres) {
      if (t.getAttribute('text-anchor') === 'end') t.setAttribute('x', visible - 2);
      fixes.append(t);
    }
    // La mida, la del dibuix: la regla general de les gràfiques l'estiraria.
    Object.assign(fixes.style, { top: `${caixa.offsetTop}px`, left: `${caixa.offsetLeft}px`,
      width: `${visible}px`, height: `${H}px` });
    fig.append(fixes);
  }

  // L'eix, natural: només les hores en punt, al pas que hi cap (pasEix), sense
  // res diferent al principi (Juanjo, 20-10-2026: «quita el ara del gráfico»
  // i «el eje x normal, sin números de más o menos al principio»). Amb hores
  // passades al davant (l'historial), una ratlla on comença la previsió; un
  // dia passat sencer no en porta.
  const iAra = files.findIndex((f) => !f.mesura);
  if (iAra > 0) g.append(svg('line', { class: 'g-ara', x1: x(iAra), x2: x(iAra), y1: yCel - 2, y2: baix }));
  // Una marca a cada hora: llarga i amb el número a les que toquen; curta i
  // sense número a la resta (Juanjo, 16-10-2026).
  files.forEach((f, i) => {
    if (!i) return;
    const gran = hora(f) % pasEix === 0;
    g.append(svg('line', { class: gran ? 'g-marca' : 'g-marca petita', x1: x(i), x2: x(i),
      y1: baix, y2: baix + (gran ? 4 : 2) }));
    if (!gran || x(i) < 8 || x(i) > W - 8) return;
    g.append(svg('text', { class: 'g-hora', x: x(i), y: yEix, 'text-anchor': 'middle' }, String(hora(f))));
  });
  // Tocar una hora (o passar-hi el ratolí): una fitxa amb tota la previsió
  // d'aquella hora, perquè a la gràfica no hi cap (Juanjo, 16-10-2026: «solo
  // pone la lluvia del mayor?»; 17-10-2026: «no se podrían añadir el resto de
  // datos?»). La part alta, la neu i l'UV, només quan diuen alguna cosa. Es
  // treu tocant fora o la mateixa hora.
  // La fitxa és fora de la caixa que es desplaça, damunt de la figura, perquè
  // no quedi retallada; a la gràfica, només la columna marcada.
  const retol = svg('g', { class: 'g-retol' });
  let fitxa = fig.querySelector('.g-fitxa');
  if (!fitxa) {
    fitxa = element('div', 'g-fitxa');
    fitxa.setAttribute('aria-hidden', 'true');
    fig.append(fitxa);
  }
  fitxa.hidden = true;
  let actiu = null;
  const amaga = () => {
    actiu = null;
    retol.replaceChildren();
    fitxa.hidden = true;
  };
  const liniesFitxa = (f, i) => {
    // Una hora passada: el que es va mesurar i el que deia la previsió de les 7.
    if (f.mesura) {
      const linies = [T`${hora(f)}\u00a0h · Mesurat`];
      const p = f.prev || {};
      const previst = (v, t) => (v == null ? '' : t);
      linies.push(f.temperatura == null ? T('Temperatura: sense mesura')
        : T`Temperatura: ${Math.round(f.temperatura)}\u00a0°C`
          + previst(p.temperatura, T` (prevista: ${Math.round(p.temperatura ?? 0)}\u00a0°C)`)
          + (f.sol ? T(' · sol sobre el termòmetre, no compta') : ''));
      const mm = (v) => (v >= 10 ? String(Math.round(v)) : v < 0.05 ? '0' : coma(Math.round(v * 10) / 10));
      const mmPrevist = p.mm == null ? '' : T`, ${mm(p.mm)}\u00a0mm`;
      const plujaNul = f.pluja_dubte != null
        ? T`Pluja: potser va plovisquejar (només una estació veïna, ${mm(f.pluja_dubte)}\u00a0mm)`
        : T('Pluja: no se sap');
      linies.push(f.pluja_mm == null ? plujaNul : T`Pluja: ${mm(f.pluja_mm)}\u00a0mm`
        + previst(p.probabilitat, T` (prevista: ${Math.round((p.probabilitat ?? 0) * 100)}\u00a0%${mmPrevist})`));
      // La resta del que es mesura (ADR 0124), amb on, si no és al barri.
      if (f.vent != null) {
        linies.push(T`Vent a Sant Cugat: ${f.vent}\u00a0km/h` + (f.ratxa != null ? T`, ratxes de ${f.ratxa}\u00a0km/h` : ''));
      }
      if (f.humitat != null) linies.push(T`Humitat: ${f.humitat}\u00a0%`);
      if (f.pressio != null) linies.push(T`Pressió: ${Math.round(f.pressio)}\u00a0hPa`);
      if (f.nuvols != null) linies.push(T`Cel tapat a Sabadell: ${f.nuvols}\u00a0%`);
      // Les alertes que hi havia (ADR 0124).
      const alertes = avisHora(f);
      if (alertes) linies.push(textPerill(alertes));
      return linies;
    }
    const [textCel] = f.plou_ara ? [T('Plou ara')] : cel(f);
    const linies = [textCel ? T`${hora(f)}\u00a0h · ${textCel}` : T`${hora(f)}\u00a0h`];
    linies.push(T`Temperatura: ${Math.round(tempZona(f))}\u00a0°C`);
    // Els mm com a la xifra de la barra: sense decimals a partir de 10.
    const v = f.pluja_mm || 0;
    const mm = v >= 10 ? String(Math.round(v)) : v < 0.05 ? '0' : coma(Math.round(v * 10) / 10);
    linies.push(f.probabilitat == null ? T`Pluja: ${mm}\u00a0mm`
      : T`Pluja: ${mm}\u00a0mm · ${Math.round(f.probabilitat * 100)}\u00a0%`);
    if ((f.neu || 0) >= 0.1) linies.push(T`Neu: ${coma(f.neu)}\u00a0cm`);
    if (f.vent != null) {
      linies.push(T`Vent: ${Math.round(f.vent)}\u00a0km/h` + (f.ratxa ? T`, ratxes de ${Math.round(f.ratxa)}\u00a0km/h` : ''));
    }
    if (f.humitat != null) linies.push(T`Humitat: ${f.humitat}\u00a0%`);
    if (f.pressio != null) linies.push(T`Pressió: ${Math.round(f.pressio)}\u00a0hPa`);
    if (f.nuvols != null) linies.push(T`Cel tapat: ${Math.round(nuvolsHora(f))}\u00a0%`);
    // L'UV, de dia i des de 3, quan l'OMS ja recomana protegir-se; amb la
    // franja de l'UV a la vista, també el baix, perquè la casella i la fitxa
    // diguin el mateix.
    if (!esNit[i] && f.uv != null && (hUv || Math.round(f.uv) >= 3)) linies.push(T`Índex UV: ${Math.round(f.uv)}`);
    return linies;
  };
  const mostra = (i) => {
    actiu = i;
    retol.replaceChildren(svg('rect', { class: 'g-retol-columna', x: x(i), y: yCel - 2, width: col,
      height: baix - yCel + 2 }));
    fitxa.replaceChildren(...liniesFitxa(files[i], i).map((l, k) => element('span', k ? null : 'titol', l)));
    fitxa.hidden = false;
    // Al costat de la columna, on hi hagi lloc dins del que es veu, perquè no
    // tapi l'hora triada; si no hi cap per cap costat, sota l'eix, damunt de
    // la llegenda.
    const ample = fitxa.offsetWidth;
    const esq = caixa.offsetLeft + x(i) - caixa.scrollLeft;
    const dreta = esq + col;
    const total = fig.clientWidth;
    let fx = dreta + 6;
    let fy = caixa.offsetTop + yCel;
    if (fx + ample > total - 4) fx = esq - 6 - ample;
    if (fx < 4) {
      fx = Math.min(Math.max(esq + col / 2 - ample / 2, 4), total - ample - 4);
      fy = caixa.offsetTop + yEix + 8;
    }
    fitxa.style.left = `${fx}px`;
    fitxa.style.top = `${fy}px`;
  };
  files.forEach((f, i) => {
    const zona = svg('rect', { class: 'g-zona', x: x(i), y: yCel - 2, width: col, height: baix - yCel + 2 });
    zona.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') mostra(i); });
    zona.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') amaga(); });
    zona.addEventListener('click', (e) => {
      e.stopPropagation();
      if (actiu === i && e.pointerType !== 'mouse') amaga();
      else mostra(i);
    });
    g.append(zona);
  });
  g.append(retol);
  for (const grup of llunesGrafica) g.append(grup);
  fig._amaga = amaga;

  fig.querySelector('.g-llegenda')?.remove();
  const ll = element('p', 'g-llegenda');
  const clau = (classe, text) => {
    const c = element('span', 'g-clau');
    c.append(element('span', classe), text);
    return c;
  };
  // Una clau per cosa, sense explicacions entre parèntesis (Juanjo, 16-10-2026:
  // «es un galimatías»); què vol dir l'alçada ja ho diuen els mm de la barra.
  // Cada clau de pluja, només si n'hi ha (Juanjo, 16-10-2026).
  // La de la zona triada: «Temperatura» o «Part alta».
  if (ambTemp) ll.append(clau('m-temp', T('Temperatura')));
  if (ambPrev) {
    const a = opcions.antelacio || 1;
    ll.append(clau('m-prev', T`Previsió ${a}\u00a0h abans`));
  }
  if (ambPrevMm) ll.append(clau('m-pluja-prev', T`Pluja prevista ${opcions.antelacio || 1}\u00a0h abans`));
  const plujes = files.map((f) => plujaGrafica(f));
  // La probabilitat en xifres: «probable» i «possible» no es distingeixen
  // (Juanjo, 16-10-2026: «entre lluvia probable y puede llover no hay
  // diferencia para un usuario normal»).
  const pct = (p) => Math.round(p * 100);
  // A l'historial, la pluja que va caure, sense probabilitat (ADR 0124).
  if (opcions.historial && plujes.includes('pluja')) ll.append(clau('m-pluja', T('Pluja mesurada')));
  else if (plujes.includes('pluja')) ll.append(clau('m-pluja', T`Pluja, ${pct(PROB_PLUJA)}\u00a0% o més`));
  if (plujes.includes('possible')) {
    ll.append(clau('m-pluja possible', T`Pluja, del ${pct(PROB_POSSIBLE)} al ${pct(PROB_PLUJA)}\u00a0%`));
  }
  if (plujes.includes('poca')) {
    ll.append(clau('m-pluja poca', T`Pluja, del ${pct(PROB_POCA)} al ${pct(PROB_POSSIBLE)}\u00a0%`));
  }
  if (files.some((f) => f.pluja_mm == null && f.pluja_dubte != null)) ll.append(clau('m-pluja-dubte', T('Potser va plovisquejar')));
  const intenses = files.filter((f) => plujaGrafica(f)).map((f) => intensitatPluja(f.pluja_mm || 0));
  if (intenses.includes('forta')) ll.append(clau('m-pluja forta', T('Pluja forta')));
  if (intenses.includes('torrencial')) ll.append(clau('m-pluja torrencial', T('Pluja torrencial')));
  if (hVent) ll.append(clau('m-vent', T('Vent')), clau('m-ratxa', T('Ratxes')));
  if (hHumitat) ll.append(clau('m-humitat', T('Humitat')));
  if (hPressio) ll.append(clau('m-pressio', T('Pressió')));
  if (hNuvols) ll.append(clau('m-nuvols', T('Núvols')));
  if (hUv) ll.append(clau('m-uv', T('Índex UV')));
  ll.append(clau('m-nit', T('Nit')));
  // La fase de la Lluna, no: ja porta el nom a la mateixa gràfica (Juanjo,
  // 25-10-2026: «dado que lluna plena ya aparece en el propio gráfico se puede
  // quitar de la leyenda»).
  if (fig._botoImatge) ll.append(botoImatge(fig, 'g-imatge'));
  if (fig._botoOpcions) ll.append(botoHistorial(), botoOpcions());
  // Els avisos de més enllà de la gràfica, a sobre (avisosMesEnlla).
  fig.querySelector('.g-mes-enlla')?.remove();
  const mesEnlla = files.length && new Date(files[n - 1].fins) > new Date() ? avisosMesEnlla(files[n - 1].fins) : [];
  if (mesEnlla.length) {
    const avisos = element('div', 'g-mes-enlla');
    avisos.append(...mesEnlla);
    caixa.before(avisos);
  }
  fig.append(ll);
}

// --- La gràfica en gran (Juanjo, 17-10-2026: «verlo en su propia ventana …
// con posibilidad de alguna configuració»): a sobre de la pàgina, amb marge,
// i amb la seva adreça (#grafica) per compartir-la. Es tria quines hores (avui,
// demà o totes) i si s'hi veu el vent; es recorda en aquest dispositiu. ---
// Dues menes d'opcions (Juanjo, 19-10-2026: «debería marcarse de forma
// diferente lo que queda fijado y lo que no cuando se sale de la
// configuración, mi propuesta es hacer lo permanente con selectores»): les que
// es recorden en aquest dispositiu i valen per a totes les gràfiques de la web
// (la zona de la temperatura, el vent, la humitat, la pressió, els núvols i l'UV), amb selectors i
// interruptors; i les d'aquesta
// visita (quines hores), amb botons, que tornen a ser les de sempre en tancar.
// «Com encerta» i l'historial de cada dia eren aquí fins a la 3.164.0: ara
// són a la pàgina «Fiabilitat», fiabilitat.html (ADR 0110). El vent, per
// defecte, no (Juanjo, 19-10-2026: «por defecto no debería mostrar el
// viento»; fins a la 3.150.2 sortia).
// Clau nova: la 2 desava «vent: true» per a tothom en canviar qualsevol cosa,
// sense que ningú ho hagués triat; d'allà es conserven la part baixa i l'alta.
const CLAU_GRAFICA = 'meteo.grafica.3';
const CLAU_GRAFICA_VELLA = 'meteo.grafica.2';
const ambVentTriat = () => llegeixOpcionsGrafica().vent === true;
// La zona del barri de les temperatures, per a tota la portada: la riera
// (per defecte; l'estació) o la part alta, amb el botó doble de dalt
// (casa.botoZona; Juanjo, 23-10-2026: «un selector de parte baja (riera) y
// parte alta de forma que marque las temperaturas en base a lo elegido»;
// ADR 0123). Es recorda al dispositiu; la primera vegada, la que es tenia a
// la gràfica, que fins a la 3.190.0 es triava a «Opcions». Un enllaç amb
// «?zona=alta» la fa servir sense desar-la.
const CLAU_ZONA = 'meteo.zona';
let ZONA = null;
function zonaTriada() {
  if (ZONA) return ZONA;
  let z = null;
  try { z = new URLSearchParams(location.search).get('zona'); } catch (_) { z = null; }
  if (z !== 'alta' && z !== 'baixa') {
    try { z = localStorage.getItem(CLAU_ZONA); } catch (_) { z = null; }
  }
  if (z !== 'alta' && z !== 'baixa') z = llegeixOpcionsGrafica().zona === 'alta' ? 'alta' : 'baixa';
  ZONA = z;
  return z;
}
function triaZona(z) {
  ZONA = z;
  try { localStorage.setItem(CLAU_ZONA, z); } catch (_) { /* sense desar, només ara */ }
  zonaALAdreca();
}
// L'adreça porta la zona si és la part alta, perquè compartir la pàgina la
// mostri tal com es veu.
function zonaALAdreca() {
  try {
    const u = new URL(location.href);
    if (zonaTriada() === 'alta') u.searchParams.set('zona', 'alta');
    else u.searchParams.delete('zona');
    if (u.href !== location.href) history.replaceState(history.state, '', u.href);
  } catch (_) { /* sense history (proves) */ }
}
// La temperatura d'una hora a la zona triada: la de la riera més la
// diferència de la part alta (ADR 0087), si n'hi ha.
function tempZona(f) {
  if (f.temperatura == null) return null;
  return zonaTriada() === 'alta' && !f.mesura ? f.temperatura + (f.dif_alta || 0) : f.temperatura;
}
const humitatTriada = () => llegeixOpcionsGrafica().humitat === true;
const pressioTriada = () => llegeixOpcionsGrafica().pressio === true;
const nuvolsTriats = () => llegeixOpcionsGrafica().nuvols === true;
const uvTriat = () => llegeixOpcionsGrafica().uv === true;
// La Lluna, de sèrie sí; es pot treure a les opcions (Juanjo, 25-10-2026).
const llunaTriada = () => llegeixOpcionsGrafica().lluna !== false;
// Si alguna fase principal cau dins les hores de la gràfica.
const faseDins = (files) => ((LLUNA && LLUNA.fases) || []).some((fase) => {
  const t = new Date(fase.hora);
  return files.some((f) => new Date(f.hora) <= t && t < new Date(f.fins));
});

// L'índex UV amb els colors i els noms de l'OMS: el límit de dalt de cada
// nivell, la classe i el nom (el «Sol» de «Consultes» i la gràfica).
const UV = () => [[2, 'uv-baix', T('baix')], [5, 'uv-moderat', T('moderat')], [7, 'uv-alt', T('alt')],
  [10, 'uv-molt-alt', T('molt alt')], [99, 'uv-extrem', T('extrem')]];

// Totes les hores que queden, sempre (Juanjo, 20-10-2026: «quiero que hagas
// siempre tot»). Fins a la 3.165.0 es triaven amb «24 h · Demà · Tot»; ara la
// gràfica va hora a hora i es desplaça de costat (dibuixaGrafica, COL_HORA).
function horesVista() {
  const ara = new Date();
  return (HORES_GRAFICA || []).filter((f) => new Date(f.fins) > ara && f.temperatura != null);
}

function llegeixOpcionsGrafica() {
  try {
    const ara = JSON.parse(localStorage.getItem(CLAU_GRAFICA));
    if (ara) return ambZona(ara);
    const vella = JSON.parse(localStorage.getItem(CLAU_GRAFICA_VELLA)) || {};
    return ambZona({ alta: vella.alta, baixa: vella.baixa });
  } catch (_) { return {}; }
}

// La zona de la temperatura, de les opcions desades. Fins a la 3.173.2 eren
// dos interruptors: qui tenia només la part alta la conserva; la resta (també
// amb les dues o cap), la part baixa.
function ambZona(o) {
  const { alta, baixa, ...resta } = o;
  return { ...resta, zona: o.zona || (alta === true && baixa === false ? 'alta' : 'baixa') };
}

// --- L'historial: el que es va mesurar al barri, hora a hora (ADR 0124;
// Juanjo, 24-10-2026: «consultar un historial, por ejemplo si llovió las
// horas pasadas o ver la temperatura hace una semana»). Les dades són les de
// «Fiabilitat» (historial.py): la temperatura de l'estació i la pluja del
// barri des del 4-10-2026. Aquí, sense la previsió: el que deia i com encerta
// són a «Fiabilitat». ---

// L'historial és a IONOS, al costat de les dades; en local, al costat de la pàgina.
function llegeixHistorial(nom) {
  return baixa(DADES_URL + nom).catch(() => baixa(nom));
}

const DIES_HISTORIAL = new Map();
function llegeixDiaHistorial(d) {
  if (!DIES_HISTORIAL.has(d)) DIES_HISTORIAL.set(d, llegeixHistorial(`historial-${d}.json`).catch(() => null));
  return DIES_HISTORIAL.get(d);
}

// El dia de Madrid d'un moment, «AAAA-MM-DD».
function isoDia(data) {
  return diaLocal(data);
}
const avuiIso = () => isoDia(new Date());

// Les hores ja acabades, sense la previsió; les últimes que encara no tenen
// mesura (la publicació va per darrere de l'hora), fora.
function horesMesurades(hores, ara = new Date()) {
  const res = (hores || []).filter((f) => new Date(f.fins) <= ara).map(({ prev, ...f }) => f);
  while (res.length && res[res.length - 1].temperatura == null && res[res.length - 1].pluja_mm == null) res.pop();
  return res;
}

// Les darreres 24 hores amb mesura: les d'ahir i les d'avui.
function darreres24(ahir, avui, ara = new Date()) {
  return horesMesurades([...((ahir && ahir.hores) || []), ...((avui && avui.hores) || [])], ara).slice(-24);
}

// El resum, com a conclusió: si va ploure i quant, i la mínima i la màxima
// amb la seva hora. Les temperatures són la mitjana de cada hora, sense les
// hores amb sol sobre el termòmetre, que no compten (historial.py).
// «vint4»: les darreres 24 h, amb «avui» i «ahir» a les hores; «ara»: el que
// encara dura (les 24 h i avui), que diu «no ha plogut» i no «no va ploure».
function resumMesurat(files, vint4 = false, ara = vint4) {
  if (!files.length) return [T('D’aquest dia no hi ha mesures.')];
  const res = [];
  const conegudes = files.filter((f) => f.pluja_mm != null);
  const mm = conegudes.reduce((s, f) => s + f.pluja_mm, 0);
  if (!conegudes.length) {
    res.push(T('De la pluja no hi ha dades.'));
  } else {
    const xifra = mm >= 10 ? String(Math.round(mm)) : coma(mm);
    let text = mm < 0.05 ? (ara ? T('No ha plogut.') : T('No va ploure.'))
      : ara ? T`Han caigut ${xifra}\u00a0mm.` : T`Van caure ${xifra}\u00a0mm.`;
    // Les hores en què només una veïna va veure pluja (historial.py,
    // «pluja_dubte»): potser va plovisquejar; la resta, sense dades.
    const dubte = files.filter((f) => f.pluja_mm == null && f.pluja_dubte != null).length;
    const sense = files.length - conegudes.length - dubte;
    if (dubte) {
      const quantes = dubte === 1 ? T('En una hora') : T`En ${dubte} hores`;
      const mes = mm < 0.05 ? '' : T(' més');
      text += ' ' + (ara ? T`${quantes}${mes} potser ha plovisquejat: només una estació veïna hi ha marcat pluja.`
        : T`${quantes}${mes} potser va plovisquejar: només una estació veïna hi va marcar pluja.`);
    }
    if (sense) text += ' ' + (sense === 1 ? T('D’una hora no se sap.') : T`De ${sense} hores no se sap.`);
    res.push(text);
  }
  const temps = files.filter((f) => f.temperatura != null && !f.sol);
  if (temps.length) {
    const avui = avuiIso();
    const quan = (f) => {
      const h = horaLocal(f.hora);
      if (!vint4) return T`a les ${h}\u00a0h`;
      return f.hora.slice(0, 10) === avui ? T`avui a les ${h}\u00a0h` : T`ahir a les ${h}\u00a0h`;
    };
    const min = temps.reduce((a, f) => (f.temperatura < a.temperatura ? f : a));
    const max = temps.reduce((a, f) => (f.temperatura > a.temperatura ? f : a));
    res.push(T`Mínima: ${Math.round(min.temperatura)}\u00a0°C, ${quan(min)}. Màxima: ${Math.round(max.temperatura)}\u00a0°C, ${quan(max)}.`);
  } else {
    res.push(T('De la temperatura no hi ha dades.'));
  }
  return res;
}

// La zona triada amb el botó de dalt (ADR 0123), també a l'historial: amb la
// part alta, la temperatura mesurada per les veïnes de dalt (historial.py,
// «temperatura_alta»; sense el sol sobre el termòmetre de casa, que no hi
// compta). Si el que es veu no en porta cap (abans del 9-10-2026), la de la
// riera, i «nomesRiera» perquè la pàgina ho digui.
function ambZonaHistorial(files, zona = zonaTriada()) {
  if (zona !== 'alta') return { files, nomesRiera: false };
  if (!files.some((f) => f.temperatura_alta != null)) return { files, nomesRiera: files.length > 0 };
  return { files: files.map(({ sol, ...f }) => ({ ...f, temperatura: f.temperatura_alta ?? null })), nomesRiera: false };
}

// El nom del que es veu: «Darreres 24 h», «Avui», «Ahir» o la data.
function nomHistorial(pos) {
  if (pos === '24h') return T('Darreres 24 h');
  if (pos === avuiIso()) return T('Avui');
  if (pos === sumaDies(new Date(), -1)) return T('Ahir');
  const nom = llegeixHora(`${pos}T12:00`).toLocaleDateString(IDIOMA.codi === 'es' ? 'es' : 'ca',
    { weekday: 'long', day: 'numeric', month: 'long', timeZone: ZONA_HORA });
  return nom.charAt(0).toUpperCase() + nom.slice(1);
}

// L'adreça de l'historial: #historial (les darreres 24 h) o #historial-AAAA-MM-DD.
const esAdrecaHistorial = (h) => /^#historial(-\d{4}-\d{2}-\d{2})?$/.test(h);
const adrecaHistorial = (pos) => (pos === '24h' ? '#historial' : `#historial-${pos}`);

function vistaGrafica(historialInicial = null) {
  if (!HORES_GRAFICA || document.querySelector('dialog.vista-grafica')) return;
  // Les que es recorden (fixes) i les d'aquesta visita, que comencen sempre igual.
  const fixes = { vent: false, zona: 'baixa', humitat: false, pressio: false, nuvols: false, uv: false, lluna: true,
    ...llegeixOpcionsGrafica() };
  const opcions = { get vent() { return fixes.vent; } };
  const dlg = element('dialog', 'vista-grafica');
  dlg.setAttribute('aria-labelledby', 'vg-titol');
  const cap = element('div', 'vg-cap');
  const titol = element('h2', null, T('Previsió'));
  titol.id = 'vg-titol';
  const fig = figuraGrafica([], T('Gràfica de la previsió hora a hora: perill, cel, temperatura i probabilitat de pluja.'));
  fig.classList.add('gran');
  const comparteixBoto = element('button', 'boto-icona');
  comparteixBoto.type = 'button';
  comparteixBoto.title = T('Comparteix l’enllaç de la gràfica');
  comparteixBoto.setAttribute('aria-label', T('Comparteix l’enllaç de la gràfica'));
  comparteixBoto.append(icona('i-share-2'));
  comparteixBoto.addEventListener('click', () => comparteix());
  // Tancar: la X de sempre, a dalt a la dreta (icona «x» de Lucide).
  const tanca = element('button', 'boto-icona');
  tanca.type = 'button';
  tanca.title = T('Tanca');
  tanca.setAttribute('aria-label', T('Tanca'));
  tanca.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  tanca.addEventListener('click', () => dlg.close());
  const accions = element('div', 'vg-accions');
  accions.append(botoImatge(fig, 'boto-icona'), comparteixBoto, tanca);
  cap.append(titol, accions);

  // Les opcions que es recorden: el vent, la humitat, la pressió, els núvols, l'UV i la Lluna.
  // Les que es recorden, amb interruptors, com a «Avisos».
  const interruptor = (clau, icon, text, descripcio) => {
    const fila = element('label', 'vg-fixa');
    fila.title = descripcio;
    const c = element('input', 'interruptor');
    c.type = 'checkbox';
    c.setAttribute('role', 'switch');
    c.checked = Boolean(fixes[clau]);
    c.addEventListener('change', () => { fixes[clau] = c.checked; desa(); dibuixa(); });
    fila.append(typeof icon === 'string' ? icona(icon) : icon, element('span', null, text), c);
    return fila;
  };
  const vent = interruptor('vent', 'i-wind', T('Vent'), T('Afegeix el vent i les ratxes, en km/h.'));
  const ambVent = HORES_GRAFICA.some((f) => f.vent != null);
  // La zona de la temperatura ja no és aquí: la tria el botó doble de dalt
  // per a tota la portada (ADR 0123).
  const humitat = interruptor('humitat', 'i-droplets', T('Humitat'), T('Afegeix la humitat relativa de l’aire, en %.'));
  const ambHumitat = HORES_GRAFICA.some((f) => f.humitat != null);
  const pressio = interruptor('pressio', 'i-gauge', T('Pressió'),
    T('Afegeix la pressió atmosfèrica, en hPa: si baixa de pressa, sol venir mal temps.'));
  const ambPressio = HORES_GRAFICA.some((f) => f.pressio != null);
  const nuvols = interruptor('nuvols', 'i-cloud', T('Núvols'), T('Afegeix quina part del cel taparan els núvols, del 0 al 100\u00a0%.'));
  const ambNuvols = HORES_GRAFICA.some((f) => f.nuvols != null);
  const uv = interruptor('uv', 'i-sun', T('UV'), T('Afegeix l’índex UV de les hores de sol, amb els colors de l’OMS.'));
  const ambUv = HORES_GRAFICA.some((f) => f.uv != null);
  // Una lluna en quart, amb el traç de les altres icones, i no la icona de la
  // lluna, que és la del tema fosc.
  const iconaFase = icona('i-cloud');
  iconaFase.setAttribute('viewBox', '0 0 24 24');
  iconaFase.innerHTML = '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>';
  const lluna = interruptor('lluna', iconaFase, T('Lluna'),
    T('Afegeix les fases principals de la Lluna (nova, plena i quarts) a la seva hora.'));
  // Només es desen les que es recorden.
  const desa = () => {
    try { localStorage.setItem(CLAU_GRAFICA, JSON.stringify(fixes)); } catch (_) {}
  };
  // L'historial: un botó que canvia la gràfica pel que es va mesurar; ‹ i ›
  // per anar d'un dia a l'altre i, al mig, el nom del dia, que obre el
  // calendari per saltar a qualsevol (ADR 0124). Comença per les darreres 24 h.
  let historial = null;      // null: la previsió; '24h' o 'AAAA-MM-DD'
  let index = null;
  const botoHist = element('button', 'vg-opcio');
  botoHist.type = 'button';
  botoHist.title = T('El que es va mesurar al barri, hora a hora');
  botoHist.append(icona('i-history'), T('Historial'));
  const navega = element('div', 'vg-dia');
  const fletxa = (d, text) => {
    const b = element('button', 'boto-icona');
    b.type = 'button';
    b.title = text;
    b.setAttribute('aria-label', text);
    b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
    return b;
  };
  const enrere = fletxa('m15 18-6-6 6-6', T('Dia anterior'));
  const endavant = fletxa('m9 18 6-6-6-6', T('Dia següent'));
  // El nom del dia obre el calendari del navegador (un camp de data amagat).
  const nomDia = element('button', 'vg-nom-dia vg-data');
  nomDia.type = 'button';
  nomDia.title = T('Tria un dia al calendari');
  const textDia = element('span');
  nomDia.append(textDia, icona('i-calendar'));
  const calendari = element('input', 'visualment-amagat vg-calendari');
  calendari.type = 'date';
  calendari.tabIndex = -1;
  calendari.setAttribute('aria-hidden', 'true');
  navega.append(enrere, nomDia, endavant, calendari);
  const barraHist = element('div', 'vg-historial');
  barraHist.append(botoHist, navega);
  const resumHist = element('p', 'vg-resum-historial');
  resumHist.setAttribute('aria-live', 'polite');
  // Les posicions, de la més antiga a la més nova: cada dia i, al final, les 24 h.
  const posicions = () => [...((index && index.dies) || []).filter((d) => d <= avuiIso()), '24h'];
  const dibuixaHistorial = async () => {
    const pos = historial;
    const llista = posicions();
    const i = llista.indexOf(pos);
    enrere.disabled = i <= 0;
    endavant.disabled = i < 0 || i >= llista.length - 1;
    textDia.textContent = nomHistorial(pos);
    nomDia.setAttribute('aria-label', T`${nomHistorial(pos)}: tria un altre dia al calendari`);
    let files;
    if (pos === '24h') {
      const [a, b] = await Promise.all([llegeixDiaHistorial(sumaDies(new Date(), -1)), llegeixDiaHistorial(avuiIso())]);
      files = darreres24(a, b);
    } else {
      files = horesMesurades((await llegeixDiaHistorial(pos) || {}).hores);
    }
    if (pos !== historial) return;
    const zona = ambZonaHistorial(files);
    files = zona.files;
    fig._amaga?.();
    fig._files = files;
    fig._opcions = { gran: true, escala: true, historial: true, vent: fixes.vent, humitat: fixes.humitat,
      pressio: fixes.pressio, nuvols: fixes.nuvols, lluna: fixes.lluna };
    mostraInterruptors(files);
    // Per als crèdits de la imatge: les 24 h, amb l'hora de l'última mesura.
    fig._nomHistorial = pos === '24h' && files.length
      ? T`les 24 h fins a les ${horaCurta(new Date(files[files.length - 1].fins))}` : nomHistorial(pos);
    if (files.length) {
      dibuixaGrafica(fig);
    } else {
      // Sense mesures, res de l'anterior: ni la gràfica ni la llegenda.
      fig.querySelector('.g-desplaca svg')?.remove();
      fig.querySelector('.g-fixes')?.remove();
      fig.querySelector('.g-llegenda')?.remove();
    }
    // Les darreres 24 h, amb el final a la vista: les últimes hores són les
    // que es busquen. Un dia, des de les 0 h.
    const caixa = fig.querySelector('.g-desplaca');
    if (caixa) caixa.scrollLeft = pos === '24h' ? caixa.scrollWidth : 0;
    resumHist.replaceChildren(...resumMesurat(files, pos === '24h', pos === '24h' || pos === avuiIso())
      .map((t) => element('span', null, t)),
    ...(zona.nomesRiera ? [element('span', null, T('D’aquest dia només hi ha la temperatura de la riera.'))] : []));
  };
  const posaHistorial = (pos) => {
    historial = pos;
    history.replaceState(null, '', pos ? adrecaHistorial(pos) : '#grafica');
    dibuixa();
  };
  botoHist.addEventListener('click', () => posaHistorial(historial ? null : '24h'));
  // Un enllaç de l'historial amb la finestra ja oberta hi va directament.
  dlg._posaHistorial = posaHistorial;
  enrere.addEventListener('click', () => {
    const llista = posicions();
    posaHistorial(llista[llista.indexOf(historial) - 1] || historial);
  });
  endavant.addEventListener('click', () => {
    const llista = posicions();
    posaHistorial(llista[llista.indexOf(historial) + 1] || historial);
  });
  nomDia.addEventListener('click', () => {
    const dies = (index && index.dies) || [];
    if (!dies.length) return;
    calendari.min = dies[0];
    calendari.max = avuiIso();
    calendari.value = historial === '24h' ? avuiIso() : historial;
    try { calendari.showPicker(); } catch (_) { calendari.focus(); }
  });
  calendari.addEventListener('change', () => {
    const d = calendari.value;
    if (posicions().includes(d)) posaHistorial(d);
    else if (d) avisBreu(T('D’aquest dia no hi ha mesures.'));
  });

  const dibuixa = () => {
    const ambHist = Boolean(historial);
    botoHist.setAttribute('aria-pressed', String(ambHist));
    navega.hidden = !ambHist;
    resumHist.hidden = !ambHist;
    titol.textContent = ambHist ? T('Historial') : T('Previsió');
    fig.querySelector('figcaption')?.replaceChildren(ambHist
      ? T('Gràfica del que es va mesurar al barri, hora a hora: temperatura i pluja.')
      : T('Gràfica de la previsió hora a hora: perill, cel, temperatura i probabilitat de pluja.'));
    if (ambHist) {
      if (!index) {
        llegeixHistorial('historial.json').then((d) => { index = d; if (historial) dibuixa(); }, () => {});
      }
      dibuixaHistorial();
      return;
    }
    fig._amaga?.();
    // De tornada de l'historial, la previsió des del principi.
    const tornada = fig._opcions && fig._opcions.historial;
    fig._nomHistorial = null;
    fig._files = horesVista();
    mostraInterruptors(HORES_GRAFICA);
    fig._opcions = { gran: true, vent: ambVent && opcions.vent,
      humitat: ambHumitat && fixes.humitat, pressio: ambPressio && fixes.pressio, nuvols: ambNuvols && fixes.nuvols, uv: ambUv && fixes.uv,
      lluna: fixes.lluna };
    dibuixaGrafica(fig);
    if (tornada) {
      const caixa = fig.querySelector('.g-desplaca');
      if (caixa) caixa.scrollLeft = 0;
    }
  };
  // Les que es recorden, a part (Juanjo, 19-10-2026), sense el rètol «Es recorda
  // per a totes les gràfiques», que ja s'entén (Juanjo, 20-10-2026: «quita
  // esto, ya se entiende»); el nom, només per als lectors de pantalla.
  const fixesEl = element('div', 'vg-fixes');
  fixesEl.setAttribute('role', 'group');
  fixesEl.setAttribute('aria-label', T('Es recorda per a totes les gràfiques'));
  // Cadascun, només si el que es veu en porta: a la previsió, el que dona el
  // model; a l'historial, el que es va mesurar (sense UV; ADR 0124).
  const interruptors = { vent, humitat, pressio, nuvols, uv, lluna };
  fixesEl.append(...Object.values(interruptors));
  const mostraInterruptors = (files) => {
    for (const [clau, el] of Object.entries(interruptors)) {
      el.hidden = clau === 'lluna' ? !faseDins(files) : !files.some((f) => f[clau] != null);
    }
    fixesEl.hidden = Object.values(interruptors).every((el) => el.hidden);
  };

  dlg.append(cap, barraHist, fig, resumHist, fixesEl);
  // Un toc fora de la finestra la tanca, com Esc.
  dlg.addEventListener('click', (e) => {
    if (e.target !== dlg) return;
    const r = dlg.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dlg.close();
  });
  dlg.addEventListener('close', () => {
    dlg.remove();
    // Les altres gràfiques de la pàgina, amb el vent que s'hi hagi triat.
    dibuixaGrafiques();
    if (location.hash === '#grafica' || esAdrecaHistorial(location.hash)) {
      history.replaceState(null, '', location.pathname + location.search);
    }
  });
  document.body.append(dlg);
  dlg.showModal();
  // Des de l'enllaç o del botó de la portada, ja a l'historial.
  historial = historialInicial;
  history.replaceState(null, '', historial ? adrecaHistorial(historial) : '#grafica');
  dibuixa();
  tanca.focus();
}

// Si s'ha obert l'enllaç de la gràfica (#grafica) o de l'historial
// (#historial, #historial-AAAA-MM-DD), en gran, la primera vegada.
function historialDeLAdreca(h) {
  if (!esAdrecaHistorial(h)) return null;
  return h === '#historial' ? '24h' : h.slice('#historial-'.length);
}
let obertaGrafica = false;
function obreGraficaDeLEnllac() {
  if (obertaGrafica || (location.hash !== '#grafica' && !esAdrecaHistorial(location.hash))) return;
  obertaGrafica = true;
  vistaGrafica(historialDeLAdreca(location.hash));
}
addEventListener('hashchange', () => {
  if (location.hash !== '#grafica' && !esAdrecaHistorial(location.hash)) return;
  const oberta = document.querySelector('dialog.vista-grafica');
  if (oberta) oberta._posaHistorial(historialDeLAdreca(location.hash));
  else vistaGrafica(historialDeLAdreca(location.hash));
});

// --- La gràfica com a imatge, des de la web i la app (Juanjo, 17-10-2026: «se
// puede añadir a la gráfica una captura? … incluiría la misma información que
// la de telegram»): el que es veu (les hores triades, el vent, els colors del
// tema) i, a sota, els crèdits de la imatge de Telegram (grafica_imatge.py).
// La fa el navegador: la gràfica ja és SVG; s'hi copien els estils calculats,
// les icones, la llegenda i els crèdits, i es passa a PNG amb un canvas. Al
// mòbil s'obre el menú de compartir amb la imatge; on no n'hi ha, es baixa. ---

// L'hora de les dades de la gràfica: la posen casa.js i consultes.js.
let GENERAT_GRAFICA = null;
// Les dades amb els avisos (smp de Meteocat i avisos de l'AEMET), per als de
// més enllà de la gràfica: també les posen casa.js i consultes.js.
let AVISOS_GRAFICA = null;

// Els avisos oficials que comencen després de l'última hora de la gràfica (que
// arriba a demà a les 21 h), un per dia, amb el color del nivell i el seu
// origen, cap a la seva fitxa de «Perill» (Juanjo, 17-10-2026: el perill molt
// alt de Meteocat de dilluns no sortia enlloc de la gràfica ni dels trams).
function avisosMesEnlla(fiIso) {
  const d = AVISOS_GRAFICA;
  if (!d) return [];
  const fi = new Date(fiIso);
  const NIVELL_SMP = { mig: 'groc', alt: 'taronja', maxim: 'vermell' };
  const nivellSmp = (p) => NIVELL_SMP[p <= 2 ? 'mig' : p <= 4 ? 'alt' : 'maxim'];
  const fenomenSmp = (m) => ([['violent', 'temps_violent'], ['pluja', 'pluja'], ['neu', 'neu'], ['vent', 'vent'],
    ['calor', 'calor'], ['fred', 'fred']].find(([k]) => (m || '').toLowerCase().includes(k)) || [null, m])[1];
  const perDia = new Map();
  const afegeix = (dia, e) => {
    if (!perDia.has(dia)) perDia.set(dia, []);
    perDia.get(dia).push(e);
  };
  for (const a of (d.smp && d.smp.avisos) || []) {
    for (const [dia, franges] of Object.entries(a.dies || {})) {
      if (franges.some(([h]) => llegeixHora(`${dia}T${String(h).padStart(2, '0')}:00`) >= fi)) {
        const fenomen = fenomenSmp(a.meteor);
        afegeix(dia, { nivell: nivellSmp(a.perill), nom: TD(fenomen), font: 'meteocat', fenomen });
      }
    }
  }
  for (const a of avisosAemet(d)) {
    if (new Date(a.inicio) < fi) continue;
    const dia = a.inicio.slice(0, 10);
    afegeix(dia, { nivell: a.nivel, nom: TD(a.tipo), font: 'aemet', fenomen: a.tipo });
  }
  const codi = IDIOMA.codi === 'es' ? 'es' : 'ca';
  return [...perDia.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([dia, elements]) => {
    const p = delNivellMesAlt(elements);
    const nom = llegeixHora(`${dia}T12:00`).toLocaleDateString(codi, { weekday: 'long', day: 'numeric', timeZone: ZONA_HORA });
    const text = `${nom.charAt(0).toUpperCase()}${nom.slice(1)}: ${textPerillCurt(p, true, true)}`;
    const a = element('a', `g-mes-enlla-avis ${p.nivell}`);
    // La fitxa, en tocar-lo: l'historial de «Perill» pot arribar després de dibuixar.
    const fitxa = () => fitxaDeLinia(p.perFont[0][0] === 'meteocat' ? 'Meteocat' : `AEMET ${p.noms.join(' ')}`);
    a.href = fitxa();
    a.addEventListener('click', () => { a.href = fitxa(); });
    a.title = textPerill(p);
    a.append(element('span', 'g-mes-enlla-marca'), text);
    return a;
  });
}

function creditsGrafica(fig = null) {
  // A l'historial, el que es va mesurar i de quan, no la previsió (ADR 0124).
  if (fig && fig._nomHistorial) {
    return [T`Temps a Montflorit (Cerdanyola del Vallès) · mesurat al barri: ${fig._nomHistorial} · meteo-montflorit.github.io`];
  }
  const g = GENERAT_GRAFICA ? new Date(GENERAT_GRAFICA) : new Date();
  const codi = IDIOMA.codi === 'es' ? 'es' : 'ca';
  const dia = `${g.toLocaleDateString(codi, { weekday: 'long', timeZone: ZONA_HORA })} ${g.toLocaleDateString(codi, { day: 'numeric', month: 'long', timeZone: ZONA_HORA })}`;
  const hora = g.toLocaleTimeString(codi, { hour: '2-digit', minute: '2-digit', timeZone: ZONA_HORA });
  return [T`Temps a Montflorit (Cerdanyola del Vallès) · previsió de ${dia}, ${hora} · meteo-montflorit.github.io`,
    T('No és oficial: si l’AEMET, Meteocat o Protecció Civil donen un avís, mana el seu.')];
}

const ESTILS_SVG = ['fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray',
  'stroke-linecap', 'stroke-linejoin', 'opacity', 'paint-order', 'font-family', 'font-size', 'font-weight',
  'stop-color', 'stop-opacity', 'color'];
const VARS_ICONES = ['--ic-sol', '--ic-sol-fons', '--ic-nuvol', '--ic-nuvol-fons', '--ic-aigua', '--ic-aigua-fons',
  '--ic-neu', '--ic-lluna', '--ic-lluna-fons'];

// La imatge, compacta: tota la gràfica a l'amplada de la pàgina, com abans
// del desplaçament (COL_HORA), i després es torna a dibuixar com era.
function svgDeLaGrafica(fig) {
  const era = fig._compacte;
  fig._compacte = true;
  dibuixaGrafica(fig);
  try {
    return svgDeLaGraficaCompacta(fig);
  } finally {
    fig._compacte = era;
    dibuixaGrafica(fig);
  }
}

function svgDeLaGraficaCompacta(fig) {
  const orig = fig.querySelector('.g-desplaca svg');
  // La llegenda es col·loca respecte de la gràfica.
  const caixa = orig.getBoundingClientRect();
  const marge = 16;
  const W = parseFloat(orig.getAttribute('width')) || caixa.width;
  const estil = getComputedStyle(fig);
  const arrel = getComputedStyle(document.documentElement);
  const fons = arrel.getPropertyValue('--superficie').trim() || '#fff';
  const suau = arrel.getPropertyValue('--suau').trim() || '#64748b';
  const lletra = estil.fontFamily;
  const g = orig.cloneNode(true);
  // Els estils calculats, element per element: fora de la pàgina no hi ha el CSS.
  const origs = [orig, ...orig.querySelectorAll('*')];
  [g, ...g.querySelectorAll('*')].forEach((e, i) => {
    const c = getComputedStyle(origs[i]);
    e.setAttribute('style', ESTILS_SVG.map((p) => `${p}:${c.getPropertyValue(p)}`).join(';'));
  });
  // Ni la fitxa de l'hora ni la columna marcada.
  g.querySelector('.g-retol')?.replaceChildren();
  // Les icones: els símbols que fa servir, amb els colors del cel.
  const defs = document.createElementNS(SVG_NS, 'defs');
  for (const id of new Set([...g.querySelectorAll('use')].map((u) => u.getAttribute('href')))) {
    const s = document.querySelector(id);
    if (s) defs.append(s.cloneNode(true));
  }
  g.prepend(defs);
  g.setAttribute('style', VARS_ICONES.map((v) => `${v}:${estil.getPropertyValue(v).trim()}`).join(';'));
  const alt = parseFloat(orig.getAttribute('height'));
  const peca = (nom, atributs, text) => svg(nom, atributs, text);
  const tot = document.createElementNS(SVG_NS, 'svg');
  tot.setAttribute('xmlns', SVG_NS);
  tot.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
  const cos = peca('g', { transform: `translate(${marge},${marge})` });
  g.setAttribute('x', 0);
  g.setAttribute('y', 0);
  cos.append(g);
  // La llegenda, on és a la pantalla: cada mostra amb el seu color i el text.
  const ll = fig.querySelector('.g-llegenda');
  let y = alt;
  if (ll) {
    const lc = getComputedStyle(ll);
    for (const clau of ll.querySelectorAll('.g-clau')) {
      const m = clau.firstElementChild;
      const r = m.getBoundingClientRect();
      const ms = getComputedStyle(m);
      const x0 = r.left - caixa.left;
      const y0 = r.top - caixa.top;
      if (ms.borderTopStyle === 'dashed' || ms.borderTopStyle === 'dotted') {
        cos.append(peca('line', { x1: x0, x2: x0 + r.width, y1: y0 + 1, y2: y0 + 1,
          style: `stroke:${ms.borderTopColor};stroke-width:2;stroke-dasharray:4 3` }));
      } else {
        cos.append(peca('rect', { x: x0, y: y0, width: r.width, height: Math.max(r.height, 2), rx: 1,
          style: `fill:${ms.backgroundColor};stroke:${ms.borderTopStyle === 'solid' ? ms.borderTopColor : 'none'}` }));
      }
      const t = [...clau.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('');
      cos.append(peca('text', { x: x0 + r.width + 5, y: y0 + r.height / 2,
        style: `fill:${lc.color};font-family:${lletra};font-size:${lc.fontSize};dominant-baseline:central` }, t));
    }
    y = ll.getBoundingClientRect().bottom - caixa.top;
  }
  // Els crèdits, com a la imatge de Telegram; al mòbil, partits en línies
  // que hi càpiguen, pels « · » si es pot.
  const mida = document.createElement('canvas').getContext('2d');
  mida.font = `13px ${lletra}`;
  const cap = (t) => mida.measureText(t).width <= W;
  const linies = creditsGrafica(fig).flatMap((l) => {
    const res = [];
    for (const tros of l.split(' · ')) {
      const prova = res.length ? `${res[res.length - 1]} · ${tros}` : tros;
      if (res.length && cap(prova)) res[res.length - 1] = prova;
      else res.push(tros);
    }
    return res.flatMap((r) => {
      if (cap(r)) return [r];
      const parts = [];
      for (const paraula of r.split(' ')) {
        const prova = parts.length ? `${parts[parts.length - 1]} ${paraula}` : paraula;
        if (parts.length && cap(prova)) parts[parts.length - 1] = prova;
        else parts.push(paraula);
      }
      return parts;
    });
  });
  linies.forEach((l, k) => cos.append(peca('text', { x: 0, y: y + 22 + k * 19,
    style: `fill:${suau};font-family:${lletra};font-size:13px` }, l)));
  const H = y + 22 + linies.length * 19 + marge;
  tot.setAttribute('width', W + 2 * marge);
  tot.setAttribute('height', H);
  tot.setAttribute('viewBox', `0 0 ${W + 2 * marge} ${H}`);
  tot.append(peca('rect', { width: W + 2 * marge, height: H, style: `fill:${fons}` }), cos);
  return tot;
}

function pngDeLaGrafica(fig, escala = 2) {
  const s = svgDeLaGrafica(fig);
  const W = parseFloat(s.getAttribute('width'));
  const H = parseFloat(s.getAttribute('height'));
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(s)], { type: 'image/svg+xml' }));
  return new Promise((resol, falla) => {
    const im = new Image();
    im.onload = () => {
      const c = document.createElement('canvas');
      c.width = Math.round(W * escala);
      c.height = Math.round(H * escala);
      const ctx = c.getContext('2d');
      ctx.scale(escala, escala);
      ctx.drawImage(im, 0, 0, W, H);
      URL.revokeObjectURL(url);
      c.toBlob((b) => (b ? resol(b) : falla(new Error('png'))), 'image/png');
    };
    im.onerror = () => { URL.revokeObjectURL(url); falla(new Error('svg')); };
    im.src = url;
  });
}

// Al mòbil, el menú de compartir amb la imatge; on no n'hi ha (l'ordinador),
// es copia al porta-retalls, a punt per enganxar (Juanjo, 17-10-2026: «no
// quiero que se baje, quiero que se copie la imagen»). La còpia es demana
// dins del mateix clic, amb la imatge encara per fer (Safari no deixa
// copiar després d'esperar). Si el navegador no deixa copiar, la imatge en
// una finestra, per copiar-la amb el botó dret o mantenint-la premuda.
function nomImatge() {
  const g = GENERAT_GRAFICA ? new Date(GENERAT_GRAFICA) : new Date();
  const dos = (n) => String(n).padStart(2, '0');
  const p = partsHora(g);
  return `temps-montflorit-${p.data}-${dos(p.hora)}${dos(p.minut)}.png`;
}

function potCompartirImatges() {
  try {
    return Boolean(navigator.canShare) && navigator.canShare({ files: [new File([''], 'a.png', { type: 'image/png' })] });
  } catch (_) {
    return false;
  }
}

function comparteixImatge(fig) {
  const png = pngDeLaGrafica(fig);
  if (potCompartirImatges()) {
    png.then((blob) => navigator.share({ files: [new File([blob], nomImatge(), { type: 'image/png' })],
      title: 'Temps a Montflorit', text: creditsGrafica(fig)[0] }))
      .catch((e) => { if (e.name !== 'AbortError') mostraImatge(png); });
    return;
  }
  if (navigator.clipboard && window.ClipboardItem) {
    navigator.clipboard.write([new ClipboardItem({ 'image/png': png })])
      .then(() => avisBreu(T('Imatge copiada')), () => mostraImatge(png));
    return;
  }
  mostraImatge(png);
}

function mostraImatge(png) {
  png.then((blob) => {
    const visor = element('dialog', 'visor');
    const im = element('img');
    im.src = URL.createObjectURL(blob);
    im.alt = T('Gràfica de la previsió hora a hora: perill, cel, temperatura i probabilitat de pluja.');
    const tanca = element('button', 'visor-tanca');
    tanca.type = 'button';
    tanca.title = T('Tanca');
    tanca.setAttribute('aria-label', T('Tanca'));
    tanca.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
    tanca.addEventListener('click', () => visor.close());
    visor.append(im, element('p', 'visor-nota', T('Copia la imatge amb el botó dret o mantenint-la premuda.')), tanca);
    visor.addEventListener('click', (e) => { if (e.target === visor) visor.close(); });
    visor.addEventListener('close', () => { URL.revokeObjectURL(im.src); visor.remove(); });
    document.body.append(visor);
    visor.showModal();
  }, () => avisBreu(T('No s’ha pogut fer la imatge.')));
}

// La càmera: a la vista en gran, al costat de compartir l'enllaç; a
// «Consultes», al final de la llegenda.
// «Opcions» de la gràfica de la portada, al final de la llegenda com la càmera
// de «Consultes»: la icona d'ajustos de Lucide i, a l'ordinador, el text
// (al mòbil no hi cap a la mateixa línia; Juanjo, 20-10-2026).
function botoOpcions() {
  const b = element('button', 'g-opcions');
  b.type = 'button';
  b.title = T('Opcions de la gràfica');
  b.setAttribute('aria-label', T('Opcions de la gràfica'));
  b.append(icona('i-sliders-horizontal'), element('span', 'text-amplia', T('Opcions')));
  b.addEventListener('click', (e) => {
    e.stopPropagation();
    vistaGrafica();
  });
  return b;
}

// L'historial, també a la vista des de la portada: és el que es busca quan es
// vol saber si ha plogut (ADR 0124). Obre la gràfica en gran, ja amb les
// darreres 24 h.
function botoHistorial() {
  const b = element('button', 'g-opcions g-historial');
  b.type = 'button';
  b.title = T('El que es va mesurar al barri, hora a hora');
  b.setAttribute('aria-label', T('Historial'));
  b.append(icona('i-history'), element('span', 'text-amplia', T('Historial')));
  b.addEventListener('click', (e) => {
    e.stopPropagation();
    vistaGrafica('24h');
  });
  return b;
}

function botoImatge(fig, classe) {
  const b = element('button', classe);
  b.type = 'button';
  b.title = T('Comparteix la imatge de la gràfica');
  b.setAttribute('aria-label', T('Comparteix la imatge de la gràfica'));
  b.append(icona('i-camera'));
  b.addEventListener('click', (e) => {
    e.stopPropagation();
    comparteixImatge(fig);
  });
  return b;
}

function dibuixaGrafiques() {
  for (const fig of document.querySelectorAll('figure.grafica')) dibuixaGrafica(fig);
}
addEventListener('resize', dibuixaGrafiques);
// Tocar fora de la gràfica treu el rètol de l'hora.
addEventListener('click', () => {
  for (const fig of document.querySelectorAll('figure.grafica')) fig._amaga?.();
});

