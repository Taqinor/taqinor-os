// Drapé satellite PUBLIC de la visionneuse 3D (/devis/mon-toit, étape 2) —
// parties PURES de viewerOnly.ts : origine ENU (doit reproduire buildViewerModel
// au sommet près), élargissement de bbox pour le plan de sol, URL Static
// MapTiler, choix de fournisseur (même ordre de repli que la carte étape 0) et
// le constructeur async buildPublicRoofImageSpec (tous les chemins d'échec →
// null, jamais un throw, jamais une texture cassée côté visiteur).
import { describe, expect, it, vi } from 'vitest';
import {
  publicRoofOutlineOrigin,
  expandRoofBBox,
  maptilerStaticRoofImageUrl,
  publicRoofImageUrl,
  enuToLngLat,
  buildPublicRoofImageSpec,
} from '../src/scripts/roofPro11/viewerOnly';
import { roofImageRequest } from '../src/lib/roofConfig';

const DEG2RAD = Math.PI / 180;
const DEG2M = 111_320; // même constante que VIEWER_DEG2M (lib/proposition.ts)

// Contour [lat,lng] — MÊME convention que captureOutline (Casablanca, ~20 m).
const OUTLINE: Array<[number, number]> = [
  [33.58, -7.62],
  [33.58, -7.6198],
  [33.5802, -7.6198],
  [33.5802, -7.62],
];

describe('publicRoofOutlineOrigin — centroïde identique à buildViewerModel', () => {
  it('moyenne des sommets [lng,lat], dans l’ordre du contour', () => {
    const origin = publicRoofOutlineOrigin(OUTLINE);
    expect(origin).not.toBeNull();
    expect(origin![0]).toBeCloseTo(-7.6199, 10);
    expect(origin![1]).toBeCloseTo(33.5801, 10);
  });

  it('filtre les points invalides EXACTEMENT comme capturePreviewLayout', () => {
    const dirty = [
      ...OUTLINE,
      [Number.NaN, -7.62],
      [33.58] as unknown as [number, number],
      'nope' as unknown as [number, number],
    ] as Array<[number, number]>;
    expect(publicRoofOutlineOrigin(dirty)).toEqual(publicRoofOutlineOrigin(OUTLINE));
  });

  it('moins de 3 sommets valides → null (aucun modèle dessinable)', () => {
    expect(publicRoofOutlineOrigin([])).toBeNull();
    expect(publicRoofOutlineOrigin([[33.58, -7.62], [33.581, -7.62]])).toBeNull();
    expect(publicRoofOutlineOrigin([[33.58, -7.62], [Number.NaN, 1], [33.581, -7.62]])).toBeNull();
  });
});

describe('expandRoofBBox — contexte sol autour du toit', () => {
  const bbox: [number, number, number, number] = [-7.62, 33.58, -7.6198, 33.5802];
  const midLat = (bbox[1] + bbox[3]) / 2;
  const cosLat = Math.cos(midLat * DEG2RAD);
  const spanM = (b: [number, number, number, number]): [number, number] => [
    (b[2] - b[0]) * DEG2M * cosLat,
    (b[3] - b[1]) * DEG2M,
  ];

  it('contient toujours la bbox d’origine, centrée', () => {
    const out = expandRoofBBox(bbox);
    expect(out[0]).toBeLessThan(bbox[0]);
    expect(out[1]).toBeLessThan(bbox[1]);
    expect(out[2]).toBeGreaterThan(bbox[2]);
    expect(out[3]).toBeGreaterThan(bbox[3]);
    // centrée : même milieu (au flottant près)
    expect((out[0] + out[2]) / 2).toBeCloseTo((bbox[0] + bbox[2]) / 2, 9);
    expect((out[1] + out[3]) / 2).toBeCloseTo((bbox[1] + bbox[3]) / 2, 9);
  });

  it('envergure cible = max(facteur × envergure, minSpanM) par axe', () => {
    // Ce toit fait ~18,6 m × ~22,3 m → à ×2.5, les DEUX axes dépassent 40 m.
    const [wIn, hIn] = spanM(bbox);
    const [wOut, hOut] = spanM(expandRoofBBox(bbox, 2.5, 40));
    expect(wOut).toBeCloseTo(Math.max(wIn * 2.5, 40), 6);
    expect(hOut).toBeCloseTo(Math.max(hIn * 2.5, 40), 6);
  });

  it('petit toit → l’envergure minimale (40 m) garantit du contexte', () => {
    const tiny: [number, number, number, number] = [-7.62, 33.58, -7.619995, 33.580004];
    const [w, h] = spanM(expandRoofBBox(tiny));
    expect(w).toBeCloseTo(40, 4);
    expect(h).toBeCloseTo(40, 4);
  });
});

