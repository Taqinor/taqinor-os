// Tests ciblés de prefill.ts — la sérialisation CAL102 (mesures) + CAL57/CAL59 (arêtes
// typées, bâtiment). D'autres extensions v2 (CAL66/CAL67/CAL72…) ajouteront leurs propres
// describe() ici au lieu d'un fichier par tâche (même contrat v2, même fichier source).
import { describe, expect, it } from 'vitest';
import {
  serializeMeasurements,
  deserializeMeasurements,
  serializeEnvironment,
  deserializeEnvironment,
  serializeLayout,
  deserializeLayout,
  serializeSolarAccess,
  deserializeSolarAccess,
  deserializeSetbacksFromLayout,
  deserializeHorizonProfileFromLayout,
  hydrateFromDevis,
} from './prefill';
import { uniformSetbacks, type PerimeterSetbacks } from '../../lib/roofPro2';
import { type HorizonProfile } from '../../lib/horizonEngine';
import { type Measurement } from './mesureUi';
import { type EnvironmentObject } from './environment';
import { type Ctx } from './context';
import { type AreaRecord } from './types';
import { creerCoucheElectrique } from './electrique3d';

const VERTS: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

function zone(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'pitched',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    result: null,
    renderPlan: null,
    ...opts,
  };
}

function makeCtx(areas: AreaRecord[], activeId = areas[0].id): Ctx {
  const active = areas.find((a) => a.id === activeId)!;
  return {
    areas,
    activeAreaId: activeId,
    vertices: active.vertices,
    obstacles: active.obstacles,
    roofType: active.roofType,
    pitchDeg: active.pitchDeg,
    facingAzimuthDeg: active.facingAzimuthDeg,
    facingManual: active.facingManual ?? false,
    neededPanels: active.neededPanels,
    neededAuto: active.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
  } as unknown as Ctx;
}

describe('CAL102 — serializeMeasurements', () => {
  it('conserve les mesures géométriquement valides, intactes', () => {
    const list: Measurement[] = [
      { id: 'm1', kind: 'distance', points: [[0, 0], [0, 1]], label: 'côté sud' },
      { id: 'm2', kind: 'area', points: [[0, 0], [1, 0], [1, 1]] },
    ];
    expect(serializeMeasurements(list)).toEqual(list);
  });

  it('écarte une mesure géométriquement invalide pour son genre, sans toucher aux autres', () => {
    const list: Measurement[] = [
      { id: 'm1', kind: 'distance', points: [[0, 0]] }, // < 2 points : invalide
      { id: 'm2', kind: 'distance', points: [[0, 0], [0, 1]] }, // valide
    ];
    const out = serializeMeasurements(list);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('m2');
  });

  it('écarte une mesure sans id ou d’un genre inconnu', () => {
    const list = [
      { id: '', kind: 'distance', points: [[0, 0], [0, 1]] },
      { id: 'm2', kind: 'diagonale', points: [[0, 0], [0, 1]] },
    ] as unknown as Measurement[];
    expect(serializeMeasurements(list)).toEqual([]);
  });

  it('null/undefined/non-tableau → tableau vide (jamais une exception)', () => {
    expect(serializeMeasurements(null)).toEqual([]);
    expect(serializeMeasurements(undefined)).toEqual([]);
    expect(serializeMeasurements([] as Measurement[])).toEqual([]);
  });

  it('omet `label` quand absent (jamais `label: undefined` dans le JSON)', () => {
    const out = serializeMeasurements([{ id: 'm1', kind: 'distance', points: [[0, 0], [0, 1]] }]);
    expect('label' in out[0]).toBe(false);
  });
});

