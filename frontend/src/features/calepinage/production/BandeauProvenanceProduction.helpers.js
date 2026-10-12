// ENF22 — helpers extraits de BandeauProvenanceProduction.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/* ============================================================================
   ACAL52 — LA BORNE HAUTE ET LES RÉGLAGES UTILISÉS, DITS SUR L'ÉCRAN.
   ----------------------------------------------------------------------------
   `production.total.complete === false` (ACAL49) veut dire que des postes de
   perte du socle n'ont pas été renseignés : le P50 servi est une BORNE HAUTE.
   Le bandeau reprend la mention SERVIE, la liste `socle_manquant` et le lien
   vers les réglages ; PR / P75 / P90 / P95 s'affichent « — non publié » (motif
   en infobulle), jamais un nombre. Rien n'est recalculé ici : la complétude est
   celle du serveur. `complete === true` : ni bandeau ni masquage.
   ========================================================================== */

/** Résultat simulé mais incomplet : le P50 existe, le socle de pertes non. */
export function estIncomplet(total) {
  return Boolean(total) && total.complete === false
    && total.p50_kwh !== null && total.p50_kwh !== undefined
}
