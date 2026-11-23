// CAL48 — REGISTRE DE FOURNISSEURS D'IMAGERIE. Prouve trois choses : (1) le registre
// déclare les fournisseurs avec leur attribution OBLIGATOIRE et leur résolution ANNONCÉE
// (jamais estimée) ; (2) le style d'un fournisseur porte cette attribution, que la carte
// affiche ; (3) SANS section `imagerie`, `buildSatelliteStyle` produit exactement le
// style d'avant CAL48 — non-régression stricte.
import { describe, expect, it, vi } from 'vitest';
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
  IGN_BD_ORTHO_ID,
  ignBdOrthoTileUrl,
  CADASTRE_FR_ID,
  cadastreFrTileUrl,
  optionalLayers,
  getOptionalLayer,
  availableOptionalLayers,
  optionalLayerSourceSpec,
  type ImageryProvider,
  imageryDisclosure,
  resolutionSourceRefus,
  styleSansImagerie,
  brancherRepliImagerie,
  themeSombreActif,
  FOND_SANS_IMAGERIE_CLAIR,
  FOND_SANS_IMAGERIE_SOMBRE,
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

describe('CAL50 — IGN BD ORTHO® : fournisseur France optionnel, attribution obligatoire', () => {
  it('avec pays=fr le fournisseur apparaît dans la liste proposable', () => {
    const ids = availableImageryProviders({ pays: 'fr' }, KEYS).map((p) => p.id);
    expect(ids).toContain(IGN_BD_ORTHO_ID);
  });

  it('avec pays=ma il est ABSENT de la liste', () => {
    const ids = availableImageryProviders({ pays: 'ma' }, KEYS).map((p) => p.id);
    expect(ids).not.toContain(IGN_BD_ORTHO_ID);
  });

  it('sans pays réglé il est ABSENT (jamais actif par défaut hors France)', () => {
    expect(availableImageryProviders({}, KEYS).map((p) => p.id)).not.toContain(IGN_BD_ORTHO_ID);
    expect(availableImageryProviders(null, KEYS).map((p) => p.id)).not.toContain(IGN_BD_ORTHO_ID);
  });

  it('il n’est pas actif d’office en France : il faut le nommer ou l’autoriser en tête', () => {
    // Liste autorisée classique, IGN non mentionné → ce n’est pas lui qui gagne.
    const p1 = resolveImageryProvider({ pays: 'fr', fournisseurs_autorises: ['mapbox', 'maptiler'] }, KEYS);
    expect(p1?.id).toBe('mapbox');
    // Nommé explicitement → il gagne.
    const p2 = resolveImageryProvider(
      { pays: 'fr', fournisseur_imagerie: IGN_BD_ORTHO_ID, fournisseurs_autorises: [IGN_BD_ORTHO_ID, 'maptiler'] },
      KEYS,
    );
    expect(p2?.id).toBe(IGN_BD_ORTHO_ID);
  });

  it('l’attribution IGN est obligatoire et portée par le style (donc affichée)', () => {
    const p = getImageryProvider(IGN_BD_ORTHO_ID)!;
    expect(p.attribution).toContain('IGN');
    expect(p.attribution).toContain('BD ORTHO');
    const style = buildProviderStyle(p, KEYS) as { sources: Record<string, { attribution: string; tiles: string[] }> };
    expect(style.sources[IGN_BD_ORTHO_ID].attribution).toContain('BD ORTHO');
    expect(style.sources[IGN_BD_ORTHO_ID].tiles).toEqual([ignBdOrthoTileUrl()]);
  });

  it('aucune clé ni jeton n’est requis : il est servable sans clés du tout', () => {
    expect(availableImageryProviders({ pays: 'fr', fournisseurs_autorises: [IGN_BD_ORTHO_ID] }, {}).map((p) => p.id)).toEqual([
      IGN_BD_ORTHO_ID,
    ]);
    expect(ignBdOrthoTileUrl()).not.toContain('key=');
    expect(ignBdOrthoTileUrl()).not.toContain('access_token');
  });

  it('les quotas/conditions sont documentés et la résolution n’est pas inventée', () => {
    const p = getImageryProvider(IGN_BD_ORTHO_ID)!;
    expect(p.quotas && p.quotas.length > 0).toBe(true);
    expect(p.resolutionM).toBeNull();
  });
});