describe('CAL102 — deserializeMeasurements', () => {
  it('relit measurements depuis un layout complet', () => {
    const layout = { measurements: [{ id: 'm1', kind: 'distance', points: [[0, 0], [0, 1]] }] };
    expect(deserializeMeasurements(layout)).toEqual(layout.measurements);
  });

  it('accepte aussi un tableau brut directement', () => {
    const raw = [{ id: 'm1', kind: 'angle', points: [[0, 0], [1, 1], [1, 0]] }];
    expect(deserializeMeasurements(raw)).toEqual(raw);
  });

  it('round-trip : serializeMeasurements → deserializeMeasurements = identité (mesures valides)', () => {
    const list: Measurement[] = [{ id: 'm1', kind: 'distance', points: [[-7.6, 33.5], [-7.601, 33.5]], label: 'test' }];
    const written = { measurements: serializeMeasurements(list) };
    expect(deserializeMeasurements(written)).toEqual(list);
  });

  it('un JSON douteux (measurements absent/mal formé) → tableau vide, jamais une exception', () => {
    expect(deserializeMeasurements(null)).toEqual([]);
    expect(deserializeMeasurements({})).toEqual([]);
    expect(deserializeMeasurements({ measurements: 'nope' })).toEqual([]);
  });
});

describe('CAL67 — serializeEnvironment / deserializeEnvironment', () => {
  it('conserve un objet valide, intact', () => {
    const list: EnvironmentObject[] = [
      { id: 'e1', kind: 'arbre', centerLng: -7.6, centerLat: 33.5, heightM: 6, crownDiameterM: 4, evergreen: true },
    ];
    expect(serializeEnvironment(list)).toEqual(list);
  });

  it('écarte un objet sans id, de genre inconnu, ou aux coordonnées non finies', () => {
    const list = [
      { id: '', kind: 'arbre', centerLng: -7.6, centerLat: 33.5 },
      { id: 'e2', kind: 'ovni', centerLng: -7.6, centerLat: 33.5 },
      { id: 'e3', kind: 'arbre', centerLng: NaN, centerLat: 33.5 },
      { id: 'e4', kind: 'batiment', centerLng: -7.6, centerLat: 33.5 },
    ] as unknown as EnvironmentObject[];
    const out = serializeEnvironment(list);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('e4');
  });

  it('n’écrit heightM/crownDiameterM que s’ils sont finis et positifs (jamais 0 ou négatif)', () => {
    const out = serializeEnvironment([
      { id: 'e1', kind: 'arbre', centerLng: -7.6, centerLat: 33.5, heightM: 0, crownDiameterM: -2 } as EnvironmentObject,
    ]);
    expect('heightM' in out[0]).toBe(false);
    expect('crownDiameterM' in out[0]).toBe(false);
  });

  it('round-trip : serialize → deserialize = identité pour un objet valide', () => {
    const list: EnvironmentObject[] = [{ id: 'e1', kind: 'batiment', centerLng: -7.6, centerLat: 33.5, heightM: 5, lengthM: 8, widthM: 6 }];
    const written = { environment: serializeEnvironment(list) };
    expect(deserializeEnvironment(written)).toEqual(list);
  });

  it('null/undefined/mal formé → tableau vide, jamais une exception', () => {
    expect(deserializeEnvironment(null)).toEqual([]);
    expect(deserializeEnvironment({})).toEqual([]);
    expect(deserializeEnvironment({ environment: 'nope' })).toEqual([]);
  });
});

describe('CAL67 — serializeLayout porte l’environnement (additif)', () => {
  it('absent du layout quand ctx.environment est vide/undefined', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    expect('environment' in layout).toBe(false);
  });

  it('présent et round-trippable quand renseigné', () => {
    const areas = [zone('z1')];
    const ctx = makeCtx(areas);
    (ctx as unknown as { environment: EnvironmentObject[] }).environment = [
      { id: 'e1', kind: 'arbre', centerLng: -7.6002, centerLat: 33.4998, heightM: 6, crownDiameterM: 4 },
    ];
    const layout = serializeLayout(ctx);
    expect(layout.environment).toHaveLength(1);
    expect(deserializeEnvironment(layout)).toEqual(ctx.environment);
  });
});

describe('CAL57 — arêtes typées, sérialisées', () => {
  it('une zone seule (pas d’adjacence) porte un égout + des arêtes inconnues, jamais de faîtière', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    const z = layout.zones[0];
    expect(z.edges).toBeTruthy();
    expect(z.edges!.length).toBe(4);
    expect(z.edges!.some((e) => e.type === 'egout')).toBe(true);
    expect(z.edges!.some((e) => e.type === 'faitage')).toBe(false);
  });

  it('un document ancien SANS edges se relit sans en gagner (round-trip verbatim, pas de déduction à la lecture)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    delete (layout.zones[0] as { edges?: unknown }).edges;
    const back = deserializeLayout(layout);
    expect(back[0].edges).toBeUndefined();
  });

  it('les arêtes survivent à un aller-retour de sérialisation (round-trip)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    const back = deserializeLayout(layout);
    expect(back[0].edges).toEqual(layout.zones[0].edges);
  });
});

