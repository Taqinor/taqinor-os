// CAL56 — préréts de forme de toiture (2/4 pans, appentis, plat) : géométrie PURE qui
// GÉNÈRE les pans depuis un contour fermé + une pente saisie, au lieu du choix binaire
// plat/pente par zone. Testé hors DOM/Three (pure geometry in, geometry out).
import { describe, expect, it, vi } from 'vitest';
import { creerCanalTeinte } from './canalTeinte'; // ACAL1621
import { cibleVue, appliquerVue } from './vuesCamera';
import { dimensionsTexture } from './panelTexture';
import {
  generateRoofShapePans,
  computeRidgeLifts,
  computeMixedAltitudeOffsets,
  type RoofShapePan,
  type RidgePan,
  hdTargetSize,
  HD_MAX_SIDE_PX,
  HD_SCALES,
  buildAffectationColoring,
  affectationColorFn,
  affectationGroupKey,
  couleurParAffectation,
  lireCouleurServie,
  AFFECTATION_UNASSIGNED,
  type AffectationRow,
  projectPlanView,
  type MixedRidgePan,
  construireChampPose,
  construireOmbriere,
  pasInterRangeeMesure,
  type PlanMoteurSurface,
  capturerApresRendu,
  imageEntierementTransparente,
  ecrireTeintesPanneaux, // ACAL1408
  GAIN_TEINTE_PANNEAU, // ACAL1408
  clePanAffectation, // ACAL1516
} from './scene3d';
import { couleurAccesActive } from '../../lib/shadingEngine'; // ACAL1408
import { buildAreasFromShape } from './zones';
import { coinLePlusProche, positionsPoignees, projeterPoignees } from './poigneesSommets3d'; // ACAL1185
import { DEG2M } from './constants'; // ACAL1185
import { decouperContour, monterFormesToit } from './formesToit';
import { geodesicAreaM2, type LngLat } from '../../lib/roof';
import { rectRing } from './harnaisAtelier';
import { modulesDuDocument, panelQuadsLngLat } from './modulesGeo'; // ACAL528
import { porteeAppliquee, poserTrianglesDeRangee } from './piedsChassis'; // ACAL579
import { readFileSync } from 'node:fs'; // ACAL579
import { resolve } from 'node:path'; // ACAL579
import { panelQuadsLngLat as panelQuadsViaScene3d } from './scene3d';
import { MODULE_ATELIER_PAR_DEFAUT } from '../../lib/roofPro2';

const sumAreaM2 = (pans: RoofShapePan[]): number => pans.reduce((s, p) => s + geodesicAreaM2(p.vertices), 0);

describe('CAL56 — generateRoofShapePans', () => {
  it('contour < 3 sommets → aucun pan', () => {
    expect(generateRoofShapePans([[0, 0], [1, 1]], 'hip')).toEqual([]);
  });

  it('plat : un seul pan = le contour entier', () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'flat');
    expect(pans).toHaveLength(1);
    expect(pans[0].vertices).toEqual(ring);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 3);
  });

  it('appentis : un seul pan, azimut = perpendiculaire au grand côté', () => {
    const ring = rectRing(10, 6); // grand côté E-O → face nord/sud
    const pans = generateRoofShapePans(ring, 'shed');
    expect(pans).toHaveLength(1);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 3);
    // La face est perpendiculaire au grand côté (E-O) → un azimut proche de 0°/180° (± petit écart).
    const az = pans[0].facingAzimuthDeg;
    const nearNorthOrSouth = Math.min(Math.abs(az - 0), Math.abs(az - 180), Math.abs(az - 360));
    expect(nearNorthOrSouth).toBeLessThan(5);
  });

  it('4 pans (croupe) : la somme des surfaces égale EXACTEMENT la surface au sol projetée', () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'hip');
    expect(pans).toHaveLength(4); // un pan par arête du contour à 4 sommets
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 2);
    // Chaque pan est un triangle cohérent (3 sommets).
    for (const p of pans) expect(p.vertices).toHaveLength(3);
  });

  it('2 pans (gable) : deux pans qui se font face, faîtière centrale — aire conservée', () => {
    const ring = rectRing(10, 6);
    const pans = generateRoofShapePans(ring, 'gable');
    expect(pans).toHaveLength(2);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 2);
    // Les deux pans se font face (azimuts opposés à ~180° l'un de l'autre).
    const diff = Math.abs(pans[0].facingAzimuthDeg - pans[1].facingAzimuthDeg);
    const opposed = Math.min(diff, 360 - diff);
    expect(opposed).toBeGreaterThan(170);
  });

  it('un contour carré redécoupé en 4 pans reste cohérent (surfaces positives, aucun pan dégénéré)', () => {
    const ring = rectRing(6, 6);
    const pans = generateRoofShapePans(ring, 'hip');
    for (const p of pans) expect(geodesicAreaM2(p.vertices)).toBeGreaterThan(0);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 2);
  });
});

// ═══════════ CALX96 — préréts EN L / EN T (contour concave) ═══════════
/** Contour EN L (6 sommets, même convention que `rectRing` : anneau ouvert) : un rectangle
 *  plein widthM × depthM dont le coin NORD-EST est amputé d'une encoche
 *  notchWidthM × notchDepthM — le coin réflexe est le sommet intérieur de l'encoche. */
function lShapeRing(widthM: number, depthM: number, notchWidthM: number, notchDepthM: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const mPerDegLat = 111320;
  const mPerDegLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const at = (xM: number, yM: number): LngLat => [lng0 + xM / mPerDegLng, lat0 + yM / mPerDegLat];
  const xNotch = widthM - notchWidthM;
  const yNotch = depthM - notchDepthM;
  return [at(0, 0), at(widthM, 0), at(widthM, yNotch), at(xNotch, yNotch), at(xNotch, depthM), at(0, depthM)];
}

/** Contour EN T (8 sommets) : une barre pleine barWidthM × barDepthM posée SUR un montant
 *  (stem) stemWidthM × stemDepthM centré sous elle — DEUX sommets réflexes, un de chaque côté
 *  du montant. */
function tShapeRing(barWidthM: number, barDepthM: number, stemWidthM: number, stemDepthM: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const mPerDegLat = 111320;
  const mPerDegLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const at = (xM: number, yM: number): LngLat => [lng0 + xM / mPerDegLng, lat0 + yM / mPerDegLat];
  const stemX0 = (barWidthM - stemWidthM) / 2;
  const stemX1 = stemX0 + stemWidthM;
  return [
    at(stemX0, 0),
    at(stemX1, 0),
    at(stemX1, stemDepthM),
    at(barWidthM, stemDepthM),
    at(barWidthM, stemDepthM + barDepthM),
    at(0, stemDepthM + barDepthM),
    at(0, stemDepthM),
    at(stemX0, stemDepthM),
  ];
}

