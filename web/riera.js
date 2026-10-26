// SPDX-License-Identifier: AGPL-3.0-or-later
// «Riera» (ADR 0107): el que necessita el veí, en aquest ordre: l'avís de la
// riera si n'hi ha (el de «Perill», amb dades reals: punt vermell a la
// pestanya), el que preveuen els models per a les properes hores (una
// previsió, no un avís: punt ambre) i, plegades, les dades d'ara i els
// episodis. Juanjo, 19-10-2026: «limítate a las previsiones y útiles para el
// vecino. Si quieres pon aparte todos estos datos de ahora. En esta página
// deberá aparecer también con punto rojo las alertas de la riera».

const FITXER_DADES = document.documentElement.dataset.dades || 'casa.json';
const FITXER_AVISOS = 'avisos.json';
const FONTS_RIERA = ['previsió', 'estació', 'radar'];
const NOM_MODEL = {
  meteofrance_arome_france_hd: 'AROME HD', meteofrance_arome_france: 'AROME', icon_eu: 'ICON-EU', ecmwf_ifs: 'ECMWF',
};
function h(iso) {
  return `${horaLocal(iso)}`;
}

// --- L'avís de la riera, si n'hi ha: el mateix que a «Perill» -------------------------

function pintaAvis(historial) {
  const sec = $('riera-avis');
  const actius = blocRiera(historial);
  if (!actius.length) {
    sec.replaceChildren();
    return;
  }
  const peces = actius.map((item) => {
    const a = element('a', 'detall', T('vegeu l’avís'));
    a.href = item.dataset.detall;
    item.append(' ', a);
    return item;
  });
  sec.replaceChildren(element('h2', 'seccio', T('Avís')), ...peces);
}

// --- Properes hores: el que preveuen els models ---------------------------------------

function quanPrevisio(p) {
  const f = p.finestra_3h;
  if (!f) return '';
  return !mateixDia(f.ini, new Date())
    ? T`demà entre les ${h(f.ini)} i les ${h(f.fi)} h` : T`entre les ${h(f.ini)} i les ${h(f.fi)} h`;
}

// La nota de «fase de proves» només amb risc: si els models no hi veuen res,
// no hi ha res a matisar (Juanjo, 19-10-2026: «esto solo debe aparecer cuando
// hay algun riesgo si está en verde, no»).
function pintaPrevisio(p) {
  const cos = $('previsio-cos');
  const detall = $('previsio-detall');
  $('previsio-nota').hidden = !(p && p.nivell === 'possible');
  if (!p) {
    cos.replaceChildren(element('p', 'avis', T('Ara no hi ha previsió dels models per a la conca.')));
    detall.replaceChildren();
    return;
  }
  const quan = quanPrevisio(p);
  const linia = element('p', `avis-item riera-previsio ${p.nivell === 'possible' ? 'taronja' : 'be'}`);
  if (p.nivell === 'possible') {
    linia.append(element('strong', null, T('Risc de crescuda possible.')), ' ',
      T`Els models preveuen fins a ${coma(p.mm_3h_max)} mm en 3 hores a la conca ${quan}. L’avís d’atenció es dona a partir de 35 mm mesurats.`);
  } else {
    // Amb 0 mm arreu, la finestra no diu res: sense hores.
    linia.append(element('strong', null, T`Cap senyal de crescuda en les properes ${p.horitzo_h} hores.`), ' ',
      p.mm_3h_max > 0 ? T`Com a molt, ${coma(p.mm_3h_max)} mm en 3 hores segons els models (${quan}).`
        : T('Els models no hi preveuen pluja.'));
  }
  cos.replaceChildren(linia);
  // El detall, plegat amb les dades d'ara.
  const frases = [];
  if (p.per_model) {
    frases.push(T('Previsió de cada model, en 3 hores: ') + Object.entries(p.per_model)
      .map(([m, mm]) => `${NOM_MODEL[m] || m} ${coma(mm)}`).join(' · ') + T` mm (mitjana, ${coma(p.mm_3h_mitjana)}).`);
  }
  if (p.mm_6h_max >= 1) frases.push(T`En 6 hores, fins a ${coma(p.mm_6h_max)} mm.`);
  if (p.xv_24h != null) frases.push(T`A Sant Cugat han caigut ${coma(p.xv_24h)} mm en les últimes 24 hores: el sòl mullat fa pujar la riera abans.`);
  if (p.generat) frases.push(T`Previsió llegida a les ${horaCurta(p.generat)}.`);
  detall.replaceChildren(element('p', 'riera-detalls', frases.join(' ')));
}

// --- Dades d'ara: el que mesura Sant Cugat i el que veu el radar ----------------------

