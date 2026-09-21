// CALX100 — le bâtiment vient du DOCUMENT (`buildings[]`, contrat CALX84), pas d'une
// constante : hauteur SAISIE + provenance. Testé HORS DOM et hors carte (pur).
import { describe, expect, it } from 'vitest';
import {
  HAUTEUR_DESSIN_M,
  ID_BATIMENT_SANS_ID,
  appliquerSaisie,
  batimentDuPan,
  emettreBatiments,
  hauteurExtrusion,
  idBatimentDuPan,
  lireBatiments,
  mentionEtages,
  serialiserBatiments,
  type Batiment,
} from './batiment';
import { serializeLayout } from './prefill';
import { FLOORS, FLOOR_HEIGHT_M } from './constants';
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
