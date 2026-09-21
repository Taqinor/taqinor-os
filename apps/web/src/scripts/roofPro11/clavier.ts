/**
 * CALX128 — LE PLAN CLAVIER UNIFIÉ DE L'ATELIER, ET SES ANNONCES.
 *
 * Constat : les raccourcis n'existaient QUE dans le panneau de disposition — tout
 * `layoutEditor.ts` est gardé par `if (!ctx.layoutMode …) return;` — et le tracé, les
 * obstacles, les zones et la mesure n'avaient AUCUNE entrée clavier ; l'aide-mémoire de
 * l'atelier prévenait lui-même que la couverture viendrait « au fur et à mesure que
 * l'atelier les expose ». Parité Scanifly : la saisie terrain doit rester utilisable en
 * conditions dégradées, sans souris.
 *
 * DEUX RÈGLES DE CE MODULE :
 *
 * 1. **Le plan est DÉCLARATIF.** `PLAN_CLAVIER` est une table de données : une touche, ses
 *    modificateurs, les modes où elle agit, son libellé français. `aideClavier()` la rend
 *    affichable telle quelle — l'aide ne peut donc pas mentir sur ce que fait une touche,
 *    et ajouter un geste, c'est ajouter UNE ligne à la table.
 * 2. **Tout geste est ANNONCÉ, accepté comme refusé, et un refus NOMME sa raison.** Un
 *    geste qui ne passe pas ne fait jamais rien en silence (règle fondateur : l'erreur
 *    désigne ce qui bloque, jamais un « non enregistré » générique).
 *
 * Le module ne connaît NI la carte, NI Three, NI le document : les gestes lui sont
 * INJECTÉS (`GestesAtelier`). Il ne porte que des conventions de DESSIN (pas d'ingénierie) :
 * le pas du curseur est un nombre de PIXELS écran, converti en mètres au zoom courant par
 * `metresParPixel` — jamais une distance en mètres inventée.
 *
 * Les gestes souris/tactile existants sont INCHANGÉS : ce module ne fait qu'AJOUTER une
 * seconde porte d'entrée, et il se retire de lui-même dès que le focus est dans un champ
 * de saisie (sinon la saisie cotée de CALX90 et la recherche d'adresse deviendraient
 * inutilisables).
 */
import { type LngLat } from '../../lib/roof';
import { metresParPixel, pointDepuisCap } from './snap';

// ————————————————————————————————————————————————————————————————————————
// Le plan déclaratif
// ————————————————————————————————————————————————————————————————————————

/** Les modes de l'atelier qui ont une entrée clavier. `'tous'` = quel que soit le mode. */
export type ModeClavier = 'trace' | 'mesure' | 'obstacle' | 'zone';

/** Un geste NOMMÉ du plan. Les gestes sont routés vers `GestesAtelier` par leur nom. */
export type ActionClavier =
  | 'curseur-nord'
  | 'curseur-sud'
  | 'curseur-est'
  | 'curseur-ouest'
  | 'poser'
  | 'annuler-dernier'
  | 'terminer'
  | 'supprimer'
  | 'sortir'
  | 'aide';

/** Modificateurs EXIGÉS par un raccourci. Absent = la touche NUE (aucun modificateur). */
export interface Modificateurs {
  shift?: boolean;
  ctrl?: boolean;
  alt?: boolean;
}

export interface Raccourci {
  /** Valeurs de `KeyboardEvent.key` reconnues (synonymes : `Delete`/`Backspace`…). */
  touches: readonly string[];
  /** Modificateurs exigés. Omis ⇒ la touche nue ; `shift: true` ⇒ Maj obligatoire. */
  modificateurs?: Modificateurs;
  action: ActionClavier;
  /** Modes où le geste agit. Omis ⇒ TOUS les modes. */
  modes?: readonly ModeClavier[];
  /** Ce que la touche fait, en français — le texte EXACT affiché dans l'aide. */
  libelle: string;
  /** Comment la combinaison s'écrit dans l'aide (« Maj + ↑ »). */
  ecriture: string;
}