function pintaAra(dades) {
  const r = dades.riera;
  const cos = $('ara-cos');
  const detall = $('ara-detall');
  if (!r) {
    cos.replaceChildren(element('p', 'avis', T('Ara no es pot calcular: l’estació de Sant Cugat (Meteocat) no dona dades recents.')));
    detall.replaceChildren();
    return;
  }
  const v = r.font === 'veines' && r.veines ? r.veines : null;
  const mm3 = v ? v.mm_3h : r.mm_3h;
  const mm6 = v ? v.mm_6h : r.mm_6h;
  const fins = horaCurta(v ? v.fins : r.fins);
  const qui = v ? T`Segons la mediana de ${v.n} estacions particulars de Sant Cugat,` : T('A Sant Cugat (Meteocat)');
  const estat = element('p', `avis-item riera-estat ${COLOR_NIVELL[r.nivell] || 'be'}`);
  const titol = titolRiera(r.nivell);
  estat.append(element('strong', null, titol), ' ',
    T`${qui} han caigut ${coma(mm3)} mm en 3 hores i ${coma(mm6)} en 6 (fins a les ${fins}).`);
  const frases = [];
  if (r.radar_1h != null) {
    frases.push(r.radar_1h >= 1 ? T`El radar hi preveu uns ${coma(r.radar_1h)} mm més fins d’aquí a una hora.`
      : T('El radar no hi veu pluja per a l’hora següent.'));
  }
  if (r.index != null) {
    frases.push(T`Índex: ${coma(r.index)} mm en 3 hores i ${coma(r.index_6h)} en 6 (mesurat més radar); atenció des de 35, perill des de 50 i 60.`);
  }
  if (r.capcalera) frases.push(T`Al Fabra (Collserola), ${coma(r.capcalera.mm_3h)} mm en 3 hores.`);
  if (r.incomplet) frases.push(T('A l’estació li falten mesures: la pluja real pot ser més alta.'));
  cos.replaceChildren(estat);
  // El detall (radar, índex, Fabra), plegat amb el de la previsió (Juanjo,
  // 19-10-2026: «lo que has puesto en verde hazlo visible»; el detall, a part).
  detall.replaceChildren(...(frases.length ? [element('p', 'riera-detalls', frases.join(' '))] : []));
}

// --- Episodis: l'historial de «Perill» -----------------------------------------------

function pintaEpisodis(historial) {
  const cos = $('episodis-cos');
  const eps = (historial || []).filter((e) => e.tipus === 'riera').sort((a, b) => llegeixHora(b.inici) - llegeixHora(a.inici));
  if (!eps.length) {
    cos.replaceChildren(element('p', 'nota', T('Cap episodi amb avís des que la web els apunta (octubre del 2026).')));
    return;
  }
  const ul = element('ul', 'riera-episodis');
  for (const e of eps) {
    const li = element('li', `episodi-linia ${e.nivell === 'perill' ? 'vermell' : 'taronja'}`);
    const d = new Date(e.inici);
    const quan = `${d.toLocaleDateString(IDIOMA.codi === 'es' ? 'es-ES' : 'ca-ES', { day: 'numeric', month: 'long', year: 'numeric', timeZone: ZONA_HORA })}, ${horaCurta(e.inici)}`;
    const nivell = e.nivell === 'perill' ? T('perill de desbordament') : T('atenció');
    li.append(element('strong', null, quan), `: ${nivell}`, e.fi ? T` · acabat a les ${horaCurta(e.fi)}` : T(' · en curs'), ' · ');
    const a = element('a', null, T('vegeu l’avís'));
    a.href = `perill.html#${idFitxa(e)}`;
    li.append(a);
    ul.append(li);
  }
  cos.replaceChildren(ul);
}

// --- La pàgina --------------------------------------------------------------------------

let DADES = null;

function pinta(dades) {
  DADES = dades;
  if (dadesVelles(dades)) {
    $('ara-cos').replaceChildren(blocDadesVelles(dades));
    $('ara-detall').replaceChildren();
    $('previsio-cos').replaceChildren();
    $('previsio-detall').replaceChildren();
    $('previsio-nota').hidden = true;
  } else {
    pintaAra(dades);
    pintaPrevisio(dades.riera_previsio);
  }
  $('avis-dades').hidden = true;
  pintaHorari(dades, FONTS_RIERA);
  posaVersio(dades.versio);
  // Vist fins ara: la pestanya ja no ha de senyalar aquesta previsió ni l'avís (comu.js).
  try { localStorage.setItem(CLAU_RIERA_VIST, new Date().toISOString()); } catch (_) {}
}

carrega(FITXER_DADES, pinta, () => {
  $('avis-dades').textContent = T('No s’han pogut carregar les dades. Torna-ho a provar d’aquí a una estona.');
  $('avis-dades').hidden = false;
});

function llegeixAvisos() {
  llegeixDades(FITXER_AVISOS).then((d) => {
    HISTORIAL_PERILL = d.historial;
    pintaAvis(d.historial);
    pintaEpisodis(d.historial);
  }, () => {
    if ($('episodis-cos').querySelector('.carregant')) {
      $('episodis-cos').replaceChildren(element('p', 'nota', T('No s’han pogut carregar els episodis.')));
    }
  });
}
llegeixAvisos();
setInterval(llegeixAvisos, 5 * 60000);
enArribarUnAvis(llegeixAvisos);
