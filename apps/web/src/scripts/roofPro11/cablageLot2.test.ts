// @vitest-environment jsdom
// CÂBLAGES du lot 2 (Groupe CALX) — chaque crochet laissé par une lane de phase A/B est
// ici EXERCÉ : la fonction existait et était testée, il manquait la ligne qui l'appelle.
// Ce fichier ne prouve que ces lignes-là (aucune fonctionnalité neuve).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createZones } from './zones';
import { couleursAretes, EDGE_COLOR_BY_TYPE, type EdgeDeductionZone } from './edges';
import { deserializeLayout, geometrieZoneActive, selectionSansChangement, serializeLayout } from './prefill'; // ACAL1916
import { etiquette, registreAtelier, reinitialiserNumerotation } from './numerotation';
import { createLayoutEditor } from './layoutEditor';
import { createWorkshopHistory, photoAtelierDepuisCtx, restaurerEnvZonesMesures } from './layoutHistory'; // ACAL515
import { type Ctx } from './context';
import { panDeTest, ctxDeBase, ptM, LNG0, LAT0, carteEditeurFactice, depsEditeur } from './harnaisAtelier';
import { type AreaRecord, type LayoutPlan } from './types';
import { type LngLat } from '../../lib/roof';
import { createLayoutState } from '../../lib/layoutVariability'; // ACAL1916

const CARRE: LngLat[] = [ptM(-5, -5), ptM(5, -5), ptM(5, 5), ptM(-5, 5)];

function zone(id: string, vertices: LngLat[]): AreaRecord {
  return panDeTest(id, { vertices, roofType: 'flat', neededPanels: 10 });
}

function makeCtx(areas: AreaRecord[], activeId = areas[0].id): Ctx {
  return {
    ...ctxDeBase(areas, activeId),
    activeArea: () => areas.find((a) => a.id === activeId),
    closed: true,
    dom: {},
  } as unknown as Ctx;
}

/** Le SOURCE de l'entrée du constructeur — seul endroit où vivent les lignes d'appel
 *  câblées ici (une page à effets de bord, non importable en test). Le chemin part du
 *  dossier de travail (`apps/web`, celui d'où vitest est lancé ici comme en CI) :
 *  `import.meta.url` n'est pas une URL de fichier sous jsdom. Les assertions ne portent
 *  JAMAIS sur plusieurs lignes à la fois (CRLF local). */
const SOURCE_ENTREE = readFileSync(
  resolve(process.cwd(), 'src/scripts/roof-tool-pro11.ts'),
  'utf8',
);

describe('CALX97/98 câblage — la carte se redessine après une transformation de pan', () => {
  it('les quatre crochets de `createZones` sont appelés par une rotation de pan', () => {
    const areas = [zone('area-1', [...CARRE])];
    const ctx = makeCtx(areas);
    const redrawTrace = vi.fn();
    const redrawObstacles = vi.fn();
    const recalc = vi.fn();
    const setStatus = vi.fn();
    const zones = createZones(ctx, { redrawTrace, redrawObstacles, recalc, setStatus });

    expect(zones.pivoterPanActif(90)).toBe(true);

    expect(redrawTrace).toHaveBeenCalledTimes(1);
    expect(redrawObstacles).toHaveBeenCalledTimes(1);
    expect(recalc).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalled();
  });

  it('un refus NOMMÉ passe par le bandeau de statut et ne redessine rien', () => {
    const areas = [zone('area-1', [...CARRE])];
    const ctx = makeCtx(areas);
    const redrawTrace = vi.fn();
    const recalc = vi.fn();
    const setStatus = vi.fn();
    const zones = createZones(ctx, { redrawTrace, recalc, setStatus });

    expect(zones.pivoterPanActif(Number.NaN)).toBe(false);

    expect(redrawTrace).not.toHaveBeenCalled();
    expect(recalc).not.toHaveBeenCalled();
    expect(setStatus).toHaveBeenCalledWith(expect.stringContaining('Zone 1')); // ACAL1430 — le nom de la liste (rang), jamais le label stocké
  });

  it('l’entrée du constructeur passe bien les quatre crochets à `createZones`', () => {
    expect(SOURCE_ENTREE).toContain('const zones = createZones(ctx, {');
    for (const crochet of [
      'redrawTrace: () => redrawTrace(), // CALX97 câblage',
      'redrawObstacles: () => redrawObstacles(), // CALX97 câblage',
      'recalc: () => recalc(), // CALX97 câblage',
      'setStatus: (msg: string) => setStatus(msg), // CALX97 câblage',
    ]) {
      expect(SOURCE_ENTREE).toContain(crochet);
    }
  });
});