describe('CALX96 — generateRoofShapePans (l_gable/t_gable, contour concave)', () => {
  it('L à 6 sommets : la somme des aires des pans égale l’aire du contour à 10⁻⁶ près', () => {
    const ring = lShapeRing(10, 10, 4, 4);
    const pans = generateRoofShapePans(ring, 'l_gable');
    const total = geodesicAreaM2(ring);
    expect(sumAreaM2(pans) / total).toBeCloseTo(1, 6);
  });

  it('L à 6 sommets : 2 ailes (2 axes de faîtière) → 4 pans, tous d’aire positive', () => {
    const ring = lShapeRing(10, 10, 4, 4);
    const pans = generateRoofShapePans(ring, 'l_gable');
    expect(pans).toHaveLength(4);
    for (const p of pans) expect(geodesicAreaM2(p.vertices)).toBeGreaterThan(0);
  });

  it('L asymétrique (encoche décentrée) : aire conservée quelle que soit la position du coin', () => {
    const ring = lShapeRing(14, 9, 6, 5);
    const pans = generateRoofShapePans(ring, 'l_gable');
    expect(sumAreaM2(pans) / geodesicAreaM2(ring)).toBeCloseTo(1, 6);
  });

  it('T à 8 sommets : 3 ailes (3 axes de faîtière) → 6 pans, aire conservée', () => {
    const ring = tShapeRing(12, 4, 4, 6);
    const pans = generateRoofShapePans(ring, 't_gable');
    expect(pans).toHaveLength(6);
    expect(sumAreaM2(pans) / geodesicAreaM2(ring)).toBeCloseTo(1, 6);
  });

  it('un contour CONVEXE soumis à l_gable est refusé en nommant la raison (jamais un découpage faux)', () => {
    const ring = rectRing(10, 6);
    expect(() => generateRoofShapePans(ring, 'l_gable')).toThrow(/concave|convexe/i);
  });

  it('un contour CONVEXE soumis à t_gable est refusé en nommant la raison', () => {
    const ring = rectRing(10, 6);
    expect(() => generateRoofShapePans(ring, 't_gable')).toThrow(/concave|convexe/i);
  });

  it('buildAreasFromShape (zones.ts) traduit l_gable SANS changement — roofType pitched pour chaque pan', () => {
    const ring = lShapeRing(10, 10, 4, 4);
    const pans = generateRoofShapePans(ring, 'l_gable');
    let n = 0;
    const areas = buildAreasFromShape(pans, 'l_gable', 28, () => `wing${n++}`);
    expect(areas).toHaveLength(pans.length);
    expect(new Set(areas.map((a) => a.id)).size).toBe(pans.length);
    for (const a of areas) {
      expect(a.roofType).toBe('pitched');
      expect(a.pitchDeg).toBe(28);
    }
  });
});

describe('CAL56 — buildAreasFromShape (zones.ts)', () => {
  it("traduit chaque pan en AreaRecord — 'flat' → roofType plat, sinon pente saisie inchangée", () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'hip');
    let n = 0;
    const areas = buildAreasFromShape(pans, 'hip', 30, () => `a${n++}`);
    expect(areas).toHaveLength(4);
    expect(new Set(areas.map((a) => a.id)).size).toBe(4); // ids distincts
    for (const a of areas) {
      expect(a.roofType).toBe('pitched');
      expect(a.pitchDeg).toBe(30); // jamais réinventée — celle saisie par l'utilisateur
      expect(a.result).toBeNull();
      expect(a.neededAuto).toBe(true);
    }
  });

  it("préré 'flat' → roofType flat pour chaque pan (ici un seul)", () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'flat');
    const areas = buildAreasFromShape(pans, 'flat', 0, () => 'z0');
    expect(areas).toHaveLength(1);
    expect(areas[0].roofType).toBe('flat');
  });
});

// ═══════════ CAL61 — calage d'altitude MIXTE (pans plats + pans en pente) ═══════════
/** Rectangle ENU (m), x ∈ [x0, x0+w], y ∈ [y0, y0+h] — anneau ouvert. */
function enuRect(x0: number, y0: number, w: number, h: number): [number, number][] {
  return [
    [x0, y0],
    [x0 + w, y0],
    [x0 + w, y0 + h],
    [x0, y0 + h],
  ];
}

