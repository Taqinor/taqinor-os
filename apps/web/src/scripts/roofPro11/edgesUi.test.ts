// @vitest-environment jsdom
// CALX94 — correction MANUELLE du type d'une arête depuis l'atelier : choix du segment au
// clic, sélecteur créé par le module, écriture dans `ctx.areas[].edges`, survie de la
// correction à la sérialisation, et couleur 3D qui suit le type RETENU.
import { beforeEach, describe, expect, it } from 'vitest';
import { areteAuPoint, createEdgesUi, EDGE_PICK_TOL_M, type EdgeMapLike } from './edgesUi';
import { EDGE_COLOR_BY_TYPE, EDGE_TYPE_LABELS, fusionnerAretesSaisies, type SerializedEdge } from './edges';
import { serializeLayout } from './prefill';
import { type Ctx } from './context';
import { type AreaRecord } from './types';
import { type LngLat } from '../../lib/roof';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LAT0 = 33.59;
const LNG0 = -7.6;

/** Point donné en MÈTRES autour de (LNG0, LAT0) — x vers l'est, y vers le nord. */
function ptM(x: number, y: number): LngLat {
  const cosLat = Math.cos(LAT0 * DEG2RAD);
  return [LNG0 + x / (DEG2M * cosLat), LAT0 + y / DEG2M];
}

/** Contour en mètres. */
function polyM(pts: [number, number][]): LngLat[] {
  return pts.map(([x, y]) => ptM(x, y));
}

/** Carré 10×10 centré sur l'origine, sommets dans l'ordre SO → SE → NE → NO :
 *  segment 0 = côté SUD, 1 = EST, 2 = NORD, 3 = OUEST. */
const CARRE: [number, number][] = [
  [-5, -5],
  [5, -5],
  [5, 5],
  [-5, 5],
];

/** Demi-croupe SUD / demi-croupe EST d'un même carré (arête partagée = la diagonale). */
const TRIANGLE_SUD: [number, number][] = [
  [0, 0],
  [-5, -5],
  [5, -5],
];
const TRIANGLE_EST: [number, number][] = [
  [0, 0],
  [5, -5],
  [5, 5],
];
const DIAGONALE_SUD = 2;

function zone(id: string, vertices: LngLat[], opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices,
    obstacles: [],
    roofType: 'pitched',
    pitchDeg: 30,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 10,
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
    activeArea: () => areas.find((a) => a.id === activeId),
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
    dom: {},
  } as unknown as Ctx;
}

function hote(): HTMLElement {
  const el = document.createElement('div');
  el.id = 'hote-test';
  document.body.appendChild(el);
  return el;
}

beforeEach(() => {
  document.body.innerHTML = '';
});

describe('CALX94 — choix du segment cliqué (géométrie pure)', () => {
  it('retient le segment le plus proche du clic', () => {
    const ring = polyM(CARRE);
    expect(areteAuPoint(ring, ptM(0, -5.2))).toBe(0); // côté sud
    expect(areteAuPoint(ring, ptM(5.1, 0))).toBe(1); // côté est
    expect(areteAuPoint(ring, ptM(0, 4.9))).toBe(2); // côté nord
    expect(areteAuPoint(ring, ptM(-4.8, 0))).toBe(3); // côté ouest
  });

  it('au-delà de la tolérance de pointage, AUCUNE arête n’est choisie', () => {
    const ring = polyM(CARRE);
    expect(areteAuPoint(ring, ptM(0, 0))).toBeNull(); // centre : 5 m de tout segment
    expect(areteAuPoint(ring, ptM(0, -5 - EDGE_PICK_TOL_M - 0.5))).toBeNull();
  });

  it('contour de moins de 3 sommets : rien à corriger', () => {
    expect(areteAuPoint([ptM(0, 0), ptM(1, 0)], ptM(0.5, 0))).toBeNull();
  });
});

