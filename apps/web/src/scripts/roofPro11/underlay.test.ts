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
import {
  caleDeuxPoints,
  calagePourDocument,
  capImageDeg,
  coinsDuPlanCale,
  deplacerCalage,
  MOTIF_PLAN_NON_CALE,
  pointImageSurCarte,
  tournerCalage,
  type CalageDeuxPoints,
} from './underlay';
import { createMapDraw, MAPLIBRE_LAYERS_PAR_CALQUE, ORDRE_RENDU_CALQUES, opacityPropFor } from './mapDraw';
import { distanceEntreM } from './snap';
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
  // `ensureTraceChips` (CALX89) s'ancre sur le parent du bouton « Terminer » : sans lui,
  // le constructeur ne crée AUCUN de ses contrôles (comportement voulu en mode capture).
  document.body.innerHTML = '<div id="rp9-barre"><button type="button" id="rp9-finish"></button></div>';
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

// ————————————————————————————————————————————————————————————————————————
// CALX108 — CALER LE FOND PAR DEUX POINTS ET UNE DISTANCE RÉELLE SAISIE
//
// Ce que ce bloc garde :
//  1. deux points distants de 100 px déclarés à 10 m ⇒ 0,1 m/px et rotation NULLE ;
//  2. distance non saisie ⇒ AUCUN calage écrit, et le motif est affiché ;
//  3. AUCUNE échelle n'est déduite du fichier — une unité/échelle/DPI que le fichier
//     prétendrait porter n'entre dans aucun calcul.
// ————————————————————————————————————————————————————————————————————————

/** Deux points de l'image alignés horizontalement, 100 px d'écart. */
const IMAGE_100PX: [[number, number], [number, number]] = [
  [120, 840],
  [220, 840],
];
/** Les deux ancres correspondantes sur la carte : plein EST (même latitude). */
const ANCRES_EST: [LngLat, LngLat] = [
  [-7.62, 33.58],
  [-7.6, 33.58],
];

describe('CALX108 — le facteur d’échelle vient de la distance SAISIE', () => {
  it('100 px déclarés à 10 m donnent 0,1 m/px et une rotation nulle', () => {
    const r = caleDeuxPoints(IMAGE_100PX, ANCRES_EST, 10, 'mesurée au télémètre');
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('calage attendu');
    expect(r.calibration.echelleMParPx).toBeCloseTo(0.1, 12);
    expect(r.calibration.rotationDeg).toBeCloseTo(0, 6);
    expect(r.calibration.distanceImagePx).toBeCloseTo(100, 12);
  });

  it('le facteur d’échelle ne dépend QUE des pixels et de la distance saisie — jamais de la carte', () => {
    // Deux ancres BEAUCOUP plus éloignées : l'échelle annoncée reste 0,1 m/px.
    const loin: [LngLat, LngLat] = [
      [-7.62, 33.58],
      [-7.4, 33.58],
    ];
    const proche = caleDeuxPoints(IMAGE_100PX, ANCRES_EST, 10, 's');
    const lointain = caleDeuxPoints(IMAGE_100PX, loin, 10, 's');
    if (!proche.ok || !lointain.ok) throw new Error('calages attendus');
    expect(lointain.calibration.echelleMParPx).toBe(proche.calibration.echelleMParPx);
    expect(lointain.calibration.echelleMParPx).toBeCloseTo(0.1, 12);
  });

  it('200 px déclarés à 10 m donnent 0,05 m/px : c’est la SAISIE qui commande', () => {
    const r = caleDeuxPoints(
      [
        [0, 0],
        [200, 0],
      ],
      ANCRES_EST,
      10,
      's',
    );
    if (!r.ok) throw new Error('calage attendu');
    expect(r.calibration.echelleMParPx).toBeCloseTo(0.05, 12);
  });

  it('un repère image tourné donne la rotation, jamais une échelle différente', () => {
    // Points image alignés VERTICALEMENT (y croît vers le bas = sud) ; ancres plein est.
    const r = caleDeuxPoints(
      [
        [0, 0],
        [0, 100],
      ],
      ANCRES_EST,
      10,
      's',
    );
    if (!r.ok) throw new Error('calage attendu');
    expect(r.calibration.echelleMParPx).toBeCloseTo(0.1, 12);
    // Image : cap 180° (sud). Carte : cap 90° (est). Rotation = 90 − 180 = −90 → 270°.
    expect(r.calibration.rotationDeg).toBeCloseTo(270, 4);
  });

  it('le repère image est le repère usuel : +x = est, +y = sud', () => {
    expect(capImageDeg(1, 0)).toBeCloseTo(90, 9); // vers la droite = est
    expect(capImageDeg(0, -1)).toBeCloseTo(0, 9); // vers le haut = nord
    expect(capImageDeg(0, 1)).toBeCloseTo(180, 9); // vers le bas = sud
    expect(capImageDeg(-1, 0)).toBeCloseTo(-90, 9); // vers la gauche = ouest
  });
});

