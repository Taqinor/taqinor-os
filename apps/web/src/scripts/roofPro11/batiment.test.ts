// CALX100/101/102 — le bâtiment vient du DOCUMENT (`buildings[]`, contrat CALX84), pas
// d'une constante : hauteur saisie + provenance, bandeau d'acrotère, lucarne qui perce le
// pan. Tout est testé HORS DOM et hors carte (les fonctions de `batiment.ts` sont pures).
import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import {
  HAUTEUR_DESSIN_M,
  ID_BATIMENT_SANS_ID,
  acrotereDuBatiment,
  anneauInterieur,
  appliquerSaisie,
  batimentDuPan,
  construireAcrotere,
  construireLucarne,
  emettreBatiments,
  hauteurExtrusion,
  idBatimentDuPan,
  lireBatiments,
  lucarnesDuPan,
  mentionEtages,
  percerPanLucarnes,
  serialiserBatiments,
  type Batiment,
} from './batiment';
import { serializeLayout } from './prefill';
import { CLEARANCE_BY_TYPE } from './types';
import { FLOORS, FLOOR_HEIGHT_M } from './constants';
import { type Obstacle } from '../../lib/obstacles';
import { type Ctx } from './context';
import { type AreaRecord } from './types';
import { type LngLat } from '../../lib/roof';

// ── Le fragment PARTAGÉ du contrat CALX84 (miroir EXACT de `EXEMPLE_BATIMENTS`,
// `backend/django_core/apps/calepinage/tests/test_calx84_batiments.py`) : un bâtiment dont
// la hauteur est SAISIE et tracée, un bâtiment dont personne n'a mesuré la hauteur.
const EXEMPLE_BATIMENTS: Batiment[] = [
  {
    id: 'bat-1',
    label: 'Villa (exemple)',
    hauteurM: 7.2,
    etages: 2,
    hauteurEtageM: 3.0,
    source: 'mesurée au télémètre sur site',
  },
  {
    id: 'bat-2',
    label: 'Garage (exemple)',
    hauteurM: null,
    etages: null,
    hauteurEtageM: null,
    source: null,
  },
];

const VERTS: LngLat[] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

function zone(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as LngLat),
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 0,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    result: null,
    renderPlan: null,
    ...opts,
  };
}

function makeCtx(areas: AreaRecord[], batiments?: Batiment[]): Ctx {
  const active = areas[0];
  return {
    areas,
    activeAreaId: active.id,
    activeArea: () => active,
    vertices: active.vertices,
    obstacles: active.obstacles,
    roofType: active.roofType,
    pitchDeg: active.pitchDeg,
    facingAzimuthDeg: active.facingAzimuthDeg,
    facingManual: false,
    neededPanels: active.neededPanels,
    neededAuto: active.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
    batiments,
  } as unknown as Ctx;
}

/** Anneau ENU rectangulaire centré en (0, 0), largeur (E-O) × profondeur (N-S), en mètres. */
function ringENU(largeurM: number, profondeurM: number): [number, number][] {
  const hw = largeurM / 2;
  const hl = profondeurM / 2;
  return [
    [-hw, -hl],
    [hw, -hl],
    [hw, hl],
    [-hw, hl],
  ];
}

/** Aire (m²) RÉELLE d'un maillage : somme des aires de ses triangles. */
function aireMaillageM2(geo: THREE.BufferGeometry): number {
  const pos = geo.attributes.position as THREE.BufferAttribute;
  const idx = geo.index;
  const n = idx ? idx.count : pos.count;
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  let total = 0;
  for (let i = 0; i < n; i += 3) {
    const i0 = idx ? idx.getX(i) : i;
    const i1 = idx ? idx.getX(i + 1) : i + 1;
    const i2 = idx ? idx.getX(i + 2) : i + 2;
    a.fromBufferAttribute(pos, i0);
    b.fromBufferAttribute(pos, i1);
    c.fromBufferAttribute(pos, i2);
    total += b.clone().sub(a).cross(c.clone().sub(a)).length() / 2;
  }
  return total;
}