describe('CALX94 — sélecteur de type créé par le module', () => {
  it('crée bouton + sélecteur des SIX types, libellés en français', () => {
    const areas = [zone('z1', polyM(CARRE))];
    createEdgesUi(makeCtx(areas), { anchor: hote() });
    const select = document.getElementById('rp9-edge-type') as HTMLSelectElement;
    expect(document.getElementById('rp9-edge-mode')).toBeTruthy();
    expect(select).toBeTruthy();
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      'faitage',
      'noue',
      'arretier',
      'egout',
      'rive',
      'inconnue',
    ]);
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual([
      EDGE_TYPE_LABELS.faitage,
      EDGE_TYPE_LABELS.noue,
      EDGE_TYPE_LABELS.arretier,
      EDGE_TYPE_LABELS.egout,
      EDGE_TYPE_LABELS.rive,
      EDGE_TYPE_LABELS.inconnue,
    ]);
    // Rien n'est sélectionné au départ : le sélecteur reste inactif.
    expect(select.disabled).toBe(true);
  });

  it('une page qui fournit déjà le panneau garde SON markup', () => {
    const h = hote();
    h.innerHTML = '<div id="rp9-edge-panel"><select id="rp9-edge-type"><option value="rive">R</option></select></div>';
    createEdgesUi(makeCtx([zone('z1', polyM(CARRE))]), { anchor: h });
    expect(document.querySelectorAll('#rp9-edge-panel')).toHaveLength(1);
    expect((document.getElementById('rp9-edge-type') as HTMLSelectElement).options).toHaveLength(1);
  });

  it('clic carte en mode correction → segment sélectionné, puis le choix du sélecteur écrit la correction', () => {
    const areas = [zone('z1', polyM(CARRE))];
    const ctx = makeCtx(areas);
    const ui = createEdgesUi(ctx, { anchor: hote() });
    ui.setEdgeMode(true);
    expect(ui.handleMapClick(ptM(5.1, 0))).toBe(true);
    expect(ui.selectedEdge()).toBe(1);
    const select = document.getElementById('rp9-edge-type') as HTMLSelectElement;
    expect(select.disabled).toBe(false);
    select.value = 'faitage';
    select.dispatchEvent(new Event('change'));
    expect(areas[0].edges).toEqual([{ index: 1, type: 'faitage', manuel: true }]);
  });

  it('hors mode correction, le clic carte n’est pas capté (le tracé garde son comportement)', () => {
    const ctx = makeCtx([zone('z1', polyM(CARRE))]);
    const ui = createEdgesUi(ctx, { anchor: hote() });
    expect(ui.isEdgeMode()).toBe(false);
    expect(ui.handleMapClick(ptM(5.1, 0))).toBe(false);
    expect(ui.selectedEdge()).toBeNull();
  });

  it('le clic carte n’est abonné à la carte QUE pendant le mode', () => {
    const abonnes: string[] = [];
    const map: EdgeMapLike = {
      on: () => abonnes.push('on'),
      off: () => abonnes.push('off'),
    };
    const ui = createEdgesUi(makeCtx([zone('z1', polyM(CARRE))]), { anchor: hote(), map });
    expect(abonnes).toEqual([]);
    ui.setEdgeMode(true);
    expect(abonnes).toEqual(['on']);
    ui.setEdgeMode(false);
    expect(abonnes).toEqual(['on', 'off']);
  });

  it('un clic loin de tout segment ne corrige rien et le dit', () => {
    const messages: string[] = [];
    const ctx = makeCtx([zone('z1', polyM(CARRE))]);
    const ui = createEdgesUi(ctx, { anchor: hote(), setStatus: (m) => messages.push(m) });
    ui.setEdgeMode(true);
    expect(ui.handleMapClick(ptM(0, 0))).toBe(false);
    expect(ui.selectedEdge()).toBeNull();
    expect(messages.join(' ')).toContain('Aucune arête');
  });
});

