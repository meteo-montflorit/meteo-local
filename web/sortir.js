// SPDX-License-Identifier: AGPL-3.0-or-later
// «Si surts» (ADR 0029): per a qui surt de Montflorit a una hora i torna a una
// altra, com anirà cada mitjà, quina roba cal, consells, si circulen els
// trens i el trànsit de prop. Tot surt de la previsió hora a hora de casa.json
// (o, a la web pública, montflorit.json): no cal res més del servidor que
// l'índex UV, l'estat dels trens i les incidències de trànsit (ADR 0052).

const FITXER_DADES = document.documentElement.dataset.dades || 'casa.json';
const TORNADA_PER_DEFECTE_H = 3;

// Llindars de pluja, iguals per a tots els mitjans (ADR 0069): només la
// probabilitat, que ja porta els models, el radar, les estacions i el que
// aprèn el programa; sense probabilitat, els mil·límetres. Amb «millor no» ha
// de ploure almenys 2 de cada 3 vegades, i amb «bé», com a molt 1 de cada 100:
// el NAS els aprèn cada dia amb el que passa a Montflorit i arriben a les dades
// (sortir_llindars); aquests, els de partida (config.SORTIR_LLINDARS_PLUJA),
// per si no hi són. Dos jocs: per d'aquí a CURT_H hores o menys, i per a més
// tard, quan la previsió és menys segura. «pluja»: «millor no» en bici i moto,
// «compte» en cotxe; «risc»: «compte» en bici i moto i el paraigua a peu.
const LLINDARS_PLUJA_INICI = { curt: { pluja: 0.4, risc: 0.1 }, llarg: { pluja: 0.6, risc: 0.1 } };
const CURT_H = 3;
const MM_RISC = 0.2;
const MM_PLUJA = 1;
let llindarsPluja = LLINDARS_PLUJA_INICI;

// Els llindars d'una hora, segons quant falta perquè acabi (com antelacio_h del registre).
function llindars(f) {
  const h = (new Date(f.fins) - Date.now()) / 3.6e6;
  const banda = h <= CURT_H ? 'curt' : 'llarg';
  return { ...LLINDARS_PLUJA_INICI[banda], ...((llindarsPluja || {})[banda] || {}) };
}
// Vent (ratxes, km/h) i fred (°C) per mitjà: [compte, millor no].
const LLINDARS = {
  peu: { ratxa: [null, 70], fred: [null, null] },
  bici: { ratxa: [40, 50], fred: [3, 1] },
  moto: { ratxa: [50, 70], fred: [3, 1] },
  cotxe: { ratxa: [90, null], fred: [1, null] },
  public: { ratxa: [null, null], fred: [null, null] },
};
// Pluja per al cotxe (mm), [compte, millor no]: els llindars de Meteocat que fan
// servir els perills de la web (config.RISC_LLINDARS, ADR 0018), que cal passar
// (no n'hi ha prou d'arribar-hi): la mesurada a
// la darrera mitja hora, si se surt ara, i la prevista en 3 hores. Fins a la
// 3.138.6, 20 i 40 mm previstos en una hora (AEMET), que amb l'arxiu de
// 2024-2026 gairebé no sortien i no encertaven l'hora (ADR 0039).
const PLUJA_COTXE_30MIN = [20, 40];
const PLUJA_COTXE_3H = [60, 90];

// La pluja prevista en 3 hores seguides al voltant d'una hora del viatge: de les
// finestres de 3 hores que la contenen, la que més acumula. Com els perills
// (riscos.py), només compten les hores en què pot ploure (20 % o més).
function plujaTresHores(hores, f) {
  const i = (hores || []).findIndex((h) => h.hora === f.hora);
  if (i < 0) return null;
  const pot = (h) => h.probabilitat == null || h.probabilitat >= PROB_POSSIBLE;
  let millor = null;
  for (let ini = Math.max(0, i - 2); ini <= i && ini + 3 <= hores.length; ini++) {
    const tram = hores.slice(ini, ini + 3);
    const mm = tram.reduce((s, h) => s + (pot(h) ? h.pluja_mm || 0 : 0), 0);
    if (!millor || mm > millor.mm) millor = { mm, ini: tram[0], fi: tram[2] };
  }
  return millor;
}
const VELOCITAT = { peu: 0, bici: 18, moto: 45, cotxe: 0, public: 0 };
const CANVI_TEMPERATURA = 6;
const CALOR = 32;
const UV_MINIM = 3;
const ORDRE = ['neutre', 'be', 'compte', 'no'];
const MITJANS_TRANSIT = ['cotxe', 'moto'];

// El temps violent de Meteocat (calamarsa, esclafits, ratxes) compta com
// les tempestes: abans no hi era i «Si surts» deia «Bé» amb «Observat ara,
// perill … per temps violent» a «Avisos actius» (inventari del 18-10-2026).
function avisPluja(f) {
  return (f.avisos || []).some((a) => a.tipus.some((t) => t === 'pluja' || t === 'tempestes' || t === 'temps_violent'));
}

// Risc de pluja en una hora: el mateix que «moja» de casa.py.
function mulla(f) {
  return sobre(f, llindars(f).risc, MM_RISC) || f.plou_ara || avisPluja(f);
}

// Una hora amb risc de pluja només per l'avís de l'AEMET: ni la probabilitat
// (que ja porta el radar), ni els models, ni les estacions hi veuen pluja. Es
// manté el que diu l'avís, però es diu clar (ADR 0008 i 0029).
function senseDades(f) {
  // «Ni el radar» ha de ser cert: amb pluja al radar per sota del llindar
  // amb què puja la probabilitat, no ho és (inventari del 18-10-2026).
  return !sobre(f, llindars(f).risc, MM_RISC) && !f.plou_ara && !(f.radar && f.radar.prob >= llindars(f).risc);
}

// «Ni el radar, ni les estacions, ni els models» ha de valer per a tota la
// sortida, no només per a l'anada i la tornada (revisor, 20-10-2026: «Pot
// arribar pluja cap a les 02:10» a la portada i la fila de les 2 amb un 37 %).
// La pluja que el radar veu venir (pluja_ara, si se surt ara) o una hora del
// mig amb dades; null si no n'hi ha.
function plujaEntremig(tram, entorn, futur) {
  const pa = (entorn || {}).pluja_ara || {};
  const t = !futur && (pa.estat === 'arriba' || pa.estat === 'possible') ? pa[pa.estat] : null;
  const fi = new Date(tram[tram.length - 1].hora).getTime() + 3600e3;
  if (t && new Date(t).getTime() < fi) return { radar: horaCurta(t) };
  const f = tram.find((x) => !senseDades(x));
  return f ? { hora: hora(f) } : null;
}

