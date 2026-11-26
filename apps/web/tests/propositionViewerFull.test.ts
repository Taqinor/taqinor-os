// @vitest-environment jsdom
// VISIONNEUSE PLEINE (page publique /proposition) — la moitié TESTABLE.
// (LOT 6 — jsdom pour la barre de la visionneuse au soleil, section 7 ; les sections 1-6 restent pures.)
//
// Le client doit voir le VRAI rendu du builder (scene3d.ts : verre, cadres,
// rails, châssis, ombres), figé, avec la carte complète. Le rendu WebGL lui-même
// n'est pas testable en CI ; TOUT ce qui peut donner un autre toit que celui
// vendu l'est, et c'est ce que ce fichier verrouille :
//   1. la traduction roof_layout → plans de rendu du builder (positions VERBATIM,
//      repère ENU, pose du module, pan actif) ;
//   2. le refus PROPRE d'un layout sans calepinage réel (anciens liens) ;
//   3. le cadrage caméra (centre + zoom) ;
//   4. le CONTRAT lecture seule du boot (aucun écouteur de geste d'édition,
//      aucun module d'édition importé) — garde de source, même convention que
//      mobilePerfWJ18.test.ts.
// Aucun DOM, aucun Three.js, aucun MapLibre : modules purs seulement.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseRoofLayout, type RoofLayout } from '../src/lib/proposition';
import { PANEL2_LONG_M, PANEL2_SHORT_M } from '../src/lib/roofPro2';
import { DEG2M } from '../src/scripts/roofPro11/constants';
import {
  buildViewerFullPlan,
  gridFromGeometry,
  ringENUFromVertices,
  viewerAreaRecords,
  zoomForSpanM,
  VIEWER_FULL_MAX_ZOOM,
  VIEWER_FULL_MIN_ZOOM,
} from '../src/scripts/roofPro11/viewerFullModel';
import { bornesCarte, degradeLegende, libelleInstant, libelleJournee, lireVisionneuseSoleil } from '../src/lib/visionneuseSoleil';
import { couleurAccesActive } from '../src/lib/shadingEngine';
import { attacherSoleil, bornesJournee, couleurParPanneau } from '../src/scripts/roofPro11/viewerSoleil';
import type { ViewerFullHandle } from '../src/scripts/roofPro11/viewerFullBoot';
import { ecrireTeintesPanneaux, GAIN_TEINTE_PANNEAU } from '../src/scripts/roofPro11/scene3d';

// ── Un toit carré réaliste au Maroc (Casablanca), convention x=Est / y=Nord ──
const LAT0 = 33.5;
const LNG0 = -7.6;
const COS = Math.cos((LAT0 * Math.PI) / 180);
function at(x: number, y: number): [number, number] {
  return [LNG0 + x / (DEG2M * COS), LAT0 + y / DEG2M];
}
function squareLngLat(half: number): Array<[number, number]> {
  return [at(-half, -half), at(half, -half), at(half, half), at(-half, half)];
}

/** Colonnes de panneaux au pas `pitch` le long de l'axe de rangée (az 180° → +x). */
function columns(pitch: number, n: number, y = 0): Array<Record<string, unknown>> {
  return Array.from({ length: n }, (_, i) => ({ cx: (i - (n - 1) / 2) * pitch, cy: y }));
}

const PORTRAIT_PITCH = PANEL2_SHORT_M + 0.02; // 1,323 m — pas de colonne portrait
const LANDSCAPE_PITCH = PANEL2_LONG_M + 0.02; // 2,404 m — pas de colonne paysage

function rawZone(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'zone-1',
    label: 'Pan principal',
    vertices: squareLngLat(12),
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 0,
    facingAzimuthDeg: 180,
    neededPanels: 0,
    geometry: {
      azimuthDeg: 180,
      tiltDeg: 13,
      family: 'south',
      flush: false,
      count: 4,
      origin: [LNG0, LAT0],
      panels: columns(PORTRAIT_PITCH, 4),
    },
    ...over,
  };
}

function layoutOf(...zones: Array<Record<string, unknown>>): RoofLayout {
  const parsed = parseRoofLayout({ version: 2, zones });
  if (!parsed) throw new Error('fixture invalide');
  return parsed;
}