describe('CALX94 — la correction voyage par le document', () => {
  /** Carré en pente plein sud, isolé : segment 0 (côté sud) = égout, le reste inconnu. */
  function ctxCarrePentu() {
    const areas = [zone('z1', polyM(CARRE), { facingAzimuthDeg: 180 })];
    return { areas, ctx: makeCtx(areas) };
  }

  it('une arête corrigée survit à DEUX serializeLayout consécutifs', () => {
    const { areas, ctx } = ctxCarrePentu();
    const ui = createEdgesUi(ctx, { anchor: hote() });
    const avant = serializeLayout(ctx).zones[0].edges!;
    expect(avant[0]).toEqual({ index: 0, type: 'egout' });

    ui.setEdgeType(0, 'faitage');
    const un = serializeLayout(ctx).zones[0].edges!;
    expect(un[0]).toEqual({ index: 0, type: 'faitage', manuel: true });
    const deux = serializeLayout(ctx).zones[0].edges!;
    expect(deux[0]).toEqual({ index: 0, type: 'faitage', manuel: true });
    // La saisie est bien sur l'enregistrement de zone, pas seulement dans le JSON.
    expect(areas[0].edges?.find((e) => e.index === 0)?.manuel).toBe(true);
  });

  it('une arête NON corrigée reste re-déduite quand le toit change', () => {
    const { areas, ctx } = ctxCarrePentu();
    const ui = createEdgesUi(ctx, { anchor: hote() });
    ui.setEdgeType(0, 'faitage');
    // Le pan devient PLAT : la déduction repasse tous les segments en « rive »…
    areas[0].roofType = 'flat';
    (ctx as unknown as { roofType: string }).roofType = 'flat';
    const edges = serializeLayout(ctx).zones[0].edges!;
    expect(edges.filter((e) => e.type === 'rive').map((e) => e.index)).toEqual([1, 2, 3]);
    // … sauf celui que l'utilisateur a corrigé.
    expect(edges[0]).toEqual({ index: 0, type: 'faitage', manuel: true });
  });

  it('la couleur 3D du segment suit le type RETENU (corrigé compris)', () => {
    const { ctx } = ctxCarrePentu();
    const ui = createEdgesUi(ctx, { anchor: hote() });
    expect(ui.typeArete(0)).toBe('egout');
    expect(ui.couleurArete(0)).toBe(EDGE_COLOR_BY_TYPE.egout);
    ui.setEdgeType(0, 'noue');
    expect(ui.typeArete(0)).toBe('noue');
    expect(ui.couleurArete(0)).toBe(EDGE_COLOR_BY_TYPE.noue);
  });

  it('crochet CALX93 : la pente SAISIE du pan voyage jusqu’à la déduction (arêtier réel)', () => {
    const sud = zone('sud', polyM(TRIANGLE_SUD), { facingAzimuthDeg: 180, pitchDeg: 30 });
    const est = zone('est', polyM(TRIANGLE_EST), { facingAzimuthDeg: 90, pitchDeg: 30 });
    const ctx = makeCtx([sud, est]);
    const edges = serializeLayout(ctx).zones[0].edges!;
    expect(edges[DIAGONALE_SUD].type).toBe('arretier');
  });

  it('sans pente saisie, la même diagonale reste « inconnue » (jamais supposée)', () => {
    const sud = zone('sud', polyM(TRIANGLE_SUD), { facingAzimuthDeg: 180, pitchDeg: Number.NaN });
    const est = zone('est', polyM(TRIANGLE_EST), { facingAzimuthDeg: 90, pitchDeg: Number.NaN });
    const ctx = makeCtx([sud, est]);
    const edges = serializeLayout(ctx).zones[0].edges!;
    expect(edges[DIAGONALE_SUD].type).toBe('inconnue');
  });
});

describe('CALX94 — fusionnerAretesSaisies (fonction pure)', () => {
  const deduites: SerializedEdge[] = [
    { index: 0, type: 'egout' },
    { index: 1, type: 'inconnue' },
  ];

  it('sans aucune saisie, la déduction passe telle quelle', () => {
    expect(fusionnerAretesSaisies(undefined, deduites)).toEqual(deduites);
    expect(fusionnerAretesSaisies([], deduites)).toEqual(deduites);
  });

  it('un type déduit puis re-déduit n’est jamais marqué « manuel »', () => {
    const existantes: SerializedEdge[] = [{ index: 0, type: 'rive' }];
    expect(fusionnerAretesSaisies(existantes, deduites)![0]).toEqual({ index: 0, type: 'egout' });
  });

  it('le retrait SAISI par arête est reporté, même sans correction de type', () => {
    const existantes: SerializedEdge[] = [{ index: 1, type: 'inconnue', retraitM: 1.2 }];
    expect(fusionnerAretesSaisies(existantes, deduites)![1]).toEqual({ index: 1, type: 'inconnue', retraitM: 1.2 });
  });

  it('un retrait illisible ou négatif n’est pas reporté (jamais un nombre inventé)', () => {
    const existantes = [
      { index: 0, type: 'rive', retraitM: -1 },
      { index: 1, type: 'rive', retraitM: Number.NaN },
    ] as unknown as SerializedEdge[];
    const out = fusionnerAretesSaisies(existantes, deduites)!;
    expect(out.every((e) => !('retraitM' in e))).toBe(true);
  });

  it('une saisie dont le segment n’existe plus est abandonnée, jamais rattachée ailleurs', () => {
    const existantes: SerializedEdge[] = [{ index: 7, type: 'faitage', manuel: true }];
    const out = fusionnerAretesSaisies(existantes, deduites)!;
    expect(out).toEqual(deduites);
  });

  it('aucune arête déduite ⇒ rien à écrire (la clé n’est pas émise)', () => {
    expect(fusionnerAretesSaisies([{ index: 0, type: 'rive', manuel: true }], [])).toBeUndefined();
  });
});

