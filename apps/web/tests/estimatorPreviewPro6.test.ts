// Garde-fous de la PRÉVISUALISATION privée « estimateur — cerveau V3 »
// (/preview/toiture-3d-pro-6) : route privée (noindex, hors sitemap), 3D/cerveau
// chargés paresseusement (jamais sur une page publique), NOUVEAUX contrôles
// (bouton Optimum, toggle type de toit plat/pente, contrôles pente+face), et tout
// l'existant (pro-3/4/5 + previews historiques, formulaire live) strictement intact.
// Le chemin TOIT PLAT reste celui de pro-5 (même appel recommend()).
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('pro-6 — route privée, jamais indexée', () => {
  it('la page /preview/toiture-3d-pro-6 est noindex', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-6.astro')).toContain('noindex={true}');
  });

  it('vit dans le sous-dossier /preview (pas de page top-level)', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture-3d-pro-6.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-6.astro', import.meta.url)))).toBe(false);
  });

  it('le filtre sitemap exclut /preview/ (donc cette page aussi)', () => {
    const filterLine = read('../astro.config.mjs').split('\n').find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).toContain('preview');
  });
});

describe('pro-6 — 3D + cerveau chargés paresseusement', () => {
  it('la page importe le script via import() dynamique, jamais en statique', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-6.astro');
    expect(src).toContain("import('../../scripts/roof-tool-pro6.ts')");
    expect(src).not.toContain("from 'three'");
    expect(src).not.toContain("from 'maplibre-gl'");
  });

  it('le script lourd reste hors de toute page publique', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de roof-tool-pro6`).not.toContain('roof-tool-pro6');
      expect(src, `${p}: pas de cerveau estimateur`).not.toContain('estimatorBrain');
    }
  });
});

describe('pro-6 — flux lead live intact (pré-remplissage seulement)', () => {
  it('la page utilise le formulaire enrichi (preview), pas le formulaire live', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-6.astro')).toContain('DiagnosticFormEnriched');
  });

  it('le script ne poste aucun lead — il ne fait que pré-remplir les champs', () => {
    const script = read('../src/scripts/roof-tool-pro6.ts');
    expect(script).not.toContain('/api/preview-lead');
    expect(script).not.toContain('/api/simulate');
    expect(script).toContain('/api/roof-yield');
  });
});

describe('pro-6 — V3 : bouton Optimum, type de toit, contrôles pente', () => {
  it('la page expose le bouton Optimum', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-6.astro')).toContain('id="rp6-optimum"');
  });

  it('la page expose le toggle « type de toit » (plat / pente)', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-6.astro');
    expect(src).toContain('data-rooftype="flat"');
    expect(src).toContain('data-rooftype="pitched"');
  });

  it('la page expose les contrôles pente (presets + curseur) et face du pan', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-6.astro');
    expect(src).toContain('data-pitch="22"');
    expect(src).toContain('id="rp6-pitch-range"');
    expect(src).toContain('data-facing="180"');
    // l'inclinaison/azimut imposés par le toit sont affichés en lecture seule
    expect(src).toContain('imposés par la toiture');
  });

  it('le script consomme l’API V3 (recherche pleine, ré-opt, toit en pente)', () => {
    const script = read('../src/scripts/roof-tool-pro6.ts');
    expect(script).toContain("from '../lib/estimatorBrainV3'");
    expect(script).toContain('reoptimize(');
    expect(script).toContain('recommendPitched(');
    expect(script).toContain('applyOptimum');
    expect(script).toContain('setRoofType');
  });
});

describe('pro-6 — le chemin TOIT PLAT reste celui de pro-5 (byte-identique)', () => {
  it('le mode plat appelle le MÊME recommend() que pro-5 (cerveau V2, opt-in aligné)', () => {
    const expected = 'recommend(ring, centroidLat, bill, obstructionRings(), { setbackM: setbackOf(), enableRoofAligned: true })';
    expect(read('../src/scripts/roof-tool-pro5.ts')).toContain(expected);
    expect(read('../src/scripts/roof-tool-pro6.ts')).toContain(expected);
  });

  it('le moteur V2 (estimatorBrainV2.ts) n’est pas modifié par V3 (composition only)', () => {
    // V3 importe V2 ; il ne le ré-implémente pas.
    const v3 = read('../src/lib/estimatorBrainV3.ts');
    expect(v3).toContain("from './estimatorBrainV2'");
    expect(v3).toContain('packConfig');
  });

  it('le rendu 3D toit-plat est inchangé : flush défaut false', () => {
    const script = read('../src/scripts/roof-tool-pro6.ts');
    expect(script).toContain('flush = false');
    expect(script).toContain('if (!flush)');
  });
});

describe('pro-6 — l’existant est strictement préservé', () => {
  it('les baselines pro-3/4/5 gardent leur page et leur script dédiés', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-3.astro')).toContain("import('../../scripts/roof-tool-pro3.ts')");
    expect(read('../src/pages/preview/toiture-3d-pro-4.astro')).toContain("import('../../scripts/roof-tool-pro4.ts')");
    expect(read('../src/pages/preview/toiture-3d-pro-5.astro')).toContain("import('../../scripts/roof-tool-pro5.ts')");
    for (const s of ['roof-tool-pro3.ts', 'roof-tool-pro4.ts', 'roof-tool-pro5.ts']) {
      expect(existsSync(fileURLToPath(new URL(`../src/scripts/${s}`, import.meta.url)))).toBe(true);
    }
  });

  it('la page pro-6 renvoie vers les baselines pro-3, pro-4 ET pro-5', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-6.astro');
    expect(src).toContain('/preview/toiture-3d-pro-3');
    expect(src).toContain('/preview/toiture-3d-pro-4');
    expect(src).toContain('/preview/toiture-3d-pro-5');
  });
});
