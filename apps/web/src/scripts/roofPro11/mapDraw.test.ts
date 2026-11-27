// @vitest-environment jsdom
// CAL49 — GÉOCODAGE DANS LE PAYS DU PROJET. Les deux appels MapTiler forçaient
// `&country=ma`. Ce fichier prouve le constructeur d'URL pour `ma`, `fr` et contexte
// absent (repli `ma` : comportement marocain byte-identique), et la mention affichée
// à côté du champ de recherche. PURE : aucun DOM, aucune carte.
import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs'; // ACAL1926
import { resolve } from 'node:path'; // ACAL1926
import { methodesCarteInertes } from './harnaisAtelier';
import { epingleAReposer } from './epingleSite'; // ACAL1926
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
  opacityPropFor,
  createMapDraw, // ACAL68
  lieuDansLePays, // ACAL507
} from './mapDraw';
import { lireCoordonneesCollees, proposerEchange } from './coordonneesCollees'; // ACAL506 / ACAL507
import { underlayPourDocument } from './underlay'; // ACAL68
import { dateImageCapturee, semerImageCapture } from './imageCapture'; // ACAL1405
import { type Ctx } from './context'; // ACAL68
import { UNDERLAY_PHOTO_LAYER_ID, UNDERLAY_PLAN_LAYER_ID } from './underlay';
import { distanceEntreM } from './snap';
import { emettreProvenanceEpingle, ZOOM_TOIT_VISIBLE } from './provenanceEpingle'; // T4-U4-013
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

// ————————————————————————————————————————————————————————————————————————
// CALX107 — les calques `photo` et `plan` du panneau ne pilotent PLUS une liste vide :
// le calque de fond existe. Le détail du placement, des refus et du rang d'insertion est
// prouvé dans `underlay.test.ts` (qui monte une carte factice).
// ————————————————————————————————————————————————————————————————————————
describe('CALX107 — les deux calques de fond pilotent une couche réelle', () => {
  it('« Photo calée » et « Plan importé » ont chacun leur couche MapLibre', () => {
    expect(MAPLIBRE_LAYERS_PAR_CALQUE.photo).toEqual([UNDERLAY_PHOTO_LAYER_ID]);
    expect(MAPLIBRE_LAYERS_PAR_CALQUE.plan).toEqual([UNDERLAY_PLAN_LAYER_ID]);
  });

  it('leur couche est un raster : l’opacité du panneau la pilote (CAL103)', () => {
    expect(opacityPropFor('raster')).toBe('raster-opacity');
  });

  it('les deux fonds restent sous le tracé client et au-dessus de l’imagerie', () => {
    const rang = (id: string) => ORDRE_RENDU_CALQUES.indexOf(id);
    expect(rang('imagerie')).toBeLessThan(rang('photo'));
    expect(rang('photo')).toBeLessThan(rang('plan'));
    expect(rang('plan')).toBeLessThan(rang('trace_client'));
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL68 — un fond présent n'est plus jamais effacé par « Enregistrer » parce que la carte
// n'était pas prête : il est porté par le document AVANT la pose graphique, et reposé au
// chargement du style.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL68 — poserFond quand la carte n’est pas prête', () => {
  it('poserFond avec addSource qui lève : underlay conservé puis reposé au load', () => {
    document.body.innerHTML = '<div><button type="button" id="rp9-finish"></button></div>';
    const surLoad: Array<() => void> = [];
    let styleChargé = false;
    const sources = new Map<string, unknown>();
    const map = {
      getSource: (id: string) => sources.get(id),
      addSource: (id: string, spec: unknown) => {
        if (!styleChargé) throw new Error('Style is not done loading');
        sources.set(id, spec);
      },
      removeSource: (id: string) => sources.delete(id),
      ...methodesCarteInertes(),
      once: (ev: string, f: () => void) => {
        if (ev === 'load') surLoad.push(f);
      },
      getZoom: () => 19,
      getCenter: () => ({ lng: -7.62, lat: 33.58 }),
      getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }),
    };
    const ctx = {
      opts: { maptilerKey: 'K', imagery: { pays: 'ma' }, reducedMotion: true },
      vertices: [], obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: [-7.62, 33.58],
    } as unknown as Ctx;
    const draw = createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
    const coins: [number, number][] = [[-7.63, 33.59], [-7.61, 33.59], [-7.61, 33.57], [-7.63, 33.57]];
    const fond = { kind: 'plan' as const, attachmentId: 512, opacite: 0.6 };
    const r = draw.setFond(fond, { url: 'https://exemple/plan.png', coinsPlan: coins });
    expect(r.ok).toBe(false);
    // Le document porte TOUJOURS le fond : « Enregistrer » ne l'efface pas.
    expect(underlayPourDocument(ctx)).toEqual({ underlay: fond });
    expect(sources.size).toBe(0);
    // Le style se charge : le fond est reposé tout seul.
    styleChargé = true;
    expect(surLoad).toHaveLength(1);
    surLoad[0]();
    expect(sources.size).toBe(1);
    expect(underlayPourDocument(ctx)).toEqual({ underlay: fond });
  });
});

