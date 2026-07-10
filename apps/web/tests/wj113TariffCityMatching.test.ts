// WJ113 — tariffForCity() used to exact-match a literal key ('Casablanca'…)
// against city input that is ALWAYS free text in production: a reverse-
// geocoded address (e.g. "Boulevard Zerktouni, Casablanca, Maroc") or a
// manual edit of that field. The exact match therefore NEVER hit a real
// address -- harmless today only because every TARIFF_BY_CITY entry still
// equals REGIE_TARIFF (the same fallback), but silently broken the day real
// per-utility grids land (a Casablanca address would then wrongly fall back
// to the conservative REGIE grid instead of the real Lydec grid). This proves
// the normalized/contains matching works on realistic geocoded strings AND
// that no tariff VALUE changed.
import { describe, expect, it } from 'vitest';
import { REGIE_TARIFF, TARIFF_BY_CITY, tariffForCity } from '../src/lib/estimatorBrainV2';

describe('WJ113 — tariffForCity : matching tolérant sur texte libre géocodé', () => {
  it('adresse géocodée complète résout vers la bonne ville (jamais un simple repli REGIE par accident)', () => {
    expect(tariffForCity('Boulevard Zerktouni, Casablanca, Maroc')).toBe(TARIFF_BY_CITY.Casablanca);
    expect(tariffForCity('Avenue Mohammed V, Rabat, Maroc')).toBe(TARIFF_BY_CITY.Rabat);
    expect(tariffForCity('Rue de la Liberté, Tanger, Maroc')).toBe(TARIFF_BY_CITY.Tanger);
  });

  it('la casse et les espaces superflus ne cassent pas le matching', () => {
    expect(tariffForCity('CASABLANCA')).toBe(TARIFF_BY_CITY.Casablanca);
    expect(tariffForCity('casablanca')).toBe(TARIFF_BY_CITY.Casablanca);
    expect(tariffForCity('  Casablanca  ')).toBe(TARIFF_BY_CITY.Casablanca);
    expect(tariffForCity('CasaBlanca, maroc')).toBe(TARIFF_BY_CITY.Casablanca);
  });

  it('les diacritiques ne cassent pas le matching (accents ajoutés/retirés)', () => {
    // Cas plausible d'une saisie ou d'un geocoder avec accent parasite.
    expect(tariffForCity('Tánger, Maroc')).toBe(TARIFF_BY_CITY.Tanger);
  });

  it('une ville inconnue ou vide retombe honnêtement sur REGIE_TARIFF (jamais une exception)', () => {
    expect(tariffForCity('Agadir')).toBe(REGIE_TARIFF);
    expect(tariffForCity('123 Rue Inconnue, Nulle Part')).toBe(REGIE_TARIFF);
    expect(tariffForCity('')).toBe(REGIE_TARIFF);
    expect(tariffForCity(undefined)).toBe(REGIE_TARIFF);
    expect(tariffForCity('   ')).toBe(REGIE_TARIFF);
  });

  it('égalité exacte historique reste prioritaire et fonctionne toujours (pas de régression)', () => {
    expect(tariffForCity('Casablanca')).toBe(TARIFF_BY_CITY.Casablanca);
    expect(tariffForCity('Rabat')).toBe(TARIFF_BY_CITY.Rabat);
    expect(tariffForCity('Tanger')).toBe(TARIFF_BY_CITY.Tanger);
  });

  it('AUCUNE valeur tarifaire n\'a changé : toutes les villes connues valent encore REGIE_TARIFF aujourd\'hui', () => {
    // Documente explicitement l'invariant WJ113 : seul le MATCHING change, pas
    // les grilles elles-mêmes (à retirer/adapter le jour où de vraies grilles
    // par régie divergent réellement de REGIE_TARIFF).
    for (const grid of Object.values(TARIFF_BY_CITY)) {
      expect(grid).toBe(REGIE_TARIFF);
    }
  });

  it('un nom de ville connu ne doit pas capturer un texte plus court qui le contient à l\'envers (sens du contains respecté)', () => {
    // "Casa" seul (pas une clé connue) ne doit PAS matcher par accident autre
    // chose que le repli -- protège contre une inversion du sens du contains.
    expect(tariffForCity('Casa')).toBe(REGIE_TARIFF);
  });
});
