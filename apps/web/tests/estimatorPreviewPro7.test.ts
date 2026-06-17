// Garde-fous de la PRÉVISUALISATION privée « estimateur — cerveau V4 »
// (/preview/toiture-3d-pro-7) : route privée (noindex, hors sitemap), 3D/cerveau
// chargés paresseusement (jamais sur une page publique), PVGIS comme source de
// vérité (optimum de grille fine au GPS exact, repli table), la ligne « Optimum
// calculé » à part, et tout l'existant (pro-3/4/5/6 + previews historiques,
// formulaire live) strictement intact.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('pro-7 — route privée, jamais indexée', () => {
  it('la page /preview/toiture-3d-pro-7 est noindex', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-7.astro')).toContain('noindex={true}');
  });

  it('vit dans le sous-dossier /preview (pas de page top-level)', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture-3d-pro-7.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-7.astro', import.meta.url)))).toBe(false);
  });
});

describe('pro-7 — 3D + cerveau chargés paresseusement, hors page publique', () => {
  it('la page importe le script via import() dynamique, jamais en statique', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-7.astro');
    expect(src).toContain("import('../../scripts/roof-tool-pro7.ts')");
    expect(src).not.toContain("from 'three'");
    expect(src).not.toContain("from 'maplibre-gl'");
  });

  it('le script lourd reste hors de toute page publique', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33', 'à-propos']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de roof-tool-pro7`).not.toContain('roof-tool-pro7');
      expect(src, `${p}: pas de cerveau estimateur`).not.toContain('estimatorBrain');
    }
  });
});

describe('pro-7 — flux lead live intact (pré-remplissage seulement)', () => {
  it('la page utilise le formulaire enrichi (preview), pas le formulaire live', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-7.astro')).toContain('DiagnosticFormEnriched');
  });

  it('le script ne poste aucun lead — il ne fait que pré-remplir les champs', () => {
    const script = read('../src/scripts/roof-tool-pro7.ts');
    expect(script).not.toContain('/api/preview-lead');
    expect(script).not.toContain('/api/simulate');
    expect(script).toContain('/api/roof-yield');
  });
});

describe('pro-7 — V4 : PVGIS source de vérité + optimum de grille fine', () => {
  it('le script consomme le moteur V4 (fineGridOptimum, candidats PVGIS)', () => {
    const script = read('../src/scripts/roof-tool-pro7.ts');
    expect(script).toContain("from '../lib/estimatorBrainV4'");
    expect(script).toContain('fineGridOptimum(');
    expect(script).toContain('pvgisCandidatePairs(');
  });

  it('le rendement spécifique PVGIS est demandé en pose « free » (toit plat racké)', () => {
    const script = read('../src/scripts/roof-tool-pro7.ts');
    expect(script).toContain("mountingplace: 'free'");
  });

  it('la page expose la ligne « Optimum calculé » badgée et sa source', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-7.astro');
    expect(src).toContain('id="rp7-optimum-card"');
    expect(src).toContain('Optimum calculé');
    expect(src).toContain('rp7-reco-badge'); // badge « Recommandé »
    expect(src).toContain('id="rp7-optimum-source"');
  });

  it('le moteur V4 compose sur V2/V3 sans les ré-implémenter', () => {
    const v4 = read('../src/lib/estimatorBrainV4.ts');
    expect(v4).toContain("from './estimatorBrainV2'");
    expect(v4).toContain('packConfig');
    expect(v4).toContain("from './estimatorBrainV3'");
  });
});

describe('pro-7 — l’existant est strictement préservé', () => {
  it('les baselines pro-3/4/5/6 gardent leur page et leur script dédiés', () => {
    for (const n of [3, 4, 5, 6]) {
      expect(read(`../src/pages/preview/toiture-3d-pro-${n}.astro`)).toContain(`import('../../scripts/roof-tool-pro${n}.ts')`);
      expect(existsSync(fileURLToPath(new URL(`../src/scripts/roof-tool-pro${n}.ts`, import.meta.url)))).toBe(true);
    }
  });

  it('pro-6 reste branché sur V3 (non ré-écrit en V4)', () => {
    const pro6 = read('../src/scripts/roof-tool-pro6.ts');
    expect(pro6).toContain("from '../lib/estimatorBrainV3'");
    expect(pro6).not.toContain("from '../lib/estimatorBrainV4'");
  });

  it('la page pro-7 renvoie vers les baselines pro-5 ET pro-6', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-7.astro');
    expect(src).toContain('/preview/toiture-3d-pro-5');
    expect(src).toContain('/preview/toiture-3d-pro-6');
  });

  it('le proxy /api/roof-yield garde mountingplace « building » par défaut (pro-3/4/5/6 inchangés)', () => {
    const route = read('../src/pages/api/roof-yield.ts');
    expect(route).toContain("body.mountingplace === 'free' ? 'free' : 'building'");
  });
});