// ── 1. Refus PROPRE (l'appelant garde viewerOnly) ────────────────────────────

describe('visionneuse pleine — refus propre, jamais un throw', () => {
  it('layout absent / vide → null', () => {
    expect(buildViewerFullPlan(null)).toBeNull();
    expect(buildViewerFullPlan(undefined)).toBeNull();
    expect(buildViewerFullPlan({ version: 1, zones: [] })).toBeNull();
  });

  it('ancien lien (aucune zone ne porte de calepinage réel) → null', () => {
    const layout = layoutOf(rawZone({ geometry: undefined }));
    expect(layout.zones[0].geometry).toBeUndefined();
    expect(buildViewerFullPlan(layout)).toBeNull();
  });

  it('geometry présente mais sans panneau exploitable → null (parse la rejette déjà)', () => {
    const layout = layoutOf(rawZone({ geometry: { ...(rawZone().geometry as object), panels: [] } }));
    expect(buildViewerFullPlan(layout)).toBeNull();
  });
});

// ── 2. Le calepinage RÉEL, recopié tel quel ──────────────────────────────────

describe('visionneuse pleine — les panneaux sont ceux de l’ERP, jamais un re-pavage', () => {
  it('chaque centre posé est repris VERBATIM (mêmes cx/cy, même face)', () => {
    const layout = layoutOf(
      rawZone({
        geometry: {
          azimuthDeg: 180,
          tiltDeg: 13,
          family: 'eastwest',
          flush: false,
          count: 3,
          origin: [LNG0, LAT0],
          panels: [
            { cx: -1.323, cy: 0, face: 'E' },
            { cx: 0, cy: 0, face: 'W' },
            { cx: 1.323, cy: 4.2 },
          ],
        },
      }),
    );
    const plan = buildViewerFullPlan(layout)!;
    const panels = plan.zones[0].plan!.grid.panels;
    expect(panels).toEqual([
      { cx: -1.323, cy: 0, face: 'E' },
      { cx: 0, cy: 0, face: 'W' },
      { cx: 1.323, cy: 4.2 },
    ]);
    expect(plan.totalPanels).toBe(3);
    // Le pack porte l'azimut/l'inclinaison/la famille RÉELS du pan vendu.
    expect(plan.zones[0].plan!.pack.azimuthDeg).toBe(180);
    expect(plan.zones[0].plan!.tiltDeg).toBe(13);
    expect(plan.zones[0].plan!.family).toBe('eastwest');
    expect(plan.zones[0].plan!.flush).toBe(false);
  });

  it('tous les panneaux posés sont dessinés (count = panels.length, jamais la cible)', () => {
    // `count` déclaré incohérent (2) alors que 4 cellules sont posées : on dessine
    // les 4 — le client doit voir ce qui est posé, pas un chiffre déclaré.
    const geo = { ...(rawZone().geometry as Record<string, unknown>), count: 2 };
    const plan = buildViewerFullPlan(layoutOf(rawZone({ geometry: geo })))!;
    expect(plan.zones[0].plan!.count).toBe(4);
    expect(plan.zones[0].plan!.grid.panels).toHaveLength(4);
  });

  it('le contour du pan passe dans le repère ENU des panneaux (origine geometry.origin)', () => {
    const layout = layoutOf(rawZone({ vertices: [at(-12, -12), at(12, -12), at(12, 12), at(-12, 12)] }));
    const ring = buildViewerFullPlan(layout)!.zones[0].plan!.pack.ringENU;
    expect(ring[0][0]).toBeCloseTo(-12, 6);
    expect(ring[0][1]).toBeCloseTo(-12, 6);
    expect(ring[2][0]).toBeCloseTo(12, 6);
    expect(ring[2][1]).toBeCloseTo(12, 6);
  });

  it('ringENUFromVertices : conversion identique à celle du builder (DEG2M/cos lat)', () => {
    const ring = ringENUFromVertices([at(7, -3)], [LNG0, LAT0]);
    expect(ring[0][0]).toBeCloseTo(7, 9);
    expect(ring[0][1]).toBeCloseTo(-3, 9);
  });

  it('les obstacles du pan suivent (boîtes 3D), avec un identifiant stable', () => {
    const layout = layoutOf(
      rawZone({ obstacles: [{ centerLng: LNG0, centerLat: LAT0, lengthM: 1.2, widthM: 0.8 }] }),
    );
    const obs = buildViewerFullPlan(layout)!.zones[0].plan!.obstacles;
    expect(obs).toHaveLength(1);
    expect(obs[0]).toMatchObject({ id: 'zone-1-obs-0', lengthM: 1.2, widthM: 0.8 });
  });
});