function textNomesAvis(q, entremig, cua) {
  if (!entremig) return T`Avís oficial per pluja ${q}: ni el radar, ni les estacions, ni els models hi veuen pluja.` + cua;
  return (entremig.radar ? T`Avís oficial per pluja ${q}, i el radar veu pluja que pot arribar cap a les ${entremig.radar}.`
    : T`Avís oficial per pluja ${q}, i entremig pot ploure, cap a les ${entremig.hora}\u00a0h.`) + cua;
}

function plouClar(f) {
  return plouRodes(f) || avisPluja(f);
}

// Sense probabilitat, manen els mil·límetres, com a la pàgina del temps.
// L'avís de l'AEMET tot sol porta a «compte», no a «no» (ADR 0047).
function sobre(f, prob, mm) {
  return f.probabilitat == null ? (f.pluja_mm || 0) >= mm : f.probabilitat >= prob;
}

function plouRodes(f) {
  return sobre(f, llindars(f).pluja, MM_PLUJA) || f.plou_ara;
}

// Si se surt ara i ara plou, es diu que plou i qui ho veu (les estacions, el
// radar o tots dos), no «pluja probable a l'anada (7 h)» (Juanjo, 19-10-2026:
// «si llueve, debe decir que llueve sea por radar, estaciones o ambas» i
// «esto solo hay que tenerlo en cuenta cuando surto está en ara»). Surt de
// l'estat únic de la pluja d'ara (pluja_ara, ADR 0101), el de la portada, no
// de la marca de l'hora en curs de la taula: passada l'hora en punt, amb les
// dades d'abans, «Ara» és ja l'hora següent i la marca no hi és.
function fontPlujaAra(plujaAra, radar, ara = new Date()) {
  const estat = (plujaAra || {}).estat;
  if (estat === 'radar_sobre') return T('el radar');
  if (estat !== 'plou') return null;
  const arriba = (radar || {}).arriba;
  return arriba && new Date(arriba) <= new Date(ara.getTime() + 5 * 60000)
    ? T('les estacions i el radar') : T('les estacions');
}

function textPlujaProbable(anada, tornada, cond, araPlou) {
  if (!araPlou) return T`Pluja probable ${quan(anada, tornada, cond)}`;
  const ara = T`Ara plou al barri, segons ${araPlou}`;
  return cond(tornada) ? T`${ara}, i pluja probable a la tornada (${hora(tornada)}\u00a0h)` : ara;
}

// Pluja per sota del 20 % (C.PROB_ATENCION), on la taula i el resum diuen
// «sense pluja»: «Si surts» ho avisa amb el seu llindar après, però amb
// «poca probabilitat», no amb «pot ploure» (inventari del 18-10-2026).
const PROB_POSSIBLE = 0.2;
function pocaPluja(fs) {
  return fs.length > 0 && fs.every((f) => f.probabilitat != null && f.probabilitat < PROB_POSSIBLE
    && !f.plou_ara && !avisPluja(f));
}

function mullaRodes(f) {
  return mulla(f);
}

function nomesAvisRodes(f) {
  return senseDades(f);
}

function hora(f) {
  return horaLocal(f.hora);
}

function graus(t) {
  return `${Math.round(t)} °C`;
}

// On passa: «a l'anada (17 h)», «a la tornada (21 h)» o «a l'anada i a la tornada».
function quan(anada, tornada, cond) {
  const a = cond(anada);
  const t = cond(tornada);
  if (a && t) return T('a l’anada i a la tornada');
  if (a) return T`a l’anada (${hora(anada)} h)`;
  return T`a la tornada (${hora(tornada)} h)`;
}