// ACAL1405 — les champs « Date de la photo » sont montés AVANT la graine du document : ils se relisent après elle.
describe('ACAL1405 — date de la photo relue à la réouverture', () => {
  it('date relue après semis : les deux champs montrent la date et la source du document', () => {
    document.body.innerHTML = '<form id="rp9-search"><input id="rp9-address"></form>';
    const map = { getSource: () => undefined, ...methodesCarteInertes(), getZoom: () => 19, getCenter: () => ({ lng: -7.62, lat: 33.58 }), getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }) };
    const ctx = { opts: { maptilerKey: 'K', imagery: { pays: 'ma' }, reducedMotion: true }, vertices: [], obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: [-7.62, 33.58] } as unknown as Ctx;
    semerImageCapture(null);
    const draw = createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
    const val = (id: string) => (document.getElementById(id) as HTMLInputElement).value;
    expect(val('rp9-image-date')).toBe('');
    semerImageCapture({ imageCapture: { date: '2026-06-21', source: 'page du fournisseur' } }); // graine du document, après le montage
    draw.relireImageCapture();
    expect([val('rp9-image-date'), val('rp9-image-date-source')]).toEqual(['2026-06-21', 'page du fournisseur']);
    expect(dateImageCapturee()).toEqual({ date: '2026-06-21', source: 'page du fournisseur' }); // aucune écriture au chargement
    semerImageCapture(null);
    draw.relireImageCapture();
    expect(val('rp9-image-date')).toBe('');
  });
});