describe('maptilerStaticRoofImageUrl — Static Maps MapTiler (pure imagerie)', () => {
  const url = maptilerStaticRoofImageUrl('KEY 1', [-7.61, 33.585], 19.5, 800, 400);

  it('cible la map `satellite` (jamais hybrid : pas d’étiquettes sur le toit)', () => {
    expect(url).toContain('api.maptiler.com/maps/satellite/static/');
    expect(url).not.toContain('/hybrid/');
    expect(url).toContain('/-7.61,33.585,19.5000/');
    expect(url).toContain('/800x400@2x.jpg');
  });

  it('clé encodée + cachet incrusté retiré (l’attribution est affichée à côté)', () => {
    expect(url).toContain('key=KEY%201');
    expect(url).toContain('attribution=false');
  });

  it('borne dimensions (1–1280) et zoom (≤22) hors plage', () => {
    const u = maptilerStaticRoofImageUrl('k', [0, 0], 99, 99999, 0);
    expect(u).toContain('/1280x1@2x.jpg');
    expect(u).toContain('0,0,22.0000/');
  });
});

describe('publicRoofImageUrl — même ordre de repli que la carte étape 0', () => {
  const req = roofImageRequest([-7.62, 33.58, -7.6198, 33.5802]);

  it('token Mapbox présent → Static Mapbox satellite-v9 + « © Mapbox © Maxar »', () => {
    const picked = publicRoofImageUrl({ maptilerKey: 'MK', mapboxToken: 'MB' }, req);
    expect(picked).not.toBeNull();
    expect(picked!.provider).toBe('mapbox');
    expect(picked!.url).toContain('api.mapbox.com/styles/v1/mapbox/satellite-v9/static/');
    expect(picked!.url).toContain('access_token=MB');
    expect(picked!.attribution).toBe('© Mapbox © Maxar');
  });

  it('token absent, clé MapTiler présente → Static MapTiler + « © MapTiler © Maxar »', () => {
    const picked = publicRoofImageUrl({ maptilerKey: 'MK' }, req);
    expect(picked).not.toBeNull();
    expect(picked!.provider).toBe('maptiler');
    expect(picked!.url).toContain('api.maptiler.com/maps/satellite/static/');
    expect(picked!.url).toContain('key=MK');
    expect(picked!.attribution).toBe('© MapTiler © Maxar');
  });

  it('aucune clé (ou espaces seuls) → null (rendu abstrait conservé)', () => {
    expect(publicRoofImageUrl({}, req)).toBeNull();
    expect(publicRoofImageUrl({ maptilerKey: '  ', mapboxToken: '' }, req)).toBeNull();
  });
});

describe('enuToLngLat — inverse exact du toENU de buildViewerModel', () => {
  it('aller-retour lng/lat → ENU → lng/lat au sommet près', () => {
    const origin: [number, number] = [-7.6199, 33.5801];
    const cosLat = Math.cos(origin[1] * DEG2RAD);
    for (const [lng, lat] of [
      [-7.61975, 33.58022],
      [-7.62, 33.58],
      [-7.6198, 33.5802],
    ] as Array<[number, number]>) {
      const x = (lng - origin[0]) * DEG2M * cosLat; // toENU (proposition.ts)
      const y = (lat - origin[1]) * DEG2M;
      const [lng2, lat2] = enuToLngLat(x, y, origin);
      expect(lng2).toBeCloseTo(lng, 9);
      expect(lat2).toBeCloseTo(lat, 9);
    }
  });
});

// — buildPublicRoofImageSpec : TOUS les échecs → null, jamais un throw. —
function okConfig(cfg: object): typeof fetch {
  return vi.fn(async () => ({ ok: true, json: async () => cfg })) as unknown as typeof fetch;
}
const FAKE_IMG = { width: 2048, height: 2048 } as unknown as HTMLImageElement;