/**
 * CALX128 — LE PLAN. Une seule table, lue par `resoudreRaccourci` (routage) ET par
 * `aideClavier` (affichage) : l'aide et le comportement ne peuvent pas diverger.
 *
 * Le pas « rapide » (Maj + flèche) est la convention universelle des outils de dessin :
 * la flèche nue avance d'un pas de pointage, Maj l'accélère. C'est une convention de
 * DESSIN — elle ne change aucune dimension du document.
 */
export const PLAN_CLAVIER: readonly Raccourci[] = [
  {
    touches: ['ArrowUp'],
    action: 'curseur-nord',
    libelle: 'Déplacer le curseur de pose vers le nord',
    ecriture: '↑',
  },
  {
    touches: ['ArrowDown'],
    action: 'curseur-sud',
    libelle: 'Déplacer le curseur de pose vers le sud',
    ecriture: '↓',
  },
  {
    touches: ['ArrowRight'],
    action: 'curseur-est',
    libelle: 'Déplacer le curseur de pose vers l’est',
    ecriture: '→',
  },
  {
    touches: ['ArrowLeft'],
    action: 'curseur-ouest',
    libelle: 'Déplacer le curseur de pose vers l’ouest',
    ecriture: '←',
  },
  {
    touches: ['ArrowUp'],
    modificateurs: { shift: true },
    action: 'curseur-nord',
    libelle: 'Déplacer le curseur vers le nord, d’un pas rapide',
    ecriture: 'Maj + ↑',
  },
  {
    touches: ['ArrowDown'],
    modificateurs: { shift: true },
    action: 'curseur-sud',
    libelle: 'Déplacer le curseur vers le sud, d’un pas rapide',
    ecriture: 'Maj + ↓',
  },
  {
    touches: ['ArrowRight'],
    modificateurs: { shift: true },
    action: 'curseur-est',
    libelle: 'Déplacer le curseur vers l’est, d’un pas rapide',
    ecriture: 'Maj + →',
  },
  {
    touches: ['ArrowLeft'],
    modificateurs: { shift: true },
    action: 'curseur-ouest',
    libelle: 'Déplacer le curseur vers l’ouest, d’un pas rapide',
    ecriture: 'Maj + ←',
  },
  {
    touches: ['Enter'],
    action: 'poser',
    libelle: 'Poser un sommet du contour, ou un point de mesure',
    ecriture: 'Entrée',
  },
  {
    touches: ['Enter'],
    modificateurs: { ctrl: true },
    action: 'terminer',
    libelle: 'Fermer le contour (ou terminer la mesure en cours)',
    ecriture: 'Ctrl + Entrée',
  },
  {
    touches: ['Backspace'],
    action: 'annuler-dernier',
    libelle: 'Annuler le dernier point posé',
    ecriture: 'Retour arrière',
  },
  {
    touches: ['Delete'],
    action: 'supprimer',
    libelle: 'Retirer l’élément sélectionné',
    ecriture: 'Suppr',
  },
  {
    touches: ['Escape'],
    action: 'sortir',
    libelle: 'Sortir du mode en cours (rien n’est posé)',
    ecriture: 'Échap',
  },
  {
    touches: ['?', 'F1'],
    action: 'aide',
    libelle: 'Afficher ou masquer la liste des raccourcis',
    ecriture: '? (ou F1)',
  },
];

/** Comment les modes s'écrivent dans l'aide. */
export const LIBELLE_MODE: Readonly<Record<ModeClavier, string>> = {
  trace: 'Tracé du contour',
  mesure: 'Mesure',
  obstacle: 'Obstacles',
  zone: 'Zones',
};

/** Une ligne d'aide, prête à afficher. */
export interface LigneAide {
  touches: string;
  libelle: string;
  /** Les modes concernés, en clair — « Tous les modes » quand le geste est universel. */
  modes: string;
}

/**
 * CALX128 — l'aide affichable, DÉRIVÉE du plan (jamais une seconde liste tenue à la main).
 * Filtrée sur un mode, elle ne montre que ce qui agit RÉELLEMENT dans ce mode.
 */
export function aideClavier(mode?: ModeClavier): LigneAide[] {
  return PLAN_CLAVIER.filter((r) => !mode || !r.modes || r.modes.includes(mode)).map((r) => ({
    touches: r.ecriture,
    libelle: r.libelle,
    modes: r.modes ? r.modes.map((m) => LIBELLE_MODE[m]).join(', ') : 'Tous les modes',
  }));
}

