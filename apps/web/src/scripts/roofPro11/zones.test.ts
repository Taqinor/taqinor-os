// CAL69 — ZONES INTERDITE / RÉSERVÉE / PRÉFÉRÉE tracées dans l'atelier. Ce fichier prouve
// la partie qui FAIT la tâche, sans DOM ni carte : les trois natures se créent et se
// rééditent, elles écrivent EXACTEMENT le contrat CAL68 (`exclusionZones` :
// id/label/nature/vertices/setbackM/heightM), elles se relisent à l'identique, et — la
// garantie centrale — INTERDITE et RESERVEE produisent une obstruction (le compte de
// modules bouge), PREFEREE n'en produit AUCUNE (le compte ne bouge jamais).
import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom'; // ACAL574
import { buildingLabel, createZones } from './zones'; // ACAL574
import { motifPanExistant } from './panExistant'; // ACAL574
import { ctxDeBase, panDeTest, ptM } from './harnaisAtelier'; // ACAL574
import { fileURLToPath } from 'node:url';
import { CHEMINS_TOURNES, CLES_REFUSEES, pivoterSite } from './siteRotation'; // ACAL514
import { motifPanVerrouille } from './panVerrouille'; // ACAL520
import { boutonReporterReglages } from './zones'; // ACAL554
import {
  EXCLUSION_NATURES,
  exclusionColor,
  exclusionZoneFromDrag,
  exclusionZoneRing,
  blockingExclusionZones,
  exclusionObstructionRings,
  serializeExclusionZones,
  deserializeExclusionZones,
  withZoneNature,
  withZoneSetback,
  withZoneHeight,
  withZoneLabel,
  pivoterPan,
  redimensionnerPan,
  dupliquerPan,
  motifPasDuplication,
  idZoneCopie,
  prochainId, // ACAL64
  tousLesObstacles, // ACAL64
  nouveauPanDepuisContour, // ACAL71
  poserModuleDeDepart, // ACAL1273
  ajoutDePanEnCours, monterToitGriseSousTrace, toitExistantGeoJSON, // ACAL1329
  type ExclusionZone,
} from './zones';
import { hydrateFromDevis, serializeLayout, type SerializedLayout } from './prefill'; // ACAL64
import { type Ctx } from './context'; // ACAL64
import { lireGabaritsZone, lireGabaritsObstacle, type AreaRecord } from './types';
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';

const A: LngLat = [-7.6, 33.5];
const B: LngLat = [-7.5995, 33.5004];

describe('CAL69 — les trois natures se tracent', () => {
  it('un glissé crée un rectangle de la nature demandée, sans rien inventer d’autre', () => {
    for (const n of EXCLUSION_NATURES) {
      const z = exclusionZoneFromDrag('z1', n.id, A, B);
      expect(z.nature).toBe(n.id);
      expect(z.vertices).toHaveLength(4);
      expect(z.setbackM).toBe(0); // retrait NON saisi ⇒ 0, jamais un repli
      expect(z.heightM).toBeUndefined(); // hauteur NON renseignée
      expect(z.label).toBeUndefined();
    }
  });

  it('le code couleur est DISTINCT du rouge des obstacles, et distinct par nature', () => {
    const couleurs = EXCLUSION_NATURES.map((n) => exclusionColor(n.id));
    expect(new Set(couleurs).size).toBe(3);
    expect(couleurs).not.toContain('#ff6b6b'); // couleur des obstacles
  });
});

describe('CAL69 — chaque zone se réédite', () => {
  const base = exclusionZoneFromDrag('z1', 'INTERDITE', A, B);

  it('nature, repère, retrait et hauteur sont modifiables', () => {
    let z = withZoneNature(base, 'RESERVEE');
    z = withZoneLabel(z, '  Réserve groupe froid  ');
    z = withZoneSetback(z, 0.5);
    z = withZoneHeight(z, 1.2);
    expect(z.nature).toBe('RESERVEE');
    expect(z.label).toBe('Réserve groupe froid');
    expect(z.setbackM).toBe(0.5);
    expect(z.heightM).toBe(1.2);
  });

  it('effacer une valeur la retire, elle ne devient jamais un nombre de repli', () => {
    let z = withZoneHeight(withZoneSetback(base, 0.5), 1.2);
    z = withZoneSetback(z, null);
    z = withZoneHeight(z, null);
    z = withZoneLabel(z, '');
    expect(z.setbackM).toBe(0);
    expect(z.heightM).toBeUndefined();
    expect(z.label).toBeUndefined();
  });
});

describe('CAL69 — LA garantie : le compte bouge pour INTERDITE/RESERVEE, jamais pour PREFEREE', () => {
  const interdite = exclusionZoneFromDrag('z1', 'INTERDITE', A, B);
  const reservee = exclusionZoneFromDrag('z2', 'RESERVEE', A, B);
  const preferee = exclusionZoneFromDrag('z3', 'PREFEREE', A, B);

  it('INTERDITE et RESERVEE retirent de la surface posable', () => {
    expect(blockingExclusionZones([interdite, reservee, preferee]).map((z) => z.id)).toEqual(['z1', 'z2']);
    expect(exclusionObstructionRings([interdite])).toHaveLength(1);
    expect(exclusionObstructionRings([reservee])).toHaveLength(1);
  });

  it('PREFEREE ne produit AUCUNE obstruction — le compte ne peut pas bouger', () => {
    expect(blockingExclusionZones([preferee])).toEqual([]);
    expect(exclusionObstructionRings([preferee])).toEqual([]);
    // Ajouter une préférée à un jeu de zones ne change pas les obstructions, à l'identique.
    expect(exclusionObstructionRings([interdite, preferee])).toEqual(exclusionObstructionRings([interdite]));
  });

  it('aucune zone / liste absente ⇒ aucune obstruction (comportement d’aujourd’hui)', () => {
    expect(exclusionObstructionRings([])).toEqual([]);
    expect(exclusionObstructionRings(null)).toEqual([]);
    expect(exclusionObstructionRings(undefined)).toEqual([]);
  });

  it('le retrait SAISI dilate l’anneau, il n’est pas ignoré', () => {
    const sans = exclusionZoneRing(interdite)!;
    const avec = exclusionZoneRing(withZoneSetback(interdite, 1))!;
    // Le sommet dilaté est strictement plus loin du centre que le sommet d'origine.
    const cx = sans.reduce((a, v) => a + v[0], 0) / sans.length;
    const cy = sans.reduce((a, v) => a + v[1], 0) / sans.length;
    const d = (v: LngLat) => Math.hypot(v[0] - cx, v[1] - cy);
    expect(d(avec[0])).toBeGreaterThan(d(sans[0]));
  });

  it('une zone de moins de 3 sommets ne se dessine pas et n’obstrue rien', () => {
    const bancale: ExclusionZone = { id: 'z9', nature: 'INTERDITE', vertices: [A], setbackM: 0 };
    expect(exclusionZoneRing(bancale)).toBeNull();
    expect(exclusionObstructionRings([bancale])).toEqual([]);
  });
});