describe('CAL66/CAL72 — hauteur d’obstacle + provenance, sérialisées', () => {
  it('heightM et provenance survivent au round-trip quand renseignés', () => {
    const areas = [
      zone('z1', {
        obstacles: [{ id: 'o1', centerLng: -7.5995, centerLat: 33.5905, lengthM: 1, widthM: 1, heightM: 1.2, provenance: 'MESURE' }],
      }),
    ];
    const layout = serializeLayout(makeCtx(areas));
    expect(layout.zones[0].obstacles[0].heightM).toBe(1.2);
    expect(layout.zones[0].obstacles[0].provenance).toBe('MESURE');
    const back = deserializeLayout(layout);
    expect(back[0].obstacles[0].heightM).toBe(1.2);
    expect(back[0].obstacles[0].provenance).toBe('MESURE');
  });

  it('absents par défaut (comportement historique)', () => {
    const areas = [zone('z1', { obstacles: [{ id: 'o1', centerLng: -7.5995, centerLat: 33.5905, lengthM: 1, widthM: 1 }] })];
    const layout = serializeLayout(makeCtx(areas));
    expect('heightM' in layout.zones[0].obstacles[0]).toBe(false);
    expect('provenance' in layout.zones[0].obstacles[0]).toBe(false);
  });
});

describe('CAL59 — buildingId (multi-bâtiments)', () => {
  it('absent par défaut (bâtiment unique, comportement historique)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    expect('buildingId' in layout.zones[0]).toBe(false);
  });

  it('porté par zone quand renseigné, et survit au round-trip', () => {
    const areas = [zone('z1', { buildingId: 'bat-1' }), zone('z2', { buildingId: 'bat-2' })];
    const layout = serializeLayout(makeCtx(areas, 'z2'));
    expect(layout.zones.find((z) => z.id === 'z1')!.buildingId).toBe('bat-1');
    expect(layout.zones.find((z) => z.id === 'z2')!.buildingId).toBe('bat-2');
    const back = deserializeLayout(layout);
    expect(back.find((a) => a.id === 'z1')!.buildingId).toBe('bat-1');
    expect(back.find((a) => a.id === 'z2')!.buildingId).toBe('bat-2');
  });
});

