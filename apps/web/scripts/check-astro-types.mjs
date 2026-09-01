#!/usr/bin/env node
// QJW23 — passe de verification de types sur les scripts des pages/composants
// `.astro` (le TSX genere par le compilateur Astro), via `astro check`
// (paquet `@astrojs/check`, tsconfig partage `tsconfig.check.json`).
//
// `tsc` seul ne sait pas parser l'extension `.astro` (verifie manuellement :
// un glob `.astro` dans un `include` de tsconfig est silencieusement ignore
// par `tsc`, donc l'ajouter a `tsconfig.check.json` ne perturbe pas
// `npm run check`'s premiere etape). Seul `astro check` type-verifie
// reellement le frontmatter + template de ces fichiers.
//
// Ce depot a un fond d'erreurs PRE-EXISTANTES (voir astro-check-frozen-errors.json)
// dans quelques fichiers deja-la, sans lien avec le contrat champs.ts que QJW23
// vise a proteger. Plutot que de les corriger a l'aveugle (hors perimetre d'une
// tache de wiring, et certaines sont des cascades de parsing, pas de vraies
// erreurs de type), on gele un PLAFOND par (fichier, code TypeScript) : ce
// script echoue si un (fichier, code) depasse son plafond connu, ou si un
// (fichier, code) absent du gel apparait avec au moins une occurrence — c'est
// exactement le cas d'une NOUVELLE erreur de type introduite dans un script
// `.astro`, le cas negatif que ce gate doit attraper.
//
// Le plafond ne remonte JAMAIS tout seul : une baisse reelle (bug corrige)
// passe silencieusement (compte <= plafond), une hausse fait rougir. Pour
// resserrer le plafond apres une vraie correction, editez
// astro-check-frozen-errors.json a la main (ce n'est pas automatise —
// resserrer un plafond est une decision, pas une mecanique).

import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { readFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
const webRoot = dirname(dirname(fileURLToPath(import.meta.url))); // apps/web
const baselinePath = join(webRoot, 'astro-check-frozen-errors.json');

// Resout le CLI Astro directement en JS (bin/astro.mjs) plutot que de passer
// par le binstub `.cmd`/shell de node_modules/.bin — portable Windows/Linux,
// et evite toute ambiguite `npx` (paquet deja installe, jamais de fallback
// reseau silencieux dans le gate CI).
const astroPkgPath = require.resolve('astro/package.json', { paths: [webRoot] });
const astroPkg = JSON.parse(readFileSync(astroPkgPath, 'utf8'));
const astroBin = join(dirname(astroPkgPath), astroPkg.bin.astro);

const result = spawnSync(
  process.execPath,
  [astroBin, 'check', '--tsconfig', 'tsconfig.check.json', '--minimumSeverity', 'error'],
  { cwd: webRoot, encoding: 'utf8' }
);

const output = `${result.stdout ?? ''}\n${result.stderr ?? ''}`;
// eslint-disable-next-line no-control-regex
const clean = output.replace(/\x1b\[[0-9;]*m/g, '');
const lines = clean.split(/\r?\n/);

if (!/^Result \(\d+ files\):/m.test(clean)) {
  console.error('astro check n\'a pas produit son resume attendu ("Result (N files):") — panne');
  console.error('d\'infrastructure (astro check a peut-etre plante), pas un simple depassement');
  console.error('de plafond. Sortie complete ci-dessous :\n');
  console.error(output);
  process.exit(1);
}

const lineRe = /^(.+?):(\d+):(\d+) - (error|warning|hint)\s+ts\((\d+)\):/;
const actualCounts = new Map(); // "file::code" -> count
for (const line of lines) {
  const m = line.match(lineRe);
  if (!m) continue;
  const [, file, , , severity, code] = m;
  if (severity !== 'error') continue;
  const key = `${file}::${code}`;
  actualCounts.set(key, (actualCounts.get(key) ?? 0) + 1);
}

const baseline = JSON.parse(readFileSync(baselinePath, 'utf8'));
const ceilings = new Map(); // "file::code" -> ceiling
for (const entry of baseline.entries) {
  ceilings.set(`${entry.file}::${entry.code}`, entry.ceiling);
}

const violations = [];
for (const [key, count] of actualCounts) {
  const ceiling = ceilings.get(key) ?? 0;
  if (count > ceiling) {
    const [file, code] = key.split('::');
    violations.push({ file, code, count, ceiling });
  }
}

const totalActual = [...actualCounts.values()].reduce((a, b) => a + b, 0);
const totalCeiling = [...ceilings.values()].reduce((a, b) => a + b, 0);

if (violations.length > 0) {
  console.error(`astro check (scripts .astro) : ${violations.length} depassement(s) de plafond gele.\n`);
  for (const v of violations.sort((a, b) => a.file.localeCompare(b.file))) {
    console.error(
      `  ${v.file}  ts(${v.code})  ${v.count} erreur(s) trouvee(s) > plafond gele ${v.ceiling}` +
        (v.ceiling === 0 ? '  [NOUVEAU (fichier, code) absent du gel — erreur non gelee]' : '')
    );
  }
  console.error(
    `\nCeci fait rougir volontairement le gate : soit une VRAIE regression de type a corriger,` +
      ` soit un depassement legitime a geler explicitement dans astro-check-frozen-errors.json` +
      ` (avec sa raison) apres verification humaine — jamais en relevant le plafond sans lire l'erreur.\n`
  );
  console.error('Sortie complete de `astro check` :\n');
  console.error(output);
  process.exit(1);
}

console.log(
  `astro check (scripts .astro) : OK — ${totalActual} erreur(s) gelee(s) connue(s) (plafond total ${totalCeiling}), 0 depassement.`
);
process.exit(0);
