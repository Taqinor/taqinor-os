// @vitest-environment jsdom
//
/**
 * CALX107 — LE CALQUE DE FOND CALÉ : ce que ce fichier garde.
 *
 * 1. `underlay` ABSENT ⇒ AUCUNE source n'est ajoutée et le style de carte est identique à
 *    celui d'aujourd'hui (aucune clé écrite dans le document non plus).
 * 2. `underlay` PRÉSENT ⇒ la couche existe, au RANG prévu par `ORDRE_RENDU_CALQUES`, et
 *    son opacité suit le réglage.
 * 3. La PHOTO se place depuis les QUATRE coins de `PhotoSite` (CAL53), jamais depuis un
 *    calage à deux points — qui lui est refusé en nommant `calage` (contrat CALX86).
 * 4. Chaque refus NOMME son champ : jamais un « non affiché » générique.
 *
 * Les fonds de référence sont ceux du contrat, recopiés de
 * `backend/django_core/apps/calepinage/tests/test_calx86_underlay.py`
 * (`EXEMPLE_PLAN` / `EXEMPLE_PHOTO`) : les lanes 3D les lisent TELS QUELS.
 */
import { describe, expect, it, vi } from 'vitest';
import {
  CALQUE_PAR_GENRE,
  coinsDepuisCalagePhoto,
  coucheAvantPourFond,
  GENRES_FOND,
  idCoucheFond,
  lireCalageDeuxPoints,
  lireUnderlay,
  OPACITE_FOND_PAR_DEFAUT,
  placementDuFond,
  specCoucheFond,
  specSourceFond,
  UNDERLAY_PHOTO_LAYER_ID,
  UNDERLAY_PLAN_LAYER_ID,
  underlayPourDocument,
  type DocumentUnderlay,
} from './underlay';
import { createMapDraw, MAPLIBRE_LAYERS_PAR_CALQUE, ORDRE_RENDU_CALQUES, opacityPropFor } from './mapDraw';
import { type Ctx } from './context';
import { type LngLat } from '../../lib/roof';

/** `EXEMPLE_PLAN` du contrat CALX86 — un plan calé à deux points, distance SAISIE. */
const EXEMPLE_PLAN = {
  kind: 'plan',
  attachmentId: 3071,
  opacite: 0.6,
  calage: {
    ancre: [
      [0.0, 0.0],
      [10.0, 0.0],
    ],
    pointsImage: [
      [120.0, 840.0],
      [1080.0, 840.0],
    ],
    distanceReelleM: 10.0,
    rotationDeg: 0,
    source: 'cote lue sur le plan',
  },
};

/** `EXEMPLE_PHOTO` du contrat CALX86 — déjà calée à quatre coins, donc AUCUN `calage`. */
const EXEMPLE_PHOTO = {
  kind: 'photo',
  photoSiteId: 918,
  attachmentId: null,
  opacite: 0.45,
};

/** `PhotoSite.calage` tel que `services/photos.py` le stocke : 4 coins `[lat, lng]`, dans
 *  l'ordre de pose des poignées (haut-gauche → haut-droite → bas-droite → bas-gauche). */
const CALAGE_PHOTO = {
  coins: [
    [33.2, -7.2],
    [33.2, -7.1],
    [33.1, -7.1],
    [33.1, -7.2],
  ],
};

describe('CALX107 — les deux calques de fond pilotent enfin de vraies couches', () => {
  it('`photo` et `plan` ne pilotent plus une liste VIDE', () => {
    expect(MAPLIBRE_LAYERS_PAR_CALQUE.photo).toEqual([UNDERLAY_PHOTO_LAYER_ID]);
    expect(MAPLIBRE_LAYERS_PAR_CALQUE.plan).toEqual([UNDERLAY_PLAN_LAYER_ID]);
  });

  it('les identifiants sont ceux annoncés par la tâche', () => {
    expect(UNDERLAY_PLAN_LAYER_ID).toBe('rp9-underlay-plan');
    expect(UNDERLAY_PHOTO_LAYER_ID).toBe('rp9-underlay-photo');
    expect(idCoucheFond('plan')).toBe(UNDERLAY_PLAN_LAYER_ID);
    expect(idCoucheFond('photo')).toBe(UNDERLAY_PHOTO_LAYER_ID);
  });

  it('chaque genre appartient au calque du panneau qui porte son nom', () => {
    expect(CALQUE_PAR_GENRE.plan).toBe('plan');
    expect(CALQUE_PAR_GENRE.photo).toBe('photo');
    for (const genre of GENRES_FOND) expect(ORDRE_RENDU_CALQUES).toContain(CALQUE_PAR_GENRE[genre]);
  });

  it('les deux calques de fond sont SOUS le tracé et AU-DESSUS de l’imagerie', () => {
    const rang = (id: string) => ORDRE_RENDU_CALQUES.indexOf(id);
    expect(rang('imagerie')).toBeLessThan(rang('photo'));
    expect(rang('photo')).toBeLessThan(rang('trace_client'));
    expect(rang('plan')).toBeLessThan(rang('trace_client'));
  });
});