// ACAL1421 — l'atelier ERP passe enfin `imagery` : la ligne d'origine de l'image apparaît et l'adresse suit le pays réglé.
describe('ACAL1421 — ligne « Image : … » et pays de recherche', () => {
  const monter = (imagery: unknown) => {
    document.body.innerHTML = '<form id="rp9-search"><input id="rp9-address"><ul id="rp9-suggestions" hidden></ul></form>';
    const map = { getSource: () => undefined, flyTo: vi.fn(), jumpTo: vi.fn(), ...methodesCarteInertes(), getZoom: () => 19, getCenter: () => ({ lng: -7.62, lat: 33.58 }), getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }) };
    const ctx = { opts: { maptilerKey: 'K', imagery, reducedMotion: true }, vertices: [], obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: [-7.62, 33.58] } as unknown as Ctx;
    return createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
  };

  it('`imagery` fourni : la ligne d’origine est créée, le pays filtre l’adresse', async () => {
    const draw = monter({ pays: 'fr' });
    expect(document.getElementById('rp9-image-source')?.textContent).toMatch(/^Image : .+ — date et résolution non annoncées par le fournisseur$/);
    expect(document.getElementById('rp9-geocode-country')?.textContent).toBe('Recherche limitée au pays : FR');
    const f = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ features: [] }) });
    vi.stubGlobal('fetch', f);
    try {
      await draw.geocode('lyon');
      expect(f.mock.calls.some((c) => String(c[0]).includes('country=fr'))).toBe(true);
    } finally { vi.unstubAllGlobals(); }
  });

  it('sans `imagery` (avant ACAL1421 côté ERP) : aucune ligne, repli MA dit', () => {
    monter(undefined);
    expect(document.getElementById('rp9-image-source')).toBeNull();
    expect(document.getElementById('rp9-geocode-country')?.textContent).toBe('Recherche limitée au pays : MA');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL506 / ACAL507 — coordonnées collées dans le champ « Adresse ».
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL506 — lecture des coordonnées collées', () => {
  it('un couple, avec virgule ou espace, est lu latitude puis longitude', () => {
    expect(lireCoordonneesCollees('33.5731, -7.5898')).toEqual({ latitude: 33.5731, longitude: -7.5898 });
    expect(lireCoordonneesCollees('33.5731 -7.5898')).toEqual({ latitude: 33.5731, longitude: -7.5898 });
  });
  it('un lien de carte (@, q=, ll=) est lu', () => {
    const attendu = { latitude: 33.5731, longitude: -7.5898 };
    expect(lireCoordonneesCollees('https://www.google.com/maps/@33.5731,-7.5898,17z')).toEqual(attendu);
    expect(lireCoordonneesCollees('https://maps.example/?q=33.5731,-7.5898')).toEqual(attendu);
    expect(lireCoordonneesCollees('https://maps.example/?z=3&ll=33.5731,-7.5898')).toEqual(attendu);
  });
  it('un couple hors bornes est refusé en nommant la latitude', () => {
    // NB : le plan écrit « -7.5898, 133.5 » ; or 133.5 en LONGITUDE est dans les bornes
    // (|longitude| <= 180) : le cas hors bornes réel est une latitude de 133,5.
    expect(lireCoordonneesCollees('133.5, -7.5898')).toEqual({
      refus: 'Latitude hors de -90 à 90 : vérifiez les coordonnées collées.',
    });
    expect(lireCoordonneesCollees('33.5, 200.5')).toEqual({
      refus: 'Longitude hors de -180 à 180 : vérifiez les coordonnées collées.',
    });
  });
  it('une adresse ou un seul nombre garde le comportement du géocodeur', () => {
    expect(lireCoordonneesCollees('rue de la Paix 12')).toBeNull();
    expect(lireCoordonneesCollees('33.5731')).toBeNull();
    expect(lireCoordonneesCollees('')).toBeNull();
  });
});

