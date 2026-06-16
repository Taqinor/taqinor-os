// Résolution de la clé MapTiler pour /api/roof-config.
//
// RÉGRESSION (bug live 2026-06-13) : la clé était posée en VARIABLE DE BUILD
// Cloudflare — présente au build (inlinée par Vite dans import.meta.env), mais
// ABSENTE du runtime (cf.env). L'endpoint ne lisait que cf.env → renvoyait
// available:false → repli affiché alors que la clé existait. Le helper doit
// accepter l'une OU l'autre source ; le repli ne reste QUE si aucune n'a de clé.
import { describe, expect, it } from 'vitest';
import {
  resolveMaptilerKey,
  resolveMapboxToken,
  buildSatelliteStyle,
  roofImageSize,
  roofImageRequest,
  roofVertexUV,
  mapboxStaticRoofImageUrl,
} from '../src/lib/roofConfig';

describe('resolveMaptilerKey — clé runtime OU build, repli seulement si aucune', () => {
  it('aucune source → chaîne vide (repli gracieux légitime)', () => {
    expect(resolveMaptilerKey(undefined, undefined)).toBe('');
    expect(resolveMaptilerKey('', '')).toBe('');
    expect(resolveMaptilerKey('   ', '   ')).toBe('');
  });

  it('variable de BUILD seule (le cas du bug) → utilisée', () => {
    expect(resolveMaptilerKey(undefined, 'BUILD_KEY')).toBe('BUILD_KEY');
    expect(resolveMaptilerKey('', 'BUILD_KEY')).toBe('BUILD_KEY');
  });

  it('variable RUNTIME seule → utilisée', () => {
    expect(resolveMaptilerKey('RUNTIME_KEY', undefined)).toBe('RUNTIME_KEY');
    expect(resolveMaptilerKey('RUNTIME_KEY', '')).toBe('RUNTIME_KEY');
  });

  it('les deux présentes → la runtime gagne (surcharge sans rebuild possible)', () => {
    expect(resolveMaptilerKey('RUNTIME_KEY', 'BUILD_KEY')).toBe('RUNTIME_KEY');
  });

  it('espaces ignorés (trim)', () => {
    expect(resolveMaptilerKey('  RK  ', undefined)).toBe('RK');
    expect(resolveMaptilerKey(undefined, '  BK  ')).toBe('BK');
  });
});

// Le token Mapbox PUBLIC (imagerie satellite Maxar Vivid, plus nette que MapTiler
// sur le Maroc) suit EXACTEMENT la même plomberie que la clé MapTiler : runtime
// (cf.env) OU build (import.meta.env), repli seulement si aucune.
describe('resolveMapboxToken — même résolution runtime OU build que MapTiler', () => {
  it('aucune source → chaîne vide', () => {
    expect(resolveMapboxToken(undefined, undefined)).toBe('');
    expect(resolveMapboxToken('', '')).toBe('');
    expect(resolveMapboxToken('   ', '   ')).toBe('');
  });

  it('variable de BUILD seule → utilisée', () => {
    expect(resolveMapboxToken(undefined, 'BUILD_TOKEN')).toBe('BUILD_TOKEN');
  });

  it('variable RUNTIME seule → utilisée', () => {
    expect(resolveMapboxToken('RUNTIME_TOKEN', undefined)).toBe('RUNTIME_TOKEN');
  });

  it('les deux présentes → la runtime gagne', () => {
    expect(resolveMapboxToken('RUNTIME_TOKEN', 'BUILD_TOKEN')).toBe('RUNTIME_TOKEN');
  });

  it('espaces ignorés (trim)', () => {
    expect(resolveMapboxToken('  RT  ', undefined)).toBe('RT');
  });
});