describe('CALX107 — `underlay` absent : rien n’est ajouté, rien n’est écrit', () => {
  it('un contexte sans fond n’écrit AUCUNE clé dans le document', () => {
    expect(underlayPourDocument({})).toEqual({});
    expect(underlayPourDocument({ underlay: null })).toEqual({});
    expect(underlayPourDocument(null)).toEqual({});
    expect(underlayPourDocument(undefined)).toEqual({});
    expect(Object.prototype.hasOwnProperty.call(underlayPourDocument({}), 'underlay')).toBe(false);
  });

  it('un fond INVALIDE n’est jamais écrit à moitié — la clé reste absente', () => {
    expect(underlayPourDocument({ underlay: { kind: 'satellite' } })).toEqual({});
    expect(underlayPourDocument({ underlay: { kind: 'plan' } })).toEqual({}); // sans fichier
    expect(underlayPourDocument({ underlay: { kind: 'photo', photoSiteId: 9, calage: EXEMPLE_PLAN.calage } })).toEqual({});
  });

  it('un fond valide voyage par le document, tel que le contrat le décrit', () => {
    const doc = underlayPourDocument({ underlay: EXEMPLE_PLAN });
    expect(doc.underlay?.kind).toBe('plan');
    expect(doc.underlay?.attachmentId).toBe(3071);
    expect(doc.underlay?.opacite).toBe(0.6);
    expect(doc.underlay?.calage?.distanceReelleM).toBe(10);
    expect(doc.underlay?.calage?.source).toBe('cote lue sur le plan');
    const photo = underlayPourDocument({ underlay: EXEMPLE_PHOTO });
    expect(photo.underlay?.kind).toBe('photo');
    expect(photo.underlay?.photoSiteId).toBe(918);
    expect(photo.underlay?.calage).toBeUndefined();
  });
});

describe('CALX107 — lecture du contrat CALX86 : chaque refus NOMME son champ', () => {
  it('les deux fonds d’exemple du contrat sont acceptés tels quels', () => {
    expect(lireUnderlay(EXEMPLE_PLAN).ok).toBe(true);
    expect(lireUnderlay(EXEMPLE_PHOTO).ok).toBe(true);
  });

  it('un genre inconnu est refusé sur `kind` (énumération FERMÉE)', () => {
    const r = lireUnderlay({ kind: 'dxf', attachmentId: 1 });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('kind');
    expect(r.motif).toContain('dxf');
  });

  it('un plan sans fichier est refusé sur `attachmentId`', () => {
    const r = lireUnderlay({ kind: 'plan' });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('attachmentId');
    expect(r.motif).toContain('attachmentId');
  });

  it('une photo sans PhotoSite est refusée sur `photoSiteId`', () => {
    const r = lireUnderlay({ kind: 'photo' });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('photoSiteId');
  });

  it('une PHOTO porteuse d’un calage à deux points est refusée sur `calage`', () => {
    const r = lireUnderlay({ ...EXEMPLE_PHOTO, calage: EXEMPLE_PLAN.calage });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('calage');
    expect(r.motif).toContain('quatre coins');
  });

  it('une opacité hors [0, 1] est refusée sur `opacite`', () => {
    for (const o of [-0.1, 1.5, Number.NaN, 'moitié']) {
      const r = lireUnderlay({ ...EXEMPLE_PLAN, opacite: o });
      expect(r.ok).toBe(false);
      if (r.ok) throw new Error('refus attendu');
      expect(r.champ).toBe('opacite');
    }
  });

  it('un calage sans distance réelle est refusé, et le motif dit qu’aucune échelle n’est déduite', () => {
    const { distanceReelleM, ...sansDistance } = EXEMPLE_PLAN.calage;
    expect(distanceReelleM).toBe(10);
    const r = lireUnderlay({ ...EXEMPLE_PLAN, calage: sansDistance });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('calage');
    expect(r.motif).toContain('distanceReelleM');
    expect(r.motif).toContain('déduite du fichier');
  });

  it('un calage sans `source` est refusé : deux plans calés autrement ne sont pas comparables', () => {
    const { source, ...sansSource } = EXEMPLE_PLAN.calage;
    expect(source).toBe('cote lue sur le plan');
    const r = lireCalageDeuxPoints(sansSource);
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.motif).toContain('source');
  });
});