// ═══════════════ CALX100 — la hauteur et sa provenance ═══════════════

describe('CALX100 — hauteurExtrusion : saisie, ou hauteur de dessin ANNONCÉE', () => {
  it('hauteur saisie 9 m avec sa provenance ⇒ la 3D extrude 9 m', () => {
    const lu = hauteurExtrusion({ id: 'b', hauteurM: 9, source: 'mesurée au télémètre' });
    expect(lu.hauteurM).toBe(9);
    expect(lu.origine).toBe('saisie');
    expect(lu.source).toBe('mesurée au télémètre');
    expect(lu.nonMesure).toEqual([]);
    expect(lu.mention).toContain('9,0 m');
    expect(lu.mention).toContain('mesurée au télémètre');
  });

  it('aucune saisie ⇒ hauteur de DESSIN (6 m, l’hypothèse d’aujourd’hui) et la mention le dit', () => {
    for (const bat of [null, undefined, { id: 'b' }, { id: 'b', hauteurM: null, source: null }]) {
      const lu = hauteurExtrusion(bat as Batiment | null);
      expect(lu.hauteurM).toBe(HAUTEUR_DESSIN_M);
      expect(lu.hauteurM).toBe(FLOORS * FLOOR_HEIGHT_M); // le repli historique, inchangé
      expect(lu.origine).toBe('dessin');
      expect(lu.source).toBeNull();
      expect(lu.mention).toContain('hypothèse');
      expect(lu.nonMesure).toEqual(['hauteur du bâtiment']);
    }
  });

  it('hauteur SANS provenance ⇒ pas engageable : hauteur de dessin, et le champ manquant est NOMMÉ', () => {
    const lu = hauteurExtrusion({ id: 'b', hauteurM: 9, source: '   ' });
    expect(lu.hauteurM).toBe(HAUTEUR_DESSIN_M);
    expect(lu.origine).toBe('dessin');
    expect(lu.nonMesure).toEqual(['provenance de la hauteur (source)']);
  });

  it('une hauteur nulle ou négative n’est pas une mesure — jamais 0 m extrudé', () => {
    expect(hauteurExtrusion({ id: 'b', hauteurM: 0, source: 'x' }).hauteurM).toBe(HAUTEUR_DESSIN_M);
    expect(hauteurExtrusion({ id: 'b', hauteurM: -3, source: 'x' }).hauteurM).toBe(HAUTEUR_DESSIN_M);
  });

  it('étages × hauteur d’étage = une information d’ÉCRAN, jamais la hauteur extrudée', () => {
    const bat: Batiment = { id: 'b', etages: 3, hauteurEtageM: 2.8, hauteurM: null, source: null };
    expect(mentionEtages(bat)).toContain('8,4 m');
    expect(hauteurExtrusion(bat).hauteurM).toBe(HAUTEUR_DESSIN_M); // AUCUNE déduction
    expect(mentionEtages({ id: 'b', etages: 3 })).toBeNull(); // un seul des deux ⇒ rien
  });
});

describe('CALX100 — le bâtiment d’un pan (CAL59 buildingId)', () => {
  it('un pan sans buildingId retombe sur la convention de document, pas sur rien', () => {
    expect(idBatimentDuPan(undefined)).toBe(ID_BATIMENT_SANS_ID);
    expect(idBatimentDuPan('   ')).toBe(ID_BATIMENT_SANS_ID);
    expect(idBatimentDuPan('bat-1')).toBe('bat-1');
  });

  it('retrouve le bâtiment que le pan désigne, et `null` quand il n’est pas décrit', () => {
    expect(batimentDuPan(EXEMPLE_BATIMENTS, 'bat-1')?.hauteurM).toBe(7.2);
    expect(batimentDuPan(EXEMPLE_BATIMENTS, 'bat-9')).toBeNull();
    expect(batimentDuPan(undefined, 'bat-1')).toBeNull();
  });
});

