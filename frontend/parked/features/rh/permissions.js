/* ============================================================================
   RH — Garde de permission côté client (pure, testable).
   ----------------------------------------------------------------------------
   La rémunération et la masse salariale sont des données paie SENSIBLES : elles
   ne sont visibles QUE pour les comptes portant la permission `salaires_voir`.
   Le serveur reste l'autorité (l'API rémunération renvoie 403 sans la
   permission, et le cockpit omet la masse salariale) ; ces helpers évitent
   simplement d'AFFICHER un onglet/une carte vides ou de tenter un appel voué à
   l'échec. Jamais de prix d'achat ni de marge — uniquement des montants
   client/RH légitimes.
   ========================================================================== */

export const PERM_SALAIRES_VOIR = 'salaires_voir'

/**
 * Vrai si la liste de permissions contient `salaires_voir`.
 * Tolérant : accepte `null`/`undefined`/non-tableau → `false`.
 */
export function peutVoirSalaires(permissions) {
  if (!Array.isArray(permissions)) return false
  return permissions.includes(PERM_SALAIRES_VOIR)
}
