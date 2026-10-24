// SPDX-License-Identifier: AGPL-3.0-or-later
// Llegeix casa.json (el genera casa.py) i pinta el temps a casa: el que mesura
// ara l'estació de casa i la previsió hora a hora, 24 hores com a mínim i
// fins a les 21 h de demà (ADR 0041).

// La pàgina pública («Temps a Montflorit», ADR 0024) és aquesta mateixa amb
// tres coses canviades a l'etiqueta <html>: el nom del lloc, com s'anomena
// l'estació pròpia i el fitxer de dades.
const LLOC = document.documentElement.dataset.lloc || 'casa';
const ESTACIO_PROPIA = document.documentElement.dataset.estacio || 'l\u2019estació de casa';
const FITXER_DADES = document.documentElement.dataset.dades || 'casa.json';

// La temperatura i la pressió, de l'estació de casa; la pluja i la humitat, de
// la xarxa del barri (casa.consens); el vent, de Meteocat.
// Cada dada, amb la seva icona, perquè es llegeixi d'una ullada.
function dada(id, text) {
  const li = element('li');
  li.append(icona(id), document.createTextNode(text));
  return li;
}

// Resum del que ve per trams del dia (matí 7–14, tarda 14–21, nit 21–7): el
// cel i les temperatures sempre; la pluja, només si alguna hora en té com a
// mínim de possible (Juanjo, 09-10-2026: «símbolo de lluvia solo si va a
// llover»); els fenòmens, només quan es donen, amb els llindars grocs del Pla
// Meteoalerta que ja usa config.RISC_LLINDARS, més neu i gel. Cada tram és un
// desplegable de la taula, amb aquest resum a la capçalera (Juanjo,
// 09-10-2026: «dividir la lista del tiempo en mañana, tarde, noche como
// desplegables»).
const TRAMS = [[7, 14, 'Matí'], [14, 21, 'Tarda'], [21, 7, 'Nit']];
// Les ratxes i la calor, amb els llindars del temps extrem (config.RISC_LLINDARS,
// els baixos de Meteocat, superats «amb més que»): abans 70 km/h i 36 °C, i
// l'etiqueta sortia sense l'avís corresponent (inventari del 18-10-2026).
const FENOMENS = { pluja_forta: INTENSITAT_PLUJA[1], pluja_torrencial: INTENSITAT_PLUJA[2], ratxa: 72, calor: 36.8, glaçada: 0 };
// El llindar taronja de les ratxes (config.RISC_LLINDARS, l'alt de Meteocat).
const RATXA_TARONJA = 108;
// Els noms, amb T() literal perquè les proves de traducció els trobin.
const NOM_TRAM = { Matí: () => T('Matí'), Tarda: () => T('Tarda'), Nit: () => T('Nit') };
const NOM_TRAM_DEMA = { Matí: () => T('Demà matí'), Tarda: () => T('Demà tarda'), Nit: () => T('Demà nit') };
const NOM_FENOMEN = {
  tempesta: () => T('tempesta'), pluja_forta: () => T('pluja forta'), pluja_torrencial: () => T('pluja torrencial'),
  neu: () => T('neu'), calor: () => T('calor'), glaçada: () => T('glaçada'),
  glaçadaRiera: () => T('glaçada vora la riera'),
};

function tramDe(f) {
  const d = new Date(f.hora);
  const h = d.getHours();
  const [ini, fi, nom] = TRAMS.find(([a, b]) => (a < b ? h >= a && h < b : h >= a || h < b));
  // La nit comença el dia anterior si som a la matinada.
  const dia = new Date(d);
  if (nom === 'Nit' && h < 7) dia.setDate(dia.getDate() - 1);
  return { clau: `${dia.toDateString()}|${nom}`, nom, ini, fi, dia };
}

// El cel del tram: boira si n'hi ha la major part de les hores; si no, la
// mitjana dels núvols. Només el cel: la pluja la diu el paraigua.
function celTram(files, nit) {
  if (files.filter(esBoira).length * 2 > files.length) return [T('Boira'), 'i-cloud-fog'];
  const n = files.filter((f) => f.nuvols != null).map(nuvolsHora);
  return n.length ? celNuvols(n.reduce((a, b) => a + b, 0) / n.length, nit) : null;
}

// Tots els trams que toca la previsió, sense les hores ja passades. Les hores
// diuen les que hi ha de veritat: el tram en curs, «fins a les…», i l'últim,
// sencer (casa.py arriba fins a les 21 h de demà i acaba amb un tram), o fins
// on arribin les dades si en falten.
// Quants graus més o menys que el dia abans (Juanjo, 10-10-2026; ADR 0061):
// el tram d'avui, amb les mateixes hores d'ahir, mesurades a l'estació; el de
// demà, amb avui (el mesurat fins ara i la previsió de la resta). La màxima de
// dia i la mínima de nit; la xifra, només des de COMPARA_MIN graus. Igual que
// bot.compara_temp, que les proves comparen.
const COMPARA_MIN = 2;

function diaAbans(clau) {
  // Sense el desfase de l'hora que es repeteix a l'octubre («T02:00+01:00»):
  // el dia abans, aquella hora només hi és una vegada.
  const [dia, resta] = clau.split('T');
  const hora = resta.slice(0, 5);
  const t = new Date(`${dia}T12:00`);
  t.setDate(t.getDate() - 1);
  const dos = (n) => String(n).padStart(2, '0');
  return `${t.getFullYear()}-${dos(t.getMonth() + 1)}-${dos(t.getDate())}T${hora}`;
}

function comparaTemp(files, nit, mesurada, totes) {
  if (!mesurada || !Object.keys(mesurada).length || !files.length) return null;
  const previstes = Object.fromEntries((totes || []).map((f) => [f.hora, f]));
  const abans = [];
  for (const f of files) {
    const a = mesurada[diaAbans(f.hora)];
    const b = mesurada[diaAbans(f.fins)];
    const p = previstes[diaAbans(f.hora)];
    const v = a != null && b != null ? (a + b) / 2 : (p ? p.temperatura : null);
    if (v == null || f.temperatura == null) return null;
    abans.push(v);
  }
  const ara = files.map((f) => f.temperatura);
  // Se restan las cifras ya redondeadas, las que se leen en las cabeceras.
  return nit ? Math.round(Math.min(...ara)) - Math.round(Math.min(...abans))
    : Math.round(Math.max(...ara)) - Math.round(Math.max(...abans));
}

function textComparacio(n, esDema) {
  if (n == null) return null;
  if (Math.abs(n) < COMPARA_MIN) return esDema ? T('semblant a avui') : T('semblant a ahir');
  if (esDema) return n > 0 ? T`${Math.abs(n)}° més que avui` : T`${Math.abs(n)}° menys que avui`;
  return n > 0 ? T`${Math.abs(n)}° més que ahir` : T`${Math.abs(n)}° menys que ahir`;
}

// El dia, com l'anterior, a «Ara», sota la temperatura (Juanjo, 23-10-2026:
// «si el día es como el de ayer, más frío, más cálido»; ADR 0061): el mateix
// compte que la línia de la temperatura del resum del bot (bot.compara_resum),
// la màxima de les hores de dia (TRAM_DIA). Fins a HORA_DEMA, les que queden
// d'avui contra les mateixes d'ahir; des de llavors, demà contra avui, com el
// resum, que llavors passa a demà.
const TRAM_DIA = [7, 21];

// Les hores amb la temperatura de la zona triada (ADR 0123), per als comptes
// que fan servir «temperatura» (comparaTemp).
function ambTempZona(files) {
  return (files || []).map((f) => (f.temperatura == null ? f : { ...f, temperatura: tempZona(f) }));
}

// El que s'ha mesurat cada hora a la zona triada: a la riera, l'estació de
// casa; a la part alta, la mediana de les de dalt (part_alta.mesurada). Sense
// (la reserva), no es compara.
function mesuradaZona(dades) {
  return zonaTriada() === 'alta' ? dades.temperatura_mesurada_alta : dades.temperatura_mesurada;
}

function comparaDia(hores, mesurada, ara = new Date()) {
  const dema = ara.getHours() >= HORA_DEMA;
  const dia = new Date(ara);
  if (dema) dia.setDate(dia.getDate() + 1);
  const files = (hores || []).filter((f) => {
    const h = new Date(f.hora);
    return new Date(f.fins) > ara && h.toDateString() === dia.toDateString()
      && h.getHours() >= TRAM_DIA[0] && h.getHours() < TRAM_DIA[1];
  });
  const text = textComparacio(comparaTemp(ambTempZona(files), false, mesurada, ambTempZona(hores)), dema);
  if (!text) return null;
  const alta = zonaTriada() === 'alta';
  const mesurat = (ahir = false) => (alta
    ? (ahir ? T('van mesurar ahir les estacions de la part alta') : T('han mesurat les estacions de la part alta'))
    : (ahir ? T('va mesurar ahir l’estació de vora la riera') : T('ha mesurat l’estació de vora la riera')));
  return {
    text: dema ? T`Demà, ${text}` : T`Avui, ${text}`,
    // Què compara, en prémer-la, com la part alta.
    explica: dema
      ? T`La màxima de demà, comparada amb la d’avui a les mateixes hores: el que ${mesurat()} i la previsió per a la resta. Amb menys de 2 graus de diferència, «semblant».`
      : T`La màxima de les hores de dia que queden avui, comparada amb la que ${mesurat(true)} a les mateixes hores. Amb menys de 2 graus de diferència, «semblant».`,
  };
}

// D'on surt la tempesta d'un tram: d'un avís oficial o dels models.
function origenTempesta(files) {
  const avis = files.flatMap((f) => (f.avisos || []).filter((a) => (a.tipus || []).includes('tempestes')))[0];
  const font = avis && (avis.font === 'meteocat' ? 'Meteocat' : 'AEMET');
  const parts = [];
  if (font === 'AEMET') parts.push(T`AEMET: avís ${TD(avis.nivell)} per tempestes`);
  else if (font) parts.push(T`Meteocat: perill ${GRAU_METEOCAT()[avis.nivell]} per tempestes`);
  if (files.some((f) => f.codi >= 95)) parts.push(T('Els models preveuen tempesta'));
  return parts.join('; ');
}

// El perill d'un tram: el nivell més alt de les seves hores i què és.
function perillTram(files) {
  return delNivellMesAlt(files.flatMap(elementsPerill));
}

// La probabilitat d'una hora per a la quantitat esperada: 1 si ja plou; sense
// probabilitat (previsió vella), 1 si el model dona pluja i 0 si no.
function probHora(f) {
  if (f.plou_ara) return 1;
  if (f.probabilitat == null) return (f.pluja_mm || 0) >= 0.2 ? 1 : 0;
  return f.probabilitat;
}

function resumTrams(hores, ara, mesurada) {
  const grups = [];
  for (const f of hores || []) {
    if (new Date(f.fins) <= ara) continue;
    const t = tramDe(f);
    let g = grups.find((x) => x.clau === t.clau);
    if (!g) grups.push(g = { ...t, files: [] });
    g.files.push(f);
  }
  const dema = new Date(ara);
  dema.setDate(dema.getDate() + 1);
  return grups.map((g) => {
    // Les temperatures de la zona triada amb el botó de dalt (ADR 0123): la
    // riera o la part alta, amb la diferència de cada hora (ADR 0087).
    const temps = g.files.map(tempZona).filter((t) => t != null);
    const riera = g.files.map((f) => f.temperatura).filter((t) => t != null);
    const fenomens = [];
    const tempesta = (f) => f.codi >= 95 || (f.avisos || []).some((a) => (a.tipus || []).includes('tempestes'));
    if (g.files.some(tempesta)) fenomens.push([NOM_FENOMEN.tempesta(), 'i-cloud-lightning', origenTempesta(g.files)]);
    // La pluja forta, només a les hores en què pot ploure (plujaHora), com el
    // cel de la taula: els mil·límetres sols no diuen si n'hi haurà
    // (inventari del 18-10-2026).
    const mmPluja = (f) => (plujaHora(f) ? f.pluja_mm || 0 : 0);
    if (g.files.some((f) => mmPluja(f) >= FENOMENS.pluja_torrencial)) fenomens.push([NOM_FENOMEN.pluja_torrencial(), 'i-cloud-rain-wind']);
    else if (g.files.some((f) => mmPluja(f) >= FENOMENS.pluja_forta)) fenomens.push([NOM_FENOMEN.pluja_forta(), 'i-cloud-rain-wind']);
    if (g.files.reduce((s, f) => s + (f.neu || 0), 0) >= 0.1) fenomens.push([NOM_FENOMEN.neu(), 'i-snowflake']);
    const ratxa = Math.max(...g.files.map((f) => f.ratxa || 0));
    if (ratxa > FENOMENS.ratxa) fenomens.push([T`ratxes de ${Math.round(ratxa)}\u00a0km/h`, 'i-wind']);
    if (temps.length && Math.max(...temps) > FENOMENS.calor) fenomens.push([NOM_FENOMEN.calor(), 'i-thermometer-sun']);
    // La glaçada de la riera surt també mirant la part alta: s'hi passa per
    // anar i venir (ADR 0123).
    if (temps.length && Math.min(...temps) <= FENOMENS.glaçada) fenomens.push([NOM_FENOMEN.glaçada(), 'i-thermometer-snowflake']);
    else if (riera.length && Math.min(...riera) <= FENOMENS.glaçada) {
      fenomens.push([NOM_FENOMEN.glaçadaRiera(), 'i-thermometer-snowflake']);
    }
    const esDema = g.dia.toDateString() === dema.toDateString();
    const actual = new Date(g.files[0].hora) <= ara;
    const fi = new Date(g.files[g.files.length - 1].fins).getHours();
    return {
      clau: g.clau,
      nom: (esDema ? NOM_TRAM_DEMA : NOM_TRAM)[g.nom](),
      hores: actual ? T`fins a les ${fi} h` : `${g.ini}–${fi} h`,
      cel: celTram(g.files, g.nom === 'Nit'),
      plou: g.files.some((f) => plujaHora(f) !== null),
      prob: Math.max(...g.files.map((f) => f.probabilitat || 0)),
      // La quantitat esperada del tram: la probabilitat de cada hora pels seus
      // mil·límetres (que són «si plou»). Sumar els mil·límetres de totes les
      // hores donava el doble del que queia (arxiu 2024-2026, ADR 0103).
      mm: g.files.reduce((s, f) => s + probHora(f) * (f.pluja_mm || 0), 0),
      tMin: temps.length ? Math.min(...temps) : null, tMax: temps.length ? Math.max(...temps) : null,
      compara: textComparacio(comparaTemp(ambTempZona(g.files), g.nom === 'Nit', mesurada, ambTempZona(hores)), esDema),
      fenomens,
      avis: g.files.some((f) => avisHora(f)),
      perill: perillTram(g.files),
      files: g.files,
    };
  });
}

