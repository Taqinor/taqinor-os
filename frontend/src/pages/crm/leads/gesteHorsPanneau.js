// EDC6 (suite, mesuré en direct le 09/10/2026) — MODULE PUR.
// Radix DIFFÈRE le rappel « pointeur hors panneau » sur un pointeur tactile
// (`deferPointerDownOutside` : reporté à l'événement `click`). Un tap sur
// « Rester » DANS la boîte de confirmation la ferme d'abord ; le rappel
// différé arrive ensuite, alors que cette couche a disparu et que le panneau
// est redevenu la couche la plus haute : il prenait ce tap pour un tap sur le
// voile et REDEMANDAIT la confirmation — la boîte ne se fermait jamais.
// Une cible déjà décrochée du document, ou qui vit dans une autre couche
// (confirmation, dialogue, popover), n'est jamais un geste de sortie.
// Fichier séparé du composant : `react-refresh/only-export-components`.

/**
 * Un « pointeur hors panneau » rapporté par Radix est-il un VRAI geste de
 * sortie (voile) ? Non si la cible n'est plus dans le document (sa couche vient
 * de se fermer) ni si elle vit dans une autre couche que le panneau lui-même.
 *
 * @param {Element|null} cible   cible de l'événement d'origine
 * @param {Element|null} panneau nœud du panneau (SheetContent)
 * @returns {boolean}
 */
export function estGesteHorsPanneau(cible, panneau) {
  if (!cible || typeof cible.closest !== 'function') return true
  if (cible.isConnected === false) return false
  const couche = cible.closest('[role="alertdialog"], [role="dialog"], [data-radix-popper-content-wrapper]')
  if (!couche) return true
  return Boolean(panneau) && couche === panneau
}