describe('CALX100 — saisie : un refus NOMME son champ, un vide EFFACE', () => {
  it('une hauteur sans provenance est REFUSÉE en nommant `source`, et rien n’est écrit', () => {
    const res = appliquerSaisie([], 'bat-1', { hauteurM: 9, source: '' });
    expect(res.refus).toHaveLength(1);
    expect(res.refus[0].champ).toBe('source');
    expect(res.batiments[0].hauteurM).toBeNull();
  });

  it('hauteur + provenance ⇒ écrite ; un champ vidé repart à `null`, jamais à 0', () => {
    const a = appliquerSaisie([], 'bat-1', { hauteurM: 9, source: 'lue sur le permis', hauteurEtageM: 2.9 });
    expect(a.refus).toEqual([]);
    expect(a.batiments[0]).toMatchObject({ id: 'bat-1', hauteurM: 9, source: 'lue sur le permis' });
    const b = appliquerSaisie(a.batiments, 'bat-1', { hauteurM: null, source: null, hauteurEtageM: null });
    expect(b.batiments[0].hauteurM).toBeNull();
    expect(b.batiments[0].hauteurEtageM).toBeNull();
    expect(hauteurExtrusion(b.batiments[0]).origine).toBe('dessin');
  });

  it('n’écrase pas les autres bâtiments et ne mute pas la liste reçue', () => {
    const avant = EXEMPLE_BATIMENTS.map((b) => ({ ...b }));
    const res = appliquerSaisie(avant, 'bat-2', { hauteurM: 3.4, source: 'déclarée par le client' });
    expect(res.batiments).toHaveLength(2);
    expect(res.batiments.find((b) => b.id === 'bat-1')?.hauteurM).toBe(7.2);
    expect(avant.find((b) => b.id === 'bat-2')?.hauteurM).toBeNull(); // l'entrée reçue est intacte
  });

  it('un bâtiment inconnu est AJOUTÉ (le pan décrit son bâtiment pour la première fois)', () => {
    const res = appliquerSaisie(EXEMPLE_BATIMENTS, 'bat-3', { hauteurAcrotereM: 1.1 });
    expect(res.batiments).toHaveLength(3);
    expect(res.batiments[2]).toMatchObject({ id: 'bat-3', hauteurAcrotereM: 1.1 });
  });
});

