// @vitest-environment jsdom
//
/**
 * CALX128 — L'ATELIER AU CLAVIER, ET SES ANNONCES. Ce que ce fichier garde :
 *
 * 1. **Un contour complet se trace au clavier SEUL** — flèches + Entrée, sans une seule
 *    interaction souris, et le contour se ferme.
 * 2. **Chaque refus émet une annonce qui NOMME sa raison** — jamais un silence, jamais un
 *    « non enregistré » générique.
 * 3. **Les gestes souris/tactile existants sont inchangés** : le plan s'efface dans les
 *    champs de saisie, ne capte aucune touche hors plan, et les tests des autres modules
 *    passent sans modification (suite `roofPro11` entière verte).
 * 4. Le plan est DÉCLARATIF et l'aide en est DÉRIVÉE : elle ne peut pas mentir.
 * 5. La mesure s'affiche avec SA PRÉCISION — jamais arrondie en silence.
 */
import { describe, expect, it, vi } from 'vitest';
import {
  aideClavier,
  annoncePourVerdict,
  createClavier,
  creerAnnonceur,
  deplacerCurseur,
  estChampDeSaisie,
  estDeplacement,
  FACTEUR_PAS_RAPIDE,
  LIBELLE_MODE,
  motifGesteIndisponible,
  PAS_CURSEUR_PX,
  pasCurseurM,
  PLAN_CLAVIER,
  resoudreRaccourci,
  ZONE_ANNONCE_ID,
  type GestesAtelier,
  type ModeClavier,
} from './clavier';
import { createMapDraw } from './mapDraw';
import {
  ARRONDI_MESURE,
  createMesureUi,
  DECIMALES_MESURE,
  decrireMesure,
  formatMesurePrecise,
  gestesMesure,
  motifMesureIncomplete,
  POINTS_MINIMUM_MESURE,
} from './mesureUi';
import { distanceEntreM, metresParPixel } from './snap';
import { type Ctx } from './context';
import { type LngLat } from '../../lib/roof';

// ————————————————————————————————————————————————————————————————————————
// Le plan déclaratif et son aide
// ————————————————————————————————————————————————————————————————————————

describe('CALX128 — le plan clavier est DÉCLARATIF, et l’aide en est dérivée', () => {
  it('chaque entrée du plan porte sa touche, son libellé français et son écriture', () => {
    expect(PLAN_CLAVIER.length).toBeGreaterThan(0);
    for (const r of PLAN_CLAVIER) {
      expect(r.touches.length).toBeGreaterThan(0);
      expect(r.libelle.length).toBeGreaterThan(0);
      expect(r.ecriture.length).toBeGreaterThan(0);
      expect(r.action.length).toBeGreaterThan(0);
    }
  });

  it('l’aide affichable a exactement une ligne par entrée du plan', () => {
    const aide = aideClavier();
    expect(aide).toHaveLength(PLAN_CLAVIER.length);
    for (let i = 0; i < aide.length; i++) {
      expect(aide[i].touches).toBe(PLAN_CLAVIER[i].ecriture);
      expect(aide[i].libelle).toBe(PLAN_CLAVIER[i].libelle);
    }
  });

  it('l’aide d’un mode ne montre que ce qui agit RÉELLEMENT dans ce mode', () => {
    for (const mode of Object.keys(LIBELLE_MODE) as ModeClavier[]) {
      for (const ligne of aideClavier(mode)) {
        expect(ligne.modes === 'Tous les modes' || ligne.modes.includes(LIBELLE_MODE[mode])).toBe(true);
      }
    }
  });

  it('les quatre gestes annoncés par la tâche sont au plan : flèches, Entrée, Échap, Suppr', () => {
    const actions = PLAN_CLAVIER.map((r) => r.action);
    expect(actions).toContain('curseur-nord');
    expect(actions).toContain('curseur-sud');
    expect(actions).toContain('curseur-est');
    expect(actions).toContain('curseur-ouest');
    expect(actions).toContain('poser');
    expect(actions).toContain('sortir');
    expect(actions).toContain('supprimer');
    expect(PLAN_CLAVIER.find((r) => r.action === 'sortir')?.touches).toContain('Escape');
    expect(PLAN_CLAVIER.find((r) => r.action === 'supprimer')?.touches).toContain('Delete');
  });
});