// CAL248 — l'accès solaire par module vivait côté client et ne sortait jamais de l'écran.
// Il voyage désormais DANS le document, dans la forme figée par le contrat v2
// (`$defs/solarAccess` de roof_layout_v2.schema.json).
describe('CAL248 — accès solaire par module persisté dans le document', () => {
  /** Plan de rendu minimal : seuls les champs lus par `serializeLayout` sont fournis. */
  function planWith(panelCount: number) {
    const panels = Array.from({ length: panelCount }, (_, i) => ({ cx: i * 1.2, cy: 0 }));
    return {
      pack: { origin: [-7.6, 33.59] as [number, number], azimuthDeg: 180 },
      grid: { panels, kwc: panelCount * 0.72 },
      tiltDeg: 15,
      family: 'south',
      flush: false,
      count: panelCount,
    } as unknown as AreaRecord['renderPlan'];
  }
  const access = (values: Array<number | null>) => ({
    values,
    method: 'Astronomie + lancer de rayon sur les obstructions renseignées, pondéré par le profil horaire du lieu.',
    assumptions: { periode: 'annee-entiere' },
    computedAt: '2026-09-20T10:00:00.000Z',
  });

  it('absent par défaut : un document SANS accès solaire reste identique à aujourd’hui', () => {
    const areas = [zone('z1', { renderPlan: planWith(3) })];
    const layout = serializeLayout(makeCtx(areas));
    expect(layout.zones[0].geometry).toBeTruthy();
    expect('solarAccess' in (layout.zones[0].geometry as object)).toBe(false);
  });

  it('écrit par zone, avec valeurs / méthode / hypothèses / date de calcul', () => {
    const areas = [zone('z1', { renderPlan: planWith(3) })];
    const layout = serializeLayout(makeCtx(areas), null, {
      solarAccessByZone: { z1: access([0.98, 0.6, 0.42]) },
    });
    const sa = layout.zones[0].geometry!.solarAccess!;
    expect(sa.values).toEqual([0.98, 0.6, 0.42]);
    expect(sa.method.length).toBeGreaterThan(10);
    expect(sa.assumptions).toEqual({ periode: 'annee-entiere' });
    expect(sa.computedAt).toBe('2026-09-20T10:00:00.000Z');
  });

  it('aller-retour JSON : les valeurs sont conservées à l’identique', () => {
    const areas = [zone('z1', { renderPlan: planWith(3) })];
    const layout = serializeLayout(makeCtx(areas), null, {
      solarAccessByZone: { z1: access([0.98, 0.6, 0.42]) },
    });
    const round = JSON.parse(JSON.stringify(layout));
    expect(deserializeSolarAccess(round.zones[0].geometry, 3)).toEqual(layout.zones[0].geometry!.solarAccess);
  });

  it('un document SANS accès solaire se relit sans erreur (jamais une valeur reconstituée)', () => {
    expect(deserializeSolarAccess(undefined, 3)).toBeNull();
    expect(deserializeSolarAccess({}, 3)).toBeNull();
    expect(deserializeSolarAccess({ solarAccess: { values: [] } }, 3)).toBeNull();
  });

  it('valeurs DÉCALÉES (longueur ≠ nombre de modules) : rien n’est écrit, jamais complété', () => {
    const areas = [zone('z1', { renderPlan: planWith(3) })];
    const layout = serializeLayout(makeCtx(areas), null, {
      solarAccessByZone: { z1: access([0.9, 0.8]) },
    });
    expect('solarAccess' in (layout.zones[0].geometry as object)).toBe(false);
  });

  it('une valeur aberrante devient null (non calculé), jamais corrigée en silence', () => {
    const sa = serializeSolarAccess(access([1.4, -0.2, 0.5]), 3);
    expect(sa!.values).toEqual([null, null, 0.5]);
  });

  it('rien de calculé du tout → rien d’écrit (aucun module à 100 % par défaut)', () => {
    expect(serializeSolarAccess(access([null, null, null]), 3)).toBeNull();
  });

  it('NON-RÉGRESSION : les autres chiffres du document ne bougent pas', () => {
    const areas = [zone('z1', { renderPlan: planWith(3) })];
    const sans = serializeLayout(makeCtx(areas));
    const avec = serializeLayout(makeCtx(areas), null, { solarAccessByZone: { z1: access([1, 0.5, 0.5]) } });
    expect(avec.result).toEqual(sans.result);
    expect(avec.zones[0].geometry!.count).toBe(sans.zones[0].geometry!.count);
    expect(avec.zones[0].geometry!.kwc).toBe(sans.zones[0].geometry!.kwc);
    expect(avec.zones[0].geometry!.panels).toEqual(sans.zones[0].geometry!.panels);
  });
});

describe('CAL76 — les quatre retraits de rive (setbacksM) persistés dans le document', () => {
  it('absent par défaut : un document sans setbacksM ne porte pas la clé', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    expect('setbacksM' in layout).toBe(false);
  });

  it('écrit à la racine quand fourni par l’appelant (meta.setbacksM)', () => {
    const areas = [zone('z1')];
    const setbacks: PerimeterSetbacks = { lateralM: 0.6, extremityM: 0.7, parapetM: 0.4, jointM: 0.3 };
    const layout = serializeLayout(makeCtx(areas), null, { setbacksM: setbacks });
    expect(layout.setbacksM).toEqual(setbacks);
  });

  it('aller-retour JSON : les quatre valeurs sont conservées à l’identique', () => {
    const areas = [zone('z1')];
    const setbacks: PerimeterSetbacks = { lateralM: 0.6, extremityM: 0.7, parapetM: 0.4, jointM: 0.3 };
    const layout = serializeLayout(makeCtx(areas), null, { setbacksM: setbacks });
    const round = JSON.parse(JSON.stringify(layout));
    expect(deserializeSetbacksFromLayout(round)).toEqual(setbacks);
  });

  it('un document SANS setbacksM (antérieur à CAL76) se relit sans erreur : null, jamais une valeur inventée', () => {
    expect(deserializeSetbacksFromLayout(undefined)).toBeNull();
    expect(deserializeSetbacksFromLayout({})).toBeNull();
  });

  it('valeur douteuse dans le JSON (négative, non finie) : assainie, jamais une exception', () => {
    const cleaned = deserializeSetbacksFromLayout({
      setbacksM: { lateralM: -1, extremityM: Number.NaN, parapetM: 0.4, jointM: -0.5 },
    });
    expect(cleaned).toEqual({ lateralM: 0, extremityM: expect.any(Number), parapetM: 0.4, jointM: 0 });
  });

  it('NON-RÉGRESSION : écrire setbacksM ne change aucun autre chiffre du document', () => {
    const areas = [zone('z1')];
    const sans = serializeLayout(makeCtx(areas));
    const avec = serializeLayout(makeCtx(areas), null, { setbacksM: uniformSetbacks(0.5) });
    expect(avec.result).toEqual(sans.result);
    expect(avec.zones).toEqual(sans.zones);
  });
});