// ── 3. La POSE du module (le bug WJ130 : des rectangles tournés de 90°) ──────

describe('visionneuse pleine — pose du module déduite du pas RÉEL', () => {
  it('pas de colonne portrait → grand côté dans la pente', () => {
    const g = { ...(rawZone().geometry as Record<string, unknown>), panels: columns(PORTRAIT_PITCH, 3) };
    const grid = gridFromGeometry(g as never);
    expect(grid.panelOrientation).toBe('portrait');
    expect(grid.slopeLenM).toBeCloseTo(PANEL2_LONG_M, 6);
    expect(grid.rowWidthM).toBeCloseTo(PANEL2_SHORT_M, 6);
  });

  it('pas de colonne paysage → grand côté le long de la rangée', () => {
    const g = { ...(rawZone().geometry as Record<string, unknown>), panels: columns(LANDSCAPE_PITCH, 3) };
    const grid = gridFromGeometry(g as never);
    expect(grid.panelOrientation).toBe('landscape');
    expect(grid.slopeLenM).toBeCloseTo(PANEL2_SHORT_M, 6);
    expect(grid.rowWidthM).toBeCloseTo(PANEL2_LONG_M, 6);
  });

  it('mesure non concluante (un seul panneau) → repli : paysage à plat, portrait affleurant', () => {
    const base = rawZone().geometry as Record<string, unknown>;
    const flat = gridFromGeometry({ ...base, panels: [{ cx: 0, cy: 0 }] } as never);
    expect(flat.panelOrientation).toBe('landscape');
    const pitched = gridFromGeometry({ ...base, flush: true, panels: [{ cx: 0, cy: 0 }] } as never);
    expect(pitched.panelOrientation).toBe('portrait');
  });
});

// ── 4. Multi-pans : pan actif, pans nus, totaux ──────────────────────────────

describe('visionneuse pleine — plusieurs pans', () => {
  const zoneA = rawZone({ id: 'A', geometry: { ...(rawZone().geometry as object), panels: columns(PORTRAIT_PITCH, 3) } });
  const zoneB = rawZone({
    id: 'B',
    vertices: squareLngLat(9).map(([lng, lat]) => [lng + 0.001, lat] as [number, number]),
    geometry: {
      azimuthDeg: 180,
      tiltDeg: 13,
      family: 'south',
      flush: false,
      count: 7,
      origin: [LNG0 + 0.001, LAT0],
      panels: columns(PORTRAIT_PITCH, 7),
    },
  });

  it('le pan ACTIF est celui qui porte le plus de panneaux posés', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, zoneB))!;
    expect(plan.zones[plan.activeIndex].id).toBe('B');
    expect(plan.totalPanels).toBe(10);
  });

  it('un pan SANS calepinage réel ne fait pas échouer le reste (volume nu, comme l’ERP)', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, rawZone({ id: 'C', geometry: undefined })))!;
    expect(plan.zones.map((z) => z.id)).toEqual(['A', 'C']);
    expect(plan.zones[1].plan).toBeNull();
    expect(plan.zones[1].panelCount).toBe(0);
    expect(plan.zones[plan.activeIndex].id).toBe('A');
  });

  it('viewerAreaRecords : un enregistrement par pan, renderPlan porté, aucun chiffre', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, rawZone({ id: 'C', geometry: undefined })))!;
    const areas = viewerAreaRecords(plan);
    expect(areas.map((a) => a.id)).toEqual(['A', 'C']);
    expect(areas[0].renderPlan).not.toBeNull();
    expect(areas[1].renderPlan).toBeNull();
    for (const a of areas) expect(a.result).toBeNull();
  });

  it('le centre de la vue est le centroïde de TOUS les sommets', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, zoneB))!;
    expect(plan.center[0]).toBeCloseTo(LNG0 + 0.0005, 9);
    expect(plan.center[1]).toBeCloseTo(LAT0, 9);
    expect(plan.spanM).toBeGreaterThan(24);
  });
});