// Veredicte d'un mitjà: {nivell: be|compte|no, motius: [...]}.
// entorn: {hores, ara} (totes les hores de la taula i el que es mesura ara),
// per a la pluja del cotxe en 3 hores i la de l'última mitja hora.
function avalua(mitja, tram, trens, futur, transit, entorn) {
  const anada = tram[0];
  const tornada = tram[tram.length - 1];
  const viatge = [anada, tornada];
  const ll = LLINDARS[mitja];
  const res = { nivell: 'be', motius: [] };
  const puja = (nivell, motiu) => {
    if (ORDRE.indexOf(nivell) > ORDRE.indexOf(res.nivell)) res.nivell = nivell;
    res.motius.push(motiu);
  };
  const ratxa = Math.max(...viatge.map((f) => f.ratxa || 0));
  const temps = viatge.map((f) => f.temperatura).filter((t) => t != null);
  const tMin = temps.length ? Math.min(...temps) : null;

  // Només si se surt ara (futur fals): la pluja que cau en aquest moment.
  const araPlou = !futur && entorn ? fontPlujaAra(entorn.pluja_ara, entorn.radar) : null;
  if (mitja === 'bici' || mitja === 'moto') {
    if (araPlou || viatge.some(plouRodes)) {
      puja('no', `${textPlujaProbable(anada, tornada, plouRodes, araPlou)}.`);
    } else if (viatge.some(mullaRodes)) {
      const moto = mitja === 'moto';
      if (viatge.filter(mullaRodes).every(nomesAvisRodes)) {
        puja('compte', textNomesAvis(quan(anada, tornada, mullaRodes), plujaEntremig(tram, entorn, futur),
          moto ? T(' Per si de cas, porta l’impermeable.') : ''));
      } else if (pocaPluja(viatge.filter(mullaRodes))) {
        puja('compte', moto ? T`Poca probabilitat de pluja ${quan(anada, tornada, mullaRodes)}: porta l’impermeable per si de cas.`
          : T`Poca probabilitat de pluja ${quan(anada, tornada, mullaRodes)}.`);
      } else {
        puja('compte', moto ? T`Pot ploure ${quan(anada, tornada, mullaRodes)}: porta l’impermeable.`
          : T`Pot ploure ${quan(anada, tornada, mullaRodes)}.`);
      }
    }
  }
  if (mitja === 'cotxe') {
    // Amb pluja el cotxe no surt «bé» per defecte: molta pluja ara al barri o
    // prevista en 3 hores (llindars de Meteocat), probable, o possible (que no
    // puja el nivell però es diu). Amb la xifra, no amb «forta» (ADR 0043).
    const ara30 = !futur ? (((entorn || {}).ara || {}).pluja_30min || 0) : 0;
    const tres = viatge.map((f) => plujaTresHores((entorn || {}).hores, f)).filter(Boolean)
      .reduce((a, b) => (!a || b.mm > a.mm ? b : a), null);
    const mm3 = tres ? Math.round(tres.mm) : 0;
    const tresTxt = tres && T`de ${hora(tres.ini)} a ${horaLocal(tres.fi.fins)}\u00a0h`;
    const mm30 = Math.round(ara30);
    if (ara30 > PLUJA_COTXE_30MIN[1]) puja('no', T`Ara plou amb molta intensitat al barri (${mm30}\u00a0mm en mitja hora): millor no agafar el cotxe.`);
    else if (tres && tres.mm > PLUJA_COTXE_3H[1]) puja('no', T`Fins a ${mm3}\u00a0mm de pluja en 3 hores (${tresTxt}): millor no agafar el cotxe.`);
    else if (ara30 > PLUJA_COTXE_30MIN[0]) puja('compte', T`Ara plou amb força al barri (${mm30}\u00a0mm en mitja hora): condueix amb compte.`);
    else if (tres && tres.mm > PLUJA_COTXE_3H[0]) puja('compte', T`Fins a ${mm3}\u00a0mm de pluja en 3 hores (${tresTxt}): condueix amb compte.`);
    else if (araPlou || viatge.some(plouClar)) {
      // El nivell, el de sempre; el text, el mateix que en moto (ADR 0047): «Pluja
      // probable» només si la probabilitat ho diu, i l'avís, si és l'únic que la veu.
      const dades = (f) => sobre(f, llindars(f).risc, MM_RISC) || f.plou_ara;
      if (araPlou || viatge.some(plouRodes)) puja('compte', T`${textPlujaProbable(anada, tornada, plouRodes, araPlou)}: condueix amb compte.`);
      else if (viatge.some(dades)) {
        puja('compte', pocaPluja(viatge.filter(dades)) ? T`Poca probabilitat de pluja ${quan(anada, tornada, dades)}: condueix amb compte.`
          : T`Pot ploure ${quan(anada, tornada, dades)}: condueix amb compte.`);
      }
      else if (viatge.some(avisPluja)) {
        puja('compte', textNomesAvis(quan(anada, tornada, avisPluja), plujaEntremig(tram, entorn, futur), T(' Condueix amb compte.')));
      } else puja('compte', T`Pot ploure ${quan(anada, tornada, plouClar)}: condueix amb compte.`);
    } else if (viatge.some(mullaRodes)) {
      res.motius.push(pocaPluja(viatge.filter(mullaRodes)) ? T`Poca probabilitat de pluja ${quan(anada, tornada, mullaRodes)}.`
        : T`Pot ploure ${quan(anada, tornada, mullaRodes)}.`);
    }
  }
  if (ll.ratxa[1] != null && ratxa >= ll.ratxa[1]) puja('no', T`Ratxes de vent de fins a ${Math.round(ratxa)} km/h.`);
  else if (ll.ratxa[0] != null && ratxa >= ll.ratxa[0]) puja('compte', T`Ratxes de vent de fins a ${Math.round(ratxa)} km/h.`);
  if (tMin != null && ll.fred[1] != null && tMin <= ll.fred[1]) puja('no', T`${graus(tMin)}: hi pot haver gel.`);
  else if (tMin != null && ll.fred[0] != null && tMin <= ll.fred[0]) puja('compte', T`${graus(tMin)}: compte amb el gel a primera hora.`);
  if (mitja === 'peu' && araPlou) {
    // Si ara plou, també a peu es diu, com en els vehicles (19-10-2026).
    puja('compte', T`Ara plou al barri, segons ${araPlou}: porta paraigua.`);
  } else if (mitja === 'peu' && tram.some(mulla)) {
    // «Pluja probable» amb el mateix llindar que els vehicles (plouRodes): amb un
    // 60 % a la tornada, a peu deia «pot ploure» i els altres «pluja probable»
    // (revisor, 19-10-2026).
    puja('compte', tram.filter(mulla).every(senseDades)
      ? T('Avís oficial per pluja mentre ets fora: ni el radar, ni les estacions, ni els models hi veuen pluja. Per si de cas, porta paraigua.')
      : tram.some(plouRodes) ? T('Pluja probable mentre ets fora: porta paraigua.')
        : pocaPluja(tram.filter(mulla)) ? T('Poca probabilitat de pluja mentre ets fora: porta paraigua per si de cas.')
          : T('Pot ploure mentre ets fora: porta paraigua.'));
  }
  if (mitja === 'public') return avaluaPublic(trens, futur);
  // En vehicle només es miren l'anada i la tornada: es diu, perquè no
  // xoqui amb els consells, que miren tot el temps fora (inventari del 18-10-2026).
  if (!res.motius.length) res.motius.push(mitja === 'peu' ? T('Sense pluja ni vent fort.') : T('Sense pluja ni vent fort a l’anada ni a la tornada.'));
  // El trànsit és el d'ara: només compta si surts ara (ADR 0052).
  if (MITJANS_TRANSIT.includes(mitja) && !futur) {
    const greus = (transit || []).filter((i) => i.tipus === 'retencio' && i.nivell >= NIVELL_TRANSIT);
    if (greus.length) {
      const carreteres = [...new Set(greus.map((i) => i.carretera))].join(', ');
      puja('compte', T`Ara hi ha retencions o talls a menys de 5\u00a0km: ${carreteres}.`);
    }
  }
  return res;
}

// El transport públic, segons els trens de Cerdanyola: tots circulen, algun
// té incidències o no en circula cap. Les incidències dels busos es llisten a
// part i no canvien el nivell.
function avaluaPublic(trens, futur) {
  const res = estatPublic(trens);
  // Les dades dels trens són les d'ara: si la sortida triada és més tard, es diu
  // (auditoria del 07-10-2026).
  if (futur) res.motius.push(T('Són els trens d’ara, no els de l’hora triada.'));
  return res;
}