// La capçalera del desplegable: el nom del tram, les hores i el resum.
function resumTram(t) {
  const sum = element('summary');
  sum.append(element('strong', null, t.nom), element('span', 'quan', ` (${t.hores})`));
  const peca = (id, text, classe = 'dada', titol = '') => {
    const s = element('span', classe);
    if (titol) s.title = titol;
    const contingut = element('span');
    contingut.append(...[].concat(text));
    s.append(icona(id), typeof text === 'string' ? text : contingut);
    sum.append(s);
  };
  if (t.cel) peca(t.cel[1], t.cel[0]);
  if (t.tMin != null) {
    // La mínima en blau i la màxima en vermell, com Meteocat (ADR 0063).
    const [min, max] = [Math.round(t.tMin), Math.round(t.tMax)];
    const xifres = min === max ? [`${min}`] : [element('span', 'temp-min', `${min}`), '–', element('span', 'temp-max', `${max}`)];
    // Cada tros sencer; si no hi cap, la part alta i la comparació passen a
    // la línia següent (Juanjo, 13-10-2026: «en movil … se desborda»).
    const nucli = element('span', 'tros');
    nucli.append(...xifres, ' °C');
    const trossos = [nucli];
    // La comparació, diferenciada de la temperatura per llegir-ho d'una
    // ullada (Juanjo, 13-10-2026). Sense l'etiqueta de la part alta des de la
    // 3.191.0: ja la tria el botó de dalt (ADR 0123).
    if (t.compara) trossos.push(' ', element('span', 'tros compara', `· ${t.compara}`));
    peca('i-thermometer', trossos, 'dada temp');
  }
  // El perill, primer i del color del nivell, com els avisos de dalt (ADR 0076).
  if (t.perill) {
    const xip = element('span', `perill-tram ${t.perill.nivell}`);
    xip.append(icona('i-triangle-alert'), textPerillCurt(t.perill));
    // D'on surt, en passar-hi el ratolí (Juanjo, 16-10-2026).
    xip.title = textPerill(t.perill);
    sum.append(xip);
  }
  if (t.plou) peca('i-umbrella', `${Math.round(t.prob * 100)} %` + (t.mm >= 1 ? T`, uns ${coma(t.mm, 0)} mm` : ''));
  for (const [text, id, origen] of t.fenomens) peca(id, text, 'dada fenomen', origen);
  return sum;
}

// «Ara» i la resta del dia en una sola targeta, sense repetir res (Juanjo,
// 17-10-2026: «las tarjetas ara y avui deberían juntarse y simplificarlas…
// sin repetirse arriba y abajo»; ADR 0074): a dalt, el que es mesura ara; a
// sota, el resum d'avui (el de «Consultes › Avui», sense el títol), amb el que
// falta per a la pluja dins la seva línia, i el radar, si diu alguna cosa.
// La conclusió, a dalt de tot d'«Ara» (portada nova, ADR 0118): el cel dels
// dos trams que venen i la pluja de les 24 hores, amb les mateixes peces de la
// taula (resumTrams) i de la línia de pluja (liniaPlujaPrevista), perquè no
// digui res diferent. Si plou o el radar en veu, la pluja la diu el radar:
// aquí, la seva conclusió, i el requadre, sota la gràfica.
const QUAN_TRAM = { Matí: () => T('Aquest matí'), Tarda: () => T('Aquesta tarda'), Nit: () => T('Aquesta nit') };
const QUAN_TRAM_DEMA = { Matí: () => T('Demà al matí'), Tarda: () => T('Demà a la tarda'), Nit: () => T('Demà a la nit') };

// Com es nota el tram, en paraules del carrer i sense xifres (Juanjo,
// 22-10-2026: «algo que haga referencia a si hace frío o calor o heladas…
// no quiero datos»): set nivells orientatius, de Juanjo, no cap classificació
// oficial. La temperatura que es nota (amb el vent quan fa fred),
// arrodonida: la mínima a la nit i al matí, la màxima a la tarda. Al matí,
// si després escalfa fins a una altra paraula, també aquesta, «fresc i
// després agradable»: la mínima del matí és la de l'alba, la mateixa de la
// nit, i sense això l'escalfament del matí no sortia enlloc (Juanjo,
// 22-10-2026). El refredament de la tarda ja el diu la nit, el tram següent.
const SENSACIO = [[-1, 'fred intens'], [5, 'molt fred'], [11, 'fred'], [17, 'fresc'], [25, 'agradable'],
  [32, 'calor'], [Infinity, 'molta calor']];
const PARAULA_SENSACIO = {
  'fred intens': () => T('amb fred intens'), 'molt fred': () => T('amb molt de fred'), fred: () => T('fred'),
  fresc: () => T('fresc'), agradable: () => T('temperatura agradable'), calor: () => T('amb calor'),
  'molta calor': () => T('amb molta calor'),
};
function sensacioTram(t) {
  const notes = t.files.filter((f) => f.temperatura != null).map((f) => esNota(tempZona(f), f.vent || 0));
  if (!notes.length) return null;
  const nivell = (v) => SENSACIO.find(([fins]) => Math.round(v) <= fins)[1];
  if (t.clau.endsWith('|Tarda')) return nivell(Math.max(...notes));
  const inici = nivell(Math.min(...notes));
  if (!t.clau.endsWith('|Matí')) return inici;
  // Només si la màxima ve després de la mínima: un matí que es refreda no escalfa.
  const despres = nivell(Math.max(...notes.slice(notes.indexOf(Math.min(...notes)))));
  return despres === inici ? inici : `${inici}>${despres}`;
}

// La sensació en paraules; la del matí que escalfa, en dues: «fresc i
// després temperatura agradable» es feia llarg, i després n'hi ha prou amb
// «agradable».
function textSensacio(s, encara = false) {
  const [inici, despres] = s.split('>');
  const primera = encara ? T`encara ${PARAULA_SENSACIO[inici]()}` : PARAULA_SENSACIO[inici]();
  if (!despres) return primera;
  return T`${primera} i després ${despres === 'agradable' ? T('agradable') : PARAULA_SENSACIO[despres]()}`;
}

// Els dos trams de la frase de dalt: el tram en curs, si només li queda una
// hora, ja no és el que ve.
function tramsFrase(hores, ara = new Date()) {
  let trams = resumTrams(hores, ara, null).filter((t) => t.cel);
  if (trams.length > 2 && trams[0].files.length <= 1) trams = trams.slice(1);
  return trams.slice(0, 2);
}

function fraseCelAra(hores, ara = new Date()) {
  const trams = tramsFrase(hores, ara);
  const dema = new Date(ara);
  dema.setDate(dema.getDate() + 1);
  const parts = trams.map((t) => {
    const nom = t.clau.split('|')[1];
    const quan = (t.files[0] && new Date(t.files[0].hora).toDateString() === dema.toDateString()
      && nom !== 'Nit' ? QUAN_TRAM_DEMA : QUAN_TRAM)[nom]();
    return [quan, t.cel[0].toLowerCase(), sensacioTram(t)];
  });
  if (!parts.length) return null;
  const minuscula = (s) => s.charAt(0).toLowerCase() + s.slice(1);
  // La sensació davant del cel: «fred i molt ennuvolat», no «molt ennuvolat i
  // fred», que es llegiria «molt fred» (Juanjo, 22-10-2026).
  // Amb dues sensacions, el cel darrere una coma: «fresc i després agradable,
  // i ennuvolat», que no es llegeixi «agradable i ennuvolat».
  const amb = (cel, s, encara) => {
    if (!s) return cel;
    return s.includes('>') ? T`${textSensacio(s, encara)}, i ${cel}` : T`${textSensacio(s, encara)} i ${cel}`;
  };
  // El mateix cel i la mateixa sensació als dos trams, en una sola frase:
  // «Aquesta tarda i aquesta nit, fresc i ennuvolat.»
  if (parts.length === 2 && parts[0][1] === parts[1][1] && parts[0][2] === parts[1][2]) {
    return T`${parts[0][0]} i ${minuscula(parts[1][0])}, ${amb(parts[0][1], parts[0][2])}.`;
  }
  // Si la sensació continua, «encara»: «…encara fresc i cobert», també quan
  // el matí comença com acaba la nit: «…encara fresc i després agradable».
  return parts.map(([quan, cel, s], i) => {
    const encara = Boolean(i && s && s.split('>')[0] === parts[0][2]);
    return T`${i ? minuscula(quan) : quan}, ${amb(cel, s, encara)}`;
  }).join('; ') + '.';
}

// Si hi ha avís de pluja o tempestes en les 24 hores que venen: amb els
// models sense pluja, mana l'avís i es diu la contradicció, no «sense pluja».
function avisDePluja(hores, ara = new Date()) {
  const fins = ara.getTime() + 24 * 3600e3;
  return (hores || []).some((f) => new Date(f.fins) > ara && new Date(f.hora).getTime() < fins
    && (f.avisos || []).some((a) => (a.tipus || []).some((t) => t === 'pluja' || t === 'tempestes')));
}

// El fons d'«Ara» i el dibuix gran, segons el cel que anuncia la frase (ADR
// 0121; Juanjo, 22-10-2026: «el fondo de esta ficha podría amoldarse a lo que
// anuncia?», «y algún sol o nubes dibujados?», «dibujos más realistas»): el
// cel del primer tram i, de dia, de nit o a la sortida i la posta del sol,
// segons l'altura del sol ara (de 6° sota l'horitzó a 6° sobre, l'alba i la
// posta). Si ara plou, la pluja (o la tempesta) mana, com a la resta de la
// portada (ADR 0101). Els dibuixos, de Meteocons (Bas Milius, MIT).
const FONS_NIT = { sere: 'nit', poc: 'nitnuvol', nuvol: 'nitcobert', cobert: 'nitcobert', boira: 'nitcobert' };
const FONS_ALBA = { sere: 'albasere', poc: 'albapoc', nuvol: 'albanuvol', cobert: 'albacobert', boira: 'albacobert', pluja: 'albapluja' };
const DIBUIX_CEL = {
  dia: { sere: 'clear-day', poc: 'partly-cloudy-day', nuvol: 'cloudy', cobert: 'overcast', boira: 'fog', pluja: 'rain', tempesta: 'thunderstorms-rain' },
  nit: { sere: 'starry-night', poc: 'partly-cloudy-night', nuvol: 'cloudy', cobert: 'overcast-night', boira: 'fog-night', pluja: 'rain',
    tempesta: 'thunderstorms-rain' },
};

function celPortada(hores, plou, radarDades, ara = new Date()) {
  const trams = tramsFrase(hores, ara);
  if (!trams.length) return null;
  const [text, ic] = trams[0].cel;
  // «Molt ennuvolat» i «Cobert» tenen la mateixa icona: el text els separa.
  let cel = ic === 'i-cloud-fog' ? 'boira' : ['i-sun', 'i-moon-cel'].includes(ic) ? 'sere'
    : ['i-cloud-sun', 'i-cloud-moon'].includes(ic) ? 'poc' : text === T('Cobert') ? 'cobert' : 'nuvol';
  const estat = radarDades && radarDades.pluja && radarDades.pluja.estat;
  if (plou || estat === 'plou' || estat === 'radar_sobre') {
    const f = (hores || []).find((h) => new Date(h.fins) > ara);
    cel = f && f.codi >= 95 ? 'tempesta' : 'pluja';
  }
  const altura = alturaSol(ara);
  const moment = altura < -6 ? 'nit' : altura < 6 ? 'alba' : 'dia';
  const fons = moment === 'nit' ? FONS_NIT[cel] || cel : moment === 'alba' ? FONS_ALBA[cel] || cel : cel;
  let dibuix = DIBUIX_CEL[moment === 'nit' ? 'nit' : 'dia'][cel];
  if (moment === 'alba' && (cel === 'sere' || cel === 'poc')) dibuix = ara.getHours() < 12 ? 'sunrise' : 'sunset';
  return { fons, dibuix };
}

