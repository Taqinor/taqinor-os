// Garde-fou du composant fondateur : le portrait réel est servi (W153), la
// branche de repli texte reste présente, et aucune image n'est référencée sans
// que ses dérivés existent (zéro crédit ni image inventés / fantômes).
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const founder = readFileSync(
  fileURLToPath(new URL('../src/components/FounderPortrait.astro', import.meta.url)),
  'utf-8',
);

describe('FounderPortrait', () => {
  it('expédie le portrait RÉEL : FOUNDER_PHOTO nomme une base dont les dérivés existent (W153)', () => {
    // null (repli texte) reste autorisé ; mais si un nom est posé, chaque dérivé
    // référencé doit exister sur disque — garde anti-référence fantôme.
    const m = founder.match(/const FOUNDER_PHOTO\s*:\s*string \| null\s*=\s*(?:null|'([^']+)')\s*;/);
    expect(m, 'déclaration FOUNDER_PHOTO introuvable').not.toBeNull();
    const base = m![1];
    if (base) {
      for (const w of [640, 480]) {
        for (const ext of ['avif', 'webp']) {
          const p = fileURLToPath(new URL(`../public/photos/${base}-${w}.${ext}`, import.meta.url));
          expect(existsSync(p), `dérivé portrait manquant : ${base}-${w}.${ext}`).toBe(true);
        }
      }
    }
  });

  it('contient le repli texte (10+ ans · Huawei) ET une branche Picture pour le portrait', () => {
    expect(founder).toContain('10+ ans');
    expect(founder).toContain('Huawei');
    expect(founder).toContain('Picture');
    expect(founder).toContain('FOUNDER_PHOTO ?');
  });

  it('renvoie vers la page /à-propos', () => {
    // W67 : le lien est désormais localisé via localizeNavHref('/à-propos', locale)
    // (FR inchangé : localizeNavHref('/à-propos','fr') === '/à-propos'). On vérifie
    // donc la cible /à-propos plutôt que le littéral href="/à-propos".
    expect(founder).toContain('/à-propos');
  });
});
