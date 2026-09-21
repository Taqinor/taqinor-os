/**
 * CALX108 câblage — CALER LE FOND À DEUX POINTS : L'INTERFACE QUI MANQUAIT.
 *
 * LE CONSTAT. `mapDraw.ts` porte déjà le mode « Caler le fond » : la pastille,
 * la boîte `rp9-fond-calage`, les champs « Distance réelle » / « Source », le
 * bouton « Caler le fond », et l'API `pointCalageFond(pointImage, ancre)` qui
 * apparie un point de l'IMAGE à un point de la CARTE. Mais l'hôte ne pouvait
 * produire AUCUN `pointImage` : l'image du fond n'était affichée nulle part
 * cliquable, et le repère de l'image (ses pixels naturels) n'existait dans
 * aucune surface. Le mode s'ouvrait donc sur une séquence impossible à finir.
 *
 * CE MODULE EST AUTONOME (patron `obstaclesUi.ts` / `zones.ts`) : il crée
 * LUI-MÊME sa vignette quand la page hôte ne la fournit pas, aucune page n'a
 * à être modifiée. Il ne connaît ni MapLibre, ni Three, ni Django : la pose
 * d'une paire lui est INJECTÉE (`deps.poserPaire` = `mapDraw.pointCalageFond`).
 *
 * LA SÉQUENCE, ET ELLE EST STRICTE :
 *   clic sur l'IMAGE (point A) → clic sur la CARTE (ancre A)
 *   → clic sur l'IMAGE (point B) → clic sur la CARTE (ancre B)
 *   → distance réelle SAISIE → « Caler le fond ».
 * Chaque étape est ANNONCÉE dans la zone `aria-live` de l'atelier
 * (`clavier.ts::creerAnnonceur`), acceptée comme refusée, et un refus NOMME sa
 * raison — jamais un clic avalé en silence.
 *
 * LES COORDONNÉES SONT EN PIXELS NATURELS DE L'IMAGE. La vignette est affichée
 * RÉDUITE (elle doit tenir dans la barre d'outils) : le facteur de réduction
 * est appliqué à chaque clic, sans quoi `caleDeuxPoints` recevrait des
 * distances image trois à huit fois trop petites et rendrait une échelle
 * fausse — qui aurait l'air juste. La taille naturelle vient du document
 * (`RessourceFond.tailleImage`, publiée par `GET …/plan-importe/`, CALX107) :
 * sans elle, AUCUN point n'est posé et le motif nomme `tailleImage`.
 *
 * AUCUNE ÉCHELLE N'EST DEVINÉE : ce module ne fait que produire les deux
 * points ; l'échelle vient de la distance réelle SAISIE (`underlay.ts`).
 */
import { type LngLat } from '../../lib/roof';
import { type TailleImage } from './underlay';
import { creerAnnonceur, type Annonceur, type VerdictGeste } from './clavier';

// ————————————————————————————————————————————————————————————————————————
// La séquence, PURE
// ————————————————————————————————————————————————————————————————————————

/** Où en est le calage. `ferme` = le mode n'est pas ouvert. */
export type EtapeCalage = 'ferme' | 'image-a' | 'carte-a' | 'image-b' | 'carte-b' | 'distance';

/**
 * CALX108 — l'étape courante, DÉDUITE de l'état (jamais tenue à part) : un
 * compteur d'étapes qui vit à côté des paires finit toujours par mentir.
 */
export function etapeCalage(etat: {
  ouvert: boolean;
  paires: number;
  pointEnAttente: boolean;
}): EtapeCalage {
  if (!etat.ouvert) return 'ferme';
  if (etat.pointEnAttente) return etat.paires === 0 ? 'carte-a' : 'carte-b';
  if (etat.paires <= 0) return 'image-a';
  if (etat.paires === 1) return 'image-b';
  return 'distance';
}

