// @vitest-environment jsdom
//
/**
 * CALX108 câblage — la séquence de calage à deux points, et son repère.
 *
 * Ce que ces tests tiennent :
 *  - les clics sur la VIGNETTE sont ramenés aux PIXELS NATURELS du fichier
 *    (facteur de réduction appliqué) — c'est le point qui, oublié, donnerait
 *    une échelle fausse mais d'apparence juste ;
 *  - la séquence est stricte (image → carte → image → carte → distance) et
 *    chaque étape est ANNONCÉE ;
 *  - chaque refus NOMME sa raison : mode fermé, point déjà en attente, taille
 *    inconnue, clic hors image, clic carte avant clic plan ;
 *  - le clic carte est CONSOMMÉ tant que le mode est ouvert (le dispatcher
 *    sort avant de tracer ou de sélectionner) ;
 *  - aucune échelle n'est déduite du fichier : ce module ne produit que des
 *    points.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import process from 'node:process';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  LARGEUR_VIGNETTE_PX,
  LIBELLE_ETAPE,
  MODIFICATEUR_FOND,
  REFUS_HORS_IMAGE,
  REFUS_MODE_FERME,
  REFUS_POINT_EN_ATTENTE,
  REFUS_SANS_POINT_IMAGE,
  REFUS_TAILLE_INCONNUE,
  VIGNETTE_ID,
  createCalageFondUi,
  deltaMetresFond,
  etapeCalage,
  facteurReduction,
  gesteFond,
  largeurVignette,
  pointNaturel,
  rotationMolette,
  surLeFond,
} from './calageFondUi';
import {
  GESTES_SOURIS,
  PLAN_CLAVIER,
  ZONE_ANNONCE_ID,
  aideGestesSouris,
  resoudreRaccourci,
} from './clavier';

const TAILLE = { largeur: 2480, hauteur: 1754 };
const URL_PLAN = 'https://minio.example/plan.png?signature';
const SOURCE_ENTREE = readFileSync(
  resolve(process.cwd(), 'src/scripts/roof-tool-pro11.ts'), 'utf8');
const SOURCE_MAPDRAW = readFileSync(
  resolve(process.cwd(), 'src/scripts/roofPro11/mapDraw.ts'), 'utf8');

describe('CALX108 câblage — l’entrée route le clic carte vers le calage', () => {
  it('le dispatcher sort AVANT le tracé et la sélection', () => {
    expect(SOURCE_ENTREE).toContain(
      'if (calageFondUi.clicCarte(lngLat)) return; // CALX108 câblage');
  });

  it('la ressource du fond est mémorisée pour la vignette', () => {
    expect(SOURCE_ENTREE).toContain(
      'ressourceFondCourante = ressource ?? {}; // CALX108 câblage');
  });

  it('le glissé et la molette appellent `ajusterFond`', () => {
    expect(SOURCE_ENTREE).toContain(
      'mapDraw.ajusterFond({ estM: delta.estM, nordM: delta.nordM }); // CALX108 câblage');
    expect(SOURCE_ENTREE).toContain(
      'mapDraw.ajusterFond({ rotationDeg }); // CALX108 câblage');
  });
});

describe('CALX108 — ajuster le fond : un geste RÉSERVÉ (Alt)', () => {
  /** Un carré d'un dixième de degré autour de Casablanca — repère d'ESSAI. */
  const COINS: Array<[number, number]> = [
    [-7.65, 33.60], [-7.55, 33.60], [-7.55, 33.55], [-7.65, 33.55],
  ];
  const DEDANS: [number, number] = [-7.60, 33.58];
  const DEHORS: [number, number] = [-7.40, 33.58];
  const REPOS = {
    altEnfoncee: true,
    surFond: true,
    modeObstacle: false,
    modeDisposition: false,
    modeCalage: false,
  };

  it('Alt + appui SUR le fond déplace le fond', () => {
    expect(gesteFond(REPOS)).toBe('deplacer');
  });

  it('SANS Alt, aucun geste de fond n’existe : le pan garde la main', () => {
    expect(gesteFond({ ...REPOS, altEnfoncee: false })).toBe('aucun');
    expect(rotationMolette(120, { ...REPOS, altEnfoncee: false })).toBe(0);
  });

  it('hors du fond, ou dans un mode qui possède déjà le glissé, aucun geste', () => {
    expect(gesteFond({ ...REPOS, surFond: false })).toBe('aucun');
    expect(gesteFond({ ...REPOS, modeObstacle: true })).toBe('aucun');
    expect(gesteFond({ ...REPOS, modeDisposition: true })).toBe('aucun');
    // Un calage en cours appartient à la séquence à deux points, pas à l'ajustement.
    expect(gesteFond({ ...REPOS, modeCalage: true })).toBe('aucun');
  });

  it('la molette fait tourner d’UN degré par cran, dans le sens du geste', () => {
    expect(rotationMolette(120, REPOS)).toBe(1);
    expect(rotationMolette(-120, REPOS)).toBe(-1);
    expect(rotationMolette(0, REPOS)).toBe(0);
    expect(rotationMolette(Number.NaN, REPOS)).toBe(0);
  });

  it('le glissé se mesure en mètres est/nord, dans le plan tangent', () => {
    const delta = deltaMetresFond([-7.6, 33.58], [-7.6, 33.581]);
    expect(delta.estM).toBeCloseTo(0, 6);
    expect(delta.nordM).toBeGreaterThan(100); // ~111 m par millième de degré
    const versEst = deltaMetresFond([-7.6, 33.58], [-7.599, 33.58]);
    expect(versEst.nordM).toBeCloseTo(0, 6);
    expect(versEst.estM).toBeGreaterThan(0);
  });

  it('« sur le fond » se décide sur les QUATRE coins du calage', () => {
    expect(surLeFond(DEDANS, COINS)).toBe(true);
    expect(surLeFond(DEHORS, COINS)).toBe(false);
    // Sans coins connus, le geste réservé ne s'applique pas.
    expect(surLeFond(DEDANS, null)).toBe(false);
    expect(surLeFond(DEDANS, [])).toBe(false);
  });
});

