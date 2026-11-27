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
import { ctxDeBase, panDeTest, ptM, rectRing } from './harnaisAtelier'; // ACAL574, ACAL1328
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
  panVierge, // ACAL1416
  ajoutDePanEnCours, monterToitGriseSousTrace, toitExistantGeoJSON, // ACAL1329
  type ExclusionZone,
} from './zones';
import { deserializeLayout, hydrateFromDevis, serializeLayout, selectionSansChangement, type SerializedLayout } from './prefill';
import { heriterDuPanDecoupe } from './tailleAuto'; // ACAL1707
import { createLayoutState } from '../../lib/layoutVariability'; // ACAL1707
import { decouperContour, propagerPenteDecoupe } from './formesToit'; // ACAL1735 // ACAL64, ACAL1415, ACAL1916
import { MENTION_MODULE_DE_DEPART, affectationDesPans } from './moduleSelect'; // ACAL1415
import { panAuModuleChoisi, remplacerParPanVierge, reprendreModuleChoisi } from './repriseModule'; // ACAL1416
import { type Ctx } from './context'; // ACAL64
import { lireGabaritsZone, lireGabaritsObstacle, type AreaRecord } from './types';
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import { CALQUE_CONTOUR, CALQUE_COTES, cotesDesAretes, monterCotesAretes, texteCote } from './cotesAretes'; // ACAL1328, ACAL2042
import { CALQUES_EDITION, poserEtapeAtelier, poserPresentation } from './presentationCarte'; // ACAL1328 ; suites v2 — l'étape
import { peindreBande, phraseTaillesDuChiffrage, texteEconomie, texteTotalProduction } from './affichageErp'; // ACAL1612, T4-X9-007
import { type CardData } from './types'; // ACAL1612

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

// ACAL1416 — « Effacer » puis retracer : le module CHOISI du pan effacé est conservé (jamais le départ du catalogue).
describe('ACAL1416 — Effacer puis retracer : le moduleId choisi est conservé, kWc identique partout', () => {
  const m720 = { id: 'produit-720', produitId: 720, libelle: 'Module 720 W', longueurMm: 2384, largeurMm: 1303, epaisseurMm: 33, poidsKg: 38, pmaxWc: 720, source: 'fiche' };
  const carre: [number, number][] = [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5002], [-7.6, 33.5002]];

  it('un pan au module choisi (Jinko 710 W) : le pan retracé garde son moduleId et son drapeau', () => {
    const avant = [panDeTest('area-1', { moduleId: 'jinko-710', ...{ moduleChoisi: true } } as Partial<AreaRecord>)];
    const neuf = reprendreModuleChoisi(panVierge(avant.slice(0, 0), carre, m720), panAuModuleChoisi(avant, 'area-1'));
    expect(neuf.moduleId).toBe('jinko-710'); // pas le module de départ (720 W)
    expect((neuf as { moduleChoisi?: boolean }).moduleChoisi).toBe(true);
  });

  it('remplacerParPanVierge : la liste ne garde que le pan neuf, au module choisi', () => {
    const pans = [panDeTest('area-1', { moduleId: 'jinko-710', ...{ moduleChoisi: true } } as Partial<AreaRecord>), panDeTest('area-2')];
    const neuf = remplacerParPanVierge(pans, 'area-1', () => panVierge([], carre, m720));
    expect(pans).toEqual([neuf]);
    expect(neuf.moduleId).toBe('jinko-710');
  });

  it('un module seulement « de départ » (jamais choisi) n’est pas repris', () => {
    const avant = [panDeTest('area-1', { moduleId: 'produit-9' })];
    expect(panAuModuleChoisi(avant, 'area-1')).toBeUndefined();
    expect(reprendreModuleChoisi(panVierge([], carre, m720), undefined).moduleId).toBe('produit-720');
  });
});

