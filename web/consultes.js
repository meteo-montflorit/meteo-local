// SPDX-License-Identifier: AGPL-3.0-or-later
// «Consultes» (ADR 0054): les consultes del bot a la web. Es tria què es vol veure
// i surt només això, com al bot (Juanjo, 09-10-2026: «no quiero una pagina
// enorme… se elige lo que se quiere ver y entonces sale»). Els textos són els
// del bot, fets per les mateixes funcions al servidor (montflorit.py,
// consultes): la web i el bot diuen sempre el mateix.

const FITXER_DADES = document.documentElement.dataset.dades || 'casa.json';
// L'ordre i les claus, les del menú del bot.
// Sense «Ara», «Radar» ni «Avisos actius», que ja surten a «El temps»; amb el
// sol, l'aire i el pol·len, que no surten enlloc més (Juanjo, 09-10-2026).
// Amb la descripció de cada fitxa, en passar-hi el ratolí o mantenint-hi el dit.
const OPCIONS = [
  ['avui', () => T('Avui'), 'i-calendar-check', () => T('La previsió d’avui, amb els avisos i l’estat dels trens.')],
  ['dema', () => T('Demà'), 'i-calendar-plus', () => T('La previsió de demà.')],
  // El sol i la Lluna (Juanjo, 25-10-2026: «datos de la luna en la pestaña de
  // sol, que deberá cambiar de nombre»; ADR 0127). La clau, «sol», no canvia:
  // els enllaços d'abans (consultes.html#sol) hi segueixen portant.
  ['sol', () => T('Sol i lluna'), 'i-sunrise', () => T('La sortida i la posta del sol i de la lluna, les fases de la lluna, les hores de llum i l’índex UV.')],
  ['aire', () => T('Aire'), 'i-factory', () => T('La qualitat de l’aire.')],
  ['pollen', () => T('Pol·len'), 'i-flower', () => T('El nivell de cada tipus de pol·len.')],
  ['trens', () => T('Trens'), 'i-train-front', () => T('L’estat de les línies de Rodalies i FGC de la zona.')],
  ['busos', () => T('Busos'), 'i-bus', () => T('Les línies de bus del barri: hores d’arribada a cada parada i incidències.')],
  ['transit', () => T('Trànsit'), 'i-traffic-cone', () => T('L’estat del trànsit a les carreteres de la zona.')],
  // Els talls de llum a prop, d'e-distribució (ADR 0072).
  ['llum', () => T('Llum'), 'i-zap-off', () => T('Els talls de llum a prop del barri, segons e-distribució.')],
];
const CLAU_TRIADA = 'meteo.consultes';
// «Nou!» damunt d'una opció nova fins que s'obre (ho recorda el navegador) o
// fins a la data, com les pestanyes (comu.js, marcaNovetats).
const NOVETATS_OPCIONS = { busos: { clau: 'meteo.busos-vist', fins: FI_NOU_BUSOS } };

function opcioNova(clau, ara = new Date()) {
  const n = NOVETATS_OPCIONS[clau];
  if (!n || ara >= n.fins) return false;
  try { return localStorage.getItem(n.clau) !== '1'; } catch (_) { return true; }
}

function opcioVista(clau) {
  const n = NOVETATS_OPCIONS[clau];
  if (!n) return;
  try { localStorage.setItem(n.clau, '1'); } catch (_) {}
  const etiqueta = document.querySelector(`#opcions input[value="${clau}"]`)?.parentElement;
  etiqueta?.classList.remove('amb-nou');
  etiqueta?.querySelector('.xip-nou')?.remove();
}
let DADES = null;

// Les adreces d'una part d'una consulta: consultes.html#lluna obre «Sol i
// lluna» i hi baixa fins a la Lluna (Juanjo, 25-10-2026: la Lluna de «Ara» i
// de la gràfica hi porten).
const PARTS = { lluna: ['sol', '.lluna-bloc'] };

// La triada: la de l'adreça (consultes.html#transit), la de l'última vegada en
// aquest dispositiu o, la primera vegada, «Avui».
function triadaInicial() {
  const part = PARTS[location.hash.slice(1)];
  if (part) return part[0];
  const delHash = location.hash.slice(1);
  if (OPCIONS.some(([c]) => c === delHash)) return delHash;
  try {
    const desada = localStorage.getItem(CLAU_TRIADA);
    if (OPCIONS.some(([c]) => c === desada)) return desada;
  } catch (_) {}
  return 'avui';
}
let triada = triadaInicial();

function tria(clau) {
  triada = clau;
  opcioVista(clau);
  try { localStorage.setItem(CLAU_TRIADA, clau); } catch (_) {}
  history.replaceState(null, '', '#' + clau);
  pintaConsulta();
}

function pintaOpcions() {
  const caixa = $('opcions');
  for (const [clau, nom, icon, descripcio] of OPCIONS) {
    const etiqueta = element('label', 'consulta-opcio');
    etiqueta.title = descripcio();
    const boto = element('input');
    boto.type = 'radio';
    boto.name = 'consulta';
    boto.value = clau;
    boto.checked = clau === triada;
    boto.addEventListener('change', () => tria(clau));
    etiqueta.append(boto, icona(icon), element('span', null, nom()));
    if (clau !== triada && opcioNova(clau)) {
      etiqueta.classList.add('amb-nou');
      etiqueta.append(element('span', 'xip-nou', T('Nou!')));
    }
    caixa.append(etiqueta);
  }
}

// Paràgrafs separats per les línies en blanc, com al bot.
function pintaText(text) {
  const peces = [];
  let p = null;
  for (const linia of trossos(text)) {
    if (!linia.length) { p = null; continue; }
    if (p) p.append(element('br'));
    else { p = element('p'); peces.push(p); }
    p.append(...nodesAmbMarques(ambMarques(linia)));
  }
  return peces;
}

// El pol·len, a la web amb una barra de nivell per tipus (de 0 a 4, com
// l'escala del PIA) i la tendència; al bot, el text (Juanjo, 09-10-2026: «es
// una seccion un poco aburrida»). Els que són a zero i estables, en una línia.
const NIVELLS_POLLEN = () => [T('Nul'), T('Baix'), T('Mig'), T('Alt'), T('Màxim')];
const TENDENCIES = () => ({ A: ['↑', T('En augment')], D: ['↓', T('En descens')], '!': ['!', T('Situació excepcional')] });

function dataCurta(iso) {
  const [, m, d] = iso.split('-').map(Number);
  return `${d}/${m}`;
}