describe('CALX128 — le routage n’attrape QUE ce que le plan déclare', () => {
  it('une flèche nue et Maj + flèche sont deux entrées distinctes', () => {
    const nue = resoudreRaccourci({ key: 'ArrowUp' }, 'trace');
    const majuscule = resoudreRaccourci({ key: 'ArrowUp', shiftKey: true }, 'trace');
    expect(nue?.action).toBe('curseur-nord');
    expect(majuscule?.action).toBe('curseur-nord');
    expect(nue).not.toBe(majuscule);
    expect(majuscule?.ecriture).toContain('Maj');
  });

  it('Ctrl+Z, Ctrl+S et les touches hors plan ne sont JAMAIS captés (gestes existants intacts)', () => {
    expect(resoudreRaccourci({ key: 'z', ctrlKey: true }, 'trace')).toBeNull();
    expect(resoudreRaccourci({ key: 's', ctrlKey: true }, 'trace')).toBeNull();
    expect(resoudreRaccourci({ key: 'a' }, 'trace')).toBeNull();
    expect(resoudreRaccourci({ key: 'Tab' }, 'trace')).toBeNull();
    expect(resoudreRaccourci({ key: 'ArrowUp', altKey: true }, 'trace')).toBeNull();
  });

  it('Entrée pose, Ctrl + Entrée termine — la combinaison compte', () => {
    expect(resoudreRaccourci({ key: 'Enter' }, 'trace')?.action).toBe('poser');
    expect(resoudreRaccourci({ key: 'Enter', ctrlKey: true }, 'trace')?.action).toBe('terminer');
    expect(resoudreRaccourci({ key: 'Enter', metaKey: true }, 'trace')?.action).toBe('terminer');
  });

  it('le plan s’efface entièrement dans un champ de saisie', () => {
    expect(estChampDeSaisie({ tagName: 'INPUT' })).toBe(true);
    expect(estChampDeSaisie({ tagName: 'textarea' })).toBe(true);
    expect(estChampDeSaisie({ tagName: 'SELECT' })).toBe(true);
    expect(estChampDeSaisie({ tagName: 'DIV', isContentEditable: true })).toBe(true);
    expect(estChampDeSaisie({ tagName: 'DIV' })).toBe(false);
    expect(estChampDeSaisie(null)).toBe(false);
  });
});

// ————————————————————————————————————————————————————————————————————————
// Le curseur de pose
// ————————————————————————————————————————————————————————————————————————

describe('CALX128 — le curseur de pose : un pas de DESSIN, jamais une distance inventée', () => {
  it('le pas est un nombre de PIXELS converti au zoom courant — aucun mètre inventé', () => {
    const lat = 33.58;
    const zoom = 19;
    // La seule source d'échelle est `metresParPixel` (snap.ts, CALX91) : le pas est son
    // produit par un nombre de pixels, jamais une distance métrique écrite en dur.
    expect(pasCurseurM(lat, zoom)).toBeCloseTo(metresParPixel(lat, zoom) * PAS_CURSEUR_PX, 12);
  });

  it('Maj multiplie le pas par le facteur rapide, et rien d’autre', () => {
    expect(pasCurseurM(33.58, 19, true)).toBeCloseTo(pasCurseurM(33.58, 19) * FACTEUR_PAS_RAPIDE, 9);
  });

  it('un zoom illisible rend un pas NUL — le curseur ne saute pas d’une distance inventée', () => {
    expect(pasCurseurM(33.58, Number.NaN)).toBe(0);
    expect(pasCurseurM(Number.NaN, 19)).toBe(0);
  });

  it('chaque flèche déplace du pas demandé, dans le bon point cardinal', () => {
    const depart: LngLat = [-7.62, 33.58];
    const nord = deplacerCurseur(depart, 'curseur-nord', 10);
    const sud = deplacerCurseur(depart, 'curseur-sud', 10);
    const est = deplacerCurseur(depart, 'curseur-est', 10);
    const ouest = deplacerCurseur(depart, 'curseur-ouest', 10);
    expect(nord[1]).toBeGreaterThan(depart[1]);
    expect(sud[1]).toBeLessThan(depart[1]);
    expect(est[0]).toBeGreaterThan(depart[0]);
    expect(ouest[0]).toBeLessThan(depart[0]);
    for (const p of [nord, sud, est, ouest]) expect(distanceEntreM(depart, p)).toBeCloseTo(10, 6);
  });

  it('un pas nul ou une action qui n’est pas un déplacement rendent le point TEL QUEL', () => {
    const depart: LngLat = [-7.62, 33.58];
    expect(deplacerCurseur(depart, 'curseur-nord', 0)).toBe(depart);
    expect(deplacerCurseur(depart, 'poser', 10)).toBe(depart);
    expect(estDeplacement('curseur-nord')).toBe(true);
    expect(estDeplacement('poser')).toBe(false);
  });
});