// ── 5. Cadrage caméra ────────────────────────────────────────────────────────

describe('visionneuse pleine — zoom initial (Web Mercator, tuiles 512 px)', () => {
  it('cadre le toit dans la boîte : une emprise de 200 m sur 800 px ≈ zoom 17,5', () => {
    expect(zoomForSpanM(200, 800, LAT0)).toBeCloseTo(17.48, 1);
  });

  it('plus l’emprise est grande, plus on est dézoomé (échelle ville comprise)', () => {
    const toit = zoomForSpanM(200, 800, LAT0);
    const quartier = zoomForSpanM(1000, 800, LAT0);
    const ville = zoomForSpanM(5000, 800, LAT0);
    expect(quartier).toBeLessThan(toit);
    expect(ville).toBeLessThan(quartier);
    expect(ville).toBeGreaterThan(11); // ~12,8 : une ville entière tient à l’écran
  });

  it('borné, et jamais NaN sur une entrée aberrante', () => {
    expect(zoomForSpanM(1, 800, LAT0)).toBe(VIEWER_FULL_MAX_ZOOM);
    expect(zoomForSpanM(1e9, 800, LAT0)).toBe(VIEWER_FULL_MIN_ZOOM);
    expect(Number.isFinite(zoomForSpanM(NaN, 0, NaN))).toBe(true);
  });
});

// ── 6. Le CONTRAT lecture seule (garde de source) ────────────────────────────

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const BOOT = readFileSync(root('../src/scripts/roofPro11/viewerFullBoot.ts'), 'utf-8');
const SCENE = readFileSync(root('../src/scripts/roofPro11/scene3d.ts'), 'utf-8');