function filesPollen(tipus, idioma) {
  const nivells = NIVELLS_POLLEN();
  const tend = TENDENCIES();
  const llista = element('ul', 'pollen');
  const nuls = [];
  for (const t of [...tipus].sort((a, b) => b.nivell - a.nivell)) {
    const nom = t.nom[idioma] || t.nom.ca;
    if (t.nivell === 0 && !tend[t.tendencia]) { nuls.push(nom); continue; }
    const li = element('li', `pollen-fila nivell-${t.nivell}`);
    const barra = element('span', 'pollen-barra');
    barra.setAttribute('aria-hidden', 'true');
    for (let n = 1; n <= 4; n += 1) barra.append(element('span', n <= t.nivell ? 'ple' : null));
    li.append(element('span', 'pollen-nom', nom), barra, element('span', 'pollen-nivell', nivells[t.nivell]));
    const tt = tend[t.tendencia];
    if (tt) {
      const fletxa = element('span', 'pollen-tendencia', tt[0]);
      fletxa.title = tt[1];
      fletxa.setAttribute('aria-label', tt[1]);
      li.append(fletxa);
    }
    llista.append(li);
  }
  const peces = [llista];
  if (nuls.length) peces.push(element('p', 'pollen-nuls', T`${nuls.join(', ')}: nivell nul.`));
  return peces;
}

function pintaPollen(p) {
  const idioma = IDIOMA.codi === 'es' ? 'es' : 'ca';
  const cap = element('p');
  cap.append(element('strong', null, T('Pol·len a Bellaterra')),
    T` (setmana del ${dataCurta(p.inici)} al ${dataCurta(p.fi)}, a ${coma(p.km)} km)`);
  const peces = [cap];
  if (llegeixHora(p.fi + 'T23:59') < new Date()) peces.push(element('p', 'nota', T('Són les dades de l’última setmana publicada.')));
  peces.push(element('h2', 'pollen-grup', T('Pol·len')), ...filesPollen(p.pollens || [], idioma));
  peces.push(element('h2', 'pollen-grup', T('Espores de fongs')), ...filesPollen(p.espores || [], idioma));
  const peu = element('p', 'nota');
  const a = element('a', null, 'Punt d’Informació Aerobiològica (UAB)');
  a.href = (p.url || {})[idioma] || (p.url || {}).ca || 'https://aerobiologia.cat/';
  a.target = '_blank';
  a.rel = 'noopener';
  peu.append(a, ' · CC BY-NC-SA 4.0');
  peces.push(peu);
  return peces;
}

// --- Aire (ADR 0054): l'escala europea amb els seus colors oficials (els de
// l'Agència Europea de Medi Ambient), on és ara, cada contaminant i cada hora
// del que queda del dia. ---
const CATEGORIES_AIRE = ['bona', 'raonablement_bona', 'regular', 'desfavorable', 'molt_desfavorable',
  'extremadament_desfavorable'];
const NOMS_AIRE = () => ({
  bona: T('Bona'), raonablement_bona: T('Raonablement bona'), regular: T('Regular'), desfavorable: T('Desfavorable'),
  molt_desfavorable: T('Molt desfavorable'), extremadament_desfavorable: T('Extremadament desfavorable'),
});
const CONTAMINANTS_AIRE = () => ({ pm2_5: T('Partícules fines (PM2,5)'), pm10: T('Partícules (PM10)'),
  nitrogen_dioxide: T('Diòxid de nitrogen (NO₂)'), ozone: T('Ozó (O₃)'), sulphur_dioxide: T('Diòxid de sofre (SO₂)') });
const categoriaAire = (i) => CATEGORIES_AIRE[[20, 40, 60, 80, 100].filter((l) => i > l).length];
const MESURES_AIRE = () => `https://mediambient.gencat.cat/${IDIOMA.codi === 'es' ? 'es' : 'ca'}/05_ambits_dactuacio/atmosfera/qualitat_de_laire/vols-saber-que-respires/`;

function escalaAire(index) {
  const escala = element('div', 'aire-escala');
  escala.setAttribute('aria-hidden', 'true');
  for (const c of CATEGORIES_AIRE) escala.append(element('span', 'aire-' + c));
  const marca = element('span', 'aire-marca');
  marca.style.left = `${Math.min(index, 120) / 120 * 100}%`;
  escala.append(marca);
  return escala;
}

function pintaAire(a) {
  const noms = NOMS_AIRE();
  const cat = a.categoria || categoriaAire(a.index);
  const cap = element('p');
  cap.append(element('strong', null, T('Qualitat de l’aire a Montflorit')));
  const ara = element('p', 'aire-ara');
  ara.append(element('span', 'aire-xip aire-' + cat, noms[cat]), ' ', T`índex europeu ${a.index}`);
  const peces = [cap, ara, escalaAire(a.index)];
  // Cada contaminant, amb el seu índex, de més a menys.
  const llista = element('ul', 'pollen');
  for (const [c, v] of Object.entries(a.contaminants || {}).sort((x, y) => y[1] - x[1])) {
    const k = categoriaAire(v);
    const li = element('li', 'aire-fila');
    const barra = element('span', 'aire-barra');
    barra.setAttribute('aria-hidden', 'true');
    const ple = element('span', 'aire-' + k);
    ple.style.width = `${Math.max(4, Math.min(v, 100))}%`;
    barra.append(ple);
    li.append(element('span', 'pollen-nom', CONTAMINANTS_AIRE()[c] || c), barra, element('span', 'pollen-nivell', noms[k]));
    llista.append(li);
  }
  if (llista.children.length) peces.push(element('h2', 'pollen-grup', T('Per contaminant')), llista);
  // La resta del dia, hora a hora.
  const hores = a.hores || [];
  if (hores.length > 1) {
    const tira = element('div', 'aire-hores');
    for (const h of hores) {
      const k = categoriaAire(h.index);
      const cel = element('span', 'aire-hora');
      const color = element('span', 'aire-' + k);
      color.title = `${horaCurta(h.hora)} · ${noms[k]} (${h.index})`;
      cel.append(color, element('span', null, h.hora.slice(11, 13)));
      tira.append(cel);
    }
    tira.setAttribute('aria-hidden', 'true');
    peces.push(element('h2', 'pollen-grup', T('La resta del dia')), tira);
    if (a.pitjor && a.pitjor.index > a.index && a.pitjor.categoria !== cat) {
      peces.push(element('p', 'nota', T`El pitjor moment: ${noms[a.pitjor.categoria].toLowerCase()} cap a les ${horaCurta(a.pitjor.hora)}.`));
    }
  }
  // Que és una estimació d'una zona, i què s'ha corregit amb les estacions
  // (Juanjo, 09-10-2026: «¿realmente es la de Montflorit?»).
  const curts = CURT_AIRE();
  const corregits = ORDRE_AIRE.filter((c) => (a.factors || {})[c]).map((c) => curts[c]);
  let nota = T('Estimació del model europeu CAMS per a una zona d’uns 10 km al voltant de Bellaterra, no mesurada a Montflorit');
  if (corregits.length) {
    const llista = corregits.length > 1 ? `${corregits.slice(0, -1).join(', ')} ${T('i')} ${corregits.at(-1)}` : corregits[0];
    nota += T`; ${llista}, corregits amb les mesures de les estacions dels últims 30 dies.`;
  } else nota += '.';
  peces.push(element('p', 'nota', nota));
  const peu = element('p', 'nota');
  peu.append(enllacExtern(T('Mesures de les estacions (Generalitat)'), MESURES_AIRE()));
  peces.push(peu);
  return peces;
}

