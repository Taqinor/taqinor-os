// Garde-fous de la PRÉVISUALISATION privée « estimateur piloté par la facture —
// cerveau V2 + W1 » (/preview/toiture-3d-pro-5) : route privée (noindex, hors
// sitemap), 3D/cerveau chargés paresseusement (jamais sur une page publique),
// nouveaux groupes d'options (azimut, marge), per-config PVGIS, et tout l'existant
// (pro-3, pro-4 + les previews historiques, formulaire live) strictement intact.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('pro-5 — route privée, jamais indexée', () => {
  it('la page /preview/toiture-3d-pro-5 est noindex', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-5.astro');
    expect(src).toContain('noindex={true}');
  });

  it('vit dans le sous-dossier /preview (pas de page top-level)', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture-3d-pro-5.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-5.astro', import.meta.url)))).toBe(false);
  });

  it('le filtre sitemap exclut /preview/ (donc cette page aussi)', () => {
    const config = read('../astro.config.mjs');
    const filterLine = config.split('\n').find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).toContain('preview');
  });
});

describe('pro-5 — 3D + cerveau chargés paresseusement', () => {
  it('la page importe le script via import() dynamique, jamais en statique', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-5.astro');
    expect(src).toContain("import('../../scripts/roof-tool-pro5.ts')");
    // Aucun import statique de Three.js / MapLibre dans la PAGE (réservé au script).
    expect(src).not.toContain("from 'three'");
    expect(src).not.toContain("from 'maplibre-gl'");
  });

  it('le script lourd reste hors de toute page publique', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de roof-tool-pro5`).not.toContain('roof-tool-pro5');
      expect(src, `${p}: pas de cerveau estimateur`).not.toContain('estimatorBrain');
    }
  });
});

describe('pro-5 — le flux lead live reste intact (pré-remplissage seulement)', () => {
  it('la page utilise le formulaire enrichi (preview), pas le formulaire live', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-5.astro');
    expect(src).toContain('DiagnosticFormEnriched');
  });

  it('le script ne poste aucun lead — il ne fait que pré-remplir les champs', () => {
    const script = read('../src/scripts/roof-tool-pro5.ts');
    expect(script).not.toContain('/api/preview-lead');
    expect(script).not.toContain('/api/simulate');
    // Il lit le productible via la route additive, jamais le lead.
    expect(script).toContain('/api/roof-yield');
  });
});

describe('pro-5 — nouveaux groupes d’options (azimut + marge)', () => {
  it('la page expose un groupe « Azimut » (plein sud / aligné toit)', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-5.astro');
    expect(src).toContain('data-azimuth="south"');
    expect(src).toContain('data-azimuth="aligned"');
  });

  it('la page expose un groupe « Marge de rive » (garder / pleine rive)', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-5.astro');
    expect(src).toContain('data-margin="keep"');
    expect(src).toContain('data-margin="remove"');
  });

  it('le script consomme l’API du cerveau (azimut + marge + badges)', () => {
    const script = read('../src/scripts/roof-tool-pro5.ts');
    expect(script).toContain('roofAlignedAzimuthDeg');
    expect(script).toContain('PERIMETER_SETBACK_M');
    expect(script).toContain('recommendedOptions');
    expect(script).toContain('setbackM');
  });

  it('la page renvoie vers les baselines pro-3 ET pro-4 dans la liste de comparaison', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-5.astro');
    expect(src).toContain('/preview/toiture-3d-pro-3');
    expect(src).toContain('/preview/toiture-3d-pro-4');
  });
});

describe('pro-5 — l’existant est strictement préservé', () => {
  it('les baselines pro-3 et pro-4 gardent leur page et leur script dédiés', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-3.astro')).toContain("import('../../scripts/roof-tool-pro3.ts')");
    expect(read('../src/pages/preview/toiture-3d-pro-4.astro')).toContain("import('../../scripts/roof-tool-pro4.ts')");
    expect(existsSync(fileURLToPath(new URL('../src/scripts/roof-tool-pro3.ts', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/scripts/roof-tool-pro4.ts', import.meta.url)))).toBe(true);
  });

  it('les previews historiques gardent leur script dédié', () => {
    expect(read('../src/pages/preview/toiture.astro')).toContain('roof-tool.ts');
    expect(read('../src/pages/preview/toiture-3d.astro')).toContain('roof-tool-3d.ts');
    expect(read('../src/pages/preview/toiture-3d-pro.astro')).toContain('roof-tool-pro.ts');
    expect(read('../src/pages/preview/toiture-3d-pro-2.astro')).toContain('roof-tool-pro2.ts');
  });

  it('la route /api/roof-yield ne touche aucune plomberie de lead', () => {
    const ry = read('../src/pages/api/roof-yield.ts');
    for (const forbidden of ['validateLead', 'forwardLead', 'fireCapi', 'buildLeadRecord', 'cleanEnrichment', 'LEAD_WEBHOOK', 'CAPI', "from '../../lib/lead'"]) {
      expect(ry, `roof-yield ne doit pas connaître ${forbidden}`).not.toContain(forbidden);
    }
  });
});