// El cel que té ara la targeta, per tornar-lo a mirar cada minut a la vora de
// la sortida i la posta del sol (de 8° sota l'horitzó a 8° sobre): així
// l'alba, la posta i la nit canvien a la seva hora i no a la propera lectura
// de les dades, fins a 15 minuts més tard (Juanjo, 22-10-2026). Fora d'aquí,
// no cal: el cel només canvia amb les dades.
let CEL_ARA = null;

function posaCel(cel) {
  const { sec, dibuix } = CEL_ARA;
  sec.classList.remove(...[...sec.classList].filter((c) => c.startsWith('cel-')));
  sec.classList.add(`cel-${cel.fons}`);
  const src = `${ARREL}img/meteocons/${cel.dibuix}.svg`;
  if (dibuix.getAttribute('src') !== src) dibuix.src = src;
}

if (typeof setInterval === 'function') {
  setInterval(() => {
    if (!CEL_ARA || !CEL_ARA.sec.isConnected || Math.abs(alturaSol(new Date())) > 8) return;
    const cel = celPortada(CEL_ARA.hores, CEL_ARA.plou, CEL_ARA.radarDades);
    if (cel) posaCel(cel);
  }, 60000);
}

function titularAra(hores, radarDades, plou, ara = new Date()) {
  const frase = fraseCelAra(hores, ara);
  if (!frase) return null;
  const div = element('div', 'titular');
  div.append(element('p', 'titular-cel', frase));
  const estat = radarDades && radarDades.pluja && radarDades.pluja.estat;
  const radarDiu = plou || ['plou', 'radar_sobre', 'arriba', 'possible'].includes(estat);
  if (!radarDiu) {
    div.append(liniaPlujaPrevista(hores, ara) || element('p', 'resum-linia', avisDePluja(hores, ara)
      ? T('Els models no hi veuen pluja, però hi ha avís: mira’l a dalt.') : T('Sense pluja prevista.')));
    return div;
  }
  // El requadre del radar va sota la gràfica (Juanjo, 22-10-2026: «prefiero
  // que salga bajo la gráfica»): aquí, només el que diu, perquè la pluja que
  // arriba es vegi en obrir la pàgina.
  const t = textRadar(radarDades, plou);
  if (t) {
    const p = element('p', 'resum-linia pluja-radar');
    const text = element('span');
    text.append(...(Array.isArray(t[1]) ? t[1] : [t[1]]), '.');
    p.append(icona('i-cloud-rain'), text);
    div.append(p);
  }
  return div;
}

// La riera sota «Ara» (portada nova, ADR 0118), amb el títol i el color de la
// pàgina «Riera», només quan anuncia alguna cosa (Juanjo, 21-10-2026: «que
// solo aparezcan cuando anuncien algo»): si plou a la conca o hi ha risc, i
// no si ja en surt l'avís a dalt, a «Avisos actius». «Cap avís», tampoc: fins
// a la 3.178.0 en sortia una línia quan no n'hi havia.
function estatPortada(dades) {
  const files = [];
  const fila = (href, classe, iconaId, titol, detall) => {
    const a = element('a', `estat-fila ${classe}`);
    a.href = href;
    const ic = element('span', 'estat-icona');
    ic.append(icona(iconaId));
    const text = element('span', 'estat-text');
    text.append(element('strong', null, titol));
    if (detall) text.append(element('span', null, detall));
    a.append(ic, text, icona('i-chevron-right'));
    return a;
  };
  const r = dades.riera;
  if (r && r.nivell && !blocRiera(HISTORIAL_PERILL).length) {
    // La pluja, d'on la compta «Riera»: Meteocat o, si falla, les estacions particulars.
    const v = r.font === 'veines' && r.veines ? r.veines : r;
    files.push(fila('riera.html', COLOR_NIVELL[r.nivell] || 'be', 'i-waves', T`Riera: ${titolRiera(r.nivell).toLowerCase()}`,
      T`A Sant Cugat, ${coma(v.mm_6h || 0)} mm en les últimes 6 hores.`));
  }
  if (!files.length) return null;
  const sec = element('section', 'targeta estat-portada');
  sec.setAttribute('aria-label', T('Avisos i riera'));
  sec.append(...files);
  return sec;
}

// La previsió de 7 dies, sota la gràfica (ADR 0122; Juanjo, 23-10-2026: «la
// previsión de los proximos 6 días… del cielo, temperatura y lluvia»). Avui i
// demà, de la previsió de la pàgina, perquè diguin el mateix que la gràfica i
// els trams: la màxima i la mínima del dia (avui, amb el que ja s'ha mesurat),
// els núvols de 7 a 21 h, la probabilitat més alta de les seves hores i la
// pluja esperada (ADR 0103). La resta, d'ECMWF corregit amb l'estació
// (setmana.py), amb la probabilitat de l'ensemble.
function diaDeLaPagina(hores, mesurada, iso, ara, lectura = null) {
  const files = (hores || []).filter((f) => f.hora.slice(0, 10) === iso && new Date(f.fins) > ara);
  if (!files.length) return null;
  const temps = files.map(tempZona).filter((v) => v != null);
  for (const [clau, v] of Object.entries(mesurada || {})) {
    if (clau.slice(0, 10) === iso && new Date(clau) <= ara && v != null) temps.push(v);
  }
  // La lectura d'«Ara», la de cada actualització: el registre només té les
  // hores en punt, i un màxim entre dues hores no hi sortia, mentre «Ara» el
  // marcava (Juanjo, 23-10-2026: «si se alcanzan 21, se rectificará?»).
  if (lectura != null) temps.push(lectura);
  if (!temps.length) return null;
  const deDia = files.filter((f) => f.nuvols != null && new Date(f.hora).getHours() >= TRAM_DIA[0]
    && new Date(f.hora).getHours() < TRAM_DIA[1]);
  const ambNuvols = deDia.length ? deDia : files.filter((f) => f.nuvols != null);
  const plujes = files.map(plujaHora);
  return {
    dia: iso, max: Math.max(...temps), min: Math.min(...temps),
    nuvols: ambNuvols.length ? ambNuvols.reduce((s, f) => s + nuvolsHora(f), 0) / ambNuvols.length : null,
    boira: deDia.length > 0 && deDia.filter(esBoira).length * 2 > deDia.length,
    pluja: plujes.includes('pluja') ? 'pluja' : plujes.includes('possible') ? 'possible' : null,
    probabilitat: Math.max(...files.map((f) => (f.plou_ara ? 1 : f.probabilitat || 0))),
    pluja_mm: files.reduce((s, f) => s + probHora(f) * (f.pluja_mm || 0), 0),
    tempesta: files.some((f) => plujaHora(f) && f.codi >= 95),
    neu: files.some((f) => plujaHora(f) && esNeu(f.codi)),
  };
}

function diesSetmana(dades, ara = new Date()) {
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const avui = iso(ara);
  const alta = zonaTriada() === 'alta';
  const c = dades.ara_casa;
  const lectura = c && c.hora && c.hora.slice(0, 10) === avui ? tempAra(c) : null;
  const res = [];
  for (const d of (dades.setmana || []).filter((x) => x.dia >= avui).slice(0, 7)) {
    const propi = res.length < 2 && diaDeLaPagina(dades.hores, mesuradaZona(dades), d.dia, ara, d.dia === avui ? lectura : null);
    if (propi) {
      res.push(propi);
      continue;
    }
    const p = d.probabilitat;
    res.push({
      dia: d.dia, max: alta ? d.max_alta ?? d.max : d.max, min: alta ? d.min_alta ?? d.min : d.min,
      nuvols: d.nuvols, boira: false, probabilitat: p, pluja_mm: d.pluja_mm,
      pluja: p == null ? null : p >= PROB_PLUJA ? 'pluja' : p >= PROB_POSSIBLE ? 'possible' : null,
      tempesta: d.codi >= 95, neu: esNeu(d.codi),
    });
  }
  return res;
}

// El cel del dia, amb les icones de la gràfica: la pluja primer, com a cada hora (cel).
function celDia(d) {
  if (d.pluja === 'pluja') {
    if (d.tempesta) return [T('Tempesta'), 'i-cloud-lightning'];
    return d.neu ? [T('Neu'), 'i-cloud-snow'] : [T('Pluja'), 'i-cloud-rain'];
  }
  if (d.pluja === 'possible') return [d.neu ? T('Possible neu') : d.tempesta ? T('Possible tempesta') : T('Possible pluja'), 'i-cloud-sun-rain'];
  if (d.boira) return [T('Boira'), 'i-cloud-fog'];
  return d.nuvols == null ? null : celNuvols(d.nuvols, false);
}

// Les abreviatures dels dies, les normatives i en minúscula, com el nom sencer
// (Juanjo, 23-10-2026): en català, les de l'IEC, dues lletres i punt; en
// castellà, les de la RAE. Escrites aquí i no les del navegador, que en
// castellà donava «sáb», «mié» sense punt.
const DIES_CURTS = {
  ca: ['dg.', 'dl.', 'dt.', 'dc.', 'dj.', 'dv.', 'ds.'],
  es: ['dom.', 'lun.', 'mar.', 'miérc.', 'juev.', 'vier.', 'sáb.'],
};

// Una columna per dia, tots set a la vista, sense desplaçar (Juanjo,
// 23-10-2026: «algo parecido a esto pero sin la gráfica»): el dia, la data,
// el cel, la màxima en vermell i la mínima en blau (ADR 0063) i, només si
// arriba a possible, la probabilitat de pluja.
function blocSetmana(dades, ara = new Date()) {
  const dies = diesSetmana(dades, ara);
  if (dies.length < 3) return null;
  const sec = element('section', 'previsio setmana');
  sec.append(element('h2', 'perque', T('Previsió de 7 dies')));
  const llista = element('ol', 'setmana-dies');
  const codi = IDIOMA.codi === 'es' ? 'es' : 'ca';
  const ambPluja = dies.some((d) => d.pluja);
  // Una columna de símbols al principi, perquè se sàpiga què és cada fila
  // (Juanjo, 23-10-2026: «el % de abajo no se sabe lo que es»): «màx» i «mín»
  // del color de les xifres i el paraigua dels trams, només si hi ha pluja.
  // Cada un, amb la seva descripció en passar-hi el ratolí o mantenint-lo
  // premut. Per als lectors de pantalla, no: cada dia ja ho diu tot.
  const claus = element('li', 'setmana-claus');
  claus.setAttribute('aria-hidden', 'true');
  const clau = (classe, contingut, descripcio) => {
    const s = element('span', classe);
    if (contingut) s.append(contingut);
    if (descripcio) s.title = descripcio;
    return s;
  };
  claus.append(clau('setmana-nom'), clau('setmana-data'), clau('setmana-cel'),
    clau('setmana-max temp-max', T('màx'), T('Temperatura màxima')),
    clau('setmana-min temp-min', T('mín'), T('Temperatura mínima')));
  if (ambPluja) claus.append(clau('setmana-pluja', icona('i-umbrella'), T('Probabilitat de pluja')));
  llista.append(claus);
  dies.forEach((d, i) => {
    const data = new Date(`${d.dia}T12:00`);
    const nom = i ? DIES_CURTS[codi][data.getDay()] : T('Avui');
    const [max, min] = [Math.round(d.max), Math.round(d.min)];
    const cel = celDia(d);
    const li = element('li');
    const pct = d.pluja ? `${Math.round(d.probabilitat * 100)} %` : '';
    // Tot el dia en una frase, per als lectors de pantalla.
    li.setAttribute('aria-label', [data.toLocaleDateString(codi, { weekday: 'long', day: 'numeric' }),
      cel && cel[0], T`màxima ${max} °C, mínima ${min} °C`, pct && T`pluja ${pct}`].filter(Boolean).join(', '));
    li.append(element('span', 'setmana-nom', nom),
      element('span', 'setmana-data', `${data.getDate()}/${data.getMonth() + 1}`));
    const ic = cel ? icona(cel[1]) : element('span');
    ic.classList.add('setmana-cel');
    li.append(ic, element('span', 'setmana-max temp-max', `${max}°`), element('span', 'setmana-min temp-min', `${min}°`));
    if (ambPluja) li.append(element('span', 'setmana-pluja', pct));
    llista.append(li);
  });
  sec.append(llista);
  return sec;
}