const ORDRE_AIRE = ['nitrogen_dioxide', 'ozone', 'pm10', 'pm2_5', 'sulphur_dioxide'];
const CURT_AIRE = () => ({ nitrogen_dioxide: 'NO₂', ozone: T('ozó'), pm10: 'PM10', pm2_5: 'PM2,5', sulphur_dioxide: 'SO₂' });


// --- Sol: el recorregut del sol avui sobre l'horitzó de Montflorit, amb el
// del dia més llarg i el del més curt per comparar, on és ara, i l'índex UV
// amb els colors de l'OMS (UV, a grafica.js). Com el de l'app LunaSolCal que
// va ensenyar Juanjo (25-10-2026: «algo parecido a esto … adáptalo como
// quieras»), però amb les hores del rellotge i les direccions en paraules.
const minutsDelDia = (iso) => Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16));
// Dibuix: alçades de -7° a 76°: sota l'horitzó, prou per veure com hi entra
// i en surt (Juanjo, 25-10-2026: «la base oscura redúcela a la mitad»), i a
// dalt, els 72° del migdia del 21 de juny i just el lloc de la xifra de
// l'alçada màxima («sobra mucho espacio por arriba»). I les hores del dia més
// llarg, centrades en el migdia d'avui: tant a cada costat com del migdia a
// la sortida o a la posta del 21 de juny, la més allunyada, i mitja hora més.
// Hi cap la llum de qualsevol dia de l'any, sense els costats buits de 0 a
// 24 h (Juanjo, 25-10-2026: «sobra mucho espacio por los lados»), i el dia
// d'avui queda simètric. L'amplada, la de la fitxa en píxels, perquè el
// dibuix l'ocupi tota amb la lletra sempre de la mateixa mida. Les fixa
// graficaSol.
// A partir de SOL_FILA píxels d'amplada, el dibuix i el text, en fila.
const SOL_FILA = 640;
const SOL_AMPLE = 0.55;
const SOL_MAX = 560;
const SOL_DIB = { ample: 340, alt: 200, esq: 6, dre: 6, dalt: 24, baix: 20, max: 76, min: -7, ini: 0, fi: 1440 };
const solX = (minuts) => SOL_DIB.esq + (minuts - SOL_DIB.ini) / (SOL_DIB.fi - SOL_DIB.ini) * (SOL_DIB.ample - SOL_DIB.esq - SOL_DIB.dre);
const solY = (graus) => SOL_DIB.dalt + (SOL_DIB.max - graus) / (SOL_DIB.max - SOL_DIB.min) * (SOL_DIB.alt - SOL_DIB.dalt - SOL_DIB.baix);

// El recorregut d'un dia (AAAA-MM-DD), cada 5 minuts: es calcula en UTC i
// es dibuixa amb el desfasament (minuts sobre UTC) de l'hora oficial d'avui,
// el mateix per a totes les corbes. El canvi d'hora no les mou: el 21 de juny
// no surt una hora més tard per l'horari d'estiu, i el dia que canvia l'hora
// la corba no fa cap salt (Juanjo, 25-10-2026: «el cambio horario no debe
// nunca distorsionar resultados … internamente siempre utc»).
function recorregutSol(dia, desfas) {
  const punts = [];
  for (let min = 0; min <= 1440; min += 5) punts.push([min, posicioSol(momentSol(dia, min, desfas)).altura]);
  return punts;
}

// El desfasament de l'hora oficial d'un dia (AAAA-MM-DD) a Madrid, el del
// migdia, sigui quina sigui la zona del dispositiu, i el moment d'un minut
// del dibuix d'aquell dia (de 0 a 1440).
const desfasSol = (dia) => desfasHora(`${dia}T12:00`);
function momentSol(dia, min, desfas = desfasSol(dia)) {
  const [a, m, d] = dia.split('-').map(Number);
  return new Date(Date.UTC(a, m - 1, d, 0, min - desfas));
}

function camiSol(punts) {
  return punts.map(([min, alt], n) => `${n ? 'L' : 'M'}${solX(min).toFixed(1)} ${solY(alt).toFixed(1)}`).join('');
}

// Per on surt o es pon, en paraules: de les vuit direccions, la més propera.
function direccioSol(azimut) {
  const noms = [T('pel nord'), T('pel nord-est'), T('per l’est'), T('pel sud-est'), T('pel sud'), T('pel sud-oest'),
    T('per l’oest'), T('pel nord-oest')];
  return noms[Math.round(azimut / 45) % 8];
}

