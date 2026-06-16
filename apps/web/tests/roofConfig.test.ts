// Résolution de la clé MapTiler pour /api/roof-config.
//
// RÉGRESSION (bug live 2026-06-13) : la clé était posée en VARIABLE DE BUILD
// Cloudflare — présente au build (inlinée par Vite dans import.meta.env), mais
// ABSENTE du runtime (cf.env). L'endpoint ne lisait que cf.env → renvoyait
// available:false → repli affiché alors que la clé existait. Le helper doit
// accepter l'une OU l'autre source ; le repli ne reste QUE si aucune n'a de clé.
import { describe, expect, it } from 'vitest';
import { resolveMaptilerKey, resolveMapboxToken, buildSatelliteStyle } from '../src/lib/roofConfig';

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