// ACAL1415 — le choix du module survit à l'enregistrement : « à confirmer » tant que personne n'a choisi (drapeau
// `geometry.moduleChoisi` absent), « Module posé » après un choix, aller-retour du document compris.
describe('ACAL1415 — module de départ « à confirmer » / module choisi, après aller-retour du document', () => {
  const m710 = { id: 'produit-7', produitId: 7, libelle: 'Module 710 W', longueurMm: 2384, largeurMm: 1303, epaisseurMm: 33, poidsKg: 38, pmaxWc: 710, source: 'fiche' };
  const catalogue = { calepinage: 1, modules: [{ module: m710, selectionnable: true, champs_manquants: [], motif: null }], champs_requis: [], motif_liste_vide: null };
  const plan = {
    pack: { origin: [-7.6, 33.59], azimuthDeg: 180 }, grid: { panels: [{ cx: 0, cy: 0 }, { cx: 2, cy: 0 }], kwc: 1.42 },
    tiltDeg: 13, family: 'south', flush: false, count: 2,
  } as unknown as AreaRecord['renderPlan'];
  /** Monte l'atelier sur `areas` (DOM le temps du geste) ; rend la mention, le document émis et l'atelier. */
  function monter(areas: AreaRecord[], geste?: (z: ReturnType<typeof createZones>) => void) {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"></div></body>').window.document;
    try {
      const ctx = { ...ctxDeBase(areas, areas[0].id), opts: { modulesDisponibles: catalogue }, activeArea: () => areas[0], closed: true,
        dom: { areasWindowEl: document.getElementById('rp9-areas') } } as unknown as Ctx;
      const zones = createZones(ctx, { recalc: vi.fn(), setStatus: vi.fn() });
      geste?.(zones);
      const doc = serializeLayout(ctx, 12000, { modules: affectationDesPans([m710], ctx.areas) });
      return { mention: document.getElementById('rp9-pan-module-mention')?.textContent ?? '', doc };
    } finally { g.document = avant; }
  }
  const pan = () => [panDeTest('area-1', { renderPlan: plan, roofType: 'flat', moduleId: 'produit-7' })];

  // T4-U4-007 — un pan dont le module n'est pas dans ce sélecteur : le refus NOMME le module (libellé du document),
  // jamais l'identifiant interne `produit-<id>`.
  // T4-U4-026 — la LECTURE du catalogue a échoué (`modulesDisponibles: null`, useAtelierBoot) : jamais « ne figure plus
  // dans le catalogue », qui accuse le module ; on dit que le catalogue n'a pas pu être lu, et le geste (« Réessayer »).
  it('catalogue illisible : le refus dit que le catalogue n’a pas pu être lu, jamais que le module en est sorti', () => {
    const m715 = { ...m710, id: 'produit-23019', produitId: 23019, libelle: 'Module 715 W', epaisseurMm: null }
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"></div></body>').window.document;
    try {
      const areas = [panDeTest('area-1', { renderPlan: plan, roofType: 'flat', moduleId: 'produit-23019' })];
      const ctx = { ...ctxDeBase(areas, 'area-1'), opts: { modulesDisponibles: null }, modulesDuDocument: [m715],
        activeArea: () => areas[0], closed: true, dom: { areasWindowEl: document.getElementById('rp9-areas') } } as unknown as Ctx;
      createZones(ctx, { recalc: vi.fn(), setStatus: vi.fn() });
      const refus = document.getElementById('rp9-pan-module-erreur')?.textContent ?? '';
      expect(refus).toContain('le catalogue des modules n’a pas pu être lu');
      expect(refus).toContain('« Réessayer »');
      expect(refus).not.toContain('ne figure plus');
      expect(refus).not.toContain('produit-23019');
    } finally { g.document = avant; }
  });

  it('module absent du sélecteur, connu du document : le refus dit son libellé, jamais « produit-<id> »', () => {
    const m715 = { ...m710, id: 'produit-23019', produitId: 23019, libelle: 'Module 715 W', epaisseurMm: null }
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"></div></body>').window.document;
    try {
      const areas = [panDeTest('area-1', { renderPlan: plan, roofType: 'flat', moduleId: 'produit-23019' })];
      const ctx = { ...ctxDeBase(areas, 'area-1'), opts: { modulesDisponibles: catalogue }, modulesDuDocument: [m715],
        activeArea: () => areas[0], closed: true, dom: { areasWindowEl: document.getElementById('rp9-areas') } } as unknown as Ctx;
      createZones(ctx, { recalc: vi.fn(), setStatus: vi.fn() }); // le sélecteur se synchronise à la création
      const refus = document.getElementById('rp9-pan-module-erreur')?.textContent ?? '';
      expect(refus).toContain('« Module 715 W »');
      expect(refus).not.toContain('produit-23019');
      // ACAL1980 — le motif est aussi posé au canal « À régler » (lu par la coque pour le panneau d'étape), pas seulement en pilule.
      const noeud = document.getElementById('rp9-pan-module-erreur')!;
      expect(noeud.hidden).toBe(false);
      expect(noeud.dataset.ton).toBe('a-regler');
      expect(noeud.dataset.code).toBe('module-absent');
    } finally { g.document = avant; }
  });

  it('ACAL1980 — un module qui revient au catalogue retire le motif du canal « À régler »', () => {
    const m715 = { ...m710, id: 'produit-23019', produitId: 23019, libelle: 'Module 715 W', epaisseurMm: null }
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"></div></body>').window.document;
    try {
      const areas = [panDeTest('area-1', { renderPlan: plan, roofType: 'flat', moduleId: 'produit-23019' })];
      const ctx = { ...ctxDeBase(areas, 'area-1'), opts: { modulesDisponibles: catalogue }, modulesDuDocument: [m715],
        activeArea: () => areas[0], closed: true, dom: { areasWindowEl: document.getElementById('rp9-areas') } } as unknown as Ctx;
      const zones = createZones(ctx, { recalc: vi.fn(), setStatus: vi.fn() });
      const noeud = document.getElementById('rp9-pan-module-erreur')!;
      expect(noeud.dataset.ton).toBe('a-regler');
      expect(zones.choisirModuleDuPanActif('produit-7')).toBe(true); // un module du catalogue est choisi
      expect(noeud.hidden).toBe(true);
      expect(noeud.dataset.ton).toBeUndefined();
    } finally { g.document = avant; }
  });

  it('pan jamais choisi : aucun drapeau écrit, « à confirmer » après rechargement', () => {
    const { doc } = monter(pan());
    expect('moduleChoisi' in (doc.zones[0].geometry ?? {})).toBe(false);
    const relus = deserializeLayout(JSON.parse(JSON.stringify(doc)));
    expect(monter(relus).mention).toBe(`Module 710 W — ${MENTION_MODULE_DE_DEPART}`);
  });

  it('pan choisi : drapeau écrit, plus « à confirmer » après rechargement (jamais un état de session)', () => {
    const { doc } = monter(pan(), (z) => { expect(z.choisirModuleDuPanActif('produit-7')).toBe(true); });
    expect(doc.zones[0].geometry?.moduleChoisi).toBe(true);
    const relus = deserializeLayout(JSON.parse(JSON.stringify(doc)));
    const rouvert = monter(relus);
    expect(rouvert.mention).not.toContain(MENTION_MODULE_DE_DEPART);
    expect(rouvert.doc.zones[0].geometry?.moduleChoisi).toBe(true); // ré-enregistré sans geste : le choix reste
    // Retour au module par défaut : le drapeau tombe avec le `moduleId`.
    expect(monter(relus, (z) => z.choisirModuleDuPanActif('')).doc.zones[0].geometry?.moduleChoisi).toBeUndefined();
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
  it('pan verrouillé ⇒ motif nommant le pan (par son rang, ACAL1430) ; sinon null', () => {
    expect(motifPanVerrouille({ verrouille: true, label: 'Pan 1' })).toBe('Zone 1 verrouillé — déverrouillez-le d’abord.');
    expect(motifPanVerrouille({ verrouille: true, label: '' }, 1)).toContain('verrouillé');
    expect(motifPanVerrouille({ verrouille: false, label: 'Pan 1' })).toBeNull();
    expect(motifPanVerrouille({ label: 'Pan 1' })).toBeNull();
    expect(motifPanVerrouille(undefined)).toBeNull();
  });
});

// ACAL1925 / ACAL1964 — le panneau d'un pan en Expert : étiquette AU-DESSUS du champ, sélecteur contenu, tableau par pan
// sans largeur minimale. Le vrai gabarit est monté par `createZones` + `renderAreasPanel` (rien n'est recopié ici).
describe('ACAL1925 / ACAL1964 — panneau du pan : étiquettes en colonne, tableau sans largeur minimale', () => {
  const m710 = { id: 'produit-7', produitId: 7, libelle: 'Module 710 W', longueurMm: 2384, largeurMm: 1303, epaisseurMm: 33, poidsKg: 38, pmaxWc: 710, source: 'fiche' };
  const catalogue = { calepinage: 1, modules: [{ module: m710, selectionnable: true, champs_manquants: [], motif: null }], champs_requis: [], motif_liste_vide: null };
  function monterPanneau() {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"><ul id="liste"></ul></div></body>').window.document;
    try {
      const areas = [panDeTest('area-1'), panDeTest('area-2')];
      const ctx = { ...ctxDeBase(areas, 'area-1'), opts: { modulesDisponibles: catalogue }, activeArea: () => areas[0], closed: true,
        dom: { areasWindowEl: document.getElementById('rp9-areas'), areasListEl: document.getElementById('liste') } } as unknown as Ctx;
      createZones(ctx, { recalc: vi.fn(), setStatus: vi.fn() }).renderAreasPanel();
      const pris = (sel: string) => [...document.querySelectorAll(sel)] as HTMLElement[];
      return {
        etiquettes: pris('#rp9-pan-geometry label, #rp9-pan-duplicate label, #rp9-pan-module label').map((l) => ({ texte: l.textContent ?? '', classe: l.className })),
        selecteur: document.getElementById('rp9-pan-module-select')?.className ?? '',
        tableau: document.querySelector('[data-pan-stat]')?.closest('table')?.className ?? '',
      };
    } finally { g.document = avant; }
  }

  it('« Largeur », « Rotation », « Rotation du site », « Décalage de la copie », « Module du pan » : étiquette au-dessus du champ', () => {
    const { etiquettes } = monterPanneau();
    const noms = ['Largeur', 'Rotation (', 'Rotation du site', 'Décalage de la copie', 'Module du pan'];
    for (const nom of noms) {
      const e = etiquettes.find((x) => x.texte.includes(nom));
      expect(e, nom).toBeDefined();
      expect(e!.classe, nom).toContain('flex-col');
      expect(e!.classe, nom).not.toContain('inline-flex');
    }
  });

  it('le sélecteur « Module du pan » prend la largeur de son panneau (ne dépasse pas le bord droit)', () => {
    const { selecteur } = monterPanneau();
    expect(selecteur).toContain('w-full');
    expect(selecteur).toContain('min-w-0');
  });

  it('ACAL1964 — le tableau par pan n’a aucune largeur minimale (520 px dans un panneau de 384 px)', () => {
    const { tableau } = monterPanneau();
    expect(tableau).toContain('w-full');
    expect(tableau).not.toMatch(/min-w-\[/);
  });

});

// ACAL1430 — après « 2 pans » (identifiants area-2 / area-3), la liste, le cadenas, le refus et le tableau disent le
// MÊME nom (« Zone 1 », « Zone 2 ») ; avant, le cadenas et le refus lisaient le `label` de l'identifiant (« Zone 2 »).
describe('ACAL1430 — après découpe en 2 pans : même nom partout', () => {
  it('liste, cadenas, refus de suppression et tableau des pans disent « Zone 1 » pour le premier pan', async () => {
    const { decouperContour } = await import('./formesToit');
    const v = decouperContour(rectRing(12, 9), 'gable', 22, [{ id: 'area-1' }]);
    if (!v.ok) throw new Error(v.motif);
    const areas = v.pans;
    expect(areas.map((a) => a.id)).toEqual(['area-2', 'area-3']);
    areas[0].verrouille = true;
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"><ul id="liste"></ul></div></body>').window.document;
    try {
      const ctx = { ...ctxDeBase(areas, 'area-2'), activeArea: () => areas[0], closed: true,
        dom: { areasWindowEl: document.getElementById('rp9-areas'), areasListEl: document.getElementById('liste') } } as unknown as Ctx;
      createZones(ctx, { setStatus: vi.fn() }).renderAreasPanel();
      const ligne = document.querySelector('[data-area-row="area-2"]')!;
      expect(ligne.querySelector('span')?.textContent).toBe('Zone 1');
      expect(ligne.querySelector('[data-area-lock]')?.getAttribute('aria-label')).toBe('Verrouiller Zone 1');
      expect(motifPanVerrouille(areas[0], 0)).toBe('Zone 1 verrouillé — déverrouillez-le d’abord.');
      expect(document.querySelector('[data-pan-stat="area-2"] td')?.textContent?.trim()).toBe('Zone 1');
      expect(serializeLayout(ctx).zones.map((z) => z.label)).toEqual(['Zone 1', 'Zone 2']); // le document suit l'ordre
    } finally { g.document = avant; }
  });
});

// ACAL1431 — un pan « existant » porte son étiquette « · Existant 2019 » dans la liste des pans ET dans les tableaux
// (par pan, et « Site — pans de toit et surfaces de pose »), y compris après une découpe ; « année non saisie » sinon.
describe('ACAL1431 — pan existant : étiquette dans la liste et le tableau', () => {
  const rendre = async (annee: number | null) => {
    const { decouperContour } = await import('./formesToit');
    const v = decouperContour(rectRing(12, 9), 'gable', 22, [{ id: 'area-1' }]);
    if (!v.ok) throw new Error(v.motif);
    const areas = v.pans;
    Object.assign(areas[0], { existant: true, anneeMiseEnService: annee });
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"><ul id="liste"></ul></div></body>').window.document;
    try {
      const ctx = { ...ctxDeBase(areas, 'area-2'), activeArea: () => areas[0], closed: true,
        dom: { areasWindowEl: document.getElementById('rp9-areas'), areasListEl: document.getElementById('liste') } } as unknown as Ctx;
      createZones(ctx, { setStatus: vi.fn() }).renderAreasPanel();
      const t = (sel: string) => document.querySelector(sel)?.textContent ?? '';
      return { liste: t('[data-area-row="area-2"]'), autre: t('[data-area-row="area-3"]'), parPan: t('[data-pan-stat="area-2"]'), site: t('[data-site-ligne="area-2"]') };
    } finally { g.document = avant; }
  };
  it('« · Existant 2019 » dans la liste, le tableau par pan et le tableau Site ; le pan à poser n’en porte aucune', async () => {
    const r = await rendre(2019);
    for (const texte of [r.liste, r.parPan, r.site]) expect(texte).toContain('· Existant 2019');
    expect(r.autre).not.toContain('Existant');
  });
  it('année non saisie : dite comme telle', async () => {
    expect((await rendre(null)).liste).toContain('· Existant (année non saisie)');
  });
});

// ACAL1510 — « Créer le toit » 12 × 9 m (premier sommet au nord-ouest) puis « 4 pans » : le pan que l'atelier CHARGE
// (le premier de la découpe) regardait le nord ⇒ 0 module, 0 kWc, et une simulation lancée à 0 module. Le pan le mieux
// exposé passe devant : le pan chargé pose des modules ; le pan nord passe en dernier (le solveur le dit « nord »).
describe('ACAL1510 — un toit 4 pans rend un motif ou des panneaux, jamais 0 sans cause', () => {
  it('le pan chargé (premier) pose des modules ; les pans sont rangés du plus exposé au pan nord', async () => {
    const { decouperContour } = await import('./formesToit');
    const { rectangleDepuisCotes } = await import('./toitParCotes');
    const { solveLivePitched } = await import('../../lib/estimatorBrainV8');
    const tanger: LngLat = [-5.8, 35.76];
    const v = decouperContour(rectangleDepuisCotes(tanger, 12, 9, 0), 'hip', 22, [{ id: 'area-1' }]);
    if (!v.ok) throw new Error(v.motif);
    const poses = v.pans.map((p) => solveLivePitched(p.vertices, tanger[1], 800, 22, p.facingAzimuthDeg, [], {}));
    expect(poses[0].northFacing).toBe(false);
    expect(poses[0].winner.placedCount).toBeGreaterThan(0);
    expect(v.pans.map((p) => Math.round(p.facingAzimuthDeg))).toEqual([180, 90, 270, 0]); // sud, est, ouest, nord
    expect(poses.map((r) => r.northFacing)).toEqual([false, false, false, true]);
    expect(v.pans.map((p) => p.id)).toEqual(['area-2', 'area-3', 'area-4', 'area-5']); // identifiants dans l'ordre affiché
  });
});

describe('ACAL554 — bouton « Appliquer ces réglages à… »', () => {
  it('un seul pan ⇒ pas de bouton ; deux pans ⇒ le bouton de la ligne', () => {
    expect(boutonReporterReglages('area-1', 1)).toBe('');
    expect(boutonReporterReglages('area-1', 2)).toContain('data-area-report="area-1"');
  });
});

// ACAL1527 — annuler « Appliquer ces réglages à… » rend l'état d'avant pour TOUS les pans (module et résultat compris).
describe("ACAL1527 — annuler le report rend le module d'origine des pans cibles", () => {
  it("annuler le report rend le module d'origine des pans cibles", async () => {
    const { createLayoutEditor } = await import('./layoutEditor');
    const { carteEditeurFactice, depsEditeur } = await import('./harnaisAtelier');
    const { appliquerReglagesAuxPans } = await import('./jeuReglages');
    const fen = new JSDOM('<!doctype html><body></body>').window;
    const g = globalThis as unknown as { document?: Document; window?: unknown; Event?: unknown };
    const avant = { d: g.document, w: g.window, e: g.Event };
    g.document = fen.document;
    g.window = fen;
    g.Event = fen.Event;
    try {
      const resultat = (n: number) => ({ placedCount: n }) as unknown as AreaRecord['result'];
      const areas = [
        { ...panDeTest('area-1', { label: 'Zone 1', moduleId: 'jinko-710', pitchDeg: 10 }) },
        { ...panDeTest('area-copie-1', { label: 'Zone 2', moduleId: 'canadien-600', result: resultat(12) }) },
        { ...panDeTest('area-copie-2', { label: 'Zone 3', moduleId: 'canadien-600', result: resultat(12) }) },
      ];
      const ctx = { ...ctxDeBase(areas, 'area-1'), activeArea: () => areas[0], closed: true, dom: {}, layoutMode: false, layoutPlan: null, layoutState: null,
        layoutSel: null, freeState: null, freeMode: false } as unknown as Ctx;
      const editor = createLayoutEditor(ctx, depsEditeur(carteEditeurFactice(fen.document.createElement('div'))));
      ctx.pushWorkshopHistory?.(); // le geste du bouton « Confirmer » (zones.ts)
      appliquerReglagesAuxPans(ctx.areas[0], [ctx.areas[1], ctx.areas[2]]);
      for (const a of [ctx.areas[1], ctx.areas[2]]) a.result = resultat(7); // re-pavage à l'activation du pan
      expect(ctx.areas.map((a) => a.moduleId)).toEqual(['jinko-710', 'jinko-710', 'jinko-710']);
      expect(editor.undo()).toBe(true);
      expect(ctx.areas.map((a) => a.moduleId)).toEqual(['jinko-710', 'canadien-600', 'canadien-600']);
      expect(ctx.areas.map((a) => (a.result as { placedCount: number } | null)?.placedCount ?? null)).toEqual([null, 12, 12]);
      expect(ctx.areas.map((a) => a.label)).toEqual(['Zone 1', 'Zone 2', 'Zone 3']);
    } finally { g.document = avant.d; g.window = avant.w; g.Event = avant.e; }
  });
});

describe("ACAL1527 — la boîte « Appliquer ces réglages à… » nomme « Zone 2 / Zone 3 »", () => {
  it("un pan dupliqué sans libellé s'écrit « Zone 2 », jamais area-copie-1", () => {
    const fen = new JSDOM('<!doctype html><body><ul id="l"></ul><div id="w"></div></body>').window;
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = fen.document;
    try {
      const areas = [panDeTest('area-1', { label: 'Zone 1' }), panDeTest('area-copie-1', { label: '' }), panDeTest('area-copie-2', { label: '' })];
      const dom = { areasListEl: fen.document.getElementById('l'), areasWindowEl: fen.document.getElementById('w') };
      const ctx = { ...ctxDeBase(areas, 'area-1'), activeArea: () => areas[0], closed: true, dom } as unknown as Ctx;
      createZones(ctx, { redrawTrace: vi.fn(), redrawObstacles: vi.fn(), recalc: vi.fn(), setStatus: vi.fn(), selectArea: vi.fn() });
      const bouton = fen.document.createElement('button');
      bouton.dataset.areaReport = 'area-1';
      dom.areasListEl!.appendChild(bouton);
      bouton.dispatchEvent(new fen.MouseEvent('click', { bubbles: true }));
      const texte = fen.document.getElementById('rp9-pan-report')?.textContent ?? '';
      expect(texte).toContain('Zone 2');
      expect(texte).toContain('Zone 3');
      expect(texte).not.toContain('area-copie');
    } finally { g.document = avant; }
  });
});

// ACAL574 — un pan « existant » est intouchable : pivoter, redimensionner, changer de module.
describe('ACAL574 — pan existant : gestes refusés, géométrie intacte', () => {
  /** Ce fichier tourne SANS DOM (il lit `import.meta.url`) : un document jsdom n'est posé que le temps du cas. */
  function avecDom<T>(f: () => T): T {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div><button id="rp9-layout-toggle">Déplacer les panneaux</button></div></body>').window.document;
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
      ligne: document.getElementById('rp9-layout-toggle-motif'), // ACAL1524
    };
  });
  it('pivoter, redimensionner et choisir un module sont refusés, motif nommant le pan, géométrie intacte', () => {
    const r = essai(true);
    expect([r.pivote, r.redim, r.module]).toEqual([false, false, false]);
    expect(r.intacte).toBe(true);
    const motif = motifPanExistant(r.pan)!;
    expect(motif).toContain('Zone 1 : pan existant');
    expect(r.setStatus).toHaveBeenCalledWith(motif);
    expect(r.grise).toBe(true);
    expect(r.titre).toBe(motif);
    expect(r.ligne?.textContent).toBe(motif); // ACAL1524 — le motif se lit sous le bouton, sans survol
    expect(r.ligne?.hidden).toBe(false);
  });
  it('pan sans clé : inchangé (le geste passe, le bouton reste actif)', () => {
    const r = essai(false);
    expect(r.pivote).toBe(true);
    expect(r.grise).toBe(false);
    expect(r.ligne?.hidden ?? true).toBe(true); // ACAL1524 — aucun motif tant que le geste est permis
  });
});

// ACAL1404 — la réouverture rejoue `close()` (optimiseur) puis `hydrateLayout` (pose enregistrée), comme
// `applyDevisHydration` / `loadArea` : un pan `existant` doit s'y paver, sans aucun refus à l'ouverture.
describe('ACAL1404 — document à pan existant : hydratation fermée, aucun refus à l’ouverture', () => {
  it('pose enregistrée reposée (5 modules), barre d’état muette ; un geste ensuite reste refusé', async () => {
    const { createOptimizer } = await import('./optimizer');
    const { createLayoutEditor } = await import('./layoutEditor');
    const { carteEditeurFactice, depsEditeur } = await import('./harnaisAtelier');
    const { occupiedCount } = await import('../../lib/layoutVariability');
    const g = globalThis as unknown as { document?: Document; window?: unknown };
    const avant = { d: g.document, w: g.window };
    const fen = new JSDOM('<!doctype html><body></body>').window;
    g.document = fen.document;
    g.window = fen;
    try {
      const CARRE: LngLat[] = [ptM(-5, -5), ptM(5, -5), ptM(5, 5), ptM(-5, 5)];
      const pan = { ...panDeTest('area-1', { vertices: [...CARRE], roofType: 'flat', neededPanels: 5, neededAuto: false }), label: 'Pan A', existant: true, anneeMiseEnService: 2019 };
      const avantPan = JSON.stringify(pan);
      const ctx = {
        ...ctxDeBase([pan], 'area-1'), activeArea: () => pan, closed: true, dom: {}, opts: {}, centroid: ptM(0, 0), centroidLat: ptM(0, 0)[1],
        pinned: new Set(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' }, v4YieldCache: new Map(),
        overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], useRecommended: true,
        layoutMode: false, layoutState: null, layoutSel: null, freeMode: false, freeState: null,
      } as unknown as Ctx;
      // Le rendu réel (`scene3d.renderScene`) mémorise le plan gagnant : c'est lui que `hydrateLayout` relit.
      const renderScene = vi.fn((pack, grid, tiltDeg, family, maxCount, flush = false, occupied?: Set<number>) => {
        if (occupied) return;
        Object.assign(ctx, { layoutPlan: { pack, grid, tiltDeg, family, flush }, layoutOptimalCount: Math.min(grid.panels.length, maxCount), layoutState: null });
      });
      const setStatus = vi.fn();
      const deps = { renderScene, paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
        syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800, obstructionRings: () => [], setStatus };
      const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
      opt.liveResolveFlat(); // close() → recalc() → renderSelection()
      const plan = (ctx as unknown as { layoutPlan: { grid: { panels: { cx: number; cy: number }[] } } | null }).layoutPlan;
      expect(plan?.grid.panels.length ?? 0).toBeGreaterThanOrEqual(5);
      const conteneur = fen.document.createElement('div');
      fen.document.body.appendChild(conteneur);
      const editeur = createLayoutEditor(ctx, depsEditeur(carteEditeurFactice(conteneur)));
      expect(editeur.hydrateLayout(plan!.grid.panels.slice(0, 5), undefined, 'lattice')).toBe(true);
      expect(occupiedCount(ctx.layoutState!)).toBe(5);
      expect(setStatus).not.toHaveBeenCalledWith(motifPanExistant(pan));
      expect(JSON.stringify(pan)).toBe(avantPan); // un simple chargement n'écrit rien
      // ACAL1920 — l'ombrage relu au boot REDESSINE (shadingUi → redessinerSansReposer → renderActive) : pose affichée,
      // ce redessin disait le refus dans la barre d'état dès l'ouverture, avant le moindre geste.
      const { redessinerSansReposer } = await import('./panExistant');
      const rendrePoseTenue = vi.fn();
      redessinerSansReposer(ctx as unknown as Parameters<typeof redessinerSansReposer>[0], () => opt.liveResolveFlat(), rendrePoseTenue);
      expect(setStatus).not.toHaveBeenCalledWith(motifPanExistant(pan)); // ouverture d'un pan existant ⇒ barre d'état vide
      expect(rendrePoseTenue).toHaveBeenCalledTimes(1); // la pose enregistrée est redessinée telle quelle
      opt.liveResolveFlat(); // un geste de l'utilisateur, pose affichée : refus nommé (ACAL574)
      expect(setStatus).toHaveBeenCalledWith(motifPanExistant(pan));
    } finally {
      g.document = avant.d;
      g.window = avant.w;
    }
  });
});

// ACAL1503 — un plat 3 × 1,5 m dont les retraits par arête dépassent la largeur se rouvrait OUVERT : l'anneau
// posable (anneauPosableParArete) revient vide, packConfig rend ringENU = [], et buildZoneMeshes appelait
// THREE.Shape.closePath sur un contour vide (« Cannot read properties of undefined (reading 'getPoint') ») avant
// que la fermeture du tracé n'aboutisse.
describe('ACAL1503 — un pan plus étroit que deux retraits se recharge fermé', () => {
  it('anneau posable vide ⇒ aucune forme construite, aucune exception ; la cause reproduite plante bien', async () => {
    const THREE = await import('three');
    const { anneauPosableParArete } = await import('../../lib/estimatorBrainV7');
    const { packConfig } = await import('../../lib/estimatorBrainV2');
    const { formeDuContour } = await import('./scene3d');
    const PLAT: LngLat[] = [ptM(-1.5, -0.75), ptM(1.5, -0.75), ptM(1.5, 0.75), ptM(-1.5, 0.75)];
    const posable = anneauPosableParArete(PLAT, { 0: 0.8, 2: 0.8 }); // rive 0,80 m sur les deux longs côtés : 1,5 − 1,6 < 0
    expect(posable).toEqual([]);
    const pack = packConfig(posable, PLAT[0][1], { family: 'south', tiltDeg: 10 } as Parameters<typeof packConfig>[2]);
    expect(pack.ringENU).toEqual([]);
    expect(() => { const s = new THREE.Shape(); pack.ringENU.forEach(([x, y], i) => (i ? s.lineTo(x, y) : s.moveTo(x, y))); s.closePath(); }).toThrow(/getPoint/);
    expect(formeDuContour(pack.ringENU)).toBeNull();
    expect(formeDuContour([[0, 0], [3, 0], [3, 1.5], [0, 1.5]])?.getPoints().length).toBeGreaterThanOrEqual(4); // pan normal : inchangé
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

// ACAL1612 — la bande « Dans la durée » n'invente plus de taux de dégradation (la fiche n'en porte pas) et le Total
// « TOUTES LES ZONES » dit « estimation de l'atelier » en nommant le P50 de la simulation et l'écart.
describe('ACAL1612 — bande sans taux inventé ; Total qui nomme la simulation', () => {
  const carte = { annualKwh: 4362, kwc: 3.6, count: 5, savingsLow: 5000, savingsHigh: 6000, target: 4000 } as unknown as CardData;
  const SERVI = { kwc: { valeur: 3.6, etat: 'servi' }, production_annuelle_kwh: { valeur: 5000, etat: 'servi' } } as never;
  const bande = (erp: boolean, chiffrage: unknown = null) => {
    const el = new JSDOM('<!doctype html><p></p>').window.document.querySelector('p') as HTMLElement;
    peindreBande(el, carte, 4000, erp, chiffrage as never, false);
    return el.textContent ?? '';
  };
  it('fiche sans dégradation (ERP) : aucun taux affiché, la raison est dite, l’année 1 est la SERVIE (ACAL2022 : jamais l’estimation)', () => {
    expect(bande(true, SERVI)).not.toMatch(/%\/an/);
    expect(bande(true, SERVI)).toContain(`Année 1 ~${(5000).toLocaleString('fr-FR')} kWh/an`);
    expect(bande(true, SERVI)).toContain('la fiche du module ne porte pas sa dégradation');
    expect(bande(true, SERVI)).not.toContain('Année 25');
    expect(bande(true)).toContain('Année 1 : production au prochain enregistrement'); // pendant le dessin : rien d'estimé
    expect(bande(true)).not.toContain('4');
  });
  it('T4-X2-006 (rejeu R5B) — Année 1 : la simulation À JOUR est lue (même chiffre que le Total) ; périmée ou absente : « au prochain enregistrement » ; site public inchangé', () => {
    const p50 = (5131).toLocaleString('fr-FR');
    expect(bande(true, { simulation: { p50_kwh: 5131, a_jour: true } })).toContain(`Année 1 ~${p50} kWh/an (simulation)`);
    expect(bande(true, { simulation: { p50_kwh: 5131, a_jour: true } })).not.toContain('prochain enregistrement');
    expect(bande(true, { simulation: { p50_kwh: 5131, a_jour: false } })).toContain('Année 1 : production au prochain enregistrement');
    expect(bande(false, { simulation: { p50_kwh: 5131, a_jour: true } })).toContain('dégradation ~0,5 %/an'); // site public : aucune notion de simulation
    expect(bande(false, { simulation: { p50_kwh: 5131, a_jour: true } })).not.toContain('simulation');
  });
  it('ACAL1268 — pompage : ni bande « Année 1 ~… kWh/an », ni Total, ni phrase « Production et économie » ; résidentiel et site public inchangés', () => {
    const POMPAGE = { ...(SERVI as object), marche: 'agricole' };
    const RESIDENTIEL = { ...(SERVI as object), marche: 'residentiel' };
    expect(bande(true, POMPAGE)).toBe('');
    expect(texteTotalProduction(4362, 3.6, true, POMPAGE as never)).toBe('—');
    expect(phraseTaillesDuChiffrage(POMPAGE as never, 5.68)).toBe('');
    // résidentiel (ERP) : exactement ce que produit le chiffrage sans `marche`
    expect(bande(true, RESIDENTIEL)).toBe(bande(true, SERVI));
    expect(texteTotalProduction(4362, 3.6, true, RESIDENTIEL as never)).toBe(texteTotalProduction(4362, 3.6, true, SERVI));
    expect(phraseTaillesDuChiffrage(RESIDENTIEL as never, 5.68)).toBe(phraseTaillesDuChiffrage(SERVI, 5.68));
    expect(phraseTaillesDuChiffrage(SERVI, 5.68)).toContain('Production et économie');
    // site public (`erp` faux) : même un chiffrage de pompage ne change rien
    expect(bande(false, POMPAGE)).toBe(bande(false));
    expect(texteTotalProduction(4362, 3.6, false, POMPAGE as never)).toBe(texteTotalProduction(4362, 3.6, false, null));
  });
  it('site public : le texte d’avant (taux du barème, inchangé)', () => {
    expect(bande(false)).toContain('dégradation ~0,5 %/an');
  });
  it('Total (ACAL2022, T4-X2-006) : la simulation à jour remplace l’estimation ; sans simulation « production au prochain enregistrement » ; servi : la production servie', () => {
    const sim = { simulation: { p50_kwh: 5131, a_jour: true } };
    expect(texteTotalProduction(4362, 3.6, true, sim as never)).toBe(`${(5131).toLocaleString('fr-FR')} kWh/an · simulation`);
    expect(texteTotalProduction(4362, 3.6, true, { simulation: { p50_kwh: 5131, a_jour: false } } as never)).toBe('production au prochain enregistrement');
    expect(texteTotalProduction(4362, 3.6, true, null)).toBe('production au prochain enregistrement');
    expect(texteTotalProduction(0, 3.6, true, null)).toBe('—');
    expect(texteTotalProduction(4362, 3.6, true, { ...(SERVI as object), ...sim } as never)).toBe(
      `${(5000).toLocaleString('fr-FR')} kWh/an · simulation : ${(5131).toLocaleString('fr-FR')} kWh/an (écart − 3 %)`);
    expect(texteTotalProduction(4362, 3.6, false, sim as never)).toBe(`${(4362).toLocaleString('fr-FR')} kWh/an`); // site public : le texte d'avant
  });
});

// M5 — au niveau de règles 14, enregistrer la pose ne change pas la taille de la conception : une pose d'une AUTRE taille ne
// recevra jamais de valeur. L'atelier dit la vraie raison, avec les deux tailles ; « au prochain enregistrement » reste pour
// le cas où il est vrai (même taille, bloc pas encore relu ; rien d'enregistré).
describe('M5 — la raison vraie quand la pose n’a pas la taille de la conception', () => {
  const carte = { annualKwh: 4362, kwc: 1.1, count: 2, savingsLow: 5000, savingsHigh: 6000, target: 4000 } as unknown as CardData;
  const AUTRE = { kwc: { valeur: 21.6, etat: 'servi' }, production_annuelle_kwh: { valeur: 25000, etat: 'servi' }, economie_annee1_mad: { valeur: null, etat: 'omis' } } as never;
  const EGALE = { kwc: { valeur: 1.1, etat: 'servi' }, production_annuelle_kwh: { valeur: null, etat: 'omis' }, economie_annee1_mad: { valeur: null, etat: 'omis' } } as never;
  const PHRASE = 'Production et économie calculées pour la conception du lead : 21,60 kWc — votre pose en compte 1,10 kWc.';
  const bande = (chiffrage: unknown) => {
    const el = new JSDOM('<!doctype html><p></p>').window.document.querySelector('p') as HTMLElement;
    peindreBande(el, carte, 4000, true, chiffrage as never, false, 1.1);
    return el.textContent ?? '';
  };
  it('autre taille : la bande, le Total et l’économie disent pour quelle taille la valeur est calculée, jamais « au prochain enregistrement »', () => {
    // T4-X9-007 — les cases des chiffres clés disent « — » ; la phrase, une, en texte courant, deux décimales.
    expect(bande(AUTRE)).toContain('Année 1 : —.');
    expect(texteTotalProduction(4362, 1.1, true, AUTRE)).toBe('—');
    expect(texteEconomie(AUTRE, 1.1, '≈ 5 000 MAD/an')).toBe('—');
    expect(phraseTaillesDuChiffrage(AUTRE, 1.1)).toBe(PHRASE);
    expect(phraseTaillesDuChiffrage(EGALE, 1.1)).toBe('');
    expect(bande(AUTRE)).not.toContain('prochain enregistrement');
  });
  it('même taille mais valeur pas encore servie, ou rien d’enregistré : « au prochain enregistrement » (vrai dans ces cas)', () => {
    expect(bande(EGALE)).toContain('Année 1 : production au prochain enregistrement');
    expect(texteTotalProduction(4362, 1.1, true, EGALE)).toBe('production au prochain enregistrement');
    expect(texteEconomie(EGALE, 1.1, '≈ 5 000 MAD/an')).toBe('économie au prochain enregistrement');
    expect(texteTotalProduction(4362, 1.1, true, null)).toBe('production au prochain enregistrement');
    expect(texteEconomie(null, 1.1, '≈ 5 000 MAD/an')).toBe('économie au prochain enregistrement');
  });
  // T4-X2-006 / T4-X9-013 — calepinage SANS lead : aucune conception ne viendra (le bloc est « non servi ») ; le Total ne dit
  // jamais « au prochain enregistrement » : la simulation fraîche de la pose (relayée par la page hôte), sinon « — ».
  it('sans lead : jamais « au prochain enregistrement » ; la simulation fraîche de la pose quand elle est là', () => {
    const SANS_LEAD = { production_annuelle_kwh: { valeur: null, etat: 'non_servi' }, economie_annee1_mad: { valeur: null, etat: 'non_servi' }, kwc: { valeur: null, etat: 'non_servi' } } as never;
    expect(texteTotalProduction(21735, 17.04, true, SANS_LEAD)).toBe('—');
    expect(texteEconomie(SANS_LEAD, 17.04, '≈ 5 000 MAD/an')).toBe('—');
    const simule = { ...(SANS_LEAD as object), simulation: { p50_kwh: 27197, a_jour: true } } as never;
    expect(texteTotalProduction(21735, 17.04, true, simule)).toBe(`${(27197).toLocaleString('fr-FR')} kWh/an · simulation`);
  });

  it('site public (aucun bloc `chiffrage`) : l’estimation, inchangée', () => {
    expect(texteEconomie(undefined, 1.1, '≈ 5 000 MAD/an')).toBe('≈ 5 000 MAD/an');
    expect(texteTotalProduction(4362, 1.1, false, undefined)).toBe(`${(4362).toLocaleString('fr-FR')} kWh/an`);
  });
});

describe('ACAL981 — buildingLabel nomme le bâtiment sans identifiant par son rang', () => {
  it('« Bâtiment <rang> » sans identifiant, l’identifiant saisi reste tel quel', () => {
    expect(buildingLabel(null, 1)).toBe('Bâtiment 1');
    expect(buildingLabel(null, 2)).toBe('Bâtiment 2');
    expect(buildingLabel('bat-A', 2)).toBe('bat-A');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL1328 — cotes d'arêtes du toit tracé (maquette Main : « 12,4 m » posé sur chaque bord) : la fonction PURE sur
// un rectangle connu, puis le calque monté sur une carte de test (suit un sommet déplacé, se tait en 3D et en
// présentation, jamais posé sur le site public). Déplacés de cotesAretes.test.ts (garde AMET84).
// ═══════════════════════════════════════════════════════════════════════════════
/** Carte de test : sources, calques, pente et événements — juste ce que lit le calque. */
function carteDeTestCotes() {
  const donnees = new Map<string, { features: Array<{ properties: { texte: string }; geometry: { coordinates: LngLat } }> }>();
  const visibilite = new Map<string, string>();
  const ecoute = new Map<string, Array<(e: { sourceId?: string }) => void>>();
  let pente = 0;
  const carte = {
    addSource: (id: string, s: { data: never }) => { donnees.set(id, s.data); },
    getSource: (id: string) => ({ setData: (d: never) => { donnees.set(id, d); } }),
    addLayer: (l: { id: string; layout?: { visibility?: string } }) => { visibilite.set(l.id, l.layout?.visibility ?? 'visible'); },
    getLayer: (id: string) => (visibilite.has(id) ? {} : undefined),
    getLayoutProperty: (id: string) => visibilite.get(id),
    setLayoutProperty: (id: string, _n: string, v: string) => { visibilite.set(id, v); },
    getPitch: () => pente,
    on: (t: string, fn: (e: { sourceId?: string }) => void) => { ecoute.set(t, [...(ecoute.get(t) ?? []), fn]); },
  };
  const emettre = (t: string, e: { sourceId?: string } = {}) => (ecoute.get(t) ?? []).forEach((fn) => fn(e));
  const textes = () => (donnees.get('rp9-cotes')?.features ?? []).map((f) => f.properties.texte);
  return { carte, emettre, textes, visibilite, donnees, pencher: (p: number) => { pente = p; emettre('pitch'); } };
}

describe('ACAL1328 — cotesDesAretes', () => {
  it('4 sommets ⇒ 4 cotes arrondies au dixième, virgule', () => {
    const ring = rectRing(12.4, 8.1);
    const cotes = cotesDesAretes(ring, true);
    expect(cotes.map((c) => c.texte)).toEqual(['12,4 m', '8,1 m', '12,4 m', '8,1 m']);
    // Le point de pose est le MILIEU de l'arête (jamais un sommet).
    expect(cotes[0].milieu[0]).toBeCloseTo((ring[0][0] + ring[1][0]) / 2, 12);
    expect(cotes[0].milieu[1]).toBeCloseTo((ring[0][1] + ring[1][1]) / 2, 12);
  });

  it('contour en cours : n − 1 arêtes ; aucun pan sans arête ; arête nulle ignorée', () => {
    const ring = rectRing(12.4, 8.1);
    expect(cotesDesAretes(ring.slice(0, 3), false)).toHaveLength(2);
    expect(cotesDesAretes([ring[0]], true)).toEqual([]);
    expect(cotesDesAretes([], true)).toEqual([]);
    expect(cotesDesAretes([ring[0], ring[0], ring[1]], false).map((c) => c.texte)).toEqual(['12,4 m']);
    expect(texteCote(8.06)).toBe('8,1 m');
  });
});

describe('ACAL1328 — calque rp9-cotes', () => {
  it('suit le sommet déplacé, se tait en 3D et en présentation', () => {
    const t = carteDeTestCotes();
    const pans: Array<{ sommets: LngLat[]; ferme: boolean }> = [{ sommets: rectRing(12.4, 8.1), ferme: true }];
    monterCotesAretes(t.carte, () => pans, true);
    expect(t.textes()).toEqual(['12,4 m', '8,1 m', '12,4 m', '8,1 m']);
    // Sommet déplacé : le tracé re-pose ses points (`rp9-pts`) ⇒ les cotes sont recalculées.
    pans[0] = { sommets: rectRing(14, 8.1), ferme: true };
    t.emettre('sourcedata', { sourceId: 'rp9-pts' });
    expect(t.textes()).toEqual(['14,0 m', '8,1 m', '14,0 m', '8,1 m']);
    t.pencher(60);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('none');
    t.pencher(0);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('visible');
    expect(CALQUES_EDITION).toContain(CALQUE_COTES);
    poserPresentation(t.carte, true);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('none');
    poserPresentation(t.carte, false);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('visible');
  });

  // ACAL1924 — calepinage 2057 : aucune cote lisible en Plan (la couche 3D, ajoutée après, couvrait le calque) ;
  // calepinage 2030 : la cote du faîtage imprimée deux fois (une par pan) ; cotes sans pilule blanche.
  it('les cotes d’arêtes sont au-dessus du remplissage du pan, une fois par bord, dans une pilule blanche', () => {
    const t = carteDeTestCotes();
    const ordre: string[] = [];
    const couches: Array<Record<string, unknown>> = [];
    const carte = {
      ...t.carte,
      addLayer: (l: { id: string; layout?: { visibility?: string } }) => { t.carte.addLayer(l); ordre.push(l.id); couches.push(l as never); },
      getLayer: (id: string) => (ordre.includes(id) ? {} : undefined),
      getLayersOrder: () => [...ordre],
      moveLayer: (id: string) => { ordre.splice(ordre.indexOf(id), 1); ordre.push(id); },
      hasImage: () => false, addImage: vi.fn(),
    };
    const sud = rectRing(12.4, 4.3);
    const nord = sud.map(([lng, lat]) => [lng, lat + (4.3 / 111194.9266)] as LngLat); // même faîtage, 4,3 m plus au nord
    monterCotesAretes(carte, () => [{ sommets: sud, ferme: true }, { sommets: nord, ferme: true }], true);
    carte.addLayer({ id: 'rp9-3d' }); // la couche 3D arrive APRÈS (roof-tool-pro11.ts)
    t.emettre('idle');
    expect(ordre.indexOf(CALQUE_COTES)).toBeGreaterThan(ordre.indexOf('rp9-3d'));
    expect(t.textes()).toEqual(['12,4 m', '4,3 m', '12,4 m', '4,3 m', '4,3 m', '12,4 m', '4,3 m']); // faîtage commun : une fois
    const cotes = couches.find((l) => l.id === CALQUE_COTES) as { layout: Record<string, unknown>; paint: Record<string, unknown> };
    expect([cotes.layout['icon-image'], cotes.layout['icon-text-fit'], cotes.paint['text-color']]).toEqual(['rp9-cote-pilule', 'both', '#0c1335']);
    expect(carte.addImage).toHaveBeenCalledTimes(1);
  });

  // ACAL2042 — la ligne du tracé (rp9-line) est VIDÉE à la fermeture (« la 3D la remplace ») et les sommets (rp9-pts), ajoutés
  // AVANT la couche 3D, étaient couverts par la dalle : aucun contour or (maquettes Main / ToitSombre : or plein 2 px + coins).
  it('contour du toit en or plein au-dessus de la 3D, poignées de coin aux jetons du thème', () => {
    const t = carteDeTestCotes();
    const ordre = ['rp9-line', 'rp9-pts'];
    const couches: Array<{ id: string; paint?: Record<string, unknown> }> = [];
    const peint: Record<string, unknown> = {};
    const conteneur = {} as Element;
    let theme: Record<string, string> = { '--cal-action': 'rgb(226 181 74)', '--cal-surface': 'rgb(255 255 255)', '--cal-or-trait': 'rgb(201 154 43)' };
    const avant = globalThis.getComputedStyle;
    globalThis.getComputedStyle = ((el: Element) => ({ getPropertyValue: (n: string) => (el === conteneur ? theme[n] ?? '' : '') })) as never;
    try {
      const carte = {
        ...t.carte,
        addLayer: (l: { id: string; layout?: { visibility?: string } }) => { t.carte.addLayer(l); ordre.push(l.id); couches.push(l); },
        getLayer: (id: string) => (ordre.includes(id) ? {} : undefined),
        getLayersOrder: () => [...ordre],
        moveLayer: (id: string) => { ordre.splice(ordre.indexOf(id), 1); ordre.push(id); },
        setPaintProperty: (id: string, nom: string, v: unknown) => { peint[`${id}|${nom}`] = v; },
        getContainer: () => conteneur,
      };
      const toit = rectRing(12.4, 8.1);
      monterCotesAretes(carte, () => [{ sommets: toit, ferme: true, actif: true }, { sommets: rectRing(4, 3), ferme: true }], true);
      carte.addLayer({ id: 'rp9-3d' });
      t.emettre('idle');
      expect(ordre.slice(ordre.indexOf('rp9-3d'))).toEqual(['rp9-3d', CALQUE_CONTOUR, 'rp9-pts', CALQUE_COTES]); // au-dessus de la dalle
      const contour = t.donnees.get(CALQUE_CONTOUR) as unknown as { features: Array<{ geometry: { coordinates: LngLat[] } }> };
      expect(contour.features.map((f) => f.geometry.coordinates)).toEqual([[...toit, toit[0]]]); // le pan CHOISI seul, fermé
      expect(couches.find((l) => l.id === CALQUE_CONTOUR)?.paint?.['line-width']).toBe(2);
      expect(peint[`${CALQUE_CONTOUR}|line-color`]).toBe('rgb(226, 181, 74)');
      expect([peint['rp9-pts|circle-color'], peint['rp9-pts|circle-stroke-color']]).toEqual(['rgb(255, 255, 255)', 'rgb(201, 154, 43)']);
      theme = { '--cal-action': 'rgb(226 181 74)', '--cal-surface': 'rgb(18 26 63)', '--cal-or-trait': 'rgb(226 181 74)' }; // thème sombre
      t.emettre('idle');
      expect([peint['rp9-pts|circle-color'], peint['rp9-pts|circle-stroke-color']]).toEqual(['rgb(18, 26, 63)', 'rgb(226, 181, 74)']);
      t.pencher(60); // en 3D, le contour au sol se tait comme les cotes
      expect(t.visibilite.get(CALQUE_CONTOUR)).toBe('none');
    } finally {
      globalThis.getComputedStyle = avant;
    }
  });

  // T4-B4-008 — en thème sombre la pilule des cotes restait BLANCHE (image figée, texte bleu nuit codé) ; maquette ToitSombre :
  // pilule bleu nuit (rgba 12,19,53), filet clair, texte clair. Fond, filet et texte suivent les jetons du thème.
  it('pilule des cotes aux jetons du thème : blanche en clair, bleu nuit à texte clair en sombre', () => {
    const t = carteDeTestCotes();
    const peint: Record<string, unknown> = {};
    const images = new Map<string, { width: number; data: Uint8ClampedArray }>();
    const conteneur = {} as Element;
    let theme: Record<string, string> = { '--cal-texte-1': 'rgb(12 19 53)', '--cal-flottante': 'rgba(255, 255, 255, 0.86)', '--cal-flottante-filet': 'rgba(255, 255, 255, 0.7)' };
    const avant = globalThis.getComputedStyle;
    globalThis.getComputedStyle = ((el: Element) => ({ getPropertyValue: (n: string) => (el === conteneur ? theme[n] ?? '' : '') })) as never;
    const centre = (img: { width: number; data: Uint8ClampedArray }) => [...img.data.slice((16 * img.width + 24) * 4, (16 * img.width + 24) * 4 + 4)];
    try {
      const carte = {
        ...t.carte,
        setPaintProperty: (id: string, nom: string, v: unknown) => { peint[`${id}|${nom}`] = v; },
        getContainer: () => conteneur,
        hasImage: (id: string) => images.has(id),
        addImage: (id: string, img: { width: number; data: Uint8ClampedArray }) => { images.set(id, img); },
        updateImage: (id: string, img: { width: number; data: Uint8ClampedArray }) => { images.set(id, img); },
      };
      monterCotesAretes(carte, () => [{ sommets: rectRing(12.4, 8.1), ferme: true, actif: true }], true);
      const [idPilule] = [...images.keys()];
      expect(centre(images.get(idPilule)!)).toEqual([255, 255, 255, 219]);
      t.emettre('idle');
      expect(peint[`${CALQUE_COTES}|text-color`]).toBe('rgb(12, 19, 53)');
      // La feuille de style CONSTRUITE (minifiée) sert les jetons en hexadécimal (relevé au navigateur : `#0c1335d1`, `#f3f5fb`) :
      // un lecteur qui ne comprenait que `rgb(…)` retombait toujours sur la pilule blanche.
      theme = { '--cal-texte-1': '#f3f5fb', '--cal-flottante': '#0c1335d1', '--cal-flottante-filet': '#ffffff1a' };
      t.emettre('idle');
      expect(peint[`${CALQUE_COTES}|text-color`]).toBe('rgb(243, 245, 251)');
      expect(centre(images.get(idPilule)!)).toEqual([12, 19, 53, 209]);
    } finally {
      globalThis.getComputedStyle = avant;
    }
  });

  // Suites des écrans v2 (24/11) — à l'étape Panneaux la carte montrait cotes, contour or et coins (maquette Main seule).
  it('étape déclarée par la coque : cotes, contour or et coins à l’étape Toit seulement ; sans étape, comme avant', async () => {
    const { creerPoignees3d } = await import('./poigneesSommets3d');
    const t = carteDeTestCotes();
    t.carte.addLayer({ id: 'rp9-pts' });
    monterCotesAretes(t.carte, () => [{ sommets: rectRing(12.4, 8.1), ferme: true, actif: true }], true);
    creerPoignees3d(t.carte as never).poser({ add: () => {} } as never, rectRing(12.4, 8.1), [-7.6, 33.5], 6);
    const vus = () => [CALQUE_COTES, CALQUE_CONTOUR, 'rp9-pts'].map((id) => t.visibilite.get(id));
    expect(vus()).toEqual(['visible', 'visible', 'visible']);
    for (const [etape, attendu] of [['panneaux', 'none'], ['electrique', 'none'], ['toit', 'visible'], ['documents', 'none'], [null, 'visible']] as const) {
      poserEtapeAtelier(t.carte, etape);
      expect(vus()).toEqual([attendu, attendu, attendu]);
    }
    poserEtapeAtelier(t.carte, 'panneaux');
    poserPresentation(t.carte, true);
    poserPresentation(t.carte, false); // la sortie de la vue client ne rallume rien hors de l'étape Toit
    expect(vus()).toEqual(['none', 'none', 'none']);
    poserEtapeAtelier(t.carte, null);
  });

  it('site public (option de montage absente) : aucun calque posé', () => {
    const t = carteDeTestCotes();
    monterCotesAretes(t.carte, () => [{ sommets: rectRing(12.4, 8.1), ferme: true }], false);
    expect(t.visibilite.has(CALQUE_COTES)).toBe(false);
  });
});

// T4-X2-010 — toit plat de 24 panneaux + un second pan ACTIF à l'enregistrement : rouvert, le toit disait « 0 modules ·
// à calculer » et paraissait vide sur la carte, alors que le document portait ses 24 panneaux (la barre les comptait).
describe('T4-X2-010 — un pan non actif rouvert garde sa pose : document, tableau du site, carte', () => {
  const panneaux = Array.from({ length: 24 }, (_, i) => ({ cx: (i % 6) * 1.2 - 3, cy: Math.floor(i / 6) * 2.2 - 3 }));
  const documentDeuxPans = (): SerializedLayout => ({
    version: 2, activeAreaId: 'z2',
    zones: [
      { id: 'z1', label: 'Zone 1', vertices: rectRing(10, 8), obstacles: [], roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 180, facingManual: false, neededPanels: 24, neededAuto: true,
        geometry: { azimuthDeg: 180, tiltDeg: 15, family: 'south', flush: false, kwc: 17.28, count: 24, origin: [-7.6, 33.5], panels: panneaux } },
      { id: 'z2', label: 'Zone 2', vertices: rectRing(6, 5, -7.5995, 33.5004), obstacles: [], roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true },
    ],
  } as unknown as SerializedLayout);

  it('le document rouvert garde 24 panneaux sur le toit ; le tableau du site dit 24 modules, son total celui du document', async () => {
    const { poserPlansEnregistres } = await import('./poseEnregistree');
    const h = hydrateFromDevis({ id: null, geometrie: { roof_layout: documentDeuxPans() }, cibleVendue: false });
    const areas = h.zones!;
    expect(h.activeAreaId).toBe('z2');
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"><ul id="liste"></ul></div></body>').window.document;
    try {
      const ctx = { ...ctxDeBase(areas, 'z2'), activeArea: () => areas[1], closed: true, surfacesPose: [],
        dom: { areasWindowEl: document.getElementById('rp9-areas'), areasListEl: document.getElementById('liste') } } as unknown as Ctx;
      // Enregistrer sans geste : le toit garde ses 24 panneaux dans le document.
      const doc = serializeLayout(ctx);
      expect(doc.zones[0].geometry?.count).toBe(24);
      const totalDocument = doc.zones.reduce((s, z) => s + (z.geometry?.count ?? 0), 0);
      createZones(ctx, { setStatus: vi.fn() }).renderAreasPanel();
      const ligne = document.querySelector('[data-site-ligne="z1"]')?.textContent ?? '';
      expect(ligne).toContain('24 modules');
      expect(ligne).not.toContain('à calculer');
      expect(document.querySelector('[data-site-resume]')?.textContent).toContain(`${totalDocument} modules`);
      expect(document.querySelector('[data-area-row="z1"]')?.textContent).toContain('24 panneaux');
      // La carte : le toit non actif reçoit un plan de rendu de ses 24 panneaux ; le pan actif aucun (la scène pose le sien).
      poserPlansEnregistres(areas, 'z2');
      expect(areas[0].renderPlan?.count).toBe(24);
      expect(areas[1].renderPlan).toBeNull();
      // Le plan posé ne change pas le document : le pan non actif est réémis tel qu'enregistré.
      expect(serializeLayout(ctx).zones[0].geometry).toEqual(doc.zones[0].geometry);
    } finally { g.document = avant; }
  });
});

describe('ACAL1916 — choisir un pan ne marque pas le document modifié', () => {
  const pan = () => ({
    id: 'area-1', vertices: [A, B, [-7.5990, 33.5]] as LngLat[], obstacles: [], roofType: 'flat', pitchDeg: 0,
    facingAzimuthDeg: 180, facingManual: false, neededPanels: 4, neededAuto: true,
    geometrieEnregistree: { count: 4, panels: [{ cx: 1, cy: 2 }] },
  });
  const vif = (a: ReturnType<typeof pan>) => ({
    vertices: [...a.vertices], obstacles: [...a.obstacles], roofType: a.roofType, pitchDeg: a.pitchDeg,
    facingAzimuthDeg: a.facingAzimuthDeg, facingManual: a.facingManual, neededPanels: a.neededPanels, neededAuto: a.neededAuto,
  });
  it('rien n’a bougé depuis le chargement ⇒ la sélection ne réécrit rien', () => {
    const a = pan();
    expect(selectionSansChangement(a as never, vif(a), { count: 4, panels: [{ cx: 1, cy: 2 }] } as never)).toBe(true);
  });
  it('un panneau déplacé, une pente ou un nombre changés ⇒ la sélection capture (modifié)', () => {
    const a = pan();
    expect(selectionSansChangement(a as never, vif(a), { count: 4, panels: [{ cx: 9, cy: 2 }] } as never)).toBe(false);
    expect(selectionSansChangement(a as never, { ...vif(a), pitchDeg: 22 }, a.geometrieEnregistree as never)).toBe(false);
    expect(selectionSansChangement(a as never, { ...vif(a), neededPanels: 5 }, a.geometrieEnregistree as never)).toBe(false);
  });
  it('un pan sans pose enregistrée n’est jamais « inchangé »', () => {
    const a = { ...pan(), geometrieEnregistree: undefined };
    expect(selectionSansChangement(a as never, vif(a as never), null)).toBe(false);
  });
});

describe('ACAL1707 — « 2 pans » sur un toit à 4 panneaux pose et enregistre 4 panneaux', () => {
  // Le geste réel (`appliquer` de `monterFormesToit`, roof-tool-pro11.ts) : découpe, nombre hérité, le pan découpé remplacé
  // par les pans, le PREMIER chargé (`loadArea(pans[0])` : son nombre pilote la pose vivante). Puis « Enregistrer » sans
  // ouvrir le pan 2 : ce que `serializeLayout` écrit. Toit long nord-sud : deux pans est / ouest, tous deux exposés.
  function decouperPuisEnregistrer(besoin: { neededPanels: number; neededAuto: boolean }) {
    const avant = panDeTest('area-1', { vertices: rectRing(9, 12), roofType: 'pitched', pitchDeg: 22, ...besoin, moduleId: 'm' } as never);
    const areas: AreaRecord[] = [avant];
    const v = decouperContour(avant.vertices, 'gable', 22, areas);
    if (!v.ok) throw new Error(v.motif);
    const pans = v.pans;
    heriterDuPanDecoupe(avant, besoin, pans, true);
    areas.splice(0, 1, ...pans);
    const actif = pans[0];
    const cellules = Array.from({ length: 12 }, (_, i) => ({ cx: (i % 4) * 1.2 - 2, cy: Math.floor(i / 4) * 2.2 - 2 })); // 12 tiennent sur le pan
    const pose = Math.min(actif.neededPanels, cellules.length); // `placedFor` : min(nombre voulu, ce qui tient)
    const ctx = {
      ...ctxDeBase(areas, actif.id), activeArea: () => actif, closed: true,
      layoutPlan: {
        pack: { origin: [-7.6, 33.5], ringENU: [[-6, -6], [6, -6], [6, 6], [-6, 6]], azimuthDeg: 180 },
        grid: { rowWidthM: 2, footprintPerPanelM2: 2, slopeLenM: 1, kwc: 12 * 0.71, panels: cellules },
        tiltDeg: 22, family: 'south', flush: true,
      },
      layoutOptimalCount: pose,
      layoutState: createLayoutState(cellules, pose),
    } as unknown as Ctx;
    return { pans, pose, doc: serializeLayout(ctx) };
  }

  it('nombre figé à 4 : 4 posés sur le pan chargé, 4 écrits au document (aucun pan non ouvert ne retire de panneau)', () => {
    const { pans, pose, doc } = decouperPuisEnregistrer({ neededPanels: 4, neededAuto: false });
    expect(pans.length).toBe(2);
    expect(pose).toBe(4);
    expect(doc.zones.reduce((s, z) => s + (z.geometry?.count ?? 0), 0)).toBe(4);
    expect(doc.zones[0].geometry?.panels.length).toBe(4);
    expect(doc.zones[0].neededPanels).toBe(4);
  });

  it('nombre d’après la facture (auto) : le pan chargé garde la cible, aucun pan n’est rempli en plus', () => {
    const { pose, doc } = decouperPuisEnregistrer({ neededPanels: 4, neededAuto: true });
    expect(pose).toBe(4);
    expect(doc.zones.reduce((s, z) => s + (z.geometry?.count ?? 0), 0)).toBe(4);
  });
});

describe('ACAL1735 — confirmer la pente d’un pan la confirme pour la même découpe', () => {
  const p = (id: string, pitchDeg: number, extra: object = {}) => ({ id, roofType: 'pitched' as const, pitchDeg, ...extra });
  it('les pans de la même découpe, de même pente et sans provenance, suivent', () => {
    const pans = [p('area-2', 22, { pitchSource: { mode: 'degres', degres: 22 } }), p('area-3', 22)];
    const src = { mode: 'degres', degres: 22 };
    expect(propagerPenteDecoupe(pans, new Set(['area-2', 'area-3']), 'area-2', 22, 22, src)).toEqual(['area-3']);
    expect((pans[1] as { pitchSource?: unknown }).pitchSource).toEqual(src);
  });
  it('un pan d’une autre découpe, d’une autre pente ou déjà confirmé n’est pas touché', () => {
    const pans = [p('area-2', 22), p('area-3', 30), p('area-4', 22), p('area-5', 22, { pitchSource: { mode: 'mesure' } })];
    const src = { mode: 'degres', degres: 22 };
    expect(propagerPenteDecoupe(pans, new Set(['area-2', 'area-3', 'area-5']), 'area-2', 22, 22, src)).toEqual([]);
    expect(propagerPenteDecoupe(pans, new Set(['area-3']), 'area-2', 22, 22, src)).toEqual([]);
  });
  it('la pente changée est suivie par les pans qui l’avaient', () => {
    const pans = [p('area-2', 30), p('area-3', 22)];
    expect(propagerPenteDecoupe(pans, new Set(['area-2', 'area-3']), 'area-2', 22, 30, { mode: 'degres', degres: 30 })).toEqual(['area-3']);
    expect(pans[1].pitchDeg).toBe(30);
  });
});

// ACAL1665 — « le plus de panneaux » est stocké comme le plafond du besoin (400) : aucune phrase de l'atelier ERP ne le montre
// comme une cible (« 13 posés / 400 cible »), par le chemin réel de l'optimiseur (`liveResolveFlat` → `syncNeedControl`).
describe('ACAL1665 — « le plus de panneaux » ne se lit jamais comme une cible de 400', () => {
  const noteAvec = async (toitM: number, opts: Record<string, unknown>) => {
    const { createOptimizer } = await import('./optimizer');
    const { rectRing } = await import('./harnaisAtelier');
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><p id="rp9-need-note"></p><input id="rp9-need-input"></body>').window.document;
    try {
      const vertices = rectRing(toitM, toitM);
      const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
      const pan = { id: 'z1', label: 'Zone 1', vertices, obstacles: [], roofType: 'flat' };
      const ctx = {
        closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts, dom: {},
        centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
        v4YieldCache: new Map(), overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
        neededAuto: false, neededPanels: 400, devisMode: true, cibleVendue: false, layoutPlan: null, layoutState: null, layoutOptimalCount: 0, useRecommended: true,
        freeMode: false, freeState: null,
      } as unknown as Ctx;
      const renderScene = vi.fn((pack: unknown, grid: { panels: unknown[] }, tiltDeg: number, family: string, maxCount: number, flush: boolean, occ?: Set<number>) => {
        if (occ) return;
        Object.assign(ctx, { layoutPlan: { pack, grid, tiltDeg, family, flush }, layoutOptimalCount: Math.min(grid.panels.length, Math.round(maxCount)), layoutState: null });
      });
      const deps = { renderScene, paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
        syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0, obstructionRings: () => [], obstructionClearances: () => [], setStatus: vi.fn() };
      createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).liveResolveFlat();
      return g.document!.getElementById('rp9-need-note')!.textContent ?? '';
    } finally { g.document = avant; }
  };
  it('ERP, toit qui tient des panneaux : « le plus de panneaux possible », jamais « 400 »', async () => {
    const note = await noteAvec(14, { chiffrage: null });
    expect(note).toMatch(/le plus de panneaux possible : \d+ posés/);
    expect(note).not.toContain('400');
  });
  it('ERP, aucun panneau ne tient : la phrase dit « le plus possible » en mots, jamais « / 400 cible »', async () => {
    const note = await noteAvec(0.5, { chiffrage: null });
    expect(note).not.toContain('400');
    expect(note).toContain('le plus possible');
  });
  it('site public : inchangé (le nombre à poser, « au devis »)', async () => {
    expect(await noteAvec(14, {})).toMatch(/posés \/ 400 au devis/);
  });
});
