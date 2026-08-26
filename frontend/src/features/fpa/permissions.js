import { PALIERS_LEGACY } from '../../router/moduleGating.js'

/* ============================================================================
   FP&A — Garde de permission côté client (WIR173/WIR198/WIR199).
   ----------------------------------------------------------------------------
   Miroir des codes serveur `apps/fpa/permissions.py` (FPA_SAISIR/FPA_VALIDER/
   FPA_ADMINISTRER/FPA_CONSULTER_TOUT). Le serveur reste l'autorité (403 sans
   le bon code, `FpaScopedPermission`) ; ces helpers évitent simplement
   d'afficher une affordance d'écriture vouée à l'échec.

   `FpaScopedPermission` gate TOUTES les écritures des 14 viewsets FP&A —
   y compris les actions soumettre/valider/rejeter d'une ligne de budget —
   par le MÊME tuple `write_permission = (fpa_saisir, fpa_valider,
   fpa_administrer)` : il n'existe pas de garde plus fine par action côté
   serveur, donc aucune ici non plus (`peutEcrireFpa`). Seules les actions de
   GOUVERNANCE d'un cycle (ouvrir-saisie/clore/dupliquer/export) exigent
   spécifiquement `fpa_administrer` (`ExigeFpaPermission`), reflété par
   `peutAdministrerFpa`.

   REPLI LÉGACY (fixé après revue Fable, incident WIR198/199) — la moitié qui
   manquait : `porte_un_code_fpa` (apps/fpa/permissions.py) n'est PAS un
   simple `permissions.includes(code)`. Superuser → toujours vrai ; un compte
   SANS rôle fin (`role is None`) → repli sur le palier historique
   responsable/admin (`user.is_responsable`) ; SEUL un compte AVEC un rôle fin
   doit réellement porter l'un des codes. Les codes `fpa_*` n'étant entrés au
   catalogue QUE dans ce batch (aucun rôle existant ne les porte), un
   `permissions.includes(...)` nu aurait rendu tout le workflow FP&A invisible
   à TOUT compte légacy Responsable/Admin ET à tout superuser — exactement les
   comptes que le serveur sert.

   Là où `porte_un_code_fpa` lit `role is None`, le client lit exactement le
   même signal via `permissions` VIDE (`UserSerializer.get_permissions` ne
   sert de codes QUE si un `Role` est posé — un compte légacy ou un superuser
   sans rôle assigné reçoit `[]`). Le superuser SANS rôle n'a pas besoin d'un
   drapeau dédié : `menu_tier` lui pose TOUJOURS le palier 'admin' (déjà dans
   `PALIERS_LEGACY`), donc le même repli tier+permissions-vides le couvre —
   même mécanique EXACTE que `estAutoriseEntree` (router/moduleGating.js,
   WIR171) : `permissions.length > 0 ? strict : PALIERS_LEGACY.includes(tier)`.
   `tier` = `state.auth.role` (palier machine 'admin'/'responsable'/'normal').
   ========================================================================== */

export const FPA_SAISIR = 'fpa_saisir'
export const FPA_VALIDER = 'fpa_valider'
export const FPA_CONSULTER_TOUT = 'fpa_consulter_tout'
export const FPA_ADMINISTRER = 'fpa_administrer'

/**
 * Vrai si `permissions` porte l'un des codes d'ÉCRITURE FP&A (saisie de
 * budget, workflow soumettre/valider/rejeter) — ou, repli légacy, si
 * `permissions` est VIDE (aucun rôle fin — superuser sans rôle inclus) et que
 * `tier` (`state.auth.role`) est responsable/admin. Tolérant : `null`/
 * `undefined`/non-tableau traité comme vide.
 */
export function peutEcrireFpa(permissions, tier) {
  const perms = Array.isArray(permissions) ? permissions : []
  if (perms.length === 0) return PALIERS_LEGACY.includes(tier)
  return perms.includes(FPA_SAISIR)
    || perms.includes(FPA_VALIDER)
    || perms.includes(FPA_ADMINISTRER)
}

/**
 * Vrai si `permissions` porte `fpa_administrer` — gouvernance des cycles
 * (ouvrir-saisie/clore/dupliquer/export) et des départements — ou, repli
 * légacy identique à `peutEcrireFpa`, si `permissions` est vide et `tier`
 * responsable/admin (le serveur ne distingue pas plus finement : un compte
 * légacy garde son accès historique complet, gouvernance comprise).
 */
export function peutAdministrerFpa(permissions, tier) {
  const perms = Array.isArray(permissions) ? permissions : []
  if (perms.length === 0) return PALIERS_LEGACY.includes(tier)
  return perms.includes(FPA_ADMINISTRER)
}
