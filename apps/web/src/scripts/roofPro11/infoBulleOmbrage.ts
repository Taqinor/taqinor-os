/**
 * CALX122 câblage — L'OMBRAGE D'UN MODULE, AU SURVOL.
 *
 * `shadingUi.moduleShadeTooltip(cellIndex)` rend depuis CALX122 un texte prêt à afficher
 * pour UN module (heures masquées sur les 288 de la matrice + premier mois concerné), et
 * son en-tête dit lui-même que le câblage au survol 3D « reste un crochet attendu ». Il
 * n'existait en effet AUCUNE info-bulle dans l'atelier : le texte n'avait nulle part où
 * s'afficher.
 *
 * Ce module est le mécanisme MINIMAL qui manquait, sur le patron de `obstaclesUi.ts` : il
 * crée lui-même son `div` quand la page hôte n'en fournit pas. Il ne mesure RIEN et ne
 * calcule RIEN — le texte lui est donné. Quand l'ombrage n'est pas mesuré, c'est
 * `moduleShadeTooltip` qui le DIT (« non renseigné — aucune obstruction n'a été saisie »)
 * et l'info-bulle affiche cette phrase : jamais un chiffre à la place d'une mesure absente.
 */

/** Décalage (px) de l'info-bulle par rapport au curseur. CONVENTION DE DESSIN. */
const DECALAGE_X_PX = 14;
const DECALAGE_Y_PX = 12;

/** L'identifiant du `div` — un seul par atelier, réutilisé s'il existe déjà. */
export const ID_INFO_BULLE_OMBRAGE = 'rp11-ombrage-bulle';

export interface InfoBulleOmbrage {
  /** Affiche le texte de CE module au point écran donné. Sans texte, elle se CACHE
   *  (un module hors plan n'a rien à dire — il ne dit pas « 0 »). */
  montrer: (texte: string | null | undefined, x: number, y: number) => boolean;
  /** Cache l'info-bulle (sortie de carte, sortie du mode disposition). */
  cacher: () => void;
  /** Le texte actuellement affiché (`''` quand elle est cachée) — pour les tests. */
  texte: () => string;
  /** L'élément, ou `null` hors DOM (capture, aperçu headless). */
  element: () => HTMLElement | null;
}

export interface InfoBulleOmbrageDeps {
  /** Le parent qui reçoit le `div`. Absent ⇒ `document.body`. */
  hote?: HTMLElement | null;
}

/**
 * Crée (ou retrouve) l'info-bulle. Hors DOM, toutes les méthodes sont des no-op qui
 * renvoient `false`/`''` — le boot de capture n'a pas de document à écrire.
 */
export function creerInfoBulleOmbrage(deps: InfoBulleOmbrageDeps = {}): InfoBulleOmbrage {
  const doc = typeof document !== 'undefined' ? document : null;
  let el: HTMLElement | null = null;
  if (doc && typeof doc.createElement === 'function') {
    el = doc.getElementById(ID_INFO_BULLE_OMBRAGE);
    if (!el) {
      el = doc.createElement('div');
      el.id = ID_INFO_BULLE_OMBRAGE;
      el.className = 'rp11-ombrage-bulle pointer-events-none fixed z-50 max-w-xs px-2 py-1 text-xs';
      // `role="status"` : le texte est une LECTURE, pas une alerte — un lecteur d'écran
      // l'annonce sans interrompre. `hidden` tant que rien n'est survolé.
      el.setAttribute('role', 'status');
      el.hidden = true;
      (deps.hote ?? doc.body)?.appendChild(el);
    }
  }

  function cacher() {
    if (!el) return;
    el.hidden = true;
    el.textContent = '';
  }

  function montrer(texte: string | null | undefined, x: number, y: number): boolean {
    if (!el) return false;
    const propre = typeof texte === 'string' ? texte.trim() : '';
    if (!propre) {
      cacher();
      return false;
    }
    el.textContent = propre;
    el.hidden = false;
    if (Number.isFinite(x)) el.style.left = `${Math.round(x) + DECALAGE_X_PX}px`;
    if (Number.isFinite(y)) el.style.top = `${Math.round(y) + DECALAGE_Y_PX}px`;
    return true;
  }

  return {
    montrer,
    cacher,
    texte: () => (el && !el.hidden ? el.textContent ?? '' : ''),
    element: () => el,
  };
}