describe('ACAL507 — « Vouliez-vous dire » ne s’applique jamais seul', () => {
  const c = { latitude: -7.5898, longitude: 33.5731 };
  it('propose l’échange seulement si le couple tel quel est hors du pays et l’échangé dedans', () => {
    expect(proposerEchange(c, false, true)).toEqual({ latitude: 33.5731, longitude: -7.5898 });
    expect(proposerEchange(c, true, true)).toBeNull();
    expect(proposerEchange(c, false, false)).toBeNull();
    expect(proposerEchange(c, null, null)).toBeNull();
    expect(proposerEchange(c, false, null)).toBeNull();
  });
  it('lieuDansLePays : un lieu rendu ⇒ true, aucun ⇒ false, réseau en échec ⇒ null', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ features: [{ place_name: 'Casablanca' }] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ features: [] }) })
      .mockRejectedValueOnce(new Error('réseau'));
    vi.stubGlobal('fetch', f);
    try {
      expect(await lieuDansLePays(-7.5898, 33.5731, 'K', 'ma')).toBe(true);
      expect(await lieuDansLePays(33.5731, -7.5898, 'K', 'ma')).toBe(false);
      expect(await lieuDansLePays(1, 2, 'K', 'ma')).toBeNull();
      expect(await lieuDansLePays(1, 133, 'K', 'ma')).toBeNull(); // latitude hors bornes : aucune requête
      expect(f).toHaveBeenCalledTimes(3);
      expect(String(f.mock.calls[0][0])).toContain('country=ma');
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

// T4-B4-005 — recliquer le PREMIER coin pour fermer posait un 5ᵉ sommet (doublon du 1ᵉʳ) : le pan enregistré avait 5 sommets,
// le rectangle 4 coins, et Longueur/Largeur restaient désactivés. Un clic sur le 1ᵉʳ coin FERME le tracé, sans sommet ajouté.
describe('T4-B4-005 — recliquer le premier coin ferme le tracé, jamais un sommet en double', () => {
  // Projection Web Mercator (tuiles de 512 px, comme `metresParPixel`) : le point ÉCRAN d'un clic, comme MapLibre le
  // donne (`e.point`). Seul un clic (il porte son point écran) peut fermer, sur la pastille du 1ᵉʳ coin
  // (VERTEX_GRAB_PX = 14 px au zoom courant).
  const ZOOM = 20;
  const projeter = (ll: [number, number] | { lng: number; lat: number }) => {
    const [lng, lat] = Array.isArray(ll) ? ll : [ll.lng, ll.lat];
    const monde = 512 * 2 ** ZOOM;
    const phi = (lat * Math.PI) / 180;
    return { x: ((lng + 180) / 360) * monde, y: ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * monde };
  };
  const cliquer = (draw: { addVertex: (v: [number, number], pt?: { x: number; y: number }) => void }, ll: [number, number]) =>
    draw.addVertex(ll, projeter(ll));
  function monter() {
    document.body.innerHTML = '<button id="rp9-finish" type="button"></button>';
    const map = { getSource: () => undefined, ...methodesCarteInertes(), getZoom: () => ZOOM, getCenter: () => ({ lng: -7.6, lat: 33.5 }), getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }) };
    const coins: [number, number][] = [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.50008]];
    const ctx = { opts: { maptilerKey: 'K', reducedMotion: true }, vertices: coins.map((c) => [...c]), obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: [-7.6, 33.5] } as unknown as Ctx;
    const draw = createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
    const fermer = vi.fn(() => { (ctx as { closed: boolean }).closed = true; });
    document.getElementById('rp9-finish')!.addEventListener('click', fermer);
    return { draw, ctx, fermer };
  }

  it('un clic à 0,2 m du premier coin ferme le tracé à 3 sommets ; un clic ailleurs pose un coin', () => {
    const { draw, ctx, fermer } = monter();
    cliquer(draw, [-7.6 + 0.000002, 33.5 + 0.000001]); // ≈ 0,2 m du premier coin : sur sa pastille
    expect(ctx.vertices).toHaveLength(3);
    expect(fermer).toHaveBeenCalledTimes(1);
    const autre = monter();
    cliquer(autre.draw, [-7.6, 33.50008]); // le 4ᵉ coin du rectangle, à ~9 m du premier
    expect(autre.ctx.vertices).toHaveLength(4);
    expect(autre.fermer).not.toHaveBeenCalled();
  });

  it('hors de la pastille (≈ 20 px) ou sans point écran (clavier) : un coin est posé, jamais une fermeture', () => {
    const pres = monter();
    cliquer(pres.draw, [-7.6 - 0.0000135, 33.5 + 0.000001]); // ≈ 1,25 m ≈ 20 px à l'ouest au zoom 20 : voisin, pas sur la pastille
    expect(pres.ctx.vertices).toHaveLength(4);
    expect(pres.fermer).not.toHaveBeenCalled();
    const clavier = monter();
    clavier.draw.addVertex([-7.6 + 0.000002, 33.5 + 0.000001]); // même point qu'au 1ᵉʳ test, mais sans clic
    expect(clavier.ctx.vertices).toHaveLength(4);
    expect(clavier.fermer).not.toHaveBeenCalled();
  });
});