describe('CALX107 — la PHOTO se place par ses QUATRE coins (CAL53), jamais autrement', () => {
  it('les coins `[lat, lng]` du stockage deviennent des `[lng, lat]` MapLibre, sans réordonner', () => {
    const r = coinsDepuisCalagePhoto(CALAGE_PHOTO);
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('placement attendu');
    expect(r.coins).toEqual([
      [-7.2, 33.2],
      [-7.1, 33.2],
      [-7.1, 33.1],
      [-7.2, 33.1],
    ]);
  });

  it('une photo NON calée n’est pas placée, et le motif le dit', () => {
    for (const calage of [null, undefined, {}, { coins: [] }, { coins: [[33.1, -7.1]] }]) {
      const r = coinsDepuisCalagePhoto(calage);
      expect(r.ok).toBe(false);
      if (r.ok) throw new Error('refus attendu');
      expect(r.motif).toContain('quatre coins');
    }
  });

  it('un coin hors amplitude GPS est refusé', () => {
    const r = coinsDepuisCalagePhoto({ coins: [[91, -7.2], [33.2, -7.1], [33.1, -7.1], [33.1, -7.2]] });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.motif).toContain('amplitude GPS');
  });

  it('le placement d’une photo ignore tout calage à deux points qu’on lui tendrait', () => {
    const fond = (lireUnderlay(EXEMPLE_PHOTO) as { ok: true; fond: DocumentUnderlay }).fond;
    const p = placementDuFond(fond, {
      url: 'https://exemple/photo.jpg',
      calagePhoto: CALAGE_PHOTO,
      coinsPlan: [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 1],
      ],
    });
    expect(p.ok).toBe(true);
    if (!p.ok) throw new Error('placement attendu');
    expect(p.layerId).toBe(UNDERLAY_PHOTO_LAYER_ID);
    // Les coins viennent de PhotoSite, PAS de `coinsPlan`.
    expect(p.coins[0]).toEqual([-7.2, 33.2]);
  });
});

describe('CALX107 — le placement et ses refus', () => {
  const planValide = (lireUnderlay(EXEMPLE_PLAN) as { ok: true; fond: DocumentUnderlay }).fond;
  const coinsPlan: LngLat[] = [
    [-7.62, 33.58],
    [-7.61, 33.58],
    [-7.61, 33.57],
    [-7.62, 33.57],
  ];

  it('sans URL de fichier, rien n’est peint — le refus nomme `url`', () => {
    const r = placementDuFond(planValide, { coinsPlan });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('url');
  });

  it('un plan NON calé n’est pas placé — le refus nomme `calage` et redit la règle', () => {
    const r = placementDuFond(planValide, { url: 'https://exemple/plan.png' });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('calage');
    expect(r.motif).toContain('distance réelle');
    expect(r.motif).toContain('déduite du fichier');
  });

  it('un plan calé rend une source `image` géo-référencée par ses quatre coins', () => {
    const r = placementDuFond(planValide, { url: 'https://exemple/plan.png', coinsPlan });
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('placement attendu');
    const source = specSourceFond(r);
    expect(source.type).toBe('image');
    expect(source.url).toBe('https://exemple/plan.png');
    expect(source.coordinates).toEqual(coinsPlan);
  });

  it('l’opacité SAISIE du document pilote la couche ; absente, la convention de dessin s’applique', () => {
    const avecOpacite = placementDuFond(planValide, { url: 'u', coinsPlan });
    if (!avecOpacite.ok) throw new Error('placement attendu');
    expect(avecOpacite.opacite).toBe(0.6);
    expect(specCoucheFond(avecOpacite).paint['raster-opacity']).toBe(0.6);

    const sansOpacite = placementDuFond({ kind: 'plan', attachmentId: 1 }, { url: 'u', coinsPlan });
    if (!sansOpacite.ok) throw new Error('placement attendu');
    expect(sansOpacite.opacite).toBe(OPACITE_FOND_PAR_DEFAUT);
  });

  it('la couche est de type `raster` : le panneau de calques la pilote par `raster-opacity`', () => {
    const r = placementDuFond(planValide, { url: 'u', coinsPlan });
    if (!r.ok) throw new Error('placement attendu');
    const couche = specCoucheFond(r);
    expect(couche.type).toBe('raster');
    expect(couche.id).toBe(UNDERLAY_PLAN_LAYER_ID);
    expect(couche.source).toBe(UNDERLAY_PLAN_LAYER_ID);
    expect(opacityPropFor(couche.type)).toBe('raster-opacity');
  });
});