describe('CALX108 — distance non saisie : AUCUN calage écrit, le motif est affiché', () => {
  it('sans distance, le refus nomme `distanceReelleM` et dit qu’aucune échelle n’est déduite', () => {
    for (const absente of [undefined, null, '', Number.NaN, 0, -3]) {
      const r = caleDeuxPoints(IMAGE_100PX, ANCRES_EST, absente, 's');
      expect(r.ok).toBe(false);
      if (r.ok) throw new Error('refus attendu');
      expect(r.champ).toBe('distanceReelleM');
      expect(r.motif).toContain('déduite du fichier');
      expect(r).not.toHaveProperty('calibration');
    }
  });

  it('`calagePourDocument` n’écrit RIEN quand la distance manque', () => {
    const r = calagePourDocument(IMAGE_100PX, ANCRES_EST, undefined, 'mesurée au télémètre');
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('distanceReelleM');
    expect(r).not.toHaveProperty('calage');
  });

  it('sans source, rien n’est écrit non plus : deux plans calés autrement ne se comparent pas', () => {
    const r = calagePourDocument(IMAGE_100PX, ANCRES_EST, 10, '   ');
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('source');
  });

  it('un seul point posé (ou deux points confondus) est refusé sur `pointsImage`', () => {
    expect(caleDeuxPoints([[0, 0]], ANCRES_EST, 10, 's').ok).toBe(false);
    const confondus = caleDeuxPoints(
      [
        [5, 5],
        [5, 5],
      ],
      ANCRES_EST,
      10,
      's',
    );
    expect(confondus.ok).toBe(false);
    if (confondus.ok) throw new Error('refus attendu');
    expect(confondus.champ).toBe('pointsImage');
    expect(confondus.motif).toContain('confondus');
  });

  it('sans ancres sur la carte, le refus nomme `ancre`', () => {
    const r = caleDeuxPoints(IMAGE_100PX, [[-7.62, 33.58]], 10, 's');
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('ancre');
  });
});

describe('CALX108 — AUCUNE échelle n’est déduite du fichier', () => {
  it('une unité/échelle/DPI portée par le fichier n’entre dans AUCUN calcul', () => {
    const nu = caleDeuxPoints(IMAGE_100PX, ANCRES_EST, 10, 's');
    // Les mêmes points, mais l'appelant prétend que le fichier porte une échelle.
    const bavard = caleDeuxPoints(
      Object.assign([...IMAGE_100PX], { unite: 'mm', echelle: 50, dpi: 300 }),
      Object.assign([...ANCRES_EST], { unite: 'm' }),
      10,
      's',
    );
    if (!nu.ok || !bavard.ok) throw new Error('calages attendus');
    expect(bavard.calibration).toEqual(nu.calibration);
  });

  it('un plan SANS calage n’est jamais placé, quoi qu’il prétende porter', () => {
    const fond = { kind: 'plan' as const, attachmentId: 3071 };
    const r = placementDuFond(fond, {
      url: 'https://exemple/plan.dxf',
      tailleImage: { largeur: 1200, hauteur: 900 },
    });
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('calage');
    expect(r.motif).toBe(MOTIF_PLAN_NON_CALE);
  });

  it('un plan calé mais dont les dimensions du fichier sont inconnues n’est pas placé non plus', () => {
    const fond = (lireUnderlay(EXEMPLE_PLAN) as { ok: true; fond: DocumentUnderlay }).fond;
    const r = placementDuFond(fond, { url: 'u' }); // ni coinsPlan, ni tailleImage
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('calage');
  });
});