describe('CAL61 — computeMixedAltitudeOffsets', () => {
  it('NON-RÉGRESSION : un ensemble 100 % pente donne EXACTEMENT computeRidgeLifts (au mm près)', () => {
    // Deux pans en pente accolés sur leur côté est/ouest, faces opposées (même géométrie
    // que le test W107 existant côté scene3d).
    const a: RidgePan = { ringENU: enuRect(0, 0, 10, 6), facingAzimuthDeg: 90, tiltDeg: 20 };
    const b: RidgePan = { ringENU: enuRect(10, 0, 10, 6), facingAzimuthDeg: 270, tiltDeg: 20 };
    const expected = computeRidgeLifts([a, b]);
    const mixed: MixedRidgePan[] = [
      { ...a, pitched: true },
      { ...b, pitched: true },
    ];
    const got = computeMixedAltitudeOffsets(mixed);
    expect(got[0]).toBeCloseTo(expected[0], 9);
    expect(got[1]).toBeCloseTo(expected[1], 9);
  });

  it('un pan plat ISOLÉ (aucun voisin en pente) garde un offset de 0 (rendu inchangé)', () => {
    const flat: MixedRidgePan = { ringENU: enuRect(0, 0, 8, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const other: MixedRidgePan = { ringENU: enuRect(100, 100, 8, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    expect(computeMixedAltitudeOffsets([flat, other])).toEqual([0, 0]);
  });

  it('un pan plat accolé à l’ÉGOUT d’un pan en pente (le point le plus bas) reste au niveau 0', () => {
    // Face sud (180°) : l'égout est le côté SUD (y minimal). Pan en pente y∈[0,6], pan
    // plat accolé juste au sud, y∈[-6,0] — arête partagée exactement à l'égout.
    const pitched: MixedRidgePan = { ringENU: enuRect(0, 0, 10, 6), facingAzimuthDeg: 180, tiltDeg: 30, pitched: true };
    const flat: MixedRidgePan = { ringENU: enuRect(0, -6, 10, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const offsets = computeMixedAltitudeOffsets([pitched, flat]);
    expect(offsets[0]).toBeCloseTo(0, 9); // pan en pente isolé → aucun lift
    expect(offsets[1]).toBeCloseTo(0, 6); // accolé à l'égout → aucune marche
  });

  it('un pan plat accolé au FAÎTAGE d’un pan en pente monte à sa hauteur exacte (tan(pente)×profondeur)', () => {
    // Même pan en pente, mais le pan plat est accolé au NORD (côté haut de pente).
    const pitched: MixedRidgePan = { ringENU: enuRect(0, 0, 10, 6), facingAzimuthDeg: 180, tiltDeg: 30, pitched: true };
    const flat: MixedRidgePan = { ringENU: enuRect(0, 6, 10, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const offsets = computeMixedAltitudeOffsets([pitched, flat]);
    const expectedH = 6 * Math.tan((30 * Math.PI) / 180);
    expect(offsets[1]).toBeCloseTo(expectedH, 6);
  });

  it('un pan plat touchant DEUX pans en pente de hauteurs différentes monte au niveau du PLUS HAUT (jamais transpercé)', () => {
    const low: MixedRidgePan = { ringENU: enuRect(0, 0, 10, 3), facingAzimuthDeg: 180, tiltDeg: 15, pitched: true };
    const high: MixedRidgePan = { ringENU: enuRect(10, 0, 10, 3), facingAzimuthDeg: 180, tiltDeg: 45, pitched: true };
    // Pan plat qui longe l'égout (y=0) des deux pans en pente, sur toute leur largeur.
    const flat: MixedRidgePan = { ringENU: enuRect(0, -6, 20, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const offsets = computeMixedAltitudeOffsets([low, high, flat]);
    // Les deux pans en pente touchent l'égout du plat exactement à leur propre hauteur 0
    // (aucun lift, isolés l'un de l'autre — pas de faîtière commune) : le plat reste à 0.
    expect(offsets[2]).toBeCloseTo(0, 6);
  });

  it('moins de 2 pans → aucun offset (garde-fou)', () => {
    const solo: MixedRidgePan = { ringENU: enuRect(0, 0, 8, 6), facingAzimuthDeg: 180, tiltDeg: 20, pitched: true };
    expect(computeMixedAltitudeOffsets([solo])).toEqual([0]);
  });
});

// CAL180 — dimensions de la cible HORS ÉCRAN. Partie PURE du rendu haute résolution :
// le facteur est RABAISSÉ quand le plafond l'impose, et le facteur effectif est rendu
// à l'appelant (il ne le suppose jamais).
describe('CAL180 — hdTargetSize', () => {
  it('2× et 3× sont les facteurs proposés', () => {
    expect([...HD_SCALES]).toEqual([2, 3]);
  });

  it('agrandit exactement du facteur demandé quand le plafond le permet', () => {
    expect(hdTargetSize(1280, 720, 2)).toEqual({ width: 2560, height: 1440, scale: 2 });
    expect(hdTargetSize(1280, 720, 3)).toEqual({ width: 3840, height: 2160, scale: 3 });
  });

  it('rabaisse le facteur plutôt que de dépasser le plafond', () => {
    const t = hdTargetSize(4000, 2000, 3)!;
    expect(t.width).toBeLessThanOrEqual(HD_MAX_SIDE_PX);
    expect(t.height).toBeLessThanOrEqual(HD_MAX_SIDE_PX);
    expect(t.scale).toBeLessThan(3);
    expect(t.width).toBe(HD_MAX_SIDE_PX);
  });

  it('un canvas déjà plus grand que le plafond n’est jamais réduit sous 1×', () => {
    const t = hdTargetSize(10000, 800, 2)!;
    expect(t.scale).toBe(1);
    expect(t.width).toBe(10000);
  });

  it('un canvas sans surface ne produit aucune cible (jamais une taille inventée)', () => {
    expect(hdTargetSize(0, 720, 2)).toBeNull();
    expect(hdTargetSize(1280, 0, 2)).toBeNull();
    expect(hdTargetSize(Number.NaN, 720, 2)).toBeNull();
    expect(hdTargetSize(1280, 720, 0)).toBeNull();
  });
});

// CAL126 — TEINTE PAR CHAÎNE / PAR MPPT. Les couleurs viennent EXCLUSIVEMENT de la table
// `electrique.affectation` du serveur (CAL125) : aucun calcul de partition côté écran.
// Un module non affecté est GRIS et COMPTÉ dans la légende. Les lignes ci-dessous sont
// exactement celles de `contract_samples/calepinage_resultat.json`.
const BLEU = 'rgb(30, 144, 255)';
const ORANGE = 'rgb(255, 140, 0)';
const GRIS = 'rgb(140, 143, 148)';
const AFFECTATION: AffectationRow[] = [
  { module: 'PAN-A#1', pan: 'PAN-A', chaine: 1, onduleur: 1, mppt: 1, couleur_chaine: BLEU, couleur_mppt: ORANGE },
  { module: 'PAN-A#2', pan: 'PAN-A', chaine: 1, onduleur: 1, mppt: 1, couleur_chaine: BLEU, couleur_mppt: ORANGE },
  { module: 'PAN-B#1', pan: 'PAN-B', chaine: 2, onduleur: 1, mppt: 2, couleur_chaine: ORANGE, couleur_mppt: BLEU },
  { module: 'PAN-B#2', pan: 'PAN-B', chaine: 2, onduleur: 1, mppt: 2, couleur_chaine: ORANGE, couleur_mppt: BLEU },
  { module: 'PAN-B#3', pan: 'PAN-B', chaine: null, onduleur: null, mppt: null, couleur_chaine: GRIS, couleur_mppt: GRIS },
];

describe('CAL126 — la couleur vient de la table, jamais d’un calcul d’écran', () => {
  it('deux modules de la MÊME chaîne ont la MÊME couleur, deux chaînes en ont deux', () => {
    const { colorByModule } = buildAffectationColoring(AFFECTATION, 'chaine');
    expect(colorByModule.get('PAN-A#1')).toEqual(colorByModule.get('PAN-A#2'));
    expect(colorByModule.get('PAN-B#1')).toEqual(colorByModule.get('PAN-B#2'));
    expect(colorByModule.get('PAN-A#1')).not.toEqual(colorByModule.get('PAN-B#1'));
  });

  it('la couleur est celle de la ligne SERVIE, selon le mode — jamais une palette locale', () => {
    const chaine = buildAffectationColoring(AFFECTATION, 'chaine').colorByModule;
    expect(chaine.get('PAN-A#1')).toEqual(lireCouleurServie(BLEU));
    expect(chaine.get('PAN-B#1')).toEqual(lireCouleurServie(ORANGE));
    // Mode MPPT : la couleur d'entrée, pas celle de chaîne (échanger les deux champs ⇒ rouge).
    const mppt = buildAffectationColoring(AFFECTATION, 'mppt').colorByModule;
    expect(mppt.get('PAN-A#1')).toEqual(lireCouleurServie(ORANGE));
    expect(mppt.get('PAN-B#1')).toEqual(lireCouleurServie(BLEU));
  });

  it('une couleur servie illisible ou absente laisse le module gris', () => {
    expect(lireCouleurServie('rgb(300, 0, 0)')).toBeNull();
    expect(lireCouleurServie(null)).toBeNull();
    const { colorByModule } = buildAffectationColoring(
      [{ module: 'X#1', chaine: 1, mppt: 1 }], 'chaine');
    expect(colorByModule.get('X#1')).toEqual(AFFECTATION_UNASSIGNED);
  });

  it('un module NON affecté est gris et COMPTÉ dans la légende (il ne disparaît pas)', () => {
    const { colorByModule, legend } = buildAffectationColoring(AFFECTATION, 'chaine');
    expect(colorByModule.get('PAN-B#3')).toEqual(AFFECTATION_UNASSIGNED);
    const nonAffecte = legend.find((e) => e.key === null)!;
    expect(nonAffecte.label).toBe('Non affecté');
    expect(nonAffecte.count).toBe(1);
    expect(legend.at(-1)).toBe(nonAffecte); // toujours en fin de légende
    expect(legend.reduce((n, e) => n + e.count, 0)).toBe(AFFECTATION.length); // rien de perdu
  });

  it('la légende nomme les chaînes et compte leurs modules', () => {
    const { legend } = buildAffectationColoring(AFFECTATION, 'chaine');
    expect(legend.filter((e) => e.key !== null).map((e) => [e.label, e.count])).toEqual([
      ['Chaîne 1', 2],
      ['Chaîne 2', 2],
    ]);
  });
});

describe('ACAL286 — la teinte atteint le canal instanceColor du module PAN-A#1', () => {
  /** Un buffer `instanceColor` minimal : on lit ce qui a été écrit, comme le canal réel. */
  const tampon = (n: number) => {
    const rgb: number[][] = Array.from({ length: n }, () => [1, 1, 1]);
    return { rgb, setXYZ: (i: number, r: number, g: number, b: number) => { rgb[i] = [r, g, b]; } };
  };

  it('setStringColoring appliquée : la couleur d’instance du module PAN-A#1 est la couleur_chaine de sa ligne', () => {
    const coloring = buildAffectationColoring(AFFECTATION, 'chaine');
    // Cellules de lattice occupées 4, 7, 9 du pan « PAN-A » : rangs 1, 2, 3.
    const cellules = [4, 7, 9];
    const fn = couleurParAffectation(coloring, cellules, 'PAN-A')!;
    const buf = tampon(cellules.length);
    cellules.forEach((c, i) => { const col = fn(c); buf.setXYZ(i, col.r, col.g, col.b); });
    const bleu = lireCouleurServie(BLEU)!;
    expect(buf.rgb[0]).toEqual([bleu.r, bleu.g, bleu.b]); // PAN-A#1
    expect(buf.rgb[1]).toEqual([bleu.r, bleu.g, bleu.b]); // PAN-A#2 : même chaîne
    // PAN-A#3 n'est pas dans la table : gris, jamais une couleur de groupe au hasard.
    expect(buf.rgb[2]).toEqual([AFFECTATION_UNASSIGNED.r, AFFECTATION_UNASSIGNED.g, AFFECTATION_UNASSIGNED.b]);
  });

  it('table vide ou non servie ⇒ aucune coloration (null)', () => {
    expect(couleurParAffectation(null, [0, 1], 'PAN-A')).toBeNull();
    expect(couleurParAffectation(buildAffectationColoring([], 'chaine'), [0, 1], 'PAN-A')).toBeNull();
  });
});

// ACAL1408 — la carte d'accès écrivait la teinte brute dans `instanceColor`, que le matériau MULTIPLIE à une texture
// de panneau quasi noire (≈ 0,05, panelTexture.ts / PV31) : « bleu nuit × noir = noir », aucun panneau ne changeait.
describe('ACAL1408 — la teinte d’accès modifie la couleur effective du panneau, pas seulement instanceColor', () => {
  const FOND_PANNEAU = 0.05; // luminance de la texture du verre (PV31)
  const tampon = (n: number) => {
    const rgb: number[][] = Array.from({ length: n }, () => [1, 1, 1]);
    return { rgb, needsUpdate: false, setXYZ(i: number, r: number, g: number, b: number) { rgb[i] = [r, g, b]; } };
  };
  const effective = (c: number[]) => c.map((v) => Math.min(1, FOND_PANNEAU * v));

  it('plein soleil ⇒ teinte lisible ; panneau ombré ⇒ nettement plus sombre ; éteinte ⇒ teinte d’origine', () => {
    const acces = [1, 0.944, 0.1]; // cellule → accès solaire
    const buf = tampon(3);
    ecrireTeintesPanneaux(buf, [0, 1, 2], (cell) => couleurAccesActive(acces[cell], 'atelier')); // rampe bleu nuit → or (ERP)
    expect(buf.needsUpdate).toBe(true);
    const soleil = effective(buf.rgb[0]);
    const ombre = effective(buf.rgb[2]);
    expect(Math.max(...soleil)).toBeGreaterThan(0.3); // or lisible, pas un noir à peine plus chaud
    const lum = (c: number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    expect(lum(soleil) - lum(ombre)).toBeGreaterThan(0.1);
    ecrireTeintesPanneaux(buf, [0, 1, 2], null);
    expect(buf.rgb).toEqual([[1, 1, 1], [1, 1, 1], [1, 1, 1]]);
  });

  it('la teinte de chaîne (setStringColoring, même canal) est gainée de la même façon', () => {
    const buf = tampon(1);
    const bleu = lireCouleurServie(BLEU)!;
    ecrireTeintesPanneaux(buf, [7], () => bleu);
    expect(buf.rgb[0]).toEqual([bleu.r * GAIN_TEINTE_PANNEAU, bleu.g * GAIN_TEINTE_PANNEAU, bleu.b * GAIN_TEINTE_PANNEAU]);
    expect(Math.max(...effective(buf.rgb[0]))).toBeGreaterThan(0.3);
  });
});

// Demande croisée (ACAL1621) — la carte d'accès et la teinte par chaîne écrivent le MÊME tampon : un maillage reconstruit
// (ou une table de chaînes arrivée) pendant la capture de la carte de chaleur repeignait les chaînes par-dessus l'accès.
describe('ACAL1621 — canal de teinte : la carte d’accès allumée passe avant la teinte par chaîne', () => {
  it('accès allumé : la reconstruction / les chaînes réécrivent l’accès ; éteint : les chaînes reviennent', () => {
    const ecrits: Array<string | null> = [];
    const nomme = (nom: string) => Object.assign(() => ({ r: 0, g: 0, b: 0 }), { nom });
    const canal = creerCanalTeinte((c) => ecrits.push(c ? (c as unknown as { nom: string }).nom : null));
    const chaines = nomme('chaînes');
    const acces = nomme('accès');
    canal.chaines(chaines);
    canal.acces(acces, () => chaines); // « Joindre la carte de chaleur » allume l'accès
    canal.chaines(chaines); // maillage reconstruit pendant la capture
    expect(canal.accesActive()).toBe(true);
    canal.acces(null, () => chaines); // capture finie : l'accès s'éteint
    canal.acces(null, () => null); // ni accès ni chaînes : teinte d'origine
    expect(ecrits).toEqual(['chaînes', 'accès', 'accès', 'chaînes', null]);
  });
});

// ACAL1516 — la carte de l'étape Électrique restait noire : le serveur sert `'<zone.id>#<n>'` (ACAL265) et la scène
// cherchait `'<libellé>#<n>'` (« Zone 1#1 ») : aucune ligne trouvée, tous les modules au gris « non affecté ».
describe('ACAL1516 — deux chaînes ⇒ deux teintes de module sur la carte', () => {
  it('pan « Zone 1 » d’id z1, lignes servies z1#1 (chaîne 1, bleu) et z1#2 (chaîne 2, orange)', () => {
    const lignes: AffectationRow[] = [
      { module: 'z1#1', pan: 'z1', chaine: 1, onduleur: 1, mppt: 1, couleur_chaine: BLEU, couleur_mppt: BLEU },
      { module: 'z1#2', pan: 'z1', chaine: 2, onduleur: 1, mppt: 2, couleur_chaine: ORANGE, couleur_mppt: ORANGE },
    ];
    const cle = clePanAffectation({ id: 'z1', label: 'Zone 1' } as { id: string }, 'z1');
    expect(cle).toBe('z1');
    const fn = couleurParAffectation(buildAffectationColoring(lignes, 'chaine'), [3, 8], cle)!;
    expect(fn(3)).toEqual(lireCouleurServie(BLEU));
    expect(fn(8)).toEqual(lireCouleurServie(ORANGE));
    expect(fn(3)).not.toEqual(fn(8));
    expect(clePanAffectation(undefined, 'z9')).toBe('z9'); // pan pas encore relu : l'id actif
  });
});

describe('CAL126 — bascule chaîne / MPPT', () => {
  it('le mode MPPT regroupe par entrée, onduleur compris', () => {
    expect(affectationGroupKey(AFFECTATION[0], 'mppt')).toBe('o1m1');
    expect(affectationGroupKey(AFFECTATION[2], 'mppt')).toBe('o1m2');
    // Deux onduleurs ont chacun leur entrée 1 : ce ne sont PAS le même groupe.
    expect(affectationGroupKey({ module: 'x', chaine: 9, onduleur: 2, mppt: 1 }, 'mppt')).toBe('o2m1');
    const { legend } = buildAffectationColoring(AFFECTATION, 'mppt');
    expect(legend.filter((e) => e.key !== null).map((e) => e.label)).toEqual([
      'Onduleur 1 — MPPT 1',
      'Onduleur 1 — MPPT 2',
    ]);
  });

  it('une chaîne nulle / un MPPT nul est « non affecté » dans les deux modes', () => {
    expect(affectationGroupKey(AFFECTATION[4], 'chaine')).toBeNull();
    expect(affectationGroupKey(AFFECTATION[4], 'mppt')).toBeNull();
  });
});

describe('CAL126 — alimentation du canal de couleur existant', () => {
  it('la fonction rend la couleur du module de CETTE cellule', () => {
    const coloring = buildAffectationColoring(AFFECTATION, 'chaine');
    const fn = affectationColorFn(coloring, ['PAN-A#1', 'PAN-B#1', 'PAN-B#3'])!;
    expect(fn(0)).toEqual(coloring.colorByModule.get('PAN-A#1'));
    expect(fn(1)).toEqual(coloring.colorByModule.get('PAN-B#1'));
    expect(fn(2)).toEqual(AFFECTATION_UNASSIGNED);
  });

  it('une cellule sans module connu est grise, jamais d’une couleur de groupe au hasard', () => {
    const coloring = buildAffectationColoring(AFFECTATION, 'chaine');
    const fn = affectationColorFn(coloring, [null, 'INCONNU'])!;
    expect(fn(0)).toEqual(AFFECTATION_UNASSIGNED);
    expect(fn(1)).toEqual(AFFECTATION_UNASSIGNED);
  });

  it('table vide ⇒ aucune coloration (comportement d’avant CAL126, heatmap intacte)', () => {
    expect(buildAffectationColoring([], 'chaine').legend).toEqual([]);
    expect(buildAffectationColoring(null, 'chaine').colorByModule.size).toBe(0);
    expect(affectationColorFn(buildAffectationColoring([], 'chaine'), [])).toBeNull();
    expect(affectationColorFn(buildAffectationColoring(undefined, 'mppt'), ['a'])).toBeNull();
  });

  it('NON-RÉGRESSION : la coloration électrique ne touche pas la carte d’accès solaire', () => {
    // Les deux sources sont indépendantes : construire l'une ne modifie pas l'autre.
    // Une fonction d'accès solaire (verte/rouge) reste exactement ce qu'elle était.
    const heat = (i: number) => ({ r: i / 10, g: 1 - i / 10, b: 0 });
    const avant = [0, 1, 2].map(heat);
    const coloring = buildAffectationColoring(AFFECTATION, 'chaine');
    affectationColorFn(coloring, ['PAN-A#1', 'PAN-B#1', 'PAN-B#3']);
    expect([0, 1, 2].map(heat)).toEqual(avant);
  });
});

// CAL104 — PROJECTION PLAN ORTHOGRAPHIQUE. Ce que ce bloc prouve : même échelle sur les
// deux axes (une cote lue est la cote réelle), nord EN HAUT, et surtout — le compte de
// modules est celui de la 3D RECOPIÉ, jamais recalculé.
describe('CAL104 — projectPlanView', () => {
  const ring = rectRing(20, 10); // 20 m E-O × 10 m N-S
  const opts = { widthPx: 800, heightPx: 400, marginPx: 20 };

  it('projette le contour, orthographique et nord en haut', () => {
    const plan = projectPlanView(ring, [], opts)!;
    expect(plan.outline).toHaveLength(4);
    // rectRing : sommet 0 = sud-ouest, sommet 2 = nord-est. Nord en haut ⇒ y plus PETIT.
    expect(plan.outline[2][1]).toBeLessThan(plan.outline[0][1]);
    // Est à droite ⇒ x plus GRAND.
    expect(plan.outline[1][0]).toBeGreaterThan(plan.outline[0][0]);
  });

  it('une SEULE échelle : la cote lue est la cote réelle', () => {
    const plan = projectPlanView(ring, [], opts)!;
    expect(plan.spanEastWestM).toBeCloseTo(20, 1);
    expect(plan.spanNorthSouthM).toBeCloseTo(10, 1);
    const [c0, c1] = plan.cotes;
    // Le côté sud mesure ~20 m et le côté est ~10 m — mesurés sur la géométrie réelle.
    expect(c0.lengthM).toBeCloseTo(20, 1);
    expect(c1.lengthM).toBeCloseTo(10, 1);
    // Rapport des longueurs À L'ÉCRAN = rapport des longueurs RÉELLES (pas d'anamorphose).
    const l0 = Math.hypot(c0.to[0] - c0.from[0], c0.to[1] - c0.from[1]);
    const l1 = Math.hypot(c1.to[0] - c1.from[0], c1.to[1] - c1.from[1]);
    expect(l0 / l1).toBeCloseTo(c0.lengthM / c1.lengthM, 2);
  });

  it('le dessin tient dans la zone, marges comprises', () => {
    const plan = projectPlanView(ring, [], opts)!;
    for (const [x, y] of plan.outline) {
      expect(x).toBeGreaterThanOrEqual(opts.marginPx - 1e-6);
      expect(x).toBeLessThanOrEqual(opts.widthPx - opts.marginPx + 1e-6);
      expect(y).toBeGreaterThanOrEqual(opts.marginPx - 1e-6);
      expect(y).toBeLessThanOrEqual(opts.heightPx - opts.marginPx + 1e-6);
    }
  });

  it('LE COMPTE EST CELUI DE LA 3D : autant de modules projetés qu’entrés, ni plus ni moins', () => {
    const modules = [rectRing(2, 1), rectRing(2, 1, -7.5999), rectRing(2, 1, -7.5998)];
    const plan = projectPlanView(ring, modules, opts)!;
    expect(plan.panelCount).toBe(3);
    expect(plan.panels).toHaveLength(3);
    expect(projectPlanView(ring, [], opts)!.panelCount).toBe(0);
  });

  it('rien à dessiner ⇒ null, jamais un plan inventé', () => {
    expect(projectPlanView([], [], opts)).toBeNull();
    expect(projectPlanView(null, [], opts)).toBeNull();
    expect(projectPlanView(ring.slice(0, 2), [], opts)).toBeNull();
    expect(projectPlanView(ring, [], { widthPx: 0, heightPx: 400 })).toBeNull();
  });
});

// CAL89 — le CHAMP AU SOL est POSÉ par le moteur : l'atelier le place, il ne le
// décide pas. Ce que ces tests interdisent : une seconde formule de pas
// inter-rangées côté client (le pas est MESURÉ sur les rangées du moteur), un
// taux d'occupation présenté comme une saisie (c'est une SORTIE), et un chiffre
// inventé quand une donnée manque (on rend `null` et on le dit).
describe('CAL89 — champ au sol : placer le plan du moteur, ne rien recalculer', () => {
  /** Un plan de moteur RÉALISTE, à la forme du contrat `pose.json` : deux rangées
   *  de deux tables, entraxe 6 m (0 → 6), tables de 4 m × 2,3 m. */
  const PLAN: PlanMoteurSurface = {
    surface: 'TERRAIN-A',
    modules: 16,
    rangees: [
      { y0: 0, modules: 8 },
      { y0: 6, modules: 8 },
    ],
    tables: [
      { x0: 0, x1: 4, y0: 0, y1: 2.3, kit: 'portrait' },
      { x0: 4.5, x1: 8.5, y0: 0, y1: 2.3, kit: 'portrait' },
      { x0: 0, x1: 4, y0: 6, y1: 8.3, kit: 'portrait' },
      { x0: 4.5, x1: 8.5, y0: 6, y1: 8.3, kit: 'portrait' },
    ],
  };

  it('le pas inter-rangées est MESURÉ sur les rangées du moteur, jamais recalculé', () => {
    expect(pasInterRangeeMesure(PLAN.rangees)).toBeCloseTo(6, 9);
    const champ = construireChampPose(PLAN, { tiltDeg: 25, aireTerrainM2: 200 });
    expect(champ.pasInterRangeeM).toBeCloseTo(6, 9);
  });

  it('moins de deux rangées → le pas n’est PAS mesurable : null, et on le dit', () => {
    expect(pasInterRangeeMesure([{ y0: 0 }])).toBeNull();
    expect(pasInterRangeeMesure(undefined)).toBeNull();
    const champ = construireChampPose({ ...PLAN, rangees: [{ y0: 0 }] }, { tiltDeg: 25, aireTerrainM2: 200 });
    expect(champ.pasInterRangeeM).toBeNull();
    expect(champ.nonMesure.join(' ')).toMatch(/pas inter-rangées/i);
  });

  it('le compte de modules est celui du MOTEUR (les tables ne sont jamais recomptées)', () => {
    const champ = construireChampPose(PLAN, { tiltDeg: 25, aireTerrainM2: 200 });
    expect(champ.modules).toBe(16); // et non 4 (le nombre de tables)
    expect(champ.tables).toHaveLength(4);
  });

  it('le taux d’occupation est une SORTIE : emprises du moteur ÷ terrain tracé', () => {
    const champ = construireChampPose(PLAN, { tiltDeg: 25, aireTerrainM2: 200 });
    const empriseAttendue = 4 * (4 * 2.3); // quatre tables de 4 m × 2,3 m
    expect(champ.empriseTablesM2).toBeCloseTo(empriseAttendue, 9);
    expect(champ.tauxOccupation).toBeCloseTo(empriseAttendue / 200, 9);
    expect(champ.tauxOccupation).toBeGreaterThan(0);
    expect(champ.tauxOccupation).toBeLessThan(1);
  });

  it('sans surface de terrain, le taux d’occupation vaut null — jamais 0 « par défaut »', () => {
    const champ = construireChampPose(PLAN, { tiltDeg: 25 });
    expect(champ.tauxOccupation).toBeNull();
    expect(champ.nonMesure.join(' ')).toMatch(/occupation/i);
  });

  it('pente du TERRAIN saisie → les tables montent d’autant ; absente → terrain horizontal', () => {
    const plat = construireChampPose(PLAN, { tiltDeg: 25, aireTerrainM2: 200 });
    expect(plat.tables.every((t) => t.z === 0)).toBe(true);
    expect(plat.nonMesure.join(' ')).toMatch(/pente du terrain/i);

    const pentu = construireChampPose(PLAN, { tiltDeg: 25, penteTerrainDeg: 10, aireTerrainM2: 200 });
    const bas = pentu.tables.find((t) => t.cy < 3);
    const haut = pentu.tables.find((t) => t.cy > 3);
    expect(bas && haut).toBeTruthy();
    // Avancée de 6 m sur une pente de 10° → dénivelé = 6·tan(10°).
    expect((haut as { z: number }).z - (bas as { z: number }).z).toBeCloseTo(6 * Math.tan((10 * Math.PI) / 180), 6);
  });

  it('hauteur libre saisie → toutes les tables sont posées à cette hauteur', () => {
    const champ = construireChampPose(PLAN, { tiltDeg: 15, hauteurLibreM: 2.4, aireTerrainM2: 200 });
    const bas = champ.tables.find((t) => t.cy < 3) as { z: number };
    expect(bas.z).toBeCloseTo(2.4, 9);
  });

  it('un plan vide ne fabrique rien et dit ce qui manque', () => {
    const champ = construireChampPose(null, { tiltDeg: 25 });
    expect(champ.tables).toHaveLength(0);
    expect(champ.modules).toBeNull();
    expect(champ.pasInterRangeeM).toBeNull();
    expect(champ.tauxOccupation).toBeNull();
    expect(champ.nonMesure.length).toBeGreaterThan(0);
  });

  it('les tables portent l’inclinaison SAISIE et leur kit, telles quelles', () => {
    const champ = construireChampPose(PLAN, { tiltDeg: 25, aireTerrainM2: 200 });
    for (const t of champ.tables) {
      expect(t.inclinaisonRad).toBeCloseTo((25 * Math.PI) / 180, 9);
      expect(t.kit).toBe('portrait');
      expect(t.largeurM).toBeCloseTo(4, 9);
      expect(t.profondeurM).toBeCloseTo(2.3, 9);
    }
  });
});

// CAL91 — l'OMBRIÈRE réutilise la construction de CAL89 ; la SEULE différence
// est la hauteur libre, qui n'est jamais supposée. Aucune charge, aucune
// structure n'est produite par cette construction : elle place des tables.
describe('CAL91 — ombrière : posée à la hauteur SAISIE, jamais à une hauteur supposée', () => {
  const PLAN: PlanMoteurSurface = {
    surface: 'OMBRIERE',
    modules: 24,
    rangees: [{ y0: 0 }, { y0: 2.5 }],
    tables: [
      { x0: 0, x1: 6, y0: 0, y1: 2.3, kit: 'terrain' },
      { x0: 0, x1: 6, y0: 2.5, y1: 4.8, kit: 'terrain' },
    ],
  };

  it('hauteur libre saisie → toutes les travées sont levées d’autant', () => {
    const champ = construireOmbriere(PLAN, { tiltDeg: 7, hauteurLibreM: 2.5, aireTerrainM2: 60 });
    expect(champ.tables).toHaveLength(2);
    const bas = champ.tables.find((t) => t.cy < 2) as { z: number };
    expect(bas.z).toBeCloseTo(2.5, 9);
    expect(champ.nonMesure.join(' ')).not.toMatch(/hauteur libre/i);
  });

  it('hauteur libre absente → la couverture n’est PAS levée, et le manque est dit', () => {
    const champ = construireOmbriere(PLAN, { tiltDeg: 7, aireTerrainM2: 60 });
    expect(champ.tables.every((t) => t.z === 0)).toBe(true);
    expect(champ.nonMesure.join(' ')).toMatch(/hauteur libre/i);
  });

  it('elle pave comme un toit incliné : compte, pas et taux viennent du moteur', () => {
    const champ = construireOmbriere(PLAN, { tiltDeg: 7, hauteurLibreM: 2.5, aireTerrainM2: 60 });
    expect(champ.modules).toBe(24); // le compte du moteur, pas les 2 travées
    expect(champ.pasInterRangeeM).toBeCloseTo(2.5, 9);
    expect(champ.tauxOccupation).toBeCloseTo((2 * 6 * 2.3) / 60, 9);
  });

  it('aucune charge, aucune masse, aucune structure n’est produite', () => {
    const champ = construireOmbriere(PLAN, { tiltDeg: 7, hauteurLibreM: 2.5, aireTerrainM2: 60 });
    const cles = [...Object.keys(champ), ...Object.keys(champ.tables[0])].join(' ').toLowerCase();
    for (const interdit of ['charge', 'masse', 'poteau', 'structure', 'prix']) {
      expect(cles).not.toContain(interdit);
    }
  });
});

// ACAL87 — l'aperçu de toiture est lu APRÈS un rendu réel (rappel `render`), et une
// image entièrement transparente n'est jamais rendue (null) : plus de PNG vide
// téléversé comme « Rendu 3D ».
describe('ACAL87 — capture de l’aperçu après rendu', () => {
  function carteFactice() {
    let rappel: (() => void) | null = null;
    const carte = {
      once: (_evt: 'render', cb: () => void) => { rappel = cb; return carte; },
      triggerRepaint: () => {},
      rendre: () => rappel?.(),
    };
    return carte;
  }
  const OPAQUE = new Uint8ClampedArray([10, 20, 30, 255, 0, 0, 0, 0]);
  const VIDE = new Uint8ClampedArray([0, 0, 0, 0, 0, 0, 0, 0]);

  it('snapshotAsync lit après l’événement render et rejette une image entièrement transparente', async () => {
    const carte = carteFactice();
    let lectures = 0;
    const canvas = { toDataURL: () => { lectures += 1; return 'data:image/png;base64,AAA='; } };
    const promesse = capturerApresRendu(carte, canvas, () => OPAQUE, 60_000);
    // Rien n'est lu tant que le rendu demandé n'a pas eu lieu.
    expect(lectures).toBe(0);
    carte.rendre();
    await expect(promesse).resolves.toBe('data:image/png;base64,AAA=');
    expect(lectures).toBe(1);

    const carte2 = carteFactice();
    const canvas2 = { toDataURL: () => 'data:image/png;base64,VIDE=' };
    const vide = capturerApresRendu(carte2, canvas2, () => VIDE, 60_000);
    carte2.rendre();
    await expect(vide).resolves.toBeNull();
  });

  it('imageEntierementTransparente : un seul pixel opaque suffit à garder l’image', () => {
    expect(imageEntierementTransparente(VIDE)).toBe(true);
    expect(imageEntierementTransparente(OPAQUE)).toBe(false);
    expect(imageEntierementTransparente(null)).toBe(true);
  });

  it('une carte qui lève rend null, jamais une exception', async () => {
    const carte = { once: () => { throw new Error('carte détachée'); }, triggerRepaint: () => {} };
    await expect(capturerApresRendu(carte, { toDataURL: () => 'x' }, () => OPAQUE, 10))
      .resolves.toBeNull();
  });
});

describe('ACAL433 : la grille de texture suit le rapport du panneau', () => {
  const pas = (r: number) => {
    const d = dimensionsTexture(r);
    return { d, h: (d.w - 28) / d.cols, v: (d.h - 34) / 2 / d.rowsHalf };
  };
  it('1,83 : rendu identique a aujourd hui (512 x 280, 24 colonnes, 3 demi-rangees)', () => {
    expect(dimensionsTexture(1.83)).toEqual({ w: 512, h: 280, cols: 24, rowsHalf: 3 });
  });
  it.each([1303 / 2384, 1.52, 1 / 1.52])('rapport %f : canevas au rapport, cellules carrées (écart <= 5 %)', (r) => {
    const { d, h, v } = pas(r);
    if (Math.round(r * 100) === 183) return; // 1,83 : grille d'origine conservée telle quelle (cas ci-dessus)
    expect(Math.abs(h / v - 1)).toBeLessThanOrEqual(0.05);
    expect(Math.abs(d.w / d.h / r - 1)).toBeLessThanOrEqual(0.03);
  });
  it('portrait et paysage donnent des grilles différentes (le rapport est lu)', () => {
    expect(dimensionsTexture(0.55)).not.toEqual(dimensionsTexture(1.83));
    expect(dimensionsTexture(1.52)).not.toEqual(dimensionsTexture(1.83));
  });
});

describe('ACAL410 — puces de forme : 4 pans, L refusé sur contour convexe', () => {
  it('« 4 pans » sur un contour de 4 sommets : 4 pans à la pente SAISIE, aire conservée, ids neufs', () => {
    const ring = rectRing(10, 6);
    const v = decouperContour(ring, 'hip', 30, [{ id: 'area-1' }]);
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.pans).toHaveLength(4);
    for (const p of v.pans) expect(p.pitchDeg).toBe(30);
    expect(new Set(v.pans.map((p) => p.id)).size).toBe(4);
    expect(v.pans.map((p) => p.id)).not.toContain('area-1');
    expect(sumAreaM2(v.pans.map((p) => ({ vertices: p.vertices, facingAzimuthDeg: 0 }))) / geodesicAreaM2(ring)).toBeCloseTo(1, 6);
  });

  it('« L » et « T » sur un contour CONVEXE : refus nommé, rien de produit', () => {
    for (const f of ['l_gable', 't_gable'] as const) {
      const v = decouperContour(rectRing(10, 6), f, 30, []);
      expect(v.ok).toBe(false);
      if (!v.ok) expect(v.motif).toMatch(/convexe/i);
    }
  });

  it('un clic remplace le pan actif ; un pan à obstacles est refusé sans rien changer', () => {
    let appels = 0;
    let statut = '';
    let nbObstacles = 0;
    const f = monterFormesToit({
      ancre: null,
      contour: () => rectRing(10, 6),
      pente: () => 30,
      existants: () => [{ id: 'area-1' }],
      obstacles: () => nbObstacles,
      appliquer: (pans) => void (appels += pans.length),
      setStatus: (m) => void (statut = m),
    });
    expect(f.cliquer('hip').ok).toBe(true);
    expect(appels).toBe(4);
    nbObstacles = 1;
    expect(f.cliquer('gable').ok).toBe(false);
    expect(appels).toBe(4);
    expect(statut).toMatch(/obstacles/);
  });
});

describe('ACAL435 : cibleVue', () => {
  it('les quatre cibles, cap = azimut + 180 mod 360, saut sous reduced-motion', () => {
    expect(cibleVue('dessus', 150)).toEqual({ pitch: 0, bearing: 0 });
    expect(cibleVue('sud', 150)).toEqual({ pitch: 58, bearing: 0 });
    expect(cibleVue('trois-quarts', 150)).toEqual({ pitch: 58, bearing: 45 });
    expect(cibleVue('face-panneaux', 150)).toEqual({ pitch: 58, bearing: 330 });
    expect(cibleVue('face-panneaux', 0).bearing).toBe(180);
    expect(cibleVue('face-panneaux', 200).bearing).toBe(20);
    const jumpTo = vi.fn();
    const easeTo = vi.fn();
    appliquerVue({ jumpTo, easeTo }, 'face-panneaux', 150, true);
    expect(jumpTo).toHaveBeenCalledWith({ pitch: 58, bearing: 330 });
    expect(easeTo).not.toHaveBeenCalled();
    appliquerVue({ jumpTo, easeTo }, 'dessus', 150, false);
    expect(easeTo).toHaveBeenCalledWith({ pitch: 0, bearing: 0, duration: 600, essential: true });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL528 — les rectangles de modules depuis le seul document enregistré.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL528 — modulesDuDocument', () => {
  const centres = [0, 1, 2, 3, 4, 5].map((i) => ({ cx: i * 1.2, cy: (i % 2) * 2.4 }));
  const document = (module: Record<string, unknown> | null, moduleId?: string) => ({
    modules: module ? [module] : undefined,
    zones: [{
      id: 'z1',
      geometry: { origin: [-7.6, 33.5], panels: centres, azimuthDeg: 180, tiltDeg: 15, ...(moduleId ? { moduleId } : {}) },
    }],
  });
  const ecartMax = (a: number[][][], b: number[][][]) =>
    Math.max(...a.flatMap((q, i) => q.flatMap((p, j) => [Math.abs(p[0] - b[i][j][0]), Math.abs(p[1] - b[i][j][1])])));

  it('6 modules d’un module catalogué : les MÊMES quadrilatères que panelQuadsLngLat (à 1e-9 degré)', () => {
    const doc = document({ id: 'mod-1', libelle: 'Module 720 Wc', longueurMm: 2384, largeurMm: 1303 }, 'mod-1');
    const [pan] = modulesDuDocument(doc);
    expect(pan.panId).toBe('z1');
    expect(pan.quads).toHaveLength(6);
    const attendu = panelQuadsLngLat([-7.6, 33.5], centres, 1.303, 2.384, 15, 180);
    expect(ecartMax(pan.quads, attendu)).toBeLessThan(1e-9);
    // le ré-export de scene3d.ts est la même fonction
    expect(panelQuadsViaScene3d).toBe(panelQuadsLngLat);
  });

  it('un module à dimensions inversées dans la fiche donne le même résultat (grand côté le long de la rangée)', () => {
    const a = modulesDuDocument(document({ id: 'm', longueurMm: 2384, largeurMm: 1303 }, 'm'))[0].quads;
    const b = modulesDuDocument(document({ id: 'm', longueurMm: 1303, largeurMm: 2384 }, 'm'))[0].quads;
    expect(ecartMax(a, b)).toBeLessThan(1e-12);
  });

  it('sans moduleId : le module par défaut de l’atelier, NOMMÉ', () => {
    const [pan] = modulesDuDocument(document(null));
    expect(pan.moduleNomme).toBe("module par défaut de l'atelier");
    const attendu = panelQuadsLngLat([-7.6, 33.5], centres, MODULE_ATELIER_PAR_DEFAUT.courtM, MODULE_ATELIER_PAR_DEFAUT.longM, 15, 180);
    expect(ecartMax(pan.quads, attendu)).toBeLessThan(1e-12);
  });

  it('dimensions `null` : aucun quadrilatère et le motif, jamais une dimension supposée', () => {
    const [pan] = modulesDuDocument(document({ id: 'm', libelle: 'Sans cotes', longueurMm: null, largeurMm: null }, 'm'));
    expect(pan.quads).toEqual([]);
    expect(pan.motif).toBe('dimensions du module non saisies');
  });

  it('un moduleId absent du catalogue est nommé, sans quadrilatère', () => {
    const [pan] = modulesDuDocument(document({ id: 'autre', longueurMm: 2000, largeurMm: 1000 }, 'm'));
    expect(pan.quads).toEqual([]);
    expect(pan.motif).toContain('« m »');
  });

  it('un pan sans géométrie posée n’a pas de ligne ; un document vide non plus', () => {
    expect(modulesDuDocument({ zones: [{ id: 'z1' }] })).toEqual([]);
    expect(modulesDuDocument(null)).toEqual([]);
  });
});

// ACAL579 — le visionneur CLIENT (`readOnly`) garde un triangle à chaque jointure malgré la portée.
describe('ACAL579 — readOnly ⇒ 13 triangles malgré la portée', () => {
  it('la portée n’est appliquée que dans l’atelier', () => {
    const p = { valeurM: 2.4, source: 'notice' };
    const row = () => Array.from({ length: 12 }, (_, i) => ({ la: i * 1.15, halfA: 0.565 }));
    const compter = (readOnly: boolean) => {
      let n = 0;
      poserTrianglesDeRangee(row(), 0.25, porteeAppliquee(readOnly, p), () => { n++; });
      return n;
    };
    expect(compter(true)).toBe(13);
    expect(compter(false)).toBe(7);
    const SRC_SCENE = readFileSync(resolve(process.cwd(), 'src/scripts/roofPro11/scene3d.ts'), 'utf8');
    expect(SRC_SCENE).toMatch(/porteeAppliquee\(readOnly, ctx\.activeArea\?\.\(\)\?\.porteeEntrePieds\)/);
  });
});

describe('ACAL1185 — poignées des coins au haut des murs', () => {
  const origine: [number, number] = [-7.6, 33.5];
  const cosLat = Math.cos((origine[1] * Math.PI) / 180);
  const coin = (dx: number, dy: number): [number, number] => [origine[0] + dx / (DEG2M * cosLat), origine[1] + dy / DEG2M];
  const sommets = [coin(-10, -10), coin(10, -10), coin(10, 10), coin(-10, 10)];
  // Matrice colonne-major ENU -> clip : x' = 0,05 x ; y' = 0,05 y + 0,04 z (la hauteur monte à l'écran).
  const m = [0.05, 0, 0, 0, 0, 0.05, 0, 0, 0, 0.04, 0, 0, 0, 0, 0, 1];

  it('4 sommets, bâtiment de 6 m ⇒ 4 poignées à z = 6 m ; le point écran d’une poignée désigne son coin', () => {
    const p = positionsPoignees(sommets, origine, 6);
    expect(p).toHaveLength(4);
    for (const h of p) expect(h.z).toBe(6);
    expect(p[0].x).toBeCloseTo(-10, 4);
    expect(p[0].y).toBeCloseTo(-10, 4);
    const ecran = projeterPoignees(p, m, 1000, 800);
    expect(ecran[0].x).toBeCloseTo(250, 3);
    expect(ecran[0].y).toBeCloseTo(504, 3); // 0,63 × 800 : relevée par la hauteur
    expect(coinLePlusProche(ecran, { x: 252, y: 506 }, 14)).toBe(0);
    // Le coin AU SOL (y = 600) n'est plus saisissable : la poignée n'y est pas.
    expect(coinLePlusProche(ecran, { x: 250, y: 600 }, 14)).toBeNull();
  });

  it('une poignée derrière la caméra n’a pas de position écran', () => {
    const derriere = [...m];
    derriere[15] = -1;
    expect(projeterPoignees(positionsPoignees(sommets, origine, 6), derriere, 1000, 800)).toEqual([]);
  });
});