describe('visionneuse pleine — lecture seule STRICTE', () => {
  it('aucun module d’ÉDITION n’est importé (tracé, obstacles, disposition, optimiseur, matrice)', () => {
    for (const m of ['mapDraw', 'obstaclesUi', 'layoutEditor', 'optimizer', 'matrix', 'prefill', 'shadingUi', 'prodWindow', 'consumption', 'zones']) {
      expect(BOOT).not.toMatch(new RegExp(`from '\\./${m}'`));
    }
  });

  it('aucun écouteur de geste d’édition sur la carte (clic, double-clic, glissé)', () => {
    for (const ev of ['click', 'dblclick', 'mousedown', 'mousemove', 'mouseup', 'touchstart', 'touchmove', 'contextmenu']) {
      expect(BOOT).not.toContain(`map.on('${ev}'`);
      expect(BOOT).not.toContain(`map.once('${ev}'`);
    }
    // Les SEULS écouteurs carte : le boot de la scène et la panne d'imagerie.
    expect(BOOT).toContain("map.on('load'");
    expect(BOOT).toContain("map.on('error'");
  });

  it('la scène est celle de l’ERP (import de scene3d), en mode readOnly', () => {
    expect(BOOT).toContain("from './scene3d'");
    expect(BOOT).toContain('readOnly: true');
  });

  it('aucune borne de navigation : le client peut dézoomer jusqu’à la ville', () => {
    // Options MapLibre jamais posées (la mention en commentaire, elle, est permise).
    expect(BOOT).not.toContain('maxBounds:');
    expect(BOOT).not.toContain('minZoom:');
    expect(BOOT).not.toContain('.setMaxBounds(');
  });

  it('scene3d : `readOnly` est ADDITIF — absent (ERP) = comportement historique', () => {
    expect(SCENE).toContain('readOnly?: boolean;');
    expect(SCENE).toContain('const readOnly = deps.readOnly === true;');
    // Le pan « autre » reste identifié même quand il n'est plus atténué : la
    // valeur par défaut rend les deux appels historiques inchangés.
    expect(SCENE).toContain('isOtherZone: boolean = dim');
  });

  it('LOT 6 — poignée ADDITIVE : sans `instant` ni `environnement`, soleil et contexte d’aujourd’hui', () => {
    expect(BOOT).toContain('sunHour: opts.instant?.heure ?? DEFAULT_SUN_HOUR,');
    expect(BOOT).toContain('sunDay: opts.instant?.jour ?? WINTER_SOLSTICE_DAY,');
    expect(BOOT).toContain('...(opts.environnement?.length ? { environment: opts.environnement } : {}),');
    expect(BOOT).toContain('scene3d.setSolarAccessHeatmap(');
    // Les bornes de la visionneuse de confiance vivent dans viewerSoleil.ts, jamais ici.
    const SOLEIL = readFileSync(root('../src/scripts/roofPro11/viewerSoleil.ts'), 'utf-8');
    expect(SOLEIL).toContain('poignee.carte.setMaxBounds(');
    expect(SOLEIL).toContain('poignee.carte.setMinZoom(');
    expect(SOLEIL).toContain('poignee.carte.setMaxPitch(INCLINAISON_MAX)');
    expect(SOLEIL).not.toMatch(/\.on\('(click|dblclick|mousedown|touchstart)'/);
    for (const m of ['mapDraw', 'obstaclesUi', 'layoutEditor', 'optimizer', 'shadingUi', 'shadingEngine\\.ts']) {
      expect(SOLEIL).not.toMatch(new RegExp(`from '\\./${m}'`));
    }
  });
});

// ── 7. LOT 6 — la visionneuse au soleil des liens de confiance (D-ACAL-132 à 138) ──

const CONTRAT_SOLEIL = JSON.parse(readFileSync(root('../src/contract_samples/visionneuse_soleil.json'), 'utf-8')) as Record<string, any>;
const payloadSoleil = (cle: 'exemple' | 'exemple_sans_mesure' = 'exemple') => structuredClone(CONTRAT_SOLEIL[cle]) as Record<string, any>;
// Le pan du contrat : `zone-1`, six modules.
const LAYOUT_SOLEIL = layoutOf(rawZone({ geometry: { ...(rawZone().geometry as object), count: 6, panels: columns(PORTRAIT_PITCH, 6) } }));

describe('lireVisionneuseSoleil — exemples du contrat', () => {
  it('exemple : accès servis tels quels, objets voisins en géométrie seule, instant choisi', () => {
    const v = lireVisionneuseSoleil(payloadSoleil(), LAYOUT_SOLEIL)!;
    expect(v.zones).toEqual([{ index: 0, id: 'zone-1', acces: [0.981, 0.979, 0.962, 0.874, null, 0.988] }]);
    expect(v.environnement).toHaveLength(2);
    expect(v.environnement[0]).toEqual({ id: 'voisin-0', kind: 'arbre', centerLng: -7.6195, centerLat: 33.5741, heightM: 7.5, crownDiameterM: 5, evergreen: true });
    expect(v.environnement[1].footprint).toHaveLength(4);
    expect(v.ouverture).toEqual({ jour: 355, heure: 16 });
  });

  it('l’exemple de `proposal_data.json` (lane B) se lit aussi, contre un pan de trois modules', () => {
    const proposal = JSON.parse(readFileSync(root('../src/contract_samples/proposal_data.json'), 'utf-8')) as Record<string, any>;
    const trois = layoutOf(rawZone({ geometry: { ...(rawZone().geometry as object), count: 3, panels: columns(PORTRAIT_PITCH, 3) } }));
    const v = lireVisionneuseSoleil(proposal.exemple, trois)!;
    expect(v.zones).toEqual([{ index: 0, id: 'zone-1', acces: [0.981, 0.874, null] }]);
    expect(v.ouverture).toEqual({ jour: 172, heure: 12 });
  });

  it('exemple sans mesure : aucune zone, aucun objet, ouverture l’été à midi (D-ACAL-135)', () => {
    expect(lireVisionneuseSoleil(payloadSoleil('exemple_sans_mesure'), LAYOUT_SOLEIL)).toEqual({ zones: [], environnement: [], ouverture: { jour: 172, heure: 12 } });
  });
});

describe('lireVisionneuseSoleil — absent ou malformé → null, jamais un throw', () => {
  const sans = (cle: string) => {
    const p = payloadSoleil();
    delete p.visionneuse_soleil[cle];
    return p;
  };
  const piege = { get visionneuse_soleil(): unknown { throw new Error('piège'); } };
  const mauvais: unknown[] = [
    undefined, null, 0, 'x', [], {}, { visionneuse_soleil: null }, { visionneuse_soleil: [] }, { visionneuse_soleil: { version: 2, zones: [], environnement: [], instant_choisi: null } },
    sans('zones'), sans('environnement'), sans('instant_choisi'), sans('version'),
    { visionneuse_soleil: { version: 1, zones: {}, environnement: [], instant_choisi: null } },
    { visionneuse_soleil: { version: 1, zones: [], environnement: [], instant_choisi: { jour: 400, heure: 12 } } },
    piege,
  ];
  it.each(mauvais.map((m, i) => [i, m]))('entrée %s', (_i, m) => {
    expect(lireVisionneuseSoleil(m, LAYOUT_SOLEIL)).toBeNull();
  });

  it('sans layout lu → null', () => {
    expect(lireVisionneuseSoleil(payloadSoleil(), null)).toBeNull();
  });

  it('pan écarté EN BLOC : id différent, longueur différente, valeur hors [0 ; 1] ou non numérique, tout null', () => {
    const variantes: Array<(z: Record<string, any>) => void> = [
      (z) => { z.id = 'zone-2'; },
      (z) => { z.acces.pop(); },
      (z) => { z.acces[0] = 1.2; },
      (z) => { z.acces[1] = '0.5'; },
      (z) => { z.acces = z.acces.map(() => null); },
      (z) => { z.index = 3; },
    ];
    for (const casse of variantes) {
      const p = payloadSoleil();
      casse(p.visionneuse_soleil.zones[0]);
      expect(lireVisionneuseSoleil(p, LAYOUT_SOLEIL)!.zones).toEqual([]);
    }
  });

  it('objets voisins : jamais le libellé ni la hauteur future ; supposé coupé, sans hauteur ou genre inconnu → écarté', () => {
    const p = payloadSoleil();
    const arbre = p.visionneuse_soleil.environnement[0];
    Object.assign(arbre, { label: 'Chez M. Voisin', id: 'env-7', hauteurFutureM: 12, dansAns: 5 });
    p.visionneuse_soleil.environnement.push({ ...arbre, supposeCoupe: true }, { ...arbre, heightM: 0 }, { ...arbre, kind: 'piscine' });
    const v = lireVisionneuseSoleil(p, LAYOUT_SOLEIL)!;
    expect(v.environnement).toHaveLength(2);
    expect(JSON.stringify(v)).not.toMatch(/Voisin|env-7|hauteurFutureM|dansAns|label/);
  });
});

describe('visionneuse au soleil — libellé, bornes de carte, légende, teinte', () => {
  it('libellé de l’instant dans l’année de dessin 2028 de l’atelier, trois langues', () => {
    expect(libelleInstant(355, 12, 'fr')).toBe('20 décembre · 12 h (heure solaire)');
    expect(libelleInstant(172, 16, 'en')).toBe('20 June · 16:00 (solar time)');
    expect(libelleInstant(172, 16, 'ar')).toBe('20 يونيو · الساعة 16 (بالتوقيت الشمسي)');
  });

  it('les bornes du curseur disent aussi l’heure SOLAIRE, trois langues (jamais une heure de montre)', () => {
    expect(libelleJournee(7, 17, 'fr')).toBe('Lever 7 h · coucher 17 h (heure solaire)');
    expect(libelleJournee(7, 17, 'en')).toBe('Sunrise 7:00 · sunset 17:00 (solar time)');
    expect(libelleJournee(7, 17, 'ar')).toBe('الشروق الساعة 7 · الغروب الساعة 17 (بالتوقيت الشمسي)');
  });

  it('bornes : emprise des sommets + 150 m, zoom mini = zoom initial − 2 (D-ACAL-138)', () => {
    const b = bornesCarte(LAYOUT_SOLEIL, 19.2)!;
    expect(b.zoomMin).toBeCloseTo(17.2);
    const [[w, s], [e, n]] = b.bornes;
    for (const [lng, lat] of LAYOUT_SOLEIL.zones[0].vertices) {
      expect((lat - s) * DEG2M).toBeGreaterThan(149);
      expect((n - lat) * DEG2M).toBeGreaterThan(149);
      expect((lng - w) * DEG2M * COS).toBeGreaterThan(149);
      expect((e - lng) * DEG2M * COS).toBeGreaterThan(149);
    }
    expect((n - s) * DEG2M).toBeLessThan(24 + 301);
  });

  it('légende : les couleurs MÊMES que la teinte (palette atelier)', () => {
    const c0 = couleurAccesActive(0, 'atelier');
    expect(degradeLegende()).toContain(`rgb(${Math.round(c0.r * 255)},${Math.round(c0.g * 255)},${Math.round(c0.b * 255)}) 0%`);
    expect(degradeLegende()).toContain('rgb(245,158,11) 100%');
  });

  it('teinte du pan actif seulement ; module non calculé = null (la scène garde sa teinte d’origine), jamais un blanc', () => {
    const v = lireVisionneuseSoleil(payloadSoleil(), LAYOUT_SOLEIL)!;
    expect(couleurParPanneau(v, 1)).toBeNull();
    const f = couleurParPanneau(v, 0)!;
    expect(f(0)).toEqual(couleurAccesActive(0.981, 'atelier'));
    expect(f(4)).toBeNull();
    expect(f(99)).toBeNull();
    // Écrit par la scène : le module non calculé reste à 1,1,1 (neutre), le module mesuré est gainé.
    const rgb: number[][] = [];
    ecrireTeintesPanneaux({ needsUpdate: false, setXYZ: (i, r, g, b) => { rgb[i] = [r, g, b]; } }, [0, 4], f);
    expect(rgb[1]).toEqual([1, 1, 1]);
    expect(rgb[0][0]).toBeCloseTo(couleurAccesActive(0.981, 'atelier').r * GAIN_TEINTE_PANNEAU);
  });

  it('journée : lever et coucher en heures pleines, de la même formule que l’atelier', () => {
    const hiver = bornesJournee(LAT0, 355)!;
    const ete = bornesJournee(LAT0, 172)!;
    expect(Number.isInteger(hiver.riseHour) && Number.isInteger(hiver.setHour)).toBe(true);
    expect(ete.setHour - ete.riseHour).toBeGreaterThan(hiver.setHour - hiver.riseHour);
    expect(bornesJournee(89, 355)).toBeNull();
  });
});

describe('attacherSoleil — la barre pilote la poignée (jsdom)', () => {
  const BARRE = `<div id="roof3d-soleil" hidden><div data-soleil-legende></div>
    <button data-soleil-lecture disabled></button><strong data-soleil-quand></strong><p data-soleil-journee></p>
    <input type="range" data-soleil-heure disabled /><button data-soleil-saison="hiver" disabled></button><button data-soleil-saison="ete" disabled></button></div>`;
  function monter(over: Partial<Parameters<typeof attacherSoleil>[0]> = {}, payload = payloadSoleil()) {
    document.body.innerHTML = BARRE;
    const barre = document.getElementById('roof3d-soleil')!;
    const carte = { setMaxBounds: vi.fn(), setMinZoom: vi.fn(), setMaxPitch: vi.fn() };
    const poignee = { carte, zoomInitial: 19, indexActif: 0, panelCount: 6, destroy: vi.fn(), poserInstant: vi.fn(), teinter: vi.fn() };
    const soleil = lireVisionneuseSoleil(payload, LAYOUT_SOLEIL)!;
    const debrancher = attacherSoleil({ barre, poignee: poignee as unknown as ViewerFullHandle, soleil, layout: LAYOUT_SOLEIL, avecTeinte: true, reducedMotion: false, ...over });
    const q = <T extends HTMLElement>(s: string) => barre.querySelector<T>(s)!;
    return { barre, poignee, carte, debrancher, q };
  }
  afterEach(() => {
    vi.useRealTimers();
    document.documentElement.lang = 'fr';
  });

  it('C3 — rendue cachée, montrée au branchement ; débranchée : cachée, plus aucun reste de légende', () => {
    const { barre, q, debrancher } = monter();
    expect(barre.hidden).toBe(false);
    expect(q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(true);
    debrancher();
    expect(barre.hidden).toBe(true);
    expect(q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(false);
  });

  it('branchée : contrôles actifs, teinte posée, légende visible, carte bornée, instant affiché', () => {
    const { poignee, carte, q } = monter();
    expect(q<HTMLButtonElement>('[data-soleil-lecture]').disabled).toBe(false);
    expect(q<HTMLInputElement>('[data-soleil-heure]').disabled).toBe(false);
    expect(poignee.teinter).toHaveBeenCalledTimes(1);
    expect(q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(true);
    expect(carte.setMaxBounds).toHaveBeenCalledWith(bornesCarte(LAYOUT_SOLEIL, 19)!.bornes);
    expect(carte.setMinZoom).toHaveBeenCalledWith(17);
    expect(carte.setMaxPitch).toHaveBeenCalledWith(60);
    expect(q('[data-soleil-quand]').textContent).toBe('20 décembre · 16 h (heure solaire)');
    const b = bornesJournee(LAYOUT_SOLEIL.zones[0].vertices[0][1], 355)!;
    expect(q('[data-soleil-journee]').textContent).toBe(libelleJournee(b.riseHour, b.setHour, 'fr'));
    expect(q('[data-soleil-saison="hiver"]').getAttribute('aria-pressed')).toBe('true');
  });

  it('aucune valeur enregistrée, ou autre taille montrée : ni teinte ni légende (D-ACAL-136)', () => {
    const a = monter({}, payloadSoleil('exemple_sans_mesure'));
    expect(a.poignee.teinter).not.toHaveBeenCalled();
    expect(a.q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(false);
    const b = monter({ avecTeinte: false });
    expect(b.poignee.teinter).not.toHaveBeenCalled();
  });

  it('lecture : un pas toutes les 700 ms depuis le lever ; second clic = pause', () => {
    vi.useFakeTimers();
    const { poignee, q } = monter();
    const lever = bornesJournee(LAYOUT_SOLEIL.zones[0].vertices[0][1], 355)!.riseHour;
    q<HTMLButtonElement>('[data-soleil-lecture]').click();
    expect(q('[data-soleil-lecture]').getAttribute('aria-pressed')).toBe('true');
    vi.advanceTimersByTime(700);
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(355, lever);
    vi.advanceTimersByTime(700);
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(355, lever + 1);
    q<HTMLButtonElement>('[data-soleil-lecture]').click();
    expect(q('[data-soleil-lecture]').getAttribute('aria-pressed')).toBe('false');
    vi.advanceTimersByTime(5000);
    expect(poignee.poserInstant).toHaveBeenCalledTimes(2);
  });

  it('reduced-motion : un seul pas (l’heure suivante), aucune boucle programmée', () => {
    vi.useFakeTimers();
    const { poignee, q } = monter({ reducedMotion: true });
    const b = bornesJournee(LAYOUT_SOLEIL.zones[0].vertices[0][1], 355)!;
    q<HTMLButtonElement>('[data-soleil-lecture]').click();
    expect(poignee.poserInstant).toHaveBeenCalledTimes(1);
    expect(poignee.poserInstant).toHaveBeenCalledWith(355, 16 + 1 <= b.setHour ? 17 : b.riseHour);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('curseur et saisons : l’instant suit, l’heure reste dans la journée', () => {
    const { poignee, q } = monter();
    const curseur = q<HTMLInputElement>('[data-soleil-heure]');
    curseur.value = '10';
    curseur.dispatchEvent(new Event('input'));
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(355, 10);
    q<HTMLButtonElement>('[data-soleil-saison="ete"]').click();
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(172, 10);
    expect(q('[data-soleil-saison="ete"]').getAttribute('aria-pressed')).toBe('true');
    expect(q('[data-soleil-quand]').textContent).toBe('20 juin · 10 h (heure solaire)');
  });

  it('la langue de la page change : le libellé suit ; débranchée : contrôles inertes', async () => {
    const { q, debrancher, poignee } = monter();
    document.documentElement.lang = 'ar';
    await new Promise((r) => setTimeout(r, 0));
    expect(q('[data-soleil-quand]').textContent).toBe('20 دجنبر · الساعة 16 (بالتوقيت الشمسي)');
    debrancher();
    expect(q<HTMLButtonElement>('[data-soleil-lecture]').disabled).toBe(true);
    q<HTMLButtonElement>('[data-soleil-saison="ete"]').click();
    expect(poignee.poserInstant).not.toHaveBeenCalled();
  });
});