let numSol = 0;
function graficaSol(avui, ara, ample = 340) {
  const any = avui.dia.slice(0, 4);
  const desfas = desfasSol(avui.dia);
  SOL_DIB.ample = ample;
  // Quadrat (Juanjo, 25-10-2026: «para evitar problemas, hazlo cuadrado»,
  // després de demanar-lo més alt dues vegades): les corbes no queden mai
  // aixafades, sigui quina sigui l'amplada.
  SOL_DIB.alt = ample;
  const svg = nodeSvg('svg', { viewBox: `0 0 ${SOL_DIB.ample} ${SOL_DIB.alt}`, class: 'sol-grafica', 'aria-hidden': 'true' });
  const y0 = solY(0);
  const fons = SOL_DIB.alt - SOL_DIB.baix;
  // De nit el sol baixa fins a 70° sota l'horitzó: les corbes, retallades
  // a la part dibuixada, perquè no tapin les hores de sota.
  const retall = `sol-retall-${numSol += 1}`;
  const defs = nodeSvg('defs');
  const clip = nodeSvg('clipPath', { id: retall });
  clip.append(nodeSvg('rect', { x: 0, y: 0, width: SOL_DIB.ample, height: fons }));
  defs.append(clip);
  svg.append(defs, nodeSvg('rect', { x: 0, y: 0, width: SOL_DIB.ample, height: y0, class: 'sol-cel' }));
  const text = (x, y, contingut, classe, ancora = 'middle') => {
    const t = nodeSvg('text', { x: x.toFixed(1), y: y.toFixed(1), class: classe, 'text-anchor': ancora });
    t.textContent = contingut;
    return t;
  };
  // El dia més llarg (ratlles) i el més curt (punts), fins, per comparar: el
  // nom, a la llegenda, perquè al dibuix no hi cap sense tocar les corbes.
  const punts = recorregutSol(avui.dia, desfas);
  const [minMig, altMig] = punts.reduce((x, y) => (y[1] > x[1] ? y : x));
  const juny = recorregutSol(`${any}-06-21`, desfas);
  const deDia = juny.filter(([, alt]) => alt > 0).map(([min]) => min);
  const mig = Math.max(minMig - deDia[0], deDia[deDia.length - 1] - minMig) + 30;
  SOL_DIB.ini = Math.max(0, minMig - mig);
  SOL_DIB.fi = Math.min(1440, minMig + mig);
  for (const [punts, classe] of [[juny, 'sol-ref sol-juny'], [recorregutSol(`${any}-12-21`, desfas), 'sol-ref sol-desembre']]) {
    svg.append(nodeSvg('path', { d: camiSol(punts), class: classe, 'clip-path': `url(#${retall})` }));
  }
  svg.append(nodeSvg('path', { d: camiSol(punts), class: 'sol-avui', 'clip-path': `url(#${retall})` }));
  // La nit, a sobre, perquè la part de sota l'horitzó quedi apagada.
  svg.append(nodeSvg('rect', { x: 0, y: y0, width: SOL_DIB.ample, height: fons - y0, class: 'sol-nit' }));
  svg.append(nodeSvg('line', { x1: 0, x2: SOL_DIB.ample, y1: y0, y2: y0, class: 'sol-horitzo' }));
  const sortida = minutsDelDia(avui.sortida);
  const posta = minutsDelDia(avui.posta);
  // Les guies de la sortida, el migdia i la posta, amb l'hora a dalt.
  const hora = (min) => horaCurta(momentSol(avui.dia, min, desfas));
  // Prop de la vora, l'hora s'alinea amb la vora perquè no quedi tallada (al
  // juny, el sol surt i es pon gairebé als extrems).
  const marge = 22;
  for (const [min, etiqueta] of [[sortida, `↑ ${horaCurta(avui.sortida)}`], [minMig, hora(minMig)], [posta, `↓ ${horaCurta(avui.posta)}`]]) {
    const x = solX(min);
    const [xt, ancora] = x < marge ? [2, 'start'] : x > SOL_DIB.ample - marge ? [SOL_DIB.ample - 2, 'end'] : [x, 'middle'];
    svg.append(nodeSvg('line', { x1: x, x2: x, y1: SOL_DIB.dalt - 6, y2: y0, class: 'sol-guia' }),
      text(xt, SOL_DIB.dalt - 10, etiqueta, 'sol-etiqueta', ancora));
  }
  svg.append(text(solX(minMig) + 12, solY(altMig) - 7, `${Math.round(altMig)}°`, 'sol-etiqueta', 'start'));
  // Les hores, a sota, cada tres; a la vora, alineades amb la vora.
  for (let h = Math.ceil(SOL_DIB.ini / 180) * 3; h * 60 <= SOL_DIB.fi; h += 3) {
    const x = solX(h * 60);
    const [xt, ancora] = x < 14 ? [2, 'start'] : x > SOL_DIB.ample - 14 ? [SOL_DIB.ample - 2, 'end'] : [x, 'middle'];
    svg.append(text(xt, SOL_DIB.alt - 5, `${h} h`, 'sol-eix', ancora));
  }
  // On és ara, si és avui.
  // El minut, el del dibuix (amb el desfasament del migdia), perquè el punt
  // caigui sobre la corba també la nit del canvi d'hora.
  const minAra = Math.round((ara - momentSol(avui.dia, 0, desfas)) / 60000);
  if (diaLocal(ara) === avui.dia && minAra >= SOL_DIB.ini && minAra <= SOL_DIB.fi) {
    const alt = posicioSol(ara).altura;
    const g = nodeSvg('g', { class: alt > -0.8 ? 'sol-ara' : 'sol-ara sol-ara-nit' });
    // De nit, si baixa més del que es dibuixa, al fons de la franja de la nit.
    const y = Math.min(solY(alt), fons - 8);
    g.append(nodeSvg('circle', { cx: solX(minAra), cy: y, r: 11, class: 'sol-ara-halo' }),
      nodeSvg('circle', { cx: solX(minAra), cy: y, r: 6.5, class: 'sol-ara-disc' }));
    svg.append(g);
  }
  return { svg, minMig, altMig };
}

function pintaSol(dies, ara = new Date(), lluna = null) {
  const avui = dies[0];
  const peces = [element('p', null, '')];
  peces[0].append(element('strong', null, T('El sol avui a Montflorit')));
  // L'amplada de dins de la fitxa, en píxels.
  const caixa = $('consulta');
  const estil = caixa && getComputedStyle(caixa);
  const dins = caixa ? caixa.clientWidth - parseFloat(estil.paddingLeft) - parseFloat(estil.paddingRight) : 340;
  // Quadrat i de tota l'amplada al mòbil (Juanjo, 25-10-2026: «que la gráfica
  // ocupe todo el ancho, debe ser cuadrada»); en una pantalla ampla, no («y en
  // pantallas anchas que no ocupe el 100%»): el quadrat, a l'esquerra, del
  // SOL_AMPLE de l'amplada i SOL_MAX píxels com a molt, i el text al costat.
  const ampla = dins >= SOL_FILA;
  const costat = ampla ? Math.min(SOL_MAX, Math.round(dins * SOL_AMPLE)) : Math.max(280, Math.round(dins) || 340);
  const { svg, minMig, altMig } = graficaSol(avui, ara, costat);
  const per = (iso) => direccioSol(posicioSol(new Date(iso)).azimut);
  const mig = horaCurta(momentSol(avui.dia, minMig));
  const dibuix = element('div', 'sol-dibuix');
  const text = element('div', 'sol-text');
  const fila = element('div', ampla ? 'sol-bloc sol-bloc-ample' : 'sol-bloc');
  if (ampla) dibuix.style.width = `${costat}px`;
  fila.append(dibuix, text);
  peces.push(fila);
  dibuix.append(svg);
  const llegenda = element('p', 'sol-llegenda');
  const peca = (classe, nom) => {
    const e = element('span', 'sol-peca');
    e.append(element('span', `sol-mostra ${classe}`), nom);
    return e;
  };
  llegenda.append(peca('sol-mostra-avui', T('avui')), peca('sol-mostra-juny', T('21 de juny, el dia més llarg')),
    peca('sol-mostra-desembre', T('21 de desembre, el més curt')));
  llegenda.setAttribute('aria-hidden', 'true');
  dibuix.append(llegenda);
  const llumMin = minutsDelDia(avui.posta) - minutsDelDia(avui.sortida);
  text.append(element('p', null, T`Surt a les ${horaCurta(avui.sortida)} ${per(avui.sortida)} i es pon a les ${horaCurta(avui.posta)} ${per(avui.posta)}: ${Math.floor(llumMin / 60)} h ${llumMin % 60} min de llum. A les ${mig}, el migdia, puja fins a ${Math.round(altMig)}° sobre l’horitzó.`));
  if (avui.uv_max != null) {
    const uv = Math.round(avui.uv_max);
    const [, classe, nom] = UV().find(([lim]) => uv <= lim);
    const linia = element('p', 'sol-uv');
    linia.append(element('span', 'uv-xip ' + classe, T`UV ${uv}`), ' ', T`Índex UV màxim ${nom}.`);
    if (uv >= 3) linia.append(' ', T('A les hores centrals, protector solar, gorra i ulleres de sol.'));
    text.append(linia);
  }
  if (dies[1]) text.append(element('p', 'nota', T`Demà surt a les ${horaCurta(dies[1].sortida)} i es pon a les ${horaCurta(dies[1].posta)}.`));
  if (lluna) peces.push(blocLluna(lluna, ara, costat, ampla));
  return peces;
}