describe('CALX108 — le fond se REPLACE une fois calé', () => {
  const calage: CalageDeuxPoints = {
    ancre: ANCRES_EST,
    pointsImage: IMAGE_100PX,
    distanceReelleM: 10,
    rotationDeg: 0,
    source: 'mesurée au télémètre',
  };

  it('le point image d’origine retombe EXACTEMENT sur son ancre', () => {
    const r = caleDeuxPoints(calage.pointsImage, calage.ancre, calage.distanceReelleM, calage.source);
    if (!r.ok) throw new Error('calage attendu');
    const p = pointImageSurCarte(r.calibration, calage.pointsImage[0]);
    expect(p[0]).toBeCloseTo(ANCRES_EST[0][0], 12);
    expect(p[1]).toBeCloseTo(ANCRES_EST[0][1], 12);
  });

  it('le SECOND point image retombe à la distance réelle SAISIE de l’ancre — 10 m, pas autre chose', () => {
    const r = caleDeuxPoints(calage.pointsImage, calage.ancre, 10, 's');
    if (!r.ok) throw new Error('calage attendu');
    const p = pointImageSurCarte(r.calibration, calage.pointsImage[1]);
    expect(distanceEntreM(ANCRES_EST[0], p)).toBeCloseTo(10, 3);
  });

  it('les quatre coins du plan se dérivent du calage et de la taille du fichier', () => {
    const r = coinsDuPlanCale(calage, { largeur: 1200, hauteur: 900 });
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('coins attendus');
    expect(r.coins).toHaveLength(4);
    // Rotation nulle : le coin haut-gauche est au NORD-OUEST du coin bas-droite.
    expect(r.coins[0][1]).toBeGreaterThan(r.coins[2][1]); // plus au nord
    expect(r.coins[0][0]).toBeLessThan(r.coins[2][0]); // plus à l'ouest
    // La largeur réelle du plan = 1200 px × 0,1 m/px = 120 m, à la précision du plan tangent.
    expect(distanceEntreM(r.coins[0], r.coins[1])).toBeCloseTo(120, 1);
    expect(distanceEntreM(r.coins[0], r.coins[3])).toBeCloseTo(90, 1);
  });

  it('sans dimensions de fichier, aucun coin n’est inventé', () => {
    for (const taille of [null, undefined, { largeur: 0, hauteur: 900 }, { largeur: 1200, hauteur: -1 }]) {
      const r = coinsDuPlanCale(calage, taille as never);
      expect(r.ok).toBe(false);
      if (r.ok) throw new Error('refus attendu');
      expect(r.motif).toContain('dimensions du fichier');
    }
  });

  it('`placementDuFond` dérive les coins tout seul dès que le plan est calé', () => {
    const fond: DocumentUnderlay = { kind: 'plan', attachmentId: 3071, calage };
    const r = placementDuFond(fond, { url: 'u', tailleImage: { largeur: 1200, hauteur: 900 } });
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('placement attendu');
    expect(distanceEntreM(r.coins[0], r.coins[1])).toBeCloseTo(120, 1);
  });
});

