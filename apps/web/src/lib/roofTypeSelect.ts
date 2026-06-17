/**
 * Sélecteur « type de toit » (plat ↔ en pente / tuiles) — propriétaire UNIQUE des
 * puces `[data-rooftype]` de /preview/toiture-3d-pro-9.
 *
 * POURQUOI CE MODULE EXISTE. La carte « Étape 2 · type de toit » (#rp9-rooftype-first)
 * invite l'utilisateur à choisir le type de toit AVANT de tracer — donc avant que
 * l'outil 3D lourd (Three.js + MapLibre) ne soit téléchargé paresseusement. Or, dans
 * pro-8/pro-9, le câblage des puces vivait À L'INTÉRIEUR de `initRoofToolPro8`, qui ne
 * s'exécute qu'après le boot de la carte (soumission de l'adresse ou « ouvrir la
 * carte »). Résultat : taper « Toit en pente » sur la page fraîche ne déclenchait
 * AUCUN gestionnaire — bouton inerte, sur mobile comme sur desktop.
 *
 * Ce contrôleur câble TOUTES les puces `[data-rooftype]` (la carte d'étape ET le
 * panneau de config post-tracé) DÈS le chargement de la page. Il détient l'état
 * canonique du type de toit et reflète `aria-pressed` sur chaque puce. L'outil 3D,
 * quand il finit par booter, s'ABONNE (au lieu de re-câbler) pour appliquer ses effets
 * (afficher les contrôles pente, recalcul PVGIS…). Un seul propriétaire ⇒ aucune
 * divergence, aucun double gestionnaire.
 *
 * Aucune dépendance, surface DOM minimale (lit via getAttribute) : il s'exécute aussi
 * bien contre le vrai `document` que contre un stub de test léger — l'outil lourd n'a
 * jamais besoin de booter pour prouver que le clic fonctionne.
 */
export type RoofType = 'flat' | 'pitched';

/** Sous-ensemble minimal d'un bouton/puce dont ce contrôleur a besoin. */
export interface RoofTypeButton {
  getAttribute(name: string): string | null;
  setAttribute(name: string, value: string): void;
  addEventListener(type: 'click', handler: () => void): void;
}

/** Sous-ensemble minimal du document (le vrai `document` y est assignable). */
export interface RoofTypeDocument {
  querySelectorAll(selectors: string): ArrayLike<RoofTypeButton>;
}

export interface RoofTypeSelect {
  /** Type de toit canonique courant. */
  get(): RoofType;
  /** Force le type de toit par programme (reflète les puces + notifie les abonnés). */
  set(t: RoofType): void;
  /** S'abonne aux changements (l'outil 3D applique ses effets ici). */
  subscribe(fn: (t: RoofType) => void): void;
}

const isRoofType = (v: string | null): v is RoofType => v === 'flat' || v === 'pitched';

/**
 * Crée et CÂBLE (immédiatement) le sélecteur de type de toit. Chaque puce
 * `[data-rooftype]` reçoit un gestionnaire de clic qui bascule l'état partagé et met à
 * jour `aria-pressed` sur TOUTES les puces. À créer EAGERLY dans le script de page,
 * avant le boot de l'outil lourd.
 */
export function createRoofTypeSelect(doc: RoofTypeDocument): RoofTypeSelect {
  const buttons = Array.from(doc.querySelectorAll('[data-rooftype]'));
  const subscribers: Array<(t: RoofType) => void> = [];

  // État de départ = la puce que le markup pré-active (défaut « flat »).
  let current: RoofType = 'flat';
  for (const b of buttons) {
    if (b.getAttribute('aria-pressed') === 'true' && isRoofType(b.getAttribute('data-rooftype'))) {
      current = b.getAttribute('data-rooftype') as RoofType;
    }
  }

  const sync = () => {
    for (const b of buttons) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-rooftype') === current));
    }
  };

  const set = (t: RoofType) => {
    if (!isRoofType(t) || t === current) {
      sync();
      return;
    }
    current = t;
    sync();
    for (const fn of subscribers) fn(current);
  };

  for (const b of buttons) {
    // Un tap (mobile) comme un clic (desktop) déclenchent l'événement 'click' du
    // navigateur — un seul gestionnaire couvre donc les deux plateformes.
    b.addEventListener('click', () => {
      const t = b.getAttribute('data-rooftype');
      if (isRoofType(t)) set(t);
    });
  }

  sync();

  return {
    get: () => current,
    set,
    subscribe: (fn) => {
      subscribers.push(fn);
    },
  };
}