// L'imagerie satellite de l'estimateur : Mapbox quand un token est présent,
// REPLI inchangé sur le style hybride MapTiler quand il manque (ordre de pose
// des variables Cloudflare indifférent : pas de token = comportement actuel).
describe('buildSatelliteStyle — Mapbox si token, repli MapTiler sinon', () => {
  it('token présent → source raster Mapbox Satellite (@2x), tileSize 256, attribution Maxar', () => {
    const style = buildSatelliteStyle({ maptilerKey: 'MK', mapboxToken: 'MB_TOKEN' });
    expect(typeof style).toBe('object');
    const src = (style as { sources: Record<string, { type: string; tiles: string[]; tileSize: number; attribution: string }> })
      .sources['mapbox-satellite'];
    expect(src.type).toBe('raster');
    expect(src.tiles[0]).toContain('api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg90');
    expect(src.tiles[0]).toContain('access_token=MB_TOKEN');
    expect(src.tileSize).toBe(256); // le schéma v4 @2x utilise les tuiles 256
    expect(src.attribution).toContain('Mapbox');
    expect(src.attribution).toContain('Maxar');
    // La couche raster s'appuie bien sur cette source.
    const layers = (style as { layers: { type: string; source: string }[] }).layers;
    expect(layers.some((l) => l.type === 'raster' && l.source === 'mapbox-satellite')).toBe(true);
    // Jamais de schéma mapbox:// (non supporté par MapLibre).
    expect(JSON.stringify(style)).not.toContain('mapbox://');
  });

  it('token absent ou vide → repli sur le style hybride MapTiler (URL inchangée)', () => {
    for (const token of [undefined, '', '   ']) {
      const style = buildSatelliteStyle({ maptilerKey: 'MK_KEY', mapboxToken: token });
      expect(typeof style).toBe('string');
      expect(style as string).toContain('api.maptiler.com/maps/hybrid/style.json');
      expect(style as string).toContain('key=MK_KEY');
    }
  });
});

describe('roofImageSize — aspect géographique préservé (alignement exact)', () => {
  it('toit large (E-O) : plus grand côté = maxPx, hauteur au ratio', () => {
    const s = roofImageSize(40, 20, 1024);
    expect(s.w).toBe(1024);
    expect(s.h).toBe(512);
  });
  it('toit haut (N-S) : hauteur = maxPx', () => {
    const s = roofImageSize(10, 30, 900);
    expect(s.h).toBe(900);
    expect(s.w).toBe(300);
  });
  it('carré → carré', () => {
    const s = roofImageSize(15, 15, 600);
    expect(s.w).toBe(600);
    expect(s.h).toBe(600);
  });
  it('borne Mapbox : jamais > 1280, jamais < 1', () => {
    const big = roofImageSize(1000, 10, 5000);
    expect(big.w).toBeLessThanOrEqual(1280);
    expect(big.h).toBeGreaterThanOrEqual(1);
  });
});

// CORRECTIF #4 (détourage de la photo de toit) : l'étendue d'une requête `[bbox]`
// Static est élargie par l'endpoint (padding/cadrage) → l'imagerie des voisins
// débordait sur le toit. On demande désormais par CENTRE+ZOOM et on CALCULE
// l'étendue réellement couverte, pour des UV alignés au pixel près.
describe('roofImageRequest — centre+zoom déterministes, étendue calculée contenant la bbox', () => {
  const bbox: [number, number, number, number] = [-7.62, 33.58, -7.6, 33.59];
  const req = roofImageRequest(bbox);

  it('le centre est au milieu de la bbox', () => {
    expect(req.center[0]).toBeCloseTo(-7.61, 6);
    expect(req.center[1]).toBeCloseTo(33.585, 4);
  });

  it('l’étendue calculée CONTIENT entièrement la bbox du toit (jamais plus petite)', () => {
    const [exMinLng, exMinLat, exMaxLng, exMaxLat] = req.extent;
    expect(exMinLng).toBeLessThanOrEqual(bbox[0] + 1e-9);
    expect(exMinLat).toBeLessThanOrEqual(bbox[1] + 1e-9);
    expect(exMaxLng).toBeGreaterThanOrEqual(bbox[2] - 1e-9);
    expect(exMaxLat).toBeGreaterThanOrEqual(bbox[3] - 1e-9);
  });

  it('aspect d’image en Mercator de la bbox → étendue ≈ bbox (marge minimale, pas une zone large)', () => {
    const [exMinLng, exMinLat, exMaxLng, exMaxLat] = req.extent;
    // Débordement < 1 % de la taille de la bbox sur chaque axe (cadrage serré).
    expect(exMaxLng - exMinLng).toBeLessThan((bbox[2] - bbox[0]) * 1.01);
    expect(exMaxLat - exMinLat).toBeLessThan((bbox[3] - bbox[1]) * 1.02);
    expect(req.zoom).toBeGreaterThan(0);
    expect(req.zoom).toBeLessThanOrEqual(22);
  });

  it('toit minuscule → zoom borné à 22 (imagerie satellite max)', () => {
    const tiny = roofImageRequest([-7.6, 33.58, -7.59995, 33.580045]);
    expect(tiny.zoom).toBeLessThanOrEqual(22);
  });
});