describe('CALX108 — glissé et molette ajustent translation et rotation, jamais la mesure', () => {
  const calage: CalageDeuxPoints = {
    ancre: ANCRES_EST,
    pointsImage: IMAGE_100PX,
    distanceReelleM: 10,
    rotationDeg: 0,
    source: 'mesurée au télémètre',
  };

  it('un glissé déplace les DEUX ancres du même vecteur — l’échelle est intacte', () => {
    const apres = deplacerCalage(calage, 25, -10);
    expect(apres.distanceReelleM).toBe(10);
    expect(apres.pointsImage).toEqual(calage.pointsImage);
    // Translation RIGIDE dans le plan tangent : l'écart entre les ancres est conservé au
    // centimètre près (le reste est la courbure — déplacer un plan vers le nord change
    // très légèrement ce qu'un degré de longitude y vaut en mètres).
    expect(distanceEntreM(apres.ancre[0], apres.ancre[1])).toBeCloseTo(
      distanceEntreM(calage.ancre[0], calage.ancre[1]),
      2,
    );
    expect(distanceEntreM(calage.ancre[0], apres.ancre[0])).toBeCloseTo(Math.hypot(25, 10), 2);
  });

  it('une rotation à la molette ne touche ni la distance saisie ni le facteur d’échelle', () => {
    const apres = tournerCalage(calage, 37);
    expect(apres.rotationDeg).toBeCloseTo(37, 9);
    expect(apres.distanceReelleM).toBe(10);
    expect(apres.ancre).toEqual(calage.ancre);
    expect(apres.pointsImage).toEqual(calage.pointsImage);
    const avant = coinsDuPlanCale(calage, { largeur: 1200, hauteur: 900 });
    const tourne = coinsDuPlanCale(apres, { largeur: 1200, hauteur: 900 });
    if (!avant.ok || !tourne.ok) throw new Error('coins attendus');
    // Le plan a tourné, mais il mesure toujours 120 m de large.
    expect(tourne.coins[0]).not.toEqual(avant.coins[0]);
    expect(distanceEntreM(tourne.coins[0], tourne.coins[1])).toBeCloseTo(120, 1);
  });

  it('la rotation reste bornée à [0, 360) comme le contrat l’exige', () => {
    expect(tournerCalage(calage, -30).rotationDeg).toBeCloseTo(330, 9);
    expect(tournerCalage({ ...calage, rotationDeg: 350 }, 20).rotationDeg).toBeCloseTo(10, 9);
  });

  it('un ajustement non fini ne change RIEN', () => {
    expect(deplacerCalage(calage, Number.NaN, 5)).toBe(calage);
    expect(tournerCalage(calage, Number.NaN)).toBe(calage);
  });
});