// ————————————————————————————————————————————————————————————————————————
// Les annonces
// ————————————————————————————————————————————————————————————————————————

describe('CALX128 — chaque geste est annoncé, chaque refus NOMME sa raison', () => {
  it('la zone d’annonces est créée par le module, en `aria-live` poli', () => {
    document.body.innerHTML = '';
    const a = creerAnnonceur();
    const zone = document.getElementById(ZONE_ANNONCE_ID);
    expect(zone).not.toBeNull();
    expect(zone?.getAttribute('aria-live')).toBe('polite');
    expect(zone?.getAttribute('aria-atomic')).toBe('true');
    expect(a.element()).toBe(zone);
  });

  it('un verdict accepté et un verdict refusé produisent deux natures distinctes', () => {
    expect(annoncePourVerdict({ ok: true, texte: 'Coin 1 placé.' })).toEqual({
      nature: 'accepte',
      texte: 'Coin 1 placé.',
    });
    expect(annoncePourVerdict({ ok: false, motif: 'Rien à annuler.' })).toEqual({
      nature: 'refus',
      texte: 'Rien à annuler.',
    });
  });

  it('l’annonce est publiée dans la zone et mémorisée', () => {
    document.body.innerHTML = '';
    const a = creerAnnonceur();
    a.annoncer({ ok: false, motif: 'Contour déjà fermé.' });
    expect(a.derniere()).toEqual({ nature: 'refus', texte: 'Contour déjà fermé.' });
    expect(document.getElementById(ZONE_ANNONCE_ID)?.textContent).toBe('Contour déjà fermé.');
  });

  it('un geste que le mode n’expose pas est ANNONCÉ, en nommant le mode — jamais un silence', () => {
    document.body.innerHTML = '';
    const clavier = createClavier({ mode: () => 'zone', gestes: () => ({}) });
    const annonce = clavier.frappe({ key: 'Enter' });
    expect(annonce?.nature).toBe('refus');
    expect(annonce?.texte).toContain(LIBELLE_MODE.zone);
    expect(motifGesteIndisponible(PLAN_CLAVIER.find((r) => r.action === 'poser')!, 'zone')).toContain('Zones');
  });

  it('une frappe hors plan, ou dans un champ de saisie, ne produit RIEN (événement intact)', () => {
    document.body.innerHTML = '';
    const geste = vi.fn(() => ({ ok: true as const, texte: 'ok' }));
    const preventDefault = vi.fn();
    const clavier = createClavier({ mode: () => 'trace', gestes: () => ({ poser: geste }) });
    expect(clavier.frappe({ key: 'q', preventDefault })).toBeNull();
    expect(clavier.frappe({ key: 'Enter', target: { tagName: 'INPUT' }, preventDefault })).toBeNull();
    expect(geste).not.toHaveBeenCalled();
    expect(preventDefault).not.toHaveBeenCalled();
  });

  it('une frappe du plan appelle son geste UNE fois et neutralise l’événement', () => {
    document.body.innerHTML = '';
    const geste = vi.fn(() => ({ ok: true as const, texte: 'Coin 1 placé.' }));
    const preventDefault = vi.fn();
    const gestes: GestesAtelier = { poser: geste };
    const clavier = createClavier({ mode: () => 'trace', gestes: () => gestes });
    const annonce = clavier.frappe({ key: 'Enter', preventDefault });
    expect(geste).toHaveBeenCalledTimes(1);
    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(annonce).toEqual({ nature: 'accepte', texte: 'Coin 1 placé.' });
  });
});