describe('CALX100 — le document : écriture, omission, réhydratation', () => {
  it('aucun bâtiment renseigné ⇒ AUCUNE clé `buildings` (document inchangé, byte pour byte)', () => {
    expect(emettreBatiments(undefined)).toEqual({});
    expect(emettreBatiments([])).toEqual({});
    expect(emettreBatiments([{ id: 'bat-1' }])).toEqual({}); // rien de renseigné = rien à dire
  });

  it('le fragment d’exemple CALX84 traverse écriture puis relecture sans perte', () => {
    const ecrit = serialiserBatiments(EXEMPLE_BATIMENTS);
    expect(ecrit).toHaveLength(2);
    expect(ecrit[0]).toMatchObject({
      id: 'bat-1',
      label: 'Villa (exemple)',
      hauteurM: 7.2,
      etages: 2,
      hauteurEtageM: 3.0,
      source: 'mesurée au télémètre sur site',
    });
    expect(ecrit[1]).toMatchObject({ id: 'bat-2', hauteurM: null, source: null });
    expect(lireBatiments({ buildings: ecrit })).toEqual(ecrit);
  });

  it('une hauteur SANS provenance ne s’écrit jamais dans le document (le contrat la refuserait)', () => {
    const ecrit = serialiserBatiments([{ id: 'bat-1', hauteurM: 9, source: null, etages: 1 }]);
    expect(ecrit[0].hauteurM).toBeNull();
    expect(ecrit[0].source).toBeNull();
  });

  it('un JSON douteux rend une liste vide plutôt que de casser l’ouverture', () => {
    expect(lireBatiments(null)).toEqual([]);
    expect(lireBatiments({ buildings: 'nope' })).toEqual([]);
    expect(lireBatiments({ buildings: [null, { id: '' }, 42] })).toEqual([]);
  });

  it('la hauteur SAISIE survit à serializeLayout puis à une réhydratation', () => {
    const saisie = appliquerSaisie([], 'bat-1', { hauteurM: 9, source: 'mesurée au télémètre' });
    const ctx = makeCtx([zone('z1', { buildingId: 'bat-1' })], saisie.batiments);
    const layout = serializeLayout(ctx);
    expect(layout.buildings).toHaveLength(1);
    expect(layout.buildings![0]).toMatchObject({ id: 'bat-1', hauteurM: 9, source: 'mesurée au télémètre' });
    // Réhydratation : la 3D re-extrude EXACTEMENT 9 m, pas l'hypothèse.
    const relus = lireBatiments(JSON.parse(JSON.stringify(layout)));
    expect(hauteurExtrusion(batimentDuPan(relus, 'bat-1')).hauteurM).toBe(9);
    expect(hauteurExtrusion(batimentDuPan(relus, 'bat-1')).origine).toBe('saisie');
  });

  it('sans bâtiment saisi, serializeLayout n’émet pas la clé (comportement d’aujourd’hui)', () => {
    const layout = serializeLayout(makeCtx([zone('z1')]));
    expect('buildings' in layout).toBe(false);
  });
});

// ═══════════════ CALX101 — le bandeau d'acrotère ═══════════════

describe('CALX101 — acrotère : un VOLUME quand il est SAISI, rien sinon', () => {
  it('aucune hauteur d’acrotère saisie ⇒ aucun volume (scène identique à aujourd’hui)', () => {
    expect(acrotereDuBatiment({ id: 'b' }, 0.5)).toBeNull();
    expect(acrotereDuBatiment({ id: 'b', hauteurAcrotereM: null }, 0.5)).toBeNull();
    expect(construireAcrotere(ringENU(10, 8), acrotereDuBatiment({ id: 'b' }, 0.5), 6, false)).toBeNull();
  });

  it('retrait d’acrotère non réglé (parapetM = 0) ⇒ aucun volume, même avec une hauteur saisie', () => {
    expect(acrotereDuBatiment({ id: 'b', hauteurAcrotereM: 1.1 }, 0)).toBeNull();
    expect(acrotereDuBatiment({ id: 'b', hauteurAcrotereM: 1.1 }, undefined)).toBeNull();
  });

  it('hauteur saisie + retrait réglé ⇒ un bandeau à cette hauteur, d’épaisseur = le retrait', () => {
    const v = acrotereDuBatiment({ id: 'b', hauteurAcrotereM: 1.1 }, 0.5)!;
    expect(v.hauteurM).toBe(1.1);
    expect(v.epaisseurM).toBe(0.5); // jamais une épaisseur inventée : le retrait CAL76
    expect(v.mention).toContain('1,1 m');
  });

  it('le maillage existe, est posé sur la dalle et PROJETTE une ombre', () => {
    const mesh = construireAcrotere(ringENU(10, 8), acrotereDuBatiment({ id: 'b', hauteurAcrotereM: 1.2 }, 0.5), 6.02, false)!;
    expect(mesh).toBeInstanceOf(THREE.Mesh);
    expect(mesh.castShadow).toBe(true);
    expect(mesh.position.z).toBeCloseTo(6.02, 6);
    const bbox = new THREE.Box3().setFromObject(mesh);
    expect(bbox.max.z - bbox.min.z).toBeCloseTo(1.2, 5); // le relevé SAISI, rien d'autre
  });

  it('anneauInterieur : un rentrant plus épais que le tracé ne tient pas ⇒ aucun bandeau', () => {
    expect(anneauInterieur(ringENU(10, 8), 0.5)).toHaveLength(4);
    expect(anneauInterieur(ringENU(1, 1), 3)).toBeNull(); // le tracé est plus étroit que l'acrotère
    expect(anneauInterieur([[0, 0], [1, 0]], 0.5)).toBeNull(); // moins de trois sommets
    expect(construireAcrotere(ringENU(1, 1), { hauteurM: 1, epaisseurM: 3, mention: '' }, 0, false)).toBeNull();
  });

  it('le rentrant est bien À L’INTÉRIEUR : l’anneau interne est plus petit du retrait, de chaque côté', () => {
    const interieur = anneauInterieur(ringENU(10, 8), 0.5)!;
    const xs = interieur.map(([x]) => x);
    const ys = interieur.map(([, y]) => y);
    expect(Math.max(...xs)).toBeCloseTo(4.5, 6); // 5 − 0,5
    expect(Math.max(...ys)).toBeCloseTo(3.5, 6); // 4 − 0,5
  });
});