// La gràfica de la Lluna, com la del sol (Juanjo, 25-10-2026: «un grafico
// similar al del sol para la luna del dia»): l'arc que interessa, el d'ara si
// és a sobre de l'horitzó i, si no, el següent, de 12 hores abans a 12 després
// del moment més alt (lluna.py, recorregut), amb les hores de nit fosques
// (quan el sol és a sota de l'horitzó), la sortida, el moment més alt i la
// posta, i la Lluna on és ara, amb la seva fase.
const LLUNA_DIB = { ample: 340, alt: 340, esq: 6, dre: 6, dalt: 24, baix: 20, max: 80, min: -7 };
function graficaLluna(lluna, ara, ample = 340) {
  const r = lluna.recorregut;
  const D = { ...LLUNA_DIB, ample, alt: ample };
  const inici = llegeixHora(r.inici);
  const fiMin = (r.alt.length - 1) * r.pas;
  const x = (min) => D.esq + (min / fiMin) * (D.ample - D.esq - D.dre);
  const y = (graus) => D.dalt + (D.max - graus) / (D.max - D.min) * (D.alt - D.dalt - D.baix);
  const minDe = (iso) => (llegeixHora(iso) - inici) / 60000;
  const svg = nodeSvg('svg', { viewBox: `0 0 ${D.ample} ${D.alt}`, class: 'sol-grafica lluna-grafica', 'aria-hidden': 'true' });
  const y0 = y(0);
  const fons = D.alt - D.baix;
  const retall = `lluna-retall-${numSol += 1}`;
  const defs = nodeSvg('defs');
  const clip = nodeSvg('clipPath', { id: retall });
  clip.append(nodeSvg('rect', { x: 0, y: 0, width: D.ample, height: fons }));
  defs.append(clip);
  svg.append(defs, nodeSvg('rect', { x: 0, y: 0, width: D.ample, height: y0, class: 'sol-cel' }));
  // Les hores de nit, el cel fosc: quan es veu la Lluna amb el cel negre.
  let nitDes = null;
  for (let min = 0; min <= fiMin; min += r.pas) {
    const nit = posicioSol(new Date(inici.getTime() + min * 60000)).altura < -0.833;
    if (nit && nitDes == null) nitDes = min;
    if ((!nit || min + r.pas > fiMin) && nitDes != null) {
      const fins = nit ? fiMin : min;
      svg.append(nodeSvg('rect', { x: x(nitDes), y: 0, width: x(fins) - x(nitDes), height: y0, class: 'lluna-nit' }));
      nitDes = null;
    }
  }
  const cami = r.alt.map((alt, n) => `${n ? 'L' : 'M'}${x(n * r.pas).toFixed(1)} ${y(alt).toFixed(1)}`).join('');
  svg.append(nodeSvg('path', { d: cami, class: 'lluna-corba', 'clip-path': `url(#${retall})` }));
  svg.append(nodeSvg('rect', { x: 0, y: y0, width: D.ample, height: fons - y0, class: 'sol-nit' }));
  svg.append(nodeSvg('line', { x1: 0, x2: D.ample, y1: y0, y2: y0, class: 'sol-horitzo' }));
  const text = (tx, ty, contingut, classe, ancora = 'middle') => {
    const t = nodeSvg('text', { x: tx.toFixed(1), y: ty.toFixed(1), class: classe, 'text-anchor': ancora });
    t.textContent = contingut;
    return t;
  };
  // La sortida, el moment més alt i la posta, amb l'hora a dalt; a la vora,
  // alineada amb la vora.
  const marge = 22;
  const guies = [[r.sortida, (h) => `↑ ${h}`], [r.culminacio && r.culminacio.hora, (h) => h], [r.posta, (h) => `↓ ${h}`]];
  for (const [iso, etiqueta] of guies) {
    if (!iso) continue;
    const gx = x(minDe(iso));
    const [xt, ancora] = gx < marge ? [2, 'start'] : gx > D.ample - marge ? [D.ample - 2, 'end'] : [gx, 'middle'];
    svg.append(nodeSvg('line', { x1: gx, x2: gx, y1: D.dalt - 6, y2: y0, class: 'sol-guia' }),
      text(xt, D.dalt - 10, etiqueta(horaCurta(iso)), 'sol-etiqueta', ancora));
  }
  if (r.culminacio && r.culminacio.alt > 0) {
    svg.append(text(x(minDe(r.culminacio.hora)) + 12, y(r.culminacio.alt) - 7, `${Math.round(r.culminacio.alt)}°`, 'sol-etiqueta', 'start'));
  }
  // Les hores del rellotge, a sota, cada tres.
  const primera = Math.ceil(inici.getTime() / 36e5) * 36e5;
  for (let t = primera; t <= inici.getTime() + fiMin * 60000; t += 36e5) {
    const h = horaLocal(new Date(t));
    if (h % 3) continue;
    const hx = x((t - inici) / 60000);
    const [xt, ancora] = hx < 14 ? [2, 'start'] : hx > D.ample - 14 ? [D.ample - 2, 'end'] : [hx, 'middle'];
    svg.append(text(xt, D.alt - 5, `${h} h`, 'sol-eix', ancora));
  }
  // On és ara, amb la fase, si és dins del dibuix.
  const minAra = (ara - inici) / 60000;
  if (minAra >= 0 && minAra <= fiMin) {
    const i = Math.min(r.alt.length - 2, Math.floor(minAra / r.pas));
    const alt = r.alt[i] + (r.alt[i + 1] - r.alt[i]) * (minAra / r.pas - i);
    const mida = 22;
    const cy = Math.min(y(alt), fons - mida / 2 - 2);
    const dib = dibuixLluna(lluna.angle);
    for (const [k, v] of Object.entries({ x: x(minAra) - mida / 2, y: cy - mida / 2, width: mida, height: mida })) dib.setAttribute(k, v);
    if (alt < 0) dib.classList.add('lluna-ara-sota');
    svg.append(dib);
  }
  return svg;
}

// Quan, amb el dia si no és avui: «avui a les 17:14», «demà a les 07:37».
function quanArc(iso, ara) {
  const h = horaCurta(iso);
  const d = diesEntre(ara, llegeixHora(iso));
  return d === 0 ? T`avui a les ${h}` : d === 1 ? T`demà a les ${h}` : d === -1 ? T`ahir a les ${h}` : T`a les ${h}`;
}