function estatPublic(trens) {
  const senseDades = (trens || []).filter((l) => l.estat === 'sense_dades');
  const deDia = (trens || []).filter((l) => l.estat !== 'fora_horari' && l.estat !== 'sense_dades');
  const noms = (ls) => ls.map((l) => l.linia).join(', ');
  if (!deDia.length) {
    const nit = (trens || []).some((l) => l.estat === 'fora_horari');
    return { nivell: 'neutre', etiqueta: nit ? 'Fora d’horari' : 'Sense dades',
      motius: [nit ? T('A aquesta hora no circulen trens.') : T('Ara no hi ha dades dels trens.')] };
  }
  const malament = deDia.filter((l) => l.estat !== 'circula');
  // Si falten dades d'alguna línia, no es pot dir que tot vagi bé (auditoria del 08-10-2026).
  if (!malament.length) {
    if (!senseDades.length) return { nivell: 'be', motius: [T('Cap incidència als trens de Cerdanyola.')] };
    return { nivell: 'neutre', etiqueta: 'Dades parcials',
      motius: [T`${noms(deDia)} sense incidències; de ${noms(senseDades)} ara no hi ha dades.`] };
  }
  const quines = malament.map((l) => `${l.linia} ${TD(TEXT_ESTAT[l.estat]).toLowerCase()}`).join(', ');
  const cap = deDia.every((l) => l.estat === 'sense_trens' || l.estat === 'bus');
  const motius = [T`Trens: ${quines}.`];
  if (senseDades.length) motius.push(T`De ${noms(senseDades)} ara no hi ha dades.`);
  return { nivell: cap ? 'no' : 'compte', etiqueta: cap ? 'Sense trens' : 'Amb incidències', motius };
}

// Peça per a una temperatura que es nota (arrodonida) i un mitjà.
function peca(mitja, s) {
  if (mitja === 'moto') {
    if (s < 0) return T('Roba de moto d’hivern tèrmica, guants d’hivern i tub de coll.');
    if (s <= 10) return T('Jaqueta de moto d’hivern, guants d’hivern i tub de coll.');
    if (s <= 17) return T('Jaqueta de moto amb folre i guants d’entretemps.');
    if (s <= 24) return T('Jaqueta de moto de mitja temporada i guants d’entretemps.');
    return T('Jaqueta de moto d’estiu, ventilada, i guants d’estiu.');
  }
  if (mitja === 'bici') {
    if (s <= 0) return T('Jaqueta d’abric, guants i tub de coll.');
    if (s <= 10) return T('Jaqueta tallavent amb una capa a sota, i guants.');
    if (s <= 17) return T('Jaqueta tallavent lleugera.');
    if (s <= 20) return T('Màniga llarga o una jaqueta molt lleugera.');
    return T('Màniga curta.');
  }
  if (s <= 0) return T('Abric, gorro, bufanda i guants.');
  if (s <= 5) return T('Abric, bufanda i guants.');
  if (s <= 10) return T('Abric.');
  if (s <= 14) return T('Jaqueta.');
  if (s <= 17) return T('Jaqueta lleugera o jersei.');
  if (s <= 20) return T('Màniga llarga o jersei fi.');
  if (s <= 24) return T('Màniga curta o màniga llarga fina.');
  return T('Màniga curta.');
}

// Roba per a un mitjà, a l'anada i a la tornada, amb el fred que es nota: a la
// velocitat del mitjà en bici i en moto, i amb el vent previst a peu (també
// fins al cotxe o a l'estació). Si la tornada demana una altra peça, es diu a
// part; en moto, una sola jaqueta per a tota la sortida, la del moment més fred.
function roba(mitja, tram, pluja) {
  const extrems = [tram[0], tram[tram.length - 1]]
    .filter((f) => f.temperatura != null)
    .map((f) => {
      const kmh = VELOCITAT[mitja] || f.vent || 0;
      return { f, t: f.temperatura, kmh, s: Math.round(esNota(f.temperatura, kmh)) };
    });
  if (!extrems.length) return '';
  const fred = extrems.reduce((a, b) => (b.s < a.s ? b : a));
  const [anada, tornada] = mitja === 'moto' ? [fred, fred] : [extrems[0], extrems[extrems.length - 1]];
  const parts = [peca(mitja, anada.s)];
  const altra = peca(mitja, tornada.s);
  if (tram.length > 1 && altra !== parts[0]) {
    parts.push(T`A la tornada (${hora(tornada.f)} h, ${graus(tornada.t)}): ${altra[0].toLowerCase() + altra.slice(1)}`);
  }
  if (fred.s < Math.round(fred.t)) {
    parts.push(VELOCITAT[mitja] ? T`A ${VELOCITAT[mitja]} km/h, ${graus(fred.t)} es noten com ${graus(fred.s)}.`
      : T`Amb vent de ${Math.round(fred.kmh)} km/h, ${graus(fred.t)} es noten com ${graus(fred.s)}.`);
  }
  if (pluja && (mitja === 'moto' || mitja === 'bici')) parts.push(T('Impermeable.'));
  return parts.join(' ');
}

const NIVELL_UV = [[11, 'extrem'], [8, 'molt alt'], [6, 'alt'], [3, 'moderat']];

