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
  lireSaisieSegment,
  grilleMetrique,
  GRILLE_LAYER_ID,
  MAX_LIGNES_GRILLE,
  ORDRE_RENDU_CALQUES,
  MAPLIBRE_LAYERS_PAR_CALQUE,
} from './mapDraw';
import { distanceEntreM } from './snap';
import { geodesicAreaM2, layoutPanels, type LngLat } from '../../lib/roof';

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

// ————————————————————————————————————————————————————————————————————————
// CALX90 — SAISIE CLAVIER « longueur (m) / angle (°) ». La garantie de la tâche :
// AUCUNE valeur n'est posée quand un des deux champs est vide — jamais un angle supposé,
// jamais une longueur de repli — et le refus NOMME le champ fautif.
// ————————————————————————————————————————————————————————————————————————
describe('CALX90 — un champ vide ne pose RIEN et nomme le champ fautif', () => {
  it('longueur vide → refus sur « longueur », aucune cote rendue', () => {
    const r = lireSaisieSegment('', '90');
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('longueur');
    expect(r.motif).toContain('Longueur manquante');
    expect(r).not.toHaveProperty('distanceM');
  });

  it('angle vide → refus sur « angle », aucun cap supposé', () => {
    const r = lireSaisieSegment('12,5', '   ');
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.champ).toBe('angle');
    expect(r.motif).toContain('Angle manquant');
    expect(r).not.toHaveProperty('capDeg');
  });

  it('les deux champs vides → refus (aucun couple inventé)', () => {
    expect(lireSaisieSegment('', '').ok).toBe(false);
  });

  it('une longueur nulle ou négative est refusée sur son propre champ', () => {
    for (const v of ['0', '-3', 'abc']) {
      const r = lireSaisieSegment(v, '90');
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.champ).toBe('longueur');
    }
  });

  it('un angle illisible est refusé sur son propre champ', () => {
    const r = lireSaisieSegment('10', 'nord');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.champ).toBe('angle');
  });
});

describe('CALX90 — deux valeurs saisies : le couple est rendu tel quel', () => {
  it('lit les décimales à la française et un cap nul', () => {
    const r = lireSaisieSegment('12,5', '0');
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('lecture attendue');
    expect(r.distanceM).toBeCloseTo(12.5, 10);
    expect(r.capDeg).toBe(0);
  });

  it('tolère les espaces de saisie et le point décimal', () => {
    const r = lireSaisieSegment(' 100.25 ', ' 271,75 ');
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('lecture attendue');
    expect(r.distanceM).toBeCloseTo(100.25, 10);
    expect(r.capDeg).toBeCloseTo(271.75, 10);
  });

  it('un cap négatif reste celui de l’utilisateur (aucune normalisation cachée)', () => {
    const r = lireSaisieSegment('10', '-45');
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('lecture attendue');
    expect(r.capDeg).toBe(-45);
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX117 — GRILLE MÉTRIQUE DE REPÈRE AU PAS SAISI. Deux garanties : l'espacement RÉEL des
// lignes vaut le pas saisi, et la grille n'entre dans AUCUN calcul (puce éteinte = aucune
// source ; allumée = l'aire posable est rigoureusement inchangée).
// ————————————————————————————————————————————————————————————————————————
const CENTRE_GRILLE: LngLat = [-7.6, 33.5];

describe('CALX117 — l’espacement des lignes vaut le pas saisi', () => {
  it('un pas de 5 m donne 5 m de distance géodésique entre deux lignes voisines', () => {
    const trame = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 5, demiEtendueM: 40 });
    const paralleles = trame.features.filter((f) => f.properties.axe === 'u');
    expect(paralleles.length).toBeGreaterThan(2);
    for (let i = 1; i < paralleles.length; i++) {
      const a = paralleles[i - 1].geometry.coordinates[0];
      const b = paralleles[i].geometry.coordinates[0];
      expect(Math.abs(distanceEntreM(a, b) - 5)).toBeLessThan(0.001);
    }
  });

  it('tient pour l’autre axe et pour un autre pas', () => {
    const trame = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 2.5, demiEtendueM: 20 });
    const perpendiculaires = trame.features.filter((f) => f.properties.axe === 'v');
    for (let i = 1; i < perpendiculaires.length; i++) {
      const a = perpendiculaires[i - 1].geometry.coordinates[0];
      const b = perpendiculaires[i].geometry.coordinates[0];
      expect(Math.abs(distanceEntreM(a, b) - 2.5)).toBeLessThan(0.001);
    }
  });

  it('les deux familles de lignes sont perpendiculaires entre elles', () => {
    const trame = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 5, demiEtendueM: 20 });
    const u = trame.features.find((f) => f.properties.axe === 'u' && f.properties.rang === 0)!;
    const v = trame.features.find((f) => f.properties.axe === 'v' && f.properties.rang === 0)!;
    // Croix centrée : les deux lignes de rang 0 passent par le centre et se coupent au milieu.
    expect(distanceEntreM(u.geometry.coordinates[0], v.geometry.coordinates[0])).toBeGreaterThan(0);
    const milieuU: LngLat = [
      (u.geometry.coordinates[0][0] + u.geometry.coordinates[1][0]) / 2,
      (u.geometry.coordinates[0][1] + u.geometry.coordinates[1][1]) / 2,
    ];
    expect(distanceEntreM(milieuU, CENTRE_GRILLE)).toBeLessThan(0.001);
  });

  it('l’azimut demandé oriente la trame (nord vrai par défaut)', () => {
    const nord = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 5, demiEtendueM: 20 });
    const tournee = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 5, demiEtendueM: 20, azimutDeg: 30 });
    const bout = (t: typeof nord) =>
      t.features.find((f) => f.properties.axe === 'u' && f.properties.rang === 0)!.geometry.coordinates[1];
    expect(distanceEntreM(bout(nord), bout(tournee))).toBeGreaterThan(1);
    // À azimut 0, la ligne de rang 0 de l'axe u est plein nord : même longitude que le centre.
    expect(bout(nord)[0]).toBeCloseTo(CENTRE_GRILLE[0], 10);
  });
});