// ═══════════════ CALX102 — la lucarne perce le pan ═══════════════

function chienAssis(over: Partial<Obstacle> = {}): Obstacle {
  return {
    id: 'obs-1',
    centerLng: 0,
    centerLat: 0,
    lengthM: 2, // nord-sud
    widthM: 3, // est-ouest
    type: 'chien_assis',
    heightM: 1.5,
    ...over,
  };
}

const ORIGINE: LngLat = [0, 0];

describe('CALX102 — lucarne : lue seulement quand sa hauteur est SAISIE', () => {
  it('sans hauteur saisie, aucun chien-assis n’est une lucarne (boîte d’aujourd’hui)', () => {
    expect(lucarnesDuPan([chienAssis({ heightM: undefined })], ORIGINE)).toEqual([]);
    expect(lucarnesDuPan([chienAssis({ type: 'cheminee' })], ORIGINE)).toEqual([]);
    expect(lucarnesDuPan(undefined, ORIGINE)).toEqual([]);
  });

  it('avec hauteur saisie : la pente est DÉRIVÉE de deux valeurs saisies, et dite', () => {
    const [l] = lucarnesDuPan([chienAssis()], ORIGINE);
    expect(l.hauteurM).toBe(1.5);
    // Faîtage sur le grand côté (3 m E-O) ⇒ pente depuis le demi-PETIT côté (1 m).
    expect(l.penteDeg).toBeCloseTo((Math.atan2(1.5, 1) * 180) / Math.PI, 6);
    expect(l.provenancePente).toContain('dérivée');
    expect(l.provenancePente).toContain('aucune pente forfaitaire');
  });
});