describe('CAL93 — le profil d’horizon lointain (horizonProfile) persisté dans le document', () => {
  const profil: HorizonProfile = {
    source: 'saisie',
    points: [{ azimuthDeg: 90, heightDeg: 8 }, { azimuthDeg: 270, heightDeg: 12 }],
    hauteurMaxDeg: 12,
  };

  it('absent par défaut : un document sans horizonProfile ne porte pas la clé', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    expect('horizonProfile' in layout).toBe(false);
  });

  it('moins de deux points exploitables : rien n’est écrit', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas), null, {
      horizonProfile: { source: 'saisie', points: [{ azimuthDeg: 90, heightDeg: 8 }], hauteurMaxDeg: 8 },
    });
    expect('horizonProfile' in layout).toBe(false);
  });

  it('écrit à la racine, points triés et hauteurMaxDeg RECALCULÉE (jamais recopiée)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas), null, {
      horizonProfile: { ...profil, hauteurMaxDeg: 999 }, // valeur fausse fournie, doit être ignorée
    });
    expect(layout.horizonProfile!.hauteurMaxDeg).toBe(12);
    expect(layout.horizonProfile!.points.map((p) => p.azimuthDeg)).toEqual([90, 270]);
  });

  it('aller-retour JSON : le profil est conservé à l’identique', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas), null, { horizonProfile: profil });
    const round = JSON.parse(JSON.stringify(layout));
    expect(deserializeHorizonProfileFromLayout(round)).toEqual(profil);
  });

  it('un document SANS horizonProfile (antérieur à CAL93) se relit sans erreur : null', () => {
    expect(deserializeHorizonProfileFromLayout(undefined)).toBeNull();
    expect(deserializeHorizonProfileFromLayout({})).toBeNull();
    expect(deserializeHorizonProfileFromLayout({ horizonProfile: { source: 'saisie', points: [{ azimuthDeg: 1, heightDeg: 2 }] } })).toBeNull();
  });

  it('NON-RÉGRESSION : écrire horizonProfile ne change aucun autre chiffre du document', () => {
    const areas = [zone('z1')];
    const sans = serializeLayout(makeCtx(areas));
    const avec = serializeLayout(makeCtx(areas), null, { horizonProfile: profil });
    expect(avec.result).toEqual(sans.result);
    expect(avec.zones).toEqual(sans.zones);
  });
});

/* ────────────────────────────────────────────────────────────────────────────
   CAL37 — `cibleVendue` : la différence entre « rien de vendu » et « zéro vendu ».
   Un DEVIS sans ligne panneau est une cible vendue de ZÉRO (incident
   DEV-202608-0016) : l'optimiseur ne doit RIEN poser. Un CALEPINAGE sans devis
   lié (contrat `calepinage_design_context.json` : `cible: null`) n'a aucune
   vente derrière lui : l'optimiseur doit poser ce qui tient, comme pour un lead
   sans facture. Le drapeau est ce qui distingue les deux — absent, le
   comportement devis/AO est strictement celui d'avant.
   ──────────────────────────────────────────────────────────────────────────── */