// La Lluna avui (ADR 0127): la gràfica del seu arc, quina fase és i quina part
// en surt il·luminada, quan surt i es pon, i les fases que vénen.
function blocLluna(lluna, ara = new Date(), costat = 340, ampla = false) {
  const bloc = element('section', 'lluna-bloc');
  const titol = element('p', 'lluna-titol');
  titol.append(element('strong', null, T('La lluna avui a Montflorit')));
  const r = lluna.recorregut;
  // Amb el recorregut, la gràfica i el text al costat o a sota, com el sol;
  // sense (dades d'abans de la 3.204.0), el dibuix gran de la fase.
  const fila = element('div', r ? (ampla ? 'sol-bloc sol-bloc-ample' : 'sol-bloc') : 'lluna-fila');
  const text = element('div', r ? 'sol-text lluna-text' : 'lluna-text');
  const fase = element('p', 'lluna-fase-ara');
  fase.append(dibuixLluna(lluna.angle), T`${nomFaseLluna(lluna, ara)}, il·luminada al ${lluna.il_luminacio} %.`);
  text.append(fase);
  if (r) {
    const dibuix = element('div', 'sol-dibuix');
    if (ampla) dibuix.style.width = `${costat}px`;
    dibuix.append(graficaLluna(lluna, ara, costat));
    const llegenda = element('p', 'sol-llegenda');
    const peca = (classe, nom) => {
      const e = element('span', 'sol-peca');
      e.append(element('span', `sol-mostra ${classe}`), nom);
      return e;
    };
    llegenda.append(peca('lluna-mostra-corba', T('la Lluna')), peca('lluna-mostra-nit', T('nit')));
    llegenda.setAttribute('aria-hidden', 'true');
    dibuix.append(llegenda);
    fila.append(dibuix, text);
  } else {
    const gran = dibuixLluna(lluna.angle);
    gran.classList.add('lluna-gran');
    fila.append(gran, text);
  }
  const h = (iso) => horaCurta(iso);
  const per = (az) => (az == null ? '' : ` ${direccioSol(az)}`);
  let quan = '';
  if (r && r.sortida && r.posta) {
    // L'arc de la gràfica, en paraules, com el del sol.
    quan = T`Surt ${quanArc(r.sortida, ara)}${per(r.sortida_az)} i es pon ${quanArc(r.posta, ara)}${per(r.posta_az)}.`;
    if (r.culminacio && r.culminacio.alt > 0) quan += ' ' + T`A les ${h(r.culminacio.hora)} puja fins a ${Math.round(r.culminacio.alt)}° sobre l’horitzó.`;
  } else {
    // La sortida i la posta, per ordre; un dia al mes no surt o no es pon.
    const { sortida, posta } = lluna.avui || {};
    quan = sortida && posta ? (sortida < posta ? T`Surt a les ${h(sortida)} i es pon a les ${h(posta)}.`
      : T`Es pon a les ${h(posta)} i surt a les ${h(sortida)}.`)
      : sortida ? T`Surt a les ${h(sortida)}; avui no es pon.` : posta ? T`Es pon a les ${h(posta)}; avui no surt.` : '';
  }
  if (quan) text.append(element('p', null, quan));
  const properes = (lluna.fases || []).filter((f) => new Date(f.hora) - ara > -FASE_A_PROP_H * 36e5).slice(0, 4);
  if (properes.length) {
    text.append(element('p', 'lluna-properes-titol', T('Les fases que vénen:')));
    const llista = element('ul', 'lluna-fases');
    for (const f of properes) {
      const li = element('li');
      li.append(dibuixLluna(ANGLE_FASE[f.fase]), `${NOM_FASE_LLUNA()[f.fase]}: ${quanFase(f.hora, ara)}`);
      llista.append(li);
    }
    text.append(llista);
  }
  bloc.append(titol, fila);
  return bloc;
}

// El títol de la fitxa, com al bot.
function titol(text) {
  const p = element('p', 'consulta-titol');
  p.append(element('strong', null, text));
  return p;
}

// Només avisa de les fonts de la fitxa triada: «Avui» i «Demà» surten de la
// previsió (i «Avui», també dels trens); les altres fitxes ja diuen soles
// «Ara aquesta consulta no està disponible» si els falta la dada.
function fontsConsulta() {
  if (triada === 'avui') return [...FONTS_TEMPS, 'trens'];
  return triada === 'dema' ? FONTS_TEMPS : [];
}

// El dibuix del sol es fa a l'amplada de la fitxa: si canvia (girar el mòbil,
// fer la finestra més ampla), es torna a fer. Només si canvia l'amplada: al
// mòbil, la barra de l'adreça que s'amaga en desplaçar també fa «resize», i
// tornar-ho a pintar treia el ressaltat de la Lluna en arribar-hi
// (consultes.html#lluna) i el lloc on es llegia.
let esperaMida = null;
let ampladaSol = typeof window !== 'undefined' ? window.innerWidth : 0;
if (typeof window !== 'undefined' && window.addEventListener) {
  window.addEventListener('resize', () => {
    clearTimeout(esperaMida);
    esperaMida = setTimeout(() => {
      if (window.innerWidth === ampladaSol) return;
      ampladaSol = window.innerWidth;
      if (triada === 'sol') pintaConsulta();
    }, 200);
  });
}