// Consells per a tota la sortida: pluja que comença o s'acaba, canvi de
// temperatura, sol, nit i calor.
function consells(tram, ara) {
  const res = [];
  const mullat = tram.map(mulla);
  const avis = tram.filter(mulla).every(senseDades);
  if (!mullat[0] && mullat.some(Boolean)) {
    const f = tram[mullat.indexOf(true)];
    res.push(avis ? T`A partir de les ${hora(f)} h, avís oficial per pluja.`
      : T`A partir de les ${hora(f)} h, risc de pluja.`);
  } else if (mullat[0] && !mullat.every(Boolean)) {
    // Si el risc torna més tard, és una pausa, no el final (revisor,
    // 18-10-2026: «s'acaba el risc» a les 15 h amb pluja possible de 16 a 0 h).
    const sec = mullat.indexOf(false);
    const torna = mullat.indexOf(true, sec);
    const h = hora(tram[sec]);
    if (torna < 0) {
      res.push(avis ? T`Cap a les ${h} h s’acaba l’avís oficial.` : T`Cap a les ${h} h s’acaba el risc de pluja.`);
    } else {
      const h2 = hora(tram[torna]);
      res.push(avis ? T`De ${h} a ${h2} h, sense avís oficial per pluja.` : T`De ${h} a ${h2} h, sense risc de pluja.`);
    }
  }
  const amb = tram.filter((f) => f.temperatura != null);
  if (amb.length) {
    const fMin = amb.reduce((a, b) => (b.temperatura < a.temperatura ? b : a));
    const fMax = amb.reduce((a, b) => (b.temperatura > a.temperatura ? b : a));
    if (fMax.temperatura - fMin.temperatura >= CANVI_TEMPERATURA) {
      res.push(T`La temperatura va de ${graus(fMin.temperatura)} (${hora(fMin)} h) a ${graus(fMax.temperatura)} (${hora(fMax)} h).`);
    }
    if (fMax.temperatura >= CALOR) {
      res.push(T`Calor: fins a ${graus(fMax.temperatura)}. Porta aigua i evita el sol de les hores centrals.`);
    }
  }
  const uv = tram.filter((f) => f.uv != null).reduce((a, b) => (!a || b.uv > a.uv ? b : a), null);
  if (uv && uv.uv >= UV_MINIM) {
    const nivell = NIVELL_UV.find(([minim]) => uv.uv >= minim)[1];
    res.push(T`Protector solar, gorra i ulleres de sol: índex UV ${TD(nivell)} (${Math.round(uv.uv)}) cap a les ${hora(uv)} h.`);
  }
  // De nit: el sol per sota de l'horitzó en sortir o en tornar.
  const surt = new Date(Math.max(new Date(tram[0].hora).getTime(), ara.getTime()));
  const torna = new Date(tram[tram.length - 1].hora);
  const nitSurt = alturaSol(surt) < -0.8;
  const nitTorna = alturaSol(torna) < -0.8;
  if (nitSurt && nitTorna) res.push(T('Surts i tornes de nit: a peu, en bici o en patinet, roba visible i llum.'));
  else if (nitSurt) res.push(T('Surts de nit: a peu, en bici o en patinet, roba visible i llum.'));
  else if (nitTorna) res.push(T('Tornaràs de nit: a peu, en bici o en patinet, roba visible i llum.'));
  return res;
}

// --- Selectors d'hora ------------------------------------------------------------

// Les hores poden arribar a l'endemà de demà al matí (la previsió acaba el
// tram de nit, ADR 0041): llavors, amb el dia de la setmana.
function etiquetaHora(f, ara) {
  const d = new Date(f.hora);
  const text = horaCurta(d);
  if (mateixDia(d, ara)) return text;
  const dia = nomDiaCurt(d, ara);
  return dia === T('demà') ? T`demà ${text}` : `${dia} ${text}`;
}

function omple(select, opcions, triada) {
  select.replaceChildren(...opcions.map(([valor, text]) => {
    const o = element('option', null, text);
    o.value = valor;
    return o;
  }));
  if (opcions.some(([v]) => v === triada)) select.value = triada;
}

let DADES = null;

// L'enllaç d'una fitxa porta les hores triades (urlFitxa): la primera vegada
// es fan servir, si encara hi són.
const HORES_ENLLAC = new URLSearchParams(location.search);

function pintaSelectors(hores, ara) {
  const surto = $('surto');
  const torno = $('torno');
  // Un enllaç d'abans de la 3.201.0 porta les hores sense el desfasament.
  const abansSurto = surto.value || ambDesfas(HORES_ENLLAC.get('surto') || '');
  const abansTorno = torno.value || ambDesfas(HORES_ENLLAC.get('torno') || '');
  omple(surto, hores.slice(0, -1).map((f, i) => [f.hora, i === 0 ? T('Ara') : etiquetaHora(f, ara)]), abansSurto);
  const i = Math.max(0, hores.findIndex((f) => f.hora === surto.value));
  const per = Math.min(i + TORNADA_PER_DEFECTE_H, hores.length - 1);
  omple(torno, hores.slice(i + 1).map((f) => [f.hora, etiquetaHora(f, ara)]),
    abansTorno && llegeixHora(abansTorno) > llegeixHora(surto.value) ? abansTorno : hores[per].hora);
}

// --- Pintar ----------------------------------------------------------------------

// Noms que es tradueixen com les paraules de les dades (TD).
const MITJANS = [['peu', 'A peu', 'i-footprints'], ['bici', 'Bici o patinet', 'i-bike'],
  ['moto', 'Moto', 'i-motorbike'], ['cotxe', 'Cotxe', 'i-car'], ['public', 'Transport públic', 'i-train-front']];

// Els mitjans que cadascú vol veure, en aquest navegador. Es desa el que s'ha
// tret, perquè un mitjà nou surti marcat.
const CLAU_AMAGATS = 'meteo.mitjans-amagats';
function amagats() {
  try { return new Set(JSON.parse(localStorage.getItem(CLAU_AMAGATS)) || []); } catch (_) { return new Set(); }
}
function desaAmagats(conjunt) {
  try { localStorage.setItem(CLAU_AMAGATS, JSON.stringify([...conjunt])); } catch (_) {}
}

// L'explicació de les caselles surt fins que algú en desmarca una per primer
// cop: llavors ja se sap com funciona.
const CLAU_EXPLICAT = 'meteo.mitjans-explicat';
function explicat() {
  try { return localStorage.getItem(CLAU_EXPLICAT) === '1'; } catch (_) { return amagats().size > 0; }
}

function pintaTriats() {
  const caixa = $('triats');
  const fora = amagats();
  const explica = element('p', 'nota explica-triats',
    T('Toca un mitjà per deixar de veure’l; torna-hi a tocar per recuperar-lo. Es recorda en aquest dispositiu.'));
  explica.hidden = explicat() || fora.size > 0;
  for (const [clau, nom, icon] of MITJANS) {
    const etiqueta = element('label', 'xip');
    etiqueta.title = T`Mostra o amaga «${TD(nom)}». Es recorda en aquest dispositiu.`;
    const casella = element('input');
    casella.type = 'checkbox';
    casella.value = clau;
    casella.checked = !fora.has(clau);
    casella.addEventListener('change', () => {
      const ara = amagats();
      if (casella.checked) ara.delete(clau); else ara.add(clau);
      desaAmagats(ara);
      if (!casella.checked) {
        try { localStorage.setItem(CLAU_EXPLICAT, '1'); } catch (_) {}
        explica.hidden = true;
      }
      posaResumTriats();
      if (DADES) pintaSortida();
    });
    etiqueta.append(casella, icona(icon), element('span', null, TD(nom)));
    caixa.append(etiqueta);
  }
  caixa.after(explica);
  posaResumTriats();
}

