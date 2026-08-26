/* ============================================================================
   FP&A — Garde de permission côté client (WIR173/WIR198).
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
   ========================================================================== */

export const FPA_SAISIR = 'fpa_saisir'
export const FPA_VALIDER = 'fpa_valider'
export const FPA_CONSULTER_TOUT = 'fpa_consulter_tout'
export const FPA_ADMINISTRER = 'fpa_administrer'

/**
 * Vrai si `permissions` porte l'un des codes d'ÉCRITURE FP&A (saisie de
 * budget, workflow soumettre/valider/rejeter). Tolérant : `null`/`undefined`/
 * non-tableau → `false`.
 */
export function peutEcrireFpa(permissions) {
  if (!Array.isArray(permissions)) return false
  return permissions.includes(FPA_SAISIR)
    || permissions.includes(FPA_VALIDER)
    || permissions.includes(FPA_ADMINISTRER)
}

/**
 * Vrai si `permissions` porte `fpa_administrer` — gouvernance des cycles
 * (ouvrir-saisie/clore/dupliquer/export) et des départements.
 */
export function peutAdministrerFpa(permissions) {
  if (!Array.isArray(permissions)) return false
  return permissions.includes(FPA_ADMINISTRER)
}