describe('CALX128 — la convention de dessin est NOMMÉE dans l’aide', () => {
  it('les deux gestes du fond sont dans la table, avec leur écriture', () => {
    const ecritures = GESTES_SOURIS.map((g) => g.ecriture);
    expect(ecritures).toContain(`${MODIFICATEUR_FOND} + glissé sur le fond`);
    expect(ecritures).toContain(`${MODIFICATEUR_FOND} + molette sur le fond`);
  });

  it('l’aide affichable est DÉRIVÉE de la table, jamais recopiée', () => {
    const aide = aideGestesSouris();
    expect(aide).toHaveLength(GESTES_SOURIS.length);
    aide.forEach((ligne, i) => {
      expect(ligne.touches).toBe(GESTES_SOURIS[i].ecriture);
      expect(ligne.libelle).toBe(GESTES_SOURIS[i].libelle);
    });
  });

  it('ces gestes restent HORS du plan clavier : Alt seule ne vole aucune frappe', () => {
    for (const raccourci of PLAN_CLAVIER) {
      expect(raccourci.touches).not.toContain('Alt');
    }
    expect(resoudreRaccourci({ key: 'Alt', altKey: true }, 'trace')).toBeNull();
  });

  it('le bandeau d’aide de l’atelier sert les deux tables', () => {
    expect(SOURCE_MAPDRAW).toContain(
      'return aideClavier(modeClavierCourant).concat(aideGestesSouris(modeClavierCourant));');
  });
});

describe('CALX108 — l’étape est DÉDUITE de l’état', () => {
  it('parcourt la séquence dans l’ordre', () => {
    expect(etapeCalage({ ouvert: false, paires: 0, pointEnAttente: false })).toBe('ferme');
    expect(etapeCalage({ ouvert: true, paires: 0, pointEnAttente: false })).toBe('image-a');
    expect(etapeCalage({ ouvert: true, paires: 0, pointEnAttente: true })).toBe('carte-a');
    expect(etapeCalage({ ouvert: true, paires: 1, pointEnAttente: false })).toBe('image-b');
    expect(etapeCalage({ ouvert: true, paires: 1, pointEnAttente: true })).toBe('carte-b');
    expect(etapeCalage({ ouvert: true, paires: 2, pointEnAttente: false })).toBe('distance');
  });

  it('chaque étape porte un libellé français non vide', () => {
    for (const texte of Object.values(LIBELLE_ETAPE)) expect(texte.trim().length).toBeGreaterThan(0);
  });
});

