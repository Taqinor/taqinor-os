import { useSelector } from 'react-redux'

/**
 * QG5 / ARC47 — rôle/permission helper partagé (frontend).
 *
 * CONVENTION (ARC47) : JAMAIS de lecture directe de `state.auth` pour le
 * *gating* (afficher/masquer/désactiver une affordance selon les droits) —
 * toujours passer par ces hooks. Un écran ne doit plus écrire
 * `useSelector(s => s.auth.role) === 'admin'` ni `permissions.includes(...)`
 * pour décider d'un droit : `useHasRole`, `useHasPermission` (et les alias
 * `useIsAdmin` / `useIsAdminOrResponsable`) sont la seule surface. Cela donne
 * à YRBAC10 (parité front↔back) un point unique à tester. Lire `state.auth`
 * pour de l'AFFICHAGE (nom du rôle, avatar…) reste permis.
 *
 * Deux dimensions distinctes, alignées sur l'auth slice :
 *   - `state.auth.role`     = palier machine ('admin' / 'responsable' / 'normal',
 *                             dérivé de menu_tier). → `useHasRole`.
 *   - `state.auth.role_nom` = nom de rôle affiché ('Directeur', 'Commercial
 *                             responsable'…) + `state.auth.permissions` (codes
 *                             ERP). → `useHasPermission`.
 * (Astuce lint : un futur no-restricted-syntax pourra interdire
 * `s.auth.role`/`.permissions.includes` hors de ce fichier — hors périmètre ici.)
 *
 * Usage :
 *   const canCreateProduit = useHasPermission('stock_creer', ['Directeur', 'Commercial responsable'])
 *   const canDelete        = useHasRole(['admin'])
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

/**
 * ARC47 — gating par PALIER machine (`state.auth.role`), la garde héritée la
 * plus courante dans l'app ('admin' / 'responsable'). Sémantique identique à
 * `role === X` / `role === X || role === Y` : appartenance à la liste blanche.
 *
 *   const canDelete = useHasRole(['admin'])
 *   const canWrite  = useHasRole(['responsable', 'admin'])
 */
export function useHasRole(allowedRoles) {
  const role = useSelector((s) => s.auth.role)
  return Array.isArray(allowedRoles) ? allowedRoles.includes(role) : false
}

// Alias lisibles pour les deux paliers les plus fréquents.
export function useIsAdmin() {
  return useHasRole(['admin'])
}

export function useIsAdminOrResponsable() {
  return useHasRole(['responsable', 'admin'])
}

// QG4/QG5 — rôles autorisés à créer un produit (partagé par tous les écrans
// qui affichent une affordance « Nouveau produit »). Garder aligné avec
// PRODUIT_CREATE_PERMISSION côté backend (apps/stock/views/produit.py).
export const PRODUIT_CREATE_ROLES = ['Directeur', 'Commercial responsable']

export function useCanCreateProduit() {
  return useHasPermission('stock_creer', PRODUIT_CREATE_ROLES)
}

// VX199 — les actions VENTES sensibles (valider/accepter un devis, émettre une
// facture) sont gardées côté backend par la permission ERP fine
// `ventes_valider` (HasPermissionOrLegacy dans ventes/views/{devis,facture}.py),
// PLUS par `IsResponsableOrAdmin`. Le front doit cacher l'affordance avec
// EXACTEMENT ce code — un test d'alignement (useHasPermission.test.jsx) échoue si
// la constante front diverge du code backend. Un rôle « lecture + une écriture »
// (ex. Commercial sans ventes_valider) ne verra plus le bouton ET recevra 403
// s'il appelle l'API directement.
export const VENTES_VALIDER_PERMISSION = 'ventes_valider'

export function useCanValiderVente() {
  return useHasPermission(VENTES_VALIDER_PERMISSION)
}

export default useHasPermission
