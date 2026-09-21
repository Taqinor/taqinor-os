// @vitest-environment jsdom
// CÂBLAGES du lot 2 (Groupe CALX) — chaque crochet laissé par une lane de phase A/B est
// ici EXERCÉ : la fonction existait et était testée, il manquait la ligne qui l'appelle.
// Ce fichier ne prouve que ces lignes-là (aucune fonctionnalité neuve).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createZones } from './zones';
import { couleursAretes, EDGE_COLOR_BY_TYPE, type EdgeDeductionZone } from './edges';
import { deserializeLayout } from './prefill';
import { etiquette, registreAtelier, reinitialiserNumerotation } from './numerotation';
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

const CARRE: LngLat[] = [ptM(-5, -5), ptM(5, -5), ptM(5, 5), ptM(-5, 5)];

function zone(id: string, vertices: LngLat[]): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices,
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 10,
    neededAuto: true,
    result: null,
    renderPlan: null,
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
    closed: true,
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
    expect(setStatus).toHaveBeenCalledWith(expect.stringContaining('Zone area-1'));
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