describe('CALX102 — le pan percé, et rien d’autre', () => {
  const ring = ringENU(20, 16);

  it('le maillage du pan perd EXACTEMENT l’emprise de la lucarne', () => {
    const lucarnes = lucarnesDuPan([chienAssis()], ORIGINE);
    const sans = new THREE.ShapeGeometry(percerPanLucarnes(ring, []).shape);
    const avec = new THREE.ShapeGeometry(percerPanLucarnes(ring, lucarnes).shape);
    const emprise = 2 * 3; // lengthM × widthM, SAISIS
    expect(aireMaillageM2(sans)).toBeCloseTo(20 * 16, 4);
    expect(aireMaillageM2(sans) - aireMaillageM2(avec)).toBeCloseTo(emprise, 4);
  });

  it('le percement se compte et se dit', () => {
    const p = percerPanLucarnes(ring, lucarnesDuPan([chienAssis()], ORIGINE));
    expect(p.percees).toEqual(['obs-1']);
    expect(p.aireRetireeM2).toBeCloseTo(6, 6);
    expect(p.shape.holes).toHaveLength(1);
    expect(p.nonPercees).toEqual([]);
  });

  it('une emprise qui mord la rive n’est PAS percée, et le motif est nommé', () => {
    const petit = ringENU(2, 2); // la lucarne 3 × 2 dépasse
    const p = percerPanLucarnes(petit, lucarnesDuPan([chienAssis()], ORIGINE));
    expect(p.percees).toEqual([]);
    expect(p.shape.holes).toHaveLength(0);
    expect(p.nonPercees[0].motif).toContain('hors du tracé');
  });

  it('sans lucarne, la forme du pan est celle d’aujourd’hui (aucun trou)', () => {
    const p = percerPanLucarnes(ring, []);
    expect(p.shape.holes).toHaveLength(0);
    expect(p.aireRetireeM2).toBe(0);
  });

  it('le percement est VISUEL : ni les obstacles ni le dégagement par type ne bougent', () => {
    const obstacles = [chienAssis()];
    const avant = JSON.parse(JSON.stringify(obstacles));
    const degagementAvant = CLEARANCE_BY_TYPE.chien_assis;
    percerPanLucarnes(ring, lucarnesDuPan(obstacles, ORIGINE));
    expect(obstacles).toEqual(avant); // l'entrée de l'optimiseur est intacte
    expect(CLEARANCE_BY_TYPE.chien_assis).toBe(degagementAvant); // jamais un second retrait
  });
});

describe('CALX102 — le volume à deux versants', () => {
  it('monte exactement à la hauteur SAISIE, est posé sur le pan et porte une ombre', () => {
    const [l] = lucarnesDuPan([chienAssis()], ORIGINE);
    const mesh = construireLucarne(l, 6.02, false)!;
    expect(mesh).toBeInstanceOf(THREE.Mesh);
    expect(mesh.castShadow).toBe(true);
    expect(mesh.position.z).toBeCloseTo(6.02, 6);
    const bbox = new THREE.Box3().setFromObject(mesh);
    expect(bbox.max.z - bbox.min.z).toBeCloseTo(1.5, 5);
    expect(bbox.max.x - bbox.min.x).toBeCloseTo(3, 4); // largeur SAISIE
    expect(bbox.max.y - bbox.min.y).toBeCloseTo(2, 4); // longueur SAISIE
  });

  it('le faîtage suit le GRAND côté saisi, dans les deux orientations', () => {
    const [eo] = lucarnesDuPan([chienAssis({ widthM: 4, lengthM: 2 })], ORIGINE);
    const [ns] = lucarnesDuPan([chienAssis({ widthM: 2, lengthM: 4 })], ORIGINE);
    // Le demi-petit côté vaut 1 m dans les deux cas ⇒ même pente dérivée.
    expect(eo.penteDeg).toBeCloseTo(ns.penteDeg, 6);
    const meshEO = construireLucarne(eo, 0, false)!;
    const posEO = meshEO.geometry.attributes.position as THREE.BufferAttribute;
    // Faîtage est-ouest : tous les sommets HAUTS sont à y = 0 (l'axe du grand côté).
    for (let i = 0; i < posEO.count; i++) {
      if (posEO.getZ(i) > 0) expect(Math.abs(posEO.getY(i))).toBeLessThan(1e-9);
    }
    const meshNS = construireLucarne(ns, 0, false)!;
    const posNS = meshNS.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < posNS.count; i++) {
      if (posNS.getZ(i) > 0) expect(Math.abs(posNS.getX(i))).toBeLessThan(1e-9);
    }
  });

  it('le volume est posé au CENTRE saisi de la lucarne, pas à l’origine de la scène', () => {
    const lucarnes = lucarnesDuPan([chienAssis()], ORIGINE, 12, -7);
    const bbox = new THREE.Box3().setFromObject(construireLucarne(lucarnes[0], 0, false)!);
    expect((bbox.max.x + bbox.min.x) / 2).toBeCloseTo(12, 4);
    expect((bbox.max.y + bbox.min.y) / 2).toBeCloseTo(-7, 4);
  });
});