describe('CAL69 — le document écrit EXACTEMENT le contrat CAL68 et se recharge', () => {
  it('les clés écrites sont celles du contrat, et rien d’autre', () => {
    let z = exclusionZoneFromDrag('SERVITUDE-EST', 'INTERDITE', A, B);
    z = withZoneLabel(withZoneSetback(z, 0.5), 'Servitude est');
    const [written] = serializeExclusionZones([z]);
    expect(Object.keys(written).sort()).toEqual(['heightM', 'id', 'label', 'nature', 'setbackM', 'vertices']);
    expect(written.nature).toBe('INTERDITE');
    expect(written.setbackM).toBe(0.5);
    expect(written.heightM).toBeNull(); // non renseignée ⇒ null explicite
  });

  it('aller-retour : ce qui est écrit se relit à l’identique', () => {
    const list = [
      withZoneSetback(exclusionZoneFromDrag('z1', 'INTERDITE', A, B), 0.5),
      withZoneHeight(exclusionZoneFromDrag('z2', 'RESERVEE', A, B), 1.2),
      exclusionZoneFromDrag('z3', 'PREFEREE', A, B),
    ];
    expect(deserializeExclusionZones(serializeExclusionZones(list))).toEqual(list);
  });

  it('un document douteux rend une liste vide, jamais une exception ni une zone inventée', () => {
    expect(deserializeExclusionZones(null)).toEqual([]);
    expect(deserializeExclusionZones({})).toEqual([]);
    expect(deserializeExclusionZones('nope')).toEqual([]);
    expect(deserializeExclusionZones([{ id: 'x', nature: 'INCONNUE', vertices: [A, B, A] }])).toEqual([]);
    expect(deserializeExclusionZones([{ id: 'x', nature: 'INTERDITE', vertices: [A] }])).toEqual([]);
    expect(deserializeExclusionZones([{ nature: 'INTERDITE', vertices: [A, B, A] }])).toEqual([]);
  });

  it('ENVELOPPE n’est pas une zone traçable ici (c’est le contour)', () => {
    expect(EXCLUSION_NATURES.map((n) => n.id)).toEqual(['INTERDITE', 'RESERVEE', 'PREFEREE']);
    expect(serializeExclusionZones([{ id: 'e', nature: 'ENVELOPPE', vertices: [A, B, A], setbackM: 0 } as unknown as ExclusionZone])).toEqual([]);
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX97 — COTES EXACTES D'UN PAN ET ROTATION D'UN BLOC. La géométrie pure (rotation de
// 360°, centroïde conservé) est prouvée dans `snap.test.ts` ; ici on prouve ce qui est
// PROPRE AU PAN : les obstacles suivent la rotation, et un refus NOMME le pan.
// ————————————————————————————————————————————————————————————————————————
const PAN: LngLat[] = [
  [-7.6, 33.5],
  [-7.599, 33.5],
  [-7.599, 33.5005],
  [-7.6, 33.5005],
];

const obstacle = (id: string, lng: number, lat: number): Obstacle => ({
  id,
  centerLng: lng,
  centerLat: lat,
  lengthM: 2,
  widthM: 1.5,
});

describe('CALX97 — pivoterPan : les obstacles suivent la rotation', () => {
  it('le centre de chaque obstacle tourne avec le contour', () => {
    const pan = { vertices: PAN, obstacles: [obstacle('o1', -7.5992, 33.5001)] };
    const v = pivoterPan(pan, 90, 'Pan 1');
    expect(v.ok).toBe(true);
    if (!v.ok) throw new Error('rotation attendue');
    expect(v.geometrie.obstacles).toHaveLength(1);
    const avant = pan.obstacles[0];
    const apres = v.geometrie.obstacles[0];
    expect(apres.id).toBe('o1');
    expect(apres.centerLng === avant.centerLng && apres.centerLat === avant.centerLat).toBe(false);
    // Les dimensions SAISIES de l'obstacle ne changent jamais (aucune orientation inventée).
    expect(apres.lengthM).toBe(2);
    expect(apres.widthM).toBe(1.5);
  });

  it('un tour complet ramène contour ET obstacles à leur place', () => {
    const o = obstacle('o1', -7.5992, 33.5001);
    let g = { vertices: PAN.map((v) => [v[0], v[1]] as LngLat), obstacles: [o] };
    for (let i = 0; i < 4; i++) {
      const v = pivoterPan(g, 90, 'Pan 1');
      if (!v.ok) throw new Error('rotation attendue');
      g = v.geometrie;
    }
    g.vertices.forEach((v, i) => {
      expect(Math.abs(v[0] - PAN[i][0])).toBeLessThan(1e-9);
      expect(Math.abs(v[1] - PAN[i][1])).toBeLessThan(1e-9);
    });
    expect(Math.abs(g.obstacles[0].centerLng - o.centerLng)).toBeLessThan(1e-9);
    expect(Math.abs(g.obstacles[0].centerLat - o.centerLat)).toBeLessThan(1e-9);
  });

  it('un pan sans obstacle tourne sans rien fabriquer', () => {
    const v = pivoterPan({ vertices: PAN, obstacles: [] }, 45, 'Pan 1');
    expect(v.ok).toBe(true);
    if (!v.ok) throw new Error('rotation attendue');
    expect(v.geometrie.obstacles).toEqual([]);
  });

  it('ne modifie PAS le pan d’origine (transformation pure)', () => {
    const o = obstacle('o1', -7.5992, 33.5001);
    const pan = { vertices: PAN.map((v) => [v[0], v[1]] as LngLat), obstacles: [o] };
    const copieSommets = pan.vertices.map((v) => [v[0], v[1]] as LngLat);
    pivoterPan(pan, 33, 'Pan 1');
    expect(pan.vertices).toEqual(copieSommets);
    expect(pan.obstacles[0].centerLng).toBe(-7.5992);
  });

  it('REFUSE en nommant le pan quand il n’a pas de contour ou que l’angle est illisible', () => {
    const sansContour = pivoterPan({ vertices: [], obstacles: [] }, 45, 'Pan 3');
    expect(sansContour.ok).toBe(false);
    if (!sansContour.ok) {
      expect(sansContour.motif).toContain('Pan 3');
      expect(sansContour.motif).toContain('contour fermé');
    }
    const sansAngle = pivoterPan({ vertices: PAN, obstacles: [] }, Number.NaN, 'Pan 3');
    expect(sansAngle.ok).toBe(false);
    if (!sansAngle.ok) {
      expect(sansAngle.motif).toContain('Pan 3');
      expect(sansAngle.motif).toContain('angle');
    }
  });
});

describe('CALX97 — redimensionnerPan', () => {
  it('applique les cotes et laisse les obstacles là où ils ont été relevés', () => {
    const o = obstacle('o1', -7.5992, 33.5001);
    const v = redimensionnerPan({ vertices: PAN, obstacles: [o] }, 30, 120, 'Pan 1');
    expect(v.ok).toBe(true);
    if (!v.ok) throw new Error('redimensionnement attendu');
    expect(v.geometrie.vertices).toHaveLength(4);
    expect(v.geometrie.obstacles[0].centerLng).toBe(o.centerLng);
    expect(v.geometrie.obstacles[0].centerLat).toBe(o.centerLat);
  });

  it('REFUSE en NOMMANT le pan quand le contour n’est pas un quadrilatère', () => {
    const v = redimensionnerPan({ vertices: PAN.slice(0, 3), obstacles: [] }, 30, 120, 'Pan 2');
    expect(v.ok).toBe(false);
    if (v.ok) throw new Error('refus attendu');
    expect(v.motif).toContain('Pan 2');
    expect(v.motif).toContain('4 côtés');
  });

  it('REFUSE en NOMMANT le pan quand une cote manque', () => {
    const v = redimensionnerPan({ vertices: PAN, obstacles: [] }, 30, Number.NaN, 'Pan 2');
    expect(v.ok).toBe(false);
    if (v.ok) throw new Error('refus attendu');
    expect(v.motif).toContain('Pan 2');
    expect(v.motif).toContain('longueur');
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX98 — DUPLIQUER UN PAN AVEC SES OBSTACLES ET SES RÉGLAGES.
// ————————————————————————————————————————————————————————————————————————
const panSource = (): AreaRecord => ({
  id: 'area-1',
  label: 'Zone A',
  vertices: PAN.map((v) => [v[0], v[1]] as LngLat),
  obstacles: [obstacle('obs-1', -7.5992, 33.5001), obstacle('obs-2', -7.5996, 33.5003)],
  roofType: 'pitched',
  pitchDeg: 27,
  facingAzimuthDeg: 143,
  facingManual: true,
  neededPanels: 42,
  neededAuto: false,
  result: { panels: 42, kwc: 30.24, annualKwh: 48000, savingsLow: 1, savingsHigh: 2 },
  renderPlan: null,
  buildingId: 'Hangar Nord',
  edges: [{ index: 0, type: 'egout' }] as AreaRecord['edges'],
});

describe('CALX98 — motifPasDuplication : aucun décalage supposé', () => {
  it('un pas absent, nul ou négatif EMPÊCHE la duplication et dit pourquoi', () => {
    for (const v of [Number.NaN, 0, -3]) {
      const motif = motifPasDuplication(v);
      expect(motif).not.toBeNull();
      expect(motif).toContain('Saisissez le décalage');
    }
  });

  it('un pas saisi > 0 lève l’empêchement', () => {
    expect(motifPasDuplication(5)).toBeNull();
    expect(motifPasDuplication(0.5)).toBeNull();
  });
});

describe('CALX98 — dupliquerPan', () => {
  it('sans pas saisi, ne crée RIEN et rend le motif affiché à côté du bouton', () => {
    const v = dupliquerPan(panSource(), 'area-copie-1', Number.NaN);
    expect(v.ok).toBe(false);
    if (v.ok) throw new Error('refus attendu');
    expect(v.motif).toBe(motifPasDuplication(Number.NaN));
  });

  it('la zone créée a un id NEUF et le MÊME nombre d’obstacles', () => {
    const source = panSource();
    const v = dupliquerPan(source, 'area-copie-1', 10);
    expect(v.ok).toBe(true);
    if (!v.ok) throw new Error('duplication attendue');
    expect(v.zone.id).toBe('area-copie-1');
    expect(v.zone.id).not.toBe(source.id);
    expect(v.zone.obstacles).toHaveLength(source.obstacles.length);
    // Les obstacles de la copie portent leurs PROPRES identifiants.
    expect(v.zone.obstacles.map((o) => o.id)).toEqual(['area-copie-1-obs-1', 'area-copie-1-obs-2']);
    expect(v.zone.vertices).toHaveLength(source.vertices.length);
  });

  it('la zone d’origine est INCHANGÉE', () => {
    const source = panSource();
    const avant = JSON.parse(JSON.stringify(source));
    dupliquerPan(source, 'area-copie-1', 10);
    expect(JSON.parse(JSON.stringify(source))).toEqual(avant);
  });

  it('recopie les réglages nommés par la tâche', () => {
    const source = panSource();
    const v = dupliquerPan(source, 'area-copie-1', 10);
    if (!v.ok) throw new Error('duplication attendue');
    expect(v.zone.roofType).toBe('pitched');
    expect(v.zone.pitchDeg).toBe(27);
    expect(v.zone.facingAzimuthDeg).toBe(143);
    expect(v.zone.facingManual).toBe(true);
    expect(v.zone.buildingId).toBe('Hangar Nord');
    expect(v.zone.edges).toEqual(source.edges);
    expect(v.zone.edges).not.toBe(source.edges); // copie, pas la même référence
  });

  it('R3-24 : la copie garde le MODULE du pan d’origine (pas le module par défaut de l’atelier)', () => {
    const v = dupliquerPan({ ...panSource(), moduleId: 'jinko-710' }, 'area-copie-1', 10);
    if (!v.ok) throw new Error('duplication attendue');
    expect(v.zone.moduleId).toBe('jinko-710');
    // Source sans module (= défaut de l'atelier) : la copie n'en invente aucun.
    const sans = dupliquerPan(panSource(), 'area-copie-2', 10);
    if (!sans.ok) throw new Error('duplication attendue');
    expect('moduleId' in sans.zone).toBe(false);
  });

  it('CALX98 : la copie garde les RÉGLAGES PHYSIQUES du pan (provenance de la pente, pavage, portée, châssis) mais reste un pan NEUF', () => {
    const reglages = {
      pitchSource: { source: 'saisie', ref: 'visite' },
      coupuresPavage: { rangs: [2] },
      porteeEntrePieds: { valeurM: 1.2 },
      chassis: { type: 'portrait' },
    };
    const source = {
      ...panSource(), ...reglages, existant: true, anneeMiseEnService: 2019, verrouille: true,
    } as unknown as AreaRecord;
    const v = dupliquerPan(source, 'area-copie-1', 10);
    if (!v.ok) throw new Error('duplication attendue');
    const z = v.zone as unknown as Record<string, unknown>;
    for (const [cle, valeur] of Object.entries(reglages)) {
      expect(z[cle]).toEqual(valeur);
      expect(z[cle]).not.toBe((source as unknown as Record<string, unknown>)[cle]); // copie profonde
    }
    // Une copie est un pan NEUF et modifiable : jamais « existant » (il sortirait du devis), jamais verrouillée.
    expect('existant' in z).toBe(false);
    expect('anneeMiseEnService' in z).toBe(false);
    expect('verrouille' in z).toBe(false);
  });

  it('ne recopie AUCUN résultat calculé (ce serait un chiffre inventé)', () => {
    const v = dupliquerPan(panSource(), 'area-copie-1', 10);
    if (!v.ok) throw new Error('duplication attendue');
    expect(v.zone.result).toBeNull();
    expect(v.zone.renderPlan).toBeNull();
    expect(v.zone.neededPanels).toBe(0);
    expect(v.zone.neededAuto).toBe(true);
  });

  it('décale la copie du pas saisi, en TRANSLATION RIGIDE (forme identique)', () => {
    const source = panSource();
    const v = dupliquerPan(source, 'area-copie-1', 10);
    if (!v.ok) throw new Error('duplication attendue');
    const decalages = v.zone.vertices.map((p, i) => p[0] - source.vertices[i][0]);
    // Le même écart de longitude pour tous les points : la copie garde exactement la forme.
    decalages.forEach((d) => expect(d).toBeCloseTo(decalages[0], 15));
    expect(decalages[0]).toBeGreaterThan(0); // vers l'est, comme la duplication d'obstacle
    // Les latitudes ne bougent pas, et les obstacles subissent le MÊME décalage.
    v.zone.vertices.forEach((p, i) => expect(p[1]).toBe(source.vertices[i][1]));
    v.zone.obstacles.forEach((o, i) => {
      expect(o.centerLng - source.obstacles[i].centerLng).toBeCloseTo(decalages[0], 15);
      expect(o.centerLat).toBe(source.obstacles[i].centerLat);
    });
  });

  it('refuse un pan sans contour fermé, en disant pourquoi', () => {
    const v = dupliquerPan({ ...panSource(), vertices: [] }, 'area-copie-1', 10);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.motif).toContain('contour fermé');
  });

  it('un pan sans obstacle donne une copie sans obstacle', () => {
    const v = dupliquerPan({ ...panSource(), obstacles: [] }, 'area-copie-1', 10);
    if (!v.ok) throw new Error('duplication attendue');
    expect(v.zone.obstacles).toEqual([]);
  });
});

describe('CALX98 — idZoneCopie : jamais de collision avec le compteur de l’entrée', () => {
  it('n’emprunte pas l’espace de noms « area-N » de « + Ajouter une zone »', () => {
    expect(idZoneCopie([{ id: 'area-1' }, { id: 'area-2' }])).toBe('area-copie-1');
  });

  it('saute les identifiants déjà pris', () => {
    expect(idZoneCopie([{ id: 'area-copie-1' }, { id: 'area-copie-2' }])).toBe('area-copie-3');
  });

  it('tient sur une liste vide ou absente', () => {
    expect(idZoneCopie([])).toBe('area-copie-1');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL64 — UNE fabrique d'identifiants : un dossier rouvert (area-1, area-2, obs-1, obs-2,
// zone-1) ne produit jamais un identifiant en double en ajoutant un pan, un obstacle, une
// zone ou un objet d'environnement.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL64 — prochainId sur un dossier rouvert', () => {
  const carre = (x: number): LngLat[] => [[x, 0], [x + 0.0001, 0], [x + 0.0001, 0.0001], [x, 0.0001]];
  function documentRouvert(): SerializedLayout {
    const pan = (id: string, x: number, obstacles: unknown[]) => ({
      id, label: id, vertices: carre(x), obstacles, roofType: 'flat', pitchDeg: 10, facingAzimuthDeg: 180,
      facingManual: false, neededPanels: 0, neededAuto: true,
    });
    const obs = (id: string) => ({ id, centerLng: 0, centerLat: 0, lengthM: 1, widthM: 1 });
    return {
      version: 2, pin: null, outline: [], billKwh: null, activeAreaId: 'area-1',
      zones: [pan('area-1', 0, [obs('obs-1')]), pan('area-2', 1, [obs('obs-2')])],
      exclusionZones: [{ id: 'zone-1', nature: 'INTERDITE', vertices: carre(2), setbackM: 0, heightM: null }],
      environment: [{ id: 'env-4', kind: 'arbre', centerLng: 0, centerLat: 0 }],
    } as unknown as SerializedLayout;
  }

  it('hydrater area-1/area-2, obs-1/obs-2, zone-1 puis ajouter pan, obstacle, zone → ids distincts, serializeLayout émet deux contours distincts', () => {
    const h = hydrateFromDevis({ id: 1, geometrie: { roof_layout: documentRouvert() }, cibleVendue: false });
    const areas = h.zones!;
    const actif = areas[0];
    const ctx = {
      areas, activeAreaId: actif.id, vertices: actif.vertices, obstacles: actif.obstacles, roofType: 'flat',
      pitchDeg: 10, facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true,
      layoutPlan: null, layoutOptimalCount: 0,
      exclusionZones: deserializeExclusionZones(documentRouvert().exclusionZones),
      environment: [{ id: 'env-4' }],
    } as unknown as Ctx;
    // Les identifiants NEUFS, tels que l'atelier les fabrique désormais.
    expect(prochainId('area', ctx.areas)).toBe('area-3');
    expect(prochainId('obs', tousLesObstacles(ctx))).toBe('obs-3');
    expect(prochainId('zone', ctx.exclusionZones ?? [])).toBe('zone-2');
    expect(prochainId('env', ctx.environment ?? [])).toBe('env-5');
    // Le nouveau pan rejoint le document SANS écraser area-2 : trois contours distincts.
    areas.push({ ...areas[1], id: prochainId('area', areas), label: 'Zone 3', vertices: carre(5), obstacles: [] });
    const doc = serializeLayout(ctx);
    expect(doc.zones.map((z) => z.id)).toEqual(['area-1', 'area-2', 'area-3']);
    expect(doc.zones[1].vertices).toEqual(carre(1));
    expect(doc.zones[2].vertices).toEqual(carre(5));
  });

  it('un compteur de session repartant de zéro (le défaut d’avant) recréerait area-2 : serializeLayout le REFUSE en le nommant', () => {
    const h = hydrateFromDevis({ id: 1, geometrie: { roof_layout: documentRouvert() }, cibleVendue: false });
    const areas = h.zones!;
    areas.push({ ...areas[1], vertices: carre(5) }); // « area-2 » en double
    const ctx = {
      areas, activeAreaId: areas[0].id, vertices: areas[0].vertices, obstacles: [], roofType: 'flat', pitchDeg: 10,
      facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, layoutPlan: null, layoutOptimalCount: 0,
    } as unknown as Ctx;
    expect(() => serializeLayout(ctx)).toThrow(/Deux pans portent l'identifiant « area-2 »/);
  });

  it('les identifiants d’une autre forme sont ignorés (area-copie-1, sh-1)', () => {
    expect(prochainId('area', [{ id: 'area-copie-4' }, { id: 'area-2' }])).toBe('area-3');
    expect(prochainId('obs', [])).toBe('obs-1');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL71 — un contour géoréférencé devient un nouveau pan ; refusé s'il se croise.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL71 — nouveauPanDepuisContour', () => {
  const carre: [number, number][] = [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5002], [-7.6, 33.5002]];

  it('nouveauPanDepuisContour : carré → pan fermé ; papillon → refus nommé', () => {
    const ok = nouveauPanDepuisContour(carre, [{ id: 'area-1' }, { id: 'area-2' }]);
    expect(ok.ok).toBe(true);
    if (!ok.ok) return;
    expect(ok.pan.id).toBe('area-3');
    expect(ok.pan.vertices).toEqual(carre);
    expect(ok.pan.vertices.length).toBeGreaterThanOrEqual(3);

    // Nœud papillon : deux sommets permutés, le contour se croise.
    const papillon: [number, number][] = [carre[0], carre[2], carre[1], carre[3]];
    const refus = nouveauPanDepuisContour(papillon, [{ id: 'area-1' }]);
    expect(refus.ok).toBe(false);
    if (refus.ok) return;
    expect(refus.motif).toMatch(/se croise/);
  });

  it('hors amplitude GPS ou moins de trois sommets : refus nommé, aucun pan', () => {
    const hors = nouveauPanDepuisContour([[-7.6, 33.5], [-7.5, 95], [-7.4, 33.6]], []);
    expect(hors.ok).toBe(false);
    if (!hors.ok) expect(hors.motif).toMatch(/amplitude GPS/);
    expect(nouveauPanDepuisContour([[-7.6, 33.5], [-7.5, 33.5]], []).ok).toBe(false);
    expect(nouveauPanDepuisContour('pas un contour', []).ok).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL1273 — le module de départ est POSÉ dans le document (pan issu d'un contour, document
// relu sans module) : jamais un pan sans `moduleId` qui retomberait sur le 720 Wc au rechargement.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL1273 — module de départ posé dans le document', () => {
  const m710 = { id: 'produit-7', produitId: 7, libelle: 'Module 710 W', longueurMm: 2384, largeurMm: 1303, epaisseurMm: 33, poidsKg: 38, pmaxWc: 710, source: 'fiche' };
  const carre: [number, number][] = [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5002], [-7.6, 33.5002]];

  it('pan issu d’un contour ⇒ moduleId de départ', () => {
    const v = nouveauPanDepuisContour(carre, [{ id: 'area-1' }], m710);
    expect(v.ok && v.pan.moduleId).toBe('produit-7');
    const sans = nouveauPanDepuisContour(carre, [{ id: 'area-1' }], null); // sans catalogue : 720 Wc NOMMÉ
    expect(sans.ok && 'moduleId' in sans.pan).toBe(false);
  });

  it('document de calepinage sans module ⇒ module de départ posé à l’hydratation, puis écrit au document', () => {
    const doc = { version: 1, zones: [{ id: 'area-1', label: 'Zone 1', vertices: carre, obstacles: [], roofType: 'flat', pitchDeg: 22, facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true }] } as unknown as SerializedLayout;
    const pans = hydrateFromDevis({ id: null, geometrie: { roof_layout: doc }, cibleVendue: false }).zones as AreaRecord[];
    expect(pans[0].moduleId).toBeUndefined(); // le document relu n'en porte aucun
    poserModuleDeDepart(pans, doc.zones, m710);
    expect(pans.map((p) => p.moduleId)).toEqual(['produit-7']);
    // Un document qui DÉSIGNE déjà un module reste tel quel ; une installation existante n'est pas la nôtre.
    const choisi = [panDeTest('area-1', { moduleId: 'produit-9' }), panDeTest('area-2')];
    poserModuleDeDepart(choisi, [{ geometry: { moduleId: 'produit-9' } }, {}], m710);
    expect(choisi.map((p) => p.moduleId)).toEqual(['produit-9', undefined]);
    const existant = [panDeTest('area-1', { existant: true })];
    poserModuleDeDepart(existant, [{}], m710);
    expect(existant[0].moduleId).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL1329 — ajouter un pan sur un toit existant : le toit reste dessiné (grisé) sous le tracé, et aucun document
// (brouillon, enregistrement) ne porte le pan avant son dernier point.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL1329 — ajout d’un pan sur un toit existant', () => {
  const toit = panDeTest('area-1');
  const neuf = panDeTest('area-2', { vertices: [] });

  it('ajout en cours : du premier clic au dernier point d’un pan ajouté, jamais pour le premier toit', () => {
    expect(ajoutDePanEnCours([toit, neuf], 'area-2', false)).toBe(true);
    expect(ajoutDePanEnCours([toit, neuf], 'area-2', true)).toBe(false); // dernier point posé
    expect(ajoutDePanEnCours([panDeTest('area-1', { vertices: [] })], 'area-1', false)).toBe(false); // premier toit
  });

  it('le toit existant reste dessiné, grisé, pendant le tracé ; le tracé du client revient ensuite', () => {
    expect(toitExistantGeoJSON([toit, neuf], 'area-2').features).toHaveLength(1);
    const peint: Record<string, string> = {};
    let donnees: unknown = null;
    let ecouteur: (e: { sourceId?: string }) => void = () => {};
    const restaurer = vi.fn();
    const etat = { areas: [toit, neuf], activeAreaId: 'area-2', closed: false };
    monterToitGriseSousTrace({
      getSource: () => ({ setData: (d: never) => { donnees = d; } }),
      getLayer: () => ({}),
      setPaintProperty: (id: string, _n: string, v: string) => { peint[id] = v; },
      setLayoutProperty: vi.fn(),
      on: (_t: string, fn: (e: { sourceId?: string }) => void) => { ecouteur = fn; },
    }, () => etat, '#f3cc66', restaurer);
    ecouteur({ sourceId: 'rp9-pts' });
    expect((donnees as { features: unknown[] }).features).toHaveLength(1);
    expect(peint['rp9-ref-contour-line']).toBe('#9aa0bb');
    etat.closed = true; // dernier point
    ecouteur({ sourceId: 'rp9-pts' });
    expect(peint['rp9-ref-contour-line']).toBe('#f3cc66');
    expect(restaurer).toHaveBeenCalledTimes(1);
  });
});

describe('ACAL291 — une zone posée depuis un gabarit réglementaire porte sa source', () => {
  const SECTION = {
    coupe_feu: {
      libelle: 'Bande coupe-feu', nature: 'INTERDITE', genre: 'bande', largeur_m: 1, cote: 'nord',
      retrait_m: 0.5, hauteur_m: 0.2, source: 'Note de service SDIS n°7',
    },
    sans_source: { libelle: 'Servitude', nature: 'RESERVEE', genre: 'polygone', sommets: [[0, 0], [1, 0], [1, 1]] },
    cheminee: { libelle: 'Cheminée', nature: 'INTERDITE', forme: 'rectangle', longueur_m: 1, largeur_m: 1, source: 'catalogue' },
    souche: { libelle: 'Souche ronde', nature: 'INTERDITE', genre: 'polygone', forme: 'cercle', rayon_m: 0.4, source: 'catalogue' },
  };

  it('zone posée depuis un gabarit porte sa source et la ressort au même octet après serialize → deserialize → serialize', () => {
    const { gabarits } = lireGabaritsZone(SECTION);
    const g = gabarits.find((x) => x.cle === 'coupe_feu')!;
    const zone = exclusionZoneFromDrag('zone-1', g.nature, A, B, g);
    expect(zone).toMatchObject({
      label: 'Bande coupe-feu', nature: 'INTERDITE', setbackM: 0.5, heightM: 0.2, source: 'Note de service SDIS n°7',
    });
    const un = serializeExclusionZones([zone]);
    expect(un[0].source).toBe('Note de service SDIS n°7');
    const deux = serializeExclusionZones(deserializeExclusionZones(un));
    expect(JSON.stringify(deux)).toBe(JSON.stringify(un));
  });

  it('une zone dessinée sans gabarit n’a pas de source', () => {
    const zone = exclusionZoneFromDrag('zone-2', 'INTERDITE', A, B);
    expect('source' in zone).toBe(false);
    expect('source' in serializeExclusionZones([zone])[0]).toBe(false);
  });

  it('lireGabaritsZone ignore les gabarits d’obstacle et refuse un gabarit sans source', () => {
    const { gabarits, refuses } = lireGabaritsZone(SECTION);
    expect(gabarits.map((g) => g.cle)).toEqual(['coupe_feu']);
    expect(refuses.map((r) => r.cle)).toEqual(['sans_source']);
    expect(refuses[0].motif).toContain('source');
    // Le jumeau obstacle reste inchangé : il lit toujours la cheminée.
    expect(lireGabaritsObstacle(SECTION).gabarits.some((g) => g.cle === 'cheminee')).toBe(true);
    // Section absente / bancale : l'état vide, jamais une zone inventée.
    expect(lireGabaritsZone(undefined)).toEqual({ gabarits: [], refuses: [] });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL514 — pivoterSite : le site entier tourne autour du barycentre de ses pans.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL514 — pivoterSite', () => {
  const site = () => ({
    pin: { lat: 33.58, lng: -7.62 },
    outline: [[33.5801, -7.6201], [33.5801, -7.6199], [33.5799, -7.6199]],
    zones: [
      {
        id: 'z1', label: 'Pan 1', facingAzimuthDeg: 180,
        vertices: [[-7.6201, 33.5801], [-7.6199, 33.5801], [-7.6199, 33.5799], [-7.6201, 33.5799]],
        obstacles: [
          { id: 'o1', centerLng: -7.6200, centerLat: 33.5800 },
          { id: 'o2', centerLng: -7.62005, centerLat: 33.58005, contour: [[-7.62006, 33.58004], [-7.62004, 33.58004], [-7.62004, 33.58006]] },
        ],
        geometry: { origin: [-7.62, 33.58], count: 0 },
      },
      { id: 'z2', facingAzimuthDeg: 90, vertices: [[-7.6198, 33.5801], [-7.6196, 33.5801], [-7.6196, 33.5799]], obstacles: [] },
    ],
    environment: [{ id: 'e1', centerLng: -7.6195, centerLat: 33.5802, footprint: [[-7.6196, 33.5801], [-7.6194, 33.5803]] }],
    exclusionZones: [{ id: 'x1', vertices: [[-7.6200, 33.5800], [-7.6199, 33.5800], [-7.6199, 33.5799]], axe: [[-7.6200, 33.5800], [-7.6199, 33.5799]] }],
    measurements: [{ id: 'm1', points: [[-7.6201, 33.5801], [-7.6197, 33.5800]] }],
    parcelle: { vertices: [[-7.63, 33.59], [-7.61, 33.59]] },
    reperesChantier: [{ id: 'r1', point: [-7.62008, 33.58008] }], // ACAL599
  });
  const maxEcart = (a: unknown, b: unknown): number => {
    if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b);
    if (Array.isArray(a) && Array.isArray(b)) return Math.max(0, ...a.map((x, i) => maxEcart(x, b[i])));
    if (a && b && typeof a === 'object' && typeof b === 'object') {
      return Math.max(0, ...Object.keys(a).map((k) => maxEcart((a as never)[k], (b as never)[k])));
    }
    return a === b ? 0 : Infinity;
  };

  it('+90 puis -90 rend le document à 1e-9 près, tout y compris axes, empreintes, contours, mesures', () => {
    const d = site();
    const a = pivoterSite(d, 90);
    expect(a.ok).toBe(true);
    if (!a.ok) return;
    expect(maxEcart(a.site, d)).toBeGreaterThan(1e-6); // ça a bien bougé
    const b = pivoterSite(a.site, -90);
    expect(b.ok).toBe(true);
    if (b.ok) expect(maxEcart(b.site, d)).toBeLessThan(1e-9);
  });

  it('les faces augmentent de 90, l’épingle et la parcelle restent en place', () => {
    const d = site();
    const a = pivoterSite(d, 90);
    if (!a.ok) throw new Error(a.motif);
    const zs = a.site.zones as Array<{ facingAzimuthDeg: number }>;
    expect(zs.map((z) => z.facingAzimuthDeg)).toEqual([270, 180]);
    expect(a.site.pin).toEqual(d.pin);
    expect(a.site.parcelle).toEqual(d.parcelle);
    expect((a.site.reperesChantier as Array<{ point: number[] }>)[0].point).not.toEqual(d.reperesChantier[0].point);
    expect(d.zones[0].facingAzimuthDeg).toBe(180); // l’entrée n’est jamais modifiée
  });

  it('un pan avec panneaux posés refuse TOUT le site en le nommant', () => {
    const d = site();
    (d.zones[1] as Record<string, unknown>).geometry = { count: 4 };
    const r = pivoterSite(d, 90);
    expect(r).toEqual({ ok: false, motif: 'Pan 2 : des panneaux sont posés — retirez la pose avant de pivoter le site.' });
  });

  it('electrical / poseSurfaces / shadeObstructions / underlay refusent en nommant la clé', () => {
    for (const cle of CLES_REFUSEES) {
      const r = pivoterSite({ ...site(), [cle]: cle === 'electrical' ? { equipements: [{}] } : [{}] }, 90);
      expect(r).toEqual({ ok: false, motif: `Le site porte \`${cle}\` : rien à pivoter sans le corrompre.` });
    }
  });

  it('un angle illisible est refusé', () => {
    const r = pivoterSite(site(), Number.NaN);
    expect(r.ok).toBe(false);
  });

  it('les chemins tournés + refusés + exemptés couvrent CHEMINS_TRANSLATES du serveur', () => {
    const py = readFileSync(fileURLToPath(new URL(
      '../../../../../backend/django_core/apps/calepinage/services/repere.py', import.meta.url)), 'utf8');
    const bloc = py.slice(py.indexOf('CHEMINS_TRANSLATES = {'), py.indexOf('}', py.indexOf('CHEMINS_TRANSLATES = {')));
    const serveur = [...bloc.matchAll(/^\s+'([^']+)':/gm)].map((m) => m[1]);
    const nous = new Set<string>([...Object.keys(CHEMINS_TOURNES), 'pin', 'parcelle.vertices']);
    const refusees = (c: string) => CLES_REFUSEES.some((k) => c === k || c.startsWith(`${k}[`) || c.startsWith(`${k}.`));
    for (const c of serveur) expect(nous.has(c) || refusees(c), `chemin non traité : ${c}`).toBe(true);
  });
});

describe('ACAL520 — motifPanVerrouille', () => {
  it('pan verrouillé ⇒ motif nommant le pan ; sinon null', () => {
    expect(motifPanVerrouille({ verrouille: true, label: 'Pan 1' })).toBe('Pan 1 verrouillé — déverrouillez-le d’abord.');
    expect(motifPanVerrouille({ verrouille: true, label: '' }, 1)).toContain('verrouillé');
    expect(motifPanVerrouille({ verrouille: false, label: 'Pan 1' })).toBeNull();
    expect(motifPanVerrouille({ label: 'Pan 1' })).toBeNull();
    expect(motifPanVerrouille(undefined)).toBeNull();
  });
});

describe('ACAL554 — bouton « Appliquer ces réglages à… »', () => {
  it('un seul pan ⇒ pas de bouton ; deux pans ⇒ le bouton de la ligne', () => {
    expect(boutonReporterReglages('area-1', 1)).toBe('');
    expect(boutonReporterReglages('area-1', 2)).toContain('data-area-report="area-1"');
  });
});

// ACAL574 — un pan « existant » est intouchable : pivoter, redimensionner, changer de module.
describe('ACAL574 — pan existant : gestes refusés, géométrie intacte', () => {
  /** Ce fichier tourne SANS DOM (il lit `import.meta.url`) : un document jsdom n'est posé que le temps du cas. */
  function avecDom<T>(f: () => T): T {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><button id="rp9-layout-toggle">Déplacer les panneaux</button></body>').window.document;
    try { return f(); } finally { g.document = avant; }
  }
  const CARRE: LngLat[] = [ptM(-5, -5), ptM(5, -5), ptM(5, 5), ptM(-5, 5)];
  const essai = (existant: boolean) => avecDom(() => {
    const areas = [{ ...panDeTest('area-1', { vertices: [...CARRE], roofType: 'flat', neededPanels: 10 }), label: 'Pan A', ...(existant ? { existant: true } : {}) }];
    const ctx = { ...ctxDeBase(areas, 'area-1'), activeArea: () => areas[0], closed: true, dom: {} } as unknown as Ctx;
    const setStatus = vi.fn();
    const zones = createZones(ctx, { redrawTrace: vi.fn(), redrawObstacles: vi.fn(), recalc: vi.fn(), setStatus });
    const avant = JSON.stringify(ctx.vertices);
    zones.renderAreasPanel();
    const btn = document.getElementById('rp9-layout-toggle') as HTMLButtonElement;
    return {
      pivote: zones.pivoterPanActif(90), redim: zones.redimensionnerPanActif(8, 12), module: zones.choisirModuleDuPanActif(null),
      intacte: JSON.stringify(ctx.vertices) === avant, setStatus, grise: btn.disabled, titre: btn.title, pan: areas[0],
    };
  });
  it('pivoter, redimensionner et choisir un module sont refusés, motif nommant le pan, géométrie intacte', () => {
    const r = essai(true);
    expect([r.pivote, r.redim, r.module]).toEqual([false, false, false]);
    expect(r.intacte).toBe(true);
    const motif = motifPanExistant(r.pan)!;
    expect(motif).toContain('Pan A : pan existant');
    expect(r.setStatus).toHaveBeenCalledWith(motif);
    expect(r.grise).toBe(true);
    expect(r.titre).toBe(motif);
  });
  it('pan sans clé : inchangé (le geste passe, le bouton reste actif)', () => {
    const r = essai(false);
    expect(r.pivote).toBe(true);
    expect(r.grise).toBe(false);
  });
});

// REP-853 / ACAL853 — le Total lit le kWh PEINT sur la carte (kWh par panneau × panneaux posés), pas
// `w.annualKwh` du solveur : deux productibles différents rendent les deux lectures distinguables.
describe('ACAL853 — liveActiveResult reprend le kWh de la carte peinte', () => {
  const essai = (carte: { kwhParPanneau: number } | null) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body></body>').window.document;
    try { return essaiSousDom(carte); } finally { g.document = avant; }
  };
  const essaiSousDom = (carte: { kwhParPanneau: number } | null) => {
    const areas = [panDeTest('area-1', { vertices: [ptM(-5, -5), ptM(5, -5), ptM(5, 5), ptM(-5, 5)], roofType: 'flat' })];
    const gagnant = { placedCount: 10, kwc: 5.4, annualKwh: 9000, savingsLow: 1, savingsHigh: 2 };
    const ctx = {
      ...ctxDeBase(areas, 'area-1'), activeArea: () => areas[0], closed: true, dom: {},
      liveResult: { winner: gagnant, target: 8000 }, shadeAnnualFactor: 1, horizonAnnualFactor: 1,
    } as unknown as Ctx;
    const zones = createZones(ctx, {
      redrawTrace: vi.fn(), redrawObstacles: vi.fn(), recalc: vi.fn(), setStatus: vi.fn(),
      ...(carte ? { etatCarte: () => carte } : {}),
    } as unknown as Parameters<typeof createZones>[1]);
    return zones.liveActiveResult();
  };
  it('carte peinte à 700 kWh/panneau : 10 panneaux → 7 000 (et non les 9 000 du solveur)', () => {
    expect(essai({ kwhParPanneau: 700 })?.annualKwh).toBe(7000);
  });
  it('carte pas encore peinte : le calcul du solveur (9 000) sert', () => {
    expect(essai(null)?.annualKwh).toBe(9000);
  });
});

describe('ACAL981 — buildingLabel nomme le bâtiment sans identifiant par son rang', () => {
  it('« Bâtiment <rang> » sans identifiant, l’identifiant saisi reste tel quel', () => {
    expect(buildingLabel(null, 1)).toBe('Bâtiment 1');
    expect(buildingLabel(null, 2)).toBe('Bâtiment 2');
    expect(buildingLabel('bat-A', 2)).toBe('bat-A');
  });
});
