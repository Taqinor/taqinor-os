/**
 * QJW8 — LE MOTEUR GÉNÉRIQUE APPLIQUER / RESTAURER DE LA PAGE PROPOSITION.
 *
 * CE QUE CE MODULE EST. Les quatre gestes que « charger une autre taille »
 * demande, écrits UNE fois et pilotés par les tables de `liaisons.ts` (QJW7) :
 * moissonner les originaux, appliquer un détail servi, restaurer la page dans
 * l'état exact de son chargement, marquer l'attente réseau.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * LA RÈGLE FONDATRICE DE CETTE PAGE, ENCODÉE ICI UNE FOIS POUR TOUTES.
 *
 *   UN `lire` QUI REND `null` CACHE L'ENVELOPPE. IL NE SUBSTITUE JAMAIS UNE
 *   VALEUR, ET IL NE RELIT JAMAIS L'ORIGINAL SOUS UNE AUTRE CARTE.
 *
 * Pourquoi elle est absolue. La page est rendue au serveur avec les nombres du
 * DEVIS OFFICIEL. Quand le client clique « Éco » ou « Max », tout champ que la
 * taille chargée ne sert PAS doit DISPARAÎTRE. Le repli « tant pis, on remet
 * l'original » écrirait un nombre RÉEL sous une carte qui n'est pas la sienne —
 * un mensonge de plus, pas de moins. C'est le bug que la page a déjà corrigé à
 * la main, deux fois, dans deux fonctions différentes (« JAMAIS un readback sur
 * l'original sous une autre carte — le bug corrigé par cette revue » ; « Le
 * laisser afficher les douze mois du devis officiel sous une autre carte serait
 * un chiffre réel attribué à la mauvaise offre »). Ici, aucune liaison future
 * ne peut se tromper : la branche `null` n'appelle PAS `peindre` et ne touche
 * AUCUN nœud — elle ne fait que masquer.
 *
 * Le seul chemin qui réécrit les originaux est `restaurer()`, et il n'est
 * appelé que pour « Recommandé » + la variante par défaut, c'est-à-dire pour la
 * carte à qui ces nombres appartiennent VRAIMENT.
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * CE QU'IL NE FAIT PAS. Aucun calcul, aucun formatage : tout cela vit dans les
 * `peindre` des tables, qui appellent les fonctions du rendu serveur. Le moteur
 * ne connaît que des sélecteurs, du texte et une visibilité.
 */

import type { Liaison, ModeCapture, NoeudsResolus, SpecNoeud, SpecNoeuds } from './liaisons';

/** L'état d'UN nœud au chargement : son contenu ET sa visibilité. */
export interface OriginalNoeud {
  readonly contenu: string | null;
  /** `hidden` tel que le serveur l'a rendu — restauré tel quel, jamais forcé. */
  readonly cache: boolean;
}

// Volontairement un tableau MUTABLE (et non `readonly`) : `Array.isArray` ne
// discrimine pas une union portant un `readonly T[]`, et ce discriminant est ce
// qui apparie un sélecteur multiple (les douze mois) à ses douze originaux.
type OriginalEntree = OriginalNoeud | OriginalNoeud[];

export interface OriginauxLiaison {
  readonly noeuds: Readonly<Record<string, OriginalEntree>>;
  /** `null` = pas d'enveloppe déclarée, ou enveloppe absente du document. */
  readonly enveloppeCachee: boolean | null;
}

/** Les originaux de TOUTES les liaisons, indexés par `cle`. */
export type Originaux = ReadonlyMap<string, OriginauxLiaison>;

const modeDe = (spec: SpecNoeud): ModeCapture => spec.capture ?? 'texte';

function resoudreUn(racine: ParentNode, spec: SpecNoeud): Element | Element[] | null {
  if (spec.tous) return Array.from(racine.querySelectorAll(spec.sel));
  return racine.querySelector(spec.sel);
}

/** Les nœuds d'une liaison, résolus dans le document (ou un conteneur de test). */
function resoudre(noeuds: SpecNoeuds, racine: ParentNode): NoeudsResolus {
  const out: Record<string, Element | Element[] | null> = {};
  for (const nom of Object.keys(noeuds)) {
    const spec = noeuds[nom];
    out[nom] = spec ? resoudreUn(racine, spec) : null;
  }
  return out;
}

function enveloppeDe(selecteur: string | undefined, racine: ParentNode): HTMLElement | null {
  if (!selecteur) return null;
  const n = racine.querySelector(selecteur);
  return n instanceof HTMLElement ? n : null;
}

function moissonner(el: Element, spec: SpecNoeud): OriginalNoeud {
  const mode = modeDe(spec);
  const contenu = mode === 'texte'
    ? el.textContent
    : mode === 'html'
      ? el.innerHTML
      : el.getAttribute(mode.attribut);
  return { contenu, cache: el instanceof HTMLElement ? el.hidden : false };
}

function reposer(el: Element, spec: SpecNoeud, orig: OriginalNoeud): void {
  const mode = modeDe(spec);
  if (mode === 'texte') el.textContent = orig.contenu;
  else if (mode === 'html') el.innerHTML = orig.contenu ?? '';
  else if (orig.contenu !== null) el.setAttribute(mode.attribut, orig.contenu);
  else el.removeAttribute(mode.attribut);
  if (el instanceof HTMLElement) el.hidden = orig.cache;
}