// La zona del barri, amb un botó doble a la botonera de dalt: la riera (les
// ones) i la part alta (la muntanya), les icones que tenia a la gràfica
// (Juanjo, 23-10-2026: «en la botonera de arriba… con el dibujo de una riera y
// de una montaña»; ADR 0123). Què és cada un, en passar-hi el ratolí o
// mantenint-lo premut. Al mòbil estret només es veu la triada, i tocar-la
// passa a l'altra. Canviar-la torna a pintar la pàgina.
function botoZona() {
  const botons = document.querySelector?.('.cap-botons');
  if (!botons || botons.querySelector('.boto-zona')) return;
  const grup = element('div', 'boto-zona');
  grup.setAttribute('role', 'group');
  grup.setAttribute('aria-label', T('Zona del barri'));
  const opcions = [
    ['baixa', 'i-waves', T('Riera'), T('Temperatures de vora la riera, la zona més baixa i més freda del barri.')],
    ['alta', 'i-mountain', T('Part alta'), T('Temperatures de la part alta del barri, que sol ser més càlida.')],
  ].map(([zona, id, nom, descripcio]) => {
    const b = element('button', 'boto-icona');
    b.type = 'button';
    b.dataset.zona = zona;
    b.title = descripcio;
    b.setAttribute('aria-label', nom);
    b.append(icona(id));
    return b;
  });
  const marca = () => opcions.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.zona === zonaTriada())));
  for (const b of opcions) {
    b.addEventListener('click', () => {
      const altra = opcions.find((x) => x !== b);
      const zona = getComputedStyle(altra).display === 'none' ? altra.dataset.zona : b.dataset.zona;
      if (zona === zonaTriada()) return;
      triaZona(zona);
      marca();
      if (DADES_AVISOS && !dadesVelles(DADES_AVISOS)) pinta(DADES_AVISOS);
    });
  }
  marca();
  zonaALAdreca();
  grup.append(...opcions);
  botons.prepend(grup);
}

// La temperatura d'«Ara» a la zona triada: a la riera, la de l'estació; a la
// part alta, la que hi mesuren ara les estacions, en graus sencers com elles
// (ADR 0123). Sense les de dalt, a la part alta no n'hi ha (null).
function tempAra(casa) {
  if (casa.temperatura == null) return null;
  if (zonaTriada() !== 'alta') return casa.temperatura;
  return casa.dif_alta == null ? null : Math.round(casa.temperatura + casa.dif_alta);
}

function blocAra(casa, radarDades, vent, veines, hores, mesurada) {
  const sec = element('section', 'decisio targeta ara heroi');
  sec.setAttribute('aria-label', T`El temps avui a ${LLOC}`);
  // Sense l'hora de la mesura: la de «Actualitzat a les…», a dalt, ja la diu, i
  // dues hores juntes semblaven un error (Juanjo, 16-10-2026; ADR 0094).
  // Compacta, perquè la gràfica càpiga a la pantalla del mòbil sense
  // desplaçar (Juanjo, 20-10-2026): sense «Avui, dimarts, a Montflorit» (el
  // lloc ja és al títol i el dia, a la gràfica) i la part alta al costat de la
  // temperatura, no a sota.
  const fila = element('div', 'ara-temp');
  const temp = element('p', 'veredicte');
  const termometre = icona('i-thermometer');
  termometre.classList.add('vehicle');
  // La de la zona triada amb el botó de dalt (ADR 0123): a la part alta, la
  // que hi mesuren ara les estacions (casa.dif_alta, part_alta.ara), sense
  // decimal, perquè les de dalt la donen en graus sencers (Juanjo, 23-10-2026);
  // si no n'hi ha, la de la riera. La de la riera, també en graus sencers des
  // de la 3.195.0, perquè canviar de zona no canviï el format i com la resta
  // de la web (Juanjo, 24-10-2026: «uniformizar … así no se ve diferencia»).
  const dalt = tempAra(casa);
  temp.append(termometre, `${zonaTriada() === 'alta' && dalt != null ? dalt : Math.round(casa.temperatura)} °C`);
  const columna = element('div', 'ara-temp-col');
  columna.append(temp);
  // Si el dia és com l'anterior, a sota (comparaDia), també al costat del
  // dibuix, perquè la targeta no creixi.
  const compara = hores && comparaDia(hores, mesurada);
  if (compara) columna.append(etiquetaAlta(compara.text, false, compara.explica));
  fila.append(columna);
  sec.append(fila);
  // Plou si ha plogut en els últims 15 minuts a la xarxa del barri: l'estació
  // de casa o alguna de les veïnes que compten (ADR 0060), amb la intensitat
  // mediana de les que en marquen (casa.consens), sense dir de quina estació
  // surt (Juanjo, 13-10-2026). Les veïnes, per a les dades d'abans de la 3.76.0.
  const plou = !!casa.plou || (veines || []).some((v) => v.plou && v.compta);
  const titular = hores && titularAra(hores, radarDades, plou);
  if (titular) sec.prepend(titular);
  const cel = hores && celPortada(hores, plou, radarDades);
  if (cel) {
    // Decoratiu: el cel ja el diu la frase.
    const dibuix = element('img', 'heroi-cel');
    dibuix.alt = '';
    dibuix.setAttribute('aria-hidden', 'true');
    fila.append(dibuix);
    CEL_ARA = { sec, dibuix, hores, plou, radarDades };
    posaCel(cel);
  } else CEL_ARA = null;
  const intensitat = (casa.plou && casa.intensitat) || 0;
  const llista = element('ul', 'dades-ara');
  // Plugim que només veu el radar (els dos, estès a sobre del barri): el
  // pluviòmetre no el recull, però «No plou» es contradiria amb el requadre
  // del radar (Juanjo, 18-10-2026; ADR 0019).
  const plugim = !plou && radarDades && radarDades.pluja && radarDades.pluja.plugim;
  llista.append(plugim ? dada('i-cloud-drizzle', T('Plugim segons el radar'))
    : !plou ? dada('i-umbrella-off', T('No plou'))
      : intensitat ? dada('i-umbrella', T`Plou: ${coma(intensitat)} mm/h`)
        : dada('i-umbrella', T('Plou')));
  // La pluja d'avui, només si n'ha caigut: «0,0 mm avui» a primera hora no diu
  // res, i així les pastilles caben en una fila al mòbil (Juanjo, 23-10-2026).
  // Tampoc «Plou» amb «0 mm avui», que es contradiu (inventari del 18-10-2026).
  if (casa.pluja_avui) llista.append(dada('i-cloud-rain', T`${coma(casa.pluja_avui)} mm avui`));
  // El vent, de l'estació de Meteocat més propera, per mitges hores (ADR
  // 0037): l'estació i l'hora, a «D'on surt» (ADR 0074). Si ve de les veïnes
  // (ADR 0064), que «D'on surt» encara no diu, es diu aquí.
  if (vent && vent.mitja != null) {
    // Les ratxes, només la xifra entre parèntesis (Juanjo, 23-10-2026).
    const ratxa = vent.ratxa != null ? ` (${coma(vent.ratxa, 0)})` : '';
    const veines = vent.font === 'veines' ? T(', estacions veïnes') : '';
    llista.append(dada('i-wind', T`Vent ${coma(vent.mitja, 0)} km/h${ratxa}` + veines));
  }
  sec.append(llista);
  // Sense la línia de la humitat i la pressió, perquè la targeta no creixi
  // amb la part alta a sota de la temperatura (Juanjo, 22-10-2026: «podemos
  // prescindir de la humedad y presión»). Es poden veure a la gràfica.
  // El radar, a part: va sota la gràfica (titularAra).
  sec._radar = blocRadar(radarDades, plou, hores);
  return sec;
}

// «d'aquí a 25 minuts», «d'aquí a 1 h 10 min»: un element que actualitzaComptes
// torna a escriure cada minut, sense recarregar la pàgina.
function compte(iso, perHores = false) {
  const s = element('span', 'compte');
  s.dataset.t = iso;
  if (perHores) s.dataset.hores = '1';
  s.textContent = textCompte(iso, perHores);
  return s;
}

function textCompte(iso, perHores) {
  const min = Math.max(0, Math.round((new Date(iso) - Date.now()) / 60000));
  // La previsió és per hores: «d'aquí a unes 6 hores», sense minuts.
  if (perHores) {
    const h = Math.round(min / 60);
    return h < 1 ? T('d’aquí a menys d’una hora') : h === 1 ? T('d’aquí a una hora') : T`d’aquí a unes ${h} hores`;
  }
  if (min < 1) return T('ara mateix');
  if (min < 60) return min === 1 ? T('d’aquí a 1 minut') : T`d’aquí a ${min} minuts`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? T`d’aquí a ${h}\u00a0h ${m}\u00a0min` : T`d’aquí a ${h}\u00a0h`;
}

function actualitzaComptes() {
  for (const s of document.querySelectorAll('.compte[data-t]')) s.textContent = textCompte(s.dataset.t, s.dataset.hores);
}
if (typeof setInterval === 'function') setInterval(actualitzaComptes, 30e3);

// La primera hora que comença en les 24 que venen amb pluja segons la
// previsió (del 20 %, «possible pluja», com a la taula).
function primeraPluja(hores, ara = new Date()) {
  const fins = new Date(ara.getTime() + 24 * 3600e3);
  return (hores || []).find((x) => new Date(x.hora) > ara && new Date(x.hora) < fins && plujaHora(x)) || null;
}

// « (49 %)», la probabilitat d'una hora; res si no en té.
function textPct(f) {
  return f.probabilitat == null ? '' : ` (${Math.round(f.probabilitat * 100)}\u00a0%)`;
}

// La primera hora de les 24 que venen amb pluja segons la previsió, amb
// l'hora i la probabilitat.
function liniaPlujaPrevista(hores, ara = new Date()) {
  const f = primeraPluja(hores, ara);
  if (!f) return null;
  const pct = f.probabilitat == null ? null : Math.round(f.probabilitat * 100);
  const segura = plujaHora(f) === 'pluja';
  const p = element('p', `resum-linia pluja-prevista${segura ? ' segura' : ''}`);
  const text = element('span');
  const etiqueta = element('span', 'comenca-pluja');
  etiqueta.append(compte(f.hora, true));
  text.append(segura ? T('Pluja prevista ') : T('Possible pluja '), etiqueta,
    T`, cap a les ${new Date(f.hora).getHours()}\u00a0h` + (pct == null ? '' : ` (${pct}\u00a0%)`) + '.');
  p.append(icona('i-cloud-rain'), text);
  return p;
}

// El resum del dia, el mateix de «Consultes › Avui», a sota d'«Ara»: el que es
// vol saber en obrir la pàgina, sense desplegar res (Juanjo, 12-10-2026; ADR
// 0074). Des de HORA_DEMA, també el de demà, com el bot. Sense la línia «Ara
// mateix», que ja és la targeta de sobre, ni la de la roba, que és cosa de
// «Si surts» (Juanjo, 12-10-2026: «lo de la ropa en pantalla principal, no es
// un poco frivolo?»), ni els avisos de l'AEMET, que ja surten a dalt, a
// «Avisos actius» (ADR 0076).
// Les alertes tampoc: totes ja surten a «Avisos actius» (ADR 0093).
const LINIA_FORA = /^(⟦[a-z-]+⟧ ?)?(Ara mateix|Ahora mismo|Roba |Ropa )/;
const liniaFora = (l) => LINIA_FORA.test(l) || LINIA_PERILL.test(l);

function textResum(dades, clau) {
  const text = ((dades.consultes || {})[IDIOMA.codi === 'es' ? 'es' : 'ca'] || {})[clau];
  return text ? text.split('\n').filter((l) => !liniaFora(l)).join('\n') : null;
}

function textosResum(dades) {
  const claus = new Date(dades.generat).getHours() >= HORA_DEMA ? ['avui', 'dema'] : ['avui'];
  return claus.map((c) => textResum(dades, c)).filter(Boolean);
}

// Les targetes del resum que no van dins «Ara»: la de demà, des de HORA_DEMA,
// i la d'avui si no hi ha dades d'ara.
function blocsResum(dades, ambAvui) {
  const claus = (new Date(dades.generat).getHours() >= HORA_DEMA ? ['avui', 'dema'] : ['avui'])
    .filter((c) => c !== 'avui' || ambAvui);
  const blocs = claus.map((c) => textResum(dades, c)).filter(Boolean).map((text) => {
    const sec = element('section', 'targeta resum-dia');
    sec.append(...ambDetalls(pintaResum(text)));
    return sec;
  });
  // Sense la invitació fixa a activar els avisos (Juanjo, 12-10-2026: «quita ese
  // texto fijo de activar avisos»; ADR 0080): ja hi ha la campana i, a qui té la
  // web instal·lada, la targeta d'oferta.
  return blocs;
}