/** Ce que l'atelier DIT à chaque étape — le texte exact annoncé et affiché. */
export const LIBELLE_ETAPE: Readonly<Record<EtapeCalage, string>> = {
  ferme: 'Le calage du fond est fermé.',
  'image-a': 'Cliquez le PREMIER point repérable sur le plan (la vignette ci-contre).',
  'carte-a': 'Premier point du plan posé. Cliquez maintenant le MÊME point sur la carte.',
  'image-b': 'Premier repère complet. Cliquez le SECOND point repérable sur le plan.',
  'carte-b': 'Second point du plan posé. Cliquez maintenant le MÊME point sur la carte.',
  distance:
    'Les deux repères sont posés. Saisissez la distance réelle qui les sépare, et d’où elle vient, puis « Caler le fond ».',
};

// ————————————————————————————————————————————————————————————————————————
// La vignette et son facteur de réduction, PURS
// ————————————————————————————————————————————————————————————————————————

/**
 * Largeur d'affichage MAXIMALE de la vignette du fond, en pixels écran.
 * CONVENTION DE DESSIN (pas une dimension du site) : la vignette vit dans la
 * barre d'outils de l'atelier, à côté des champs de calage. Elle n'AGRANDIT
 * jamais une image plus petite — agrandir n'ajoute aucune précision de
 * pointage, et ferait croire à une finesse qui n'existe pas.
 */
export const LARGEUR_VIGNETTE_PX = 320;

/** La largeur d'AFFICHAGE de la vignette, ou 0 quand la taille est inconnue. */
export function largeurVignette(taille: TailleImage | null | undefined): number {
  const largeur = taille?.largeur;
  if (typeof largeur !== 'number' || !Number.isFinite(largeur) || largeur <= 0) return 0;
  return Math.min(LARGEUR_VIGNETTE_PX, largeur);
}

/**
 * CALX108 — combien de pixels NATURELS vaut un pixel AFFICHÉ. `0` quand l'une
 * des deux largeurs est inconnue : l'appelant refuse alors le clic plutôt que
 * de poser un point au facteur 1 (qui serait faux dès que la vignette réduit).
 */
export function facteurReduction(
  taille: TailleImage | null | undefined,
  largeurAffichee: number,
): number {
  const largeur = taille?.largeur;
  if (typeof largeur !== 'number' || !Number.isFinite(largeur) || largeur <= 0) return 0;
  if (!Number.isFinite(largeurAffichee) || largeurAffichee <= 0) return 0;
  return largeur / largeurAffichee;
}

/**
 * CALX108 — le point cliqué, converti en PIXELS NATURELS de l'image. `null`
 * quand le clic tombe hors de l'image ou que le facteur est inconnu : un point
 * hors cadre n'a pas de correspondant sur la carte.
 *
 * Le résultat est ARRONDI au pixel : un pixel est l'unité de l'image, et une
 * fraction de pixel afficherait une finesse que le pointage n'a pas.
 */
export function pointNaturel(
  x: number,
  y: number,
  facteur: number,
  taille: TailleImage | null | undefined,
): [number, number] | null {
  if (!(facteur > 0) || !taille) return null;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const nx = Math.round(x * facteur);
  const ny = Math.round(y * facteur);
  if (nx < 0 || ny < 0 || nx > taille.largeur || ny > taille.hauteur) return null;
  return [nx, ny];
}

// ————————————————————————————————————————————————————————————————————————
// Les refus — chacun NOMME ce qui bloque
// ————————————————————————————————————————————————————————————————————————

export const REFUS_MODE_FERME =
  'Le calage du fond n’est pas ouvert : appuyez d’abord sur « Caler le fond ».';

export const REFUS_POINT_EN_ATTENTE =
  'Un point du plan attend encore son point sur la carte : cliquez la carte avant de revenir sur le plan.';

export const REFUS_TAILLE_INCONNUE =
  'Calage impossible : les dimensions du plan (tailleImage) ne sont pas connues, donc un clic sur la vignette ne peut pas être ramené aux pixels du fichier.';

export const REFUS_HORS_IMAGE =
  'Ce clic tombe hors du plan : visez un point repérable À L’INTÉRIEUR de la vignette.';

export const REFUS_SANS_POINT_IMAGE =
  'Cliquez d’abord le point sur le PLAN (la vignette), puis son correspondant sur la carte.';

export const REFUS_SANS_FOND =
  'Aucun plan de fond n’est chargé : le calage à deux points ne concerne que les plans importés.';

// ————————————————————————————————————————————————————————————————————————
// Le module
// ————————————————————————————————————————————————————————————————————————