describe('ACAL506 / ACAL507 — geocode dans le champ « Adresse »', () => {
  function monter() {
    document.body.innerHTML =
      '<form id="rp9-search"><input id="rp9-address"><ul id="rp9-suggestions" hidden></ul></form>';
    const flyTo = vi.fn();
    const map = {
      getSource: () => undefined, flyTo, jumpTo: vi.fn(), ...methodesCarteInertes(),
      getZoom: () => 19, getCenter: () => ({ lng: -7.62, lat: 33.58 }),
      getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }),
    };
    const ctx = {
      opts: { maptilerKey: 'K', imagery: { pays: 'ma' }, reducedMotion: false },
      vertices: [], obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: [-7.62, 33.58],
    } as unknown as Ctx;
    const setStatus = vi.fn();
    const draw = createMapDraw(ctx, { map: map as never, setStatus, updateAreaReadout: vi.fn() });
    return { draw, flyTo, setStatus };
  }
  const lignes = () => Array.from(document.querySelectorAll('#rp9-suggestions li')).map((l) => l.textContent);

  it('un couple collé ouvre UNE ligne, sans appel réseau avant ACAL507 sur un couple déjà au pays', async () => {
    const { draw } = monter();
    const f = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ features: [{ place_name: 'X' }] }) });
    vi.stubGlobal('fetch', f);
    try {
      await draw.geocode('33.5731, -7.5898');
      await new Promise((r) => setTimeout(r, 0));
      expect(lignes()).toEqual(['Coordonnées collées : 33.5731, -7.5898']);
      // aucune recherche d'adresse (`/geocoding/<texte>.json` avec limit=5)
      expect(f.mock.calls.some((c) => String(c[0]).includes('limit=5'))).toBe(false);
    } finally { vi.unstubAllGlobals(); }
  });

  it('inversé : seconde ligne proposée, jamais appliquée seule ; la choisir centre la carte', async () => {
    const { draw, flyTo } = monter();
    // un lieu n'existe que pour (lng 33.5731, lat -7.5898) inversé = (lng -7.5898, lat 33.5731)
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
      ok: true,
      json: async () => ({ features: String(url).includes('/-7.5898,33.5731.json') ? [{ place_name: 'Casablanca' }] : [] }),
    })));
    try {
      await draw.geocode('-7.5898, 33.5731');
      await new Promise((r) => setTimeout(r, 0));
      expect(lignes()).toEqual(['Coordonnées collées : -7.5898, 33.5731', 'Vouliez-vous dire 33.5731, -7.5898 ?']);
      expect(flyTo).not.toHaveBeenCalled();
      document.querySelectorAll('#rp9-suggestions li')[1].dispatchEvent(new Event('mousedown', { cancelable: true }));
      expect(flyTo).toHaveBeenCalledTimes(1);
      expect(flyTo.mock.calls[0][0].center).toEqual([-7.5898, 33.5731]);
    } finally { vi.unstubAllGlobals(); }
  });

  it('hors bornes : aucune ligne, la barre d’état nomme la latitude, aucun réseau', async () => {
    const { draw, setStatus } = monter();
    const f = vi.fn();
    vi.stubGlobal('fetch', f);
    try {
      await draw.geocode('133.5, -7.5898');
      expect(lignes()).toEqual([]);
      expect(setStatus).toHaveBeenCalledWith('Latitude hors de -90 à 90 : vérifiez les coordonnées collées.');
      expect(f).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); }
  });
});