// Els mitjans, plegats sota «Tria els mitjans (5 de 5)»: es trien un cop i es recorden,
// i la resposta queda a dalt (Juanjo, 12-10-2026; ADR 0074).
function posaResumTriats() {
  const vistos = MITJANS.length - MITJANS.filter(([c]) => amagats().has(c)).length;
  $('triats-resum').textContent = T`Tria els mitjans (${vistos} de ${MITJANS.length})`;
}
const TEXT_NIVELL = { be: 'Bé', compte: 'Compte', no: 'Millor no' };

// Els avisos de perill no es repeteixen aquí: una sola línia diu quants n'hi
// ha que poden afectar la conducció i porta a «Perill» (Juanjo, 19-10-2026:
// «en si surts salen todas las alertas, prefiero simplificarlo. si hay alertas
// que afectan a la conduccion lo mejor es que remita a la pestaña perill»;
// ADR 0093). No hi compten la calor, el mar, el Pla Alfa i els tancaments
// d'espais forestals (l'accés a peu al bosc) ni els talls de llum, que
// segueixen a la portada i a «Perill».
const SENSE_CONDUCCIO = new Set(['calor', 'mar', 'costaners']);

// Meteocat, un per fenomen, com a «Avisos actius» de la portada (curtsSmp):
// només la clau i el color, que és el que es compta.
function smpPerFenomen(smp) {
  const fenomens = ((smp || {}).fenomens || []).filter((f) => COLOR_SMP[f.nivell]);
  const llista = fenomens.length ? fenomens : ((smp || {}).linies || []).filter((l) => COLOR_SMP[l.nivell]);
  return llista.map((f, n) => ({ dataset: { clau: `smp:${f.fenomen || `linia${n}`}` }, className: `avis-item ${COLOR_SMP[f.nivell]}` }));
}

function avisosConduccio(dades, ara = new Date()) {
  const aemet = avisosAemet(dades);
  const items = [...blocPlans(dades.plans), ...smpPerFenomen(dades.smp),
    ...(aemet.length ? blocAvisosAemet(aemet, ara) : []), ...blocRiera(HISTORIAL_PERILL, ara),
    ...blocEntorn(dades.entorn), blocRiscos(dades.riscos)].filter(Boolean);
  return items.filter((i) => {
    const clau = i.dataset.clau || '';
    if (/^(alfa|tancat):/.test(clau)) return false;
    if (clau.startsWith('smp:')) return !SENSE_CONDUCCIO.has(clau.split(':')[1]);
    if (clau.startsWith('aemet:')) return clau.split(':')[2].split(',').some((t) => !SENSE_CONDUCCIO.has(t));
    if (clau.startsWith('risc:')) return (dades.riscos || []).some((r) => !SENSE_CONDUCCIO.has(r.tipus));
    return true;
  });
}

// El pla de Protecció Civil, la riera i un incendi a prop no canvien els
// veredictes, que surten del temps i del trànsit (ADR 0008), però es diu a la
// mateixa línia, perquè «Bé en tots els mitjans» no es llegeixi com que no hi
// ha cap perill (Juanjo, 07-10-2026; inventari del 18-10-2026). Abans remetia
// a «l'avís de dalt», que ja no hi és.
function noTeEnCompte(dades) {
  const pla = (dades.plans || []).find((p) => p.fase === 'emergència') || (dades.plans || []).find((p) => p.fase === 'alerta');
  const coses = [
    pla && (pla.fase === 'emergència' ? T('l’emergència de Protecció Civil') : T('l’alerta de Protecció Civil')),
    (dades.perill_riera || []).length && T('el perill de la riera de Sant Cugat'),
    ((dades.entorn || {}).incendis || []).length && T('l’incendi proper'),
  ].filter(Boolean);
  if (!coses.length) return null;
  const llista = coses.length === 1 ? coses[0] : `${coses.slice(0, -1).join(', ')}${T(' ni ')}${coses[coses.length - 1]}`;
  return T`El consell de cada mitjà surt del temps previst i del trànsit: no té en compte ${llista}.`;
}

function liniaAvisosConduccio(dades, ara = new Date()) {
  const avisos = avisosConduccio(dades, ara);
  if (!avisos.length) return null;
  const n = avisos.length;
  const pitjor = ['vermell', 'taronja', 'groc', 'prealerta'].find((c) => avisos.some((a) => nivellDe(a) === c)) || 'compte';
  const p = element('p', `avis-item avisos-conduccio ${pitjor}`);
  const a = element('a', null, T('Avisos'));
  a.href = 'perill.html';
  p.append(n === 1 ? T('Hi ha 1 avís de perill que pot afectar la conducció: mira’l a ')
    : T`Hi ha ${n} avisos de perill que poden afectar la conducció: mira’ls a `, a, '.');
  const nota = noTeEnCompte(dades);
  if (nota) p.append(' ', nota);
  return p;
}