/**
 * CALX108 — LES GESTES SOURIS À MODIFICATEUR, dans la MÊME aide.
 *
 * Un geste réservé (Alt + glissé, Alt + molette) est invisible tant qu'on ne
 * l'a pas lu quelque part : il n'a ni bouton ni curseur propre. Il vit donc
 * dans la table, à côté des touches, pour que l'aide de l'atelier le nomme.
 *
 * Il reste HORS de `PLAN_CLAVIER` : ce plan-là est lu par `resoudreRaccourci`,
 * qui capterait alors la touche Alt seule et avalerait des frappes qui ne lui
 * appartiennent pas. Deux tables, un seul affichage (`aideGestesSouris`).
 */
export interface GesteSouris {
  /** Comment le geste s'écrit dans l'aide (« Alt + glissé sur le fond »). */
  ecriture: string;
  /** Ce qu'il fait, en français — le texte EXACT affiché. */
  libelle: string;
  /** Modes où le geste agit. Omis ⇒ TOUS les modes. */
  modes?: readonly ModeClavier[];
}

/** Les gestes souris à modificateur de l'atelier. */
export const GESTES_SOURIS: readonly GesteSouris[] = [
  {
    ecriture: 'Alt + glissé sur le fond',
    libelle: 'Déplacer le calque de fond (plan calé) sans toucher à son échelle',
  },
  {
    ecriture: 'Alt + molette sur le fond',
    libelle: 'Faire pivoter le calque de fond, d’un degré par cran',
  },
];

/** CALX108 — l'aide des gestes souris, DÉRIVÉE de la table (jamais recopiée). */
export function aideGestesSouris(mode?: ModeClavier): LigneAide[] {
  return GESTES_SOURIS.filter((g) => !mode || !g.modes || g.modes.includes(mode)).map((g) => ({
    touches: g.ecriture,
    libelle: g.libelle,
    modes: g.modes ? g.modes.map((m) => LIBELLE_MODE[m]).join(', ') : 'Tous les modes',
  }));
}

/** L'événement clavier, réduit à ce que le routage lit. */
export interface EvenementClavier {
  key: string;
  shiftKey?: boolean;
  ctrlKey?: boolean;
  altKey?: boolean;
  metaKey?: boolean;
}

/** Un élément est-il un champ de SAISIE ? Le plan clavier s'y efface entièrement — sans
 *  quoi la saisie cotée (CALX90), la distance de calage (CALX108) et la recherche
 *  d'adresse deviendraient intapables. */
export function estChampDeSaisie(cible: unknown): boolean {
  const el = cible as { tagName?: string; isContentEditable?: boolean } | null | undefined;
  if (!el || typeof el.tagName !== 'string') return false;
  if (el.isContentEditable) return true;
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName.toUpperCase());
}

/**
 * CALX128 — quel geste du plan cette frappe déclenche, dans ce mode ? `null` quand aucune
 * entrée du plan ne correspond : l'événement est alors laissé INTACT au navigateur (donc
 * les gestes existants — souris, tabulation, raccourcis du panneau de disposition —
 * continuent de fonctionner exactement comme avant).
 *
 * Les modificateurs sont EXACTS : `Maj + ↑` et `↑` sont deux entrées distinctes, et
 * Ctrl/Cmd non demandé disqualifie le raccourci (sinon `Ctrl+Z` poserait un sommet).
 */
export function resoudreRaccourci(e: EvenementClavier, mode: ModeClavier): Raccourci | null {
  if (!e || typeof e.key !== 'string') return null;
  const shift = Boolean(e.shiftKey);
  // Cmd (macOS) et Ctrl se lisent de la même façon : un raccourci d'atelier n'en demande
  // jamais deux à la fois.
  const ctrl = Boolean(e.ctrlKey) || Boolean(e.metaKey);
  const alt = Boolean(e.altKey);
  for (const r of PLAN_CLAVIER) {
    if (!r.touches.includes(e.key)) continue;
    if (r.modes && !r.modes.includes(mode)) continue;
    const m = r.modificateurs ?? {};
    if (Boolean(m.shift) !== shift) continue;
    if (Boolean(m.ctrl) !== ctrl) continue;
    if (Boolean(m.alt) !== alt) continue;
    return r;
  }
  return null;
}

