// SPDX-License-Identifier: AGPL-3.0-or-later
// La revisió del JavaScript de la web (ADR 0112): les regles recomanades
// d'ESLint, que busquen errors (noms sense definir, variables que no es fan
// servir, codi que no s'arriba a executar), no l'estil.
//
// Les pàgines carreguen scripts clàssics que comparteixen l'àmbit global:
// es.js (només en castellà), comu.js i grafica.js defineixen el que fan
// servir els altres. Els noms que declaren a dalt de tot es llegeixen d'ells
// mateixos, perquè la llista no s'hagi de mantenir a mà.
import fs from 'node:fs';
import js from '@eslint/js';
import globals from 'globals';

const COMPARTITS = ['web/comu.js', 'web/grafica.js', 'montflorit/es.js'];

function declarats(fitxer) {
  const noms = {};
  const re = /^(?:async\s+)?(?:const|let|var|function\*?|class)\s+([A-Za-z_$][\w$]*)/gm;
  // «writable»: un «let» compartit el poden canviar els altres scripts.
  for (const m of fs.readFileSync(fitxer, 'utf8').matchAll(re)) noms[m[1]] = 'writable';
  return noms;
}

const compartits = Object.assign({}, ...COMPARTITS.map(declarats));

export default [
  js.configs.recommended,
  {
    files: ['web/**/*.js', 'montflorit/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'script',
      globals: { ...globals.browser, ...compartits },
    },
    rules: {
      // El que declara un script a dalt de tot el fan servir els altres.
      'no-unused-vars': ['error', { vars: 'local', args: 'none', caughtErrors: 'none', ignoreRestSiblings: true }],
      // Un script compartit no pot tornar a declarar el seu propi nom.
      'no-redeclare': ['error', { builtinGlobals: false }],
      // Els espais no separables dels textos («35 mm») són volguts.
      'no-irregular-whitespace': ['error', { skipStrings: true, skipTemplates: true }],
      // Un «catch» buit és volgut quan el navegador no deixa desar (localStorage).
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    // El giny d'Android (ADR 0131): un programa de Node, no de la web.
    files: ['giny.js'],
    languageOptions: { ecmaVersion: 'latest', sourceType: 'commonjs', globals: { ...globals.node } },
  },
  {
    files: ['web/sw.js'],
    languageOptions: { globals: { ...globals.serviceworker } },
  },
];