function pintaSortida() {
  const dades = DADES;
  const ara = new Date();
  const hores = dades.hores || [];
  const cont = $('sortida');
  if (hores.length < 2) {
    cont.replaceChildren(element('p', 'avis', T('Ara no hi ha previsió hora a hora.')));
    return;
  }
  const i = hores.findIndex((f) => f.hora === $('surto').value);
  const j = hores.findIndex((f) => f.hora === $('torno').value);
  const tram = hores.slice(i, j + 1);
  const trens = dades.trens && dades.trens.linies;
  const transit = dades.transit && dades.transit.incidencies;
  const llista = element('ul', 'mitjans');
  const fora = amagats();
  FITXES.clear();
  for (const [clau, nom, icon] of MITJANS) {
    const v = avalua(clau, tram, trens, i > 0, transit, { hores, ara: dades.ara_casa, pluja_ara: dades.pluja_ara, radar: dades.radar });
    const li = element('li', 'mitja ' + v.nivell);
    li.dataset.mitja = clau;
    const cap = element('p', 'mitja-cap');
    // El títol obre la fitxa en gran (ADR 0119).
    const titol = element('button', 'mitja-nom mitja-obre');
    titol.type = 'button';
    titol.title = T('Obre la fitxa sencera');
    titol.setAttribute('aria-haspopup', 'dialog');
    titol.append(icona(icon), TD(nom));
    titol.addEventListener('click', () => obreFitxa(clau));
    const etiqueta = TD(v.etiqueta || TEXT_NIVELL[v.nivell]);
    FITXES.set(clau, { li, nom: TD(nom), icon, nivell: v.nivell, etiqueta });
    cap.append(titol, ' ', element('span', 'mitja-nivell', etiqueta), botoCompartirFitxa(clau, 'compartir-mitja'));
    const plujaViatge = clau === 'moto' || clau === 'bici' ? mullaRodes : mulla;
    const r = roba(clau, tram, v.nivell !== 'be' && [tram[0], tram[tram.length - 1]].some(plujaViatge));
    if (clau === 'public') {
      // Trens i busos, cadascun en el seu apartat (Juanjo, 22-10-2026). El
      // títol ja diu «Trens»: el motiu, sense.
      li.append(cap, element('p', 'seccio apartat', T('Trens')),
        element('p', 'mitja-motiu', v.motius.map((m) => m.replace(/^(Trens|Trenes): /, '')).join(' ')));
      // Les incidències, dins de la fitxa i plegades: no cal anar a cap altre
      // lloc de la pàgina (Juanjo, 09-10-2026).
      if (trens && trens.length) li.append(plec('trens', T('Estat de cada línia'), blocTrens(dades.trens)));
      if (dades.busos) {
        li.append(element('p', 'seccio apartat', T('Busos')), ...liniesBusosSortida(dades.busos, i > 0 ? new Date(hores[i].hora) : ara));
      }
      if (r) li.append(element('p', 'mitja-roba', T`Roba: ${r}`));
    } else {
      li.append(cap, element('p', 'mitja-motiu', v.motius.join(' ')));
      if (r) li.append(element('p', 'mitja-roba', T`Roba: ${r}`));
    }
    if (MITJANS_TRANSIT.includes(clau) && dades.transit) {
      const n = (transit || []).length;
      if (!n) li.append(element('p', 'mitja-roba', T('Trànsit ara: cap incidència a menys de 5\u00a0km.')));
      else {
        li.append(plec(`transit-${clau}`, n === 1 ? T('Trànsit ara: 1 incidència a menys de 5\u00a0km') : T`Trànsit ara: ${n} incidències a menys de 5\u00a0km`,
          blocTransit(dades.transit)));
      }
    }
    if (!fora.has(clau)) llista.append(li);
  }
  const parts = llista.children.length ? [llista]
    : [element('p', 'nota', T('Tria a dalt els mitjans que vols veure.'))];
  const cs = consells(tram, ara);
  if (cs.length) {
    const ul = element('ul', 'consells');
    for (const c of cs) ul.append(element('li', null, c));
    parts.push(ul);
  }
  cont.replaceChildren(...parts);
  // Si hi ha una fitxa oberta en gran, amb les dades noves.
  const oberta = document.querySelector('dialog.vista-mitja');
  if (oberta) obreFitxa(oberta.dataset.mitja);
}