describe('buildPublicRoofImageSpec — chemin nominal et replis propres', () => {
  it('succès (token Mapbox) : spec complet, URL Mapbox passée au chargeur', async () => {
    const fetchImpl = okConfig({ maptilerKey: 'MK', mapboxToken: 'MB', available: true });
    const seenUrls: string[] = [];
    const spec = await buildPublicRoofImageSpec({
      outline: OUTLINE,
      fetchImpl,
      loadImageImpl: async (url) => {
        seenUrls.push(url);
        return FAKE_IMG;
      },
    });
    expect(spec).not.toBeNull();
    expect(spec!.provider).toBe('mapbox');
    expect(spec!.attribution).toBe('© Mapbox © Maxar');
    expect(spec!.image).toBe(FAKE_IMG);
    expect(spec!.origin[0]).toBeCloseTo(-7.6199, 9);
    expect(spec!.origin[1]).toBeCloseTo(33.5801, 9);
    // L'étendue de l'image contient la bbox du contour (toit + contexte sol).
    const [minLng, minLat, maxLng, maxLat] = spec!.extent;
    expect(minLng).toBeLessThan(-7.62);
    expect(minLat).toBeLessThan(33.58);
    expect(maxLng).toBeGreaterThan(-7.6198);
    expect(maxLat).toBeGreaterThan(33.5802);
    expect(seenUrls[0]).toContain('api.mapbox.com/styles/v1/mapbox/satellite-v9/static/');
    expect(fetchImpl).toHaveBeenCalledWith('/api/roof-config', expect.anything());
  });

  it('clé MapTiler seule → fournisseur maptiler', async () => {
    const spec = await buildPublicRoofImageSpec({
      outline: OUTLINE,
      fetchImpl: okConfig({ maptilerKey: 'MK', mapboxToken: '', available: true }),
      loadImageImpl: async () => FAKE_IMG,
    });
    expect(spec!.provider).toBe('maptiler');
    expect(spec!.attribution).toBe('© MapTiler © Maxar');
  });

  it('contour absent/invalide → null SANS toucher au réseau', async () => {
    const fetchImpl = okConfig({});
    expect(await buildPublicRoofImageSpec({ outline: [], fetchImpl })).toBeNull();
    expect(
      await buildPublicRoofImageSpec({ outline: [[33.58, -7.62], [33.581, -7.62]], fetchImpl }),
    ).toBeNull();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('aucune clé imagerie → null SANS tenter de charger une image', async () => {
    const loadImageImpl = vi.fn(async () => FAKE_IMG);
    const spec = await buildPublicRoofImageSpec({
      outline: OUTLINE,
      fetchImpl: okConfig({ maptilerKey: '', mapboxToken: '', available: false }),
      loadImageImpl,
    });
    expect(spec).toBeNull();
    expect(loadImageImpl).not.toHaveBeenCalled();
  });

  it('config HTTP non-ok / fetch qui jette / JSON invalide → null, jamais un throw', async () => {
    const notOk = vi.fn(async () => ({ ok: false, json: async () => ({}) })) as unknown as typeof fetch;
    expect(await buildPublicRoofImageSpec({ outline: OUTLINE, fetchImpl: notOk })).toBeNull();
    const throws = vi.fn(async () => {
      throw new Error('réseau coupé');
    }) as unknown as typeof fetch;
    expect(await buildPublicRoofImageSpec({ outline: OUTLINE, fetchImpl: throws })).toBeNull();
    const badJson = vi.fn(async () => ({
      ok: true,
      json: async () => {
        throw new Error('JSON invalide');
      },
    })) as unknown as typeof fetch;
    expect(await buildPublicRoofImageSpec({ outline: OUTLINE, fetchImpl: badJson })).toBeNull();
  });

  it('image en échec de chargement → null (le rendu abstrait reste)', async () => {
    const spec = await buildPublicRoofImageSpec({
      outline: OUTLINE,
      fetchImpl: okConfig({ maptilerKey: 'MK', mapboxToken: 'MB', available: true }),
      loadImageImpl: async () => null,
    });
    expect(spec).toBeNull();
  });
});