/**
 * Moissonne l'état de chargement de TOUS les nœuds pilotés, en UNE passe.
 *
 * C'est ce qui rend le retour sur « Recommandé » exact : la page n'a rien à
 * reconstruire, elle repose ce que le serveur avait rendu — y compris le corps
 * HTML du tableau année par année et l'attribut géométrique de l'anneau. À
 * appeler UNE fois, à l'initialisation, avant que quoi que ce soit ne bouge.
 */
export function capturerOriginaux<C>(
  liaisons: readonly Liaison<C>[],
  racine: ParentNode = document,
): Originaux {
  const map = new Map<string, OriginauxLiaison>();
  for (const l of liaisons) {
    const resolus = resoudre(l.noeuds, racine);
    const etat: Record<string, OriginalEntree> = {};
    for (const nom of Object.keys(l.noeuds)) {
      const spec = l.noeuds[nom];
      const cible = resolus[nom];
      if (!spec || cible == null) continue;
      etat[nom] = Array.isArray(cible)
        ? cible.map((el) => moissonner(el, spec))
        : moissonner(cible, spec);
    }
    const env = enveloppeDe(l.enveloppe, racine);
    map.set(l.cle, { noeuds: etat, enveloppeCachee: env ? env.hidden : null });
  }
  return map;
}

/**
 * Applique un contexte servi (le détail d'une taille, ou le texte déjà rendu
 * par la carte choisie) à toutes les liaisons.
 *
 * LA BRANCHE `null` EST LA RAISON D'ÊTRE DE CE MODULE : elle masque et sort.
 * Elle n'appelle pas `peindre`, ne lit aucun original, n'écrit aucun nœud.
 * L'enveloppe n'est démasquée qu'APRÈS que `peindre` a posé la vraie valeur —
 * jamais un bloc visible une frame avec le chiffre de la carte précédente.
 */
export function appliquer<C>(
  liaisons: readonly Liaison<C>[],
  contexte: C,
  racine: ParentNode = document,
): void {
  for (const l of liaisons) {
    const env = enveloppeDe(l.enveloppe, racine);
    const valeur = l.lire(contexte);
    if (valeur === null || valeur === undefined) {
      if (env) env.hidden = true;
      continue;
    }
    l.peindre(resoudre(l.noeuds, racine), valeur);
    if (env) env.hidden = false;
  }
}

/**
 * Remet la page EXACTEMENT dans l'état de son chargement : chaque nœud retrouve
 * son contenu ET sa visibilité d'origine, chaque enveloppe la sienne, et toute
 * marque d'attente disparaît. Réservé à « Recommandé » + variante par défaut —
 * la seule carte à qui ces nombres appartiennent.
 */
export function restaurer<C>(
  liaisons: readonly Liaison<C>[],
  originaux: Originaux,
  racine: ParentNode = document,
): void {
  for (const l of liaisons) {
    const memoire = originaux.get(l.cle);
    if (!memoire) continue;
    const resolus = resoudre(l.noeuds, racine);
    for (const nom of Object.keys(l.noeuds)) {
      const spec = l.noeuds[nom];
      const cible = resolus[nom];
      const orig = memoire.noeuds[nom];
      if (!spec || cible == null || orig === undefined) continue;
      if (Array.isArray(cible) && Array.isArray(orig)) {
        cible.forEach((el, i) => {
          const o = orig[i];
          if (o) reposer(el, spec, o);
        });
      } else if (!Array.isArray(cible) && !Array.isArray(orig)) {
        reposer(cible, spec, orig);
      }
    }
    const env = enveloppeDe(l.enveloppe, racine);
    if (env) {
      env.removeAttribute('aria-busy');
      if (memoire.enveloppeCachee !== null) env.hidden = memoire.enveloppeCachee;
    }
  }
}

/**
 * ÉTAT DE CHARGEMENT — ET IL MASQUE, IL NE GRISE PAS.
 *
 * Pendant l'appel réseau, les chapitres portent encore les nombres du DEVIS
 * OFFICIEL. Les laisser lisibles — même atténués — sous une carte Éco ou Max,
 * c'est afficher un chiffre réel attribué à la mauvaise offre : exactement ce
 * que cette page corrige partout ailleurs. On les masque donc, en annonçant
 * l'attente aux lecteurs d'écran (`aria-busy`).
 *
 * La sortie de chargement ne DÉMASQUE rien : c'est `appliquer` (ou
 * `restaurer`) qui décide, champ par champ, de ce qui a le droit de revenir.
 */
export function marquerChargement<C>(
  liaisons: readonly Liaison<C>[],
  enCours: boolean,
  racine: ParentNode = document,
): void {
  for (const l of liaisons) {
    const env = enveloppeDe(l.enveloppe, racine);
    if (!env) continue;
    if (enCours) {
      env.setAttribute('aria-busy', 'true');
      env.hidden = true;
    } else {
      env.removeAttribute('aria-busy');
    }
  }
}