// ————————————————————————————————————————————————————————————————————————
// Le curseur de pose
// ————————————————————————————————————————————————————————————————————————

/**
 * Pas du curseur, en PIXELS écran. CONVENTION DE DESSIN (pas un seuil métier) : c'est le
 * rayon de pointage d'un sommet, soit le déplacement au-delà duquel l'œil voit que le
 * curseur a bougé. Converti en mètres au zoom courant par `metresParPixel` — donc aucune
 * distance en mètres n'est inventée, et le pas suit le zoom comme la souris.
 */
export const PAS_CURSEUR_PX = 8;

/** Multiplicateur du pas RAPIDE (Maj + flèche). CONVENTION DE DESSIN, convention
 *  universelle des outils de dessin (la flèche affine, Maj parcourt). */
export const FACTEUR_PAS_RAPIDE = 10;

/** Cap (° depuis le nord) de chaque déplacement du curseur. */
const CAP_PAR_ACTION: Readonly<Partial<Record<ActionClavier, number>>> = {
  'curseur-nord': 0,
  'curseur-est': 90,
  'curseur-sud': 180,
  'curseur-ouest': 270,
};

/** Le geste est-il un déplacement de curseur ? */
export function estDeplacement(action: ActionClavier): boolean {
  return action in CAP_PAR_ACTION;
}

/**
 * CALX128 — le pas du curseur EN MÈTRES au zoom et à la latitude courants. Un zoom ou une
 * latitude illisibles rendent 0 : le curseur ne bouge alors pas, plutôt que de sauter
 * d'une distance inventée.
 */
export function pasCurseurM(latDeg: number, zoom: number, rapide = false): number {
  const parPixel = metresParPixel(latDeg, zoom);
  if (!(parPixel > 0)) return 0;
  return parPixel * PAS_CURSEUR_PX * (rapide ? FACTEUR_PAS_RAPIDE : 1);
}

/**
 * CALX128 — déplace le curseur de pose d'un pas dans la direction du geste. Un pas nul ou
 * une action qui n'est pas un déplacement rendent le point TEL QUEL (même référence) : rien
 * ne bouge en silence.
 */
export function deplacerCurseur(point: LngLat, action: ActionClavier, pasM: number): LngLat {
  const cap = CAP_PAR_ACTION[action];
  if (typeof cap !== 'number') return point;
  if (!Number.isFinite(pasM) || pasM <= 0) return point;
  return pointDepuisCap(point, cap, pasM);
}

// ————————————————————————————————————————————————————————————————————————
// Les annonces (`aria-live`)
// ————————————————————————————————————————————————————————————————————————

/** Verdict d'un geste : accepté (ce qui a été fait) ou refusé (POURQUOI). */
export type VerdictGeste = { ok: true; texte: string } | { ok: false; motif: string };

export interface Annonce {
  nature: 'accepte' | 'refus';
  texte: string;
}

/** L'annonce correspondant à un verdict — un refus porte TOUJOURS sa raison. */
export function annoncePourVerdict(verdict: VerdictGeste): Annonce {
  return verdict.ok ? { nature: 'accepte', texte: verdict.texte } : { nature: 'refus', texte: verdict.motif };
}

export interface Annonceur {
  /** Publie l'annonce dans la zone `aria-live` et la mémorise. */
  annoncer: (verdict: VerdictGeste) => Annonce;
  /** La DERNIÈRE annonce publiée, ou null. */
  derniere: () => Annonce | null;
  /** La zone `aria-live`, quand le DOM a permis de la créer. */
  element: () => HTMLElement | null;
}

/** Identifiant de la zone d'annonces de l'atelier. */
export const ZONE_ANNONCE_ID = 'rp9-annonces';

/**
 * CALX128 — crée (ou retrouve) la zone `aria-live` de l'atelier. Le constructeur crée
 * LUI-MÊME son contrôle quand la page hôte ne le fournit pas (patron `obstaclesUi.ts` /
 * `zones.ts`) : aucune page n'a à être modifiée.
 *
 * `aria-live="polite"` : les annonces suivent le geste sans couper la lecture en cours.
 * Un refus est aussi `role="alert"`-isé par son préfixe textuel, jamais par un changement
 * de rôle à chaud (qui n'est pas relu de façon fiable).
 */