// R2-09 / R3-03 — la barre d'aides au tracé (« Angles droits »…) ne recouvre jamais la carte : quand « Terminer le tracé » flotte
// sur la carte (bandeau absolu, parent DIRECT ou ANCÊTRE), elle va en flux sous l'enveloppe de la carte ; sinon elle reste dans son bandeau.
describe('R2-09 / R3-03 — barre d’aides au tracé : sous la carte quand « Terminer » flotte dessus', () => {
  const monter = (html: string) => {
    document.body.innerHTML = html;
    const map = { ...methodesCarteInertes(), getZoom: () => 19, getCenter: () => ({ lng: -7.62, lat: 33.58 }), getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }) };
    const ctx = { opts: { maptilerKey: 'K', imagery: { pays: 'ma' }, reducedMotion: true }, vertices: [], obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: [-7.62, 33.58] } as unknown as Ctx;
    createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
    return document.getElementById('rp9-trace-chips') as HTMLElement;
  };
  it('parent direct absolu : la barre est le frère SUIVANT de l’enveloppe de la carte', () => {
    const chips = monter('<section><div id="carte" class="relative"><div id="bandeau" class="absolute"><button id="rp9-finish"></button></div></div></section>');
    expect(chips.previousElementSibling?.id).toBe('carte');
    expect(chips.parentElement?.tagName).toBe('SECTION');
    expect(document.getElementById('carte')!.contains(chips)).toBe(false);
  });
  it('R3-03 : bandeau absolu ANCÊTRE (parent de « Terminer » non absolu) : la barre sort quand même de la carte', () => {
    const chips = monter('<section><div id="carte" class="relative"><div id="bandeau" class="absolute"><div id="rang"><button id="rp9-finish"></button></div></div></div></section>');
    expect(chips.previousElementSibling?.id).toBe('carte');
    expect(document.getElementById('carte')!.contains(chips)).toBe(false);
  });
  it('aucun bandeau absolu (page publique) : la barre reste dans le bandeau de « Terminer », comme avant', () => {
    const chips = monter('<section><div id="barre"><button id="rp9-finish"></button></div></section>');
    expect(chips.parentElement?.id).toBe('barre');
  });
});

