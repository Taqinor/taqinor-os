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

// ERR-SAV-TECH-USERS-403 — `GET /users/` (liste des comptes) est réservé au
// palier admin ou à `users_gerer` (authentication/views.py, ASEC10) : tout écran
// qui peuple un sélecteur d'utilisateurs n'appelle l'endpoint que si ce hook dit oui.
export function useCanListUsers() {
  const estAdmin = useHasRole(['admin'])
  const aUsersGerer = useHasPermission('users_gerer')
  return estAdmin || aUsersGerer
}

// NTOBS21 — règle serveur : `core.maintenance_windows.FiabilitePermission` (lecture) :
// Directeur/Administrateur, palier admin, ou `fiabilite_voir`/`fiabilite_administration`.
export function useCanLireFiabilite() {
  const estAdmin = useHasRole(['admin'])
  const roleDirection = useHasPermission(null, ['Directeur', 'Administrateur'])
  const voir = useHasPermission('fiabilite_voir')
  const administrer = useHasPermission('fiabilite_administration')
  return estAdmin || roleDirection || voir || administrer
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

// ERR-PARAM-ASSIGNABLE-USERS-403 — `GET /crm/assignable-users/` est gardé par
// IsResponsableOrAdmin (authentication/permissions.py, ASEC11) : pour un rôle
// fin non administrateur, il faut au moins un code du module `crm`
// (`crm_*`, apps/roles/permissions_registre.py) ; le palier admin et le
// compte hérité sans rôle fin (palier responsable) passent. Un Admin RH n'y a
// pas droit : l'écran ne doit pas appeler l'endpoint (403 en console).
export function useCanListAssignableUsers() {
  const role = useSelector((s) => s.auth.role)
  const roleNom = useSelector((s) => s.auth.role_nom)
  const permissions = useSelector((s) => s.auth.permissions) || []
  if (role === 'admin') return true
  if (role === 'responsable' && !roleNom && permissions.length === 0) return true
  return permissions.some((c) => typeof c === 'string' && c.startsWith('crm_'))
}

// ERR-ASEC11-LECTURE-FACTURES, ADVS23 — la règle de `LectureVentes`
// (apps/ventes/gardes_lecture.py) : lire les devis et les factures exige, pour un
// rôle fin, AU MOINS UN code du module `ventes` (`ventes_*` + `encaisser`,
// apps/roles/permissions_registre.py) : Commercial terrain, Admin RH, Technicien
// → 403. Palier admin et compte hérité sans rôle fin (aucun role_nom, aucune
// permission) passent, comme côté serveur.
export function useCanLireVentes() {
  const role = useSelector((s) => s.auth.role)
  const roleNom = useSelector((s) => s.auth.role_nom)
  const permissions = useSelector((s) => s.auth.permissions) || []
  if (role === 'admin') return true
  if (!roleNom && permissions.length === 0) return true
  return permissions.some((c) => typeof c === 'string'
    && (c.startsWith('ventes_') || c === 'encaisser'))
}

// ERR-ACC-ACCUEIL-403-LECTEUR — règle serveur : `CustomUser.is_responsable`
// (authentication/models.py, ERR4) : un rôle fin n'est « responsable » que s'il
// porte AU MOINS UN code d'écriture/gestion (ni `*_voir`/`*_view`, ni marqueur
// `records_scope*`, ni `portail_*`) ; un compte hérité sans rôle fin suit son
// palier (`state.auth.role`). Un Lecteur (Viewer, que des `*_voir`) est donc
// refusé (403) par toute garde `IsResponsableOrAdmin` : l'écran n'appelle pas.
function estResponsable(role, roleNom, permissions) {
  if (role === 'admin') return true
  if (!roleNom && permissions.length === 0) return role === 'responsable'
  return permissions.some((c) => typeof c === 'string'
    && !c.endsWith('_voir') && !c.endsWith('_view')
    && !c.startsWith('records_scope') && !c.startsWith('portail_'))
}

// `GET /monitoring/configs/co2-fleet/` (ImpactPastille) : `IsResponsableOrAdmin`
// sur le module `sav` (`MonitoringConfigViewSet.permission_module`, AMON45) :
// responsable ET, pour un rôle fin non admin, au moins un code du module `sav`
// (`sav_*`, `equipement_voir`/`equipement_gerer` — PERMISSION_MODULE de
// apps/roles/permissions_registre.py, lecture comprise). Admin Ventes et
// Commercial terrain n'en portent aucun : 403 (ERR-ACC-SIDEBAR-CO2-403).
export function useCanLireParcMonitoring() {
  const role = useSelector((s) => s.auth.role)
  const roleNom = useSelector((s) => s.auth.role_nom)
  const permissions = useSelector((s) => s.auth.permissions) || []
  if (role === 'admin') return true
  if (!estResponsable(role, roleNom, permissions)) return false
  if (!roleNom && permissions.length === 0) return true
  return permissions.some((c) => typeof c === 'string'
    && (c.startsWith('sav_') || c === 'equipement_voir' || c === 'equipement_gerer'))
}

// `GET /crm/equipes/statistiques/` (MesEquipesCard) : `IsResponsableOrAdmin`
// sur le module `crm` : responsable ET, pour un rôle fin non admin, au moins un
// code `crm_*` (lecture comprise).
export function useCanLireEquipesCrm() {
  const role = useSelector((s) => s.auth.role)
  const roleNom = useSelector((s) => s.auth.role_nom)
  const permissions = useSelector((s) => s.auth.permissions) || []
  if (role === 'admin') return true
  if (!estResponsable(role, roleNom, permissions)) return false
  if (!roleNom && permissions.length === 0) return true
  return permissions.some((c) => typeof c === 'string' && c.startsWith('crm_'))
}

export const useCanListFactures = useCanLireVentes

export default useHasPermission