/** Le fichier du fond, tel que la page hôte l'a fourni au constructeur. */
export interface FondAffichable {
  url?: string | null;
  tailleImage?: TailleImage | null;
}

export interface CalageFondDeps {
  /** Où la vignette s'insère — la boîte `rp9-fond-calage` de `mapDraw.ts`. */
  hote: () => HTMLElement | null;
  /** Le fichier du fond courant (URL servie + pixels naturels), ou `null`. */
  fond: () => FondAffichable | null;
  /** Vrai tant que le mode « Caler le fond » est ouvert (`modeCalageFond`). */
  modeOuvert: () => boolean;
  /** Apparie un point image à une ancre carte — `mapDraw.pointCalageFond`.
   *  Rend le NOMBRE de paires posées. */
  poserPaire: (pointImage: [number, number], ancre: LngLat) => number;
  /** Où publier les annonces. Créé par le module si absent. */
  annonceur?: Annonceur;
}

export interface CalageFondUi {
  /** (Re)pose la vignette pour le fond courant, et annonce l'étape. */
  rafraichir: () => void;
  /** Un clic sur la vignette, en coordonnées AFFICHÉES (pixels de la vignette). */
  clicImage: (x: number, y: number) => VerdictGeste;
  /** Un clic sur la CARTE. Rend `true` quand le clic est CONSOMMÉ par le calage
   *  (le dispatcher sort alors sans tracer ni sélectionner). */
  clicCarte: (ancre: LngLat) => boolean;
  /** L'étape courante. */
  etape: () => EtapeCalage;
  /** Le point du plan qui attend son ancre, en PIXELS NATURELS, ou `null`. */
  pointEnAttente: () => [number, number] | null;
  /** La vignette, quand le DOM a permis de la créer. */
  vignette: () => HTMLImageElement | null;
  annonceur: Annonceur;
}

/** Identifiants DOM de la vignette — stables, pour les tests et le CSS. */
export const VIGNETTE_ID = 'rp9-fond-vignette';
export const VIGNETTE_CADRE_ID = 'rp9-fond-vignette-cadre';
export const VIGNETTE_ETAPE_ID = 'rp9-fond-vignette-etape';

/**
 * CALX108 — l'interface de calage à deux points. Elle ne décide d'aucune
 * géométrie : elle produit les deux points, dans le bon repère, dans le bon
 * ordre, et dit à voix haute où l'on en est.
 */
