// WJ117 — État sélectionné des cartes-boutons (bug cascade layers).
// Les groupes de cartes SURVIVANTS du parcours devis (.mt-mode/.mt-tension/
// .mt-activity/.mt-water-source/.mt-water-unit/.mt-pro-unit/.mt-equipes/
// .mt-commercial-cat/.mt-ombrage — type de toit, irrigation et groupe
// électrogène ont quitté le tunnel, coupe fondateur 18/08)
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
    // règles dans @layer, l'état sélectionné redevient invisible. On retire
    // les commentaires d'abord (le mot @layer apparaît dans le commentaire
    // explicatif de la règle WJ117 elle-même).
    const sansCommentaires = css.replace(/\/\*[\s\S]*?\*\//g, '');
    expect(sansCommentaires).not.toContain('@layer');
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

  it('syncModeCards / wireCardGroup présents (tous les groupes SURVIVANTS couverts)', () => {
    expect(src).toContain('function syncModeCards()');
    expect(src).toContain('function wireCardGroup(');
    for (const group of [
      "wireCardGroup('.mt-pro-unit'",
      "wireCardGroup('.mt-tension'",
      "wireCardGroup('.mt-activity'",
      "wireCardGroup('.mt-water-source'",
      "wireCardGroup('.mt-water-unit'",
      "wireCardGroup('.mt-equipes'",
      "wireCardGroup('.mt-commercial-cat'",
    ]) {
      expect(src).toContain(group);
    }
    // Coupe fondateur 18/08 — ces deux groupes ont quitté le tunnel avec leurs
    // questions : ils ne nourrissaient aucune estimation.
    expect(src).not.toContain("wireCardGroup('.mt-irrigation'");
    expect(src).not.toContain("wireCardGroup('.mt-generator'");
    expect(src).not.toContain('function syncRoofCards()');
  });

  it('le HTML statique porte aria-pressed sur les cartes mode (état initial annoncé aux lecteurs d\'écran)', () => {
    expect(src).toMatch(/data-mode=\{m\.id\}\s+aria-pressed="false"/);
    // Les cartes « type de toit » (data-roof) sont retirées du tunnel (coupe
    // fondateur 18/08) ; l'ombrage reprend le même patron aria-pressed.
    expect(src).not.toMatch(/data-roof=/);
    expect(src).toMatch(/class="mt-ombrage[^"]*"[^>]*aria-pressed="false"/);
  });
});