// ————————————————————————————————————————————————————————————————————————
// Le tracé au clavier SEUL (l'atelier réel)
// ————————————————————————————————————————————————————————————————————————

/** Carte factice : juste assez pour construire `createMapDraw` et lire zoom/centre. */
function carteFactice() {
  return {
    getSource: () => undefined,
    addSource: vi.fn(),
    removeSource: vi.fn(),
    getLayer: () => undefined,
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
    setLayoutProperty: vi.fn(),
    setPaintProperty: vi.fn(),
    on: vi.fn(),
    getZoom: () => 19,
    getCenter: () => ({ lng: -7.62, lat: 33.58 }),
    getCanvas: () => ({ clientWidth: 800, clientHeight: 600 }),
  };
}

function atelier() {
  document.body.innerHTML = '<div id="rp9-barre"><button type="button" id="rp9-finish"></button></div>';
  const map = carteFactice();
  const ctx = {
    opts: { maptilerKey: 'K', imagery: { pays: 'ma' }, reducedMotion: true },
    vertices: [] as LngLat[],
    obstacles: [],
    areas: [],
    activeAreaId: 'a1',
    closed: false,
    centroid: [-7.62, 33.58] as LngLat,
  } as unknown as Ctx;
  const setStatus = vi.fn();
  const draw = createMapDraw(ctx, { map: map as never, setStatus, updateAreaReadout: vi.fn() });
  const finish = document.getElementById('rp9-finish') as HTMLButtonElement;
  return { draw, ctx, map, setStatus, finish };
}

/** Une frappe, comme le document la livrerait (aucun clic, aucun geste souris). */
function frappe(draw: ReturnType<typeof atelier>['draw'], key: string, mods: Record<string, boolean> = {}) {
  return draw.clavier.frappe({ key, preventDefault: () => {}, ...mods });
}

describe('CALX128 — un contour complet se trace au CLAVIER SEUL', () => {
  it('flèches + Entrée posent quatre coins, puis Ctrl + Entrée ferme le contour', () => {
    const { draw, ctx, finish } = atelier();
    const ferme = vi.fn();
    finish.addEventListener('click', ferme);

    // Coin 1 : au centre de la vue, sans bouger.
    expect(frappe(draw, 'Enter')?.nature).toBe('accepte');
    // Coin 2 : plein est, d'un pas rapide.
    expect(frappe(draw, 'ArrowRight', { shiftKey: true })?.nature).toBe('accepte');
    expect(frappe(draw, 'Enter')?.nature).toBe('accepte');
    // Coin 3 : plein nord.
    expect(frappe(draw, 'ArrowUp', { shiftKey: true })?.nature).toBe('accepte');
    expect(frappe(draw, 'Enter')?.nature).toBe('accepte');
    // Coin 4 : plein ouest.
    expect(frappe(draw, 'ArrowLeft', { shiftKey: true })?.nature).toBe('accepte');
    expect(frappe(draw, 'Enter')?.nature).toBe('accepte');

    expect(ctx.vertices).toHaveLength(4);
    // Le contour tracé est un vrai quadrilatère : quatre points distincts.
    const uniques = new Set(ctx.vertices.map((v) => `${v[0]},${v[1]}`));
    expect(uniques.size).toBe(4);

    const fermeture = frappe(draw, 'Enter', { ctrlKey: true });
    expect(fermeture?.nature).toBe('accepte');
    expect(fermeture?.texte).toContain('4 coins');
    expect(ferme).toHaveBeenCalledTimes(1);
  });

  it('chaque pas de curseur avance de la distance ANNONCÉE, au zoom courant', () => {
    const { draw, ctx } = atelier();
    frappe(draw, 'Enter'); // coin 1
    const depart = [...ctx.vertices[0]] as LngLat;
    const annonce = frappe(draw, 'ArrowRight');
    expect(annonce?.nature).toBe('accepte');
    frappe(draw, 'Enter'); // coin 2
    const attendu = pasCurseurM(depart[1], 19);
    expect(distanceEntreM(depart, ctx.vertices[1])).toBeCloseTo(attendu, 4);
    expect(annonce?.texte).toContain('est');
  });

  it('le curseur SUIT le sommet réellement posé (aimantation comprise)', () => {
    const { draw, ctx } = atelier();
    frappe(draw, 'Enter');
    expect(draw.curseurClavier()).toEqual(ctx.vertices[0]);
  });
});