describe('CALX99 — prendre l’azimut d’un pan depuis une arête cliquée', () => {
  it('crée le bouton « Prendre l’azimut… » à côté du bouton de correction de type', () => {
    const areas = [zone('z1', polyM(CARRE))];
    createEdgesUi(makeCtx(areas), { anchor: hote() });
    expect(document.getElementById('rp9-edge-mode')).toBeTruthy();
    expect(document.getElementById('rp9-edge-azimuth-mode')).toBeTruthy();
  });

  it('une page qui fournit déjà le panneau garde SON markup (pas de bouton azimut ajouté)', () => {
    const h = hote();
    h.innerHTML = '<div id="rp9-edge-panel"><select id="rp9-edge-type"><option value="rive">R</option></select></div>';
    createEdgesUi(makeCtx([zone('z1', polyM(CARRE))]), { anchor: h });
    expect(document.getElementById('rp9-edge-azimuth-mode')).toBeNull();
  });

  it('clic sur le côté EST en mode azimut écrit ctx.facingAzimuthDeg (90°, cap+90) et facingManual, sans sélection persistée', () => {
    const areas = [zone('z1', polyM(CARRE), { facingAzimuthDeg: 180, facingManual: false })];
    const ctx = makeCtx(areas);
    const ui = createEdgesUi(ctx, { anchor: hote() });
    ui.setAzimuthMode(true);
    expect(ui.handleMapClick(ptM(5.1, 0))).toBe(true); // côté EST (segment 1 : SE→NE, cap 0 → normale 90°)
    expect(ctx.facingAzimuthDeg).toBeCloseTo(90, 3);
    expect(ctx.facingManual).toBe(true);
    expect(areas[0].facingManual).toBe(true); // même geste que les boutons cardinaux
    expect(ui.selectedEdge()).toBeNull(); // le mode azimut ne persiste aucune sélection de type
  });

  it('sur le côté SUD (arête est-ouest), la normale rend 180° — l’exemple du Done', () => {
    const areas = [zone('z1', polyM(CARRE), { facingAzimuthDeg: 0 })];
    const ctx = makeCtx(areas);
    const ui = createEdgesUi(ctx, { anchor: hote() });
    ui.setAzimuthMode(true);
    expect(ui.handleMapClick(ptM(0, -5.2))).toBe(true); // côté SUD (segment 0)
    expect(ctx.facingAzimuthDeg).toBeCloseTo(180, 3);
  });

  it('un clic loin de tout segment ne pose aucun azimut et le dit', () => {
    const messages: string[] = [];
    const areas = [zone('z1', polyM(CARRE), { facingAzimuthDeg: 33 })];
    const ctx = makeCtx(areas);
    const ui = createEdgesUi(ctx, { anchor: hote(), setStatus: (m) => messages.push(m) });
    ui.setAzimuthMode(true);
    expect(ui.handleMapClick(ptM(0, 0))).toBe(false); // centre : hors tolérance de tout côté
    expect(ctx.facingAzimuthDeg).toBe(33); // rien n’a bougé
    expect(ctx.facingManual).toBe(false);
    expect(messages.join(' ')).toContain('Aucune arête');
  });

  it('hors mode azimut, le clic carte n’écrit aucun azimut', () => {
    const areas = [zone('z1', polyM(CARRE), { facingAzimuthDeg: 33 })];
    const ctx = makeCtx(areas);
    const ui = createEdgesUi(ctx, { anchor: hote() });
    expect(ui.isAzimuthMode()).toBe(false);
    expect(ui.handleMapClick(ptM(5.1, 0))).toBe(false); // mode « type » : aucune arête sous tolérance sélectionnée non plus, mais surtout aucun azimut écrit
    expect(ctx.facingAzimuthDeg).toBe(33);
  });

  it('les deux modes « clic sur arête » sont mutuellement exclusifs', () => {
    const ctx = makeCtx([zone('z1', polyM(CARRE))]);
    const ui = createEdgesUi(ctx, { anchor: hote() });
    ui.setEdgeMode(true);
    expect(ui.isEdgeMode()).toBe(true);
    ui.setAzimuthMode(true);
    expect(ui.isAzimuthMode()).toBe(true);
    expect(ui.isEdgeMode()).toBe(false); // armer l'azimut désarme la correction de type

    ui.setEdgeMode(true);
    expect(ui.isEdgeMode()).toBe(true);
    expect(ui.isAzimuthMode()).toBe(false); // et réciproquement
  });

  it('l’abonnement carte est UN SEUL abonnement, partagé par les deux modes', () => {
    const abonnes: string[] = [];
    const map: EdgeMapLike = {
      on: () => abonnes.push('on'),
      off: () => abonnes.push('off'),
    };
    const ui = createEdgesUi(makeCtx([zone('z1', polyM(CARRE))]), { anchor: hote(), map });
    expect(abonnes).toEqual([]);
    ui.setAzimuthMode(true);
    expect(abonnes).toEqual(['on']);
    // Basculer vers l'autre mode ne désabonne/réabonne pas (toujours au moins un mode armé).
    ui.setEdgeMode(true);
    expect(abonnes).toEqual(['on']);
    ui.setEdgeMode(false);
    expect(abonnes).toEqual(['on', 'off']);
  });
});
