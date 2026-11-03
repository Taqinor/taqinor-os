// WAUD59 — fuite de français dans <main> des pages EN/AR construites, avec une base gelée
// (tests/localeLeak.base.json) qui ne peut que rétrécir : chaque lane de localisation la baisse.
// Régénérer la base (après une baisse) : LOCALE_LEAK_WRITE=1 npx vitest run tests/localeLeak.test.ts
// Nouveau fichier car aucun module existant ne lit dist/ entier. W313 (scripts/check-locale-parity.mjs,
// parité de structure) reste une commande à part : npm run check:locale-parity.
import { describe, expect, it } from 'vitest';
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { mainOf, visibleText } from './builtHtmlHelper';

const CLIENT = join(process.cwd(), 'dist/client');
const BASE = join(process.cwd(), 'tests/localeLeak.base.json');

const FRANCAIS = /(?<![\p{L}-])(janvier|février|avril|juin|juillet|août|septembre|octobre|novembre|décembre|ans|à|Garantie)(?![\p{L}-])/gu;

export function occurrences(html: string): number {
  return (visibleText(mainOf(html)).match(FRANCAIS) ?? []).length;
}

function compter(): Record<string, number> {
  const out: Record<string, number> = {};
  for (const loc of ['en', 'ar']) {
    for (const f of readdirSync(join(CLIENT, loc), { recursive: true }) as string[]) {
      const rel = f.replace(/\\/g, '/');
      if (!rel.endsWith('index.html')) continue;
      const n = occurrences(readFileSync(join(CLIENT, loc, f), 'utf-8'));
      if (n > 0) out[`/${loc}/${rel.replace(/index\.html$/, '')}`] = n;
    }
  }
  return out;
}

describe('WAUD59 — fuite de français sur EN/AR', () => {
  it('aucune page ne dépasse la base gelée', () => {
    expect(existsSync(CLIENT), 'lancer « npm run build » avant vitest').toBe(true);
    const actuel = compter();
    if (process.env.LOCALE_LEAK_WRITE) {
      const trie = Object.fromEntries(Object.entries(actuel).sort(([a], [b]) => a.localeCompare(b)));
      writeFileSync(BASE, `${JSON.stringify(trie, null, 1)}\n`);
      return;
    }
    const base = JSON.parse(readFileSync(BASE, 'utf-8')) as Record<string, number>;
    const depassements = Object.entries(actuel)
      .filter(([p, n]) => n > (base[p] ?? 0))
      .map(([p, n]) => `${p} : ${n} > base ${base[p] ?? 0}`);
    expect(depassements).toEqual([]);
  });

  it('test du test : un mois français dans <main> est compté, hors <main> non', () => {
    expect(occurrences('<main><p>installed in avril 2026, Garantie 5 ans</p></main>')).toBe(3);
    expect(occurrences('<header>avril</header><main><p>April 2026</p></main>')).toBe(0);
  });
});
