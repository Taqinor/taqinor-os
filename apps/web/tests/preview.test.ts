// Garde-fous de la PRÉVISUALISATION privée (diagnostic enrichi + schéma).
// Vérifie que la preview est bien privée ET que le formulaire/les pages live
// restent rigoureusement intacts jusqu'à promotion.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('preview — route privée, jamais indexée', () => {
  it('la page /preview/diagnostic est noindex', () => {
    const src = read('../src/pages/preview/diagnostic.astro');
    expect(src).toContain('noindex={true}');
  });

  it('le filtre sitemap exclut /preview/', () => {
    const config = read('../astro.config.mjs');
    const filterLine = config.split('\n').find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).toContain('preview');
    // Garde-fou de non-régression /v2 /v3 (cohérent avec elevation.test.ts)
    expect(filterLine).not.toContain('v2');
    expect(filterLine).not.toContain('v3');
  });

  it('la preview vit dans un sous-dossier (compte de pages top-level inchangé)', () => {
    // elevation.test.ts impose 9 .astro top-level ; la preview doit rester en sous-dossier.
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/diagnostic.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview.astro', import.meta.url)))).toBe(false);
  });
});

describe('preview — le formulaire LIVE est intact', () => {
  it('DiagnosticForm (live) poste toujours vers /api/simulate, jamais /api/preview-lead', () => {
    const live = read('../src/components/DiagnosticForm.astro');
    expect(live).toContain("fetch('/api/simulate'");
    expect(live).not.toContain('preview-lead');
    // Aucun champ facultatif n'a fui dans le formulaire live
    expect(live).not.toContain('supplyType');
    expect(live).not.toContain('orientation');
    expect(live).not.toContain('roofArea');
  });

  it('aucune page publique ne monte le formulaire enrichi ni le schéma', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de formulaire enrichi`).not.toContain('DiagnosticFormEnriched');
      expect(src, `${p}: pas de schéma (promotion = drop-in séparé)`).not.toContain('SchemaInstallation');
    }
  });

  it("l'endpoint /api/simulate (live) ne connaît pas les champs facultatifs", () => {
    const sim = read('../src/pages/api/simulate.ts');
    expect(sim).not.toContain('enrichment');
    expect(sim).not.toContain('cleanEnrichment');
  });
});

describe('preview — le diagnostic enrichi se branche sur la route privée', () => {
  it('poste vers /api/preview-lead et porte les 3 champs facultatifs', () => {
    const enr = read('../src/components/DiagnosticFormEnriched.astro');
    expect(enr).toContain("fetch('/api/preview-lead'");
    expect(enr).toContain('name="supplyType"');
    expect(enr).toContain('name="roofArea"');
    expect(enr).toContain('name="orientation"');
    // La section facultative est une disclosure native (utilisable sans JS)
    expect(enr).toContain('<details');
    expect(enr).toContain('facultatif');
    // Le bouton de soumission reste hors de toute condition de champ facultatif
    expect(enr).toContain('Recevoir mon étude sur WhatsApp');
  });

  it('inputs facultatifs en saisie libre (jamais de snap/rejet) : step="any"', () => {
    const enr = read('../src/components/DiagnosticFormEnriched.astro');
    expect(enr).toContain('novalidate');
    expect(enr).toMatch(/name="roofArea"[^>]*step="any"/s);
  });

  it("l'endpoint preview n'ajoute l'enrichissement QUE s'il est rempli", () => {
    const ep = read('../src/pages/api/preview-lead.ts');
    expect(ep).toContain('hasEnrichment');
    expect(ep).toContain('cleanEnrichment');
    // CAPI reçoit le record de base (signal publicitaire inchangé)
    expect(ep).toContain('fireCapi(baseRecord');
  });
});

describe('preview — le schéma est sûr (mouvement gated, pas de reflow)', () => {
  it('tout mouvement est sous prefers-reduced-motion: no-preference', () => {
    const svg = read('../src/components/SchemaInstallation.astro');
    expect(svg).toContain('prefers-reduced-motion: no-preference');
    // Les @keyframes n'animent QUE transform/opacity → zéro reflow, zéro CLS.
    const frames = [...svg.matchAll(/@keyframes[^{]+\{([\s\S]*?\}\s*)\}/g)].map((m) => m[1]);
    expect(frames.length).toBeGreaterThan(0);
    for (const body of frames) {
      const props = [...body.matchAll(/([a-z-]+)\s*:/g)].map((m) => m[1]);
      for (const p of props) {
        expect(['transform', 'opacity'], `propriété animée interdite: ${p}`).toContain(p);
      }
    }
  });
});