// La pluja del radar portada endavant (ADR 0019): quan arribaria a casa i,
// si ja hi és, quan pararia, «en entrenament» mentre aprèn (ADR 0049): el
// tercer valor diu si cal la marca.
function textRadar(r, plou) {
  if (!r) return null;
  const aviat = (t) => new Date(t) <= new Date(Date.now() + 5 * 60e3);
  // L'estat únic de la pluja (ADR 0101): el mateix que diu «Ara». El que es
  // mesura mana: si ja plou, «Pluja a sobre», encara que el radar només en
  // vegi una part; si no en veu gens, sense hora (Juanjo, 08-10-2026). Si
  // només la veu el radar, es diu (Juanjo, 18-10-2026: «lo decía el radar:
  // lluvia encima, pero no había»). Amb dades d'abans de la 3.136.0, sense
  // l'estat, com abans.
  const estat = r.pluja ? r.pluja.estat
    : plou ? 'plou' : r.arriba && aviat(r.arriba) ? 'radar_sobre' : null;
  if (estat === 'plou' && !(r.arriba && aviat(r.arriba)) && !(r.possible && aviat(r.possible))) {
    // La mesuren les estacions i el radar no la veu a sobre (el plugim, sovint):
    // es diu, perquè el mapa del costat no en mostra (Juanjo, 18-10-2026).
    return ['arriba', T('Pluja a sobre segons les estacions del barri · el radar no la veu'), false, true];
  }
  if (estat === 'plou' || estat === 'radar_sobre') {
    const fi = !(r.arriba || r.possible) ? ''
      : r.fi ? T` · pararia cap a les\u00a0${horaCurta(r.fi)}`
        : r.sense_fi ? T(' · no s’acaba en 2 hores') : '';
    const nomesRadar = estat === 'radar_sobre' ? T(' segons el radar · cap estació del barri no en mesura') : '';
    return ['arriba', T('Pluja a sobre') + nomesRadar + fi, Boolean(fi), true];
  }
  // Quant falta, en minuts, i l'hora (Juanjo, 17-10-2026: «empezará a llover
  // en x horas o minutos (se actualizará en tiempo real) y la hora prevista»);
  // el compte s'actualitza sol cada minut (actualitzaComptes).
  if (r.arriba) return ['arriba', [T('Pluja '), compte(r.arriba), T` (cap a les\u00a0${horaCurta(r.arriba)})`]];
  if (r.possible) {
    if (aviat(r.possible)) return ['possible', T('Pluja a prop: pot arribar')];
    return ['possible', [T('Pot arribar pluja '), compte(r.possible), T` (cap a les\u00a0${horaCurta(r.possible)})`]];
  }
  // Ecos febles estesos a sobre del barri als dos radars: plugim, que les
  // estacions no recullen (Juanjo, 18-10-2026: «el radar de la web dice que no
  // se ve lluvia, en el de meteocat sí y realmente acaba de empezar a llover»).
  if (estat === 'no' && r.pluja && r.pluja.plugim) {
    return ['possible', T('El radar veu pluja molt feble a sobre (plugim), que les estacions no mesuren')];
  }
  // Pluja forta o més a 15 km o menys que no ve cap aquí: es diu al titular,
  // amb el color de «pot arribar» (Juanjo, 17-10-2026, amb trons i el radar
  // dient «no veu pluja que vingui cap aquí»: «esta imagen es compatible con
  // el mensaje?»).
  const f = r.forta;
  if (f && f.km >= 1) {
    return ['a-prop', T`Pluja ${NOM_INTENSITAT()[f.classe]} a ${Math.round(f.km)}\u00a0km ${textRumb(f.rumb)}, que de moment no ve cap aquí`];
  }
  // Només diu el que veu: la pluja que encara no s'ha format no hi surt
  // (Juanjo, 17-10-2026, davant «No s'acosta pluja en 2 hores» i «Comença
  // d'aquí a menys d'una hora» alhora: «son mensajes contrarios»).
  return ['res', T('El radar no veu pluja que vingui cap aquí')];
}

// On veure el radar en directe, centrat a Montflorit quan es pot.
const RADAR_EN_DIRECTE = {
  rainviewer: 'https://www.rainviewer.com/map.html?loc=41.482,2.135,9&layer=radar',
  meteocat: 'https://www.meteo.cat/observacions/radar',
};

// Si la previsió dona pluja, com a mínim possible, en alguna de les dues
// hores que venen: llavors que el radar no en vegi és notícia.
function plujaPrevistaAviat(hores, ara = new Date()) {
  const fins = new Date(ara.getTime() + 2 * 3600e3);
  return (hores || []).some((f) => new Date(f.fins) > ara && new Date(f.hora) < fins && plujaHora(f));
}

// Franja pròpia dins «Ara a casa», amb el color del que diu: ambre si la
// pluja arriba, blau si és possible, neutre si no se n'acosta. Que no se
// n'acosti només surt si la previsió en dona aviat; si no, no diu res que no
// digui ja la previsió (Juanjo, 10-10-2026: «si no anuncia nada como ahora
// mejor que no salga»; ADR 0019).
function blocRadar(r, plou, hores) {
  const t = textRadar(r, plou);
  if (!t) return null;
  const creix = textCreixement(r);
  if (t[0] === 'res' && !creix && !plujaPrevistaAviat(hores)) return null;
  const [estat, text, proves, aSobre] = t;
  // Si la pluja creix al voltant, en blau com «pot arribar» (17-10-2026).
  const caixa = element('div', `radar-ara ${estat === 'res' && creix ? 'a-prop' : estat}`);
  caixa.append(icona('i-radar'));
  const cos = element('div');
  const p = element('p', 'radar-text');
  p.append(...(Array.isArray(text) ? text : [text]));
  if (proves) {
    const marca = element('span', 'en-proves', T(' (en entrenament)'));
    marca.title = T('Hora estimada amb el radar. Encara s’està entrenant amb la pluja real: pot fallar.');
    p.append(marca);
  }
  cos.append(p);
  if (creix && (estat === 'res' || estat === 'a-prop')) cos.append(element('p', 'radar-propera', creix));
  // Si la previsió en dona i el radar no en veu venir, la mateixa hora i
  // probabilitat que l'etiqueta «Comença…», perquè es llegeixin juntes. Si
  // el radar veu pluja a 15 km o menys, no és «pluja que el radar encara no
  // veu»: pot ser aquesta, que creixi o es desviï (Juanjo, 17-10-2026).
  if (estat === 'res' || estat === 'a-prop') {
    const ara = new Date();
    const f = primeraPluja(hores, ara);
    const aProp = r.propera && r.propera.km <= 15;
    // La que només ve de la pluja que acaba de caure (segons_estacio) no és
    // pluja que el radar no veu (inventari del 18-10-2026).
    // Qui dona què: la previsió per hores, amb l'hora (el compte ja és a
    // l'etiqueta de dalt). Abans, «La previsió en dona d'aquí a…», que no es
    // llegia bé (Juanjo, 18-10-2026: «quien da la previsión? queda extraño»).
    const resta = (x) => (x.segons_estacio ? T`${textPct(x)}, per la pluja que ha caigut fa poc al barri.`
      : aProp ? T`${textPct(x)}: pot ser pluja de prop que creixi o es desviï cap aquí.`
        : T`${textPct(x)}: seria pluja que es formi a prop, que el radar encara no veu.`);
    // Primer, la de l'hora en curs: si ja en dona, «a partir de les 17 h» deia
    // l'hora següent amb la de les 16 a la taula (revisor, 19-10-2026).
    const g = (hores || []).find((x) => new Date(x.hora) <= ara && new Date(x.fins) > ara && plujaHora(x));
    if (g) cos.append(element('p', 'radar-propera', T('La previsió per hores sí que dona pluja per a aquesta hora') + resta(g)));
    else if (f && new Date(f.hora) < new Date(ara.getTime() + 2 * 3600e3)) {
      cos.append(element('p', 'radar-propera',
        T`La previsió per hores sí que dona pluja a partir de les ${new Date(f.hora).getHours()}\u00a0h` + resta(f)));
    }
  }
  // La pluja més propera, si no és a sobre (Juanjo, 17-10-2026), i si no és
  // la mateixa que ja diu el titular.
  const pr = r.propera;
  const repetida = estat === 'a-prop' && pr && Math.round(pr.km) === Math.round(r.forta.km) && pr.rumb === r.forta.rumb;
  // Si plou a sobre, la més propera no diu res: és aquesta (ADR 0101). Amb
  // plugim a sobre, tampoc: confonia (Juanjo, 18-10-2026).
  const plugim = r.pluja && r.pluja.plugim;
  const propera = !repetida && !aSobre && !plugim && textPropera(pr);
  if (propera) cos.append(element('p', 'radar-propera', propera));
  // La font i l'hora de la imatge, com demana Meteocat per reutilitzar-la,
  // amb l'enllaç al radar en directe (Juanjo, 08-10-2026). Sense moviment
  // (menys d'1 km/h), no es diu cap on va: «a 0 km/h» no vol dir res.
  const font = r.imatge === 'rainviewer' ? 'RainViewer' : 'Meteocat';
  const mov = r.cap_a && r.velocitat_kmh >= 1 ? T` \u00b7 va cap ${TD(r.cap_a)} a ${r.velocitat_kmh}\u00a0km/h` : '';
  const detall = element('p', 'radar-detall');
  detall.append(...ambEnllacRadar(T`Radar de ${font} de les ${horaCurta(r.hora)}${mov}`, r, font));
  cos.append(detall);
  // Compacte si no és urgent: el titular en una línia i la resta plegada a
  // sota, perquè la gràfica es vegi sense desplaçar (Juanjo, 19-10-2026: «sí,
  // hazlo así»). Sencer si plou a sobre o la pluja arriba en menys d'una hora.
  const urgent = aSobre || (estat === 'arriba' && r.arriba
    && new Date(r.arriba) - new Date() < 60 * 60000);
  if (!urgent && cos.children.length > 1) {
    const plec = element('details', 'radar-plec');
    const resum = element('summary', 'radar-text');
    resum.append(...p.childNodes);
    plec.append(resum, ...[...cos.children].slice(1));
    cos.replaceChildren(plec);
  }
  caixa.append(cos);
  if (r.mapa) caixa.append(miniaturaMapa(r, font));
  return caixa;
}

// --- El mapa del radar (Juanjo, 17-10-2026: «un mapa donde se vea
// montflorit y la lluvia (puede ser estático…)»): el tros de la imatge que
// porten les dades (nowcast.mapa), 30 km al voltant, dibuixat aquí, sense
// demanar res a cap servidor de mapes. Cercles cada 10 km, el nord i unes
// quantes poblacions per situar-se. Una miniatura al requadre i, en prémer-la,
// gran. A sota, el Mapa base estàndard gris de l'ICGC del mateix quadrat
// (img/radar-fons.webp, fet amb eines/fons_radar.py), amb els noms dels
// pobles, la costa i les carreteres. ---
const NOM_INTENSITAT = () => [null, T('feble'), T('moderada'), T('forta'), T('molt forta'), T('torrencial')];
const COLOR_INTENSITAT = [null, '#93c5fd', '#2563eb', '#facc15', '#f97316', '#dc2626'];
// El plugim que només es diu si el veuen els dos radars (ADR 0019): lila clar,
// com la franja més baixa del radar de Meteocat.
const COLOR_PLUGIM = '#c4b5fd';
// Si el requadre parla de plugim, el mapa el pinta (Juanjo, 18-10-2026).
const ambPlugim = (r) => Boolean(r.pluja && r.pluja.plugim && r.mapa && r.mapa.febles);
// Les poblacions, en km des de Montflorit (est i nord), i on va el nom: a la
// dreta o, perquè no en tapi cap altre ni surti del mapa, a l'esquerra («e»)
// o a sota («s»). Damunt del mapa, que les porta més febles perquè és aclarit
// (Juanjo, 17-10-2026: «ahora ya no se ve mucho»).
const POBLES = [['Terrassa', -10.6, 9.1], ['Sabadell', -2.1, 6.8], ['Sant Cugat', -4.1, -1.1, 's'],
  ['Barcelona', 2.8, -10.5], ['Badalona', 9.4, -3.6], ['Granollers', 12.7, 14.0], ['Mataró', 25.8, 6.2, 'e'],
  ['Martorell', -17.0, -0.8]];
const LLOC_NOM = { e: [-0.9, 0.6, 'end'], s: [0, 2.3, 'middle'] };
const CERCLES_KM = [10, 20, 30];

// La pluja que creix al voltant de casa, el que es mesura i prou: quanta n'hi
// ha a 15 km o menys respecte de fa mitja hora, al mateix radar (nowcast.
// creixement). El moviment només desplaça la imatge, i el 17-10-2026 la
// tempesta es formava cada cop més a prop (Juanjo: «no se trata solo de la
// direccion de la lluvia sino de hacia donde crece»).
// Quina part del terreny ocupa, ara i fa mitja hora: el doble de 10 km² no és
// el doble de 216 (Juanjo, 17-10-2026).
function textCreixement(r) {
  const c = r && r.creixement;
  if (!c || !c.creix || c.pct == null) return null;
  if (!c.km2_abans) return T`La pluja s’està formant a prop: ja ocupa el ${c.pct}\u00a0% del terreny a 15\u00a0km o menys; fa mitja hora, gens.`;
  return T`La pluja s’està formant a prop: ja ocupa el ${c.pct}\u00a0% del terreny a 15\u00a0km o menys; fa mitja hora, el ${Math.max(c.pct_abans, 1)}\u00a0%.`;
}

// «al nord-oest»; en castellà, «al noroeste».
function textRumb(rumb) {
  return IDIOMA.codi === 'es' ? `al ${TD(rumb).replace(/^el /, '')}` : rumb;
}

// «a 6 km al nord-oest (moderada)».
function textPropera(p) {
  if (!p || p.km < 1) return null;
  return T`La més propera, a ${Math.round(p.km)}\u00a0km ${textRumb(p.rumb)} (${NOM_INTENSITAT()[p.classe] || T('feble')}).`;
}