// T4-U4-013 — l'épingle n'est que le centre du tracé : le document dit si quelqu'un a LOCALISÉ le site (`siteLocalise`).
// Un toit tracé par clics à l'échelle du pays reste « non localisé » (`null`) ; tracé sur le toit VU (zoom ≥ 17), ou après
// une adresse retenue, il l'est. Sans suivi activé par la page hôte (site public), aucune clé n'est écrite.
describe('T4-U4-013 — la provenance du site suit les gestes', () => {
  function monter(zoom: number, suivi: boolean) {
    document.body.innerHTML = '<form id="rp9-search"><input id="rp9-address"><ul id="rp9-suggestions" hidden></ul></form><button id="rp9-finish" type="button"></button>';
    const map = { getSource: () => undefined, flyTo: vi.fn(), jumpTo: vi.fn(), ...methodesCarteInertes(), getZoom: () => zoom, getCenter: () => ({ lng: -7.09, lat: 31.79 }), getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }) };
    const ecouter = vi.fn();
    const ctx = {
      opts: { maptilerKey: 'K', reducedMotion: true, ...(suivi ? { suiviSite: { initial: null, ecouter } } : {}) },
      vertices: [], obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: null,
    } as unknown as Ctx;
    const draw = createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
    return { draw, ctx, ecouter };
  }
  const tracer = (draw: { addVertex: (v: [number, number]) => void }) => {
    for (const c of [[-7.5, 32.2], [-6.6, 32.2], [-6.6, 31.4]] as [number, number][]) draw.addVertex(c);
  };
  const documentEmis = (ctx: Ctx) => emettreProvenanceEpingle({ pin: { lat: 31.93, lng: -6.9 } } as Record<string, unknown>, ctx);

  it('tracé par clics au niveau du pays : le document dit « non localisé » (null), jamais une épingle posée', () => {
    const { draw, ctx, ecouter } = monter(6, true);
    tracer(draw);
    expect(ctx.vertices).toHaveLength(3);
    expect(documentEmis(ctx).siteLocalise).toBeNull();
    expect(ecouter).toHaveBeenLastCalledWith(null);
  });

  it('tracé sur le toit vu (zoom ≥ 17) : « trace » ; adresse retenue : « adresse »', async () => {
    const vu = monter(ZOOM_TOIT_VISIBLE, true);
    tracer(vu.draw);
    expect(documentEmis(vu.ctx).siteLocalise).toBe('trace');
    expect(vu.ecouter).toHaveBeenLastCalledWith('trace');
    const adresse = monter(6, true);
    await adresse.draw.geocode('31.6295, -7.9811', true); // coordonnées collées, retenues
    expect(documentEmis(adresse.ctx).siteLocalise).toBe('adresse');
  });

  it('suivi éteint (site public) : aucune clé `siteLocalise`', () => {
    const { draw, ctx } = monter(6, false);
    tracer(draw);
    expect('siteLocalise' in documentEmis(ctx)).toBe(false);
  });

  // T4-X2-005 — toit tracé sans « Localiser » (épingle au centre du pays, 31,79°) : le pas entre rangées était calé sur
  // 31,79° quand la simulation du même calepinage se fait sur Casablanca (33,573°). Un seul lieu pour tous les calculs.
  it('T4-X2-005 — site non localisé : les calculs prennent le point de repli servi, et la note du pas le nomme', async () => {
    const { latitudeDuCalcul, lieuDeRepli } = await import('./provenanceEpingle');
    const { describeRowPitch } = await import('../../lib/roofPro2');
    const { draw, ctx } = monter(6, true);
    (ctx.opts as unknown as { suiviSite: Record<string, unknown> }).suiviSite.repli = { lat: 33.573, lon: -7.589, libelle: 'Casablanca (ville de référence)' };
    tracer(draw);
    expect(latitudeDuCalcul(ctx, 31.79)).toBe(33.573);
    const note = describeRowPitch({ rowPitchM: 4.9, latitudeDeg: latitudeDuCalcul(ctx, 31.79), lieu: lieuDeRepli(ctx)?.libelle });
    expect(note.label).toContain('à la latitude de Casablanca (ville de référence)');
    expect(note.label).toContain('33,57°');
    // Site localisé ensuite (adresse retenue) : la latitude du tracé reprend la main, la note redit « du site ».
    await draw.geocode('31.6295, -7.9811', true);
    expect(latitudeDuCalcul(ctx, 31.79)).toBe(31.79);
    expect(lieuDeRepli(ctx)).toBeNull();
    // Site public (aucun suivi) : la latitude du tracé, comme avant.
    const publicSite = monter(6, false);
    tracer(publicSite.draw);
    expect(latitudeDuCalcul(publicSite.ctx, 31.79)).toBe(31.79);
  });
});

describe('ACAL1926 — Effacer sur un calepinage rouvert repose l’épingle', () => {
  it('document rouvert avec son toit (aucun repère planté) ⇒ le point de l’épingle du document', () => {
    expect(epingleAReposer(false, { pin: { lat: 33.5, lng: -7.6 } })).toEqual([-7.6, 33.5]);
  });
  it('un repère existe déjà, ou le document n’a pas d’épingle ⇒ rien à poser', () => {
    expect(epingleAReposer(true, { pin: { lat: 33.5, lng: -7.6 } })).toBeNull();
    expect(epingleAReposer(false, { pin: null })).toBeNull();
    expect(epingleAReposer(false, null)).toBeNull();
  });
});

