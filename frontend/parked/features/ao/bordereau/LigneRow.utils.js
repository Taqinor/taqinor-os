/* ============================================================================
   AOF179 — Règles de provenance/verrouillage d'une ligne du bordereau.
   Extrait de LigneRow.jsx (react-refresh/only-export-components) : un fichier
   de composant ne doit exporter QUE des composants ; ces constantes/fonctions
   n'ont pas leur place là, seul le composant les consomme.
   ========================================================================== */

export const SOURCE_BADGE = {
  calepinage: { label: 'quantité issue du calepinage — verrouillée', tone: 'info' },
  acheteur: { label: 'cadre acheteur — non modifiable', tone: 'warning' },
  manuelle: { label: 'manuelle', tone: 'neutral' },
  catalogue: { label: 'catalogue', tone: 'neutral' },
}

/** Quantité modifiable ? Verrouillée par provenance (calepinage/acheteur) ou par
    le drapeau serveur, sauf déverrouillage explicite déjà tracé. */
export function quantiteVerrouillee(ligne) {
  if (ligne?.deverrouillee) return false
  if (ligne?.quantite_verrouillee) return true
  return ligne?.quantite_source === 'calepinage' || ligne?.quantite_source === 'acheteur'
}

/** Le cadre de l'acheteur fige AUSSI la désignation et l'unité (AOF121). */
export function cadreAcheteur(ligne) {
  return ligne?.quantite_source === 'acheteur' && !ligne?.deverrouillee
}