export function createCalageFondUi(deps: CalageFondDeps): CalageFondUi {
  const annonceur = deps.annonceur ?? creerAnnonceur(deps.hote() ?? null);
  let attente: [number, number] | null = null;
  let paires = 0;
  let cadre: HTMLElement | null = null;
  let image: HTMLImageElement | null = null;
  let legende: HTMLElement | null = null;

  function creerDom(): void {
    if (image) return;
    const hote = deps.hote();
    if (!hote || typeof document === 'undefined' || typeof document.createElement !== 'function') {
      return;
    }
    const existante = document.getElementById(VIGNETTE_ID);
    if (existante instanceof HTMLImageElement) {
      image = existante;
      cadre = document.getElementById(VIGNETTE_CADRE_ID);
      legende = document.getElementById(VIGNETTE_ETAPE_ID);
      return;
    }
    cadre = document.createElement('figure');
    cadre.id = VIGNETTE_CADRE_ID;
    cadre.className = 'rp9-fond-vignette-cadre inline-flex flex-col gap-1';
    cadre.hidden = true;
    image = document.createElement('img');
    image.id = VIGNETTE_ID;
    image.className = 'rp9-fond-vignette cursor-crosshair';
    image.alt = 'Plan de fond à caler — cliquez un point repérable du plan.';
    legende = document.createElement('figcaption');
    legende.id = VIGNETTE_ETAPE_ID;
    legende.className = 'text-xs opacity-70';
    cadre.appendChild(image);
    cadre.appendChild(legende);
    hote.appendChild(cadre);
    image.addEventListener('click', (e) => {
      const ev = e as MouseEvent;
      const cible = ev.currentTarget as HTMLElement | null;
      const rect = cible?.getBoundingClientRect?.();
      // `offsetX` quand le navigateur le donne (il est déjà relatif à l'image) ;
      // sinon la position dans le rectangle de l'image. Aucun repli inventé.
      const x = Number.isFinite(ev.offsetX) ? ev.offsetX : ev.clientX - (rect?.left ?? 0);
      const y = Number.isFinite(ev.offsetY) ? ev.offsetY : ev.clientY - (rect?.top ?? 0);
      clicImage(x, y);
    });
  }

  function tailleCourante(): TailleImage | null {
    const taille = deps.fond()?.tailleImage;
    return taille && Number.isFinite(taille.largeur) && Number.isFinite(taille.hauteur)
      ? taille
      : null;
  }

  function etape(): EtapeCalage {
    return etapeCalage({
      ouvert: Boolean(deps.modeOuvert()),
      paires,
      pointEnAttente: attente != null,
    });
  }

  function syncLegende(): void {
    if (legende) legende.textContent = LIBELLE_ETAPE[etape()];
  }

  function rafraichir(): void {
    creerDom();
    const fond = deps.fond();
    const url = typeof fond?.url === 'string' ? fond.url.trim() : '';
    const ouvert = Boolean(deps.modeOuvert());
    if (!ouvert) {
      // Sortir du mode remet la séquence à zéro : deux points d'une session
      // précédente n'ont aucune raison de valoir pour la suivante.
      attente = null;
      paires = 0;
    }
    if (cadre) cadre.hidden = !ouvert || !url;
    if (image && url && image.getAttribute('src') !== url) image.setAttribute('src', url);
    const largeur = largeurVignette(tailleCourante());
    if (image && largeur > 0) image.width = largeur;
    syncLegende();
    if (ouvert) {
      annonceur.annoncer(
        url
          ? { ok: true, texte: LIBELLE_ETAPE[etape()] }
          : { ok: false, motif: REFUS_SANS_FOND },
      );
    }
  }

  function clicImage(x: number, y: number): VerdictGeste {
    if (!deps.modeOuvert()) {
      annonceur.annoncer({ ok: false, motif: REFUS_MODE_FERME });
      return { ok: false, motif: REFUS_MODE_FERME };
    }
    if (attente != null) {
      annonceur.annoncer({ ok: false, motif: REFUS_POINT_EN_ATTENTE });
      return { ok: false, motif: REFUS_POINT_EN_ATTENTE };
    }
    const taille = tailleCourante();
    const largeurAffichee = image?.width || largeurVignette(taille);
    const facteur = facteurReduction(taille, largeurAffichee);
    if (!(facteur > 0)) {
      annonceur.annoncer({ ok: false, motif: REFUS_TAILLE_INCONNUE });
      return { ok: false, motif: REFUS_TAILLE_INCONNUE };
    }
    const point = pointNaturel(x, y, facteur, taille);
    if (!point) {
      annonceur.annoncer({ ok: false, motif: REFUS_HORS_IMAGE });
      return { ok: false, motif: REFUS_HORS_IMAGE };
    }
    attente = point;
    syncLegende();
    const verdict: VerdictGeste = {
      ok: true,
      texte: `Point du plan posé à ${point[0]} × ${point[1]} px. ${LIBELLE_ETAPE[etape()]}`,
    };
    annonceur.annoncer(verdict);
    return verdict;
  }

  function clicCarte(ancre: LngLat): boolean {
    if (!deps.modeOuvert()) return false;
    if (attente == null) {
      annonceur.annoncer({ ok: false, motif: REFUS_SANS_POINT_IMAGE });
      return true; // le clic est CONSOMMÉ : il ne doit ni tracer ni sélectionner
    }
    const point = attente;
    attente = null;
    paires = deps.poserPaire(point, ancre);
    syncLegende();
    annonceur.annoncer({
      ok: true,
      texte: `Repère ${paires} posé sur la carte. ${LIBELLE_ETAPE[etape()]}`,
    });
    return true;
  }

  creerDom();
  syncLegende();

  return {
    rafraichir,
    clicImage,
    clicCarte,
    etape,
    pointEnAttente: () => (attente ? [attente[0], attente[1]] : null),
    vignette: () => image,
    annonceur,
  };
}