describe('roofVertexUV — UV depuis la VRAIE position du sommet dans l’étendue de l’image', () => {
  const extent: [number, number, number, number] = [-7.62, 33.58, -7.6, 33.59];
  it('coin sud-ouest → (0,0), coin nord-est → (1,1)', () => {
    const [u0, v0] = roofVertexUV(-7.62, 33.58, extent);
    const [u1, v1] = roofVertexUV(-7.6, 33.59, extent);
    expect(u0).toBeCloseTo(0, 6);
    expect(v0).toBeCloseTo(0, 6);
    expect(u1).toBeCloseTo(1, 6);
    expect(v1).toBeCloseTo(1, 6);
  });
  it('le nord (lat haute) tombe en haut de l’image (v plus grand — flipY THREE)', () => {
    const [, vNorth] = roofVertexUV(-7.61, 33.589, extent);
    const [, vSouth] = roofVertexUV(-7.61, 33.581, extent);
    expect(vNorth).toBeGreaterThan(vSouth);
  });
  it('un sommet au coin de la bbox du toit retombe DANS l’image (UV ∈ [0,1]) — pas de débordement', () => {
    // L'étendue contient la bbox, donc tout sommet du toit a des UV valides.
    const req = roofImageRequest([-7.62, 33.58, -7.6, 33.59]);
    for (const [lng, lat] of [
      [-7.62, 33.58],
      [-7.6, 33.59],
      [-7.61, 33.585],
    ] as [number, number][]) {
      const [u, v] = roofVertexUV(lng, lat, req.extent);
      expect(u).toBeGreaterThanOrEqual(0);
      expect(u).toBeLessThanOrEqual(1);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });
});

describe('mapboxStaticRoofImageUrl — image satellite par centre+zoom (étendue déterministe)', () => {
  const url = mapboxStaticRoofImageUrl('TOK EN', [-7.61, 33.585], 19.5, 800, 400);
  it('cible l’endpoint satellite Static avec centre,zoom,bearing (PAS une bbox élargie)', () => {
    expect(url).toContain('api.mapbox.com/styles/v1/mapbox/satellite-v9/static/');
    expect(url).toContain('/-7.61,33.585,19.5000,0/');
    expect(url).toContain('/800x400@2x');
    expect(url).not.toContain('['); // plus aucune requête par bbox
  });
  it('réutilise le token (encodé) et retire logo/attribution de l’image', () => {
    expect(url).toContain('access_token=TOK%20EN');
    expect(url).toContain('logo=false');
    expect(url).toContain('attribution=false');
  });
  it('borne les dimensions et le zoom hors plage', () => {
    const u = mapboxStaticRoofImageUrl('t', [0, 0], 99, 99999, 0);
    expect(u).toContain('/1280x1@2x');
    expect(u).toContain('0,0,22.0000,0'); // zoom borné à 22
  });
});
