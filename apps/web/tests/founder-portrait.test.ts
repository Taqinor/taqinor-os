// Garde-fou du composant fondateur : photo-ready, mais repli texte par défaut,
// sans crédit ni image inventés.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const founder = readFileSync(
  fileURLToPath(new URL('../src/components/FounderPortrait.astro', import.meta.url)),
  'utf-8',
);

describe('FounderPortrait', () => {
  it('expédie le repli texte par défaut : FOUNDER_PHOTO vaut null (aucune image inventée)', () => {
    expect(founder).toMatch(/const FOUNDER_PHOTO\s*:\s*string \| null\s*=\s*null\s*;/);
  });

  it('contient le repli texte (10+ ans · Huawei) ET une branche Picture pour le portrait', () => {
    expect(founder).toContain('10+ ans');
    expect(founder).toContain('Huawei');
    expect(founder).toContain('Picture');
    expect(founder).toContain('FOUNDER_PHOTO ?');
  });

  it('renvoie vers la page /à-propos', () => {
    expect(founder).toContain('href="/à-propos"');
  });
});
