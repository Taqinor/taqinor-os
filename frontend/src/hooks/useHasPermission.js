import { useSelector } from 'react-redux'

/**
 * QG5 — rôle/permission helper partagé (frontend).
 *
 * L'app n'avait pas de hook dédié : chaque écran relisait `state.auth.role`
 * ou `state.auth.permissions` à sa façon. Ce hook centralise la même règle
 * que le backend `HasPermissionAndRole` (authentication/permissions.py) :
 * porter le code de permission ERP demandé ET avoir un `role_nom` dans la
 * liste blanche fournie. C'est de la cohérence UX — le backend reste la
 * seule garde qui compte (QG4) ; ce hook ne fait qu'éviter d'afficher un
 * bouton que le serveur refuserait de toute façon.
 *
 * Usage :
 *   const canCreateProduit = useHasPermission('stock_creer', ['Directeur', 'Commercial responsable'])
 */
export function useHasPermission(permissionCode, allowedRoleNames) {
  const permissions = useSelector((s) => s.auth.permissions) || []
  const roleNom = useSelector((s) => s.auth.role_nom)

  const hasCode = permissionCode ? permissions.includes(permissionCode) : true
  const hasRole = Array.isArray(allowedRoleNames) && allowedRoleNames.length
    ? allowedRoleNames.includes(roleNom)
    : true

  return hasCode && hasRole
}

// QG4/QG5 — rôles autorisés à créer un produit (partagé par tous les écrans
// qui affichent une affordance « Nouveau produit »). Garder aligné avec
// PRODUIT_CREATE_PERMISSION côté backend (apps/stock/views/produit.py).
export const PRODUIT_CREATE_ROLES = ['Directeur', 'Commercial responsable']

export function useCanCreateProduit() {
  return useHasPermission('stock_creer', PRODUIT_CREATE_ROLES)
}

export default useHasPermission