describe('CALX107 — rang d’insertion : le fond atterrit sous le tracé', () => {
  const installee = (ids: string[]) => (id: string) => ids.includes(id);

  it('le fond s’insère AVANT la première couche d’un calque situé au-dessus', () => {
    const avant = coucheAvantPourFond(
      'photo',
      ORDRE_RENDU_CALQUES,
      MAPLIBRE_LAYERS_PAR_CALQUE,
      installee(['rp9-ref-contour-fill', 'rp9-obs']),
    );
    expect(avant).toBe('rp9-ref-contour-fill');
  });

  it('rien au-dessus n’étant posé, l’ajout se fait en fin de pile (aucun `beforeId`)', () => {
    expect(coucheAvantPourFond('plan', ORDRE_RENDU_CALQUES, MAPLIBRE_LAYERS_PAR_CALQUE, installee([]))).toBeUndefined();
  });

  it('une couche d’un calque situé EN DESSOUS n’est jamais choisie', () => {
    const avant = coucheAvantPourFond(
      'plan',
      ORDRE_RENDU_CALQUES,
      MAPLIBRE_LAYERS_PAR_CALQUE,
      installee(['rp9-opt-cadastre', UNDERLAY_PHOTO_LAYER_ID]),
    );
    expect(avant).toBeUndefined();
  });

  it('une carte dont le style n’est pas prêt (getLayer qui lève) ne fait jamais tomber le calcul', () => {
    expect(
      coucheAvantPourFond('photo', ORDRE_RENDU_CALQUES, MAPLIBRE_LAYERS_PAR_CALQUE, () => {
        throw new Error('style pas encore chargé');
      }),
    ).toBeUndefined();
  });

  it('un calque inconnu ne propose aucun rang', () => {
    expect(coucheAvantPourFond('inexistant', ORDRE_RENDU_CALQUES, MAPLIBRE_LAYERS_PAR_CALQUE, installee([]))).toBeUndefined();
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX107 — LE FOND SUR LA CARTE RÉELLE (`createMapDraw`).
//
// Carte MapLibre FACTICE qui enregistre ce qu'on lui demande : c'est elle qui prouve la
// promesse « `underlay` absent ⇒ AUCUNE source ajoutée, style identique à aujourd'hui ».
// ————————————————————————————————————————————————————————————————————————

interface CoucheFactice {
  id: string;
  type?: string;
  avant?: string;
  paint?: Record<string, unknown>;
  layout: Record<string, unknown>;
}

function carteFactice() {
  const sources = new Map<string, unknown>();
  const couches = new Map<string, CoucheFactice>();
  /** Ordre d'insertion RÉEL de la pile, `beforeId` respecté (comme MapLibre). */
  const pile: string[] = [];
  const map = {
    getSource: (id: string) => sources.get(id),
    addSource: (id: string, spec: unknown) => {
      sources.set(id, spec);
    },
    removeSource: (id: string) => {
      sources.delete(id);
    },
    getLayer: (id: string) => couches.get(id),
    addLayer: (spec: { id: string; type?: string; paint?: Record<string, unknown> }, avant?: string) => {
      couches.set(spec.id, { ...spec, avant, layout: {} });
      const at = avant ? pile.indexOf(avant) : -1;
      if (at >= 0) pile.splice(at, 0, spec.id);
      else pile.push(spec.id);
    },
    removeLayer: (id: string) => {
      couches.delete(id);
      const at = pile.indexOf(id);
      if (at >= 0) pile.splice(at, 1);
    },
    setLayoutProperty: (id: string, prop: string, val: unknown) => {
      const c = couches.get(id);
      if (c) c.layout[prop] = val;
    },
    setPaintProperty: (id: string, prop: string, val: unknown) => {
      const c = couches.get(id);
      if (c) c.paint = { ...(c.paint ?? {}), [prop]: val };
    },
    on: vi.fn(),
    getZoom: () => 19,
    getCenter: () => ({ lng: -7.62, lat: 33.58 }),
    getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }),
  };
  return { map, sources, couches, pile };
}

function harnaisMapDraw() {
  document.body.innerHTML = '';
  const { map, sources, couches, pile } = carteFactice();
  const ctx = {
    opts: { maptilerKey: 'K', imagery: { pays: 'ma' }, reducedMotion: true },
    vertices: [] as LngLat[],
    obstacles: [],
    areas: [],
    activeAreaId: 'a1',
    closed: false,
    centroid: [-7.62, 33.58] as LngLat,
  } as unknown as Ctx;
  const setStatus = vi.fn();
  const draw = createMapDraw(ctx, { map: map as never, setStatus, updateAreaReadout: vi.fn() });
  return { draw, ctx, map, sources, couches, pile, setStatus };
}

const COINS_PLAN: LngLat[] = [
  [-7.63, 33.59],
  [-7.61, 33.59],
  [-7.61, 33.57],
  [-7.63, 33.57],
];

describe('CALX107 — `underlay` absent : le style de carte est celui d’aujourd’hui', () => {
  it('construire l’atelier n’ajoute AUCUNE source ni couche de fond', () => {
    const { sources, couches } = harnaisMapDraw();
    expect(sources.has(UNDERLAY_PLAN_LAYER_ID)).toBe(false);
    expect(sources.has(UNDERLAY_PHOTO_LAYER_ID)).toBe(false);
    expect(couches.has(UNDERLAY_PLAN_LAYER_ID)).toBe(false);
    expect(couches.has(UNDERLAY_PHOTO_LAYER_ID)).toBe(false);
  });

  it('sans fond, le document ne porte aucune clé `underlay` et `fond()` rend null', () => {
    const { draw, ctx } = harnaisMapDraw();
    expect(draw.fond()).toBeNull();
    expect(underlayPourDocument(ctx)).toEqual({});
  });

  it('basculer les calques `photo`/`plan` sans fond reste le no-op silencieux d’aujourd’hui', () => {
    const { draw, sources, couches } = harnaisMapDraw();
    expect(draw.setLayerState('photo', { visible: false, opacite: 0.3 })).toBe(true);
    expect(draw.setLayerState('plan', { visible: true, opacite: 1 })).toBe(true);
    expect(sources.size).toBe(0);
    expect(couches.size).toBe(0);
  });
});

describe('CALX107 — `underlay` présent : la couche existe, au bon rang, à la bonne opacité', () => {
  it('un plan calé pose sa source `image` et sa couche raster', () => {
    const { draw, sources, couches } = harnaisMapDraw();
    const r = draw.setFond(
      { kind: 'plan', attachmentId: 3071, opacite: 0.6 },
      { url: 'https://exemple/plan.png', coinsPlan: COINS_PLAN },
    );
    expect(r.ok).toBe(true);
    expect(sources.get(UNDERLAY_PLAN_LAYER_ID)).toEqual({
      type: 'image',
      url: 'https://exemple/plan.png',
      coordinates: COINS_PLAN,
    });
    expect(couches.get(UNDERLAY_PLAN_LAYER_ID)?.type).toBe('raster');
    expect(couches.get(UNDERLAY_PLAN_LAYER_ID)?.paint?.['raster-opacity']).toBe(0.6);
  });

  it('la couche s’insère SOUS le tracé client, au rang de `ORDRE_RENDU_CALQUES`', () => {
    const { draw, map, pile } = harnaisMapDraw();
    // Le tracé client est déjà installé : le fond doit passer DESSOUS.
    map.addLayer({ id: 'rp9-ref-contour-fill', type: 'fill' });
    draw.setFond({ kind: 'plan', attachmentId: 1 }, { url: 'u', coinsPlan: COINS_PLAN });
    expect(pile.indexOf(UNDERLAY_PLAN_LAYER_ID)).toBeLessThan(pile.indexOf('rp9-ref-contour-fill'));
  });

  it('l’opacité du panneau de calques pilote la couche de fond (CAL103)', () => {
    const { draw, couches } = harnaisMapDraw();
    draw.setFond({ kind: 'plan', attachmentId: 1, opacite: 0.6 }, { url: 'u', coinsPlan: COINS_PLAN });
    expect(draw.setLayerState('plan', { visible: true, opacite: 0.2 })).toBe(true);
    expect(couches.get(UNDERLAY_PLAN_LAYER_ID)?.paint?.['raster-opacity']).toBe(0.2);
    expect(couches.get(UNDERLAY_PLAN_LAYER_ID)?.layout.visibility).toBe('visible');
    draw.setLayerState('plan', { visible: false });
    expect(couches.get(UNDERLAY_PLAN_LAYER_ID)?.layout.visibility).toBe('none');
  });

  it('une photo se pose depuis les quatre coins de sa PhotoSite (CAL53)', () => {
    const { draw, sources } = harnaisMapDraw();
    const r = draw.setFond(
      { kind: 'photo', photoSiteId: 918, opacite: 0.45 },
      { url: 'https://exemple/photo.jpg', calagePhoto: CALAGE_PHOTO },
    );
    expect(r.ok).toBe(true);
    expect(sources.get(UNDERLAY_PHOTO_LAYER_ID)).toEqual({
      type: 'image',
      url: 'https://exemple/photo.jpg',
      coordinates: [
        [-7.2, 33.2],
        [-7.1, 33.2],
        [-7.1, 33.1],
        [-7.2, 33.1],
      ],
    });
  });

  it('UN SEUL fond à la fois : poser une photo retire le plan précédent', () => {
    const { draw, sources, couches } = harnaisMapDraw();
    draw.setFond({ kind: 'plan', attachmentId: 1 }, { url: 'u', coinsPlan: COINS_PLAN });
    draw.setFond({ kind: 'photo', photoSiteId: 918 }, { url: 'p', calagePhoto: CALAGE_PHOTO });
    expect(sources.has(UNDERLAY_PLAN_LAYER_ID)).toBe(false);
    expect(couches.has(UNDERLAY_PLAN_LAYER_ID)).toBe(false);
    expect(couches.has(UNDERLAY_PHOTO_LAYER_ID)).toBe(true);
  });

  it('retirer le fond (`null`) ne laisse RIEN sur la carte ni dans le document', () => {
    const { draw, ctx, sources, couches } = harnaisMapDraw();
    draw.setFond({ kind: 'plan', attachmentId: 1 }, { url: 'u', coinsPlan: COINS_PLAN });
    expect(draw.setFond(null).ok).toBe(true);
    expect(sources.size).toBe(0);
    expect(couches.size).toBe(0);
    expect(draw.fond()).toBeNull();
    expect(underlayPourDocument(ctx)).toEqual({});
  });

  it('le fond posé VOYAGE par le document (contrat CALX86)', () => {
    const { draw, ctx } = harnaisMapDraw();
    draw.setFond({ kind: 'photo', photoSiteId: 918, opacite: 0.45 }, { url: 'p', calagePhoto: CALAGE_PHOTO });
    expect(underlayPourDocument(ctx)).toEqual({
      underlay: { kind: 'photo', photoSiteId: 918, opacite: 0.45 },
    });
  });
});

describe('CALX107 — un fond qu’on ne sait pas placer n’est JAMAIS peint au jugé', () => {
  it('un plan non calé : aucune couche, et le motif nomme la règle', () => {
    const { draw, sources, couches, setStatus } = harnaisMapDraw();
    const r = draw.setFond({ kind: 'plan', attachmentId: 1 }, { url: 'u' });
    expect(r.ok).toBe(false);
    expect(r.motif).toContain('distance réelle');
    expect(sources.size).toBe(0);
    expect(couches.size).toBe(0);
    expect(setStatus).toHaveBeenCalledWith(r.motif);
  });

  it('une photo non calée : aucune couche, et le motif le dit', () => {
    const { draw, couches, setStatus } = harnaisMapDraw();
    const r = draw.setFond({ kind: 'photo', photoSiteId: 918 }, { url: 'p', calagePhoto: null });
    expect(r.ok).toBe(false);
    expect(r.motif).toContain('quatre coins');
    expect(couches.size).toBe(0);
    expect(setStatus).toHaveBeenCalledWith(r.motif);
  });

  it('un fond hors contrat (photo + calage à deux points) est refusé avant tout dessin', () => {
    const { draw, ctx, couches } = harnaisMapDraw();
    const r = draw.setFond({ kind: 'photo', photoSiteId: 918, calage: EXEMPLE_PLAN.calage } as never, {
      url: 'p',
      calagePhoto: CALAGE_PHOTO,
    });
    expect(r.ok).toBe(false);
    expect(r.motif).toContain('quatre coins');
    expect(couches.size).toBe(0);
    expect(underlayPourDocument(ctx)).toEqual({}); // rien n'est entré dans le document
  });
});
