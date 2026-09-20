// CAL49 — GÉOCODAGE DANS LE PAYS DU PROJET. Les deux appels MapTiler forçaient
// `&country=ma`. Ce fichier prouve le constructeur d'URL pour `ma`, `fr` et contexte
// absent (repli `ma` : comportement marocain byte-identique), et la mention affichée
// à côté du champ de recherche. PURE : aucun DOM, aucune carte.
import { describe, expect, it } from 'vitest';
import {
  GEOCODE_DEFAULT_COUNTRY,
  geocodeCountry,
  geocodeSearchUrl,
  geocodeReverseUrl,
  geocodeCountryNote,
} from './mapDraw';

describe('CAL49 — pays du géocodage', () => {
  it('contexte absent → repli `ma` (comportement historique)', () => {
    expect(GEOCODE_DEFAULT_COUNTRY).toBe('ma');
    expect(geocodeCountry(undefined)).toBe('ma');
    expect(geocodeCountry(null)).toBe('ma');
    expect(geocodeCountry('')).toBe('ma');
    expect(geocodeCountry('   ')).toBe('ma');
  });

  it('un code ISO-2 est normalisé en minuscules', () => {
    expect(geocodeCountry('FR')).toBe('fr');
    expect(geocodeCountry(' fr ')).toBe('fr');
    expect(geocodeCountry('ma')).toBe('ma');
  });

  it('une valeur qui n’est pas un code ISO-2 retombe sur le repli, jamais dans l’URL', () => {
    expect(geocodeCountry('france')).toBe('ma');
    expect(geocodeCountry('f')).toBe('ma');
    expect(geocodeCountry('1234')).toBe('ma');
  });
});

describe('CAL49 — URL de recherche d’adresse', () => {
  it('contexte absent → URL byte-identique à celle d’avant CAL49', () => {
    expect(geocodeSearchUrl('casablanca', 'K')).toBe(
      'https://api.maptiler.com/geocoding/casablanca.json?key=K&country=ma&limit=5&language=fr',
    );
  });

  it('pays=ma → même URL', () => {
    expect(geocodeSearchUrl('casablanca', 'K', 'ma')).toBe(
      'https://api.maptiler.com/geocoding/casablanca.json?key=K&country=ma&limit=5&language=fr',
    );
  });

  it('pays=fr → l’adresse française devient trouvable', () => {
    expect(geocodeSearchUrl('lyon', 'K', 'fr')).toBe(
      'https://api.maptiler.com/geocoding/lyon.json?key=K&country=fr&limit=5&language=fr',
    );
  });

  it('la requête et la clé restent encodées', () => {
    const url = geocodeSearchUrl('rue de l’Étoile & co', 'a b', 'fr');
    expect(url).toContain('key=a%20b');
    expect(url).not.toContain(' & co');
    expect(url.startsWith('https://api.maptiler.com/geocoding/')).toBe(true);
  });
});

describe('CAL49 — URL de géocodage inverse', () => {
  it('contexte absent → country=ma, comme avant', () => {
    expect(geocodeReverseUrl(-7.6, 33.5, 'K')).toBe(
      'https://api.maptiler.com/geocoding/-7.6,33.5.json?key=K&language=fr&country=ma',
    );
  });

  it('pays=fr → country=fr', () => {
    expect(geocodeReverseUrl(4.83, 45.76, 'K', 'FR')).toBe(
      'https://api.maptiler.com/geocoding/4.83,45.76.json?key=K&language=fr&country=fr',
    );
  });
});

describe('CAL49 — mention du pays filtré affichée à côté du champ', () => {
  it('nomme le pays réellement filtré', () => {
    expect(geocodeCountryNote('fr')).toBe('Recherche limitée au pays : FR');
    expect(geocodeCountryNote(null)).toBe('Recherche limitée au pays : MA');
  });
});
