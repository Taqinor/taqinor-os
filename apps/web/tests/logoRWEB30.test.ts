// RWEB30 — Logo.astro porte les couleurs du pack maître « TAQINOR_Logo » (mesurées
// sur backend/django_core/apps/ventes/quote_engine/assets/logo.png : navy #022F53,
// or #FEC811), plus les anciennes #0a1238 / #f7b919.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const src = readFileSync(new URL('../src/components/Logo.astro', import.meta.url), 'utf8');

describe('RWEB30 — couleurs du logo', () => {
  it('utilise navy et or du pack maître', () => {
    expect(src).toContain('#022F53');
    expect(src).toContain('#FEC811');
  });
  it("n'a plus les anciennes déclinaisons", () => {
    expect(src.toLowerCase()).not.toContain('#0a1238');
    expect(src.toLowerCase()).not.toContain('#f7b919');
  });
});
