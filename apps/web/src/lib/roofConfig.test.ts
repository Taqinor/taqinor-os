// CAL48 — REGISTRE DE FOURNISSEURS D'IMAGERIE. Prouve trois choses : (1) le registre
// déclare les fournisseurs avec leur attribution OBLIGATOIRE et leur résolution ANNONCÉE
// (jamais estimée) ; (2) le style d'un fournisseur porte cette attribution, que la carte
// affiche ; (3) SANS section `imagerie`, `buildSatelliteStyle` produit exactement le
// style d'avant CAL48 — non-régression stricte.
import { describe, expect, it } from 'vitest';
import {
  buildSatelliteStyle,
  maptilerHybridStyleUrl,
  mapboxSatelliteTileUrl,
  imageryProviders,
  getImageryProvider,
  registerImageryProvider,
  availableImageryProviders,
  resolveImageryProvider,
  imageryAttribution,
  buildProviderStyle,
  type ImageryProvider,
} from './roofConfig';

const KEYS = { maptilerKey: 'KEY', mapboxToken: 'TOK' };

describe('CAL48 — le registre déclare les fournisseurs existants, aucun de plus', () => {
  it('maptiler et mapbox sont déclarés, chacun avec une attribution NON vide', () => {
    const ids = imageryProviders().map((p) => p.id);
    expect(ids).toContain('maptiler');
    expect(ids).toContain('mapbox');
    for (const p of imageryProviders()) {
      expect(p.attribution.trim().length).toBeGreaterThan(0);
    }
  });

  it('la résolution est ANNONCÉE ou null — jamais un chiffre estimé', () => {
    for (const p of imageryProviders()) {
      expect(p.resolutionM === null || p.resolutionM > 0).toBe(true);
    }
    expect(getImageryProvider('maptiler')?.resolutionM).toBeNull();
    expect(getImageryProvider('mapbox')?.resolutionM).toBeNull();
  });

  it('un identifiant inconnu ne renvoie rien (aucun fournisseur inventé)', () => {
    expect(getImageryProvider('inconnu')).toBeNull();
    expect(getImageryProvider(null)).toBeNull();
  });
});

describe('CAL48 — sélection du fournisseur actif depuis les réglages société', () => {
  it('sans clé Mapbox, mapbox n’est pas proposable', () => {
    const list = availableImageryProviders({ fournisseurs_autorises: ['mapbox', 'maptiler'] }, { maptilerKey: 'K' });
    expect(list.map((p) => p.id)).toEqual(['maptiler']);
  });

  it('le fournisseur NOMMÉ par la société gagne quand il est proposable', () => {
    const p = resolveImageryProvider({ fournisseur_imagerie: 'maptiler', fournisseurs_autorises: ['mapbox', 'maptiler'] }, KEYS);
    expect(p?.id).toBe('maptiler');
  });

  it('fournisseur nommé non proposable → premier de la liste autorisée', () => {
    const p = resolveImageryProvider({ fournisseur_imagerie: 'inexistant', fournisseurs_autorises: ['mapbox', 'maptiler'] }, KEYS);
    expect(p?.id).toBe('mapbox');
  });

  it('un fournisseur restreint à un pays est écarté ailleurs', () => {
    const fake: ImageryProvider = {
      id: 'test_fr_only',
      label: 'Test FR',
      attribution: '© Test',
      resolutionM: 0.2,
      countries: ['fr'],
      tiles: () => ['https://example.invalid/{z}/{x}/{y}.png'],
    };
    registerImageryProvider(fake);
    expect(availableImageryProviders({ pays: 'fr' }, KEYS).map((p) => p.id)).toContain('test_fr_only');
    expect(availableImageryProviders({ pays: 'ma' }, KEYS).map((p) => p.id)).not.toContain('test_fr_only');
    expect(availableImageryProviders({}, KEYS).map((p) => p.id)).not.toContain('test_fr_only');
  });
});

describe('CAL48 — l’attribution du fournisseur actif est portée par le style', () => {
  it('un fournisseur à tuiles produit une source raster portant son attribution', () => {
    const p = getImageryProvider('mapbox')!;
    const style = buildProviderStyle(p, KEYS) as { sources: Record<string, { attribution: string }> };
    expect(style.sources.mapbox.attribution).toContain('Mapbox');
    expect(style.sources.mapbox.attribution).toContain('Maxar');
  });

  it('la mention SAISIE par la société complète celle du fournisseur, sans la remplacer', () => {
    const p = getImageryProvider('mapbox')!;
    const attr = imageryAttribution(p, { attribution: '© IGN — BD ORTHO®' });
    expect(attr).toContain('Mapbox');
    expect(attr).toContain('© IGN — BD ORTHO®');
  });

  it('un fournisseur à style URL renvoie son URL', () => {
    const p = getImageryProvider('maptiler')!;
    expect(buildProviderStyle(p, { maptilerKey: 'K' })).toBe(maptilerHybridStyleUrl('K'));
    expect(buildProviderStyle(p, {})).toBeNull();
  });
});

describe('CAL48 — sans contexte d’imagerie, le style est celui d’avant (non-régression)', () => {
  it('aucun token Mapbox → URL MapTiler hybride, inchangée', () => {
    expect(buildSatelliteStyle({ maptilerKey: 'K' })).toBe(maptilerHybridStyleUrl('K'));
  });

  it('token Mapbox → style raster Mapbox, identique à l’historique', () => {
    const style = buildSatelliteStyle({ maptilerKey: 'K', mapboxToken: 'T' }) as {
      version: number;
      sources: Record<string, { tiles: string[]; tileSize: number; attribution: string }>;
      layers: Array<{ id: string; type: string; source: string }>;
    };
    expect(style.version).toBe(8);
    expect(style.sources['mapbox-satellite'].tiles).toEqual([mapboxSatelliteTileUrl('T')]);
    expect(style.sources['mapbox-satellite'].tileSize).toBe(256);
    expect(style.layers).toEqual([{ id: 'mapbox-satellite', type: 'raster', source: 'mapbox-satellite' }]);
  });

  it('section `imagerie` VIDE = société qui n’a rien réglé ⇒ comportement identique', () => {
    expect(buildSatelliteStyle({ maptilerKey: 'K', imagery: {} })).toBe(maptilerHybridStyleUrl('K'));
    expect(buildSatelliteStyle({ maptilerKey: 'K', imagery: null })).toBe(maptilerHybridStyleUrl('K'));
  });

  it('section renseignée ⇒ c’est le registre qui décide', () => {
    const style = buildSatelliteStyle({
      maptilerKey: 'K',
      mapboxToken: 'T',
      imagery: { fournisseur_imagerie: 'maptiler', fournisseurs_autorises: ['maptiler', 'mapbox'] },
    });
    expect(style).toBe(maptilerHybridStyleUrl('K'));
  });
});