describe('hydrateFromDevis — cible vendue vs cible absente (CAL37)', () => {
  const geometrie = {
    roof_layout: null,
    roof_point: { lat: 33.5731, lng: -7.5898 },
    roof_outline: [
      [33.5731, -7.5898],
      [33.5732, -7.5898],
      [33.5732, -7.5897],
    ] as Array<[number, number]>,
  };

  it('drapeau ABSENT (devis, AO) : cible vendue — comportement inchangé', () => {
    const h = hydrateFromDevis({ id: 412, geometrie, cible: { panneaux: null } });
    expect(h.cibleVendue).toBe(true);
    expect(h.neededPanels).toBeNull();
  });

  it('cibleVendue: false (calepinage sans devis) : aucune cible vendue', () => {
    const h = hydrateFromDevis({ id: null, geometrie, cible: { panneaux: null }, cibleVendue: false });
    expect(h.cibleVendue).toBe(false);
    // Le pan vient quand même du tracé client, et la carte a son centre.
    expect(h.vertices.length).toBe(3);
    expect(h.center).toEqual([-7.5898, 33.5731]);
  });

  it('un calepinage avec devis lié garde la cible VENDUE et son imposition', () => {
    const h = hydrateFromDevis({ id: null, geometrie, cible: { panneaux: 12 }, cibleVendue: true });
    expect(h.cibleVendue).toBe(true);
    expect(h.neededPanels).toBe(12);
    expect(h.neededAuto).toBe(false);
  });
});

/* ────────────────────────────────────────────────────────────────────────────
   CALX22x câblage — `serializeLayout` porte la couche électrique (crochet 1/4).
   La logique d'écriture n'est JAMAIS recopiée ici : elle reste entièrement
   déléguée à `couche.ecrireDansDocument` (electrique3d.ts, CALX219-221/223).
   Un document sans organe ni cheminement ne porte pas la clé `electrical`.
   ──────────────────────────────────────────────────────────────────────────── */
describe('CALX22x câblage — serializeLayout porte `electrical` via couche.ecrireDansDocument', () => {
  it('absente du layout quand aucune `meta.coucheElectrique` n’est fournie (comportement historique)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    expect('electrical' in layout).toBe(false);
  });

  it('absente quand la couche fournie ne porte encore aucun organe ni cheminement', () => {
    const areas = [zone('z1')];
    const couche = creerCoucheElectrique({});
    const layout = serializeLayout(makeCtx(areas), null, { coucheElectrique: couche });
    expect('electrical' in layout).toBe(false);
  });

  it('présente, avec la forme EXACTE écrite par la couche, dès qu’un organe est posé', () => {
    const areas = [zone('z1')];
    const couche = creerCoucheElectrique({});
    couche.armerPose('onduleur');
    couche.poser([-7.6002, 33.5001], { label: 'Onduleur toiture' });
    const layout = serializeLayout(makeCtx(areas), null, { coucheElectrique: couche });
    expect(layout.electrical).toEqual(couche.documentElectrique());
    // Le crochet d'export ne partage AUCUNE référence avec l'état vivant de la couche.
    expect(layout.electrical).not.toBe(couche.documentElectrique());
  });

  it('un cheminement seul (sans équipement) suffit aussi à porter la clé', () => {
    const areas = [zone('z1')];
    const couche = creerCoucheElectrique({ areas: [{ id: 'z1' }] });
    const fait = couche.saisirCheminement({ cote: 'dc', de: 'z1', vers: 'z1', longueurM: 5 });
    expect(fait.ok).toBe(true);
    const layout = serializeLayout(makeCtx(areas), null, { coucheElectrique: couche });
    expect(layout.electrical?.cheminements).toHaveLength(1);
  });

  it('NON-RÉGRESSION : porter `electrical` ne change aucun autre chiffre du document', () => {
    const areas = [zone('z1')];
    const sans = serializeLayout(makeCtx(areas));
    const couche = creerCoucheElectrique({});
    couche.armerPose('tgbt');
    couche.poser([-7.6, 33.5]);
    const avec = serializeLayout(makeCtx(areas), null, { coucheElectrique: couche });
    expect(avec.result).toEqual(sans.result);
    expect(avec.zones).toEqual(sans.zones);
  });
});
