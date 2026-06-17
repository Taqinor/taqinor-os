// Garde-fous de la PRÉVISUALISATION privée « estimateur — cerveau V7 / W34 »
// (/preview/toiture-3d-pro-10) : route privée (noindex, hors sitemap), 3D/cerveau
// chargés paresseusement (jamais sur une page publique), et l'OPTIMISEUR CONTRAINT
// VIVANT pour toit plat :
//   - chaque option est un AXE qui se VERROUILLE puis re-résout en direct via solveLive
//     (V7), production PVGIS au GPS exact (repli table « estimé ») ;
//   - les verrous s'accumulent ; « Réinitialiser » les relâche ;
//   - chaque groupe affiche sa valeur « Recommandé » (axe libéré, autres verrous tenus).
// Tout l'existant (pro-3..pro-9 + le formulaire live) reste strictement intact, et le
// toit en pente garde le modèle affleurant de pro-9 (W35 l'optimisera).
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('pro-10 — route privée, jamais indexée', () => {
  it('la page /preview/toiture-3d-pro-10 est noindex', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-10.astro')).toContain('noindex={true}');
  });

  it('vit dans le sous-dossier /preview (pas de page top-level)', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture-3d-pro-10.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-10.astro', import.meta.url)))).toBe(false);
  });
});

describe('pro-10 — 3D + cerveau chargés paresseusement, hors page publique', () => {
  it('la page importe SON script pro-10 via import() dynamique, jamais en statique', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-10.astro');
    expect(src).toContain("import('../../scripts/roof-tool-pro10.ts')");
    expect(src).not.toContain("roof-tool-pro9.ts"); // ne ré-utilise PAS le script pro-9
    expect(src).not.toContain("from 'three'");
    expect(src).not.toContain("from 'maplibre-gl'");
  });

  it('le script lourd reste hors de toute page publique', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'à-propos']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de roof-tool-pro10`).not.toContain('roof-tool-pro10');
      expect(src, `${p}: pas de cerveau estimateur`).not.toContain('estimatorBrain');
    }
  });

  it('le script ne poste aucun lead — il ne fait que pré-remplir les champs', () => {
    const script = read('../src/scripts/roof-tool-pro10.ts');
    expect(script).not.toContain('/api/preview-lead');
    expect(script).not.toContain('/api/simulate');
    expect(script).toContain('prefillLead('); // pré-remplissage seulement
  });
});

describe('pro-10 — W34 : optimiseur contraint VIVANT (toit plat) via cerveau V7', () => {
  const script = read('../src/scripts/roof-tool-pro10.ts');

  it('le script branche le cerveau V7 (solveLive) et re-résout en direct', () => {
    expect(script).toContain("from '../lib/estimatorBrainV7'");
    expect(script).toContain('solveLive(');
    expect(script).toContain('function liveResolveFlat(');
    // renderSelection est désormais l'alias du solveur vivant
    expect(script).toContain('function renderSelection()');
  });

  it('la production vient de PVGIS au GPS exact (cache partagé), repli table « estimé »', () => {
    // le yieldFn injecté lit le cache PVGIS (kWh/kWc/an) — jamais un facteur générique
    expect(script).toContain('v4YieldCache.get(v4Key(');
    expect(script).toContain('solveLive(ring, centroidLat, bill, obstructionRings(), locks, { yieldFn })');
    // après l'arrivée PVGIS (buildMatrix), le solveur vivant se re-résout
    expect(script).toContain("if (roofType === 'flat') liveResolveFlat();");
  });

  it('les verrous s\'ACCUMULENT (pinned) et « Réinitialiser » les relâche', () => {
    expect(script).toContain('function buildFlatLocks(');
    expect(script).toContain('function resetFlatLocks(');
    expect(script).toContain('pinned.clear()');
    // le bouton Optimum est repensé en Réinitialiser (plat) / re-dimensionnement (pente)
    expect(script).toContain('else resetFlatLocks();');
  });

  it('chaque groupe affiche la valeur « Recommandé » (axe libéré, autres verrous tenus)', () => {
    expect(script).toContain('function updateLiveBadges(');
    expect(script).toContain('res.recommended');
    expect(script).toContain('rp9-reco-badge');
  });

  it('le plafond « besoin » est respecté : posé = min(besoin, ce qui tient)', () => {
    // garanti par le moteur V7 ; ici on vérifie que la cible besoin entre dans les verrous
    expect(script).toContain('locks.need = neededPanels');
  });

  it('la page expose le bouton « Réinitialiser » et garde la matrice complète', () => {
    const page = read('../src/pages/preview/toiture-3d-pro-10.astro');
    expect(page).toContain('id="rp9-optimum"');
    expect(page).toContain('Réinitialiser');
    expect(page).toContain('id="rp9-matrix-filter"'); // matrice V6 conservée
    expect(page).toContain('data-rp9-sort="annualKwh"');
  });
});

describe('pro-10 — le toit en pente garde le modèle pro-9 (W35 l\'optimisera)', () => {
  const script = read('../src/scripts/roof-tool-pro10.ts');
  it('le mode pente reste la pose affleurante coplanaire (géométrie V6)', () => {
    expect(script).toContain('pitchedDeckZ(');
    expect(script).toContain('flushPanelCenterAt(');
    expect(script).toContain('PITCHED_FLUSH_STANDOFF_M');
  });
  it('le type de toit est toujours choisi AVANT le tracé (preset 45° conservé)', () => {
    const page = read('../src/pages/preview/toiture-3d-pro-10.astro');
    expect(page).toContain('id="rp9-rooftype-first"');
    for (const p of ['data-pitch="15"', 'data-pitch="22"', 'data-pitch="30"', 'data-pitch="45"']) {
      expect(page, p).toContain(p);
    }
  });
});

describe('pro-10 — l\'existant est strictement préservé', () => {
  it('les baselines pro-3..pro-9 gardent leur page et leur script dédiés', () => {
    for (const n of [3, 4, 5, 6, 7, 8, 9]) {
      expect(read(`../src/pages/preview/toiture-3d-pro-${n}.astro`)).toContain(`import('../../scripts/roof-tool-pro${n}.ts')`);
      expect(existsSync(fileURLToPath(new URL(`../src/scripts/roof-tool-pro${n}.ts`, import.meta.url)))).toBe(true);
    }
  });

  it('pro-9 reste en V6 et N\'utilise PAS le cerveau V7', () => {
    const pro9 = read('../src/scripts/roof-tool-pro9.ts');
    expect(pro9).toContain("from '../lib/estimatorBrainV6'");
    expect(pro9).not.toContain("from '../lib/estimatorBrainV7'");
    expect(pro9).not.toContain('solveLive(');
  });

  it('le moteur V7 compose sur V2 + V6 sans les ré-implémenter (pas d\'édition)', () => {
    const v7 = read('../src/lib/estimatorBrainV7.ts');
    expect(v7).toContain("from './estimatorBrainV2'");
    expect(v7).toContain("from './estimatorBrainV6'");
    expect(v7).toContain('export function solveLive');
  });

  it('le proxy /api/roof-yield garde « building » par défaut ; « free » seulement si demandé', () => {
    const route = read('../src/pages/api/roof-yield.ts');
    expect(route).toContain("body.mountingplace === 'free' ? 'free' : 'building'");
  });
});