describe('CALX108 — le repère de l’image : pixels NATURELS', () => {
  it('la vignette réduit, elle n’agrandit jamais', () => {
    expect(largeurVignette(TAILLE)).toBe(LARGEUR_VIGNETTE_PX);
    expect(largeurVignette({ largeur: 120, hauteur: 80 })).toBe(120);
    expect(largeurVignette(null)).toBe(0);
    expect(largeurVignette({ largeur: 0, hauteur: 10 })).toBe(0);
  });

  it('le facteur de réduction est la largeur naturelle sur la largeur affichée', () => {
    expect(facteurReduction({ largeur: 1600, hauteur: 900 }, 400)).toBe(4);
    expect(facteurReduction({ largeur: 320, hauteur: 200 }, 320)).toBe(1);
    // Taille ou largeur inconnue ⇒ 0 : l'appelant refuse, il ne suppose pas 1.
    expect(facteurReduction(null, 320)).toBe(0);
    expect(facteurReduction({ largeur: 1600, hauteur: 900 }, 0)).toBe(0);
  });

  it('un clic affiché est ramené aux pixels naturels, arrondi au pixel', () => {
    expect(pointNaturel(100, 50, 4, { largeur: 1600, hauteur: 900 })).toEqual([400, 200]);
    expect(pointNaturel(10.4, 10.6, 2, { largeur: 100, hauteur: 100 })).toEqual([21, 21]);
  });

  it('un clic hors image n’est PAS un point', () => {
    expect(pointNaturel(500, 10, 4, { largeur: 1600, hauteur: 900 })).toBeNull();
    expect(pointNaturel(-1, 10, 4, { largeur: 1600, hauteur: 900 })).toBeNull();
    expect(pointNaturel(10, 10, 0, { largeur: 1600, hauteur: 900 })).toBeNull();
  });
});

