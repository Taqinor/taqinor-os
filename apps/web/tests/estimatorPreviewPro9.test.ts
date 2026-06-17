// Garde-fous de la PRÉVISUALISATION privée « estimateur — cerveau V6 »
// (/preview/toiture-3d-pro-9) : route privée (noindex, hors sitemap), 3D/cerveau
// chargés paresseusement (jamais sur une page publique), et les DEUX corrections V6 :
//   FIX 1 — toit en pente = VRAI plan incliné, panneaux affleurants/coplanaires, AUCUN
//           châssis triangulaire en pente (gardé par `flush`) ;
//   FIX 2 — l'optimiseur AFFICHE la MATRICE complète (triable/filtrable), plus les ~6
//           lignes nommées du V4.
// Tout l'existant (pro-3..pro-8 + le formulaire live) reste strictement intact.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('pro-9 — route privée, jamais indexée', () => {
  it('la page /preview/toiture-3d-pro-9 est noindex', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-9.astro')).toContain('noindex={true}');
  });

  it('vit dans le sous-dossier /preview (pas de page top-level)', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture-3d-pro-9.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-9.astro', import.meta.url)))).toBe(false);
  });
});

describe('pro-9 — 3D + cerveau chargés paresseusement, hors page publique', () => {
  it('la page importe le script via import() dynamique, jamais en statique', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-9.astro');
    expect(src).toContain("import('../../scripts/roof-tool-pro9.ts')");
    expect(src).not.toContain("from 'three'");
    expect(src).not.toContain("from 'maplibre-gl'");
  });

  it('le script lourd reste hors de toute page publique', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'à-propos']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de roof-tool-pro9`).not.toContain('roof-tool-pro9');
      expect(src, `${p}: pas de cerveau estimateur`).not.toContain('estimatorBrain');
    }
  });

  it('le script ne poste aucun lead — il ne fait que pré-remplir les champs', () => {
    const script = read('../src/scripts/roof-tool-pro9.ts');
    expect(script).not.toContain('/api/preview-lead');
    expect(script).not.toContain('/api/simulate');
  });
});

describe('pro-9 — FIX 1 : toit en pente = vrai plan incliné, pose affleurante, sans châssis', () => {
  const script = read('../src/scripts/roof-tool-pro9.ts');

  it('le rendu pente utilise la GÉOMÉTRIE V6 (plan incliné + pose coplanaire)', () => {
    expect(script).toContain("from '../lib/estimatorBrainV6'");
    expect(script).toContain('pitchedDeckZ('); // la SURFACE de toit devient un plan incliné
    expect(script).toContain('flushPanelCenterAt('); // panneaux posés coplanaires sur le plan
    expect(script).toContain('PITCHED_FLUSH_STANDOFF_M'); // décalage constant le long de la normale
    expect(script).toContain('eaveUpSlopeCoord('); // réf. d'égout → la pente monte
  });

  it('AUCUN châssis triangulaire en pente : front/back/rail/lest gardés par `!flush`', () => {
    expect(script).toContain('if (!flush) for (const xe of ends)'); // pieds de châssis
    expect(script).toContain('if (!flush) for (const xe of [-halfAlong'); // lest
    // le mesh de la dalle est incliné UNIQUEMENT en pente (la photo reste géo-alignée).
    expect(script).toContain('if (flush) {');
    expect(script).toContain('deckGeo.computeVertexNormals()');
  });

  it('le moteur V6 compose sur V2/V4/V5 (aspect PVGIS, pente) sans les ré-implémenter', () => {
    const v6 = read('../src/lib/estimatorBrainV6.ts');
    expect(v6).toContain("from './estimatorBrainV2'");
    expect(v6).toContain("from './estimatorBrainV4'");
    expect(v6).toContain('roofPlaneNormal');
    expect(v6).toContain('PITCHED_FLUSH_STANDOFF_M');
  });
});

describe('pro-9 — FIX 2 : la MATRICE complète est balayée ET affichée (triable/filtrable)', () => {
  const script = read('../src/scripts/roof-tool-pro9.ts');
  const page = read('../src/pages/preview/toiture-3d-pro-9.astro');

  it('le script balaie et affiche la matrice V6 (plus les ~6 lignes V4)', () => {
    expect(script).toContain('fineGridMatrixV6(');
    expect(script).toContain('pvgisMatrixCandidatePairs(');
    expect(script).toContain('sortMatrix(');
    expect(script).toContain('matrixGroupKey(');
    // le tableau 6-lignes V4 (fineGridOptimum / pvgisCandidatePairs) n'est plus utilisé.
    expect(script).not.toContain('fineGridOptimum');
    expect(script).not.toContain('pvgisCandidatePairs(');
  });

  it('la page expose des en-têtes triables + un filtre par orientation', () => {
    expect(page).toContain('data-rp9-sort="annualKwh"');
    expect(page).toContain('data-rp9-sort="placedCount"');
    expect(page).toContain('data-rp9-sort="pctOfTarget"');
    expect(page).toContain('id="rp9-matrix-filter"');
  });

  it('le tri/filtre sont câblés (repaint sans re-balayage) et l\'optimum est badgé', () => {
    expect(script).toContain('setMatrixSort(');
    expect(script).toContain("matrixFilter = ");
    expect(script).toContain('✓ Recommandé');
  });
});

describe('pro-9 — l’existant est strictement préservé', () => {
  it('les baselines pro-3..pro-8 gardent leur page et leur script dédiés', () => {
    for (const n of [3, 4, 5, 6, 7, 8]) {
      expect(read(`../src/pages/preview/toiture-3d-pro-${n}.astro`)).toContain(`import('../../scripts/roof-tool-pro${n}.ts')`);
      expect(existsSync(fileURLToPath(new URL(`../src/scripts/roof-tool-pro${n}.ts`, import.meta.url)))).toBe(true);
    }
  });

  it('pro-8 reste en V5 (pente affleurante pro-8) et utilise encore le V4 optimum', () => {
    const pro8 = read('../src/scripts/roof-tool-pro8.ts');
    expect(pro8).toContain("from '../lib/estimatorBrainV5'");
    expect(pro8).toContain('fineGridOptimum(');
    expect(pro8).not.toContain("from '../lib/estimatorBrainV6'");
  });

  it('pro-7 reste en V4 (toit plat), non réécrit', () => {
    const pro7 = read('../src/scripts/roof-tool-pro7.ts');
    expect(pro7).toContain("from '../lib/estimatorBrainV4'");
    expect(pro7).not.toContain("from '../lib/estimatorBrainV6'");
  });

  it('le proxy /api/roof-yield garde « building » par défaut ; « free » seulement si demandé', () => {
    const route = read('../src/pages/api/roof-yield.ts');
    expect(route).toContain("body.mountingplace === 'free' ? 'free' : 'building'");
  });

  it('le type de toit reste choisi AVANT le tracé (hérité de pro-8) avec preset 45°', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-9.astro');
    expect(src).toContain('id="rp9-rooftype-first"');
    for (const p of ['data-pitch="15"', 'data-pitch="22"', 'data-pitch="30"', 'data-pitch="45"']) {
      expect(src, p).toContain(p);
    }
  });
});