describe('CALX128 — chaque refus du tracé émet une annonce qui nomme sa raison', () => {
  it('annuler sans aucun coin posé : refus nommé', () => {
    const { draw } = atelier();
    const a = frappe(draw, 'Backspace');
    expect(a?.nature).toBe('refus');
    expect(a?.texte).toContain('aucun coin n’est posé');
  });

  it('fermer avec moins de 3 coins : le refus DIT combien il en faut et combien sont posés', () => {
    const { draw } = atelier();
    frappe(draw, 'Enter');
    const a = frappe(draw, 'Enter', { ctrlKey: true });
    expect(a?.nature).toBe('refus');
    expect(a?.texte).toContain('au moins 3 coins');
    expect(a?.texte).toContain('1 posé(s)');
  });

  it('poser sur un contour DÉJÀ FERMÉ : refus nommé, et rien n’est ajouté', () => {
    const { draw, ctx } = atelier();
    frappe(draw, 'Enter');
    (ctx as unknown as { closed: boolean }).closed = true;
    const a = frappe(draw, 'Enter');
    expect(a?.nature).toBe('refus');
    expect(a?.texte).toContain('déjà fermé');
    expect(ctx.vertices).toHaveLength(1);
  });

  it('un point qui ferait CROISER le tracé (nœud papillon) est refusé, et le refus le dit', () => {
    const { draw, ctx } = atelier();
    // Nœud papillon tracé AU CLAVIER SEUL : coins (0,0) → (E,0) → (0,N) → (E,N), dont les
    // deux diagonales se croisent. Le garde W76 doit refuser le QUATRIÈME coin.
    frappe(draw, 'Enter'); // coin 1, au centre
    frappe(draw, 'ArrowRight', { shiftKey: true });
    frappe(draw, 'Enter'); // coin 2, à l'est
    frappe(draw, 'ArrowLeft', { shiftKey: true });
    frappe(draw, 'ArrowUp', { shiftKey: true });
    frappe(draw, 'Enter'); // coin 3, au nord du coin 1
    expect(ctx.vertices).toHaveLength(3);
    frappe(draw, 'ArrowRight', { shiftKey: true }); // curseur au nord-est : diagonale croisée
    const a = frappe(draw, 'Enter');
    expect(a?.nature).toBe('refus');
    expect(a?.texte).toContain('croiserait');
    expect(ctx.vertices).toHaveLength(3); // rien n'est posé
  });

  it('le déplacement est refusé, en le disant, quand le zoom n’est pas lisible', () => {
    document.body.innerHTML = '<div id="rp9-barre"><button type="button" id="rp9-finish"></button></div>';
    const map = { ...carteFactice(), getZoom: () => Number.NaN };
    const ctx = {
      opts: { maptilerKey: 'K', reducedMotion: true },
      vertices: [] as LngLat[],
      obstacles: [],
      areas: [],
      activeAreaId: 'a1',
      closed: false,
      centroid: [-7.62, 33.58] as LngLat,
    } as unknown as Ctx;
    const draw = createMapDraw(ctx, { map: map as never, setStatus: vi.fn(), updateAreaReadout: vi.fn() });
    const a = draw.clavier.frappe({ key: 'ArrowUp', preventDefault: () => {} });
    expect(a?.nature).toBe('refus');
    expect(a?.texte).toContain('zoom');
  });

  it('Échap relâche le curseur SANS toucher au tracé en cours', () => {
    const { draw, ctx } = atelier();
    frappe(draw, 'Enter');
    frappe(draw, 'ArrowUp');
    const a = frappe(draw, 'Escape');
    expect(a?.nature).toBe('accepte');
    expect(a?.texte).toContain('conservé');
    expect(ctx.vertices).toHaveLength(1);
  });

  it('« ? » annonce la liste des raccourcis disponibles', () => {
    const { draw } = atelier();
    const a = frappe(draw, '?');
    expect(a?.nature).toBe('accepte');
    expect(a?.texte).toContain('raccourcis disponibles');
    expect(draw.aideRaccourcis().length).toBeGreaterThan(0);
  });
});