describe('CALX108 — la séquence complète, annoncée', () => {
  let hote: HTMLElement;
  let fond: { url: string | null; tailleImage: typeof TAILLE | null };
  let ouvert: boolean;
  let poserPaire: ReturnType<typeof vi.fn>;
  let paires: Array<{ image: [number, number]; ancre: [number, number] }>;

  function monter() {
    return createCalageFondUi({
      hote: () => hote,
      fond: () => fond,
      modeOuvert: () => ouvert,
      poserPaire: (image, ancre) => poserPaire(image, ancre),
    });
  }

  beforeEach(() => {
    document.body.innerHTML = '';
    hote = document.createElement('span');
    hote.id = 'rp9-fond-calage';
    document.body.appendChild(hote);
    fond = { url: URL_PLAN, tailleImage: TAILLE };
    ouvert = true;
    paires = [];
    poserPaire = vi.fn((image: [number, number], ancre: [number, number]) => {
      paires.push({ image, ancre });
      return paires.length;
    });
  });

  it('crée LUI-MÊME sa vignette : aucune page hôte n’est modifiée', () => {
    const ui = monter();
    ui.rafraichir();

    const img = document.getElementById(VIGNETTE_ID) as HTMLImageElement | null;
    expect(img).toBe(ui.vignette());
    expect(img?.getAttribute('src')).toBe(URL_PLAN);
    expect(img?.width).toBe(LARGEUR_VIGNETTE_PX);
    // La zone d'annonces de l'atelier existe (aria-live, CALX128).
    expect(document.getElementById(ZONE_ANNONCE_ID)?.getAttribute('aria-live')).toBe('polite');
  });

  it('image → carte → image → carte : les paires partent en pixels NATURELS', () => {
    const ui = monter();
    ui.rafraichir();

    expect(ui.etape()).toBe('image-a');
    expect(ui.clicImage(80, 40).ok).toBe(true);
    // 2480 / 320 = 7,75 px naturels par px affiché.
    expect(ui.pointEnAttente()).toEqual([620, 310]);
    expect(ui.etape()).toBe('carte-a');

    expect(ui.clicCarte([-7.6, 33.59])).toBe(true);
    expect(poserPaire).toHaveBeenCalledWith([620, 310], [-7.6, 33.59]);
    expect(ui.pointEnAttente()).toBeNull();
    expect(ui.etape()).toBe('image-b');

    ui.clicImage(160, 40);
    ui.clicCarte([-7.59, 33.59]);
    expect(paires).toHaveLength(2);
    expect(paires[1].image).toEqual([1240, 310]);
    expect(ui.etape()).toBe('distance');
    // La dernière annonce renvoie vers la distance réelle SAISIE.
    expect(ui.annonceur.derniere()?.texte).toContain('distance réelle');
  });

  it('chaque étape est annoncée dans la zone aria-live', () => {
    const ui = monter();
    ui.rafraichir();
    const zone = document.getElementById(ZONE_ANNONCE_ID);

    ui.clicImage(80, 40);
    expect(zone?.textContent).toContain(LIBELLE_ETAPE['carte-a']);
    ui.clicCarte([-7.6, 33.59]);
    expect(zone?.textContent).toContain(LIBELLE_ETAPE['image-b']);
  });

  it('refus NOMMÉS : mode fermé, point en attente, hors image, carte sans plan', () => {
    const ui = monter();
    ui.rafraichir();

    ui.clicImage(80, 40);
    expect(ui.clicImage(90, 40)).toEqual({ ok: false, motif: REFUS_POINT_EN_ATTENTE });
    expect(ui.annonceur.derniere()?.nature).toBe('refus');

    ui.clicCarte([-7.6, 33.59]);
    expect(ui.clicImage(9999, 40)).toEqual({ ok: false, motif: REFUS_HORS_IMAGE });

    // Un clic carte AVANT le clic plan est consommé, et il DIT pourquoi.
    expect(ui.clicCarte([-7.6, 33.59])).toBe(true);
    expect(ui.annonceur.derniere()?.texte).toBe(REFUS_SANS_POINT_IMAGE);
    expect(poserPaire).toHaveBeenCalledTimes(1);

    ouvert = false;
    expect(ui.clicImage(80, 40)).toEqual({ ok: false, motif: REFUS_MODE_FERME });
    expect(ui.clicCarte([-7.6, 33.59])).toBe(false); // le clic repart au tracé
  });

  it('sans dimensions publiées, AUCUN point n’est posé et le motif nomme `tailleImage`', () => {
    fond = { url: URL_PLAN, tailleImage: null };
    const ui = monter();
    ui.rafraichir();

    expect(ui.clicImage(80, 40)).toEqual({ ok: false, motif: REFUS_TAILLE_INCONNUE });
    expect(REFUS_TAILLE_INCONNUE).toContain('tailleImage');
    expect(ui.pointEnAttente()).toBeNull();
    expect(poserPaire).not.toHaveBeenCalled();
  });

  it('sortir du mode remet la séquence à zéro (aucun point d’une session précédente)', () => {
    const ui = monter();
    ui.rafraichir();
    ui.clicImage(80, 40);
    ui.clicCarte([-7.6, 33.59]);

    ouvert = false;
    ui.rafraichir();
    ouvert = true;
    ui.rafraichir();

    expect(ui.etape()).toBe('image-a');
    expect(ui.pointEnAttente()).toBeNull();
  });

  it('un clic RÉEL sur la vignette passe par le même chemin', () => {
    const ui = monter();
    ui.rafraichir();
    const img = ui.vignette();
    expect(img).not.toBeNull();

    const evenement = new MouseEvent('click', { bubbles: true });
    Object.defineProperty(evenement, 'offsetX', { value: 80 });
    Object.defineProperty(evenement, 'offsetY', { value: 40 });
    img?.dispatchEvent(evenement);

    expect(ui.pointEnAttente()).toEqual([620, 310]);
  });
});
