// WJ117 — État sélectionné des cartes-boutons (bug cascade layers).
// Les 8 groupes de cartes du parcours devis (.mt-mode/.mt-roof-card/.mt-tension/
// .mt-activity/.mt-water-source/.mt-irrigation/.mt-water-unit/.mt-pro-unit)
// togglent aria-pressed + l'utilitaire Tailwind `border-brass-400`, mais ces
// utilitaires vivent dans un @layer (Tailwind v4) alors que `.cine-card`
// (global.css) est NON layered et pose `border: 1px solid …` par shorthand —
// une règle hors layer gagne toujours sur une règle layered : l'état
// sélectionné était INVISIBLE. Le fix est UNE règle CSS non-layered
// `.cine-card[aria-pressed="true"]` dans global.css (bordure brass 2px
// visible, fond teinté brass, ✓ en coin, label en gras) qui répare les
// 8 groupes × 3 locales d'un coup. Ce test source-level garde :
//   (a) la règle CSS et ses 4 exigences visuelles, HORS de tout @layer ;
//   (b) le toggling aria-pressed dans le JS des 3 locales (FR/EN/AR) —
//       sans lui la règle n'aurait rien à matcher (et les lecteurs d'écran
//       perdraient l'état).
//
// NOTE : le plan demandait des captures Playwright avant/après — apps/web n'a
// pas Playwright (vitest uniquement) ; ce test source-level est le substitut.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const css = read('../src/styles/global.css');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

// Le bloc principal de la règle sélectionnée (jusqu'à sa première '}').
const selectedRule = css.match(/\.cine-card\[aria-pressed="true"\]\s*\{[^}]*\}/)?.[0];
// Le bloc ::after (le ✓ en coin).
const checkRule = css.match(/\.cine-card\[aria-pressed="true"\]::after\s*\{[^}]*\}/)?.[0];

describe('WJ117 — règle CSS .cine-card[aria-pressed="true"] dans global.css', () => {
  it('la règle existe', () => {
    expect(selectedRule).toBeTruthy();
  });

  it('global.css ne contient AUCUN bloc @layer — la règle est donc non-layered et bat les utilitaires Tailwind v4 (le point du fix)', () => {
    // Tout le fichier est hors layer ; si quelqu'un enveloppe un jour ces
    // règles dans @layer, l'état sélectionné redevient invisible.
    expect(css).not.toContain('@layer');
  });

  it('bordure brass : border-color brass-400 + ring inset 1px = 2px visibles sans décalage de layout', () => {
    expect(selectedRule).toContain('border-color: var(--color-brass-400)');
    expect(selectedRule).toContain('inset 0 0 0 1px var(--color-brass-400)');
  });

  it('fond teinté brass ~10 %', () => {
    expect(selectedRule).toContain('background-color: rgb(232 181 74 / 0.10)');
  });

  it('label en gras', () => {
    expect(selectedRule).toContain('font-weight: 700');
  });

  it('✓ en coin via ::after (inset-inline-end : suit le RTL arabe)', () => {
    expect(checkRule).toBeTruthy();
    expect(checkRule).toContain("content: '✓'");
    expect(checkRule).toContain('inset-inline-end');
  });

  it("ne touche pas à outline : le ring clavier :focus-visible global (W209) reste intact", () => {
    expect(selectedRule).not.toContain('outline');
    // La règle globale W209 est toujours là.
    expect(css).toMatch(/button:focus-visible/);
  });
});

describe.each(LOCALES)('WJ117 — toggling aria-pressed dans mon-toit.astro (%s)', (_locale, rel) => {
  const src = read(rel);

  it('le JS toggle aria-pressed sur les cartes (String(on))', () => {
    expect(src).toContain("setAttribute('aria-pressed', String(on))");
  });

  it('syncModeCards / syncRoofCards / wireCardGroup présents (les 8 groupes couverts)', () => {
    expect(src).toContain('function syncModeCards()');
    expect(src).toContain('function syncRoofCards()');
    expect(src).toContain('function wireCardGroup(');
    for (const group of [
      "wireCardGroup('.mt-pro-unit'",
      "wireCardGroup('.mt-tension'",
      "wireCardGroup('.mt-activity'",
      "wireCardGroup('.mt-water-source'",
      "wireCardGroup('.mt-irrigation'",
      "wireCardGroup('.mt-water-unit'",
    ]) {
      expect(src).toContain(group);
    }
  });

  it('le HTML statique porte aria-pressed sur les cartes mode et toit (état initial annoncé aux lecteurs d\'écran)', () => {
    expect(src).toMatch(/data-mode=\{m\.id\}\s+aria-pressed="false"/);
    expect(src).toMatch(/data-roof=\{r\.id\}\s+aria-pressed="false"/);
  });
});