function svgMapa(r, gran) {
  const m = r.mapa;
  const ns = 'http://www.w3.org/2000/svg';
  const nou = (tag, at = {}) => {
    const e = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(at)) e.setAttribute(k, v);
    return e;
  };
  const R = CERCLES_KM[CERCLES_KM.length - 1];
  // La miniatura és dins d'un botó que ja diu què és: per als lectors de
  // pantalla, només el botó.
  const svg = nou('svg', { viewBox: `${-R} ${-R} ${2 * R} ${2 * R}`, class: 'mapa-radar-svg',
    ...(gran ? { role: 'img' } : { 'aria-hidden': 'true' }) });
  svg.append(nou('rect', { x: -R, y: -R, width: 2 * R, height: 2 * R, class: 'mapa-fons' }),
    nou('image', { href: ARREL + 'img/radar-fons.webp', x: -R, y: -R, width: 2 * R, height: 2 * R,
      preserveAspectRatio: 'none', class: 'mapa-base' }));
  // La pluja: un camí per intensitat, un quadrat per píxel.
  const k = m.km_px;
  const camins = COLOR_INTENSITAT.map(() => []);
  for (let i = 0; i < m.n; i++) {
    for (let j = 0; j < m.n; j++) {
      const c = +m.classes[i * m.n + j];
      if (!c) continue;
      // En píxels del radar, i el grup escalat a km: sense arrodoniments
      // que deixin ratlles entre quadrats, que se solapen una mica.
      const x = j - m.col;
      const y = i - m.fila;
      if (Math.abs(x * k) > R || Math.abs(y * k) > R) continue;
      camins[c].push(`M${x.toFixed(2)} ${y.toFixed(2)}h1.04v1.04h-1.04z`);
    }
  }
  const febles = [];
  if (ambPlugim(r)) {
    for (let i = 0; i < m.n; i++) {
      for (let j = 0; j < m.n; j++) {
        if (m.febles[i * m.n + j] !== '1') continue;
        const x = j - m.col;
        const y = i - m.fila;
        if (Math.abs(x * k) > R || Math.abs(y * k) > R) continue;
        febles.push(`M${x.toFixed(2)} ${y.toFixed(2)}h1.04v1.04h-1.04z`);
      }
    }
  }
  const pluja = nou('g', { transform: `scale(${k})`, class: 'mapa-pluja' });
  if (febles.length) pluja.append(nou('path', { d: febles.join(''), fill: COLOR_PLUGIM }));
  camins.forEach((d, c) => { if (d.length) pluja.append(nou('path', { d: d.join(''), fill: COLOR_INTENSITAT[c] })); });
  svg.append(pluja);
  for (const km of CERCLES_KM) svg.append(nou('circle', { cx: 0, cy: 0, r: km, class: 'mapa-cercle' }));
  if (gran) {
    for (const km of CERCLES_KM) {
      const t = nou('text', { x: 0.6, y: -km + 1.9, class: 'mapa-km' });
      t.textContent = `${km} km`;
      svg.append(t);
    }
    for (const [nom, x, y, on] of POBLES) {
      svg.append(nou('circle', { cx: x, cy: -y, r: 0.45, class: 'mapa-poble' }));
      const [dx, dy, ancora] = LLOC_NOM[on] || [0.9, 0.6, 'start'];
      const t = nou('text', { x: x + dx, y: -y + dy, class: 'mapa-nom', 'text-anchor': ancora });
      t.textContent = nom;
      svg.append(t);
    }
    svg.append(...fletxesMoviment(r, R, nou));
    const credit = nou('text', { x: R - 0.8, y: R - 0.8, class: 'mapa-credit' });
    credit.textContent = 'Mapa © ICGC · CC BY 4.0';
    svg.append(credit);
    // Qui l'ha fet, dins de la imatge: és un mapa propi, no una captura d'una
    // altra web (Juanjo, 17-10-2026), amb el radar i l'hora de què surt.
    const autor = nou('text', { class: 'mapa-autor' });
    const font = r.imatge === 'rainviewer' ? 'RainViewer' : 'Meteocat';
    [[nomPropi(), 'mapa-autor-nom'], [T('Mapa d’elaboració pròpia')],
      [T`Radar: ${font}, ${horaCurta(r.hora)}`]].forEach(([text, classe], i) => {
      const linia = nou('tspan', { x: -R + 0.8, y: -R + 2.2 + i * 1.8, ...(classe ? { class: classe } : {}) });
      linia.textContent = text;
      autor.append(linia);
    });
    svg.append(autor);
    const n = nou('text', { x: R - 2.2, y: -R + 3.6, class: 'mapa-nord' });
    n.textContent = 'N';
    svg.append(nou('path', { d: `M${R - 1.6} ${-R + 8.4}l0 -3.2m-1 1l1 -1.2l1 1.2`, class: 'mapa-fletxa' }), n);
  }
  svg.append(nou('circle', { cx: 0, cy: 0, r: gran ? 0.9 : 1.6, class: 'mapa-casa' }));
  if (gran) {
    const t = nou('text', { x: 1.4, y: -1.2, class: 'mapa-nom mapa-nom-casa' });
    t.textContent = LLOC;
    svg.append(t);
  }
  return svg;
}

// El text amb el nom de la font enllaçat al radar en directe.
function ambEnllacRadar(text, r, font) {
  const [abans, despres] = text.split(font);
  const enllac = element('a', null, font);
  enllac.href = RADAR_EN_DIRECTE[r.imatge === 'rainviewer' ? 'rainviewer' : 'meteocat'];
  enllac.target = '_blank';
  enllac.rel = 'noopener';
  return [abans, enllac, despres];
}

// Cap on va la pluja (Juanjo, 17-10-2026: «un vector… y también la
// velocidad»). El moviment és un de sol per a tota la pluja (nowcast.moviment),
// el mateix amb què es calcula quan arriba: una fletxa a la cantonada, amb què
// és i la velocitat. Sense moviment (menys d'1 km/h o no se sap), cap fletxa,
// com al text.
function fletxesMoviment(r, R, nou) {
  if (r.graus == null || !(r.velocitat_kmh >= 1)) return [];
  const rad = r.graus * Math.PI / 180;
  const [ux, uy] = [Math.sin(rad), -Math.cos(rad)];   // l'est cap a la dreta, el nord cap amunt
  const punta = (x, y, mida) => `M${x - mida * (ux + 0.6 * uy)} ${y - mida * (uy - 0.6 * ux)}L${x} ${y}`
    + `L${x - mida * (ux - 0.6 * uy)} ${y - mida * (uy + 0.6 * ux)}`;
  const res = [];
  // A la cantonada de baix a l'esquerra, davant del nord.
  const [cx, cy, l] = [-R + 3.6, R - 3.6, 2.4];
  res.push(nou('circle', { cx, cy, r: 3.1, class: 'mapa-mov-fons' }),
    nou('path', { d: `M${cx - ux * l} ${cy - uy * l}L${cx + ux * l} ${cy + uy * l}${punta(cx + ux * l, cy + uy * l, 1)}`,
      class: 'mapa-mov' }));
  // Què és, al costat (Juanjo, 17-10-2026: «no dice lo que es y debería decirlo»).
  const que = nou('text', { x: cx + 3.8, y: cy - 0.5, class: 'mapa-nom mapa-que' });
  que.textContent = T('moviment de la pluja');
  const vel = nou('text', { x: cx + 3.8, y: cy + 1.6, class: 'mapa-nom mapa-vel' });
  vel.textContent = `${r.velocitat_kmh}\u00a0km/h`;
  res.push(que, vel);
  return res;
}

// Les intensitats que surten al dibuix, per a la llegenda: el tros de les
// dades és una mica més gran que el mapa, i el que en queda fora no compta.
function classesDibuixades(m, R) {
  const res = new Set();
  for (let i = 0; i < m.n; i++) {
    for (let j = 0; j < m.n; j++) {
      const c = m.classes[i * m.n + j];
      if (c !== '0' && Math.abs((j - m.col) * m.km_px) <= R && Math.abs((i - m.fila) * m.km_px) <= R) res.add(c);
    }
  }
  return res;
}

function miniaturaMapa(r, font) {
  const b = element('button', 'mapa-radar-mini');
  b.type = 'button';
  b.title = T('Amplia el mapa del radar');
  b.setAttribute('aria-label', T('Amplia el mapa del radar'));
  b.append(svgMapa(r, false));
  b.addEventListener('click', () => obreMapa(r, font));
  return b;
}

function obreMapa(r, font) {
  const visor = element('dialog', 'visor mapa-radar');
  const caixa = element('div', 'mapa-radar-caixa');
  const svg = svgMapa(r, true);
  const titol = T`Radar de ${font} de les ${horaCurta(r.hora)}`;
  const mov = r.cap_a && r.velocitat_kmh >= 1 ? T` Va cap ${TD(r.cap_a)} a ${r.velocitat_kmh}\u00a0km/h.` : '';
  svg.setAttribute('aria-label', T`${titol}: la pluja al voltant de ${LLOC}, amb cercles cada 10 km.` + mov
    + T` Mapa d’elaboració pròpia de ${nomPropi()}.`);
  const llegenda = element('p', 'mapa-llegenda');
  const presents = classesDibuixades(r.mapa, CERCLES_KM[CERCLES_KM.length - 1]);
  if (ambPlugim(r)) {
    const s = element('span', 'mapa-clau');
    const q = element('span', 'mapa-quadre');
    q.style.background = COLOR_PLUGIM;
    s.append(q, T('plugim'));
    llegenda.append(s);
  }
  NOM_INTENSITAT().forEach((nom, c) => {
    if (!nom || !presents.has(String(c))) return;
    const s = element('span', 'mapa-clau');
    const q = element('span', 'mapa-quadre');
    q.style.background = COLOR_INTENSITAT[c];
    s.append(q, nom);
    llegenda.append(s);
  });
  // La font, enllaçada al radar en directe, com al requadre (Juanjo,
  // 17-10-2026: «aquí puedes poner un enlace clicable al radar en tiempo real?»).
  const capcalera = element('p', 'mapa-titol');
  capcalera.append(...ambEnllacRadar(`${titol} \u00b7 ${T('cercles cada 10 km')}`, r, font));
  caixa.append(capcalera, svg, llegenda);
  const tanca = element('button', 'visor-tanca');
  tanca.type = 'button';
  tanca.title = T('Tanca');
  tanca.setAttribute('aria-label', T('Tanca'));
  tanca.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  tanca.addEventListener('click', () => visor.close());
  visor.append(caixa, tanca);
  visor.setAttribute('aria-label', titol);
  visor.addEventListener('click', (e) => { if (e.target === visor) visor.close(); });
  visor.addEventListener('close', () => visor.remove());
  document.body.append(visor);
  visor.showModal();
  tanca.focus();
}


// Barra vertical del color de l'avís al llarg de les hores que cobreix. El
// text, tan llarg com hi càpiga; el complet, per als lectors de pantalla.
function franjaAvis(tram) {
  const td = element('td', `col-avis franja-avis ${tram.nivell}`);
  td.rowSpan = tram.hores;
  const complet = textPerill(tram);
  td.title = complet;
  const barra = element('span', 'barra-avis');
  barra.append(element('span', 'text-avis'));
  const curt = textPerillCurt(tram, false);
  barra.dataset.textos = JSON.stringify([textPerillCurt(tram).replace(/: /g, ' · '), curt,
    curt.startsWith(T('Perill')) ? T('Perill') : T('Avís'), '']);
  barra.setAttribute('aria-hidden', 'true');
  // D'on surt, també al mòbil, on no hi ha ratolí: en tocar-la, un missatge
  // breu a baix (Juanjo, 16-10-2026; ADR 0093).
  const boto = element('button', 'boto-franja');
  boto.type = 'button';
  boto.setAttribute('aria-label', complet);
  boto.addEventListener('click', () => avisBreu(`${complet}.`));
  boto.append(barra);
  td.append(boto);
  return td;
}

// El text més llarg que hi cap, mesurat ja a la pàgina (l'alçada de les
// files canvia amb la pantalla).
function ajustaFranges() {
  for (const barra of document.querySelectorAll('.barra-avis')) {
    const text = barra.querySelector('.text-avis');
    for (const t of JSON.parse(barra.dataset.textos)) {
      text.textContent = t;
      if (text.offsetHeight <= barra.clientHeight - 6) break;
    }
  }
}
addEventListener('resize', ajustaFranges);

// Quins trams surten oberts (Juanjo, 09-10-2026: «no debería ser
// persistente?»). Els trams canvien de nom al llarg del dia, així que no es
// recorda cadascun sinó com ho vol veure cadascú: amb «Desplega-ho tot», tots
// oberts, desat en aquest dispositiu; si no, tots plegats, també els que tenen
// un avís o un fenomen, que ja es veu a la capçalera (Juanjo, 17-10-2026: «no
// hay que desplegar los tramos horarios con avisos… el usuario mira lo que le
// interesa según la hora en que se encuentra»). El que s'obre o es tanca a mà
// es manté mentre la pàgina és oberta, encara que es torni a pintar amb dades
// noves, però no es desa.
const CLAU_TOT_OBERT = 'meteo.previsio-tot-obert';
function totObert() {
  try { return localStorage.getItem(CLAU_TOT_OBERT) === '1'; } catch (_) { return false; }
}
const obertsAMa = new Map();
function obertDeSortida(t) {
  if (obertsAMa.has(t.clau)) return obertsAMa.get(t.clau);
  return totObert();
}

