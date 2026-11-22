/**
 * ACAL414 — LA TABLE UNIQUE DES RACCOURCIS DE L'ATELIER.
 *
 * Trois endroits disaient ce que fait une touche (`clavier.ts::PLAN_CLAVIER`, l'aide React
 * `RaccourcisAtelier.helpers.js::RACCOURCIS`, le keydown de `layoutEditor.ts`). Ils lisent
 * désormais cette seule table : ajouter une touche = ajouter une ligne ici, elle apparaît dans
 * l'aide. Données pures — aucun import, aucune dépendance.
 */

/** Où la touche agit : un mode de tracé, le panneau de disposition, ou l'écran de l'atelier. */
export type PorteeRaccourci = 'trace' | 'mesure' | 'obstacle' | 'zone' | 'disposition' | 'atelier';

export interface LigneRaccourci {
  portees: readonly PorteeRaccourci[];
  /** Valeurs de `KeyboardEvent.key` reconnues (portées disposition/atelier : minuscules). */
  touches: readonly string[];
  modificateurs?: { shift?: boolean; ctrl?: boolean; alt?: boolean };
  action: string;
  libelle: string;
  ecriture: string;
  /** Le geste retire quelque chose. */
  destructif?: boolean;
}

const MODES_TRACE = ['trace', 'mesure', 'obstacle', 'zone'] as const;

export const TABLE_RACCOURCIS: readonly LigneRaccourci[] = [
  { portees: MODES_TRACE, touches: ['ArrowUp'], action: 'curseur-nord', libelle: 'Déplacer le curseur de pose vers le nord', ecriture: '↑' },
  { portees: MODES_TRACE, touches: ['ArrowDown'], action: 'curseur-sud', libelle: 'Déplacer le curseur de pose vers le sud', ecriture: '↓' },
  { portees: MODES_TRACE, touches: ['ArrowRight'], action: 'curseur-est', libelle: 'Déplacer le curseur de pose vers l’est', ecriture: '→' },
  { portees: MODES_TRACE, touches: ['ArrowLeft'], action: 'curseur-ouest', libelle: 'Déplacer le curseur de pose vers l’ouest', ecriture: '←' },
  { portees: MODES_TRACE, touches: ['ArrowUp'], modificateurs: { shift: true }, action: 'curseur-nord', libelle: 'Déplacer le curseur vers le nord, d’un pas rapide', ecriture: 'Maj + ↑' },
  { portees: MODES_TRACE, touches: ['ArrowDown'], modificateurs: { shift: true }, action: 'curseur-sud', libelle: 'Déplacer le curseur vers le sud, d’un pas rapide', ecriture: 'Maj + ↓' },
  { portees: MODES_TRACE, touches: ['ArrowRight'], modificateurs: { shift: true }, action: 'curseur-est', libelle: 'Déplacer le curseur vers l’est, d’un pas rapide', ecriture: 'Maj + →' },
  { portees: MODES_TRACE, touches: ['ArrowLeft'], modificateurs: { shift: true }, action: 'curseur-ouest', libelle: 'Déplacer le curseur vers l’ouest, d’un pas rapide', ecriture: 'Maj + ←' },
  { portees: MODES_TRACE, touches: ['Enter'], action: 'poser', libelle: 'Poser un sommet du contour, ou un point de mesure', ecriture: 'Entrée' },
  { portees: MODES_TRACE, touches: ['Enter'], modificateurs: { ctrl: true }, action: 'terminer', libelle: 'Fermer le contour (ou terminer la mesure en cours)', ecriture: 'Ctrl + Entrée' },
  { portees: MODES_TRACE, touches: ['Backspace'], action: 'annuler-dernier', libelle: 'Annuler le dernier point posé', ecriture: 'Retour arrière', destructif: true },
  { portees: MODES_TRACE, touches: ['Delete'], action: 'supprimer', libelle: 'Retirer l’élément sélectionné', ecriture: 'Suppr', destructif: true },
  { portees: MODES_TRACE, touches: ['Escape'], action: 'sortir', libelle: 'Sortir du mode en cours (rien n’est posé)', ecriture: 'Échap' },
  { portees: MODES_TRACE, touches: ['?', 'F1'], action: 'aide', libelle: 'Afficher ou masquer la liste des raccourcis', ecriture: '? (ou F1)' },
  // Disposition (panneau de calepinage) : lu par `actionDisposition` depuis layoutEditor.ts.
  { portees: ['disposition'], touches: ['z'], modificateurs: { ctrl: true }, action: 'annuler', libelle: 'Annuler la dernière modification de la disposition', ecriture: 'Ctrl + Z' },
  { portees: ['disposition'], touches: ['y'], modificateurs: { ctrl: true }, action: 'refaire', libelle: 'Rétablir la modification annulée', ecriture: 'Ctrl + Y' },
  { portees: ['disposition'], touches: ['z'], modificateurs: { ctrl: true, shift: true }, action: 'refaire', libelle: 'Rétablir la modification annulée', ecriture: 'Ctrl + Maj + Z' },
  // Écran de l'atelier (aide React) : touches en minuscules, comparées sans casse.
  { portees: ['atelier'], touches: ['t'], action: 'outilTrace', libelle: 'Outil tracé de toit', ecriture: 'T' },
  { portees: ['atelier'], touches: ['o'], action: 'outilObstacle', libelle: 'Outil obstacle', ecriture: 'O' },
  { portees: ['atelier'], touches: ['z'], action: 'outilZone', libelle: 'Outil zone', ecriture: 'Z' },
  { portees: ['atelier'], touches: ['m'], action: 'outilMesure', libelle: 'Outil mesure', ecriture: 'M' },
  { portees: ['atelier'], touches: ['a'], action: 'aimantation', libelle: 'Activer ou couper l’aimantation', ecriture: 'A' },
  { portees: ['atelier'], touches: ['delete'], action: 'supprimer', libelle: 'Supprimer la sélection', ecriture: 'Suppr', destructif: true },
  { portees: ['atelier'], touches: ['d'], modificateurs: { ctrl: true }, action: 'dupliquer', libelle: 'Dupliquer l’obstacle sélectionné', ecriture: 'Ctrl + D' },
  { portees: ['atelier'], touches: ['c'], modificateurs: { ctrl: true }, action: 'copier', libelle: 'Copier les panneaux sélectionnés (placement libre)', ecriture: 'Ctrl + C' },
  { portees: ['atelier'], touches: ['v'], modificateurs: { ctrl: true }, action: 'coller', libelle: 'Coller les panneaux copiés au curseur', ecriture: 'Ctrl + V' },
  { portees: ['atelier'], touches: ['f'], action: 'pleinEcran', libelle: 'Plein écran', ecriture: 'F' },
];

