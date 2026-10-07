#!/usr/bin/env node
/**
 * Polices auto-hébergées (YBW39) — familles candidates du tour design (YBW42),
 * toutes sous licence SIL Open Font License 1.1 (vérifiée dans le LICENSE de
 * chaque paquet @fontsource-variable/* 5.3.0, champ `license: OFL-1.1`).
 *
 * Deux modes :
 *   node scripts/build-fonts.mjs --depuis <dossier>
 *       <dossier> contient les paquets extraits (`npm pack` puis tar) :
 *       copie le sous-ensemble LATIN variable (axe wght) de chaque famille et
 *       son texte OFL dans public/fonts/ (noms versionnés), puis écrit fonts.css.
 *   node scripts/build-fonts.mjs
 *       régénère seulement src/styles/fonts.css depuis public/fonts/.
 *
 * fonts.css : @font-face (unicode-range latin, font-display: swap) + une face
 * de REPLI MÉTRIQUE par famille (Arial local recalé : size-adjust,
 * ascent/descent/line-gap-override, calculés depuis les tables de la police —
 * scripts/font-metrics.mjs), + les variables --police-texte / --police-titre.
 * Aucun CDN : tout est servi depuis /fonts/.
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { metriques, surcharges } from './font-metrics.mjs';

const RACINE = fileURLToPath(new URL('../', import.meta.url));
const POLICES = join(RACINE, 'public', 'fonts');
const CSS = join(RACINE, 'src', 'styles', 'fonts.css');
export const VERSION = '5.3.0';

/** Familles candidates (YBW42) ; après YBW44, retirer les non retenues. */
export const FAMILLES = [
  { id: 'outfit', nom: 'Outfit', generique: 'sans-serif' },
  { id: 'urbanist', nom: 'Urbanist', generique: 'sans-serif' },
  { id: 'instrument-sans', nom: 'Instrument Sans', generique: 'sans-serif' },
  { id: 'geist', nom: 'Geist', generique: 'sans-serif' },
  { id: 'geist-mono', nom: 'Geist Mono', generique: 'monospace' },
  { id: 'fraunces', nom: 'Fraunces', generique: 'serif' },
  { id: 'plus-jakarta-sans', nom: 'Plus Jakarta Sans', generique: 'sans-serif' },
];

/** Sous-ensemble latin (identique à celui des paquets Fontsource). */
export const PLAGE_LATIN =
  'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';

/** @param {string} id */
export const fichierPolice = (id) => `${id}-latin-wght-${VERSION}.woff2`;
/** @param {string} id */
export const fichierLicence = (id) => `${id}-OFL-${VERSION}.txt`;

/** Contenu de fonts.css, calculé depuis les fichiers de public/fonts/. */
export function cssPolices(dossier = POLICES) {
  const blocs = [
    '/*',
    ' * Polices auto-hébergées (YBW39) — GÉNÉRÉ par scripts/build-fonts.mjs, ne pas éditer.',
    ' * Licence SIL OFL 1.1 : textes dans /fonts/*-OFL-*.txt. Aucun CDN.',
    ' */',
  ];
  for (const f of FAMILLES) {
    const s = surcharges(metriques(readFileSync(join(dossier, fichierPolice(f.id)))));
    blocs.push(
      `@font-face {`,
      `  font-family: '${f.nom}';`,
      `  font-style: normal;`,
      `  font-weight: 100 900;`,
      `  font-display: swap;`,
      `  src: url('/fonts/${fichierPolice(f.id)}') format('woff2');`,
      `  unicode-range: ${PLAGE_LATIN};`,
      `}`,
      `@font-face {`,
      `  font-family: '${f.nom} repli';`,
      `  src: local('Arial'), local('ArialMT'), local('Liberation Sans'), local('Helvetica');`,
      `  size-adjust: ${s.sizeAdjust};`,
      `  ascent-override: ${s.ascentOverride};`,
      `  descent-override: ${s.descentOverride};`,
      `  line-gap-override: ${s.lineGapOverride};`,
      `}`,
    );
  }
  blocs.push(
    '',
    '/* Familles provisoires (direction A recommandée) — figées au tour design (YBW44). */',
    ':root {',
    "  --police-texte: 'Instrument Sans', 'Instrument Sans repli', sans-serif;",
    "  --police-titre: 'Outfit', 'Outfit repli', sans-serif;",
    '}',
    '',
    'body {',
    '  font-family: var(--police-texte);',
    '}',
    '',
    'h1,',
    'h2,',
    'h3 {',
    '  font-family: var(--police-titre);',
    '}',
    '',
  );
  return blocs.join('\n');
}

function principal() {
  const i = process.argv.indexOf('--depuis');
  if (i !== -1) {
    const source = process.argv[i + 1];
    mkdirSync(POLICES, { recursive: true });
    for (const f of FAMILLES) {
      const paquet = join(source, `fontsource-variable-${f.id}-${VERSION}`, 'package');
      const police = join(paquet, 'files', `${f.id}-latin-wght-normal.woff2`);
      const licence = join(paquet, 'LICENSE');
      if (!existsSync(police) || !readFileSync(licence, 'utf-8').includes('SIL OPEN FONT LICENSE')) {
        throw new Error(`${f.nom} : police latine ou licence OFL introuvable dans ${paquet}`);
      }
      copyFileSync(police, join(POLICES, fichierPolice(f.id)));
      copyFileSync(licence, join(POLICES, fichierLicence(f.id)));
    }
  }
  writeFileSync(CSS, cssPolices());
  console.log('src/styles/fonts.css écrit');
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) principal();
