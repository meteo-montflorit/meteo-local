// SPDX-License-Identifier: AGPL-3.0-or-later
// Service worker perquè la web es pugui instal·lar com a aplicació (ADR 0015).
// Primer la xarxa: amb connexió es veu sempre la versió publicada. Sense
// connexió, les pàgines i els estils guardats. Les dades (.json) no es guarden
// mai: una previsió vella no s'ha de mostrar com si fos d'ara.
const MAGATZEM = 'meteo-local';
const PECES = ['casa.html', 'sortir.html', 'perill.html', 'riera.html', 'consultes.html', 'avisos.html', 'fonts.html', 'fiabilitat.html', 'privacitat.html', 'estil.css', 'comu.js', 'grafica.js', 'casa.js', 'sortir.js', 'perill.js', 'riera.js', 'consultes.js', 'avisos.js', 'fiabilitat.js',
  'manifest.webmanifest', 'icones/icona-192.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(MAGATZEM).then((c) => c.addAll(PECES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.endsWith('.json')) return;
  // Sempre es pregunta al servidor si hi ha versió nova (no-cache: si no ha
  // canviat, respon «sense canvis» i no es torna a baixar). Sense això, la
  // memòria del navegador (GitHub Pages hi deixa 10 minuts) servia el
  // programa d'abans just després de publicar: el 11-10-2026, la casella
  // nova dels talls de llum no sortia a «Avisos» (ADR 0015).
  e.respondWith(
    fetch(e.request, { cache: 'no-cache' })
      .then((resposta) => {
        if (resposta.ok) {
          const copia = resposta.clone();
          caches.open(MAGATZEM).then((c) => c.put(e.request, copia));
        }
        return resposta;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true })),
  );
});

// Els avisos al navegador (ADR 0048): bot/push.py envia {title, body, url,
// tag, expira, dia}; tocar la notificació obre la pàgina de l'avís (la previsió
// de demà, a «Consultes», fitxa «Demà»).
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data.json(); } catch (_) { d = { title: e.data ? e.data.text() : '' }; }
  // Un avís que arriba quan ja ha caducat (el mòbil apagat una estona) no es
  // mostra: push.py hi posa «expira» (auditoria del 09-10-2026).
  if (d.expira && Date.now() > Date.parse(d.expira)) return;
  e.waitUntil(Promise.all([
    self.registration.showNotification(d.title || 'Temps a Montflorit', {
      body: d.body || '',
      icon: 'icones/icona-192.png',
      // La gràfica del resum (ADR 0098): Chrome i la app d'Android la mostren
      // en desplegar la notificació; Firefox i Safari, no, i surt el text sol.
      image: d.image,
      tag: d.tag,
      data: { url: new URL(d.url || './', self.registration.scope).href, dia: d.dia },
    }),
    // Si la web és oberta, que es posi al dia ara mateix: l'avís ha de sortir
    // a la pàgina alhora que la notificació (Juanjo, 12-10-2026; ADR 0048).
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((finestres) => finestres.forEach((f) => f.postMessage({ tipus: 'avis' }))),
  ]));
});

// El dia d'un moment a Madrid, «AAAA-MM-DD», sigui quina sigui la zona del
// dispositiu (ADR 0128): el «dia» de l'avís és el de Madrid. El service
// worker no carrega comu.js: el mateix compte que comu.diaLocal.
const DIA_MADRID = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Madrid', year: 'numeric', month: '2-digit', day: '2-digit' });
function diaLocal(t) {
  const v = {};
  for (const { type, value } of DIA_MADRID.formatToParts(t)) v[type] = value;
  return `${v.year}-${v.month}-${v.day}`;
}

// On porta una notificació en tocar-la: la previsió de demà es toca de
// vegades passada la mitjanit, quan «Demà» ja seria demà passat; si el dia
// de què parla ja ha arribat, s'obre «Avui».
function destiAvis(url, dia, ara = new Date()) {
  const u = new URL(url);
  if (dia && u.hash === '#dema' && dia <= diaLocal(ara)) u.hash = '#avui';
  return u.href;
}

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const d = e.notification.data || {};
  const url = destiAvis(d.url || self.registration.scope, d.dia);
  const sensePunt = (u) => u.split('#')[0];
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((finestres) => {
    // Si la web ja és oberta (millor a la mateixa pàgina), s'hi porta l'avís
    // en lloc d'obrir-ne una altra finestra; si no es pot, se n'obre una.
    const oberta = finestres.find((f) => sensePunt(f.url) === sensePunt(url))
      || finestres.find((f) => f.url.startsWith(self.registration.scope));
    if (!oberta) return self.clients.openWindow(url);
    if (oberta.url === url) return oberta.focus();
    if (!oberta.navigate) return self.clients.openWindow(url);
    // Primer s'hi va i després es porta al davant: si el navegador no deixa
    // portar-la al davant, la finestra ja és a la pàgina de l'avís.
    return oberta.navigate(url)
      .then((nova) => (nova || oberta).focus().catch(() => {}))
      .catch(() => self.clients.openWindow(url));
  }));
});