describe('CALX94 câblage — le type d’arête corrigé se voit en 3D et le clic lui est routé', () => {
  const carre = (): EdgeDeductionZone => ({
    vertices: [...CARRE],
    roofType: 'flat',
    facingAzimuthDeg: 180,
  });

  it('une arête corrigée à la main prend SA couleur, les autres celle du type déduit', () => {
    const sans = couleursAretes(carre(), [], undefined);
    expect(sans).toHaveLength(4);

    const avec = couleursAretes(carre(), [], [{ index: 1, type: 'faitage', manuel: true }]);
    expect(avec[1]).toBe(EDGE_COLOR_BY_TYPE.faitage);
    // Les trois autres segments n'ont pas bougé : la correction n'en déborde pas.
    expect([avec[0], avec[2], avec[3]]).toEqual([sans[0], sans[2], sans[3]]);
  });

  it('une saisie NON marquée `manuel` ne repeint rien (elle n’a pas été corrigée)', () => {
    const sans = couleursAretes(carre(), [], undefined);
    const avec = couleursAretes(carre(), [], [{ index: 1, type: 'faitage' }]);
    expect(avec).toEqual(sans);
  });

  it('un contour de moins de trois sommets ne produit AUCUNE couleur', () => {
    expect(couleursAretes({ ...carre(), vertices: CARRE.slice(0, 2) }, [], undefined)).toEqual([]);
  });

  it('l’entrée route le clic carte vers `edgesUi` quand le mode arêtes est armé', () => {
    expect(SOURCE_ENTREE).toContain('if (edgesUi.isEdgeMode()) {');
    expect(SOURCE_ENTREE).toContain('edgesUi.handleMapClick(lngLat); // CALX94 câblage');
    // Le module ne reçoit PAS la carte : sans cela il s'abonnerait aussi et le clic serait
    // traité deux fois.
    expect(SOURCE_ENTREE).toContain('const edgesUi = createEdgesUi(ctx, {');
    expect(SOURCE_ENTREE).not.toContain('createEdgesUi(ctx, { map');
  });

  it('la scène colore chaque segment du contour via `couleursAretes`', () => {
    const scene = readFileSync(resolve(process.cwd(), 'src/scripts/roofPro11/scene3d.ts'), 'utf8');
    expect(scene).toContain('if (!isOtherZone) { // CALX94 câblage');
    expect(scene).toContain('const couleurs = couleursAretes(');
    expect(scene).toContain('new THREE.LineBasicMaterial({ color: couleur, transparent: true, opacity: 0.95 }),');
  });
});

describe('CALX111 câblage — les numéros du document survivent à une réouverture', () => {
  beforeEach(() => reinitialiserNumerotation());

  it('`deserializeLayout` sème la mémoire de l’atelier depuis le document rouvert', () => {
    const document = {
      zones: [
        {
          id: 'area-1',
          label: 'Zone 1',
          vertices: CARRE.map(([lng, lat]) => [lng, lat]),
          obstacles: [],
          geometry: {
            azimuthDeg: 180,
            numerotation: { depart: 1, sens: 'ligne' as const },
            panels: [
              { cx: 0, cy: 0, n: 7 },
              { cx: 2.4, cy: 0, n: 8 },
            ],
          },
        },
      ],
    };
    // Avant lecture : l'atelier ne sait rien de ce pan.
    expect(registreAtelier.historique('area-1').plafond).toBe(0);

    deserializeLayout(document as unknown as Parameters<typeof deserializeLayout>[0]);

    // Après lecture : les numéros DU DOCUMENT sont la mémoire — le prochain module posé
    // prendra le 9, et non le 1 (sinon rouvrir un dossier renumérotait tout le pan).
    expect(registreAtelier.historique('area-1').plafond).toBe(8);
    expect(registreAtelier.convention('area-1')).toEqual({ depart: 1, sens: 'ligne' });
    expect(registreAtelier.modules('area-1').map((m) => m.n)).toEqual([7, 8]);
  });

  it('la désignation d’un module visé suit `n`, et retombe sur le rang sans numérotation', () => {
    // L'expression exacte que `shadingUi.etiquetteModule` évalue.
    const designer = (i: number) =>
      etiquette(registreAtelier.modules('area-1')[i], registreAtelier.convention('area-1')) ||
      `nº${i + 1}`;

    // Aucun document absorbé : le libellé d'aujourd'hui, inchangé.
    expect(designer(0)).toBe('nº1');

    registreAtelier.absorberDocument({
      zones: [
        {
          id: 'area-1',
          geometry: {
            azimuthDeg: 180,
            numerotation: { prefixe: 'PV', depart: 1, sens: 'ligne' as const },
            panels: [
              { cx: 0, cy: 0, n: 7 },
              { cx: 2.4, cy: 0, n: 8 },
            ],
          },
        },
      ],
    });
    expect(designer(0)).toBe('PV nº7');
    expect(designer(1)).toBe('PV nº8');
    // Hors plan : jamais un numéro inventé, on retombe sur le rang.
    expect(designer(5)).toBe('nº6');
  });

  it('les deux points d’appel portent la ligne câblée', () => {
    const shading = readFileSync(resolve(process.cwd(), 'src/scripts/roofPro11/shadingUi.ts'), 'utf8');
    expect(shading).toContain('proposal.indices.map(etiquetteModule)');
    expect(shading).not.toContain('proposal.indices.map((i) => `nº${i + 1}`)');
    const prefillSrc = readFileSync(resolve(process.cwd(), 'src/scripts/roofPro11/prefill.ts'), 'utf8');
    expect(prefillSrc).toContain('registreAtelier.absorberDocument(json); // CALX111 câblage');
  });
});