// Una taula per tram, amb les mateixes columnes.
// La sortida i la posta del sol, a la fila de l'hora en què passen, al costat
// del cel: discretes, en gris (Juanjo, 13-10-2026).
function solPerHora(sol) {
  const clau = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${d.getHours()}`;
  const res = new Map();
  for (const dia of sol || []) {
    if (dia.sortida) res.set(clau(new Date(dia.sortida)), ['i-sunrise', T('Surt el sol a les'), dia.sortida]);
    if (dia.posta) res.set(clau(new Date(dia.posta)), ['i-sunset', T('Es pon el sol a les'), dia.posta]);
  }
  return (hora) => res.get(clau(new Date(hora)));
}

function marcaSol([id, text, quan]) {
  const m = element('span', 'sol-fila');
  // Sense el zero de davant (8:02), com les hores de la taula (8–9): al mòbil
  // ha de cabre al costat de la icona del cel.
  const hora = new Date(quan).toLocaleTimeString(IDIOMA.codi, { hour: 'numeric', minute: '2-digit' });
  m.append(icona(id), element('span', 'visualment-amagat', text + ' '), hora);
  return m;
}

function origenTram(t) {
  const parts = t.perill ? [textPerill(t.perill)] : [];
  // D'on surt la tempesta, sense repetir l'avís que el perill ja diu («AEMET:
  // avís groc per pluja i tempestes») i sense passar a minúscula una sigla:
  // sortia «Tempesta: aEMET: avís groc per tempestes» (revisor, 19-10-2026).
  const tempesta = ((t.fenomens.find(([, id]) => id === 'i-cloud-lightning') || [])[2] || '')
    .split('; ').filter((o) => o && !parts.flatMap((x) => x.split('; '))
      .some((x) => x.startsWith(o.split(':')[0] + ':') && /tempest|torment/i.test(x)))
    .join('; ');
  if (tempesta) {
    const minuscula = /^.[A-Z]/.test(tempesta) ? tempesta : tempesta.replace(/^./, (c) => c.toLowerCase());
    parts.push(T`${NOM_FENOMEN.tempesta().replace(/^./, (c) => c.toUpperCase())}: ${minuscula}`);
  }
  return parts.length ? `${parts.join('. ')}.` : '';
}

// La ratxa que passa el llindar de l'avís de vent fort, del color del nivell
// i amb una «i» que porta a l'avís, on diu d'on surt i quant s'hi pot confiar
// (Juanjo, 19-10-2026: «me sale una alerta de viento fuerte… en la tabla sin
// embargo no sale nada» i «se puede añadir una i de info que lleve a la
// explicación de la alerta»). Sense avís actiu (més enllà de les 24 hores que
// mira), a l'explicació general.
function nivellRatxa(ratxa) {
  return ratxa > RATXA_TARONJA ? 'taronja' : ratxa > FENOMENS.ratxa ? 'groc' : null;
}

function celVent(f) {
  const td = element('td', 'num');
  if (f.vent == null) return td;
  const n = f.ratxa && nivellRatxa(f.ratxa);
  if (!n) {
    td.textContent = `${Math.round(f.vent)}${f.ratxa ? ` (${Math.round(f.ratxa)})` : ''}`;
    return td;
  }
  const a = element('a', `ratxa-forta ${n}`);
  const desti = () => {
    const fitxa = fitxaPerill((h) => h.clau === 'propi');
    return fitxa === 'perill.html' ? 'com-funciona.html#temps-extrem' : fitxa;
  };
  a.href = desti();
  // L'historial de «Perill» pot arribar després de pintar la taula.
  a.addEventListener('click', () => { a.href = desti(); });
  a.title = T('Avís de vent fort: d’on surt');
  a.setAttribute('aria-label', T`Ratxa de ${Math.round(f.ratxa)} km/h, avís de vent fort: d’on surt`);
  a.append(`${Math.round(f.ratxa)}`, icona('i-info'));
  td.append(`${Math.round(f.vent)} (`, a, ')');
  return td;
}

function taulaTram(t, obert, solHora) {
  const det = element('details', `tram-hores${t.perill ? ` amb-perill ${t.perill.nivell}` : ''}`);
  det.open = obert;
  det.dataset.clau = t.clau;
  det.append(resumTram(t));
  // D'on surten el perill i la tempesta del tram, a la vista en obrir-lo: al
  // mòbil no hi ha el text del ratolí (Juanjo, 16-10-2026; ADR 0093).
  const origen = origenTram(t);
  if (origen) {
    const p = element('p', 'origen-tram');
    p.append(icona('i-triangle-alert'), origen);
    det.append(p);
  }
  const contenidor = element('div', 'taula-contenidor');
  // Al mòbil la taula es desplaça de costat: s'hi ha de poder arribar amb el teclat (axe-core).
  contenidor.tabIndex = 0;
  contenidor.setAttribute('role', 'region');
  contenidor.setAttribute('aria-label', `${t.nom} (${t.hores})`);
  const taula = element('table', 'taula-hores');
  const cols = element('colgroup');
  for (const c of ['hora', 'col-avis', 'cel', 'temp', 'mm', 'prob', 'vent']) cols.append(element('col', `c-${c}`));
  taula.append(cols);
  const cap = element('thead');
  const fila = element('tr');
  // Les unitats van a la capçalera perquè la taula càpiga al mòbil.
  for (const [text, classe] of [[T('Hora'), ''], [T('Avisos'), 'col-avis'], [T('Cel'), ''], ['°C', 'num'],
    [T('Pluja (mm)'), 'num'], [T('Prob.'), 'num'], [T('Vent'), 'num']]) {
    const th = element('th', classe);
    // La columna dels avisos no porta títol a la vista: la barra ja ho diu.
    th.append(classe === 'col-avis' ? element('span', 'visualment-amagat', text) : text);
    th.scope = 'col';
    fila.append(th);
  }
  cap.append(fila);
  taula.append(cap);
  const cos = element('tbody');
  const avisos = tramsAvis(t.files);
  t.files.forEach((f, i) => {
    const tr = element('tr', { pluja: 'amb-pluja', possible: 'pluja-possible' }[plujaHora(f)] || '');
    const h0 = new Date(f.hora).getHours();
    const hora = element('th', 'hora', `${h0}–${(h0 + 1) % 24}`);
    hora.scope = 'row';
    tr.append(hora);
    const avis = avisos[i];
    if (avis === null) tr.append(element('td', 'col-avis'));
    else if (avis) tr.append(franjaAvis(avis));
    const [textCel, iconaCel] = f.plou_ara ? [T('Plou ara'), 'i-umbrella'] : cel(f);
    const celCel = element('td', 'cel');
    const sol = solHora && solHora(f.hora);
    const linia = element('span', sol ? 'cel-text amb-sol' : 'cel-text');
    if (iconaCel) linia.append(icona(iconaCel));
    linia.append(sol ? element('span', 'cel-nom', textCel) : textCel);
    if (sol) linia.append(marcaSol(sol));
    celCel.append(linia);
    tr.append(celCel);
    tr.append(element('td', 'num', f.temperatura == null ? '' : `${Math.round(tempZona(f))}`));
    tr.append(element('td', 'num', f.pluja_mm >= 0.1 ? coma(f.pluja_mm) : '\u2013'));
    const prob = element('td', 'num prob');
    if (f.probabilitat != null) {
      const pct = Math.round(f.probabilitat * 100);
      prob.textContent = `${pct} %${f.segons_estacio ? '*' : f.segons_radar ? '\u2020' : ''}`;
      prob.style.setProperty('--prob', `${pct}%`);
    }
    tr.append(prob);
    tr.append(celVent(f));
    cos.append(tr);
  });
  taula.append(cos);
  // Amb una ratxa de l'avís, la xifra porta la «i»: la columna de vent, més ampla.
  if (t.files.some((f) => f.vent != null && f.ratxa && nivellRatxa(f.ratxa))) taula.classList.add('amb-ratxa-forta');
  contenidor.append(taula);
  det.append(contenidor);
  // Plegada, la barra de l'avís no té alçada: s'ajusta en obrir-la.
  det.addEventListener('toggle', () => {
    obertsAMa.set(t.clau, det.open);
    ajustaFranges();
    posaBotoTot();
  });
  return det;
}

function taula(hores, mesurada, riscos, sol) {
  const ara = new Date();
  for (const f of hores) f.riscos_hora = riscosHora(f, riscos, ara);
  const trams = resumTrams(hores, ara, mesurada);
  if (!trams.length) return null;
  const sec = element('section', 'previsio');
  const cap = element('div', 'cap-previsio');
  const boto = element('button', 'boto-tot');
  boto.type = 'button';
  boto.id = 'boto-tot';
  boto.addEventListener('click', () => {
    const obrir = boto.dataset.accio === 'obre';
    try { localStorage.setItem(CLAU_TOT_OBERT, obrir ? '1' : '0'); } catch (_) {}
    for (const d of document.querySelectorAll('.tram-hores')) {
      d.open = obrir;
      obertsAMa.set(d.dataset.clau, obrir);
    }
    posaBotoTot();
  });
  const graf = grafica(hores);
  const botons = element('div', 'cap-previsio-botons');
  // La gràfica, en una secció pròpia que va just després d'«Ara» (pinta;
  // 19-10-2026), amb «Opcions» (la gràfica en gran, amb les seves opcions)
  // al final de la llegenda, dins de la figura: sense una fila per a ell sol
  // (Juanjo, 20-10-2026: «el botón opciones, se podría meter dentro del
  // gráfico sin trastornarlo? sin texto en el movil, ganariamos un espacio»).
  // Abans anava sota la gràfica (Juanjo, 20-10-2026: «los prefiero debajo de
  // la gráfica, así no se desvía la atención»): ara també hi és, a la línia
  // de la llegenda. Totes les hores, hora a hora, desplaçant de costat: sense
  // el selector «24 h · Demà · Tot» (3.166.0).
  if (graf) {
    const secG = element('section', 'previsio previsio-grafica');
    graf._botoOpcions = true;
    // Sense el rètol «Previsió», perquè la gràfica càpiga a la pantalla del
    // mòbil (Juanjo, 20-10-2026). El nom, per als lectors de pantalla.
    secG.setAttribute('aria-label', T('Previsió'));
    secG.append(graf);
    sec._grafica = secG;
  }
  botons.append(boto);
  cap.append(element('h2', 'perque', T('Per hores')), botons);
  sec.append(cap);
  const solHora = solPerHora(sol);
  trams.forEach((t) => sec.append(taulaTram(t, obertDeSortida(t), solHora)));
  // Les notes, plegades: només les que diuen alguna cosa de les hores d'ara.
  const visibles = trams.flatMap((t) => t.files);
  const notes = element('details', 'com notes-taula');
  notes.append(element('summary', null, T('Com es llegeix la previsió')));
  // Només què vol dir cada cosa; com es calcula, a «D'on surt» (Juanjo,
  // 12-10-2026: «dice cosas poco útiles … solo lo que significa»; ADR 0077).
  // Cada terme en negreta i què vol dir al costat (Juanjo, 13-10-2026: «usa
  // negritas… esto es muy rancio»).
  const llista = element('dl', 'llegenda');
  const terme = (nom, text, classe = null) => {
    const dt = element('dt');
    dt.append(classe ? element('span', classe, nom) : nom);
    llista.append(dt, element('dd', null, text));
  };
  // Què fer amb la xifra, amb els mateixos llindars que el cel de la taula
  // (PROB_POSSIBLE i PROB_PLUJA; Juanjo, 13-10-2026: «alguna indicación útil»).
  // El cel, amb els llindars de celNuvols i de plujaHora (Juanjo, 13-10-2026:
  // «no hay nada sobre el cel»; ADR 0088).
  terme(T('Cel'), T('Quina part del cel tapen els núvols: serè, menys del 20\u00a0%; poc ennuvolat, fins al 45\u00a0%; mig ennuvolat, fins al 70\u00a0%; molt ennuvolat, fins al 85\u00a0%, i cobert, més. Si la probabilitat de pluja arriba al 20\u00a0%, hi surt «possible pluja», i del 50\u00a0% amunt, la pluja. A l’hora en curs, els núvols baixos són els que s’observen a l’aeroport de Sabadell, i els alts, els dels models.'));
  // La sortida i la posta del sol, amb les icones tal com surten a la taula.
  if (visibles.some((f) => solHora(f.hora))) {
    const dt = element('dt', 'sol-fila');
    dt.append(icona('i-sunrise'), icona('i-sunset'));
    llista.append(dt, element('dd', null, T('L’hora en què surt i es pon el sol, a la fila de l’hora en què passa.')));
  }
  // Les paraules de la frase de dalt d'«Ara» (sensacioTram), orientatives.
  terme(T('Fred, fresc, calor…'), T('A la frase de dalt, com es nota cada tram, amb la temperatura que es nota (amb el vent, quan fa fred): la mínima a la nit i al matí i la màxima a la tarda; al matí, si després escalfa fins a una altra paraula, també aquesta («fresc i després agradable»). Fred intens, sota 0\u00a0°C; molt fred, de 0 a 5\u00a0°C; fred, de 6 a 11\u00a0°C; fresc, de 12 a 17\u00a0°C; temperatura agradable, de 18 a 25\u00a0°C; calor, de 26 a 32\u00a0°C, i molta calor, des de 33\u00a0°C. Són intervals orientatius, no una classificació oficial.'));
  terme(T('Prob.'), T('La probabilitat que plogui en aquella hora. Per sota del 10\u00a0%, no s’espera pluja; del 10 al 20\u00a0%, és poc probable, però pot caure algun ruixat; del 20 al 50\u00a0%, pot ploure: si surts, porta paraigua; del 50\u00a0% amunt, el més probable és que plogui. Per exemple, un 40\u00a0% vol dir que, de cada 10 vegades que la previsió dona un 40\u00a0% per a una hora, en 4 acaba plovent.'));
  terme(T('Pluja'), T('Els mil·límetres que caurien si plou.'));
  // La xifra de la capçalera de cada tram és la quantitat esperada (ADR 0103),
  // no la suma de la columna: la pàgina no ho deia (revisor, 19-10-2026: «uns
  // 31 mm» amb unes files que sumaven 34).
  if (trams.some((t) => t.plou && t.mm >= 1)) {
    terme(T('Pluja del tram'), T('A la capçalera, la probabilitat més alta de les seves hores i la pluja que s’espera: els mil·límetres de cada hora pesats per la seva probabilitat. No és la suma de la columna Pluja, que diu el que cauria si plou.'));
  }
  // La persistència: la pluja de l'última hora, no la d'ara (revisor, 18-10-2026).
  if (visibles.some((f) => f.segons_estacio)) terme('*', T('Xifra que ve de la pluja de l’última hora al barri, encara que ja hagi parat: els models en donaven menys.'));
  if (visibles.some((f) => f.segons_radar)) terme('\u2020', T('Hi compta la pluja que el radar veu acostar-se.'));
  // La part alta, quan és la triada (ADR 0087 i 0123): d'on surt.
  if (zonaTriada() === 'alta') {
    terme(T('Part alta'), T('Les temperatures de la part alta són les de vora la riera més el que sol fer-hi de més, que canvia segons l’hora del dia i l’època de l’any: surt del que han mesurat les estacions del barri a cada hora els últims 30 dies i, de nit, també dels núvols i el vent previstos, perquè amb el cel serè i sense vent l’aire fred s’acumula vora la riera.'));
  }
  if (visibles.some((f) => avisHora(f))) terme(T('Barra de color'), T('Hores amb avís, del color del nivell.'));
  terme(T('Vent'), T('La mitjana de l’hora en km/h i, entre parèntesis, la ratxa més forta de l’hora, la del model que en preveu més.'));
  if (visibles.some((f) => f.vent != null && f.ratxa && nivellRatxa(f.ratxa))) {
    terme(T('Ratxa en color'), T('Passa el llindar groc (72\u00a0km/h) o taronja (108\u00a0km/h) dels avisos de Meteocat i dona l’avís de vent fort. La «i» porta a l’avís, amb d’on surt i quant s’hi pot confiar.'));
  }
  // Si la taula travessa un canvi d'hora, la franja de 2 a 3 surt dues
  // vegades (octubre) o no hi és (març): es diu per què (Juanjo, 13-10-2026).
  const desfasos = visibles.map((f) => new Date(f.hora).getTimezoneOffset());
  if (new Set(desfasos).size > 1) {
    terme(T('Canvi d’hora'), desfasos[desfasos.length - 1] > desfasos[0]
      ? T('Aquesta nit el rellotge es retarda una hora: a les 3 tornen a ser les 2, i la franja de 2 a 3 surt dues vegades.')
      : T('Aquesta nit el rellotge s’avança una hora: a les 2 passen a ser les 3, i la franja de 2 a 3 no hi és.'));
  }
  // La taula arriba fins a les 21 h de demà (ADR 0041): més enllà d'un dia, menys fina.
  if (visibles.length && new Date(visibles[visibles.length - 1].fins) - new Date() > 24 * 3600e3) {
    terme(T('Demà'), T('Més enllà de 24 hores, la previsió és menys segura.'));
  }
  notes.append(llista);
  sec.append(notes);
  return sec;
}

// El botó diu el que farà: desplegar-ho tot si en queda algun de plegat.
function posaBotoTot() {
  const boto = $('boto-tot');
  if (!boto) return;
  const obre = [...document.querySelectorAll('.tram-hores')].some((d) => !d.open);
  boto.dataset.accio = obre ? 'obre' : 'plega';
  boto.replaceChildren(icona(obre ? 'i-chevrons-up-down' : 'i-chevrons-down-up'), obre ? T('Desplega-ho tot') : T('Plega-ho tot'));
  boto.title = obre ? T('Obre totes les franges del dia per veure la previsió hora a hora.') : T('Tanca totes les franges del dia.');
}

// En imprimir, tots els trams oberts; després, com estaven.
addEventListener('beforeprint', () => {
  for (const d of document.querySelectorAll('.previsio details:not([open])')) {
    d.dataset.plegat = '1';
    d.open = true;
  }
});
addEventListener('afterprint', () => {
  for (const d of document.querySelectorAll('.previsio details[data-plegat]')) {
    d.open = false;
    delete d.dataset.plegat;
  }
});

// Tots els avisos vigents en un sol bloc, a dalt; les notes, després. Es
// torna a pintar quan arriba l'historial de «Perill», per la riera (ADR 0076).
let DADES_AVISOS = null;
function pintaAvisos(dades) {
  const avisos = $('avisos');
  avisos.querySelector('.avisos-actius')?.remove();
  const actius = blocAvisos(dades);
  if (actius) avisos.prepend(actius);
}
function repintaAvisos() {
  if (DADES_AVISOS && !dadesVelles(DADES_AVISOS)) pintaAvisos(DADES_AVISOS);
}

// La línia «Actualitzat a les… · propera: …» es queda al capdamunt, sota el
// subtítol, com a «Si surts» i «Consultes» (Juanjo, 17-10-2026: «está oculto
// en medio del texto… que se vea nada más entrar»; ADR 0094).
function pinta(dades) {
  const cont = $('casa');
  cont.replaceChildren();
  // Dades de fa massa: només l'avís i on mirar (ADR 0031).
  if (dadesVelles(dades)) {
    $('avisos').replaceChildren();
    DADES_AVISOS = dades;
    cont.append(blocDadesVelles(dades));
    pintaHorari(dades);
    posaVersio(dades.versio);
    return;
  }
  DADES_AVISOS = dades;
  GENERAT_GRAFICA = dades.generat;
  AVISOS_GRAFICA = dades;
  $('avisos').replaceChildren();
  pintaAvisos(dades);
  const avisos = $('avisos');
  if (dades.previsio_de) avisos.append(element('p', 'avis', textPrevisioAnterior(dades)));
  if (dades.models && dades.models.no_encerten) {
    const m = dades.models;
    avisos.append(element('p', 'avis', T`Avui els models no veuen aquesta pluja: en les darreres ${m.hores} hores han caigut ${coma(m.mesurada_mm)}\u00a0mm a Montflorit i en preveien ${coma(m.prevista_mm)}. Les primeres hores de la taula parteixen del que mesura l\u2019estació; per a la resta, fes més cas dels avisos.`));
  }
  // El radar porta l'estat únic de la pluja (ADR 0101), per dir el mateix que «Ara».
  const radarAmbPluja = dades.radar && dades.pluja_ara ? { ...dades.radar, pluja: dades.pluja_ara } : dades.radar;
  const ara = dades.ara_casa && blocAra(dades.ara_casa, radarAmbPluja, dades.vent, dades.veines, dades.hores,
    mesuradaZona(dades));
  if (ara) cont.append(ara);
  const estat = estatPortada(dades);
  if (estat) cont.append(estat);
  const previsio = dades.hores && taula(dades.hores, mesuradaZona(dades), dades.riscos, dades.sol);
  // La gràfica, just després d'«Ara» (19-10-2026); el detall del dia, després.
  if (previsio && previsio._grafica) cont.append(previsio._grafica);
  // El radar, sota la gràfica (Juanjo, 22-10-2026); la frase d'«Ara» ja en diu
  // la conclusió.
  if (ara && ara._radar) cont.append(ara._radar);
  // La setmana, sota la gràfica i el radar (ADR 0122): primer el que és a prop.
  const setmana = dades.hores && blocSetmana(dades);
  if (setmana) cont.append(setmana);
  // El resum d'avui i el de demà, en text, ja no hi són (portada nova, ADR
  // 0118): ho diuen la frase de dalt d'«Ara» i els trams. Sense dades d'ara,
  // el resum d'avui, com sempre.
  if (OFERTA_AVISOS) cont.append(OFERTA_AVISOS);
  if (!ara) cont.append(...blocsResum(dades, true));
  if (previsio) {
    cont.append(previsio);
    dibuixaGrafiques();
    obreGraficaDeLEnllac();
    ajustaFranges();
    posaBotoTot();
  }
  pintaHorari(dades);
  posaVersio(dades.versio);
}

// L'oferta d'avisos a qui té la web instal·lada (Juanjo, 12-10-2026; ADR 0080):
// el navegador no deixa enviar notificacions sense permís, i el permís només
// es pot demanar quan la persona toca un botó. Qui instal·la la web la vol a
// mà: en obrir-la instal·lada, i si encara no té els avisos, una targeta sota
// «Ara», sense finestra, amb un sol toc per rebre els de perill i la riera
// (AVISOS_PER_DEFECTE). «Ara no» la treu per sempre en aquest dispositiu.
const CLAU_OFERTA_AVISOS = 'meteo.oferta-avisos';
let OFERTA_AVISOS = null;

function webInstallada() {
  return matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
}

async function calOfertaAvisos() {
  if (!webInstallada() || !('serviceWorker' in navigator) || !('PushManager' in window)
      || !('Notification' in window) || Notification.permission === 'denied') return false;
  try { if (localStorage.getItem(CLAU_OFERTA_AVISOS) === 'no') return false; } catch (_) {}
  const registre = await navigator.serviceWorker.ready;
  return !(await registre.pushManager.getSubscription());
}

function targetaOfertaAvisos() {
  const sec = element('section', 'targeta oferta-avisos');
  sec.setAttribute('aria-label', T('Avisos de perill'));
  const estat = element('p', 'oferta-estat');
  estat.setAttribute('role', 'status');
  const si = element('button', 'boto', T('Activa-ho'));
  // Qui en vol uns altres, a «Avisos», on es trien (Juanjo, 12-10-2026: «que se
  // puede configurar en la sección avisos, con su botón»).
  const tria = element('a', 'boto secundari', T('Tria quins'));
  tria.href = 'avisos.html';
  const no = element('button', 'boto secundari', T('Ara no'));
  si.type = 'button';
  no.type = 'button';
  const botons = element('p', 'oferta-botons');
  botons.append(si, tria, no);
  sec.append(element('p', 'oferta-titol', T('Avisos de perill')),
    element('p', null, T('Riera, incendis, avisos oficials i temps extrem a Montflorit, al moment.')), botons, estat);
  no.addEventListener('click', () => {
    try { localStorage.setItem(CLAU_OFERTA_AVISOS, 'no'); } catch (_) {}
    sec.remove();
    OFERTA_AVISOS = null;
  });
  si.addEventListener('click', async () => {
    si.disabled = true;
    try {
      if ((await Notification.requestPermission()) !== 'granted') {
        estat.textContent = T('El navegador té bloquejades les notificacions d’aquesta web. Permet-les a la configuració del navegador (al cadenat, al costat de l’adreça) i torna-ho a provar.');
        return;
      }
      const subscripcio = await subscriuAvisos(await navigator.serviceWorker.ready);
      await cridaAvisos({ accio: 'desa', subscripcio: subscripcio.toJSON(), avisos: AVISOS_PER_DEFECTE, resum: '', nit: false,
        idioma: document.documentElement.lang === 'es' ? 'es' : 'ca' });
      botons.remove();
      estat.textContent = T('Fet: t’arribaran els avisos de perill i de la riera. Per triar-ne més, toca la campana.');
      OFERTA_AVISOS = null;
    } catch (_) {
      estat.textContent = T('No s’han pogut activar els avisos. Torna-ho a provar d’aquí a una estona.');
    } finally {
      si.disabled = false;
    }
  });
  return sec;
}

calOfertaAvisos().then((cal) => {
  if (!cal) return;
  OFERTA_AVISOS = targetaOfertaAvisos();
  const ara = document.querySelector('#casa .targeta.ara');
  if (ara) ara.after(OFERTA_AVISOS);
}).catch(() => {});

botoZona();

carrega(FITXER_DADES, pinta, () => {
  $('casa').replaceChildren(element('p', 'avis', T('No s’ha pogut carregar la previsió. Torna-ho a provar d’aquí a una estona.')));
});
