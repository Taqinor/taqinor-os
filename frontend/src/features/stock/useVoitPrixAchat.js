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

export default useVoitPrixAchat