// Plec d'una fitxa (trens, trànsit): a la fitxa, només el títol, que l'obre en
// gran amb tot desplegat (ADR 0119). Abans es desplegava a la graella i la
// fitxa passava a ocupar tota l'amplada; ara hi ha una sola manera de veure-ho.
function plec(clau, titol, peces) {
  const d = element('div', 'mitja-plec');
  d.id = clau;
  const b = element('button', 'mitja-mes', titol);
  b.type = 'button';
  b.setAttribute('aria-haspopup', 'dialog');
  b.insertAdjacentHTML('beforeend', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>');
  b.addEventListener('click', () => obreFitxa(b.closest('[data-mitja]').dataset.mitja, clau));
  const cos = element('div', 'mitja-plec-cos');
  cos.hidden = true;
  cos.append(...peces);
  d.append(b, cos);
  return d;
}

// --- Cada fitxa en gran, amb el seu enllaç (Juanjo, 22-10-2026: «quiero que
// se pueda compartir cada tarjeta. haciendo clic el titulo de la tarjeta se
// abre en un modal con todo desplegado»; ADR 0119). Es fan totes, també les
// dels mitjans amagats, perquè un enllaç compartit les pugui obrir.
const FITXES = new Map();

// L'adreça de la fitxa (sortir.html#moto), amb l'hora de sortir i de tornar si
// no són les de sempre (ara i tres hores després), perquè qui l'obri vegi el
// mateix trajecte.
function urlFitxa(clau) {
  const url = new URL(location.href);
  const hores = DADES.hores;
  const surto = $('surto').value;
  const i = hores.findIndex((f) => f.hora === surto);
  const per = hores[Math.min(Math.max(i, 0) + TORNADA_PER_DEFECTE_H, hores.length - 1)].hora;
  if (i > 0) url.searchParams.set('surto', surto); else url.searchParams.delete('surto');
  if ($('torno').value !== per) url.searchParams.set('torno', $('torno').value); else url.searchParams.delete('torno');
  url.hash = clau;
  return url.href;
}

// Les hores del trajecte, com als selectors.
function horesFitxa() {
  return T`Surto: ${$('surto').selectedOptions[0].textContent} · Torno: ${$('torno').selectedOptions[0].textContent}`;
}

// Es comparteix només l'enllaç, que obre la fitxa, sense el seu text (Juanjo,
// 22-10-2026: «el enlace a la ficha, se abre la ficha. no incluyas la
// descripción … quiero solo el enlace»).
function botoCompartirFitxa(clau, classe) {
  const nom = FITXES.get(clau).nom;
  const b = element('button', classe);
  b.type = 'button';
  b.title = T`Comparteix la fitxa «${nom}»`;
  b.setAttribute('aria-label', b.title);
  b.append(icona('i-share-2'));
  b.addEventListener('click', () => {
    const f = FITXES.get(clau);
    if (f) comparteix(urlFitxa(clau), T`Si surts: ${f.nom}`);
  });
  return b;
}

// La fitxa en gran: a dalt, el mitjà, compartir i la X, com la gràfica; a sota,
// les hores i el consell, i els plecs desplegats. Si ja n'hi ha una d'oberta,
// es canvia el que hi ha a dins.
function obreFitxa(clau, seccio) {
  const f = FITXES.get(clau);
  if (!f) return;
  let dlg = document.querySelector('dialog.vista-mitja');
  const nova = !dlg;
  if (nova) {
    dlg = element('dialog');
    dlg.setAttribute('aria-labelledby', 'vm-titol');
    // Un toc fora de la finestra la tanca, com Esc.
    dlg.addEventListener('click', (e) => {
      if (e.target !== dlg) return;
      const r = dlg.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dlg.close();
    });
    dlg.addEventListener('close', () => {
      dlg.remove();
      if (location.hash) history.replaceState(null, '', location.pathname + location.search);
    });
    document.body.append(dlg);
  }
  dlg.className = `vista-mitja ${f.nivell}`;
  dlg.dataset.mitja = clau;
  const cap = element('div', 'vg-cap');
  const titol = element('h2', 'mitja-nom');
  titol.id = 'vm-titol';
  titol.append(icona(f.icon), f.nom);
  // Tancar: la X de sempre, a dalt a la dreta (icona «x» de Lucide).
  const tanca = element('button', 'boto-icona');
  tanca.type = 'button';
  tanca.title = T('Tanca');
  tanca.setAttribute('aria-label', T('Tanca'));
  tanca.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  tanca.addEventListener('click', () => dlg.close());
  const accions = element('div', 'vg-accions');
  accions.append(botoCompartirFitxa(clau, 'boto-icona'), tanca);
  cap.append(titol, accions);
  const estat = element('p', 'mitja-cap vm-estat');
  estat.append(element('span', 'vm-hores', horesFitxa()), element('span', 'mitja-nivell', f.etiqueta));
  // El contingut de la fitxa, sense el títol, i els plecs oberts, amb el seu
  // títol a sobre. Sense els id, que ja són a la pàgina.
  const cos = [...f.li.cloneNode(true).children].filter((c) => !c.classList.contains('mitja-cap'));
  for (const el of cos) {
    for (const p of [el, ...el.querySelectorAll('.mitja-plec')].filter((x) => x.classList.contains('mitja-plec'))) {
      const boto = p.querySelector(':scope > .mitja-mes');
      p.dataset.plec = p.id;
      p.removeAttribute('id');
      p.querySelector(':scope > .mitja-plec-cos').hidden = false;
      boto.replaceWith(element('h3', null, boto.textContent));
    }
    for (const x of el.querySelectorAll('[id]')) x.removeAttribute('id');
  }
  dlg.replaceChildren(cap, estat, ...cos);
  if (nova) {
    dlg.showModal();
    tanca.focus();
  }
  if (location.hash !== `#${clau}`) history.replaceState(null, '', `${location.pathname}${location.search}#${clau}`);
  const desti = seccio && dlg.querySelector(`[data-plec="${CSS.escape(seccio)}"]`);
  if (desti) {
    desti.scrollIntoView({ block: 'start' });
    assenyala(desti);
  }
}

// Les franges que encara no han acabat: la primera és «Ara». Sense això, amb
// dades endarrerides (menys de 2 hores) «Ara» podia ser una hora ja passada
// (auditoria del 08-10-2026).
// «Si surts» fa servir el temps i, a més, l'índex UV (la roba), els trens i el trànsit.
const FONTS_SORTIR = [...FONTS_TEMPS, 'índex UV', 'trens', 'trànsit'];

function horesVigents(hores, ara) {
  return (hores || []).filter((f) => new Date(f.fins) > ara);
}

// La línia dels avisos que poden afectar la conducció; es torna a pintar quan
// arriba l'historial de «Perill», per la riera (ADR 0076).
function repintaAvisos() {
  if (!DADES || dadesVelles(DADES)) return;
  $('avisos').querySelector('.avisos-conduccio')?.remove();
  const linia = liniaAvisosConduccio(DADES);
  if (linia) $('avisos').prepend(linia);
}

function pinta(dades) {
  dades = { ...dades, hores: horesVigents(dades.hores, new Date()) };
  DADES = dades;
  llindarsPluja = dades.sortir_llindars || LLINDARS_PLUJA_INICI;
  // A «Com es decideix», els llindars d'ara, que s'aprenen (ADR 0069).
  for (const banda of ['curt', 'llarg']) {
    for (const k of ['pluja', 'risc']) {
      const el = $(`ll-${banda}-${k}`);
      const v = ((llindarsPluja || {})[banda] || LLINDARS_PLUJA_INICI[banda])[k];
      if (el && v != null) el.textContent = String(Math.round(v * 100));
    }
  }
  // Dades de fa massa: només l'avís i on mirar (ADR 0031).
  const velles = dadesVelles(dades);
  for (const id of ['hores', 'plec-triats']) $(id).hidden = velles;
  const explica = document.querySelector('.explica-triats');
  if (velles) {
    if (explica) explica.hidden = true;
    $('avisos').replaceChildren();
    $('sortida').replaceChildren(blocDadesVelles(dades));
    pintaHorari(dades, FONTS_SORTIR);
    posaVersio(dades.versio);
    return;
  }
  if (explica) explica.hidden = explicat() || amagats().size > 0;
  $('avisos').replaceChildren();
  repintaAvisos();
  if (dades.hores && dades.hores.length >= 2) pintaSelectors(dades.hores, new Date());
  pintaSortida();
  obreDelEnllac();
  pintaHorari(dades, FONTS_SORTIR);
  posaVersio(dades.versio);
}

// L'enllaç d'una fitxa (sortir.html#moto) l'obre en gran; el d'un plec (els
// avisos dels trens porten a «sortir.html#trens»), la seva fitxa, amb el plec
// destacat. Només la primera vegada que es pinta, i quan canvia l'adreça.
let enllacFet = false;
function obreDelEnllac() {
  if (enllacFet) return;
  enllacFet = true;
  vesAlEnllac(location.hash.slice(1));
}

function vesAlEnllac(id) {
  if (!id) return;
  if (FITXES.has(id)) {
    obreFitxa(id);
    return;
  }
  for (const [clau, f] of FITXES) {
    if (f.li.querySelector(`#${CSS.escape(id)}`)) {
      obreFitxa(clau, id);
      return;
    }
  }
}
addEventListener('hashchange', () => vesAlEnllac(location.hash.slice(1)));

pintaTriats();
$('surto').addEventListener('change', () => {
  pintaSelectors(DADES.hores, new Date());
  pintaSortida();
});
$('torno').addEventListener('change', pintaSortida);
$('hores').addEventListener('submit', (e) => e.preventDefault());

carrega(FITXER_DADES, pinta, () => {
  $('sortida').replaceChildren(element('p', 'avis', T('No s’ha pogut carregar la previsió. Torna-ho a provar d’aquí a una estona.')));
});