describe('CALX128 — les gestes souris/tactile ne changent pas', () => {
  it('le clavier ne pose RIEN quand le focus est dans la saisie cotée (CALX90)', () => {
    const { draw, ctx } = atelier();
    frappe(draw, 'Enter');
    const champ = document.getElementById('rp9-cote-longueur');
    expect(champ).not.toBeNull();
    const avant = ctx.vertices.length;
    expect(draw.clavier.frappe({ key: 'Enter', target: champ, preventDefault: () => {} })).toBeNull();
    expect(ctx.vertices).toHaveLength(avant);
  });

  it('`addVertex` (le chemin SOURIS) reste inchangé et n’exige aucun curseur clavier', () => {
    const { draw, ctx } = atelier();
    draw.addVertex([-7.62, 33.58]);
    draw.addVertex([-7.61, 33.58]);
    expect(ctx.vertices).toHaveLength(2);
  });

  it('un mode sans gestes enregistrés le DIT ; l’hôte peut y brancher les siens', () => {
    const { draw } = atelier();
    draw.setModeClavier('mesure');
    expect(draw.modeClavier()).toBe('mesure');
    expect(frappe(draw, 'Enter')?.nature).toBe('refus');
    draw.enregistrerGestesClavier('mesure', { poser: () => ({ ok: true, texte: 'Point 1 posé.' }) });
    expect(frappe(draw, 'Enter')).toEqual({ nature: 'accepte', texte: 'Point 1 posé.' });
  });
});

// ————————————————————————————————————————————————————————————————————————
// L'outil de MESURE : la précision est DITE, jamais tue
// ————————————————————————————————————————————————————————————————————————

describe('CALX128 — une mesure est affichée AVEC sa précision', () => {
  const côté: LngLat[] = [
    [-7.62, 33.58],
    [-7.61, 33.58],
  ];

  it('une distance dit son arrondi au centimètre, et le texte complet le porte', () => {
    const a = formatMesurePrecise({ kind: 'distance', points: côté });
    expect(a.unite).toBe('m');
    expect(a.decimales).toBe(DECIMALES_MESURE.distance);
    expect(a.arrondi).toBe(ARRONDI_MESURE.distance);
    expect(a.texteComplet).toBe(`${a.texte} (${a.arrondi})`);
    expect(a.texteComplet).toContain('centimètre');
    // La valeur BRUTE est conservée : seul l'affichage est arrondi.
    expect(a.valeur).not.toBe(a.valeurAffichee);
    expect(Math.abs(a.valeur - a.valeurAffichee)).toBeLessThan(0.005);
  });

  it('une surface dit son arrondi au décimètre carré, un angle le sien au degré', () => {
    const carre: LngLat[] = [
      [-7.62, 33.58],
      [-7.61, 33.58],
      [-7.61, 33.57],
      [-7.62, 33.57],
    ];
    expect(formatMesurePrecise({ kind: 'area', points: carre }).arrondi).toContain('décimètre carré');
    expect(formatMesurePrecise({ kind: 'area', points: carre }).unite).toBe('m²');
    const angle: LngLat[] = [
      [-7.62, 33.58],
      [-7.61, 33.58],
      [-7.61, 33.57],
    ];
    const a = formatMesurePrecise({ kind: 'angle', points: angle });
    expect(a.arrondi).toContain('degré');
    expect(a.decimales).toBe(0);
  });

  it('la phrase d’une mesure nomme son genre ET son arrondi', () => {
    const phrase = decrireMesure({ kind: 'distance', points: côté });
    expect(phrase.startsWith('Distance :')).toBe(true);
    expect(phrase).toContain('centimètre');
  });

  it('une mesure incomplète est refusée en disant combien de points manquent', () => {
    const motif = motifMesureIncomplete('area', 2);
    expect(motif).toContain(`${POINTS_MINIMUM_MESURE.area} points`);
    expect(motif).toContain('2 posé(s)');
    expect(motif).toContain('il en manque 1');
    expect(motif).toContain('Rien n’est enregistré');
  });
});

