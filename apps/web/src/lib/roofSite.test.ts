// CAL55 — ALTITUDE ET FUSEAU DU SITE, SOURCÉS, JAMAIS DEVINÉS.
// L'altitude est LUE dans la réponse PVGIS déjà reçue (`inputs.location.elevation`) et
// voyage avec sa source ; PVGIS muet ⇒ « non renseignée », jamais un nombre de repli.
// Le fuseau vient de la base IANA ou est SAISI — jamais dérivé de la longitude (le Maroc
// est à UTC+1 toute l'année depuis 2018 : une dérivation longitudinale le mettrait à UTC+0).
import { describe, expect, it } from 'vitest';
import {
  pvgisElevationM,
  resolveSiteAltitude,
  siteAltitudeLabel,
  PVGIS_ALTITUDE_SOURCE,
} from './roofEstimate';
import { isIanaTimeZone, siteTimeZone, siteTimeZoneLabel } from './roofConfig';

describe('CAL55 — altitude lue dans la réponse PVGIS, avec sa source', () => {
  it('une réponse PVGIS portant une élévation donne l’altitude ET sa source', () => {
    const a = pvgisElevationM({ inputs: { location: { latitude: 33.5, longitude: -7.6, elevation: 62 } } });
    expect(a).toEqual({ altitudeM: 62, source: PVGIS_ALTITUDE_SOURCE });
    expect(siteAltitudeLabel(a)).toBe('62 m (source PVGIS)');
  });

  it('une altitude négative (sous le niveau de la mer) est une vraie valeur, conservée', () => {
    expect(pvgisElevationM({ inputs: { location: { elevation: -3 } } })?.altitudeM).toBe(-3);
  });

  it('PVGIS muet ⇒ null, jamais 0 ni un repli', () => {
    expect(pvgisElevationM({})).toBeNull();
    expect(pvgisElevationM(null)).toBeNull();
    expect(pvgisElevationM(undefined)).toBeNull();
    expect(pvgisElevationM({ inputs: {} })).toBeNull();
    expect(pvgisElevationM({ inputs: { location: {} } })).toBeNull();
    expect(pvgisElevationM({ inputs: { location: { elevation: '62' } } })).toBeNull();
    expect(pvgisElevationM({ inputs: { location: { elevation: Number.NaN } } })).toBeNull();
    expect(siteAltitudeLabel(null)).toBe('Altitude non renseignée');
  });
});

describe('CAL55 — altitude retenue : la saisie terrain prime sur PVGIS', () => {
  const pvgis = { altitudeM: 62, source: PVGIS_ALTITUDE_SOURCE };

  it('altitude saisie + source saisie → c’est elle qui est retenue, avec SA source', () => {
    expect(resolveSiteAltitude({ altitude_m: 145, source_altitude: 'relevé GPS terrain du 12/03/2026' }, pvgis)).toEqual({
      altitudeM: 145,
      source: 'relevé GPS terrain du 12/03/2026',
    });
  });

  it('altitude saisie SANS source → retenue, mais la provenance n’est pas fabriquée', () => {
    expect(resolveSiteAltitude({ altitude_m: 145 }, pvgis)).toEqual({
      altitudeM: 145,
      source: 'saisie, source non renseignée',
    });
  });

  it('rien de saisi → la lecture PVGIS, telle quelle', () => {
    expect(resolveSiteAltitude({}, pvgis)).toEqual(pvgis);
    expect(resolveSiteAltitude(null, pvgis)).toEqual(pvgis);
    expect(resolveSiteAltitude({ altitude_m: null }, pvgis)).toEqual(pvgis);
  });

  it('rien de saisi ET PVGIS muet → null : « non renseignée »', () => {
    expect(resolveSiteAltitude({}, null)).toBeNull();
    expect(resolveSiteAltitude(null, null)).toBeNull();
  });
});

describe('CAL55 — fuseau horaire : base IANA ou saisie, jamais dérivé de la longitude', () => {
  it('un identifiant IANA est accepté tel quel', () => {
    expect(isIanaTimeZone('Africa/Casablanca')).toBe(true);
    expect(isIanaTimeZone('Europe/Paris')).toBe(true);
    expect(isIanaTimeZone('America/Argentina/Buenos_Aires')).toBe(true);
    expect(siteTimeZone({ fuseau: 'Africa/Casablanca' })).toBe('Africa/Casablanca');
  });

  it('ce qui n’est pas un identifiant de fuseau est refusé (aucun fuseau inventé)', () => {
    expect(isIanaTimeZone('UTC+1')).toBe(false);
    expect(isIanaTimeZone('-7.6')).toBe(false);
    expect(siteTimeZone({ fuseau: 'UTC+1' })).toBeNull();
    expect(siteTimeZone({ fuseau: '' })).toBeNull();
    expect(siteTimeZone({})).toBeNull();
    expect(siteTimeZone(null)).toBeNull();
  });

  it('le Maroc réglé à Africa/Casablanca reste Africa/Casablanca — la longitude n’entre jamais en jeu', () => {
    // La signature ne PEUT PAS recevoir de longitude : la dérivation est structurellement
    // impossible. Un site marocain (longitude ≈ -7,6 ⇒ UTC+0 si on dérivait) garde UTC+1.
    expect(siteTimeZone({ fuseau: 'Africa/Casablanca', pays: 'ma' })).toBe('Africa/Casablanca');
    expect(siteTimeZoneLabel({ fuseau: 'Africa/Casablanca' })).toBe('Fuseau : Africa/Casablanca (base de fuseaux IANA)');
    expect(siteTimeZoneLabel({})).toBe('Fuseau non renseigné');
  });
});