export function creerAnnonceur(hote?: HTMLElement | null): Annonceur {
  let derniereAnnonce: Annonce | null = null;
  let zone: HTMLElement | null = null;
  if (typeof document !== 'undefined' && typeof document.createElement === 'function') {
    zone = document.getElementById(ZONE_ANNONCE_ID);
    if (!zone) {
      const parent = hote ?? document.body ?? null;
      if (parent) {
        zone = document.createElement('p');
        zone.id = ZONE_ANNONCE_ID;
        zone.className = 'rp9-annonces sr-only';
        zone.setAttribute('aria-live', 'polite');
        zone.setAttribute('aria-atomic', 'true');
        parent.appendChild(zone);
      }
    }
  }
  function annoncer(verdict: VerdictGeste): Annonce {
    const annonce = annoncePourVerdict(verdict);
    derniereAnnonce = annonce;
    if (zone) zone.textContent = annonce.texte;
    return annonce;
  }
  return { annoncer, derniere: () => derniereAnnonce, element: () => zone };
}

// ————————————————————————————————————————————————————————————————————————
// Le routage
// ————————————————————————————————————————————————————————————————————————

/**
 * Les gestes que l'atelier expose au clavier. CHAQUE geste rend un VERDICT : c'est lui qui
 * sait pourquoi il refuse (contour fermé, point qui croiserait, rien de sélectionné…).
 * Un geste ABSENT de la table est un geste que ce mode n'expose pas — le clavier le dit,
 * il ne fait pas semblant.
 */
export type GestesAtelier = Partial<Record<ActionClavier, () => VerdictGeste>>;

export interface ClavierDeps {
  /** Le mode courant de l'atelier, relu à CHAQUE frappe (il change au fil des gestes). */
  mode: () => ModeClavier;
  /** Les gestes du mode courant. Relus à chaque frappe, pour la même raison. */
  gestes: () => GestesAtelier;
  /** Où publier les annonces. Créé par le module si absent. */
  annonceur?: Annonceur;
}

export interface Clavier {
  /** Traite une frappe. Rend l'annonce publiée, ou `null` si la frappe ne concerne pas
   *  l'atelier (laissée INTACTE au navigateur : aucun geste existant n'est volé). */
  frappe: (e: EvenementClavier & { target?: unknown; preventDefault?: () => void }) => Annonce | null;
  /** L'aide affichable du mode courant. */
  aide: () => LigneAide[];
  /** L'annonceur, pour le lire dans un test ou l'afficher. */
  annonceur: Annonceur;
}

/** Le refus type d'un geste que le mode courant n'expose pas — il NOMME le mode. */
export function motifGesteIndisponible(raccourci: Raccourci, mode: ModeClavier): string {
  return `${raccourci.ecriture} : « ${raccourci.libelle} » n’est pas disponible en mode ${LIBELLE_MODE[mode]}.`;
}

/**
 * CALX128 — le routeur. Il ne décide RIEN : il résout la frappe dans le plan, appelle le
 * geste correspondant, et annonce son verdict. Deux situations ne touchent à rien :
 *  - le focus est dans un champ de saisie (le plan s'efface entièrement) ;
 *  - aucune entrée du plan ne correspond (l'événement part intact au navigateur).
 */
export function createClavier(deps: ClavierDeps): Clavier {
  const annonceur = deps.annonceur ?? creerAnnonceur();
  function frappe(e: EvenementClavier & { target?: unknown; preventDefault?: () => void }): Annonce | null {
    if (!e) return null;
    if (estChampDeSaisie(e.target)) return null; // la saisie garde toutes ses touches
    const mode = deps.mode();
    const raccourci = resoudreRaccourci(e, mode);
    if (!raccourci) return null; // pas du plan : le navigateur garde la main
    e.preventDefault?.();
    const geste = deps.gestes()[raccourci.action];
    if (!geste) {
      return annonceur.annoncer({ ok: false, motif: motifGesteIndisponible(raccourci, mode) });
    }
    return annonceur.annoncer(geste());
  }
  return { frappe, aide: () => aideClavier(deps.mode()), annonceur };
}
