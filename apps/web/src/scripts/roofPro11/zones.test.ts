// CAL69 — ZONES INTERDITE / RÉSERVÉE / PRÉFÉRÉE tracées dans l'atelier. Ce fichier prouve
// la partie qui FAIT la tâche, sans DOM ni carte : les trois natures se créent et se
// rééditent, elles écrivent EXACTEMENT le contrat CAL68 (`exclusionZones` :
// id/label/nature/vertices/setbackM/heightM), elles se relisent à l'identique, et — la
// garantie centrale — INTERDITE et RESERVEE produisent une obstruction (le compte de
// modules bouge), PREFEREE n'en produit AUCUNE (le compte ne bouge jamais).
import { describe, expect, it } from 'vitest';
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
  type ExclusionZone,
} from './zones';
import { type AreaRecord } from './types';
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