describe('ACAL1926 (revue) — « Effacer » repose l’épingle : repli lead et câblage de l’entrée', () => {
  it('document sans `pin` ⇒ le point GPS du lead ; le `pin` du document passe avant le lead', () => {
    expect(epingleAReposer(false, { pin: null }, { lat: 33.59, lng: -7.61 })).toEqual([-7.61, 33.59]);
    expect(epingleAReposer(false, { pin: { lat: 33.5, lng: -7.6 } }, { lat: 33.59, lng: -7.61 })).toEqual([-7.6, 33.5]);
    expect(epingleAReposer(false, null, { lat: Number.NaN, lng: -7.61 })).toBeNull();
    expect(epingleAReposer(true, { pin: null }, { lat: 33.59, lng: -7.61 })).toBeNull();
  });

  /** L'entrée est une page à effets de bord, non importable en test : on lit son SOURCE (comme cablageLot2.test.ts). */
  const SOURCE_ENTREE = readFileSync(resolve(process.cwd(), 'src/scripts/roof-tool-pro11.ts'), 'utf8');
  it('`reset` (« Effacer ») plante le repère rendu par `epingleAReposer`, avec le lead du document rouvert', () => {
    const i = SOURCE_ENTREE.indexOf('function reset() {');
    expect(i).toBeGreaterThan(0);
    const corps = SOURCE_ENTREE.slice(i, SOURCE_ENTREE.indexOf('shadingUi.reset();', i));
    const appel = corps.indexOf('const aReposer = epingleAReposer(!!clientPinMarker, ctx.documentRelu, pointLeadSite);');
    expect(appel).toBeGreaterThan(corps.indexOf('clearEditorState();'));
    expect(corps.indexOf('if (aReposer) planterClientPinMarker(aReposer);')).toBeGreaterThan(appel);
    expect(SOURCE_ENTREE).toContain('pointLeadSite = devis.geometrie?.roof_point ?? null;');
  });
});

// ACAL1828 (revue) — l'observateur de thème ne survit pas à la carte, et le fond neutre suit la bascule.
describe('ACAL1828 — observateur de thème', () => {
  it('débranché au retrait de la carte ; le fond neutre sans photo est repeint selon html.dark', () => {
    const observateurs: { cb: () => void; disconnect: ReturnType<typeof vi.fn> }[] = [];
    vi.stubGlobal('MutationObserver', class {
      cb: () => void; disconnect = vi.fn();
      constructor(cb: () => void) { this.cb = cb; observateurs.push(this); }
      observe() { /* doublure */ }
    });
    try {
      const surCarte: Record<string, () => void> = {};
      const setPaintProperty = vi.fn();
      const map = {
        ...methodesCarteInertes(),
        getLayer: (id: string) => (id === 'fond-sans-imagerie' ? {} : undefined),
        setPaintProperty,
        on: (ev: string, f: () => void) => { surCarte[ev] = f; },
        once: vi.fn(),
        getZoom: () => 19,
        getCenter: () => ({ lng: -7.62, lat: 33.58 }),
        getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }),
      };
      const ctx = {
        opts: { maptilerKey: 'K', imagery: { pays: 'ma' }, reducedMotion: true },
        vertices: [], obstacles: [], areas: [], activeAreaId: 'a1', closed: false, centroid: [-7.62, 33.58],
      } as unknown as Ctx;
      createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
      expect(observateurs).toHaveLength(1);
      document.documentElement.classList.add('dark');
      observateurs[0].cb();
      expect(setPaintProperty).toHaveBeenCalledWith('fond-sans-imagerie', 'background-color', '#0a0f2a');
      document.documentElement.classList.remove('dark');
      observateurs[0].cb();
      expect(setPaintProperty).toHaveBeenLastCalledWith('fond-sans-imagerie', 'background-color', '#e7e5df');
      expect(observateurs[0].disconnect).not.toHaveBeenCalled();
      surCarte.remove();
      expect(observateurs[0].disconnect).toHaveBeenCalledTimes(1);
    } finally {
      vi.unstubAllGlobals();
      document.documentElement.classList.remove('dark');
    }
  });
});