function pintaConsulta() {
  const caixa = $('consulta');
  if (!DADES) return;
  if (!dadesVelles(DADES)) pintaHorari(DADES, fontsConsulta());
  let peces = null;
  if (triada === 'pollen' && DADES.pollen) peces = pintaPollen(DADES.pollen);
  else if (triada === 'aire' && DADES.aire && DADES.aire.index != null) peces = pintaAire(DADES.aire);
  else if (triada === 'sol' && DADES.sol && DADES.sol.length) peces = pintaSol(DADES.sol, new Date(), DADES.lluna);
  else if (triada === 'trens' && DADES.trens && (DADES.trens.linies || []).length) {
    peces = [titol(T('Trens de Cerdanyola')), ...blocTrens(DADES.trens)];
  } else if (triada === 'busos' && DADES.busos) {
    peces = [titol(T('Busos de Montflorit')), ...blocBusos(DADES.busos, new Date())];
  } else if (triada === 'transit' && DADES.transit) {
    peces = [titol(T('Trànsit a menys de 5\u00a0km de Montflorit')), ...blocTransit(DADES.transit)];
    if (!DADES.transit.incidencies.length) peces.splice(1, 0, element('p', null, T('Cap incidència a menys de 5\u00a0km de Montflorit.')));
  }
  if (peces) {
    caixa.replaceChildren(...peces);
    return;
  }
  const textos = (DADES.consultes || {})[IDIOMA.codi === 'es' ? 'es' : 'ca'] || {};
  const text = textos[triada];
  if (!text) caixa.replaceChildren(element('p', 'nota', T('Ara aquesta consulta no està disponible.')));
  else caixa.replaceChildren(...((triada === 'avui' || triada === 'dema') ? ambDetalls(pintaResum(text)) : pintaText(text)));
  // «Avui» i «Demà», amb la gràfica del seu dia sota el títol (Juanjo,
  // 17-10-2026), la mateixa de la portada (grafica.js).
  if (text && (triada === 'avui' || triada === 'dema')) {
    const fig = graficaDia(DADES.hores, DADES.riscos, triada);
    if (fig && caixa.firstElementChild) {
      caixa.firstElementChild.after(fig);
      dibuixaGrafica(fig);
    }
  }
  // Les fitxes que tenen un avís configurable, amb l'enllaç per activar-lo (ADR 0072).
  const avis = { llum: () => T('Per rebre els talls de llum al moment, '),
    avui: () => T('Per rebre la previsió cada dia, '), dema: () => T('Per rebre la previsió cada dia, ') }[triada];
  if (text && avis) caixa.append(enllacAvisos(avis()));
  // «Al barri»: el mapa dels límits, a «Com funciona» (ADR 0072).
  if (text && triada === 'llum') {
    // Cada tall amb el seu punt, al mapa (ADR 0077).
    for (const t of (DADES.llum && DADES.llum.talls) || []) {
      if (t.lat == null || t.lon == null) continue;
      if (CARRERS) caixa.append(mapaTall(t, CARRERS));
      else llegeixCarrers();
    }
    const p = element('p', 'enllac-avisos');
    const a = element('a', null, T('mapa dels límits'));
    a.href = 'com-funciona.html#barri';
    p.append(T('Què compta com a barri: el '), a, '.');
    caixa.append(p);
  }
}

// --- El mapa de cada tall de llum (ADR 0077): un retall del mapa del barri
// d'uns 600 × 450 m al voltant del punt aproximat d'e-distribució, amb els
// carrers probables ressaltats i el nom, i com a molt NOMS_A_PROP noms de
// carrers del voltant que no es trepitgin (Juanjo, 12-10-2026: «hay que evitar
// que quede tan cargado de nombres que no se pueda visualizar bien»). El fons
// (img/mapa-base.svg) i els carrers (img/carrers.json) els fa
// eines/mapa_barri.py amb OpenStreetMap; aquí no es demana res a fora. ---
let CARRERS = null;
let llegintCarrers = false;
const FINESTRA = [330, 250];
const NOMS_A_PROP = 4;
const A_PROP = 160;          // unitats del dibuix: uns 290 m
const SEPARACIO = 60;
const SVG = 'http://www.w3.org/2000/svg';

function llegeixCarrers() {
  if (llegintCarrers) return;
  llegintCarrers = true;
  fetch(ARREL + 'img/carrers.json').then((r) => r.json()).then((d) => {
    CARRERS = d;
    if (triada === 'llum') pintaConsulta();
  }, () => {});
}

// «Carrer de Sant Jeroni» → «Sant Jeroni», com al mapa general.
function nomCurt(nom) {
  const abreujats = [['Avinguda de la ', 'Av. '], ['Avinguda del ', 'Av. '], ['Avinguda de ', 'Av. '],
    ['Avinguda d\u2019', 'Av. '], ["Avinguda d'", 'Av. '], ['Avinguda ', 'Av. '], ['Passeig de ', 'Pg. '],
    ['Passatge de ', 'Ptge. '], ['Carrer de la ', ''], ['Carrer de les ', ''], ["Carrer de l'", ''],
    ['Carrer dels ', ''], ['Carrer del ', ''], ['Carrer de ', ''], ["Carrer d'", ''], ['Carrer ', '']];
  const a = abreujats.find(([llarg]) => nom.startsWith(llarg));
  return a ? a[1] + nom.slice(a[0].length) : nom;
}

function alDibuix(m, lon, lat) {
  return [(lon - m.lon0) * m.kx - m.ox, m.oy - (lat - m.lat0) * m.ky];
}

// La finestra del retall, centrada al punt i sense sortir del dibuix.
function finestra(m, x, y) {
  const [w, h] = FINESTRA;
  return [Math.max(0, Math.min(m.W - w, x - w / 2)), Math.max(0, Math.min(m.H - h, y - h / 2)), w, h];
}

// Els trossos de cada tram dins de la finestra (amb marge), en parells [x, y].
function trossosDins(trams, [vx, vy, w, h], marge = 8) {
  const res = [];
  for (const t of trams) {
    let tros = [];
    for (let i = 0; i < t.length; i += 2) {
      const p = [t[i], t[i + 1]];
      if (p[0] >= vx + marge && p[0] <= vx + w - marge && p[1] >= vy + marge && p[1] <= vy + h - marge) tros.push(p);
      else { if (tros.length > 1) res.push(tros); tros = []; }
    }
    if (tros.length > 1) res.push(tros);
  }
  return res;
}

const llargada = (t) => t.slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - t[i][0], p[1] - t[i][1]), 0);
const distPunt = (t, x, y) => Math.min(...t.map((p) => Math.hypot(p[0] - x, p[1] - y)));

// Els trossos d'un tram prou llargs per al nom i gairebé rectes (la corda,
// com a mínim RECTE de la llargada): en una corba tancada, el nom es
// trencaria o quedaria del revés.
const RECTE = 0.9;
function trossosPerAlNom(tram, cal) {
  const res = [];
  for (let i = 0; i < tram.length - 1; i += 1) {
    let l = 0;
    for (let j = i + 1; j < tram.length; j += 1) {
      l += Math.hypot(tram[j][0] - tram[j - 1][0], tram[j][1] - tram[j - 1][1]);
      if (l < cal) continue;
      const tros = tram.slice(i, j + 1);
      const corda = Math.hypot(tros.at(-1)[0] - tros[0][0], tros.at(-1)[1] - tros[0][1]);
      if (corda >= RECTE * l) res.push(tros);
      break;
    }
  }
  return res;
}

// El punt de la meitat del recorregut, on va el centre del nom.
function puntMig(tros) {
  let falta = llargada(tros) / 2;
  for (let i = 1; i < tros.length; i += 1) {
    const l = Math.hypot(tros[i][0] - tros[i - 1][0], tros[i][1] - tros[i - 1][1]);
    if (l >= falta) {
      const f = l ? falta / l : 0;
      return [tros[i - 1][0] + (tros[i][0] - tros[i - 1][0]) * f, tros[i - 1][1] + (tros[i][1] - tros[i - 1][1]) * f];
    }
    falta -= l;
  }
  return tros.at(-1);
}