describe('CAL54 — parcellaire cadastral : calque optionnel France, purement visuel', () => {
  it('activé par la société ET pays=fr → proposable', () => {
    const ids = availableOptionalLayers({ pays: 'fr', calques_optionnels: [CADASTRE_FR_ID] }).map((l) => l.id);
    expect(ids).toEqual([CADASTRE_FR_ID]);
  });

  it('activé mais pays=ma → non proposable (le parcellaire français n’existe pas là-bas)', () => {
    expect(availableOptionalLayers({ pays: 'ma', calques_optionnels: [CADASTRE_FR_ID] })).toEqual([]);
  });

  it('société muette → AUCUN calque optionnel (comportement d’aujourd’hui)', () => {
    expect(availableOptionalLayers({})).toEqual([]);
    expect(availableOptionalLayers(null)).toEqual([]);
    expect(availableOptionalLayers({ pays: 'fr' })).toEqual([]);
  });

  it('un identifiant de calque inconnu est ignoré, jamais inventé', () => {
    expect(availableOptionalLayers({ pays: 'fr', calques_optionnels: ['inconnu'] })).toEqual([]);
    expect(getOptionalLayer('inconnu')).toBeNull();
  });

  it('attribution obligatoire, aucune clé payante, quotas documentés', () => {
    const l = getOptionalLayer(CADASTRE_FR_ID)!;
    expect(l.attribution).toContain('IGN');
    expect(l.quotas && l.quotas.length > 0).toBe(true);
    expect(cadastreFrTileUrl()).not.toContain('key=');
    expect(cadastreFrTileUrl()).not.toContain('access_token');
    const src = optionalLayerSourceSpec(l) as { type: string; attribution: string; tiles: string[] };
    expect(src.type).toBe('raster');
    expect(src.attribution).toContain('IGN');
    expect(src.tiles).toEqual([cadastreFrTileUrl()]);
  });

  it('PUREMENT VISUEL : le calque ne change ni le fond, ni le fournisseur, ni aucune entrée de calcul', () => {
    const sans = { pays: 'fr', fournisseurs_autorises: ['maptiler'] };
    const avec = { ...sans, calques_optionnels: [CADASTRE_FR_ID] };
    // Même style de fond, à l’octet près.
    expect(buildSatelliteStyle({ maptilerKey: 'K', mapboxToken: 'T', imagery: avec })).toEqual(
      buildSatelliteStyle({ maptilerKey: 'K', mapboxToken: 'T', imagery: sans }),
    );
    // Même fournisseur actif.
    expect(resolveImageryProvider(avec, KEYS)?.id).toBe(resolveImageryProvider(sans, KEYS)?.id);
    // Un calque optionnel n’est JAMAIS un fournisseur d’imagerie : il ne peut donc pas
    // devenir le fond, ni porter la moindre donnée de calcul.
    expect(imageryProviders().map((p) => p.id)).not.toContain(CADASTRE_FR_ID);
    expect(optionalLayers().every((l) => l.visualOnly === true)).toBe(true);
  });
});

describe('ACAL508 — d’où vient l’image', () => {
  const base: ImageryProvider = {
    id: 'essai', label: 'Essai Satellite', attribution: 'x', resolutionM: null, countries: null,
  };
  it('sans résolution annoncée : la phrase « non annoncées », jamais un nombre', () => {
    expect(imageryDisclosure(getImageryProvider('mapbox'))).toBe(
      'Image : Mapbox Satellite (Maxar Vivid) — date et résolution non annoncées par le fournisseur',
    );
    expect(imageryDisclosure(base)).not.toMatch(/\d/);
  });
  it('avec résolution ET source : la valeur et l’URL', () => {
    const p = { ...base, resolutionM: 0.3, resolutionSource: 'https://fournisseur.example/resolution' };
    expect(imageryDisclosure(p)).toBe(
      'Image : Essai Satellite — résolution annoncée : 0,3 m par pixel (source : https://fournisseur.example/resolution)',
    );
    expect(resolutionSourceRefus(p)).toBeNull();
  });
  it('une résolution sans source est refusée en nommant le fournisseur et n’est jamais affichée', () => {
    const p = { ...base, resolutionM: 0.3 };
    expect(resolutionSourceRefus(p)).toContain('« essai »');
    expect(imageryDisclosure(p)).not.toContain('0,3');
  });
  it('les trois fournisseurs déclarés respectent la règle', () => {
    for (const id of ['maptiler', 'mapbox', 'ign_bd_ortho']) expect(resolutionSourceRefus(getImageryProvider(id)!)).toBeNull();
  });
  it('aucun fournisseur ⇒ aucune ligne', () => {
    expect(imageryDisclosure(null)).toBe('');
  });
});

describe('ACAL2004 — le fond neutre de la carte suit le thème', () => {
  const fond = (s: object) => (s as { layers: { paint: Record<string, string> }[] }).layers[0].paint['background-color'];
  it('clair : le papier chaud d’avant ; sombre : le fond de scène nuit', () => {
    expect(fond(styleSansImagerie('K'))).toBe(FOND_SANS_IMAGERIE_CLAIR);
    expect(fond(styleSansImagerie('K', false))).toBe('#e7e5df');
    expect(fond(styleSansImagerie('K', true))).toBe(FOND_SANS_IMAGERIE_SOMBRE);
    expect(FOND_SANS_IMAGERIE_SOMBRE).toBe('#0a0f2a');
  });
  it('la bascule de repli lit le thème au moment où le style est refusé', () => {
    const poses: object[] = [];
    let erreur: (e: unknown) => void = () => undefined;
    brancherRepliImagerie<object>({
      on: (_ev, h) => { erreur = h; },
      once: () => undefined,
      isStyleLoaded: () => false,
      setStyle: (s: object) => { poses.push(s); },
    }, () => undefined, 'K');
    // Environnement node : un <html> minimal porte la classe `.dark` comme l'ERP le pose.
    vi.stubGlobal('document', { documentElement: { classList: { contains: (c: string) => c === 'dark' } } });
    try {
      expect(themeSombreActif()).toBe(true);
      erreur({ error: { message: 'refusé' } });
    } finally { vi.unstubAllGlobals(); }
    expect(poses).toHaveLength(1);
    expect(fond(poses[0])).toBe(FOND_SANS_IMAGERIE_SOMBRE);
    expect(themeSombreActif()).toBe(false);
  });
});