describe('CALX113 câblage — une symétrie survit au rechargement (l’orientation voyage)', () => {
  /** Plan de pavage minimal, azimut 0, un contour carré généreux. */
  function plan(): LayoutPlan {
    const c = 40;
    return {
      pack: {
        origin: [LNG0, LAT0],
        ringENU: [
          [-c, -c],
          [c, -c],
          [c, c],
          [-c, c],
        ],
        azimuthDeg: 0,
      },
      grid: { rowWidthM: 2, footprintPerPanelM2: 2, slopeLenM: 1, kwc: 1.44, panels: [{ cx: 0, cy: 0 }] },
      count: 2,
      tiltDeg: 0,
      family: 'south',
      flush: false,
    } as unknown as LayoutPlan;
  }

  /** ctx en PLACEMENT LIBRE : un panneau tourné (symétrie appliquée), un autre non. */
  function ctxLibre(): Ctx {
    const areas = [zone('area-1', [...CARRE])];
    return {
      ...(makeCtx(areas) as unknown as Record<string, unknown>),
      layoutPlan: plan(),
      layoutState: null,
      freeMode: true,
      freeState: { panels: [{ cx: 1, cy: 2, angleDeg: 37 }, { cx: 4, cy: 2 }] },
    } as unknown as Ctx;
  }

  it('`serializeLayout` écrit `angleDeg` — et seulement là où il existe', () => {
    const doc = serializeLayout(ctxLibre());
    const panneaux = doc.zones[0].geometry!.panels;
    expect(doc.zones[0].geometry!.mode).toBe('free');
    expect(panneaux[0].angleDeg).toBe(37);
    // Panneau jamais tourné : la clé reste ABSENTE (document d'hier, octet pour octet).
    expect('angleDeg' in panneaux[1]).toBe(false);
  });

  it('la relecture repose l’orientation enregistrée sur le panneau libre', () => {
    const doc = serializeLayout(ctxLibre());
    const geo = doc.zones[0].geometry!;

    const conteneur = document.createElement('div');
    document.body.appendChild(conteneur);
    const map = carteEditeurFactice(conteneur);
    const ctxNeuf = {
      ...(makeCtx([zone('area-1', [...CARRE])]) as unknown as Record<string, unknown>),
      layoutMode: true,
      layoutPlan: plan(),
      layoutState: null,
      layoutSel: null,
      freeMode: false,
      freeState: null,
    } as unknown as Ctx;
    const editor = createLayoutEditor(ctxNeuf, depsEditeur(map));

    expect(editor.hydrateLayout(geo.panels, geo.origin, 'free')).toBe(true);
    const reposes = editor.freePanels();
    expect(reposes[0].angleDeg).toBe(37);
    expect(reposes[1].angleDeg).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL515 — « Pivoter le site » : un geste, un Annuler.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL515 — pivoterSiteActif', () => {
  const montage = (opts: { panneaux?: boolean } = {}) => {
    const decale = (d: number) => CARRE.map(([x, y]) => [x + d, y] as LngLat);
    const areas = [
      { ...zone('area-1', [...CARRE]), obstacles: [{ id: 'o1', centerLng: LNG0, centerLat: LAT0 }] as never },
      { ...zone('area-2', decale(0.0004)), facingAzimuthDeg: 90 },
    ];
    if (opts.panneaux) areas[1].result = { panels: 6, kwc: 3, annualKwh: 4000, savingsLow: 0, savingsHigh: 0 };
    const ctx = {
      ...ctxDeBase(areas), activeArea: () => areas[0], closed: true, dom: {},
      environment: [{ id: 'e1', kind: 'tree', centerLng: LNG0 + 0.0002, centerLat: LAT0 + 0.0001 }],
      exclusionZones: [{ id: 'x1', nature: 'interdite', vertices: [[LNG0, LAT0], [LNG0 + 0.0001, LAT0], [LNG0, LAT0 + 0.0001]], setbackM: 0 }],
      measurements: [{ id: 'm1', kind: 'distance', points: [[LNG0, LAT0], [LNG0 + 0.0003, LAT0]] }],
    } as unknown as Ctx;
    const historique = createWorkshopHistory();
    const pousser = vi.fn(() => historique.push(photoAtelierDepuisCtx(ctx)));
    ctx.pushWorkshopHistory = pousser;
    const setStatus = vi.fn();
    const zones = createZones(ctx, { redrawTrace: vi.fn(), redrawObstacles: vi.fn(), recalc: vi.fn(), setStatus });
    return { ctx, areas, zones, historique, pousser, setStatus };
  };

  it('pivote tous les pans d’un geste : UNE photo d’historique, faces +90, statut nommé', () => {
    const { ctx, areas, zones, pousser, setStatus } = montage();
    const avant = JSON.stringify(areas.map((a) => a.vertices));
    expect(zones.pivoterSiteActif(90)).toBe(true);
    expect(pousser).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(areas.map((a) => a.vertices))).not.toBe(avant);
    expect(areas.map((a) => a.facingAzimuthDeg)).toEqual([270, 180]);
    expect(ctx.facingAzimuthDeg).toBe(270); // le pan vivant tourne aussi
    expect(ctx.vertices).toEqual(areas[0].vertices);
    expect(setStatus).toHaveBeenCalledWith('Site pivoté de 90° — les obstacles gardent leur orientation nord-sud.');
  });

  it('Annuler restaure aussi environnement, zones d’exclusion et mesures', () => {
    const { ctx, zones, historique } = montage();
    const avant = JSON.stringify([ctx.environment, ctx.exclusionZones, ctx.measurements, ctx.areas.map((a) => a.vertices)]);
    const refEnv = ctx.environment;
    expect(zones.pivoterSiteActif(90)).toBe(true);
    expect(JSON.stringify([ctx.environment, ctx.exclusionZones, ctx.measurements])).not.toBe(JSON.stringify(JSON.parse(avant).slice(0, 3)));
    const photo = historique.undo(photoAtelierDepuisCtx(ctx));
    expect(photo).not.toBeNull();
    restaurerEnvZonesMesures(ctx, photo!);
    ctx.areas.splice(0, ctx.areas.length, ...photo!.areas);
    expect(JSON.stringify([ctx.environment, ctx.exclusionZones, ctx.measurements, ctx.areas.map((a) => a.vertices)])).toBe(avant);
    expect(ctx.environment).toBe(refEnv); // référence stable
    expect(historique.canUndo()).toBe(false); // une seule photo
  });

  it('un pan avec panneaux posés : refus nommé, rien ne bouge, aucune photo', () => {
    const { areas, zones, pousser, setStatus } = montage({ panneaux: true });
    const avant = JSON.stringify(areas);
    expect(zones.pivoterSiteActif(90)).toBe(false);
    expect(JSON.stringify(areas)).toBe(avant);
    expect(pousser).not.toHaveBeenCalled();
    expect(setStatus).toHaveBeenCalledWith('Zone area-2 : des panneaux sont posés — retirez la pose avant de pivoter le site.');
  });

  it('un angle illisible est refusé', () => {
    const { zones, pousser } = montage();
    expect(zones.pivoterSiteActif(Number.NaN)).toBe(false);
    expect(pousser).not.toHaveBeenCalled();
  });
});

// ACAL520 — le cadenas d'un pan refuse cotes et rotation (le glissé de sommet et la suppression sont
// gardés par `motifPanVerrouille`, même fonction, dans obstaclesUi.ts et roof-tool-pro11.ts).
describe('ACAL520 — pan verrouillé : cotes et rotation refusées', () => {
  it('appliquerAuPanActif refuse en nommant le pan ; déverrouiller rétablit le geste', () => {
    const areas = [{ ...zone('area-1', [...CARRE]), label: 'Pan 1', verrouille: true }, zone('area-2', [...CARRE])];
    const ctx = makeCtx(areas);
    const setStatus = vi.fn();
    const zones = createZones(ctx, { redrawTrace: vi.fn(), redrawObstacles: vi.fn(), recalc: vi.fn(), setStatus });
    const avant = JSON.stringify(ctx.vertices);
    expect(zones.pivoterPanActif(90)).toBe(false);
    expect(zones.redimensionnerPanActif(8, 12)).toBe(false);
    expect(JSON.stringify(ctx.vertices)).toBe(avant);
    expect(setStatus).toHaveBeenCalledWith('Zone 1 verrouillé — déverrouillez-le d’abord.'); // ACAL1430
    delete areas[0].verrouille;
    expect(zones.pivoterPanActif(90)).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL1916 (revue) — « Voir » un autre pan d'un calepinage rouvert ne réécrit rien.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL1916 — choisir un pan intact ne capture rien (entrée `selectArea`)', () => {
  /** Le corps de `selectArea` dans l'entrée (une page à effets de bord, non importable : voir SOURCE_ENTREE). */
  const corpsSelectArea = (): string => {
    const i = SOURCE_ENTREE.indexOf('function selectArea(id: string)');
    expect(i).toBeGreaterThan(0);
    return SOURCE_ENTREE.slice(i, SOURCE_ENTREE.indexOf('loadArea(target);', i));
  };

  it('les trois captures du pan quitté passent derrière `selectionSansChangement` sur la pose vivante', () => {
    const corps = corpsSelectArea();
    const garde = corps.indexOf('selectionSansChangement(actif,');
    expect(garde).toBeGreaterThan(0);
    expect(corps).toContain('geometrieZoneActive(ctx,');
    for (const capture of ['capturerGeometrieActive();', 'snapshotActiveAreaGeometry();', 'snapshotActiveAreaResult();']) {
      expect(corps.indexOf(capture)).toBeGreaterThan(garde); // jamais capturé avant la garde (mutant : capturer à chaque sélection)
    }
  });

  it('enregistré, rouvert, reposé tel quel : « inchangé » ; un panneau retiré le rend modifié', () => {
    const centres = Array.from({ length: 10 }, (_, i) => ({ cx: -2 * (i % 5), cy: 2 * Math.floor(i / 5) }));
    const conteneur = document.createElement('div');
    document.body.appendChild(conteneur);
    const monter = (areas: AreaRecord[], poses: number) => {
      const ctx = {
        ...(makeCtx(areas, 'z1') as unknown as Record<string, unknown>),
        layoutMode: true,
        layoutPlan: {
          pack: { origin: [LNG0, LAT0], ringENU: [[-60, -60], [60, -60], [60, 60], [-60, 60]], azimuthDeg: 0 },
          grid: { rowWidthM: 2, footprintPerPanelM2: 2, slopeLenM: 1, kwc: 10 * 0.71, panels: centres },
          tiltDeg: 0, family: 'south', flush: false,
        } as unknown as LayoutPlan,
        layoutState: createLayoutState(centres, poses),
        layoutOptimalCount: 6,
        layoutSel: null, freeMode: false, freeState: null,
      } as unknown as Ctx;
      return { ctx, editor: createLayoutEditor(ctx, depsEditeur(carteEditeurFactice(conteneur))) };
    };
    // « Enregistrer » : le document tel que l'atelier l'écrit (6 posés sur le pan 1, pan 2 vide).
    const z1 = panDeTest('z1', { vertices: [...CARRE], roofType: 'flat', neededPanels: 6, neededAuto: false });
    const z2 = panDeTest('z2', { vertices: CARRE.map(([x, y]) => [x + 0.0002, y] as LngLat), roofType: 'flat' });
    const doc = JSON.parse(JSON.stringify(serializeLayout(monter([z1, z2], 6).ctx)));
    // Réouverture : le pan relu porte sa pose, l'optimum repave (10), puis la pose enregistrée est reposée (PV27).
    const areas = deserializeLayout(doc);
    const { ctx, editor } = monter(areas, 10);
    expect(editor.hydrateLayout(doc.zones[0].geometry.panels, doc.zones[0].geometry.origin, 'lattice')).toBe(true);
    const vif = { vertices: ctx.vertices, obstacles: ctx.obstacles, roofType: ctx.roofType, pitchDeg: ctx.pitchDeg, facingAzimuthDeg: ctx.facingAzimuthDeg, facingManual: ctx.facingManual, neededPanels: ctx.neededPanels, neededAuto: ctx.neededAuto };
    expect(selectionSansChangement(areas[0], vif, geometrieZoneActive(ctx))).toBe(true);
    ctx.layoutState!.occupied.delete(5); // un panneau retiré à la main
    expect(selectionSansChangement(areas[0], vif, geometrieZoneActive(ctx))).toBe(false);
  });
});
