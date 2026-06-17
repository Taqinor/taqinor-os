// Garde-fous de la PRÉVISUALISATION privée « estimateur — cerveau V5 »
// (/preview/toiture-3d-pro-8) : route privée (noindex, hors sitemap), 3D/cerveau
// chargés paresseusement (jamais sur une page publique), TYPE DE TOIT choisi AVANT
// le tracé, preset de pente 45°, production du toit en pente via PVGIS pose
// « building », et tout l'existant (pro-3..pro-7 + le défaut « building » du proxy,
// formulaire live) strictement intact.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('pro-8 — route privée, jamais indexée', () => {
  it('la page /preview/toiture-3d-pro-8 est noindex', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-8.astro')).toContain('noindex={true}');
  });

  it('vit dans le sous-dossier /preview (pas de page top-level)', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture-3d-pro-8.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-8.astro', import.meta.url)))).toBe(false);
  });
});

describe('pro-8 — 3D + cerveau chargés paresseusement, hors page publique', () => {
  it('la page importe le script via import() dynamique, jamais en statique', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-8.astro');
    expect(src).toContain("import('../../scripts/roof-tool-pro8.ts')");
    expect(src).not.toContain("from 'three'");
    expect(src).not.toContain("from 'maplibre-gl'");
  });

  it('le script lourd reste hors de toute page publique', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'à-propos']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de roof-tool-pro8`).not.toContain('roof-tool-pro8');
      expect(src, `${p}: pas de cerveau estimateur`).not.toContain('estimatorBrain');
    }
  });

  it('le script ne poste aucun lead — il ne fait que pré-remplir les champs', () => {
    const script = read('../src/scripts/roof-tool-pro8.ts');
    expect(script).not.toContain('/api/preview-lead');
    expect(script).not.toContain('/api/simulate');
  });
});

describe('pro-8 — V5 : type de toit d’abord, pente 45°, PVGIS « building »', () => {
  it('le type de toit est choisi AVANT le tracé (étape dédiée, puces data-rooftype)', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-8.astro');
    expect(src).toContain('id="rp8-rooftype-first"');
    // L'étape « type de toit » précède l'étape « tracez le toit » dans le flux.
    const idxRoofType = src.indexOf('rp8-rooftype-first');
    const idxTrace = src.indexOf('Tracez le toit');
    expect(idxRoofType).toBeGreaterThan(0);
    expect(idxRoofType).toBeLessThan(idxTrace);
  });

  it('expose le preset de pente 45° (en plus de 15/22/30)', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-8.astro');
    for (const p of ['data-pitch="15"', 'data-pitch="22"', 'data-pitch="30"', 'data-pitch="45"']) {
      expect(src, p).toContain(p);
    }
  });

  it('le script demande la production pente à PVGIS en pose « building » (V5)', () => {
    const script = read('../src/scripts/roof-tool-pro8.ts');
    expect(script).toContain("from '../lib/estimatorBrainV5'");
    expect(script).toContain('pitchedPlaneLeg(');
    expect(script).toContain("mountingplace: 'building'");
    expect(script).toContain('refinePitchedPvgis');
  });

  it('le moteur V5 compose sur V4 (aspect PVGIS) sans le ré-implémenter', () => {
    const v5 = read('../src/lib/estimatorBrainV5.ts');
    expect(v5).toContain("from './estimatorBrainV4'");
    expect(v5).toContain('PITCH_PRESETS_V5');
  });
});

describe('pro-8 — l’existant est strictement préservé', () => {
  it('les baselines pro-3..pro-7 gardent leur page et leur script dédiés', () => {
    for (const n of [3, 4, 5, 6, 7]) {
      expect(read(`../src/pages/preview/toiture-3d-pro-${n}.astro`)).toContain(`import('../../scripts/roof-tool-pro${n}.ts')`);
      expect(existsSync(fileURLToPath(new URL(`../src/scripts/roof-tool-pro${n}.ts`, import.meta.url)))).toBe(true);
    }
  });

  it('pro-7 reste en V4 (toit plat), non réécrit en V5', () => {
    const pro7 = read('../src/scripts/roof-tool-pro7.ts');
    expect(pro7).toContain("from '../lib/estimatorBrainV4'");
    expect(pro7).not.toContain("from '../lib/estimatorBrainV5'");
  });

  it('le proxy /api/roof-yield garde « building » par défaut ; « free » seulement si demandé', () => {
    const route = read('../src/pages/api/roof-yield.ts');
    expect(route).toContain("body.mountingplace === 'free' ? 'free' : 'building'");
  });

  it('le chemin TOIT PLAT de pro-8 reste l’optimiseur V4 (inchangé)', () => {
    const script = read('../src/scripts/roof-tool-pro8.ts');
    expect(script).toContain('fineGridOptimum(');
    expect(script).toContain("recommend(ring, centroidLat, bill, obstructionRings(), { setbackM: setbackOf(), enableRoofAligned: true })");
  });
});