describe('CALX117 — PUCE ÉTEINTE : aucune source ajoutée', () => {
  it('un pas nul, négatif, absent ou illisible rend une trame VIDE', () => {
    for (const pas of [0, -5, Number.NaN]) {
      expect(grilleMetrique({ centre: CENTRE_GRILLE, pasM: pas, demiEtendueM: 40 }).features).toEqual([]);
    }
  });

  it('une étendue nulle (carte pas prête) rend une trame VIDE', () => {
    expect(grilleMetrique({ centre: CENTRE_GRILLE, pasM: 5, demiEtendueM: 0 }).features).toEqual([]);
  });

  it('un centre illisible rend une trame VIDE', () => {
    expect(grilleMetrique({ centre: [Number.NaN, 33.5], pasM: 5, demiEtendueM: 40 }).features).toEqual([]);
  });

  it('un pas trop fin pour la vue ne dessine RIEN (plafond de rendu)', () => {
    const trame = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 0.1, demiEtendueM: 500 });
    expect(trame.features).toEqual([]);
  });

  it('une trame affichée reste sous le plafond de rendu', () => {
    const trame = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 5, demiEtendueM: 200 });
    expect(trame.features.length).toBeGreaterThan(0);
    expect(trame.features.length).toBeLessThanOrEqual(MAX_LIGNES_GRILLE);
  });
});

describe('CALX117 — la grille n’entre dans AUCUN calcul', () => {
  const toit: LngLat[] = [
    [-7.6, 33.5],
    [-7.5993, 33.5],
    [-7.5993, 33.5004],
    [-7.6, 33.5004],
  ];

  it('l’aire posable est rigoureusement inchangée quand la grille est allumée', () => {
    const aireAvant = geodesicAreaM2(toit);
    const poseAvant = layoutPanels(toit);
    // On « allume » la grille : elle produit ses lignes, et rien d'autre.
    const trame = grilleMetrique({ centre: CENTRE_GRILLE, pasM: 5, demiEtendueM: 40 });
    expect(trame.features.length).toBeGreaterThan(0);
    expect(geodesicAreaM2(toit)).toBe(aireAvant);
    expect(layoutPanels(toit).panels.length).toBe(poseAvant.panels.length);
  });

  it('elle ne touche pas le contour qu’on lui passe en repère', () => {
    const copie = toit.map((v) => [v[0], v[1]] as LngLat);
    grilleMetrique({ centre: toit[0], pasM: 5, demiEtendueM: 40 });
    expect(toit).toEqual(copie);
  });

  it('sa couche n’appartient à AUCUN calque de l’ordre de rendu (CAL103)', () => {
    expect(GRILLE_LAYER_ID).toBe('rp9-grille');
    expect(ORDRE_RENDU_CALQUES).not.toContain(GRILLE_LAYER_ID);
    for (const couches of Object.values(MAPLIBRE_LAYERS_PAR_CALQUE)) {
      expect(couches).not.toContain(GRILLE_LAYER_ID);
    }
  });
});