// Quins noms van al mapa: primer els carrers probables; després, els més
// propers del voltant. Cadascun, en un tros recte on hi càpiga i que no
// trepitgi cap altre nom; si no n'hi ha, sense nom.
function nomsDelMapa(m, t, fin, x, y) {
  const triats = [];
  const centres = [];
  const probables = t.carrers || [];
  const candidats = Object.entries(m.carrers).map(([nom, trams]) => {
    const dins = trossosDins(trams, fin);
    if (!dins.length) return null;
    return { nom, dins, dist: Math.min(...dins.map((d) => distPunt(d, x, y))), probable: probables.includes(nom) };
  }).filter(Boolean).sort((a, b) => (b.probable - a.probable) || (a.dist - b.dist));
  let altres = 0;
  for (const c of candidats) {
    if (!c.probable && (altres >= NOMS_A_PROP || c.dist > A_PROP)) continue;
    const text = nomCurt(c.nom);
    const mida = c.probable ? 12 : 10.5;
    const cal = text.length * mida * 0.58 + 12;
    const trossos = c.dins.flatMap((d) => trossosPerAlNom(d, cal)).map((tros) => {
      const mig = puntMig(tros);
      return { tros, mig, dist: Math.hypot(mig[0] - x, mig[1] - y) };
    }).filter((q) => q.dist > 28 && !centres.some((p) => Math.hypot(p[0] - q.mig[0], p[1] - q.mig[1]) < SEPARACIO))
      .sort((p, q) => p.dist - q.dist);
    if (!trossos.length) continue;
    centres.push(trossos[0].mig);
    triats.push({ ...c, tram: trossos[0].tros, text, mida });
    if (!c.probable) altres += 1;
  }
  return triats;
}

function nodeSvg(nom, atributs = {}) {
  const n = document.createElementNS(SVG, nom);
  for (const [k, v] of Object.entries(atributs)) n.setAttribute(k, v);
  return n;
}

let numMapa = 0;
function mapaTall(t, m) {
  const [x, y] = alDibuix(m, t.lon, t.lat);
  const fin = finestra(m, x, y);
  const id = `mapa${++numMapa}`;
  const probables = t.carrers || [];
  const descripcio = probables.length
    ? T`Mapa del tall de llum: punt aproximat a ${probables.map(nomCurt).join(T(' o '))}.`
    : T('Mapa del tall de llum: punt aproximat.');
  const svg = nodeSvg('svg', { viewBox: fin.join(' '), role: 'img', 'aria-label': descripcio, class: 'mapa-tall-svg' });
  svg.append(nodeSvg('image', { href: ARREL + 'img/mapa-base.svg', x: 0, y: 0, width: m.W, height: m.H }));
  // Els carrers probables, ressaltats.
  for (const nom of probables) {
    for (const tram of m.carrers[nom] || []) {
      const punts = [];
      for (let i = 0; i < tram.length; i += 2) punts.push(`${tram[i]} ${tram[i + 1]}`);
      svg.append(nodeSvg('path', { d: `M${punts.join(' ')}`, fill: 'none', stroke: '#f59e0b', 'stroke-width': 7,
        'stroke-opacity': '.75', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
    }
  }
  // El punt, aproximat: un cercle ample al voltant.
  svg.append(nodeSvg('circle', { cx: x, cy: y, r: 22, fill: '#dc2626', 'fill-opacity': '.16', stroke: '#dc2626',
    'stroke-opacity': '.5', 'stroke-dasharray': '4 3' }));
  svg.append(nodeSvg('circle', { cx: x, cy: y, r: 6, fill: '#dc2626', stroke: '#fff', 'stroke-width': 2 }));
  nomsDelMapa(m, t, fin, x, y).forEach((n, i) => {
    const via = `${id}-via${i}`;
    const tram = n.tram[n.tram.length - 1][0] >= n.tram[0][0] ? n.tram : [...n.tram].reverse();
    svg.append(nodeSvg('path', { id: via, d: `M${tram.map((p) => p.join(' ')).join(' ')}`, fill: 'none' }));
    const text = nodeSvg('text', { 'font-size': n.mida, 'font-weight': n.probable ? 700 : 600, dy: 4,
      fill: n.probable ? '#7c2d12' : '#3d3d3d', stroke: '#fff', 'stroke-width': 3, 'paint-order': 'stroke' });
    const cami = nodeSvg('textPath', { href: `#${via}`, startOffset: '50%', 'text-anchor': 'middle' });
    cami.textContent = n.text;
    text.append(cami);
    svg.append(text);
  });
  const font = nodeSvg('text', { x: fin[0] + fin[2] - 5, y: fin[1] + fin[3] - 5, 'font-size': 9, 'text-anchor': 'end',
    fill: '#555', stroke: '#f4f1ea', 'stroke-width': 3, 'paint-order': 'stroke' });
  font.textContent = '© OpenStreetMap';
  svg.append(font);
  const figura = element('figure', 'mapa-tall');
  figura.append(svg, element('figcaption', null, T('Punt aproximat del tall, segons e-distribució; els carrers ressaltats, estimats.')));
  return figura;
}

// Si s'hi arriba per un enllaç (consultes.html#llum), la consulta es destaca
// la primera vegada que es pinta.
let assenyalada = !OPCIONS.some(([c]) => c === location.hash.slice(1)) && !PARTS[location.hash.slice(1)];

// Què es destaca en arribar: la part (la Lluna) o la consulta sencera.
function assenyalaArribada() {
  const part = PARTS[location.hash.slice(1)];
  assenyala((part && $('consulta').querySelector(part[1])) || $('consulta'));
}
function pinta(dades) {
  DADES = dades;
  LLUNA = dades.lluna || null;
  GENERAT_GRAFICA = dades.generat;
  AVISOS_GRAFICA = dades;
  // Dades de fa massa: només l'avís i on mirar (ADR 0031).
  const velles = dadesVelles(dades);
  $('opcions').hidden = velles;
  if (velles) $('consulta').replaceChildren(blocDadesVelles(dades));
  else pintaConsulta();
  pintaHorari(dades, fontsConsulta());
  posaVersio(dades.versio);
  if (!assenyalada && !velles) {
    assenyalada = true;
    assenyalaArribada();
  }
}

// Quan arriba l'historial de «Perill» (comu.js), les alertes del resum ja
// poden portar a la seva fitxa.
function repintaAvisos() {
  if (DADES && !dadesVelles(DADES) && (triada === 'avui' || triada === 'dema')) pintaConsulta();
}

pintaOpcions();
opcioVista(triada);
window.addEventListener('hashchange', () => {
  const part = PARTS[location.hash.slice(1)];
  const clau = part ? part[0] : location.hash.slice(1);
  if (!OPCIONS.some(([c]) => c === clau)) return;
  if (clau !== triada) {
    triada = clau;
    opcioVista(clau);
    for (const r of document.querySelectorAll('#opcions input')) r.checked = r.value === clau;
    pintaConsulta();
  } else if (!part) return;
  assenyalaArribada();
});
carrega(FITXER_DADES, pinta, () => {
  $('consulta').replaceChildren(element('p', 'avis', T('No s’ha pogut carregar la previsió. Torna-ho a provar d’aquí a una estona.')));
});
