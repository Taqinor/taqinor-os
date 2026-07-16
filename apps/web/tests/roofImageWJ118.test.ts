// WJ118 — Photo satellite drapée sur la 3D de la page client (/proposition/
// [token]). Deux volets testés :
//  (a) le convertisseur PUR `roofLayoutOutlineLatLng` (lib/proposition.ts) qui
//      aplatit tous les sommets [lng,lat] de `roof_layout.zones[].vertices`
//      (champ backend exposé depuis QJ26) en un contour [lat,lng] — la
//      convention attendue par `buildPublicRoofImageSpec` (roofPro11/
//      viewerOnly.ts, IDENTIQUE à `captureOutline`) ;
//  (b) une vérification en LECTURE SOURCE (même convention que
//      propositionViewerKeyboardWJ90.test.ts) que [token].astro câble bien
//      `roofImage` sur `createRoofViewer` et que le commentaire périmé
//      (« backend n'expose pas encore roof_layout ») a disparu.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { roofLayoutOutlineLatLng, parseRoofLayout, type RoofLayout } from '../src/lib/proposition';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const PROPOSITION = read('../src/pages/proposition/[token].astro');

function zone(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'z1',
    label: 'Pan',
    vertices: [
      [-7.62, 33.58],
      [-7.6198, 33.58],
      [-7.6198, 33.5802],
      [-7.62, 33.5802],
    ],
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 0,
    facingAzimuthDeg: 180,
    neededPanels: 4,
    ...over,
  };
}

describe('WJ118 — roofLayoutOutlineLatLng (aplati [lng,lat] → [lat,lng])', () => {
  it('anneau normal : même ensemble de sommets, coordonnées inversées', () => {
    const layout: RoofLayout = { version: 1, zones: [zone() as unknown as RoofLayout['zones'][number]] };
    const outline = roofLayoutOutlineLatLng(layout);
    expect(outline).toEqual([
      [33.58, -7.62],
      [33.58, -7.6198],
      [33.5802, -7.6198],
      [33.5802, -7.62],
    ]);
  });

  it('plusieurs zones : sommets de TOUTES les zones aplatis (même ensemble que le centroïde buildViewerModel)', () => {
    const layout: RoofLayout = {
      version: 1,
      zones: [
        zone({
          id: 'z1',
          vertices: [[-7.62, 33.58], [-7.6199, 33.58], [-7.6199, 33.5801]],
        }) as unknown as RoofLayout['zones'][number],
        zone({
          id: 'z2',
          vertices: [[-7.6198, 33.5802], [-7.6197, 33.5802], [-7.6197, 33.5803]],
        }) as unknown as RoofLayout['zones'][number],
      ],
    };
    expect(roofLayoutOutlineLatLng(layout)).toHaveLength(6);
  });

  it('layout null ou sans zone → tableau vide (le client saute alors l’appel réseau)', () => {
    expect(roofLayoutOutlineLatLng(null)).toEqual([]);
    expect(roofLayoutOutlineLatLng({ version: 1, zones: [] })).toEqual([]);
  });

  it('sommets malformés filtrés — jamais un throw', () => {
    const layout = {
      version: 1,
      zones: [
        zone({
          vertices: [
            [-7.62, 33.58],
            [Number.NaN, 33.58],
            [-7.62] as unknown as [number, number],
            'nope' as unknown as [number, number],
            [-7.6198, 33.5802],
          ],
        }),
      ],
    } as unknown as RoofLayout;
    expect(roofLayoutOutlineLatLng(layout)).toEqual([
      [33.58, -7.62],
      [33.5802, -7.6198],
    ]);
  });

  it('zone sans tableau vertices, ou layout sans tableau zones → ignoré, jamais un throw', () => {
    const noVertices = { version: 1, zones: [{ id: 'z1' }] } as unknown as RoofLayout;
    expect(roofLayoutOutlineLatLng(noVertices)).toEqual([]);
    const zonesNotArray = { version: 1, zones: 'nope' } as unknown as RoofLayout;
    expect(roofLayoutOutlineLatLng(zonesNotArray)).toEqual([]);
  });

  it('cohérence avec parseRoofLayout : contour issu d’un payload backend brut', () => {
    const layout = parseRoofLayout({ version: 1, zones: [zone()] });
    expect(layout).not.toBeNull();
    const outline = roofLayoutOutlineLatLng(layout);
    expect(outline).toHaveLength(4);
    // [lat,lng] : la latitude de Casablanca est ~33, la longitude ~-7.
    for (const [lat, lng] of outline) {
      expect(lat).toBeGreaterThan(33);
      expect(lat).toBeLessThan(34);
      expect(lng).toBeLessThan(-7);
    }
  });
});

describe('WJ118 — [token].astro câble roofImage sur la visionneuse 3D', () => {
  it('calcule roofOutlineLatLng côté serveur et le sérialise dans viewerConfig', () => {
    expect(PROPOSITION).toContain('roofLayoutOutlineLatLng');
    expect(PROPOSITION).toMatch(/JSON\.stringify\(\{\s*model:\s*viewerModel,\s*roofOutlineLatLng\s*\}\)/);
  });

  it('lit roofOutlineLatLng du dataset côté client', () => {
    expect(PROPOSITION).toContain('roofOutlineLatLng?: Array<[number, number]>');
    expect(PROPOSITION).toContain('roofOutlineLatLng = Array.isArray(parsed.roofOutlineLatLng)');
  });

  it('appelle buildPublicRoofImageSpec puis passe roofImage à createRoofViewer', () => {
    expect(PROPOSITION).toContain('mod.buildPublicRoofImageSpec({ outline: roofOutlineLatLng })');
    expect(PROPOSITION).toMatch(/createRoofViewer\(stage, model, \{[\s\S]{0,200}roofImage,/);
    // Jamais un court-circuit qui forcerait roofImage à null (régression triviale).
    expect(PROPOSITION).not.toMatch(/roofImage:\s*null\s*,/);
  });

  it('bascule .roof3d-stage--sky UNIQUEMENT dans onReady (photo réellement drapée)', () => {
    expect(PROPOSITION).toContain("stage.classList.add('roof3d-stage--sky')");
    expect(PROPOSITION).toContain('.roof3d-stage.roof3d-stage--sky');
  });

  it('le commentaire périmé « backend n’expose pas (encore) roof_layout » a disparu', () => {
    expect(PROPOSITION).not.toMatch(/backend n['’]expose pas(?: encore)? `?roof_layout`?/);
    expect(PROPOSITION).not.toMatch(/QJ26,\s*pas encore en\s*\n?\s*prod aujourd'hui/);
  });
});
