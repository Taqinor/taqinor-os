import { useSelector } from 'react-redux'
import { useHasPermission } from '../../hooks/useHasPermission'

/**
 * ASTK21 (D-ASTK-3) — l'utilisateur porte-t-il le code achats `code`
 * (`achats_commander`, `achats_receptionner`, `achats_payer`,
 * `catalogue_prix_modifier`, `prix_achat_voir`) ?
 *
 * Compte à rôle fin (codes ERP présents) : le code décide — un geste que le
 * serveur refuserait (403) n'est jamais affiché. Compte légacy SANS codes :
 * comportement historique conservé (le serveur arbitre par son repli
 * `HasPermissionOrLegacy` / `can_view_buy_prices`).
 */
export function usePermissionAchats(code) {
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const viaPermission = useHasPermission(code)
  return hasFinePermissions ? viaPermission : true
}

/**
 * ASTK15 (D-ASTK-2) — l'utilisateur voit-il les prix et montants d'ACHAT ?
 * Miroir front de `User.can_view_buy_prices`. Sans ce droit, le serveur
 * RETIRE les clés de prix : l'écran affiche « — », masque les gestes qui
 * n'existent que pour les prix (PDF interne, historique, tarifs, accords) et
 * n'envoie jamais de prix.
 */
export function useVoitPrixAchat() {
  return usePermissionAchats('prix_achat_voir')
}

/**
 * D-ACAL-152 — l'utilisateur voit-il les prix de VENTE du catalogue ?
 * Miroir front de `User.can_view_sale_prices` (code `prix_vente_voir`, porté
 * par tous les rôles sauf Technicien et Technicien responsable). Sans ce
 * droit, le serveur RETIRE les clés de prix de vente : l'écran ne rend pas les
 * colonnes de prix (jamais une colonne de « — ») et ne montre aucun prix.
 *
 * `produits` (facultatif) : le serveur fait foi — dès qu'un produit servi
 * porte la clé `prix_vente`, les prix sont affichés, quel que soit le code.
 */
export function useVoitPrixVente(produits) {
  const droit = usePermissionAchats('prix_vente_voir')
  return droit || (Array.isArray(produits) && produits.some((p) => p != null && 'prix_vente' in p))
}

export default useVoitPrixAchat