describe('CALX128 — les gestes clavier du mode MESURE', () => {
  function sessionMesure(kind: 'distance' | 'area' | 'angle' = 'distance') {
    const ctx = { measurements: [] } as unknown as Ctx;
    const mesure = createMesureUi(ctx);
    let curseur: LngLat | null = [-7.62, 33.58];
    const gestes = gestesMesure(mesure, () => curseur);
    mesure.begin(kind);
    return { mesure, gestes, ctx, bouger: (p: LngLat | null) => { curseur = p; } };
  }

  it('Entrée pose un point de mesure et annonce la valeur avec sa précision', () => {
    const { gestes, bouger } = sessionMesure();
    expect(gestes.poser()).toEqual({ ok: true, texte: 'Point 1 posé.' });
    bouger([-7.61, 33.58]);
    const second = gestes.poser();
    expect(second.ok).toBe(true);
    if (!second.ok) throw new Error('pose attendue');
    expect(second.texte).toContain('Point 2 posé.');
    expect(second.texte).toContain('centimètre'); // la précision est DITE
  });

  it('poser hors session est refusé en le disant', () => {
    const ctx = { measurements: [] } as unknown as Ctx;
    const gestes = gestesMesure(createMesureUi(ctx), () => [-7.62, 33.58]);
    const r = gestes.poser();
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.motif).toContain('Aucune mesure en cours');
  });

  it('poser sans curseur positionné est refusé en le disant', () => {
    const { gestes, bouger } = sessionMesure();
    bouger(null);
    const r = gestes.poser();
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.motif).toContain('curseur de pose');
  });

  it('terminer une mesure incomplète la GARDE ouverte et nomme ce qui manque', () => {
    const { gestes, mesure } = sessionMesure('area');
    gestes.poser();
    const r = gestes.terminer();
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.motif).toContain('3 points');
    expect(mesure.isActive()).toBe(true); // rien n'est perdu
    expect(mesure.list()).toHaveLength(0); // rien n'est enregistré
  });

  it('terminer une mesure valide l’enregistre et l’annonce avec sa précision', () => {
    const { gestes, mesure, bouger } = sessionMesure();
    gestes.poser();
    bouger([-7.61, 33.58]);
    gestes.poser();
    const r = gestes.terminer();
    expect(r.ok).toBe(true);
    if (!r.ok) throw new Error('pose attendue');
    expect(r.texte).toContain('Mesure enregistrée');
    expect(r.texte).toContain('Distance :');
    expect(mesure.list()).toHaveLength(1);
  });

  it('un angle refuse un 4ᵉ point en le disant, plutôt que de l’ignorer', () => {
    const { gestes, bouger } = sessionMesure('angle');
    gestes.poser();
    bouger([-7.61, 33.58]);
    gestes.poser();
    bouger([-7.61, 33.57]);
    gestes.poser();
    bouger([-7.6, 33.56]);
    const r = gestes.poser();
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error('refus attendu');
    expect(r.motif).toContain('3 points');
  });

  it('annuler le dernier point, puis Échap : rien n’est enregistré', () => {
    const { gestes, mesure } = sessionMesure();
    expect(gestes['annuler-dernier']().ok).toBe(false); // rien de posé encore
    gestes.poser();
    const annule = gestes['annuler-dernier']();
    expect(annule.ok).toBe(true);
    const sortie = gestes.sortir();
    expect(sortie.ok).toBe(true);
    if (!sortie.ok) throw new Error('sortie attendue');
    expect(sortie.texte).toContain('abandonnée');
    expect(mesure.isActive()).toBe(false);
    expect(mesure.list()).toHaveLength(0);
  });
});