/** Les lignes d'une portée (les modes de tracé partagent leurs lignes). */
export function lignesDePortee(portee: PorteeRaccourci): LigneRaccourci[] {
  return TABLE_RACCOURCIS.filter((l) => l.portees.includes(portee));
}

/** Le geste de disposition (`annuler` / `refaire`) que cette frappe désigne, ou null. */
export function actionDisposition(e: { key: string; shiftKey?: boolean; ctrlKey?: boolean; metaKey?: boolean }): string | null {
  const key = e.key.toLowerCase();
  const ctrl = Boolean(e.ctrlKey || e.metaKey);
  const shift = Boolean(e.shiftKey);
  const l = lignesDePortee('disposition').find(
    (r) => r.touches.includes(key) && Boolean(r.modificateurs?.ctrl) === ctrl && Boolean(r.modificateurs?.shift) === shift,
  );
  return l ? l.action : null;
}

/** ACAL553 — le geste d'atelier à Ctrl (`copier` / `coller` / …) que cette frappe désigne, ou null. */
export function actionAtelierCtrl(e: { key: string; shiftKey?: boolean; ctrlKey?: boolean; metaKey?: boolean }): string | null {
  const key = e.key.toLowerCase();
  const shift = Boolean(e.shiftKey);
  const l = lignesDePortee('atelier').find(
    (r) => r.modificateurs?.ctrl && r.touches.includes(key) && Boolean(r.modificateurs?.shift) === shift,
  );
  return l ? l.action : null;
}