describe('CALX108 — le mode « caler le fond » dans l’atelier', () => {
  function atelierAvecPlan() {
    const h = harnaisMapDraw();
    h.draw.setFond({ kind: 'plan', attachmentId: 3071 }, { url: 'u', tailleImage: { largeur: 1200, hauteur: 900 } });
    return h;
  }

  it('le mode ne s’ouvre que sur un PLAN — une photo est déjà calée à quatre coins', () => {
    const h = harnaisMapDraw();
    expect(h.draw.demarrerCalageFond()).toBe(false); // aucun fond
    h.draw.setFond({ kind: 'photo', photoSiteId: 918 }, { url: 'p', calagePhoto: CALAGE_PHOTO });
    expect(h.draw.demarrerCalageFond()).toBe(false);
    expect(h.draw.modeCalageFond()).toBe(false);
  });

  it('deux points + une distance saisie écrivent `underlay.calage` et replacent le fond', () => {
    const { draw, ctx, sources } = atelierAvecPlan();
    expect(draw.demarrerCalageFond()).toBe(true);
    expect(draw.modeCalageFond()).toBe(true);
    expect(draw.pointCalageFond(IMAGE_100PX[0], ANCRES_EST[0])).toBe(1);
    expect(draw.pointCalageFond(IMAGE_100PX[1], ANCRES_EST[1])).toBe(2);
    const distance = document.getElementById('rp9-fond-distance') as HTMLInputElement;
    const source = document.getElementById('rp9-fond-source') as HTMLInputElement;
    distance.value = '10';
    source.value = 'mesurée au télémètre';
    expect(draw.validerCalageFond().ok).toBe(true);
    // Le calage voyage par le document, avec sa distance SAISIE et sa source.
    const doc = underlayPourDocument(ctx);
    expect(doc.underlay?.calage?.distanceReelleM).toBe(10);
    expect(doc.underlay?.calage?.source).toBe('mesurée au télémètre');
    expect(doc.underlay?.calage?.pointsImage).toEqual(IMAGE_100PX);
    // Et le fond est peint, à l'échelle saisie.
    const spec = sources.get(UNDERLAY_PLAN_LAYER_ID) as { coordinates: LngLat[] };
    expect(distanceEntreM(spec.coordinates[0], spec.coordinates[1])).toBeCloseTo(120, 1);
    expect(draw.modeCalageFond()).toBe(false); // le mode se referme
  });

  it('distance NON saisie : rien n’est écrit, le refus nomme le champ et l’affiche sous lui', () => {
    const { draw, ctx, sources } = atelierAvecPlan();
    draw.demarrerCalageFond();
    draw.pointCalageFond(IMAGE_100PX[0], ANCRES_EST[0]);
    draw.pointCalageFond(IMAGE_100PX[1], ANCRES_EST[1]);
    (document.getElementById('rp9-fond-source') as HTMLInputElement).value = 'mesurée au télémètre';
    const r = draw.validerCalageFond();
    expect(r.ok).toBe(false);
    expect(r.champ).toBe('distanceReelleM');
    expect(underlayPourDocument(ctx).underlay?.calage).toBeUndefined();
    expect(sources.has(UNDERLAY_PLAN_LAYER_ID)).toBe(false);
    const erreur = document.getElementById('rp9-fond-erreur') as HTMLElement;
    expect(erreur.hidden).toBe(false);
    expect(erreur.textContent).toContain('déduite du fichier');
    expect(document.getElementById('rp9-fond-distance')?.getAttribute('aria-invalid')).toBe('true');
    expect(draw.modeCalageFond()).toBe(true); // le mode RESTE ouvert : on peut corriger
  });

  it('un seul point posé est refusé en nommant `pointsImage`', () => {
    const { draw } = atelierAvecPlan();
    draw.demarrerCalageFond();
    draw.pointCalageFond(IMAGE_100PX[0], ANCRES_EST[0]);
    (document.getElementById('rp9-fond-distance') as HTMLInputElement).value = '10';
    const r = draw.validerCalageFond();
    expect(r.ok).toBe(false);
    expect(r.champ).toBe('pointsImage');
  });

  it('annuler le calage n’écrit RIEN', () => {
    const { draw, ctx } = atelierAvecPlan();
    draw.demarrerCalageFond();
    draw.pointCalageFond(IMAGE_100PX[0], ANCRES_EST[0]);
    draw.pointCalageFond(IMAGE_100PX[1], ANCRES_EST[1]);
    draw.annulerCalageFond();
    expect(draw.modeCalageFond()).toBe(false);
    expect(underlayPourDocument(ctx).underlay?.calage).toBeUndefined();
  });

  it('`ajusterFond` ne fait rien tant que le plan n’est pas calé', () => {
    const { draw } = atelierAvecPlan();
    expect(draw.ajusterFond({ estM: 5 })).toBe(false);
  });

  it('une fois calé, glissé et molette replacent le fond sans toucher la mesure', () => {
    const { draw, ctx } = atelierAvecPlan();
    draw.demarrerCalageFond();
    draw.pointCalageFond(IMAGE_100PX[0], ANCRES_EST[0]);
    draw.pointCalageFond(IMAGE_100PX[1], ANCRES_EST[1]);
    (document.getElementById('rp9-fond-distance') as HTMLInputElement).value = '10';
    (document.getElementById('rp9-fond-source') as HTMLInputElement).value = 'télémètre';
    draw.validerCalageFond();
    const avant = underlayPourDocument(ctx).underlay?.calage as CalageDeuxPoints;
    expect(draw.ajusterFond({ estM: 12, nordM: -4, rotationDeg: 15 })).toBe(true);
    const apres = underlayPourDocument(ctx).underlay?.calage as CalageDeuxPoints;
    expect(apres.distanceReelleM).toBe(10);
    expect(apres.source).toBe('télémètre');
    expect(apres.pointsImage).toEqual(avant.pointsImage);
    expect(apres.rotationDeg).toBeCloseTo(15, 6);
    expect(apres.ancre[0]).not.toEqual(avant.ancre[0]);
  });
});
